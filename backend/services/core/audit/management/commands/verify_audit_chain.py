import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from services.core.audit import chain
from services.core.audit.models import AuditLog


def _newest_saved(path: Path) -> dict:
    """The newest line saved for each chain in the keep-file ({chain: {at, seq, hash}})."""
    newest = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                item = json.loads(line)
                newest[item['chain']] = item
            except (ValueError, KeyError):
                continue
    return newest


class Command(BaseCommand):
    help = ('Check the tamper-evident trail of AI and risk-review decisions. Prints the newest hash of each school. Keep those hashes '
            'somewhere the database administrator cannot change: with --keep-file the command appends them to a file (put it on another '
            'machine, in a ticket, or in write-once storage) and, next time, checks the old hashes are still in the trail, which also '
            'catches a rewrite of a whole chain. Run it on a schedule.')

    def add_arguments(self, parser):
        parser.add_argument('--chain', help='Check one school (its id) instead of all.')
        parser.add_argument('--keep-file', help='A file to compare against and append the newest hashes to (one JSON line per school per run).')

    def handle(self, *args, **options):
        result = chain.verify(options.get('chain'))
        problems = list(result['problems'])
        keep = Path(options['keep_file']) if options.get('keep_file') else None
        self.stdout.write(f"Checked {result['records']} record(s) in {result['chains']} chain(s).")
        for name, head in result['heads'].items():
            self.stdout.write(f'  {name}: newest hash {head or "(none)"}')
        if keep is not None:
            for name, saved in _newest_saved(keep).items():
                if options.get('chain') and name != options['chain']:
                    continue
                row = AuditLog._base_manager.filter(chain=name, seq=saved['seq']).exclude(entry_hash='').first()
                if row is None or row.entry_hash != saved['hash']:
                    problems.append(f"{name}: record {saved['seq']}, whose hash was kept on {saved['at']}, is no longer the same "
                                    f"(the history before that date was rewritten or removed)")
        if problems:
            for problem in problems:
                self.stderr.write(self.style.ERROR(problem))
            raise CommandError('The trail does not verify.')
        if keep is not None:
            now = timezone.now().isoformat()
            with keep.open('a', encoding='utf-8') as f:
                for name, head in result['heads'].items():
                    last = AuditLog._base_manager.filter(chain=name).exclude(entry_hash='').order_by('-seq').values_list('seq', flat=True).first()
                    if head and last:
                        f.write(json.dumps({'at': now, 'chain': name, 'seq': last, 'hash': head}) + '\n')
            self.stdout.write(f'Newest hashes appended to {keep}.')
        self.stdout.write(self.style.SUCCESS('The trail verifies: nothing was changed, removed or inserted.'))
