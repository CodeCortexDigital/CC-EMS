"""Counting the working days a leave uses: weekends and school holidays do not count, a half day is 0.5."""
from datetime import date, timedelta

DEFAULT_WORKING = {0, 1, 2, 3, 4}  # Monday to Friday
_DAY_PREFIX = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


def get_policy(tenant):
    """The school's leave policy, or an unsaved one carrying the defaults."""
    from .models import LeavePolicy
    policy = LeavePolicy._base_manager.filter(tenant=tenant).first() if tenant else None
    return policy or LeavePolicy(tenant=tenant)


def working_weekdays(tenant):
    """Weekday numbers (Mon=0) the school works; from the weekday setup when it has one, else Monday to Friday."""
    from services.education.finance.models import WeekdayConfig
    rows = list(WeekdayConfig._base_manager.filter(tenant=tenant)) if tenant else []
    if not rows:
        return set(DEFAULT_WORKING)
    days = set()
    for row in rows:
        code = (row.day_code or row.name or '').strip().lower()[:3]
        if row.is_active and code in _DAY_PREFIX:
            days.add(_DAY_PREFIX.index(code))
    return days or set(DEFAULT_WORKING)


def holiday_dates(tenant, start, end):
    """Dates between start and end on which the school is closed (calendar holidays and closures)."""
    from django.db.models import Q
    from services.education.schoolcalendar.models import CalendarEvent
    if not tenant:
        return set()
    events = CalendarEvent._base_manager.filter(tenant=tenant, start_date__lte=end, end_date__gte=start).filter(
        Q(kind='holiday') | Q(closes_school=True))
    out = set()
    for ev in events:
        d = max(ev.start_date, start)
        while d <= min(ev.end_date, end):
            out.add(d)
            d += timedelta(days=1)
    return out


def count_days(start: date, end: date, tenant=None, day_part='full') -> float:
    policy = get_policy(tenant)
    working = working_weekdays(tenant) if policy.skip_weekends else set(range(7))
    closed = holiday_dates(tenant, start, end) if policy.skip_holidays else set()
    total, d = 0, start
    while d <= end:
        if d.weekday() in working and d not in closed:
            total += 1
        d += timedelta(days=1)
    if day_part in ('am', 'pm') and start == end:
        return 0.5 if total else 0
    return total


def leave_days(leave) -> float:
    tenant = getattr(leave, 'tenant', None)
    if tenant is None and leave.teacher_id:
        tenant = leave.teacher.tenant
    return count_days(leave.start_date, leave.end_date, tenant, leave.day_part)
