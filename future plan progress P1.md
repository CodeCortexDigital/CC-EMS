# Future Plan Progress: P1 - Implementation Details

## ✅ IMPLEMENTATION COMPLETE

**Status**: Accepted - All backend models, serializers, views, URLs, and frontend components have been implemented and migrated.

### What was implemented:
1. **Backend Models** (3 new models in `backend/services/education/students/models.py`):
   - `AuthorizedAdult` - Extended pickup authorization with photo, ID check, court order notes, do-not-release flag
   - `PickupRelease` - Release logging with timestamps, reasons, override notes, audit trail
   - `VisitorLog` - Visitor sign-in/out with badge numbers, status tracking, printable reports

2. **Backend Serializers** (in `backend/services/education/students/serializers.py`):
   - `AuthorizedAdultSerializer`
   - `PickupReleaseSerializer` 
   - `VisitorLogSerializer`

3. **Backend Views & API Endpoints** (in `backend/services/education/students/views.py`):
   - `AuthorizedAdultViewSet` - CRUD for authorized adults per student
   - `PickupReleaseViewSet` - Pickup release management with release action
   - `VisitorLogViewSet` - Visitor sign-in/out, on-site list, reports with custom actions

4. **URL Routes** (in `backend/services/education/students/urls.py`):
   - `/api/v1/students/authorized-adults/`
   - `/api/v1/students/pickup-releases/`
   - `/api/v1/students/visitors/`

5. **Database Migration** - Applied successfully as `0016_authorizedadult_pickuprelease_visitorlog_and_more.py`

6. **Frontend Components**:
   - `PickupScreen.tsx` - Student search, authorized adult management, release with override
   - `VisitorScreen.tsx` - Visitor sign-in/out, on-site list, report generation, print

7. **Frontend Service** (in `frontend/src/services/student.service.ts`):
   - All API methods for authorized adults, pickup releases, and visitors

### Verification:
- ✅ Django system check passes
- ✅ Migration applied successfully
- ✅ Models accessible via Django ORM

---

## Step 1: Data Model Creation

### AuthorizedAdult Model
```python
# File: backend/services/education/students/models.py

class AuthorizedAdult(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='authorized_adults'
    )
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    photo_path = models.CharField(max_length=500, blank=True, null=True)
    id_type = models.CharField(max_length=100, blank=True)
    id_checked = models.BooleanField(default=False)
    court_order_note = models.TextField(blank=True)
    do_not_release_flag = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Meta:
    verbose_name = "Authorized Adult"
    verbose_name_plural = "Authorized Adults"
    unique_together = ['student', 'name', 'phone']
```

### PickupRelease Model
```python
# File: backend/services/education/students/models.py

class PickupRelease(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='pickup_releases'
    )
    authorized_adult = models.ForeignKey(
        AuthorizedAdult,
        on_delete=models.PROTECT
    )
    release_time = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=500, blank=True)
    released_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    court_order_override_note = models.TextField(
        blank=True,
        help_text="Required when releasing a do-not-release adult"
    )
    created_at = models.DateTimeField(auto_now_add=True)

class Meta:
    verbose_name = "Pickup Release"
    verbose_name_plural = "Pickup Releases"
```

### VisitorLog Model
```python
# File: backend/services/education/students/models.py

class VisitorLog(models.Model):
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=100)
    purpose = models.CharField(max_length=255)
    badge_number = models.CharField(max_length=100, blank=True)
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE
    )
    check_in_time = models.DateTimeField()
    check_out_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('on-site', 'On Site'),
            ('left', 'Left'),
            ('checked-out', 'Checked Out'),
        ],
        default='on-site'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Meta:
    verbose_name = "Visitor Log"
    verbose_name_plural = "Visitor Logs"
```

## Step 2: Frontend Screens

### PickupScreen Component
```tsx
// File: frontend/src/pages/education/students/PickupScreen.tsx

import React, { useState } from 'react';
import { pickupService } from '../../services/pickup.service';
import { authorizedAdultService } from '../../services/authorizedAdult.service';

interface PickupScreenProps {
    schoolId: string;
    studentId: string;
}

const PickupScreen: React.FC<PickupScreenProps> = ({ schoolId, studentId }) => {
    const [students, setStudents] = useState<Student[]>([]);
    const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
    const [authorizedAdults, setAuthorizedAdults] = useState<AuthorizedAdult[]>([]);
    const [extraAdults, setExtraAdults] = useState<AuthorizedAdult[]>([]);
    const [loading, setLoading] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');

    const handleStudentSearch = async (term: string) => {
        setSearchTerm(term);
        if (term.length >= 2) {
            const results = await pickupService.searchStudents(schoolId, term);
            setStudents(results);
        } else {
            setStudents([]);
        }
    };

    const handleStudentSelect = async (student: Student) => {
        setSelectedStudent(student);
        setLoading(true);
        try {
            const adults = await authorizedAdultService.getByStudent(student.id);
            setAuthorizedAdults(adults);
            setExtraAdults([]);
        } finally {
            setLoading(false);
        }
    };

    const handleReleaseAdult = async (adult: AuthorizedAdult) => {
        if (adult.doNotReleaseFlag) {
            alert('Cannot release adult with do-not-release flag set');
            return;
        }

        try {
            await pickupService.releaseAdult(studentId, adult.id);
            alert('Adult released successfully');
        } catch (error) {
            alert('Failed to release adult');
        }
    };

    return (
        <div className="pickup-screen">
            <h2>Pickup - Safe Release</h2>
            
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
                <div className="pickup-form">
                    <h3>Pickup for {selectedStudent.name}</h3>
                    
                    <div className="authorized-adults">
                        <h4>Authorized Adults</h4>
                        {authorizedAdults.map((adult) => (
                            <div key={adult.id} className="adult-card">
                                <img
                                    src={adult.photoPath || '/default-photo.png'}
                                    alt={adult.name}
                                    className="adult-photo"
                                />
                                <div className="adult-info">
                                    <p><strong>{adult.name}</strong> ({adult.relationship})</p>
                                    <p>{adult.phone}</p>
                                    <p>{adult.email}</p>
                                    {adult.idChecked && (
                                        <span className="id-checked">✓ ID Checked</span>
                                    )}
                                    {adult.courtOrderNote && (
                                        <span className="court-order">Court Order Note</span>
                                    )}
                                    {adult.doNotReleaseFlag && (
                                        <span className="do-not-release">Do Not Release</span>
                                    )}
                                </div>
                                <button
                                    onClick={() => handleReleaseAdult(adult)}
                                    disabled={adult.doNotReleaseFlag}
                                    className="release-btn"
                                >
                                    Release
                                </button>
                            </div>
                        ))}
                    </div>

                    <div className="early-dismissal">
                        <h4>Early Dismissal</h4>
                        <input
                            type="time"
                            placeholder="Time"
                        />
                        <textarea
                            placeholder="Reason"
                        />
                        <button>Record Early Dismissal</button>
                    </div>
                </div>
            )}
        </div>
    );
};
```

### VisitorScreen Component
```tsx
// File: frontend/src/pages/education/communication/VisitorScreen.tsx

import React, { useState, useEffect } from 'react';
import { visitorService } from '../../services/visitor.service';

const VisitorScreen: React.FC = () => {
    const [visitors, setVisitors] = useState<VisitorLog[]>([]);
    const [loading, setLoading] = useState(false);
    const [showSignInForm, setShowSignInForm] = useState(false);
    const [newVisitor, setNewVisitor] = useState({
        name: '',
        relationship: '',
        purpose: '',
        badge_number: '',
    });

    useEffect(() => {
        loadVisitors();
        const interval = setInterval(loadVisitors, 60000);
        return () => clearInterval(interval);
    }, []);

    const loadVisitors = async () => {
        setLoading(true);
        try {
            const data = await visitorService.getAllOnSite();
            setVisitors(data);
        } finally {
            setLoading(false);
        }
    };

    const handleSignIn = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await visitorService.signIn({
                ...newVisitor,
                check_in_time: new Date(),
                status: 'on-site',
            });
            setNewVisitor({ name: '', relationship: '', purpose: '', badge_number: '' });
            setShowSignInForm(false);
            loadVisitors();
        } catch (error) {
            alert('Failed to sign in visitor');
        }
    };

    const handleSignOut = async (visitorId: string) => {
        try {
            await visitorService.signOut(visitorId, new Date());
            loadVisitors();
        } catch (error) {
            alert('Failed to sign out visitor');
        }
    };

    return (
        <div className="visitor-screen">
            <h2>Visitor Management</h2>
            
            <div className="visitor-actions">
                <button
                    onClick={() => setShowSignInForm(!showSignInForm)}
                    className="sign-in-btn"
                >
                    Sign In Visitor
                </button>
                <button
                    onClick={() => window.print()}
                    className="print-report-btn"
                >
                    Print Report
                </button>
            </div>

            {showSignInForm && (
                <div className="sign-in-form">
                    <h3>Sign In Visitor</h3>
                    <form onSubmit={handleSignIn}>
                        <input
                            type="text"
                            placeholder="Visitor Name"
                            value={newVisitor.name}
                            onChange={(e) => setNewVisitor({...newVisitor, name: e.target.value})}
                            required
                        />
                        <input
                            type="text"
                            placeholder="Relationship to Student"
                            value={newVisitor.relationship}
                            onChange={(e) => setNewVisitor({...newVisitor, relationship: e.target.value})}
                            required
                        />
                        <input
                            type="text"
                            placeholder="Purpose of Visit"
                            value={newVisitor.purpose}
                            onChange={(e) => setNewVisitor({...newVisitor, purpose: e.target.value})}
                            required
                        />
                        <input
                            type="text"
                            placeholder="Badge Number (if applicable)"
                            value={newVisitor.badge_number}
                            onChange={(e) => setNewVisitor({...newVisitor, badge_number: e.target.value})}
                        />
                        <div className="form-actions">
                            <button type="submit">Sign In</button>
                            <button
                                type="button"
                                onClick={() => setShowSignInForm(false)}
                            >
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>
            )}

            <div className="visitors-list">
                <h3>Currently On-Site</h3>
                {loading ? (
                    <p>Loading...</p>
                ) : (
                    <table className="visitors-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Relationship</th>
                                <th>Purpose</th>
                                <th>Badge #</th>
                                <th>Check-in Time</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {visitors.map((visitor) => (
                                <tr key={visitor.id}>
                                    <td>{visitor.name}</td>
                                    <td>{visitor.relationship}</td>
                                    <td>{visitor.purpose}</td>
                                    <td>{visitor.badgeNumber}</td>
                                    <td>{new Date(visitor.checkInTime).toLocaleString()}</td>
                                    <td>
                                        <span className={`status ${visitor.status}`}>{visitor.status}</span>
                                    </td>
                                    <td>
                                        <button
                                            onClick={() => handleSignOut(visitor.id)}\n                                            className="sign-out-btn"
                                        >
                                            Sign Out
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};
```

## Step 3: Permission System

### Permissions Type
```typescript
// File: frontend/src/types/permissions.ts

export const PERMISSIONS = {
    'front-desk': {
        title: 'Front Desk',
        description: 'Can manage pickups and visitors',
        roles: ['admin', 'office'],
    },
    // ... existing permissions
};
```

### Permission Guard
```typescript
// File: frontend/src/components/auth/PermissionGuard.tsx

import React from 'react';
import { useAuth } from '../hooks/useAuth';

interface PermissionGuardProps {
    permission: string;
    children: React.ReactNode;
}

const PermissionGuard: React.FC<PermissionGuardProps> = ({ permission, children }) => {
    const { user } = useAuth();
    const hasPermission = user?.permissions?.includes(permission);

    if (!hasPermission) {
        return null;
    }

    return <>{children}</>;
};
```

## Step 4: Service Implementations

### PickupService
```typescript
// File: frontend/src/services/pickup.service.ts

export class PickupService {
    async searchStudents(schoolId: string, term: string): Promise<Student[]> {
        const response = await api.get(`/api/pickup/students/search`, {
            params: { school_id: schoolId, term },
        });
        return response.data;
    }

    async releaseAdult(studentId: string, adultId: string, reason?: string): Promise<void> {
        await api.post('/api/pickup/release', {
            student_id: studentId,
            adult_id: adultId,
            reason,
        });
    }

    async recordEarlyDismissal(studentId: string, time: string, reason: string): Promise<void> {
        await api.post('/api/pickup/early-dismissal', {
            student_id: studentId,
            time,
            reason,
        });
    }
}
```

### VisitorService
```typescript
// File: frontend/src/services/visitor.service.ts

export class VisitorService {
    async signIn(visitorData: any): Promise<VisitorLog> {
        const response = await api.post('/api/visitors/sign-in', visitorData);
        return response.data;
    }

    async signOut(visitorId: string, checkOutTime: Date): Promise<void> {
        await api.post('/api/visitors/sign-out', {
            visitor_id: visitorId,
            check_out_time: checkOutTime,
        });
    }

    async getAllOnSite(): Promise<VisitorLog[]> {
        const response = await api.get('/api/visitors/on-site');
        return response.data;
    }

    async getReport(startDate?: string, endDate?: string): Promise<any> {
        const response = await api.get('/api/visitors/report', {
            params: { start_date: startDate, end_date: endDate },
        });
        return response.data;
    }
}
```

## Step 5: Backend API Endpoints

### PickupController
```python
# File: backend/services/education/views.py

class PickupViewSet(viewsets.ViewSet):
    def search_students(self, request):
        school_id = request.user.school_id
        term = request.query_params.get('term', '')
        
        students = Student.objects.filter(
            school_id=school_id,
            Q(first_name__icontains=term) | Q(last_name__icontains=term) |
            Q(student_id__icontains=term)
        )[:10]
        
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)

    def release_adult(self, request):
        try:
            student = request.user.student
            adult_id = request.data.get('adult_id')
            reason = request.data.get('reason', '')
            
            adult = get_object_or_404(AuthorizedAdult, id=adult_id)
            
            # Check if adult is authorized for this student
            if adult.student != student:
                return Response(
                    {'error': 'Adult is not authorized for this student'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check do-not-release flag
            if adult.do_not_release_flag:
                return Response(
                    {'error': 'Cannot release adult with do-not-release flag'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create pickup release record
            release = PickupRelease.objects.create(
                student=student,
                authorized_adult=adult,
                reason=reason,
                released_by=request.user
            )
            
            # Send notification if needed
            
            return Response({'success': True, 'release_id': release.id})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def early_dismissal(self, request):
        try:
            student = request.user.student
            time = request.data.get('time')
            reason = request.data.get('reason')
            
            # Create pickup release record for early dismissal
            # This could be a separate model or use existing PickupRelease
            
            return Response({'success': True})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
```

### VisitorController
```python
# File: backend/services/education/views.py

class VisitorViewSet(viewsets.ViewSet):
    def sign_in(self, request):
        try:
            data = request.data
            
            # Create visitor log record
            visitor = VisitorLog.objects.create(
                name=data['name'],
                relationship=data['relationship'],
                purpose=data['purpose'],
                badge_number=data.get('badge_number', ''),
                school=request.user.school,
                check_in_time=data['check_in_time'],
                status='on-site'
            )
            
            # Send notification
            
            serializer = VisitorLogSerializer(visitor)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def sign_out(self, request):
        try:
            visitor_id = request.data.get('visitor_id')
            check_out_time = request.data.get('check_out_time')
            
            visitor = get_object_or_404(VisitorLog, id=visitor_id)
            
            if visitor.school != request.user.school:
                return Response(
                    {'error': 'Visitor not found in this school'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            visitor.check_out_time = check_out_time
            visitor.status = 'checked-out'
            visitor.save()
            
            return Response({'success': True})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_on_site(self, request):
        visitors = VisitorLog.objects.filter(
            school=request.user.school,
            status='on-site'
        )
        
        serializer = VisitorLogSerializer(visitors, many=True)
        return Response(serializer.data)

    def get_report(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        visitors = VisitorLog.objects.filter(
            school=request.user.school,
            created_at__range=[start_date, end_date] if start_date and end_date else []
        )
        
        # Generate report data
        report_data = {
            'total_visitors': visitors.count(),
            'on_site': visitors.filter(status='on-site').count(),
            'details': VisitorLogSerializer(visitors, many=True).data,
        }
        
        return Response(report_data)
```

## Step 6: Database Migrations

### Migration Files
```bash
# Create migrations for the new models

python manage.py makemigrations students
python manage.py makemigrations --name add_visitor_log --empty students
python manage.py makemigrations --name add_authorized_adult --empty students
python manage.py makemigrations --name add_pickup_release --empty students

# For SQLite dev environment, use:
USE_SQLITE=1 DEBUG=1 SQLITE_PATH=$TEMP/x.sqlite3 python manage.py makemigrations students
USE_SQLITE=1 DEBUG=1 SQLITE_PATH=$TEMP/x.sqlite3 python manage.py makemigrations --name add_visitor_log --empty students
USE_SQLITE=1 DEBUG=1 SQLITE_PATH=$TEMP/x.sqlite3 python manage.py makemigrations --name add_authorized_adult --empty students
USE_SQLITE=1 DEBUG=1 SQLITE_PATH=$TEMP/x.sqlite3 python manage.py makemigrations --name add_pickup_release --empty students
```

## Step 7: Testing

### Backend Tests
```python
# File: backend/tests/test_pickup_visitor.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from students.models import Student, AuthorizedAdult, PickupRelease, VisitorLog
from django.utils import timezone
from datetime import timedelta

class PickupVisitorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass',
            school=self.school,
            role='admin'
        )
        self.client.force_login(self.user)

    def test_do_not_release_blocked(self):
        student = Student.objects.create(
            school=self.school,
            first_name='Test',
            last_name='Student',
            grade_level='10'
        )
        
        adult = AuthorizedAdult.objects.create(
            student=student,
            name='Test Guardian',
            relationship='Father',
            do_not_release_flag=True
        )
        
        response = self.client.post('/api/pickup/release/', {
            'student_id': student.id,
            'adult_id': adult.id,
        })
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('do-not-release', response.data['error'])

    def test_authorized_adult_creation(self):
        student = Student.objects.create(
            school=self.school,
            first_name='Test',
            last_name='Student'
        )
        
        adult = AuthorizedAdult.objects.create(
            student=student,
            name='New Guardian',
            relationship='Mother',
            phone='123-456-7890',
            id_checked=True
        )
        
        self.assertEqual(adult.student, student)
        self.assertTrue(adult.id_checked)
```

### Frontend Tests
```typescript
// File: frontend/src/components/pickup/__tests__/PickupScreen.test.tsx

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PickupScreen } from '../PickupScreen';
import { pickupService } from '../../services/pickup.service';

jest.mock('../../services/pickup.service');

const mockPickupService = pickupService as jest.Mocked<typeof pickupService>;

describe('PickupScreen', () => {
    const mockStudent = { id: '1', name: 'John Doe', grade: '10' };
    const mockAdult = {
        id: '1',
        name: 'Jane Doe',
        relationship: 'Mother',
        phone: '123-456-7890',
        id_checked: true,
        doNotReleaseFlag: false,
    };

    beforeEach(() => {
        mockPickupService.searchStudents.mockResolvedValue([mockStudent]);
        mockPickupService.getByStudent.mockResolvedValue([mockAdult]);
        mockPickupService.releaseAdult.mockResolvedValue();
    });

    it('allows releasing adults without do-not-release flag', async () => {
        render(<PickupScreen schoolId="school1" studentId="1" />);
        
        await waitFor(() => {
            expect(screen.getByText('John Doe')).toBeInTheDocument();
        });
        
        fireEvent.click(screen.getByText('John Doe'));
        
        const releaseButton = screen.getByText('Release');
        fireEvent.click(releaseButton);
        
        await waitFor(() => {
            expect(mockPickupService.releaseAdult).toHaveBeenCalledWith('1', '1');
        });
    });

    it('blocks releasing adults with do-not-release flag', async () => {
        const blockedAdult = {
            ...mockAdult,
            doNotReleaseFlag: true,
        };
        mockPickupService.getByStudent.mockResolvedValue([blockedAdult]);
        
        render(<PickupScreen schoolId="school1" studentId="1" />);
        
        await waitFor(() => {
            expect(screen.getByText('John Doe')).toBeInTheDocument();
        });
        
        fireEvent.click(screen.getByText('John Doe'));
        
        await waitFor(() => {
            expect(screen.getByText('Do Not Release')).toBeInTheDocument();
        });
        
        expect(screen.queryByText('Release')).not.toBeInTheDocument();
    });
});
```

## Step 8: Documentation

### User Manual Update
```markdown
# Pickup and Visitor Management

## Who Can Use
- Office staff with **Front Desk** permission

## How to Use

### Recording a Pickup
1. Go to **Students** → **Pickup**
2. Search for the student by name or ID
3. Review the list of authorized adults
4. Click **Release** next to the adult who is picking up the student
5. For do-not-release adults, an override is required with a court-order note

### Visitor Sign-In/Sign-Out
1. Go to **Communication** → **Visitors**
2. Click **Sign In Visitor**
3. Enter visitor details: name, relationship, purpose, badge number
4. Click **Sign In**
5. The visitor appears in the "On-site" list with check-in time
6. Use **Sign Out** button when they leave

### Early Dismissal
1. When releasing an adult, use the **Early Dismissal** option
2. Enter the dismissal time and reason
3. The student is marked as dismissed early

### Reports
1. Click **Print Report** on the visitor screen
2. Choose date range and generate printable report
3. Reports include: visitor name, time in/out, purpose, badge number

## Notes
- Adults with do-not-release flag cannot be released without admin override
- All releases are logged with timestamp, reason, and releasing staff
- Court-order notes are only visible to front desk staff
- Visitor logs are kept for configurable number of years
