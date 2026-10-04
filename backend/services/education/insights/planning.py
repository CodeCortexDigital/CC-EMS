"""Planning reports for the office (mounted beside the other insights, ``/api/v1/auth/insights/``).

- ``forecast/``   next year's enrolment by grade, with a range, seats and sections. Every assumption is returned with the answer.
- ``trends/``     average scores term over term by subject or class, with decline flags. Groups under 10 students are hidden.
- ``/auth/hr/signals/``  workload and retention signals for staff (contracts, credentials, time away, cover load). Not a rating.
- ``narrative/``  a short written read of figures the school already has. A draft; the figures stay beside it.
"""
from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from services.core.accounts.decorators import is_admin
from services.core.tenants.localization import school_locale

from . import api as base

logger = logging.getLogger('erp.ai')

MIN_GROUP = 10                 # smaller groups are never shown, so no individual can be picked out
ASSUMED_RETENTION = 0.95
ASSUMED_CONVERSION = 0.35


def _denied():
    return Response({'error': 'Only the office can see this.'}, status=403)


def grade_of(text) -> int | None:
    """'Grade 5' -> 5, 'Kindergarten' or 'K' -> 0, 'Pre-K' -> -1. None when it cannot be told."""
    t = str(text or '').strip().lower()
    if re.search(r'pre[\s-]*k|nursery', t):
        return -1
    if re.fullmatch(r'k|kg|kindergarten|kinder', t) or t.startswith('kindergarten'):
        return 0
    m = re.search(r'\d+', t)
    return int(m.group()) if m else None


# ---------------------------------------------------------------------------
# D1  Enrolment forecast
# ---------------------------------------------------------------------------

def project(roll: dict, retention: float, confirmed: dict, pipeline: dict, conversion: float, class_size: dict, capacity: dict) -> list[dict]:
    """Next year's grade N = this year's grade N-1 x retention + confirmed offers + pipeline x conversion, with a low-high range."""
    grades = sorted(set(roll) | set(confirmed) | set(pipeline))
    top = max(roll) if roll else None
    rows = []
    for g in grades:
        if top is not None and g > top and g not in confirmed and g not in pipeline:
            continue
        feeder = roll.get(g - 1, 0)
        expected = feeder * retention + confirmed.get(g, 0) + pipeline.get(g, 0) * conversion
        low = feeder * max(0.0, retention - 0.04) + confirmed.get(g, 0)
        high = feeder * min(1.0, retention + 0.02) + confirmed.get(g, 0) + pipeline.get(g, 0) * min(1.0, conversion * 1.5)
        size = class_size.get(g) or 25
        seats = capacity.get(g)
        rows.append({
            'grade': g, 'this_year': roll.get(g, 0), 'from_below': round(feeder * retention, 1), 'confirmed': confirmed.get(g, 0),
            'pipeline': pipeline.get(g, 0), 'expected': round(expected), 'low': round(low), 'high': round(high),
            'seats': seats, 'seats_left': None if seats is None else seats - round(expected),
            'sections_needed': math.ceil(round(expected) / size) if expected > 0 else 0, 'class_size': size,
        })
    return rows


def grade_label(g: int) -> str:
    return 'Pre-K' if g < 0 else 'Kindergarten' if g == 0 else f'Grade {g}'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def forecast(request):
    from services.education.academics.models import SchoolClass
    from services.education.admissions.models import Application, WaitlistConfig
    from services.education.students.models import Enrollment, Student

    if not is_admin(request.user):
        return _denied()
    today = timezone.localdate()
    active = Student.objects.filter(is_active=True)
    roll = defaultdict(int)
    for g, n in active.exclude(current_class__isnull=True).values_list('current_class__grade_level').annotate(n=Count('id')):
        if g is not None:
            roll[g] += n
    classes_per_grade = defaultdict(int)
    for g in SchoolClass.objects.values_list('grade_level', flat=True):
        if g is not None:
            classes_per_grade[g] += 1
    class_size = {g: max(1, round(roll[g] / classes_per_grade[g])) for g in roll if classes_per_grade.get(g)}

    # Retention: of the students a year ago, how many are still here (graduating students do not count as leaving).
    year_ago = today - timedelta(days=365)
    left = Enrollment.objects.filter(status='withdrawn', end_date__range=(year_ago, today)).values('student').distinct().count()
    joined = Student.objects.filter(Q(admission_date__range=(year_ago, today)) | Q(admission_date__isnull=True, created_at__date__range=(year_ago, today))).count()
    roll_then = max(0, sum(roll.values()) + left - joined)
    retention_assumed = roll_then < 20
    retention = ASSUMED_RETENTION if retention_assumed else max(0.5, min(1.0, 1 - left / roll_then))

    configs = WaitlistConfig.objects.all()
    years = {c.academic_year for c in configs} | set(Application.objects.values_list('academic_year', flat=True))
    year = request.query_params.get('year') or (max(years) if years else '')
    apps = Application.objects.filter(academic_year=year).select_related('applicant')
    confirmed, pipeline, unmatched = defaultdict(int), defaultdict(int), 0
    for a in apps:
        g = grade_of(a.applicant.applying_for_class)
        if a.status in ('rejected', 'withdrawn', 'enrolled'):
            continue
        if g is None:
            unmatched += 1
        elif a.status == 'approved':
            confirmed[g] += 1
        else:
            pipeline[g] += 1
    closed = Application.objects.filter(status__in=('enrolled', 'approved', 'rejected', 'withdrawn')).count()
    enrolled = Application.objects.filter(status='enrolled').count()
    conversion_assumed = closed < 10
    conversion = ASSUMED_CONVERSION if conversion_assumed else max(0.05, min(0.95, enrolled / closed))
    capacity = {grade_of(c.class_name): c.capacity for c in configs if c.academic_year == year and grade_of(c.class_name) is not None}

    rows = project(dict(roll), retention, dict(confirmed), dict(pipeline), conversion, class_size, capacity)
    for r in rows:
        r['label'] = grade_label(r['grade'])
    if request.query_params.get('export') == 'csv':
        return base._csv('enrolment-forecast', ['Grade', 'This year', 'Expected', 'Low', 'High', 'Seats', 'Sections needed'],
                         [[r['label'], r['this_year'], r['expected'], r['low'], r['high'], r['seats'], r['sections_needed']] for r in rows])
    return Response({
        'year': year, 'grades': rows, 'total': {'this_year': sum(roll.values()), 'expected': sum(r['expected'] for r in rows),
                                                'low': sum(r['low'] for r in rows), 'high': sum(r['high'] for r in rows)},
        'assumptions': {
            'retention': round(retention, 3), 'retention_assumed': retention_assumed,
            'conversion': round(conversion, 3), 'conversion_assumed': conversion_assumed,
            'how': 'Next year\'s grade N = this year\'s grade N-1 x retention + approved offers + waiting applications x conversion. '
                   'The grade above the top one is assumed to graduate. The range uses a lower and a higher retention and conversion.',
        },
        'unmatched_applications': unmatched,
    })


# ---------------------------------------------------------------------------
# D3  Performance trends
# ---------------------------------------------------------------------------

def summarise_trend(points: dict, order: list) -> dict | None:
    """points: {term_id: (earned, possible, students)}. Needs the last two terms, each with enough students."""
    seen = [t for t in order if t in points]
    series = [{'term': t, 'average': round(points[t][0] * 100 / points[t][1], 1) if points[t][1] else None, 'students': len(points[t][2])} for t in seen]
    if len(series) < 2:
        return None
    last, prev = series[-1], series[-2]
    if last['students'] < MIN_GROUP or prev['students'] < MIN_GROUP or last['average'] is None or prev['average'] is None:
        return None
    change = round(last['average'] - prev['average'], 1)
    return {'series': [s for s in series if s['students'] >= MIN_GROUP], 'change': change, 'declining': change <= -5.0}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trends(request):
    from services.education.academics.models import Term
    from services.education.gradebook.models import Score

    if not is_admin(request.user):
        return _denied()
    by = request.query_params.get('by') if request.query_params.get('by') in ('subject', 'class') else 'subject'
    terms = list(Term.objects.order_by('start_date'))
    recent = [t for t in terms if t.start_date <= timezone.localdate()][-4:]
    order = [t.id for t in recent]
    names = {t.id: t.name for t in recent}
    qs = Score.objects.filter(points__isnull=False, status__in=('graded', 'late'), assignment__counts_toward_grade=True,
                              assignment__term_id__in=order, assignment__points_possible__gt=0)
    grade_filter = request.query_params.get('grade')
    if grade_filter and grade_filter.lstrip('-').isdigit():
        qs = qs.filter(assignment__class_subject__class_ref__grade_level=int(grade_filter))
    subject_filter = request.query_params.get('subject')
    if subject_filter:
        qs = qs.filter(assignment__class_subject__subject__name=subject_filter)
    groups: dict = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, set()]))
    for sid, tid, subj, cls, pts, poss in qs.values_list('student_id', 'assignment__term_id', 'assignment__class_subject__subject__name',
                                                          'assignment__class_subject__class_ref__name', 'points', 'assignment__points_possible'):
        cell = groups[subj if by == 'subject' else cls][tid]
        cell[0] += float(pts)
        cell[1] += float(poss)
        cell[2].add(sid)
    rows, hidden = [], 0
    for key, points in groups.items():
        s = summarise_trend(points, order)
        if s is None:
            hidden += 1
            continue
        rows.append({'name': key or 'Unassigned', **s, 'series': [{**p, 'term_name': names[p['term']], 'term': str(p['term'])} for p in s['series']]})
    rows.sort(key=lambda r: r['change'])
    return Response({'by': by, 'terms': [{'id': str(t.id), 'name': t.name} for t in recent], 'groups': rows,
                     'declining': sum(1 for r in rows if r['declining']), 'hidden_groups': hidden, 'min_group': MIN_GROUP,
                     'note': f'Groups with fewer than {MIN_GROUP} students are not shown, and a decline needs two terms of data.'})


# ---------------------------------------------------------------------------
# D4  Staffing signals
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staffing(request):
    from services.education.academics.models import Teacher, TeacherLeave, TimetableEntry
    from services.education.hr.access import is_hr
    from services.education.hr.models import SubstituteRequest
    from services.education.hr.records import alerts

    if not is_hr(request.user):
        return Response({'error': 'Only HR and administrators can see staffing signals.'}, status=403)
    today = timezone.localdate()
    signals: dict = defaultdict(list)
    names: dict = {}

    def add(tid, name, kind, label, detail):
        names[tid] = name
        signals[tid].append({'kind': kind, 'label': label, 'detail': detail})

    for a in alerts(90, today):
        label = {'contract_end': 'Contract ending', 'probation_end': 'Probation ending', 'credential': 'Credential'}[a['kind']]
        when = 'expired' if a['expired'] else f"in {a['days_left']} days"
        add(a['teacher_id'], a['teacher_name'], a['kind'], label, f"{a['what']}: {when}")
    since = today - timedelta(days=90)
    away = defaultdict(int)
    for lv in TeacherLeave.objects.filter(status='approved', teacher__isnull=False, end_date__gte=since, start_date__lte=today).select_related('teacher'):
        away[lv.teacher_id] += (min(lv.end_date, today) - max(lv.start_date, since)).days + 1
        names[str(lv.teacher_id)] = lv.teacher.full_name
    for tid, days in away.items():
        if days >= 10:
            add(str(tid), names[str(tid)], 'time_away', 'Time away', f'{days} days of approved leave in the last 90 days')
    covered = defaultdict(int)
    for r in SubstituteRequest.objects.filter(status='filled', date__range=(today - timedelta(days=30), today), substitute__isnull=False).select_related('substitute'):
        covered[r.substitute_id] += 1
        names[str(r.substitute_id)] = r.substitute.full_name
    for tid, n in covered.items():
        if n >= 6:
            add(str(tid), names[str(tid)], 'cover_load', 'Heavy cover load', f'{n} covered periods in the last 30 days')
    lessons = defaultdict(int)
    for tid in TimetableEntry.objects.filter(is_active=True).values_list('teacher_id', flat=True):
        lessons[tid] += 1
    for tid, n in lessons.items():
        if n >= 30 and tid is not None:
            t = Teacher.objects.filter(pk=tid, is_active=True).first()
            if t:
                add(str(tid), t.full_name, 'timetable', 'Full timetable', f'{n} lessons a week')
    rows = sorted(({'teacher_id': k, 'teacher_name': names[k], 'signals': v} for k, v in signals.items()),
                  key=lambda r: (-len(r['signals']), r['teacher_name']))
    counts: dict = defaultdict(int)
    for r in rows:
        for s in r['signals']:
            counts[s['kind']] += 1
    return Response({'staff': rows, 'counts': dict(counts), 'active_staff': Teacher.objects.filter(is_active=True).count(),
                     'note': 'These are workload and retention signals to start a conversation. They are not a rating of anyone\'s work.'})


# ---------------------------------------------------------------------------
# D2  Written summary of the figures
# ---------------------------------------------------------------------------

def _chg(now, before, unit=''):
    ch = base._change(now, before)
    if ch is None:
        return None
    if ch == 0:
        return 'unchanged on the previous period'
    return f"{'up' if ch > 0 else 'down'} {abs(ch)}{unit} on the previous period"


def narrative_facts(report: str, start, end, pstart, pend) -> tuple[str, list[dict]]:
    from services.education.students.models import Student

    if report == 'attendance':
        now, before = base.attendance_counts(start, end), base.attendance_counts(pstart, pend)
        facts = [{'label': 'Attendance rate', 'value': f"{now['rate']}%" if now['rate'] is not None else 'no records', 'change': _chg(now['rate'], before['rate'], ' points')},
                 {'label': 'Absences', 'value': now['absent']}, {'label': 'Late arrivals', 'value': now['late']}, {'label': 'Excused absences', 'value': now['excused']}]
        return 'Attendance', facts
    if report == 'finance':
        got, bill = base.money_in(start, end), base.billed(start, end)
        total_owed, overdue, _ = base.owed(end)
        pg, pb = base.money_in(pstart, pend), base.billed(pstart, pend)
        facts = [{'label': 'Billed', 'value': base._n(bill), 'change': None}, {'label': 'Collected', 'value': base._n(got), 'change': None},
                 {'label': 'Collection rate', 'value': f"{base._pct(got, bill)}%" if bill else 'nothing billed', 'change': _chg(base._pct(got, bill), base._pct(pg, pb), ' points')},
                 {'label': 'Overdue', 'value': base._n(overdue)}, {'label': 'Owed in all', 'value': base._n(total_owed)}]
        return 'Fees', facts
    if report == 'enrolment':
        joined, left = base.enrolment_numbers(start, end)
        pj, pl = base.enrolment_numbers(pstart, pend)
        facts = [{'label': 'Students on roll', 'value': Student.objects.filter(is_active=True).count()},
                 {'label': 'Joined', 'value': joined, 'change': _chg(joined, pj)}, {'label': 'Left', 'value': left, 'change': _chg(left, pl)}]
        return 'Enrolment', facts
    att, patt = base.attendance_counts(start, end), base.attendance_counts(pstart, pend)
    got, pgot = base.money_in(start, end), base.money_in(pstart, pend)
    joined, left = base.enrolment_numbers(start, end)
    _, overdue, _ = base.owed(end)
    facts = [{'label': 'Students on roll', 'value': Student.objects.filter(is_active=True).count()},
             {'label': 'Joined', 'value': joined}, {'label': 'Left', 'value': left},
             {'label': 'Attendance rate', 'value': f"{att['rate']}%" if att['rate'] is not None else 'no records', 'change': _chg(att['rate'], patt['rate'], ' points')},
             {'label': 'Fees collected', 'value': base._n(got), 'change': _chg(base._n(got), base._n(pgot))},
             {'label': 'Overdue fees', 'value': base._n(overdue)}]
    return 'School overview', facts


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def narrative(request):
    """{report: overview|attendance|finance|enrolment, from?, to?} -> {summary, source, facts, ...}. The figures go with it."""
    from services.ai.generation import generate_narrative, template_narrative
    from services.ai.llm import LLMError
    from services.ai.quota import record_usage
    from services.ai.teacher_tools import _ready

    if not is_admin(request.user):
        return _denied()
    report = str(request.data.get('report') or 'overview')
    if report not in ('overview', 'attendance', 'finance', 'enrolment'):
        return Response({'error': 'Choose a report from the list.'}, status=400)
    request._request.GET = request._request.GET.copy()
    for k in ('from', 'to'):
        if request.data.get(k):
            request._request.GET[k] = str(request.data[k])
    start, end, pstart, pend = base._period(request)
    title, facts = narrative_facts(report, start, end, pstart, pend)
    period = f'{start.isoformat()} to {end.isoformat()}'
    payload = {'report': report, 'title': title, 'period': period, 'facts': facts}
    ctx, llm, error = _ready(request, 'ai_narrative')
    if error:
        return error
    if llm is None:
        return Response({**template_narrative(title=title, facts=facts), **payload})
    tenant_id = getattr(ctx.tenant, 'pk', None)
    key = f'narrative:{tenant_id}:{report}:{start}:{end}:{timezone.localdate()}'
    hit = cache.get(key)
    if hit:
        return Response({**payload, 'summary': hit, 'source': 'ai', 'cached': True})
    try:
        out, usage, model = generate_narrative(llm, title=title, period=period, facts=facts, region=school_locale(ctx.tenant)['region'])
    except LLMError:
        logger.exception('Narrative summary failed')
        return Response({'error': 'Could not write the summary right now. Please try again.'}, status=502)
    record_usage(ctx, 'ai_narrative', llm.provider, model, usage)
    cache.set(key, out['summary'], 24 * 3600)
    return Response({**payload, 'summary': out['summary'], 'source': 'ai', 'cached': False})
