"""Load a data pack into a school.

    python manage.py load_pack ../sample-data/us-school --school "Maple Grove Academy"
    python manage.py load_pack school-export.zip --school "My School" --mode restore

The school is created if it does not exist. ``--mode`` is add, update (the default) or restore.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from services.core.security.defaults import refuse_on_live
from services.education.imports import loader


def get_or_create_school(name):
    from services.core.tenants.models import School

    school = School.objects.filter(name=name).first()
    if school is None:
        code = ''.join(w[0] for w in name.split())[:3].upper().ljust(3, 'X')
        n = 0
        while School.objects.filter(tenant_code=code).exists():
            n += 1
            code = f'{code[:2]}{n}'[:3]
        school = School.objects.create(tenant_code=code, name=name, subdomain=slugify(name)[:60] or 'school', is_active=True)
    return school


class Command(BaseCommand):
    help = 'Load a data pack (folder of CSV files or a zip) into a school.'

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--school', required=True, help='School name; created when it does not exist')
        parser.add_argument('--mode', default='update', choices=['add', 'update', 'restore'])

    def handle(self, *args, **opts):
        refuse_on_live('load_pack')
        school = get_or_create_school(opts['school'])
        try:
            results = loader.load(opts['path'], school, opts['mode'], out=self.stdout.write)
        except ValueError as exc:
            raise CommandError(str(exc))
        total = sum(r['ready'] for r in results.values())
        problems = sum(r['error'] for r in results.values())
        self.stdout.write(self.style.SUCCESS(f'Loaded {total} records into {school.name}.') if not problems
                          else self.style.WARNING(f'Loaded {total} records into {school.name}; {problems} rows had problems (listed above).'))
