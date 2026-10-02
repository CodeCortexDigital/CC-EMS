"""Spreadsheet import: templates, a preview that checks every row, the import itself, an exporter and a history.
/api/v1/auth/imports/   (whole-school packs are in pack_api.py)"""
from __future__ import annotations

import csv

from django.db import transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from services.core.accounts.permissions import IsSchoolAdmin

from . import engine
from .models import ImportRun
from .specs import KINDS

MAX_ROWS = engine.MAX_ROWS


def _kind(kind):
    spec = KINDS.get(kind)
    if spec is None:
        return None, Response({'error': 'Unknown import.'}, status=status.HTTP_404_NOT_FOUND)
    return spec, None


def _describe(kind, spec):
    return {'kind': kind, 'label': spec['label'], 'help': spec['help'], 'order': spec['order'], 'file': spec.get('filename', f'{kind}.csv'),
            'depends': spec.get('depends', []), 'tier': spec.get('tier', 1), 'can_update': spec.get('update') is not None,
            'can_export': spec.get('export') is not None,
            'columns': [{'key': k, 'label': label, 'required': req} for k, label, req, _ in spec['columns']]}


def csv_response(filename, header, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('﻿')  # Excel opens UTF-8 CSVs correctly with a BOM
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return response


def header_of(spec):
    return [label + (' *' if req else '') for _, label, req, _ in spec['columns']]


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def kinds(request):
    runs = {r.kind: r for r in reversed(list(ImportRun.objects.all()[:200]))}
    out = []
    for kind, spec in sorted(KINDS.items(), key=lambda kv: kv[1]['order']):
        d = _describe(kind, spec)
        last = runs.get(kind)
        d['last_import'] = {'when': last.created_at, 'added': last.added} if last else None
        out.append(d)
    return Response({'kinds': out, 'max_rows': MAX_ROWS, 'modes': list(engine.MODES)})


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def template(request, kind):
    spec, error = _kind(kind)
    if error:
        return error
    return csv_response(f'import-{kind}.csv', header_of(spec), spec['example'])


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def export_kind(request, kind):
    """This school's records of one kind, in exactly the layout the importer reads."""
    spec, error = _kind(kind)
    if error:
        return error
    if spec.get('export') is None:
        return Response({'error': 'This kind cannot be exported yet.'}, status=status.HTTP_404_NOT_FOUND)
    return csv_response(spec.get('filename', f'{kind}.csv'), header_of(spec), spec['export']({'school': request.tenant}))


def _mode(request):
    mode = (request.data.get('mode') or request.query_params.get('mode') or 'add').lower()
    return mode if mode in engine.MODES else 'add'


def _check(request, kind):
    spec, error = _kind(kind)
    if error:
        return None, error
    upload = request.FILES.get('file')
    if upload is None:
        return None, Response({'error': 'Choose a CSV or Excel file.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        rows = engine.read_rows(upload.name, upload.read())
    except ValueError as exc:
        return None, Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        return None, Response({'error': 'The file could not be read. Save it as CSV or .xlsx and try again.'}, status=status.HTTP_400_BAD_REQUEST)
    mode = _mode(request)
    if mode == 'restore' and not _school_is_empty(request.tenant):
        return None, Response({'error': 'Restore is for an empty school. This school already has students or staff; use "Add and update" instead.'},
                              status=status.HTTP_409_CONFLICT)
    result, message = engine.check_rows(kind, spec, rows, request.tenant, mode)
    if message:
        return None, Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
    engine.apply_plan_limit(kind, request.tenant, result['rows'])
    result.update(name=upload.name, mode=mode)
    return result, None


def _school_is_empty(school):
    from django.apps import apps
    return not (apps.get_model('education_students', 'Student').objects.exists() or apps.get_model('education_academics', 'Teacher').objects.exists())


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
@parser_classes([MultiPartParser, FormParser])
def preview(request, kind):
    result, error = _check(request, kind)
    if error:
        return error
    rows = [{k: v for k, v in r.items() if k != '_clean'} for r in result['rows']]
    return Response({'file': result['name'], 'mode': result['mode'], 'columns': result['columns'], 'unknown_columns': result['unknown'],
                     'summary': engine.summary(result['rows']), 'rows': rows})


def record_run(request, kind, name, rows, mode):
    return record_run_for(request.tenant, request.user, kind, name, rows, mode)


def record_run_for(school, user, kind, name, rows, mode):
    problems = engine.problems_of(rows)
    summary = engine.summary(rows)
    return ImportRun.objects.create(
        tenant=school, kind=kind, file_name=name[:255], created_by=user, rows=len(rows), added=summary['ready'],
        updated=summary['update'], mode=mode, skipped=summary['duplicate'], failed=summary['error'], problems=problems[:1000])


def run_message(run):
    return (f'{run.added} added' + (f', {run.updated} updated' if run.updated else '') + (f', {run.skipped} already existed' if run.skipped else '')
            + (f', {run.failed} had problems' if run.failed else '') + '.')


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
@parser_classes([MultiPartParser, FormParser])
def commit(request, kind):
    """Saves every ready row (and updates, in update mode) in one go (all or nothing); other rows are skipped and reported."""
    result, error = _check(request, kind)
    if error:
        return error
    spec, rows = result['spec'], result['rows']
    try:
        with transaction.atomic():
            engine.apply_rows(spec, result)
    except engine.ApplyError as exc:  # nothing is saved; tell the office which row stopped it
        return Response({'error': f'Nothing was imported: row {exc.row} could not be saved ({str(exc)[:200]}). Fix it and try again.'},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({'error': f'Nothing was imported: {str(exc)[:200]}. Fix the file and try again.'}, status=status.HTTP_400_BAD_REQUEST)
    run = record_run(request, kind, result['name'], rows, result['mode'])
    return Response({'id': str(run.id), 'added': run.added, 'updated': run.updated, 'skipped': run.skipped, 'failed': run.failed,
                     'problems': engine.problems_of(rows), 'message': run_message(run)})


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def history(request):
    return Response({'results': [{
        'id': str(r.id), 'kind': r.kind, 'label': KINDS.get(r.kind, {}).get('label', r.kind), 'file': r.file_name, 'mode': r.mode,
        'when': r.created_at, 'by': (getattr(r.created_by, 'full_name', '') or getattr(r.created_by, 'email', '')) if r.created_by else '',
        'rows': r.rows, 'added': r.added, 'updated': r.updated, 'skipped': r.skipped, 'failed': r.failed, 'has_problems': bool(r.problems),
    } for r in ImportRun.objects.select_related('created_by')[:50]]})


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def problems_csv(request, run_id):
    run = ImportRun.objects.filter(pk=run_id).first()
    if run is None:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    spec = KINDS.get(run.kind, {'columns': []})
    keys = [k for k, *_ in spec['columns']]
    return csv_response(f'import-{run.kind}-problems.csv', ['Row', 'Problem'] + [label for _, label, *_ in spec['columns']],
                        [[p['row'], '; '.join(p['messages'])] + [p['values'].get(k, '') for k in keys] for p in run.problems])
