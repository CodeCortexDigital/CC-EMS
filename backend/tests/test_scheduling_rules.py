"""Who may teach what: qualification by subject, assignment and timetable rules, and the teaching-coverage report."""
from datetime import date, time

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.tenants.context import use_tenant
from services.core.tenants.models import TenantMembership
from services.education.academics.eligibility import is_qualified, qualified_teachers
from services.education.academics.models import (AcademicYear, ClassSubject, Classroom, Period, SchoolClass, Subject,
                                                  Teacher, TeacherSubjectAssignment)
from tests.conftest import SchoolFactory, UserFactory

ACAD = '/api/v1/auth/academics'


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _teacher(school, name, email, **kw):
    with use_tenant(school):
        return Teacher.objects.create(tenant=school, employee_id=email.split('@')[0].upper()[:20], full_name=name, email=email,
                                      joining_date=date(2024, 8, 1), **kw)


@pytest.fixture
def rules(db):
    s = SchoolFactory(name='Rules Academy')
    admin = UserFactory(email='head@rules.test', full_name='Head')
    TenantMembership.objects.create(user=admin, school=s, role='admin', is_primary=True)
    with use_tenant(s):
        year = AcademicYear.objects.create(tenant=s, name='2026-27', start_date=date(2026, 8, 1), end_date=date(2027, 6, 30), is_active=True)
        maths = Subject.objects.create(tenant=s, name='Mathematics', code='MATH')
        art = Subject.objects.create(tenant=s, name='Art', code='ART')
        martial = Subject.objects.create(tenant=s, name='Martial Arts', code='MART')
        grade5 = SchoolClass.objects.create(tenant=s, name='Grade 5', code='G5')
        cs_math = ClassSubject.objects.create(class_ref=grade5, subject=maths)
        period = Period.objects.create(academic_year=year, period_number=1, name='P1', start_time=time(8), end_time=time(9), duration_minutes=60)
        room = Classroom.objects.create(tenant=s, name='R1', code='R1')
    return dict(s=s, admin=admin, office=_client(admin), year=year, maths=maths, art=art, martial=martial, cs_math=cs_math,
                period=period, room=room, grade5=grade5)


@pytest.mark.django_db
def test_free_text_matches_exact_words_and_short_forms_only(rules):
    s = rules['s']
    with use_tenant(s):
        phys_maths = _teacher(s, 'Pat Phys', 'pat@rules.test', specializations=['Physics, Maths'])
        title_only = _teacher(s, 'Tina Title', 'tina@rules.test', specializations=['Teacher'])
        art_teacher = _teacher(s, 'Art Teacher', 'artt@rules.test', specializations=['art'])
        listed = _teacher(s, 'Lee Listed', 'lee@rules.test', specializations=['Teacher'])
        listed.subjects.set([rules['art']])
        assert is_qualified(phys_maths, rules['maths'])                       # "maths" is a short form of mathematics
        assert not is_qualified(title_only, rules['maths'])                   # a job title qualifies nobody
        assert is_qualified(art_teacher, rules['art']) and not is_qualified(art_teacher, rules['martial'])  # no loose substring
        assert is_qualified(listed, rules['art']) and not is_qualified(listed, rules['maths'])           # the list wins over the text
        assert {t.full_name for t in qualified_teachers(rules['maths'])} == {'Pat Phys'}


@pytest.mark.django_db
def test_assignment_needs_a_qualified_teacher_or_an_admin_override(rules):
    s, office = rules['s'], rules['office']
    maths_t = _teacher(s, 'Mia Maths', 'mia@rules.test')
    maths_t.subjects.set([rules['maths']])
    art_t = _teacher(s, 'Art Only', 'arto@rules.test')
    art_t.subjects.set([rules['art']])

    def body(t, **k):
        return {'teacher': str(t.id), 'class_subject': str(rules['cs_math'].id), 'academic_year': str(rules['year'].id), **k}

    ok = office.post(f'{ACAD}/teacher-assignments/', body(maths_t), format='json')
    assert ok.status_code == 201, ok.content
    no = office.post(f'{ACAD}/teacher-assignments/', body(art_t), format='json')
    assert no.status_code == 400 and 'qualified for Art' in str(no.json()) and 'override' in str(no.json())
    over = office.post(f'{ACAD}/teacher-assignments/', body(art_t, override_reason='Maths teacher on maternity leave'), format='json')
    assert over.status_code == 201
    assert TeacherSubjectAssignment.objects.get(teacher=art_t).override_reason.startswith('Maths teacher')
    # A teacher cannot give themselves an override.
    from django.contrib.auth import get_user_model
    art_user = get_user_model().objects.get(email='arto@rules.test')
    TenantMembership.objects.get_or_create(user=art_user, school=s, defaults={'role': 'teacher'})
    TeacherSubjectAssignment.objects.filter(teacher=art_t).delete()
    mine = _client(art_user).post(f'{ACAD}/teacher-assignments/', body(art_t, override_reason='trust me'), format='json')
    assert mine.status_code in (400, 403)
    # With the rule switched off anyone can be assigned.
    office.patch(f'{ACAD}/scheduling/policy/', {'enforce_subject_match': False}, format='json')
    assert office.post(f'{ACAD}/teacher-assignments/', body(art_t), format='json').status_code == 201


@pytest.mark.django_db
def test_timetable_slot_needs_a_qualified_or_assigned_teacher(rules):
    s, office = rules['s'], rules['office']
    art_t = _teacher(s, 'Art Only', 'arto@rules.test')
    art_t.subjects.set([rules['art']])
    slot = {'academic_year': str(rules['year'].id), 'class_subject': str(rules['cs_math'].id), 'teacher': str(art_t.id),
            'classroom': str(rules['room'].id), 'day_of_week': 'monday', 'period': str(rules['period'].id), 'is_active': True}
    bad = office.post(f'{ACAD}/timetable-entries/', slot, format='json')
    assert bad.status_code == 400 and 'Art' in str(bad.json())
    with use_tenant(s):
        TeacherSubjectAssignment.objects.create(teacher=art_t, class_subject=rules['cs_math'], academic_year=rules['year'],
                                                override_reason='approved by head')
    assert office.post(f'{ACAD}/timetable-entries/', slot, format='json').status_code == 201


@pytest.mark.django_db
def test_subject_list_endpoint_eligible_list_and_coverage_report(rules):
    s, office = rules['s'], rules['office']
    mia = _teacher(s, 'Mia Maths', 'mia@rules.test', specializations=['Maths'])
    bo = _teacher(s, 'Bo Bare', 'bo@rules.test', specializations=['Teacher'])
    stranger = _client(UserFactory(email='x@rules.test'))
    assert stranger.put(f'{ACAD}/teachers/{bo.id}/subjects/', {'subjects': []}, format='json').status_code in (403, 404)
    put = office.put(f'{ACAD}/teachers/{bo.id}/subjects/', {'subjects': [str(rules['art'].id)]}, format='json')
    assert put.status_code == 200 and [x['name'] for x in put.json()['subjects']] == ['Art']
    missing = office.put(f'{ACAD}/teachers/{bo.id}/subjects/', {'subjects': ['00000000-0000-0000-0000-000000000000']}, format='json')
    assert missing.status_code == 400
    elig = office.get(f'{ACAD}/scheduling/eligible-teachers/', {'class_subject': str(rules['cs_math'].id)}).json()
    assert [t['name'] for t in elig['qualified']] == ['Mia Maths']
    assert elig['not_qualified'][0]['name'] == 'Bo Bare' and 'qualified for Art' in elig['not_qualified'][0]['reason']
    cov = office.get(f'{ACAD}/scheduling/coverage/').json()
    assert cov['counts']['unstaffed'] == 0                                  # Mia covers Grade 5 maths
    assert cov['class_subjects_with_one_qualified_teacher'][0]['only'] == 'Mia Maths'
    mia.is_active = False
    mia.save()
    assert office.get(f'{ACAD}/scheduling/coverage/').json()['counts']['unstaffed'] == 1   # nobody qualified now


@pytest.mark.django_db
def test_policy_limits_are_checked_and_admin_only(rules):
    office = rules['office']
    got = office.get(f'{ACAD}/scheduling/policy/').json()
    assert got['enforce_subject_match'] is True and got['max_periods_per_day'] == 6
    assert office.patch(f'{ACAD}/scheduling/policy/', {'max_periods_per_day': 0}, format='json').status_code == 400
    assert office.patch(f'{ACAD}/scheduling/policy/', {'max_periods_per_day': 2, 'max_periods_per_week': 30}, format='json').status_code == 400
    ok = office.patch(f'{ACAD}/scheduling/policy/', {'max_periods_per_day': 7, 'max_periods_per_week': 32, 'cover_allow_over_load': True}, format='json')
    assert ok.status_code == 200 and ok.json()['max_periods_per_week'] == 32 and ok.json()['cover_allow_over_load'] is True
    other = UserFactory(email='t@rules.test')
    TenantMembership.objects.create(user=other, school=rules['s'], role='teacher')
    assert _client(other).patch(f'{ACAD}/scheduling/policy/', {'max_consecutive': 2}, format='json').status_code == 403
