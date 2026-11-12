"""The term report (通知表): layouts, opening and filling a student's report for a term, finalising and re-opening it.

Administrators set the layouts and can re-open a finalised report. A teacher fills in and finalises the reports of the classes they teach.
Families and students have no access here (a family-facing release can be added later). Reads and changes are audited, as the report is
about a named child.
"""
from __future__ import annotations

from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from services.core.accounts.decorators import _get_teacher_class_ids
from services.education.academics.models import AcademicYear, ClassSubject, Term
from services.education.students.access import audit_read, audit_write
from services.education.students.models import Student

from . import forms, prefill, termreport
from .models import TermReport, TermReportLayout
from .views import RecordStaff, _may_see, _role


def layout_payload(layout: TermReportLayout) -> dict:
    return {'id': str(layout.pk), 'name': layout.name, 'level': layout.level, 'is_default': layout.is_default, 'config': layout.config}


def report_payload(report: TermReport) -> dict:
    s = report.student
    return {
        'id': str(report.pk), 'student': str(s.pk), 'student_name': s.full_name, 'student_number': s.student_id, 'layout': report.layout_snapshot,
        'term': str(report.term_id) if report.term_id else None, 'year_label': report.year_label, 'term_label': report.term_label,
        'class_name': report.class_name, 'teacher_name': report.teacher_name, 'principal_name': report.principal_name,
        'school_days': report.school_days, 'suspended_days': report.suspended_days, 'absent_days': report.absent_days,
        'attendance_remarks': report.attendance_remarks, 'content': report.content, 'is_locked': report.is_locked,
        'finalised_at': report.finalised_at.isoformat() if report.finalised_at else None,
        'finalised_by': (getattr(report.finalised_by, 'full_name', '') or getattr(report.finalised_by, 'email', '')) if report.finalised_by_id else '',
        'school_name': prefill._school_profile(report.tenant)[0] if report.tenant_id else '',
    }


def ensure_layouts() -> list[TermReportLayout]:
    """The school's layouts; a starting one for elementary and junior high is made the first time (a school edits it to match its own form)."""
    rows = list(TermReportLayout.objects.all())
    if not rows:
        for level, name in (('elementary', '小学校 通知表'), ('junior_high', '中学校 通知表')):
            rows.append(TermReportLayout.objects.create(name=name, level=level, config=termreport.default_config(level), is_default=True))
    return rows


def _layout_for(level: str, layout_id=None):
    layouts = ensure_layouts()
    if layout_id:
        return next((x for x in layouts if str(x.pk) == str(layout_id)), None)
    same = [x for x in layouts if x.level == level]
    return next((x for x in same if x.is_default), same[0] if same else layouts[0])


# ------------------------------------------------------------------------------------------------ layouts
@api_view(['GET', 'POST'])
@permission_classes([RecordStaff])
def layouts(request):
    """GET: the layouts (and the choices for building one). POST (administrators): save one, ``{id?, name, level, config, is_default}``."""
    if request.method == 'POST':
        if _role(request.user) != 'admin':
            return Response({'detail': 'Only an administrator can change the layout.'}, status=status.HTTP_403_FORBIDDEN)
        d = request.data or {}
        config, problem = termreport.clean_config(d.get('config'))
        if problem:
            return Response({'config': problem}, status=status.HTTP_400_BAD_REQUEST)
        name = str(d.get('name') or '').strip()
        level = d.get('level')
        if not name or level not in forms.LEVELS:
            return Response({'name': 'Give the layout a name and choose a school level.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            ensure_layouts()
            if d.get('id'):
                layout = TermReportLayout.objects.filter(pk=d['id']).first()
                if layout is None:
                    return Response({'detail': 'Layout not found.'}, status=status.HTTP_404_NOT_FOUND)
                layout.name, layout.level, layout.config = name[:80], level, config
            else:
                layout = TermReportLayout(name=name[:80], level=level, config=config)
            if d.get('is_default'):
                TermReportLayout.objects.filter(level=level).exclude(pk=layout.pk).update(is_default=False)
                layout.is_default = True
            layout.save()
        audit_write(request, 'UPDATE' if d.get('id') else 'CREATE', 'records/term-layout', layout.pk, {'name': layout.name})
        return Response(layout_payload(layout))
    return Response({'layouts': [layout_payload(x) for x in ensure_layouts()], 'scales': termreport.SCALE_LABELS,
                     'viewpoints': [{'key': k, 'label': v} for k, v in forms.VIEWPOINTS]})


# ------------------------------------------------------------------------------------------------ roster and open
def _terms():
    year = AcademicYear.objects.filter(is_active=True).first()
    qs = Term.objects.filter(academic_year=year).order_by('order', 'start_date') if year else Term.objects.none()
    return year, list(qs)


@api_view(['GET'])
@permission_classes([RecordStaff])
def roster(request):
    """The terms of the school year, and the students of one class with the state of their report for ``?term=``."""
    from services.education.academics.models import SchoolClass
    year, terms = _terms()
    out = {'year': year.name if year else '', 'terms': [{'id': str(t.pk), 'name': t.name} for t in terms], 'results': []}
    params = request.query_params
    term = next((t for t in terms if str(t.pk) == params.get('term')), None)
    if not params.get('class') or term is None:
        return Response(out)
    cls = SchoolClass.objects.filter(pk=params['class']).first()
    if cls is None:
        return Response({'detail': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)
    if _role(request.user) != 'admin' and cls.pk not in set(_get_teacher_class_ids(request.user)):
        return Response({'detail': 'This is not one of your classes.'}, status=status.HTTP_403_FORBIDDEN)
    mine = {r.student_id: r for r in TermReport.objects.filter(term=term, student__current_class=cls)}
    for s in Student.objects.filter(current_class=cls, is_active=True).select_related('current_section').order_by('student_id'):
        r = mine.get(s.pk)
        out['results'].append({'student': str(s.pk), 'student_number': s.student_id, 'student_name': s.full_name,
                               'report_id': str(r.pk) if r else None, 'is_locked': bool(r and r.is_locked)})
    audit_read(request, 'records/term-roster')
    return Response(out)


def _fill(report: TermReport, today: date | None = None, ratings: bool = True) -> None:
    """Class, teacher, principal and attendance for the term, and (when asked) the rating each subject's gradebook grade works out to.
    Only empty values are written for ratings; a typed rating is never replaced."""
    s, today = report.student, today or date.today()
    if s.current_class_id:
        report.class_name = report.class_name or prefill._class_label(s)
        report.teacher_name = report.teacher_name or prefill._teacher_for(s.current_class, s)
    report.principal_name = report.principal_name or prefill._principal_name()
    if report.term_id:
        t = report.term
        counts = prefill.attendance_counts(s, t.start_date, min(t.end_date, today))
        report.school_days, report.suspended_days, report.absent_days = counts['school_days'], counts['suspended_days'], counts['absent_days']
    if ratings and report.term_id and s.current_class_id:
        from services.education.gradebook.calc import term_grade
        content = report.content or {}
        subjects = content.setdefault('subjects', {})
        for name in report.layout_snapshot.get('subjects', []):
            cell = subjects.setdefault(name, {'v1': '', 'v2': '', 'v3': '', 'rating': ''})
            if cell.get('rating'):
                continue
            cs = ClassSubject.objects.filter(class_ref=s.current_class, subject__name=name).first()
            if cs is None:
                continue
            cell['rating'] = termreport.rating_from_percent(report.layout_snapshot, term_grade(s, cs, report.term).percent)
        report.content = content


@api_view(['POST'])
@permission_classes([RecordStaff])
def open_report(request):
    """Make (or find) a student's report for a term: ``{"student": id, "term": id, "layout": id?}``. A new report is filled from school data."""
    d = request.data or {}
    student = Student.objects.select_related('current_class').filter(pk=d.get('student')).first()
    if student is None:
        return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not _may_see(request.user, student):
        return Response({'detail': 'This student is not in one of your classes.'}, status=status.HTTP_403_FORBIDDEN)
    year, terms = _terms()
    term = next((t for t in terms if str(t.pk) == str(d.get('term'))), None)
    if term is None:
        return Response({'term': 'Choose a term of this school year.'}, status=status.HTTP_400_BAD_REQUEST)
    existing = TermReport.objects.filter(student=student, year_label=year.name, term_label=term.name).first()
    if existing:
        return Response(report_payload(existing))
    level = forms.level_for_class_grade(student.current_class.grade_level if student.current_class_id else None)
    layout = _layout_for(level, d.get('layout'))
    if layout is None:
        return Response({'layout': 'Layout not found.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        with transaction.atomic():
            report = TermReport(student=student, layout=layout, layout_snapshot=layout.config, term=term, year_label=year.name, term_label=term.name,
                                content={'subjects': {}, 'conduct': {}, 'comments': {}})
            _fill(report)
            report.save()
    except IntegrityError:
        report = TermReport.objects.get(student=student, year_label=year.name, term_label=term.name)
    audit_write(request, 'CREATE', 'records/term-report', report.pk, {'student': str(student.pk), 'term': term.name})
    return Response(report_payload(report), status=status.HTTP_201_CREATED)


def _report_or_error(request, pk):
    report = TermReport.objects.select_related('student', 'student__current_class', 'term', 'tenant', 'finalised_by').filter(pk=pk).first()
    if report is None:
        return None, Response({'detail': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not _may_see(request.user, report.student):
        return None, Response({'detail': 'This student is not in one of your classes.'}, status=status.HTTP_403_FORBIDDEN)
    return report, None


@api_view(['GET', 'PUT'])
@permission_classes([RecordStaff])
def report_detail(request, pk):
    report, error = _report_or_error(request, pk)
    if error:
        return error
    if request.method == 'GET':
        audit_read(request, 'records/term-report', report.pk)
        return Response(report_payload(report))
    if report.is_locked:
        return Response({'detail': 'This report is finalised. An administrator can re-open it.'}, status=status.HTTP_409_CONFLICT)
    d = request.data or {}
    if 'content' in d:
        content, problem = termreport.clean_content(report.layout_snapshot, d['content'])
        if problem:
            return Response({'content': problem}, status=status.HTTP_400_BAD_REQUEST)
        report.content = content
    for f in ('class_name', 'teacher_name', 'principal_name', 'attendance_remarks'):
        if f in d:
            setattr(report, f, str(d[f] or '')[:300])
    for f in ('school_days', 'suspended_days', 'absent_days'):
        if f in d:
            try:
                v = None if d[f] in (None, '') else int(d[f])
            except (TypeError, ValueError):
                return Response({f: 'Enter a whole number.'}, status=status.HTTP_400_BAD_REQUEST)
            if v is not None and not 0 <= v <= 366:
                return Response({f: 'Enter a number of days from 0 to 366.'}, status=status.HTTP_400_BAD_REQUEST)
            setattr(report, f, v)
    report.save()
    audit_write(request, 'UPDATE', 'records/term-report', report.pk, {'student': str(report.student_id)})
    return Response(report_payload(report))


@api_view(['POST'])
@permission_classes([RecordStaff])
def report_prefill(request, pk):
    """Fill the class, teacher, attendance and the ratings from the gradebook (typed ratings are kept)."""
    report, error = _report_or_error(request, pk)
    if error:
        return error
    if report.is_locked:
        return Response({'detail': 'This report is finalised.'}, status=status.HTTP_409_CONFLICT)
    _fill(report)
    report.save()
    audit_write(request, 'UPDATE', 'records/term-report-prefill', report.pk, {'student': str(report.student_id)})
    return Response(report_payload(report))


@api_view(['POST'])
@permission_classes([RecordStaff])
def report_finalise(request, pk):
    report, error = _report_or_error(request, pk)
    if error:
        return error
    if report.is_locked:
        return Response({'detail': 'This report is already finalised.'}, status=status.HTTP_409_CONFLICT)
    missing = [label for label, v in (('学級', report.class_name), ('学級担任者', report.teacher_name)) if not v]
    if missing:
        return Response({'detail': 'Fill in: ' + '、'.join(missing)}, status=status.HTTP_400_BAD_REQUEST)
    report.finalised_at, report.finalised_by = timezone.now(), request.user
    report.save()
    audit_write(request, 'UPDATE', 'records/term-report-finalise', report.pk, {'student': str(report.student_id)})
    return Response(report_payload(report))


@api_view(['POST'])
@permission_classes([RecordStaff])
def report_reopen(request, pk):
    report, error = _report_or_error(request, pk)
    if error:
        return error
    if _role(request.user) != 'admin':
        return Response({'detail': 'Only an administrator can re-open a finalised report.'}, status=status.HTTP_403_FORBIDDEN)
    reason = str((request.data or {}).get('reason') or '').strip()
    if not report.is_locked:
        return Response({'detail': 'This report is not finalised.'}, status=status.HTTP_400_BAD_REQUEST)
    if not reason:
        return Response({'reason': 'Write why it is being re-opened.'}, status=status.HTTP_400_BAD_REQUEST)
    report.finalised_at = report.finalised_by = None
    report.save()
    audit_write(request, 'UPDATE', 'records/term-report-reopen', report.pk, {'student': str(report.student_id), 'reason': reason})
    return Response(report_payload(report))
