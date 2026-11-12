"""Alerts for unusual use of personal information, and the draft of an initial breach report (個人情報漏えい等の報告, 速報).

Detection reads the audit log (see ``audit_personal_view`` and the activity log): in any sliding window of one hour, a person who
 * opened at least ``views`` different student records            -> ``bulk_views``
 * opened at least ``night_views`` different student records between 22:00 and 06:00 (school time) -> ``night_views``
 * made at least ``exports`` exports                                -> ``bulk_exports``
 * had at least ``refused`` requests refused                        -> ``refused``
raises one alert per burst. It is idempotent: the same log always gives the same alerts, so it can run on every visit and from cron
(``python manage.py check_access_alerts``). It finds *signs*, not breaches: a person decides, by reviewing the alert.

The draft report is a starting point for the school's own report to the Personal Information Protection Commission: it fills what the
system knows and leaves everything else marked 要確認. Whether a report is legally required is for the school to decide.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone

from services.core.audit.models import AuditLog

from .models import AccessAlert

WINDOW = timedelta(hours=1)
LOOKBACK_DAYS = 30
DEFAULTS = {'views': 30, 'night_views': 5, 'exports': 5, 'refused': 10}
LIMITS = (1, 10000)
NIGHT = (22, 6)          # from 22:00 until 06:00


def thresholds(school) -> dict:
    saved = ((getattr(school, 'settings_json', None) or {}).get('access_alerts') or {})
    out = dict(DEFAULTS)
    for k in DEFAULTS:
        try:
            v = int(saved.get(k))
        except (TypeError, ValueError):
            continue
        if LIMITS[0] <= v <= LIMITS[1]:
            out[k] = v
    return out


def clean_thresholds(raw) -> tuple[dict | None, str | None]:
    if not isinstance(raw, dict):
        return None, 'Send the limits as an object.'
    out = {}
    for k in DEFAULTS:
        try:
            v = int(raw.get(k, DEFAULTS[k]))
        except (TypeError, ValueError):
            return None, f'"{k}" must be a whole number.'
        if not LIMITS[0] <= v <= LIMITS[1]:
            return None, f'Each limit is between {LIMITS[0]} and {LIMITS[1]}.'
        out[k] = v
    return out, None


def _is_night(ts) -> bool:
    h = timezone.localtime(ts).hour
    return h >= NIGHT[0] or h < NIGHT[1]


def _bursts(events, limit, distinct):
    """Greedy sliding windows over (timestamp, key) events sorted by time: yield (start, end, count, keys) for each burst that reaches
    ``limit`` (distinct keys when ``distinct``, else events). A burst is not reported twice: scanning resumes after its window."""
    i, n = 0, len(events)
    while i < n:
        start = events[i][0]
        j, seen = i, Counter()
        while j < n and events[j][0] - start < WINDOW:
            seen[events[j][1]] += 1
            j += 1
        count = len(seen) if distinct else j - i
        if count >= limit:
            yield start, events[j - 1][0], count, sorted(str(k) for k in seen if k)
            i = j
        else:
            i += 1


def detect(school, now=None) -> int:
    """Look over the last 30 days of this school's log and save a new alert for every burst not seen before. Returns how many were new."""
    now = now or timezone.now()
    limits = thresholds(school)
    rows = (AuditLog.objects.filter(school=school, timestamp__gte=now - timedelta(days=LOOKBACK_DAYS), user__isnull=False,
                                    action__in=('VIEW', 'EXPORT', 'PERMISSION_DENIED')).order_by('timestamp').values('user_id', 'action', 'resource_type', 'resource_id', 'timestamp')[:100000])
    per_user: dict = {}
    for r in rows:
        per_user.setdefault(r['user_id'], []).append(r)
    created = 0
    for user_id, items in per_user.items():
        views = [(r['timestamp'], r['resource_id']) for r in items if r['action'] == 'VIEW' and (r['resource_type'] or '') == 'students/profile' and r['resource_id']]
        plans = [
            ('bulk_views', views, limits['views'], True),
            ('night_views', [e for e in views if _is_night(e[0])], limits['night_views'], True),
            ('bulk_exports', [(r['timestamp'], r['resource_type']) for r in items if r['action'] == 'EXPORT' and not (r['resource_type'] or '').startswith('print/')], limits['exports'], False),
            ('refused', [(r['timestamp'], r['resource_type']) for r in items if r['action'] == 'PERMISSION_DENIED'], limits['refused'], False),
        ]
        for kind, events, limit, distinct in plans:
            for start, end, count, keys in _bursts(events, limit, distinct):
                details = {'count': count, 'limit': limit, **({'students': keys[:200]} if kind in ('bulk_views', 'night_views') else {'areas': keys[:20]})}
                try:
                    _, new = AccessAlert.objects.get_or_create(school=school, user_id=user_id, kind=kind, window_start=start,
                                                               defaults={'window_end': end, 'details': details})
                    created += int(new)
                except IntegrityError:
                    pass
    return created


# ---- the draft initial report -------------------------------------------------------------------------------------------

TO_CONFIRM = {'ja': '要確認', 'en': 'To confirm'}


def _when(dt) -> str:
    return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M')


def draft_report(alert: AccessAlert, lang: str = 'ja') -> dict:
    """A draft initial report (速報) for this alert: what the system knows is filled in, the rest says 要確認. ``lang`` is 'ja' or 'en'."""
    ja = (lang or '').lower().startswith('ja')
    tc = TO_CONFIRM['ja' if ja else 'en']
    who = getattr(alert.user, 'full_name', '') or getattr(alert.user, 'email', '') or ('不明' if ja else 'unknown')
    email = getattr(alert.user, 'email', '')
    n = alert.details.get('count', 0)
    students = alert.details.get('students') or []
    span = f'{_when(alert.window_start)} – {_when(alert.window_end)}'
    if ja:
        what = {'bulk_views': f'{who}({email})が、1時間のうちに {n} 名分の生徒記録を閲覧した。',
                'night_views': f'{who}({email})が、夜間(22時〜6時)に {n} 名分の生徒記録を閲覧した。',
                'bulk_exports': f'{who}({email})が、1時間のうちに {n} 回のエクスポートを行った。',
                'refused': f'{who}({email})の操作が、1時間のうちに {n} 回拒否された。'}[alert.kind]
        items = ('生徒の氏名・学籍番号・住所・保護者の連絡先など(健康情報などの要配慮個人情報が含まれるか: ' + tc + ')') if alert.kind != 'refused' else '個人データは取得されていない(拒否されたため)。確認: ' + tc
        sections = [
            ('概要', what + ' 業務上必要な閲覧・操作かどうかは ' + tc + '。'), ('発生日時', span), ('発覚日時', _when(alert.created_at)),
            ('漏えい等のおそれのある個人データの項目', items),
            ('本人の数', f'{len(students)} 名(ログによる)' if students else tc), ('原因', '調査中(' + tc + ')'),
            ('二次被害のおそれ', tc), ('本人への対応', '未実施(' + tc + ')'), ('公表の予定', '未定(' + tc + ')'), ('再発防止策', '未定(' + tc + ')'),
        ]
        guide = ['報告が必要となる主な場合: 要配慮個人情報が含まれる / 財産的被害のおそれがある / 不正の目的によるおそれがある / 1,000人を超える。該当するかは学校で判断してください。',
                 '報告の期限の目安: 速報は発覚から速やかに(概ね3〜5日以内)、確報は30日以内(不正の目的によるおそれがある場合は60日以内)。最新の指針を確認してください。']
        title = '個人データの漏えい等のおそれに関する報告(速報)(案)'
        note = 'この文書は、システムが把握している事実から作成した下書きです。内容を確認・修正のうえ、学校の責任で提出してください。'
    else:
        what = {'bulk_views': f'{who} ({email}) opened the records of {n} students within one hour.',
                'night_views': f'{who} ({email}) opened the records of {n} students at night (22:00 to 06:00).',
                'bulk_exports': f'{who} ({email}) made {n} exports within one hour.',
                'refused': f'{who} ({email}) had {n} requests refused within one hour.'}[alert.kind]
        items = ('Student names, student numbers, addresses and guardians\' contact details (whether health or other sensitive information is included: ' + tc + ')') if alert.kind != 'refused' else 'No personal data was obtained (the requests were refused). Confirm: ' + tc
        sections = [
            ('Summary', what + ' Whether this was needed for their work: ' + tc + '.'), ('When it happened', span), ('When it was found', _when(alert.created_at)),
            ('Personal data that may be involved', items), ('Number of people affected', f'{len(students)} (from the log)' if students else tc),
            ('Cause', 'Under investigation (' + tc + ')'), ('Risk of further harm', tc), ('Action for the people affected', 'Not yet (' + tc + ')'),
            ('Public announcement', 'Not decided (' + tc + ')'), ('Measures to prevent it happening again', 'Not decided (' + tc + ')'),
        ]
        guide = ['A report is generally needed when sensitive information is involved, there is a risk of financial harm, it may be malicious, or more than 1,000 people are affected. The school decides whether this applies.',
                 'Typical deadlines: an initial report promptly (about 3 to 5 days after discovery) and a final report within 30 days (60 days if malicious). Check the current guidance.']
        title = 'Draft initial report on a possible leak of personal data'
        note = 'This is a draft made from what the system knows. Check and correct it, and submit it under the school\'s own responsibility.'
    return {'title': title, 'sections': [{'heading': h, 'text': t} for h, t in sections], 'guidance': guide, 'note': note,
            'school': alert.school.name, 'prepared_on': timezone.localdate().isoformat(), 'alert': str(alert.pk)}


# ---- API helpers (the views are in ``api.py``) ------------------------------------------------------------------------------

def _payload(a: AccessAlert) -> dict:
    return {'id': str(a.pk), 'kind': a.kind, 'kind_label': a.get_kind_display(), 'who': (getattr(a.user, 'full_name', '') or getattr(a.user, 'email', '')) if a.user_id else '',
            'email': a.user.email if a.user_id else '', 'window_start': timezone.localtime(a.window_start).isoformat(), 'window_end': timezone.localtime(a.window_end).isoformat(),
            'count': a.details.get('count'), 'limit': a.details.get('limit'), 'status': a.status, 'status_label': a.get_status_display(), 'note': a.note,
            'reviewed_by': (getattr(a.reviewed_by, 'full_name', '') or getattr(a.reviewed_by, 'email', '')) if a.reviewed_by_id else '',
            'reviewed_at': timezone.localtime(a.reviewed_at).isoformat() if a.reviewed_at else None, 'created_at': timezone.localtime(a.created_at).isoformat()}
