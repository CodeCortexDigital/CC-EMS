"""Alerts for unusual use of personal information, and the draft initial breach report."""
import uuid
from datetime import datetime, timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from services.core.audit.models import AuditLog
from services.core.security import access_alerts as aa
from services.core.security.models import AccessAlert
from tests.safety_helpers import api
from tests.test_records import world  # noqa: F401  (a school with an administrator, a teacher and a parent, and a second school)

URL = '/api/v1/security/access-alerts/'


def _noon(days_ago=2):
    return timezone.make_aware(datetime.combine((timezone.localtime() - timedelta(days=days_ago)).date(), datetime.min.time())).replace(hour=12)


def _log(school, user, action, resource_type, at, resource_id=None):
    row = AuditLog.objects.create(user=user, school=school, action=action, resource_type=resource_type, resource_id=resource_id)
    AuditLog.objects.filter(pk=row.pk).update(timestamp=at)         # unchained rows can be dated for the test


def _views(world, count, start, step=timedelta(minutes=1), user=None):  # noqa: F811
    for i in range(count):
        _log(world['a'], user or world['teacher'], 'VIEW', 'students/profile', start + step * i, resource_id=uuid.uuid4())


class TestDetection:
    def test_many_different_records_in_an_hour_raise_an_alert(self, world):  # noqa: F811
        _views(world, 30, _noon())
        assert aa.detect(world['a']) == 1
        a = AccessAlert.objects.get()
        assert (a.kind, a.user, a.status, a.details['count'], a.details['limit']) == ('bulk_views', world['teacher'], 'open', 30, 30)
        assert len(a.details['students']) == 30

    def test_one_fewer_does_not(self, world):  # noqa: F811
        _views(world, 29, _noon())
        assert aa.detect(world['a']) == 0

    def test_the_same_record_opened_again_counts_once(self, world):  # noqa: F811
        sid = uuid.uuid4()
        for i in range(60):
            _log(world['a'], world['teacher'], 'VIEW', 'students/profile', _noon() + timedelta(minutes=i % 50), resource_id=sid)
        assert aa.detect(world['a']) == 0

    def test_a_slow_trickle_over_several_hours_does_not(self, world):  # noqa: F811
        _views(world, 40, _noon(), step=timedelta(minutes=12))          # 40 records over 8 hours: at most 5 in any hour
        assert aa.detect(world['a']) == 0

    def test_running_it_again_finds_nothing_new_and_two_separate_bursts_are_two_alerts(self, world):  # noqa: F811
        _views(world, 30, _noon())
        _views(world, 30, _noon() + timedelta(hours=5))
        assert aa.detect(world['a']) == 2
        assert aa.detect(world['a']) == 0
        assert AccessAlert.objects.count() == 2

    def test_night_time_has_a_lower_limit(self, world):  # noqa: F811
        night = _noon().replace(hour=23)
        _views(world, 5, night)
        _views(world, 5, _noon() - timedelta(days=1), user=world['admin'])          # the same number at midday: nothing
        assert aa.detect(world['a']) == 1
        a = AccessAlert.objects.get()
        assert a.kind == 'night_views' and a.user == world['teacher']

    def test_exports_count_but_prints_do_not(self, world):  # noqa: F811
        for i in range(5):
            _log(world['a'], world['teacher'], 'EXPORT', 'students/export', _noon() + timedelta(minutes=i))
        for i in range(8):
            _log(world['a'], world['admin'], 'EXPORT', 'print/records', _noon() + timedelta(minutes=i))
        assert aa.detect(world['a']) == 1
        assert AccessAlert.objects.get().kind == 'bulk_exports'

    def test_many_refused_requests_raise_one(self, world):  # noqa: F811
        for i in range(10):
            _log(world['a'], world['teacher'], 'PERMISSION_DENIED', f'finance/invoices/{i}', _noon() + timedelta(minutes=i))
        assert aa.detect(world['a']) == 1
        assert AccessAlert.objects.get().kind == 'refused'

    def test_each_school_is_looked_at_on_its_own(self, world):  # noqa: F811
        _views(world, 30, _noon())
        assert aa.detect(world['b']) == 0
        assert aa.detect(world['a']) == 1

    def test_old_activity_is_not_looked_at(self, world):  # noqa: F811
        _views(world, 30, _noon(days_ago=45))
        assert aa.detect(world['a']) == 0

    def test_the_limits_are_the_schools_own(self, world):  # noqa: F811
        world['a'].settings_json = {'access_alerts': {'views': 5}}
        world['a'].save()
        _views(world, 5, _noon())
        assert aa.detect(world['a']) == 1


class TestApi:
    def test_the_screen_checks_the_log_and_lists_alerts_open_first(self, world):  # noqa: F811
        _views(world, 30, _noon())
        d = api(world['admin']).get(URL).json()
        assert d['new'] == 1 and d['open'] == 1 and d['limits']['views'] == 30 and d['defaults']['exports'] == 5
        r = d['results'][0]
        assert (r['kind'], r['who'], r['count'], r['status']) == ('bulk_views', world['teacher'].full_name or world['teacher'].email, 30, 'open')
        assert api(world['admin']).get(URL).json()['new'] == 0
        assert api(world['admin']).get(URL, {'check': '0'}).json()['open'] == 1

    def test_the_overview_shows_how_many_are_open(self, world):  # noqa: F811
        _views(world, 30, _noon())
        api(world['admin']).get(URL)
        assert api(world['admin']).get('/api/v1/security/overview/').json()['access_alerts_open'] == 1

    def test_the_limits_can_be_changed_and_a_bad_value_is_refused(self, world):  # noqa: F811
        a = api(world['admin'])
        r = a.put(URL, {'limits': {'views': 5, 'night_views': 2, 'exports': 3, 'refused': 4}}, format='json')
        assert r.status_code == 200 and r.json()['limits'] == {'views': 5, 'night_views': 2, 'exports': 3, 'refused': 4}
        assert a.put(URL, {'limits': {'views': 0}}, format='json').status_code == 400
        assert a.put(URL, {'limits': {'views': 'many'}}, format='json').status_code == 400
        assert AuditLog.objects.filter(resource_type='security/access-alert-limits').exists()
        assert api(world['admin_b']).get(URL).json()['limits']['views'] == 30

    def test_an_alert_is_reviewed_with_a_note_and_can_be_reopened(self, world):  # noqa: F811
        _views(world, 30, _noon())
        c = api(world['admin'])
        alert = c.get(URL).json()['results'][0]
        assert c.post(f'{URL}{alert["id"]}/', {'status': 'reviewed'}, format='json').status_code == 400          # a note is needed
        assert c.post(f'{URL}{alert["id"]}/', {'status': 'maybe', 'note': 'x'}, format='json').status_code == 400
        r = c.post(f'{URL}{alert["id"]}/', {'status': 'dismissed', 'note': '進路指導の準備のため'}, format='json').json()
        assert (r['status'], r['note'], bool(r['reviewed_by'])) == ('dismissed', '進路指導の準備のため', True)
        assert c.get(URL).json()['open'] == 0
        assert c.post(f'{URL}{alert["id"]}/', {'status': 'open'}, format='json').json()['status'] == 'open'
        assert AuditLog.objects.filter(resource_type='security/access-alert').count() == 2

    def test_only_this_schools_administrator_sees_or_changes_them(self, world):  # noqa: F811
        _views(world, 30, _noon())
        alert = api(world['admin']).get(URL).json()['results'][0]
        for who in ('teacher', 'mom'):
            assert api(world[who]).get(URL).status_code == 403
            assert api(world[who]).post(f'{URL}{alert["id"]}/', {'status': 'dismissed', 'note': 'x'}, format='json').status_code == 403
        assert api().get(URL).status_code == 401
        b = api(world['admin_b'])
        assert b.get(URL).json()['results'] == []
        assert b.post(f'{URL}{alert["id"]}/', {'status': 'dismissed', 'note': 'x'}, format='json').status_code == 404
        assert b.get(f'{URL}{alert["id"]}/report/').status_code == 404


class TestReport:
    def _alert(self, world):  # noqa: F811
        _views(world, 30, _noon())
        return api(world['admin']).get(URL).json()['results'][0]['id']

    def test_the_japanese_draft_fills_what_is_known_and_marks_the_rest(self, world):  # noqa: F811
        alert = self._alert(world)
        d = api(world['admin']).get(f'{URL}{alert}/report/').json()
        sections = {s['heading']: s['text'] for s in d['sections']}
        assert d['title'].startswith('個人データの漏えい等のおそれに関する報告')
        assert '30 名分の生徒記録を閲覧' in sections['概要'] and world['teacher'].email in sections['概要']
        assert sections['本人の数'] == '30 名(ログによる)'
        assert '要確認' in sections['原因'] and '要確認' in sections['二次被害のおそれ']
        assert any('3〜5日' in g and '30日' in g for g in d['guidance']) and any('1,000人' in g for g in d['guidance'])
        assert d['school'] == world['a'].name and d['note']

    def test_the_english_draft(self, world):  # noqa: F811
        alert = self._alert(world)
        d = api(world['admin']).get(f'{URL}{alert}/report/', {'lang': 'en'}).json()
        sections = {s['heading']: s['text'] for s in d['sections']}
        assert 'opened the records of 30 students' in sections['Summary'] and sections['Number of people affected'] == '30 (from the log)'
        assert 'To confirm' in sections['Cause'] and d['title'].startswith('Draft initial report')

    def test_each_kind_has_its_own_summary_and_reading_it_is_audited(self, world):  # noqa: F811
        for i in range(10):
            _log(world['a'], world['teacher'], 'PERMISSION_DENIED', f'finance/invoices/{i}', _noon() + timedelta(minutes=i))
        c = api(world['admin'])
        alert = c.get(URL).json()['results'][0]
        d = c.get(f'{URL}{alert["id"]}/report/').json()
        assert '10 回拒否' in d['sections'][0]['text']
        assert AuditLog.objects.filter(resource_type='security/access-alert-report').exists()


def test_the_command_checks_every_school(world):  # noqa: F811
    _views(world, 30, _noon())
    call_command('check_access_alerts')
    assert AccessAlert.objects.filter(school=world['a']).count() == 1 and AccessAlert.objects.filter(school=world['b']).count() == 0
