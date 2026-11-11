"""Governed AI: the assistant answers from the school's own documents (with sources) and can only *ask* for actions, which a
person with the right role must approve before anything runs."""
import datetime
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.ai import actions, knowledge
from services.ai.agent import run_agent
from services.ai.context import AIContext
from services.ai.llm.base import LLMTurn, ToolCall, Usage
from services.ai.models import AIActionRequest, KnowledgeChunk, KnowledgeDocument
from services.ai.tools import ToolNotAllowed, call_tool, get_tools_for_role
from services.core.audit.models import AuditLog
from services.core.tenants.models import TenantMembership
from services.core.tenants.signup import create_school_with_admin
from tests.conftest import ClassFactory, InvoiceFactory, SectionFactory, StudentFactory, UserFactory

BASE = '/api/v1/ai/governance/'
User = get_user_model()


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


@pytest.fixture(autouse=True)
def no_llm(settings):
    settings.OPENAI_API_KEY = ''


@pytest.fixture
def roles(monkeypatch):
    """Give plain users the role a test needs (the real rule reads profiles and memberships that these tests do not need)."""
    table = {}
    from services.core.accounts import decorators
    real = decorators.get_user_role

    def fake(user):
        return table.get(getattr(user, 'pk', None)) or real(user)

    for module in ('services.ai.permissions', 'services.ai.context', 'services.ai.actions'):
        monkeypatch.setattr(f'{module}.get_user_role', fake)
    return table


@pytest.fixture
def school(db):
    school, admin = create_school_with_admin(school_name='Alder Academy', admin_email='head@alder.test', admin_name='Head', password='Sturdy-Pass-91x')
    # New schools need two different approvers by default; these tests are about one approval unless they say otherwise.
    school.settings_json = {**(school.settings_json or {}), 'ai_approval': {'required': 1, 'approvers': []}}
    school.save(update_fields=['settings_json'])
    return school, admin


@pytest.fixture
def other_school(db):
    return create_school_with_admin(school_name='Birch Academy', admin_email='head@birch.test', admin_name='Birch Head', password='Sturdy-Pass-91x')


def _member(school, roles, role, email):
    user = UserFactory(email=email)
    TenantMembership.objects.create(user=user, school=school, role='staff', is_active=True, is_primary=True)
    roles[user.pk] = role
    return user


def _doc(client, title='Late policy', body=None, audience='everyone'):
    body = body or ('Students who arrive after 8:15 are marked late. Three late arrivals in a month lead to a call home.\n\n'
                    'Uniform: navy sweater, grey trousers or skirt, and plain black shoes.')
    return client.post(BASE + 'knowledge/', {'title': title, 'body': body, 'audience': audience}, format='json')


def _unpaid_invoice(school):
    student = StudentFactory(tenant=school)
    return InvoiceFactory(student=student, amount=1000, paid_amount=0, status='pending', due_date=datetime.date.today())


class TestKnowledgeSearch:
    def test_the_best_passage_comes_first_and_has_its_title(self, school):
        s, admin = school
        assert _doc(_client(admin)).status_code == 201
        _doc(_client(admin), title='Lunch', body='Lunch is served at noon in the hall. Vegetarian meals are available every day of the week.')
        hits = knowledge.search('when are students marked late?', role='parent', tenant=s)
        assert hits and hits[0]['title'] == 'Late policy' and 'after 8:15' in hits[0]['text']
        assert knowledge.search('quantum chromodynamics', role='parent', tenant=s) == []

    def test_long_documents_are_split_into_passages(self, school):
        s, admin = school
        body = '\n\n'.join(f'Paragraph {i}. ' + 'The school day runs as normal. ' * 12 for i in range(12))
        res = _doc(_client(admin), title='Handbook', body=body)
        assert res.status_code == 201 and res.json()['passages'] >= 3
        assert all(len(c.text) <= knowledge.CHUNK_CHARS + knowledge.OVERLAP_CHARS + 20 for c in KnowledgeChunk._base_manager.all())

    def test_audience_is_enforced_for_each_role(self, school):
        s, admin = school
        c = _client(admin)
        _doc(c, 'Public', 'Visitors sign in at the front desk before entering the building.', 'everyone')
        _doc(c, 'Staff only', 'Staff parking is behind the gym; the gate code is changed every term.', 'staff')
        _doc(c, 'Admin only', 'Salary bands for teachers are reviewed in March by the board.', 'admin')
        titles = lambda role, q: {h['title'] for h in knowledge.search(q, role=role, tenant=s)}      # noqa: E731
        assert titles('parent', 'gate code parking') == set() and titles('student', 'salary bands') == set()
        assert titles('teacher', 'gate code parking') == {'Staff only'} and titles('teacher', 'salary bands') == set()
        assert titles('admin', 'salary bands') == {'Admin only'}
        assert titles('parent', 'visitors sign in') == {'Public'}

    def test_another_schools_documents_are_never_found(self, school, other_school):
        a, admin_a = school
        b, admin_b = other_school
        _doc(_client(admin_a), 'Alder secret', 'The Alder Academy emergency meeting point is the east field behind the library.')
        assert knowledge.search('emergency meeting point', role='admin', tenant=b) == []
        assert _client(admin_b).get(BASE + 'knowledge/').json() == []
        doc = KnowledgeDocument.all_objects.get(tenant=a)
        assert _client(admin_b).get(f'{BASE}knowledge/{doc.id}/').status_code == 404
        assert _client(admin_b).delete(f'{BASE}knowledge/{doc.id}/').status_code == 404
        assert KnowledgeDocument.all_objects.filter(pk=doc.pk).exists()

    def test_only_administrators_manage_documents(self, school, roles):
        s, admin = school
        teacher = _member(s, roles, 'teacher', 'tess@alder.test')
        assert _doc(_client(teacher)).status_code == 403
        assert _client(teacher).get(BASE + 'knowledge/').status_code == 403

    def test_editing_reindexes_and_deleting_removes(self, school):
        s, admin = school
        c = _client(admin)
        doc = _doc(c).json()
        res = c.patch(f"{BASE}knowledge/{doc['id']}/", {'body': 'Homework is set on Mondays and due on Fridays every week.'}, format='json')
        assert res.status_code == 200
        assert knowledge.search('after 8:15 late', role='admin', tenant=s) == []
        assert knowledge.search('homework due fridays', role='admin', tenant=s)
        assert c.delete(f"{BASE}knowledge/{doc['id']}/").status_code == 204
        assert not KnowledgeChunk._base_manager.filter(document_id=doc['id']).exists()

    def test_a_document_needs_a_title_and_some_text(self, school):
        s, admin = school
        c = _client(admin)
        assert c.post(BASE + 'knowledge/', {'title': '', 'body': 'x' * 40}, format='json').status_code == 400
        assert c.post(BASE + 'knowledge/', {'title': 'T', 'body': 'short'}, format='json').status_code == 400
        assert c.post(BASE + 'knowledge/', {'title': 'T', 'body': 'x' * 40, 'audience': 'world'}, format='json').status_code == 400

    def test_the_test_search_shows_what_a_role_would_find(self, school):
        s, admin = school
        c = _client(admin)
        _doc(c, 'Admin only', 'Salary bands for teachers are reviewed in March by the board.', 'admin')
        assert c.post(BASE + 'knowledge/search/', {'query': 'salary bands'}, format='json').json()['passages']
        assert c.post(BASE + 'knowledge/search/', {'query': 'salary bands', 'as_role': 'parent'}, format='json').json()['passages'] == []


class TestAssistantUsesDocuments:
    def test_the_tool_is_offered_to_every_role_and_returns_sources(self, school):
        s, admin = school
        _doc(_client(admin))
        assert all('search_school_knowledge' in {t['name'] for t in get_tools_for_role(r)} for r in ('admin', 'teacher', 'student', 'parent'))
        ctx = AIContext(user=admin, role='parent', tenant=s)
        out = call_tool('search_school_knowledge', {'query': 'late arrivals'}, ctx)
        assert out['found'] and out['passages'][0]['document'] == 'Late policy'
        assert list(ctx.extra['sources'].values()) == ['Late policy']

    def test_without_an_ai_provider_the_chat_still_answers_from_the_documents(self, school):
        s, admin = school
        _doc(_client(admin))
        res = _client(admin).post('/api/v1/ai/chat/', {'message': 'what happens after three late arrivals'}, format='json')
        assert res.status_code == 200
        body = res.json()
        assert 'call home' in body['reply'] and body['sources'][0]['title'] == 'Late policy'


class ScriptedLLM:
    """A model that first asks for one tool, then answers."""
    provider = 'scripted'

    def __init__(self, name, arguments):
        self.calls = [ToolCall(id='1', name=name, arguments=arguments)]
        self.asked = False

    def respond(self, *, system, messages, tools, tier='fast'):
        self.tool_names = [t['name'] for t in tools]
        if not self.asked:
            self.asked = True
            return LLMTurn(text='', tool_calls=self.calls, usage=Usage(), model='scripted')
        return LLMTurn(text='It is waiting for approval.', tool_calls=[], usage=Usage(), model='scripted')

    def assistant_turn(self, turn):
        return {'role': 'assistant', 'content': 'tool'}

    def tool_results(self, results):
        self.results = results
        return [{'role': 'user', 'content': 'results'}]


class TestApprovalGate:
    def _ask(self, school, roles, who='accountant'):
        s, admin = school
        accountant = _member(s, roles, who, 'amy@alder.test')
        inv = _unpaid_invoice(s)
        ctx = AIContext(user=accountant, role=who, tenant=s)
        return s, admin, accountant, inv, ctx

    def test_the_assistant_can_only_ask_and_nothing_runs(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        with mock.patch('services.education.communication.texts.fee_reminder') as sender:
            llm = ScriptedLLM('propose_send_fee_reminder', {'invoice_number': inv.invoice_number})
            events = list(run_agent(ctx, [{'role': 'user', 'content': 'remind them'}], llm))
        assert not sender.called
        req = AIActionRequest.all_objects.get()
        assert req.status == 'pending' and req.tenant == s and req.requested_by == accountant and req.requester_role == 'accountant'
        assert 'Nothing has been done' in llm.results[0][1] and events[-1]['result'].reply == 'It is waiting for approval.'
        assert AuditLog.objects.filter(resource_type='ai.action.send_fee_reminder', new_data__status='requested').exists()

    def test_only_roles_allowed_to_ask_are_given_the_tool(self, school, roles):
        names = lambda r: {t['name'] for t in get_tools_for_role(r)}                       # noqa: E731
        assert 'propose_send_fee_reminder' in names('accountant') and 'propose_send_fee_reminder' not in names('teacher')
        assert not any(n.startswith('propose_') for n in names('student') | names('parent'))
        s, admin = school
        student_ctx = AIContext(user=admin, role='student', tenant=s)
        with pytest.raises(ToolNotAllowed):
            call_tool('propose_send_fee_reminder', {'invoice_number': 'X'}, student_ctx)

    def test_the_assistant_cannot_name_an_action_that_is_not_registered(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        assert call_tool('propose_delete_every_student', {}, ctx) == {'error': 'Unknown tool propose_delete_every_student'}
        assert actions.propose(ctx, 'delete_every_student', {})['error'].startswith('This action is not available')
        assert not AIActionRequest.all_objects.exists()

    def test_an_invoice_that_does_not_exist_or_is_another_schools_is_refused(self, school, other_school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        theirs = _unpaid_invoice(other_school[0])
        assert 'No invoice' in call_tool('propose_send_fee_reminder', {'invoice_number': 'NOPE'}, ctx)['error']
        assert 'No invoice' in call_tool('propose_send_fee_reminder', {'invoice_number': theirs.invoice_number}, ctx)['error']
        assert not AIActionRequest.all_objects.exists()

    def test_approving_runs_it_exactly_once(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        req = AIActionRequest.all_objects.get()
        with mock.patch('services.education.communication.texts.fee_reminder', return_value=[object()]) as sender:
            res = _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {'note': 'Go ahead'}, format='json')
            again = _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {}, format='json')
        assert res.status_code == 200 and res.json()['status'] == 'executed' and res.json()['decided_by'] and res.json()['result']['sent'] == 1
        assert again.status_code == 409 and sender.call_count == 1
        assert AuditLog.objects.filter(resource_type='ai.action.send_fee_reminder', new_data__status='executed').exists()

    def test_nothing_runs_if_the_approval_cannot_be_recorded(self, school, roles):
        from services.core.audit import chain as audit_chain

        s, admin, accountant, inv, ctx = self._ask(school, roles)
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        req = AIActionRequest.all_objects.get()
        with mock.patch('services.education.communication.texts.fee_reminder') as sender,                 mock.patch('services.ai.actions.audit_chain.append', side_effect=audit_chain.AuditWriteError('down')):
            with pytest.raises(audit_chain.AuditWriteError):
                actions.approve(req, admin, 'admin', s)
        req.refresh_from_db()
        assert not sender.called and req.status == 'pending' and req.decided_by is None

    def test_a_request_that_cannot_be_recorded_is_not_stored(self, school, roles):
        from services.core.audit import chain as audit_chain

        s, admin, accountant, inv, ctx = self._ask(school, roles)
        with mock.patch('services.ai.actions.audit_chain.append', side_effect=audit_chain.AuditWriteError('down')):
            out = call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        assert 'could not be recorded' in out['error'] and not AIActionRequest.all_objects.exists()

    def test_the_whole_approval_is_in_the_verified_trail(self, school, roles):
        from services.core.audit import chain as audit_chain

        s, admin, accountant, inv, ctx = self._ask(school, roles)
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        req = AIActionRequest.all_objects.get()
        with mock.patch('services.education.communication.texts.fee_reminder', return_value=[object()]):
            _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {'note': 'Go ahead'}, format='json')
        steps = list(AuditLog.objects.filter(chain=str(s.pk)).order_by('seq').values_list('new_data__status', flat=True))
        assert steps == ['requested', 'approved', 'running', 'executed'] and audit_chain.verify()['ok']

    def test_rejecting_runs_nothing(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        req = AIActionRequest.all_objects.get()
        with mock.patch('services.education.communication.texts.fee_reminder') as sender:
            res = _client(admin).post(f'{BASE}approvals/{req.id}/reject/', {'note': 'Not today'}, format='json')
            late = _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {}, format='json')
        assert res.json()['status'] == 'rejected' and res.json()['decision_note'] == 'Not today'
        assert late.status_code == 409 and not sender.called

    def test_the_person_who_asked_cannot_approve_their_own_request(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        req = AIActionRequest.all_objects.get()
        with mock.patch('services.education.communication.texts.fee_reminder') as sender:
            res = _client(accountant).post(f'{BASE}approvals/{req.id}/approve/', {}, format='json')
        assert res.status_code == 403 and not sender.called
        assert AIActionRequest.all_objects.get().status == 'pending'

    def test_another_schools_administrator_cannot_see_or_decide_it(self, school, other_school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        req = AIActionRequest.all_objects.get()
        outsider = _client(other_school[1])
        assert outsider.get(BASE + 'approvals/?status=all').json() == []
        assert outsider.post(f'{BASE}approvals/{req.id}/approve/', {}, format='json').status_code == 404
        assert AIActionRequest.all_objects.get().status == 'pending'

    def test_an_expired_request_cannot_be_approved(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        AIActionRequest.all_objects.update(expires_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc))
        req = AIActionRequest.all_objects.get()
        with mock.patch('services.education.communication.texts.fee_reminder') as sender:
            res = _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {}, format='json')
        assert res.status_code == 409 and 'expired' in res.json()['error'] and not sender.called
        assert AIActionRequest.all_objects.get().status == 'expired'

    def test_permission_is_checked_again_at_approval_time(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        req = AIActionRequest.all_objects.get()
        roles[accountant.pk] = 'student'                                   # their role changed after asking
        with mock.patch('services.education.communication.texts.fee_reminder') as sender:
            res = _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {}, format='json')
        assert res.json()['status'] == 'failed' and 'no longer has permission' in res.json()['result']['error'] and not sender.called

    def test_the_data_is_checked_again_at_approval_time(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        inv.paid_amount = inv.amount
        inv.save()                                                          # paid in the meantime
        req = AIActionRequest.all_objects.get()
        with mock.patch('services.education.communication.texts.fee_reminder') as sender:
            res = _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {}, format='json')
        assert res.json()['status'] == 'failed' and 'nothing left to pay' in res.json()['result']['error'] and not sender.called

    def test_lists_show_approvers_everything_and_others_only_their_own(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        other = _member(s, roles, 'accountant', 'bob@alder.test')
        call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        assert len(_client(admin).get(BASE + 'approvals/').json()) == 1
        assert _client(admin).get(BASE + 'approvals/').json()[0]['can_decide'] is True
        mine = _client(accountant).get(BASE + 'approvals/').json()
        assert len(mine) == 1 and mine[0]['can_decide'] is False
        assert _client(other).get(BASE + 'approvals/').json() == []

    def test_there_is_a_limit_on_waiting_requests(self, school, roles):
        s, admin, accountant, inv, ctx = self._ask(school, roles)
        for _ in range(actions.MAX_PENDING_PER_USER):
            assert 'error' not in call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)
        assert 'waiting for approval' in call_tool('propose_send_fee_reminder', {'invoice_number': inv.invoice_number}, ctx)['error']

    def test_the_chat_reports_requests_it_made(self, school, roles):
        s, admin = school
        inv = _unpaid_invoice(s)
        llm = ScriptedLLM('propose_send_fee_reminder', {'invoice_number': inv.invoice_number})
        with mock.patch('services.ai.views.get_llm_client', return_value=llm), mock.patch('services.ai.views.record_usage'):
            res = _client(admin).post('/api/v1/ai/chat/', {'message': 'send a reminder for that invoice'}, format='json')
        assert res.status_code == 200
        assert res.json()['requests'][0]['status'] == 'pending' and 'fee reminder' in res.json()['requests'][0]['summary']


class TestSupportCaseAction:
    def test_a_teacher_can_only_ask_for_students_in_their_own_classes(self, school, roles, monkeypatch):
        from services.education.interventions.models import Intervention

        s, admin = school
        teacher = _member(s, roles, 'teacher', 'tess@alder.test')
        mine, theirs = ClassFactory(school=s), ClassFactory(school=s)
        kid = StudentFactory(tenant=s, current_class=mine, current_section=SectionFactory(class_obj=mine))
        stranger = StudentFactory(tenant=s, current_class=theirs, current_section=SectionFactory(class_obj=theirs))
        monkeypatch.setattr('services.ai.context._get_teacher_class_ids', lambda user: [mine.id])      # which classes they teach
        ctx = AIContext(user=teacher, role='teacher', tenant=s)
        assert 'error' in call_tool('propose_open_support_case', {'student_id': stranger.student_id, 'title': 'Check in'}, ctx)
        ok = call_tool('propose_open_support_case', {'student_id': kid.student_id, 'title': 'Check in', 'priority': 'high'}, ctx)
        assert ok['status'] == 'pending_approval' and not Intervention.all_objects.exists()
        req = AIActionRequest.all_objects.get()
        res = _client(admin).post(f'{BASE}approvals/{req.id}/approve/', {}, format='json')
        assert res.json()['status'] == 'executed'
        case = Intervention.all_objects.get()
        assert case.student == kid and case.priority == 'high' and case.created_by == admin and case.tenant == s
