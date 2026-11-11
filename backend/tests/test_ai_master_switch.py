"""One switch turns all AI off for a school, including the risk scoring, and every change to the switches is a recorded decision."""
from unittest import mock

import pytest

from services.ai.context import AIContext
from services.ai.quota import ai_enabled, feature_enabled
from services.core.audit import chain
from services.core.audit.models import AuditLog
from tests.safety_helpers import api, make_user, two_schools

URL = '/api/v1/ai/settings/'
RISK_URLS = [('get', '/api/v1/ai/student-predictions/'), ('get', '/api/v1/ai/attendance-anomalies/'), ('post', '/api/v1/ai/train-models/')]


@pytest.fixture
def world(db):
    a, b = two_schools()
    return {'a': a, 'b': b, 'admin': make_user(a, 'head@a.test', 'admin'), 'admin_b': make_user(b, 'head@b.test', 'admin'),
            'teacher': make_user(a, 'tim.teacher@a.test', 'teacher')}


@pytest.fixture(autouse=True)
def no_provider():
    with mock.patch('services.ai.settings_api.get_llm_client', return_value=None):
        yield


def _ctx(user, school):
    return AIContext(user=user, role='admin', tenant=school)


def test_the_master_switch_turns_everything_off_for_one_school_only(world):
    c = api(world['admin'])
    assert c.get(URL).json()['ai_enabled'] is True
    data = c.put(URL, {'ai_enabled': False}, format='json').json()
    assert data['ai_enabled'] is False and all(f['enabled'] for f in data['features'] if f['key'] != 'ai_face_attendance')      # each feature keeps its own setting
    assert ai_enabled(_ctx(world['admin'], world['a'])) is False
    assert feature_enabled('ai_chat', _ctx(world['admin'], world['a'])) is False
    assert feature_enabled('ai_chat', _ctx(world['admin_b'], world['b'])) is True
    assert api(world['admin_b']).get(URL).json()['ai_enabled'] is True


def test_switching_it_back_on_restores_what_each_feature_was(world):
    c = api(world['admin'])
    c.put(URL, {'features': {'ai_translation': False}}, format='json')
    c.put(URL, {'ai_enabled': False}, format='json')
    c.put(URL, {'ai_enabled': True}, format='json')
    ctx = _ctx(world['admin'], world['a'])
    assert feature_enabled('ai_translation', ctx) is False and feature_enabled('ai_quiz', ctx) is True


@pytest.mark.parametrize('method,url', RISK_URLS)
def test_the_risk_scoring_endpoints_refuse_while_ai_is_off(world, method, url):
    c = api(world['admin'])
    c.put(URL, {'ai_enabled': False}, format='json')
    res = getattr(c, method)(url)
    assert res.status_code == 403 and res.json()['ai_off'] is True
    c.put(URL, {'ai_enabled': True}, format='json')
    assert getattr(c, method)(url).status_code != 403


def test_reviewing_and_notifying_about_a_risk_flag_refuse_while_ai_is_off(world):
    c = api(world['admin'])
    c.put(URL, {'ai_enabled': False}, format='json')
    assert c.post('/api/v1/ai/student-predictions/00000000-0000-0000-0000-000000000001/review/', {'decision': 'confirmed'}, format='json').status_code == 403
    assert c.post('/api/v1/ai/dropout-risk/notify/', {'student_id': '00000000-0000-0000-0000-000000000001'}, format='json').status_code == 403


def test_the_risk_scoring_has_its_own_switch(world):
    c = api(world['admin'])
    c.put(URL, {'features': {'ai_risk_scan': False}}, format='json')
    assert c.get('/api/v1/ai/student-predictions/').status_code == 403
    assert api(world['admin_b']).get('/api/v1/ai/student-predictions/').status_code != 403


def test_every_change_is_a_recorded_decision_that_verifies(world):
    c = api(world['admin'])
    c.put(URL, {'ai_enabled': False}, format='json')
    c.put(URL, {'features': {'ai_translation': False}}, format='json')
    steps = list(AuditLog.objects.filter(chain=str(world['a'].pk)).order_by('seq'))
    assert [(s.resource_type, s.new_data['feature'], s.new_data['was_on'], s.new_data['now_on']) for s in steps] == [
        ('ai.settings.master', 'ai_master', True, False), ('ai.settings.feature', 'ai_translation', True, False)]
    assert steps[0].new_data['actor'] == 'head@a.test' and chain.verify()['ok']


def test_a_change_that_cannot_be_recorded_is_not_made(world):
    c = api(world['admin'])
    with mock.patch('services.ai.settings_api.audit_chain.append', side_effect=chain.AuditWriteError('down')):
        res = c.put(URL, {'ai_enabled': False}, format='json')
    assert res.status_code == 503 and ai_enabled(_ctx(world['admin'], world['a'])) is True


def test_accepting_the_notice_is_recorded(world):
    api(world['admin']).post('/api/v1/ai/settings/accept-notice/')
    row = AuditLog.objects.get(resource_type='ai.settings.notice')
    assert row.new_data['actor'] == 'head@a.test' and chain.verify()['ok']


def test_only_administrators_can_use_the_switch(world):
    assert api(world['teacher']).put(URL, {'ai_enabled': False}, format='json').status_code == 403


def test_face_recognition_is_off_until_a_school_turns_it_on(world):
    c = api(world['admin'])
    ctx = _ctx(world['admin'], world['a'])
    assert feature_enabled('ai_face_attendance', ctx) is False
    assert c.post('/api/v1/ai/face-attendance/').status_code == 403 and c.post('/api/v1/ai/face-register/').status_code == 403
    assert c.get('/api/v1/ai/capabilities/').json()['face_recognition'] is False
    c.put(URL, {'features': {'ai_face_attendance': True}}, format='json')
    assert feature_enabled('ai_face_attendance', ctx) is True
    assert feature_enabled('ai_face_attendance', _ctx(world['admin_b'], world['b'])) is False          # another school is unaffected
    c.put(URL, {'ai_enabled': False}, format='json')
    assert feature_enabled('ai_face_attendance', ctx) is False                                           # the master switch still wins
