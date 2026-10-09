"""Daily briefs API (``/api/v1/auth/briefs/``). Administrators only.

    GET    today/                      this school day's morning brief and evening summary (or none yet), and the settings
    GET    ?kind=morning|evening       the daily briefs still kept (about three months)
    POST   generate/                   {kind, date?} make (or remake) a draft
    GET    <id>/                       one brief, in full
    PATCH  <id>/                       {narrative} edit the words of a draft
    POST   <id>/approve/               {narrative?} approve it; it is then locked
    DELETE <id>/                       delete it
    GET/PUT settings/                  {enabled, morning_time, evening_time}
    GET    rollups/?period=            weekly, fortnightly and monthly roll-ups
    POST   rollups/generate/           {period, end?} build a roll-up from the daily briefs
    GET/PATCH/DELETE rollups/<id>/ and POST rollups/<id>/approve/    the same as for a daily brief
"""
import datetime

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from services.core.accounts.permissions import IsSchoolAdmin
from services.education.students.access import audit_write

from . import service
from . import metrics
from .models import BriefRead, BriefRollup, DailyBrief


def _err(msg, code=400):
    return Response({'error': msg}, status=code)


def _summary(b, read_ids=None):
    out = {'id': str(b.id), 'status': b.status, 'narrative_source': b.narrative_source, 'edited': b.edited,
           'attention_count': len(b.metrics.get('attention', [])), 'approved_at': b.approved_at,
           'approved_by': (b.approved_by.full_name or b.approved_by.email) if b.approved_by_id else '',
           'read_by_me': (b.id in read_ids) if read_ids is not None else False}
    if isinstance(b, DailyBrief):
        out.update({'kind': b.kind, 'date': b.date.isoformat()})
    else:
        out.update({'period': b.period, 'period_start': b.period_start.isoformat(), 'period_end': b.period_end.isoformat(), 'days': b.days})
    return out


def _detail(b, request=None):
    reads = service.readers(b)
    me = str(request.user.pk) if request is not None else None
    kind = b.kind if isinstance(b, DailyBrief) else 'rollup'
    return {**_summary(b, {b.id} if me and any(r['user'] == me for r in reads) else set()), 'read_by': [{'name': r['name'], 'at': r['at']} for r in reads],
            'headline': metrics.headline(kind, b.metrics.get('sections', [])), 'narrative': b.narrative, 'original_narrative': b.original_narrative, 'generated_at': b.generated_at,
            'sections': b.metrics.get('sections', []), 'attention': b.metrics.get('attention', []),
            'approved_days': b.metrics.get('approved_days')}


def _read_ids(request, qs_model, objs):
    field = 'daily' if qs_model is DailyBrief else 'rollup'
    return set(BriefRead.objects.filter(user=request.user, **{f'{field}__in': [o.id for o in objs]}).values_list(f'{field}_id', flat=True))


def _settings_payload():
    s = service.get_settings()
    return {'enabled': s.enabled, 'morning_time': s.morning_time.strftime('%H:%M'), 'evening_time': s.evening_time.strftime('%H:%M'),
            'retention_days': service.RETENTION_DAYS}


def _ctx(request):
    from services.ai.context import AIContext

    try:
        return AIContext.from_request(request)
    except Exception:
        return None


def _school(request):
    from services.core.tenants.context import get_current_tenant

    return get_current_tenant()


def _parse_date(raw):
    try:
        return datetime.date.fromisoformat(str(raw)) if raw else None
    except ValueError:
        raise service.BriefError('The date is not valid.')


# ---- daily briefs -----------------------------------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def today(request):
    school = _school(request)
    day = service.school_today(school)
    rows = {b.kind: b for b in DailyBrief.objects.filter(date=day).select_related('approved_by')}
    return Response({'date': day.isoformat(), 'morning': _detail(rows['morning'], request) if 'morning' in rows else None,
                     'evening': _detail(rows['evening'], request) if 'evening' in rows else None, 'settings': _settings_payload(),
                     'time_zone': str(service.school_tz(school))})


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def daily_list(request):
    qs = DailyBrief.objects.select_related('approved_by')
    if request.query_params.get('kind') in ('morning', 'evening'):
        qs = qs.filter(kind=request.query_params['kind'])
    rows = list(qs[:200])
    ids = _read_ids(request, DailyBrief, rows)
    return Response([_summary(b, ids) for b in rows])


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
def generate(request):
    try:
        brief = service.generate(_school(request), str(request.data.get('kind') or ''), _parse_date(request.data.get('date')),
                                 ctx=_ctx(request), rate_limit=True)
    except service.BriefLocked as exc:
        return _err(str(exc), 409)
    except service.BriefError as exc:
        return _err(str(exc))
    audit_write(request, 'CREATE', 'daily_brief', str(brief.id), {'kind': brief.kind, 'date': brief.date.isoformat()})
    return Response(_detail(brief, request), status=201)


def _one(model, pk):
    return get_object_or_404(model.objects.select_related('approved_by'), pk=pk)


def _detail_view(model, request, pk):
    b = _one(model, pk)
    if request.method == 'DELETE':
        audit_write(request, 'DELETE', model.__name__.lower(), str(b.id), {'status': b.status, 'when': str(getattr(b, 'date', None) or b.period_end)})
        b.delete()
        return Response(status=204)
    if request.method == 'PATCH':
        try:
            service.edit(b, request.data.get('narrative', b.narrative))
        except service.BriefLocked as exc:
            return _err(str(exc), 409)
        audit_write(request, 'UPDATE', model.__name__.lower(), str(b.id), {'edited': True})
    return Response(_detail(b, request))


def _approve_view(model, request, pk):
    b = _one(model, pk)
    try:
        service.approve(b, request.user, request.data.get('narrative'))
    except service.BriefLocked as exc:
        return _err(str(exc), 409)
    audit_write(request, 'UPDATE', model.__name__.lower(), str(b.id), {'approved': True, 'edited': b.edited})
    return Response(_detail(b, request))


def _read_view(model, request, pk):
    b = _one(model, pk)
    service.mark_read(b, request.user)
    return Response(_detail(b, request))


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsSchoolAdmin])
def daily_detail(request, pk):
    return _detail_view(DailyBrief, request, pk)


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
def daily_approve(request, pk):
    return _approve_view(DailyBrief, request, pk)


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
def daily_read(request, pk):
    return _read_view(DailyBrief, request, pk)


# ---- roll-ups ---------------------------------------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def rollup_list(request):
    qs = BriefRollup.objects.select_related('approved_by')
    if request.query_params.get('period') in ('week', 'fortnight', 'month'):
        qs = qs.filter(period=request.query_params['period'])
    rows = list(qs[:100])
    ids = _read_ids(request, BriefRollup, rows)
    return Response([_summary(b, ids) for b in rows])


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
def rollup_generate(request):
    school = _school(request)
    try:
        end = _parse_date(request.data.get('end')) or service.school_today(school) - datetime.timedelta(days=1)
        r = service.rollup(school, str(request.data.get('period') or ''), end, ctx=_ctx(request), rate_limit=True)
    except service.BriefLocked as exc:
        return _err(str(exc), 409)
    except service.NothingToSummarise as exc:
        return _err(str(exc), 404)
    except service.BriefError as exc:
        return _err(str(exc))
    audit_write(request, 'CREATE', 'briefrollup', str(r.id), {'period': r.period, 'end': r.period_end.isoformat()})
    return Response(_detail(r, request), status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsSchoolAdmin])
def rollup_detail(request, pk):
    return _detail_view(BriefRollup, request, pk)


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
def rollup_approve(request, pk):
    return _approve_view(BriefRollup, request, pk)


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
def rollup_read(request, pk):
    return _read_view(BriefRollup, request, pk)


# ---- settings ---------------------------------------------------------------------------------------------------------

@api_view(['GET', 'PUT'])
@permission_classes([IsSchoolAdmin])
def settings_view(request):
    s = service.get_settings()
    if request.method == 'PUT':
        try:
            for key in ('morning_time', 'evening_time'):
                if key in request.data:
                    setattr(s, key, datetime.time.fromisoformat(str(request.data[key])))
        except ValueError:
            return _err('Times must look like 06:30.')
        if 'enabled' in request.data:
            s.enabled = bool(request.data['enabled'])
        s.save()
        audit_write(request, 'UPDATE', 'brief_settings', str(s.id), _settings_payload())
    return Response(_settings_payload())
