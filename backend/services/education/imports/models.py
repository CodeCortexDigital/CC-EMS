"""A record of each spreadsheet import (P10)."""
import uuid

from django.conf import settings
from django.db import models

from services.core.tenants.mixins import TenantScopedModel


class ImportRun(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=30)
    mode = models.CharField(max_length=10, default='add', blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    rows = models.PositiveIntegerField(default=0)
    added = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    skipped = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    problems = models.JSONField(default=list, blank=True)  # [{row, messages}] for the error report
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.kind} import {self.created_at:%Y-%m-%d} ({self.added} added)'


class ImportJob(TenantScopedModel):
    """A big pack (check or load) running in the background, so the request that started it does not time out."""
    STATUSES = [('running', 'Running'), ('done', 'Done'), ('failed', 'Failed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_name = models.CharField(max_length=255, blank=True)
    mode = models.CharField(max_length=10, default='add')
    commit = models.BooleanField(default=False, help_text='False = a preview that saves nothing')
    status = models.CharField(max_length=10, choices=STATUSES, default='running')
    total_files = models.PositiveIntegerField(default=0)
    files_done = models.PositiveIntegerField(default=0)
    current = models.CharField(max_length=80, blank=True, default='')
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
