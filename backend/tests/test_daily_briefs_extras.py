"""Daily briefs, second round: more figures, the one-screen headline version, and the mark-as-read stamp."""
import datetime as dt

import pytest

from services.core.tenants.context import use_tenant
from services.education.attendance.models import AttendanceRecord
from services.education.briefs import service
from services.education.briefs.models import BriefRead
from tests.safety_helpers import api, make_student, make_user
from tests.test_daily_briefs import BASE, DAY, TZ, _daily, _yday, busy, world  # noqa: F401  (busy and world are fixtures)

pytestmark = pytest.mark.django_db


class TestMoreFigures:
    def test_every_figure_listed_is_produced_and_nothing_is_produced_unlisted(self, world):
        """Runs every query of both briefs on a school with data in none of the new corners: a wrong field name would fail here."""
        with use_tenant(world['school']):
            for kind in ('morning', 'evening'):
                got = set(service.metrics.COLLECT[kind](DAY, TZ))
                listed = {m.key for m in service.metrics.METRICS if m.brief == kind}
                assert got == listed, (kind, got ^ listed)

    def test_roll_and_late_arrivals_and_behaviour_are_counted(self, busy):
        from services.education.behaviour.models import BehaviourCategory, BehaviourIncident

        s, kid = busy['school'], busy['student']
        with use_tenant(s):
            AttendanceRecord.objects.create(student=make_student(s, full_name='Late Kid'), date=_yday(), status='late')
            cat = BehaviourCategory.objects.create(name='Disruption', kind='negative')
            BehaviourIncident.objects.create(student=kid, category=cat, kind='negative', date=_yday())
            BehaviourIncident.objects.create(student=kid, category=cat, kind='negative', date=DAY)
            m = service.metrics.morning(DAY, TZ)
            e = service.metrics.evening(DAY, TZ)
        assert m['students_on_roll'] == 3 and m['late_prev'] == 1 and m['behaviour_prev'] == 1
        assert e['behaviour_today'] == 1

    def test_the_new_figures_combine_correctly_in_a_roll_up(self, world):
        keys = {m.key: m for m in service.metrics.METRICS}
        assert keys['medication_issues'].flag is True and keys['medication_doses'].agg == 'sum' and keys['students_on_roll'].agg == 'last'
        s = world['school']
        for i in range(3):
            _daily(s, dt.date(2026, 10, 5) + dt.timedelta(days=i), 'evening', forms_signed=i + 1, medication_issues=i)
        r = service.rollup(s, 'week', dt.date(2026, 10, 11))
        assert r.metrics['values']['forms_signed'] == 6 and r.metrics['values']['medication_issues'] == 3


class TestHeadlines:
    def test_a_one_screen_version_holds_only_the_few_figures_that_matter(self, busy):
        a = api(busy['admin'])
        morning = a.post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').json()
        assert [i['key'] for i in morning['headline']] == ['incidents_open', 'cover_open', 'interventions_overdue', 'attendance_rate_prev',
                                                           'fees_overdue_amount_am']
        evening = a.post(f'{BASE}/generate/', {'kind': 'evening', 'date': DAY.isoformat()}, format='json').json()
        assert 0 < len(evening['headline']) <= 5

    def test_a_figure_that_was_not_recorded_is_left_off_rather_than_shown_as_zero(self, world):
        morning = api(world['admin']).post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').json()
        assert 'attendance_rate_prev' not in [i['key'] for i in morning['headline']]            # nobody marked attendance

    def test_roll_ups_have_a_headline_too(self, world):
        _daily(world['school'], dt.date(2026, 10, 9), 'evening', attendance_rate=93.0, incidents_reported=2, payments_amount=50.0)
        r = api(world['admin']).post(f'{BASE}/rollups/generate/', {'period': 'week', 'end': '2026-10-11'}, format='json').json()
        assert [i['key'] for i in r['headline']] == ['attendance_rate', 'incidents_reported', 'payments_amount']


class TestMarkAsRead:
    def _brief(self, w):
        return api(w['admin']).post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').json()

    def test_each_administrator_stamps_their_own_reading(self, busy):
        w = busy
        second = make_user(w['school'], 'deputy@school.test', 'admin')
        b = self._brief(w)
        assert b['read_by_me'] is False and b['read_by'] == []
        mine = api(w['admin']).post(f"{BASE}/{b['id']}/read/", {}, format='json').json()
        assert mine['read_by_me'] is True and len(mine['read_by']) == 1
        again = api(w['admin']).post(f"{BASE}/{b['id']}/read/", {}, format='json').json()
        assert len(again['read_by']) == 1 and again['read_by'][0]['at'] == mine['read_by'][0]['at']      # pressing twice keeps the first time
        theirs = api(second).get(f"{BASE}/{b['id']}/").json()
        assert theirs['read_by_me'] is False and len(theirs['read_by']) == 1                           # the deputy still sees it as unread
        api(second).post(f"{BASE}/{b['id']}/read/", {}, format='json')
        assert len(api(w['admin']).get(f"{BASE}/{b['id']}/").json()['read_by']) == 2

    def test_the_lists_and_the_today_page_show_whether_you_have_read_it(self, busy):
        w = busy
        a = api(w['admin'])
        b = a.post(f'{BASE}/generate/', {'kind': 'morning'}, format='json').json()          # for the school's real today, which the Today page shows
        assert a.get(f'{BASE}/').json()[0]['read_by_me'] is False
        assert a.get(f'{BASE}/today/').json()['morning']['read_by_me'] is False
        a.post(f"{BASE}/{b['id']}/read/", {}, format='json')
        assert a.get(f'{BASE}/').json()[0]['read_by_me'] is True
        assert a.get(f'{BASE}/today/').json()['morning']['read_by_me'] is True

    def test_a_remade_draft_has_not_been_read_and_deleting_removes_the_stamps(self, busy):
        w = busy
        a = api(w['admin'])
        b = self._brief(w)
        a.post(f"{BASE}/{b['id']}/read/", {}, format='json')
        remade = a.post(f'{BASE}/generate/', {'kind': 'morning', 'date': DAY.isoformat()}, format='json').json()
        assert remade['id'] == b['id'] and remade['read_by'] == [] and remade['read_by_me'] is False
        a.post(f"{BASE}/{b['id']}/read/", {}, format='json')
        a.delete(f"{BASE}/{b['id']}/")
        with use_tenant(w['school']):
            assert BriefRead.objects.count() == 0

    def test_roll_ups_can_be_marked_read_too(self, world):
        _daily(world['school'], dt.date(2026, 10, 9), 'evening', incidents_reported=1)
        a = api(world['admin'])
        r = a.post(f'{BASE}/rollups/generate/', {'period': 'week', 'end': '2026-10-11'}, format='json').json()
        assert a.get(f'{BASE}/rollups/').json()[0]['read_by_me'] is False
        assert a.post(f"{BASE}/rollups/{r['id']}/read/", {}, format='json').json()['read_by_me'] is True
        assert a.get(f'{BASE}/rollups/').json()[0]['read_by_me'] is True

    def test_only_administrators_of_that_school_can_stamp_it(self, busy):
        w = busy
        b = self._brief(w)
        assert api(w['teacher']).post(f"{BASE}/{b['id']}/read/", {}, format='json').status_code == 403
        assert api(w['parent']).post(f"{BASE}/{b['id']}/read/", {}, format='json').status_code == 403
        assert api(w['admin2']).post(f"{BASE}/{b['id']}/read/", {}, format='json').status_code == 404
