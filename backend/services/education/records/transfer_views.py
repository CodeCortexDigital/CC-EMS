"""Sending a 指導要録 to another school (転学 / 進学), and retention: which records have passed their period and may be disposed of.

Only the principal (an administrator) sends a record, and only when every year of it carries the principal's seal. Sending saves an unchangeable
copy (so the school can show exactly what was sent), and records where it went on the record itself: a transfer sets the day the pupil left (which
starts the retention clock), an advance sets the next school. Disposal is never automatic: it is a deliberate action, refused before the period
has passed, and recorded without the child's name.
"""
from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from services.education.students.access import audit_read, audit_write

from . import retention
from .models import CumulativeRecord, RecordTransfer
from .views import RecordStaff, _record_for, _role, record_payload

KINDS = {'transfer': '転学 (写し)', 'advance': '進学 (抄本)'}


def _issue(t: RecordTransfer, full: bool = False) -> dict:
    out = {'id': str(t.pk), 'kind': t.kind, 'kind_label': KINDS.get(t.kind, t.kind), 'to_school': t.to_school, 'sent_on': t.sent_on.isoformat(), 'note': t.note,
           'issued_at': t.issued_at.isoformat(), 'issued_by': (getattr(t.issued_by, 'full_name', '') or getattr(t.issued_by, 'email', '')) if t.issued_by_id else ''}
    if full:
        out['snapshot'] = t.snapshot
    return out


def _problems(record: CumulativeRecord) -> list[str]:
    years = list(record.years.all())
    if not years:
        return ['記録された学年がありません。']
    return [f'第{y.grade}学年に校長の印がありません。' for y in sorted(years, key=lambda y: y.grade) if not y.is_locked]


@api_view(['GET', 'POST'])
@permission_classes([RecordStaff])
def transfer(request, pk):
    """GET: what is needed before sending, the retention dates and what was sent before. POST ``{kind: transfer | advance, to_school, sent_on, note?}``
    (administrator): send it."""
    record, error = _record_for(request, pk)
    if error:
        return error
    problems = _problems(record)
    if request.method == 'POST':
        if _role(request.user) != 'admin':
            return Response({'detail': 'Only the principal (an administrator) can send a record to another school.'}, status=status.HTTP_403_FORBIDDEN)
        d = request.data or {}
        kind, to_school = d.get('kind'), str(d.get('to_school') or '').strip()
        if kind not in KINDS:
            return Response({'kind': 'Choose 転学 (transfer) or 進学 (advance).'}, status=status.HTTP_400_BAD_REQUEST)
        if not to_school:
            return Response({'to_school': 'Write which school it is for (送付先).'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            sent_on = date.fromisoformat(str(d.get('sent_on') or '')[:10])
        except ValueError:
            return Response({'sent_on': 'Use a date like 2026-03-25.'}, status=status.HTTP_400_BAD_REQUEST)
        if problems:
            return Response({'detail': 'It cannot be sent yet.', 'problems': problems}, status=status.HTTP_409_CONFLICT)
        with transaction.atomic():
            if kind == 'transfer':
                record.transfer_out_date, record.transfer_out_note = sent_on, f'転学先: {to_school}'[:300]
            else:
                record.next_school = to_school[:200]
            record.save(update_fields=['transfer_out_date', 'transfer_out_note', 'next_school', 'updated_at'])
            record.refresh_from_db()
            t = RecordTransfer.objects.create(record=record, kind=kind, to_school=to_school[:200], sent_on=sent_on, note=str(d.get('note') or '')[:300],
                                              snapshot=record_payload(record), issued_by=request.user)
        audit_write(request, 'CREATE', 'records/transfer', t.pk, {'record': str(record.pk), 'kind': kind, 'to_school': t.to_school})
        return Response(_issue(t, full=True), status=status.HTTP_201_CREATED)
    audit_read(request, 'records/transfer', record.pk)
    return Response({'problems': problems, 'ready': not problems, 'retention': retention.dates(record),
                     'transfers': [_issue(t) for t in record.transfers.select_related('issued_by')]})


@api_view(['GET'])
@permission_classes([RecordStaff])
def transfer_issue(request, pk, issue_id):
    """One record as it was sent."""
    record, error = _record_for(request, pk)
    if error:
        return error
    t = record.transfers.select_related('issued_by').filter(pk=issue_id).first()
    if t is None:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    audit_read(request, 'records/transfer-copy', t.pk)
    return Response(_issue(t, full=True))


# ---------------------------------------------------------------------------------------------------- retention
def _row(r: CumulativeRecord, today: date) -> dict:
    d = retention.dates(r)
    return {'id': str(r.pk), 'student_number': r.student.student_id, 'class_name': r.student.current_class.name if r.student.current_class_id else '',
            'level': r.level, **d, 'guidance_expired': retention.guidance_expired(r, today), 'register_expired': retention.register_expired(r, today)}


@api_view(['GET', 'POST'])
@permission_classes([RecordStaff])
def retention_view(request):
    """GET (administrators): records whose guidance part (5 years) or register (20 years) has passed its period, and those reaching it within a year.
    POST ``{"dispose": "guidance" | "register", "ids": [...], "confirm": <how many>}``: dispose of them. Refused for any record not yet past its period."""
    if _role(request.user) != 'admin':
        return Response({'detail': 'Only an administrator can manage retention.'}, status=status.HTTP_403_FORBIDDEN)
    today = timezone.localdate()
    qs = CumulativeRecord.objects.select_related('student', 'student__current_class').exclude(graduation_date=None, transfer_out_date=None)
    if request.method == 'POST':
        d = request.data or {}
        part, ids = d.get('dispose'), [str(i) for i in (d.get('ids') or [])]
        if part not in ('guidance', 'register') or not ids:
            return Response({'detail': 'Choose which part to dispose of and which records.'}, status=status.HTTP_400_BAD_REQUEST)
        records = list(qs.filter(pk__in=ids))
        check = retention.guidance_expired if part == 'guidance' else retention.register_expired
        early = [str(r.pk) for r in records if not check(r, today)]
        if early or len(records) != len(set(ids)):
            return Response({'detail': 'Some of these records have not reached the end of their period (or were not found), so nothing was changed.', 'ids': early}, status=status.HTTP_409_CONFLICT)
        if d.get('confirm') != len(records):
            return Response({'detail': 'Type the number of records to confirm.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for r in records:
                if part == 'guidance':
                    r.years.update(content={}, school_days=None, suspended_days=None, abroad_days=None, absent_days=None, attendance_remarks='')
                    r.guidance_disposed_at = timezone.now()
                    r.save(update_fields=['guidance_disposed_at', 'updated_at'])
                else:
                    r.delete()
        audit_write(request, 'DELETE', f'records/retention-{part}', None, {'count': len(records), 'records': [str(r.pk) for r in records]})
        return Response({'disposed': len(records), 'part': part})
    rows = [_row(r, today) for r in qs]
    audit_read(request, 'records/retention')
    return Response({
        'guidance_years': retention.GUIDANCE_YEARS, 'register_years': retention.REGISTER_YEARS,
        'guidance_due': [r for r in rows if r['guidance_expired']], 'register_due': [r for r in rows if r['register_expired']],
        'soon': [r for r, rec in zip(rows, qs) if retention.soon(rec, today) and not r['guidance_expired'] and not r['register_expired']],
        'kept': len(rows),
    })
