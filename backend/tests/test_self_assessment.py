"""The self-assessment for the board: lines the system works out from its own state, and lines only the school can answer."""
from unittest import mock

import pytest

from services.core.audit import chain
from services.core.security import assessment
from tests.safety_helpers import api, make_user, two_schools

A = '/api/v1/security/self-assessment/'
P = '/api/v1/privacy'


@pytest.fixture
def world(db, settings):
    settings.TIMESTAMP_AUTHORITY_URL = ''
    a, b = two_schools()
    return {'a': a, 'b': b, 'admin': make_user(a, 'head@a.test', 'admin'), 'admin_b': make_user(b, 'head@b.test', 'admin'),
            'parent': make_user(a, 'mom@a.test', 'parent')}


def _get(world, who='admin'):
    r = api(world[who]).get(A)
    assert r.status_code == 200, r.content
    return r.json()


def _item(data, key):
    return next(i for i in data['items'] if i['key'] == key)


class TestShape:
    def test_it_says_it_is_not_an_audit_and_adds_up(self, world):
        d = _get(world)
        assert 'not an audit' in d['disclaimer'] and 'legal advice' in d['disclaimer']
        s = d['summary']
        assert s['met'] + s['partly'] + s['open'] == s['total'] == len(d['items'])
        assert {i['source'] for i in d['items']} == {'system', 'school'}
        assert all(i['text'] and i['area'] and i['status'] in ('met', 'partly', 'open') for i in d['items'])

    def test_lines_only_the_school_can_answer_start_open_and_say_so(self, world):
        d = _get(world)
        manual = [i for i in d['items'] if i['source'] == 'school']
        assert {i['key'] for i in manual} == assessment.MANUAL_KEYS
        assert all(i['status'] == 'open' and i['evidence'] == 'Not answered yet.' for i in manual)

    def test_only_this_schools_administrator(self, world):
        assert api(world['parent']).get(A).status_code == 403
        assert api(world['parent']).put(A, {'key': 'officer', 'answer': 'yes'}, format='json').status_code == 403
        assert api().get(A).status_code == 401


class TestWorkedOutByTheSystem:
    def test_the_register_and_the_notice(self, world):
        d = _get(world)
        assert _item(d, 'register')['status'] == 'open' and _item(d, 'notice')['status'] == 'open' and _item(d, 'consent')['status'] == 'met'
        a = api(world['admin'])
        a.post(f'{P}/register/', {'action': 'load_defaults', 'lang': 'en'}, format='json')
        d = _get(world)
        assert _item(d, 'register')['status'] == 'met' and '13 lines' in _item(d, 'register')['evidence']
        assert _item(d, 'consent')['status'] == 'open'                                    # sensitive lines, no consent question yet
        a.post(f'{P}/notice-draft/', {'ensure_consent': True}, format='json')
        assert _item(_get(world), 'consent')['status'] == 'met'
        draft = a.get(f'{P}/notice-draft/').json()
        a.post(f'{P}/documents/', {'title': draft['title'], 'body': draft['body']}, format='json')
        d = _get(world)
        assert _item(d, 'notice')['status'] == 'met' and _item(d, 'notice_read')['status'] == 'open' and '0 of' in _item(d, 'notice_read')['evidence']

    def test_a_register_changed_after_the_notice_makes_it_partly(self, world):
        a = api(world['admin'])
        a.post(f'{P}/register/', {'action': 'load_defaults', 'lang': 'en'}, format='json')
        draft = a.get(f'{P}/notice-draft/').json()
        a.post(f'{P}/documents/', {'title': draft['title'], 'body': draft['body']}, format='json')
        line = a.get(f'{P}/register/').json()['entries'][0]
        a.post(f'{P}/register/', {**line, 'purpose': 'changed'}, format='json')
        assert _item(_get(world), 'notice')['status'] == 'partly'

    def test_security_rules(self, world):
        d = _get(world)
        assert _item(d, 'admin_2fa')['status'] == 'open' and _item(d, 'lockout')['status'] == 'met' and _item(d, 'access_roles')['status'] == 'met'
        world['a'].settings_json = {'security': {'admin_two_factor': 1, 'idle_minutes': 20}}
        world['a'].save(update_fields=['settings_json'])
        d = _get(world)
        assert _item(d, 'admin_2fa')['status'] == 'met' and _item(d, 'idle')['status'] == 'met' and '20 minutes' in _item(d, 'idle')['evidence']

    def test_the_ai_lines_follow_the_schools_ai_switches(self, world):
        d = _get(world)
        assert all(_item(d, k)['status'] == 'open' for k in ('ai_training', 'ai_enforced', 'ai_notice', 'ai_names'))
        assert _item(d, 'ai_human')['status'] == 'met'
        c = api(world['admin'])
        c.put('/api/v1/ai/settings/controls/', {'require_training': True, 'require_user_notice': True, 'mask_names': True}, format='json')
        c.post('/api/v1/ai/settings/training-confirmation/', {'provider': 'x', 'confirmed_on': '2026-11-01'}, format='json')
        d = _get(world)
        assert all(_item(d, k)['status'] == 'met' for k in ('ai_training', 'ai_enforced', 'ai_notice', 'ai_names'))

    def test_the_trail_and_its_outside_time_stamp(self, world, settings):
        chain.append(user=world['admin'], school=world['a'], action='UPDATE', resource_type='ai.settings.x', new_data={})
        d = _get(world)
        assert _item(d, 'chain')['status'] == 'met' and _item(d, 'timestamp')['status'] == 'open' and 'No time-stamping authority' in _item(d, 'timestamp')['evidence']
        settings.TIMESTAMP_AUTHORITY_URL = 'https://tsa.example/stamp'
        assert _item(_get(world), 'timestamp')['evidence'] == 'Never time-stamped.'
        from tests.test_timestamp_anchor import _tsa

        with _tsa():
            api(world['admin']).post('/api/v1/security/timestamps/')
        assert _item(_get(world), 'timestamp')['status'] == 'met'
        chain.append(user=world['admin'], school=world['a'], action='UPDATE', resource_type='ai.settings.x', new_data={})
        assert _item(_get(world), 'timestamp')['status'] == 'partly'

    def test_a_broken_chain_is_open(self, world):
        chain.append(user=world['admin'], school=world['a'], action='UPDATE', resource_type='ai.settings.x', new_data={})
        from services.core.audit.models import AuditLog
        AuditLog._base_manager.filter(chain=str(world['a'].pk)).update(entry_hash='0' * 64)
        assert _item(_get(world), 'chain')['status'] == 'open'

    def test_open_alerts_make_the_alert_line_partly(self, world):
        assert _item(_get(world), 'alerts')['status'] == 'met'
        from django.utils import timezone

        from services.core.security.models import AccessAlert
        now = timezone.now()
        AccessAlert.objects.create(school=world['a'], kind='bulk_views', window_start=now, window_end=now)
        assert _item(_get(world), 'alerts')['status'] == 'partly'


class TestAnswers:
    def test_an_answer_is_kept_with_who_and_when(self, world):
        r = api(world['admin']).put(A, {'key': 'officer', 'answer': 'yes', 'note': 'Ms Sato, deputy head'}, format='json')
        assert r.status_code == 200
        i = _item(r.json(), 'officer')
        assert i['status'] == 'met' and i['evidence'] == 'Ms Sato, deputy head' and i['answered_by'] == 'head@a.test' and i['answered_at']

    def test_partly_and_no_and_clearing(self, world):
        c = api(world['admin'])
        assert _item(c.put(A, {'key': 'training', 'answer': 'partly'}, format='json').json(), 'training')['status'] == 'partly'
        assert _item(c.put(A, {'key': 'training', 'answer': 'no', 'note': 'planned'}, format='json').json(), 'training')['status'] == 'open'
        cleared = _item(c.put(A, {'key': 'training', 'answer': ''}, format='json').json(), 'training')
        assert cleared['status'] == 'open' and cleared['evidence'] == 'Not answered yet.'

    def test_only_lines_for_the_school_with_a_proper_answer(self, world):
        c = api(world['admin'])
        assert c.put(A, {'key': 'register', 'answer': 'yes'}, format='json').status_code == 400       # worked out by the system
        assert c.put(A, {'key': 'nothing', 'answer': 'yes'}, format='json').status_code == 400
        assert c.put(A, {'key': 'officer', 'answer': 'maybe'}, format='json').status_code == 400

    def test_one_schools_answers_are_not_another_schools(self, world):
        api(world['admin']).put(A, {'key': 'officer', 'answer': 'yes'}, format='json')
        assert _item(_get(world, 'admin_b'), 'officer')['status'] == 'open'

    def test_answers_are_recorded_in_the_activity_log(self, world):
        from services.core.audit.models import AuditLog

        api(world['admin']).put(A, {'key': 'backup', 'answer': 'yes'}, format='json')
        assert AuditLog.objects.filter(resource_type='security/self-assessment', school=world['a']).exists()


class TestDownload:
    def test_csv_with_the_disclaimer_first(self, world):
        api(world['admin']).put(A, {'key': 'officer', 'answer': 'yes', 'note': 'Ms Sato'}, format='json')
        r = api(world['admin']).get(A, {'export': 'csv'})
        text = r.content.decode('utf-8-sig')
        lines = text.splitlines()
        assert r['Content-Type'].startswith('text/csv') and 'not an audit' in lines[0]
        assert lines[1].startswith('Area,Line,Status,Source,Evidence or note')
        assert 'Ms Sato' in text and 'System' in text and 'School' in text and 'Met' in text
