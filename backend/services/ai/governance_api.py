"""Approvals and school documents for the AI assistant (``/api/v1/ai/governance/``).

    GET  actions/                     the actions the assistant can ask for, and who may ask and approve
    GET  approvals/?status=           requests waiting (default), or all. Approvers see the whole school's; others see their own
    GET  approvals/<id>/record/       the decision record for one request: basis, every step in the verified trail, and the chain check
                                      (add ?download=1 to save it as a file)
    POST requests/fee-reminder/       {student_id}  ask for a fee reminder for the student's oldest open invoice (admin or accountant);
                                      it waits here for an administrator, like anything the assistant asks for
    POST approvals/<id>/approve/      {note?}  approve and run it (approver roles only)
    POST approvals/<id>/reject/       {note?}  reject it (approver roles only)
    GET/POST knowledge/               the school's documents the assistant may quote (administrators)
    GET/PATCH/DELETE knowledge/<id>/  one document, with its text
    POST knowledge/search/            {query}  what the assistant would find for a question, as each role would see it
"""
from __future__ import annotations

import json

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from services.core.audit import chain as audit_chain
from services.core.audit.models import AuditLog
from services.education.students.access import audit_write

from . import actions, knowledge
from .context import AIContext
from .models import AIActionRequest, KnowledgeDocument
from .permissions import HasAIRole, IsAIAdmin
from .quota import requires_feature

MAX_TITLE = 200


def _err(message, code=400):
    return Response({'error': message}, status=code)


def _person(user):
    return (getattr(user, 'full_name', '') or user.email) if user else ''


def _request_json(r: AIActionRequest, ctx) -> dict:
    spec = actions.ACTIONS.get(r.action)
    pending = r.status == 'pending'
    problem = actions.decide_problem(ctx.user, ctx.role, r, ctx.tenant, 'approve') if pending else None
    return {
        'id': str(r.id), 'action': r.action, 'label': spec.label if spec else r.action, 'summary': r.summary, 'status': r.status,
        'requested_by': _person(r.requested_by), 'requester_role': r.requester_role, 'created_at': r.created_at, 'expires_at': r.expires_at,
        'decided_by': _person(r.decided_by), 'decided_at': r.decided_at, 'decision_note': r.decision_note, 'result': r.result,
        'approver_roles': list(spec.approver_roles) if spec else [],
        'approvals_needed': actions.approvals_needed(r, ctx.tenant),
        'approvals': [{'by': a.get('name', ''), 'at': a.get('at'), 'note': a.get('note', '')} for a in (r.approvals or [])],
        'can_decide': pending and problem is None,
        'why_not': problem if pending and problem and actions.is_approver(ctx.user, ctx.role, ctx.tenant) else '',
        'can_withdraw': pending and r.requested_by_id == ctx.user.id,
    }


@api_view(['GET'])
@permission_classes([HasAIRole])
def action_list(request):
    return Response([{'name': s.name, 'label': s.label, 'request_roles': list(s.request_roles), 'approver_roles': list(s.approver_roles)}
                     for s in actions.ACTIONS.values()])


@api_view(['GET'])
@permission_classes([HasAIRole])
def approval_list(request):
    ctx = AIContext.from_request(request)
    now = timezone.now()
    AIActionRequest.all_objects.filter(tenant=ctx.tenant, status='pending', expires_at__lte=now).update(status='expired')
    rows = AIActionRequest.all_objects.filter(tenant=ctx.tenant).select_related('requested_by', 'decided_by')
    if not actions.is_approver(ctx.user, ctx.role, ctx.tenant):
        rows = rows.filter(requested_by=request.user)               # only approvers see other people's requests
    if request.query_params.get('status', 'pending') != 'all':
        rows = rows.filter(status='pending')
    return Response([_request_json(r, ctx) for r in rows[:100]])


def _decide(request, pk, verb):
    ctx = AIContext.from_request(request)
    req = AIActionRequest.all_objects.filter(pk=pk, tenant=ctx.tenant).first()
    if req is None:
        return _err('Request not found.', 404)
    problem = actions.decide_problem(request.user, ctx.role, req, ctx.tenant, verb)
    if problem:
        return _err(problem, 409 if 'already been decided' in problem else 403)
    note = request.data.get('note', '') if isinstance(request.data, dict) else ''
    try:
        done = (actions.approve if verb == 'approve' else actions.reject)(req, request.user, ctx.role, ctx.tenant, str(note or ''))
    except actions.ActionError as exc:
        return _err(str(exc), 409)
    except PermissionError as exc:
        return _err(str(exc), 403)
    done = AIActionRequest.all_objects.select_related('requested_by', 'decided_by').get(pk=done.pk)
    return Response(_request_json(done, ctx))


@api_view(['POST'])
@permission_classes([HasAIRole])
@requires_feature('ai_risk_scan')
def request_fee_reminder(request):
    """A person asks for a fee reminder from the risk forecasts table. Nothing is sent: it becomes a request for an administrator to
    approve, with a decision record, exactly like a request from the assistant."""
    from services.education.finance.billing import account_for_student
    from services.education.students.models import Student

    ctx = AIContext.from_request(request)
    data = request.data if isinstance(request.data, dict) else {}
    try:
        student = Student.all_objects.filter(tenant=ctx.tenant, pk=data.get('student_id')).first()
    except Exception:
        student = None
    if student is None:
        return _err('Student not found.', 404)
    invoice = account_for_student(student).open_invoices().first()
    if invoice is None:
        return _err(f'{student.full_name} has no open invoices, so there is nothing to remind about.')
    ctx.extra.update({'origin': 'risk forecasts table (a person asked for it)', 'llm_provider': '', 'llm_model': '',
                      'user_message': f'{_person(request.user)} asked for a fee reminder for {student.full_name} from the risk forecasts table.'})
    out = actions.propose(ctx, 'send_fee_reminder', {'invoice_number': invoice.invoice_number})
    if out.get('error'):
        return _err(out['error'], 403 if 'not available for your role' in out['error'] else 400)
    return Response({'request_id': out['request_id'], 'summary': out['summary'],
                     'message': 'Sent for approval. Nothing has been sent to the family yet: an administrator must approve it in AI Approvals.'}, status=202)


@api_view(['GET'])
@permission_classes([HasAIRole])
def approval_record(request, pk):
    """The decision record: what was asked, what the request was based on, every recorded step and who took it, and whether the
    trail still verifies. Approvers see any request in the school; everyone else only their own."""
    ctx = AIContext.from_request(request)
    req = AIActionRequest.all_objects.filter(pk=pk, tenant=ctx.tenant).select_related('requested_by', 'decided_by').first()
    if req is None or (not actions.is_approver(request.user, ctx.role, ctx.tenant) and req.requested_by_id != request.user.id):
        return _err('Request not found.', 404)
    chain_name = str(ctx.tenant.pk) if ctx.tenant else 'platform'
    steps = AuditLog.objects.filter(chain=chain_name, resource_id=req.id).order_by('seq')
    trail = [{'seq': r.seq, 'at': r.timestamp, 'status': (r.new_data or {}).get('status'), 'action': r.action, 'by': (r.new_data or {}).get('actor', ''),
              'data': {k: v for k, v in (r.new_data or {}).items() if k not in ('actor', 'status')}, 'hash': r.entry_hash, 'previous_hash': r.prev_hash}
             for r in steps]
    asked_hash = next((t['data'].get('basis_sha256') for t in trail if t['status'] == 'requested'), None)
    check = audit_chain.verify(chain_name)
    body = {
        'request': {**_request_json(req, ctx), 'arguments': req.arguments},
        'basis': req.record, 'basis_sha256': actions.basis_hash(req.record),
        'basis_matches_trail': bool(asked_hash) and asked_hash == actions.basis_hash(req.record),
        'trail': trail,
        'chain': {'verifies': check['ok'], 'records_checked': check['records'], 'problems': check['problems'],
                  'newest_hash': check['heads'].get(chain_name, '')},
        'generated_at': timezone.now(),
        'note': 'The trail is tamper-evident, not tamper-proof: it shows if a record was changed or removed, and relies on the newest hash being kept outside the database.',
    }
    if request.query_params.get('download'):
        resp = HttpResponse(json.dumps(body, default=str, indent=2, ensure_ascii=False), content_type='application/json')
        resp['Content-Disposition'] = f'attachment; filename="decision-record-{req.id}.json"'
        return resp
    return Response(body)


@api_view(['POST'])
@permission_classes([HasAIRole])
def approval_approve(request, pk):
    return _decide(request, pk, 'approve')


@api_view(['POST'])
@permission_classes([HasAIRole])
def approval_reject(request, pk):
    return _decide(request, pk, 'reject')


# --- the school's documents -------------------------------------------------------------------------------------------------

def _doc_json(d: KnowledgeDocument, full=False) -> dict:
    out = {'id': str(d.id), 'title': d.title, 'audience': d.audience, 'is_active': d.is_active, 'passages': d.chunks.count(),
           'characters': len(d.body), 'updated_at': d.updated_at}
    if full:
        out['body'] = d.body
    return out


def _clean(data, doc=None):
    """Validated fields from a request body, or an error message."""
    fields = {}
    if 'title' in data or doc is None:
        title = str(data.get('title', '')).strip()
        if not title:
            return None, 'A title is needed.'
        fields['title'] = title[:MAX_TITLE]
    if 'body' in data or doc is None:
        body = str(data.get('body', '')).strip()
        if len(body) < 20:
            return None, 'The document needs some text (at least a sentence).'
        if len(body) > knowledge.MAX_DOCUMENT_CHARS:
            return None, f'The document is too long ({knowledge.MAX_DOCUMENT_CHARS:,} characters at most). Split it into parts.'
        fields['body'] = body
    if 'audience' in data:
        if data['audience'] not in knowledge.AUDIENCE_ROLES:
            return None, 'Audience must be everyone, staff or admin.'
        fields['audience'] = data['audience']
    if 'is_active' in data:
        fields['is_active'] = bool(data['is_active'])
    return fields, None


@api_view(['GET', 'POST'])
@permission_classes([IsAIAdmin])
def knowledge_list(request):
    ctx = AIContext.from_request(request)
    if request.method == 'GET':
        return Response([_doc_json(d) for d in KnowledgeDocument.all_objects.filter(tenant=ctx.tenant)])
    fields, error = _clean(request.data if isinstance(request.data, dict) else {})
    if error:
        return _err(error)
    doc = KnowledgeDocument.all_objects.create(tenant=ctx.tenant, created_by=request.user, **fields)
    knowledge.index_document(doc)
    audit_write(request, 'CREATE', 'ai.knowledge', doc.id, {'title': doc.title, 'audience': doc.audience})
    return Response(_doc_json(doc, full=True), status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAIAdmin])
def knowledge_detail(request, pk):
    ctx = AIContext.from_request(request)
    doc = KnowledgeDocument.all_objects.filter(pk=pk, tenant=ctx.tenant).first()
    if doc is None:
        return _err('Document not found.', 404)
    if request.method == 'DELETE':
        audit_write(request, 'DELETE', 'ai.knowledge', doc.id, {'title': doc.title})
        doc.delete()
        return Response(status=204)
    if request.method == 'PATCH':
        fields, error = _clean(request.data if isinstance(request.data, dict) else {}, doc)
        if error:
            return _err(error)
        for key, value in fields.items():
            setattr(doc, key, value)
        doc.save()
        if 'body' in fields:
            knowledge.index_document(doc)
        audit_write(request, 'UPDATE', 'ai.knowledge', doc.id, {'title': doc.title, 'fields': sorted(fields)})
    return Response(_doc_json(doc, full=True))


@api_view(['POST'])
@permission_classes([IsAIAdmin])
def knowledge_search(request):
    ctx = AIContext.from_request(request)
    data = request.data if isinstance(request.data, dict) else {}
    role = data.get('as_role') if data.get('as_role') in knowledge.AUDIENCE_ROLES['everyone'] else ctx.role
    return Response({'as_role': role, 'passages': knowledge.search(str(data.get('query', ''))[:500], role=role, tenant=ctx.tenant)})
