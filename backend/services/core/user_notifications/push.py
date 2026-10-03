"""Web push: a phone or computer that has installed the app gets notifications even when the app is closed.

Push is one more delivery channel for the in-app notifications that already exist: every new ``Notification`` is also
sent to the recipient's registered devices, unless they have turned that type off. It is opt-in (nothing is sent to a
device until its owner subscribes) and needs VAPID keys in the environment:

    VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_CONTACT (a mailto: address)

Create a pair with ``python manage.py generate_vapid_keys``. Without keys the app works normally and the settings
screen says push is not available.
"""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification, PushPreference, PushSubscription

logger = logging.getLogger(__name__)

MAX_DEVICES = 10
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='push')


def vapid_config():
    """(public key, private key, contact). Read each time, so a change of environment takes effect at once."""
    return (os.environ.get('VAPID_PUBLIC_KEY', '').strip(), os.environ.get('VAPID_PRIVATE_KEY', '').strip(),
            os.environ.get('VAPID_CONTACT', '').strip() or 'mailto:admin@example.com')


def is_configured() -> bool:
    public, private, _ = vapid_config()
    return bool(public and private)


def muted_types(user_id):
    pref = PushPreference.objects.filter(user_id=user_id).first()
    return set(pref.muted_types) if pref else set()


def payload_for(notification):
    return {'title': notification.title, 'body': notification.message[:240], 'url': '/', 'tag': str(notification.pk),
            'type': notification.notification_type}


def send_to_user(user_id, payload) -> int:
    """Send one push to every device the user has registered. Returns how many devices accepted it."""
    if not is_configured():
        return 0
    from pywebpush import WebPushException, webpush

    _, private, contact = vapid_config()
    sent = 0
    for sub in list(PushSubscription.objects.filter(user_id=user_id)):
        try:
            webpush(subscription_info={'endpoint': sub.endpoint, 'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}},
                    data=json.dumps(payload), vapid_private_key=private, vapid_claims={'sub': contact}, ttl=86400, timeout=10)
            sent += 1
        except WebPushException as exc:
            code = getattr(getattr(exc, 'response', None), 'status_code', None)
            if code in (404, 410):  # the device uninstalled the app or revoked permission
                sub.delete()
            else:
                logger.warning('Push to %s failed: %s', sub.pk, exc)
        except Exception:  # one bad device must not stop the others
            logger.exception('Push failed')
    return sent


def deliver(notification_id):
    """Push one stored notification to its recipient, unless that type is switched off."""
    notification = Notification.objects.filter(pk=notification_id).first()
    if notification is None or notification.notification_type in muted_types(notification.recipient_id):
        return 0
    return send_to_user(notification.recipient_id, payload_for(notification))


def queue(notification):
    """Called when a notification is created: push it in the background so the request that made it is not slowed."""
    if is_configured() and PushSubscription.objects.filter(user_id=notification.recipient_id).exists():
        _executor.submit(deliver, notification.pk)


def _clean(value, limit):
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= limit else None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vapid_key_view(request):
    public, private, _ = vapid_config()
    return Response({'enabled': bool(public and private), 'public_key': public if private else ''})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def push_subscribe(request):
    """Register this device. Body: the browser's subscription ({endpoint, keys: {p256dh, auth}})."""
    if not is_configured():
        return Response({'error': 'Push notifications are not set up for this school yet.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    keys = request.data.get('keys') if isinstance(request.data.get('keys'), dict) else {}
    endpoint, p256dh, auth = _clean(request.data.get('endpoint'), 2000), _clean(keys.get('p256dh'), 255), _clean(keys.get('auth'), 255)
    if not (endpoint and p256dh and auth) or urlparse(endpoint).scheme != 'https':
        return Response({'error': 'That subscription is not valid.'}, status=status.HTTP_400_BAD_REQUEST)
    sub, created = PushSubscription.objects.update_or_create(
        user=request.user, endpoint=endpoint,
        defaults={'p256dh': p256dh, 'auth': auth, 'user_agent': str(request.data.get('userAgent') or '')[:500],
                  'platform': str(request.data.get('platform') or 'web')[:50]})
    old = list(PushSubscription.objects.filter(user=request.user).order_by('-updated_at').values_list('pk', flat=True)[MAX_DEVICES:])
    if old:
        PushSubscription.objects.filter(pk__in=old).delete()
    return Response({'id': str(sub.pk), 'created': created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def push_unsubscribe(request):
    endpoint = _clean(request.data.get('endpoint'), 2000)
    if not endpoint:
        return Response({'error': 'Say which device.'}, status=status.HTTP_400_BAD_REQUEST)
    deleted, _ = PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return Response({'removed': deleted > 0})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_devices(request):
    return Response({'enabled': is_configured(), 'devices': [
        {'id': str(s.pk), 'platform': s.platform, 'user_agent': s.user_agent, 'added': s.created_at, 'last_active': s.updated_at}
        for s in PushSubscription.objects.filter(user=request.user)]})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_device(request, device_id):
    deleted, _ = PushSubscription.objects.filter(pk=device_id, user=request.user).delete()
    return Response({'removed': True}) if deleted else Response({'error': 'Device not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def push_preferences(request):
    """Which kinds of notification may be pushed to this person's devices."""
    keys = [k for k, _ in Notification.NOTIFICATION_TYPES]
    if request.method == 'PUT':
        muted = request.data.get('muted_types')
        if not isinstance(muted, list) or any(m not in keys for m in muted):
            return Response({'error': 'Choose from: ' + ', '.join(keys)}, status=status.HTTP_400_BAD_REQUEST)
        PushPreference.objects.update_or_create(user=request.user, defaults={'muted_types': sorted(set(muted))})
    off = muted_types(request.user.pk)
    return Response({'types': [{'key': k, 'label': label, 'enabled': k not in off} for k, label in Notification.NOTIFICATION_TYPES]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def push_test(request):
    """Send a test push to the signed-in person's own devices."""
    if not is_configured():
        return Response({'error': 'Push notifications are not set up for this school yet.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    sent = send_to_user(request.user.pk, {'title': 'Test notification', 'body': 'Push notifications are working on this device.', 'url': '/', 'tag': 'test'})
    return Response({'sent': sent})
