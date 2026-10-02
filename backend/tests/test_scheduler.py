"""Timetable generator: hard rules hold in every result, only qualified teachers teach, reports say what could not be
placed, the same seed gives the same week, and a committed timetable can be undone."""
from collections import Counter
from datetime import date, time

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.tenants.context import use_tenant
from services.core.tenants.models import TenantMembership
from services.education.academics import scheduler
from services.education.academics.eligibility import is_qualified
from services.education.academics.models import (AcademicYear, ClassSubject, Classroom, Period, SchedulingPolicy, SchoolClass,
                                                  Section, Subject, Teacher, TeacherAvailability, TeacherSubjectAssignment,
                                                  TimetableEntry, TimetableSnapshot)
from services.education.finance.models import WeekdayConfig
from tests.conftest import SchoolFactory, UserFactory

ACAD = '/api/v1/auth/academics'


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _teacher(s, name, subjects, **kw):
    email = name.lower().replace(' ', '.') + '@sched.test'
    t = Teacher.objects.create(tenant=s, employee_id=name[:3].upper() + str(abs(hash(name)) % 1000), full_name=name, email=email,
                               joining_date=date(2024, 8, 1), **kw)
    t.subjects.set(subjects)
    return t


@pytest.fixture
def school(db):
    s = SchoolFactory(name='Sched Academy')
    admin = UserFactory(email='head@sched.test', full_name='Head')
    TenantMembership.objects.create(user=admin, school=s, role='admin', is_primary=True)
    with use_tenant(s):
        year = AcademicYear.objects.create(tenant=s, name='2026-27', start_date=date(2026, 8, 1), end_date=date(2027, 6, 30), is_active=True)
        for i in range(1, 7):
            Period.objects.create(academic_year=year, period_number=i, name=f'P{i}', start_time=time(7 + i), end_time=time(8 + i), duration_minutes=60)
        rooms = [Classroom.objects.create(tenant=s, name=f'Room {i}', code=f'R{i}', capacity=30, category='classroom') for i in range(1, 5)]
        lab = Classroom.objects.create(tenant=s, name='Lab', code='LAB', capacity=30, category='lab')
        subj = {n: Subject.objects.create(tenant=s, name=n, code=n[:4].upper()) for n in
                ['Mathematics', 'English', 'Science', 'Chemistry', 'Art', 'Physical Education']}
        ppw = {'Mathematics': 5, 'English': 5, 'Science': 3, 'Chemistry': 2, 'Art': 2, 'Physical Education': 2}
        sections = []
        for g in (5, 6, 7):
            cls = SchoolClass.objects.create(tenant=s, name=f'Grade {g}', code=f'G{g}')
            sections.append(Section.objects.create(tenant=s, class_ref=cls, name='A', capacity=25))
            for n, sub in subj.items():
                ClassSubject.objects.create(class_ref=cls, subject=sub, periods_per_week=ppw[n])
        teachers = {
            'm1': _teacher(s, 'Mia Maths', [subj['Mathematics']]), 'm2': _teacher(s, 'Max Maths', [subj['Mathematics']]),
            'e1': _teacher(s, 'Eve English', [subj['English']]), 'e2': _teacher(s, 'Ed English', [subj['English']]),
            's1': _teacher(s, 'Sam Science', [subj['Science']]), 'a1': _teacher(s, 'Ann Art', [subj['Art']]),
            'p1': _teacher(s, 'Pete PE', [subj['Physical Education']]),
            'relief': _teacher(s, 'Rita Relief', [subj['Mathematics']], teacher_type='relief'),
        }
    return dict(s=s, admin=admin, year=year, subj=subj, rooms=rooms, lab=lab, sections=sections, teachers=teachers)


def _check_hard_rules(school, year, max_day=6, max_week=30):
    """No double booking of a teacher, room or class; only qualified or assigned teachers; limits kept."""
    entries = list(TimetableEntry.objects.filter(academic_year=year).select_related('teacher', 'class_subject__subject'))
    assert entries
    for key in (lambda e: (e.teacher_id, e.day_of_week, e.period_id), lambda e: (e.classroom_id, e.day_of_week, e.period_id),
                lambda e: (e.section_id, e.day_of_week, e.period_id)):
        counts = Counter(key(e) for e in entries)
        assert max(counts.values()) == 1
    assigned = {(a.teacher_id, a.class_subject_id) for a in TeacherSubjectAssignment.objects.all()}
    for e in entries:
        assert (e.teacher_id, e.class_subject_id) in assigned or is_qualified(e.teacher, e.class_subject.subject)
    per_day, per_week = Counter(), Counter()
    for e in entries:
        per_day[(e.teacher_id, e.day_of_week)] += 1
        per_week[e.teacher_id] += 1
    assert max(per_day.values()) <= max_day and max(per_week.values()) <= max_week
    return entries


@pytest.mark.django_db
def test_result_has_no_clashes_and_uses_only_qualified_teachers(school):
    s, year = school['s'], school['year']
    with use_tenant(s):
        res = scheduler.run(year.id, tenant_id=str(s.id), seed=11, restarts=3, commit=True)
        assert res['status'] == 'success' and res['committed'] is True
        entries = _check_hard_rules(school, year)
        # Relief teachers are the cover pool, not part of the weekly timetable.
        assert school['teachers']['relief'].id not in {e.teacher_id for e in entries}
        # Chemistry has nobody qualified: reported, never given to someone else.
        chem = [u for u in res['unscheduled'] if u['subject'] == 'Chemistry']
        assert len(chem) == 3 and all(u['missing'] == 2 and 'Nobody is qualified' in u['reason'] for u in chem)
        assert not any(e.class_subject.subject.name == 'Chemistry' for e in entries)
        assert res['slots_scheduled'] == res['slots_requested'] - 6
        assert res['conflicts_resolved'] is False


@pytest.mark.django_db
def test_everything_is_placed_when_it_can_be_and_chemistry_uses_the_lab(school):
    s, year = school['s'], school['year']
    with use_tenant(s):
        chem = school['subj']['Chemistry']
        school['teachers']['c1'] = _teacher(s, 'Chloe Chem', [chem])
        res = scheduler.run(year.id, tenant_id=str(s.id), seed=5, restarts=4, commit=True)
        assert res['unscheduled'] == [] and res['conflicts_resolved'] is True
        entries = _check_hard_rules(school, year)
        chem_rooms = {e.classroom_id for e in entries if e.class_subject.subject_id == chem.id}
        assert chem_rooms == {school['lab'].id}
        assert len(entries) == 3 * 19


@pytest.mark.django_db
def test_same_seed_same_week_and_commit_matches_the_preview(school):
    s, year = school['s'], school['year']
    with use_tenant(s):
        a = scheduler.run(year.id, tenant_id=str(s.id), seed=7, restarts=3)
        b = scheduler.run(year.id, tenant_id=str(s.id), seed=7, restarts=3)
        assert a['slots'] == b['slots'] and a['seed'] == 7
        assert not TimetableEntry.objects.filter(academic_year=year).exists()      # a preview saves nothing
        c = scheduler.run(year.id, tenant_id=str(s.id), seed=a['seed'], restarts=3, commit=True)
        saved = {(e.section_id, e.class_subject_id, e.teacher_id, e.classroom_id, e.day_of_week, e.period_id)
                 for e in TimetableEntry.objects.filter(academic_year=year)}
        previewed = {(r['section_id'], r['class_subject_id'], r['teacher_id'], r['classroom_id'], r['day_of_week'], r['period_id'])
                     for r in a['slots']}
        assert saved == previewed and c['slots_scheduled'] == len(previewed)


@pytest.mark.django_db
def test_limits_in_the_policy_are_never_exceeded_and_overflow_is_reported(school):
    s, year = school['s'], school['year']
    with use_tenant(s):
        SchedulingPolicy.objects.create(tenant=s, max_periods_per_day=2, max_periods_per_week=8, max_consecutive=2)
        res = scheduler.run(year.id, tenant_id=str(s.id), seed=3, restarts=3, commit=True)
        _check_hard_rules(school, year, max_day=2, max_week=8)
        science = [u for u in res['unscheduled'] if u['subject'] == 'Science']
        # one science teacher at 8 a week cannot take 3 sections x 3 lessons = 9
        assert sum(u['missing'] for u in science) == 1 and 'weekly limit' in science[0]['reason']


@pytest.mark.django_db
def test_working_days_half_days_and_availability_are_respected(school):
    s, year = school['s'], school['year']
    with use_tenant(s):
        for order, (code, half) in enumerate([('sun', False), ('mon', False), ('tue', False), ('wed', False), ('thu', True)]):
            WeekdayConfig.objects.create(tenant=s, name=code.title(), day_code=code, is_active=True, is_half_day=half, order=order)
        sam = school['teachers']['s1']
        # On Mondays Sam can only teach periods 1-3 (days without a window are open).
        TeacherAvailability.objects.create(teacher=sam, academic_year=year, day_of_week='monday', start_time=time(8), end_time=time(11), is_available=True)
        scheduler.run(year.id, tenant_id=str(s.id), seed=2, restarts=3, commit=True)
        entries = list(TimetableEntry.objects.filter(academic_year=year).select_related('period'))
        assert {e.day_of_week for e in entries} <= {'sunday', 'monday', 'tuesday', 'wednesday', 'thursday'}
        assert all(e.period.period_number <= 3 for e in entries if e.day_of_week == 'thursday')       # half day: first half only
        sam_slots = [(e.day_of_week, e.period.period_number) for e in entries if e.teacher_id == sam.id]
        assert sam_slots and all(n <= 3 for d, n in sam_slots if d == 'monday')


@pytest.mark.django_db
def test_an_assigned_teacher_is_trusted_even_without_the_subject_listed(school):
    s, year = school['s'], school['year']
    with use_tenant(s):
        chem_cs = ClassSubject.objects.filter(subject=school['subj']['Chemistry'], class_ref=school['sections'][0].class_ref).first()
        helper = _teacher(s, 'Hal Helper', [])
        TeacherSubjectAssignment.objects.create(teacher=helper, class_subject=chem_cs, academic_year=year, override_reason='head approved')
        res = scheduler.run(year.id, tenant_id=str(s.id), seed=4, restarts=2, commit=True)
        mine = TimetableEntry.objects.filter(academic_year=year, teacher=helper)
        assert mine.count() == 2 and all(e.class_subject_id == chem_cs.id for e in mine)
        assert sum(u['missing'] for u in res['unscheduled'] if u['subject'] == 'Chemistry') == 4   # the other two grades


@pytest.mark.django_db
def test_commit_keeps_a_snapshot_and_undo_restores_the_old_timetable(school):
    s, year, admin = school['s'], school['year'], school['admin']
    with use_tenant(s):
        scheduler.run(year.id, tenant_id=str(s.id), seed=1, restarts=2, commit=True)
        before = sorted((str(e.section_id), str(e.class_subject_id), e.day_of_week, str(e.period_id)) for e in TimetableEntry.objects.filter(academic_year=year))
        second = scheduler.run(year.id, tenant_id=str(s.id), seed=99, restarts=2, commit=True)
        after = sorted((str(e.section_id), str(e.class_subject_id), e.day_of_week, str(e.period_id)) for e in TimetableEntry.objects.filter(academic_year=year))
        assert after != before
        snap = TimetableSnapshot.objects.get(pk=second['snapshot_id'])
        assert len(snap.entries) == len(before)
    office = _client(admin)
    listed = office.get(f'{ACAD}/timetable-snapshots/', {'academic_year': str(year.id)}).json()
    assert listed[0]['id'] == second['snapshot_id'] and listed[0]['undone'] is False
    assert _client(school['teachers']['m1'].user if hasattr(school['teachers']['m1'], 'user') else UserFactory()).post(
        f"{ACAD}/timetable-snapshots/{snap.id}/undo/").status_code in (403, 404)
    done = office.post(f'{ACAD}/timetable-snapshots/{snap.id}/undo/')
    assert done.status_code == 200 and done.json()['restored'] == len(before)
    with use_tenant(s):
        restored = sorted((str(e.section_id), str(e.class_subject_id), e.day_of_week, str(e.period_id)) for e in TimetableEntry.objects.filter(academic_year=year))
    assert restored == before
    assert office.post(f'{ACAD}/timetable-snapshots/{snap.id}/undo/').status_code == 409


@pytest.mark.django_db
def test_generate_endpoint_previews_then_commits_the_same_week(school):
    s, year, admin = school['s'], school['year'], school['admin']
    office = _client(admin)
    prev = office.post('/api/v1/ai/generate-timetable/', {'academic_year': str(year.id)}, format='json')
    assert prev.status_code == 200, prev.content
    body = prev.json()
    assert body['committed'] is False and body['slots'] and 'seed' in body and 'unscheduled' in body and 'workloads' in body
    assert {'class_name', 'subject', 'teacher', 'classroom', 'day_of_week', 'period_number'} <= set(body['slots'][0])
    with use_tenant(s):
        assert not TimetableEntry.objects.filter(academic_year=year).exists()
    done = office.post('/api/v1/ai/generate-timetable/', {'academic_year': str(year.id), 'commit': True, 'seed': body['seed']}, format='json')
    assert done.status_code == 200 and done.json()['snapshot_id'] and done.json()['slots_scheduled'] == body['slots_scheduled']
    with use_tenant(s):
        assert TimetableEntry.objects.filter(academic_year=year).count() == body['slots_scheduled']


@pytest.mark.django_db
def test_missing_setup_is_explained(db):
    s = SchoolFactory(name='Empty')
    with use_tenant(s):
        year = AcademicYear.objects.create(tenant=s, name='y', start_date=date(2026, 8, 1), end_date=date(2027, 6, 30), is_active=True)
        res = scheduler.run(year.id, tenant_id=str(s.id), seed=1)
    assert 'classrooms and time periods' in res['error']
