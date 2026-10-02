"""Tell each school's administrators about contracts, probations and credentials that are about to end.

Run it daily (cron or the scheduler): ``python manage.py send_hr_alerts --days 30``. A school's administrators get at
most one such notification per day, so running it twice is harmless.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from services.core.tenants.context import use_tenant
from services.core.tenants.models import School, TenantMembership
from services.core.user_notifications.models import Notification
from services.education.hr.records import alerts

TITLE = 'Staff contracts and credentials need attention'


class Command(BaseCommand):
    help = 'Notify school administrators about expiring staff contracts, probations and credentials.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Look this many days ahead (default 30)')

    def handle(self, *args, **opts):
        sent = 0
        today = timezone.localdate()
        for school in School.objects.all():
            with use_tenant(school):
                rows = alerts(opts['days'], today)
                if not rows:
                    continue
                expired = sum(1 for r in rows if r['expired'])
                lines = [f"{r['teacher_name']}: {r['what']} {'ended' if r['expired'] else 'ends'} {r['date']:%d %b %Y}"
                         for r in rows[:8]]
                text = (f'{len(rows)} item(s) need attention' + (f', {expired} already expired' if expired else '') + '.\n'
                        + '\n'.join(lines) + ('\n...and more in Staff & HR.' if len(rows) > 8 else ''))
                admins = TenantMembership.objects.filter(school=school, role='admin', is_active=True).select_related('user')
                for m in admins:
                    already = Notification.objects.filter(
                        recipient=m.user, title=TITLE, created_at__date=today).exists()
                    if not already:
                        Notification.objects.create(recipient=m.user, title=TITLE, message=text, notification_type='system',
                                                    tenant=school)
                        sent += 1
        self.stdout.write(self.style.SUCCESS(f'Sent {sent} notification(s).'))
