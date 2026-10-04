"""Helper for the school's scheduled jobs.

Each job is a Celery task in its own app's ``tasks.py`` (so Celery finds it) that runs the management command an
administrator could run by hand, for example ``python manage.py admissions_daily``. Try a job by hand before trusting
it to the schedule. The schedule is ``CELERY_BEAT_SCHEDULE`` in ``erp_core/settings.py``; a Celery worker and Beat must
be running for jobs to fire.
"""
import logging

from django.core.management import call_command

logger = logging.getLogger('erp.jobs')


def run_command(command: str, **options) -> dict:
    """Run one management command. A failure is logged with the command's name and returned, never raised, so one broken
    job cannot stop the others."""
    try:
        call_command(command, **options)
        return {'command': command, 'ok': True}
    except Exception:
        logger.exception('Scheduled job %s failed', command)
        return {'command': command, 'ok': False}
