"""Teaching rules and who is qualified for what. Mounted under ``/api/v1/auth/academics/``."""
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from services.core.accounts.decorators import is_admin
from services.core.accounts.permissions import IsSchoolAdmin

from .eligibility import get_policy, qualified_subject_ids, why_not
from . import scheduler
from .models import (ClassSubject, SchedulingPolicy, Subject, Teacher, TeacherSubjectAssignment, TimetableEntry,
                     TimetableSnapshot)

POLICY_FIELDS = ('enforce_subject_match', 'max_periods_per_day', 'max_periods_per_week', 'max_consecutive', 'cover_allow_over_load')


def _err(message, code=400):
    return Response({'error': message}, status=code)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def scheduling_policy(request):
    tenant = getattr(request, 'tenant', None)
    policy = get_policy(tenant)
    if request.method == 'PATCH':
        if not is_admin(request.user):
            return _err('Only school administrators can change the teaching rules.', 403)
        policy = SchedulingPolicy.objects.filter(tenant=tenant).first() or SchedulingPolicy(tenant=tenant)
        for f in POLICY_FIELDS:
            if f in request.data:
                setattr(policy, f, request.data[f])
        for f in ('max_periods_per_day', 'max_periods_per_week', 'max_consecutive'):
            try:
                value = int(getattr(policy, f))
            except (TypeError, ValueError):
                return _err('Limits must be whole numbers.')
            if not 1 <= value <= 60:
                return _err('Limits must be between 1 and 60.')
            setattr(policy, f, value)
        if policy.max_periods_per_day * 7 < policy.max_periods_per_week:
            return _err('The weekly limit cannot be more than seven times the daily limit.')
        policy.save()
    return Response({f: getattr(policy, f) for f in POLICY_FIELDS})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def teacher_subjects(request, teacher_id):
    """The subjects a teacher is qualified for. Reading is open to staff; changing needs an administrator."""
    teacher = get_object_or_404(Teacher, pk=teacher_id)
    if request.method == 'PUT':
        if not is_admin(request.user):
            return _err('Only school administrators can change who teaches what.', 403)
        ids = request.data.get('subjects')
        if not isinstance(ids, list):
            return _err('Send the list of subject ids as "subjects".')
        found = list(Subject.objects.filter(pk__in=ids))
        if len(found) != len(set(map(str, ids))):
            return _err('One of those subjects does not exist.')
        teacher.subjects.set(found)
    return Response({'teacher': str(teacher.id), 'subjects': [{'id': str(s.id), 'name': s.name, 'code': s.code}
                                                              for s in teacher.subjects.all().order_by('name')]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def eligible_teachers(request):
    """For one class-subject: who is qualified (with their weekly load) and who is not, and why."""
    cs = get_object_or_404(ClassSubject.objects.select_related('subject', 'class_ref'), pk=request.query_params.get('class_subject'))
    subjects = list(Subject.objects.all())
    assigned = set(TeacherSubjectAssignment.objects.filter(class_subject=cs, is_active=True).values_list('teacher_id', flat=True))
    load = {}
    for t_id in TimetableEntry.objects.filter(is_active=True).values_list('teacher_id', flat=True):
        load[t_id] = load.get(t_id, 0) + 1
    ok, no = [], []
    for t in Teacher.objects.filter(is_active=True).prefetch_related('subjects').order_by('full_name'):
        row = {'id': str(t.id), 'name': t.full_name, 'relief': t.teacher_type == 'relief', 'assigned': t.id in assigned,
               'periods_per_week': load.get(t.id, 0)}
        if cs.subject_id in qualified_subject_ids(t, subjects):
            ok.append(row)
        else:
            no.append({**row, 'reason': why_not(t, cs.subject)})
    return Response({'subject': cs.subject.name, 'class_name': cs.class_ref.name, 'qualified': ok, 'not_qualified': no})


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def teaching_coverage(request):
    """What an administrator has to fix before strict rules and the generator can work well."""
    subjects = list(Subject.objects.all())
    teachers = list(Teacher.objects.filter(is_active=True).prefetch_related('subjects'))
    qualified_by_subject = {s.id: [] for s in subjects}
    no_subjects = []
    for t in teachers:
        ids = qualified_subject_ids(t, subjects)
        if not ids:
            no_subjects.append({'id': str(t.id), 'name': t.full_name, 'text': ', '.join(map(str, t.specializations))
                                if isinstance(t.specializations, list) else str(t.specializations or ''),
                                'relief': t.teacher_type == 'relief'})
        for sid in ids:
            qualified_by_subject.setdefault(sid, []).append(t)
    gaps, thin = [], []
    for cs in ClassSubject.objects.select_related('subject', 'class_ref'):
        people = qualified_by_subject.get(cs.subject_id, [])
        row = {'class_subject': str(cs.id), 'class_name': cs.class_ref.name, 'subject': cs.subject.name,
               'periods_per_week': cs.periods_per_week}
        assigned = TeacherSubjectAssignment.objects.filter(class_subject=cs, is_active=True).exists()
        if not people and not assigned:
            gaps.append(row)
        elif len(people) == 1 and not assigned:
            thin.append({**row, 'only': people[0].full_name})
    return Response({
        'teachers_without_subjects': no_subjects,
        'class_subjects_without_qualified_teacher': gaps,
        'class_subjects_with_one_qualified_teacher': thin,
        'counts': {'teachers': len(teachers), 'subjects': len(subjects), 'teachers_without_subjects': len(no_subjects),
                   'unstaffed': len(gaps)},
    })


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def snapshots(request):
    """Earlier timetables that a generation replaced, newest first. The last 30 days are kept."""
    qs = TimetableSnapshot.objects.select_related('created_by', 'academic_year')
    if request.query_params.get('academic_year'):
        qs = qs.filter(academic_year_id=request.query_params['academic_year'])
    return Response([{'id': str(s.id), 'created_at': s.created_at, 'created_by': getattr(s.created_by, 'email', '') or '',
                      'entries': len(s.entries), 'academic_year': s.academic_year.name, 'undone': s.undone, 'label': s.label}
                     for s in qs[:30]])


@api_view(['POST'])
@permission_classes([IsSchoolAdmin])
def undo_snapshot(request, snapshot_id):
    snap = get_object_or_404(TimetableSnapshot, pk=snapshot_id)
    try:
        restored = scheduler.undo(snap)
    except ValueError as e:
        return _err(str(e), 409)
    return Response({'restored': restored})
