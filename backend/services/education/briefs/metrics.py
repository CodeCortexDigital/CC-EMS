"""The figures in the morning brief and the evening summary.

Every figure is a count, an amount of money or a percentage for the whole school: never a name. Each is listed once in
``METRICS`` with how it combines in a weekly, fortnightly or monthly roll-up:

* ``sum``  something that happened (incidents reported, payments received): add the days up
* ``avg``  a rate (attendance): average the days
* ``last`` a position at that moment (incidents open, fees overdue): take the latest day

``flag`` marks a figure that, when above zero, needs someone's attention (it is listed at the top of the page).
"""
from __future__ import annotations

from collections import namedtuple
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, F, Q, Sum

M = namedtuple('M', 'key brief section label unit agg link flag')

# Section order is the priority order: safety and health first, then people, then support, and so on.
SECTIONS = [
    ('safety', 'Safety & health'), ('people', 'Staff & cover'), ('support', 'Student support'), ('attendance', 'Attendance'),
    ('admissions', 'Admissions'), ('money', 'Money'), ('ahead', 'Coming up'),
]
ORDER = {key: i for i, (key, _) in enumerate(SECTIONS)}
TITLES = dict(SECTIONS)

METRICS = [
    # ---- morning ------------------------------------------------------------------------------------------------
    M('incidents_open', 'morning', 'safety', 'Safety incidents still open', 'count', 'last', 'safety', True),
    M('incidents_new', 'morning', 'safety', 'Safety incidents reported yesterday', 'count', 'sum', 'safety', False),
    M('followups_overdue', 'morning', 'safety', 'Incident follow-up tasks overdue', 'count', 'last', 'safety', True),
    M('health_visits_prev', 'morning', 'safety', 'Health office visits yesterday', 'count', 'sum', 'health', False),
    M('staff_on_leave', 'morning', 'people', 'Staff on approved leave today', 'count', 'last', 'hr', False),
    M('cover_open', 'morning', 'people', 'Lessons today still needing cover', 'count', 'last', 'cover', True),
    M('cover_filled', 'morning', 'people', 'Lessons today with cover arranged', 'count', 'last', 'cover', False),
    M('credentials_expired', 'morning', 'people', 'Staff credentials already expired', 'count', 'last', 'hr', True),
    M('credentials_expiring', 'morning', 'people', 'Staff credentials expiring within 30 days', 'count', 'last', 'hr', False),
    M('contracts_ending', 'morning', 'people', 'Staff contracts ending within 30 days', 'count', 'last', 'hr', False),
    M('interventions_overdue', 'morning', 'support', 'Student interventions overdue', 'count', 'last', 'interventions', True),
    M('interventions_due', 'morning', 'support', 'Student interventions due today', 'count', 'last', 'interventions', False),
    M('interventions_unassigned', 'morning', 'support', 'Student interventions with no owner', 'count', 'last', 'interventions', True),
    M('interventions_open', 'morning', 'support', 'Student interventions open', 'count', 'last', 'interventions', False),
    M('students_on_roll', 'morning', 'attendance', 'Students on roll', 'count', 'last', 'students', False),
    M('attendance_rate_prev', 'morning', 'attendance', 'Attendance yesterday', 'percent', 'avg', 'attendance', False),
    M('late_prev', 'morning', 'attendance', 'Students late yesterday', 'count', 'sum', 'attendance', False),
    M('behaviour_prev', 'morning', 'support', 'Behaviour incidents logged yesterday', 'count', 'sum', 'behaviour', False),
    M('absent_prev', 'morning', 'attendance', 'Students absent yesterday', 'count', 'sum', 'attendance', False),
    M('applications_new', 'morning', 'admissions', 'Applications received yesterday', 'count', 'sum', 'admissions', False),
    M('tours_today', 'morning', 'admissions', 'School tours booked today', 'count', 'sum', 'admissions', False),
    M('applications_waiting', 'morning', 'admissions', 'Applications waiting for review', 'count', 'last', 'admissions', False),
    M('offers_expiring', 'morning', 'admissions', 'Waiting-list offers expiring in 48 hours', 'count', 'last', 'admissions', True),
    M('fees_overdue_count_am', 'morning', 'money', 'Invoices overdue', 'count', 'last', 'finance', False),
    M('fees_overdue_amount_am', 'morning', 'money', 'Amount overdue', 'money', 'last', 'finance', False),
    M('payments_prev_count', 'morning', 'money', 'Payments received yesterday', 'count', 'sum', 'finance', False),
    M('payments_prev_amount', 'morning', 'money', 'Amount received yesterday', 'money', 'sum', 'finance', False),
    M('events_today', 'morning', 'ahead', 'Calendar events today', 'count', 'sum', 'calendar', False),
    M('school_closed_today', 'morning', 'ahead', 'School closed today (1 = yes)', 'count', 'sum', 'calendar', False),
    M('meetings_today', 'morning', 'ahead', 'Parent-teacher meetings today', 'count', 'sum', 'calendar', False),
    M('forms_due_soon', 'morning', 'ahead', 'Forms still unsigned and due within 2 days', 'count', 'last', 'forms', False),
    # ---- evening ------------------------------------------------------------------------------------------------
    M('incidents_reported', 'evening', 'safety', 'Safety incidents reported today', 'count', 'sum', 'safety', False),
    M('incidents_closed', 'evening', 'safety', 'Safety incidents closed today', 'count', 'sum', 'safety', False),
    M('incidents_open_pm', 'evening', 'safety', 'Safety incidents still open', 'count', 'last', 'safety', True),
    M('health_visits', 'evening', 'safety', 'Health office visits today', 'count', 'sum', 'health', False),
    M('sent_home', 'evening', 'safety', 'Students sent home from the health office', 'count', 'sum', 'health', False),
    M('medication_doses', 'evening', 'safety', 'Medication doses given at the health office', 'count', 'sum', 'health', False),
    M('medication_issues', 'evening', 'safety', 'Medication doses refused, missed or in error', 'count', 'sum', 'health', True),
    M('pickup_releases', 'evening', 'safety', 'Students released at pickup', 'count', 'sum', 'frontdesk', False),
    M('visitors', 'evening', 'safety', 'Visitors signed in today', 'count', 'sum', 'frontdesk', False),
    M('visitors_on_site', 'evening', 'safety', 'Visitors still signed in', 'count', 'last', 'frontdesk', True),
    M('cover_filled_pm', 'evening', 'people', 'Lessons covered today', 'count', 'sum', 'cover', False),
    M('cover_unfilled', 'evening', 'people', 'Lessons today left without cover', 'count', 'sum', 'cover', True),
    M('interventions_opened', 'evening', 'support', 'Student interventions opened today', 'count', 'sum', 'interventions', False),
    M('interventions_completed', 'evening', 'support', 'Student interventions completed today', 'count', 'sum', 'interventions', False),
    M('behaviour_today', 'evening', 'support', 'Behaviour incidents logged today', 'count', 'sum', 'behaviour', False),
    M('absence_alerts', 'evening', 'support', 'Absence-ladder steps triggered today', 'count', 'sum', 'attendance', False),
    M('interventions_overdue_pm', 'evening', 'support', 'Student interventions overdue', 'count', 'last', 'interventions', True),
    M('attendance_rate', 'evening', 'attendance', 'Attendance today', 'percent', 'avg', 'attendance', False),
    M('absent_today', 'evening', 'attendance', 'Students absent today', 'count', 'sum', 'attendance', False),
    M('late_today', 'evening', 'attendance', 'Students late today', 'count', 'sum', 'attendance', False),
    M('attendance_marked', 'evening', 'attendance', 'Attendance records entered today', 'count', 'sum', 'attendance', False),
    M('applications_received', 'evening', 'admissions', 'Applications received today', 'count', 'sum', 'admissions', False),
    M('applications_decided', 'evening', 'admissions', 'Applications decided today', 'count', 'sum', 'admissions', False),
    M('payments_count', 'evening', 'money', 'Payments received today', 'count', 'sum', 'finance', False),
    M('payments_amount', 'evening', 'money', 'Amount received today', 'money', 'sum', 'finance', False),
    M('forms_signed', 'evening', 'admissions', 'Forms signed today', 'count', 'sum', 'forms', False),
    M('invoices_issued', 'evening', 'money', 'Invoices issued today', 'count', 'sum', 'finance', False),
    M('fees_overdue_count_pm', 'evening', 'money', 'Invoices overdue', 'count', 'last', 'finance', False),
    M('fees_overdue_amount_pm', 'evening', 'money', 'Amount overdue', 'money', 'last', 'finance', False),
    M('cover_open_tomorrow', 'evening', 'ahead', 'Lessons tomorrow still needing cover', 'count', 'last', 'cover', True),
    M('events_tomorrow', 'evening', 'ahead', 'Calendar events tomorrow', 'count', 'sum', 'calendar', False),
    M('meetings_tomorrow', 'evening', 'ahead', 'Parent-teacher meetings tomorrow', 'count', 'sum', 'calendar', False),
    M('forms_due_tomorrow', 'evening', 'ahead', 'Forms unsigned and due tomorrow', 'count', 'last', 'forms', False),
]
BY_KEY = {m.key: m for m in METRICS}

# The few figures a principal wants on one screen, in this order (the headline version of a brief).
HEADLINE = {
    'morning': ['incidents_open', 'cover_open', 'interventions_overdue', 'attendance_rate_prev', 'fees_overdue_amount_am'],
    'evening': ['attendance_rate', 'incidents_open_pm', 'cover_open_tomorrow', 'payments_amount', 'interventions_completed'],
    'rollup': ['attendance_rate', 'incidents_reported', 'interventions_completed', 'payments_amount', 'fees_overdue_amount_pm'],
}


def bounds(day: date, tz: ZoneInfo):
    """The start and end of one school day, in the school's own time zone."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def _on(day):
    """Calendar entries that cover this day."""
    return Q(start_date__lte=day) & (Q(end_date__gte=day) | Q(end_date__isnull=True, start_date=day))


def _attendance(day):
    from services.education.attendance.models import AttendanceRecord

    rows = AttendanceRecord.objects.filter(date=day).exclude(status='holiday')
    c = {s: n for s, n in rows.values_list('status').annotate(n=Count('id'))}
    total = sum(c.values())
    attended = sum(c.get(s, 0) for s in ('present', 'late', 'early_dismissal'))
    return {'rate': round(attended * 100 / total, 1) if total else None, 'absent': c.get('absent', 0), 'late': c.get('late', 0), 'marked': total}


def _overdue_fees(day):
    from services.education.finance.models import Invoice

    q = Invoice.objects.filter(due_date__lt=day, status__in=['issued', 'partial', 'overdue']).annotate(
        bal=F('opening_balance') + F('amount') - F('discount_amount') + F('late_fee_amount') - F('paid_amount')).filter(bal__gt=0)
    agg = q.aggregate(n=Count('id'), s=Sum('bal'))
    return agg['n'] or 0, float(agg['s'] or 0)


def _payments(day):
    from services.education.finance.models import Payment

    agg = Payment.objects.filter(payment_date=day).aggregate(n=Count('id'), s=Sum('amount'))
    return agg['n'] or 0, float(agg['s'] or 0)


def _common(day, tz):
    """Figures that mean the same in the morning and in the evening."""
    from services.education.academics.models import TeacherLeave
    from services.education.hr.models import StaffContract, StaffCredential, SubstituteRequest
    from services.education.interventions.models import Intervention
    from services.education.safety.models import FollowUpTask, SafetyIncident

    active = Intervention.objects.filter(status__in=['open', 'in_progress'])
    return {
        'incidents_open': SafetyIncident.objects.exclude(status='closed').count(),
        'followups_overdue': FollowUpTask.objects.filter(completed=False, due_date__lt=day).count(),
        'interventions_overdue': active.filter(due_date__lt=day).count(),
        'interventions_due': active.filter(due_date=day).count(),
        'interventions_unassigned': active.filter(owner__isnull=True).count(),
        'interventions_open': active.count(),
        'staff_on_leave': TeacherLeave.objects.filter(status='approved', start_date__lte=day, end_date__gte=day).count(),
        'cover_open': SubstituteRequest.objects.filter(date=day, status='open').count(),
        'cover_filled': SubstituteRequest.objects.filter(date=day, status='filled').count(),
        'credentials_expired': StaffCredential.objects.filter(teacher__is_active=True, expires_on__lt=day).count(),
        'credentials_expiring': StaffCredential.objects.filter(teacher__is_active=True, expires_on__gte=day, expires_on__lte=day + timedelta(days=30)).count(),
        'contracts_ending': StaffContract.objects.filter(teacher__is_active=True, end_date__gte=day, end_date__lte=day + timedelta(days=30)).count(),
    }


def morning(day: date, tz: ZoneInfo) -> dict:
    from services.education.admissions.models import Application, Offer
    from services.education.forms.models import FormAssignment
    from services.education.admissions.models import TourBooking
    from services.education.behaviour.models import BehaviourIncident
    from services.education.safety.models import SafetyIncident
    from services.education.schoolcalendar.models import CalendarEvent, MeetingSlot
    from services.education.students.models import HealthVisit, Student

    y = day - timedelta(days=1)
    ys, ye = bounds(y, tz)
    ds, _ = bounds(day, tz)
    c = _common(day, tz)
    att = _attendance(y)
    n_over, amt_over = _overdue_fees(day)
    pn, pa = _payments(y)
    v = {k: c[k] for k in ('incidents_open', 'followups_overdue', 'interventions_overdue', 'interventions_due', 'interventions_unassigned',
                           'interventions_open', 'staff_on_leave', 'cover_open', 'cover_filled', 'credentials_expired',
                           'credentials_expiring', 'contracts_ending')}
    v.update({
        'incidents_new': SafetyIncident.objects.filter(created_at__gte=ys, created_at__lt=ye).count(),
        'health_visits_prev': HealthVisit.objects.filter(time_in__gte=ys, time_in__lt=ye).count(),
        'attendance_rate_prev': att['rate'], 'absent_prev': att['absent'], 'late_prev': att['late'],
        'students_on_roll': Student.objects.filter(is_active=True).count(),
        'behaviour_prev': BehaviourIncident.objects.filter(date=y, kind='negative').count(),
        'tours_today': TourBooking.objects.filter(status='booked', slot__starts_at__gte=ds, slot__starts_at__lt=ds + timedelta(days=1)).count(),
        'applications_new': Application.objects.filter(submitted_at__gte=ys, submitted_at__lt=ye).count(),
        'applications_waiting': Application.objects.filter(status__in=['pending', 'reviewing']).count(),
        'offers_expiring': Offer.objects.filter(status='offered', expires_at__gte=ds, expires_at__lt=ds + timedelta(hours=48)).count(),
        'fees_overdue_count_am': n_over, 'fees_overdue_amount_am': amt_over,
        'payments_prev_count': pn, 'payments_prev_amount': pa,
        'events_today': CalendarEvent.objects.filter(_on(day)).count(),
        'school_closed_today': 1 if CalendarEvent.objects.filter(_on(day), closes_school=True).exists() else 0,
        'meetings_today': MeetingSlot.objects.filter(date=day, booked_by__isnull=False).count(),
        'forms_due_soon': FormAssignment.objects.filter(status='pending', template__status='published', template__due_date__gte=day,
                                                         template__due_date__lte=day + timedelta(days=2)).count(),
    })
    return v


def evening(day: date, tz: ZoneInfo) -> dict:
    from services.education.admissions.models import Application
    from services.education.attendance.models import AbsenceEscalation
    from services.education.behaviour.models import BehaviourIncident
    from services.education.forms.models import FormAssignment, FormResponse
    from services.education.hr.models import SubstituteRequest
    from services.education.interventions.models import Intervention
    from services.education.safety.models import SafetyIncident
    from services.education.schoolcalendar.models import CalendarEvent, MeetingSlot
    from services.education.students.models import HealthVisit, MedicationLog, PickupRelease, VisitorLog

    s, e = bounds(day, tz)
    nxt = day + timedelta(days=1)
    c = _common(day, tz)
    att = _attendance(day)
    n_over, amt_over = _overdue_fees(day + timedelta(days=1))   # "overdue" at the end of today
    pn, pa = _payments(day)
    from services.education.finance.models import Invoice

    return {
        'incidents_reported': SafetyIncident.objects.filter(created_at__gte=s, created_at__lt=e).count(),
        'incidents_closed': SafetyIncident.objects.filter(closed_at__gte=s, closed_at__lt=e).count(),
        'incidents_open_pm': c['incidents_open'],
        'health_visits': HealthVisit.objects.filter(time_in__gte=s, time_in__lt=e).count(),
        'medication_doses': MedicationLog.objects.filter(status='given', given_at__gte=s, given_at__lt=e).count(),
        'medication_issues': MedicationLog.objects.filter(status__in=['refused', 'missed', 'error'], given_at__gte=s, given_at__lt=e).count(),
        'behaviour_today': BehaviourIncident.objects.filter(date=day, kind='negative').count(),
        'absence_alerts': AbsenceEscalation.objects.filter(created_at__gte=s, created_at__lt=e).count(),
        'forms_signed': FormResponse.objects.filter(signed_at__gte=s, signed_at__lt=e).count(),
        'sent_home': HealthVisit.objects.filter(time_in__gte=s, time_in__lt=e, sent_home=True).count(),
        'pickup_releases': PickupRelease.objects.filter(released_at__gte=s, released_at__lt=e).count(),
        'visitors': VisitorLog.objects.filter(checked_in_at__gte=s, checked_in_at__lt=e).count(),
        'visitors_on_site': VisitorLog.objects.filter(checked_out_at__isnull=True).count(),
        'cover_filled_pm': SubstituteRequest.objects.filter(date=day, status='filled').count(),
        'cover_unfilled': c['cover_open'],
        'interventions_opened': Intervention.objects.filter(created_at__gte=s, created_at__lt=e).count(),
        'interventions_completed': Intervention.objects.filter(status='done', closed_at__gte=s, closed_at__lt=e).count(),
        'interventions_overdue_pm': c['interventions_overdue'],
        'attendance_rate': att['rate'], 'absent_today': att['absent'], 'late_today': att['late'], 'attendance_marked': att['marked'],
        'applications_received': Application.objects.filter(submitted_at__gte=s, submitted_at__lt=e).count(),
        'applications_decided': Application.objects.filter(decided_at__gte=s, decided_at__lt=e).count(),
        'payments_count': pn, 'payments_amount': pa,
        'invoices_issued': Invoice.objects.filter(issue_date=day).exclude(status__in=['draft', 'cancelled']).count(),
        'fees_overdue_count_pm': n_over, 'fees_overdue_amount_pm': amt_over,
        'cover_open_tomorrow': SubstituteRequest.objects.filter(date=nxt, status='open').count(),
        'events_tomorrow': CalendarEvent.objects.filter(_on(nxt)).count(),
        'meetings_tomorrow': MeetingSlot.objects.filter(date=nxt, booked_by__isnull=False).count(),
        'forms_due_tomorrow': FormAssignment.objects.filter(status='pending', template__status='published', template__due_date=nxt).count(),
    }


COLLECT = {'morning': morning, 'evening': evening}


def sections_for(kind: str | None, values: dict) -> tuple[list, list]:
    """Group the figures into the page's sections, and pick out the ones that need attention (most urgent section first).
    kind=None is for a roll-up, which holds both the morning and the evening figures."""
    from collections import Counter

    labels = Counter(m.label for m in METRICS)
    sections, attention = [], []
    for key, title in SECTIONS:
        items = []
        for m in METRICS:
            if (kind and m.brief != kind) or m.section != key or m.key not in values:
                continue
            val = values[m.key]
            label = m.label if (kind or labels[m.label] == 1) else f"{m.label} ({m.brief})"
            item = {'key': m.key, 'label': label, 'value': val, 'unit': m.unit, 'link': m.link, 'attention': bool(m.flag and val)}
            items.append(item)
            if item['attention']:
                attention.append({'key': m.key, 'label': label, 'value': val, 'link': m.link, 'section': title})
        if items:
            sections.append({'key': key, 'title': title, 'items': items})
    return sections, attention


def headline(kind: str, sections: list) -> list[dict]:
    """The few figures for the one-screen (principal's) version, in a fixed order, skipping any that were not recorded."""
    items = {i['key']: i for s in sections for i in s['items']}
    return [items[k] for k in HEADLINE.get(kind, []) if k in items and items[k]['value'] is not None]


def facts_for_ai(sections: list) -> list[dict]:
    """The figures as plain facts for the written read: label and value only, nothing that names anyone."""
    out = []
    for s in sections:
        for i in s['items']:
            if i['value'] is None:
                continue
            value = f"{i['value']}%" if i['unit'] == 'percent' else i['value']
            out.append({'label': i['label'], 'value': value, 'attention': i['attention'], 'section': s['title']})
    return out
