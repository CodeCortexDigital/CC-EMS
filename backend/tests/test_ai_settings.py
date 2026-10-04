"""The school's AI settings: feature switches, usage and the AI use notice."""
from unittest import mock

import pytest
from django.utils import timezone

from services.ai.context import AIContext
from services.ai.models import AIUsage
from services.ai.quota import feature_enabled
from services.ai.settings_api import FEATURES, NOTICE_VERSION, notice_accepted
from tests.safety_helpers import api, make_user, two_schools

URL = '/api/v1/ai/settings/'


@pytest.fixture
def world(db):
    a, b = two_schools()
    return {'a': a, 'b': b, 'admin': make_user(a, 'head@a.test', 'admin'), 'admin_b': make_user(b, 'head@b.test', 'admin'),
            'teacher': make_user(a, 'tim.teacher@a.test', 'teacher'), 'parent': make_user(a, 'mom@a.test', 'parent')}


def _ctx(user, school):
    return AIContext(user=user, role='admin', tenant=school)


@pytest.fixture(autouse=True)
def no_provider():
    with mock.patch('services.ai.settings_api.get_llm_client', return_value=None):
        yield


class TestAccess:
    def test_only_administrators(self, world):
        assert api(world['admin']).get(URL).status_code == 200
        for who in ('teacher', 'parent'):
            assert api(world[who]).get(URL).status_code == 403
            assert api(world[who]).put(URL, {'features': {'ai_translation': False}}, format='json').status_code == 403
            assert api(world[who]).post(URL + 'accept-notice/').status_code == 403
        assert api().get(URL).status_code == 401


class TestOverview:
    def test_lists_every_feature_switched_on_by_default(self, world):
        data = api(world['admin']).get(URL).json()
        assert [f['key'] for f in data['features']] == [k for k, _, _ in FEATURES]
        assert all(f['enabled'] for f in data['features']) and all(f['label'] and f['description'] for f in data['features'])
        assert data['provider']['configured'] is False and 'templates' in data['provider']['note']

    def test_says_which_provider_is_configured(self, world):
        with mock.patch('services.ai.settings_api.get_llm_client', return_value=mock.Mock(provider='anthropic')):
            data = api(world['admin']).get(URL).json()
        assert data['provider'] == {'configured': True, 'name': 'anthropic', 'note': ''}


class TestFeatureSwitches:
    def test_a_feature_can_be_turned_off_for_one_school_only(self, world):
        c = api(world['admin'])
        data = c.put(URL, {'features': {'ai_translation': False, 'ai_quiz': False}}, format='json').json()
        enabled = {f['key']: f['enabled'] for f in data['features']}
        assert enabled['ai_translation'] is False and enabled['ai_quiz'] is False and enabled['ai_lesson_plans'] is True
        # the check every AI endpoint makes
        assert feature_enabled('ai_translation', _ctx(world['admin'], world['a'])) is False
        assert feature_enabled('ai_translation', _ctx(world['admin_b'], world['b'])) is True
        other = {f['key']: f['enabled'] for f in api(world['admin_b']).get(URL).json()['features']}
        assert other['ai_translation'] is True

    def test_and_turned_back_on(self, world):
        c = api(world['admin'])
        c.put(URL, {'features': {'ai_translation': False}}, format='json')
        c.put(URL, {'features': {'ai_translation': True}}, format='json')
        assert feature_enabled('ai_translation', _ctx(world['admin'], world['a'])) is True

    def test_bad_requests_are_refused(self, world):
        c = api(world['admin'])
        assert c.put(URL, {'features': {'ai_world_domination': True}}, format='json').status_code == 400
        assert c.put(URL, {}, format='json').status_code == 400
        assert c.put(URL, {'features': 'ai_quiz'}, format='json').status_code == 400


class TestUsage:
    def test_shows_this_months_use_for_this_school_only(self, world):
        today = timezone.localdate()
        AIUsage.objects.create(tenant=world['a'], user=world['admin'], date=today, feature='ai_translation', requests=3, input_tokens=100, output_tokens=50)
        AIUsage.objects.create(tenant=world['a'], user=world['teacher'], date=today, feature='ai_lesson_plans', requests=5, input_tokens=400, output_tokens=200)
        AIUsage.objects.create(tenant=world['a'], user=world['admin'], date=today.replace(day=1) - timezone.timedelta(days=3), feature='ai_quiz', requests=99, input_tokens=1, output_tokens=1)
        AIUsage.objects.create(tenant=world['b'], user=world['admin_b'], date=today, feature='ai_translation', requests=7, input_tokens=1000, output_tokens=1000)
        usage = api(world['admin']).get(URL).json()['usage']
        assert usage['requests'] == 8 and usage['input_tokens'] == 500 and usage['output_tokens'] == 250
        assert [(r['feature'], r['requests'], r['tokens']) for r in usage['by_feature']] == [('ai_lesson_plans', 5, 600), ('ai_translation', 3, 150)]
        assert api(world['admin_b']).get(URL).json()['usage']['requests'] == 7

    def test_no_use_yet_is_zero_not_an_error(self, world):
        usage = api(world['admin']).get(URL).json()['usage']
        assert usage['requests'] == 0 and usage['by_feature'] == []


class TestNotice:
    def test_starts_unaccepted_then_records_who_accepted_and_when(self, world):
        c = api(world['admin'])
        assert c.get(URL).json()['notice']['accepted'] is False and notice_accepted(world['a']) is False
        notice = c.post(URL + 'accept-notice/').json()['notice']
        assert notice['accepted'] is True and notice['accepted_by'] == 'head@a.test' and notice['accepted_at']
        assert notice['version'] == NOTICE_VERSION and 'draft' in notice['text']
        world['a'].refresh_from_db()
        assert notice_accepted(world['a']) is True

    def test_another_school_is_not_affected(self, world):
        api(world['admin']).post(URL + 'accept-notice/')
        assert api(world['admin_b']).get(URL).json()['notice']['accepted'] is False
        world['b'].refresh_from_db()
        assert notice_accepted(world['b']) is False

    def test_an_older_notice_version_is_not_enough(self, world):
        world['a'].settings_json = {'ai_notice': {'version': 0, 'accepted_at': '2020-01-01T00:00:00Z', 'accepted_by': 'old@a.test'}}
        world['a'].save()
        assert notice_accepted(world['a']) is False
        assert notice_accepted(None) is False
