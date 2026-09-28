"""Celery Beat task: nightly AI risk scan (docs table "AI Attendance Insights").

Keeps dropout/fee-default risk scores fresh without an admin having to click
"Run AI Risk Scan" — early intervention depends on the data not going stale.
"""
import logging

from celery import shared_task

logger = logging.getLogger('erp.ai')


@shared_task(name='services.analytics.tasks.nightly_risk_scan')
def nightly_risk_scan():
    from services.analytics.ai_views import RISK_ML_AVAILABLE, _run_risk_scan
    from services.core.billing.service import subscription_for
    from services.core.tenants.models import School

    if not RISK_ML_AVAILABLE:
        logger.info('Skipping nightly risk scan: ML packages are not installed.')
        return {'skipped': True}

    results = {}
    for school in School.objects.filter(is_active=True):
        sub = subscription_for(school)
        if sub is not None and not sub.has_module('ai'):
            continue
        try:
            results[str(school.id)] = _run_risk_scan(str(school.id))
        except Exception:
            logger.exception('Nightly risk scan failed for school %s', school.id)
            results[str(school.id)] = {'error': True}
    return results
