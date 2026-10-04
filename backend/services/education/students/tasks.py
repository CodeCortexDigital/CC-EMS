from celery import shared_task

from services.core.tasks.scheduled_jobs import run_command


@shared_task(name='services.education.students.tasks.immunization_reminders')
def immunization_reminders():
    """Remind parents of immunisations that are due soon or overdue, once per due date."""
    return run_command('send_immunization_reminders')
