"""The decision-record list: assistant answers, risk-flag reviews, approvals and setting changes in one verified trail, for administrators only;
and "tell the counsellors" going through approval like everything else."""
from unittest import mock

import pytest

from services.ai.models import AIActionRequest
from services.analytics.models import StudentRisk
from services.core.audit.models import AuditLog
from tests.conftest import StudentFactory
from tests.test_dual_approval import _approve, _member, _second_admin
from tests.test_governed_ai import BASE, _client, no_llm, other_school, roles, school  # noqa: F401

CHAT = '/api/v1/ai/chat/'


def _chat(user, text='How many students are in the school?'):
    return _client(user).post(CHAT, {'message': text}, format='json')


def test_an_assistant_answer_is_recorded_with_what_it_was_based_on(school):
    s, admin = school
    assert _chat(admin).status_code == 200
    row = AuditLog.objects.filter(resource_type='ai.chat.answer').get()
    assert row.entry_hash and row.chain == str(s.pk)
    assert row.new_data['basis']['asked'].startswith('How many') and row.new_data['answer'] and row.new_data['basis_sha256']


def test_an_answer_that_cannot_be_recorded_is_not_shown(school):
    from services.core.audit import chain
    s, admin = school
    with mock.patch.object(chain, 'append', side_effect=chain.AuditWriteError('disk full')):
        res = _chat(admin)
    assert 'could not be recorded' in res.json()['reply']
    assert not AuditLog.objects.filter(resource_type='ai.chat.answer').exists()


def test_the_list_and_one_entry_are_for_administrators_only(school, roles):
    s, admin = school
    _chat(admin)
    listing = _client(admin).get(BASE + 'records/').json()
    assert listing and listing[0]['kind'] == 'answer' and listing[0]['kind_label'] == 'Assistant answer'
    detail = _client(admin).get(f"{BASE}records/{listing[0]['seq']}/").json()
    assert detail['chain']['verifies'] is True and detail['hash'] and 'tamper-evident' in detail['note']
    teacher = _member(s, roles, 'teacher', 'tess@alder.test')
    assert _client(teacher).get(BASE + 'records/').status_code == 403
    assert _client(teacher).get(f"{BASE}records/{listing[0]['seq']}/").status_code == 403


def test_one_school_never_sees_anothers_records(school, other_school):
    s, admin = school
    o, other_admin = other_school
    _chat(admin)
    assert _client(other_admin).get(BASE + 'records/').json() == []
    seq = AuditLog.objects.filter(resource_type='ai.chat.answer').get().seq
    assert _client(other_admin).get(f'{BASE}records/{seq}/').status_code == 404


def test_the_list_can_be_filtered_by_kind(school):
    s, admin = school
    _chat(admin)
    _client(admin).put('/api/v1/ai/settings/', {'features': {'ai_translation': False}}, format='json')
    assert {r['kind'] for r in _client(admin).get(BASE + 'records/?kind=settings').json()} == {'settings'}
    assert {r['kind'] for r in _client(admin).get(BASE + 'records/?kind=answer').json()} == {'answer'}


def test_telling_the_counsellors_waits_for_approval_and_then_runs(school):
    s, admin = school
    deputy = _second_admin(s)
    _client(admin).put('/api/v1/ai/settings/', {'approval': {'required': 1, 'approvers': []}}, format='json')
    student = StudentFactory(tenant=s)
    StudentRisk.objects.create(student=student, risk_level='high', factors={'dropout_risk': 62})
    res = _client(admin).post('/api/v1/ai/dropout-risk/notify/', {'student_id': str(student.id)}, format='json')
    assert res.status_code == 202 and 'approve' in res.json()['message']
    req = AIActionRequest.all_objects.get(action='notify_counsel')
    assert req.status == 'pending'
    done = _approve(deputy, req)
    assert done.json()['status'] == 'executed' and done.json()['result']['notified'] >= 1
