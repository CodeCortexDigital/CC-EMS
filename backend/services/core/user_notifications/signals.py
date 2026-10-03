import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification


def _dispatch_notification_to_socket(recipient_id, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f'user_notifications_{recipient_id}',
        {
            'type': 'send_notification',
            'data': payload,
        },
    )


@receiver(post_save, sender=Notification)
def notify_user_via_websocket(sender, instance, created, **kwargs):
    if not created:
        return

    payload = {
        'id': str(instance.id),
        'title': instance.title,
        'message': instance.message,
        'notification_type': instance.notification_type,
        'is_read': instance.is_read,
        'created_at': instance.created_at.isoformat(),
    }

    _dispatch_notification_to_socket(instance.recipient_id, payload)


@receiver(post_save, sender=Notification)
def push_to_devices(sender, instance, created, **kwargs):
    """Also push the notification to the recipient's installed app, after the database has committed it.

    Loading history (importers, seeders) sets ``_silent`` so it never pings anyone's phone.
    """
    if not created or getattr(instance, '_silent', False):
        return
    from . import push

    transaction.on_commit(lambda: push.queue(instance))
