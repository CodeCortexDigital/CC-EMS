"""The absence ladder: what the school does as a student's unexcused absences add up.

A school sets steps, for example 3, 5 and 10 unexcused absences. When a student reaches a step, the family is told, and
for the higher steps the school's staff are told and an intervention is opened for a counselor. Each step fires once per
run of absences: it will not fire again until its window (default 30 days) has passed since it last fired, however many
more absences are recorded. Only unexcused absences count.

With no steps saved, the ladder is built from the older single ``chronic_threshold`` setting, then the usual 5 and 10.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from .models import AbsenceEscalation, AttendanceRecord

logger = logging.getLogger(__name__)

DEFAULT_STEPS = [
    {'count': 3, 'days': 30, 'staff': False, 'intervention': False},
    {'count': 5, 'days': 30, 'staff': True, 'intervention': True},
    {'count': 10, 'days': 60, 'staff': True, 'intervention': True},
]
MAX_STEPS = 6
MIN_DAYS, MAX_DAYS = 7, 365
SUGGESTED_ACTIONS = ['Call the family', 'Find out the reason (health, transport, family)', 'Agree a plan and review it in two weeks']


def _flag(value, default=False) -> bool:
    return value in (True, 'true', '1', 1, 'on') if value is not None else default


def clean_steps(raw):
    """Checked, sorted steps, or None when nothing sensible was given (so the default ladder is used)."""
    if not isinstance(raw, list):
        return None
    steps, seen = [], set()
    for item in raw[:MAX_STEPS]:
        if not isinstance(item, dict):
            continue
        try:
            count, days = int(item.get('count')), int(item.get('days', 30))
        except (TypeError, ValueError):
            continue
        if not 1 <= count <= 365 or count in seen:
            continue
        seen.add(count)
        steps.append({'count': count, 'days': min(MAX_DAYS, max(MIN_DAYS, days)),
                      'staff': _flag(item.get('staff')), 'intervention': _flag(item.get('intervention'))})
    return sorted(steps, key=lambda s: s['count'])


def steps_for(cfg: dict) -> list[dict]:
    """The ladder this school uses (empty = no escalation)."""
    saved = cfg.get('escalation')
    if saved is not None:
        return saved
    first = int(cfg.get('chronic_threshold') or 0)
    if first <= 0:
        return []
    # the school's own first step, then the usual higher steps (5 and 10) that are above it
    return [{'count': first, 'days': 30, 'staff': False, 'intervention': False}] + [dict(s) for s in DEFAULT_STEPS[1:] if s['count'] > first]


def unexcused_absences(student, day, days: int) -> int:
    return AttendanceRecord.objects.filter(student=student, date__gt=day - timedelta(days=days), date__lte=day,
                                           status='absent', is_excused=False).count()


def _recently_fired(student, step: dict, day) -> bool:
    return AbsenceEscalation.objects.filter(student=student, step=step['count'], triggered_on__gt=day - timedelta(days=step['days'])).exists()


def family_message(student, count: int, days: int, level: int) -> str:
    name = student.full_name
    if level == 0:
        return (f'{name} has missed {count} school days without an excuse in the last {days} days. '
                'Regular attendance matters. Please contact the school so we can help.')
    return (f'{name} has now missed {count} school days without an excuse in the last {days} days. We would like to work with '
            'you to get things back on track. Please contact the school office this week to arrange a meeting.')


def run(student, day, cfg: dict | None = None):
    """Check the ladder after an unexcused absence is recorded. Returns the step that fired, or None."""
    from services.education.interventions import engine

    from .register import send_notice, settings_for

    cfg = cfg or settings_for(student.tenant)
    steps = steps_for(cfg)
    if not steps:
        return None
    counts = {s['count']: unexcused_absences(student, day, s['days']) for s in steps}
    reached = [s for s in steps if counts[s['count']] >= s['count']]
    if not reached:
        return None
    top = reached[-1]
    if _recently_fired(student, top, day):
        return None
    for step in reached:  # steps below the top that apply now count as fired, so they do not fire later for the same run
        if not _recently_fired(student, step, day):
            AbsenceEscalation.objects.create(tenant_id=student.tenant_id, student=student, step=step['count'],
                                             absences=counts[step['count']], window_days=step['days'], triggered_on=day)

    count, days, level = counts[top['count']], top['days'], steps.index(top)
    send_notice(student, day, 'chronic', family_message(student, count, days, level), {'count': count})

    if top['staff']:
        from services.core.user_notifications.utils import create_user_notification
        for user in engine.staff_to_notify(student.tenant_id):
            create_user_notification(user, f'Attendance concern: {student.full_name}',
                                     f'{student.full_name} has {count} unexcused absences in the last {days} days.', 'attendance')
    if top['intervention']:
        engine.open_intervention(
            student=student, source='absence', title=f'{count} unexcused absences in {days} days',
            description=f'{student.full_name} reached the {top["count"]}-absence step of the school\'s attendance ladder.',
            actions=SUGGESTED_ACTIONS, priority='high' if level >= 2 else 'normal', due_days=5,
            dedupe_key=f'absence:{student.pk}:{top["count"]}', notify=not top['staff'])
    return top
