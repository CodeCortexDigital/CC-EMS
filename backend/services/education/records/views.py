"""The cumulative record (指導要録): open, fill in, seal and export.

Administrators (the principal) see and change every record and are the only ones who can put the principal's seal on a year and re-open
a sealed one. A teacher works on the records of the classes they teach and can put the class teacher's seal on a year. Families and
students have no access. Every read and change is written to the audit log, because the record is about a named child.
"""
from __future__ import annotations

import csv
import io

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from services.core.accounts.decorators import _get_teacher_class_ids, get_user_role
from services.core.tenants.context import get_current_tenant
from services.education.students.access import audit_read, audit_write
from services.education.students.models import Student

from . import forms, prefill
from .models import CumulativeRecord, CumulativeYear

BASE_FIELDS = ('student_furigana', 'student_address', 'guardian_name', 'guardian_furigana', 'guardian_address', 'previous_history', 'entry_date',
               'entry_kind', 'entry_grade', 'transfer_in_date', 'transfer_in_grade', 'transfer_out_date', 'transfer_out_note', 'abroad_from',
               'abroad_to', 'graduation_date', 'next_school', 'next_work', 'school_name', 'school_address', 'course_name', 'level')
DATE_FIELDS = ('entry_date', 'transfer_in_date', 'transfer_out_date', 'abroad_from', 'abroad_to', 'graduation_date')
YEAR_TEXT = ('year_label', 'class_name', 'roll_number', 'teacher_name', 'principal_name', 'attendance_remarks')
YEAR_NUMBERS = ('school_days', 'suspended_days', 'abroad_days', 'absent_days')


def _role(user):
    return get_user_role(user)


class RecordStaff(BasePermission):
    message = 'The cumulative record is for the principal and teachers.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and _role(request.user) in ('admin', 'teacher'))


def _may_see(user, student) -> bool:
    if _role(user) == 'admin':
        return True
    return student.current_class_id is not None and student.current_class_id in set(_get_teacher_class_ids(user))


def _record_for(request, pk):
    """(record, None) when the user may use it, else (None, a 404 or 403 response)."""
    record = CumulativeRecord.objects.select_related('student', 'student__current_class').filter(pk=pk).first()
    if record is None:
        return None, Response({'detail': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not _may_see(request.user, record.student):
        return None, Response({'detail': 'This student is not in one of your classes.'}, status=status.HTTP_403_FORBIDDEN)
    return record, None


def _iso(d):
    return d.isoformat() if d else None


def year_payload(y: CumulativeYear) -> dict:
    return {
        'id': str(y.pk), 'grade': y.grade, 'year_label': y.year_label, 'class_name': y.class_name, 'roll_number': y.roll_number,
        'teacher_name': y.teacher_name, 'principal_name': y.principal_name, 'school_days': y.school_days, 'suspended_days': y.suspended_days,
        'abroad_days': y.abroad_days, 'absent_days': y.absent_days, 'required_days': y.required_days, 'present_days': y.present_days,
        'attendance_remarks': y.attendance_remarks, 'content': y.content or {}, 'locked': y.is_locked,
        'teacher_confirmed_at': y.teacher_confirmed_at.isoformat() if y.teacher_confirmed_at else None,
        'teacher_confirmed_by': y.teacher_confirmed_by.full_name if y.teacher_confirmed_by_id else '',
        'principal_confirmed_at': y.principal_confirmed_at.isoformat() if y.principal_confirmed_at else None,
        'principal_confirmed_by': y.principal_confirmed_by.full_name if y.principal_confirmed_by_id else '',
    }


def record_payload(record: CumulativeRecord) -> dict:
    s = record.student
    years = list(record.years.select_related('teacher_confirmed_by', 'principal_confirmed_by').order_by('grade'))
    base = {f: (_iso(getattr(record, f)) if f in DATE_FIELDS else getattr(record, f)) for f in BASE_FIELDS}
    return {
        'id': str(record.pk), 'student': str(s.pk), 'student_number': s.student_id, 'student_name': s.full_name, 'gender': s.gender or '',
        'date_of_birth': _iso(s.date_of_birth), 'class_name': s.current_class.name if s.current_class_id else '',
        **base, 'years': [year_payload(y) for y in years], 'definition': forms.level_definition(record.level),
        'credit_totals': credit_totals(years) if record.level == 'high' else {},
    }


def credit_totals(years) -> dict:
    """修得単位数の計 for each course on the back of 様式1 (high school): the credits of every year added up."""
    totals: dict[str, dict] = {}
    for y in years:
        for c in (y.content or {}).get('courses', []):
            key = f'{c.get("area", "")}|{c.get("course", "")}'
            row = totals.setdefault(key, {'area': c.get('area', ''), 'course': c.get('course', ''), 'credits': 0})
            row['credits'] += int(c.get('credits') or 0)
    return {'courses': sorted(totals.values(), key=lambda r: (r['area'], r['course'])), 'total': sum(r['credits'] for r in totals.values())}


def _parse_date(value):
    from datetime import date
    if value in (None, ''):
        return None, None
    try:
        return date.fromisoformat(str(value)[:10]), None
    except ValueError:
        return None, 'Use a date like 2026-04-06.'


# ------------------------------------------------------------------------------------------------------ the roster
@api_view(['GET'])
@permission_classes([RecordStaff])
def roster(request):
    """Students with the state of their record, for one class (or every class an administrator can see)."""
    from services.education.academics.models import SchoolClass
    params = request.query_params
    cls = SchoolClass.objects.filter(pk=params['class']).first() if params.get('class') else None
    if params.get('class') and cls is None:
        return Response({'detail': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)
    qs = prefill.class_summary(cls)
    if _role(request.user) != 'admin':
        qs = qs.filter(current_class_id__in=_get_teacher_class_ids(request.user))
    if params.get('search'):
        q = params['search']
        qs = qs.filter(Q(full_name__icontains=q) | Q(student_id__icontains=q))
    qs = qs.order_by('current_class__grade_level', 'current_class__name', 'current_section__name', 'student_id')[:400]
    rows = []
    for s in qs:
        rec = CumulativeRecord.objects.filter(student=s).values_list('pk', 'level').first()
        rows.append({'student': str(s.pk), 'student_number': s.student_id, 'student_name': s.full_name,
                     'class_name': f'{s.current_class.name}{s.current_section.name if s.current_section_id else ""}' if s.current_class_id else '',
                     'record_id': str(rec[0]) if rec else None, 'level': rec[1] if rec else forms.level_for_class_grade(s.current_class.grade_level if s.current_class_id else None),
                     'years': s.years_total, 'years_sealed': s.years_sealed})
    audit_read(request, 'records/roster')
    return Response({'count': len(rows), 'results': rows})


# ------------------------------------------------------------------------------------------- opening and reading
@api_view(['POST'])
@permission_classes([RecordStaff])
def open_record(request):
    student = Student.objects.select_related('current_class', 'current_section').filter(pk=request.data.get('student')).first()
    if student is None:
        return Response({'student': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not _may_see(request.user, student):
        return Response({'detail': 'This student is not in one of your classes.'}, status=status.HTTP_403_FORBIDDEN)
    record, created = prefill.open_record(student, get_current_tenant(), request.user)
    if created:
        audit_write(request, 'CREATE', 'records/record', record.pk, {'student': str(student.pk)})
    return Response(record_payload(record), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['GET', 'PATCH'])
@permission_classes([RecordStaff])
def record_detail(request, pk):
    record, error = _record_for(request, pk)
    if error:
        return error
    if request.method == 'GET':
        audit_read(request, 'records/record', record_id=str(record.pk))
        return Response(record_payload(record))
    data, errors, changed = request.data or {}, {}, []
    if record.years.filter(principal_confirmed_at__isnull=False).exists() and _role(request.user) != 'admin':
        return Response({'detail': 'Part of this record has the principal\'s seal. Ask the principal to change it.'}, status=status.HTTP_403_FORBIDDEN)
    for f in BASE_FIELDS:
        if f not in data:
            continue
        v = data[f]
        if f in DATE_FIELDS:
            v, err = _parse_date(v)
            if err:
                errors[f] = err
                continue
        elif f == 'level':
            if v not in forms.LEVELS:
                errors[f] = 'Choose elementary, junior_high or high.'
                continue
        elif f in ('entry_grade', 'transfer_in_grade'):
            try:
                v = int(v) if v not in (None, '') else (1 if f == 'entry_grade' else None)
            except (TypeError, ValueError):
                errors[f] = 'Must be a number.'
                continue
        elif f == 'entry_kind':
            if v not in ('enrolled', 'admitted'):
                errors[f] = 'Choose 入学 or 編入学.'
                continue
        else:
            v = str(v or '')[:2000 if f == 'previous_history' else 300]
        setattr(record, f, v)
        changed.append(f)
    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)
    record.updated_by = request.user
    record.save()
    audit_write(request, 'UPDATE', 'records/record', record.pk, {'fields': changed})
    return Response(record_payload(record))


@api_view(['GET'])
@permission_classes([RecordStaff])
def form_definition(request, level):
    if level not in forms.LEVELS:
        return Response({'detail': 'Unknown level.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(forms.level_definition(level))


# --------------------------------------------------------------------------------------------------- the years
def _year_or_error(request, pk, grade):
    record, error = _record_for(request, pk)
    if error:
        return None, None, error
    if not 1 <= int(grade) <= forms.LEVELS[record.level]['grades']:
        return None, None, Response({'grade': f'This level has years 1 to {forms.LEVELS[record.level]["grades"]}.'}, status=status.HTTP_400_BAD_REQUEST)
    return record, CumulativeYear.objects.filter(record=record, grade=grade).first(), None


@api_view(['PUT'])
@permission_classes([RecordStaff])
def year_save(request, pk, grade):
    record, entry, error = _year_or_error(request, pk, grade)
    if error:
        return error
    if entry is not None and entry.is_locked:
        return Response({'detail': 'This year has the principal\'s seal. An administrator must re-open it first.'}, status=status.HTTP_409_CONFLICT)
    data, errors = request.data or {}, {}
    content, content_errors = forms.clean_content(record.level, int(grade), data.get('content', (entry.content if entry else {})))
    errors.update(content_errors)
    numbers = {}
    for f in YEAR_NUMBERS:
        if f in data:
            raw = data[f]
            if raw in (None, ''):
                numbers[f] = None
                continue
            try:
                n = int(raw)
                if not 0 <= n <= 366:
                    raise ValueError
                numbers[f] = n
            except (TypeError, ValueError):
                errors[f] = 'Use a whole number of days (0 to 366).'
    texts = {f: str(data[f] or '')[:300] for f in YEAR_TEXT if f in data}
    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        entry = entry or CumulativeYear(record=record, grade=int(grade))
        for f, v in {**numbers, **texts}.items():
            setattr(entry, f, v)
        entry.content = content
        # Anything changed after a class teacher's seal withdraws it: the teacher must look at the final text again.
        if entry.pk and entry.teacher_confirmed_at:
            entry.teacher_confirmed_at = entry.teacher_confirmed_by = None
        entry.save()
    audit_write(request, 'UPDATE', 'records/year', entry.pk, {'record': str(record.pk), 'grade': int(grade)})
    return Response(year_payload(entry))


@api_view(['POST'])
@permission_classes([RecordStaff])
def year_prefill(request, pk, grade):
    record, entry, error = _year_or_error(request, pk, grade)
    if error:
        return error
    if entry is not None and entry.is_locked:
        return Response({'detail': 'This year has the principal\'s seal.'}, status=status.HTTP_409_CONFLICT)
    entry = prefill.fill_year(record, int(grade))
    audit_write(request, 'UPDATE', 'records/year', entry.pk, {'record': str(record.pk), 'grade': int(grade), 'prefill': True})
    return Response(year_payload(entry))


@api_view(['POST'])
@permission_classes([RecordStaff])
def year_confirm(request, pk, grade):
    """Put a seal (印) on a year: ``{"as": "teacher"}`` (class teacher) or ``{"as": "principal"}`` (administrator, after the teacher)."""
    record, entry, error = _year_or_error(request, pk, grade)
    if error:
        return error
    if entry is None:
        return Response({'detail': 'Fill in this year first.'}, status=status.HTTP_400_BAD_REQUEST)
    who = (request.data or {}).get('as')
    if who not in ('teacher', 'principal'):
        return Response({'as': 'Choose teacher or principal.'}, status=status.HTTP_400_BAD_REQUEST)
    if who == 'principal' and _role(request.user) != 'admin':
        return Response({'detail': 'Only the principal (an administrator) can put the principal\'s seal.'}, status=status.HTTP_403_FORBIDDEN)
    if entry.is_locked:
        return Response({'detail': 'This year already has the principal\'s seal.'}, status=status.HTTP_409_CONFLICT)
    missing = [label for label, value in (('年度', entry.year_label), ('学級', entry.class_name), ('学級担任者', entry.teacher_name)) if not value]
    if who == 'principal':
        if not entry.teacher_confirmed_at:
            return Response({'detail': 'The class teacher must put a seal on this year first.'}, status=status.HTTP_409_CONFLICT)
        if not entry.principal_name:
            missing.append('校長')
    if missing:
        return Response({'detail': 'Fill in: ' + '、'.join(missing)}, status=status.HTTP_400_BAD_REQUEST)
    now = timezone.now()
    if who == 'teacher':
        entry.teacher_confirmed_at, entry.teacher_confirmed_by = now, request.user
    else:
        entry.principal_confirmed_at, entry.principal_confirmed_by = now, request.user
    entry.save()
    audit_write(request, 'UPDATE', 'records/seal', entry.pk, {'record': str(record.pk), 'grade': int(grade), 'seal': who})
    return Response(year_payload(entry))


@api_view(['POST'])
@permission_classes([RecordStaff])
def year_reopen(request, pk, grade):
    record, entry, error = _year_or_error(request, pk, grade)
    if error:
        return error
    if _role(request.user) != 'admin':
        return Response({'detail': 'Only an administrator can re-open a sealed year.'}, status=status.HTTP_403_FORBIDDEN)
    reason = str((request.data or {}).get('reason') or '').strip()
    if entry is None or not (entry.principal_confirmed_at or entry.teacher_confirmed_at):
        return Response({'detail': 'This year has no seal to remove.'}, status=status.HTTP_400_BAD_REQUEST)
    if not reason:
        return Response({'reason': 'Write why it is being re-opened.'}, status=status.HTTP_400_BAD_REQUEST)
    entry.teacher_confirmed_at = entry.teacher_confirmed_by = entry.principal_confirmed_at = entry.principal_confirmed_by = None
    entry.save()
    audit_write(request, 'UPDATE', 'records/reopen', entry.pk, {'record': str(record.pk), 'grade': int(grade), 'reason': reason})
    return Response(year_payload(entry))


# ---------------------------------------------------------------------------------------------------- export
def _flat_rows(records):
    """One row per student and year, with the same columns for every row of one level (the Japanese legal record export)."""
    out = []
    for record in records:
        spec = forms.LEVELS[record.level]
        s = record.student
        for y in record.years.order_by('grade'):
            c = y.content or {}
            row = {
                '学籍番号': s.student_id, '氏名': s.full_name, 'ふりがな': record.student_furigana, '性別': {'male': '男', 'female': '女'}.get(s.gender or '', ''),
                '生年月日': _iso(s.date_of_birth) or '', '校種': dict(CumulativeRecord.LEVELS)[record.level], '学年': y.grade, '年度': y.year_label,
                '学級': y.class_name, '整理番号': y.roll_number, '学級担任者': y.teacher_name, '校長': y.principal_name,
                '授業日数': y.school_days if y.school_days is not None else '', '出席停止・忌引等の日数': y.suspended_days if y.suspended_days is not None else '',
                '出席しなければならない日数': y.required_days if y.required_days is not None else '', '欠席日数': y.absent_days if y.absent_days is not None else '',
                '出席日数': y.present_days if y.present_days is not None else '', '出欠備考': y.attendance_remarks,
            }
            for subj in spec['subjects']:
                cell = (c.get('subjects') or {}).get(subj['code'], {})
                for key, label in forms.VIEWPOINTS:
                    row[f'{subj["name"]}_{label}'] = cell.get(key, '')
                row[f'{subj["name"]}_評定'] = cell.get('rating', '')
            if record.level == 'high':
                row['修得単位数'] = sum(int(x.get('credits') or 0) for x in c.get('courses', []))
            row['道徳'] = c.get('moral', '')
            for key, label in (('integrated_activity', '総合_学習活動'), ('integrated_viewpoint', '総合_観点'), ('integrated_evaluation', '総合_評価')):
                row[label] = c.get(key, '')
            for key, label in forms.SPECIAL_ACTIVITIES[record.level]:
                row[f'特別活動_{label}'] = '○' if (c.get('special_activities') or {}).get(key) else ''
            for key, label in forms.BEHAVIOUR_ITEMS:
                row[f'行動_{label}'] = '○' if (c.get('behaviour') or {}).get(key) else ''
            row['総合所見'] = c.get('comment', '')
            row['担任印'] = _iso(y.teacher_confirmed_at.date()) if y.teacher_confirmed_at else ''
            row['校長印'] = _iso(y.principal_confirmed_at.date()) if y.principal_confirmed_at else ''
            out.append(row)
    return out


def _csv_response(rows, filename):
    names: list[str] = []
    for r in rows:
        for k in r:
            if k not in names:
                names.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=names, extrasaction='ignore')
    w.writeheader()
    w.writerows(rows)
    resp = HttpResponse('﻿' + buf.getvalue(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@api_view(['GET'])
@permission_classes([RecordStaff])
def export_one(request, pk):
    record, error = _record_for(request, pk)
    if error:
        return error
    audit_read(request, 'records/export', record_id=str(record.pk))
    if request.query_params.get('type') == 'csv':
        return _csv_response(_flat_rows([record]), f'shido-yoroku-{record.student.student_id}.csv')
    return Response(record_payload(record))


@api_view(['GET'])
@permission_classes([RecordStaff])
def export_many(request):
    """Every record of a class (or the whole school, administrators only) as one CSV or JSON file."""
    params = request.query_params
    qs = CumulativeRecord.objects.select_related('student', 'student__current_class')
    if params.get('class'):
        qs = qs.filter(student__current_class_id=params['class'])
    if _role(request.user) != 'admin':
        qs = qs.filter(student__current_class_id__in=_get_teacher_class_ids(request.user))
    elif not params.get('class') and params.get('all') not in ('1', 'true'):
        return Response({'detail': 'Choose a class, or ask for all with all=1.'}, status=status.HTTP_400_BAD_REQUEST)
    records = list(qs.order_by('student__current_class__grade_level', 'student__student_id')[:2000])
    audit_read(request, 'records/export-many')
    if params.get('type') == 'csv':
        return _csv_response(_flat_rows(records), 'shido-yoroku.csv')
    return Response({'count': len(records), 'results': [record_payload(r) for r in records]})
