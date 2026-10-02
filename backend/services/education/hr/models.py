"""Staff & HR: cover requests, hiring, onboarding, contracts and credentials, reviews and goals, pay setup.

Leave, the staff list and payslips already live in the academics and finance apps; these models sit beside them.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from services.core.tenants.mixins import TenantScopedModel

MONEY = dict(max_digits=12, decimal_places=2)


class SubstituteRequest(TenantScopedModel):
    """A period (or other duty) that needs someone to cover it on one date, and who ended up covering it."""
    STATUSES = [('open', 'Needs cover'), ('filled', 'Covered'), ('cancelled', 'Cancelled')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey('education_academics.Teacher', on_delete=models.CASCADE, related_name='cover_requests')
    date = models.DateField(db_index=True)
    entry = models.ForeignKey('education_academics.TimetableEntry', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='cover_requests')
    period = models.ForeignKey('education_academics.Period', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='+')
    description = models.CharField(max_length=255, blank=True, default='',
                                   help_text='What needs covering, e.g. Grade 5 maths or lunch duty')
    reason = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUSES, default='open', db_index=True)
    substitute = models.ForeignKey('education_academics.Teacher', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='cover_given')
    filled_how = models.CharField(max_length=10, blank=True, default='', help_text='claimed, assigned or auto')
    leave = models.ForeignKey('education_academics.TeacherLeave', on_delete=models.CASCADE, null=True, blank=True,
                              related_name='cover', help_text='The approved leave this cover was arranged for')
    override_reason = models.CharField(max_length=255, blank=True, default='',
                                       help_text='Why an administrator gave cover to someone not qualified for the subject')
    filled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'period__period_number', 'created_at']


class JobOpening(TenantScopedModel):
    STATUSES = [('draft', 'Draft'), ('open', 'Open'), ('closed', 'Closed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    department = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')
    positions = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=10, choices=STATUSES, default='open')
    closes_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class JobCandidate(TenantScopedModel):
    STAGES = [('applied', 'Applied'), ('screening', 'Screening'), ('interview', 'Interview'), ('offer', 'Offer'),
              ('hired', 'Hired'), ('rejected', 'Rejected')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    opening = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name='candidates')
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=40, blank=True, default='')
    source = models.CharField(max_length=80, blank=True, default='')
    stage = models.CharField(max_length=10, choices=STAGES, default='applied', db_index=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True, help_text='1 to 5')
    interview_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    history = models.JSONField(default=list, blank=True, help_text='Every stage change: at, by, from, to, note')
    staff = models.OneToOneField('education_academics.Teacher', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='hired_from')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class OnboardingTask(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey('education_academics.Teacher', on_delete=models.CASCADE, related_name='onboarding_tasks')
    title = models.CharField(max_length=200)
    due_date = models.DateField(null=True, blank=True)
    done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'due_date']


class StaffContract(TenantScopedModel):
    KINDS = [('full_time', 'Full time'), ('part_time', 'Part time'), ('fixed_term', 'Fixed term'),
             ('temporary', 'Temporary'), ('contractor', 'Contractor')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey('education_academics.Teacher', on_delete=models.CASCADE, related_name='contracts')
    kind = models.CharField(max_length=12, choices=KINDS, default='full_time')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text='Empty = open-ended')
    probation_end = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']


class StaffCredential(TenantScopedModel):
    """A teaching licence, certificate or background check that has to be kept current."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey('education_academics.Teacher', on_delete=models.CASCADE, related_name='credentials')
    name = models.CharField(max_length=150)
    issuer = models.CharField(max_length=150, blank=True, default='')
    number = models.CharField(max_length=100, blank=True, default='')
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True, db_index=True)
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['expires_on', 'name']


class PerformanceReview(TenantScopedModel):
    KINDS = [('annual', 'Annual review'), ('mid_year', 'Mid-year review'), ('probation', 'Probation review'),
             ('observation', 'Classroom observation')]
    STATUSES = [('draft', 'Draft'), ('shared', 'Shared with employee'), ('acknowledged', 'Acknowledged')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey('education_academics.Teacher', on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    kind = models.CharField(max_length=12, choices=KINDS, default='annual')
    period_label = models.CharField(max_length=60, blank=True, default='', help_text='For example 2026-27 or Term 1')
    review_date = models.DateField()
    rating = models.PositiveSmallIntegerField(null=True, blank=True, help_text='1 (needs improvement) to 5 (outstanding)')
    strengths = models.TextField(blank=True, default='')
    improvements = models.TextField(blank=True, default='')
    observed_class = models.CharField(max_length=120, blank=True, default='', help_text='Observations: which lesson')
    employee_comment = models.TextField(blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUSES, default='draft')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-review_date', '-created_at']


class StaffGoal(TenantScopedModel):
    STATUSES = [('open', 'In progress'), ('done', 'Achieved'), ('dropped', 'Dropped')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey('education_academics.Teacher', on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0, help_text='0 to 100')
    status = models.CharField(max_length=8, choices=STATUSES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['status', 'due_date']


class PayGrade(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    base_salary = models.DecimalField(**MONEY)
    notes = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['base_salary', 'name']
        constraints = [models.UniqueConstraint(fields=['tenant', 'name'], name='uniq_paygrade_name_per_school')]


class PayrollProfile(TenantScopedModel):
    """How one person's pay is built: grade, tax withholding and benefits. Used when payslips are generated."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.OneToOneField('education_academics.Teacher', on_delete=models.CASCADE, related_name='payroll_profile')
    pay_grade = models.ForeignKey(PayGrade, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles')
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'),
                                           help_text='Withheld from basic pay plus allowances')
    benefits = models.JSONField(default=list, blank=True,
                                help_text='List of {name, amount, kind} where kind is allowance or deduction')
    updated_at = models.DateTimeField(auto_now=True)
