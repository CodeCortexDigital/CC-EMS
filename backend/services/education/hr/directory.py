"""Staff directory and org chart. Mounted under ``/api/v1/auth/hr/``."""
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from services.education.academics.models import Teacher

from .access import err, is_hr


def _person(t):
    return {'id': str(t.id), 'name': t.full_name, 'employee_id': t.employee_id, 'role': t.role,
            'department': t.department, 'email': t.email, 'phone': t.phone, 'teacher_type': t.teacher_type,
            'is_active': t.is_active, 'manager_id': str(t.manager_id) if t.manager_id else None,
            'manager_name': t.manager.full_name if t.manager_id else ''}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def directory(request):
    """Who is who: names, roles, departments and who reports to whom. Pay and personal details are not included."""
    qs = Teacher.objects.select_related('manager').order_by('full_name')
    if request.query_params.get('include_inactive') != '1':
        qs = qs.filter(is_active=True)
    return Response([_person(t) for t in qs])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def org_chart(request):
    """The reporting tree. People with no manager are the top level; anyone caught in a loop is shown at the top too."""
    people = list(Teacher.objects.filter(is_active=True).select_related('manager').order_by('full_name'))
    ids = {t.id for t in people}
    kids = {}
    for t in people:
        if t.manager_id in ids:
            kids.setdefault(t.manager_id, []).append(t)

    def node(t, seen):
        seen = seen | {t.id}
        return {**_person(t), 'reports': [node(c, seen) for c in kids.get(t.id, []) if c.id not in seen]}

    roots = [t for t in people if t.manager_id not in ids]
    placed = set()

    def walk(n):
        placed.add(n['id'])
        for c in n['reports']:
            walk(c)

    tree = [node(t, frozenset()) for t in roots]
    for n in tree:
        walk(n)
    for t in people:  # a reporting loop (A reports to B, B to A) leaves people unplaced: list them at the top
        if str(t.id) not in placed:
            n = node(t, frozenset())
            tree.append(n)
            walk(n)
    return Response({'tree': tree, 'count': len(people)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_manager(request, teacher_id):
    if not is_hr(request.user):
        return err('Only HR and administrators can change who reports to whom.', 403)
    teacher = get_object_or_404(Teacher, pk=teacher_id)
    manager_id = request.data.get('manager_id') or None
    manager = None
    if manager_id:
        manager = get_object_or_404(Teacher, pk=manager_id)
        if manager.id == teacher.id:
            return err('Nobody can be their own manager.')
        up, seen = manager, set()
        while up is not None and up.id not in seen:  # walk up: the new manager must not already report to this person
            if up.id == teacher.id:
                return err(f'{manager.full_name} already reports to {teacher.full_name}, so that would make a loop.')
            seen.add(up.id)
            up = up.manager
    teacher.manager = manager
    teacher.save(update_fields=['manager', 'updated_at'])
    return Response(_person(Teacher.objects.select_related('manager').get(pk=teacher.pk)))
