from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Library: due-tomorrow reminders, overdue notices and expired holds (run once a day from cron).'

    def handle(self, *args, **options):
        from ...tasks import send_all_reminders

        totals = send_all_reminders()
        self.stdout.write(f"{totals['due_tomorrow']} due-tomorrow reminder(s), {totals['overdue']} overdue notice(s), "
                          f"{totals['holds_expired']} hold(s) released.")
