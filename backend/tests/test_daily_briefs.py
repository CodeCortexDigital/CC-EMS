"""Morning brief and evening summary: counts only, drafted then approved by an administrator, in the school's time zone, rolled up
weekly, fortnightly and monthly, and kept for about three months."""
import datetime as dt
import json
from decimal import Decimal
from unittest import mock

import pytest

from services.core.audit.models import AuditLog
from services.core.tenants.context import use_tenant
from services.education.academics.models import Teacher
from services.education.briefs import service
from services.education.briefs.models import BriefRollup, DailyBrief
from services.education.finance.models import Invoice, Payment
from services.education.hr.models import StaffCredential
from services.education.interventions.models import Intervention
from services.education.safety.models import FollowUpTask, SafetyIncident
from services.education.attendance.models import AttendanceRecord
from services.education.students.models import HealthVisit
from tests.safety_helpers import api, make_student, make_user, two_schools

BASE = '/api/v1/auth/briefs'
TZ = service.ZoneInfo('America/New_York')
DAY = dt.date(2026, 10, 12)            # a Monday
NAME = 'Zara Quillfeather'


def _llm(*rows):
    from tests.test_ai_platform import FakeLLM

    llm = FakeLLM([])
    llm.structured_results = list(rows)
    return llm


@pytest.fixture
def world(db):
    school, other = two_schools()
    school.settings_json = {**(school.settings_json or {}), 'timezone': 'America/New_York', 'currency': 'USD', 'region': 'us'}
    school.save()
    admin = make_user(school, 'head@school.test', 'admin')
    teacher = make_user(school, 'teach@school.test', 'teacher')
    parent = make_user(school, 'mum@school.test', 'parent')
    admin2 = make_user(other, 'head@other.test', 'admin')
    student = make_student(school, full_name=NAME)
    return dict(school=school, other=other, admin=admin, teacher=teacher, parent=parent, admin2=admin2, student=student)


def _yday():
    return DAY - dt.timedelta(days=1)


def _at(day, hour=10):
    return dt.datetime.combine(day, dt.time(hour), tzinfo=TZ)


@pytest.fixture
def busy(world):
    """A school with something in every corner, all dated around DAY (Monday 12 Oct 2026)."""
    w = world
    s, kid = w['school'], w['student']
    with use_tenant(s):
        inc = SafetyIncident.objects.create(title='Fall', incident_date=_yday(), incident_time=dt.time(10), description=NAME + ' fell', reporter=w['teacher'])
        SafetyIncident.objects.filter(pk=inc.pk).update(created_at=_at(_yday()))
        FollowUpTask.objects.create(incident=inc, description='Call ' + NAME, due_date=_yday(), created_by=w['admin'])
        Intervention.objects.create(student=kid, title='Check in with ' + NAME, status='open', due_date=_yday())
        AttendanceRecord.objects.create(student=kid, date=_yday(), status='absent')
        AttendanceRecord.objects.create(student=make_student(s, full_name='Other Kid'), date=_yday(), status='present')
        HealthVisit.objects.create(student=kid, time_in=_at(_yday()), visit_type='illness')
        inv = Invoice.objects.create(student=kid, amount=Decimal('500'), due_date=_yday() - dt.timedelta(days=3), status='issued', invoice_type='tuition')
        p = Payment.objects.create(invoice=inv, amount=Decimal('100'), payment_method='cash')
        Payment.objects.filter(pk=p.pk).update(payment_date=_yday())
        t = Teacher.objects.create(tenant=s, full_name='Mr Expired', email='exp@school.test', employee_id='T1', joining_date='2020-01-01')
        StaffCredential.objects.create(teacher=t, name='Licence', expires_on=_yday())
    return w


class TestTheFigures:
    def test_morning_counts_match_what_is_in_the_school(self, busy):
        with use_tenant(busy['school']):
            v = service.metrics.morning(DAY, TZ)
        assert v['incidents_open'] == 1 and v['incidents_new'] == 1
        assert v['followups_overdue'] == 1
        assert v['interventions_overdue'] == 1 and v['interventions_unassigned'] == 1 and v['interventions_open'] == 1
        assert v['absent_prev'] == 1 and v['attendance_rate_prev'] == 50.0
        assert v['health_visits_prev'] == 1
        assert v['fees_overdue_count_am'] == 1 and v['fees_overdue_amount_am'] == 400.0
        assert v['payments_prev_count'] == 1 and v['payments_prev_amount'] == 100.0
        assert v['credentials_expired'] == 1
        assert v['cover_open'] == 0 and v['staff_on_leave'] == 0

    def test_evening_counts_look_at_the_day_itself(self, busy):
        with use_tenant(busy['school']):
            v = service.metrics.evening(_yday(), TZ)          # "today" is the day the records are dated
        assert v['incidents_reported'] == 1 and v['health_visits'] == 1
        assert v['absent_today'] == 1 and v['attendance_rate'] == 50.0 and v['attendance_marked'] == 2
        assert v['payments_count'] == 1 and v['payments_amount'] == 100.0

    def test_a_day_without_attendance_says_not_recorded_rather_than_zero(self, world):
        with use_tenant(world['school']):
            assert service.metrics.morning(DAY, TZ)['attendance_rate_prev'] is None

    def test_an_item_that_needs_attention_is_listed_first(self, busy):
        with use_tenant(busy['school']):
            b = service.generate(busy['school'], 'morning', DAY)
        keys = [a['key'] for a in b.metrics['attention']]
        assert keys[0] == 'incidents_open'                                   # safety comes before staff, support and money
        assert {'followups_overdue', 'credentials_expired', 'interventions_overdue', 'interventions_unassigned'} <= set(keys)


class TestNoNamesAnywhere:
    def test_nothing_stored_or_sent_to_the_ai_holds_a_name(self, busy):
        llm = _llm({'summary': 'One safety incident is open.'})
        from services.ai.context import AIContext

        ctx = AIContext(user=busy['admin'], role='admin', tenant=busy['school'])
        with mock.patch('services.ai.llm.get_llm_client', return_value=llm):
            b = service.generate(busy['school'], 'morning', DAY, ctx=ctx)
        assert b.narrative_source == 'ai' and b.narrative == 'One safety incident is open.'
        sent = llm.calls[0]['prompt'] + llm.calls[0]['system']
        stored = json.dumps(b.metrics) + b.narrative + b.original_narrative
        for text in (sent, stored):
            assert NAME not in text and 'Quillfeather' not in text and 'Mr Expired' not in text and 'Fall' not in text
        assert 'needs attention' in sent

    def test_the_plain_summary_has_no_names_either(self, busy):
        b = service.generate(busy['school'], 'morning', DAY)
        assert b.narrative_source == 'template'
        assert 'Quillfeather' not in b.narrative and 'Needs attention' in b.narrative

    def test_ai_can_be_switched_off_for_the_school(self, busy):
        from services.ai.context import AIContext
        from services.core.features.models import FeatureFlag

        FeatureFlag.objects.create(name='ai_daily_brief', tenant=busy['school'], is_enabled=False)
        llm = _llm({'summary': 'x'})
        with mock.patch('services.ai.llm.get_llm_client', return_value=llm):
            b = service.generate(busy['school'], 'morning', DAY, ctx=AIContext(user=busy['admin'], role='admin', tenant=busy['school']))
        assert b.narrative_source == 'template' and llm.calls == []

    def test_a_failing_ai_falls_back_to_the_plain_summary(self, busy):
        from services.ai.context import AIContext
        from services.ai.llm import LLMError

        llm = _llm()
        llm.structured = mock.Mock(side_effect=LLMError('down'))
        with mock.patch('services.ai.llm.get_llm_client', return_value=llm):
            b = service.generate(busy['school'], 'evening', DAY, ctx=AIContext(user=busy['admin'], role='admin', tenant=busy['school']))
        assert b.narrative_source == 'template' and b.narrative


class TestDraftApproveLock:
    def test_the_whole_workflow_through_the_api(self, busy):
        a = api(busy['admin'])
        made = a.post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json')
        assert made.status_code == 201 and made.json()['status'] == 'draft'
        bid = made.json()['id']
        original = made.json()['narrative']
        edited = a.patch(f'{BASE}/{bid}/', {'narrative': 'My own words.'}, format='json').json()
        assert edited['narrative'] == 'My own words.' and edited['edited'] is True and edited['original_narrative'] == original
        done = a.post(f'{BASE}/{bid}/approve/', {}, format='json').json()
        assert done['status'] == 'approved' and done['approved_by'] and done['approved_at']
        # Locked: no edit, no remake, no second approval.
        assert a.patch(f'{BASE}/{bid}/', {'narrative': 'x'}, format='json').status_code == 409
        assert a.post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').status_code == 409
        assert a.post(f'{BASE}/{bid}/approve/', {}, format='json').status_code == 409
        # Deleting is allowed, and then it can be made again as a fresh draft.
        assert a.delete(f'{BASE}/{bid}/').status_code == 204
        again = a.post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json')
        assert again.status_code == 201 and again.json()['status'] == 'draft'

    def test_a_last_edit_can_go_in_with_the_approval(self, busy):
        a = api(busy['admin'])
        bid = a.post(f'{BASE}/generate/', {'kind': 'evening', 'date': DAY.isoformat()}, format='json').json()['id']
        res = a.post(f'{BASE}/{bid}/approve/', {'narrative': 'Final wording.'}, format='json').json()
        assert res['narrative'] == 'Final wording.' and res['edited'] is True and res['status'] == 'approved'

    def test_a_draft_can_be_remade_and_it_replaces_the_old_draft(self, busy):
        a = api(busy['admin'])
        first = a.post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').json()
        a.patch(f"{BASE}/{first['id']}/", {'narrative': 'draft edit'}, format='json')
        second = a.post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').json()
        assert second['id'] == first['id'] and second['edited'] is False
        assert DailyBrief.objects.filter(kind='morning', date=DAY).count() == 1

    def test_who_approved_and_what_was_done_is_in_the_audit_log(self, busy):
        a = api(busy['admin'])
        bid = a.post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').json()['id']
        a.post(f'{BASE}/{bid}/approve/', {}, format='json')
        a.delete(f'{BASE}/{bid}/')
        rows = AuditLog.objects.filter(user=busy['admin'], resource_type__in=['daily_brief', 'dailybrief']).order_by('timestamp')
        assert [r.action for r in rows][-3:] == ['CREATE', 'UPDATE', 'DELETE']

    def test_bad_input_is_refused(self, busy):
        a = api(busy['admin'])
        assert a.post(f'{BASE}/generate/', {'kind': 'lunch'}, format='json').status_code == 400
        assert a.post(f'{BASE}/generate/', {'kind': 'morning', 'date': 'soon'}, format='json').status_code == 400


class TestAdminsOnly:
    def test_nobody_else_can_open_or_change_a_brief(self, busy):
        bid = api(busy['admin']).post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').json()['id']
        for who in ('teacher', 'parent'):
            c = api(busy[who])
            assert c.get(f'{BASE}/today/').status_code == 403
            assert c.get(f'{BASE}/').status_code == 403
            assert c.get(f'{BASE}/{bid}/').status_code == 403
            assert c.post(f'{BASE}/generate/', {'kind': 'morning'}, format='json').status_code == 403
            assert c.post(f'{BASE}/{bid}/approve/', {}, format='json').status_code == 403
            assert c.delete(f'{BASE}/{bid}/').status_code == 403
            assert c.get(f'{BASE}/rollups/').status_code == 403
            assert c.put(f'{BASE}/settings/', {'enabled': False}, format='json').status_code == 403
        assert api().get(f'{BASE}/today/').status_code in (401, 403)

    def test_another_school_never_sees_it(self, busy):
        bid = api(busy['admin']).post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').json()['id']
        other = api(busy['admin2'])
        assert other.get(f'{BASE}/{bid}/').status_code == 404
        assert other.post(f'{BASE}/{bid}/approve/', {}, format='json').status_code == 404
        assert other.get(f'{BASE}/').json() == []


class TestSchoolTimeZone:
    def test_each_school_is_prepared_at_its_own_local_time(self, world):
        w = world
        w['other'].settings_json = {**(w['other'].settings_json or {}), 'timezone': 'Pacific/Honolulu'}
        w['other'].save()
        now = dt.datetime(2026, 10, 12, 11, 0, tzinfo=dt.timezone.utc)       # 07:00 in New York, 01:00 in Honolulu
        done = service.run_due(now)
        mine = [d for d in done if d.startswith(w['school'].tenant_code)]
        theirs = [d for d in done if d.startswith(w['other'].tenant_code)]
        assert any('morning 2026-10-12' in d for d in mine) and not any('evening' in d for d in mine)
        assert not theirs                                                    # 01:00 in Honolulu: not yet
        later = service.run_due(dt.datetime(2026, 10, 12, 23, 0, tzinfo=dt.timezone.utc))   # 19:00 New York, 13:00 Honolulu
        assert any('evening 2026-10-12' in d for d in later if d.startswith(w['school'].tenant_code))
        assert any('morning 2026-10-12' in d for d in later if d.startswith(w['other'].tenant_code))

    def test_the_date_is_the_schools_date_not_the_servers(self, world):
        service.run_due(dt.datetime(2026, 10, 13, 3, 0, tzinfo=dt.timezone.utc))      # still the evening of the 12th in New York
        with use_tenant(world['school']):
            assert set(DailyBrief.objects.values_list('date', flat=True)) == {dt.date(2026, 10, 12)}

    def test_running_again_makes_nothing_new_and_a_switched_off_school_is_skipped(self, world):
        now = dt.datetime(2026, 10, 12, 23, 0, tzinfo=dt.timezone.utc)
        service.run_due(now)
        assert not [d for d in service.run_due(now) if 'morning' in d or 'evening' in d]
        with use_tenant(world['school']):
            cfg = service.get_settings()
            cfg.enabled = False
            cfg.save()
            DailyBrief.objects.all().delete()
        assert not [d for d in service.run_due(now) if d.startswith(world['school'].tenant_code)]

    def test_the_times_are_the_schools_to_change(self, world):
        a = api(world['admin'])
        assert a.put(f'{BASE}/settings/', {'morning_time': '07:15', 'evening_time': '16:30', 'enabled': True}, format='json').json()['morning_time'] == '07:15'
        assert a.put(f'{BASE}/settings/', {'morning_time': 'late'}, format='json').status_code == 400
        # 07:00 in New York is now before the school's morning time.
        done = service.run_due(dt.datetime(2026, 10, 12, 11, 0, tzinfo=dt.timezone.utc))
        assert not [d for d in done if d.startswith(world['school'].tenant_code) and 'morning' in d]
        assert a.get(f'{BASE}/today/').json()['time_zone'] == 'America/New_York'


def _daily(school, day, kind, **values):
    with use_tenant(school):
        return DailyBrief.objects.create(kind=kind, date=day, status='approved', narrative='x',
                                         metrics={'sections': [], 'attention': [], 'values': values})


class TestRollups:
    def test_figures_combine_the_right_way(self, world):
        s = world['school']
        start = dt.date(2026, 10, 5)                                         # Monday
        for i in range(7):
            d = start + dt.timedelta(days=i)
            _daily(s, d, 'evening', incidents_reported=i, attendance_rate=90 + i, incidents_open_pm=10 - i, payments_amount=100.5)
        _daily(s, start, 'morning', incidents_open=4)
        r = service.rollup(s, 'week', dt.date(2026, 10, 11))
        v = r.metrics['values']
        assert v['incidents_reported'] == sum(range(7))                      # events add up
        assert v['attendance_rate'] == 93.0                                  # rates average
        assert v['incidents_open_pm'] == 4                                   # a position is the latest day's
        assert v['payments_amount'] == 703.5
        assert r.days == 8 and r.metrics['approved_days'] == 8 and r.period_start == start and r.status == 'draft'

    def test_it_is_built_through_the_api_and_follows_the_same_approval_rules(self, world):
        a = api(world['admin'])
        _daily(world['school'], dt.date(2026, 10, 9), 'evening', incidents_reported=2)
        none = a.post(f'{BASE}/rollups/generate/', {'period': 'week', 'end': '2026-09-20'}, format='json')
        assert none.status_code == 404                                       # nothing in that week
        made = a.post(f'{BASE}/rollups/generate/', {'period': 'week', 'end': '2026-10-11'}, format='json')
        assert made.status_code == 201 and made.json()['days'] == 1
        rid = made.json()['id']
        assert a.post(f'{BASE}/rollups/{rid}/approve/', {}, format='json').json()['status'] == 'approved'
        assert a.post(f'{BASE}/rollups/generate/', {'period': 'week', 'end': '2026-10-11'}, format='json').status_code == 409
        assert [r['id'] for r in a.get(f'{BASE}/rollups/?period=week').json()] == [rid]
        assert a.delete(f'{BASE}/rollups/{rid}/').status_code == 204
        assert a.post(f'{BASE}/rollups/generate/', {'period': 'year'}, format='json').status_code == 400

    def test_week_fortnight_and_month_cover_the_right_days(self):
        assert service.period_bounds('week', dt.date(2026, 10, 11)) == (dt.date(2026, 10, 5), dt.date(2026, 10, 11))
        assert service.period_bounds('fortnight', dt.date(2026, 10, 11)) == (dt.date(2026, 9, 28), dt.date(2026, 10, 11))
        assert service.period_bounds('month', dt.date(2026, 9, 30)) == (dt.date(2026, 9, 1), dt.date(2026, 9, 30))

    def test_the_latest_finished_periods_are_made_once(self, world):
        s = world['school']
        for i in range(40):
            _daily(s, dt.date(2026, 9, 1) + dt.timedelta(days=i), 'evening', incidents_reported=1)
        today = dt.date(2026, 10, 12)
        ends = dict(service.latest_complete_periods(today))
        assert ends['week'] == dt.date(2026, 10, 11) and ends['month'] == dt.date(2026, 9, 30)
        assert (ends['fortnight'] - service.ANCHOR).days % 14 == 13 and ends['fortnight'] < today
        made = service.ensure_rollups(s, today)
        assert {r.period for r in made} == {'week', 'fortnight', 'month'}
        assert service.ensure_rollups(s, today) == []                        # nothing new the second time


class TestKeepingAboutThreeMonths:
    def test_older_days_and_roll_ups_are_removed_and_the_rest_kept(self, world):
        s = world['school']
        today = dt.date(2026, 10, 12)
        edge = today - dt.timedelta(days=service.RETENTION_DAYS)
        old = edge - dt.timedelta(days=1)
        for d in (old, edge, today):
            _daily(s, d, 'morning', incidents_open=1)
        with use_tenant(s):
            BriefRollup.objects.create(period='week', period_start=old - dt.timedelta(days=6), period_end=old, days=1, metrics={})
            BriefRollup.objects.create(period='week', period_start=edge - dt.timedelta(days=6), period_end=edge, days=1, metrics={})
        gone = service.purge(s, today)
        assert gone == {'daily': 1, 'rollups': 1}
        with use_tenant(s):
            assert set(DailyBrief.objects.values_list('date', flat=True)) == {edge, today}
            assert BriefRollup.objects.count() == 1

    def test_the_scheduled_run_does_the_trimming_too_and_only_for_its_own_school(self, world):
        w = world
        old = dt.date(2026, 10, 12) - dt.timedelta(days=200)
        _daily(w['school'], old, 'morning', incidents_open=1)
        _daily(w['other'], old, 'morning', incidents_open=1)
        service.run_due(dt.datetime(2026, 10, 12, 11, 0, tzinfo=dt.timezone.utc), schools=[w['school']])
        with use_tenant(w['school']):
            assert not DailyBrief.objects.filter(date=old).exists()
        with use_tenant(w['other']):
            assert DailyBrief.objects.filter(date=old).exists()              # untouched: it was not part of this run

    def test_the_page_says_how_long_things_are_kept(self, world):
        assert api(world['admin']).get(f'{BASE}/today/').json()['settings']['retention_days'] == service.RETENTION_DAYS == 92
