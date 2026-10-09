"""The nightly demo reset endpoint: only on a demo server, only with the secret, one at a time, never on the live site."""
import pytest
from rest_framework.test import APIClient

from services.education.imports import demo_reset_api

pytestmark = pytest.mark.django_db
URL = '/api/v1/demo/reset/'


class _Inline:
    """Runs the reset straight away instead of in a background thread."""
    def __init__(self, target, daemon=True):
        self.target = target

    def start(self):
        self.target()


@pytest.fixture
def server(monkeypatch, settings):
    settings.APP_ENV = 'staging'
    monkeypatch.setenv('DEMO_RESET_TOKEN', 'long-random-secret')
    calls = []
    monkeypatch.setattr(demo_reset_api, 'call_command', lambda *a, **k: calls.append(a))
    monkeypatch.setattr(demo_reset_api.threading, 'Thread', _Inline)
    monkeypatch.setattr(demo_reset_api, 'connection', type('C', (), {'close': staticmethod(lambda: None)}))
    return calls


def _post(token='long-random-secret'):
    headers = {'HTTP_X_DEMO_RESET_TOKEN': token} if token is not None else {}
    return APIClient().post(URL, **headers)


def test_the_right_token_starts_a_reset(server):
    res = _post()
    assert res.status_code == 202 and res.json()['status'] == 'started'
    assert server == [('setup_demo', '--reset')]


def test_a_wrong_or_missing_token_looks_like_nothing_is_there(server):
    assert _post('guess').status_code == 404
    assert _post(None).status_code == 404
    assert server == []


def test_it_never_exists_on_the_live_site(server, settings):
    settings.APP_ENV = 'production'
    assert _post().status_code == 404
    assert server == []


def test_it_is_off_unless_a_token_is_configured(server, monkeypatch):
    monkeypatch.delenv('DEMO_RESET_TOKEN')
    assert _post().status_code == 404
    assert server == []


def test_only_one_reset_runs_at_a_time(server):
    assert demo_reset_api._running.acquire(blocking=False)
    try:
        res = _post()
        assert res.status_code == 409
        assert server == []
    finally:
        demo_reset_api._running.release()
    assert _post().status_code == 202                                           # and it can run again afterwards
