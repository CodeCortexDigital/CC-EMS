"""Tell a student's counsellors about a dropout-risk finding. Reached only through an approved request (see services.ai.actions)."""
from __future__ import annotations

import logging

from django.apps import apps
from django.utils import timezone

logger = logging.getLogger(__name__)


def dropout_risk_of(student):
    StudentRisk = apps.get_model('analytics', 'StudentRisk')
    risk = StudentRisk.objects.filter(student=student).first()
    value = (risk.factors or {}).get('dropout_risk') if risk else None
    return risk, value


def notify(student, by) -> dict:
    """Open the follow-up, notify the class teachers and the school's administrators, and note it on the student's risk row.
    ``by`` is the person who approved it. Raises ValueError('no_scan') when the school has not been scored."""
    from services.core.accounts.models import TeacherProfile
    from services.core.tenants.models import TenantMembership
    from services.core.user_notifications.utils import create_user_notification

    Recommendation = apps.get_model('analytics', 'Recommendation')
    risk, dropout_risk = dropout_risk_of(student)
    if dropout_risk is None:
        raise ValueError('no_scan')

    message = f"{student.full_name} shows a {dropout_risk:.0f}% dropout risk (attendance, grades and behaviour). Please follow up."
    rec = Recommendation.objects.create(
        student=student, recommendation_type='attendance', title='Dropout risk follow-up',
        description=message, action_items=['Meet with the student', 'Contact the family',
                                           'Review attendance and recent grades'])

    recipients = {t.user_id: t.user for t in TeacherProfile.objects.filter(
        assigned_classes=student.current_class_id).select_related('user') if t.user_id}
    if student.tenant_id:
        recipients.update({m.user_id: m.user for m in TenantMembership.objects.filter(
            school_id=student.tenant_id, role='admin').select_related('user')})
    notified = 0
    for user in recipients.values():
        if create_user_notification(user, 'Dropout risk alert', message, 'academic'):
            notified += 1

    try:  # the same reason as the nightly scan's, so it lands in the counsellor queue once
        from services.education.interventions.engine import open_intervention

        open_intervention(student=student, source='risk', title=f'Dropout risk {dropout_risk:.0f}%', description=message,
                          actions=['Meet with the student', 'Contact the family', 'Review attendance and recent grades'],
                          due_days=7, dedupe_key=f'risk:{student.pk}', created_by=by, notify=False)
    except Exception:
        logger.exception('Could not open an intervention for student %s', student.pk)

    risk.recommendations = (risk.recommendations or []) + [
        {'action': 'counsel_notified', 'at': timezone.now().isoformat(), 'by': getattr(by, 'email', ''), 'notified': notified}]
    risk.save(update_fields=['recommendations'])
    return {'notified': notified, 'recommendation_id': str(rec.id)}
