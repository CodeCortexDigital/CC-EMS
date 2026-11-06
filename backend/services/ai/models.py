import uuid

from django.conf import settings
from django.db import models

from services.core.tenants.mixins import TenantScopedModel


class AIConversation(models.Model):
    """One chat thread between a user and the AI assistant."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core_tenants.School', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='ai_conversations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_conversations')
    role = models.CharField(max_length=20, blank=True)
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['user', '-updated_at'])]

    def __str__(self):
        return self.title or f"Conversation {self.id}"


class AIMessage(models.Model):
    """A visible chat turn. Tool calls made while producing an assistant turn are
    kept in `tool_calls` for auditing; they are not replayed to the model."""
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant')]
    FEEDBACK_CHOICES = [(1, 'Helpful'), (-1, 'Not helpful')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    tool_calls = models.JSONField(default=list, blank=True)
    provider = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=100, blank=True)
    offline = models.BooleanField(default=False)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cached_input_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    feedback = models.SmallIntegerField(choices=FEEDBACK_CHOICES, null=True, blank=True)
    feedback_note = models.CharField(max_length=500, blank=True)
    sources = models.JSONField(default=list, blank=True)      # school documents the answer used: [{id, title}]
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        adding = self._state.adding
        super().save(*args, **kwargs)
        if adding:
            # The clock can give a question and its answer the same time (it is coarse on Windows), which made the
            # conversation come back in the wrong order. Each new turn is kept strictly after the one before.
            from datetime import timedelta

            last = (AIMessage.objects.filter(conversation_id=self.conversation_id).exclude(pk=self.pk)
                    .order_by('-created_at').values_list('created_at', flat=True).first())
            if last and last >= self.created_at:
                self.created_at = last + timedelta(milliseconds=1)
                AIMessage.objects.filter(pk=self.pk).update(created_at=self.created_at)


class AIUsage(models.Model):
    """Daily token usage per user and feature — the basis for limits and cost reports."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core_tenants.School', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='ai_usage')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='ai_usage')
    date = models.DateField(db_index=True)
    feature = models.CharField(max_length=40)
    provider = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=100, blank=True)
    requests = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveBigIntegerField(default=0)
    output_tokens = models.PositiveBigIntegerField(default=0)
    cached_input_tokens = models.PositiveBigIntegerField(default=0)

    class Meta:
        # Not unique: tenant is nullable (NULLs never collide), so reports sum rows.
        indexes = [models.Index(fields=['tenant', 'date']), models.Index(fields=['user', 'date'])]


class KnowledgeDocument(TenantScopedModel):
    """A school document the assistant may quote from: handbook, policies, fee rules, calendar notes.

    The text is split into passages (KnowledgeChunk) that are searched when someone asks a question. Who may be shown a
    document is set per document, and always checked on the server."""
    AUDIENCES = [('everyone', 'Everyone (students, parents and staff)'), ('staff', 'Staff only'), ('admin', 'Administrators only')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    audience = models.CharField(max_length=10, choices=AUDIENCES, default='everyone')
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']


class KnowledgeChunk(models.Model):
    """One searchable passage of a document. Reaches its school through the document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name='chunks')
    ordinal = models.PositiveIntegerField()
    text = models.TextField()
    terms = models.JSONField(default=dict, blank=True)         # word -> times it appears (the search index)
    length = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['document_id', 'ordinal']


class AIActionRequest(TenantScopedModel):
    """Something the AI assistant wants done. It is only a request: nothing happens until a person with the right role
    approves it, and then only through an action that is registered in code (see actions.py)."""
    STATUSES = [('pending', 'Waiting for approval'), ('executed', 'Approved and done'), ('failed', 'Approved, but it did not work'),
                ('rejected', 'Rejected'), ('expired', 'Expired'), ('running', 'Approved, running now'),
                ('unknown', 'Approved, result could not be confirmed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=60)
    summary = models.CharField(max_length=300)
    arguments = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default='pending', db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_action_requests')
    requester_role = models.CharField(max_length=20, blank=True)
    conversation = models.ForeignKey(AIConversation, null=True, blank=True, on_delete=models.SET_NULL, related_name='action_requests')
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=500, blank=True)
    result = models.JSONField(default=dict, blank=True)
    # What the request was based on when it was made: provider and model, a fingerprint of the instructions given to the model,
    # what the person asked, what data was sent (after masking), the sources used and the controls that were on. Its hash is written
    # into the verified trail, so a changed record is noticed (see actions.basis_hash and the decision record page).
    record = models.JSONField(default=dict, blank=True)
    # Each approval given so far: [{user_id, name, at, note}]. The action runs when there are as many as the school requires (1 or 2).
    approvals = models.JSONField(default=list, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['tenant', 'status', '-created_at'])]


class AIActionEffect(TenantScopedModel):
    """The saved intent to carry out one approved request, and what is known about the outcome. One row per request (the key is unique), so a
    second attempt cannot create another. States: dispatching (saved, not yet finished), confirmed, not_done (stopped by a check, nothing
    was sent) and unknown (it was attempted and the result could not be confirmed; it is not retried automatically)."""
    STATES = [('dispatching', 'Running'), ('confirmed', 'Done'), ('not_done', 'Not done'), ('unknown', 'Result not confirmed')]

    request = models.OneToOneField(AIActionRequest, on_delete=models.CASCADE, related_name='effect')
    effect_key = models.CharField(max_length=120, unique=True)
    state = models.CharField(max_length=12, choices=STATES, default='dispatching')
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
