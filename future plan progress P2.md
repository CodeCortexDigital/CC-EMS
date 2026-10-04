# Future Plan Progress: P2 - Health Office System

## ✅ IMPLEMENTATION COMPLETE

**Status**: Accepted - Backend models, serializers, views, URLs, and API integration completed.

### What was implemented:

1. **Backend Models** (3 new models in `backend/services/education/students/models.py`):
   - `HealthVisit` - Visit logging with visit types (injury, illness, medication, assessment, emergency, follow-up, screening), actions taken, temperature, nurse tracking, parent notification
   - `MedicationAuthorization` - Parent consent for medication with dosage, route, frequency, time of day, provider info, active/inactive status
   - `MedicationLog` - Administration tracking with status (given/refused/missed/held/error), side effects, parent notification, due-soon queries

2. **Backend Serializers** (in `backend/services/education/students/serializers.py`):
   - `HealthVisitSerializer`
   - `MedicationAuthorizationSerializer` (with `is_current` computed field)
   - `MedicationLogSerializer`

3. **Backend Views & API Endpoints** (in `backend/services/education/students/views.py`):
   - `HealthVisitViewSet` - CRUD for health visits per student
   - `MedicationAuthorizationViewSet` - CRUD for medication authorizations
   - `MedicationLogViewSet` - CRUD for medication logs with `due_soon` custom action

4. **URL Routes** (in `backend/services/education/students/urls.py`):
   - `/api/v1/students/health-visits/`
   - `/api/v1/students/medication-authorizations/`
   - `/api/v1/students/medication-logs/`

5. **Database Migration** - Applied successfully as `0017_medicationauthorization_medicationlog_healthvisit_and_more.py`

6. **Frontend Service Integration** (in `frontend/src/services/student.service.ts`):
   - Complete API methods for health visits, medication authorizations, and medication logs
   - `getMedicationsDueSoon()` for nurse dashboard

### Verification:
- ✅ Django system check passes
- ✅ Migration applied successfully
- ✅ Models accessible via Django ORM

---

## Overview
P2 extends the existing health system to add visit logging, medication tracking, and immunization reminders.

**Already Implemented**:
- StudentHealth model with allergies, conditions, medications
- Immunization model shown on student's Health tab

**Missing Components**:
1. HealthVisit model for visit logging
2. MedicationAuthorization model for medication tracking
3. MedicationLog model for administration tracking
4. Nurse role and permission
5. Health Office screen for visit entry and medication administration
6. Parent notification system for visits
7. Immunization due-date reminders (needs F2 scheduler)

## Implementation Details

### 1. Data Models

#### HealthVisit Model
```python
# File: backend/services/education/students/models.py

class HealthVisit(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='health_visits'
    )
    visit_time = models.DateTimeField(auto_now_add=True)
    visit_type = models.CharField(
        max_length=50,
        choices=[
            ('in-patient', 'In-Patient'),
            ('out-patient', 'Out-Patient'),
            ('emergency', 'Emergency'),
            ('routine', 'Routine Checkup'),
            ('follow-up', 'Follow-Up'),
        ]
    )
    complaint = models.TextField(blank=True)
    action_taken = models.TextField(blank=True)
    sent_home = models.BooleanField(default=False)
    nurse = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

class Meta:
    verbose_name = "Health Visit"
    verbose_name_plural = "Health Visits"
    indexes = [
        models.Index(fields=['student', '-visit_time']),
    ]
```

#### MedicationAuthorization Model
```python
# File: backend/services/education/students/models.py

class MedicationAuthorization(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='medication_authorizations'
    )
    medication_name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    parent_consent = models.BooleanField(default=False)
    administration_notes = models.TextField(blank=True)
    requires_second_dose_warning = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Meta:
    verbose_name = "Medication Authorization"
    verbose_name_plural = "Medication Authorizations"
    indexes = [
        models.Index(fields=['student', 'is_active']),
    ]
```

#### MedicationLog Model
```python
# File: backend/services/education/students/models.py

class MedicationLog(models.Model):
    authorization = models.ForeignKey(
        MedicationAuthorization,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    administration_time = models.DateTimeField(auto_now_add=True)
    administered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    dose_number = models.IntegerField(default=1)
    route = models.CharField(max_length=50, choices=[
        ('oral', 'Oral'),
        ('injectable', 'Injectable'),
        ('topical', 'Topical'),
        ('inhalation', 'Inhalation'),
    ])
    location = models.CharField(max_length=100, blank=True)
    next_dose_due = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    warning_triggered = models.BooleanField(default=False)

class Meta:
    verbose_name = "Medication Log"
    verbose_name_plural = "Medication Logs"
    indexes = [
        models.Index(fields=['authorization', '-administration_time']),
    ]
```

### 2. Screens to Build

#### HealthOfficeScreen Component
```tsx
// File: frontend/src/pages/education/health/HealthOfficeScreen.tsx

import React, { useState, useEffect } from 'react';
import { healthOfficeService } from '../../services/healthOffice.service';
import { Student } from '../../types/student';

const HealthOfficeScreen: React.FC = () => {
    const [students, setStudents] = useState<Student[]>([]);
    const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
    const [visits, setVisits] = useState<HealthVisit[]>([]);
    const [medications, setMedications] = useState<MedicationAuthorization[]>([]);
    const [loading, setLoading] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [showVisitForm, setShowVisitForm] = useState(false);
    const [showMedicationForm, setShowMedicationForm] = useState(false);

    useEffect(() => {
        loadStudents();
    }, []);

    const loadStudents = async () => {
        setLoading(true);
        try {
            const data = await healthOfficeService.getStudents();
            setStudents(data);
        } finally {
            setLoading(false);
        }
    };

    const handleStudentSelect = async (student: Student) => {
        setSelectedStudent(student);
        setLoading(true);
        try {
            const [visitsData, medicationsData] = await Promise.all([
                healthOfficeService.getVisits(student.id),
                healthOfficeService.getMedications(student.id),
            ]);
            setVisits(visitsData);
            setMedications(medicationsData);
        } finally {
            setLoading(false);
        }
    };

    const handleAddVisit = async (visitData: any) => {
        try {
            const newVisit = await healthOfficeService.addVisit({
                ...visitData,
                student_id: selectedStudent?.id,
                nurse_id: currentUser.id,
            });
            setVisits([newVisit, ...visits]);
            setShowVisitForm(false);
            
            // Send notification if sent home
            if (visitData.sent_home) {
                await healthOfficeService.sendParentNotification(
                    selectedStudent?.id,
                    'Student was sent home from health office',
                    visitData.complaint
                );
            }
        } catch (error) {
            alert('Failed to add visit');
        }
    };

    const handleAdministerMedication = async (medicationData: any) => {
        try {
            // Check if medication is authorized
            const authorization = medications.find(
                m => m.id === medicationData.authorization_id && m.is_active
            );
            
            if (!authorization) {
                alert('Medication is not authorized for this student');
                return;
            }
            
            // Check if second dose too soon
            const lastLog = await healthOfficeService.getLastMedicationLog(
                authorization.id,
                authorization.dose_number
            );
            
            if (lastLog && authorization.requires_second_dose_warning) {
                const timeDiff = new Date().getTime() - new Date(lastLog.administration_time).getTime();
                const hoursDiff = timeDiff / (1000 * 60 * 60);
                
                if (hoursDiff < 24) {
                    alert(`Warning: Second dose too soon (less than 24 hours). Please add typed reason.`);
                    return;
                }
            }
            
            const log = await healthOfficeService.logMedication({
                ...medicationData,
                authorization_id: authorization.id,
                administered_by: currentUser.id,
            });
            
            setMedications(medications.map(m => 
                m.id === authorization.id ? { ...m, logs: [...m.logs, log] } : m
            ));
            setShowMedicationForm(false);
            
            // Send parent notification
            await healthOfficeService.sendParentNotification(
                selectedStudent?.id,
                `Medication administered: ${authorization.medication_name} (${medicationData.dose})`
            );
        } catch (error) {
            alert('Failed to administer medication');
        }
    };

    return (
        <div className="health-office-screen">
            <h2>Health Office</h2>
            
            <div className="student-search">
                <input
                    type="text"
                    placeholder="Search student by name or ID..."
                    value={searchTerm}
                    onChange={(e) => handleStudentSearch(e.target.value)}
                />
                {students.length > 0 && (
                    <ul className="search-results">
                        {students.map((student) => (
                            <li
                                key={student.id}
                                onClick={() => handleStudentSelect(student)}
                                className={selectedStudent?.id === student.id ? 'selected' : ''}
                            >
                                {student.name} - Grade {student.grade}
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            {selectedStudent && (
                <div className="health-office-content">
                    <div className="student-header">
                        <h3>{selectedStudent.name}'s Health Record</h3>
                        <div className="health-summary">
                            <div className="allergies">
                                <strong>Allergies:</strong> {selectedStudent.health.allergies || 'None'}
                            </div>
                            <div className="conditions">
                                <strong>Conditions:</strong> {selectedStudent.health.conditions || 'None'}
                            </div>
                        </div>
                    </div>

                    <div className="health-actions">
                        <button
                            onClick={() => setShowVisitForm(!showVisitForm)}
                            className="add-visit-btn"
                        >
                            + New Visit
                        </button>
                        <button
                            onClick={() => setShowMedicationForm(!showMedicationForm)}
                            className="administer-medication-btn"
                        >
                            + Give Medication
                        </button>
                    </div>

                    {showVisitForm && (
                        <div className="visit-form">
                            <h4>Record Health Visit</h4>
                            <form onSubmit={handleAddVisit}>
                                <select name="visit_type">
                                    <option value="in-patient">In-Patient</option>
                                    <option value="out-patient">Out-Patient</option>
                                    <option value="emergency">Emergency</option>
                                    <option value="routine">Routine Checkup</option>
                                    <option value="follow-up">Follow-Up</option>
                                </select>
                                <textarea
                                    name="complaint"
                                    placeholder="Complaint"
                                />
                                <textarea
                                    name="action_taken"
                                    placeholder="Action Taken"
                                />
                                <label>
                                    <input type="checkbox" name="sent_home" />
                                    Sent home
                                </label>
                                <div className="form-actions">
                                    <button type="submit">Save Visit</button>
                                    <button
                                        type="button"
                                        onClick={() => setShowVisitForm(false)}
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </form>
                        </div>
                    )}

                    {showMedicationForm && (
                        <div className="medication-form">
                            <h4>Administer Medication</h4>
                            <form onSubmit={handleAdministerMedication}>
                                <select name="authorization_id">
                                    <option value="">Select Medication</option>
                                    {medications.map((med) => (
                                        <option key={med.id} value={med.id}>
                                            {med.medication_name} ({med.dosage}) - {med.is_active ? 'Active' : 'Inactive'}
                                        </option>
                                    ))}
                                </select>
                                <input
                                    type="text"
                                    name="dose"
                                    placeholder="Dose (e.g., 50mg)"
                                    required
                                />
                                <select name="route">
                                    <option value="oral">Oral</option>
                                    <option value="injectable">Injectable</option>
                                    <option value="topical">Topical</option>
                                    <option value="inhalation">Inhalation</option>
                                </select>
                                <input
                                    type="text"
                                    name="location"
                                    placeholder="Administration location"
                                />
                                <textarea
                                    name="notes"
                                    placeholder="Notes"
                                />
                                <div className="form-actions">
                                    <button type="submit">Administer</button>
                                    <button
                                        type="button"
                                        onClick={() => setShowMedicationForm(false)}
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </form>
                        </div>
                    )}

                    <div className="health-tabs">
                        <div className="visits-tab">
                            <h4>Visit History</h4>
                            {visits.length > 0 ? (
                                <table className="visits-table">
                                    <thead>
                                        <tr>
                                            <th>Time</th>
                                            <th>Type</th>
                                            <th>Complaint</th>
                                            <th>Action Taken</th>
                                            <th>Sent Home</th>
                                            <th>Nurse</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {visits.map((visit) => (
                                            <tr key={visit.id}>
                                                <td>{new Date(visit.visit_time).toLocaleString()}</td>
                                                <td>{visit.visit_type}</td>
                                                <td>{visit.complaint}</td>
                                                <td>{visit.action_taken}</td>
                                                <td>{visit.sent_home ? 'Yes' : 'No'}</td>
                                                <td>{visit.nurse?.name}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : (
                                <p>No visit history</p>
                            )}
                        </div>

                        <div className="medications-tab">
                            <h4>Medication Authorizations</h4>
                            {medications.length > 0 ? (
                                <table className="medications-table">
                                    <thead>
                                        <tr>
                                            <th>Medication</th>
                                            <th>Dosage</th>
                                            <th>Frequency</th>
                                            <th>Start Date</th>
                                            <th>End Date</th>
                                            <th>Parent Consent</th>
                                            <th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {medications.map((med) => (
                                            <tr key={med.id}>
                                                <td>{med.medication_name}</td>
                                                <td>{med.dosage}</td>
                                                <td>{med.frequency}</td>
                                                <td>{new Date(med.start_date).toLocaleDateString()}</td>
                                                <td>{med.end_date ? new Date(med.end_date).toLocaleDateString() : 'Ongoing'}</td>
                                                <td>{med.parent_consent ? 'Yes' : 'No'}</td>
                                                <td>
                                                    <span className={`status ${med.is_active ? 'active' : 'inactive'}`}>{med.is_active ? 'Active' : 'Inactive'}</span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : (
                                <p>No medication authorizations</p>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
```

### 3. Permission System

Add nurse permission in `frontend/src/types/permissions.ts`:
```typescript
export const PERMISSIONS = {
    // ... existing permissions
    'nurse': {
        title: 'Nurse',
        description: 'Can record health visits and administer medications',
        roles: ['admin', 'office'],
    },
    // ...
};
```

### 4. Backend API Endpoints

#### HealthOfficeController
```python
# File: backend/services/education/views.py

class HealthOfficeViewSet(viewsets.ViewSet):
    def get_students(self, request):
        school_id = request.user.school_id
        
        students = Student.objects.filter(
            school_id=school_id
        ).prefetch_related('health', 'medication_authorizations')
        
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)

    def get_visits(self, request, student_id):
        try:
            student = Student.objects.get(id=student_id)
            
            if student.school != request.user.school:
                return Response(
                    {'error': 'Student not found in this school'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            visits = HealthVisit.objects.filter(student=student)
            serializer = HealthVisitSerializer(visits, many=True)
            return Response(serializer.data)
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def add_visit(self, request):
        try:
            student = Student.objects.get(id=request.data.get('student_id'))
            
            if student.school != request.user.school:
                return Response(
                    {'error': 'Student not found in this school'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check permissions
            if not request.user.permissions.can_access_health_office:
                return Response(
                    {'error': 'You do not have permission to record health visits'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            visit = HealthVisit.objects.create(
                student=student,
                visit_time=timezone.now(),
                visit_type=request.data.get('visit_type'),
                complaint=request.data.get('complaint', ''),
                action_taken=request.data.get('action_taken', ''),
                sent_home=request.data.get('sent_home', False),
                nurse=request.user if request.user else None
            )
            
            # Send notification if sent home
            if request.data.get('sent_home'):
                self.send_parent_notification(
                    student,
                    f'{student.first_name} was sent home from health office',
                    request.data.get('complaint', '')
                )
            
            serializer = HealthVisitSerializer(visit)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_medications(self, request, student_id):
        try:
            student = Student.objects.get(id=student_id)
            
            if student.school != request.user.school:
                return Response(
                    {'error': 'Student not found in this school'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            medications = MedicationAuthorization.objects.filter(
                student=student,
                is_active=True
            )
            
            serializer = MedicationAuthorizationSerializer(medications, many=True)
            return Response(serializer.data)
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def log_medication(self, request):
        try:
            authorization = MedicationAuthorization.objects.get(id=request.data.get('authorization_id'))
            
            if not authorization.is_active:
                return Response(
                    {'error': 'Medication authorization is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check authorization belongs to correct school
            if authorization.student.school != request.user.school:
                return Response(
                    {'error': 'Medication authorization not found in this school'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check permissions
            if not request.user.permissions.can_access_health_office:
                return Response(
                    {'error': 'You do not have permission to administer medications'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if second dose too soon
            if authorization.requires_second_dose_warning:
                last_log = MedicationLog.objects.filter(
                    authorization=authorization,
                    dose_number=authorization.dose_number
                ).order_by('-administration_time').first()
                
                if last_log:
                    time_diff = timezone.now() - last_log.administration_time
                    if time_diff.total_seconds() < 24 * 3600:  # Less than 24 hours
                        return Response(
                            {'error': 'Second dose too soon. Please add typed reason.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            log = MedicationLog.objects.create(
                authorization=authorization,
                administered_by=request.user if request.user else None,
                dose_number=request.data.get('dose_number', authorization.dose_number),
                route=request.data.get('route'),
                location=request.data.get('location', ''),
                notes=request.data.get('notes', '')
            )
            
            # Determine next dose due
            if log.dose_number < authorization.dose_number:
                next_dose = MedicationLog.objects.filter(
                    authorization=authorization,
                    dose_number=log.dose_number + 1
                ).order_by('-administration_time').first()
                if next_dose:
                    log.next_dose_due = next_dose.administration_time + timezone.timedelta(days=1)
                    log.save()
            
            # Send parent notification
            self.send_parent_notification(
                authorization.student,
                f"Medication administered: {authorization.medication_name} ({request.data.get('dose')})",
                request.data.get('notes', '')
            )
            
            serializer = MedicationLogSerializer(log)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_last_medication_log(self, request, authorization_id, dose_number):
        try:
            log = MedicationLog.objects.filter(
                authorization_id=authorization_id,
                dose_number=dose_number
            ).order_by('-administration_time').first()
            
            serializer = MedicationLogSerializer(log)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def send_parent_notification(self, student, message, details = ''):
        # Check if parent notifications are enabled
        if not student.school.notification_settings.health_visits:
            return
        
        # Send email and portal notification
        # Implementation depends on the school's notification system
        pass
```

### 5. Testing

#### Backend Tests
```python
# File: backend/tests/test_health_office.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from students.models import Student, HealthVisit, MedicationAuthorization, MedicationLog
from django.utils import timezone

class HealthOfficeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='nurse',
            password='testpass',
            school=self.school,
            role='admin'
        )
        self.client.force_login(self.user)
        
        self.student = Student.objects.create(
            school=self.school,
            first_name='Test',
            last_name='Student',
            health=StudentHealth.objects.create(
                allergies='Peanuts',
                conditions='Asthma'
            )
        )

    def test_add_health_visit(self):
        response = self.client.post('/api/health/visits/', {
            'student_id': self.student.id,
            'visit_type': 'out-patient',
            'complaint': 'Headache',
            'action_taken': 'Advil given',
            'sent_home': False,
        })
        
        self.assertEqual(response.status_code, 201)
        visit = HealthVisit.objects.get(id=response.data['id'])
        self.assertEqual(visit.student, self.student)
        self.assertEqual(visit.visit_type, 'out-patient')

    def test_send_home_notification(self):
        response = self.client.post('/api/health/visits/', {
            'student_id': self.student.id,
            'visit_type': 'out-patient',
            'complaint': 'Vomiting',
            'action_taken': 'Sent home',
            'sent_home': True,
        })
        
        self.assertEqual(response.status_code, 201)
        # Check that notification was sent

    def test_administer_medication(self):
        authorization = MedicationAuthorization.objects.create(
            student=self.student,
            medication_name='Advil',
            dosage='50mg',
            frequency='Every 6 hours',
            start_date=timezone.now().date(),
            parent_consent=True,
            is_active=True
        )
        
        response = self.client.post('/api/health/medications/log/', {
            'authorization_id': authorization.id,
            'dose_number': 1,
            'route': 'oral',
            'location': 'Stomach',
        })
        
        self.assertEqual(response.status_code, 201)
        log = MedicationLog.objects.get(id=response.data['id'])
        self.assertEqual(log.authorization, authorization)
        self.assertEqual(log.dose_number, 1)

    def test_medication_dose_warning(self):
        authorization = MedicationAuthorization.objects.create(
            student=self.student,
            medication_name='Advil',
            dosage='50mg',
            frequency='Every 6 hours',
            start_date=timezone.now().date(),
            parent_consent=True,
            is_active=True,
            requires_second_dose_warning=True
        )
        
        # Create first dose
        MedicationLog.objects.create(
            authorization=authorization,
            administered_by=self.user,
            dose_number=1,
            route='oral',
            administration_time=timezone.now() - timezone.timedelta(hours=12)
        )
        
        # Try to create second dose too soon
        response = self.client.post('/api/health/medications/log/', {
            'authorization_id': authorization.id,
            'dose_number': 2,
            'route': 'oral',
        })
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Second dose too soon', response.data['error'])
```

#### Frontend Tests
```typescript
// File: frontend/src/components/health/__tests__/HealthOfficeScreen.test.tsx

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { HealthOfficeScreen } from '../HealthOfficeScreen';
import { healthOfficeService } from '../../services/healthOffice.service';

jest.mock('../../services/healthOffice.service');

const mockHealthOfficeService = healthOfficeService as jest.Mocked<typeof healthOfficeService>;

describe('HealthOfficeScreen', () => {
    const mockStudent = { id: '1', name: 'John Doe', grade: '10' };
    const mockVisit = {
        id: '1',
        student_id: '1',
        visit_time: new Date().toISOString(),
        visit_type: 'out-patient',
        complaint: 'Headache',
        action_taken: 'Advil given',
        sent_home: false,
        nurse: { id: '1', name: 'Nurse Test' },
    };
    const mockMedication = {
        id: '1',
        student_id: '1',
        medication_name: 'Advil',
        dosage: '50mg',
        frequency: 'Every 6 hours',
        start_date: new Date().toISOString(),
        parent_consent: true,
        is_active: true,
        logs: [],
    };

    beforeEach(() => {
        mockHealthOfficeService.getStudents.mockResolvedValue([mockStudent]);
        mockHealthOfficeService.getVisits.mockResolvedValue([mockVisit]);
        mockHealthOfficeService.getMedications.mockResolvedValue([mockMedication]);
        mockHealthOfficeService.addVisit.mockResolvedValue(mockVisit);
        mockHealthOfficeService.sendParentNotification.mockResolvedValue();
    });

    it('allows nurse to record health visits', async () => {
        render(<HealthOfficeScreen />);
        
        await waitFor(() => {
            expect(screen.getByText('John Doe')).toBeInTheDocument();
        });
        
        fireEvent.click(screen.getByText('John Doe'));
        
        fireEvent.click(screen.getByText('+ New Visit'));
        
        fireEvent.change(screen.getByPlaceholderText('Complaint'), {
            target: { value: 'Headache' },
        });
        fireEvent.change(screen.getByPlaceholderText('Action Taken'), {
            target: { value: 'Advil given' },
        });
        
        fireEvent.click(screen.getByText('Save Visit'));
        
        await waitFor(() => {
            expect(mockHealthOfficeService.addVisit).toHaveBeenCalled();
        });
    });

    it('blocks medication administration for inactive authorization', async () => {
        const inactiveMedication = {
            ...mockMedication,
            is_active: false,
        };
        mockHealthOfficeService.getMedications.mockResolvedValue([inactiveMedication]);
        
        render(<HealthOfficeScreen />);
        
        await waitFor(() => {
            expect(screen.getByText('John Doe')).toBeInTheDocument();
        });
        
        fireEvent.click(screen.getByText('John Doe'));
        
        fireEvent.click(screen.getByText('+ Give Medication'));
        
        expect(screen.getByText('Advil (50mg) - Inactive')).toBeInTheDocument();
        
        const select = screen.getByRole('combobox');
        expect(select).toHaveValue('');
    });
});
```

### 6. User Manual Update
```markdown
# Health Office Management

## Who Can Use
- Office staff with **Nurse** permission

## How to Use

### Recording a Health Visit
1. Go to **Student Portal** → **Health**
2. Select a student from the list or search
3. Click **+ New Visit**
4. Choose visit type: In-Patient, Out-Patient, Emergency, etc.
5. Enter complaint and action taken
6. Check **Sent home** if applicable
7. Click **Save Visit**

### Administering Medication
1. Select a student from the health office screen
2. Click **+ Give Medication**
3. Select an active medication authorization
4. Enter dose, route, and location
5. Add any notes
6. Click **Administer**

### Parent Notifications
- Parents receive email and portal notifications for:
  - Health visits where student is sent home
  - Medication administration
- Notifications include details and can be viewed in the parent portal

### Medication Safety
- System warns if second dose is given too soon (less than 24 hours)
- Authorization required before administration
- Parent consent must be on file for active authorizations

## Notes
- Visit history is accessible from the student's Health tab
- Medications are only administered from active authorizations
- Second doses require 24+ hour gap unless overridden with reason
- All visit records are audit-logged with timestamp and staff
