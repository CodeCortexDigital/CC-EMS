import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from services.core.tenants.mixins import TenantScopedModel


class Intervention(TenantScopedModel):
    """Something the school has decided to do about one student: a counselor's to-do, with an owner and a due date.

    They are opened by people, and automatically when absences add up (attendance escalation) or the early-warning
    model flags a student. An open intervention for the same reason is never opened twice (``dedupe_key``).
    """
    SOURCES = [('absence', 'Attendance'), ('risk', 'Early-warning model'), ('behaviour', 'Behaviour'), ('manual', 'Added by staff')]
    STATUSES = [('open', 'Open'), ('in_progress', 'In progress'), ('done', 'Done'), ('dismissed', 'Dismissed')]
    PRIORITIES = [('normal', 'Normal'), ('high', 'High')]
    ACTIVE = ('open', 'in_progress')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey('education_students.Student', on_delete=models.CASCADE, related_name='interventions')
    source = models.CharField(max_length=12, choices=SOURCES, default='manual')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    suggested_actions = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default='open')
    priority = models.CharField(max_length=8, choices=PRIORITIES, default='normal')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='interventions_owned')
    due_date = models.DateField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=120, blank=True, default='', help_text='Stops the same reason opening twice while one is still open')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    closure_note = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['due_date', '-created_at']
        indexes = [models.Index(fields=['status', 'due_date']), models.Index(fields=['student', 'status'])]
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'dedupe_key'], name='one_active_intervention_per_reason',
                                    condition=models.Q(status__in=('open', 'in_progress')) & ~models.Q(dedupe_key='')),
        ]

    @property
    def is_overdue(self):
        return self.status in self.ACTIVE and self.due_date is not None and self.due_date < timezone.localdate()


class InterventionNote(models.Model):
    """The running log on an intervention. Reaches its school through the intervention."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
