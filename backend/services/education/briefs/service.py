"""Daily briefs: make a draft, let an administrator edit and approve it, roll the days up, and keep only about three months.

* A brief is prepared in the school's own time zone, at the times in its settings.
* It always starts as a draft. Only an administrator's approval makes it final, and an approved brief is locked.
* The figures are counts and amounts, and the AI is only ever shown those, never a name.
* Weekly, fortnightly and monthly roll-ups are worked out from the daily briefs.
* Anything older than ``RETENTION_DAYS`` is deleted, so the oldest days are overwritten rather than piling up.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from services.core.tenants.context import use_tenant
from services.core.tenants.localization import school_locale

from . import metrics
from .models import BriefRead, BriefRollup, BriefSettings, DailyBrief

logger = logging.getLogger('erp.briefs')
RETENTION_DAYS = 92          # about three months
ANCHOR = date(2024, 1, 1)    # a Monday: fortnights are counted from here, so they are the same every year


class BriefError(Exception):
    pass


class BriefLocked(BriefError):
    """An approved brief cannot be changed."""


class NothingToSummarise(BriefError):
    pass


def school_tz(school) -> ZoneInfo:
    try:
        return ZoneInfo(school_locale(school)['timezone'])
    except Exception:
        return ZoneInfo('America/New_York')


def school_today(school, now: datetime | None = None) -> date:
    return (now or timezone.now()).astimezone(school_tz(school)).date()


def get_settings() -> BriefSettings:
    obj = BriefSettings.objects.first()
    return obj or BriefSettings.objects.create()


def system_context(school):
    """Who a scheduled run is billed to for AI use: the school's first administrator (no one is signed in at 06:30)."""
    from services.core.tenants.models import TenantMembership

    from services.ai.context import AIContext

    m = TenantMembership.objects.filter(school=school, role='admin', is_active=True).select_related('user').order_by('joined_at').first()
    return AIContext(user=m.user, role='admin', tenant=school) if m else None


def _label(day: date) -> str:
    return f"{day:%A, %B} {day.day}, {day.year}"


def _write(kind: str, day_label: str, sections: list, ctx, rate_limit: bool, school) -> tuple[str, str]:
    """(text, 'ai' | 'template'). Falls back to a plain summary of the same figures if AI is off, missing or fails."""
    from services.ai.generation import generate_brief_narrative, template_brief_narrative
    from services.ai.llm import LLMError, get_llm_client
    from services.ai.quota import AIQuotaExceeded, check_rate_limit, check_token_budget, feature_enabled, record_usage

    facts = metrics.facts_for_ai(sections)
    llm = get_llm_client() if ctx is not None else None
    if llm is not None and feature_enabled('ai_daily_brief', ctx):
        try:
            if rate_limit:
                check_rate_limit(ctx, 'ai_daily_brief')
            check_token_budget(ctx)
            out, usage, model = generate_brief_narrative(llm, kind=kind, date_label=day_label, facts=facts, region=school_locale(school)['region'])
            record_usage(ctx, 'ai_daily_brief', llm.provider, model, usage)
            return out['summary'], 'ai'
        except (AIQuotaExceeded, LLMError):
            logger.exception('Brief wording fell back to the plain summary')
    return template_brief_narrative(kind=kind, date_label=day_label, facts=facts), 'template'


def generate(school, kind: str, day: date | None = None, ctx=None, rate_limit: bool = False) -> DailyBrief:
    """Make (or remake) the draft for one kind and day. An approved brief is never touched."""
    if kind not in metrics.COLLECT:
        raise BriefError('Choose the morning brief or the evening summary.')
    with use_tenant(school):
        tz = school_tz(school)
        day = day or school_today(school)
        existing = DailyBrief.objects.filter(kind=kind, date=day).first()
        if existing and existing.status == 'approved':
            raise BriefLocked('This brief has been approved, so it cannot be changed. Delete it first to make a new one.')
        values = metrics.COLLECT[kind](day, tz)
        sections, attention = metrics.sections_for(kind, values)
        text, source = _write(kind, _label(day), sections, ctx, rate_limit, school)
        brief = existing or DailyBrief(kind=kind, date=day)
        if existing:
            existing.reads.all().delete()          # new figures, so nobody has read these yet
        brief.metrics = {'sections': sections, 'attention': attention, 'values': values}
        brief.narrative = brief.original_narrative = text
        brief.narrative_source, brief.edited, brief.status = source, False, 'draft'
        brief.approved_by, brief.approved_at = None, None
        brief.save()
        return brief


def mark_read(brief, user) -> BriefRead:
    """Stamp that this administrator has read the brief (pressing it again keeps the first time)."""
    field = 'daily' if isinstance(brief, DailyBrief) else 'rollup'
    obj, _ = BriefRead.objects.get_or_create(**{field: brief, 'user': user})
    return obj


def readers(brief) -> list[dict]:
    return [{'name': r.user.full_name or r.user.email, 'at': r.read_at, 'user': str(r.user_id)} for r in brief.reads.select_related('user')]


def edit(brief, narrative: str):
    if brief.status == 'approved':
        raise BriefLocked('This has been approved, so it cannot be edited.')
    brief.narrative = (narrative or '').strip()[:3000]
    brief.edited = brief.narrative != brief.original_narrative
    brief.save(update_fields=['narrative', 'edited', 'generated_at'])
    return brief


def approve(brief, user, narrative: str | None = None):
    """Lock the brief as it stands (optionally with a last edit to the words). Records who approved and when."""
    if brief.status == 'approved':
        raise BriefLocked('This has already been approved.')
    if narrative is not None:
        brief.narrative = narrative.strip()[:3000]
        brief.edited = brief.narrative != brief.original_narrative
    brief.status, brief.approved_by, brief.approved_at = 'approved', user, timezone.now()
    brief.save()
    return brief


# ---- roll-ups ---------------------------------------------------------------------------------------------------------

def period_bounds(period: str, end: date) -> tuple[date, date]:
    if period == 'week':
        return end - timedelta(days=6), end
    if period == 'fortnight':
        return end - timedelta(days=13), end
    if period == 'month':
        return end.replace(day=1), end
    raise BriefError('Choose weekly, fortnightly or monthly.')


def _combine(dailies) -> dict:
    values = {}
    for m in metrics.METRICS:
        rows = sorted(((d.date, d.metrics.get('values', {}).get(m.key)) for d in dailies if d.kind == m.brief), key=lambda r: r[0])
        rows = [(dt, v) for dt, v in rows if v is not None]
        if not rows:
            continue
        nums = [v for _, v in rows]
        if m.agg == 'sum':
            v = sum(nums)
        elif m.agg == 'avg':
            v = round(sum(nums) / len(nums), 1)
        else:
            v = nums[-1]
        values[m.key] = round(v, 2) if isinstance(v, float) else v
    return values


def rollup(school, period: str, end: date, ctx=None, rate_limit: bool = False) -> BriefRollup:
    """Build (or remake the draft of) a weekly, fortnightly or monthly roll-up from the daily briefs in that period."""
    start, end = period_bounds(period, end)
    with use_tenant(school):
        dailies = list(DailyBrief.objects.filter(date__range=(start, end)))
        if not dailies:
            raise NothingToSummarise('There are no daily briefs in that period to roll up.')
        existing = BriefRollup.objects.filter(period=period, period_start=start, period_end=end).first()
        if existing and existing.status == 'approved':
            raise BriefLocked('This roll-up has been approved, so it cannot be changed. Delete it first to make a new one.')
        values = _combine(dailies)
        sections, attention = metrics.sections_for(None, values)
        label = f"{start:%b} {start.day} to {end:%b} {end.day}, {end.year}"
        text, source = _write('rollup', label, sections, ctx, rate_limit, school)
        obj = existing or BriefRollup(period=period, period_start=start, period_end=end)
        if existing:
            existing.reads.all().delete()
        obj.metrics = {'sections': sections, 'attention': attention, 'values': values,
                       'approved_days': sum(1 for d in dailies if d.status == 'approved')}
        obj.days = len(dailies)
        obj.narrative = obj.original_narrative = text
        obj.narrative_source, obj.edited, obj.status = source, False, 'draft'
        obj.approved_by, obj.approved_at = None, None
        obj.save()
        return obj


def latest_complete_periods(today: date) -> list[tuple[str, date]]:
    """The most recent finished week, fortnight and month, as (period, end date)."""
    last_sunday = today - timedelta(days=today.weekday() + 1)
    k = (today - ANCHOR).days // 14 - 1
    fortnight_end = ANCHOR + timedelta(days=14 * k + 13)
    month_end = today.replace(day=1) - timedelta(days=1)
    return [('week', last_sunday), ('fortnight', fortnight_end), ('month', month_end)]


def ensure_rollups(school, today: date, ctx=None) -> list[BriefRollup]:
    made = []
    with use_tenant(school):
        for period, end in latest_complete_periods(today):
            start, _ = period_bounds(period, end)
            if BriefRollup.objects.filter(period=period, period_start=start, period_end=end).exists():
                continue
            try:
                made.append(rollup(school, period, end, ctx=ctx))
            except NothingToSummarise:
                continue
    return made


# ---- keeping only about three months ----------------------------------------------------------------------------------

def purge(school, today: date | None = None) -> dict:
    """Delete daily briefs and roll-ups older than the retention window, so the oldest are overwritten, not piled up."""
    with use_tenant(school):
        cutoff = (today or school_today(school)) - timedelta(days=RETENTION_DAYS)
        d = DailyBrief.objects.filter(date__lt=cutoff).delete()[0]
        r = BriefRollup.objects.filter(period_end__lt=cutoff).delete()[0]
    return {'daily': d, 'rollups': r}


# ---- the scheduled run ------------------------------------------------------------------------------------------------

def run_due(now: datetime | None = None, schools=None) -> list[str]:
    """Called every few minutes: for each school, prepare any brief whose time (in that school's zone) has passed and which does
    not exist yet, make sure the latest roll-ups exist, and trim the old ones. Returns what it did (for logs and tests)."""
    from services.core.tenants.models import School

    now = now or timezone.now()
    done = []
    for school in (schools if schools is not None else School.objects.filter(is_active=True)):
        try:
            with use_tenant(school):
                cfg = get_settings()
                if not cfg.enabled:
                    continue
                local = now.astimezone(school_tz(school))
                ctx = system_context(school)
                for kind, at in (('morning', cfg.morning_time), ('evening', cfg.evening_time)):
                    if local.time() >= at and not DailyBrief.objects.filter(kind=kind, date=local.date()).exists():
                        generate(school, kind, local.date(), ctx=ctx)
                        done.append(f'{school.tenant_code}: {kind} {local.date()}')
                for r in ensure_rollups(school, local.date(), ctx=ctx):
                    done.append(f'{school.tenant_code}: {r.period} roll-up to {r.period_end}')
                gone = purge(school, local.date())
                if gone['daily'] or gone['rollups']:
                    done.append(f'{school.tenant_code}: removed {gone["daily"]} old briefs and {gone["rollups"]} roll-ups')
        except Exception:
            logger.exception('Daily briefs failed for %s', getattr(school, 'tenant_code', school))
    return done
