from functools import cached_property

from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid

from services.core.db.softdelete import SoftDeleteModel
from services.core.storage.utils import student_profile_upload_to
from services.core.tenants.mixins import SchoolAliasMixin, TenantScopedModel


class Student(SchoolAliasMixin, SoftDeleteModel):
    tenant = models.ForeignKey(
        'core_tenants.School',
        on_delete=models.CASCADE,
        related_name='students',
        null=True,
        blank=True,
        db_index=True,
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], null=True, blank=True)
    guardian_name = models.CharField(max_length=255, blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True)
    father_name = models.CharField(max_length=255, blank=True)
    mother_name = models.CharField(max_length=255, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    additional_note = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # Extended "Other Information" / guardian detail fields
    discount_in_fee = models.CharField(max_length=20, blank=True, default='')
    identification_mark = models.TextField(blank=True, default='')
    blood_group = models.CharField(max_length=10, blank=True, default='')
    disease = models.TextField(blank=True, default='')
    birth_form_id = models.CharField(max_length=100, blank=True, default='')
    cast = models.CharField(max_length=100, blank=True, default='')
    previous_school = models.CharField(max_length=200, blank=True, default='')
    previous_id = models.CharField(max_length=100, blank=True, default='')
    orphan_student = models.CharField(max_length=20, blank=True, default='')
    osc = models.CharField(max_length=100, blank=True, default='')
    religion = models.CharField(max_length=100, blank=True, default='')
    select_family = models.CharField(max_length=100, blank=True, default='')
    family_type = models.CharField(max_length=100, blank=True, default='')
    total_siblings = models.IntegerField(null=True, blank=True)
    father_national_id = models.CharField(max_length=100, blank=True, default='')
    father_occupation = models.CharField(max_length=100, blank=True, default='')
    father_education = models.CharField(max_length=100, blank=True, default='')
    father_mobile = models.CharField(max_length=20, blank=True, default='')
    father_profession = models.CharField(max_length=100, blank=True, default='')
    father_income = models.CharField(max_length=20, blank=True, default='')
    mother_national_id = models.CharField(max_length=100, blank=True, default='')
    mother_occupation = models.CharField(max_length=100, blank=True, default='')
    mother_education = models.CharField(max_length=100, blank=True, default='')
    mother_mobile = models.CharField(max_length=20, blank=True, default='')
    mother_profession = models.CharField(max_length=100, blank=True, default='')
    mother_income = models.CharField(max_length=20, blank=True, default='')
    current_class = models.ForeignKey(
        'education_academics.SchoolClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        db_index=True,
    )
    current_section = models.ForeignKey(
        'education_academics.Section',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
    )
    household = models.ForeignKey(
        'Household', on_delete=models.SET_NULL, null=True, blank=True, related_name='students',
    )
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to=student_profile_upload_to,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['current_class', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    @property
    def class_obj(self):
        return self.current_class

    @class_obj.setter
    def class_obj(self, value):
        self.current_class = value

    @property
    def section(self):
        return self.current_section

    @section.setter
    def section(self, value):
        self.current_section = value

    def __str__(self):
        return self.display_label

    @cached_property
    def display_label(self) -> str:
        """Cached per-instance label for serializers and admin (avoids repeated string formatting)."""
        class_name = self.current_class.name if self.current_class_id else ''
        section_name = self.current_section.name if self.current_section_id else ''
        if class_name and section_name:
            return f'{self.full_name} ({self.student_id}) — {class_name}-{section_name}'
        return f'{self.full_name} ({self.student_id})'


class Certificate(models.Model):
    """Generated certificates for students and employees"""
    # School (tenant) this row belongs to; filled in automatically (tenants/scoping.py).
    tenant = models.ForeignKey('core_tenants.School', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='+', db_index=True)
    RECIPIENT_CHOICES = [
        ('student', 'Student'),
        ('employee', 'Employee'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.CharField(max_length=100)
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_CHOICES)
    recipient_name = models.CharField(max_length=255)
    recipient_id = models.CharField(max_length=100, blank=True, default='')
    recipient_details = models.JSONField(default=dict, blank=True)
    custom_text = models.TextField(blank=True, default='')
    issue_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.template} - {self.recipient_name}"

    class Meta:
        ordering = ['-issue_date', '-created_at']


# ---------------------------------------------------------------------------
# Households, guardians and health (international-standard student record).
# A student belongs to one household; a household has any number of guardians,
# and what each guardian may do for a given student (custody, pickup, billing,
# messages) lives on the StudentGuardian link.
# ---------------------------------------------------------------------------


class Household(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text='For example: Khan family')
    address = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    preferred_language = models.CharField(max_length=10, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Guardian(TenantScopedModel):
    RELATIONSHIPS = [
        ('mother', 'Mother'), ('father', 'Father'), ('stepmother', 'Stepmother'),
        ('stepfather', 'Stepfather'), ('grandparent', 'Grandparent'), ('aunt_uncle', 'Aunt or uncle'),
        ('sibling', 'Sibling'), ('legal_guardian', 'Legal guardian'), ('foster_parent', 'Foster parent'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    household = models.ForeignKey(Household, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='guardians')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, default='')
    relationship = models.CharField(max_length=20, choices=RELATIONSHIPS, default='other')
    email = models.EmailField(blank=True, default='')
    mobile_phone = models.CharField(max_length=30, blank=True, default='')
    home_phone = models.CharField(max_length=30, blank=True, default='')
    work_phone = models.CharField(max_length=30, blank=True, default='')
    occupation = models.CharField(max_length=100, blank=True, default='')
    employer = models.CharField(max_length=150, blank=True, default='')
    national_id = models.CharField(max_length=100, blank=True, default='')
    address = models.TextField(blank=True, default='', help_text='Only if different from the household')
    preferred_language = models.CharField(max_length=10, blank=True, default='')
    # Portal login for this guardian, once one has been issued.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='guardian_records')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def __str__(self):
        return self.full_name


class StudentGuardian(TenantScopedModel):
    """What one guardian may do for one student."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardian_links')
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name='student_links')
    is_primary = models.BooleanField(default=False, help_text='Main contact for this student')
    lives_with = models.BooleanField(default=True)
    has_custody = models.BooleanField(default=True, help_text='Legal custody; may make decisions')
    can_pickup = models.BooleanField(default=True, help_text='Allowed to collect the student from school')
    is_emergency_contact = models.BooleanField(default=True)
    receives_billing = models.BooleanField(default=False, help_text='Gets invoices and statements')
    receives_messages = models.BooleanField(default=True, help_text='Gets announcements and alerts')
    portal_access = models.BooleanField(default=True, help_text='May see this student in the parent portal')
    custody_notes = models.TextField(blank=True, default='',
                                     help_text='Court orders or restrictions the office must know about')
    priority = models.PositiveSmallIntegerField(default=1, help_text='Order to call in an emergency')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'created_at']
        constraints = [
            models.UniqueConstraint(fields=['student', 'guardian'], name='uniq_student_guardian'),
        ]


class StudentHealth(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='health')
    allergies = models.TextField(blank=True, default='')
    has_severe_allergy = models.BooleanField(default=False, help_text='For example, needs an EpiPen')
    medical_conditions = models.TextField(blank=True, default='')
    medications = models.TextField(blank=True, default='')
    dietary_restrictions = models.TextField(blank=True, default='')
    physician_name = models.CharField(max_length=150, blank=True, default='')
    physician_phone = models.CharField(max_length=30, blank=True, default='')
    insurance_provider = models.CharField(max_length=150, blank=True, default='')
    insurance_policy_number = models.CharField(max_length=100, blank=True, default='')
    emergency_treatment_consent = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)


class Immunization(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='immunizations')
    vaccine = models.CharField(max_length=100)
    dose = models.CharField(max_length=30, blank=True, default='')
    date_given = models.DateField(null=True, blank=True)
    exempt = models.BooleanField(default=False)
    exemption_reason = models.CharField(max_length=255, blank=True, default='')
    notes = models.CharField(max_length=255, blank=True, default='')
    next_due_date = models.DateField(null=True, blank=True, help_text='When the next dose is due, for reminders')
    reminder_sent_on = models.DateField(null=True, blank=True, help_text='Due date a reminder was last sent for')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['vaccine', 'date_given']

class Enrollment(TenantScopedModel):
    """Which class and section a student was in, from when to when, and how it ended."""
    STATUSES = [
        ('enrolled', 'Enrolled'), ('promoted', 'Promoted'), ('repeated', 'Repeated the year'),
        ('transferred', 'Moved to another class'), ('withdrawn', 'Left the school'), ('graduated', 'Graduated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    academic_year = models.ForeignKey('education_academics.AcademicYear', on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name='enrollments')
    school_class = models.ForeignKey('education_academics.SchoolClass', on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name='enrollments')
    section = models.ForeignKey('education_academics.Section', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='enrollments')
    class_name = models.CharField(max_length=80, blank=True, default='', help_text='Kept if the class is deleted')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default='enrolled')
    note = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date', '-created_at']


class StudentDocument(TenantScopedModel):
    """A file kept on a student's record: report, certificate, medical note, consent form and so on.

    Staff choose whether families can see it; files a family uploads are always visible to them and to staff.
    """
    CATEGORIES = [
        ('report', 'Report'), ('certificate', 'Certificate'), ('medical', 'Medical'), ('identity', 'Identity'),
        ('letter', 'Letter'), ('consent', 'Consent form'), ('assignment', 'Schoolwork'), ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='other')
    file = models.FileField(upload_to='student-documents/%Y/%m/')
    original_name = models.CharField(max_length=255, blank=True, default='')
    content_type = models.CharField(max_length=100, blank=True, default='')
    size = models.PositiveIntegerField(default=0)
    visible_to_family = models.BooleanField(default=True)
    from_family = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']


class ContactChangeRequest(TenantScopedModel):
    """A family asks the office to update household or guardian contact details; the office approves or declines."""
    STATUSES = [('pending', 'Waiting for the office'), ('approved', 'Updated'), ('declined', 'Declined')]
    HOUSEHOLD_FIELDS = ('address', 'city', 'state', 'postal_code', 'country', 'phone', 'email', 'preferred_language')
    GUARDIAN_FIELDS = ('first_name', 'last_name', 'email', 'mobile_phone', 'home_phone', 'work_phone', 'occupation',
                       'employer', 'address', 'preferred_language')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    household = models.ForeignKey(Household, on_delete=models.CASCADE, null=True, blank=True, related_name='change_requests')
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, null=True, blank=True, related_name='change_requests')
    # {field: {"from": old, "to": new}}
    changes = models.JSONField(default=dict)
    note = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUSES, default='pending')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    review_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


# ---- Front desk: safe pickup and visitors ---------------------------------------------------------------------

class AuthorizedAdult(TenantScopedModel):
    """An adult, besides the guardians on file, who may collect one student. Can also be marked do-not-release."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='authorized_adults')
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    photo_path = models.CharField(max_length=500, blank=True, default='')
    id_type = models.CharField(max_length=100, blank=True, default='')
    id_checked = models.BooleanField(default=False, help_text='Photo ID has been seen and recorded')
    do_not_release = models.BooleanField(default=False)
    court_order_note = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [models.Index(fields=['student', 'do_not_release'])]


class PickupRelease(TenantScopedModel):
    """One time a student left with someone. It is the record, so the screens never edit or delete it."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='pickup_releases')
    authorized_adult = models.ForeignKey(AuthorizedAdult, null=True, blank=True, on_delete=models.PROTECT, related_name='releases')
    guardian = models.ForeignKey('Guardian', null=True, blank=True, on_delete=models.PROTECT, related_name='pickup_releases')
    released_to_name = models.CharField(max_length=255, help_text='Name at the time of release')
    released_at = models.DateTimeField(default=timezone.now)
    early_dismissal = models.BooleanField(default=False)
    reason = models.CharField(max_length=500, blank=True, default='')
    id_confirmed = models.BooleanField(default=False)
    override_used = models.BooleanField(default=False)
    override_reason = models.TextField(blank=True, default='')
    released_by = models.ForeignKey('core_accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='pickup_releases_made')

    class Meta:
        ordering = ['-released_at']
        indexes = [models.Index(fields=['student', '-released_at'])]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(authorized_adult__isnull=False, guardian__isnull=True)
                       | models.Q(authorized_adult__isnull=True, guardian__isnull=False)),
                name='pickup_release_one_adult'),
        ]


class VisitorLog(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    organisation = models.CharField(max_length=255, blank=True, default='')
    visiting = models.CharField(max_length=255, blank=True, default='', help_text='Who or what they came to see')
    purpose = models.CharField(max_length=255, blank=True, default='')
    badge_number = models.CharField(max_length=50, blank=True, default='')
    checked_in_at = models.DateTimeField(default=timezone.now)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey('core_accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    checked_out_by = models.ForeignKey('core_accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-checked_in_at']
        indexes = [models.Index(fields=['tenant', 'checked_out_at'])]

    @property
    def on_site(self):
        return self.checked_out_at is None


# ---- Health office --------------------------------------------------------------------------------------------

class HealthVisit(TenantScopedModel):
    """Each time a student goes to the nurse."""
    VISIT_TYPES = [('injury', 'Injury'), ('illness', 'Illness'), ('medication', 'Medication'), ('assessment', 'Assessment'),
                   ('emergency', 'Emergency'), ('follow-up', 'Follow-up'), ('screening', 'Screening'), ('other', 'Other')]
    ACTIONS = [('treated', 'Treated at school'), ('rested', 'Rested and returned'), ('sent_home', 'Sent home'),
               ('hospital', 'Sent to hospital'), ('referred', 'Referred'), ('other', 'Other')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='health_visits')
    time_in = models.DateTimeField(default=timezone.now)
    time_out = models.DateTimeField(null=True, blank=True)
    visit_type = models.CharField(max_length=20, choices=VISIT_TYPES, default='illness')
    complaint = models.TextField(blank=True, default='')
    action_taken = models.CharField(max_length=20, choices=ACTIONS, blank=True, default='')
    action_notes = models.TextField(blank=True, default='')
    sent_home = models.BooleanField(default=False)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    recorded_by = models.ForeignKey('core_accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='health_visits_recorded')
    parent_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-time_in']
        indexes = [models.Index(fields=['student', '-time_in'])]


class MedicationAuthorization(TenantScopedModel):
    """What a parent has allowed the school to give. Doses can only be logged against a current one."""
    ROUTES = [('oral', 'Oral'), ('topical', 'Topical'), ('inhaled', 'Inhaled'), ('injection', 'Injection'), ('other', 'Other')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='medication_authorizations')
    medication_name = models.CharField(max_length=200)
    dose = models.CharField(max_length=100)
    route = models.CharField(max_length=20, choices=ROUTES, default='oral')
    times = models.CharField(max_length=200, blank=True, default='', help_text='For example "12:00" or "with lunch"')
    min_hours_between_doses = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Warn if a dose is logged sooner than this')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    instructions = models.TextField(blank=True, default='')
    prescriber = models.CharField(max_length=200, blank=True, default='')
    parent_consent = models.BooleanField(default=False)
    parent_consent_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date', '-created_at']
        indexes = [models.Index(fields=['student', 'is_active'])]

    def is_current(self, today=None):
        today = today or timezone.localdate()
        return bool(self.is_active and self.parent_consent and self.start_date <= today
                    and (self.end_date is None or today <= self.end_date))


class MedicationLog(TenantScopedModel):
    STATUSES = [('given', 'Given'), ('refused', 'Refused'), ('missed', 'Missed'), ('held', 'Held'), ('error', 'Error')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    authorization = models.ForeignKey(MedicationAuthorization, on_delete=models.CASCADE, related_name='logs')
    given_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUSES, default='given')
    dose_given = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    override_reason = models.TextField(blank=True, default='', help_text='Why a dose was given sooner than allowed')
    given_by = models.ForeignKey('core_accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='medications_given')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-given_at']
        indexes = [models.Index(fields=['authorization', '-given_at'])]
