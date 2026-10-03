"""A minimal "find a student" for school staff who work with one child at a time (front desk, nurse, counsellor, anyone
filing a safety report). It returns only a name, student number and class, and only active students of this school."""
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from services.core.accounts.decorators import get_user_role

from .models import Student

MIN_CHARS = 2
LIMIT = 15


class StaffOnly(BasePermission):
    message = 'Only school staff can look students up.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and get_user_role(user) not in (None, 'parent', 'student'))


@api_view(['GET'])
@permission_classes([StaffOnly])
def student_lookup(request):
    q = str(request.query_params.get('q') or '').strip()
    if len(q) < MIN_CHARS:
        return Response([])
    students = (Student.objects.filter(is_active=True).filter(Q(full_name__icontains=q) | Q(student_id__icontains=q))
                .select_related('current_class').order_by('full_name')[:LIMIT])
    return Response([{'id': str(s.pk), 'student_id': s.student_id, 'name': s.full_name,
                     'class_name': s.current_class.name if s.current_class_id else ''} for s in students])
