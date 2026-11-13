"""A OneRoster 1.1 roster export (CSV bulk, as a zip) for a learning portal or another system that reads OneRoster.

    GET /api/v1/education/records/oneroster/            the zip (administrators)
    GET /api/v1/education/records/oneroster/?preview=1  the counts and what is left out, without the files

What is in it: the school (with its MEXT school code as the identifier, when set), the school years and terms, the subjects as courses, each class
as a homeroom class plus one scheduled class for each subject it has, students and teachers as users, and their enrolments (students in their
class's homeroom and subject classes; teachers in the classes they are the homeroom teacher of or are timetabled for).

What is left out on purpose: parents and guardians, and every contact detail (phone, address, email) unless ``?contacts=1`` is given, because
the receiving system seldom needs them. Passwords are never included. Every download is recorded in the activity log.

Not covered: OneRoster's results, categories, line items and demographics files, and the xAPI Japan Profile for learning logs (a different format
for a different system, which also needs a learning record store).
"""
from __future__ import annotations

import csv
import io
import zipfile

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from services.core.tenants.context import get_current_tenant
from services.core.tenants.localization import school_locale
from services.education.academics.models import AcademicYear, ClassSubject, SchoolClass, Subject, Teacher, TimetableEntry, Term
from services.education.students.access import audit_write
from services.education.students.models import Student

from .standards_views import SchoolAdmin

FILES = {
    'orgs': ['sourcedId', 'status', 'dateLastModified', 'name', 'type', 'identifier', 'parentSourcedId'],
    'academicSessions': ['sourcedId', 'status', 'dateLastModified', 'title', 'type', 'startDate', 'endDate', 'parentSourcedId', 'schoolYear'],
    'courses': ['sourcedId', 'status', 'dateLastModified', 'schoolYearSourcedId', 'title', 'courseCode', 'grades', 'orgSourcedId', 'subjects', 'subjectCodes'],
    'classes': ['sourcedId', 'status', 'dateLastModified', 'title', 'grades', 'courseSourcedId', 'classCode', 'classType', 'location', 'schoolSourcedId',
                'termSourcedIds', 'subjects', 'subjectCodes', 'periods'],
    'users': ['sourcedId', 'status', 'dateLastModified', 'enabledUser', 'orgSourcedIds', 'role', 'username', 'userIds', 'givenName', 'familyName',
              'middleName', 'identifier', 'email', 'sms', 'phone', 'agentSourcedIds', 'grades', 'password'],
    'enrollments': ['sourcedId', 'status', 'dateLastModified', 'classSourcedId', 'schoolSourcedId', 'userSourcedId', 'role', 'primary', 'beginDate', 'endDate'],
}


def grade_code(level) -> str:
    """OneRoster grade codes: PK, KG, 01-12."""
    if level is None:
        return ''
    return 'PK' if level == -1 else 'KG' if level == 0 else f'{int(level):02d}' if 1 <= int(level) <= 12 else ''


def split_name(full: str, family_first: bool) -> tuple[str, str]:
    """(given, family). Japanese names are written family name first; others given name first."""
    parts = (full or '').split()
    if len(parts) <= 1:
        return (parts[0] if parts else ''), (parts[0] if parts else '')
    return (' '.join(parts[1:]), parts[0]) if family_first else (parts[0], ' '.join(parts[1:]))


def _day(value) -> str:
    return value.isoformat() if value else ''


def build(school, contacts: bool = False) -> tuple[dict[str, list[list]], dict]:
    """The rows of each file, and a report of the counts and what was left out."""
    now = timezone.now().date().isoformat()
    family_first = school_locale(school)['language'] == 'ja'
    sid = str(school.pk)
    rows: dict[str, list[list]] = {k: [] for k in FILES}
    skipped = {'students_without_class': 0, 'teachers_inactive': 0}

    code = ((school.settings_json or {}).get('mext_school_code') or '')
    rows['orgs'].append([sid, 'active', now, school.name, 'school', code, ''])

    years = list(AcademicYear.objects.all())
    for y in years:
        rows['academicSessions'].append([str(y.id), 'active', now, y.name, 'schoolYear', _day(y.start_date), _day(y.end_date), '', y.start_date.year])
    year_by_id = {y.id: y for y in years}
    for t in Term.objects.all():
        y = year_by_id.get(t.academic_year_id)
        if y is None:
            continue
        rows['academicSessions'].append([str(t.id), 'active', now, t.name, 'term', _day(getattr(t, 'start_date', None)), _day(getattr(t, 'end_date', None)), str(y.id), y.start_date.year])

    subjects = list(Subject.objects.filter(is_active=True))
    for s in subjects:
        rows['courses'].append([str(s.id), 'active', now, '', s.name, s.code, '', sid, s.name, s.curriculum_code])
    subject_by_id = {s.id: s for s in subjects}

    classes = list(SchoolClass.objects.filter(is_active=True))
    by_class: dict = {}
    for c in classes:
        grades = grade_code(c.grade_level)
        rows['classes'].append([str(c.id), 'active', now, c.name, grades, '', c.code, 'homeroom', '', sid, str(c.academic_year_id or ''), '', '', ''])
        by_class[c.id] = {'home': str(c.id), 'subject_classes': []}
    for cs in ClassSubject.objects.filter(class_ref__in=[c.id for c in classes]).select_related('class_ref', 'subject'):
        subj = subject_by_id.get(cs.subject_id)
        if subj is None:
            continue
        c = cs.class_ref
        rows['classes'].append([str(cs.id), 'active', now, f'{c.name} {subj.name}', grade_code(c.grade_level), str(subj.id), f'{c.code}-{subj.code}', 'scheduled', '', sid,
                                str(c.academic_year_id or ''), subj.name, subj.curriculum_code, ''])
        by_class[c.id]['subject_classes'].append(str(cs.id))

    teachers = list(Teacher.objects.filter(is_active=True))
    skipped['teachers_inactive'] = Teacher.objects.filter(is_active=False).count()
    for t in teachers:
        given, family = split_name(t.full_name, family_first)
        rows['users'].append([str(t.id), 'active', now, 'true', sid, 'teacher', t.employee_id, '', given, family, '', t.employee_id,
                              t.email if contacts else '', '', t.phone if contacts else '', '', '', ''])
    teacher_ids = {t.id for t in teachers}

    students = list(Student.objects.filter(is_active=True))
    for st in students:
        given, family = split_name(st.full_name, family_first)
        grade = grade_code(next((c.grade_level for c in classes if c.id == st.current_class_id), None))
        rows['users'].append([str(st.id), 'active', now, 'true', sid, 'student', st.student_id, '', given, family, '', st.student_id,
                              st.email if contacts else '', '', st.phone if contacts else '', '', grade, ''])
        info = by_class.get(st.current_class_id)
        if info is None:
            skipped['students_without_class'] += 1
            continue
        for cid in [info['home']] + info['subject_classes']:
            rows['enrollments'].append([f'{cid}:{st.id}', 'active', now, cid, sid, str(st.id), 'student', 'false', '', ''])

    for c in classes:
        if c.homeroom_teacher_id in teacher_ids:
            rows['enrollments'].append([f'{c.id}:{c.homeroom_teacher_id}', 'active', now, str(c.id), sid, str(c.homeroom_teacher_id), 'teacher', 'true', '', ''])
    seen = set()
    for e in TimetableEntry.objects.filter(is_active=True, teacher__in=teacher_ids).select_related('class_subject'):
        key = (e.class_subject_id, e.teacher_id)
        if key in seen:
            continue
        seen.add(key)
        rows['enrollments'].append([f'{e.class_subject_id}:{e.teacher_id}', 'active', now, str(e.class_subject_id), sid, str(e.teacher_id), 'teacher', 'false', '', ''])

    report = {'files': {k: len(v) for k, v in rows.items()}, 'skipped': skipped,
              'left_out': ['Parents and guardians', 'Phone numbers, addresses and passwords'] + ([] if contacts else ['Email addresses']),
              'contacts_included': contacts, 'school_code': code}
    return rows, report


def to_zip(rows: dict[str, list[list]], school) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        def write(name, header, body):
            out = io.StringIO()
            w = csv.writer(out, lineterminator='\r\n')
            w.writerow(header)
            w.writerows(body)
            z.writestr(f'{name}.csv', out.getvalue().encode('utf-8'))

        manifest = [['manifest.version', '1.0'], ['oneroster.version', '1.1']] + [[f'file.{k}', 'bulk'] for k in FILES] + [
            ['file.categories', 'absent'], ['file.demographics', 'absent'], ['file.lineItems', 'absent'], ['file.results', 'absent'],
            ['source.systemName', 'CC-EMS'], ['source.systemCode', str(school.pk)]]
        write('manifest', ['propertyName', 'value'], manifest)
        for name, header in FILES.items():
            write(name, header, rows[name])
    return buf.getvalue()


@api_view(['GET'])
@permission_classes([SchoolAdmin])
def export(request):
    school = get_current_tenant()
    contacts = request.GET.get('contacts') == '1'
    rows, report = build(school, contacts)
    if request.GET.get('preview') == '1':
        return Response(report)
    resp = HttpResponse(to_zip(rows, school), content_type='application/zip')
    resp['Content-Disposition'] = 'attachment; filename="oneroster.zip"'
    audit_write(request, 'EXPORT', 'education/records/oneroster', None, {'files': report['files'], 'contacts_included': contacts})
    return resp
