# Future Plan Progress: P5 - Admissions: Automatic Waitlist Offers, Tours, Documents, Application Fee

## ✅ IMPLEMENTATION COMPLETE

**Status**: Accepted - All four admission extensions implemented in the existing admissions app.

### What was implemented:

1. **New Models** (8 models added to `backend/services/education/admissions/models.py`):
   - `WaitlistConfig` - Capacity per grade/year with available seats tracking
   - `WaitlistEntry` - Waitlist positions with ranking scores
   - `Offer` - Generated offers with deadlines and status tracking
   - `TourSlot` - Tour/interview scheduling with capacity management
   - `TourBooking` - Applicant tour bookings with status tracking
   - `DocumentRequirement` - Configurable document requirements with file type/size limits
   - `DocumentSubmission` - Document upload/review workflow (pending/approved/rejected)
   - `ApplicationFee` - Fee tracking with Stripe payment intent integration

2. **Serializers** (in `backend/services/education/admissions/serializers.py`):
   - All 8 new models with appropriate nested relationships

3. **Views & API Endpoints** (in `backend/services/education/admissions/views.py`):
   - `WaitlistConfigViewSet` - Capacity management per grade/year
   - `WaitlistEntryViewSet` - Waitlist management with `generate_offers` action
   - `OfferViewSet` - Offer management with `accept`/`decline` actions
   - `TourSlotViewSet` - Tour scheduling with capacity tracking
   - `TourBookingViewSet` - Booking management with capacity enforcement
   - `DocumentRequirementViewSet` - Document checklist configuration
   - `DocumentSubmissionViewSet` - Upload/review workflow with `approve`/`reject` actions
   - `ApplicationFeeViewSet` - Fee tracking with `create_payment_intent`/`confirm_payment` actions

4. **URL Routes** (in `backend/services/education/admissions/urls.py`):
   - All 8 viewsets registered via DRF router

5. **Database Migration** - Applied successfully as `0005_applicationfee_documentrequirement_offer_tourslot_and_more.py`

### Key Features:
- ✅ Capacity tracking per grade/year with automatic seat calculation
- ✅ Waitlist ranking with automatic offer generation
- ✅ Offer deadlines (7 days) with accept/decline workflow
- ✅ Tour scheduling with capacity management
- ✅ Document checklist with upload/review/approval workflow
- ✅ Application fee with Stripe payment intent integration (mock)
- ✅ All models tenant-scoped for multi-school isolation

### Verification:
- ✅ Django system check passes
- ✅ Migration applied successfully
- ✅ Models accessible via Django ORM

---

## Overview
P5 extends the existing admissions system (P5 already has waitlist status, online form, and StudentDocument). It needs to implement FOUR new small tasks:
1. Waitlist offers (3-4 / 6-7 days)
2. Tours and interviews (3 / 5 days)
3. Document checklist (3-4 / 6-7 days)
4. Application fee (2 / 4 days)

**What Already Exists**:
- Waitlist status in applications
- Online admissions form
- StudentDocument model
- Stripe payment gateway (needs account setup)

**Missing Components**:
1. Capacity per grade/year tracking
2. Ranking rules (date, sibling priority, staff child)
3. Automatic offer generation when seats open
4. Tour slot management system
5. Document checklist with upload/review workflow
6. Application fee integration with Stripe
7. F2 scheduler dependencies (hr_alerts, refresh_cover jobs)

## Implementation Details

### 1. Waitlist Offers System

#### Data Models
```python
# File: backend/services/education/admissions/models.py

class WaitlistConfig(models.Model):
    school_year = models.ForeignKey(
        SchoolYear,
        on_delete=models.CASCADE
    )
    grade_level = models.CharField(max_length=50)
    capacity = models.IntegerField(help_text="Maximum students per grade")
    current_enrollment = models.IntegerField(default=0)
    waitlist_position = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['school_year', 'grade_level']
```

```python
# File: backend/services/education/admissions/models.py

class WaitlistEntry(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='waitlist_entries'
    )
    position = models.IntegerField()
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    offer_accepted = models.BooleanField(default=False)
    offer_accepted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['application', 'position']
        indexes = [
            models.Index(fields=['application', 'position']),
        ]
```

```python
# File: backend/services/education/admissions/models.py

class Offer(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='offers'
    )
    deadline_date = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('declined', 'Declined'),
            ('expired', 'Expired'),
        ],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

class Meta:
    verbose_name = "Offer"
    verbose_name_plural = "Offers"
```

#### Offer Generation Logic
```python
# File: backend/services/education/admissions/utils.py

def generate_offers():
    """Generate offers when seats open in a grade"""
    school_year = SchoolYear.objects.get(is_current=True)
    
    for config in WaitlistConfig.objects.filter(school_year=school_year):
        # Check if grade has available capacity
        enrolled_count = Application.objects.filter(
            grade_level=config.grade_level,
            status='accepted',
            school_year=school_year
        ).count()
        
        available_seats = config.capacity - enrolled_count
        
        if available_seats > 0:
            # Get waitlist applications
            waitlist_apps = Application.objects.filter(
                grade_level=config.grade_level,
                status='waitlisted',
                school_year=school_year
            ).order_by('ranking_score', 'application_date')
            
            # Generate offers for first N applicants
            for i, app in enumerate(waitlist_apps[:available_seats]):
                # Calculate offer deadline (7 days from now)
                deadline = timezone.now() + timezone.timedelta(days=7)
                
                offer = Offer.objects.create(
                    application=app,
                    deadline_date=deadline,
                    status='pending'
                )
                
                # Update waitlist entry
                waitlist_entry = WaitlistEntry.objects.get(
                    application=app,
                    position=i + 1
                )
                waitlist_entry.position = i + 1
                waitlist_entry.save()
                
                # Send email notification
                send_offer_email(app, offer)
```

#### Ranking Rules
```python
# File: backend/services/education/admissions/utils.py

def calculate_ranking_score(application):
    """Calculate ranking score for waitlist"""
    score = 0
    
    # Earlier applications get higher score
    days_old = (timezone.now() - application.application_date).days
    score += max(0, 100 - days_old)  # 100 points for new apps
    
    # Sibling priority
    if has_sibling_enrolled(application):
        score += 50
    
    # Staff child priority
    if is_staff_child(application):
        score += 30
    
    return score

def has_sibling_enrolled(application):
    """Check if application has siblings already enrolled"""
    student = application.student
    school_year = SchoolYear.objects.get(is_current=True)
    
    enrolled_siblings = Student.objects.filter(
        school=application.school,
        school_year=school_year,
        household=student.household
    ).exclude(id=student.id)
    
    return enrolled_siblings.exists()

def is_staff_child(application):
    """Check if applicant is a staff child"""
    # Check if any guardian is school staff
    for guardian in application.guardians.all():
        if guardian.user and guardian.user.is_staff:
            return True
    
    return False
```

### 2. Tour and Interview System

#### Data Models
```python
# File: backend/services/education/admissions/models.py

class TourSlot(models.Model):
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_participants = models.IntegerField()
    current_participants = models.IntegerField(default=0)
    location = models.CharField(max_length=255)
    zoom_link = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['date', 'start_time']
```

```python
# File: backend/services/education/admissions/models.py

class TourBooking(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='tour_bookings'
    )
    slot = models.ForeignKey(
        TourSlot,
        on_delete=models.PROTECT
    )
    booking_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
            ('no-show', 'No Show'),
        ],
        default='confirmed'
    )
    reminder_sent = models.DateTimeField(null=True, blank=True)

class Meta:
    verbose_name = "Tour Booking"
    verbose_name_plural = "Tour Bookings"
```

#### Tour Management
```python
# File: backend/services/education/admissions/views.py

class TourSlotViewSet(viewsets.ViewSet):
    def list_slots(self, request):
        school = request.user.school
        
        slots = TourSlot.objects.filter(
            school=school,
            date__gte=timezone.now().date()
        ).order_by('date', 'start_time')
        
        serializer = TourSlotSerializer(slots, many=True)
        return Response(serializer.data)

    def create_slot(self, request):
        if not request.user.is_admin:
            return Response(
                {'error': 'Only admins can create tour slots'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        data = request.data
        
        slot = TourSlot.objects.create(
            school=request.user.school,
            date=data['date'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            max_participants=data['max_participants'],
            location=data['location'],
            zoom_link=data.get('zoom_link', ''),
            notes=data.get('notes', '')
        )
        
        serializer = TourSlotSerializer(slot)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def book_slot(self, request, pk=None):
        application = request.user.application
        slot = get_object_or_404(TourSlot, pk=pk)
        
        # Check if slot has capacity
        if slot.current_participants >= slot.max_participants:
            return Response(
                {'error': 'Tour slot is full'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if application already booked
        if TourBooking.objects.filter(application=application).exists():
            return Response(
                {'error': 'Application already has a tour booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking = TourBooking.objects.create(
            application=application,
            slot=slot,
            status='confirmed'
        )
        
        slot.current_participants += 1
        slot.save()
        
        # Send confirmation email
        send_tour_confirmation(application, slot)
        
        serializer = TourBookingSerializer(booking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

### 3. Document Checklist System

#### Data Models
```python
# File: backend/services/education/admissions/models.py

class DocumentRequirement(models.Model):
    form_template = models.ForeignKey(
        FormTemplate,
        on_delete=models.CASCADE,
        related_name='requirements'
    )
    name = models.CharField(max_length=255)
    description = models.TextField()
    required = models.BooleanField(default=True)
    file_types = models.CharField(
        max_length=100,
        help_text="Comma-separated file types (pdf, jpg, png)"
    )
    max_size_mb = models.IntegerField(default=10)
    order = models.IntegerField(default=0)

class Meta:
    verbose_name = "Document Requirement"
    verbose_name_plural = "Document Requirements"
```

```python
# File: backend/services/education/admissions/models.py

class DocumentSubmission(models.Model):
    assignment = models.ForeignKey(
        FormAssignment,
        on_delete=models.CASCADE,
        related_name='document_submissions'
    )
    requirement = models.ForeignKey(
        DocumentRequirement,
        on_delete=models.PROTECT
    )
    file_path = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents'
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('needs_revision', 'Needs Revision'),
        ],
        default='pending'
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

class Meta:
    verbose_name = "Document Submission"
    verbose_name_plural = "Document Submissions"
    unique_together = ['assignment', 'requirement']
```

### 4. Application Fee System

#### Fee Integration with Stripe
```python
# File: backend/services/education/admissions/services.py

class ApplicationFeeService:
    def __init__(self):
        self.stripe = Stripe(settings.PLATFORM_STRIPE_SECRET_KEY)
    
    def create_payment_intent(self, application_id, amount, currency='usd'):
        """Create a Stripe payment intent for application fee"""
        application = get_object_or_404(Application, id=application_id)
        
        # Check if fee is required
        if not self.is_fee_required(application):
            return None
        
        try:
            intent = self.stripe.payment_intents.create(
                amount=amount * 100,  # Convert to cents
                currency=currency,
                metadata={
                    'application_id': application_id,
                    'student_name': application.student.get_full_name(),
                    'grade_level': application.grade_level,
                },
                payment_method_options={
                    'card': {
                        'request_three_d_secure': 'automatic'
                    }
                }
            )
            
            # Create application fee record
            fee = ApplicationFee.objects.create(
                application=application,
                amount=amount,
                currency=currency,
                stripe_payment_intent_id=intent.id,
                status='pending'
            )
            
            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'fee_id': fee.id,
                'amount': amount,
                'currency': currency,
            }
        except Exception as e:
            raise Exception(f"Failed to create payment intent: {str(e)}")
    
    def confirm_payment(self, payment_intent_id, application_id):
        """Confirm payment and update application status"""
        try:
            intent = self.stripe.payment_intents.retrieve(payment_intent_id)
            
            if intent.status != 'requires_payment_method':
                fee = get_object_or_404(ApplicationFee, stripe_payment_intent_id=payment_intent_id)
                
                if intent.status == 'succeeded':
                    fee.status = 'paid'
                    fee.paid_at = timezone.now()
                    fee.save()
                    
                    # Update application status to 'accepted' or keep as 'pending_payment'
                    application = fee.application
                    application.status = 'accepted'
                    application.save()
                    
                    # Send confirmation email
                    send_fee_confirmation(application, fee)
                    
                    return {'success': True, 'status': 'paid'}
                else:
                    fee.status = 'failed'
                    fee.failed_at = timezone.now()
                    fee.failure_reason = intent.last_payment_error
                    fee.save()
                    
                    return {'success': False, 'status': intent.status}
            
            return {'success': False, 'status': 'pending'}
        except Exception as e:
            raise Exception(f"Failed to confirm payment: {str(e)}")
    
    def is_fee_required(self, application):
        """Check if application fee is required"""
        # Logic to determine if fee applies
        # Could be based on grade, plan, etc.
        return True
```

### 5. Screens to Build

#### AdmissionsDashboard Component
```tsx
// File: frontend/src/pages/education/admissions/AdmissionsDashboard.tsx

import React, { useState, useEffect } from 'react';
import { admissionsDashboardService } from '../../services/admissionsDashboard.service';

const AdmissionsDashboard: React.FC = () => {
    const [stats, setStats] = useState({
        total_applications: 0,
        accepted: 0,
        waitlisted: 0,
        offers_sent: 0,
        tour_bookings: 0,
        documents_pending: 0,
        fees_pending: 0,
    });
    const [offers, setOffers] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadDashboardData();
        // Auto-refresh every 5 minutes
        const interval = setInterval(loadDashboardData, 300000);
        return () => clearInterval(interval);
    }, []);

    const loadDashboardData = async () => {
        setLoading(true);
        try {
            const data = await admissionsDashboardService.getDashboardStats();
            setStats(data.stats);
            setOffers(data.recent_offers);
        } finally {
            setLoading(false);
        }
    };

    const handleGenerateOffers = async () => {
        try {
            await admissionsDashboardService.generateWaitlistOffers();
            alert('Waitlist offers generated successfully');
            loadDashboardData();
        } catch (error) {
            alert('Failed to generate offers');
        }
    };

    const handleViewTourSlots = () => {
        // Navigate to tour management page
    };

    const handleViewDocumentTracker = () => {
        // Navigate to document tracker page
    };

    return (
        <div className="admissions-dashboard">
            <h2>Admissions Dashboard</h2>
            
            <div className="dashboard-stats">
                <div className="stat-card">
                    <h3>Total Applications</h3>
                    <p>{stats.total_applications}</p>
                </div>
                <div className="stat-card">
                    <h3>Accepted</h3>
                    <p>{stats.accepted}</p>
                </div>
                <div className="stat-card">
                    <h3>Waitlisted</h3>
                    <p>{stats.waitlisted}</p>
                </div>
                <div className="stat-card">
                    <h3>Offers Sent</h3>
                    <p>{stats.offers_sent}</p>
                </div>
                <div className="stat-card">
                    <h3>Tour Bookings</h3>
                    <p>{stats.tour_bookings}</p>
                </div>
                <div className="stat-card">
                    <h3>Docs Pending</h3>
                    <p>{stats.documents_pending}</p>
                </div>
                <div className="stat-card">
                    <h3>Fees Pending</h3>
                    <p>{stats.fees_pending}</p>
                </div>
            </div>

            <div className="dashboard-actions">
                <button
                    onClick={handleGenerateOffers}
                    className="generate-offers-btn"
                >
                    Generate Waitlist Offers
                </button>
                <button
                    onClick={handleViewTourSlots}
                    className="tour-management-btn"
                >
                    Manage Tour Slots
                </button>
                <button
                    onClick={handleViewDocumentTracker}
                    className="document-tracker-btn"
                >
                    Document Tracker
                </button>
            </div>

            <div className="recent-offers">
                <h3>Recent Offers</h3>
                {offers.length > 0 ? (
                    <table className="offers-table">
                        <thead>
                            <tr>
                                <th>Student</th>
                                <th>Grade</th>
                                <th>Offer Deadline</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {offers.map((offer) => (
                                <tr key={offer.id}>
                                    <td>{offer.studentName}</td>
                                    <td>{offer.gradeLevel}</td>
                                    <td>{new Date(offer.deadline).toLocaleDateString()}</td>
                                    <td>
                                        <span className={`status ${offer.status}`}>{offer.status}</span>
                                    </td>
                                    <td>
                                        <button className="view-btn">View</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : (
                    <p>No recent offers</p>
                )}
            </div>
        </div>
    );
};
```

### 6. Testing

#### Backend Tests
```python
# File: backend/tests/test_admissions_p5.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from admissions.models import Application, Offer, WaitlistConfig, TourSlot, TourBooking
from students.models import Student
from django.utils import timezone

class AdmissionsP5Tests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin',
            password='testpass',
            role='admin'
        )
        
        self.school = School.objects.create(
            name='Test School',
            domain='test.edu'
        )
        
        self.admin.school = self.school
        self.admin.save()
        
        # Create a student with application
        self.student = Student.objects.create(
            school=self.school,
            first_name='Test',
            last_name='Student',
            student_id='STU001'
        )
        
        self.application = Application.objects.create(
            school=self.school,
            student=self.student,
            grade_level='10',
            status='waitlisted',
            application_date=timezone.now() - timezone.timedelta(days=5)
        )
        
        self.client.force_login(self.admin)
        
        # Create waitlist config
        self.school_year = SchoolYear.objects.create(
            year='2026-2027',
            is_current=True
        )
        
        self.waitlist_config = WaitlistConfig.objects.create(
            school_year=self.school_year,
            grade_level='10',
            capacity=30,
            current_enrollment=25
        )

    def test_generate_offers(self):
        response = self.client.post('/api/admissions/generate-offers/')
        
        self.assertEqual(response.status_code, 200)
        
        # Check that offers were created
        self.assertTrue(Offer.objects.filter(application=self.application).exists())
        
        offer = Offer.objects.get(application=self.application)
        self.assertEqual(offer.status, 'pending')
        self.assertLess(offer.deadline_date, timezone.now() + timezone.timedelta(days=8))

    def test_tour_booking(self):
        # Create a tour slot
        tour_slot = TourSlot.objects.create(
            school=self.school,
            date=timezone.now().date() + timezone.timedelta(days=7),
            start_time='14:00',
            end_time='15:00',
            max_participants=10,
            location='Room 101'
        )
        
        response = self.client.post(f'/api/admissions/tour-booking/{tour_slot.id}/', {
            'application_id': self.application.id,
        })
        
        self.assertEqual(response.status_code, 201)
        
        booking = TourBooking.objects.get(application=self.application)
        self.assertEqual(booking.slot, tour_slot)
        self.assertEqual(booking.status, 'confirmed')
        
        tour_slot.refresh_from_db()
        self.assertEqual(tour_slot.current_participants, 1)

    def test_document_submission(self):
        # Create a document requirement
        template = FormTemplate.objects.create(
            title='Admission Documents',
            body='Please upload required documents',
            audience='class',
            audience_target='10',
            due_date=timezone.now() + timezone.timedelta(days=10),
            questions=[]
        )
        
        requirement = DocumentRequirement.objects.create(
            form_template=template,
            name='Transcripts',
            description='High school transcripts',
            required=True,
            file_types='pdf',
            max_size_mb=20
        )
        
        response = self.client.post('/api/admissions/documents/upload/', {
            'application_id': self.application.id,
            'requirement_id': requirement.id,
            'notes': 'Uploaded PDFs',
        })
        
        self.assertEqual(response.status_code, 201)
        
        submission = DocumentSubmission.objects.get(application=self.application)
        self.assertEqual(submission.requirement, requirement)
        self.assertEqual(submission.status, 'pending')

    def test_application_fee_payment(self):
        # Create payment intent
        response = self.client.post('/api/admissions/fee/payment-intent/', {
            'application_id': self.application.id,
            'amount': 100.00,
            'currency': 'usd',
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('client_secret', response.data)
        
        # Simulate payment confirmation (in real scenario, Stripe webhook)
        payment_intent_id = response.data['payment_intent_id']
        
        response = self.client.post('/api/admissions/fee/confirm-payment/', {
            'payment_intent_id': payment_intent_id,
            'application_id': self.application.id,
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'accepted')
```

#### Frontend Tests
```typescript
// File: frontend/src/components/admissions/__tests__/AdmissionsDashboard.test.tsx

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AdmissionsDashboard } from '../AdmissionsDashboard';
import { admissionsDashboardService } from '../../services/admissionsDashboard.service';

jest.mock('../../services/admissionsDashboard.service');

const mockAdmissionsDashboardService = admissionsDashboardService as jest.Mocked<typeof admissionsDashboardService>;

describe('AdmissionsDashboard', () => {
    const mockStats = {
        total_applications: 150,
        accepted: 45,
        waitlisted: 75,
        offers_sent: 20,
        tour_bookings: 30,
        documents_pending: 25,
        fees_pending: 10,
    };
    
    const mockOffers = [
        {
            id: '1',
            studentName: 'John Doe',
            gradeLevel: '10',
            deadline: new Date().toISOString(),
            status: 'pending',
        },
    ];

    beforeEach(() => {
        mockAdmissionsDashboardService.getDashboardStats.mockResolvedValue({
            stats: mockStats,
            recent_offers: mockOffers,
        });
        mockAdmissionsDashboardService.generateWaitlistOffers.mockResolvedValue();
    });

    it('allows admin to generate waitlist offers', async () => {
        render(<AdmissionsDashboard />);
        
        await waitFor(() => {
            expect(screen.getByText('150')).toBeInTheDocument();
        });
        
        fireEvent.click(screen.getByText('Generate Waitlist Offers'));
        
        await waitFor(() => {
            expect(mockAdmissionsDashboardService.generateWaitlistOffers).toHaveBeenCalled();
        });
    });
});
```

### 7. User Manual Update
```markdown
# Admissions: Waitlist, Tours, Documents, and Fees

## Who Can Use
- **Admin/Office staff**: Generate offers, manage tours, track documents, process fees
- **Admissions team**: Full access to all admissions features

## How to Use

### Generating Waitlist Offers
1. Go to **Admissions** → **Dashboard**
2. Click **Generate Waitlist Offers**
3. System automatically:
   - Checks available seats per grade
   - Ranks waitlist applicants (earlier applications, siblings, staff children)
   - Generates offers with 7-day deadlines
   - Sends email notifications to accepted applicants

**Offer Features**:
- **Ranking**: Applications are ranked by date (higher score), sibling priority (+50), staff children (+30)
- **Deadline**: 7 days to accept or decline
- **Status tracking**: Pending, Accepted, Declined, Expired

### Managing Tour Slots
1. Go to **Admissions** → **Tours**
2. **Create Tour Slots**:
   - Set date, start/end time
   - Maximum participants (e.g., 10)
   - Location or Zoom link
3. **Book Tours**:
   - Applications can book their preferred slot
   - System shows availability
   - Automated confirmation emails

### Document Checklist
1. Go to **Admissions** → **Documents**
2. **Set Up Requirements**:
   - Define documents needed (transcripts, ID, etc.)
   - Set file types and size limits
   - Set due dates
3. **Track Submissions**:
   - View status: Pending, Approved, Rejected, Needs Revision
   - Send reminders for overdue submissions
   - Export reports (CSV/PDF)

### Application Fee Processing
1. Go to **Admissions** → **Fees**
2. **Set Up Fees**:
   - Define fee amount (e.g., $100)
   - Configure currency
   - Set up Stripe integration
3. **Process Payments**:
   - Create Stripe payment intents
   - Track payment status
   - Automatically accept applications upon payment

## Integration Notes

### Waitlist Offers Dependencies
- **F2 scheduler**: Daily job to check for seat availability
- **HR jobs**: `send_hr_alerts`, `refresh_cover` for staff notifications
- **Email templates**: Offer acceptance, rejection, deadline reminders

### Tour Management
- **Calendar integration**: With school calendar system
- **Capacity management**: Prevent overbooking
- **Automated reminders**: Day before tour

### Document Workflow
- **Upload restrictions**: File types, size limits enforced
- **Status tracking**: Clear workflow from submission to approval
- **Audit trail**: All document actions logged

### Fee Processing
- **Stripe integration**: Platform-wide payment processing
- **Webhook handling**: Real-time payment confirmation
- **Automatic acceptance**: Applications accepted immediately upon payment

## Notes
- All features integrate with the existing admissions workflow
- Email notifications sent for all major actions
- Overdue items automatically tracked and flagged
- Full audit trail maintained for compliance
- Integration with F2 scheduler for automated tasks
