"""The application fee: set per school, held on each application, paid by card (Stripe) or recorded by the office.

While a fee is unpaid the application is held: staff cannot move it forward (see views.update_application_status).
Card payments are confirmed only by a signed Stripe webhook, never by the browser coming back to the site.
"""
from decimal import Decimal, InvalidOperation

import requests
from django.db import transaction
from django.utils import timezone

from .models import ApplicationEvent, ApplicationFee


def fee_setting(school):
    """(amount, currency) the school charges, or (None, '') when there is no application fee."""
    raw = ((school.settings_json or {}).get('admissions') or {}) if school else {}
    try:
        amount = Decimal(str(raw.get('application_fee_amount') or '0'))
    except InvalidOperation:
        return None, ''
    return (amount, (raw.get('application_fee_currency') or 'USD').upper()) if amount > 0 else (None, '')


def create_for(application, school):
    """Give a new application its fee, if the school charges one."""
    amount, currency = fee_setting(school)
    if amount is None:
        return None
    return ApplicationFee.objects.get_or_create(application=application, defaults={'amount': amount, 'currency': currency})[0]


def is_held(application) -> bool:
    fee = getattr(application, 'fee', None) if hasattr(application, 'fee') else None
    return bool(fee and fee.status == 'unpaid')


def _event(application, note, by=''):
    ApplicationEvent.objects.create(application=application, from_status=application.status, to_status=application.status, note=note, by_name=by)


@transaction.atomic
def mark_paid(fee, reference='', by='', note=''):
    """Idempotent: a second call for the same fee changes nothing."""
    fee = ApplicationFee.objects.select_for_update().get(pk=fee.pk)
    if fee.status != 'unpaid':
        return fee
    fee.status, fee.paid_at, fee.payment_reference = 'paid', timezone.now(), reference[:255]
    if note:
        fee.note = note[:255]
    fee.save()
    _event(fee.application, f'Application fee paid ({fee.amount} {fee.currency}){" - " + reference if reference else ""}', by)
    return fee


@transaction.atomic
def waive(fee, note, by=''):
    fee = ApplicationFee.objects.select_for_update().get(pk=fee.pk)
    if fee.status != 'unpaid':
        raise ValueError(f'The fee is already {fee.get_status_display().lower()}.')
    fee.status, fee.note = 'waived', note[:255]
    fee.save()
    _event(fee.application, f'Application fee waived: {note}', by)
    return fee


def start_checkout(fee, config, success_url, cancel_url, customer_email=''):
    """Open a Stripe Checkout page for this fee and return its URL."""
    from services.education.finance.payments import stripe_gateway

    key = stripe_gateway.secret_key(config)
    if not key:
        raise ValueError('Online payment is not set up for this school yet.')
    if fee.status != 'unpaid':
        raise ValueError('There is nothing to pay.')
    data = {
        'mode': 'payment', 'success_url': success_url, 'cancel_url': cancel_url,
        'client_reference_id': str(fee.pk), 'metadata[application_fee_id]': str(fee.pk),
        'payment_intent_data[metadata][application_fee_id]': str(fee.pk),
        'line_items[0][quantity]': 1, 'line_items[0][price_data][currency]': fee.currency.lower(),
        'line_items[0][price_data][unit_amount]': stripe_gateway.to_minor_units(fee.amount, fee.currency),
        'line_items[0][price_data][product_data][name]': f'Application fee {fee.application.application_no}',
    }
    if customer_email:
        data['customer_email'] = customer_email
    resp = requests.post(f'{stripe_gateway.API}/checkout/sessions', data=data, auth=(key, ''), timeout=20)
    body = resp.json() if resp.content else {}
    if resp.status_code >= 400:
        raise ValueError((body.get('error') or {}).get('message') or 'The payment could not be started.')
    fee.checkout_session_id = body.get('id', '')
    fee.save(update_fields=['checkout_session_id'])
    return body['url']


def apply_stripe_event(raw_body: bytes, signature_header: str, event: dict):
    """Handle a Stripe event that belongs to an application fee.

    Returns None when the event is not about an application fee (so the caller can treat it as something else),
    otherwise (ok, message). The signature is checked with the secret of the school that owns the fee.
    """
    from services.core.tenants.context import use_tenant
    from services.education.finance.payments import stripe_gateway
    from services.education.finance.payments.gateways import get_active_gateway_config

    obj = (event.get('data') or {}).get('object') or {}
    fee_id = (obj.get('metadata') or {}).get('application_fee_id')
    if not fee_id:
        return None
    with use_tenant(None):
        try:
            fee = ApplicationFee.objects.select_related('application__applicant__tenant').filter(pk=fee_id).first()
        except Exception:  # not a uuid
            fee = None
        if fee is None:
            return None
        school = fee.application.applicant.tenant
    with use_tenant(school):
        config = get_active_gateway_config('stripe', tenant=school)
        if not stripe_gateway.verify_signature(raw_body, signature_header, stripe_gateway.webhook_secret(config)):
            return False, 'Invalid signature'
        kind = event.get('type', '')
        if kind in ('checkout.session.completed', 'checkout.session.async_payment_succeeded') and obj.get('payment_status') == 'paid':
            expected = stripe_gateway.to_minor_units(fee.amount, fee.currency)
            if obj.get('amount_total') != expected or str(obj.get('currency', '')).upper() != fee.currency:
                return False, 'Amount does not match the fee'
            mark_paid(fee, reference=str(obj.get('payment_intent') or obj.get('id') or ''), by='Stripe')
        return True, 'Processed'
