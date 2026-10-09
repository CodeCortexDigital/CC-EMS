"""The school's AI settings: which AI features are on, what they cost this month, and the school's AI use notice.

Administrators only. Switching a feature off here turns it off for this school only (it writes a per-school feature
flag, which every AI endpoint already checks). The notice is the school's own acknowledgement of how AI is used; new
AI features that send student information to a provider require it (see ``notice_accepted``).
"""
from __future__ import annotations

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from services.core.features.models import FeatureFlag
from services.core.tenants.context import use_tenant

from .context import AIContext
from .llm import get_llm_client
from .models import AIUsage
from .permissions import IsAIAdmin
from .quota import feature_enabled

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


def notice_accepted(school) -> bool:
    """True when this school has accepted the current AI use notice."""
    saved = ((getattr(school, 'settings_json', None) or {}).get('ai_notice') or {}) if school else {}
    return int(saved.get('version') or 0) >= NOTICE_VERSION


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
        'contact_details_shared': bool(getattr(settings, 'AI_SHARE_CONTACT_INFO', False)),
        'features': [{'key': k, 'label': label, 'description': text, 'enabled': feature_enabled(k, ctx)} for k, label, text in FEATURES],
        'usage': _usage(school),
        'notice': {'version': NOTICE_VERSION, 'text': NOTICE_TEXT, 'accepted': notice_accepted(school),
                   'accepted_at': saved.get('accepted_at'), 'accepted_by': saved.get('accepted_by')},
    }


@api_view(['GET', 'PUT'])
@permission_classes([IsAIAdmin])
def ai_settings(request):
    """GET: the settings. PUT {features: {ai_translation: false, ...}}: switch features on or off for this school."""
    if request.method == 'PUT':
        ctx = AIContext.from_request(request)
        wanted = request.data.get('features')
        if not isinstance(wanted, dict) or not wanted:
            return Response({'error': 'Say which features to change.'}, status=status.HTTP_400_BAD_REQUEST)
        unknown = [k for k in wanted if k not in FEATURE_KEYS]
        if unknown:
            return Response({'error': f'Unknown feature: {unknown[0]}'}, status=status.HTTP_400_BAD_REQUEST)
        if ctx.tenant is None:
            return Response({'error': 'No school selected.'}, status=status.HTTP_400_BAD_REQUEST)
        for key, on in wanted.items():
            FeatureFlag.objects.update_or_create(name=key, tenant=ctx.tenant, defaults={
                'is_enabled': bool(on), 'rollout_percentage': 100, 'description': 'Set from AI settings'})
    return Response(_payload(request))


@api_view(['POST'])
@permission_classes([IsAIAdmin])
def accept_notice(request):
    """The administrator accepts the AI use notice for this school."""
    from services.core.tenants.models import School

    ctx = AIContext.from_request(request)
    if ctx.tenant is None:
        return Response({'error': 'No school selected.'}, status=status.HTTP_400_BAD_REQUEST)
    with use_tenant(None):
        fresh = School.objects.get(pk=ctx.tenant.pk)
        fresh.settings_json = {**(fresh.settings_json or {}), 'ai_notice': {
            'version': NOTICE_VERSION, 'accepted_at': timezone.now().isoformat(), 'accepted_by': request.user.email}}
        fresh.save(update_fields=['settings_json'])
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
