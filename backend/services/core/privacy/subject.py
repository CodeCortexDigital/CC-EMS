"""Everything the school holds about one student: a copy to hand over, and an erasure that can be shown before it is done.

*Copy* (a "see my data" request). Built from the database's own relations, not a hand-kept list: every table that points at the
student is included, so a module added later is covered without anyone remembering to add it. Passwords, tokens and secrets are never
written, files appear as their names, and nothing from another student or another school can come along (rows are matched to this
student, and the student must belong to the school asking).

*Erasure* (an "erase my data" request). The student's name, contacts, ID numbers, address, health notes, documents, face template,
risk scores and portal login are removed; guardians are removed unless they have another child here (``retention._anonymise_student``).
Marks, attendance and invoices stay without a name, so the school's statistics and accounts still add up. A preview says what will
happen before anything is touched, and the person doing it must type the student's ID.
"""
from __future__ import annotations

import datetime
import decimal
import uuid

from django.db import transaction
from django.db.models import FileField

MAX_ROWS_PER_TABLE = 5000
SKIP_FIELD_PARTS = ('password', 'token', 'secret', 'hash', 'apikey', 'api_key', 'auth_key', 'p256dh')


def _value(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat()
    if isinstance(v, (decimal.Decimal, uuid.UUID)):
        return str(v)
    if isinstance(v, (list, dict)):
        return v
    return str(v)


def _row(obj) -> dict:
    out = {}
    for f in obj._meta.concrete_fields:
        if any(part in f.name.lower() for part in SKIP_FIELD_PARTS):
            continue
        raw = getattr(obj, f.attname, None)
        if isinstance(f, FileField):
            out[f.name] = getattr(raw, 'name', '') or ''        # the file's name only, never its bytes
        else:
            out[f.attname] = _value(raw)
    return out


def related_tables(student):
    """[(label, queryset)] for every table that points at this student."""
    found = []
    for rel in type(student)._meta.related_objects:
        model = rel.related_model
        if rel.many_to_many or not (rel.one_to_many or rel.one_to_one) or model._meta.auto_created:
            continue
        found.append((model._meta.label, model._base_manager.filter(**{rel.field.name: student})))
    return sorted(found, key=lambda pair: pair[0])


def export_student(student) -> dict:
    """The copy handed to the person who asked: the student's own record and every row about them, by table."""
    tables, counts = {}, {}
    for label, qs in related_tables(student):
        total = qs.count()
        if not total:
            continue
        tables[label] = [_row(o) for o in qs[:MAX_ROWS_PER_TABLE]]
        counts[label] = total
    return {
        'about': {'student_id': student.student_id, 'name': student.full_name},
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'record': _row(student),
        'tables': tables,
        'row_counts': counts,
        'notes': 'Files are listed by name only. Passwords, tokens and keys are never included. Tables with no rows are left out.',
    }


def erase_preview(student) -> dict:
    """What an erasure would do, without doing it."""
    from services.core.security.retention import ERASED_PREFIX

    kept = {'education_attendance.AttendanceRecord', 'education_exams.ExamResult', 'education_finance.Invoice',
            'education_gradebook.Score', 'behaviour.BehaviourRating'}
    removed, anonymised = {}, {}
    gone_labels = {'education_students.StudentHealth', 'education_students.Immunization', 'education_students.StudentDocument',
                   'education_students.StudentGuardian', 'education_attendance.StudentFaceEncoding', 'analytics.StudentRisk',
                   'analytics.AcademicPrediction', 'analytics.Recommendation'}
    for label, qs in related_tables(student):
        n = qs.count()
        if not n:
            continue
        if label in gone_labels:
            removed[label] = n
        elif label in kept:
            anonymised[label] = n
    return {
        'student': {'student_id': student.student_id, 'name': student.full_name},
        'already_erased': student.full_name.startswith(ERASED_PREFIX),
        'becomes': f'{ERASED_PREFIX} {student.student_id}',
        'removed': removed,
        'kept_without_a_name': anonymised,
        'also': ['Name, contact details, ID numbers, address and birth date (kept as year only) are cleared.',
                 'Guardians with no other child in the school are cleared.', 'The portal login is switched off.'],
    }


def erase_student(student) -> dict:
    """Do it. Safe to run twice."""
    from services.core.security.retention import _anonymise_student

    preview = erase_preview(student)
    with transaction.atomic():
        _anonymise_student(student)
    return preview
