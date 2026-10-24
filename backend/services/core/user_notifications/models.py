from django.db import models
from django.conf import settings
import uuid

from services.core.db.softdelete import SoftDeleteModel


class Notification(SoftDeleteModel):
    tenant = models.ForeignKey(
        'core_tenants.School',
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        db_index=True,
    )
    NOTIFICATION_TYPES = [
        ('attendance', 'Attendance'),
        ('finance', 'Finance'),
        ('exam', 'Exam'),
        ('admission', 'Admission'),
        ('announcement', 'Announcement'),
        ('library', 'Library'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'created_at']),
            models.Index(fields=['recipient', 'is_read', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.email}"


class PushSubscription(models.Model):
    """Web Push subscription for a user"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )
    endpoint = models.TextField()
    p256dh = models.TextField()
    auth = models.TextField()
    user_agent = models.TextField(blank=True, default='')
    platform = models.CharField(max_length=50, default='web')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'endpoint']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.platform}"


class PushPreference(models.Model):
    """Kinds of notification a person does not want pushed to their devices (everything is on until they switch it off)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_preference')
    muted_types = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
