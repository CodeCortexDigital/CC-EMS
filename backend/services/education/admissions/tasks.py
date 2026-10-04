from celery import shared_task

from services.core.tasks.scheduled_jobs import run_command


@shared_task(name='services.education.admissions.tasks.admissions_daily')
def admissions_daily():
    """Expire seat offers (and offer those seats on), and send tour and document reminders."""
    return run_command('admissions_daily')
