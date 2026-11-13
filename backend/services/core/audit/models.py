import uuid
from django.db import models
from django.conf import settings


class ProtectedAuditError(Exception):
    """Raised when something tries to change or delete a protected (hash-chained) audit record."""


class AuditLogQuerySet(models.QuerySet):
    """Rows written to the hash chain (see chain.py) can be read, but never updated or deleted through the application."""

    def _refuse_if_protected(self, what):
        if self.exclude(entry_hash='').exists():
            raise ProtectedAuditError(f'Protected audit records cannot be {what}.')

    def delete(self):
        self._refuse_if_protected('deleted')
        return super().delete()

    def update(self, **kwargs):
        self._refuse_if_protected('changed')
        return super().update(**kwargs)


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('PERMISSION_DENIED', 'Permission Denied'),
        ('EXPORT', 'Export'),
        ('SECURITY', 'Security'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs')
    # The school the action was done in (Phase 21). Older rows have none and are only visible to the platform owner.
    school = models.ForeignKey('core_tenants.School', null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs')
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=128, blank=True)
    resource_id = models.UUIDField(null=True, blank=True)
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    changes = models.JSONField(null=True, blank=True, help_text="Field-level diff: {field: {old, new}}")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    # Decision records (AI approvals, risk reviews, AI settings) are chained: each carries the hash of the one before it for the
    # same school, so a changed, removed or inserted record shows up in `verify_audit_chain`. Older and routine rows leave these blank.
    chain = models.CharField(max_length=40, blank=True, db_index=True)
    seq = models.PositiveBigIntegerField(null=True, blank=True)
    prev_hash = models.CharField(max_length=64, blank=True)
    entry_hash = models.CharField(max_length=64, blank=True)

    objects = AuditLogQuerySet.as_manager()

    def _is_protected_in_db(self):
        return (not self._state.adding and AuditLog._base_manager.filter(pk=self.pk).exclude(entry_hash='').exists())

    def save(self, *args, **kwargs):
        if self._is_protected_in_db():
            raise ProtectedAuditError('Protected audit records cannot be changed.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._is_protected_in_db():
            raise ProtectedAuditError('Protected audit records cannot be deleted.')
        return super().delete(*args, **kwargs)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['resource_type']),
            models.Index(fields=['resource_id']),
            models.Index(fields=['user']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['resource_type', 'timestamp']),
            models.Index(fields=['school', 'timestamp']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['chain', 'seq'], condition=models.Q(seq__isnull=False), name='audit_chain_seq_unique'),
        ]

    def __str__(self):
        return f"{self.action} - {self.resource_type} - {self.resource_id} - {self.user_id or 'anon'}"


class AuditChainHead(models.Model):
    """The newest record of each chain. It is locked while a record is added, so two writers cannot both extend the same tip."""
    chain = models.CharField(max_length=40, primary_key=True)
    last_seq = models.PositiveBigIntegerField(default=0)
    last_hash = models.CharField(max_length=64, blank=True)


class ChainAnchor(models.Model):
    """The newest hash of a school's chain, sent to an outside time-stamping authority (RFC 3161) and kept with the signed reply.
    Later, the record at that position must still have that hash; a rewritten history cannot match a hash an outsider signed."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey('core_tenants.School', null=True, blank=True, on_delete=models.CASCADE, related_name='chain_anchors')
    chain = models.CharField(max_length=40, db_index=True)
    seq = models.PositiveBigIntegerField()
    head_hash = models.CharField(max_length=64)
    authority = models.CharField(max_length=300)
    token = models.BinaryField()                           # the authority's signed reply, as received (a .tsr file)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
