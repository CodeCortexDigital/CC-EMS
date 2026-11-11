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


def _unknown(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    _one_approval(_client(admin))
    _, req = _ask(school, roles)
    with mock.patch(SENDER, side_effect=TimeoutError('no answer')):
        assert _approve(deputy, req).json()['status'] == 'unknown'
    return s, admin, deputy, req


def _settle(user, req, outcome='done', note='Looked in the mail log'):
    return _client(user).post(f'{BASE}approvals/{req.id}/settle/', {'outcome': outcome, 'note': note}, format='json')


def test_a_person_settles_an_unconfirmed_result_and_it_is_recorded(school, roles):
    s, admin, deputy, req = _unknown(school, roles)
    listed = _client(deputy).get(BASE + 'approvals/?status=all').json()[0]
    assert listed['can_settle'] is True
    res = _settle(deputy, req, 'done')
    assert res.status_code == 200 and res.json()['status'] == 'executed'
    assert AIActionEffect.objects.get(request=req).state == 'confirmed'
    steps = [r.new_data['status'] for r in AuditLog.objects.filter(resource_id=req.id).exclude(entry_hash='').order_by('seq')]
    assert steps[-1] == 'settled'
    from services.core.audit import chain
    assert chain.verify()['ok']


def test_settling_as_not_done_closes_it_without_sending(school, roles):
    s, admin, deputy, req = _unknown(school, roles)
    with mock.patch(SENDER, return_value=OK) as sender:
        res = _settle(deputy, req, 'not_done')
    assert res.json()['status'] == 'failed' and sender.call_count == 0
    assert AIActionEffect.objects.get(request=req).state == 'not_done'


def test_settling_needs_a_note_a_valid_outcome_an_eligible_person_and_an_unconfirmed_result(school, roles):
    s, admin, deputy, req = _unknown(school, roles)
    assert _settle(deputy, req, 'done', note='').status_code == 400
    assert _settle(deputy, req, 'maybe').status_code == 400
    from tests.test_governed_ai import _member
    stranger = _member(s, roles, 'accountant', 'zed@alder.test')
    assert _settle(stranger, req).status_code == 403
    assert _settle(deputy, req).status_code == 200
    assert _settle(deputy, req).status_code == 409                       # already settled
