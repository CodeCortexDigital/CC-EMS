"""Families and staff: urgency labels on incoming messages, translations that are kept, and a draft reply for staff."""
from unittest import mock

import pytest

from services.ai.models import AIUsage
from services.education.communication.models import TranslationCache
from services.education.communication.urgency import classify, worst
from tests.test_messaging import _client, school  # noqa: F401  (school is a fixture)

BASE = '/api/v1/auth/communication'


def _start(d, body, subject='Question'):
    res = _client(d['p4']).post(f'{BASE}/conversations/', {
        'participants': [str(d['green'].id)], 'subject': subject, 'body': body, 'student': str(d['kid4'].id)}, format='json')
    assert res.status_code == 201, res.content
    return res.json()['id']


class TestClassifier:
    def test_urgent_words_win(self):
        assert classify('Pickup', 'My son is injured, please call me ASAP') == 'urgent'
        assert classify('Where is she?', "She hasn't arrived home") == 'urgent'

    def test_frustration_is_picked_up_without_being_urgent(self):
        assert classify('Homework', 'This is the third time I am asking. Very disappointed.') == 'frustrated'
        assert classify('Hi', 'WHY NOBODY TELLS US ANYTHING') == 'frustrated'

    def test_ordinary_messages_stay_normal(self):
        assert classify('Science project', 'Can Kid bring a poster on Friday?') == 'normal'
        assert classify('Homework', 'He is missing one worksheet') == 'normal'

    def test_worst_of_a_set(self):
        assert worst(['normal', 'frustrated', 'normal']) == 'frustrated'
        assert worst(['frustrated', 'urgent']) == 'urgent'
        assert worst([]) == 'normal'


@pytest.mark.django_db
class TestUrgencyInTheInbox:
    def test_staff_see_the_label_and_the_family_never_does(self, school):
        d = school
        conv = _start(d, 'My daughter is bleeding after PE, call me immediately')
        staff = _client(d['green'])
        row = next(c for c in staff.get(f'{BASE}/conversations/').json() if c['id'] == conv)
        assert row['urgency'] == 'urgent'
        thread = staff.get(f'{BASE}/conversations/{conv}/').json()
        assert thread['messages'][0]['urgency'] == 'urgent'
        # The sender's own view never shows how their message was read.
        mine = _client(d['p4'])
        assert next(c for c in mine.get(f'{BASE}/conversations/').json() if c['id'] == conv)['urgency'] == 'normal'
        assert mine.get(f'{BASE}/conversations/{conv}/').json()['messages'][0]['urgency'] == 'normal'

    def test_the_label_clears_once_staff_have_read_it(self, school):
        d = school
        conv = _start(d, 'This is unacceptable, nobody replied')
        staff = _client(d['green'])
        assert next(c for c in staff.get(f'{BASE}/conversations/').json() if c['id'] == conv)['urgency'] == 'frustrated'
        staff.get(f'{BASE}/conversations/{conv}/')                              # opening it marks it read
        assert next(c for c in staff.get(f'{BASE}/conversations/').json() if c['id'] == conv)['urgency'] == 'normal'

    def test_a_reply_is_labelled_too(self, school):
        d = school
        conv = _start(d, 'Hello')
        _client(d['p4']).post(f'{BASE}/conversations/{conv}/messages/', {'body': 'Please call, it is an emergency'}, format='json')
        row = next(c for c in _client(d['green']).get(f'{BASE}/conversations/').json() if c['id'] == conv)
        assert row['urgency'] == 'urgent'


@pytest.mark.django_db
class TestTranslationIsKept:
    def _fake(self, text='Visite au musée vendredi.'):
        from tests.test_ai_platform import FakeLLM

        llm = FakeLLM([])
        llm.structured_results = [{'translated_text': text}]
        return llm

    def test_second_request_reuses_the_first_and_costs_nothing(self, school):
        d = school
        conv = _start(d, 'The museum visit is on Friday.')
        msg = _client(d['green']).get(f'{BASE}/conversations/{conv}/').json()['messages'][0]['id']
        url = f'{BASE}/conversations/{conv}/messages/{msg}/translate/'
        llm = self._fake()
        staff = _client(d['green'])
        with mock.patch('services.ai.llm.get_llm_client', return_value=llm):
            first = staff.post(url, {'target_language': 'fr'}, format='json')
            second = staff.post(url, {'target_language': 'fr'}, format='json')
        assert first.status_code == second.status_code == 200
        assert first.json()['cached'] is False and second.json()['cached'] is True
        assert second.json()['translated_text'] == 'Visite au musée vendredi.'
        assert len(llm.calls) == 1
        assert AIUsage.objects.filter(feature='ai_translation').count() == 1

    def test_another_language_is_a_new_translation(self, school):
        d = school
        conv = _start(d, 'The museum visit is on Friday.')
        msg = _client(d['green']).get(f'{BASE}/conversations/{conv}/').json()['messages'][0]['id']
        url = f'{BASE}/conversations/{conv}/messages/{msg}/translate/'
        llm = self._fake()
        llm.structured_results = [{'translated_text': 'fr text'}, {'translated_text': 'es text'}]
        with mock.patch('services.ai.llm.get_llm_client', return_value=llm):
            _client(d['green']).post(url, {'target_language': 'fr'}, format='json')
            es = _client(d['green']).post(url, {'target_language': 'es'}, format='json').json()
        assert es['translated_text'] == 'es text' and es['cached'] is False
        assert TranslationCache.objects.count() == 2

    def test_a_stand_in_translation_is_never_kept(self, school):
        d = school
        conv = _start(d, 'Hello there')
        msg = _client(d['green']).get(f'{BASE}/conversations/{conv}/').json()['messages'][0]['id']
        res = _client(d['green']).post(f'{BASE}/conversations/{conv}/messages/{msg}/translate/', {'target_language': 'fr'}, format='json')
        assert res.json()['source'] == 'template'
        assert TranslationCache.objects.count() == 0

    def test_one_school_never_reads_anothers_cached_translation(self, school):
        from services.core.tenants.context import use_tenant
        from tests.conftest import SchoolFactory

        d = school
        conv = _start(d, 'The museum visit is on Friday.')
        msg = _client(d['green']).get(f'{BASE}/conversations/{conv}/').json()['messages'][0]['id']
        with mock.patch('services.ai.llm.get_llm_client', return_value=self._fake()):
            _client(d['green']).post(f'{BASE}/conversations/{conv}/messages/{msg}/translate/', {'target_language': 'fr'}, format='json')
        other = SchoolFactory(name='Elsewhere')
        with use_tenant(other):
            assert TranslationCache.objects.count() == 0


@pytest.mark.django_db
class TestSuggestedReply:
    def _summary(self, with_reply=True):
        from tests.test_ai_platform import FakeLLM

        llm = FakeLLM([])
        row = {'summary': 'Parent asks about a poster.', 'key_points': []}
        if with_reply:
            row['suggested_reply'] = 'Thanks for asking, any size is fine.'
        llm.structured_results = [row]
        return llm

    def test_staff_get_a_draft_when_the_family_spoke_last(self, school):
        d = school
        conv = _start(d, 'Can Kid bring a poster on Friday?')
        llm = self._summary()
        with mock.patch('services.ai.llm.get_llm_client', return_value=llm):
            res = _client(d['green']).post(f'{BASE}/conversations/{conv}/summarize/', {}, format='json')
        assert res.status_code == 200, res.content
        assert res.json()['suggested_reply'] == 'Thanks for asking, any size is fine.'
        assert 'suggested_reply' in llm.calls[0]['prompt']

    def test_no_draft_for_the_family_or_when_staff_spoke_last(self, school):
        d = school
        conv = _start(d, 'Can Kid bring a poster on Friday?')
        llm = self._summary(with_reply=False)
        with mock.patch('services.ai.llm.get_llm_client', return_value=llm):
            res = _client(d['p4']).post(f'{BASE}/conversations/{conv}/summarize/', {}, format='json')
        assert 'suggested_reply' not in res.json()
        _client(d['green']).post(f'{BASE}/conversations/{conv}/messages/', {'body': 'Yes, any size.'}, format='json')
        llm = self._summary(with_reply=False)
        with mock.patch('services.ai.llm.get_llm_client', return_value=llm):
            res = _client(d['green']).post(f'{BASE}/conversations/{conv}/summarize/', {}, format='json')
        assert 'suggested_reply' not in res.json()
        assert 'suggested_reply' not in llm.calls[0]['prompt']

    def test_the_draft_is_not_sent_for_them(self, school):
        d = school
        conv = _start(d, 'Can Kid bring a poster on Friday?')
        with mock.patch('services.ai.llm.get_llm_client', return_value=self._summary()):
            _client(d['green']).post(f'{BASE}/conversations/{conv}/summarize/', {}, format='json')
        thread = _client(d['green']).get(f'{BASE}/conversations/{conv}/').json()
        assert len(thread['messages']) == 1
