"""Safety incident reports with follow-up.

Any staff member can report an incident and sees their own reports. Administrators and the counsellor see every report
(including which students were involved) and run the follow-up. Parents and students get nothing. Reads are audited.
"""
from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from services.core.accounts.decorators import get_user_role
from services.education.students.access import audit_read, audit_write
from services.education.students.health_api import notify_parents

from .models import FollowUpTask, SafetyIncident


def is_reviewer(user) -> bool:
    return get_user_role(user) in ('admin', 'counsellor')


class StaffOnly(BasePermission):
    message = 'Safety reports are for school staff.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and get_user_role(user) not in (None, 'parent', 'student'))


class FollowUpTaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)
    owner_name = serializers.CharField(source='owner.full_name', read_only=True, default='')

    class Meta:
        model = FollowUpTask
        fields = ('id', 'incident', 'description', 'owner', 'owner_name', 'due_date', 'completed', 'completed_at', 'is_overdue', 'created_at')
        read_only_fields = ('completed_at', 'created_at', 'incident')


class SafetyIncidentSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reporter.full_name', read_only=True, default='')
    follow_up_tasks = FollowUpTaskSerializer(many=True, read_only=True)
    overdue_tasks = serializers.SerializerMethodField()
    student_names = serializers.SerializerMethodField()

    class Meta:
        model = SafetyIncident
        exclude = ('tenant',)
        read_only_fields = ('status', 'parent_notified_at', 'closure_note', 'closed_at', 'closed_by', 'reporter', 'created_at', 'updated_at')

    def get_overdue_tasks(self, obj):
        return sum(1 for t in obj.follow_up_tasks.all() if t.is_overdue)

    def get_student_names(self, obj):
        return [s.full_name for s in obj.students_involved.all()]


class SafetyIncidentViewSet(viewsets.ModelViewSet):
    permission_classes = [StaffOnly]
    serializer_class = SafetyIncidentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'incident_type', 'severity']
    search_fields = ['title', 'description', 'place', 'people_involved']
    http_method_names = ['get', 'post', 'patch', 'head', 'options']  # reports are never deleted

    def get_queryset(self):
        qs = SafetyIncident.objects.select_related('reporter').prefetch_related('follow_up_tasks__owner', 'students_involved')
        return qs if is_reviewer(self.request.user) else qs.filter(reporter=self.request.user)

    def list(self, request, *args, **kwargs):
        audit_read(request, 'safety/incident')
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        audit_read(request, 'safety/incident', record_id=kwargs.get('pk'))
        return response

    @transaction.atomic
    def perform_create(self, serializer):
        incident = serializer.save(reporter=self.request.user)
        audit_write(self.request, 'CREATE', 'safety/incident', incident.pk, {'severity': incident.severity, 'type': incident.incident_type})
        if incident.notify_parents:
            told = sum(notify_parents(s, 'Incident at school',
                                      f'An incident involving {s.full_name} was reported at school: {incident.title}. '
                                      'Please contact the school office if you have questions.')
                       for s in incident.students_involved.all())
            if told:
                incident.parent_notified_at = timezone.now()
                incident.save(update_fields=['parent_notified_at'])

    def perform_update(self, serializer):
        if serializer.instance.status == 'closed':
            raise serializers.ValidationError('This incident is closed. Reopen it before changing it.')
        incident = serializer.save()
        audit_write(self.request, 'UPDATE', 'safety/incident', incident.pk)

    def _reviewer_only(self, request):
        if not is_reviewer(request.user):
            return Response({'detail': 'Only administrators and the counsellor can do this.'}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'])
    def add_follow_up(self, request, pk=None):
        denied = self._reviewer_only(request)
        if denied:
            return denied
        incident = self.get_object()
        if incident.status == 'closed':
            return Response({'error': 'This incident is closed. Reopen it first.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = FollowUpTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save(incident=incident, created_by=request.user)
        if incident.status == 'open':
            incident.status = 'in_follow_up'
            incident.save(update_fields=['status', 'updated_at'])
        audit_write(request, 'CREATE', 'safety/follow_up', task.pk, {'incident': str(incident.pk)})
        return Response(FollowUpTaskSerializer(task).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        denied = self._reviewer_only(request)
        if denied:
            return denied
        incident = self.get_object()
        note = (request.data.get('closure_note') or '').strip()
        if incident.status == 'closed':
            return Response({'error': 'Already closed.'}, status=status.HTTP_400_BAD_REQUEST)
        if not note:
            return Response({'closure_note': 'Say how this was resolved before closing it.'}, status=status.HTTP_400_BAD_REQUEST)
        open_tasks = incident.follow_up_tasks.filter(completed=False).count()
        if open_tasks:
            return Response({'error': f'{open_tasks} follow-up task(s) are still open.'}, status=status.HTTP_400_BAD_REQUEST)
        incident.status, incident.closure_note, incident.closed_at, incident.closed_by = 'closed', note, timezone.now(), request.user
        incident.save()
        audit_write(request, 'UPDATE', 'safety/incident', incident.pk, {'status': 'closed'})
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        denied = self._reviewer_only(request)
        if denied:
            return denied
        incident = self.get_object()
        if incident.status != 'closed':
            return Response({'error': 'Only a closed incident can be reopened.'}, status=status.HTTP_400_BAD_REQUEST)
        incident.status = 'in_follow_up' if incident.follow_up_tasks.exists() else 'open'
        incident.closed_at = incident.closed_by = None
        incident.save()
        audit_write(request, 'UPDATE', 'safety/incident', incident.pk, {'status': 'reopened'})
        return Response(self.get_serializer(incident).data)

    @action(detail=False, methods=['get'])
    def owners(self, request):
        """Staff a follow-up task can be given to (administrators and the counsellor)."""
        denied = self._reviewer_only(request)
        if denied:
            return denied
        from services.core.tenants.context import get_current_tenant
        from services.core.tenants.models import TenantMembership

        members = (TenantMembership.objects.filter(school=get_current_tenant(), is_active=True)
                   .exclude(role__in=('parent', 'student')).select_related('user').order_by('user__full_name'))
        return Response([{'id': str(m.user_id), 'name': m.user.full_name or m.user.email, 'role': m.role} for m in members])

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Follow-up tasks past their due date (administrators and the counsellor)."""
        denied = self._reviewer_only(request)
        if denied:
            return denied
        tasks = FollowUpTask.objects.filter(completed=False, due_date__lt=timezone.localdate()).select_related('incident', 'owner')
        return Response([{**FollowUpTaskSerializer(t).data, 'incident_title': t.incident.title} for t in tasks])


class FollowUpTaskViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read tasks, and mark one done (the person it is assigned to, an administrator or the counsellor)."""
    permission_classes = [StaffOnly]
    serializer_class = FollowUpTaskSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['incident', 'completed']

    def get_queryset(self):
        qs = FollowUpTask.objects.select_related('incident', 'owner')
        return qs if is_reviewer(self.request.user) else qs.filter(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        if task.completed:
            return Response({'error': 'Already done.'}, status=status.HTTP_400_BAD_REQUEST)
        task.completed, task.completed_at = True, timezone.now()
        task.save(update_fields=['completed', 'completed_at'])
        audit_write(request, 'UPDATE', 'safety/follow_up', task.pk, {'completed': True})
        return Response(self.get_serializer(task).data)
