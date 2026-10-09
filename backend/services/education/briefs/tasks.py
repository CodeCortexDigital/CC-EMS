from celery import shared_task

from . import service


@shared_task(name='services.education.briefs.tasks.run_due_briefs')
def run_due_briefs():
    """Every 15 minutes: prepare the morning brief and evening summary when their time has come in each school's own time zone,
    make sure the latest weekly, fortnightly and monthly roll-ups exist, and delete anything older than about three months."""
    return service.run_due()
