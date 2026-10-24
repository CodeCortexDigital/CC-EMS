"""Actions the AI assistant may ask for, and the approval step in front of them.

The assistant can only *request* an action. A request is stored as pending (AIActionRequest) and nothing happens until a person
whose role is allowed to approve that action says yes. Only actions registered here can ever run: there is no way for the assistant
to name anything else, and the arguments are checked against the action's own schema.

    ask   (assistant tool ``propose_<action>``)  -> authorised for the asker's role and school, then stored as pending
    decide (approver, in the app)                -> the approver's role, the school and the request's age are checked again,
                                                    and the asker's role is re-checked too, then the action runs once
    audit                                        -> the request, the decision and the result are written to the audit log

Each registered action says who may ask for it, who may approve it, what it needs, how to check a request before it is stored
(``check``) and what to do when it is approved (``run``).
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Callable

from django.db import transaction
from django.utils import timezone

from services.core.accounts.decorators import get_user_role
from services.core.audit.models import AuditLog

from .context import AIContext
from .models import AIActionRequest

logger = logging.getLogger('erp.ai')

REQUEST_LIFETIME = datetime.timedelta(days=2)
MAX_PENDING_PER_USER = 10


class ActionError(Exception):
    """A problem to show the user in plain words."""


@dataclass
class ActionSpec:
    name: str
    label: str
    description: str                       # what the assistant is told it does
    request_roles: tuple[str, ...]         # who may ask for it
    approver_roles: tuple[str, ...]        # who may approve it
    properties: dict
    required: tuple[str, ...]
    check: Callable                        # (ctx, args) -> (summary, cleaned_args); raises ActionError
    run: Callable                          # (ctx_of_requester, args, approver) -> result dict; raises ActionError


ACTIONS: dict[str, ActionSpec] = {}


def register(spec: ActionSpec) -> ActionSpec:
    ACTIONS[spec.name] = spec
    return spec


def _audit(user, tenant, name, request_id, status, data=None, action='UPDATE'):
    try:
        AuditLog.objects.create(user=user, school=tenant, action=action, resource_type=f'ai.action.{name}', resource_id=request_id,
                                new_data={'status': status, **(data or {})})
    except Exception:
        logger.exception('Failed to audit AI action %s', name)


def propose(ctx: AIContext, name: str, arguments: dict) -> dict:
    """Store a request for approval. Returns what the assistant is told (it never sees a 'done')."""
    spec = ACTIONS.get(name)
    if spec is None or ctx.role not in spec.request_roles:
        _audit(ctx.user, ctx.tenant, name, None, 'denied', action='PERMISSION_DENIED')
        return {'error': 'This action is not available for your role.'}
    waiting = AIActionRequest.all_objects.filter(tenant=ctx.tenant, requested_by=ctx.user, status='pending').count()
    if waiting >= MAX_PENDING_PER_USER:
        return {'error': 'There are already several requests waiting for approval. Ask for those to be reviewed first.'}
    try:
        summary, cleaned = spec.check(ctx, arguments)
    except ActionError as exc:
        return {'error': str(exc)}
    req = AIActionRequest.all_objects.create(
        tenant=ctx.tenant, action=name, summary=summary[:300], arguments=cleaned, requested_by=ctx.user, requester_role=ctx.role or '',
        conversation_id=ctx.extra.get('conversation_id'), expires_at=timezone.now() + REQUEST_LIFETIME)
    _audit(ctx.user, ctx.tenant, name, req.id, 'requested', {'arguments': cleaned})
    return {'status': 'pending_approval', 'request_id': str(req.id), 'summary': summary,
            'message': 'This has been sent for approval. Nothing has been done yet. Tell the user it is waiting for '
                       + ' or '.join(spec.approver_roles) + ' approval.'}


def can_decide(user_role, req: AIActionRequest) -> bool:
    spec = ACTIONS.get(req.action)
    return bool(spec and user_role in spec.approver_roles)


def _expire_if_due(req: AIActionRequest, tenant) -> None:
    """A request that waited too long is closed, and stays closed (this is saved before the error is raised)."""
    if AIActionRequest.all_objects.filter(pk=req.pk, tenant=tenant, status='pending', expires_at__lte=timezone.now()).update(status='expired'):
        raise ActionError('This request has expired. Ask for it again.')


def reject(req: AIActionRequest, user, role, tenant, note: str = '') -> AIActionRequest:
    _expire_if_due(req, tenant)
    with transaction.atomic():
        req = _lock(req, tenant)
        _require_decidable(req, role)
        req.status, req.decided_by, req.decided_at, req.decision_note = 'rejected', user, timezone.now(), (note or '')[:500]
        req.save(update_fields=['status', 'decided_by', 'decided_at', 'decision_note'])
    _audit(user, tenant, req.action, req.id, 'rejected', {'note': req.decision_note})
    return req


def approve(req: AIActionRequest, user, role, tenant, note: str = '') -> AIActionRequest:
    """Approve and run once. The asker's own permission is checked again, because their role may have changed since."""
    _expire_if_due(req, tenant)
    with transaction.atomic():
        req = _lock(req, tenant)
        _require_decidable(req, role)
        spec = ACTIONS[req.action]
        requester = req.requested_by
        requester_role = get_user_role(requester)
        req.decided_by, req.decided_at, req.decision_note = user, timezone.now(), (note or '')[:500]
        if not requester.is_active or requester_role not in spec.request_roles:
            req.status, req.result = 'failed', {'error': 'The person who asked no longer has permission for this action, so it was not run.'}
        else:
            ctx = AIContext(user=requester, role=requester_role, tenant=tenant)
            try:
                _, cleaned = spec.check(ctx, req.arguments)           # the same checks as when it was asked, against today's data
                req.result = spec.run(ctx, cleaned, user) or {}
                req.status = 'executed'
            except ActionError as exc:
                req.status, req.result = 'failed', {'error': str(exc)}
            except Exception:
                logger.exception('AI action %s failed', req.action)
                req.status, req.result = 'failed', {'error': 'The action could not be completed.'}
        req.save(update_fields=['status', 'decided_by', 'decided_at', 'decision_note', 'result'])
    _audit(user, tenant, req.action, req.id, req.status, {'result': req.result, 'asked_by': str(req.requested_by_id)})
    return req


def _lock(req, tenant) -> AIActionRequest:
    return AIActionRequest.all_objects.select_for_update().get(pk=req.pk, tenant=tenant)     # another school's request is not found


def _require_decidable(req: AIActionRequest, role) -> None:
    if req.status != 'pending':
        raise ActionError('This request has already been decided.')
    if not can_decide(role, req):
        raise PermissionError('Your role cannot decide this request.')


# ---------------------------------------------------------------------------
# The registered actions
# ---------------------------------------------------------------------------

def _student_in_scope(ctx: AIContext, key: str):
    from services.education.students.models import Student

    qs = Student.all_objects.filter(tenant=ctx.tenant)
    if ctx.role == 'teacher':
        qs = qs.filter(current_class_id__in=ctx.teacher_class_ids)
    student = qs.filter(student_id__iexact=(key or '').strip()).select_related('current_class').first()
    if student is None:
        raise ActionError('No student with that ID was found among the students you can see.')
    return student


def _invoice_in_school(ctx, number):
    from services.education.finance.models import Invoice

    return Invoice._base_manager.filter(student__tenant=ctx.tenant, invoice_number__iexact=str(number).strip()).select_related('student').first()


def _check_fee_reminder(ctx, args):
    inv = _invoice_in_school(ctx, args.get('invoice_number', ''))
    if inv is None:
        raise ActionError('No invoice with that number was found.')
    if (inv.balance_due or 0) <= 0:
        raise ActionError(f'Invoice {inv.invoice_number} has nothing left to pay, so no reminder is needed.')
    return f'Send a fee reminder for invoice {inv.invoice_number} ({inv.student.full_name}) to the family', {'invoice_number': inv.invoice_number}


def _run_fee_reminder(ctx, args, approver):
    from services.education.communication import texts

    inv = _invoice_in_school(ctx, args['invoice_number'])
    if inv is None:
        raise ActionError('The invoice no longer exists.')
    sent = texts.fee_reminder(inv)
    if not sent:
        return {'sent': 0, 'note': 'No text was sent: text messaging is not set up for this school, or fee reminders are switched off.'}
    return {'sent': len(sent), 'note': f'{len(sent)} message(s) queued to the family.'}


def _check_support_case(ctx, args):
    student = _student_in_scope(ctx, args.get('student_id'))
    title = str(args.get('title', '')).strip()[:200]
    if not title:
        raise ActionError('A short title is needed for the support case.')
    priority = 'high' if args.get('priority') == 'high' else 'normal'
    return (f'Open a support case for {student.full_name}: {title}',
            {'student_id': student.student_id, 'title': title, 'description': str(args.get('description', '')).strip()[:2000], 'priority': priority})


def _run_support_case(ctx, args, approver):
    from services.education.interventions.models import Intervention

    student = _student_in_scope(ctx, args['student_id'])
    case = Intervention.all_objects.create(
        tenant=ctx.tenant, student=student, source='manual', title=args['title'], description=args.get('description', ''),
        priority=args.get('priority', 'normal'), created_by=approver)
    return {'case_id': str(case.id), 'note': f'Support case opened for {student.full_name}.'}


register(ActionSpec(
    name='send_fee_reminder', label='Send a fee reminder',
    description='Ask to send a fee reminder text to the family for ONE unpaid invoice. It is only a request: an administrator must approve it before anything is sent.',
    request_roles=('admin', 'accountant'), approver_roles=('admin',),
    properties={'invoice_number': {'type': 'string', 'description': 'The invoice number, exactly as shown.'}},
    required=('invoice_number',), check=_check_fee_reminder, run=_run_fee_reminder))

register(ActionSpec(
    name='open_support_case', label='Open a student support case',
    description='Ask to open a support case (a follow-up to-do) for one student. It is only a request: an administrator must approve it first.',
    request_roles=('admin', 'teacher'), approver_roles=('admin',),
    properties={'student_id': {'type': 'string', 'description': "The student's ID."},
                'title': {'type': 'string', 'description': 'A short title.'},
                'description': {'type': 'string', 'description': 'What was noticed and why. Facts only.'},
                'priority': {'type': 'string', 'description': "'normal' or 'high'."}},
    required=('student_id', 'title'), check=_check_support_case, run=_run_support_case))
