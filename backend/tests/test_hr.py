"""Staff & HR: leave counting and approval, cover requests, hiring and onboarding, contracts and credentials,
reviews and goals, pay setup and the org chart."""
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.tenants.context import use_tenant
from services.core.tenants.models import TenantMembership
from services.core.user_notifications.models import Notification
from services.education.academics.leave_days import count_days
from services.education.academics.models import (AcademicYear, ClassSubject, Classroom, LeaveBalance, LeavePolicy,
                                                  Period, SchoolClass, Subject, Teacher, TeacherLeave, TimetableEntry)
from services.education.finance.models import Payslip
from services.education.schoolcalendar.models import CalendarEvent
from tests.conftest import SchoolFactory, UserFactory

HR = '/api/v1/auth/hr'
ACAD = '/api/v1/auth/academics'


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _rows(response):
    """List endpoints may be paginated ({'results': [...]}) or plain lists."""
    data = response.json()
    return data['results'] if isinstance(data, dict) else data


def _next(weekday):
    """The next date (strictly after today) that falls on this weekday (Mon=0)."""
    d = timezone.localdate() + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


def _staff(school, name, email, **kw):
    with use_tenant(school):
        t = Teacher.objects.create(tenant=school, employee_id=kw.pop('employee_id', email.split('@')[0].upper()[:20]),
                                   full_name=name, email=email, joining_date=date(2024, 8, 1), **kw)
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.get(email=email)
    TenantMembership.objects.get_or_create(user=user, school=school, defaults={'role': 'teacher'})
    return t, user


def _role_user(school, email, role_name):
    from django.apps import apps
    user = UserFactory(email=email, full_name=role_name.title())
    TenantMembership.objects.create(user=user, school=school, role='staff')
    Role = apps.get_model('rbac_models', 'Role')
    Profile = apps.get_model('core_accounts', 'UserProfile')
    role, _ = Role.objects.get_or_create(name=role_name)
    Profile.objects.get_or_create(user=user, defaults={'role': role})
    return user


@pytest.fixture
def hr(db):
    s = SchoolFactory(name='Maple Grove Academy')
    admin = UserFactory(email='head@maple.test', full_name='Head Teacher')
    TenantMembership.objects.create(user=admin, school=s, role='admin', is_primary=True)
    hr_user = _role_user(s, 'hr@maple.test', 'hr')
    manager = _role_user(s, 'mgr@maple.test', 'manager')
    ann, ann_u = _staff(s, 'Ann Math', 'ann@maple.test', specializations=['Mathematics'])
    ben, ben_u = _staff(s, 'Ben Relief', 'ben@maple.test', teacher_type='relief', specializations=['Mathematics'])
    cat, cat_u = _staff(s, 'Cat Busy', 'cat@maple.test', specializations=['Art'])
    with use_tenant(s):
        year = AcademicYear.objects.create(tenant=s, name='2026-27', start_date=date(2026, 8, 1),
                                           end_date=date(2027, 6, 30), is_active=True)
        p1 = Period.objects.create(academic_year=year, period_number=1, name='Period 1', start_time=time(8, 0),
                                   end_time=time(8, 45), duration_minutes=45)
        p2 = Period.objects.create(academic_year=year, period_number=2, name='Period 2', start_time=time(8, 50),
                                   end_time=time(9, 35), duration_minutes=45)
        room = Classroom.objects.create(tenant=s, name='Room 1', code='R1')
        grade5 = SchoolClass.objects.create(tenant=s, name='Grade 5', code='G5')
        math = Subject.objects.create(tenant=s, name='Mathematics', code='MATH')
        art = Subject.objects.create(tenant=s, name='Art', code='ART')
        cs_math = ClassSubject.objects.create(class_ref=grade5, subject=math)
        cs_art = ClassSubject.objects.create(class_ref=grade5, subject=art)
        # Ann teaches maths in periods 1 and 2 on Mondays; Cat teaches art in period 1 on Mondays.
        e1 = TimetableEntry.objects.create(academic_year=year, class_subject=cs_math, teacher=ann, classroom=room,
                                           day_of_week='monday', period=p1)
        e2 = TimetableEntry.objects.create(academic_year=year, class_subject=cs_math, teacher=ann, classroom=room,
                                           day_of_week='monday', period=p2)
        TimetableEntry.objects.create(academic_year=year, class_subject=cs_art, teacher=cat, classroom=room,
                                      day_of_week='monday', period=p1)
    return dict(s=s, admin=admin, hr=hr_user, manager=manager, ann=ann, ann_u=ann_u, ben=ben, ben_u=ben_u, cat=cat,
                cat_u=cat_u, p1=p1, p2=p2, e1=e1, e2=e2, office=_client(admin))


# ------------------------------------------------------------------ leave: counting, half days, types

@pytest.mark.django_db
def test_leave_days_skip_weekends_holidays_and_halve_a_half_day(hr):
    s = hr['s']
    mon = _next(0)
    fri = mon + timedelta(days=4)
    assert count_days(mon, mon + timedelta(days=6), s) == 5            # Mon..Sun = 5 working days
    with use_tenant(s):
        CalendarEvent.objects.create(tenant=s, title='Fall break', kind='holiday', start_date=mon + timedelta(days=1),
                                     end_date=mon + timedelta(days=2))
    assert count_days(mon, fri, s) == 3                               # two days are school holidays
    assert count_days(mon, mon, s, 'am') == 0.5
    with use_tenant(s):
        LeavePolicy.objects.create(tenant=s, skip_weekends=False, skip_holidays=False)
    assert count_days(mon, mon + timedelta(days=6), s) == 7


@pytest.mark.django_db
def test_apply_for_half_day_and_new_us_leave_types(hr):
    ann = _client(hr['ann_u'])
    day = _next(1)
    r = ann.post(f'{ACAD}/teacher-leaves/', {'teacher': str(hr['ann'].id), 'leave_type': 'personal', 'day_part': 'am',
                                              'start_date': str(day), 'end_date': str(day)}, format='json')
    assert r.status_code == 201, r.content
    assert r.json()['days'] == 0.5 and r.json()['leave_type'] == 'personal'
    # A half day over two dates is refused.
    bad = ann.post(f'{ACAD}/teacher-leaves/', {'teacher': str(hr['ann'].id), 'leave_type': 'jury', 'day_part': 'pm',
                                                'start_date': str(_next(2)), 'end_date': str(_next(3))}, format='json')
    assert bad.status_code == 400 and 'half-day' in str(bad.json()).lower()
    for kind in ('bereavement', 'jury', 'professional', 'unpaid'):
        d = _next(3) + timedelta(days=7 * (1 + ['bereavement', 'jury', 'professional', 'unpaid'].index(kind)))
        ok = ann.post(f'{ACAD}/teacher-leaves/', {'teacher': str(hr['ann'].id), 'leave_type': kind,
                                                   'start_date': str(d), 'end_date': str(d)}, format='json')
        assert ok.status_code == 201, (kind, ok.content)


@pytest.mark.django_db
def test_balance_counts_working_days_and_new_types(hr):
    ann = hr['ann']
    mon = _next(0)
    with use_tenant(hr['s']):
        bal = LeaveBalance.objects.create(teacher=ann, personal_entitlement=3, annual_type_entitlement=10)
        TeacherLeave.objects.create(teacher=ann, leave_type='personal', start_date=mon, end_date=mon, day_part='pm',
                                    status='approved')
        TeacherLeave.objects.create(teacher=ann, leave_type='annual', start_date=mon, end_date=mon + timedelta(days=6),
                                    status='approved')
    assert bal.used_for('personal') == 0.5 and bal.balance_for('personal') == 2.5
    assert bal.used_for('annual') == 5 and bal.balance_for('annual') == 5   # weekend not counted


@pytest.mark.django_db
def test_leave_day_preview_matches_what_the_balance_will_use(hr):
    ann = _client(hr['ann_u'])
    mon = _next(0)
    q = {'start': str(mon), 'end': str(mon + timedelta(days=6))}
    assert ann.get(f'{ACAD}/leave-days/', q).json() == {'days': 5}
    assert ann.get(f'{ACAD}/leave-days/', {'start': str(mon), 'end': str(mon), 'day_part': 'pm'}).json() == {'days': 0.5}
    assert ann.get(f'{ACAD}/leave-days/', {'start': str(mon), 'end': str(mon - timedelta(days=1))}).status_code == 400
    assert ann.get(f'{ACAD}/leave-days/', {'start': 'nope', 'end': 'x'}).status_code == 400


# ------------------------------------------------------------------ leave: policy, two-step approval, carry-over

@pytest.mark.django_db
def test_two_step_approval_and_notifications(hr):
    office = hr['office']
    assert _client(hr['ann_u']).patch(f'{ACAD}/leave-policy/', {'two_step_approval': True}, format='json').status_code == 403
    assert office.patch(f'{ACAD}/leave-policy/', {'two_step_approval': True, 'carry_over_max_days': 5},
                        format='json').json()['two_step_approval'] is True
    day = _next(1)
    leave = _client(hr['ann_u']).post(f'{ACAD}/teacher-leaves/', {'teacher': str(hr['ann'].id), 'leave_type': 'sick',
                                      'start_date': str(day), 'end_date': str(day)}, format='json').json()
    url = f"{ACAD}/teacher-leaves/{leave['id']}/"
    mgr = _client(hr['manager'])
    # The manager may recommend but not give final approval.
    assert mgr.patch(url, {'status': 'approved'}, format='json').status_code == 400
    rec = mgr.patch(url, {'status': 'recommended'}, format='json')
    assert rec.status_code == 200 and rec.json()['recommended_by'] == 'mgr@maple.test'
    done = office.patch(url, {'status': 'approved', 'decision_note': 'Feel better'}, format='json')
    assert done.status_code == 200 and done.json()['decided_by'] == 'head@maple.test' and done.json()['decided_at']
    titles = list(Notification.objects.filter(recipient=hr['ann_u']).values_list('title', flat=True))
    assert 'Leave recommended for approval' in titles and 'Leave approved' in titles
    # Managers and HR see everyone's leave; a teacher only their own.
    assert len(_rows(mgr.get(f'{ACAD}/teacher-leaves/'))) == 1
    assert len(_rows(_client(hr['ben_u']).get(f'{ACAD}/teacher-leaves/'))) == 0


@pytest.mark.django_db
def test_carry_over_is_capped_and_repeatable(hr):
    office = hr['office']
    office.patch(f'{ACAD}/leave-policy/', {'carry_over_max_days': 3}, format='json')
    last_year = timezone.localdate().year - 1
    with use_tenant(hr['s']):
        bal = LeaveBalance.objects.create(teacher=hr['ann'], annual_type_entitlement=10)
        TeacherLeave.objects.create(teacher=hr['ann'], leave_type='annual', status='approved',
                                    start_date=date(last_year, 3, 4), end_date=date(last_year, 3, 4))  # a Wednesday or so
    assert _client(hr['ann_u']).post(f'{ACAD}/leave-balances/carry-over/').status_code == 403
    first = office.post(f'{ACAD}/leave-balances/carry-over/', {}, format='json').json()
    bal.refresh_from_db()
    assert first['year'] == last_year and bal.carried_over_days == 3          # ~9 left, capped at 3
    again = office.post(f'{ACAD}/leave-balances/carry-over/', {}, format='json').json()
    bal.refresh_from_db()
    assert bal.carried_over_days == 3 and again['carried'][0]['days'] == 3    # running twice changes nothing
    assert bal.entitlement_for('annual') == 13


@pytest.mark.django_db
def test_leave_calendar_shows_who_is_out(hr):
    mon = _next(0)
    with use_tenant(hr['s']):
        TeacherLeave.objects.create(teacher=hr['ann'], leave_type='sick', start_date=mon, end_date=mon, status='approved')
        TeacherLeave.objects.create(teacher=hr['cat'], leave_type='casual', start_date=mon, end_date=mon, status='pending')
    q = {'start': str(mon), 'end': str(mon + timedelta(days=6))}
    staff_view = _client(hr['ben_u']).get(f'{ACAD}/leave-calendar/', q).json()
    assert [x['name'] for x in staff_view['leaves']] == ['Ann Math']        # pending is only for reviewers
    boss_view = _client(hr['manager']).get(f'{ACAD}/leave-calendar/', q).json()
    assert {x['name'] for x in boss_view['leaves']} == {'Ann Math', 'Cat Busy'}


# ------------------------------------------------------------------ cover requests

def _cover(client, day, entry, **extra):
    return client.post(f'{HR}/cover/', {'date': str(day), 'entry_id': str(entry.id), **extra}, format='json')


@pytest.mark.django_db
def test_cover_request_claim_assign_release_and_cancel(hr):
    monday = _next(0)
    ann, ben, cat = _client(hr['ann_u']), _client(hr['ben_u']), _client(hr['cat_u'])
    made = _cover(ann, monday, hr['e1'], reason='Dentist')
    assert made.status_code == 201, made.content
    req = made.json()
    assert req['status'] == 'open' and req['subject'] == 'Mathematics' and req['class_name'] == 'Grade 5'
    assert _cover(ann, monday, hr['e1']).status_code == 400                        # no duplicates
    # Ben (relief, maths) was told; Cat teaches period 1 so cannot take it and is not asked.
    assert Notification.objects.filter(recipient=hr['ben_u'], title='Cover needed').exists()
    assert not Notification.objects.filter(recipient=hr['cat_u'], title='Cover needed').exists()
    assert cat.post(f"{HR}/cover/{req['id']}/accept/").status_code == 409
    assert ann.post(f"{HR}/cover/{req['id']}/accept/").status_code in (400, 409)   # not your own period
    seen = ben.get(f'{HR}/cover/').json()
    assert [r['id'] for r in seen] == [req['id']] and seen[0]['can_accept']
    taken = ben.post(f"{HR}/cover/{req['id']}/accept/")
    assert taken.status_code == 200 and taken.json()['status'] == 'filled' and taken.json()['substitute']['name'] == 'Ben Relief'
    assert Notification.objects.filter(recipient=hr['ann_u'], title='Your cover is arranged').exists()
    assert cat.post(f"{HR}/cover/{req['id']}/accept/").status_code == 409          # already filled
    # Ben gives it back; it opens up again and the office assigns Cat's... no: Cat is busy, so the office is refused.
    assert ben.post(f"{HR}/cover/{req['id']}/release/").json()['status'] == 'open'
    office = hr['office']
    assert office.post(f"{HR}/cover/{req['id']}/assign/", {'teacher_id': str(hr['cat'].id)}, format='json').status_code == 409
    cands = office.get(f"{HR}/cover/{req['id']}/candidates/").json()
    assert [c['name'] for c in cands] == ['Ben Relief']                           # Cat is busy, Ann is the requester
    assert cands[0]['relief'] and cands[0]['subject_match']
    assigned = office.post(f"{HR}/cover/{req['id']}/assign/", {'teacher_id': str(hr['ben'].id)}, format='json')
    assert assigned.json()['filled_how'] == 'assigned'
    assert Notification.objects.filter(recipient=hr['ben_u'], title='You were asked to cover').exists()
    assert cat.post(f"{HR}/cover/{req['id']}/cancel/").status_code == 403         # only the requester or HR
    assert ann.post(f"{HR}/cover/{req['id']}/cancel/").json()['status'] == 'cancelled'
    assert Notification.objects.filter(recipient=hr['ben_u'], title='Cover cancelled').exists()


@pytest.mark.django_db
def test_cover_rules_dates_ownership_and_visibility(hr):
    ann, ben = _client(hr['ann_u']), _client(hr['ben_u'])
    assert _cover(ann, timezone.localdate() - timedelta(days=1), hr['e1']).status_code == 400
    assert _cover(ann, _next(1), hr['e1']).status_code == 400                      # entry is a Monday period
    assert _cover(ben, _next(0), hr['e1']).status_code == 400                      # not Ben's period
    assert ben.get(f'{HR}/cover/', {'scope': 'all'}).status_code == 403
    assert ann.post(f'{HR}/cover/', {'date': str(_next(0))}, format='json').status_code == 400   # nothing chosen


@pytest.mark.django_db
def test_one_off_absence_requests_every_period_that_day(hr):
    monday = _next(0)
    r = _client(hr['ann_u']).post(f'{HR}/cover/absence/', {'date': str(monday), 'reason': 'Sick'}, format='json')
    assert r.status_code == 201 and [c['period']['number'] for c in r.json()['created']] == [1, 2]
    again = _client(hr['ann_u']).post(f'{HR}/cover/absence/', {'date': str(monday)}, format='json')
    assert again.status_code == 200 and len(again.json()['already_covered']) == 2
    assert _client(hr['ann_u']).post(f'{HR}/cover/absence/', {'date': str(_next(1))}, format='json').status_code == 400
    # The office can raise it for a teacher who phoned in.
    other = hr['office'].post(f'{HR}/cover/absence/', {'date': str(_next(0) + timedelta(days=7)),
                              'teacher_id': str(hr['cat'].id)}, format='json')
    assert other.status_code == 201 and len(other.json()['created']) == 1


@pytest.mark.django_db
def test_period_picker_lists_my_periods_for_the_date(hr):
    monday = _next(0)
    ann = _client(hr['ann_u'])
    got = ann.get(f'{HR}/cover/periods/', {'date': str(monday)}).json()
    assert [e['label'] for e in got['entries']] == ['Grade 5 Mathematics'] * 2 and len(got['periods']) == 2
    assert not got['entries'][0]['already_requested']
    _cover(ann, monday, hr['e1'])
    assert ann.get(f'{HR}/cover/periods/', {'date': str(monday)}).json()['entries'][0]['already_requested']
    assert ann.get(f'{HR}/cover/periods/', {'date': str(_next(1))}).json()['entries'] == []


@pytest.mark.django_db
def test_free_teacher_can_take_unrelated_duty_period(hr):
    monday = _next(0)
    req = hr['office'].post(f'{HR}/cover/', {'date': str(monday), 'teacher_id': str(hr['ann'].id), 'period_id': str(hr['p2'].id),
                                              'description': 'Lunch duty'}, format='json')
    assert req.status_code == 201 and req.json()['description'] == 'Lunch duty'
    assert _client(hr['cat_u']).post(f"{HR}/cover/{req.json()['id']}/accept/").json()['status'] == 'filled'


# ------------------------------------------------------------------ recruitment and onboarding

@pytest.mark.django_db
def test_hiring_pipeline_creates_staff_and_onboarding(hr):
    office, ann = hr['office'], _client(hr['ann_u'])
    assert _rows(ann.get(f'{HR}/openings/')) == []
    assert ann.post(f'{HR}/openings/', {'title': 'Science teacher'}, format='json').status_code == 403
    op = office.post(f'{HR}/openings/', {'title': 'Science teacher', 'department': 'Science', 'positions': 1}, format='json').json()
    cand = office.post(f'{HR}/candidates/', {'opening': op['id'], 'full_name': 'Dana New', 'email': 'dana@maple.test'},
                       format='json')
    assert cand.status_code == 201 and cand.json()['stage'] == 'applied'
    cid = cand.json()['id']
    mv = office.post(f'{HR}/candidates/{cid}/stage/', {'stage': 'interview', 'note': 'Phone screen ok'}, format='json').json()
    assert mv['stage'] == 'interview' and [h['to'] for h in mv['history']] == ['applied', 'interview']
    assert office.post(f'{HR}/candidates/{cid}/stage/', {'stage': 'hired'}, format='json').status_code == 400
    hired = office.post(f'{HR}/candidates/{cid}/hire/', {'joining_date': str(_next(0))}, format='json')
    assert hired.status_code == 201, hired.content
    body = hired.json()
    assert body['onboarding_tasks'] == 9 and body['candidate']['stage'] == 'hired'
    t = Teacher.objects.get(id=body['teacher_id'])
    assert t.full_name == 'Dana New' and t.role == 'Science teacher' and t.department == 'Science'
    assert office.get(f'{HR}/openings/{op["id"]}/').json()['status'] == 'closed'    # the one position is filled
    assert office.post(f'{HR}/candidates/{cid}/hire/', {}, format='json').status_code == 409
    tasks = _rows(office.get(f'{HR}/onboarding/', {'teacher_id': body['teacher_id']}))
    assert len(tasks) == 9
    done = office.patch(f"{HR}/onboarding/{tasks[0]['id']}/", {'done': True}, format='json')
    assert done.status_code == 200 and done.json()['done']


@pytest.mark.django_db
def test_hire_refuses_an_email_already_on_staff(hr):
    office = hr['office']
    op = office.post(f'{HR}/openings/', {'title': 'Cover teacher'}, format='json').json()
    cid = office.post(f'{HR}/candidates/', {'opening': op['id'], 'full_name': 'Ann Again', 'email': 'ann@maple.test'},
                      format='json').json()['id']
    assert office.post(f'{HR}/candidates/{cid}/hire/', {}, format='json').status_code == 409


# ------------------------------------------------------------------ contracts and credentials

@pytest.mark.django_db
def test_contracts_credentials_alerts_and_privacy(hr):
    office, ann, ben = hr['office'], _client(hr['ann_u']), _client(hr['ben_u'])
    today = timezone.localdate()
    assert office.post(f'{HR}/contracts/', {'teacher': str(hr['ann'].id), 'kind': 'fixed_term', 'start_date': str(today - timedelta(days=300)),
                       'end_date': str(today + timedelta(days=20)), 'probation_end': str(today + timedelta(days=5))},
                       format='json').status_code == 201
    office.post(f'{HR}/credentials/', {'teacher': str(hr['ann'].id), 'name': 'State teaching licence',
                                       'expires_on': str(today - timedelta(days=3))}, format='json')
    office.post(f'{HR}/credentials/', {'teacher': str(hr['ben'].id), 'name': 'First aid', 'expires_on': str(today + timedelta(days=400))},
                format='json')
    rows = office.get(f'{HR}/alerts/', {'days': 60}).json()
    assert [r['kind'] for r in rows] == ['credential', 'probation_end', 'contract_end']
    assert rows[0]['expired'] and rows[1]['days_left'] == 5 and all(r['teacher_name'] == 'Ann Math' for r in rows)
    assert ann.get(f'{HR}/alerts/').status_code == 403
    # A teacher sees only their own records and cannot write.
    own = _rows(ben.get(f'{HR}/credentials/'))
    assert [c['name'] for c in own] == ['First aid']
    assert ben.post(f'{HR}/credentials/', {'teacher': str(hr['ben'].id), 'name': 'x'}, format='json').status_code == 403
    cid = _rows(office.get(f'{HR}/credentials/', {'teacher_id': str(hr['ann'].id)}))[0]['id']
    assert ben.get(f'{HR}/credentials/{cid}/').status_code == 404
    ov = office.get(f'{HR}/overview/').json()
    assert ov['alert_count'] == 3 and ov['expired'] == 1 and ov['staff'] == 3


@pytest.mark.django_db
def test_alert_command_notifies_admin_once_a_day(hr):
    with use_tenant(hr['s']):
        from services.education.hr.models import StaffCredential
        StaffCredential.objects.create(teacher=hr['ann'], name='CPR', expires_on=timezone.localdate() + timedelta(days=10))
    call_command('send_hr_alerts', '--days', '30')
    call_command('send_hr_alerts', '--days', '30')
    n = Notification.objects.filter(recipient=hr['admin'], title='Staff contracts and credentials need attention')
    assert n.count() == 1 and 'Ann Math: CPR ends' in n.first().message


# ------------------------------------------------------------------ performance

@pytest.mark.django_db
def test_reviews_are_private_until_shared_and_goals_belong_to_the_owner(hr):
    office, ann, ben = hr['office'], _client(hr['ann_u']), _client(hr['ben_u'])
    rv = office.post(f'{HR}/reviews/', {'teacher': str(hr['ann'].id), 'kind': 'annual', 'period_label': '2026-27',
                                        'review_date': str(timezone.localdate()), 'rating': 4, 'strengths': 'Great rapport'},
                     format='json')
    assert rv.status_code == 201 and rv.json()['status'] == 'draft' and rv.json()['reviewer_name'] == 'Head Teacher'
    assert office.post(f'{HR}/reviews/', {'teacher': str(hr['ann'].id), 'review_date': str(timezone.localdate()), 'rating': 9},
                       format='json').status_code == 400
    rid = rv.json()['id']
    assert _rows(ann.get(f'{HR}/reviews/')) == []
    assert ann.post(f'{HR}/reviews/{rid}/acknowledge/').status_code == 409    # a draft has not been shared yet
    office.patch(f'{HR}/reviews/{rid}/', {'status': 'shared'}, format='json')
    mine = _rows(ann.get(f'{HR}/reviews/'))
    assert [r['id'] for r in mine] == [rid]
    assert ben.post(f'{HR}/reviews/{rid}/acknowledge/').status_code == 403
    ack = ann.post(f'{HR}/reviews/{rid}/acknowledge/', {'comment': 'Thanks'}, format='json')
    assert ack.json()['status'] == 'acknowledged' and ack.json()['employee_comment'] == 'Thanks'
    # Goals: the owner may move progress and status, nothing else.
    g = office.post(f'{HR}/goals/', {'teacher': str(hr['ann'].id), 'title': 'Run a maths club'}, format='json').json()
    up = ann.patch(f"{HR}/goals/{g['id']}/", {'progress': 60}, format='json')
    assert up.status_code == 200 and up.json()['progress'] == 60
    assert ann.patch(f"{HR}/goals/{g['id']}/", {'title': 'Easier goal'}, format='json').status_code == 403
    assert ben.patch(f"{HR}/goals/{g['id']}/", {'progress': 100}, format='json').status_code == 404
    assert ann.patch(f"{HR}/goals/{g['id']}/", {'progress': 120}, format='json').status_code == 400


# ------------------------------------------------------------------ pay setup

@pytest.mark.django_db
def test_pay_grade_tax_benefits_feed_payslips(hr):
    office, ann = hr['office'], _client(hr['ann_u'])
    assert ann.get(f'{HR}/payroll/profiles/').status_code == 403
    assert _client(hr['manager']).get(f'{HR}/payroll/grades/').status_code == 403   # a manager is not payroll
    g = office.post(f'{HR}/payroll/grades/', {'name': 'Teacher L2', 'base_salary': '3000'}, format='json')
    assert g.status_code == 201
    assert office.post(f'{HR}/payroll/grades/', {'name': 'Teacher L2', 'base_salary': '1'}, format='json').status_code == 400
    p = office.patch(f"{HR}/payroll/profiles/{hr['ann'].id}/", {
        'pay_grade': g.json()['id'], 'tax_rate_percent': '10',
        'benefits': [{'name': 'Transport', 'amount': '200', 'kind': 'allowance'},
                     {'name': 'Health plan', 'amount': '100', 'kind': 'deduction'}]}, format='json').json()
    assert (p['basic'], p['allowances'], p['tax'], p['deductions'], p['net']) == (3000, 200, 320, 420, 2780)
    assert office.patch(f"{HR}/payroll/profiles/{hr['ann'].id}/", {'tax_rate_percent': '90'}, format='json').status_code == 400
    assert office.patch(f"{HR}/payroll/profiles/{hr['ann'].id}/", {'benefits': [{'name': 'x', 'amount': '-1'}]},
                        format='json').status_code == 400
    with use_tenant(hr['s']):
        Teacher.objects.filter(pk=hr['ben'].pk).update(monthly_salary=Decimal('2000'))
    gen = office.post('/api/v1/auth/finance/payslips/bulk-generate/', {'month': '2026-10-01'}, format='json')
    assert gen.status_code == 200, gen.content
    with use_tenant(hr['s']):
        slip = Payslip.objects.get(employee=hr['ann'])
        assert (slip.basic_salary, slip.allowances, slip.deductions, slip.net_salary) == (3000, 200, 420, 2780)
        assert 'Tax withheld' in slip.notes
        assert Payslip.objects.get(employee=hr['ben']).net_salary == 2000          # no profile: salary as before


# ------------------------------------------------------------------ directory and org chart

@pytest.mark.django_db
def test_org_chart_reporting_lines_and_loops(hr):
    office = hr['office']
    ann, ben, cat = hr['ann'], hr['ben'], hr['cat']
    assert _client(hr['ann_u']).post(f'{HR}/directory/{ben.id}/manager/', {'manager_id': str(ann.id)}, format='json').status_code == 403
    assert office.post(f'{HR}/directory/{ben.id}/manager/', {'manager_id': str(ann.id)}, format='json').status_code == 200
    assert office.post(f'{HR}/directory/{cat.id}/manager/', {'manager_id': str(ben.id)}, format='json').status_code == 200
    assert office.post(f'{HR}/directory/{ann.id}/manager/', {'manager_id': str(cat.id)}, format='json').status_code == 400   # loop
    assert office.post(f'{HR}/directory/{ann.id}/manager/', {'manager_id': str(ann.id)}, format='json').status_code == 400
    tree = _client(hr['cat_u']).get(f'{HR}/org-chart/').json()
    assert tree['count'] == 3 and [n['name'] for n in tree['tree']] == ['Ann Math']
    assert tree['tree'][0]['reports'][0]['name'] == 'Ben Relief' and tree['tree'][0]['reports'][0]['reports'][0]['name'] == 'Cat Busy'
    rows = _client(hr['cat_u']).get(f'{HR}/directory/').json()
    assert {r['name']: r['manager_name'] for r in rows}['Cat Busy'] == 'Ben Relief'
    assert 'monthly_salary' not in rows[0] and 'national_id' not in rows[0]
    assert office.post(f'{HR}/directory/{ben.id}/manager/', {'manager_id': None}, format='json').json()['manager_id'] is None


@pytest.mark.django_db
def test_my_hr_summary(hr):
    with use_tenant(hr['s']):
        from services.education.hr.models import StaffGoal
        StaffGoal.objects.create(teacher=hr['ann'], title='Learn the gradebook')
    me = _client(hr['ann_u']).get(f'{HR}/me/').json()
    assert me['linked'] and me['teacher']['name'] == 'Ann Math' and me['goals'][0]['title'] == 'Learn the gradebook'
    assert _client(hr['admin']).get(f'{HR}/me/').json() == {'linked': False}
