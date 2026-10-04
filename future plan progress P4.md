# Future Plan Progress: P4 - Permission Slips and E-Signature Forms

## ✅ IMPLEMENTATION COMPLETE

**Status**: Accepted - Backend models, serializers, views, URLs, and API endpoints completed.

### What was implemented:

1. **New Django App**: `services.education.forms` - Dedicated app for permission slips and e-signature forms

2. **Backend Models** (3 new models in `backend/services/education/forms/models.py`):
   - `FormTemplate` - Admin-built forms with: title, body, audience (class/grade/everyone), due date, questions (yes/no/text/choice), versioning, active status
   - `FormAssignment` - Links forms to specific students with: status (pending/signed/declined/overdue), due date, reminder tracking, version at assignment
   - `FormResponse` - Guardian responses with: typed signature, JSON responses, signed timestamp, version at sign, cannot-be-edited flag

3. **Backend Serializers** (in `backend/services/education/forms/serializers.py`):
   - `FormTemplateSerializer` - with assignments count, creator name
   - `FormAssignmentSerializer` - with student name, form title, guardian signed name, overdue detection
   - `FormResponseSerializer` - with guardian name, student name, form title

4. **Backend Views & API Endpoints** (in `backend/services/education/forms/views.py`):
   - `FormTemplateViewSet` - CRUD + `assign` action (bulk assign to students by audience) + versioning on update
   - `FormAssignmentViewSet` - Track assignments + `send_reminder`, `export_csv`, `export_pdf` actions
   - `FormResponseViewSet` - Guardian responses with validation + guardian-specific listing

4. **URL Routes** (in `backend/services/education/forms/urls.py`):
   - `/api/v1/auth/forms/templates/`
   - `/api/v1/auth/forms/assignments/`
   - `/api/v1/auth/forms/responses/`

5. **Database Migration** - Applied successfully as `0001_initial.py`

6. **Configuration**:
   - Added to `INSTALLED_APPS` in `erp_core/settings.py`
   - Added to `api/v1/urls.py` under `/auth/forms/`

### Key Features:
- ✅ Multi-question form builder (yes/no, text, choice, signature)
- ✅ Audience targeting: class, grade, or everyone
- ✅ One response per child per guardian
- ✅ Versioning: form updates create new versions, old assignments keep original version
- ✅ Signed responses cannot be edited (immutable)
- ✅ Guardian validation: only linked guardians can sign
- ✅ Status tracking: pending → signed/declined/overdue
- ✅ Reminder system for pending forms
- ✅ CSV export for responses
- ✅ Role-based access: guardians see only their children's forms

### Verification:
- ✅ Django system check passes
- ✅ Migration applied successfully
- ✅ Models accessible via Django ORM

---

## Overview
P4 is a NEW task (not built yet) that implements permission slips and e-signature forms for school applications (field trip, photo consent, medical consent). Each family signs online, and staff can see who has not signed.

**Key Requirements**:
- Admin builds forms with questions (yes/no, text, choice)
- Families sign under Documents and as notification
- One response per child
- Admin/teacher tracker: signed, not signed, declined
- Remind button for unsigned forms
- Export to CSV and PDF
- Signatures store who, when, exact text signed
- Signed responses cannot be edited
- Changed forms create new versions
- Only guardian linked to student may sign

## Implementation Details

### 1. Data Models

#### FormTemplate Model
```python
# File: backend/services/education/permissions/models.py

class FormTemplate(models.Model):
    title = models.CharField(max_length=255)
    body = models.TextField()
    audience = models.CharField(
        max_length=50,
        choices=[
            ('class', 'Class'),
            ('grade', 'Grade'),
            ('everyone', 'Everyone'),
        ]
    )
    audience_target = models.CharField(
        max_length=100,
        help_text="Specific class, grade, or 'all'"
    )
    due_date = models.DateTimeField()
    questions = models.JSONField(
        help_text="List of questions with type and options"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_forms'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

class Meta:
    verbose_name = "Form Template"
    verbose_name_plural = "Form Templates"
    indexes = [
        models.Index(fields=['audience', 'audience_target', 'due_date']),
    ]
```

#### FormAssignment Model
```python
# File: backend/services/education/permissions/models.py

class FormAssignment(models.Model):
    form_template = models.ForeignKey(
        FormTemplate,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='form_assignments'
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_forms'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('signed', 'Signed'),
            ('declined', 'Declined'),
            ('overdue', 'Overdue'),
        ],
        default='pending'
    )
    reminder_sent = models.DateTimeField(null=True, blank=True)

class Meta:
    verbose_name = "Form Assignment"
    verbose_name_plural = "Form Assignments"
    unique_together = ['form_template', 'student']
    indexes = [
        models.Index(fields=['student', 'status']),
        models.Index(fields=['due_date']),
    ]
```

#### FormResponse Model
```python
# File: backend/services/education/permissions/models.py

class FormResponse(models.Model):
    assignment = models.ForeignKey(
        FormAssignment,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    guardian = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='form_responses'
    )
    signature = models.CharField(max_length=255)
    signed_at = models.DateTimeField(auto_now_add=True)
    responses = models.JSONField(
        help_text="Answers to questions"
    )
    version_at_sign = models.CharField(max_length=50)
    cannot_be_edited = models.BooleanField(default=True)

class Meta:
    verbose_name = "Form Response"
    verbose_name_plural = "Form Responses"
    unique_together = ['assignment', 'guardian']
    indexes = [
        models.Index(fields=['guardian', 'signed_at']),
    ]
```

### 2. Screens to Build

#### FormsManagementScreen Component
```tsx
// File: frontend/src/pages/education/forms/FormsManagementScreen.tsx

import React, { useState, useEffect } from 'react';
import { formService } from '../../services/form.service';
import { FormTemplate } from '../../types/form';

const FormsManagementScreen: React.FC = () => {
    const [templates, setTemplates] = useState<FormTemplate[]>([]);
    const [loading, setLoading] = useState(false);
    const [showCreateForm, setShowCreateForm] = useState(false);

    useEffect(() => {
        loadTemplates();
    }, []);

    const loadTemplates = async () => {
        setLoading(true);
        try {
            const data = await formService.getTemplates();
            setTemplates(data);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateTemplate = async (templateData: any) => {
        try {
            const newTemplate = await formService.createTemplate(templateData);
            setTemplates([newTemplate, ...templates]);
            setShowCreateForm(false);
        } catch (error) {
            alert('Failed to create form template');
        }
    };

    const handleAssignForm = async (templateId: string, assignmentData: any) => {
        try {
            const assignment = await formService.assignForm(
                templateId,
                assignmentData
            );
            alert('Form assigned successfully');
        } catch (error) {
            alert('Failed to assign form');
        }
    };

    return (
        <div className="forms-management-screen">
            <h2>Permission Slips and E-Signature Forms</h2>
            
            <div className="forms-header">
                <button
                    onClick={() => setShowCreateForm(!showCreateForm)}
                    className="create-form-btn"
                >
                    + New Form
                </button>
            </div>

            {showCreateForm && (
                <div className="create-form-modal">
                    <h3>Create New Form</h3>
                    <form onSubmit={handleCreateTemplate}>
                        <input
                            type="text"
                            placeholder="Form Title"
                            required
                        />
                        <textarea
                            placeholder="Form Body"
                            required
                        />
                        <div className="form-audience">
                            <label>
                                <input type="radio" name="audience" value="class" />
                                Class
                            </label>
                            <label>
                                <input type="radio" name="audience" value="grade" />
                                Grade
                            </label>
                            <label>
                                <input type="radio" name="audience" value="everyone" />
                                Everyone
                            </label>
                        </div>
                        <input
                            type="text"
                            placeholder="Audience Target (e.g., 'Grade 5', 'Class A')"
                            required
                        />
                        <input
                            type="datetime-local"
                            placeholder="Due Date"
                            required
                        />
                        <div className="questions-editor">
                            <h4>Questions</h4>
                            <button type="button">+ Add Question</button>
                            {/* Question editor would go here */}
                        </div>
                        
                        <div className="form-actions">
                            <button type="submit">Create</button>
                            <button
                                type="button"
                                onClick={() => setShowCreateForm(false)}
                            >
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>
            )}

            <div className="templates-list">
                {loading ? (
                    <p>Loading...</p>
                ) : (
                    <div className="templates-grid">
                        {templates.map((template) => (
                            <div key={template.id} className="template-card">
                                <h3>{template.title}</h3>
                                <p>{template.body.substring(0, 100)}...</p>
                                <div className="template-meta">
                                    <span>Audience: {template.audience}</span>
                                    <span>Target: {template.audienceTarget}</span>
                                    <span>Due: {new Date(template.dueDate).toLocaleDateString()}</span>
                                </div>
                                <div className="template-actions">
                                    <button
                                        onClick={() => handleAssignForm(template.id, {
                                            audience: template.audience,
                                            target: template.audienceTarget,
                                            due_date: template.dueDate,
                                        })}
                                        className="assign-btn"
                                    >
                                        Assign
                                    </button>
                                    <button className="export-btn">Export CSV</button>
                                    <button className="export-btn">Export PDF</button>
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

#### FormsTrackerScreen Component
```tsx
// File: frontend/src/pages/education/forms/FormsTrackerScreen.tsx

import React, { useState, useEffect } from 'react';
import { formService } from '../../services/form.service';
import { FormAssignment } from '../../types/form';

const FormsTrackerScreen: React.FC = () => {
    const [assignments, setAssignments] = useState<FormAssignment[]>([]);
    const [loading, setLoading] = useState(false);
    const [filterStatus, setFilterStatus] = useState<string>('');
    const [selectedStudent, setSelectedStudent] = useState<string>('');

    useEffect(() => {
        loadAssignments();
    }, [filterStatus, selectedStudent]);

    const loadAssignments = async () => {
        setLoading(true);
        try {
            const data = await formService.getAssignments(
                filterStatus || undefined,
                selectedStudent || undefined
            );
            setAssignments(data);
        } finally {
            setLoading(false);
        }
    };

    const handleReminder = async (assignmentId: string) => {
        try {
            await formService.sendReminder(assignmentId);
            alert('Reminder sent');
            loadAssignments();
        } catch (error) {
            alert('Failed to send reminder');
        }
    };

    const handleExportCSV = async (assignmentId: string) => {
        try {
            const csvData = await formService.exportCSV(assignmentId);
            // Download CSV file
            const blob = new Blob([csvData], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `form_responses_${assignmentId}.csv`;
            a.click();
        } catch (error) {
            alert('Failed to export CSV');
        }
    };

    const handleExportPDF = async (assignmentId: string) => {
        try {
            const pdfData = await formService.exportPDF(assignmentId);
            // Download PDF file
            const blob = new Blob([pdfData], { type: 'application/pdf' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `form_responses_${assignmentId}.pdf`;
            a.click();
        } catch (error) {
            alert('Failed to export PDF');
        }
    };

    return (
        <div className="forms-tracker-screen">
            <h2>Forms Tracker</h2>
            
            <div className="tracker-filters">
                <input
                    type="text"
                    placeholder="Filter by student name..."
                    value={selectedStudent}
                    onChange={(e) => setSelectedStudent(e.target.value)}
                />
                <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                >
                    <option value="">All Status</option>
                    <option value="pending">Pending</option>
                    <option value="signed">Signed</option>
                    <option value="declined">Declined</option>
                    <option value="overdue">Overdue</option>
                </select>
                <button onClick={loadAssignments}>Apply Filters</button>
            </div>

            <div className="assignments-list">
                {loading ? (
                    <p>Loading...</p>
                ) : (
                    <table className="assignments-table">
                        <thead>
                            <tr>
                                <th>Student</th>
                                <th>Form Title</th>
                                <th>Audience</th>
                                <th>Due Date</th>
                                <th>Status</th>
                                <th>Guardian Signed</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {assignments.map((assignment) => (
                                <tr key={assignment.id}>
                                    <td>{assignment.studentName}</td>
                                    <td>{assignment.formTitle}</td>
                                    <td>{assignment.audienceTarget}</td>
                                    <td>{new Date(assignment.dueDate).toLocaleDateString()}</td>
                                    <td>
                                        <span className={`status ${assignment.status}`}>{assignment.status}</span>
                                    </td>
                                    <td>{assignment.guardianSignedName}</td>
                                    <td>
                                        <button
                                            onClick={() => handleReminder(assignment.id)}
                                            className="reminder-btn"
                                            disabled={assignment.status === 'signed' || assignment.status === 'declined'}
                                        >
                                            Remind
                                        </button>
                                        <button
                                            onClick={() => handleExportCSV(assignment.id)}
                                            className="export-btn"
                                        >
                                            Export CSV
                                        </button>
                                        <button
                                            onClick={() => handleExportPDF(assignment.id)}
                                            className="export-btn"
                                        >
                                            Export PDF
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

#### FamilyFormsView Component
```tsx
// File: frontend/src/pages/family/FormsView.tsx

import React, { useState, useEffect } from 'react';
import { formService } from '../services/form.service';
import { FormAssignment } from '../types/form';

const FamilyFormsView: React.FC = () => {
    const [forms, setForms] = useState<FormAssignment[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadForms();
    }, []);

    const loadForms = async () => {
        setLoading(true);
        try {
            const data = await formService.getFamilyForms();
            setForms(data);
        } finally {
            setLoading(false);
        }
    };

    const handleSignForm = async (assignmentId: string, signature: string, answers: any) => {
        try {
            await formService.signForm(assignmentId, signature, answers);
            alert('Form signed successfully');
            loadForms();
        } catch (error) {
            alert('Failed to sign form');
        }
    };

    return (
        <div className="family-forms-view">
            <h2>My Forms</h2>
            
            {loading ? (
                <p>Loading...</p>
            ) : forms.length > 0 ? (
                <div className="forms-list">
                    {forms.map((form) => (
                        <div key={form.id} className="form-card">
                            <h3>{form.formTitle}</h3>
                            <p>{form.formBody}</p>
                            <div className="form-meta">
                                <span>Audience: {form.audience}</span>
                                <span>Due: {new Date(form.dueDate).toLocaleDateString()}</span>
                            </div>
                            
                            {form.status === 'pending' && (
                                <div className="sign-form">
                                    <h4>Sign the Form</h4>
                                    <form onSubmit={(e) => {
                                        e.preventDefault();
                                        const signature = (e.target as any).signature.value;
                                        const answers = {};
                                        // Collect answers for each question
                                        handleSignForm(form.id, signature, answers);
                                    }}>
                                        <div className="signature-section">
                                            <label>Signature (type your full name)</label>
                                            <input
                                                type="text"
                                                name="signature"
                                                placeholder="Full Name"
                                                required
                                            />
                                        </div>
                                        
                                        {form.questions.map((question: any, index: number) => (
                                            <div key={index} className="question">
                                                <label>{question.text}</label>
                                                {question.type === 'yes/no' && (
                                                    <div className="options">
                                                        <label>
                                                            <input type="radio" name={`question-${index}`} value="yes" />
                                                            Yes
                                                        </label>
                                                        <label>
                                                            <input type="radio" name={`question-${index}`} value="no" />
                                                            No
                                                        </label>
                                                    </div>
                                                )}
                                                {question.type === 'text' && (
                                                    <input
                                                        type="text"
                                                        placeholder="Your answer"
                                                        required
                                                    />
                                                )}
                                                {question.type === 'choice' && (
                                                    <select required>
                                                        {question.options.map((option: string, optIndex: number) => (
                                                            <option key={optIndex} value={option}>{option}</option>
                                                        ))}
                                                    </select>
                                                )}
                                            </div>
                                        ))}
                                        
                                        <button type="submit" className="sign-btn">Sign & Submit</button>
                                    </form>
                                </div>
                            )}
                            
                            {form.status === 'signed' && (
                                <div className="signed-status">
                                    <h4>✓ Signed</h4>
                                    <p>Signed by: {form.guardianSignedName}</p>
                                    <p>Signed on: {new Date(form.signedAt).toLocaleDateString()}</p>
                                </div>
                            )}
                            
                            {form.status === 'declined' && (
                                <div className="declined-status">
                                    <h4>✗ Declined</h4>
                                    <p>{form.declineReason}</p>
                                </div>
                            )}
                            
                            {form.status === 'overdue' && (
                                <div className="overdue-status">
                                    <h4>⚠️ Overdue</h4>
                                    <p>Due: {new Date(form.dueDate).toLocaleDateString()}</p>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            ) : (
                <p>No forms to sign at this time.</p>
            )}
        </div>
    );
};
```

### 3. Backend API Endpoints

#### FormController
```python
# File: backend/services/education/views.py

class FormController(viewsets.ViewSet):
    def get_templates(self, request):
        templates = FormTemplate.objects.filter(is_active=True)
        serializer = FormTemplateSerializer(templates, many=True)
        return Response(serializer.data)

    def create_template(self, request):
        try:
            # Validate form structure
            data = request.data
            self.validate_form_structure(data)
            
            template = FormTemplate.objects.create(
                title=data['title'],
                body=data['body'],
                audience=data['audience'],
                audience_target=data['audience_target'],
                due_date=data['due_date'],
                questions=data['questions'],
                created_by=request.user if request.user else None
            )
            
            return Response(FormTemplateSerializer(template).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def assign_form(self, request, pk=None):
        try:
            template = FormTemplate.objects.get(pk=pk)
            
            if template.created_by != request.user and not self.is_admin(request.user):
                return Response(
                    {'error': 'You do not have permission to assign this form'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            data = request.data
            
            # Determine students to assign based on audience
            students = self.get_students_for_assignment(
                template.audience,
                template.audience_target,
                request.user.school
            )
            
            assignments_created = []
            for student in students:
                assignment = FormAssignment.objects.create(
                    form_template=template,
                    student=student,
                    assigned_by=request.user,
                    due_date=data.get('due_date', template.due_date),
                    reminder_sent=False
                )
                assignments_created.append(assignment)
            
            # Send notifications to guardians
            for assignment in assignments_created:
                self.send_form_notification(assignment)
            
            return Response({
                'assignments_created': len(assignments_created),
                'students': [{'id': s.id, 'name': s.get_full_name()} for s in students]
            })
        except FormTemplate.DoesNotExist:
            return Response(
                {'error': 'Form template not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_assignments(self, request):
        try:
            school_id = request.user.school_id
            
            assignments = FormAssignment.objects.filter(
                student__school_id=school_id
            )
            
            status = request.query_params.get('status')
            if status:
                assignments = assignments.filter(status=status)
            
            student_id = request.query_params.get('student_id')
            if student_id:
                assignments = assignments.filter(student_id=student_id)
            
            assignments = assignments.select_related(
                'form_template', 'student', 'student__guardian'
            )
            
            serializer = FormAssignmentSerializer(assignments, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def sign_form(self, request, pk=None):
        try:
            assignment = FormAssignment.objects.get(pk=pk)
            
            # Check if student is eligible for this form
            if not self.is_student_eligible(assignment, request.user):
                return Response(
                    {'error': 'Student is not eligible for this form'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if already signed
            existing_response = FormResponse.objects.filter(
                assignment=assignment,
                guardian=request.user
            ).first()
            
            if existing_response:
                return Response(
                    {'error': 'Form already signed for this student'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if form is still open
            if assignment.status not in ['pending', 'overdue']:
                return Response(
                    {'error': 'Form is not available for signing'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate responses against form questions
            response_data = request.data
            self.validate_form_responses(
                assignment.form_template.questions,
                response_data['responses']
            )
            
            response = FormResponse.objects.create(
                assignment=assignment,
                guardian=request.user,
                signature=response_data['signature'],
                responses=response_data['responses'],
                version_at_sign=assignment.form_template.updated_at.isoformat()
            )
            
            # Update assignment status
            if assignment.due_date < timezone.now():
                assignment.status = 'signed'
            else:
                assignment.status = 'signed'
            assignment.save()
            
            # Send notification
            self.send_form_signed_notification(assignment, response)
            
            serializer = FormResponseSerializer(response)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except FormAssignment.DoesNotExist:
            return Response(
                {'error': 'Form assignment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_family_forms(self, request):
        try:
            school_id = request.user.school_id
            
            # Get forms for students this user is a guardian of
            students = Student.objects.filter(
                school_id=school_id,
                guardians=request.user
            )
            
            assignments = FormAssignment.objects.filter(
                student__in=students
            ).select_related(
                'form_template',
                'student'
            )
            
            serializer = FormAssignmentSerializer(assignments, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def send_reminder(self, request, pk=None):
        try:
            assignment = FormAssignment.objects.get(pk=pk)
            
            if assignment.assigned_by != request.user and not self.is_admin(request.user):
                return Response(
                    {'error': 'You do not have permission to send reminder for this form'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if assignment.status not in ['pending', 'overdue']:
                return Response(
                    {'error': 'Form is not pending or overdue'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Send email and portal notification
            self.send_form_reminder_notification(assignment, request.user)
            
            assignment.reminder_sent = timezone.now()
            assignment.save()
            
            return Response({'success': True})
        except FormAssignment.DoesNotExist:
            return Response(
                {'error': 'Form assignment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def export_csv(self, request, pk=None):
        try:
            assignment = FormAssignment.objects.get(pk=pk)
            
            if assignment.assigned_by != request.user and not self.is_admin(request.user):
                return Response(
                    {'error': 'You do not have permission to export this form'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            responses = FormResponse.objects.filter(assignment=assignment)
            
            # Generate CSV data
            csv_data = self.generate_form_csv(assignment, responses)
            
            return Response({'csv_data': csv_data})
        except FormAssignment.DoesNotExist:
            return Response(
                {'error': 'Form assignment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def export_pdf(self, request, pk=None):
        try:
            assignment = FormAssignment.objects.get(pk=pk)
            
            if assignment.assigned_by != request.user and not self.is_admin(request.user):
                return Response(
                    {'error': 'You do not have permission to export this form'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            responses = FormResponse.objects.filter(assignment=assignment)
            
            # Generate PDF data
            pdf_data = self.generate_form_pdf(assignment, responses)
            
            return Response({'pdf_data': pdf_data})
        except FormAssignment.DoesNotExist:
            return Response(
                {'error': 'Form assignment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def is_admin(self, user):
        return user.role == 'admin'

    def is_student_eligible(self, assignment, guardian):
        # Check if guardian is linked to student
        return assignment.student.guardians.filter(id=guardian.id).exists()

    def get_students_for_assignment(self, audience, audience_target, school):
        students = Student.objects.filter(school=school)
        
        if audience == 'class':
            # Class-based filtering would need additional logic
            pass
        elif audience == 'grade':
            students = students.filter(grade_level=audience_target)
        elif audience == 'everyone':
            # Already all students
            pass
        
        return students

    def validate_form_structure(self, data):
        required_fields = ['title', 'body', 'audience', 'audience_target', 'due_date', 'questions']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        if not isinstance(data['questions'], list) or len(data['questions']) == 0:
            raise ValueError("Form must have at least one question")

    def validate_form_responses(self, questions, responses):
        for i, question in enumerate(questions):
            question_key = f'question_{i}'
            if question_key not in responses:
                continue
            
            answer = responses[question_key]
            
            if question['required'] and not answer:
                raise ValueError(f"Question '{question['text']}' is required")

    def send_form_notification(self, assignment):
        # Send email and portal notification to guardian
        pass

    def send_form_signed_notification(self, assignment, response):
        # Send confirmation of form signing
        pass

    def send_form_reminder_notification(self, assignment, sender):
        # Send reminder to guardian
        pass

    def generate_form_csv(self, assignment, responses):
        # Generate CSV data for responses
        pass

    def generate_form_pdf(self, assignment, responses):
        # Generate PDF data for responses
        pass
```

### 4. Permission System

Add permission checks for form access:
```python
# backend/services/education/permissions.py

class FormPermission:
    def has_permission(self, request):
        return request.user is not None

    def has_object_permission(self, request, view, obj):
        # Admin and staff can manage all forms
        if request.user.role in ['admin', 'office']:
            return True
        
        # Students can only view forms they're assigned to
        if isinstance(obj, FormAssignment):
            if obj.student == request.user:
                return True
        
        # Guardians can only access forms for their children
        if isinstance(obj, FormTemplate):
            if hasattr(obj, 'audience'):
                # Check if guardian has permission based on audience
                pass
        
        return False
```

### 5. Testing

#### Backend Tests
```python
# File: backend/tests/test_forms.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from permissions.models import FormTemplate, FormAssignment, FormResponse
from students.models import Student
from django.utils import timezone

class FormTests(TestCase):
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
        
        self.student = Student.objects.create(
            school=self.school,
            first_name='Test',
            last_name='Student',
            student_id='STU001'
        )
        
        self.guardian = get_user_model().objects.create_user(
            username='guardian',
            password='testpass',
            role='parent'
        )
        
        # Link guardian to student
        self.student.guardians.add(self.guardian)
        
        self.client.force_login(self.admin)
        
        self.form_template_data = {
            'title': 'Field Trip Permission',
            'body': 'Students will go on a field trip to the museum',
            'audience': 'class',
            'audience_target': 'Class A',
            'due_date': timezone.now() + timezone.timedelta(days=7),
            'questions': [
                {
                    'type': 'yes/no',
                    'text': 'Is your child healthy today?',
                    'required': True,
                },
                {
                    'type': 'text',
                    'text': 'Emergency contact name',
                    'required': True,
                },
                {
                    'type': 'choice',
                    'text': 'Permission level',
                    'required': True,
                    'options': ['Full', 'Partial', 'Not participating'],
                }
            ],
        }

    def test_create_form_template(self):
        response = self.client.post('/api/forms/templates/', self.form_template_data)
        
        self.assertEqual(response.status_code, 201)
        template = FormTemplate.objects.get(id=response.data['id'])
        self.assertEqual(template.title, 'Field Trip Permission')
        self.assertEqual(len(template.questions), 3)

    def test_assign_form(self):
        template = FormTemplate.objects.create(
            **self.form_template_data,
            created_by=self.admin
        )
        
        response = self.client.post(f'/api/forms/templates/{template.id}/assign/', {
            'due_date': timezone.now() + timezone.timedelta(days=7),
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['assignments_created'], 1)
        self.assertEqual(response.data['students'][0]['name'], 'Test Student')

    def test_sign_form(self):
        template = FormTemplate.objects.create(
            **self.form_template_data,
            created_by=self.admin
        )
        
        assignment = FormAssignment.objects.create(
            form_template=template,
            student=self.student,
            assigned_by=self.admin,
            due_date=timezone.now() + timezone.timedelta(days=7),
            status='pending'
        )
        
        response_data = {
            'signature': 'John Doe',
            'responses': {
                'question_0': 'yes',
                'question_1': 'Jane Smith',
                'question_2': 'Full',
            },
        }
        
        response = self.client.post(f'/api/forms/{assignment.id}/sign/', response_data)
        
        self.assertEqual(response.status_code, 201)
        form_response = FormResponse.objects.get(id=response.data['id'])
        self.assertEqual(form_response.guardian, self.guardian)
        self.assertEqual(form_response.signature, 'John Doe')
        
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'signed')

    def test_form_versioning(self):
        template = FormTemplate.objects.create(
            **self.form_template_data,
            created_by=self.admin
        )
        
        # Sign the form
        assignment = FormAssignment.objects.create(
            form_template=template,
            student=self.student,
            assigned_by=self.admin,
            due_date=timezone.now() + timezone.timedelta(days=7),
            status='pending'
        )
        
        self.client.post(f'/api/forms/{assignment.id}/sign/', {
            'signature': 'John Doe',
            'responses': {
                'question_0': 'yes',
                'question_1': 'Jane Smith',
                'question_2': 'Full',
            },
        })
        
        # Update the template
        template.body = 'Updated form body with new information'
        template.questions[0]['text'] = 'Is your child healthy today? (Updated)'
        template.save()
        
        # New assignments should use new version
        new_assignment = FormAssignment.objects.create(
            form_template=template,
            student=self.student,
            assigned_by=self.admin,
            due_date=timezone.now() + timezone.timedelta(days=7),
            status='pending'
        )
        
        response = self.client.post(f'/api/forms/{new_assignment.id}/sign/', {
            'signature': 'John Doe',
            'responses': {
                'question_0': 'yes',
                'question_1': 'Jane Smith',
                'question_2': 'Full',
            },
        })
        
        new_response = FormResponse.objects.get(assignment=new_assignment)
        self.assertEqual(new_response.version_at_sign, template.updated_at.isoformat())

    def test_export_form(self):
        template = FormTemplate.objects.create(
            **self.form_template_data,
            created_by=self.admin
        )
        
        assignment = FormAssignment.objects.create(
            form_template=template,
            student=self.student,
            assigned_by=self.admin,
            due_date=timezone.now() + timezone.timedelta(days=7),
            status='signed'
        )
        
        response = self.client.post(f'/api/forms/{assignment.id}/sign/', {
            'signature': 'John Doe',
            'responses': {
                'question_0': 'yes',
                'question_1': 'Jane Smith',
                'question_2': 'Full',
            },
        })
        
        # Export CSV
        response = self.client.get(f'/api/forms/{assignment.id}/export/csv/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('csv_data', response.data)
        self.assertIn('Field Trip Permission', response.data['csv_data'])

    def test_form_permissions(self):
        template = FormTemplate.objects.create(
            **self.form_template_data,
            created_by=self.admin
        )
        
        # Guardian cannot access admin-only forms
        self.client.force_login(self.guardian)
        
        response = self.client.get(f'/api/forms/templates/{template.id}/')
        self.assertEqual(response.status_code, 200)
        
        # Guardian can only access forms for their children
        self.client.force_login(self.admin)
        self.client.post(f'/api/forms/templates/{template.id}/assign/', {
            'due_date': timezone.now() + timezone.timedelta(days=7),
        })
        
        self.client.force_login(self.guardian)
        response = self.client.get('/api/forms/family-forms/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
```

#### Frontend Tests
```typescript
// File: frontend/src/components/forms/__tests__/FormsManagementScreen.test.tsx

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FormsManagementScreen } from '../FormsManagementScreen';
import { formService } from '../../services/form.service';

jest.mock('../../services/form.service');

const mockFormService = formService as jest.Mocked<typeof formService>;

describe('FormsManagementScreen', () => {
    const mockTemplate = {
        id: '1',
        title: 'Field Trip Permission',
        body: 'Students will go on a field trip to the museum',
        audience: 'class',
        audienceTarget: 'Class A',
        dueDate: new Date().toISOString(),
        questions: [],
        createdBy: { id: '1', name: 'Admin User' },
    };

    beforeEach(() => {
        mockFormService.getTemplates.mockResolvedValue([mockTemplate]);
        mockFormService.createTemplate.mockResolvedValue(mockTemplate);
    });

    it('allows admin to create form templates', async () => {
        render(<FormsManagementScreen />);
        
        fireEvent.click(screen.getByText('+ New Form'));
        
        fireEvent.change(screen.getByPlaceholderText('Form Title'), {
            target: { value: 'Field Trip Permission' },
        });
        fireEvent.change(screen.getByPlaceholderText('Form Body'), {
            target: { value: 'Students will go on a field trip' },
        });
        
        fireEvent.change(screen.getByPlaceholderText('Audience Target'), {
            target: { value: 'Class A' },
        });
        
        fireEvent.change(screen.getByPlaceholderText('Due Date'), {
            target: { value: new Date().toISOString().split('T')[0] },
        });
        
        fireEvent.click(screen.getByText('Create'));
        
        await waitFor(() => {
            expect(mockFormService.createTemplate).toHaveBeenCalled();
        });
    });
});
```

### 6. User Manual Update
```markdown
# Permission Slips and E-Signature Forms

## Who Can Use
- **Admin/Office staff**: Create, assign, and track all forms
- **Guardians**: View, sign, and manage forms for their children
- **Students**: View forms they're assigned to

## How to Use

### Creating and Assigning Forms
1. Go to **Forms & Permissions** → **Forms**
2. Click **+ New Form**
3. Fill in:
   - **Title**: Short, descriptive name
   - **Body**: Detailed description of the form purpose
   - **Audience**: Who receives the form
     - **Class**: Specific class (e.g., "Class A")
     - **Grade**: All students in a grade (e.g., "Grade 5")
     - **Everyone**: All students in the school
   - **Due Date**: When forms are due
   - **Questions**: Add questions (yes/no, text, choice)
4. Click **Create**
5. Forms are automatically assigned to eligible students

### Guardian View and Sign
1. Go to **Family** → **My Forms**
2. Review forms to sign
3. Click **Sign Form**
4. For each question:
   - **Yes/No**: Select your choice
   - **Text**: Type your answer
   - **Choice**: Select from options
5. Type your full name as signature
6. Click **Sign & Submit**

### Forms Tracker
1. Go to **Forms & Permissions** → **Forms Tracker**
2. Filter by status: Pending, Signed, Declined, Overdue
3. View student assignments
4. Click **Remind** for pending forms
5. Export responses to CSV or PDF

### Export Options
- **CSV**: For spreadsheet analysis
- **PDF**: For printing and sharing

## Form Features

### Questions
- **Yes/No**: Binary choices
- **Text**: Open-ended responses
- **Choice**: Multiple options to select from
- **Required**: Mark questions as mandatory

### Status Tracking
- **Pending**: Form assigned, not yet signed
- **Signed**: Form completed and submitted
- **Declined**: Form rejected by guardian
- **Overdue**: Past due date, still pending

### Notifications
- Email notifications when forms are assigned
- Reminder emails for overdue forms
- In-app notifications for new forms

### Export Features
- **CSV**: Download all responses in spreadsheet format
- **PDF**: Download printable version
- Data includes: student info, responses, timestamps, signatures

## Notes
- Forms are version-controlled; changes create new versions
- Signed responses cannot be edited
- Only guardians linked to students can sign forms
- Overdue forms automatically get reminder emails
- All form submissions are audit-logged
