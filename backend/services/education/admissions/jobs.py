"""The daily admissions jobs: close expired seat offers, remind families about tours, and about missing documents."""
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone

from . import waitlist
from .waitlist import portal_link
from .models import Application, TourBooking
from .views import _settings

OPEN_STATUSES = ('pending', 'reviewing', 'approved', 'waitlisted')
DOCUMENT_REMINDER_GAP = timedelta(days=7)


def _mail(to, subject, body):
    if to:
        try:
            send_mail(subject, body, None, [to], fail_silently=True)
        except Exception:
            pass


def remind_tours(now):
    """One reminder per booking, the day before. Returns how many were sent."""
    sent = 0
    due = TourBooking.objects.filter(status='booked', reminder_sent_at__isnull=True, slot__starts_at__gt=now,
                                     slot__starts_at__lte=now + timedelta(hours=26)).select_related('slot', 'application__applicant')
    for booking in due:
        app, slot = booking.application, booking.slot
        _mail(app.applicant.email, f'Reminder: your {slot.get_kind_display().lower()} tomorrow',
              f'This is a reminder of your {slot.get_kind_display().lower()} on {timezone.localtime(slot.starts_at):%A, %B %d at %I:%M %p}.\n{slot.location}')
        booking.reminder_sent_at = now
        booking.save(update_fields=['reminder_sent_at'])
        sent += 1
    return sent


def remind_documents(now):
    """Email each family that still owes documents, at most once a week. Returns how many families were reminded."""
    from .ext_api import checklist

    sent = 0
    apps_ = Application.objects.filter(status__in=OPEN_STATUSES).select_related('applicant')
    for app in apps_:
        if app.docs_reminded_at and now - app.docs_reminded_at < DOCUMENT_REMINDER_GAP:
            continue
        school = app.applicant.tenant
        todo = [i for i in checklist(app, school) if i['state'] in ('missing', 'redo')]
        if not todo:
            continue
        lines = '\n'.join(f"- {i['name']}" + (f" (please send again: {i['note']})" if i['state'] == 'redo' else '') for i in todo)
        _mail(app.applicant.email, f'Documents still needed: application {app.application_no}',
              f'We still need these documents for {app.applicant.full_name}:\n{lines}\n\n'
              f'Send them here: {portal_link(app)}\n\nApplication number: {app.application_no}\nTracking code: {app.tracking_token}')
        app.docs_reminded_at = now
        app.save(update_fields=['docs_reminded_at'])
        sent += 1
    return sent


def run(now=None):
    now = now or timezone.now()
    return {'offers_expired': waitlist.expire_due(now), 'tour_reminders': remind_tours(now), 'document_reminders': remind_documents(now)}
