"""One page that says what was asked, what the request was based on, every step, and whether the trail still verifies."""
from unittest import mock

import pytest

from services.ai.agent import run_agent
from services.ai.context import AIContext
from services.ai.models import AIActionRequest
from services.core.audit.models import AuditLog

from tests.test_governed_ai import (BASE, ScriptedLLM, _client, _member, _unpaid_invoice, no_llm, other_school, roles, school)  # noqa: F401


def _make(school, roles):
    s, admin = school
    accountant = _member(s, roles, 'accountant', 'amy@alder.test')
    inv = _unpaid_invoice(s)
    ctx = AIContext(user=accountant, role='accountant', tenant=s)
    llm = ScriptedLLM('propose_send_fee_reminder', {'invoice_number': inv.invoice_number})
    llm.provider = 'gemini'
    llm.model_for = lambda tier: 'gemini-test'
    list(run_agent(ctx, [{'role': 'user', 'content': 'Please remind the family of invoice ' + inv.invoice_number}], llm))
    return s, admin, accountant, AIActionRequest.all_objects.get()


def test_the_record_holds_the_basis_the_steps_and_a_verified_chain(school, roles):
    s, admin, accountant, req = _make(school, roles)
    with mock.patch('services.education.communication.texts.fee_reminder', return_value=[object()]):
        _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {'note': 'Go ahead'}, format='json')
    body = _client(admin).get(f'{BASE}approvals/{req.id}/record/').json()
    basis = body['basis']
    assert basis['provider'] == 'gemini' and basis['model'] == 'gemini-test' and len(basis['instructions_sha256']) == 64
    assert 'remind the family' in basis['asked'] and basis['controls']['contact_details_shared'] is False
    assert basis['controls']['use_notice_version'] >= 1 and 'monthly_token_cap' in basis['controls']
    assert [t['status'] for t in body['trail']] == ['requested', 'approved', 'executed']
    assert body['trail'][0]['by'] == 'amy@alder.test' and body['trail'][1]['by'] == 'head@alder.test'
    assert body['request']['status'] == 'executed' and body['request']['decision_note'] == 'Go ahead'
    assert body['chain']['verifies'] and body['basis_matches_trail']


def test_a_changed_basis_or_trail_is_reported(school, roles):
    s, admin, accountant, req = _make(school, roles)
    AIActionRequest.all_objects.filter(pk=req.pk).update(record={**req.record, 'asked': 'something else entirely'})
    assert _client(admin).get(f'{BASE}approvals/{req.id}/record/').json()['basis_matches_trail'] is False
    AuditLog._base_manager.filter(chain=str(s.pk), seq=1).update(new_data={'status': 'requested', 'actor': 'someone@else.test'})
    body = _client(admin).get(f'{BASE}approvals/{req.id}/record/').json()
    assert body['chain']['verifies'] is False and body['chain']['problems']


def test_who_may_open_a_record(school, other_school, roles):
    s, admin, accountant, req = _make(school, roles)
    assert _client(accountant).get(f'{BASE}approvals/{req.id}/record/').status_code == 200            # their own
    stranger = _member(s, roles, 'accountant', 'bob@alder.test')
    assert _client(stranger).get(f'{BASE}approvals/{req.id}/record/').status_code == 404              # someone else's
    assert _client(other_school[1]).get(f'{BASE}approvals/{req.id}/record/').status_code == 404       # another school
    download = _client(admin).get(f'{BASE}approvals/{req.id}/record/?download=1')
    assert download.status_code == 200 and 'attachment' in download['Content-Disposition']
