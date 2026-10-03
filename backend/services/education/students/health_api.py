"""Health office: nurse visits, medication permissions and the dose log.

Visible to the school nurse and administrators (read and write) and to a child's parents (read only, their own child).
Teachers and everyone else get nothing. Every read is written to the audit log.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from services.core.tenants.context import get_current_tenant
from services.core.user_notifications.utils import create_user_notification

from .access import NurseOrParentReadOnly, audit_read, audit_write, is_nurse, parent_student_ids
from .models import HealthVisit, MedicationAuthorization, MedicationLog


def notify_parents(student, title, message):
    """In-app notice to each parent login linked to this student. Returns how many were told."""
    told = 0
    for profile in student.parents.select_related('user'):
        if profile.user and create_user_notification(profile.user, title, message, 'system'):
            told += 1
    return told


def notify_setting():
    """'always' (default) or 'sent_home': when a parent is told about a nurse visit. Kept in the school's settings."""
    school = get_current_tenant()
    return ((getattr(school, 'settings_json', None) or {}).get('health_office') or {}).get('notify', 'always')


class HealthVisitSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True, default='')

    class Meta:
        model = HealthVisit
        exclude = ('tenant',)
        read_only_fields = ('recorded_by', 'parent_notified_at', 'created_at')

    def validate(self, attrs):
        time_in, time_out = attrs.get('time_in'), attrs.get('time_out')
        if time_in and time_out and time_out < time_in:
            raise serializers.ValidationError({'time_out': 'Time out cannot be before time in.'})
        return attrs


class MedicationAuthorizationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = MedicationAuthorization
        exclude = ('tenant',)
        read_only_fields = ('created_at',)

    def get_is_current(self, obj):
        return obj.is_current()

    def validate(self, attrs):
        start, end = attrs.get('start_date'), attrs.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'The end date cannot be before the start date.'})
        return attrs


class MedicationLogSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='authorization.medication_name', read_only=True)
    student_name = serializers.CharField(source='authorization.student.full_name', read_only=True)
    given_by_name = serializers.CharField(source='given_by.full_name', read_only=True, default='')

    class Meta:
        model = MedicationLog
        exclude = ('tenant',)
        read_only_fields = ('given_by', 'created_at')

    def validate(self, attrs):
        auth = attrs['authorization']
        when = attrs.get('given_at') or timezone.now()
        if not auth.is_current(timezone.localtime(when).date()):
            raise serializers.ValidationError({'authorization': 'There is no current parent permission for this medication (not consented, switched off, or outside its dates).'})
        if attrs.get('status', 'given') == 'given' and auth.min_hours_between_doses:
            last = auth.logs.filter(status='given', given_at__lte=when).order_by('-given_at').first()
            if last and when - last.given_at < timedelta(hours=auth.min_hours_between_doses):
                minutes = int((when - last.given_at).total_seconds() // 60)
                if not (attrs.get('override_reason') or '').strip():
                    raise serializers.ValidationError({'override_reason': (
                        f'A dose was given {minutes} minutes ago and at least {auth.min_hours_between_doses} hours are needed '
                        'between doses. Type a reason to give it anyway.')})
        return attrs


class _HealthBase(viewsets.ModelViewSet):
    permission_classes = [NurseOrParentReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    audit_name = 'health'

    def scope(self, qs, student_path):
        """Parents only ever see their own children."""
        if not is_nurse(self.request.user):
            qs = qs.filter(**{f'{student_path}__in': parent_student_ids(self.request.user)})
        return qs

    def list(self, request, *args, **kwargs):
        audit_read(request, self.audit_name, student_id=request.query_params.get('student'))
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        audit_read(request, self.audit_name, record_id=kwargs.get('pk'))
        return response


class HealthVisitViewSet(_HealthBase):
    serializer_class = HealthVisitSerializer
    audit_name = 'health/visit'
    filterset_fields = ['student', 'visit_type', 'sent_home']
    search_fields = ['complaint', 'action_notes', 'student__full_name']

    def get_queryset(self):
        return self.scope(HealthVisit.objects.select_related('student', 'recorded_by'), 'student_id')

    @transaction.atomic
    def perform_create(self, serializer):
        visit = serializer.save(recorded_by=self.request.user)
        audit_write(self.request, 'CREATE', 'health/visit', visit.pk, {'student': str(visit.student_id)})
        if notify_setting() == 'always' or visit.sent_home:
            told = notify_parents(
                visit.student, 'Visit to the health office',
                f'{visit.student.full_name} visited the health office. '
                + (f'Reason: {visit.complaint.strip()}. ' if visit.complaint.strip() else '')
                + ('They were sent home.' if visit.sent_home else 'They are fine to stay at school.' if visit.action_taken in ('treated', 'rested') else ''))
            if told:
                visit.parent_notified_at = timezone.now()
                visit.save(update_fields=['parent_notified_at'])

    def perform_update(self, serializer):
        visit = serializer.save()
        audit_write(self.request, 'UPDATE', 'health/visit', visit.pk, {'student': str(visit.student_id)})


class MedicationAuthorizationViewSet(_HealthBase):
    serializer_class = MedicationAuthorizationSerializer
    audit_name = 'health/medication_authorization'
    filterset_fields = ['student', 'is_active', 'route']
    search_fields = ['medication_name', 'student__full_name']

    def get_queryset(self):
        return self.scope(MedicationAuthorization.objects.select_related('student'), 'student_id')

    def perform_create(self, serializer):
        consent = serializer.validated_data.get('parent_consent')
        auth = serializer.save(parent_consent_on=timezone.localdate() if consent else None)
        audit_write(self.request, 'CREATE', 'health/medication_authorization', auth.pk, {'student': str(auth.student_id)})

    def perform_update(self, serializer):
        before = serializer.instance.parent_consent
        auth = serializer.save()
        if auth.parent_consent and not before:
            auth.parent_consent_on = timezone.localdate()
            auth.save(update_fields=['parent_consent_on'])
        audit_write(self.request, 'UPDATE', 'health/medication_authorization', auth.pk, {'student': str(auth.student_id)})


class MedicationLogViewSet(_HealthBase):
    serializer_class = MedicationLogSerializer
    audit_name = 'health/medication_log'
    http_method_names = ['get', 'post', 'head', 'options']  # a dose record is never edited or removed
    filterset_fields = ['authorization', 'status', 'authorization__student']
    search_fields = ['notes', 'authorization__medication_name']

    def get_queryset(self):
        return self.scope(MedicationLog.objects.select_related('authorization', 'authorization__student', 'given_by'),
                          'authorization__student_id')

    def perform_create(self, serializer):
        log = serializer.save(given_by=self.request.user)
        audit_write(self.request, 'CREATE', 'health/medication_log', log.pk,
                    {'student': str(log.authorization.student_id), 'status': log.status, 'override': bool(log.override_reason)})
