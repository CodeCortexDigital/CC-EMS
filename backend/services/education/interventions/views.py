"""The intervention queue.

Administrators and counselors see and run every intervention. Any other staff member sees only the ones assigned to
them and can add notes and finish those. Families and students get nothing. Reads and changes are audited, because they
are about named students.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from services.core.accounts.decorators import get_user_role
from services.education.students.access import audit_read, audit_write

from .models import Intervention, InterventionNote

REVIEWER_ROLES = ('admin', 'counsellor')


def is_reviewer(user) -> bool:
    return get_user_role(user) in REVIEWER_ROLES


class StaffOnly(BasePermission):
    message = 'Interventions are for school staff.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and get_user_role(user) not in (None, 'parent', 'student'))


class NoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True, default='')

    class Meta:
        model = InterventionNote
        fields = ('id', 'author_name', 'text', 'created_at')


class InterventionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_number = serializers.CharField(source='student.student_id', read_only=True)
    class_name = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source='owner.full_name', read_only=True, default='')
    is_overdue = serializers.BooleanField(read_only=True)
    notes = NoteSerializer(many=True, read_only=True)

    class Meta:
        model = Intervention
        fields = ('id', 'student', 'student_name', 'student_number', 'class_name', 'source', 'title', 'description', 'suggested_actions',
                  'status', 'priority', 'owner', 'owner_name', 'due_date', 'is_overdue', 'notes', 'created_at', 'closed_at', 'closure_note')
        read_only_fields = ('source', 'suggested_actions', 'status', 'created_at', 'closed_at', 'closure_note')

    def get_class_name(self, obj):
        return obj.student.current_class.name if obj.student.current_class_id else ''

    def validate_owner(self, user):
        from services.core.tenants.context import get_current_tenant
        from services.core.tenants.models import TenantMembership
        if user is not None and not TenantMembership.objects.filter(user=user, school=get_current_tenant(), is_active=True).exclude(role__in=('parent', 'student')).exists():
            raise serializers.ValidationError('Choose a member of staff at this school.')
        return user


class InterventionViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [StaffOnly]
    serializer_class = InterventionSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']  # nothing is deleted
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'source', 'priority', 'student']
    search_fields = ['title', 'student__full_name', 'student__student_id']
    ordering_fields = ['due_date', 'created_at', 'priority']

    def get_queryset(self):
        qs = Intervention.objects.select_related('student', 'student__current_class', 'owner').prefetch_related('notes__author')
        user, params = self.request.user, self.request.query_params
        if not is_reviewer(user):
            qs = qs.filter(owner=user)
        owner = params.get('owner')
        if owner == 'me':
            qs = qs.filter(owner=user)
        elif owner == 'none':
            qs = qs.filter(owner__isnull=True)
        elif owner:
            qs = qs.filter(owner_id=owner)
        if params.get('overdue') in ('1', 'true'):
            qs = qs.filter(status__in=Intervention.ACTIVE, due_date__lt=timezone.localdate())
        if params.get('active') in ('1', 'true'):
            qs = qs.filter(status__in=Intervention.ACTIVE)
        return qs

    # ---------------------------------------------------------------------------------------------- reading
    def list(self, request, *args, **kwargs):
        audit_read(request, 'interventions/list')
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        audit_read(request, 'interventions/detail', record_id=kwargs.get('pk'))
        return response

    # ---------------------------------------------------------------------------------------------- writing
    def _reviewers_only(self, request):
        if not is_reviewer(request.user):
            return Response({'detail': 'Only administrators and counselors can do this.'}, status=status.HTTP_403_FORBIDDEN)

    def create(self, request, *args, **kwargs):
        return self._reviewers_only(request) or super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        item = serializer.save(source='manual', created_by=self.request.user)
        audit_write(self.request, 'CREATE', 'interventions/item', item.pk, {'student': str(item.student_id)})

    def partial_update(self, request, *args, **kwargs):
        denied = self._reviewers_only(request)
        if denied:
            return denied
        if self.get_object().status not in Intervention.ACTIVE:
            return Response({'error': 'This intervention is closed. Reopen it to change it.'}, status=status.HTTP_400_BAD_REQUEST)
        return super().partial_update(request, *args, **kwargs)

    def perform_update(self, serializer):
        item = serializer.save()
        audit_write(self.request, 'UPDATE', 'interventions/item', item.pk, {'student': str(item.student_id)})

    def _fresh(self, item):
        """The intervention as it is now (its notes were prefetched before this request added one)."""
        return self.get_queryset().get(pk=item.pk)

    def _may_work_on(self, request, item) -> bool:
        return is_reviewer(request.user) or item.owner_id == request.user.pk

    @action(detail=True, methods=['post'])
    def add_note(self, request, pk=None):
        item = self.get_object()
        text = str(request.data.get('text') or '').strip()
        if not text:
            return Response({'text': 'Write a note first.'}, status=status.HTTP_400_BAD_REQUEST)
        if not self._may_work_on(request, item):
            return Response({'detail': 'This one is not assigned to you.'}, status=status.HTTP_403_FORBIDDEN)
        note = InterventionNote.objects.create(intervention=item, author=request.user, text=text)
        audit_write(request, 'CREATE', 'interventions/note', note.pk, {'intervention': str(item.pk)})
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        item = self.get_object()
        if not self._may_work_on(request, item):
            return Response({'detail': 'This one is not assigned to you.'}, status=status.HTTP_403_FORBIDDEN)
        if item.status != 'open':
            return Response({'error': 'Only an open intervention can be started.'}, status=status.HTTP_400_BAD_REQUEST)
        item.status = 'in_progress'
        item.save(update_fields=['status', 'updated_at'])
        audit_write(request, 'UPDATE', 'interventions/item', item.pk, {'status': 'in_progress'})
        return Response(self.get_serializer(self._fresh(item)).data)

    def _close(self, request, item, to_status, label):
        note = str(request.data.get('note') or '').strip()
        if item.status not in Intervention.ACTIVE:
            return Response({'error': 'This intervention is already closed.'}, status=status.HTTP_400_BAD_REQUEST)
        if not note:
            return Response({'note': f'Say {label} before closing it.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            item.status, item.closure_note, item.closed_at, item.closed_by = to_status, note, timezone.now(), request.user
            item.save()
            InterventionNote.objects.create(intervention=item, author=request.user, text=f'{to_status.title()}: {note}')
        audit_write(request, 'UPDATE', 'interventions/item', item.pk, {'status': to_status})
        return Response(self.get_serializer(self._fresh(item)).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        item = self.get_object()
        if not self._may_work_on(request, item):
            return Response({'detail': 'This one is not assigned to you.'}, status=status.HTTP_403_FORBIDDEN)
        return self._close(request, item, 'done', 'what was done')

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        denied = self._reviewers_only(request)
        return denied or self._close(request, self.get_object(), 'dismissed', 'why no action is needed')

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        denied = self._reviewers_only(request)
        if denied:
            return denied
        item = self.get_object()
        if item.status in Intervention.ACTIVE:
            return Response({'error': 'It is already open.'}, status=status.HTTP_400_BAD_REQUEST)
        item.status, item.closed_at, item.closed_by, item.closure_note = 'open', None, None, ''
        try:
            with transaction.atomic():
                item.save()
        except Exception:  # the same reason was opened again while this was closed
            return Response({'error': 'The same reason has been opened again. Use that one.'}, status=status.HTTP_400_BAD_REQUEST)
        InterventionNote.objects.create(intervention=item, author=request.user, text='Reopened')
        audit_write(request, 'UPDATE', 'interventions/item', item.pk, {'status': 'reopened'})
        return Response(self.get_serializer(self._fresh(item)).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Counts for the top of the screen."""
        today = timezone.localdate()
        qs = self.get_queryset()
        active = qs.filter(status__in=Intervention.ACTIVE)
        return Response({
            'open': qs.filter(status='open').count(), 'in_progress': qs.filter(status='in_progress').count(),
            'overdue': active.filter(due_date__lt=today).count(), 'unassigned': active.filter(owner__isnull=True).count(),
            'mine': Intervention.objects.filter(owner=request.user, status__in=Intervention.ACTIVE).count(),
            'high_priority': active.filter(priority='high').count(),
        })

    @action(detail=False, methods=['get'])
    def owners(self, request):
        """Staff an intervention can be assigned to (administrators and counselors)."""
        denied = self._reviewers_only(request)
        if denied:
            return denied
        from services.core.tenants.context import get_current_tenant
        from services.core.tenants.models import TenantMembership

        members = (TenantMembership.objects.filter(school=get_current_tenant(), is_active=True)
                   .exclude(role__in=('parent', 'student')).select_related('user').order_by('user__full_name'))
        return Response([{'id': str(m.user_id), 'name': m.user.full_name or m.user.email, 'role': m.role} for m in members])
