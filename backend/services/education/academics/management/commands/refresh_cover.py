"""Keep cover for approved leave up to date: add what is missing and try again for periods that were left open.

Run it daily (cron or the scheduler): ``python manage.py refresh_cover --days 14``. Safe to run as often as you like.
"""
from django.core.management.base import BaseCommand

from services.core.tenants.context import use_tenant
from services.core.tenants.models import School
from services.education.academics.substitution import refresh_cover


class Command(BaseCommand):
    help = 'Arrange cover for approved leave in the next N days, for every school.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=14)

    def handle(self, *args, **opts):
        total = 0
        for school in School.objects.all():
            with use_tenant(school):
                total += refresh_cover(opts['days'])
        self.stdout.write(self.style.SUCCESS(f'Checked {total} approved leave(s).'))
