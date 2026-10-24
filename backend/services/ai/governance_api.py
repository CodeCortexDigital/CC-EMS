"""Approvals and school documents for the AI assistant (``/api/v1/ai/governance/``).

    GET  actions/                     the actions the assistant can ask for, and who may ask and approve
    GET  approvals/?status=           requests waiting (default), or all. Approvers see the whole school's; others see their own
    POST approvals/<id>/approve/      {note?}  approve and run it (approver roles only)
    POST approvals/<id>/reject/       {note?}  reject it (approver roles only)
    GET/POST knowledge/               the school's documents the assistant may quote (administrators)
    GET/PATCH/DELETE knowledge/<id>/  one document, with its text
    POST knowledge/search/            {query}  what the assistant would find for a question, as each role would see it
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from services.education.students.access import audit_write

from . import actions, knowledge
from .context import AIContext
from .models import AIActionRequest, KnowledgeDocument
from .permissions import HasAIRole, IsAIAdmin

MAX_TITLE = 200


def _err(message, code=400):
    return Response({'error': message}, status=code)


def _person(user):
    return (getattr(user, 'full_name', '') or user.email) if user else ''


def _request_json(r: AIActionRequest, role) -> dict:
    spec = actions.ACTIONS.get(r.action)
    return {
        'id': str(r.id), 'action': r.action, 'label': spec.label if spec else r.action, 'summary': r.summary, 'status': r.status,
        'requested_by': _person(r.requested_by), 'requester_role': r.requester_role, 'created_at': r.created_at, 'expires_at': r.expires_at,
        'decided_by': _person(r.decided_by), 'decided_at': r.decided_at, 'decision_note': r.decision_note, 'result': r.result,
        'approver_roles': list(spec.approver_roles) if spec else [], 'can_decide': r.status == 'pending' and actions.can_decide(role, r),
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
    if not any(ctx.role in s.approver_roles for s in actions.ACTIONS.values()):
        rows = rows.filter(requested_by=request.user)               # only approvers see other people's requests
    if request.query_params.get('status', 'pending') != 'all':
        rows = rows.filter(status='pending')
    return Response([_request_json(r, ctx.role) for r in rows[:100]])


def _decide(request, pk, verb):
    ctx = AIContext.from_request(request)
    req = AIActionRequest.all_objects.filter(pk=pk, tenant=ctx.tenant).first()
    if req is None:
        return _err('Request not found.', 404)
    if not actions.can_decide(ctx.role, req):
        return _err('Your role cannot decide this request.', 403)
    note = request.data.get('note', '') if isinstance(request.data, dict) else ''
    try:
        done = (actions.approve if verb == 'approve' else actions.reject)(req, request.user, ctx.role, ctx.tenant, str(note or ''))
    except actions.ActionError as exc:
        return _err(str(exc), 409)
    except PermissionError as exc:
        return _err(str(exc), 403)
    done = AIActionRequest.all_objects.select_related('requested_by', 'decided_by').get(pk=done.pk)
    return Response(_request_json(done, ctx.role))


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
