import uuid

from django.conf import settings
from django.db import models

from services.core.tenants.mixins import TenantScopedModel


class FormTemplate(TenantScopedModel):
    """A form the school sends to families to sign (field trip, photo consent, medical consent...)."""
    AUDIENCES = [('everyone', 'Everyone'), ('classes', 'Chosen classes')]
    STATUSES = [('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    body = models.TextField(help_text='The text families agree to')
    # [{"id": "q1", "label": "...", "type": "yes_no" | "text" | "choice", "options": [...], "required": true}]
    questions = models.JSONField(default=list, blank=True)
    audience = models.CharField(max_length=20, choices=AUDIENCES, default='everyone')
    classes = models.ManyToManyField('education_academics.SchoolClass', blank=True, related_name='+')
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default='draft')
    version = models.PositiveIntegerField(default=1)
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='next_versions')
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} (v{self.version})'

    def snapshot(self):
        """The exact wording a family signs; stored on the response so later edits never change what was agreed to."""
        return {'title': self.title, 'body': self.body, 'questions': self.questions, 'version': self.version}


class FormAssignment(TenantScopedModel):
    """One form for one child. A parent with two children has two of these."""
    STATUSES = [('pending', 'Not signed'), ('signed', 'Signed'), ('declined', 'Declined')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name='assignments')
    student = models.ForeignKey('education_students.Student', on_delete=models.CASCADE, related_name='form_assignments')
    status = models.CharField(max_length=10, choices=STATUSES, default='pending')
    last_reminded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['student__full_name']
        constraints = [models.UniqueConstraint(fields=['template', 'student'], name='uniq_form_template_student')]
        indexes = [models.Index(fields=['student', 'status'])]


class FormResponse(TenantScopedModel):
    """A signature. Never changed or removed once written."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.OneToOneField(FormAssignment, on_delete=models.PROTECT, related_name='response')
    signer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='form_responses')
    signer_name = models.CharField(max_length=255, help_text='The name they typed')
    decision = models.CharField(max_length=10, choices=[('signed', 'Signed'), ('declined', 'Declined')])
    answers = models.JSONField(default=dict, blank=True)
    text_snapshot = models.JSONField(default=dict)
    signed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')

    class Meta:
        ordering = ['-signed_at']
