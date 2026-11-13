"""The notice of the purposes of use: drafted from the data handling register, published to families, with a record of who has read it."""
import pytest
from django.utils import timezone

from services.core.privacy.models import ConsentType, DataHandlingEntry
from tests.safety_helpers import api, link_parent
from tests.test_records import world  # noqa: F401  (a school with an administrator, a teacher and a parent, and a second school)

P = '/api/v1/privacy'


def _register(world, lang='ja'):  # noqa: F811
    api(world['admin']).post(f'{P}/register/', {'action': 'load_defaults', 'lang': lang}, format='json')


def _publish(world, lang='ja'):  # noqa: F811
    d = api(world['admin']).get(f'{P}/notice-draft/', {'lang': lang}).json()
    r = api(world['admin']).post(f'{P}/documents/', {'title': d['title'], 'body': d['body']}, format='json')
    assert r.status_code == 201, r.content
    return r.json()['document']


class TestDraft:
    def test_an_empty_register_cannot_make_a_notice(self, world):  # noqa: F811
        r = api(world['admin']).get(f'{P}/notice-draft/')
        assert r.status_code == 400 and 'register is empty' in r.json()['error']

    def test_the_japanese_draft_lists_each_purpose_and_marks_sensitive_information(self, world):  # noqa: F811
        _register(world)
        d = api(world['admin']).get(f'{P}/notice-draft/', {'lang': 'ja'}).json()
        assert d['title'].endswith('個人情報の利用目的のお知らせ') and d['entries'] == 13 and d['sensitive'] == 4
        body = d['body']
        assert world['a'].name in body and '■ 指導要録' in body and '利用目的:' in body and '保存期間:' in body and '提供先:' in body
        assert body.count('【要配慮個人情報】') == 4 and '要配慮個人情報について' in body
        assert d['consent'] == {'needed': True, 'exists': False, 'label': ''}

    def test_the_english_draft(self, world):  # noqa: F811
        _register(world, 'en')
        d = api(world['admin']).get(f'{P}/notice-draft/', {'lang': 'en'}).json()
        assert 'purposes of use of personal information' in d['title'] and body_has(d['body'], ['* Attendance', 'Purpose of use:', 'About sensitive information'])
        assert d['body'].count('[SENSITIVE INFORMATION]') == 4

    def test_a_line_switched_off_is_left_out_and_without_sensitive_lines_no_consent_is_needed(self, world):  # noqa: F811
        _register(world)
        a = api(world['admin'])
        for e in a.get(f'{P}/register/').json()['entries']:
            if e['sensitive']:
                a.post(f'{P}/register/', {**e, 'is_active': False}, format='json')
        d = a.get(f'{P}/notice-draft/').json()
        assert d['entries'] == 9 and d['sensitive'] == 0 and d['consent']['needed'] is False
        assert '要配慮個人情報について' not in d['body'] and '健康情報' not in d['body']

    def test_drafting_changes_nothing(self, world):  # noqa: F811
        _register(world)
        api(world['admin']).get(f'{P}/notice-draft/')
        assert ConsentType.objects.filter(key='sensitive-info').count() == 0
        assert api(world['admin']).get(f'{P}/documents/').json()['history'] == []


def _mom(data):
    return next(r for r in data['rows'] if r['email'] == 'mom@a.test')


def body_has(body, parts):
    return all(p in body for p in parts)


class TestSensitiveConsent:
    def test_the_consent_question_is_added_once(self, world):  # noqa: F811
        _register(world)
        a = api(world['admin'])
        r = a.post(f'{P}/notice-draft/', {'ensure_consent': True, 'lang': 'ja'}, format='json').json()
        assert r['created'] is True and '要配慮個人情報' in r['consent']['label']
        assert a.post(f'{P}/notice-draft/', {'ensure_consent': True}, format='json').json()['created'] is False
        assert ConsentType.objects.filter(school=world['a'], key='sensitive-info').count() == 1
        assert a.get(f'{P}/notice-draft/').json()['consent']['exists'] is True
        assert any(t['key'] == 'sensitive-info' for t in a.get(f'{P}/consent-types/').json()['types'])

    def test_it_is_for_each_child_and_other_schools_do_not_get_it(self, world):  # noqa: F811
        _register(world)
        api(world['admin']).post(f'{P}/notice-draft/', {'ensure_consent': True}, format='json')
        assert ConsentType.objects.get(key='sensitive-info').subject == 'student'
        assert not ConsentType.objects.filter(school=world['b'], key='sensitive-info').exists()

    def test_a_post_without_the_flag_does_nothing(self, world):  # noqa: F811
        assert api(world['admin']).post(f'{P}/notice-draft/', {}, format='json').status_code == 400


class TestNoticeIsCurrent:
    def test_a_register_changed_after_publishing_is_flagged_until_the_notice_is_published_again(self, world):  # noqa: F811
        _register(world)
        a = api(world['admin'])
        assert a.get(f'{P}/documents/').json()['register_newer'] is False                 # nothing published yet
        _publish(world)
        assert a.get(f'{P}/documents/').json()['register_newer'] is False
        line = a.get(f'{P}/register/').json()['entries'][0]
        a.post(f'{P}/register/', {**line, 'purpose': '新しい目的'}, format='json')
        assert a.get(f'{P}/documents/').json()['register_newer'] is True
        _publish(world)
        assert a.get(f'{P}/documents/').json()['register_newer'] is False


class TestDelivery:
    def test_nothing_is_published_yet(self, world):  # noqa: F811
        assert api(world['admin']).get(f'{P}/notice-delivery/').json() == {'document': None, 'rows': [], 'summary': {'people': 0, 'read': 0, 'not_read': 0}}

    def test_it_lists_families_who_have_not_read_it_with_their_children_and_then_when_they_did(self, world):  # noqa: F811
        link_parent(world['mom'], world['kid'])
        _register(world)
        _publish(world)
        a = api(world['admin'])
        d = a.get(f'{P}/notice-delivery/').json()
        assert d['document']['version'] == 1 and d['summary']['read'] == 0 and d['summary']['not_read'] == d['summary']['people'] >= 1
        row = _mom(d)
        assert row['role'] == 'Parent / guardian' and row['read'] is False and world['kid'].full_name in row['children']
        api(world['mom']).post(f'{P}/accept/', {'documents': [i['id'] for i in api(world['mom']).get(f'{P}/pending/').json()['documents']]}, format='json')
        d2 = a.get(f'{P}/notice-delivery/').json()
        assert d2['summary']['read'] == 1 and d2['summary']['not_read'] == d['summary']['not_read'] - 1
        assert _mom(d2)['read'] is True and _mom(d2)['read_at']
        assert _mom(d2) not in d2['rows'][:0] and d2['rows'][-1]['read'] is True           # those who have not read it come first

    def test_a_new_version_has_to_be_read_again(self, world):  # noqa: F811
        link_parent(world['mom'], world['kid'])
        _register(world)
        _publish(world)
        m = api(world['mom'])
        m.post(f'{P}/accept/', {'documents': [i['id'] for i in m.get(f'{P}/pending/').json()['documents']]}, format='json')
        assert _mom(api(world['admin']).get(f'{P}/notice-delivery/').json())['read'] is True
        _publish(world)
        d = api(world['admin']).get(f'{P}/notice-delivery/').json()
        assert d['document']['version'] == 2 and d['summary']['read'] == 0 and _mom(d)['read'] is False
        assert any(i['title'] for i in m.get(f'{P}/pending/').json()['documents'])           # the family is asked again at next sign-in

    def test_staff_can_be_listed_and_the_list_downloaded(self, world):  # noqa: F811
        link_parent(world['mom'], world['kid'])
        _register(world)
        _publish(world)
        a = api(world['admin'])
        staff = a.get(f'{P}/notice-delivery/', {'who': 'staff'}).json()
        assert 'sato.teacher@a.test' in [r['email'] for r in staff['rows']] and 'mom@a.test' not in [r['email'] for r in staff['rows']]
        r = a.get(f'{P}/notice-delivery/', {'who': 'all', 'export': 'csv'})
        text = r.content.decode('utf-8-sig')
        assert r['Content-Type'].startswith('text/csv') and text.splitlines()[0] == 'Name,Email,Role,Children,Read,Read at' and 'mom@a.test' in text

    def test_only_the_administrator_sees_any_of_it_and_only_for_their_school(self, world):  # noqa: F811
        link_parent(world['mom'], world['kid'])
        _register(world)
        _publish(world)
        for who in ('teacher', 'mom'):
            for path in (f'{P}/notice-delivery/', f'{P}/notice-draft/'):
                assert api(world[who]).get(path).status_code == 403
            assert api(world[who]).post(f'{P}/notice-draft/', {'ensure_consent': True}, format='json').status_code == 403
        assert api().get(f'{P}/notice-delivery/').status_code == 401
        assert api(world['admin_b']).get(f'{P}/notice-delivery/').json()['document'] is None
        assert api(world['admin_b']).get(f'{P}/notice-draft/').status_code == 400          # its own register is empty
