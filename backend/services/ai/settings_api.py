"""The school's AI settings: which AI features are on, what they cost this month, and the school's AI use notice.

Administrators only. Switching a feature off here turns it off for this school only (it writes a per-school feature
flag, which every AI endpoint already checks). The notice is the school's own acknowledgement of how AI is used; new
AI features that send student information to a provider require it (see ``notice_accepted``).
"""
from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from services.core.audit import chain as audit_chain
from services.core.features.models import FeatureFlag
from services.core.tenants.context import use_tenant

from .context import AIContext
from .llm import get_llm_client
from .models import AIUsage
from .permissions import IsAIAdmin
from .quota import MASTER_FLAG, OPT_IN_FEATURES, ai_enabled, feature_enabled

# key (the name every AI endpoint checks), label, what it does
FEATURES = [
    ('ai_chat', 'Assistant chat', 'Answers questions about school data for each person, within their role.'),
    ('ai_lesson_plans', 'Lesson plans', 'Teachers draft lesson plans.'),
    ('ai_quiz', 'Quizzes', 'Teachers draft quizzes.'),
    ('ai_parent_message', 'Parent message drafts', 'Teachers draft a message to a family and edit it before sending.'),
    ('ai_rubric', 'Rubrics', 'Teachers draft a scoring rubric for an assignment.'),
    ('ai_daily_brief', 'Daily briefs', 'Writes the short read at the top of the morning brief and evening summary (counts only; an administrator approves it).'),
    ('ai_narrative', 'Report summaries', 'Writes a short plain-language read of the school figures for administrators.'),
    ('ai_report_comments', 'Report card comments', 'Drafts a comment for a teacher to edit.'),
    ('ai_homework_help', 'Homework hints', 'Students get hints, not answers.'),
    ('ai_admission_screening', 'Admission screening', 'Compares an application with the school\'s criteria. A person decides.'),
    ('ai_behaviour_pattern', 'Behaviour patterns', 'Explains a pattern in behaviour records for staff.'),
    ('ai_message_summary', 'Message summaries', 'Summarises long messages and announcements.'),
    ('ai_translation', 'Translation', 'Translates messages and announcements for families.'),
    ('ai_timetable', 'Timetable suggestions', 'Suggests timetable changes.'),
    ('ai_face_attendance', 'Face-recognition attendance', 'Off until you turn it on. A face is biometric data, and several US states restrict it for students, so it is not offered to US schools by default.'),
    ('ai_risk_scan', 'Student risk scoring', 'Scores students for attendance, marks and fee risk, and lists attendance anomalies. Advice for staff; a person reviews every flag.'),
]
FEATURE_KEYS = {k for k, _, _ in FEATURES}

NOTICE_VERSION = 1
NOTICE_TEXT = (
    'AI features send the text a person types, and short summaries of school records, to an AI provider to produce a '
    'draft. Phone numbers, email addresses and home addresses are masked first. Everything the AI writes is a draft: a '
    'member of staff must read it before it is shared, and the AI never decides grades, admissions or discipline. '
    'The school is responsible for choosing a provider whose terms meet its own and its district\'s privacy requirements, '
    'and for telling families that AI is used.'
)


def _own_flag(key, ctx) -> bool:
    """The school's own setting for one switch, whether or not the master switch is on."""
    from services.core.features.services import evaluate_flag, get_flag_record

    flag = get_flag_record(key, tenant=ctx.tenant)
    if flag is None:
        return key not in OPT_IN_FEATURES
    return evaluate_flag(flag, tenant=ctx.tenant, user=ctx.user)


def _approval_candidates(school) -> list[dict]:
    """People at this school who could be named as approvers: administrators and accountants who are active members."""
    from services.core.accounts.decorators import get_user_role
    from services.core.tenants.models import TenantMembership

    seen, out = set(), []
    for m in TenantMembership.objects.filter(school=school, is_active=True).select_related('user'):
        u = m.user
        role = get_user_role(u)
        if u.pk in seen or not u.is_active or role not in ('admin', 'accountant'):
            continue
        seen.add(u.pk)
        out.append({'id': str(u.pk), 'name': getattr(u, 'full_name', '') or u.email, 'email': u.email, 'role': role})
    return sorted(out, key=lambda c: c['name'].lower())


def _approval_payload(school) -> dict:
    from .actions import approval_policy

    pol = approval_policy(school)
    return {'required': pol['required'], 'approvers': pol['approvers'], 'candidates': _approval_candidates(school) if school else []}


def notice_accepted(school) -> bool:
    """True when this school has accepted the current AI use notice."""
    saved = ((getattr(school, 'settings_json', None) or {}).get('ai_notice') or {}) if school else {}
    return int(saved.get('version') or 0) >= NOTICE_VERSION


def training_confirmation(school) -> dict:
    """The school's record of the AI provider's written confirmation that inputs are not used to train its models
    (MEXT generative-AI guidelines). Empty when none has been recorded."""
    return dict(((getattr(school, 'settings_json', None) or {}).get('ai_training_confirmation') or {})) if school else {}


def _training_payload(school, client) -> dict:
    saved = training_confirmation(school)
    in_use = (getattr(client, 'provider', '') or '').lower() if client else ''
    named = str(saved.get('provider') or '').lower()
    return {'confirmed': bool(saved), 'provider': saved.get('provider', ''), 'confirmed_by': saved.get('confirmed_by', ''),
            'confirmed_on': saved.get('confirmed_on', ''), 'reference': saved.get('reference', ''),
            'recorded_by': saved.get('recorded_by', ''), 'recorded_at': saved.get('recorded_at'),
            # A confirmation for one provider says nothing about another: tell the school when the server uses a different one.
            'provider_mismatch': bool(saved and in_use and named and in_use not in named and named not in in_use)}


def _usage(school):
    start = timezone.localdate().replace(day=1)
    rows = AIUsage.objects.filter(tenant=school, date__gte=start)
    totals = rows.aggregate(requests=Sum('requests'), tokens_in=Sum('input_tokens'), tokens_out=Sum('output_tokens'))
    by_feature = {r['feature']: r for r in rows.values('feature').annotate(requests=Sum('requests'), tokens=Sum('input_tokens') + Sum('output_tokens'))}
    labels = {k: label for k, label, _ in FEATURES}
    return {
        'since': start.isoformat(),
        'requests': totals['requests'] or 0, 'input_tokens': totals['tokens_in'] or 0, 'output_tokens': totals['tokens_out'] or 0,
        'monthly_token_cap': getattr(settings, 'AI_TENANT_MONTHLY_TOKENS', 0),
        'by_feature': sorted(({'feature': k, 'label': labels.get(k, k), 'requests': v['requests'] or 0, 'tokens': v['tokens'] or 0}
                              for k, v in by_feature.items()), key=lambda r: -r['requests']),
    }


def _payload(request):
    ctx = AIContext.from_request(request)
    school = ctx.tenant
    client = get_llm_client()
    saved = ((getattr(school, 'settings_json', None) or {}).get('ai_notice') or {}) if school else {}
    return {
        'provider': {'configured': client is not None, 'name': getattr(client, 'provider', '') if client else '',
                     'note': '' if client else 'No AI provider is set up on the server, so features use built-in templates and say so.'},
        'ai_enabled': ai_enabled(ctx),
        'contact_details_shared': bool(getattr(settings, 'AI_SHARE_CONTACT_INFO', False)),
        'features': [{'key': k, 'label': label, 'description': text, 'enabled': _own_flag(k, ctx)} for k, label, text in FEATURES],
        'usage': _usage(school),
        'approval': _approval_payload(school),
        'notice': {'version': NOTICE_VERSION, 'text': NOTICE_TEXT, 'accepted': notice_accepted(school),
                   'accepted_at': saved.get('accepted_at'), 'accepted_by': saved.get('accepted_by')},
        'training': _training_payload(school, client),
        'always_masked': ['Government ID numbers (US SSN style)', 'Birth dates', 'Health details', 'Passwords and tokens'],
    }


def _validate_approval(school, approval) -> str | None:
    if school is None:
        return 'No school selected.'
    if not isinstance(approval, dict):
        return 'Say how many approvals are needed and who may approve.'
    required = approval.get('required', 1)
    if required not in (1, 2):
        return 'One or two approvals can be required.'
    ids = [str(x) for x in (approval.get('approvers') or [])]
    candidates = {c['id']: c for c in _approval_candidates(school)}
    if any(i not in candidates for i in ids):
        return 'Only active administrators and accountants of this school can be named as approvers.'
    pool = len(ids) if ids else sum(1 for c in candidates.values() if c['role'] == 'admin')
    if required == 2 and pool < 2:
        return 'Two approvals need at least two people who can approve. Name more people, or add another administrator.'
    return None


def _save_approval(ctx, user, approval) -> None:
    """Store the school's approval rule and record the change (inside the caller's transaction)."""
    from services.core.tenants.models import School

    from .actions import approval_policy

    was = approval_policy(ctx.tenant)
    now = {'required': approval.get('required', 1), 'approvers': [str(x) for x in (approval.get('approvers') or [])]}
    with use_tenant(None):
        fresh = School.objects.select_for_update().get(pk=ctx.tenant.pk)
        fresh.settings_json = {**(fresh.settings_json or {}), 'ai_approval': now}
        fresh.save(update_fields=['settings_json'])
    ctx.tenant.settings_json = fresh.settings_json
    audit_chain.append(user=user, school=ctx.tenant, action='UPDATE', resource_type='ai.settings.approval',
                       new_data={'was': was, 'now': now})


@api_view(['GET', 'PUT'])
@permission_classes([IsAIAdmin])
def ai_settings(request):
    """GET: the settings. PUT {features: {ai_translation: false, ...}}: switch features on or off for this school."""
    if request.method == 'PUT':
        ctx = AIContext.from_request(request)
        data = request.data if isinstance(request.data, dict) else {}
        wanted = data.get('features')
        master = data.get('ai_enabled')
        approval = data.get('approval')
        if wanted is not None and (not isinstance(wanted, dict) or not wanted):
            return Response({'error': 'Say which features to change.'}, status=status.HTTP_400_BAD_REQUEST)
        if wanted is None and master is None and approval is None:
            return Response({'error': 'Say which features to change.'}, status=status.HTTP_400_BAD_REQUEST)
        if approval is not None:
            problem = _validate_approval(ctx.tenant, approval)
            if problem:
                return Response({'error': problem}, status=status.HTTP_400_BAD_REQUEST)
        unknown = [k for k in (wanted or {}) if k not in FEATURE_KEYS]
        if unknown:
            return Response({'error': f'Unknown feature: {unknown[0]}'}, status=status.HTTP_400_BAD_REQUEST)
        if ctx.tenant is None:
            return Response({'error': 'No school selected.'}, status=status.HTTP_400_BAD_REQUEST)
        changes = dict(wanted or {})
        if master is not None:
            changes[MASTER_FLAG] = bool(master)
        try:
            # Each change and its record are saved together. A change that cannot be recorded is not made.
            with transaction.atomic():
                if approval is not None:
                    _save_approval(ctx, request.user, approval)
                for key, on in changes.items():
                    was = _own_flag(key, ctx)
                    FeatureFlag.objects.update_or_create(name=key, tenant=ctx.tenant, defaults={
                        'is_enabled': bool(on), 'rollout_percentage': 100, 'description': 'Set from AI settings'})
                    audit_chain.append(user=request.user, school=ctx.tenant, action='UPDATE',
                                       resource_type='ai.settings.master' if key == MASTER_FLAG else 'ai.settings.feature',
                                       resource_id=None, new_data={'feature': key, 'was_on': bool(was), 'now_on': bool(on)})
        except audit_chain.AuditWriteError:
            return Response({'error': 'The change could not be recorded, so it was not made. Try again.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(_payload(request))


@api_view(['POST'])
@permission_classes([IsAIAdmin])
def accept_notice(request):
    """The administrator accepts the AI use notice for this school."""
    from services.core.tenants.models import School

    ctx = AIContext.from_request(request)
    if ctx.tenant is None:
        return Response({'error': 'No school selected.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        with transaction.atomic(), use_tenant(None):
            fresh = School.objects.get(pk=ctx.tenant.pk)
            fresh.settings_json = {**(fresh.settings_json or {}), 'ai_notice': {
                'version': NOTICE_VERSION, 'accepted_at': timezone.now().isoformat(), 'accepted_by': request.user.email}}
            fresh.save(update_fields=['settings_json'])
            audit_chain.append(user=request.user, school=ctx.tenant, action='UPDATE', resource_type='ai.settings.notice',
                               new_data={'notice_version': NOTICE_VERSION})
    except audit_chain.AuditWriteError:
        return Response({'error': 'The acceptance could not be recorded, so it was not saved. Try again.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    ctx.tenant.settings_json = fresh.settings_json
    return Response(_payload(request))


@api_view(['POST', 'DELETE'])
@permission_classes([IsAIAdmin])
def set_training_confirmation(request):
    """POST {provider, confirmed_by, confirmed_on, reference}: record the provider's written confirmation that inputs are not used for
    model training. DELETE: remove it. The change is recorded in the audit chain."""
    from services.core.tenants.models import School

    ctx = AIContext.from_request(request)
    if ctx.tenant is None:
        return Response({'error': 'No school selected.'}, status=status.HTTP_400_BAD_REQUEST)
    record = None
    if request.method == 'POST':
        d = request.data if isinstance(request.data, dict) else {}
        provider = str(d.get('provider') or '').strip()
        on = str(d.get('confirmed_on') or '').strip()
        if not provider:
            return Response({'error': 'Say which AI provider gave the confirmation.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from datetime import date as _date

            _date.fromisoformat(on)
        except ValueError:
            return Response({'error': 'Give the date of the confirmation (YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)
        record = {'provider': provider[:80], 'confirmed_by': str(d.get('confirmed_by') or '').strip()[:120], 'confirmed_on': on,
                  'reference': str(d.get('reference') or '').strip()[:300], 'recorded_by': request.user.email, 'recorded_at': timezone.now().isoformat()}
    try:
        with transaction.atomic(), use_tenant(None):
            fresh = School.objects.select_for_update().get(pk=ctx.tenant.pk)
            was = (fresh.settings_json or {}).get('ai_training_confirmation')
            sj = dict(fresh.settings_json or {})
            if record:
                sj['ai_training_confirmation'] = record
            else:
                sj.pop('ai_training_confirmation', None)
            fresh.settings_json = sj
            fresh.save(update_fields=['settings_json'])
            audit_chain.append(user=request.user, school=ctx.tenant, action='UPDATE', resource_type='ai.settings.training_confirmation',
                               new_data={'was': was, 'now': record})
    except audit_chain.AuditWriteError:
        return Response({'error': 'The change could not be recorded, so it was not saved. Try again.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    ctx.tenant.settings_json = fresh.settings_json
    return Response(_payload(request))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def capabilities(request):
    """What this server can actually do, so screens only offer working features (anyone signed in)."""
    from services.analytics import ai_views

    ctx = AIContext.from_request(request)
    return Response({
        'face_recognition': bool(ai_views.FACE_ML_AVAILABLE and feature_enabled('ai_face_attendance', ctx)),
        'ai_provider': get_llm_client() is not None,
    })
