"""Two-person control: the person who asked never approves their own request, the school can name who may approve, and it can
require two different approvers before anything runs."""
import datetime
from unittest import mock

import pytest

from services.ai import actions
from services.ai.context import AIContext
from services.ai.models import AIActionRequest
from services.ai.tools import call_tool
from services.core.audit import chain
from services.core.audit.models import AuditLog
from services.core.tenants.models import TenantMembership
from tests.conftest import InvoiceFactory, StudentFactory, UserFactory
from tests.test_governed_ai import BASE, _client, _member, no_llm, other_school, roles, school  # noqa: F401

SETTINGS = '/api/v1/ai/settings/'
SENDER = 'services.education.finance.views._send_invoice_reminder'
OK = {'message': 'Fee reminder sent successfully', 'recipient': 'mum@example.test'}


def _second_admin(school, email='deputy@alder.test'):
    user = UserFactory(email=email)
    TenantMembership.objects.create(user=user, school=school, role='admin', is_active=True, is_primary=True)
    return user


def _ask(school, roles, who='accountant', email='amy@alder.test'):
    s, admin = school
    asker = _member(s, roles, who, email)
    student = StudentFactory(tenant=s)
    inv = InvoiceFactory(student=student, amount=1000, paid_amount=0, status='issued', due_date=datetime.date.today())
    from services.core.tenants.models import School
    ctx = AIContext(user=asker, role=who, tenant=School.objects.get(pk=s.pk))          # a request arrives with the school as saved now
    assert call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)['status'] == 'pending_approval'
    return asker, AIActionRequest.all_objects.get()


def _approve(user, req, note=''):
    return _client(user).post(f'{BASE}approvals/{req.id}/approve/', {'note': note}, format='json')


def test_nobody_approves_a_request_they_asked_for(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    ctx = AIContext(user=admin, role='admin', tenant=s)
    student = StudentFactory(tenant=s)
    inv = InvoiceFactory(student=student, amount=500, paid_amount=0, status='issued', due_date=datetime.date.today())
    call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
    req = AIActionRequest.all_objects.get()
    with mock.patch(SENDER, return_value=OK) as sender:
        own = _approve(admin, req)
        listed = _client(admin).get(BASE + 'approvals/').json()[0]
        other = _approve(deputy, req)
    assert own.status_code == 403 and 'someone else has to approve' in own.json()['error'] and listed['can_decide'] is False
    assert 'someone else' in listed['why_not'] and listed['can_withdraw'] is True
    assert other.status_code == 200 and other.json()['status'] == 'executed' and sender.call_count == 1


def test_the_person_who_asked_can_withdraw_but_a_stranger_cannot(school, roles):
    s, admin = school
    asker, req = _ask(school, roles)
    stranger = _member(s, roles, 'accountant', 'bob@alder.test')
    assert _client(stranger).post(f'{BASE}approvals/{req.id}/reject/', {}, format='json').status_code == 403
    res = _client(asker).post(f'{BASE}approvals/{req.id}/reject/', {'note': 'asked by mistake'}, format='json')
    assert res.status_code == 200 and res.json()['status'] == 'rejected'


def test_two_approvals_from_two_different_people_before_anything_runs(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    assert _client(admin).put(SETTINGS, {'approval': {'required': 2, 'approvers': []}}, format='json').status_code == 200
    asker, req = _ask(school, roles)
    with mock.patch(SENDER, return_value=OK) as sender:
        first = _approve(admin, req, 'looks right')
        assert first.json()['status'] == 'pending' and first.json()['approvals_needed'] == 2 and len(first.json()['approvals']) == 1 and not sender.called
        again = _approve(admin, req)
        assert again.status_code == 403 and 'already approved' in again.json()['error'] and not sender.called
        second = _approve(deputy, req, 'agreed')
    assert second.json()['status'] == 'executed' and sender.call_count == 1
    assert [a['by'] for a in second.json()['approvals']] and len(second.json()['approvals']) == 2
    steps = [(r.new_data['status'], r.new_data.get('step')) for r in AuditLog.objects.filter(chain=str(s.pk), resource_id=req.id).order_by('seq')]
    assert steps == [('requested', None), ('approved', 1), ('approved', 2), ('running', None), ('executed', None)] and chain.verify()['ok']
    record = _client(admin).get(f'{BASE}approvals/{req.id}/record/').json()
    assert record['basis']['controls']['approvals_required'] == 2 and record['request']['approvals_needed'] == 2


def test_a_request_keeps_the_stricter_rule_it_was_made_under(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    _client(admin).put(SETTINGS, {'approval': {'required': 2, 'approvers': []}}, format='json')
    asker, req = _ask(school, roles)
    _client(admin).put(SETTINGS, {'approval': {'required': 1, 'approvers': []}}, format='json')
    with mock.patch(SENDER, return_value=OK) as sender:
        assert _approve(admin, req).json()['status'] == 'pending' and not sender.called


def test_the_administrator_names_who_may_approve(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    res = _client(admin).put(SETTINGS, {'approval': {'required': 1, 'approvers': [str(deputy.pk)]}}, format='json')
    assert res.status_code == 200 and res.json()['approval']['approvers'] == [str(deputy.pk)]
    assert {c['email'] for c in res.json()['approval']['candidates']} >= {'head@alder.test', 'deputy@alder.test'}
    asker, req = _ask(school, roles)
    with mock.patch(SENDER, return_value=OK):
        refused = _approve(admin, req)
        assert refused.status_code == 403 and 'not one of the people' in refused.json()['error']
        assert _client(admin).get(BASE + 'approvals/').json() == []               # not named, so not shown other people's requests
        assert _approve(deputy, req).json()['status'] == 'executed'


def test_the_rule_cannot_be_set_to_something_nobody_can_meet(school, roles):
    s, admin = school
    one_admin = _client(admin).put(SETTINGS, {'approval': {'required': 2, 'approvers': []}}, format='json')
    assert one_admin.status_code == 400 and 'at least two people' in one_admin.json()['error']
    stranger = UserFactory(email='nobody@elsewhere.test')
    assert _client(admin).put(SETTINGS, {'approval': {'required': 1, 'approvers': [str(stranger.pk)]}}, format='json').status_code == 400
    assert _client(admin).put(SETTINGS, {'approval': {'required': 3, 'approvers': []}}, format='json').status_code == 400


def test_changing_the_rule_is_a_recorded_decision(school, roles):
    s, admin = school
    deputy = _second_admin(s)
    _client(admin).put(SETTINGS, {'approval': {'required': 2, 'approvers': []}}, format='json')
    row = AuditLog.objects.get(resource_type='ai.settings.approval')
    assert row.new_data['was']['required'] == 1 and row.new_data['now']['required'] == 2 and row.new_data['actor'] == 'head@alder.test'
    assert chain.verify()['ok']
    with mock.patch('services.ai.settings_api.audit_chain.append', side_effect=chain.AuditWriteError('down')):
        res = _client(admin).put(SETTINGS, {'approval': {'required': 1, 'approvers': []}}, format='json')
    from services.core.tenants.models import School
    assert res.status_code == 503 and actions.approval_policy(School.objects.get(pk=s.pk))['required'] == 2
