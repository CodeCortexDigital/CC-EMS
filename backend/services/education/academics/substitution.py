"""Cover for approved leave, arranged date by date.

When leave is approved, every lesson the teacher has on each working day of the leave becomes a cover request
(``hr.SubstituteRequest`` linked to the leave). For each one we pick a free colleague who is *qualified for the subject*:

1. teachers in the relief pool come first (cover is their job), then regular teachers;
2. within each group, the teacher who has covered the fewest periods lately (fair share);
3. never someone who is teaching, already covering, on leave, or past their daily/weekly limit (unless the school
   allows over-load), and never someone unqualified.

A period nobody qualified can take stays an open cover request and HR is told, so nothing is lost silently. The
timetable itself is never changed; cover is a dated record. Running this again only adds what is missing (so it is
safe to call after the timetable or the leave changes), and cancelling or shortening leave removes future cover only.
"""
import math
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .eligibility import get_policy, qualified_subject_ids
from .leave_days import holiday_dates, working_weekdays
from .models import Period, Subject, Teacher, TimetableEntry

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def _leave_tenant(leave):
    return getattr(leave, 'tenant', None) or (leave.teacher.tenant if leave.teacher_id else None)


def _entry_dates(leave, today):
    """The dates in the leave on which the school is open (today or later)."""
    tenant = _leave_tenant(leave)
    open_days = working_weekdays(tenant)
    closed = holiday_dates(tenant, leave.start_date, leave.end_date)
    d, out = max(leave.start_date, today), []
    while d <= leave.end_date:
        if d.weekday() in open_days and d not in closed:
            out.append(d)
        d += timedelta(days=1)
    return out


def _teacher_entries(teacher):
    qs = TimetableEntry.objects.filter(teacher=teacher, is_active=True).select_related('class_subject__subject', 'class_subject__class_ref', 'period')
    current = qs.filter(academic_year__is_active=True)
    return current if current.exists() else qs


def _half_filter(entry, part, period_counts):
    """For a half-day leave, only the lessons in that half of the day."""
    if part == 'full':
        return True
    n = period_counts.get(entry.academic_year_id)
    if n is None:
        n = period_counts[entry.academic_year_id] = Period.objects.filter(
            academic_year_id=entry.academic_year_id, is_active=True, is_break=False).count()
    first_half = math.ceil(n / 2)
    index = Period.objects.filter(academic_year_id=entry.academic_year_id, is_active=True, is_break=False,
                                  period_number__lt=entry.period.period_number).count()
    return index < first_half if part == 'am' else index >= first_half


class _Chooser:
    """Picks a cover teacher, remembering what it has already handed out in this run."""

    def __init__(self, tenant):
        from services.education.hr.models import SubstituteRequest
        self.SR = SubstituteRequest
        self.policy = get_policy(tenant)
        self.subjects = list(Subject.objects.all())
        self.teachers = list(Teacher.objects.filter(is_active=True).prefetch_related('subjects'))
        since = timezone.localdate() - timedelta(days=90)
        self.recent = Counter(self.SR.objects.filter(status='filled', date__gte=since, substitute__isnull=False)
                              .values_list('substitute_id', flat=True))
        self.week_timetable = Counter(TimetableEntry.objects.filter(is_active=True).values_list('teacher_id', flat=True))
        self.qualified = {}

    def qualified_for(self, subject_id):
        if subject_id not in self.qualified:
            self.qualified[subject_id] = [t for t in self.teachers if subject_id in qualified_subject_ids(t, self.subjects)]
        return self.qualified[subject_id]

    def _load_ok(self, teacher, day):
        if self.policy.cover_allow_over_load:
            return True
        week_start = day - timedelta(days=day.weekday())
        covers_week = self.SR.objects.filter(substitute=teacher, status='filled', date__gte=week_start,
                                             date__lte=week_start + timedelta(days=6)).count()
        covers_day = self.SR.objects.filter(substitute=teacher, status='filled', date=day).count()
        teaching_day = TimetableEntry.objects.filter(teacher=teacher, is_active=True, day_of_week=WEEKDAYS[day.weekday()]).count()
        return (self.week_timetable[teacher.id] + covers_week < self.policy.max_periods_per_week
                and teaching_day + covers_day < self.policy.max_periods_per_day)

    def choose(self, leaver, day, entry):
        from services.education.hr.substitutes import is_busy
        subject_id = entry.class_subject.subject_id
        pool = [t for t in self.qualified_for(subject_id) if t.id != leaver.id]
        free = [t for t in pool if not is_busy(t, day, entry.period_id) and self._load_ok(t, day)]
        if not free:
            return None
        free.sort(key=lambda t: (0 if t.teacher_type == 'relief' else 1, self.recent[t.id], t.full_name.lower()))
        pick = free[0]
        self.recent[pick.id] += 1
        return pick


def create_substitutions_for_leave(leave, today=None):
    """Arrange cover for the leave's future working days. Returns {'covered': n, 'open': n}."""
    from services.education.hr.models import SubstituteRequest
    from services.education.hr.access import notify_teacher
    from services.education.hr.substitutes import _ask_for_cover
    teacher = leave.teacher
    if not teacher:
        leave.substitute_assigned = False
        leave.save(update_fields=['substitute_assigned'])
        return {'covered': 0, 'open': 0}
    today = today or timezone.localdate()
    entries = list(_teacher_entries(teacher))
    chooser = _Chooser(_leave_tenant(leave))
    period_counts = {}
    covered = open_ = 0
    given = defaultdict(list)
    new_open = []
    for day in _entry_dates(leave, today):
        for entry in entries:
            if entry.day_of_week != WEEKDAYS[day.weekday()] or not _half_filter(entry, leave.day_part, period_counts):
                continue
            existing = SubstituteRequest.objects.filter(requester=teacher, date=day, period_id=entry.period_id).exclude(status='cancelled').first()
            was_new = existing is None
            if existing and existing.status == 'filled':
                covered += 1
                continue
            cs = entry.class_subject
            pick = chooser.choose(teacher, day, entry)
            if existing is None:
                existing = SubstituteRequest.objects.create(
                    requester=teacher, date=day, entry=entry, period=entry.period, leave=leave, status='open',
                    description=f'{cs.class_ref.name} {cs.subject.name}'[:255], reason=f'{leave.get_leave_type_display()} leave')
            elif existing.leave_id is None:
                existing.leave = leave
                existing.save(update_fields=['leave'])
            if pick is not None:
                existing.status, existing.substitute, existing.filled_how, existing.filled_at = 'filled', pick, 'auto', timezone.now()
                existing.save(update_fields=['status', 'substitute', 'filled_how', 'filled_at'])
                covered += 1
                given[pick.id].append((pick, day, entry))
            else:
                open_ += 1
                if was_new:
                    new_open.append(existing)
    for rows in given.values():
        t = rows[0][0]
        first = ', '.join(f'{d:%a %d %b} {e.period.name or "P" + str(e.period.period_number)}' for _, d, e in rows[:4])
        notify_teacher(t, 'You are covering lessons', f'You will cover {len(rows)} period(s) for {teacher.full_name}: {first}'
                       + (' and more.' if len(rows) > 4 else '.'))
    if new_open:
        _tell_hr(leave, teacher, len(new_open))
        for req in new_open[:5]:
            _ask_for_cover(req)
    leave.substitute_assigned = SubstituteRequest.objects.filter(leave=leave, status='filled').exists()
    leave.save(update_fields=['substitute_assigned'])
    return {'covered': covered, 'open': open_}


def _tell_hr(leave, teacher, count):
    """Tell the school's administrators that some periods have nobody qualified free."""
    from services.core.tenants.models import TenantMembership
    from services.core.user_notifications.utils import create_user_notification
    tenant = _leave_tenant(leave)
    if tenant is None:
        return
    for m in TenantMembership.objects.filter(school=tenant, role='admin', is_active=True).select_related('user'):
        create_user_notification(
            m.user, 'Cover needed for approved leave',
            f"{count} period(s) for {teacher.full_name} ({leave.start_date} to {leave.end_date}) have no qualified free teacher. "
            f"Open Staff & HR > Cover requests to assign someone.", 'system')


def revert_substitutions_for_leave(leave, from_date=None):
    """Remove cover that has not happened yet (today or later): open requests and automatic cover for this leave."""
    from services.education.hr.models import SubstituteRequest
    from services.education.hr.access import notify_teacher
    from_date = from_date or timezone.localdate()
    qs = SubstituteRequest.objects.filter(leave=leave, date__gte=from_date).exclude(status='cancelled')
    qs = qs.filter(Q(status='open') | Q(filled_how='auto'))
    told = {}
    for req in qs.select_related('substitute'):
        if req.substitute_id:
            told.setdefault(req.substitute_id, (req.substitute, 0))
            told[req.substitute_id] = (req.substitute, told[req.substitute_id][1] + 1)
    cancelled = qs.update(status='cancelled')
    for t, n in told.values():
        notify_teacher(t, 'Cover cancelled', f'You no longer need to cover {n} period(s) for {leave.teacher.full_name if leave.teacher else "a colleague"}.')
    leave.substitute_assigned = SubstituteRequest.objects.filter(leave=leave, status='filled').exists()
    leave.save(update_fields=['substitute_assigned'])
    return cancelled


def refresh_cover(days=14, today=None):
    """Daily top-up: for approved leave in the next `days`, add cover that is missing and fill open periods."""
    today = today or timezone.localdate()
    from .models import TeacherLeave
    done = 0
    for leave in TeacherLeave.objects.filter(status='approved', end_date__gte=today, start_date__lte=today + timedelta(days=days),
                                             teacher__isnull=False).select_related('teacher'):
        create_substitutions_for_leave(leave, today=today)
        done += 1
    return done
