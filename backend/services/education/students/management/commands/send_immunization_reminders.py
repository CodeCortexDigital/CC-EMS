"""Tell parents when a child's next immunisation dose is due (or overdue). Run daily.

Each due date is reminded once: the record remembers which due date it last reminded for, so running this every day
never repeats itself, and entering a new due date starts a fresh reminder.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone

from services.core.tenants.context import use_tenant
from services.education.students.health_api import notify_parents
from services.education.students.models import Immunization


class Command(BaseCommand):
    help = 'Remind parents of immunisations that are due soon or overdue (once per due date).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='How many days ahead to remind (default 30).')

    def handle(self, *args, **opts):
        today = timezone.localdate()
        horizon = today + timedelta(days=opts['days'])
        due = (Immunization.all_objects
               .filter(next_due_date__isnull=False, next_due_date__lte=horizon, exempt=False, student__is_active=True)
               .exclude(reminder_sent_on=F('next_due_date'))
               .select_related('student', 'student__tenant'))
        reminded = checked = 0
        for record in due:
            checked += 1
            student = record.student
            when = 'is overdue' if record.next_due_date < today else f'is due on {record.next_due_date:%B %d, %Y}'
            with use_tenant(student.tenant):
                told = notify_parents(student, 'Immunization reminder',
                                      f"{student.full_name}'s next {record.vaccine} dose {when}. "
                                      'Please send the updated record to the school office.')
            record.reminder_sent_on = record.next_due_date  # also stops daily repeats when nobody has a login yet
            record.save(update_fields=['reminder_sent_on'])
            reminded += 1 if told else 0
        self.stdout.write(f'{checked} due; parents notified for {reminded}.')
