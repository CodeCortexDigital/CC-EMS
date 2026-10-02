"""Write docs/DATA_PACK_SPEC.md from the import kinds (so the document cannot drift from the code).

    python manage.py pack_spec_doc --out ../docs/DATA_PACK_SPEC.md
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from services.education.imports.specs import KINDS

INTRO = """# School data pack: file format

A data pack is a **zip of CSV files**, one file per kind of record. The same files are used to **load** data (Settings > Import data),
to **export** a school, and to **restore** one. This page is generated from the code (`python manage.py pack_spec_doc`), so it is exact.

## Rules for every file

* UTF-8 CSV with a header row (a byte-order mark is fine, so Excel opens it). `.xlsx` is accepted for single files.
* Headings are matched ignoring case, spaces and punctuation, and a trailing `*` is ignored. Alternative headings are listed below.
* Columns marked **required** must have a value. Other columns may be empty.
* Dates are `2026-09-26` (also `26/09/2026`). Times are `08:30`. Yes/no columns accept yes, no, y, n, true, false, 1, 0. Amounts are plain
  numbers (`2500` or `2500.50`; `$` and thousands separators are ignored).
* Records refer to each other by **natural keys people already use**: class name, subject code, student number, employee number,
  invoice number, exam code. Never by internal ids. A reference can only find records of the same school.
* Files load in the order below, so a file can refer to records in the files before it. A file whose references are missing fails
  row by row; the other files still load.
* A file is all-or-nothing: if a row that passed the check cannot be saved, nothing from that file is saved.
* Passwords, tokens and keys are never in a pack. People get new random logins when created.

## Modes

| Mode | What happens to a record that already exists (same key) |
|------|------------------------------------------------------|
| Add only | Left alone. New records are added. |
| Add and update | Updated with the cells you filled in. Empty cells never erase what is there. |
| Restore | Same as update, and only allowed into a school with no students and no staff. |

Every upload is checked first (Preview) and nothing is saved until you press Import. Packs with many rows run in the background.

## Version and manifest

`manifest.json` (written by the exporter, optional on upload) holds `pack_version`, the school name, and for each file its kind, row
count and SHA-256 checksum. A pack with a newer `pack_version` than the system is refused, and a file that does not match its checksum is
refused (delete `manifest.json` to load an edited pack).

## Files
"""


class Command(BaseCommand):
    help = 'Write the data pack specification as Markdown.'

    def add_arguments(self, parser):
        parser.add_argument('--out', default='../docs/DATA_PACK_SPEC.md')

    def handle(self, *args, **opts):
        lines = [INTRO]
        order = sorted(KINDS, key=lambda k: (KINDS[k]['order'], k))
        lines.append('| # | File | What it holds | Needs first |\n|---|------|---------------|-------------|')
        for i, k in enumerate(order, 1):
            s = KINDS[k]
            lines.append(f'| {i} | `{s["filename"]}` | {s["label"]} | {", ".join(s.get("depends", [])) or "nothing"} |')
        for k in order:
            s = KINDS[k]
            lines += ['', f'### `{s["filename"]}`: {s["label"]}', '', s['help'], '']
            key = s.get('key')
            if key:
                labels = {c[0]: c[1] for c in s['columns']}
                lines.append(f'A record is identified by: {", ".join(labels.get(x, x) for x in key)}.')
                lines.append('')
            lines.append('| Column | Required | Also accepted as |')
            lines.append('|--------|----------|------------------|')
            for key_, label, req, aliases in s['columns']:
                lines.append(f'| {label} | {"yes" if req else ""} | {", ".join(aliases)} |')
            lines += ['', 'Update mode: ' + ('supported.' if s.get('update') else 'not supported (existing records are left alone).'),
                      'Export: ' + ('yes.' if s.get('export') else 'no.')]
            if s.get('example'):
                lines += ['', 'Example row: `' + ', '.join(str(c) for c in s['example'][0]) + '`']
        out = Path(opts['out'])
        out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Wrote {out}'))
