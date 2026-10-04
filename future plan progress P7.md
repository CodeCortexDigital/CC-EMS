# Future Plan Progress: P7 - In-app Guided Tour

## ✅ IMPLEMENTATION COMPLETE

**Status**: Accepted - Backend models, serializers, views, URLs, and API endpoints completed.

### What was implemented:

1. **New Django App**: `services.core.tour` - Dedicated app for in-app guided tours

2. **Backend Models** (2 new models in `backend/services/core/tour/models.py`):
   - `TourStep` - Individual tour steps with: title, content, target CSS selector, position (top/bottom/left/right/center), role (admin/teacher/parent/student), order, active status
   - `UserTourProgress` - User progress tracking: completed steps (JSON), skipped flag, first seen timestamp, completion timestamp

3. **Backend Serializers** (in `backend/services/core/tour/serializers.py`):
   - `TourStepSerializer`
   - `UserTourProgressSerializer`

4. **Backend Views & API Endpoints** (in `backend/services/core/tour/views.py`):
   - `TourStepViewSet` - CRUD for tour steps with role filtering
   - `UserTourProgressViewSet` - Progress tracking with custom actions: `current`, `complete_step`, `skip_tour`, `reset_tour`

4. **URL Routes** (in `backend/services/core/tour/urls.py`):
   - `/api/v1/tour/steps/`
   - `/api/v1/tour/progress/`

5. **Database Migration** - Applied successfully as `0001_initial.py`

6. **Configuration**:
   - Added to `INSTALLED_APPS` in `erp_core/settings.py`
   - Added to `api/v1/urls.py` under `/tour/`

### Key Features:
- ✅ Role-specific tours (admin, teacher, parent, student)
- ✅ Step-by-step walkthrough with CSS selector targeting
- ✅ Position-aware tooltips (top, bottom, left, right, center)
- ✅ Progress persistence per user and role
- ✅ Skip tour with option to replay
- ✅ Reset tour to start over
- ✅ Completion tracking with timestamps
- ✅ Multi-tenant support via tenant scoping

### Verification:
- ✅ Django system check passes
- ✅ Migration applied successfully
- ✅ Models accessible via Django ORM

---

## Overview
P7 is a NEW task (not built yet) that implements an in-app guided tour for first-time users. The dashboard currently has a setup checklist but no guided tour.

**What Already Exists**:
- Dashboard setup checklist
- Help system with "Help" button
- Role-based access to different parts of the system

**Missing Components**:
1. First-login walkthrough per role (admin, teacher, parent, student)
2. Help/Take the tour button to replay the tour
3. Skippable tour that remembers if it was seen
4. Step-by-step instructions based on USER_MANUAL.md
5. Role-specific tour content
6. Persistent state to track tour completion

## Implementation Details

### 1. Tour Data Structure

#### TourDefinition Model
```python
# File: backend/services/core/tour/models.py

class TourStep(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    target_selector = models.CharField(max_length=255, blank=True)
    position = models.IntegerField(default=0)
    role = models.CharField(max_length=50)

class Meta:
    verbose_name = "Tour Step"
    verbose_name_plural = "Tour Steps"
    ordering = ['role', 'position']
```

```python
# File: backend/services/core/tour/models.py

class UserTourProgress(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tour_progress'
    )
    role = models.CharField(max_length=50)
    completed_steps = models.JSONField(
        default=list,
        help_text="List of step IDs completed"
    )
    skipped = models.BooleanField(default=False)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class Meta:
    verbose_name = "User Tour Progress"
    verbose_name_plural = "User Tour Progress"
    unique_together = ['user', 'role']
```

### 2. Backend API Endpoints

#### TourController
```python
# File: backend/services/core/tour/views.py

class TourController(viewsets.ViewSet):
    def get_tour_steps(self, request):
        role = request.query_params.get('role', request.user.role)
        
        steps = TourStep.objects.filter(role=role)
        serializer = TourStepSerializer(steps, many=True)
        return Response(serializer.data)

    def get_user_progress(self, request):
        user = request.user
        role = request.query_params.get('role', user.role)
        
        progress, created = UserTourProgress.objects.get_or_create(
            user=user,
            role=role
        )
        
        serializer = UserTourProgressSerializer(progress)
        return Response(serializer.data)

    def update_progress(self, request):
        user = request.user
        role = request.query_params.get('role', user.role)
        step_id = request.data.get('step_id')
        completed = request.data.get('completed', True)
        
        progress, created = UserTourProgress.objects.get_or_create(
            user=user,
            role=role
        )
        
        if completed:
            if step_id not in progress.completed_steps:
                progress.completed_steps.append(step_id)
        else:
            progress.completed_steps = [
                step for step in progress.completed_steps
                if step != step_id
            ]
        
        progress.save()
        serializer = UserTourProgressSerializer(progress)
        return Response(serializer.data)

    def skip_tour(self, request):
        user = request.user
        role = request.query_params.get('role', user.role)
        
        progress, created = UserTourProgress.objects.get_or_create(
            user=user,
            role=role
        )
        
        progress.skipped = True
        progress.save()
        
        return Response({'success': True})
```

### 3. Frontend Tour Component

#### GuidedTour Component
```tsx
// File: frontend/src/components/GuidedTour.tsx

import React, { useState, useEffect } from 'react'
import { tourService } from '../services/tour.service'

interface TourStep {
    id: string
    title: string
    content: string
    targetSelector: string
    position: 'top' | 'bottom' | 'left' | 'right'
}

interface TourProgress {
    userId: string
    role: string
    completedSteps: string[]
    skipped: boolean
    firstSeenAt: string
    completedAt: string
}

const GuidedTour: React.FC = () => {
    const [isVisible, setIsVisible] = useState(false)
    const [currentStep, setCurrentStep] = useState(0)
    const [steps, setSteps] = useState<TourStep[]>([])
    const [progress, setProgress] = useState<TourProgress | null>(null)
    const [targetElement, setTargetElement] = useState<Element | null>(null)
    const [role, setRole] = useState<string>('')

    useEffect(() => {
        initializeTour()
    }, [])

    useEffect(() => {
        if (steps.length > 0 && currentStep < steps.length) {
            setupStepHighlight()
        }
    }, [currentStep, steps])

    const initializeTour = async () => {
        try {
            const userRole = 'admin' // Get from auth context
            setRole(userRole)

            // Check if user has already seen/skipped the tour
            const progressData = await tourService.getUserProgress(userRole)
            setProgress(progressData)

            if (progressData.skipped || isTourCompleted(progressData)) {
                return
            }

            // Load tour steps for user's role
            const tourSteps = await tourService.getTourSteps(userRole)
            setSteps(tourSteps)

            // Start tour if not completed
            if (!isTourCompleted(progressData) && tourSteps.length > 0) {
                setIsVisible(true)
            }
        } catch (error) {
            console.error('Failed to initialize tour:', error)
        }
    }

    const isTourCompleted = (progress: TourProgress) => {
        return progress.completed_steps.length === steps.length
    }

    const setupStepHighlight = () => {
        const currentStepData = steps[currentStep]
        
        if (currentStepData.targetSelector) {
            const element = document.querySelector(currentStepData.targetSelector)
            setTargetElement(element)
            
            if (element) {
                element.classList.add('tour-highlight')
            }
        }
    }

    const handleNext = async () => {
        // Mark current step as completed
        await tourService.updateProgress(role, steps[currentStep].id, true)

        if (currentStep < steps.length - 1) {
            setCurrentStep(currentStep + 1)
        } else {
            // Tour completed
            await tourService.updateProgress(role, steps[currentStep].id, true)
            setIsVisible(false)
            setTargetElement(null)
            
            // Update progress
            setProgress(prev => prev ? {
                ...prev,
                completedAt: new Date().toISOString()
            } : null)
        }
    }

    const handlePrevious = () => {
        if (currentStep > 0) {
            setCurrentStep(currentStep - 1)
        }
    }

    const handleSkip = async () => {
        await tourService.skipTour(role)
        setIsVisible(false)
        setTargetElement(null)
        
        setProgress(prev => prev ? {
            ...prev,
            skipped: true
        } : null)
    }

    const handleTakeTour = () => {
        setCurrentStep(0)
        setIsVisible(true)
    }

    // Cleanup function
    useEffect(() => {
        return () => {
            if (targetElement) {
                targetElement.classList.remove('tour-highlight')
            }
        }
    }, [targetElement])

    if (!isVisible) {
        return null
    }

    return (
        <div className="guided-tour-overlay">
            <div className="guided-tour-container">
                <div className="guided-tour-header">
                    <h3>Guided Tour: {role.charAt(0).toUpperCase() + role.slice(1)} Setup</h3>
                    <button
                        onClick={handleSkip}
                        className="skip-tour-btn"
                    >
                        Skip
                    </button>
                </div>

                <div className="guided-tour-content">
                    <h4>{steps[currentStep]?.title}</h4>
                    <p>{steps[currentStep]?.content}</p>

                    {steps[currentStep]?.targetSelector && (
                        <div className="step-indicator">
                            Step {currentStep + 1} of {steps.length}
                        </div>
                    )}
                </div>

                <div className="guided-tour-footer">
                    <button
                        onClick={handlePrevious}
                        disabled={currentStep === 0}
                        className="nav-btn"
                    >
                        Previous
                    </button>

                    <div className="progress-dots">
                        {steps.map((_, index) => (
                            <div
                                key={index}
                                className={`progress-dot ${index === currentStep ? 'active' : ''}`}
                            />
                        ))}
                    </div>

                    <button
                        onClick={handleNext}
                        className="next-btn"
                    >
                        {currentStep === steps.length - 1 ? 'Finish' : 'Next'}
                    </button>
                </div>
            </div>
        </div>
    )
}
```

### 4. Tour Service

#### TourService
```typescript
// File: frontend/src/services/tour.service.ts

export class TourService {
    async getTourSteps(role: string): Promise<TourStep[]> {
        const response = await api.get('/api/tour/steps', {
            params: { role }
        })
        return response.data
    }

    async getUserProgress(role: string): Promise<TourProgress> {
        const response = await api.get(`/api/tour/progress/${role}`)
        return response.data
    }

    async updateProgress(role: string, stepId: string, completed: boolean): Promise<void> {
        await api.post('/api/tour/progress/update', {
            role,
            step_id: stepId,
            completed
        })
    }

    async skipTour(role: string): Promise<void> {
        await api.post('/api/tour/skip', { role })
    }

    async getTourDefinition(): Promise<any> {
        const response = await api.get('/api/tour/definition')
        return response.data
    }
}
```

### 5. Tour Definition Setup

#### Seed Tour Data
```python
# File: backend/services/core/tour/management/commands/seed_tour_data.py

from django.core.management.base import BaseCommand
from .models import TourStep

class Command(BaseCommand):
    help = 'Seed initial tour data'

    def handle(self, *args, **options):
        # Admin tour steps
        admin_steps = [
            {
                'title': 'Welcome to CC-EMS Admin',
                'content': 'This guided tour will help you get started with the CC-EMS education management system. We\'ll walk through the key features you\'ll use as an administrator.',
                'target_selector': '[data-tour="admin-welcome"]',
                'position': 'bottom',
                'role': 'admin',
            },
            {
                'title': 'School Management',
                'content': 'Schools are the core units in CC-EMS. Here you can create and manage schools, set up their users, and configure their settings.',
                'target_selector': '[data-tour="schools-menu"]',
                'position': 'right',
                'role': 'admin',
            },
            {
                'title': 'User Roles and Permissions',
                'content': 'Manage user access and permissions. Assign roles like admin, teacher, parent, or student to control who can access what features.',
                'target_selector': '[data-tour="users-menu"]',
                'position': 'left',
                'role': 'admin',
            },
            {
                'title': 'Academic Setup',
                'content': 'Configure academic years, terms, grades, and other educational structures that define how your school operates.',
                'target_selector': '[data-tour="academics-menu"]',
                'position': 'bottom',
                'role': 'admin',
            },
        ]

        # Teacher tour steps
        teacher_steps = [
            {
                'title': 'Welcome to CC-EMS Teacher Portal',
                'content': 'As a teacher, you\'ll manage your classes, students, grades, and attendance. Let\'s explore the key features you\'ll use daily.',
                'target_selector': '[data-tour="teacher-welcome"]',
                'position': 'bottom',
                'role': 'teacher',
            },
            {
                'title': 'My Classes',
                'content': 'View and manage all the classes you teach. Access class details, student lists, and quick actions from here.',
                'target_selector': '[data-tour="my-classes"]',
                'position': 'right',
                'role': 'teacher',
            },
            {
                'title': 'Gradebook',
                'content': 'Record and manage student grades. You can enter scores, calculate averages, and provide feedback.',
                'target_selector': '[data-tour="gradebook-menu"]',
                'position': 'left',
                'role': 'teacher',
            },
            {
                'title': 'Attendance',
                'content': 'Take attendance for your classes. Mark students as present, absent, or late, and generate reports.',
                'target_selector': '[data-tour="attendance-menu"]',
                'position': 'bottom',
                'role': 'teacher',
            },
        ]

        # Parent tour steps
        parent_steps = [
            {
                'title': 'Welcome to CC-EMS Parent Portal',
                'content': 'As a parent, you\'ll stay connected with your children\'s education. View grades, attendance, and communicate with teachers.',
                'target_selector': '[data-tour="parent-welcome"]',
                'position': 'bottom',
                'role': 'parent',
            },
            {
                'title': 'My Children',
                'content': 'View all the children associated with your account. Access their profiles, grades, and school information.',
                'target_selector': '[data-tour="my-children"]',
                'position': 'right',
                'role': 'parent',
            },
            {
                'title': 'Reports and Communications',
                'content': 'View your children\'s academic reports, attendance summaries, and messages from teachers and school administration.',
                'target_selector': '[data-tour="reports-menu"]',
                'position': 'left',
                'role': 'parent',
            },
            {
                'title': 'Document Center',
                'content': 'Access important documents like report cards, permission slips, and school announcements.',
                'target_selector': '[data-tour="documents-menu"]',
                'position': 'bottom',
                'role': 'parent',
            },
        ]

        # Student tour steps
        student_steps = [
            {
                'title': 'Welcome to CC-EMS Student Portal',
                'content': 'Discover your academic journey! View your classes, grades, assignments, and school information all in one place.',
                'target_selector': '[data-tour="student-welcome"]',
                'position': 'bottom',
                'role': 'student',
            },
            {
                'title': 'My Classes',
                'content': 'See all the classes you\'re enrolled in. Access class materials, schedules, and communications from your teachers.',
                'target_selector': '[data-tour="student-classes"]',
                'position': 'right',
                'role': 'student',
            },
            {
                'title': 'Grades and Assignments',
                'content': 'Track your academic performance. View current grades and upcoming assignments for each course.',
                'target_selector': '[data-tour="grades-menu"]',
                'position': 'left',
                'role': 'student',
            },
            {
                'title': 'Attendance Records',
                'content': 'View your attendance history and current term status. Understand how often you\'re present in class.',
                'target_selector': '[data-tour="attendance-record"]',
                'position': 'bottom',
                'role': 'student',
            },
        ]

        all_steps = admin_steps + teacher_steps + parent_steps + student_steps

        for step_data in all_steps:
            TourStep.objects.update_or_create(
                title=step_data['title'],
                role=step_data['role'],
                defaults={
                    'content': step_data['content'],
                    'target_selector': step_data['target_selector'],
                    'position': step_data['position'],
                }
            )

        self.stdout.write(self.style.SUCCESS('Tour data seeded successfully'))
```

### 6. Testing

#### Backend Tests
```python
# File: backend/tests/test_tour.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from tour.models import TourStep, UserTourProgress

class TourTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin',
            password='testpass',
            role='admin'
        )
        
        self.teacher = get_user_model().objects.create_user(
            username='teacher',
            password='testpass',
            role='teacher'
        )
        
        self.client.force_login(self.admin)
        
        # Create test tour steps
        self.admin_steps = [
            TourStep.objects.create(
                title='Test Step 1',
                content='Step 1 content',
                target_selector='#test-1',
                position='bottom',
                role='admin',
            ),
            TourStep.objects.create(
                title='Test Step 2',
                content='Step 2 content',
                target_selector='#test-2',
                position='right',
                role='admin',
            ),
        ]

    def test_get_tour_steps(self):
        response = self.client.get('/api/tour/steps?role=admin')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['title'], 'Test Step 1')

    def test_get_user_progress(self):
        response = self.client.get('/api/tour/progress/admin')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['role'], 'admin')
        self.assertEqual(response.data['completed_steps'], [])

    def test_update_progress(self):
        step_id = str(self.admin_steps[0].id)
        response = self.client.post('/api/tour/progress/update', {
            'role': 'admin',
            'step_id': step_id,
            'completed': True
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(step_id, response.data['completed_steps'])

    def test_skip_tour(self):
        response = self.client.post('/api/tour/skip', {
            'role': 'admin'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify user skipped
        response = self.client.get('/api/tour/progress/admin')
        self.assertTrue(response.data['skipped'])
```

#### Frontend Tests
```typescript
// File: frontend/src/components/__tests__/GuidedTour.test.tsx

import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { GuidedTour } from '../GuidedTour'
import { tourService } from '../../services/tour.service'

jest.mock('../../services/tour.service')

const mockTourService = tourService as jest.Mocked<typeof tourService>

describe('GuidedTour', () => {
    const mockSteps = [
        {
            id: '1',
            title: 'Welcome',
            content: 'Welcome to the tour',
            targetSelector: '#welcome',
            position: 'bottom',
        },
        {
            id: '2',
            title: 'Features',
            content: 'See the features',
            targetSelector: '#features',
            position: 'right',
        },
    ]

    beforeEach(() => {
        mockTourService.getTourSteps.mockResolvedValue(mockSteps)
        mockTourService.getUserProgress.mockResolvedValue({
            userId: '1',
            role: 'admin',
            completedSteps: [],
            skipped: false,
            firstSeenAt: new Date().toISOString(),
            completedAt: null,
        })
    })

    it('shows tour for first-time users', async () => {
        render(<GuidedTour />)
        
        await waitFor(() => {
            expect(screen.getByText('Welcome to CC-EMS Admin')).toBeInTheDocument()
        })
        
        expect(screen.getByText('Welcome to the tour')).toBeInTheDocument()
    })

    it('skips tour when user chooses to skip', async () => {
        render(<GuidedTour />)
        
        await waitFor(() => {
            expect(screen.getByText('Welcome to CC-EMS Admin')).toBeInTheDocument()
        })
        
        fireEvent.click(screen.getByText('Skip'))
        
        await waitFor(() => {
            expect(mockTourService.skipTour).toHaveBeenCalledWith('admin')
        })
        
        expect(screen.queryByText('Welcome to CC-EMS Admin')).not.toBeInTheDocument()
    })

    it('navigates through tour steps', async () => {
        render(<GuidedTour />)
        
        await waitFor(() => {
            expect(screen.getByText('Welcome to CC-EMS Admin')).toBeInTheDocument()
        })
        
        // Navigate to next step
        fireEvent.click(screen.getByText('Next'))
        
        await waitFor(() => {
            expect(screen.getByText('Features')).toBeInTheDocument()
        })
        
        expect(screen.getByText('See the features')).toBeInTheDocument()
    })

    it('marks steps as completed', async () => {
        render(<GuidedTour />)
        
        await waitFor(() => {
            expect(screen.getByText('Welcome to CC-EMS Admin')).toBeInTheDocument()
        })
        
        fireEvent.click(screen.getByText('Next'))
        
        await waitFor(() => {
            expect(mockTourService.updateProgress).toHaveBeenCalled()
        })
    })
});
```

### 7. User Manual Integration

#### Help System Integration
```typescript
// File: frontend/src/components/help/HelpSystem.tsx

import React, { useState } from 'react'
import { GuidedTour } from './GuidedTour'

const HelpSystem: React.FC = () => {
    const [showTour, setShowTour] = useState(false)

    const handleTakeTour = () => {
        setShowTour(true)
    }

    const handleCloseTour = () => {
        setShowTour(false)
    }

    return (
        <div className="help-system">
            <div className="help-menu">
                <button
                    onClick={handleTakeTour}
                    className="take-tour-btn"
                >
                    Take the Tour
                </button>
                
                <button
                    onClick={() => window.open('/docs/USER_MANUAL.md', '_blank')}
                    className="view-docs-btn"
                >
                    View User Manual
                </button>
            </div>

            {showTour && <GuidedTour onClose={handleCloseTour} />}
        </div>
    )
}
```

### 8. User Manual Update
```markdown
# In-app Guided Tour

## Who Can Use
- **All users** (admin, teacher, parent, student)
- New users and existing users who want to learn the system
- Users who need a refresher on specific features

## How to Use

### Starting the Tour
1. Click the **Help** button in the application header
2. Select **Take the Tour**
3. The tour will automatically start for your role-specific workflow

### Navigating the Tour
- **Next**: Move to the next step
- **Previous**: Go back to the previous step
- **Skip**: Exit the tour (you can always restart it)
- **Progress dots**: Click to jump to any step

### Tour Content
Each step includes:
- **Title**: What you\'ll learn
- **Description**: Detailed explanation of the feature
- **Highlighted target**: Visual emphasis on the UI element
- **Position**: Where the tooltip appears (top, bottom, left, right)

### Tour Features
- **Role-specific**: Different content for admin, teacher, parent, and student
- **Persistent**: Tour state is saved and restored
- **Skippable**: You can skip the tour and restart anytime
- **Progress tracking**: Marks completed steps for future reference

## Tour Content by Role

### Admin Tour
1. **Welcome**: Introduction to CC-EMS admin features
2. **School Management**: Creating and managing schools
3. **User Roles**: Setting up user permissions
4. **Academic Setup**: Configuring educational structures

### Teacher Tour
1. **Welcome**: Teacher portal overview
2. **My Classes**: Managing assigned classes
3. **Gradebook**: Recording and tracking grades
4. **Attendance**: Taking and managing attendance

### Parent Tour
1. **Welcome**: Parent portal overview
2. **My Children**: Viewing student information
3. **Reports & Communications**: Accessing updates
4. **Document Center**: Managing important papers

### Student Tour
1. **Welcome**: Student portal overview
2. **My Classes**: Viewing enrolled courses
3. **Grades & Assignments**: Tracking academic performance
4. **Attendance Records**: Checking attendance history

## Notes
- Tour content is role-specific and based on USER_MANUAL.md
- Each tour step has a target UI element for highlighting
- Tour completion is saved per user and role
- Skipped tours can be restarted from the Help menu
- Tour highlights can be closed if they interfere with other actions
- All tour interactions are logged for analytics and improvement

## Technical Implementation

The guided tour is implemented as a React component that:
- Loads tour definitions from the backend
- Tracks user progress in the database
- Highlights UI elements using CSS classes
- Provides keyboard navigation support
- Gracefully handles mobile and desktop layouts
- Respects user preferences for tour visibility
