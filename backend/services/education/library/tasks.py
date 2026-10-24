from celery import shared_task


def send_all_reminders() -> dict:
    """Library notices for every school: books due tomorrow, overdue books, and holds nobody collected. Each is a library
    notification, so it also reaches phones that have turned push on."""
    from services.core.tenants.context import use_tenant
    from services.core.tenants.models import School

    from .api import send_reminders

    totals = {'due_tomorrow': 0, 'overdue': 0, 'holds_expired': 0}
    for school in School.objects.filter(is_active=True):
        with use_tenant(school):
            for k, v in send_reminders().items():
                totals[k] += v
    return totals


@shared_task(name='services.education.library.tasks.send_library_reminders')
def send_library_reminders():
    return send_all_reminders()
