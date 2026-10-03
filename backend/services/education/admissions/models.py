from django.conf import settings
from django.db import models
from django.utils import timezone
from services.core.tenants.mixins import TenantScopedModel
import secrets
import uuid


def _tracking_token():
    return secrets.token_urlsafe(24)


class Applicant(models.Model):
    # School (tenant) this row belongs to; filled in automatically (tenants/scoping.py).
    tenant = models.ForeignKey('core_tenants.School', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='+', db_index=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
    nationality = models.CharField(max_length=100, blank=True, default='')
    address = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    home_language = models.CharField(max_length=50, blank=True, default='')
    father_name = models.CharField(max_length=200, blank=True, default='')
    father_phone = models.CharField(max_length=20, blank=True, default='')
    father_occupation = models.CharField(max_length=100, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)
    mother_phone = models.CharField(max_length=20, blank=True)
    mother_occupation = models.CharField(max_length=100, blank=True)
    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    guardian_relation = models.CharField(max_length=50, blank=True)
    # Parents/guardians from the online form: [{first_name, last_name, relationship, email,
    # mobile_phone, occupation, lives_with, has_custody, can_pickup, receives_billing}, ...]
    guardians = models.JSONField(default=list, blank=True)
    previous_school = models.CharField(max_length=200, blank=True)
    previous_class = models.CharField(max_length=50, blank=True)
    previous_grade = models.CharField(max_length=10, blank=True)
    applying_for_class = models.CharField(max_length=50)
    applying_for_section = models.CharField(max_length=50, blank=True)
    academic_year = models.CharField(max_length=20, default='2026-2027')
    medical_notes = models.TextField(blank=True, default='')
    special_needs = models.TextField(blank=True, default='')
    sibling_at_school = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} - {self.applying_for_class}"

    class Meta:
        ordering = ['-created_at']


class Application(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewing', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('waitlisted', 'Waitlisted'),
        ('enrolled', 'Enrolled'),
        ('withdrawn', 'Withdrawn'),
    ]
    SOURCES = [('office', 'Entered by the office'), ('online', 'Online application')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_no = models.CharField(max_length=50, unique=True, editable=False)
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='applications')
    program = models.CharField(max_length=100, blank=True)
    semester = models.CharField(max_length=20, blank=True)
    academic_year = models.CharField(max_length=20, default='2026-2027')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    status_notes = models.TextField(blank=True)
    interview_date = models.DateTimeField(null=True, blank=True)
    interview_notes = models.TextField(blank=True)
    interview_rating = models.IntegerField(null=True, blank=True)
    ai_screening_score = models.IntegerField(null=True, blank=True, help_text='0-100, how well the application matches the school\'s admission criteria')
    ai_screening_summary = models.TextField(blank=True, default='')
    ai_screened_at = models.DateTimeField(null=True, blank=True)
    converted_to_student = models.ForeignKey('education_students.Student', on_delete=models.SET_NULL, null=True, blank=True)
    source = models.CharField(max_length=10, choices=SOURCES, default='office')
    # Lets the family check progress online without an account.
    tracking_token = models.CharField(max_length=40, default=_tracking_token, editable=False, db_index=True)
    # Electronic signature: typed full name plus agreement to the declarations.
    signature_name = models.CharField(max_length=200, blank=True, default='')
    signed_at = models.DateTimeField(null=True, blank=True)
    signature_ip = models.GenericIPAddressField(null=True, blank=True)
    consents = models.JSONField(default=dict, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    docs_reminded_at = models.DateTimeField(null=True, blank=True, help_text='When the family was last reminded about missing documents')
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.application_no:
            year = timezone.now().year
            # Numbers are unique across all schools, so look past the current school's scope.
            from services.core.tenants.context import use_tenant

            with use_tenant(None):
                last_app = Application.objects.filter(
                    application_no__startswith=f'APP-{year}').order_by('-application_no').first()
            if last_app:
                last_num = int(last_app.application_no.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            self.application_no = f'APP-{year}-{str(new_num).zfill(4)}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application_no} - {self.applicant.full_name}"

    class Meta:
        ordering = ['-submitted_at']


class ApplicationDocument(models.Model):
    """A file sent with an application (birth certificate, report card, photo and so on)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=60)
    file = models.FileField(upload_to='admissions/%Y/%m/')
    original_name = models.CharField(max_length=255, blank=True, default='')
    size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    review_status = models.CharField(max_length=10, default='pending',
                                     choices=[('pending', 'Not checked'), ('received', 'Received'), ('redo', 'Needs sending again')])
    review_note = models.CharField(max_length=255, blank=True, default='')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['uploaded_at']


class ApplicationEvent(models.Model):
    """Review history: every status change and note, with who made it."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='events')
    from_status = models.CharField(max_length=20, blank=True, default='')
    to_status = models.CharField(max_length=20, blank=True, default='')
    note = models.TextField(blank=True, default='')
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    by_name = models.CharField(max_length=200, blank=True, default='')
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['at']


class ReEnrollmentCampaign(models.Model):
    """Asks the families of current students whether they are returning next year."""
    tenant = models.ForeignKey('core_tenants.School', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='+', db_index=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, default='')
    closes_on = models.DateField(null=True, blank=True)
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ReEnrollmentResponse(models.Model):
    INTENTS = [('pending', 'No answer yet'), ('returning', 'Returning'), ('not_returning', 'Not returning'),
               ('undecided', 'Undecided')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(ReEnrollmentCampaign, on_delete=models.CASCADE, related_name='responses')
    student = models.ForeignKey('education_students.Student', on_delete=models.CASCADE, related_name='reenrollments')
    intent = models.CharField(max_length=20, choices=INTENTS, default='pending')
    reason = models.TextField(blank=True, default='')
    signature_name = models.CharField(max_length=200, blank=True, default='')
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+')

    class Meta:
        ordering = ['student__full_name']
        constraints = [models.UniqueConstraint(fields=['campaign', 'student'], name='uniq_reenrollment_student')]


# ---- Waitlist, tours and the application fee -------------------------------------------------------------------

class WaitlistConfig(TenantScopedModel):
    """How many seats a grade has for a year, and how the waiting list is ranked and offered."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class_name = models.CharField(max_length=50, help_text='Same wording as the class applied for, e.g. "Grade 5"')
    academic_year = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField(help_text='Seats for approved and enrolled children, plus offers still open')
    offer_hours = models.PositiveSmallIntegerField(default=72, help_text='How long a family has to answer an offer')
    sibling_priority = models.BooleanField(default=True)
    staff_child_priority = models.BooleanField(default=True)

    class Meta:
        ordering = ['academic_year', 'class_name']
        constraints = [models.UniqueConstraint(fields=['tenant', 'class_name', 'academic_year'], name='uniq_waitlist_grade_year')]

    def __str__(self):
        return f'{self.class_name} {self.academic_year} ({self.capacity} seats)'


class WaitlistEntry(TenantScopedModel):
    STATUSES = [('active', 'Waiting'), ('offered', 'Offered a seat'), ('accepted', 'Accepted'), ('declined', 'Declined'),
                ('expired', 'Offer expired'), ('removed', 'Removed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='waitlist_entry')
    staff_child = models.BooleanField(default=False)
    joined_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUSES, default='active')

    class Meta:
        ordering = ['joined_at']


class Offer(TenantScopedModel):
    STATUSES = [('offered', 'Open'), ('accepted', 'Accepted'), ('declined', 'Declined'), ('expired', 'Expired'), ('withdrawn', 'Withdrawn')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(WaitlistEntry, on_delete=models.CASCADE, related_name='offers')
    offered_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUSES, default='offered')
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-offered_at']
        constraints = [models.UniqueConstraint(fields=['entry'], condition=models.Q(status='offered'), name='one_open_offer_per_entry')]


class TourSlot(TenantScopedModel):
    """A time the school offers for a visit or an interview."""
    KINDS = [('tour', 'School tour'), ('interview', 'Interview')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=KINDS, default='tour')
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True, default='')
    host = models.CharField(max_length=200, blank=True, default='')
    capacity = models.PositiveSmallIntegerField(default=1, help_text='How many families can book this time')
    is_open = models.BooleanField(default=True)

    class Meta:
        ordering = ['starts_at']


class TourBooking(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slot = models.ForeignKey(TourSlot, on_delete=models.CASCADE, related_name='bookings')
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='tour_bookings')
    status = models.CharField(max_length=10, choices=[('booked', 'Booked'), ('cancelled', 'Cancelled')], default='booked')
    created_at = models.DateTimeField(auto_now_add=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['slot__starts_at']
        constraints = [models.UniqueConstraint(fields=['slot', 'application'], condition=models.Q(status='booked'), name='one_booking_per_slot_family')]


class ApplicationFee(TenantScopedModel):
    """The fee for applying. While it is unpaid the application is held and cannot move forward."""
    STATUSES = [('unpaid', 'Unpaid'), ('paid', 'Paid'), ('waived', 'Waived')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='fee')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=10, choices=STATUSES, default='unpaid')
    checkout_session_id = models.CharField(max_length=255, blank=True, default='')
    payment_reference = models.CharField(max_length=255, blank=True, default='')
    paid_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='application_fee_positive')]
