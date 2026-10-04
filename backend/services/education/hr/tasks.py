from celery import shared_task

from services.core.tasks.scheduled_jobs import run_command


@shared_task(name='services.education.hr.tasks.hr_alerts')
def hr_alerts():
    """Contracts, probation and licences that are about to end."""
    return run_command('send_hr_alerts')


@shared_task(name='services.education.hr.tasks.refresh_cover')
def refresh_cover():
    """Look again for substitute cover for open lessons."""
    return run_command('refresh_cover')
