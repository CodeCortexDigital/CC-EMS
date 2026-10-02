"""Cover requests: a teacher (or the office) asks for a period to be covered on a date; a free colleague accepts it,
or the office assigns someone. Mounted under ``/api/v1/auth/hr/``.

This sits beside the automatic cover that is arranged when leave is approved (academics/substitution.py): that one
handles planned leave, this one handles one-off absences, swaps and anything the automatic cover could not fill.
"""
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from services.education.academics.eligibility import get_policy, is_qualified, why_not
from services.education.academics.models import Period, Teacher, TeacherLeave, TimetableEntry

from .access import err, is_hr, notify_teacher, parse_date, teacher_for
from .models import SubstituteRequest

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def is_busy(teacher, day, period_id) -> bool:
    """True when this teacher already teaches, covers or is on leave in that period on that date."""
    name = WEEKDAYS[day.weekday()]
    if TimetableEntry.objects.filter(teacher=teacher, day_of_week=name, period_id=period_id, is_active=True).exists():
        return True
    if SubstituteRequest.objects.filter(substitute=teacher, date=day, period_id=period_id, status='filled').exists():
        return True
    return TeacherLeave.objects.filter(
        teacher=teacher, status='approved', start_date__lte=day, end_date__gte=day).exclude(day_part__in=['am', 'pm']).exists()


def subject_of(req):
    cs = req.entry.class_subject if req.entry_id else None
    return cs.subject.name if cs and cs.subject else ''


def _subject_obj(req):
    return req.entry.class_subject.subject if req.entry_id else None


def enforced(req) -> bool:
    return get_policy(req.requester.tenant).enforce_subject_match and _subject_obj(req) is not None


def qualified_for(teacher, req) -> bool:
    """True when the period needs no particular subject, or the teacher is qualified for it."""
    subject = _subject_obj(req)
    return subject is None or is_qualified(teacher, subject)


def candidates_for(req):
    """Free colleagues for this request: qualified ones first, then the relief pool, then by name.

    Each item is (teacher, qualified). Unqualified people are included so HR can see who is free, but only an
    administrator can give them the period, with a reason."""
    out = []
    for t in Teacher.objects.filter(is_active=True).exclude(pk=req.requester_id).prefetch_related('subjects'):
        if req.period_id and is_busy(t, req.date, req.period_id):
            continue
        ok = qualified_for(t, req)
        out.append((0 if ok else 1, 0 if t.teacher_type == 'relief' else 1, t.full_name.lower(), t, ok))
    out.sort(key=lambda x: x[:3])
    return [(t, ok) for *_, t, ok in out]


def _who(t):
    return {'id': str(t.id), 'name': t.full_name} if t else None


def present(req, viewer=None, mine=None):
    """JSON for one request. `can_accept` tells the viewer whether they could take it."""
    period = req.period
    cs = req.entry.class_subject if req.entry_id else None
    can_accept = bool(
        req.status == 'open' and mine is not None and mine.id != req.requester_id and mine.is_active
        and req.date >= timezone.localdate() and not (req.period_id and is_busy(mine, req.date, req.period_id))
        and (not enforced(req) or qualified_for(mine, req)))
    return {
        'id': str(req.id), 'date': req.date, 'status': req.status,
        'requester': _who(req.requester), 'substitute': _who(req.substitute),
        'period': ({'id': str(period.id), 'name': period.name or f'Period {period.period_number}',
                    'number': period.period_number, 'start': str(period.start_time)[:5], 'end': str(period.end_time)[:5]}
                   if period else None),
        'class_name': cs.class_ref.name if cs else '', 'subject': subject_of(req),
        'description': req.description, 'reason': req.reason,
        'filled_how': req.filled_how, 'filled_at': req.filled_at, 'created_at': req.created_at,
        'can_accept': can_accept,
        'can_cancel': bool(viewer and (is_hr(viewer) or (mine and mine.id == req.requester_id)) and req.status != 'cancelled'),
        'is_mine': bool(mine and mine.id == req.requester_id),
        'is_covering': bool(mine and req.substitute_id == mine.id),
    }


def _base_qs():
    return SubstituteRequest.objects.select_related(
        'requester', 'substitute', 'period', 'entry__class_subject__subject', 'entry__class_subject__class_ref')


def _ask_for_cover(req):
    """Tell the free colleagues who could take it (the best matches first, at most ten)."""
    people = [t for t, ok in candidates_for(req) if ok][:10]
    when = f'{req.date:%a %d %b}'
    what = req.description or subject_of(req) or 'a period'
    for t in people:
        notify_teacher(t, 'Cover needed', f'{req.requester.full_name} needs cover for {what} on {when}. Open Staff & HR > Cover requests to take it.')


def _make_request(requester, day, entry=None, period=None, description='', reason='', user=None):
    if entry is not None:
        period = entry.period
        if not description:
            cs = entry.class_subject
            description = f'{cs.class_ref.name} {cs.subject.name}'.strip()
    req = SubstituteRequest.objects.create(
        requester=requester, date=day, entry=entry, period=period, description=description[:255],
        reason=reason[:255], created_by=user)
    return req


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def requests_(request):
    me = teacher_for(request.user)
    hr = is_hr(request.user)
    if request.method == 'GET':
        qs = _base_qs()
        scope = request.query_params.get('scope') or ('all' if hr else 'involved')
        if scope == 'all' and not hr:
            return err('Only HR and administrators can see every request.', 403)
        if scope == 'mine':
            qs = qs.filter(requester=me) if me else qs.none()
        elif scope == 'covering':
            qs = qs.filter(substitute=me) if me else qs.none()
        elif scope in ('available', 'involved'):
            if not me:
                return Response([])
            today = timezone.localdate()
            rows = [r for r in qs.filter(status='open', date__gte=today).exclude(requester=me)
                    if present(r, request.user, me)['can_accept']]
            ids = [r.id for r in rows]
            q = Q(id__in=ids)
            if scope == 'involved':
                q |= Q(requester=me) | Q(substitute=me)
            qs = qs.filter(q)
        if request.query_params.get('status'):
            qs = qs.filter(status=request.query_params['status'])
        if request.query_params.get('from'):
            qs = qs.filter(date__gte=request.query_params['from'])
        if request.query_params.get('to'):
            qs = qs.filter(date__lte=request.query_params['to'])
        return Response([present(r, request.user, me) for r in qs[:300]])

    # POST: ask for one period (an entry, or a period plus a description) to be covered.
    d = request.data
    try:
        day = parse_date(d.get('date'))
    except ValueError as e:
        return err(str(e))
    if day < timezone.localdate():
        return err('Cover can only be requested for today or a later date.')
    if hr and d.get('teacher_id'):
        requester = get_object_or_404(Teacher, pk=d['teacher_id'])
    elif me:
        requester = me
    else:
        return err('Your login is not linked to a staff record, so you cannot ask for cover. Ask the office.', 403)
    entry = None
    period = None
    if d.get('entry_id'):
        entry = get_object_or_404(TimetableEntry, pk=d['entry_id'])
        if entry.teacher_id != requester.id:
            return err('That period is not on this teacher\'s timetable.')
        if entry.day_of_week != WEEKDAYS[day.weekday()]:
            return err(f'That period is on {entry.day_of_week.title()}s, not on {day:%A}.')
    elif d.get('period_id'):
        period = get_object_or_404(Period, pk=d['period_id'])
        if not (d.get('description') or '').strip():
            return err('Say what needs covering, for example "lunch duty".')
    else:
        return err('Choose the period that needs cover.')
    if SubstituteRequest.objects.filter(requester=requester, date=day, status__in=['open', 'filled'],
                                        period_id=(entry.period_id if entry else period.id)).exists():
        return err('Cover has already been requested for that period.')
    req = _make_request(requester, day, entry, period, (d.get('description') or '').strip(), (d.get('reason') or '').strip(),
                        request.user)
    _ask_for_cover(req)
    return Response(present(_base_qs().get(pk=req.pk), request.user, me), status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_periods(request):
    """The periods a teacher has on a date (to pick from when asking for cover), and every period for duties."""
    me = teacher_for(request.user)
    try:
        day = parse_date(request.query_params.get('date'))
    except ValueError as e:
        return err(str(e))
    teacher = me
    if is_hr(request.user) and request.query_params.get('teacher_id'):
        teacher = get_object_or_404(Teacher, pk=request.query_params['teacher_id'])
    entries = []
    if teacher:
        entries = TimetableEntry.objects.filter(
            teacher=teacher, day_of_week=WEEKDAYS[day.weekday()], is_active=True
        ).select_related('period', 'class_subject__subject', 'class_subject__class_ref').order_by('period__period_number')
    asked = set(SubstituteRequest.objects.filter(
        requester=teacher, date=day, status__in=['open', 'filled']).values_list('period_id', flat=True)) if teacher else set()
    periods = Period.objects.filter(is_active=True, is_break=False, academic_year__is_active=True).order_by('period_number')
    return Response({
        'teacher': _who(teacher),
        'entries': [{'id': str(e.id), 'period': e.period.name or f'Period {e.period.period_number}',
                     'time': f'{str(e.period.start_time)[:5]}-{str(e.period.end_time)[:5]}',
                     'label': f'{e.class_subject.class_ref.name} {e.class_subject.subject.name}'.strip(),
                     'already_requested': e.period_id in asked} for e in entries],
        'periods': [{'id': str(p.id), 'name': p.name or f'Period {p.period_number}',
                     'time': f'{str(p.start_time)[:5]}-{str(p.end_time)[:5]}'} for p in periods],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def absence(request):
    """One-off absence (a sick call this morning): ask cover for every period the teacher has that day."""
    me = teacher_for(request.user)
    hr = is_hr(request.user)
    try:
        day = parse_date(request.data.get('date'))
    except ValueError as e:
        return err(str(e))
    if day < timezone.localdate():
        return err('Cover can only be requested for today or a later date.')
    if hr and request.data.get('teacher_id'):
        teacher = get_object_or_404(Teacher, pk=request.data['teacher_id'])
    elif me:
        teacher = me
    else:
        return err('Your login is not linked to a staff record.', 403)
    reason = (request.data.get('reason') or '').strip()
    entries = TimetableEntry.objects.filter(
        teacher=teacher, day_of_week=WEEKDAYS[day.weekday()], is_active=True
    ).select_related('period', 'class_subject__subject', 'class_subject__class_ref').order_by('period__period_number')
    made, skipped = [], []
    for entry in entries:
        if SubstituteRequest.objects.filter(requester=teacher, date=day, period_id=entry.period_id,
                                            status__in=['open', 'filled']).exists():
            skipped.append(entry.period.name or f'Period {entry.period.period_number}')
            continue
        made.append(_make_request(teacher, day, entry, None, '', reason, request.user))
    if not entries:
        return err(f'{teacher.full_name} has no periods on {day:%A}, so there is nothing to cover.')
    for req in made:
        _ask_for_cover(req)
    return Response({'created': [present(_base_qs().get(pk=r.pk), request.user, me) for r in made], 'already_covered': skipped},
                    status=201 if made else 200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def candidates(request, request_id):
    if not is_hr(request.user):
        return err('Only HR and administrators can choose who covers.', 403)
    req = get_object_or_404(_base_qs(), pk=request_id)
    return Response([{'id': str(t.id), 'name': t.full_name, 'relief': t.teacher_type == 'relief', 'subject_match': ok,
                      'qualified': ok, 'department': t.department,
                      'reason': '' if ok else why_not(t, _subject_obj(req))} for t, ok in candidates_for(req)])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def act(request, request_id, action):
    me = teacher_for(request.user)
    hr = is_hr(request.user)
    with transaction.atomic():
        req = get_object_or_404(_base_qs().select_for_update(of=('self',)) if _supports_lock() else _base_qs(), pk=request_id)
        what = req.description or subject_of(req) or 'a period'
        when = f'{req.date:%a %d %b}'
        if action in ('accept', 'assign'):
            if req.status != 'open':
                return err('This request is no longer open.', 409)
            override = ''
            if action == 'accept':
                if me is None:
                    return err('Your login is not linked to a staff record.', 403)
                taker, how = me, 'claimed'
            else:
                if not hr:
                    return err('Only HR and administrators can assign cover.', 403)
                taker = get_object_or_404(Teacher, pk=request.data.get('teacher_id'), is_active=True)
                how = 'assigned'
            if taker.id == req.requester_id:
                return err('A teacher cannot cover their own period.')
            if req.date < timezone.localdate():
                return err('That date has already passed.')
            if req.period_id and is_busy(taker, req.date, req.period_id):
                return err(f'{taker.full_name} is not free in that period.', 409)
            if enforced(req) and not qualified_for(taker, req):
                override = (request.data.get('override_reason') or '').strip()
                if action == 'accept' or not override:
                    return err(why_not(taker, _subject_obj(req)) + (
                        ' An administrator can still assign this period by giving a reason.' if action == 'assign'
                        else ' Ask HR to assign it if you should cover it.'), 403 if action == 'accept' else 400)
            req.status, req.substitute, req.filled_how, req.filled_at = 'filled', taker, how, timezone.now()
            req.override_reason = override
            req.save(update_fields=['status', 'substitute', 'filled_how', 'filled_at', 'override_reason'])
            notify_teacher(req.requester, 'Your cover is arranged', f'{taker.full_name} will cover {what} on {when}.')
            if how == 'assigned':
                notify_teacher(taker, 'You were asked to cover', f'You are covering {what} for {req.requester.full_name} on {when}.')
        elif action == 'release':
            if req.status != 'filled' or not (hr or (me and req.substitute_id == me.id)):
                return err('Only the person covering (or HR) can give a covered period back.', 403)
            gone = req.substitute
            req.status, req.substitute, req.filled_how, req.filled_at = 'open', None, '', None
            req.save(update_fields=['status', 'substitute', 'filled_how', 'filled_at'])
            notify_teacher(req.requester, 'Cover fell through', f'{gone.full_name} can no longer cover {what} on {when}. It is open again.')
            _ask_for_cover(req)
        elif action == 'cancel':
            if not (hr or (me and req.requester_id == me.id)):
                return err('Only the teacher who asked (or HR) can cancel this.', 403)
            if req.status == 'cancelled':
                return err('Already cancelled.', 409)
            gone = req.substitute
            req.status = 'cancelled'
            req.save(update_fields=['status'])
            notify_teacher(gone, 'Cover cancelled', f'You no longer need to cover {what} on {when}.')
        else:
            return err('Unknown action.', 404)
    return Response(present(_base_qs().get(pk=req.pk), request.user, me))


def _supports_lock():
    from django.db import connection
    return connection.features.has_select_for_update
