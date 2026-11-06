"""What happens between "approved" and "done": the exact action asked for is checked again, the intent to run is saved once, and an outcome
that cannot be confirmed is kept as UNKNOWN instead of being retried."""
import datetime
from unittest import mock

import pytest

from services.ai import actions
from services.ai.models import AIActionEffect, AIActionRequest
from services.core.audit.models import AuditLog
from tests.test_dual_approval import OK, SENDER, _approve, _ask, _second_admin
from tests.test_governed_ai import BASE, _client, no_llm, other_school, roles, school  # noqa: F401


def _one_approval(client_admin):
    client_admin.put('/api/v1/ai/settings/', {'approval': {'required': 1, 'approvers': []}}, format='json')


def test_the_default_is_two_different_approvers():
    from types import SimpleNamespace
    assert actions.approval_policy(SimpleNamespace(settings_json={}))['required'] == 2
    assert actions.approval_policy(SimpleNamespace(settings_json={'ai_approval': {'required': 1}}))['required'] == 1


def test_a_done_action_leaves_one_confirmed_intent_row(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    _one_approval(_client(admin))
    _, req = _ask(school, roles)
    with mock.patch(SENDER, return_value=OK):
        assert _approve(deputy, req).json()['status'] == 'executed'
    effect = AIActionEffect.objects.get(request=req)
    assert effect.state == 'confirmed' and effect.effect_key == f'send_fee_reminder:{req.id}' and effect.finished_at


def test_an_unconfirmed_outcome_is_kept_as_unknown_and_is_not_retried(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    _one_approval(_client(admin))
    _, req = _ask(school, roles)
    with mock.patch(SENDER, side_effect=TimeoutError('mail server did not answer')) as sender:
        first = _approve(deputy, req)
        again = _approve(deputy, req)
    assert first.json()['status'] == 'unknown' and 'could not confirm' in first.json()['result']['error']
    assert AIActionEffect.objects.get(request=req).state == 'unknown'
    assert again.status_code == 409 and sender.call_count == 1           # approving again does not send again


def test_a_check_that_stops_it_is_recorded_as_not_done(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    _one_approval(_client(admin))
    _, req = _ask(school, roles)
    with mock.patch(SENDER, side_effect=ValueError('no_email')):
        res = _approve(deputy, req)
    assert res.json()['status'] == 'failed' and AIActionEffect.objects.get(request=req).state == 'not_done'


def test_a_request_changed_after_it_was_asked_does_not_run(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    _one_approval(_client(admin))
    _, req = _ask(school, roles)
    AIActionRequest.all_objects.filter(pk=req.pk).update(arguments={'invoice_number': 'SOMEONE-ELSES-INVOICE'})
    with mock.patch(SENDER, return_value=OK) as sender:
        res = _approve(deputy, req)
    body = res.json()
    assert body['status'] == 'failed' and 'no longer matches' in body['result']['error']
    assert sender.call_count == 0 and not AIActionEffect.objects.filter(request=req).exists()


def test_the_digest_is_written_into_the_trail_when_the_request_is_made(school, roles):
    s, admin = school
    _, req = _ask(school, roles)
    row = AuditLog.objects.filter(resource_id=req.id).order_by('seq').first()
    assert row.new_data['action_sha256'] == actions.action_digest(req.action, s, req.arguments)
    assert actions.action_digest(req.action, s, {'invoice_number': 'X'}) != row.new_data['action_sha256']
