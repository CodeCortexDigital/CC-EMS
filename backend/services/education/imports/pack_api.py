"""The school data pack: one zip of CSV files that is both what a school uploads and what it can download.
/api/v1/auth/imports/pack/

* ``spec/``      what files exist, their columns, and the order they load in
* ``template/``  an empty pack (headings and one example row per file) to fill in
* ``export/``    this school's data as a pack, in exactly the layout the importer reads
* ``preview/``   check a pack (a zip, or a single CSV with ``kind``) without saving anything
* ``import/``    load a pack
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import threading
import zipfile

from django.conf import settings
from django.db import connection, transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from services.core.accounts.permissions import IsSchoolAdmin

from . import engine
from .api import _describe, _mode, _school_is_empty, header_of, record_run_for, run_message
from .models import ImportJob
from .specs import KINDS, norm

PACK_VERSION = 1
MAX_UNZIPPED = 150 * 1024 * 1024
README = """CC-EMS school data pack (version {version})

One CSV file per kind of record. Fill in the files you need and upload the whole zip (or one file at a time) under
Settings > Import data. Files load in this order, so a file can refer to records in the files before it:

{order}

Rules
- Keep the headings. Columns marked * are required; other columns may be left empty.
- Records refer to each other by what people write: class name, subject code, student number, employee number, invoice number.
- Dates are 2026-09-26. Yes/no columns accept yes or no. Amounts are plain numbers (2500 or 2500.50).
- Nothing is saved until you choose Import; Preview shows every row and what is wrong with it.
- Modes: "Add only" skips records that already exist; "Add and update" also updates them (empty cells are left as they are);
  "Restore" is for an empty school.
"""


def _ordered(kinds=None):
    names = [k for k in KINDS if kinds is None or k in kinds]
    return sorted(names, key=lambda k: (KINDS[k]['order'], k))


def _file_name(kind):
    return KINDS[kind].get('filename', f'{kind}.csv')


def _csv_bytes(header, rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return ('﻿' + out.getvalue()).encode('utf-8')


def _kind_by_file():
    """Every name a file may use for each kind: its file name, the kind key and its label, all reduced the same way."""
    out = {}
    for kind, spec in KINDS.items():
        for name in (_file_name(kind), kind, spec['label']):
            out.setdefault(engine.slug(name) if '.' in name else norm(name), kind)
    return out


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def pack_spec(request):
    return Response({'version': PACK_VERSION, 'kinds': [_describe(k, KINDS[k]) for k in _ordered()], 'max_rows': engine.MAX_ROWS,
                     'modes': list(engine.MODES)})


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def pack_template(request):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        order = _ordered()
        zf.writestr('README.txt', README.format(version=PACK_VERSION, order='\n'.join(
            f'{i}. {_file_name(k)}  -  {KINDS[k]["label"]}: {KINDS[k]["help"]}' for i, k in enumerate(order, 1))))
        for k in order:
            zf.writestr(_file_name(k), _csv_bytes(header_of(KINDS[k]), KINDS[k]['example']))
    return _zip(buf, 'ccems-data-pack-template.zip')


def _zip(buf, name):
    response = HttpResponse(buf.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{name}"'
    return response


def build_pack(school, kinds=None, with_files=False):
    """(zip bytes, manifest) for the school's data in pack format."""
    buf = io.BytesIO()
    files = {}
    ctx_base = {'school': school}
    for k in _ordered(kinds):
        spec = KINDS[k]
        if spec.get('export') is None:
            continue
        rows = spec['export'](dict(ctx_base))
        files[_file_name(k)] = (k, _csv_bytes(header_of(spec), rows), len(rows))
    manifest = {'pack_version': PACK_VERSION, 'school': getattr(school, 'name', ''), 'created': timezone.now().isoformat(),
                'files': {n: {'kind': k, 'rows': c, 'sha256': hashlib.sha256(b).hexdigest()} for n, (k, b, c) in files.items()}}
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('manifest.json', json.dumps(manifest, indent=2))
        zf.writestr('README.txt', README.format(version=PACK_VERSION, order='\n'.join(
            f'{i}. {n}  -  {KINDS[k]["label"]}' for i, (n, (k, _b, _c)) in enumerate(files.items(), 1))))
        for n, (_k, b, _c) in files.items():
            zf.writestr(n, b)
    return buf, manifest


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def pack_export(request):
    wanted = [k for k in (request.query_params.get('kinds') or '').split(',') if k in KINDS] or None
    buf, manifest = build_pack(request.tenant, wanted)
    stamp = timezone.localdate().isoformat()
    return _zip(buf, f'{(manifest["school"] or "school").replace(" ", "-").lower()}-data-pack-{stamp}.zip')


def _unpack(upload, kind):
    """{kind: rows} from a zip, or from one CSV/Excel file when `kind` is given. Returns (files, unknown, name, error)."""
    raw = upload.read()
    name = upload.name or 'upload'
    if name.lower().endswith('.zip'):
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            return None, [], name, 'That is not a valid zip file.'
        infos = [i for i in zf.infolist() if not i.is_dir() and '__MACOSX' not in i.filename and not i.filename.split('/')[-1].startswith('.')]
        if sum(i.file_size for i in infos) > MAX_UNZIPPED:
            return None, [], name, 'The zip is too large when unpacked.'
        manifest = None
        by_name = {i.filename.split('/')[-1].lower(): i for i in infos}
        if 'manifest.json' in by_name:
            try:
                manifest = json.loads(zf.read(by_name['manifest.json']).decode('utf-8'))
            except ValueError:
                return None, [], name, 'manifest.json in the zip is not valid.'
            if int(manifest.get('pack_version', 1)) > PACK_VERSION:
                return None, [], name, 'This pack was made by a newer version of the system. Update the system, or export it again.'
        names, files, unknown = _kind_by_file(), {}, []
        for i in infos:
            base = i.filename.split('/')[-1]
            if base.lower() in ('manifest.json', 'readme.txt'):
                continue
            k = names.get(engine.slug(base))
            if k is None:
                unknown.append(base)
                continue
            data = zf.read(i)
            if manifest and base in manifest.get('files', {}) and manifest['files'][base].get('sha256') != hashlib.sha256(data).hexdigest():
                return None, [], name, f'{base} was changed after the pack was made (its checksum does not match). Export again, or remove manifest.json to load it anyway.'
            try:
                files[k] = engine.read_rows(base, data)
            except ValueError as exc:
                return None, [], name, f'{base}: {exc}'
            except Exception:
                return None, [], name, f'{base} could not be read. Save it as CSV and try again.'
        if not files:
            return None, unknown, name, 'No file in the zip matches a kind of record. Download the template to see the file names.'
        return files, unknown, name, None
    if kind not in KINDS:
        return None, [], name, 'Say which kind of records this file holds, or upload a zip pack.'
    try:
        return {kind: engine.read_rows(name, raw)}, [], name, None
    except ValueError as exc:
        return None, [], name, str(exc)
    except Exception:
        return None, [], name, 'The file could not be read. Save it as CSV or .xlsx and try again.'


def run_pack(school, user, files, mode, commit, on_progress=None, whole_transaction=True):
    """Check and apply every file in order. A preview (and a small load) runs inside one transaction that is rolled back
    unless `commit`; a big load commits file by file so its progress can be seen."""
    results = []
    order = sorted(files, key=lambda k: (KINDS[k]['order'], k))
    with (transaction.atomic() if whole_transaction else contextlib.nullcontext()):
        for i, kind in enumerate(order):
            if on_progress:
                on_progress(i, len(order), KINDS[kind]['label'])
            spec = KINDS[kind]
            result, message = engine.check_rows(kind, spec, files[kind], school, mode)
            if message:
                results.append({'kind': kind, 'label': spec['label'], 'file': _file_name(kind), 'error': message})
                continue
            engine.apply_plan_limit(kind, school, result['rows'])
            failure = None
            try:
                with transaction.atomic():      # one kind is all-or-nothing; the pack carries on without it
                    engine.apply_rows(spec, result)
            except engine.ApplyError as exc:
                failure = f'Nothing from this file was saved: row {exc.row} could not be saved ({str(exc)[:200]}).'
            except Exception as exc:
                failure = f'Nothing from this file was saved: {str(exc)[:200]}.'
            rows = result['rows']
            if failure:
                for r in rows:
                    if r['state'] in ('ready', 'update'):
                        r['state'], r['messages'] = 'error', [failure]
            shown = [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows if r['state'] in ('error', 'duplicate')]
            shown += [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows if r['state'] in ('ready', 'update')][:25]
            item = {'kind': kind, 'label': spec['label'], 'file': _file_name(kind), 'summary': engine.summary(rows), 'rows': shown,
                    'truncated': len(shown) < len(rows), 'unknown_columns': result['unknown'], 'columns': result['columns']}
            if failure:
                item['error'] = failure
            if commit and not failure:
                run = record_run_for(school, user, kind, _file_name(kind), rows, mode)
                item['run_id'] = str(run.id)
                item['message'] = run_message(run)
            results.append(item)
        if whole_transaction and not commit:
            transaction.set_rollback(True)
    totals = {s: sum(r.get('summary', {}).get(s, 0) for r in results) for s in ('ready', 'update', 'duplicate', 'error')}
    return results, totals


def _pack_request(request, commit):
    upload = request.FILES.get('file')
    if upload is None:
        return Response({'error': 'Choose a zip pack, or a CSV or Excel file.'}, status=status.HTTP_400_BAD_REQUEST)
    mode = _mode(request)
    if mode == 'restore' and not _school_is_empty(request.tenant):
        return Response({'error': 'Restore is for an empty school. This school already has students or staff; use "Add and update" instead.'},
                        status=status.HTTP_409_CONFLICT)
    files, unknown, name, error = _unpack(upload, request.data.get('kind') or request.query_params.get('kind'))
    if error:
        return Response({'error': error, 'unknown_files': unknown}, status=status.HTTP_400_BAD_REQUEST)
    rows = sum(max(0, len(r) - 1) for r in files.values())
    if rows > getattr(settings, 'IMPORT_JOB_ROWS', 400):
        job = _start_job(request, files, mode, commit, name, unknown)
        return Response({'job': _job_json(job)}, status=status.HTTP_202_ACCEPTED)
    results, totals = run_pack(request.tenant, request.user, files, mode, commit)
    return Response(_payload(name, mode, commit, results, totals, unknown))


def _payload(name, mode, commit, results, totals, unknown):
    return {'file': name, 'mode': mode, 'committed': commit, 'kinds': results, 'totals': totals, 'unknown_files': unknown,
            'order': [r['kind'] for r in results]}


# ---- big packs run in the background ---------------------------------------------------------------------------------

def _job_json(job):
    return {'id': str(job.id), 'status': job.status, 'file': job.file_name, 'mode': job.mode, 'commit': job.commit,
            'total_files': job.total_files, 'files_done': job.files_done, 'current': job.current, 'error': job.error,
            'result': job.result if job.status == 'done' else None}


def _execute_job(job_id, school, user, files, mode, commit, name, unknown, threaded):
    from services.core.tenants.context import use_tenant

    job = ImportJob._base_manager.get(pk=job_id)

    def progress(i, total, label):
        job.files_done, job.total_files, job.current = i, total, label
        job.save(update_fields=['files_done', 'total_files', 'current'])

    try:
        with use_tenant(school):
            results, totals = run_pack(school, user, files, mode, commit, on_progress=progress, whole_transaction=not commit)
        job.result, job.status, job.files_done = _payload(name, mode, commit, results, totals, unknown), 'done', len(files)
    except Exception as exc:
        job.status, job.error = 'failed', str(exc)[:500]
    job.current, job.finished_at = '', timezone.now()
    job.save()
    if threaded:
        connection.close()


def _start_job(request, files, mode, commit, name, unknown):
    job = ImportJob.objects.create(tenant=request.tenant, file_name=name[:255], mode=mode, commit=commit, total_files=len(files),
                                   created_by=request.user)
    args = (job.id, request.tenant, request.user, files, mode, commit, name, unknown)
    if getattr(settings, 'IMPORT_JOBS_INLINE', False):       # tests and single-process set-ups: do it now
        _execute_job(*args, threaded=False)
        job.refresh_from_db()
    else:
        threading.Thread(target=_execute_job, args=(*args, True), daemon=True).start()
    return job


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def pack_job(request, job_id):
    job = ImportJob.objects.filter(pk=job_id).first()
    if job is None:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if job.status == 'running' and timezone.now() - job.created_at > timezone.timedelta(minutes=45):
        job.status, job.error, job.finished_at = 'failed', 'The server restarted or the job took too long. Nothing more will be saved; check the History tab.', timezone.now()
        job.save()
    return Response(_job_json(job))


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
@parser_classes([MultiPartParser, FormParser])
def pack_preview(request):
    return _pack_request(request, commit=False)


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
@parser_classes([MultiPartParser, FormParser])
def pack_import(request):
    return _pack_request(request, commit=True)
