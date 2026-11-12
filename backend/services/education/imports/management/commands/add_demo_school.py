"""Add one more sample school to a demo database that already has schools, with its own administrator.

    python manage.py add_demo_school --pack jp-school --admin-email masato@admin.com --admin-password '...' --admin-name 'Masato Yamano'
    python manage.py add_demo_school --pack jp-school --reset ...      # clears and reloads THIS school only

This is the multi-school case: every school keeps its own people and data (rows are tagged with their school and every query is limited to
the signed-in school). Nothing of the other schools, and none of the public demo logins, is touched. The new school gets four logins of its own:
the administrator you name (the password is yours), and a teacher, a parent and a student at ``<role>@<school>.example`` with the usual demo
passwords. Each school's region (country style: currency, date format, language, terms) is its own setting under Settings > Language & currency.

Refuses to run on the live site (APP_ENV=production).
"""
import os

from django.core.management.base import BaseCommand, CommandError

from services.core.security.defaults import refuse_on_live


def own_logins(subdomain: str, admin_email: str) -> dict:
    return {'admin': admin_email, 'deputy': None, 'teacher': f'teacher@{subdomain}.example', 'parent': f'parent@{subdomain}.example', 'student': f'student@{subdomain}.example'}


def ensure_users(logins: dict, admin_password: str, admin_name: str, say=lambda *_: None):
    from services.core.accounts.models import User

    spec = {'admin': (admin_password, admin_name or 'Administrator'), 'teacher': ('Teacher@123', 'Teacher'), 'parent': ('Parent@123', 'Parent'), 'student': ('Student@123', 'Student')}
    for role, (password, name) in spec.items():
        email = logins[role]
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=password, full_name=name)
        else:
            user.set_password(password)
            if role == 'admin' and admin_name:
                user.full_name = admin_name
        user.account_status, user.email_verified = User.AccountStatus.ACTIVE, True
        user.save()
        say(f'Login ready: {email}')


class Command(BaseCommand):
    help = 'Add a sample school (and its own logins) next to the schools already in this database.'

    def add_arguments(self, parser):
        parser.add_argument('--pack', required=True)
        parser.add_argument('--admin-email', default=os.environ.get('DEMO_EXTRA_ADMIN_EMAIL', '').strip())
        parser.add_argument('--admin-password', default=os.environ.get('DEMO_EXTRA_ADMIN_PASSWORD', ''))
        parser.add_argument('--admin-name', default=os.environ.get('DEMO_EXTRA_ADMIN_NAME', '').strip())
        parser.add_argument('--reset', action='store_true', help='Clear and reload this school only')

    def handle(self, *args, **opts):
        refuse_on_live('add_demo_school')
        from services.core.accounts.management.commands.seed_demo import Command as SeedDemo
        from services.core.tenants.models import School
        from services.education.imports.management.commands.setup_demo import add_demo_admin, keep_subscription_active

        pack = opts['pack']
        info = SeedDemo.PACKS.get(pack)
        if info is None:
            raise CommandError(f"Unknown pack '{pack}'. Available: {', '.join(SeedDemo.PACKS)}.")
        if not opts['admin_email'] or not opts['admin_password']:
            raise CommandError('Give --admin-email and --admin-password (or DEMO_EXTRA_ADMIN_EMAIL / DEMO_EXTRA_ADMIN_PASSWORD).')
        logins = own_logins(info['subdomain'], opts['admin_email'])
        ensure_users(logins, opts['admin_password'], opts['admin_name'], self.stdout.write)
        seeder = SeedDemo(stdout=self.stdout, stderr=self.stderr)
        seeder._seed_pack(pack, opts['reset'], logins=logins)
        school = School.objects.get(tenant_code=info['code'])
        keep_subscription_active(school)
        add_demo_admin(school, opts['admin_email'], opts['admin_password'], opts['admin_name'], self.stdout.write, switch_off_public=False)
