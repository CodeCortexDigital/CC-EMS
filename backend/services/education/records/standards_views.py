"""MEXT education data standards: the school's MEXT school code and the IDs other systems use for our students and teachers.

Administrators only. The school code is checked for its shape (a letter and twelve digits, like B113110000012); it is not checked against MEXT's
published list. External IDs let an import or export from another system (a board of education's school-affairs system, a learning portal) be matched
by ID instead of by name. The curriculum code (学習指導要領コード) of a subject is a field on the subject itself (``Subject.curriculum_code``).
"""
from __future__ import annotations

import csv
import io
import re

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from services.core.accounts.decorators import get_user_role
from services.core.tenants.context import get_current_tenant
from services.education.academics.models import Teacher
from services.education.students.access import audit_write
from services.education.students.models import Student

from .models import ExternalId

SCHOOL_CODE = re.compile(r'^[A-Z]\d{12}$')
MAX_ROWS = 5000


class SchoolAdmin(BasePermission):
    message = 'Only a school administrator can use this.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and get_user_role(request.user) == 'admin' and get_current_tenant() is not None)


@api_view(['GET', 'PUT'])
@permission_classes([SchoolAdmin])
def standards(request):
    """GET: the school's MEXT school code. PUT ``{"school_code": "B113110000012"}`` (an empty string clears it)."""
    from services.core.tenants.models import School

    school = get_current_tenant()
    if request.method == 'PUT':
        code = str((request.data or {}).get('school_code') or '').strip().upper().replace(' ', '')
        if code and not SCHOOL_CODE.match(code):
            return Response({'school_code': 'The MEXT school code is a letter and twelve digits, for example B113110000012.'}, status=status.HTTP_400_BAD_REQUEST)
        was = (school.settings_json or {}).get('mext_school_code', '')
        school = School.objects.get(pk=school.pk)
        sj = dict(school.settings_json or {})
        if code:
            sj['mext_school_code'] = code
        else:
            sj.pop('mext_school_code', None)
        school.settings_json = sj
        school.save(update_fields=['settings_json'])
        audit_write(request, 'UPDATE', 'records/mext-school-code', school.pk, {'was': was, 'now': code})
    return Response({'school_code': (school.settings_json or {}).get('mext_school_code', ''), 'systems': sorted(ExternalId.objects.order_by('system').values_list('system', flat=True).distinct())})


def _row(e: ExternalId) -> dict:
    person = e.student if e.kind == 'student' else e.teacher
    return {'id': str(e.pk), 'kind': e.kind, 'local_id': (person.student_id if e.kind == 'student' else person.employee_id) if person else '',
            'name': person.full_name if person else '', 'system': e.system, 'external_id': e.external_id}


def _parse_csv(text: str) -> list[dict]:
    """Rows of ``kind,local_id,external_id`` (a header line is allowed; ``kind`` may be 'student' or 'teacher')."""
    rows = []
    for line in csv.reader(io.StringIO(text.lstrip('﻿'))):
        cells = [c.strip() for c in line]
        if not any(cells) or cells[0].lower() in ('kind', '種別'):
            continue
        rows.append({'kind': cells[0].lower(), 'local_id': cells[1] if len(cells) > 1 else '', 'external_id': cells[2] if len(cells) > 2 else ''})
    return rows


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([SchoolAdmin])
def external_ids(request):
    """GET ``?system=`` (and ``&export=csv``): the IDs. POST ``{system, rows | csv}``: set many (a person's ID in that system is replaced).
    DELETE ``?id=``: remove one."""
    if request.method == 'DELETE':
        e = get_object_or_404(ExternalId, pk=request.GET.get('id'))
        e.delete()
        audit_write(request, 'DELETE', 'records/external-id', e.pk, {'system': e.system})
    result = {}
    if request.method == 'POST':
        d = request.data or {}
        system = str(d.get('system') or '').strip()[:80]
        if not system:
            return Response({'system': 'Name the system these IDs belong to (for example the board of education\'s system).'}, status=status.HTTP_400_BAD_REQUEST)
        rows = _parse_csv(str(d['csv'])) if d.get('csv') else list(d.get('rows') or [])
        if not rows:
            return Response({'rows': 'There are no rows to save.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(rows) > MAX_ROWS:
            return Response({'rows': f'At most {MAX_ROWS} rows at a time.'}, status=status.HTTP_400_BAD_REQUEST)
        saved, errors = 0, []
        for i, r in enumerate(rows, start=1):
            kind, local, ext = str(r.get('kind') or '').lower(), str(r.get('local_id') or '').strip(), str(r.get('external_id') or '').strip()[:60]
            if kind not in ('student', 'teacher') or not local or not ext:
                errors.append({'row': i, 'message': 'Each row needs kind (student or teacher), our ID and the other system\'s ID.'})
                continue
            person = (Student.objects.filter(student_id=local).first() if kind == 'student' else Teacher.objects.filter(employee_id=local).first())
            if person is None:
                errors.append({'row': i, 'message': f'No {kind} with the ID {local}.'})
                continue
            try:
                with transaction.atomic():
                    ExternalId.objects.update_or_create(**{kind: person, 'system': system}, defaults={'kind': kind, 'external_id': ext, 'updated_by': request.user})
                saved += 1
            except IntegrityError:
                errors.append({'row': i, 'message': f'The ID {ext} is already used for someone else in {system}.'})
        audit_write(request, 'UPDATE', 'records/external-ids', None, {'system': system, 'saved': saved, 'errors': len(errors), 'at': timezone.now().isoformat()})
        result = {'saved': saved, 'errors': errors}
    qs = ExternalId.objects.select_related('student', 'teacher')
    if request.GET.get('system') or (request.method == 'POST' and request.data.get('system')):
        qs = qs.filter(system=request.GET.get('system') or str(request.data.get('system')).strip()[:80])
    rows_ = [_row(e) for e in qs[:MAX_ROWS]]
    if request.method == 'GET' and request.GET.get('export') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="external-ids.csv"'
        resp.write('﻿')
        w = csv.writer(resp)
        w.writerow(['kind', 'local_id', 'name', 'system', 'external_id'])
        for r in rows_:
            w.writerow([r['kind'], r['local_id'], r['name'], r['system'], r['external_id']])
        return resp
    return Response({'results': rows_, 'systems': sorted(ExternalId.objects.order_by('system').values_list('system', flat=True).distinct()), **result})
