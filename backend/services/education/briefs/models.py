import datetime
import uuid

from django.conf import settings
from django.db import models

from services.core.tenants.mixins import TenantScopedModel


class BriefBase(TenantScopedModel):
    """What a daily brief and a roll-up share: the figures, the written read of them, and who approved it.

    The figures are counts and amounts only (never a person's name), so what is stored and what any AI is shown holds no
    personal information. A brief starts as a draft. Once an administrator approves it, its figures and words are locked.
    """
    STATUSES = [('draft', 'Draft, not yet reviewed'), ('approved', 'Approved')]
    SOURCES = [('ai', 'Written by AI'), ('template', 'Plain summary (AI not used)')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=10, choices=STATUSES, default='draft', db_index=True)
    metrics = models.JSONField(default=dict, blank=True)          # {'sections': [...], 'values': {...}, 'attention': [...]}
    narrative = models.TextField(blank=True, default='')
    original_narrative = models.TextField(blank=True, default='', help_text='What was generated, before any edit')
    narrative_source = models.CharField(max_length=10, choices=SOURCES, default='template')
    edited = models.BooleanField(default=False)
    generated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class DailyBrief(BriefBase):
    """The morning brief or the evening summary for one school day (the school's own date)."""
    KINDS = [('morning', 'Morning brief'), ('evening', 'Evening summary')]

    kind = models.CharField(max_length=8, choices=KINDS)
    date = models.DateField(db_index=True)

    class Meta:
        ordering = ['-date', 'kind']
        constraints = [models.UniqueConstraint(fields=['tenant', 'kind', 'date'], name='one_brief_per_kind_and_day')]


class BriefRollup(BriefBase):
    """A weekly, fortnightly or monthly brief, worked out from the daily briefs of that period."""
    PERIODS = [('week', 'Weekly'), ('fortnight', 'Fortnightly'), ('month', 'Monthly')]

    period = models.CharField(max_length=10, choices=PERIODS)
    period_start = models.DateField()
    period_end = models.DateField(db_index=True)
    days = models.PositiveSmallIntegerField(default=0, help_text='Daily briefs it was built from')

    class Meta:
        ordering = ['-period_end', 'period']
        constraints = [models.UniqueConstraint(fields=['tenant', 'period', 'period_start', 'period_end'], name='one_rollup_per_period')]


class BriefSettings(TenantScopedModel):
    """When each school's briefs are prepared (in the school's own time zone)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enabled = models.BooleanField(default=True)
    morning_time = models.TimeField(default=datetime.time(6, 30))
    evening_time = models.TimeField(default=datetime.time(17, 0))


class BriefRead(TenantScopedModel):
    """An administrator marking a brief as read, so the others can see it has been looked at (and by whom)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    daily = models.ForeignKey(DailyBrief, on_delete=models.CASCADE, null=True, blank=True, related_name='reads')
    rollup = models.ForeignKey(BriefRollup, on_delete=models.CASCADE, null=True, blank=True, related_name='reads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['read_at']
        constraints = [
            models.UniqueConstraint(fields=['daily', 'user'], condition=models.Q(daily__isnull=False), name='one_read_per_admin_daily'),
            models.UniqueConstraint(fields=['rollup', 'user'], condition=models.Q(rollup__isnull=False), name='one_read_per_admin_rollup'),
        ]
