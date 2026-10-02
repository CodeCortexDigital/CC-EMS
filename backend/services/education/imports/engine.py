"""The import engine, shared by the single-file importer and the whole-school data pack.

One kind of record is handled in three steps: read the rows and match the file's headings to the kind's columns, check
every row (nothing is saved), then apply the rows that are fine. A row is one of:

* ``ready``     - new; will be added
* ``update``    - already there (same natural key); will be updated (update mode only)
* ``duplicate`` - already there; left alone
* ``error``     - cannot be imported; says why
"""
from __future__ import annotations

import csv
import io
import re

from .specs import norm, text

MAX_ROWS = 20000
MAX_BYTES = 25 * 1024 * 1024
MODES = ('add', 'update', 'restore')


def read_rows(name: str, raw: bytes):
    """Rows as lists of cell values, from CSV or Excel bytes."""
    lower = (name or '').lower()
    if len(raw) > MAX_BYTES:
        raise ValueError(f'The file is larger than {MAX_BYTES // (1024 * 1024)} MB.')
    if lower.endswith(('.xlsx', '.xlsm')):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        return [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    if lower.endswith('.xls'):
        raise ValueError('Old .xls files are not supported. In Excel choose File > Save As > .xlsx or CSV.')
    content = None
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = content[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(content), dialect)]


def map_headers(header, spec):
    """Which column of the file feeds which field. Returns (mapping, unknown_headings, missing_required_labels)."""
    lookup = {}
    for key, label, _req, aliases in spec['columns']:
        for name in [key, label, *aliases]:
            lookup.setdefault(norm(name.replace('*', '')), key)
    mapping, unknown = {}, []
    for i, h in enumerate(header):
        k = lookup.get(norm(text(h).replace('*', '')))
        if k and k not in mapping.values():
            mapping[i] = k
        elif text(h):
            unknown.append(text(h))
    missing = [label for key, label, req, _ in spec['columns'] if req and key not in mapping.values()]
    return mapping, unknown, missing


def check_rows(kind, spec, rows, school, mode='add'):
    """Check every row of one kind. Returns (result dict, error message or None). Nothing is saved.

    `result` has `rows` (each with `_clean`), `columns`, `unknown`, and `ctx` (the state the apply step needs)."""
    rows = [r for r in rows if any(text(c) for c in r)]
    if not rows:
        return None, 'The file is empty.'
    mapping, unknown, missing = map_headers(rows[0], spec)
    if missing:
        return None, (f'Missing column{"s" if len(missing) > 1 else ""}: {", ".join(missing)}. '
                      f'Download the template to see the headings.')
    body = rows[1:]
    if len(body) > MAX_ROWS:
        return None, f'Up to {MAX_ROWS} rows at a time; this file has {len(body)}. Split it into smaller files.'
    ctx = {'school': school, 'mode': mode}
    updating = mode in ('update', 'restore') and spec.get('update') is not None
    checked = []
    for n, raw in enumerate(body, start=2):
        row = {key: (raw[i] if i < len(raw) else None) for i, key in mapping.items()}
        clean, errors, duplicate, note = spec['check'](row, ctx)
        state = 'error' if errors else 'duplicate' if duplicate else 'ready'
        if state == 'duplicate' and updating:
            state, note = 'update', (note + ' ' if note else '') + f'Updates the existing record ({duplicate})'
        checked.append({'row': n, 'state': state, 'messages': errors or ([duplicate] if duplicate and state != 'update' else []),
                        'note': note, 'values': {k: text(v) for k, v in row.items()}, '_clean': clean})
    return {'spec': spec, 'rows': checked, 'unknown': unknown, 'ctx': ctx,
            'columns': [{'key': k, 'label': label} for k, label, _r, _a in spec['columns'] if k in mapping.values()]}, None


def apply_plan_limit(kind, school, checked):
    """The school's plan limit on students and staff (P11): extra new rows become errors."""
    if kind not in ('students', 'staff'):
        return
    from services.core.billing.service import room_left

    left = room_left(school, kind)
    if left is not None:
        for r in [r for r in checked if r['state'] == 'ready'][left:]:
            r['state'], r['messages'] = 'error', [f'Over your plan limit ({left} more {kind} allowed). Upgrade in Settings > Plan & billing.']


def summary(rows):
    return {s: sum(1 for r in rows if r['state'] == s) for s in ('ready', 'update', 'duplicate', 'error')}


class ApplyError(Exception):
    """A row that passed the check could not be saved; `row` is its line number in the file."""

    def __init__(self, row, cause):
        super().__init__(str(cause))
        self.row = row


def apply_rows(spec, result):
    """Save the ready rows and apply the updates. Call inside a transaction; raises ApplyError naming the row that failed."""
    ctx = result['ctx']
    for r in result['rows']:
        try:
            if r['state'] == 'ready':
                spec['create'](r['_clean'], ctx)
            elif r['state'] == 'update':
                spec['update'](r['_clean'], ctx)
        except Exception as exc:
            raise ApplyError(r['row'], exc) from exc
    finish = spec.get('finish')
    if finish:
        finish(ctx)


def problems_of(rows):
    return [{'row': r['row'], 'state': r['state'], 'messages': r['messages'], 'values': r['values']}
            for r in rows if r['state'] in ('error', 'duplicate')]


def slug(name: str) -> str:
    """A file name's stem, reduced for matching to a kind: 'Class Subjects (1).csv' -> 'classsubjects1'."""
    stem = re.sub(r'\.[A-Za-z0-9]+$', '', (name or '').split('/')[-1])
    return norm(stem)
