from services.core.accounts.permissions import IsSchoolAdmin
from services.core.accounts.decorators import is_admin
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db.models import Q, Sum

from rest_framework.exceptions import ValidationError

from .models import EmployeeTask, Timesheet, EmployeeDocument


def _person(request, wanted):
    """Who a new task, timesheet or document is for. Only an administrator may choose someone else, and only someone in the same school."""
    from services.core.tenants.scoping import tenant_for_request
    from services.core.tenants.utils import user_can_access_tenant

    if wanted is None or wanted == request.user or not is_admin(request.user):
        return request.user
    tenant = tenant_for_request(request)
    if tenant is not None and not user_can_access_tenant(wanted, tenant):
        raise ValidationError('That person is not in your school.')
    return wanted
from .serializers import EmployeeTaskSerializer, TimesheetSerializer, EmployeeDocumentSerializer


class EmployeeTaskListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeTaskSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = EmployeeTask.objects.all()
        if not is_admin(user):
            queryset = queryset.filter(assignee=user)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(created_by=user, assignee=_person(self.request, serializer.validated_data.get('assignee')))


class EmployeeTaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeTaskSerializer
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        queryset = EmployeeTask.objects.all()          # already limited to this school
        if not is_admin(user):
            queryset = queryset.filter(Q(assignee=user) | Q(created_by=user))
        return queryset

    def perform_update(self, serializer):
        # Auto-stamp completed_at when marked done.
        was_done = serializer.instance.status == 'done'
        instance = serializer.save()
        if instance.status == 'done' and not was_done and not instance.completed_at:
            instance.completed_at = timezone.now()
            instance.save(update_fields=['completed_at', 'updated_at'])


class TimesheetListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TimesheetSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Timesheet.objects.all()
        if not is_admin(user):
            queryset = queryset.filter(employee=user)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(employee=_person(self.request, serializer.validated_data.get('employee')))


class TimesheetDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TimesheetSerializer
    lookup_field = 'id'

    def get_queryset(self):
        queryset = Timesheet.objects.all()
        return queryset if is_admin(self.request.user) else queryset.filter(employee=self.request.user)


class EmployeeDocumentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeDocumentSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = EmployeeDocument.objects.all()
        if not is_admin(user):
            queryset = queryset.filter(owner=user)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        file = self.request.FILES.get('file')
        serializer.save(
            owner=_person(self.request, serializer.validated_data.get('owner')),
            uploaded_by=user,
            file_name=file.name if file else '',
        )


class EmployeeDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeDocumentSerializer
    lookup_field = 'id'

    def get_queryset(self):
        queryset = EmployeeDocument.objects.all()
        return queryset if is_admin(self.request.user) else queryset.filter(owner=self.request.user)


class EmployeeSummaryView(generics.GenericAPIView):
    """Lightweight aggregate for the employee dashboard widgets."""
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        user = request.user
        tasks = EmployeeTask.objects.filter(assignee=user)
        pending_tasks = tasks.exclude(status='done').exclude(status='cancelled').count()
        done_tasks = tasks.filter(status='done').count()
        timesheets = Timesheet.objects.filter(employee=user)
        total_hours = timesheets.aggregate(total=Sum('hours_worked'))['total'] or 0
        docs = EmployeeDocument.objects.filter(owner=user).count()
        return Response({
            'pending_tasks': pending_tasks,
            'done_tasks': done_tasks,
            'total_hours': float(total_hours),
            'documents': docs,
        })
