"""Run the daily admissions jobs: expire seat offers (and offer those seats on), and send tour and document reminders."""
from django.core.management.base import BaseCommand

from services.education.admissions import jobs


class Command(BaseCommand):
    help = 'Expire waiting-list offers, then send tour and missing-document reminders.'

    def handle(self, *args, **options):
        result = jobs.run()
        self.stdout.write(', '.join(f'{k.replace("_", " ")}: {v}' for k, v in result.items()))
