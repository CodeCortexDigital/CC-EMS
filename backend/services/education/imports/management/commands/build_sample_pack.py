"""Rebuild the sample US school pack (CSV files and a zip) from its fixed seed.

    USE_SQLITE=1 SQLITE_PATH=/tmp/pack.sqlite3 python manage.py migrate
    USE_SQLITE=1 SQLITE_PATH=/tmp/pack.sqlite3 python manage.py build_sample_pack --out ../sample-data/us-school

Uses a scratch school that is rolled back, so it leaves nothing behind, but it needs a migrated database (use a scratch
one, not a school's live database).
"""
import hashlib
import io
import json
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand

from services.education.imports import sample_pack
from services.education.imports.specs import KINDS

README = """# Maple Grove Academy: sample US school (K-8)

A complete, invented private school as a CC-EMS data pack: {students} students in nine classes (Kindergarten to Grade 8),
{staff} staff, a clash-free timetable, three months of fees and payments, attendance, exams, payroll, leave, admissions
applications, health records, HR records and the school calendar. Names and numbers are made up. Dates are school year 2026-27,
loaded up to 2 October 2026.

## Use it

* **In the app:** Settings > Import data > Load data, choose `us-school-pack.zip`, pick **Add and update**, check the preview, Import.
  Use **Restore** on a brand new, empty school.
* **From the command line:** `python manage.py load_pack ../sample-data/us-school --school "Maple Grove Academy"`
* **Demo school with logins:** `python manage.py seed_demo --pack us-school`

## Files (loaded in this order)

{files}

All files are plain CSV (UTF-8). People refer to each other by student number (`MG26-001`), employee number (`E-001`),
class name, subject code and invoice number, never by internal ids.

Rebuild with `python manage.py build_sample_pack` (same seed gives the same files).
"""


class Command(BaseCommand):
    help = 'Rebuild the sample US school pack.'

    def add_arguments(self, parser):
        parser.add_argument('--out', default='../sample-data/us-school')
        parser.add_argument('--seed', type=int, default=2026)

    def handle(self, *args, **opts):
        out = Path(opts['out'])
        out.mkdir(parents=True, exist_ok=True)
        files = sample_pack.build(opts['seed'])
        order = sorted(files, key=lambda k: (KINDS[k]['order'], k))
        manifest = {'pack_version': 1, 'school': sample_pack.SCHOOL, 'files': {}}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for kind in order:
                text = sample_pack.to_csv(kind, files[kind])
                name = KINDS[kind]['filename']
                data = text.encode('utf-8')
                (out / name).write_bytes(data)
                zf.writestr(name, data)
                manifest['files'][name] = {'kind': kind, 'rows': len(files[kind]), 'sha256': hashlib.sha256(data).hexdigest()}
            zf.writestr('manifest.json', json.dumps(manifest, indent=2))
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        (out / 'us-school-pack.zip').write_bytes(buf.getvalue())
        listing = '\n'.join(f'{i}. `{KINDS[k]["filename"]}`: {KINDS[k]["label"]} ({len(files[k])} rows)' for i, k in enumerate(order, 1))
        (out / 'README.md').write_text(README.format(students=len(files['students']), staff=len(files['staff']), files=listing), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Wrote {len(order)} files and us-school-pack.zip to {out}'))
