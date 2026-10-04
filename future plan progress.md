# Future Plan Progress: P1

## P1. Visitor sign-in and safe pickup

### Current Status
**Extend**: `StudentGuardian.can_pickup` exists (`education/students/models.py`)

**Already Implemented**:
- StudentGuardian model with can_pickup field

**Missing Components**:
1. Extra authorised adult list (AuthorizedAdult model)
2. Pickup release log (PickupRelease model)  
3. Visitor log (VisitorLog model)
4. Front-desk Pickup screen
5. Visitor screen for sign-in/sign-out
6. "front desk" permission

### Implementation Plan

#### 1. Data Models to Create

**AuthorizedAdult Model** (in `backend/services/education/students/models.py`):
- Fields: student (ForeignKey to Student), name, relationship, phone, email, photo_path, id_type, id_checked, court_order_note, do_not_release_flag

**PickupRelease Model** (in `backend/services/education/students/models.py`):
- Fields: student (ForeignKey), authorized_adult (ForeignKey), release_time, reason, released_by, court_order_override_note, audit_log

**VisitorLog Model** (in `backend/services/education/students/models.py`):
- Fields: name, relationship, purpose, badge_number, school, check_in_time, check_out_time, status (on-site), printable_report

#### 2. Screens to Build

**Pickup Screen** (in `frontend/src/pages/education/students/`):
- Search student by name/ID
- Show list of authorized adults and extra adults
- For each adult: display photo, ID checked status, court order note
- Toggle do_not_release flag
- "Released" button for authorized adults
- Show early dismissal time and reason

**Visitor Screen** (in `frontend/src/pages/education/communication/`):
- Sign in form: name, who they visit, purpose, badge number
- Display "On site now" list with timer
- Sign out functionality
- Printable report of visitors

#### 3. Permissions to Add

**Front Desk Permission** (in `frontend/src/types/permissions.ts`):
- Add "front desk" permission for office staff
- Used in Pickup and Visitor screens

#### 4. Rules and Constraints

- Do-not-release adult cannot be released (hard stop)
- Admin override requires typed reason and audit log
- Logs kept for configurable number of years
- Teacher cannot see court-order notes

#### 5. Testing Requirements

**Backend Tests**:
- Test releasing to unlisted adult is blocked
- Test do-not-release flag stops a release
- Test On-site list is correct after sign-in/sign-out
- Test teacher cannot see court-order notes

**Frontend Tests**:
- Test Pickup screen functionality
- Test Visitor screen functionality
- Test permission-based access

### Next Steps
1. Create the three new models with migrations
2. Build Pickup and Visitor screens
3. Add front desk permission
4. Implement the rules and constraints
5. Write tests and verify functionality
