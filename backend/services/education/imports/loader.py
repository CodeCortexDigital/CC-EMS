"""Load a data pack (a folder of CSV files, or a zip) into a school from the command line.

The same engine as the upload screen: every file is checked, then applied in dependency order, one file at a time.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from django.db import transaction

from . import engine
from .specs import KINDS, norm


def read_pack(path):
    """{kind: rows} from a folder or a zip of CSV files, plus the names that matched nothing."""
    path = Path(path)
    names = {}
    for kind, spec in KINDS.items():
        for n in (spec.get('filename', f'{kind}.csv'), kind, spec['label']):
            names.setdefault(engine.slug(n) if '.' in n else norm(n), kind)
    blobs = {}
    if path.is_dir():
        for f in sorted(path.iterdir()):
            if f.is_file() and f.suffix.lower() in ('.csv', '.xlsx'):
                blobs[f.name] = f.read_bytes()
    elif path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as zf:
            for i in zf.infolist():
                base = i.filename.split('/')[-1]
                if not i.is_dir() and base.lower().endswith(('.csv', '.xlsx')):
                    blobs[base] = zf.read(i)
    else:
        raise ValueError('Give a folder of CSV files or a .zip pack.')
    files, unknown = {}, []
    for name, data in blobs.items():
        kind = names.get(engine.slug(name))
        if kind is None:
            unknown.append(name)
        else:
            files[kind] = engine.read_rows(name, data)
    return files, unknown


def load(path, school, mode='update', out=None):
    """Check and apply every file in the pack for `school`. Returns {kind: summary}, raising on a file that cannot be read."""
    from services.core.tenants.context import use_tenant

    files, unknown = read_pack(path)
    say = out or (lambda *_: None)
    if unknown:
        say(f'Skipped (no matching kind): {", ".join(unknown)}')
    results = {}
    with use_tenant(school):
        for kind in sorted(files, key=lambda k: (KINDS[k]['order'], k)):
            spec = KINDS[kind]
            result, message = engine.check_rows(kind, spec, files[kind], school, mode)
            if message:
                raise ValueError(f'{spec["filename"]}: {message}')
            rows = result['rows']
            bad = [r for r in rows if r['state'] == 'error']
            with transaction.atomic():
                engine.apply_rows(spec, result)
            results[kind] = engine.summary(rows)
            say(f'{spec["filename"]:<28} {results[kind]["ready"]:>5} new  {results[kind]["update"]:>4} updated  '
                f'{results[kind]["duplicate"]:>4} existed  {results[kind]["error"]:>3} problems')
            for r in bad[:3]:
                say(f'    row {r["row"]}: {"; ".join(r["messages"])}')
    return results
