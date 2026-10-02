"""Cover for approved leave: dated, only qualified teachers, relief pool first, fair share, open when nobody fits."""
from datetime import date, time, timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.tenants.context import use_tenant
from services.core.tenants.models import TenantMembership
from services.core.user_notifications.models import Notification
from services.education.academics.models import (AcademicYear, ClassSubject, Classroom, Period, SchedulingPolicy, SchoolClass,
                                                  Subject, Teacher, TeacherLeave, TimetableEntry)
from services.education.hr.models import SubstituteRequest
from services.education.schoolcalendar.models import CalendarEvent
from tests.conftest import SchoolFactory, UserFactory

ACAD = '/api/v1/auth/academics'
HR = '/api/v1/auth/hr'


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _next(weekday, weeks=0):
    d = timezone.localdate() + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d + timedelta(weeks=weeks)


def _teacher(s, name, subjects, **kw):
    email = name.lower().replace(' ', '.') + '@cover.test'
    t = Teacher.objects.create(tenant=s, employee_id=name[:3].upper() + str(abs(hash(name)) % 1000), full_name=name, email=email,
                               joining_date=date(2024, 8, 1), **kw)
    t.subjects.set(subjects)
    return t


@pytest.fixture
def cover(db):
    s = SchoolFactory(name='Cover Academy')
    admin = UserFactory(email='head@cover.test', full_name='Head')
    TenantMembership.objects.create(user=admin, school=s, role='admin', is_primary=True)
    with use_tenant(s):
        year = AcademicYear.objects.create(tenant=s, name='2026-27', start_date=date(2026, 8, 1), end_date=date(2027, 6, 30), is_active=True)
        p1 = Period.objects.create(academic_year=year, period_number=1, name='P1', start_time=time(8), end_time=time(9), duration_minutes=60)
        p2 = Period.objects.create(academic_year=year, period_number=2, name='P2', start_time=time(9), end_time=time(10), duration_minutes=60)
        room = Classroom.objects.create(tenant=s, name='R1', code='R1')
        maths = Subject.objects.create(tenant=s, name='Mathematics', code='MATH')
        art = Subject.objects.create(tenant=s, name='Art', code='ART')
        g5 = SchoolClass.objects.create(tenant=s, name='Grade 5', code='G5')
        cs_math = ClassSubject.objects.create(class_ref=g5, subject=maths)
        cs_art = ClassSubject.objects.create(class_ref=g5, subject=art)
        ann = _teacher(s, 'Ann Maths', [maths])
        ben = _teacher(s, 'Ben Relief', [maths], teacher_type='relief')
        cat = _teacher(s, 'Cat Maths', [maths])
        dan = _teacher(s, 'Dan Maths', [maths])
        eve = _teacher(s, 'Eve Art', [art])

        def entry(t, day, period, cs=cs_math):
            return TimetableEntry.objects.create(academic_year=year, class_subject=cs, teacher=t, classroom=room,
                                                 day_of_week=day, period=period)
        e = {'ann_mon1': entry(ann, 'monday', p1), 'ann_mon2': entry(ann, 'monday', p2), 'ann_tue1': entry(ann, 'tuesday', p1),
             'cat_mon1': entry(cat, 'monday', p1, cs=cs_art)}
    return dict(s=s, admin=admin, office=_client(admin), year=year, p1=p1, p2=p2, maths=maths, art=art, ann=ann, ben=ben, cat=cat,
                dan=dan, eve=eve, e=e)


def _leave(c, start, end=None, **kw):
    with use_tenant(c['s']):
        return TeacherLeave.objects.create(teacher=c['ann'], applicant_name='Ann Maths', applicant_email=c['ann'].email, leave_type='sick',
                                           start_date=start, end_date=end or start, status='pending', **kw)


def _approve(c, leave):
    r = c['office'].patch(f'{ACAD}/teacher-leaves/{leave.id}/', {'status': 'approved'}, format='json')
    assert r.status_code == 200, r.content
    return r.json()


def _cover_rows(leave):
    with use_tenant(leave.tenant):
        return list(SubstituteRequest.objects.filter(leave=leave).exclude(status='cancelled').order_by('date', 'period__period_number'))


@pytest.mark.django_db
def test_cover_is_dated_one_day_leave_only_covers_that_day(cover):
    tue = _next(1)
    leave = _leave(cover, tue)
    out = _approve(cover, leave)
    rows = _cover_rows(leave)
    assert [(r.date, r.period.name) for r in rows] == [(tue, 'P1')]            # Monday's periods are not touched
    assert rows[0].substitute_id == cover['ben'].id and rows[0].filled_how == 'auto' and rows[0].status == 'filled'
    assert out['substitute_assigned'] is True and out['substitutions'][0]['relief_teacher_name'] == 'Ben Relief'
    assert out['substitutions'][0]['day_of_week'] == 'tuesday' and out['substitutions'][0]['date'] == str(tue)
    assert Notification.objects.filter(recipient__email=cover['ben'].email, title='You are covering lessons').count() == 1


@pytest.mark.django_db
def test_week_long_leave_covers_each_lesson_date_and_skips_holidays(cover):
    mon, fri = _next(0, 1), _next(0, 1) + timedelta(days=4)
    with use_tenant(cover['s']):
        CalendarEvent.objects.create(tenant=cover['s'], title='Holiday', kind='holiday', start_date=mon + timedelta(days=1), end_date=mon + timedelta(days=1))
    leave = _leave(cover, mon, fri)
    _approve(cover, leave)
    rows = _cover_rows(leave)
    # Monday P1 and P2; Tuesday is a school holiday so Tuesday P1 is not needed.
    assert [(r.date, r.period.name) for r in rows] == [(mon, 'P1'), (mon, 'P2')]


@pytest.mark.django_db
def test_relief_first_then_fair_share_and_never_the_unqualified(cover):
    with use_tenant(cover['s']):
        cover['ben'].is_active = False          # no relief teacher available
        cover['ben'].save()
        SubstituteRequest.objects.create(requester=cover['ann'], date=timezone.localdate() - timedelta(days=3), status='filled',
                                         substitute=cover['dan'], filled_how='claimed')            # Dan covered recently
    mon = _next(0, 1)
    leave = _leave(cover, mon)
    _approve(cover, leave)
    rows = _cover_rows(leave)
    # Cat teaches art P1 on Monday so is busy then; Dan has covered more lately, so Cat gets P2 and Dan gets P1.
    by_period = {r.period.name: r.substitute.full_name for r in rows}
    assert by_period == {'P1': 'Dan Maths', 'P2': 'Cat Maths'}
    assert all(r.substitute_id != cover['eve'].id for r in rows)                                    # Eve teaches Art: never chosen


@pytest.mark.django_db
def test_nobody_qualified_leaves_an_open_request_and_tells_the_office(cover):
    with use_tenant(cover['s']):
        for k in ('ben', 'cat', 'dan'):
            cover[k].is_active = False
            cover[k].save()
    mon = _next(0, 1)
    leave = _leave(cover, mon)
    out = _approve(cover, leave)
    rows = _cover_rows(leave)
    assert [r.status for r in rows] == ['open', 'open'] and out['substitute_assigned'] is False
    assert [s['relief_teacher_name'] for s in out['substitutions']] == ['', '']
    assert Notification.objects.filter(recipient=cover['admin'], title='Cover needed for approved leave').count() == 1
    # HR can assign Eve only with a reason; Eve cannot take it herself.
    req = rows[0]
    eve_user = __import__('django.contrib.auth', fromlist=['x']).get_user_model().objects.get(email=cover['eve'].email)
    assert _client(eve_user).post(f'{HR}/cover/{req.id}/accept/').status_code == 403
    assert cover['office'].post(f'{HR}/cover/{req.id}/assign/', {'teacher_id': str(cover['eve'].id)}, format='json').status_code == 400
    ok = cover['office'].post(f'{HR}/cover/{req.id}/assign/', {'teacher_id': str(cover['eve'].id), 'override_reason': 'Art teacher is a qualified maths grad'}, format='json')
    assert ok.status_code == 200 and ok.json()['status'] == 'filled'
    with use_tenant(cover['s']):
        assert SubstituteRequest.objects.get(pk=req.id).override_reason.startswith('Art teacher')
    cands = cover['office'].get(f'{HR}/cover/{rows[1].id}/candidates/').json()
    assert cands and all(c['qualified'] is False and 'qualified for Art' in c['reason'] for c in cands if c['name'] == 'Eve Art')


@pytest.mark.django_db
def test_candidates_and_cover_requests_follow_the_qualification_rule(cover):
    mon = _next(0, 1)
    ann = _client(__import__('django.contrib.auth', fromlist=['x']).get_user_model().objects.get(email=cover['ann'].email))
    made = ann.post(f'{HR}/cover/', {'date': str(mon), 'entry_id': str(cover['e']['ann_mon2'].id)}, format='json').json()
    # Eve (art) is free in P2 but cannot take a maths period; Dan can.
    eve = _client(__import__('django.contrib.auth', fromlist=['x']).get_user_model().objects.get(email=cover['eve'].email))
    assert eve.get(f'{HR}/cover/').json() == []
    assert eve.post(f"{HR}/cover/{made['id']}/accept/").status_code == 403
    dan = _client(__import__('django.contrib.auth', fromlist=['x']).get_user_model().objects.get(email=cover['dan'].email))
    assert [r['id'] for r in dan.get(f'{HR}/cover/').json()] == [made['id']]
    # With the rule switched off Eve may take it.
    cover['office'].patch(f'{ACAD}/scheduling/policy/', {'enforce_subject_match': False}, format='json')
    assert eve.post(f"{HR}/cover/{made['id']}/accept/").status_code == 200


@pytest.mark.django_db
def test_half_day_leave_covers_only_that_half(cover):
    mon = _next(0, 1)
    leave = _leave(cover, mon, day_part='pm')
    _approve(cover, leave)
    assert [r.period.name for r in _cover_rows(leave)] == ['P2']
    leave2 = _leave(cover, _next(0, 2), day_part='am')
    _approve(cover, leave2)
    assert [r.period.name for r in _cover_rows(leave2)] == ['P1']


@pytest.mark.django_db
def test_weekly_limit_stops_cover_and_the_period_stays_open(cover):
    with use_tenant(cover['s']):
        SchedulingPolicy.objects.create(tenant=cover['s'], max_periods_per_week=1, max_periods_per_day=6)
        for k in ('cat', 'dan'):
            cover[k].is_active = False
            cover[k].save()
    leave = _leave(cover, _next(0, 1))
    _approve(cover, leave)
    rows = _cover_rows(leave)
    # Ben (relief, no timetable) can take one period this week; the second would pass the limit of 1 and stays open.
    assert sorted(r.status for r in rows) == ['filled', 'open']


@pytest.mark.django_db
def test_cancelling_or_moving_leave_removes_only_future_cover(cover):
    mon = _next(0, 1)
    leave = _leave(cover, mon)
    _approve(cover, leave)
    assert len(_cover_rows(leave)) == 2
    moved = cover['office'].patch(f'{ACAD}/teacher-leaves/{leave.id}/', {'start_date': str(_next(1, 1)), 'end_date': str(_next(1, 1))}, format='json')
    assert moved.status_code == 200, moved.content
    assert [(r.date.weekday(), r.period.name) for r in _cover_rows(leave)] == [(1, 'P1')]          # now Tuesday only
    cancel = cover['office'].patch(f'{ACAD}/teacher-leaves/{leave.id}/', {'status': 'cancelled'}, format='json')
    assert cancel.status_code == 200 and cancel.json()['substitute_assigned'] is False
    assert _cover_rows(leave) == []
    assert Notification.objects.filter(recipient__email=cover['ben'].email, title='Cover cancelled').exists()


@pytest.mark.django_db
def test_refresh_command_fills_open_periods_once_someone_qualified_is_free(cover):
    with use_tenant(cover['s']):
        for k in ('ben', 'cat', 'dan'):
            cover[k].is_active = False
            cover[k].save()
    leave = _leave(cover, _next(0, 1))
    _approve(cover, leave)
    assert [r.status for r in _cover_rows(leave)] == ['open', 'open']
    with use_tenant(cover['s']):
        cover['dan'].is_active = True
        cover['dan'].save()
    call_command('refresh_cover', '--days', '30')
    assert [r.status for r in _cover_rows(leave)] == ['filled', 'filled']
    assert {r.substitute_id for r in _cover_rows(leave)} == {cover['dan'].id}
    call_command('refresh_cover', '--days', '30')                                                  # a second run changes nothing
    assert len(_cover_rows(leave)) == 2


@pytest.mark.django_db
def test_substitutions_endpoint_lists_dated_cover_and_hides_it_from_strangers(cover):
    leave = _leave(cover, _next(1, 1))
    _approve(cover, leave)
    rows = cover['office'].get(f'{ACAD}/timetable-substitutions/', {'leave_id': str(leave.id)}).json()
    rows = rows['results'] if isinstance(rows, dict) else rows
    assert len(rows) == 1 and rows[0]['relief_teacher_name'] == 'Ben Relief' and rows[0]['subject_name'] == 'Mathematics'
    eve = _client(__import__('django.contrib.auth', fromlist=['x']).get_user_model().objects.get(email=cover['eve'].email))
    seen = eve.get(f'{ACAD}/timetable-substitutions/', {'leave_id': str(leave.id)}).json()
    assert (seen['results'] if isinstance(seen, dict) else seen) == []
