"""The risk forecasts table's reminder is a request that an administrator approves, not an email sent on one click."""
import datetime
from unittest import mock

from services.ai.models import AIActionRequest
from services.core.audit import chain
from services.core.audit.models import AuditLog
from tests.conftest import InvoiceFactory, StudentFactory
from tests.test_governed_ai import BASE, _client, _member, no_llm, other_school, roles, school  # noqa: F401

URL = BASE + 'requests/fee-reminder/'
SENDER = 'services.education.finance.views._send_invoice_reminder'


def _student_with_invoice(school):
    student = StudentFactory(tenant=school)
    InvoiceFactory(student=student, amount=1000, paid_amount=0, status='issued', due_date=datetime.date.today())
    return student


def test_asking_for_a_reminder_sends_nothing_and_waits_for_an_administrator(school, roles):
    s, admin = school
    accountant = _member(s, roles, 'accountant', 'amy@alder.test')
    student = _student_with_invoice(s)
    with mock.patch(SENDER) as sender:
        res = _client(accountant).post(URL, {'student_id': str(student.pk)}, format='json')
    assert res.status_code == 202 and 'Nothing has been sent' in res.json()['message'] and not sender.called
    req = AIActionRequest.all_objects.get()
    assert req.status == 'pending' and req.action == 'send_fee_reminder' and req.requested_by == accountant
    assert 'risk forecasts table' in req.record['origin'] and 'asked for a fee reminder' in req.record['asked']
    assert [r.new_data['status'] for r in AuditLog.objects.filter(chain=str(s.pk)).order_by('seq')] == ['requested']


def test_approving_it_sends_once_and_records_the_approver(school, roles):
    s, admin = school
    accountant = _member(s, roles, 'accountant', 'amy@alder.test')
    student = _student_with_invoice(s)
    _client(accountant).post(URL, {'student_id': str(student.pk)}, format='json')
    req = AIActionRequest.all_objects.get()
    with mock.patch(SENDER, return_value={'message': 'Fee reminder sent successfully', 'recipient': 'mum@example.test'}) as sender:
        res = _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {'note': 'Yes'}, format='json')
    assert res.status_code == 200 and res.json()['status'] == 'executed' and sender.call_count == 1
    assert sender.call_args.args[0].user == admin                                   # the approver is the one recorded as sending it
    assert [r.new_data['status'] for r in AuditLog.objects.filter(chain=str(s.pk)).order_by('seq')] == ['requested', 'approved', 'executed']
    assert chain.verify()['ok']


def test_a_family_with_no_contact_is_a_failed_approval_not_a_silent_success(school, roles):
    s, admin = school
    accountant = _member(s, roles, 'accountant', 'amy@alder.test')
    student = _student_with_invoice(s)
    _client(accountant).post(URL, {'student_id': str(student.pk)}, format='json')
    req = AIActionRequest.all_objects.get()
    with mock.patch(SENDER, side_effect=ValueError('no_email')):
        res = _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {}, format='json')
    assert res.json()['status'] == 'failed' and 'No email address' in res.json()['result']['error']


def test_who_can_ask_and_for_whom(school, other_school, roles):
    s, admin = school
    student = _student_with_invoice(s)
    teacher = _member(s, roles, 'teacher', 'tim@alder.test')
    assert _client(teacher).post(URL, {'student_id': str(student.pk)}, format='json').status_code == 403
    accountant = _member(s, roles, 'accountant', 'amy@alder.test')
    theirs = _student_with_invoice(other_school[0])
    assert _client(accountant).post(URL, {'student_id': str(theirs.pk)}, format='json').status_code == 404
    assert _client(accountant).post(URL, {'student_id': 'nonsense'}, format='json').status_code == 404
    no_debt = StudentFactory(tenant=s)
    res = _client(accountant).post(URL, {'student_id': str(no_debt.pk)}, format='json')
    assert res.status_code == 400 and 'no open invoices' in res.json()['error']
    assert not AIActionRequest.all_objects.exists()


def test_it_is_refused_while_ai_is_off(school, roles):
    s, admin = school
    accountant = _member(s, roles, 'accountant', 'amy@alder.test')
    student = _student_with_invoice(s)
    _client(admin).put('/api/v1/ai/settings/', {'ai_enabled': False}, format='json')
    assert _client(accountant).post(URL, {'student_id': str(student.pk)}, format='json').status_code == 403
