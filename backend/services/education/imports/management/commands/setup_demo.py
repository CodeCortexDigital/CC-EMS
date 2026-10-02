"""Make a hosted demo site: the four demo accounts and the sample US school, and nothing else.

    python manage.py setup_demo                # loads Maple Grove Academy if it is not there yet (safe to run on every start)
    python manage.py setup_demo --reset        # first deletes ALL schools, people and data, then loads it again
    DEMO_RESET=1 python manage.py setup_demo   # same as --reset (set it for one deploy, then remove it)

Refuses to run on the live site (APP_ENV=production): the demo accounts have publicly known passwords. Run it on staging or
a demo site (APP_ENV=staging).
"""
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from services.core.security.defaults import refuse_on_live

SCHOOL_CODE = 'MGA'
KEEP_SCHOOL = 'DEF'   # the empty default school the system uses as a placeholder


def wipe_school(school, say=lambda *_: None):
    """Delete everything one school owns (like the account-deletion path), then its memberships."""
    from services.core.portability.data import school_querysets
    from services.core.tenants.models import TenantMembership

    sets = list(school_querysets(school))
    for _ in range(8):
        blocked = []
        for label, Model, qs in sets:
            try:
                with transaction.atomic():
                    qs.delete()
            except (ProtectedError, IntegrityError):
                blocked.append((label, Model, qs))
        if not blocked:
            break
        sets = blocked
    TenantMembership.objects.filter(school=school).delete()


def wipe_everything(say=lambda *_: None):
    """Every school (except the empty default one) and every account. A clean slate for the demo."""
    from services.core.tenants.models import School

    schools = list(School.objects.exclude(tenant_code=KEEP_SCHOOL))
    for school in schools:
        say(f'Deleting {school.name}...')
        wipe_school(school)
        school.delete()
    n = get_user_model().objects.all().delete()[0]
    say(f'Removed {len(schools)} school(s) and the accounts ({n} records).')


class Command(BaseCommand):
    help = 'Set up the demo site: the demo accounts and the sample US school only.'

    def add_arguments(self, parser):
        parser.add_argument('--pack', default='us-school')
        parser.add_argument('--reset', action='store_true', help='Delete every school and account first')

    def handle(self, *args, **opts):
        refuse_on_live('setup_demo')
        from services.core.tenants.models import School
        from services.education.students.models import Student

        reset = opts['reset'] or os.environ.get('DEMO_RESET', '').strip().lower() in ('1', 'true', 'yes')
        if reset:
            wipe_everything(self.stdout.write)
        school = School.objects.filter(tenant_code=SCHOOL_CODE).first()
        if school is not None and Student.all_objects.filter(tenant=school).exists():
            self.stdout.write(self.style.SUCCESS('Demo school is already loaded. Nothing to do.'))
            return
        call_command('seed_sample_users', '--force')
        call_command('seed_demo', '--pack', opts['pack'], '--reset', stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS('Demo site ready. Log in as admin@code.com / Admin@123.'))
