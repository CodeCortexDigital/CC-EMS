import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from services.core.tenants.mixins import TenantScopedModel


class SafetyIncident(TenantScopedModel):
    """A safety report (injury, bullying, property damage...). Not the data-breach ``privacy.Incident``."""
    TYPES = [('injury', 'Injury'), ('bullying', 'Bullying'), ('property', 'Property damage'), ('other', 'Other')]
    SEVERITIES = [('minor', 'Minor'), ('moderate', 'Moderate'), ('serious', 'Serious'), ('critical', 'Critical')]
    STATUSES = [('open', 'Open'), ('in_follow_up', 'In follow-up'), ('closed', 'Closed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    incident_date = models.DateField(default=timezone.localdate)
    incident_time = models.TimeField(null=True, blank=True)
    place = models.CharField(max_length=255, blank=True, default='')
    incident_type = models.CharField(max_length=20, choices=TYPES, default='other')
    severity = models.CharField(max_length=20, choices=SEVERITIES, default='minor')
    status = models.CharField(max_length=20, choices=STATUSES, default='open')
    students_involved = models.ManyToManyField('education_students.Student', blank=True, related_name='safety_incidents')
    people_involved = models.TextField(blank=True, default='', help_text='Anyone else: staff, visitors, or names not in the system')
    description = models.TextField()
    witnesses = models.TextField(blank=True, default='')
    action_taken = models.TextField(blank=True, default='')
    notify_parents = models.BooleanField(default=False, help_text="Tell the involved students' parents")
    parent_notified_at = models.DateTimeField(null=True, blank=True)
    closure_note = models.TextField(blank=True, default='')
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='safety_incidents_reported')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-incident_date', '-created_at']
        indexes = [models.Index(fields=['status', '-incident_date']), models.Index(fields=['incident_type', 'severity'])]

    def __str__(self):
        return f'{self.title} ({self.incident_date})'


class FollowUpTask(models.Model):
    """Something someone has to do after an incident. Reaches its school through the incident."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(SafetyIncident, on_delete=models.CASCADE, related_name='follow_up_tasks')
    description = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='safety_tasks')
    due_date = models.DateField()
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date', 'created_at']
        indexes = [models.Index(fields=['completed', 'due_date'])]

    @property
    def is_overdue(self):
        return not self.completed and self.due_date < timezone.localdate()
