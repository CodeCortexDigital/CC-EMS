"""Teacher assistant endpoints: draft a message to a family, draft a rubric.

Both return drafts for the teacher to read and edit. Nothing is sent or saved by these calls. The message drafter sends a
student's first name to the AI provider, so it needs the school to have accepted the AI use notice first.
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from services.core.accounts.decorators import ensure_student_access
from services.core.tenants.localization import school_locale
from services.education.students.households import find_student

from .context import AIContext
from .generation import (
    DEFAULT_LEVELS, MESSAGE_KINDS, TONES, generate_parent_message, generate_rubric, parent_message_warnings,
    template_parent_message, template_rubric,
)
from .llm import LLMError, get_llm_client
from .permissions import IsAIEducator
from .quota import AIQuotaExceeded, check_rate_limit, check_token_budget, feature_enabled, record_usage
from .settings_api import notice_accepted

logger = logging.getLogger("erp.ai")


def _ready(request, feature):
    """(ctx, llm) when a real provider can be used, (ctx, None) when the stand-in should be used, or an error Response."""
    ctx = AIContext.from_request(request)
    if not feature_enabled(feature, ctx):
        return None, None, Response({'error': 'This AI feature is turned off for your school.'}, status=status.HTTP_403_FORBIDDEN)
    llm = get_llm_client()
    if llm is None:
        return ctx, None, None
    try:
        check_rate_limit(ctx, feature)
        check_token_budget(ctx)
    except AIQuotaExceeded as exc:
        return None, None, Response({'error': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    return ctx, llm, None


@api_view(['POST'])
@permission_classes([IsAIEducator])
def ai_parent_message(request):
    """{student, template, details, tone} -> {subject, body, source, warnings}"""
    kind = str(request.data.get('template') or 'custom')
    tone = str(request.data.get('tone') or 'warm')
    details = str(request.data.get('details') or '').strip()[:1500]
    if kind not in MESSAGE_KINDS or tone not in TONES:
        return Response({'error': 'Choose a message type and a tone from the lists.'}, status=400)
    if not details:
        return Response({'error': 'Write a few notes about what you want to say.'}, status=400)
    student = find_student(request.data.get('student'))
    if student is None or not ensure_student_access(request.user, student):
        return Response({'error': 'Student not found.'}, status=404)
    ctx, llm, error = _ready(request, 'ai_parent_message')
    if error:
        return error
    first = (student.full_name or 'the student').split()[0]
    teacher = request.user.full_name or request.user.email
    warnings = parent_message_warnings(details)
    if llm is None:  # nothing leaves the school when no provider is set up
        return Response({**template_parent_message(kind=kind, student_first_name=first, teacher_name=teacher, details=details),
                         'warnings': warnings})
    if not notice_accepted(ctx.tenant):
        return Response({'error': 'An administrator needs to accept the AI use notice (Settings, AI Assistant) before this can be used.'}, status=403)
    try:
        out, usage, model = generate_parent_message(llm, kind=kind, student_first_name=first, teacher_name=teacher, details=details,
                                                    tone=tone, region=school_locale(ctx.tenant)['region'])
    except LLMError:
        logger.exception('Parent message draft failed')
        return Response({'error': 'Could not draft the message right now. Please try again.'}, status=502)
    record_usage(ctx, 'ai_parent_message', llm.provider, model, usage)
    return Response({**out, 'source': 'ai', 'warnings': warnings})


@api_view(['POST'])
@permission_classes([IsAIEducator])
def ai_rubric(request):
    """{title, instructions, subject, grade, standards, levels} -> {criteria: [{name, levels: [{label, description}]}], source}"""
    title = str(request.data.get('title') or '').strip()[:200]
    if not title:
        return Response({'error': 'Give the assignment a title first.'}, status=400)
    instructions = str(request.data.get('instructions') or '').strip()[:3000]
    subject = str(request.data.get('subject') or '').strip()[:100]
    grade = str(request.data.get('grade') or '').strip()[:100]
    standards = [str(s).strip()[:300] for s in (request.data.get('standards') or []) if str(s).strip()][:10]
    levels = [str(x).strip()[:40] for x in (request.data.get('levels') or DEFAULT_LEVELS) if str(x).strip()][:5]
    if len(levels) < 2:
        return Response({'error': 'A rubric needs at least two levels.'}, status=400)
    ctx, llm, error = _ready(request, 'ai_rubric')
    if error:
        return error
    if llm is None:
        return Response(template_rubric(title=title, levels=levels))
    try:
        out, usage, model = generate_rubric(llm, title=title, instructions=instructions, subject=subject, grade=grade,
                                            standards=standards, levels=levels, region=school_locale(ctx.tenant)['region'])
    except LLMError:
        logger.exception('Rubric generation failed')
        return Response({'error': 'Could not draft the rubric right now. Please try again.'}, status=502)
    record_usage(ctx, 'ai_rubric', llm.provider, model, usage)
    return Response({**out, 'source': 'ai'})
