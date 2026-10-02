"""Staff records: job openings and candidates, onboarding, contracts, credentials, reviews and goals.

HR (administrators, HR and managers) manage everything. A staff member sees, and for goals and onboarding updates,
only their own. Mounted under ``/api/v1/auth/hr/``.
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from services.education.academics.models import Teacher

from .access import err, is_hr, parse_date, teacher_for
from .models import (JobCandidate, JobOpening, OnboardingTask, PerformanceReview, StaffContract, StaffCredential,
                     StaffGoal)


# ---------------------------------------------------------------- serializers

def _serializer(model, extra=None, read_only=(), **named):
    attrs = {'Meta': type('Meta', (), {'model': model, 'exclude': ['tenant'], 'read_only_fields': list(read_only)})}
    attrs.update(extra or {})
    attrs.update(named)
    return type(f'{model.__name__}Serializer', (serializers.ModelSerializer,), attrs)


def _teacher_name():
    return serializers.CharField(source='teacher.full_name', read_only=True)


OpeningSerializer = _serializer(
    JobOpening,
    candidate_count=serializers.SerializerMethodField(),
    get_candidate_count=lambda self, o: o.candidates.exclude(stage='rejected').count(),
    hired_count=serializers.SerializerMethodField(),
    get_hired_count=lambda self, o: o.candidates.filter(stage='hired').count(),
    read_only=['created_at'],
)
CandidateSerializer = _serializer(
    JobCandidate, opening_title=serializers.CharField(source='opening.title', read_only=True),
    read_only=['history', 'staff', 'created_at', 'stage'])
ContractSerializer = _serializer(StaffContract, teacher_name=_teacher_name(), read_only=['created_at'])
CredentialSerializer = _serializer(StaffCredential, teacher_name=_teacher_name(), read_only=['created_at'])
OnboardingSerializer = _serializer(OnboardingTask, teacher_name=_teacher_name(), read_only=['done_at'])
GoalSerializer = _serializer(StaffGoal, teacher_name=_teacher_name(), read_only=['created_at'])
ReviewSerializer = _serializer(
    PerformanceReview, teacher_name=_teacher_name(),
    reviewer_name=serializers.CharField(source='reviewer.full_name', read_only=True, default=''),
    read_only=['reviewer', 'acknowledged_at', 'created_at', 'employee_comment'])


def _check_rating(value):
    if value is not None and not 1 <= value <= 5:
        raise serializers.ValidationError('Rating must be from 1 to 5.')
    return value


ReviewSerializer.validate_rating = lambda self, v: _check_rating(v)


def _check_progress(self, value):
    if not 0 <= value <= 100:
        raise serializers.ValidationError('Progress must be from 0 to 100.')
    return value


GoalSerializer.validate_progress = _check_progress


# ---------------------------------------------------------------- generic views

class HRList(generics.ListCreateAPIView):
    """List and create. Staff see (and, for `staff_can_write`, change) only rows about themselves."""
    permission_classes = [IsAuthenticated]
    model = None
    owner_field = 'teacher'
    select = ('teacher',)
    staff_visible = None  # extra filter for non-HR viewers, e.g. {'status__in': [...]}
    filter_params = ('teacher_id', 'status')

    def get_queryset(self):
        qs = self.model.objects.all()
        if self.select:
            qs = qs.select_related(*self.select)
        if not is_hr(self.request.user):
            me = teacher_for(self.request.user)
            if me is None:
                return qs.none()
            qs = qs.filter(**{self.owner_field: me})
            if self.staff_visible:
                qs = qs.filter(**self.staff_visible)
        for p in self.filter_params:
            if self.request.query_params.get(p):
                qs = qs.filter(**{('teacher_id' if p == 'teacher_id' else p): self.request.query_params[p]})
        return qs

    def create(self, request, *args, **kwargs):
        if not is_hr(request.user):
            return err('Only HR and administrators can add these.', 403)
        return super().create(request, *args, **kwargs)


class HRDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    model = None
    owner_field = 'teacher'
    select = ('teacher',)
    staff_visible = None
    staff_editable = ()  # fields a non-HR owner may change

    def get_queryset(self):
        qs = self.model.objects.all()
        if self.select:
            qs = qs.select_related(*self.select)
        if not is_hr(self.request.user):
            me = teacher_for(self.request.user)
            if me is None:
                return qs.none()
            qs = qs.filter(**{self.owner_field: me})
            if self.staff_visible:
                qs = qs.filter(**self.staff_visible)
        return qs

    def update(self, request, *args, **kwargs):
        if not is_hr(request.user):
            extra = set(request.data) - set(self.staff_editable)
            if not self.staff_editable or extra:
                return err('Only HR and administrators can change this.', 403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not is_hr(request.user):
            return err('Only HR and administrators can delete this.', 403)
        return super().destroy(request, *args, **kwargs)


def _make_views(model, serializer, name, **opts):
    """Build the list and detail view for a model with the same options."""
    list_opts = {k: v for k, v in opts.items() if k != 'staff_editable'}
    L = type(f'{name}List', (HRList,), {'model': model, 'serializer_class': serializer, **list_opts})
    D = type(f'{name}Detail', (HRDetail,), {'model': model, 'serializer_class': serializer, **opts})
    return L, D


ContractList, ContractDetail = _make_views(StaffContract, ContractSerializer, 'Contract', filter_params=('teacher_id',))
CredentialList, CredentialDetail = _make_views(StaffCredential, CredentialSerializer, 'Credential', filter_params=('teacher_id',))
OnboardingList, OnboardingDetail = _make_views(
    OnboardingTask, OnboardingSerializer, 'Onboarding', filter_params=('teacher_id',), staff_editable=('done',))
GoalList, GoalDetail = _make_views(
    StaffGoal, GoalSerializer, 'Goal', filter_params=('teacher_id', 'status'), staff_editable=('progress', 'status'))


class ReviewList(HRList):
    model = PerformanceReview
    serializer_class = ReviewSerializer
    select = ('teacher', 'reviewer')
    staff_visible = {'status__in': ['shared', 'acknowledged']}
    filter_params = ('teacher_id', 'status', 'kind')

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)


class ReviewDetail(HRDetail):
    model = PerformanceReview
    serializer_class = ReviewSerializer
    select = ('teacher', 'reviewer')
    staff_visible = {'status__in': ['shared', 'acknowledged']}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def acknowledge_review(request, review_id):
    """The reviewed person confirms they have read their review and may add a comment."""
    me = teacher_for(request.user)
    review = get_object_or_404(PerformanceReview.objects.select_related('teacher'), pk=review_id)
    if me is None or review.teacher_id != me.id:
        return err('You can only acknowledge your own review.', 403)
    if review.status == 'draft':
        return err('This review has not been shared with you yet.', 409)
    review.employee_comment = (request.data.get('comment') or review.employee_comment)[:4000]
    review.status = 'acknowledged'
    review.acknowledged_at = timezone.now()
    review.save(update_fields=['employee_comment', 'status', 'acknowledged_at'])
    return Response(ReviewSerializer(review).data)


# ---------------------------------------------------------------- job openings and candidates

class OpeningList(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OpeningSerializer

    def get_queryset(self):
        if not is_hr(self.request.user):
            return JobOpening.objects.none()
        qs = JobOpening.objects.all()
        return qs.filter(status=self.request.query_params['status']) if self.request.query_params.get('status') else qs

    def create(self, request, *args, **kwargs):
        if not is_hr(request.user):
            return err('Only HR and administrators can post openings.', 403)
        return super().create(request, *args, **kwargs)


class OpeningDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OpeningSerializer

    def get_queryset(self):
        return JobOpening.objects.all() if is_hr(self.request.user) else JobOpening.objects.none()


class CandidateList(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CandidateSerializer

    def get_queryset(self):
        if not is_hr(self.request.user):
            return JobCandidate.objects.none()
        qs = JobCandidate.objects.select_related('opening')
        for p in ('opening', 'stage'):
            if self.request.query_params.get(p):
                qs = qs.filter(**{p: self.request.query_params[p]})
        return qs

    def create(self, request, *args, **kwargs):
        if not is_hr(request.user):
            return err('Only HR and administrators can add candidates.', 403)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        who = getattr(self.request.user, 'email', '')
        serializer.save(history=[{'at': timezone.now().isoformat(), 'by': who, 'from': '', 'to': 'applied', 'note': 'Added'}])


class CandidateDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CandidateSerializer

    def get_queryset(self):
        return JobCandidate.objects.select_related('opening') if is_hr(self.request.user) else JobCandidate.objects.none()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def candidate_stage(request, candidate_id):
    """Move a candidate along the pipeline; every move is written to their history."""
    if not is_hr(request.user):
        return err('Only HR and administrators can move candidates.', 403)
    cand = get_object_or_404(JobCandidate, pk=candidate_id)
    stage = request.data.get('stage')
    if stage not in dict(JobCandidate.STAGES):
        return err('Unknown stage.')
    if stage == 'hired':
        return err('Use "Hire" to turn a candidate into a staff member.')
    if cand.stage == 'hired':
        return err('This candidate is already hired.', 409)
    cand.history = list(cand.history) + [{
        'at': timezone.now().isoformat(), 'by': getattr(request.user, 'email', ''), 'from': cand.stage, 'to': stage,
        'note': (request.data.get('note') or '')[:500]}]
    cand.stage = stage
    if stage == 'interview' and request.data.get('interview_at'):
        cand.interview_at = request.data['interview_at']
    cand.save()
    return Response(CandidateSerializer(cand).data)


DEFAULT_ONBOARDING = [
    ('Collect ID and work-eligibility documents', 0), ('Sign contract and school policies', 0),
    ('Background check and references cleared', 3), ('Create school email and login', 1),
    ('Add to payroll', 7), ('Assign classes and timetable', 7), ('Issue staff ID card and keys', 3),
    ('Orientation with line manager', 5), ('Safeguarding and safety training', 14),
]


def start_onboarding(teacher, start=None):
    """Give a new staff member the standard checklist (does nothing if they already have one)."""
    if OnboardingTask.objects.filter(teacher=teacher).exists():
        return 0
    start = start or timezone.localdate()
    OnboardingTask.objects.bulk_create([
        OnboardingTask(teacher=teacher, title=t, due_date=start + timedelta(days=d), order=i)
        for i, (t, d) in enumerate(DEFAULT_ONBOARDING)])
    return len(DEFAULT_ONBOARDING)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_start(request):
    if not is_hr(request.user):
        return err('Only HR and administrators can start onboarding.', 403)
    teacher = get_object_or_404(Teacher, pk=request.data.get('teacher_id'))
    made = start_onboarding(teacher, teacher.joining_date if teacher.joining_date >= timezone.localdate() else None)
    return Response({'created': made}, status=201 if made else 200)


def _next_employee_id():
    n = Teacher.objects.count() + 1
    while Teacher.objects.filter(employee_id=f'EMP-{n:04d}').exists():
        n += 1
    return f'EMP-{n:04d}'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def candidate_hire(request, candidate_id):
    """Turn a candidate into a staff member (with a login) and give them the onboarding checklist."""
    if not is_hr(request.user):
        return err('Only HR and administrators can hire.', 403)
    cand = get_object_or_404(JobCandidate.objects.select_related('opening'), pk=candidate_id)
    if cand.staff_id or cand.stage == 'hired':
        return err('This candidate has already been hired.', 409)
    email = (request.data.get('email') or cand.email or '').strip().lower()
    if not email:
        return err('An email address is needed to create the staff login.')
    if Teacher.objects.filter(email__iexact=email).exists():
        return err('A staff member with that email already exists.', 409)
    try:
        joining = parse_date(request.data.get('joining_date') or timezone.localdate().isoformat(), 'Joining date')
    except ValueError as e:
        return err(str(e))
    with transaction.atomic():
        try:
            teacher = Teacher.objects.create(
                employee_id=(request.data.get('employee_id') or _next_employee_id())[:20], full_name=cand.full_name,
                email=email, phone=cand.phone, joining_date=joining, role=cand.opening.title[:100],
                department=cand.opening.department[:100])
        except IntegrityError:
            return err('That employee ID is already in use.', 409)
        cand.history = list(cand.history) + [{
            'at': timezone.now().isoformat(), 'by': getattr(request.user, 'email', ''), 'from': cand.stage,
            'to': 'hired', 'note': f'Hired as {teacher.employee_id}'}]
        cand.stage, cand.staff = 'hired', teacher
        cand.save()
        tasks = start_onboarding(teacher, joining if joining >= timezone.localdate() else None)
        if cand.opening.candidates.filter(stage='hired').count() >= cand.opening.positions:
            cand.opening.status = 'closed'
            cand.opening.save(update_fields=['status'])
    return Response({'candidate': CandidateSerializer(cand).data, 'teacher_id': str(teacher.id),
                     'employee_id': teacher.employee_id, 'onboarding_tasks': tasks}, status=201)


# ---------------------------------------------------------------- alerts, overview and "my HR"

def alerts(days=60, today=None):
    """Contracts, probations and credentials that end within `days` (or already have)."""
    today = today or timezone.localdate()
    limit = today + timedelta(days=days)
    out = []
    for c in StaffContract.objects.select_related('teacher').filter(teacher__is_active=True):
        if c.end_date and c.end_date <= limit and c.end_date >= today - timedelta(days=30):
            out.append(('contract_end', c.teacher, c.end_date, f'{c.get_kind_display()} contract'))
        if c.probation_end and today <= c.probation_end <= limit:
            out.append(('probation_end', c.teacher, c.probation_end, 'Probation ends'))
    for c in StaffCredential.objects.select_related('teacher').filter(teacher__is_active=True, expires_on__isnull=False,
                                                                    expires_on__lte=limit):
        out.append(('credential', c.teacher, c.expires_on, c.name))
    rows = [{'kind': k, 'teacher_id': str(t.id), 'teacher_name': t.full_name, 'date': d, 'what': w,
             'days_left': (d - today).days, 'expired': d < today} for k, t, d, w in out]
    return sorted(rows, key=lambda r: r['date'])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alerts_view(request):
    if not is_hr(request.user):
        return err('Only HR and administrators can see expiry alerts.', 403)
    try:
        days = max(1, min(int(request.query_params.get('days', 60)), 365))
    except ValueError:
        return err('days must be a number.')
    return Response(alerts(days))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overview(request):
    """Numbers for the HR landing page."""
    if not is_hr(request.user):
        return err('Only HR and administrators can see the HR overview.', 403)
    from services.education.academics.models import TeacherLeave

    from .models import SubstituteRequest
    today = timezone.localdate()
    rows = alerts(60, today)
    return Response({
        'staff': Teacher.objects.filter(is_active=True).count(),
        'on_leave_today': TeacherLeave.objects.filter(status='approved', start_date__lte=today, end_date__gte=today).count(),
        'leave_waiting': TeacherLeave.objects.filter(status__in=['pending', 'recommended']).count(),
        'cover_open': SubstituteRequest.objects.filter(status='open', date__gte=today).count(),
        'open_positions': JobOpening.objects.filter(status='open').count(),
        'candidates_active': JobCandidate.objects.exclude(stage__in=['hired', 'rejected']).count(),
        'onboarding_open': OnboardingTask.objects.filter(done=False).values('teacher').distinct().count(),
        'reviews_draft': PerformanceReview.objects.filter(status='draft').count(),
        'alerts': rows[:12], 'alert_count': len(rows),
        'expired': sum(1 for r in rows if r['expired']),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_hr(request):
    """Everything HR holds about the signed-in staff member (for the employee portal)."""
    me = teacher_for(request.user)
    if me is None:
        return Response({'linked': False})
    from .models import SubstituteRequest
    from .substitutes import _base_qs, present
    today = timezone.localdate()
    cover = _base_qs().filter(date__gte=today).exclude(status='cancelled')
    return Response({
        'linked': True,
        'teacher': {'id': str(me.id), 'name': me.full_name, 'role': me.role, 'department': me.department,
                    'manager': ({'id': str(me.manager_id), 'name': me.manager.full_name} if me.manager_id else None)},
        'contracts': ContractSerializer(StaffContract.objects.filter(teacher=me), many=True).data,
        'credentials': CredentialSerializer(StaffCredential.objects.filter(teacher=me), many=True).data,
        'goals': GoalSerializer(StaffGoal.objects.filter(teacher=me), many=True).data,
        'reviews': ReviewSerializer(PerformanceReview.objects.filter(teacher=me, status__in=['shared', 'acknowledged']),
                                    many=True).data,
        'onboarding': OnboardingSerializer(OnboardingTask.objects.filter(teacher=me), many=True).data,
        'cover': [present(r, request.user, me) for r in
                  (cover.filter(requester=me) | cover.filter(substitute=me)).order_by('date')[:20]],
    })
