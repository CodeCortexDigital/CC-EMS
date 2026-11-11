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
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from services.core.security.defaults import refuse_on_live

SCHOOL_CODE = 'MGA'   # the US sample school; a pack's own code comes from seed_demo
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


def keep_subscription_active(school):
    """A demo school's free trial must not run out while people are looking at it (a lapsed trial makes the school read-only).
    Each start puts the demo on an active plan with a year left. It is the plan that includes the AI assistant, so every demo login (teacher,
    parent, student) can use it and not only the platform owner's account, which skips plan checks."""
    from datetime import timedelta

    from django.utils import timezone

    from services.core.billing.models import Plan, Subscription

    now = timezone.now()
    changes = {'status': 'active', 'current_period_start': now, 'current_period_end': now + timedelta(days=365)}
    plan = Plan.objects.filter(code='premium').first()
    if plan is not None:
        changes['plan'] = plan
    Subscription.objects.filter(school=school).update(**changes)
    # A new school needs two different approvers (and the person who asked never counts). The demo has two administrators, so it starts with
    # one approval; the presenter can switch to two in AI settings (then a teacher asks and both administrators approve).
    saved = dict(school.settings_json or {})
    if 'ai_approval' not in saved:
        saved['ai_approval'] = {'required': 1, 'approvers': []}
        type(school).objects.filter(pk=school.pk).update(settings_json=saved)


def pack_code(pack: str) -> str:
    from services.core.accounts.management.commands.seed_demo import Command as SeedDemo
    return SeedDemo.PACKS.get(pack, {}).get('code', SCHOOL_CODE)


def add_demo_admin(school, email: str, password: str, name: str, say=lambda *_: None):
    """A named administrator for one client's demo, with a password only that client is told (it comes from the environment, never from the repository).

    The two public administrator logins (admin@code.com, deputy@code.com) are switched off on this site, so the only way in as administrator is this account.
    Runs on every start, so changing the password variable and redeploying changes the password.
    """
    from services.core.accounts.models import User
    from services.core.tenants.models import TenantMembership

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(email=email, password=password, full_name=name or email)
    else:
        user.set_password(password)
    user.account_status, user.email_verified = User.AccountStatus.ACTIVE, True
    if name:
        user.full_name = name
    user.save()
    TenantMembership.objects.filter(user=user).exclude(school=school).update(is_primary=False)
    member, _ = TenantMembership.objects.get_or_create(user=user, school=school, defaults={'role': 'admin', 'is_primary': True})
    if member.role != 'admin' or not member.is_primary:
        member.role, member.is_primary = 'admin', True
        member.save(update_fields=['role', 'is_primary'])
    User.objects.filter(email__in=('admin@code.com', 'deputy@code.com')).exclude(pk=user.pk).update(account_status=User.AccountStatus.INACTIVE)
    say(f'Administrator {email} is ready; the public administrator logins are switched off.')


class Command(BaseCommand):
    help = 'Set up the demo site: the demo accounts and one sample school (US by default; --pack jp-school for the Japanese one).'

    def add_arguments(self, parser):
        parser.add_argument('--pack', default=os.environ.get('DEMO_PACK', '').strip() or 'us-school')
        parser.add_argument('--reset', action='store_true', help='Delete every school and account first')

    def handle(self, *args, **opts):
        refuse_on_live('setup_demo')
        from services.core.tenants.models import School
        from services.education.students.models import Student

        reset = opts['reset'] or os.environ.get('DEMO_RESET', '').strip().lower() in ('1', 'true', 'yes')
        if reset:
            wipe_everything(self.stdout.write)
        code = pack_code(opts['pack'])
        admin_email = os.environ.get('DEMO_ADMIN_EMAIL', '').strip()
        admin_password = os.environ.get('DEMO_ADMIN_PASSWORD', '')
        if admin_email and not admin_password:
            raise CommandError('DEMO_ADMIN_EMAIL is set but DEMO_ADMIN_PASSWORD is not.')
        school = School.objects.filter(tenant_code=code).first()
        loaded = school is not None and Student.all_objects.filter(tenant=school).exists()
        if loaded:
            keep_subscription_active(school)
            self.stdout.write(self.style.SUCCESS('Demo school is already loaded. Its plan is kept active.'))
        else:
            call_command('seed_sample_users', '--force')
            call_command('seed_demo', '--pack', opts['pack'], '--reset', stdout=self.stdout)
            school = School.objects.filter(tenant_code=code).first()
            keep_subscription_active(school)
        if admin_email:
            add_demo_admin(school, admin_email, admin_password, os.environ.get('DEMO_ADMIN_NAME', '').strip(), self.stdout.write)
        elif not loaded:
            self.stdout.write(self.style.SUCCESS('Demo site ready. Log in as admin@code.com / Admin@123.'))
