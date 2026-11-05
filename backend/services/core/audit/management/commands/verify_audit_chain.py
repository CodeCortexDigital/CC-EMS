from django.core.management.base import BaseCommand, CommandError

from services.core.audit import chain


class Command(BaseCommand):
    help = ('Check the tamper-evident trail of AI and risk-review decisions. Prints the newest hash of each school; copy those somewhere '
            'outside the database now and then, so that a rewrite of a whole chain can also be spotted.')

    def add_arguments(self, parser):
        parser.add_argument('--chain', help='Check one school (its id) instead of all.')

    def handle(self, *args, **options):
        result = chain.verify(options.get('chain'))
        self.stdout.write(f"Checked {result['records']} record(s) in {result['chains']} chain(s).")
        for name, head in result['heads'].items():
            self.stdout.write(f'  {name}: newest hash {head or "(none)"}')
        if not result['ok']:
            for problem in result['problems']:
                self.stderr.write(self.style.ERROR(problem))
            raise CommandError('The trail does not verify.')
        self.stdout.write(self.style.SUCCESS('The trail verifies: nothing was changed, removed or inserted.'))
