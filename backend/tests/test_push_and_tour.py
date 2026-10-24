"""Installed-app push notifications (subscribe, preferences, delivery) and the guided-tour progress record."""
import io
import json
from unittest import mock

import pytest
from django.core.management import call_command

from services.core.user_notifications import push
from services.core.user_notifications.models import Notification, PushSubscription
from tests.safety_helpers import api, link_parent, make_student, make_user, two_schools

N = '/api/v1/auth/notifications'
SUB = {'endpoint': 'https://push.example.test/send/abc', 'keys': {'p256dh': 'BPUBLICKEY', 'auth': 'AUTHSECRET'}, 'platform': 'android'}


class Inline:
    """Stands in for the background thread pool so a test can see the result straight away."""

    def submit(self, fn, *args):
        fn(*args)


@pytest.fixture
def people(db):
    a, b = two_schools()
    return {'a': a, 'admin': make_user(a, 'head@a.test', 'admin'), 'parent': make_user(a, 'mom@a.test', 'parent'),
            'other': make_user(b, 'other@b.test', 'admin')}


@pytest.fixture
def vapid(monkeypatch):
    monkeypatch.setenv('VAPID_PUBLIC_KEY', 'PUBLIC-APP-SERVER-KEY')
    monkeypatch.setenv('VAPID_PRIVATE_KEY', 'PRIVATE-KEY')
    monkeypatch.setenv('VAPID_CONTACT', 'mailto:office@school.test')
    monkeypatch.setattr(push, '_executor', Inline())


class TestSubscribing:
    def test_without_keys_the_app_says_push_is_not_available(self, people, monkeypatch):
        for name in ('VAPID_PUBLIC_KEY', 'VAPID_PRIVATE_KEY'):
            monkeypatch.delenv(name, raising=False)
        c = api(people['parent'])
        assert c.get(f'{N}/push/vapid-key/').json() == {'enabled': False, 'public_key': ''}
        assert c.post(f'{N}/push/subscribe/', SUB, format='json').status_code == 503
        assert not PushSubscription.objects.exists()

    def test_the_public_key_is_shared_but_never_the_private_one(self, people, vapid):
        body = api(people['parent']).get(f'{N}/push/vapid-key/')
        assert body.json() == {'enabled': True, 'public_key': 'PUBLIC-APP-SERVER-KEY'}
        assert 'PRIVATE' not in body.content.decode()
        assert api().get(f'{N}/push/vapid-key/').status_code == 401

    def test_a_parent_can_register_a_device_and_registering_again_updates_it(self, people, vapid):
        c = api(people['parent'])
        first = c.post(f'{N}/push/subscribe/', SUB, format='json')
        assert first.status_code == 201 and first.json()['created'] is True
        again = c.post(f'{N}/push/subscribe/', {**SUB, 'keys': {'p256dh': 'NEWKEY', 'auth': 'NEWAUTH'}}, format='json')
        assert again.status_code == 200 and again.json()['created'] is False
        assert PushSubscription.objects.count() == 1 and PushSubscription.objects.get().p256dh == 'NEWKEY'

    @pytest.mark.parametrize('bad', [
        {'endpoint': 'http://insecure.test/x', 'keys': {'p256dh': 'a', 'auth': 'b'}},
        {'endpoint': 'https://push.test/x', 'keys': {'p256dh': 'a'}},
        {'endpoint': 'https://push.test/x'},
        {'keys': {'p256dh': 'a', 'auth': 'b'}},
        {'endpoint': 'https://push.test/' + 'x' * 2100, 'keys': {'p256dh': 'a', 'auth': 'b'}},
    ])
    def test_invalid_subscriptions_are_refused(self, people, vapid, bad):
        assert api(people['parent']).post(f'{N}/push/subscribe/', bad, format='json').status_code == 400
        assert not PushSubscription.objects.exists()

    def test_a_person_keeps_at_most_ten_devices(self, people, vapid):
        c = api(people['parent'])
        for i in range(12):
            c.post(f'{N}/push/subscribe/', {**SUB, 'endpoint': f'https://push.example.test/{i}'}, format='json')
        assert PushSubscription.objects.filter(user=people['parent']).count() == 10

    def test_devices_belong_to_their_owner(self, people, vapid):
        mine = api(people['parent'])
        mine.post(f'{N}/push/subscribe/', SUB, format='json')
        device = mine.get(f'{N}/devices/').json()['devices'][0]
        assert api(people['admin']).get(f'{N}/devices/').json()['devices'] == []
        assert api(people['admin']).delete(f'{N}/devices/{device["id"]}/').status_code == 404
        assert PushSubscription.objects.count() == 1
        assert mine.delete(f'{N}/devices/{device["id"]}/').status_code == 200
        mine.post(f'{N}/push/subscribe/', SUB, format='json')
        assert mine.post(f'{N}/push/unsubscribe/', {'endpoint': SUB['endpoint']}, format='json').json() == {'removed': True}
        assert mine.post(f'{N}/push/unsubscribe/', {}, format='json').status_code == 400


class TestPreferences:
    def test_everything_is_on_until_switched_off(self, people):
        c = api(people['parent'])
        types = c.get(f'{N}/push/preferences/').json()['types']
        assert {t['key'] for t in types} == {'attendance', 'finance', 'exam', 'admission', 'announcement', 'library', 'system'} and all(t['enabled'] for t in types)
        after = c.put(f'{N}/push/preferences/', {'muted_types': ['finance', 'exam']}, format='json').json()['types']
        assert {t['key'] for t in after if not t['enabled']} == {'finance', 'exam'}
        assert c.put(f'{N}/push/preferences/', {'muted_types': ['nonsense']}, format='json').status_code == 400
        assert c.put(f'{N}/push/preferences/', {'muted_types': 'finance'}, format='json').status_code == 400
        assert all(t['enabled'] for t in api(people['admin']).get(f'{N}/push/preferences/').json()['types'])   # someone else's are untouched


class TestDelivery:
    def _subscribe(self, user):
        PushSubscription.objects.create(user=user, endpoint=SUB['endpoint'], p256dh='K', auth='A')

    def _notify(self, user, capture, kind='announcement', silent=False):
        n = Notification(recipient=user, title='School closed', message='Snow day tomorrow.', notification_type=kind)
        n._silent = silent
        with capture(execute=True):
            n.save()
        return n

    def test_a_new_notification_is_pushed_to_the_recipients_devices(self, people, vapid, django_capture_on_commit_callbacks):
        self._subscribe(people['parent'])
        with mock.patch('pywebpush.webpush') as sender:
            n = self._notify(people['parent'], django_capture_on_commit_callbacks)
        assert sender.call_count == 1
        kwargs = sender.call_args.kwargs
        assert kwargs['subscription_info'] == {'endpoint': SUB['endpoint'], 'keys': {'p256dh': 'K', 'auth': 'A'}}
        assert kwargs['vapid_private_key'] == 'PRIVATE-KEY' and kwargs['vapid_claims'] == {'sub': 'mailto:office@school.test'}
        assert json.loads(kwargs['data']) == {'title': 'School closed', 'body': 'Snow day tomorrow.', 'url': '/', 'tag': str(n.pk), 'type': 'announcement'}

    def test_nothing_is_pushed_when_it_should_not_be(self, people, vapid, django_capture_on_commit_callbacks, monkeypatch):
        self._subscribe(people['parent'])
        api(people['parent']).put(f'{N}/push/preferences/', {'muted_types': ['finance']}, format='json')
        with mock.patch('pywebpush.webpush') as sender:
            self._notify(people['parent'], django_capture_on_commit_callbacks, kind='finance')                    # switched off
            self._notify(people['parent'], django_capture_on_commit_callbacks, silent=True)                       # history load
            self._notify(people['admin'], django_capture_on_commit_callbacks)                                      # no device
            monkeypatch.delenv('VAPID_PRIVATE_KEY')
            self._notify(people['parent'], django_capture_on_commit_callbacks)                                     # push not set up
        assert sender.call_count == 0

    def test_a_device_that_has_gone_is_forgotten_and_one_failure_does_not_stop_the_rest(self, people, vapid, django_capture_on_commit_callbacks):
        from pywebpush import WebPushException
        PushSubscription.objects.create(user=people['parent'], endpoint='https://push.example.test/gone', p256dh='K', auth='A')
        PushSubscription.objects.create(user=people['parent'], endpoint='https://push.example.test/ok', p256dh='K', auth='A')
        PushSubscription.objects.create(user=people['parent'], endpoint='https://push.example.test/flaky', p256dh='K', auth='A')
        gone = WebPushException('gone', response=mock.Mock(status_code=410))

        def fake(subscription_info, **kw):
            if subscription_info['endpoint'].endswith('/gone'):
                raise gone
            if subscription_info['endpoint'].endswith('/flaky'):
                raise RuntimeError('network down')

        with mock.patch('pywebpush.webpush', side_effect=fake):
            self._notify(people['parent'], django_capture_on_commit_callbacks)
        assert sorted(PushSubscription.objects.values_list('endpoint', flat=True)) == ['https://push.example.test/flaky', 'https://push.example.test/ok']

    def test_send_a_test_push_to_my_own_devices(self, people, vapid):
        self._subscribe(people['parent'])
        with mock.patch('pywebpush.webpush') as sender:
            assert api(people['parent']).post(f'{N}/push/test/').json() == {'sent': 1}
            assert api(people['admin']).post(f'{N}/push/test/').json() == {'sent': 0}
        assert sender.call_count == 1


class TestKeyGenerator:
    def test_the_generated_keys_really_sign_a_push_request(self, monkeypatch):
        from py_vapid import Vapid
        out = io.StringIO()
        call_command('generate_vapid_keys', '--contact', 'mailto:office@school.test', stdout=out)
        env = dict(line.split('=', 1) for line in out.getvalue().splitlines() if line.startswith('VAPID_'))
        assert env['VAPID_CONTACT'] == 'mailto:office@school.test'
        signed = Vapid.from_string(env['VAPID_PRIVATE_KEY']).sign({'sub': env['VAPID_CONTACT'], 'aud': 'https://push.example.test', 'exp': 4102444800})
        assert signed['Authorization'].startswith('vapid t=')
        assert f"k={env['VAPID_PUBLIC_KEY']}" in signed['Authorization']       # the public key goes with the signature


TOUR = '/api/v1/tour/progress/'


class TestTourProgress:
    def test_remembers_finished_and_skipped_per_person_and_tour(self, people):
        c = api(people['admin'])
        assert c.get(TOUR).json() == {'tours': {}}
        assert c.post(TOUR, {'tour': 'admin', 'version': 1, 'status': 'completed'}, format='json').json()['tours'] == {'admin': {'version': 1, 'status': 'completed'}}
        both = c.post(TOUR, {'tour': 'hr', 'version': 2, 'status': 'skipped'}, format='json').json()['tours']
        assert both == {'admin': {'version': 1, 'status': 'completed'}, 'hr': {'version': 2, 'status': 'skipped'}}
        again = c.post(TOUR, {'tour': 'admin', 'version': 2, 'status': 'skipped'}, format='json').json()['tours']
        assert again['admin'] == {'version': 2, 'status': 'skipped'}
        assert api(people['other']).get(TOUR).json() == {'tours': {}}            # someone else's progress is separate

    def test_replaying_forgets_only_the_chosen_tour(self, people):
        c = api(people['admin'])
        c.post(TOUR, {'tour': 'admin', 'version': 1, 'status': 'completed'}, format='json')
        c.post(TOUR, {'tour': 'hr', 'version': 1, 'status': 'completed'}, format='json')
        assert list(c.delete(TOUR + '?tour=admin').json()['tours']) == ['hr']
        assert c.delete(TOUR).json()['tours'] == {}

    @pytest.mark.parametrize('bad', [
        {'tour': '', 'version': 1, 'status': 'completed'}, {'tour': 'Bad Name!', 'version': 1, 'status': 'completed'},
        {'tour': 'admin', 'version': 1, 'status': 'maybe'}, {'tour': 'admin', 'version': 'one', 'status': 'completed'},
        {'tour': 'admin', 'version': 0, 'status': 'completed'}, {'tour': 'admin', 'version': True, 'status': 'completed'},
    ])
    def test_bad_requests_are_refused(self, people, bad):
        assert api(people['admin']).post(TOUR, bad, format='json').status_code == 400

    def test_every_role_can_record_its_own_progress(self, people):
        kid = make_student(people['a'])
        link_parent(people['parent'], kid)
        assert api(people['parent']).post(TOUR, {'tour': 'parent', 'version': 1, 'status': 'completed'}, format='json').status_code == 200
        assert api().get(TOUR).status_code == 401
