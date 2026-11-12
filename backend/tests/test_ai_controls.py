"""The school's AI controls: a use notice per person, the provider's no-training record, and masking of student names."""
import json
from unittest import mock

import pytest
from django.core.cache import cache

from services.ai.actions import build_record
from services.ai.agent import run_agent
from services.ai.context import AIContext
from services.ai.controls import AINotReady, NameMask, accept_user_notice, check_ready, controls, user_accepted
from services.ai.models import AIUserNotice
from services.ai.quota import AIQuotaExceeded, check_rate_limit
from services.core.audit.models import AuditLog
from tests.conftest import ClassFactory, SchoolFactory, SectionFactory, StudentFactory
from tests.safety_helpers import api, make_user, two_schools
from tests.test_ai_platform import FakeLLM, text_turn, tool_turn

S = '/api/v1/ai/settings/'
CHAT = '/api/v1/ai/chat/'
NOTICE = '/api/v1/ai/user-notice/'


@pytest.fixture
def world(db):
    cache.clear()
    a, b = two_schools()
    return {'a': a, 'b': b, 'admin': make_user(a, 'head@a.test', 'admin'), 'admin_b': make_user(b, 'head@b.test', 'admin'),
            'teacher': make_user(a, 'tim.teacher@a.test', 'teacher'), 'parent': make_user(a, 'mom@a.test', 'parent')}


@pytest.fixture
def provider():
    """A provider is set up (so AI use sends things out)."""
    llm = FakeLLM([])
    with mock.patch('services.ai.controls.get_llm_client', return_value=llm), mock.patch('services.ai.settings_api.get_llm_client', return_value=llm):
        yield llm


def _set(world, **on):
    r = api(world['admin']).put(S + 'controls/', on, format='json')
    assert r.status_code == 200, r.content
    return r.json()


def _ctx(world, who='parent', school='a'):
    world[school].refresh_from_db()                                                    # the setting was saved by another request
    return AIContext(user=world[who], role='admin' if who.startswith('admin') else who, tenant=world[school])


class TestSwitches:
    def test_all_three_are_off_until_the_school_switches_them_on(self, world):
        assert api(world['admin']).get(S).json()['controls'] == {'require_user_notice': False, 'require_training': False, 'mask_names': False,
                                                                 'accepted_by': 0, 'notice_version': 1}

    def test_an_administrator_changes_them_one_at_a_time_and_each_change_is_recorded(self, world):
        d = _set(world, mask_names=True)['controls']
        assert d['mask_names'] is True and d['require_user_notice'] is False
        d = _set(world, require_user_notice=True)['controls']
        assert d['mask_names'] is True and d['require_user_notice'] is True            # the first is kept
        rows = AuditLog.objects.filter(resource_type='ai.settings.controls', school=world['a'])
        assert rows.count() == 2

    def test_only_this_school_and_only_administrators(self, world):
        _set(world, require_training=True)
        assert api(world['admin_b']).get(S).json()['controls']['require_training'] is False
        for who in ('teacher', 'parent'):
            assert api(world[who]).put(S + 'controls/', {'mask_names': True}, format='json').status_code == 403
        assert api().put(S + 'controls/', {'mask_names': True}, format='json').status_code == 401

    def test_an_empty_change_is_refused(self, world):
        assert api(world['admin']).put(S + 'controls/', {}, format='json').status_code == 400
        assert api(world['admin']).put(S + 'controls/', {'unknown': True}, format='json').status_code == 400


class TestUserNotice:
    def test_nothing_is_asked_while_the_school_has_not_switched_it_on(self, world, provider):
        check_ready(_ctx(world))                                                       # no error

    def test_without_a_provider_nothing_leaves_so_nothing_is_asked(self, world):
        _set(world, require_user_notice=True, require_training=True)
        with mock.patch('services.ai.controls.get_llm_client', return_value=None):
            check_ready(_ctx(world))

    def test_each_person_has_to_accept_it_once(self, world, provider):
        _set(world, require_user_notice=True)
        with pytest.raises(AINotReady) as e:
            check_ready(_ctx(world))
        assert e.value.code == 'ai_notice_required'
        resp = api(world['parent']).post(NOTICE)
        assert resp.status_code == 200, resp.content
        r = resp.json()
        assert r['accepted'] is True and r['required'] is True and 'sent to an outside AI provider' in r['text']
        check_ready(_ctx(world))
        with pytest.raises(AINotReady):                                                # the other person still has to
            check_ready(_ctx(world, 'admin'))
        api(world['parent']).post(NOTICE)
        assert AIUserNotice.objects.filter(user=world['parent']).count() == 1          # accepting twice keeps one row

    def test_acceptance_is_for_one_school_and_recorded(self, world, provider):
        accept_user_notice(world['parent'], world['b'])
        assert user_accepted(world['parent'], world['b']) and not user_accepted(world['parent'], world['a'])
        api(world['parent']).post(NOTICE)
        assert AuditLog.objects.filter(resource_type='ai.user_notice', user=world['parent']).exists()

    def test_the_notice_can_be_read_before_accepting(self, world):
        d = api(world['parent']).get(NOTICE).json()
        assert d['accepted'] is False and d['required'] is False and d['version'] == 1
        assert api().get(NOTICE).status_code in (401, 403)

    def test_the_assistant_refuses_with_a_code_until_it_is_accepted(self, world, provider):
        _set(world, require_user_notice=True)
        r = api(world['parent']).post(CHAT, {'message': 'hello'}, format='json')
        assert r.status_code == 403 and r.json().get('code') == 'ai_notice_required', (r.status_code, r.content)
        assert provider.calls == []                                                    # nothing was sent
        api(world['parent']).post(NOTICE)
        provider.turns = [text_turn('Hello.')]
        with mock.patch('services.ai.views.get_llm_client', return_value=provider):
            r = api(world['parent']).post(CHAT, {'message': 'hello'}, format='json')
        assert r.status_code == 200 and r.json()['reply'] == 'Hello.'

    def test_other_ai_features_are_stopped_in_the_same_place(self, world, provider):
        _set(world, require_user_notice=True)
        with pytest.raises(AIQuotaExceeded, match='AI use notice'):
            check_rate_limit(_ctx(world), 'ai_translation')
        accept_user_notice(world['parent'], world['a'])
        check_rate_limit(_ctx(world), 'ai_translation')


class TestTrainingRecord:
    RECORD = {'provider': 'fake', 'confirmed_by': 'Sales', 'confirmed_on': '2026-11-01', 'reference': 'mail 1'}

    def test_ai_is_paused_while_there_is_no_record(self, world, provider):
        _set(world, require_training=True)
        with pytest.raises(AINotReady) as e:
            check_ready(_ctx(world))
        assert e.value.code == 'ai_training_required'
        r = api(world['parent']).post(CHAT, {'message': 'hello'}, format='json')
        assert r.status_code == 403 and r.json()['code'] == 'ai_training_required' and provider.calls == []

    def test_and_runs_once_it_is_recorded(self, world, provider):
        _set(world, require_training=True)
        api(world['admin']).post(S + 'training-confirmation/', self.RECORD, format='json')
        check_ready(_ctx(world))

    def test_a_record_for_another_provider_does_not_count(self, world, provider):
        _set(world, require_training=True)
        api(world['admin']).post(S + 'training-confirmation/', {**self.RECORD, 'provider': 'openai'}, format='json')
        with pytest.raises(AINotReady):
            check_ready(_ctx(world))

    def test_removing_the_record_pauses_it_again(self, world, provider):
        _set(world, require_training=True)
        api(world['admin']).post(S + 'training-confirmation/', self.RECORD, format='json')
        api(world['admin']).delete(S + 'training-confirmation/')
        with pytest.raises(AINotReady):
            check_ready(_ctx(world))

    def test_another_school_is_not_paused(self, world, provider):
        _set(world, require_training=True)
        check_ready(_ctx(world, 'admin_b', 'b'))


class TestNameMask:
    def test_names_are_replaced_with_or_without_the_space_and_the_same_name_gets_the_same_token(self):
        m = NameMask(['山田 太郎', 'Amy Brown'])
        out = m.mask('山田太郎さんと 山田 太郎 と amy  brown')
        assert out == '[Student 1]さんと [Student 1] と [Student 2]'
        assert m.restore(out) == '山田 太郎さんと 山田 太郎 と Amy Brown'
        assert m.count == 2

    def test_nested_data_is_masked_and_restored(self):
        m = NameMask(['Amy Brown'])
        data = {'students': [{'name': 'Amy Brown', 'n': 3}], 'note': 'Amy Brown is late'}
        masked = m.mask_data(data)
        assert 'Amy' not in json.dumps(masked) and masked['students'][0]['n'] == 3
        assert m.restore_data(masked) == data

    def test_a_name_in_the_reply_is_noticed(self):
        m = NameMask(['Amy Brown'])
        assert m.leaked('Amy Brown is fine') and not m.leaked('[Student 1] is fine')

    def test_streamed_tokens_split_across_pieces_are_put_back(self):
        m = NameMask(['Amy Brown'])
        m.mask('Amy Brown')
        s = m.streamer()
        out = ''.join(s.feed(p) for p in ['Hello [Stu', 'dent ', '1] is ', 'here [', 'x'])
        out += s.flush()
        assert out == 'Hello Amy Brown is here [x'

    def test_one_letter_names_and_blanks_are_ignored(self):
        m = NameMask(['', 'A', None])
        assert m.mask('A is here') == 'A is here'


@pytest.fixture
def school():
    return SchoolFactory()


def _kid(school, name):
    cls = ClassFactory(school=school)
    return StudentFactory(tenant=school, current_class=cls, current_section=SectionFactory(class_obj=cls), full_name=name)


def _admin_ctx(school):
    from tests.conftest import UserFactory

    return AIContext(user=UserFactory(is_superuser=True), role='admin', tenant=school)


def _masking(school, on):
    school.settings_json = {'ai_controls': {'mask_names': on}}
    school.save(update_fields=['settings_json'])


@pytest.mark.django_db
class TestAgentMasking:
    def test_the_provider_never_sees_the_name_and_the_person_gets_it_back(self, school):
        _kid(school, 'Loop Kid')
        _masking(school, True)
        ctx = _admin_ctx(school)
        llm = FakeLLM([tool_turn('search_students', {'query': '[Student 1]'}), text_turn('[Student 1] is in class 3.')])
        events = list(run_agent(ctx, [{'role': 'user', 'content': 'Find Loop Kid please'}], llm))
        assert events[-1]['result'].reply == 'Loop Kid is in class 3.'
        sent = json.dumps([llm.calls[0]['messages'], llm.calls[1]['messages']], ensure_ascii=False)
        assert 'Loop' not in sent and '[Student 1]' in sent
        assert 'never write or guess a real name' in llm.calls[0]['system']
        payload = json.loads(llm.calls[1]['messages'][-1]['content'])
        assert payload['students'][0]['name'] == '[Student 1]'                          # the search worked on the real name
        assert ctx.extra['masking'] == {'on': True, 'names_replaced': 1, 'name_in_answer': False}

    def test_a_real_name_in_the_models_own_reply_is_flagged_in_the_record(self, school):
        _kid(school, 'Loop Kid')
        _masking(school, True)
        ctx = _admin_ctx(school)
        list(run_agent(ctx, [{'role': 'user', 'content': 'Loop Kid?'}], FakeLLM([text_turn('Loop Kid is great.')])))
        rec = build_record(ctx)
        assert rec['controls']['name_masking']['name_in_answer'] is True and rec['controls']['school_controls']['mask_names'] is True
        assert 'Loop' not in rec['asked']                                               # the record shows what was sent

    def test_streaming_puts_names_back(self, school):
        _kid(school, 'Loop Kid')
        _masking(school, True)
        events = list(run_agent(_admin_ctx(school), [{'role': 'user', 'content': 'Loop Kid?'}], FakeLLM([text_turn('[Student 1] is fine')]), stream=True))
        assert ''.join(e['text'] for e in events if e['type'] == 'token').strip() == 'Loop Kid is fine'

    def test_off_means_nothing_changes(self, school):
        _kid(school, 'Loop Kid')
        ctx = _admin_ctx(school)
        llm = FakeLLM([text_turn('Loop Kid.')])
        events = list(run_agent(ctx, [{'role': 'user', 'content': 'Loop Kid?'}], llm))
        assert 'Loop Kid' in json.dumps(llm.calls[0]['messages']) and events[-1]['result'].reply == 'Loop Kid.'
        assert ctx.extra['masking'] == {'on': False}

    def test_only_this_schools_students_are_known(self, school):
        _kid(SchoolFactory(), 'Other Kid')
        _masking(school, True)
        llm = FakeLLM([text_turn('ok')])
        list(run_agent(_admin_ctx(school), [{'role': 'user', 'content': 'Other Kid?'}], llm))
        assert 'Other Kid' in json.dumps(llm.calls[0]['messages'])
