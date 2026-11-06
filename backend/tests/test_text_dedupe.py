"""The same automatic text to the same number is saved, and sent, once: the database refuses a second row with the same key."""
from unittest import mock

import pytest
from django.db import IntegrityError, transaction

from services.education.communication import texts
from services.education.communication.models import Message, SmsConfig
from tests.conftest import SchoolFactory


@pytest.fixture
def cfg(db):
    school = SchoolFactory()
    return SmsConfig.all_objects.create(tenant=school, account_sid='AC1', auth_token='t', from_number='+15550001111', default_country_code='1')


def _send(cfg, key):
    with mock.patch.object(texts.requests, 'post') as post:
        post.return_value.status_code, post.return_value.content, post.return_value.json.return_value = 201, b'{}', {'status': 'queued', 'sid': 'SM1'}
        return texts.send_text(cfg, 'sms', '+15550002222', 'Hello', event='fee', dedupe_key=key), post.call_count


def test_a_second_text_with_the_same_key_is_not_sent(cfg):
    first, calls_first = _send(cfg, 'fee:1:2026-11-06:sms:+15550002222')
    second, calls_second = _send(cfg, 'fee:1:2026-11-06:sms:+15550002222')
    assert first is not None and calls_first == 1
    assert second is None and calls_second == 0
    assert Message._base_manager.filter(tenant_id=cfg.tenant_id).count() == 1


def test_the_database_itself_refuses_a_duplicate_key(cfg):
    Message._base_manager.create(tenant_id=cfg.tenant_id, sender='School', recipient='x', message='a', channel='sms', dedupe_key='k1')
    with pytest.raises(IntegrityError), transaction.atomic():
        Message._base_manager.create(tenant_id=cfg.tenant_id, sender='School', recipient='x', message='b', channel='sms', dedupe_key='k1')
    # messages without a key are not affected, and another school may use the same key
    Message._base_manager.create(tenant_id=cfg.tenant_id, sender='School', recipient='x', message='c', channel='sms')
    Message._base_manager.create(tenant_id=cfg.tenant_id, sender='School', recipient='x', message='d', channel='sms')
    other = SchoolFactory()
    Message._base_manager.create(tenant_id=other.pk, sender='School', recipient='x', message='e', channel='sms', dedupe_key='k1')


def test_losing_the_race_means_no_send(cfg):
    """Two requests pass the look-up together; the second one's insert is refused and it must not call the provider."""
    Message._base_manager.create(tenant_id=cfg.tenant_id, sender='School', recipient='x', message='a', channel='sms', dedupe_key='k2')
    with mock.patch('django.db.models.query.QuerySet.exists', return_value=False):          # the look-up said "not sent yet"
        result, calls = _send(cfg, 'k2')
    assert result is None and calls == 0
