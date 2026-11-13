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
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Callable

from django.db import transaction
from django.utils import timezone

from services.core.accounts.decorators import get_user_role
from services.core.audit import chain as audit_chain
from services.core.audit.models import AuditLog

from .context import AIContext
from .models import AIActionEffect, AIActionRequest

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
    """Write the decision record. Not optional: if it cannot be saved this raises, and (called inside the transaction of what it
    records) the request, decision or action does not go ahead."""
    audit_chain.append(user=user, school=tenant, action=action, resource_type=f'ai.action.{name}', resource_id=request_id,
                       new_data={'status': status, **(data or {})})


def build_record(ctx: AIContext) -> dict:
    """What this request is based on, for the decision record: who answered (provider, model), a fingerprint of the instructions the
    model was given, what the person asked, what data was sent to the model (after masking), the sources used and the controls on."""
    from django.conf import settings

    from .controls import controls, user_accepted
    from .quota import feature_enabled
    from .settings_api import NOTICE_VERSION, notice_accepted

    extra = ctx.extra or {}
    return {
        'provider': extra.get('llm_provider', ''), 'model': extra.get('llm_model', ''),
        'instructions_sha256': extra.get('instructions_sha256', ''),
        'asked': str(extra.get('user_message') or '')[:2000],
        'tool_outputs_sent': extra.get('tool_outputs', []),
        'sources': [{'id': k, 'title': v} for k, v in (extra.get('sources') or {}).items()],
        'controls': {
            'ai_chat_enabled': bool(feature_enabled('ai_chat', ctx)),
            'contact_details_shared': bool(getattr(settings, 'AI_SHARE_CONTACT_INFO', False)),
            'use_notice_version': NOTICE_VERSION, 'use_notice_accepted': bool(notice_accepted(ctx.tenant)),
            'school_controls': controls(ctx.tenant), 'user_notice_accepted': bool(user_accepted(ctx.user, ctx.tenant)),
            'name_masking': extra.get('masking') or {'on': False},
            'rate_limit_per_window': getattr(settings, 'AI_RATE_LIMIT', 0), 'rate_window_seconds': getattr(settings, 'AI_RATE_WINDOW', 0),
            'monthly_token_cap': getattr(settings, 'AI_TENANT_MONTHLY_TOKENS', 0),
            'approvals_required': approval_policy(ctx.tenant)['required'],
            'named_approvers': approval_policy(ctx.tenant)['approvers'],
        },
        'origin': extra.get('origin', 'assistant chat'),
        'recorded_at': timezone.now().isoformat(),
    }


def basis_hash(record: dict) -> str:
    """The fingerprint of a record, as written into the verified trail when the request is made."""
    plain = json.loads(json.dumps(record or {}, default=str, ensure_ascii=False))
    return hashlib.sha256(json.dumps(plain, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def propose(ctx: AIContext, name: str, arguments: dict) -> dict:
    """Store a request for approval. Returns what the assistant is told (it never sees a 'done')."""
    spec = ACTIONS.get(name)
    if spec is None or ctx.role not in spec.request_roles:
        try:
            _audit(ctx.user, ctx.tenant, name, None, 'denied', action='PERMISSION_DENIED')
        except audit_chain.AuditWriteError:
            logger.exception('Could not record a refused AI action %s', name)
        return {'error': 'This action is not available for your role.'}
    waiting = AIActionRequest.all_objects.filter(tenant=ctx.tenant, requested_by=ctx.user, status='pending').count()
    if waiting >= MAX_PENDING_PER_USER:
        return {'error': 'There are already several requests waiting for approval. Ask for those to be reviewed first.'}
    try:
        summary, cleaned = spec.check(ctx, arguments)
    except ActionError as exc:
        return {'error': str(exc)}
    record = build_record(ctx)
    try:
        with transaction.atomic():
            req = AIActionRequest.all_objects.create(
                tenant=ctx.tenant, action=name, summary=summary[:300], arguments=cleaned, requested_by=ctx.user, requester_role=ctx.role or '',
                conversation_id=ctx.extra.get('conversation_id'), record=record, expires_at=timezone.now() + REQUEST_LIFETIME)
            _audit(ctx.user, ctx.tenant, name, req.id, 'requested',
                   {'arguments': cleaned, 'action_sha256': action_digest(name, ctx.tenant, cleaned), 'basis_sha256': basis_hash(record), 'provider': record['provider'], 'model': record['model']})
    except audit_chain.AuditWriteError:
        logger.exception('AI action %s was not stored because its record could not be written', name)
        return {'error': 'The request could not be recorded, so it was not sent for approval. Try again.'}
    return {'status': 'pending_approval', 'request_id': str(req.id), 'summary': summary,
            'message': 'This has been sent for approval. Nothing has been done yet. Tell the user it is waiting for '
                       + ' or '.join(spec.approver_roles) + ' approval.'}


def approval_policy(tenant) -> dict:
    """The school's rule for approving: how many different people must approve (1 or 2), and, if the administrator named them, who may.
    With nobody named, any administrator may approve. The person who asked can never approve their own request."""
    saved = ((getattr(tenant, 'settings_json', None) or {}).get('ai_approval') or {}) if tenant else {}
    return {'required': 1 if int(saved.get('required') or 2) <= 1 else 2, 'approvers': [str(x) for x in (saved.get('approvers') or [])]}


def _eligible(user, role, spec, tenant) -> bool:
    named = approval_policy(tenant)['approvers']
    if role not in spec.approver_roles:
        return False                      # a named person who has since lost the role can no longer approve
    return (str(user.pk) in named) if named else True


def is_approver(user, role, tenant) -> bool:
    """Whether this person may approve requests at all (they then see everyone's requests, not just their own)."""
    return any(_eligible(user, role, spec, tenant) for spec in ACTIONS.values())


def decide_problem(user, role, req: AIActionRequest, tenant, verb: str = 'approve') -> str | None:
    """Why this person cannot approve (or reject) this request now, in plain words, or None when they can."""
    spec = ACTIONS.get(req.action)
    if spec is None:
        return 'This action is no longer available.'
    if req.status != 'pending':
        return 'This request has already been decided.'
    if verb == 'reject' and user.pk == req.requested_by_id:
        return None                                                   # the person who asked may always withdraw it
    if not _eligible(user, role, spec, tenant):
        return 'You are not one of the people who can decide this request.'
    if verb == 'approve':
        if user.pk == req.requested_by_id:
            return 'You asked for this, so someone else has to approve it.'
        if any(a.get('user_id') == str(user.pk) for a in (req.approvals or [])):
            return 'You have already approved this. A different person has to give the other approval.'
    return None


def can_decide(user, role, req: AIActionRequest, tenant) -> bool:
    return decide_problem(user, role, req, tenant, 'approve') is None


def approvals_needed(req: AIActionRequest, tenant) -> int:
    """How many approvals this request needs: what applied when it was asked, or what applies now if that is stricter."""
    recorded = int(((req.record or {}).get('controls') or {}).get('approvals_required') or 1)
    return max(recorded, approval_policy(tenant)['required'])


def _expire_if_due(req: AIActionRequest, tenant) -> None:
    """A request that waited too long is closed, and stays closed (this is saved before the error is raised)."""
    if AIActionRequest.all_objects.filter(pk=req.pk, tenant=tenant, status='pending', expires_at__lte=timezone.now()).update(status='expired'):
        raise ActionError('This request has expired. Ask for it again.')


def reject(req: AIActionRequest, user, role, tenant, note: str = '') -> AIActionRequest:
    _expire_if_due(req, tenant)
    with transaction.atomic():
        req = _lock(req, tenant)
        _require_decidable(user, role, req, tenant, 'reject')
        req.status, req.decided_by, req.decided_at, req.decision_note = 'rejected', user, timezone.now(), (note or '')[:500]
        req.save(update_fields=['status', 'decided_by', 'decided_at', 'decision_note'])
        _audit(user, tenant, req.action, req.id, 'rejected', {'note': req.decision_note})
    return req


def action_digest(name: str, tenant, arguments: dict) -> str:
    """A fingerprint of exactly what is being approved: the action, the school and its (checked) arguments. It is written into the
    verified trail when the request is made, and compared again just before anything runs ("is this still the action that was asked
    for?"). It does not replace the checks against today's data ("is it still allowed now?"); both are made."""
    plain = json.loads(json.dumps({'action': name, 'school': str(getattr(tenant, 'pk', '') or ''), 'arguments': arguments or {}},
                                  default=str, ensure_ascii=False))
    return hashlib.sha256(json.dumps(plain, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def _asked_digest(req: AIActionRequest, tenant) -> str:
    """The digest written into the trail when the request was made ('' for a request made before digests were recorded)."""
    row = AuditLog.objects.filter(chain=str(tenant.pk) if tenant else 'platform', resource_id=req.id,
                                  resource_type=f'ai.action.{req.action}').order_by('seq').first()
    return str(((row.new_data if row else None) or {}).get('action_sha256') or '')


def approve(req: AIActionRequest, user, role, tenant, note: str = '') -> AIActionRequest:
    """Approve and run once.

    Three steps, each saved before the next: (1) the approval is recorded and, on the last one, the intent to run is saved under a key
    that can exist only once; (2) the action runs, outside that transaction, after the same checks as when it was asked, made against
    today's data; (3) the outcome is saved: done, not done, or UNKNOWN when the result cannot be confirmed (then it is not retried
    automatically: asking again is a new decision)."""
    _expire_if_due(req, tenant)
    with transaction.atomic():
        req = _lock(req, tenant)
        _require_decidable(user, role, req, tenant, 'approve')
        spec = ACTIONS[req.action]
        requester = req.requested_by
        requester_role = get_user_role(requester)
        needed = approvals_needed(req, tenant)
        given = list(req.approvals or []) + [{'user_id': str(user.pk), 'name': getattr(user, 'full_name', '') or user.email,
                                               'at': timezone.now().isoformat(), 'note': (note or '')[:500]}]
        # Each approval is recorded before anything runs: if it cannot be saved, nothing is done.
        _audit(user, tenant, req.action, req.id, 'approved',
               {'note': (note or '')[:500], 'step': len(given), 'of': needed, 'asked_by': str(req.requested_by_id)})
        req.approvals = given
        if len(given) < needed:
            req.save(update_fields=['approvals'])                      # waits for the other person; nothing runs yet
            return req
        req.decided_by, req.decided_at, req.decision_note = user, timezone.now(), (note or '')[:500]
        asked = _asked_digest(req, tenant)
        problem = None
        if not requester.is_active or requester_role not in spec.request_roles:
            problem = 'The person who asked no longer has permission for this action, so it was not run.'
        elif asked and asked != action_digest(req.action, tenant, req.arguments):
            problem = 'This request no longer matches what was asked for, so it was not run. Ask for it again.'
        if problem:
            req.status, req.result = 'failed', {'error': problem}
            req.save(update_fields=['status', 'decided_by', 'decided_at', 'decision_note', 'result', 'approvals'])
            _audit(user, tenant, req.action, req.id, 'failed', {'result': req.result, 'asked_by': str(req.requested_by_id)})
            return req
        req.status = 'running'
        req.save(update_fields=['status', 'decided_by', 'decided_at', 'decision_note', 'approvals'])
        # The intent, saved before anything is sent. One row per request: a second attempt cannot create another.
        AIActionEffect.objects.create(request=req, tenant=tenant, effect_key=f'{req.action}:{req.id}', state='dispatching')
        _audit(user, tenant, req.action, req.id, 'running', {'asked_by': str(req.requested_by_id), 'action_sha256': asked})
    return _execute(req, tenant, requester, requester_role, spec, user)


def _execute(req, tenant, requester, requester_role, spec, approver) -> AIActionRequest:
    ctx = AIContext(user=requester, role=requester_role, tenant=tenant)
    try:
        _, cleaned = spec.check(ctx, req.arguments)                    # the same checks as when it was asked, against today's data
        result, state, status = spec.run(ctx, cleaned, approver) or {}, 'confirmed', 'executed'
    except ActionError as exc:
        result, state, status = {'error': str(exc)}, 'not_done', 'failed'
    except Exception:
        logger.exception('AI action %s ended in an unknown state', req.action)
        result, state, status = ({'error': 'We could not confirm whether this was done. Check before asking again: asking again is a new decision.'},
                                 'unknown', 'unknown')
    try:
        with transaction.atomic():
            req = _lock(req, tenant)
            req.status, req.result = status, result
            req.save(update_fields=['status', 'result'])
            AIActionEffect.objects.filter(request=req).update(state=state, detail=result, finished_at=timezone.now())
            _audit(approver, tenant, req.action, req.id, status, {'result': result, 'effect_state': state, 'asked_by': str(req.requested_by_id)})
    except audit_chain.AuditWriteError:
        logger.exception('The outcome of AI action %s could not be recorded; it stays "running" until someone checks', req.action)
    return AIActionRequest.all_objects.get(pk=req.pk)


STALE_RUNNING = datetime.timedelta(minutes=10)


def can_settle(req: AIActionRequest) -> bool:
    """A request whose result could not be confirmed (or one that has been "running" for too long, for example the server stopped)."""
    if req.status == 'unknown':
        return True
    return req.status == 'running' and bool(req.decided_at) and timezone.now() - req.decided_at > STALE_RUNNING


def settle(req: AIActionRequest, user, role, tenant, outcome: str, note: str) -> AIActionRequest:
    """A person checks what really happened (for example looks in the mail log) and records it. This is how an unconfirmed result is
    closed: it is never retried by the system. 'done' = it did happen; 'not_done' = it did not, so a new request may be asked for."""
    if outcome not in ('done', 'not_done'):
        raise ActionError("Say whether it was done or not done.")
    note = (note or '').strip()[:500]
    if not note:
        raise ActionError('Write what you checked, so the record shows how this was settled.')
    with transaction.atomic():
        req = _lock(req, tenant)
        spec = ACTIONS.get(req.action)
        if spec is None or not _eligible(user, role, spec, tenant):
            raise PermissionError('You are not one of the people who can settle this request.')
        if not can_settle(req):
            raise ActionError('This request has no unconfirmed result to settle.')
        done = outcome == 'done'
        req.status = 'executed' if done else 'failed'
        req.result = {**(req.result or {}), 'settled_by_person': True, 'settled_as': outcome, 'settled_note': note,
                      **({'note': 'A person confirmed this was done.'} if done else {'error': 'A person confirmed this was not done.'})}
        req.save(update_fields=['status', 'result'])
        AIActionEffect.objects.filter(request=req).update(state='confirmed' if done else 'not_done', finished_at=timezone.now(),
                                                          detail=req.result)
        _audit(user, tenant, req.action, req.id, 'settled', {'outcome': outcome, 'note': note, 'asked_by': str(req.requested_by_id)})
    return req


def _lock(req, tenant) -> AIActionRequest:
    return AIActionRequest.all_objects.select_for_update().get(pk=req.pk, tenant=tenant)     # another school's request is not found


def _require_decidable(user, role, req: AIActionRequest, tenant, verb: str) -> None:
    problem = decide_problem(user, role, req, tenant, verb)
    if problem == 'This request has already been decided.':
        raise ActionError(problem)
    if problem:
        raise PermissionError(problem)


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
    """Email (and, where the school has it on, text) the family about this invoice. It is the same sender as the fee office's own
    reminder button; the approver is recorded as the person who sent it."""
    from types import SimpleNamespace

    from services.education.finance.views import _send_invoice_reminder

    inv = _invoice_in_school(ctx, args['invoice_number'])
    if inv is None:
        raise ActionError('The invoice no longer exists.')
    try:
        sent = _send_invoice_reminder(SimpleNamespace(tenant=ctx.tenant, user=approver), inv)
    except ValueError as exc:
        if str(exc) != 'no_email':
            raise                                                    # a different problem (for example a mail error): not "no address"
        raise ActionError('No email address or phone number for this family. Add one to a guardian marked "Receives invoices".')
    return {'sent': 1, 'note': sent.get('message') or 'Reminder sent to the family.', 'recipient': sent.get('recipient', '')}


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


def _check_counsel(ctx, args):
    from services.analytics import counsel

    student = _student_in_scope(ctx, args.get('student_id'))
    value = counsel.dropout_risk_of(student)[1]
    if value is None:
        raise ActionError('The risk scan has not scored this student yet.')
    return (f'Tell the counsellors about {student.full_name} ({value:.0f}% dropout-risk finding)', {'student_id': student.student_id})


def _run_counsel(ctx, args, approver):
    from services.analytics import counsel

    student = _student_in_scope(ctx, args['student_id'])
    try:
        out = counsel.notify(student, approver)
    except ValueError:
        raise ActionError('The risk scan has not scored this student yet.')
    return {**out, 'note': f"Counsellors told about {student.full_name} ({out['notified']} people notified)."}


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

register(ActionSpec(
    name='notify_counsel', label='Tell the counsellors about a risk finding',
    description="Ask for the class teachers, administrators and the counsellor queue to be told about one student's dropout-risk finding. It is only a request: an administrator must approve it first.",
    request_roles=('admin', 'teacher'), approver_roles=('admin',),
    properties={'student_id': {'type': 'string', 'description': "The student's ID."}},
    required=('student_id',), check=_check_counsel, run=_run_counsel))
