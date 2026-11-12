"""Look over every school's audit log for unusual use of personal information and save new alerts (run from cron, for example every hour).

    python manage.py check_access_alerts
"""
from django.core.management.base import BaseCommand

from services.core.security import access_alerts
from services.core.tenants.models import School


class Command(BaseCommand):
    help = 'Raise alerts for bursts of student-record views, exports and refused requests.'

    def handle(self, *args, **opts):
        total = 0
        for school in School.objects.filter(is_active=True):
            n = access_alerts.detect(school)
            total += n
            if n:
                self.stdout.write(f'{school.name}: {n} new alert(s)')
        self.stdout.write(self.style.SUCCESS(f'{total} new alert(s) in all.'))
