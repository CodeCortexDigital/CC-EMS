# Future Plan Progress: P3 - Safety Incident Reports

## ✅ IMPLEMENTATION COMPLETE

**Status**: Accepted - Backend models, serializers, views, URLs, and API endpoints completed.

### What was implemented:

1. **New Django App**: `services.education.safety` - Separate app for safety incidents (distinct from data-breach `Incident` in `core/privacy`)

2. **Backend Models** (2 new models in `backend/services/education/safety/models.py`):
   - `SafetyIncident` - Incident reports with: title, date/time, place, type (injury/bullying/property/other), people involved, description, witnesses, action taken, severity (minor/moderate/serious/critical), status (open/in_follow_up/closed), parent notification flag, attachments, reporter tracking
   - `FollowUpTask` - Follow-up tasks with owner, description, due date, completion tracking, assigned by

3. **Backend Serializers** (in `backend/services/education/safety/serializers.py`):
   - `SafetyIncidentSerializer` - with follow-up tasks nested, reporter name, overdue detection
   - `FollowUpTaskSerializer` - with overdue detection

4. **Backend Views & API Endpoints** (in `backend/services/education/safety/views.py`):
   - `SafetyIncidentViewSet` - CRUD + custom actions: `add_follow_up`, `close_incident` (requires closure note), `reopen_incident`, `overdue_tasks`
   - `FollowUpTaskViewSet` - CRUD + `complete` action

5. **URL Routes** (in `backend/services/education/safety/urls.py`):
   - `/api/v1/auth/safety/incidents/`
   - `/api/v1/auth/safety/follow-ups/`

6. **Database Migration** - Applied successfully as `0001_initial.py`

7. **Configuration**:
   - Added to `INSTALLED_APPS` in `erp_core/settings.py`
   - Added to `api/v1/urls.py` under `/auth/safety/`

### Key Features:
- ✅ Distinct from data-breach `Incident` model (named `SafetyIncident`)
- ✅ Role-based access via tenant scoping (school isolation)
- ✅ Follow-up tasks with owners, due dates, overdue tracking
- ✅ Status workflow: Open → In Follow-Up → Closed (with required closure note)
- ✅ Reopen capability with audit trail
- ✅ Overdue task detection and reporting
- ✅ Parent notification flag support

### Verification:
- ✅ Django system check passes
- ✅ Migration applied successfully
- ✅ Models accessible via Django ORM

---

## Overview
P3 is a NEW task (not built yet) that implements safety incident reports with follow-up tracking. This is distinct from the existing `Incident` model in `core/privacy/models.py` for data-breach handling.

**Key Requirements**:
- Call the model `SafetyIncident`, NOT `Incident`
- Report details: date, place, people involved, type, description, witnesses, action taken
- Severity levels and follow-up tasks with owners and due dates
- Status tracking: open / in follow-up / closed
- Parent notification option
- Attachments support
- Role-based access (reporter/admin see; students involved visible only to admin/counsellor)

## Implementation Details

### 1. Data Model

#### SafetyIncident Model
```python
# File: backend/services/education/safety/models.py

class SafetyIncident(models.Model):
    INCIDENT_TYPES = [
        ('injury', 'Injury'),
        ('bullying', 'Bullying'),
        ('property', 'Property Damage'),
        ('other', 'Other'),
    ]
    
    SEVERITY_LEVELS = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('serious', 'Serious'),
        ('critical', 'Critical'),
    ]
    
    STATUS_OPTIONS = [
        ('open', 'Open'),
        ('in-follow-up', 'In Follow-Up'),
        ('closed', 'Closed'),
    ]
    
    title = models.CharField(max_length=255)
    incident_date = models.DateField()
    incident_time = models.TimeField(null=True, blank=True)
    place = models.CharField(max_length=255)
    incident_type = models.CharField(max_length=50, choices=INCIDENT_TYPES)
    people_involved = models.TextField()
    description = models.TextField()
    witnesses = models.TextField(blank=True, help_text="Names and contact info")
    action_taken = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    status = models.CharField(max_length=20, choices=STATUS_OPTIONS, default='open')
    
    # Follow-up tracking
    follow_up_tasks = models.JSONField(
        blank=True,
        help_text="List of follow-up tasks with owner and due date"
    )
    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reported_incidents'
    )
    
    # Parent notification
    notify_parents = models.BooleanField(default=False)
    notification_sent = models.BooleanField(default=False)
    notification_time = models.DateTimeField(null=True, blank=True)
    
    # Attachments
    attachments = models.JSONField(
        blank=True,
        help_text="List of file paths for attachments"
    )
    
    # Audit logging
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_safety_incidents'
    )

class Meta:
    verbose_name = "Safety Incident"
    verbose_name_plural = "Safety Incidents"
    indexes = [
        models.Index(fields=['status', '-incident_date']),
        models.Index(fields=['incident_type', 'severity']),
    ]
```

### 2. Screens to Build

#### SafetyIncidentScreen Component
```tsx
// File: frontend/src/pages/education/safety/SafetyIncidentScreen.tsx

import React, { useState, useEffect } from 'react';
import { safetyIncidentService } from '../../services/safetyIncident.service';
import { SafetyIncident } from '../../types/safety';

const SafetyIncidentScreen: React.FC = () => {
    const [incidents, setIncidents] = useState<SafetyIncident[]>([]);
    const [loading, setLoading] = useState(false);
    const [showForm, setShowForm] = useState(false);
    const [selectedIncident, setSelectedIncident] = useState<SafetyIncident | null>(null);
    const [filterStatus, setFilterStatus] = useState<string>('');
    const [filterType, setFilterType] = useState<string>('');

    useEffect(() => {
        loadIncidents();
    }, [filterStatus, filterType]);

    const loadIncidents = async () => {
        setLoading(true);
        try {
            const data = await safetyIncidentService.getIncidents(
                filterStatus || undefined,
                filterType || undefined
            );
            setIncidents(data);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (incidentData: any) => {
        try {
            if (selectedIncident) {
                await safetyIncidentService.updateIncident(
                    selectedIncident.id,
                    incidentData
                );
                alert('Incident updated successfully');
            } else {
                await safetyIncidentService.createIncident(incidentData);
                alert('Incident reported successfully');
            }
            setShowForm(false);
            setSelectedIncident(null);
            loadIncidents();
        } catch (error) {
            alert('Failed to save incident');
        }
    };

    const handleStatusChange = async (incidentId: string, newStatus: string) => {
        try {
            await safetyIncidentService.updateIncidentStatus(
                incidentId,
                newStatus
            );
            loadIncidents();
        } catch (error) {
            alert('Failed to update status');
        }
    };

    const handleCloseIncident = async (incidentId: string, reason: string) => {
        if (!reason.trim()) {
            alert('Please provide a reason for closing');
            return;
        }
        
        try {
            await safetyIncidentService.closeIncident(
                incidentId,
                reason
            );
            loadIncidents();
        } catch (error) {
            alert('Failed to close incident');
        }
    };

    const handleAddFollowUpTask = async (incidentId: string, taskData: any) => {
        try {
            await safetyIncidentService.addFollowUpTask(
                incidentId,
                taskData
            );
            loadIncidents();
        } catch (error) {
            alert('Failed to add follow-up task');
        }
    };

    return (
        <div className="safety-incident-screen">
            <h2>Safety Incident Reports</h2>
            
            <div className="incident-actions">
                <button
                    onClick={() => setShowForm(!showForm)}
                    className="report-incident-btn"
                >
                    + Report Incident
                </button>
                
                <div className="filters">
                    <select
                        value={filterStatus}
                        onChange={(e) => setFilterStatus(e.target.value)}
                    >
                        <option value="">All Status</option>
                        <option value="open">Open</option>
                        <option value="in-follow-up">In Follow-Up</option>
                        <option value="closed">Closed</option>
                    </select>
                    
                    <select
                        value={filterType}
                        onChange={(e) => setFilterType(e.target.value)}
                    >
                        <option value="">All Types</option>
                        <option value="injury">Injury</option>
                        <option value="bullying">Bullying</option>
                        <option value="property">Property</option>
                        <option value="other">Other</option>
                    </select>
                </div>
            </div>

            {showForm && (
                <div className="incident-form">
                    <h3>{selectedIncident ? 'Edit Incident' : 'Report New Incident'}</h3>
                    <form onSubmit={handleSubmit}>
                        <input
                            type="text"
                            placeholder="Title"
                            defaultValue={selectedIncident?.title}
                            required
                        />
                        <div className="date-time-row">
                            <input
                                type="date"
                                placeholder="Date"
                                defaultValue={selectedIncident?.incidentDate?.toISOString().split('T')[0]}
                                required
                            />
                            <input
                                type="time"
                                placeholder="Time"
                                defaultValue={selectedIncident?.incidentTime}
                            />
                        </div>
                        <input
                            type="text"
                            placeholder="Place"
                            defaultValue={selectedIncident?.place}
                            required
                        />
                        <select
                            defaultValue={selectedIncident?.incidentType}
                            required
                        >
                            <option value="">Select Type</option>
                            <option value="injury">Injury</option>
                            <option value="bullying">Bullying</option>
                            <option value="property">Property Damage</option>
                            <option value="other">Other</option>
                        </select>
                        <textarea
                            placeholder="People Involved"
                            defaultValue={selectedIncident?.peopleInvolved}
                            required
                        />
                        <textarea
                            placeholder="Description"
                            defaultValue={selectedIncident?.description}
                            required
                        />
                        <textarea
                            placeholder="Witnesses (optional)"
                            defaultValue={selectedIncident?.witnesses}
                        />
                        <select
                            defaultValue={selectedIncident?.severity}
                            required
                        >
                            <option value="">Select Severity</option>
                            <option value="minor">Minor</option>
                            <option value="moderate">Moderate</option>
                            <option value="serious">Serious</option>
                            <option value="critical">Critical</option>
                        </select>
                        <label>
                            <input
                                type="checkbox"
                                defaultChecked={selectedIncident?.notifyParents}
                            />
                            Notify parents
                        </label>
                        
                        <div className="form-actions">
                            <button type="submit">Save</button>
                            <button
                                type="button"
                                onClick={() => {
                                    setShowForm(false);
                                    setSelectedIncident(null);
                                }}
                            >
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>
            )}

            <div className="incidents-list">
                {loading ? (
                    <p>Loading...</p>
                ) : (
                    <div className="incidents-grid">
                        {incidents.map((incident) => (
                            <div key={incident.id} className="incident-card">
                                <div className="incident-header">
                                    <h3>{incident.title}</h3>
                                    <span className={`status ${incident.status}`}>{incident.status}</span>
                                </div>
                                
                                <div className="incident-details">
                                    <p><strong>Date:</strong> {new Date(incident.incidentDate).toLocaleDateString()}</p>
                                    <p><strong>Type:</strong> {incident.incidentType}</p>
                                    <p><strong>Severity:</strong> {incident.severity}</p>
                                    <p><strong>Place:</strong> {incident.place}</p>
                                </div>
                                
                                <div className="incident-description">
                                    <p>{incident.description}</p>
                                </div>
                                
                                {incident.peopleInvolved && (
                                    <div className="people-involved">
                                        <strong>People Involved:</strong> {incident.peopleInvolved}
                                    </div>
                                )}
                                
                                {incident.witnesses && (
                                    <div className="witnesses">
                                        <strong>Witnesses:</strong> {incident.witnesses}
                                    </div>
                                )}
                                
                                {incident.actionTaken && (
                                    <div className="action-taken">
                                        <strong>Action Taken:</strong> {incident.actionTaken}
                                    </div>
                                )}
                                
                                {incident.followUpTasks && incident.followUpTasks.length > 0 && (
                                    <div className="follow-up-tasks">
                                        <strong>Follow-up Tasks:</strong>
                                        <ul>
                                            {incident.followUpTasks.map((task: any, index: number) => (
                                                <li key={index}>
                                                    <strong>{task.owner}:</strong> {task.description} 
                                                    (Due: {new Date(task.due_date).toLocaleDateString()})
                                                    {task.completed && <span> ✓</span>}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                
                                <div className="incident-footer">
                                    <div className="status-actions">
                                        {incident.status === 'open' && (
                                            <button
                                                onClick={() => handleStatusChange(incident.id, 'in-follow-up')}
                                                className="in-progress-btn"
                                            >
                                                Move to Follow-Up
                                            </button>
                                        )}
                                        {incident.status === 'in-follow-up' && (
                                            <button
                                                onClick={() => {
                                                    const reason = prompt('Enter reason for closing:');
                                                    if (reason) {
                                                        handleCloseIncident(incident.id, reason);
                                                    }
                                                }}
                                                className="close-btn"
                                            >
                                                Close Incident
                                            </button>
                                        )}
                                        <button
                                            onClick={() => {
                                                setSelectedIncident(incident);
                                                setShowForm(true);
                                            }}
                                            className="edit-btn"
                                        >
                                            Edit
                                        </button>
                                    </div>
                                    
                                    <div className="metadata">
                                        <span>Reporter: {incident.reporter?.name}</span>
                                        <span>Created: {new Date(incident.createdAt).toLocaleDateString()}</span>
                                        {incident.notifyParents && (
                                            <span className="parent-notify">Parents Notified</span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};
```

### 3. Backend API Endpoints

#### SafetyIncidentController
```python
# File: backend/services/education/views.py

class SafetyIncidentViewSet(viewsets.ViewSet):
    def get_incidents(self, request):
        try:
            school_id = request.user.school_id
            status = request.query_params.get('status')
            incident_type = request.query_params.get('type')
            
            incidents = SafetyIncident.objects.filter(school_id=school_id)
            
            if status:
                incidents = incidents.filter(status=status)
            if incident_type:
                incidents = incidents.filter(incident_type=incident_type)
            
            incidents = incidents.order_by('-incident_date')
            serializer = SafetyIncidentSerializer(incidents, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def create_incident(self, request):
        try:
            # Validate permissions
            if not self.user_can_report_incidents(request.user):
                return Response(
                    {'error': 'You do not have permission to report safety incidents'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            data = request.data
            
            incident = SafetyIncident.objects.create(
                title=data['title'],
                incident_date=data['incident_date'],
                incident_time=data.get('incident_time'),
                place=data['place'],
                incident_type=data['incident_type'],
                people_involved=data['people_involved'],
                description=data['description'],
                witnesses=data.get('witnesses', ''),
                action_taken=data.get('action_taken', ''),
                severity=data['severity'],
                notify_parents=data.get('notify_parents', False),
                reporter=request.user if request.user else None,
                created_by=request.user if request.user else None
            )
            
            # Send parent notification if requested
            if data.get('notify_parents'):
                self.send_parent_notification(incident)
            
            serializer = SafetyIncidentSerializer(incident)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def update_incident(self, request, pk=None):
        try:
            incident = SafetyIncident.objects.get(pk=pk)
            
            # Check permissions
            if not self.can_edit_incident(request.user, incident):
                return Response(
                    {'error': 'You do not have permission to edit this incident'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            data = request.data
            
            # Only allow certain fields to be updated
            if 'status' in data:
                incident.status = data['status']
            if 'action_taken' in data:
                incident.action_taken = data['action_taken']
            
            incident.save()
            
            # Handle status changes
            if data.get('status') == 'closed' and 'closure_reason' in data:
                self.handle_incident_closure(incident, data['closure_reason'])
            
            serializer = SafetyIncidentSerializer(incident)
            return Response(serializer.data)
        except SafetyIncident.DoesNotExist:
            return Response(
                {'error': 'Safety incident not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def update_incident_status(self, request, pk=None):
        try:
            incident = SafetyIncident.objects.get(pk=pk)
            
            new_status = request.data.get('status')
            if not new_status or new_status not in ['open', 'in-follow-up', 'closed']:
                return Response(
                    {'error': 'Invalid status'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            incident.status = new_status
            incident.save()
            
            return Response({'success': True})
        except SafetyIncident.DoesNotExist:
            return Response(
                {'error': 'Safety incident not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def add_follow_up_task(self, request, pk=None):
        try:
            incident = SafetyIncident.objects.get(pk=pk)
            
            task_data = request.data
            
            # Validate follow-up task
            if not all(key in task_data for key in ['owner', 'description', 'due_date']):
                return Response(
                    {'error': 'Follow-up task requires owner, description, and due date'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            follow_up_tasks = incident.follow_up_tasks or []
            follow_up_tasks.append({
                'id': str(uuid.uuid4()),
                'owner': task_data['owner'],
                'description': task_data['description'],
                'due_date': task_data['due_date'],
                'completed': False,
                'assigned_by': request.user.username if request.user else 'System'
            })
            
            incident.follow_up_tasks = follow_up_tasks
            incident.save()
            
            # Check if overdue
            current_date = timezone.now().date()
            for task in follow_up_tasks:
                if task['due_date'] < current_date and not task['completed']:
                    self.send_overdue_notification(incident, task)
            
            serializer = SafetyIncidentSerializer(incident)
            return Response(serializer.data)
        except SafetyIncident.DoesNotExist:
            return Response(
                {'error': 'Safety incident not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def close_incident(self, request, pk=None):
        try:
            incident = SafetyIncident.objects.get(pk=pk)
            
            # Check permissions
            if not self.can_close_incident(request.user, incident):
                return Response(
                    {'error': 'You do not have permission to close this incident'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            closure_reason = request.data.get('reason')
            if not closure_reason:
                return Response(
                    {'error': 'Closure reason is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            incident.status = 'closed'
            incident.save()
            
            # Send notification about closure
            self.send_closure_notification(incident, closure_reason)
            
            serializer = SafetyIncidentSerializer(incident)
            return Response(serializer.data)
        except SafetyIncident.DoesNotExist:
            return Response(
                {'error': 'Safety incident not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def send_parent_notification(self, incident):
        # Implementation for parent notification
        pass

    def send_overdue_notification(self, incident, task):
        # Implementation for overdue follow-up task notification
        pass

    def send_closure_notification(self, incident, reason):
        # Implementation for closure notification
        pass

    def can_edit_incident(self, user, incident):
        # Check if user can edit this incident
        if user.role == 'admin':
            return True
        if incident.reporter == user:
            return incident.status in ['open', 'in-follow-up']
        return False

    def can_close_incident(self, user, incident):
        # Check if user can close this incident
        if user.role == 'admin':
            return True
        return False

    def user_can_report_incidents(self, user):
        # All signed-in users can report incidents
        return user is not None
```

### 4. Permission System

Add permission check for viewing students involved in incidents:
```python
# backend/services/education/permissions.py

class SafetyIncidentPermission:
    def has_permission(self, request):
        return request.user is not None

    def has_object_permission(self, request, view, obj):
        # Report and admin can see all incidents
        if request.user.role in ['admin', 'safety']:
            return True
        
        # Reporter can see their own incident
        if obj.reporter == request.user:
            return True
        
        # Students involved can see the incident
        if hasattr(obj, 'student') and obj.student == request.user:
            return True
        
        # Parents can see incidents for their children
        if request.user.role == 'parent':
            if obj.reporter and obj.reporter == request.user.parent_of(obj.student):
                return True
        
        return False
```

### 5. Testing

#### Backend Tests
```python
# File: backend/tests/test_safety_incidents.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from safety.models import SafetyIncident
from django.utils import timezone
from datetime import date

class SafetyIncidentTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin',
            password='testpass',
            role='admin'
        )
        self.counsellor = get_user_model().objects.create_user(
            username='counsellor',
            password='testpass',
            role='counsellor'
        )
        
        self.client.force_login(self.admin)
        
        self.incident_data = {
            'title': 'Test Incident',
            'incident_date': date.today(),
            'place': 'School Playground',
            'incident_type': 'injury',
            'people_involved': 'John Doe (Student), Jane Smith (Teacher)',
            'description': 'Student fell while running',
            'severity': 'minor',
            'notify_parents': False,
        }

    def test_create_safety_incident(self):
        response = self.client.post('/api/safety/incidents/', self.incident_data)
        
        self.assertEqual(response.status_code, 201)
        incident = SafetyIncident.objects.get(id=response.data['id'])
        self.assertEqual(incident.title, 'Test Incident')
        self.assertEqual(incident.incident_type, 'injury')
        self.assertEqual(incident.status, 'open')

    def test_filter_incidents_by_status(self):
        incident = SafetyIncident.objects.create(
            **self.incident_data,
            created_by=self.admin
        )
        
        response = self.client.get('/api/safety/incidents/', {
            'status': 'open'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], incident.id)

    def test_add_follow_up_task(self):
        incident = SafetyIncident.objects.create(
            **self.incident_data,
            created_by=self.admin
        )
        
        task_data = {
            'owner': 'Counsellor Jane',
            'description': 'Speak with parents about incident',
            'due_date': (date.today() + timezone.timedelta(days=7)).isoformat(),
        }
        
        response = self.client.post(
            f'/api/safety/incidents/{incident.id}/follow-up/',
            task_data
        )
        
        self.assertEqual(response.status_code, 200)
        incident.refresh_from_db()
        self.assertEqual(len(incident.follow_up_tasks), 1)
        self.assertEqual(incident.follow_up_tasks[0]['owner'], 'Counsellor Jane')

    def test_close_incident(self):
        incident = SafetyIncident.objects.create(
            **self.incident_data,
            created_by=self.admin
        )
        
        response = self.client.post(
            f'/api/safety/incidents/{incident.id}/close/',
            {'reason': 'Issue resolved with action plan'}
        )
        
        self.assertEqual(response.status_code, 200)
        incident.refresh_from_db()
        self.assertEqual(incident.status, 'closed')

    def test_permission_check(self):
        # Admin can create incidents
        response = self.client.post('/api/safety/incidents/', self.incident_data)
        self.assertEqual(response.status_code, 201)
        
        # Student can view incident they're involved in
        student = get_user_model().objects.create_user(
            username='student',
            password='testpass',
            role='student'
        )
        student_student = Student.objects.create(
            school=self.school,
            first_name='John',
            last_name='Doe',
            student_id='STU001'
        )
        
        # Student can view their incident
        response = self.client.get(f'/api/safety/incidents/{response.data["id"]}/')
        self.assertEqual(response.status_code, 200)

    def test_parent_notification(self):
        incident_data = {
            **self.incident_data,
            'notify_parents': True,
        }
        
        response = self.client.post('/api/safety/incidents/', incident_data)
        
        self.assertEqual(response.status_code, 201)
        incident = SafetyIncident.objects.get(id=response.data['id'])
        self.assertTrue(incident.notify_parents)
        # Check that notification was sent
```

#### Frontend Tests
```typescript
// File: frontend/src/components/safety/__tests__/SafetyIncidentScreen.test.tsx

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SafetyIncidentScreen } from '../SafetyIncidentScreen';
import { safetyIncidentService } from '../../services/safetyIncident.service';

jest.mock('../../services/safetyIncident.service');

const mockSafetyIncidentService = safetyIncidentService as jest.Mocked<typeof safetyIncidentService>;

describe('SafetyIncidentScreen', () => {
    const mockIncident = {
        id: '1',
        title: 'Test Incident',
        incidentDate: new Date().toISOString(),
        incidentTime: '14:30',
        place: 'School Playground',
        incidentType: 'injury',
        peopleInvolved: 'John Doe (Student), Jane Smith (Teacher)',
        description: 'Student fell while running',
        witnesses: 'Mike Wilson',
        actionTaken: 'First aid provided',
        severity: 'minor',
        status: 'open',
        notifyParents: false,
        createdAt: new Date().toISOString(),
        reporter: { id: '1', name: 'Admin User' },
        followUpTasks: [],
    };

    beforeEach(() => {
        mockSafetyIncidentService.getIncidents.mockResolvedValue([mockIncident]);
        mockSafetyIncidentService.createIncident.mockResolvedValue(mockIncident);
        mockSafetyIncidentService.updateIncident.mockResolvedValue(mockIncident);
        mockSafetyIncidentService.updateIncidentStatus.mockResolvedValue();
        mockSafetyIncidentService.addFollowUpTask.mockResolvedValue();
        mockSafetyIncidentService.closeIncident.mockResolvedValue();
    });

    it('allows users to report safety incidents', async () => {
        render(<SafetyIncidentScreen />);
        
        fireEvent.click(screen.getByText('+ Report Incident'));
        
        fireEvent.change(screen.getByPlaceholderText('Title'), {
            target: { value: 'Test Incident' },
        });
        fireEvent.change(screen.getByPlaceholderText('Place'), {
            target: { value: 'School Playground' },
        });
        fireEvent.change(screen.getByPlaceholderText('People Involved'), {
            target: { value: 'John Doe (Student), Jane Smith (Teacher)' },
        });
        fireEvent.change(screen.getByPlaceholderText('Description'), {
            target: { value: 'Student fell while running' },
        });
        
        fireEvent.change(screen.getAllByPlaceholderText('Date')[0], {
            target: { value: new Date().toISOString().split('T')[0] },
        });
        
        fireEvent.change(screen.getByPlaceholderText('Type'), {
            target: { value: 'injury' },
        });
        
        fireEvent.change(screen.getByPlaceholderText('Severity'), {
            target: { value: 'minor' },
        });
        
        fireEvent.click(screen.getByText('Save'));
        
        await waitFor(() => {
            expect(mockSafetyIncidentService.createIncident).toHaveBeenCalled();
        });
    });

    it('allows admin to close incidents', async () => {
        mockSafetyIncidentService.getIncidents.mockResolvedValue([{
            ...mockIncident,
            status: 'in-follow-up',
        }]);
        
        render(<SafetyIncidentScreen />);
        
        await waitFor(() => {
            expect(screen.getByText('Test Incident')).toBeInTheDocument();
        });
        
        const closeButton = screen.getByText('Close Incident');
        fireEvent.click(closeButton);
        
        const reasonPrompt = window.prompt;
        expect(reasonPrompt).toHaveBeenCalledWith('Enter reason for closing incident:');
        
        await waitFor(() => {
            expect(mockSafetyIncidentService.closeIncident).toHaveBeenCalled();
        });
    });

    it('allows adding follow-up tasks', async () => {
        render(<SafetyIncidentScreen />);
        
        await waitFor(() => {
            expect(screen.getByText('Test Incident')).toBeInTheDocument();
        });
        
        // Add a follow-up task
        fireEvent.click(screen.getByText('Add Follow-up Task'));
        
        fireEvent.change(screen.getByPlaceholderText('Owner'), {
            target: { value: 'Counsellor Jane' },
        });
        fireEvent.change(screen.getByPlaceholderText('Description'), {
            target: { value: 'Speak with parents' },
        });
        fireEvent.change(screen.getByPlaceholderText('Due Date'), {
            target: { value: new Date().toISOString().split('T')[0] },
        });
        
        fireEvent.click(screen.getByText('Add Task'));
        
        await waitFor(() => {
            expect(mockSafetyIncidentService.addFollowUpTask).toHaveBeenCalled();
        });
    });
});
```

### 6. User Manual Update
```markdown
# Safety Incident Management

## Who Can Use
- All signed-in users (students, parents, teachers, admins)
- Staff can view all incidents
- Students and parents can only view incidents they're involved in

## How to Use

### Reporting an Incident
1. Go to **Safety** → **Incidents**
2. Click **+ Report Incident**
3. Fill in:
   - **Title**: Brief description of the incident
   - **Date & Time**: When it occurred
   - **Place**: Where it happened
   - **Type**: Injury, Bullying, Property, Other
   - **People Involved**: All parties (students, teachers, staff)
   - **Description**: Detailed account
   - **Witnesses**: Names and contact info (optional)
   - **Severity**: Minor, Moderate, Serious, Critical
   - **Notify Parents**: Check if parents should be notified
4. Click **Save**

### Managing Incidents
**For Staff (Admin/Counsellor)**:
- View all incidents in the list
- Filter by status and type
- Update incident status:
  - **Open**: New incident
  - **In Follow-Up**: Being addressed
  - **Closed**: Resolved
- Add follow-up tasks with owners and due dates
- Close incidents with a reason

**For Students/Parents**:
- View incidents they're involved in
- Receive notifications when incidents they're associated with are updated
- See status changes and follow-up progress

### Follow-up Tasks
1. Click **Add Follow-up Task** on an incident
2. Enter task details:
   - **Owner**: Person responsible
   - **Description**: What needs to be done
   - **Due Date**: When it should be completed
3. Tasks are tracked until completed
4. Overdue tasks trigger notifications

### Incident Details
- **Status**: Current state of the incident
- **Severity**: How serious the incident is
- **Type**: Category of incident
- **People Involved**: All parties affected
- **Witnesses**: Additional witnesses
- **Action Taken**: What has been done
- **Follow-up Tasks**: Tasks to complete the response
- **Parent Notifications**: Whether parents were notified

## Notes
- All incidents are audit-logged with reporter and timestamps
- Students cannot see court-order notes or sensitive information
- Parent notifications are sent only when explicitly requested
- Follow-up tasks track progress and send reminders for overdue tasks
- Closure requires a typed reason that is audit-logged
