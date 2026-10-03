"""The waiting list: who is next in line, offering a seat, and offering it on when it is declined or runs out.

A grade has a capacity for a year. Seats used = children approved or enrolled + offers still open, so the number of
seats left can never go below zero. When a seat is free the family at the front of the line is offered it, with a
deadline. If they decline, or the deadline passes, the next family is offered it automatically.

Line order: families with a sibling at the school first (if the grade is set to), then staff children (if set to),
then whoever joined the list first.
"""
import os
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Application, ApplicationEvent, Offer, WaitlistConfig, WaitlistEntry

SEAT_STATUSES = ('approved', 'enrolled')


def _mail(to, subject, body):
    if to:
        try:
            send_mail(subject, body, None, [to], fail_silently=True)
        except Exception:  # mail trouble must never stop the list moving
            pass


def _event(application, to_status, note):
    ApplicationEvent.objects.create(application=application, from_status=application.status, to_status=to_status, note=note, by_name='Waiting list')


def config_for(application):
    return WaitlistConfig.objects.filter(class_name__iexact=application.applicant.applying_for_class,
                                         academic_year=application.academic_year).first()


def _grade_applications(config):
    return Application.objects.filter(applicant__applying_for_class__iexact=config.class_name, academic_year=config.academic_year)


def seats_taken(config) -> int:
    return _grade_applications(config).filter(status__in=SEAT_STATUSES).count()


def open_offer_count(config) -> int:
    return Offer.objects.filter(status='offered', entry__application__in=_grade_applications(config)).count()


def seats_left(config) -> int:
    return max(0, config.capacity - seats_taken(config) - open_offer_count(config))


def ranked_entries(config):
    """Everyone still waiting for this grade and year, in the order they will be offered a seat."""
    entries = list(WaitlistEntry.objects.filter(status='active', application__in=_grade_applications(config))
                   .select_related('application', 'application__applicant'))

    def key(e):
        sibling = bool(e.application.applicant.sibling_at_school.strip())
        return (0 if (config.sibling_priority and sibling) else 1, 0 if (config.staff_child_priority and e.staff_child) else 1, e.joined_at)

    return sorted(entries, key=key)


def ensure_entry(application):
    """Put an application on the waiting list (or back on it)."""
    entry, created = WaitlistEntry.objects.get_or_create(application=application, defaults={'tenant_id': application.applicant.tenant_id})
    if not created and entry.status != 'active':
        entry.status, entry.joined_at = 'active', timezone.now()
        entry.save(update_fields=['status', 'joined_at'])
    return entry


def portal_link(application):
    """The family's page for answering offers, paying the fee, sending documents and booking visits."""
    base = (os.environ.get('FRONTEND_URL', '') or (getattr(settings, 'FRONTEND_ORIGINS', '') or '').split(',')[0]).strip().rstrip('/')
    return f'{base}/apply/manage?no={application.application_no}&token={application.tracking_token}'


@transaction.atomic
def fill(config, now=None):
    """Offer every free seat to the next family in line. Returns the offers made."""
    now = now or timezone.now()
    config = WaitlistConfig.objects.select_for_update().get(pk=config.pk)
    made = []
    for entry in ranked_entries(config):
        if seats_left(config) <= 0:
            break
        offer = Offer.objects.create(entry=entry, tenant_id=config.tenant_id, offered_at=now, expires_at=now + timedelta(hours=config.offer_hours))
        entry.status = 'offered'
        entry.save(update_fields=['status'])
        app = entry.application
        _event(app, app.status, f'Offered a seat (answer by {timezone.localtime(offer.expires_at):%b %d, %I:%M %p})')
        _mail(app.applicant.email, f'A place is available: application {app.application_no}',
              f'Good news: a place has opened for {app.applicant.full_name} ({config.class_name}).\n\n'
              f'Please accept or decline before {timezone.localtime(offer.expires_at):%B %d, %Y at %I:%M %p}.\n{portal_link(app)}\n\n'
              f'Application number: {app.application_no}\nTracking code: {app.tracking_token}')
        made.append(offer)
    return made


@transaction.atomic
def respond(offer, accept: bool, now=None):
    """The family answers an open offer. Accepting approves the application; declining passes the seat on."""
    now = now or timezone.now()
    if offer.status != 'offered':
        raise ValueError('This offer is no longer open.')
    if offer.expires_at <= now:
        raise ValueError('This offer has expired.')
    entry, app = offer.entry, offer.entry.application
    offer.status, offer.responded_at = ('accepted' if accept else 'declined'), now
    offer.save(update_fields=['status', 'responded_at'])
    if accept:
        entry.status = 'accepted'
        _event(app, 'approved', 'Family accepted the offered seat')
        app.status, app.decided_at = 'approved', now
        app.save(update_fields=['status', 'decided_at', 'updated_at'])
    else:
        entry.status = 'declined'
        _event(app, app.status, 'Family declined the offered seat')
    entry.save(update_fields=['status'])
    if not accept:
        config = config_for(app)
        if config:
            fill(config, now)
    return offer


@transaction.atomic
def expire_due(now=None):
    """Close offers whose deadline has passed and offer those seats to the next families. Returns how many expired."""
    now = now or timezone.now()
    count = 0
    seen = {}
    for offer in Offer.objects.filter(status='offered', expires_at__lte=now).select_related('entry__application__applicant'):
        offer.status, offer.responded_at = 'expired', now
        offer.save(update_fields=['status', 'responded_at'])
        offer.entry.status = 'expired'
        offer.entry.save(update_fields=['status'])
        app = offer.entry.application
        _event(app, app.status, 'The offered seat expired without an answer')
        _mail(app.applicant.email, f'Offer expired: application {app.application_no}',
              'The time to answer the offer of a place has passed, so it was offered to another family. '
              'Please contact the school office if you still want a place.')
        config = config_for(app)
        if config:
            seen[config.pk] = config
        count += 1
    for config in seen.values():
        fill(config, now)
    return count


def release_seat(application):
    """A seat may have opened because an approved or enrolled application was rejected or withdrawn."""
    config = config_for(application)
    return fill(config) if config else []


def on_status_change(application, previous, new):
    """Keep the waiting list in step when staff change an application's status."""
    if new == 'waitlisted':
        ensure_entry(application)
        config = config_for(application)
        if config:
            fill(config)
        return
    freed = previous in SEAT_STATUSES and new not in SEAT_STATUSES
    entry = WaitlistEntry.objects.filter(application=application).first()
    if entry and entry.status in ('active', 'offered'):
        if entry.status == 'offered':
            Offer.objects.filter(entry=entry, status='offered').update(status='withdrawn', responded_at=timezone.now())
            freed = True
        entry.status = 'accepted' if new in SEAT_STATUSES else 'removed'
        entry.save(update_fields=['status'])
    if freed:
        release_seat(application)
