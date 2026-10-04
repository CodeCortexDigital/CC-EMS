"""Opening interventions, and finding who should be told about them.

Used by the attendance escalation ladder and the early-warning risk scan, and by the screen when staff add one by hand.
These run from background jobs as well as requests, so the school is always taken from the student and stamped
explicitly rather than from the current request.
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from services.core.user_notifications.utils import create_user_notification

from .models import Intervention

COUNSELLOR_ROLE_NAMES = ('counsellor', 'counselor', 'school counsellor', 'school counselor')


def staff_to_notify(school_id):
    """School administrators and counselors (users with a counselor-named role) of one school."""
    from services.core.accounts.decorators import normalize_role_name
    from services.core.tenants.models import TenantMembership

    users = {}
    members = TenantMembership.objects.filter(school_id=school_id, is_active=True).select_related('user')
    for m in members:
        if m.role == 'admin':
            users[m.user_id] = m.user
            continue
        profile = getattr(m.user, 'profile', None)
        role = getattr(getattr(profile, 'role', None), 'name', None)
        if normalize_role_name(role) in COUNSELLOR_ROLE_NAMES:
            users[m.user_id] = m.user
    return list(users.values())


def open_intervention(*, student, source, title, description='', actions=(), priority='normal', due_days=7,
                      dedupe_key='', created_by=None, owner=None, notify=True):
    """Open an intervention for a student. Returns (intervention, created).

    If one with the same ``dedupe_key`` is still open or in progress, that one is returned and nothing new is made, so
    a nightly scan or a daily absence count never piles up copies of the same thing.
    """
    if dedupe_key:
        existing = Intervention.all_objects.filter(tenant_id=student.tenant_id, dedupe_key=dedupe_key, status__in=Intervention.ACTIVE).first()
        if existing:
            return existing, False
    try:
        with transaction.atomic():
            item = Intervention.all_objects.create(
                tenant_id=student.tenant_id, student=student, source=source, title=title[:200], description=description,
                suggested_actions=list(actions), priority=priority, owner=owner, created_by=created_by, dedupe_key=dedupe_key,
                due_date=timezone.localdate() + timedelta(days=due_days) if due_days else None)
    except IntegrityError:  # two jobs raced to open the same reason: keep the first
        return Intervention.all_objects.get(tenant_id=student.tenant_id, dedupe_key=dedupe_key, status__in=Intervention.ACTIVE), False
    if notify:
        for user in ([owner] if owner else staff_to_notify(student.tenant_id)):
            create_user_notification(user, f'New intervention: {student.full_name}', f'{title}. Open Interventions to follow up.', 'system')
    return item, True


def from_risk(student, risk):
    """The early-warning scan flagged this student: open one intervention for the dropout risk (not one per scan)."""
    dropout = float((risk.factors or {}).get('dropout_risk') or 0)
    if risk.risk_level not in ('high', 'critical') or dropout <= 50:
        return None, False
    return open_intervention(
        student=student, source='risk', priority='high' if risk.risk_level == 'critical' else 'normal',
        title=f'Dropout risk {dropout:.0f}%',
        description=f'The early-warning model estimates a {dropout:.0f}% chance that {student.full_name} will drop out, '
                    'from attendance, grades and behaviour. It is a prompt to look closer, not a decision.',
        actions=['Meet with the student', 'Contact the family', 'Review attendance and recent grades'],
        due_days=7, dedupe_key=f'risk:{student.pk}')
