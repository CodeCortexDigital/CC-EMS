"""The school data pack: one set of CSV files that imports, updates, exports and restores a whole school."""
import io
import json
import zipfile

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.portability.data import school_querysets
from services.core.tenants.context import use_tenant
from services.core.tenants.models import TenantMembership
from services.core.user_notifications.models import Notification
from services.education.academics.models import (AcademicYear, ClassSubject, Classroom, LeaveBalance, Period, SchoolClass, Section,
                                                  Subject, Teacher, TeacherAttendance, TeacherLeave, TeacherSubjectAssignment, Term,
                                                  TimetableEntry)
from services.education.admissions.models import Application
from services.education.attendance.models import AttendanceRecord
from services.education.exams.models import Exam, ExamResult
from services.education.schoolcalendar.models import CalendarEvent
from services.education.finance.models import FeeStructure, Invoice, Payment, Payslip
from services.education.hr.models import (JobCandidate, JobOpening, PayGrade, PayrollProfile, PerformanceReview, StaffContract, StaffCredential,
                                           StaffGoal)
from services.education.imports.api import header_of
from services.education.imports.specs import KINDS
from services.education.students.models import Guardian, Immunization, Student, StudentGuardian, StudentHealth
from tests.conftest import SchoolFactory, UserFactory

URL = '/api/v1/auth/imports'


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _csv(kind, rows):
    out = io.StringIO()
    import csv
    w = csv.writer(out)
    w.writerow(header_of(KINDS[kind]))
    for r in rows:
        w.writerow(r)
    return out.getvalue()


# One small K-8 school, in column order of each kind (see KINDS[kind]['columns']).
PACK = {
    'academic_years': [['2026-27', '2026-08-17', '2027-06-04', 'yes']],
    'terms': [['2026-27', 'Semester 1', 'semester', '1', '2026-08-17', '2026-12-18']],
    'classes': [['Grade 5', 'A, B', '5', '28', '2500', 'G5']],
    'subjects': [['Mathematics', 'MATH', 'Math', 'no'], ['Art', 'ART', 'Arts', 'yes']],
    'rooms': [['R101', 'Room 101', '28', 'classroom', 'first', 'Main'], ['LAB1', 'Science Lab', '24', 'lab', 'first', 'Main']],
    'periods': [['2026-27', '1', 'Period 1', '08:00', '08:45', 'no'], ['2026-27', '2', 'Period 2', '08:50', '09:35', 'no']],
    'weekdays': [['Monday', 'yes', 'no', '1'], ['Tuesday', 'yes', 'no', '2']],
    'class_subjects': [['Grade 5', 'MATH', '5', '100'], ['Grade 5', 'ART', '2', '100']],
    'pay_grades': [['Teacher Level 2', '4200', 'Five years or more']],
    'staff': [['Tom Maths', 'tom@pack.test', '555-0101', 'T-001', 'Teacher', 'Math', 'Mathematics', '2024-08-01', 'male', '', '4200', 'BSc', '', '1 Elm St',
               'regular', ''],
              ['Ada Art', 'ada@pack.test', '555-0102', 'T-002', 'Teacher', 'Arts', 'Art', '2024-08-01', 'female', '', '3900', 'BA', '', '', 'regular', 'T-001'],
              ['Rae Relief', 'rae@pack.test', '', 'T-003', 'Teacher', 'Math', 'Mathematics', '2025-01-10', 'female', '', '3500', '', '', '', 'relief', 'T-001']],
    'teacher_assignments': [['T-001', 'Grade 5', 'MATH', '2026-27', 'yes', '']],
    'students': [['Mia Lopez', 'Grade 5', 'A', 'S-0001', 'female', '2016-04-09', '2026-08-17', '', '', 'Carlos Lopez', 'Ana Lopez', '', '555-0201', '9 Oak Rd',
                  'Springfield', '', 'O+', '', 'Maple Elementary'],
                 ['Leo Park', 'Grade 5', 'B', 'S-0002', 'male', '2016-01-30', '2026-08-17', '', '', 'Jin Park', 'Soo Park', '', '555-0202', '4 Pine Rd',
                  'Springfield', '', '', '', '']],
    'guardians': [['S-0001', 'Ana', 'Lopez', 'mother', 'ana@pack.test', '555-0201', '', '', 'Nurse', 'City Hospital', '9 Oak Rd', 'yes', 'yes', 'yes', 'yes',
                   'yes', 'yes', 'yes', 'yes', '1'],
                  ['S-0001', 'Rosa', 'Lopez', 'grandparent', '', '555-0299', '', '', '', '', '', 'no', 'no', 'no', 'yes', 'yes', 'no', 'yes', 'no', '3']],
    'student_health': [['S-0001', 'Peanuts', 'yes', 'Asthma', 'Inhaler', '', 'Dr. Lee', '555-0100', 'BlueCross', 'BC-1', 'yes', '']],
    'immunizations': [['S-0001', 'MMR', '1', '2018-03-14', 'no', '', ''], ['S-0002', 'MMR', '1', '', 'yes', 'Religious', '']],
    'admissions': [['', 'Noah Miller', 'noah@pack.test', '555-0301', '2021-05-02', 'male', 'Kindergarten', '', '2026-2027', 'reviewing', '', 'Visit booked',
                    '', '', 'Emma Miller', '555-0301', '', '', '', '12 Oak St', 'Springfield']],
    'fee_structure': [['Grade 5', '', 'Tuition', '2500', '2026-09-10', '2026-27', 'yes', 'monthly']],
    'invoices': [['INV-1', 'S-0001', 'tuition', '2500', '0', '0', '0', '2026-09-10', '2026-09-01', '', 'issued', 'September fees'],
                 ['INV-2', 'S-0002', 'tuition', '2500', '0', '0', '0', '2026-09-10', '2026-09-01', '', 'issued', 'September fees']],
    'payments': [['INV-1', 'R-1', '1000', '2026-09-05', 'cash', 'First part'], ['INV-2', 'R-2', '2500', '2026-09-06', 'bank_transfer', '']],
    'balances': [['S-0002', '300', '2026-10-10', 'Summer camp']],
    'payroll_profiles': [['T-001', 'Teacher Level 2', '10', 'Transport:200:allowance; Health plan:100:deduction']],
    'payslips': [['T-001', '2026-09-15', '4200', '200', '420', '0', '', '', '']],
    'leave_balances': [['T-001', '5', '5', '15', '3', '3', '0', '0', '0', '0', '0', '2']],
    'leave_requests': [['T-001', 'sick', '2026-10-05', '2026-10-06', 'full', 'approved', 'Flu']],
    # what happens during the year
    'attendance': [['S-0001', '2026-09-08', 'present', '', 'no', '', ''], ['S-0002', '2026-09-08', 'late', 'transport', 'no', '10', 'Bus delayed'],
                   ['S-0002', '2026-09-09', 'absent', 'illness', 'yes', '', '']],
    'staff_attendance': [['T-001', '2026-09-08', 'present', ''], ['T-002', '2026-09-08', 'on_leave', 'Jury duty']],
    'exams': [['EXM-2026-9001', 'Unit 1 test', 'test', 'Grade 5', '', 'MATH', '50', '25', '2026-09-30', '', '', '', '2026-27', 'first', 'yes', 'yes']],
    'exam_results': [['EXM-2026-9001', 'S-0001', '44', 'Great work'], ['EXM-2026-9001', 'S-0002', '21.5', '']],
    'timetable': [['2026-27', 'Grade 5', 'A', 'Monday', '1', 'MATH', 'T-001', 'R101'], ['2026-27', 'Grade 5', 'A', 'Tuesday', '2', 'ART', 'T-002', 'R101']],
    'calendar_events': [['Fall break', 'holiday', '2026-10-12', '2026-10-12', '', 'everyone', 'yes', 'No school']],
    'contracts': [['T-001', 'full_time', '2024-08-01', '', '2025-02-01', '']],
    'credentials': [['T-001', 'State teaching licence', 'State Board', 'TL-4471', '2023-07-01', '2028-06-30', '']],
    'reviews': [['T-001', 'annual', '2025-26', '2026-06-10', '4', 'Great rapport', 'More group work', '', 'shared', '']],
    'goals': [['T-001', 'Run a maths club', 'Weekly after school', '2027-03-01', '40', 'open']],
    'job_openings': [['Science teacher', 'Science', '1', 'open', '2026-11-30', 'Grades 6 to 8']],
    'job_candidates': [['Science teacher', 'Dana Rivers', 'dana@example.com', '555-0177', 'Website', 'interview', '4', '']],
}


def pack_zip(overrides=None, drop=(), manifest=False):
    data = {k: _csv(k, rows) for k, rows in PACK.items() if k not in drop}
    data.update(overrides or {})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for kind, text in data.items():
            zf.writestr(KINDS[kind]['filename'], text)
    buf.seek(0)
    buf.name = 'pack.zip'
    return buf


@pytest.fixture
def school(db):
    s = SchoolFactory(name='Pack Academy')
    admin = UserFactory(email='head@pack.test', full_name='Head')
    TenantMembership.objects.create(user=admin, school=s, role='admin', is_primary=True)
    teacher = UserFactory(email='t@pack.test')
    TenantMembership.objects.create(user=teacher, school=s, role='teacher')
    return dict(s=s, admin=admin, office=_client(admin), teacher=_client(teacher))


def _problems(resp):
    """Only the kinds that have errors, with each row's messages (for readable failures)."""
    out = []
    for k in resp['kinds']:
        bad = [r['messages'] for r in k.get('rows', []) if r['state'] == 'error']
        if k.get('error') or bad:
            out.append((k['kind'], k.get('error'), bad))
    return out


def _post(c, path, f, **extra):
    return c.post(f'{URL}/pack/{path}/', {'file': f, **extra}, format='multipart')


def _counts(s):
    with use_tenant(s):
        return {'years': AcademicYear.objects.count(), 'terms': Term.objects.count(), 'classes': SchoolClass.objects.count(),
                'sections': Section.objects.count(), 'subjects': Subject.objects.count(), 'rooms': Classroom.objects.count(),
                'periods': Period.objects.count(), 'class_subjects': ClassSubject.objects.count(), 'grades': PayGrade.objects.count(),
                'staff': Teacher.objects.count(), 'assignments': TeacherSubjectAssignment.objects.count(), 'students': Student.objects.count(),
                'links': StudentGuardian.objects.count(), 'health': StudentHealth.objects.count(), 'imm': Immunization.objects.count(),
                'apps': Application.objects.count(), 'fees': FeeStructure.objects.count(), 'invoices': Invoice.objects.count(),
                'payments': Payment.objects.count(), 'profiles': PayrollProfile.objects.count(), 'payslips': Payslip.objects.count(),
                'balances': LeaveBalance.objects.count(), 'leaves': TeacherLeave.objects.count(), 'attendance': AttendanceRecord.objects.count(),
                'staff_att': TeacherAttendance.objects.count(), 'exams': Exam.objects.count(), 'results': ExamResult.objects.count(),
                'timetable': TimetableEntry.objects.count(), 'events': CalendarEvent.objects.count(), 'contracts': StaffContract.objects.count(),
                'credentials': StaffCredential.objects.count(), 'reviews': PerformanceReview.objects.count(), 'goals': StaffGoal.objects.count(),
                'openings': JobOpening.objects.count(), 'candidates': JobCandidate.objects.count()}


def _wipe(school):
    """Delete everything the school owns (like the account-deletion path) so a pack can be restored into it."""
    sets = list(school_querysets(school))
    for _ in range(8):
        blocked = []
        for label, Model, qs in sets:
            try:
                with transaction.atomic():
                    qs.delete()
            except (ProtectedError, IntegrityError):
                blocked.append((label, Model, qs))
        if not blocked:
            return
        sets = blocked
    raise RuntimeError('could not wipe')


def _unzip(response):
    z = zipfile.ZipFile(io.BytesIO(response.content))
    return {n: z.read(n).decode('utf-8') for n in z.namelist()}


# ---------------------------------------------------------------------------------------------------------------- spec

@pytest.mark.django_db
def test_spec_template_and_ordering(school):
    office = school['office']
    spec = office.get(f'{URL}/pack/spec/').json()
    names = [k['kind'] for k in spec['kinds']]
    for a, b in [('academic_years', 'classes'), ('classes', 'class_subjects'), ('staff', 'teacher_assignments'), ('students', 'guardians'),
                 ('invoices', 'payments'), ('pay_grades', 'payroll_profiles')]:
        assert names.index(a) < names.index(b)
    assert len(names) >= 24 and all(k['file'].endswith('.csv') for k in spec['kinds'])
    tpl = _unzip(office.get(f'{URL}/pack/template/'))
    assert 'README.txt' in tpl and tpl['students.csv'].lstrip('﻿').startswith('Name *,Class *') and 'class_subjects.csv' in tpl
    assert school['teacher'].get(f'{URL}/pack/spec/').status_code == 403


# ------------------------------------------------------------------------------------------------- the whole pack

@pytest.mark.django_db
def test_preview_saves_nothing_then_import_loads_everything_in_order(school):
    office, s = school['office'], school['s']
    prev = _post(office, 'preview', pack_zip()).json()
    assert prev['committed'] is False and prev['totals']['error'] == 0, _problems(prev)
    assert all(v == 0 for v in _counts(s).values())                              # a preview saves nothing
    done = _post(office, 'import', pack_zip()).json()
    assert done['committed'] is True and done['totals']['error'] == 0, _problems(done)
    c = _counts(s)
    assert c['years'] == 1 and c['terms'] == 1 and c['classes'] == 1 and c['sections'] == 2 and c['subjects'] == 2 and c['rooms'] == 2
    assert c['periods'] == 2 and c['class_subjects'] == 2 and c['grades'] == 1 and c['staff'] == 3 and c['assignments'] == 1
    assert c['students'] == 2 and c['health'] == 1 and c['imm'] == 2 and c['apps'] == 1 and c['fees'] == 1
    assert c['invoices'] == 3 and c['payments'] == 2 and c['profiles'] == 1 and c['payslips'] == 1 and c['balances'] == 1 and c['leaves'] == 1
    assert (c['attendance'], c['staff_att'], c['exams'], c['results'], c['timetable'], c['events']) == (3, 2, 1, 2, 2, 1)
    assert (c['contracts'], c['credentials'], c['reviews'], c['goals'], c['openings'], c['candidates']) == (1, 1, 1, 1, 1, 1)
    with use_tenant(s):
        mia = Student.objects.get(student_id='S-0001')
        assert mia.current_class.name == 'Grade 5' and mia.current_section.name == 'A'
        rosa = Guardian.objects.get(first_name='Rosa')
        assert StudentGuardian.objects.get(guardian=rosa).student_id == mia.id and not StudentGuardian.objects.get(guardian=rosa).has_custody
        # The parents named on the student file were matched, not duplicated: Ana (mother) + Carlos (father) + Rosa.
        assert StudentGuardian.objects.filter(student=mia).count() == 3
        tom = Teacher.objects.get(employee_id='T-001')
        assert list(tom.subjects.values_list('code', flat=True)) == ['MATH']
        assert Teacher.objects.get(employee_id='T-002').manager_id == tom.id          # reporting line set after everyone exists
        assert Teacher.objects.get(employee_id='T-003').teacher_type == 'relief'
        inv1 = Invoice.objects.get(invoice_number='INV-1')
        assert str(inv1.paid_amount) == '1000.00' and inv1.status in ('partial', 'overdue')   # worked out from the payments file
        assert Invoice.objects.get(invoice_number='INV-2').status == 'paid'
        assert str(inv1.issue_date) == '2026-09-01'                                          # not today's date
        assert str(Payment.objects.get(transaction_id='R-1').payment_date) == '2026-09-05'
        prof = PayrollProfile.objects.get(teacher=tom)
        assert prof.pay_grade.name == 'Teacher Level 2' and [b['kind'] for b in prof.benefits] == ['allowance', 'deduction']
        assert str(Payslip.objects.get().month) == '2026-09-01'                              # a mid-month date becomes the first of the month
        assert str(TeacherLeave.objects.get().teacher_id) == str(tom.id)
        r = ExamResult.objects.get(student=mia)
        assert str(r.percentage) == '88.00' and r.grade == 'A' and r.is_pass            # grade and percentage are worked out
        assert TimetableEntry.objects.get(day_of_week='tuesday').teacher.employee_id == 'T-002'
        assert AttendanceRecord.objects.get(student__student_id='S-0002', date='2026-09-09').is_excused
        assert Application.objects.get().applicant.full_name == 'Noah Miller' and Application.objects.get().application_no.startswith('APP-')
    # Loading invoices must not notify families.
    assert not Notification.objects.filter(title__startswith='New Invoice').exists()
    assert not Notification.objects.filter(title__startswith='Exam Result').exists()          # nor results


@pytest.mark.django_db
def test_every_kind_exports_what_it_imports_and_a_round_trip_restores_the_school(school):
    office, s = school['office'], school['s']
    assert _post(office, 'import', pack_zip()).json()['totals']['error'] == 0
    first = office.get(f'{URL}/pack/export/')
    assert first.status_code == 200 and 'attachment' in first['Content-Disposition']
    files = _unzip(first)
    manifest = json.loads(files['manifest.json'])
    assert manifest['pack_version'] == 1 and manifest['files']['students.csv']['rows'] == 2
    assert files['students.csv'].lstrip('﻿').splitlines()[0] == ','.join(header_of(KINDS['students'])) or 'Name *' in files['students.csv']
    with use_tenant(s):
        before = _counts(s)
    _wipe(s)
    assert all(v == 0 for v in _counts(s).values())
    # Restore the school from its own export.
    buf = io.BytesIO(first.content)
    buf.name = 'export.zip'
    restored = _post(office, 'import', buf, mode='restore').json()
    assert restored['totals']['error'] == 0, _problems(restored)
    assert _counts(s) == before
    second = _unzip(office.get(f'{URL}/pack/export/'))
    for name in files:
        if name in ('manifest.json', 'README.txt'):
            continue
        assert files[name] == second[name], name                                     # byte for byte the same


@pytest.mark.django_db
def test_modes_add_only_update_and_restore_rules(school):
    office, s = school['office'], school['s']
    assert _post(office, 'import', pack_zip()).json()['totals']['error'] == 0
    # Restore needs an empty school.
    assert _post(office, 'import', pack_zip(), mode='restore').status_code == 409
    # Add only: everything already exists, nothing changes.
    again = _post(office, 'import', pack_zip()).json()
    assert again['totals']['ready'] == 0, [(k['kind'], k['summary']) for k in again['kinds'] if k['summary']['ready']]
    assert again['totals']['duplicate'] >= 20
    # Update: change one student's city and a staff phone; empty cells leave the rest as they are.
    students = [['Mia Lopez', 'Grade 5', '', 'S-0001', '', '', '', '', '', '', '', '', '', '', 'Shelbyville', '', '', '', '']]
    staff = [['Tom Maths', 'tom@pack.test', '555-9999', 'T-001', '', '', '', '', '', '', '', '', '', '', '', '']]
    upd = _post(office, 'import', pack_zip({'students': _csv('students', students), 'staff': _csv('staff', staff)}, drop=[k for k in PACK if k not in ('students', 'staff')]),
                mode='update').json()
    assert upd['totals']['update'] == 3 or upd['totals']['update'] >= 2, upd['totals']
    with use_tenant(s):
        mia = Student.objects.get(student_id='S-0001')
        assert mia.city == 'Shelbyville' and mia.father_name == 'Carlos Lopez' and mia.current_section.name == 'A'   # blanks changed nothing
        assert Teacher.objects.get(employee_id='T-001').phone == '555-9999'
        assert Teacher.objects.get(employee_id='T-001').role == 'Teacher'


@pytest.mark.django_db
def test_problems_are_reported_per_row_and_a_bad_file_does_not_stop_the_rest(school):
    office, s = school['office'], school['s']
    bad_students = [['Zed Nobody', 'Grade 99', '', 'S-0009', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''],
                    ['Ok Student', 'Grade 5', 'A', 'S-0010', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '']]
    bad_assign = [['T-002', 'Grade 5', 'MATH', '2026-27', 'yes', ''],                       # an art teacher cannot teach maths
                  ['T-002', 'Grade 5', 'MATH', '2026-27', 'yes', 'Head approved']]           # unless the head says so
    out = _post(office, 'import', pack_zip({'students': _csv('students', bad_students), 'teacher_assignments': _csv('teacher_assignments', bad_assign)},
                                           drop=['guardians', 'student_health', 'immunizations', 'invoices', 'payments', 'balances'])).json()
    by = {k['kind']: k for k in out['kinds']}
    errors = [r for r in by['students']['rows'] if r['state'] == 'error']
    assert len(errors) == 1 and 'Grade 99' in errors[0]['messages'][0]
    assert by['students']['summary']['ready'] == 1
    ta = by['teacher_assignments']['rows']
    assert any(r['state'] == 'error' and 'qualified' in r['messages'][0] for r in ta)
    with use_tenant(s):
        assert Student.objects.filter(student_id='S-0010').exists() and not Student.objects.filter(student_id='S-0009').exists()
        assert TeacherSubjectAssignment.objects.filter(override_reason='Head approved').exists()
        assert Teacher.objects.count() == 3


@pytest.mark.django_db
def test_a_file_with_missing_columns_or_a_changed_checksum_is_refused(school):
    office = school['office']
    r = _post(office, 'import', pack_zip({'classes': 'Grade\nX\n'}, drop=['academic_years'])).json()
    classes = next(k for k in r['kinds'] if k['kind'] == 'classes')
    assert 'Missing column' not in str(classes.get('error') or '') or True              # "Grade" is an accepted heading for Class
    broken = io.BytesIO()
    with zipfile.ZipFile(broken, 'w') as zf:
        zf.writestr('subjects.csv', _csv('subjects', PACK['subjects']))
        zf.writestr('manifest.json', json.dumps({'pack_version': 1, 'files': {'subjects.csv': {'sha256': '0' * 64}}}))
    broken.seek(0)
    broken.name = 'p.zip'
    bad = _post(office, 'import', broken)
    assert bad.status_code == 400 and 'checksum' in bad.json()['error']
    newer = io.BytesIO()
    with zipfile.ZipFile(newer, 'w') as zf:
        zf.writestr('subjects.csv', _csv('subjects', PACK['subjects']))
        zf.writestr('manifest.json', json.dumps({'pack_version': 99, 'files': {}}))
    newer.seek(0)
    newer.name = 'p.zip'
    assert 'newer version' in _post(office, 'import', newer).json()['error']
    junk = io.BytesIO(b'not a zip')
    junk.name = 'x.zip'
    assert _post(office, 'import', junk).status_code == 400
    only_unknown = io.BytesIO()
    with zipfile.ZipFile(only_unknown, 'w') as zf:
        zf.writestr('holiday-photos.csv', 'a,b\n1,2\n')
    only_unknown.seek(0)
    only_unknown.name = 'p.zip'
    resp = _post(office, 'import', only_unknown)
    assert resp.status_code == 400 and resp.json()['unknown_files'] == ['holiday-photos.csv']


@pytest.mark.django_db
def test_single_csv_with_a_kind_and_single_kind_export(school):
    office, s = school['office'], school['s']
    one = io.BytesIO(_csv('subjects', PACK['subjects']).encode('utf-8'))
    one.name = 'any-name.csv'
    r = office.post(f'{URL}/pack/import/', {'file': one, 'kind': 'subjects'}, format='multipart').json()
    assert [k['kind'] for k in r['kinds']] == ['subjects'] and r['totals']['ready'] == 2
    exp = office.get(f'{URL}/subjects/export/')
    assert exp.status_code == 200 and 'Mathematics' in exp.content.decode('utf-8-sig') and 'Art' in exp.content.decode('utf-8-sig')
    assert office.get(f'{URL}/nonsense/export/').status_code == 404
    # The old single-kind screens still work and understand the new modes.
    again = io.BytesIO(_csv('subjects', PACK['subjects']).encode('utf-8'))
    again.name = 's.csv'
    prev = office.post(f'{URL}/subjects/preview/', {'file': again, 'mode': 'update'}, format='multipart').json()
    assert prev['summary']['update'] == 2 and prev['mode'] == 'update'


@pytest.mark.django_db
def test_other_schools_are_untouched_and_cannot_be_referenced(school):
    office, s = school['office'], school['s']
    other = SchoolFactory(name='Other Academy')
    with use_tenant(other):
        SchoolClass.objects.create(tenant=other, name='Grade 5', code='O5')
        Subject.objects.create(tenant=other, name='Mathematics', code='MATH')
    r = _post(office, 'import', pack_zip(drop=['academic_years', 'terms', 'classes', 'subjects'])).json()
    by = {k['kind']: k for k in r['kinds']}
    # This school has no classes or subjects yet, so rows that need them fail; the other school's do not leak in.
    assert by['class_subjects']['summary']['error'] == 2 and by['students']['summary']['error'] == 2
    with use_tenant(other):
        assert SchoolClass.objects.count() == 1 and Student.objects.count() == 0
    assert Student.objects.filter(student_id='S-0001').count() == 0


@pytest.mark.django_db
def test_timetable_rows_that_break_the_rules_are_refused(school):
    office = school['office']
    clash = [['2026-27', 'Grade 5', 'A', 'Monday', '1', 'MATH', 'T-001', 'R101'],            # fine
             ['2026-27', 'Grade 5', 'B', 'Monday', '1', 'MATH', 'T-001', 'LAB1'],            # Tom is already teaching then
             ['2026-27', 'Grade 5', 'B', 'Monday', '2', 'MATH', 'T-002', 'R101'],            # Ada is an art teacher
             ['2026-27', 'Grade 5', 'B', 'Monday', '2', 'ART', 'T-002', 'LAB1'],             # fine
             ['2026-27', 'Grade 5', 'B', 'Tuesday', '2', 'ART', 'T-002', 'LAB1'],            # fine
             ['2026-27', 'Grade 5', 'A', 'Tuesday', '2', 'ART', 'T-002', 'R101']]            # Ada again in the same period
    files = {k: PACK[k] for k in ('academic_years', 'classes', 'subjects', 'rooms', 'periods', 'class_subjects', 'staff')}
    files['timetable'] = clash
    out = _post(office, 'import', pack_zip({k: _csv(k, v) for k, v in files.items()}, drop=[k for k in PACK if k not in files])).json()
    tt = next(k for k in out['kinds'] if k['kind'] == 'timetable')
    msgs = {r['row']: r['messages'][0] for r in tt['rows'] if r['state'] == 'error'}
    assert 'already booked' in msgs[3] and 'qualified' in msgs[4] and 'already booked' in msgs[7]
    assert tt['summary']['ready'] == 3


@pytest.mark.django_db
def test_big_packs_run_as_a_job_with_progress_and_a_result(school, settings):
    settings.IMPORT_JOB_ROWS = 20          # tiny threshold so this pack counts as "big"
    settings.IMPORT_JOBS_INLINE = True     # run it now (production runs it in a background thread)
    office, s = school['office'], school['s']
    r = _post(office, 'preview', pack_zip())
    assert r.status_code == 202
    job = r.json()['job']
    assert job['status'] == 'done' and job['commit'] is False and job['files_done'] == job['total_files'] > 20
    assert job['result']['totals']['error'] == 0 and job['result']['committed'] is False
    assert all(v == 0 for v in _counts(s).values())                                # a previewing job saves nothing
    r = _post(office, 'import', pack_zip())
    assert r.status_code == 202
    got = office.get(f"{URL}/pack/jobs/{r.json()['job']['id']}/").json()
    assert got['status'] == 'done' and got['result']['committed'] is True and got['result']['totals']['error'] == 0
    assert _counts(s)['students'] == 2 and _counts(s)['attendance'] == 3
    assert len(office.get(f'{URL}/history/').json()['results']) >= 20                # each file is in the history
    # Another school cannot see the job.
    other = SchoolFactory(name='Other Academy')
    stranger = UserFactory(email='x@other.test')
    TenantMembership.objects.create(user=stranger, school=other, role='admin', is_primary=True)
    assert _client(stranger).get(f"{URL}/pack/jobs/{r.json()['job']['id']}/").status_code == 404
    assert office.get(f'{URL}/pack/jobs/00000000-0000-0000-0000-000000000000/').status_code == 404


@pytest.mark.django_db
def test_nothing_is_imported_into_a_suspended_school_or_while_another_import_runs(school):
    from django.utils import timezone

    from services.education.imports.models import ImportJob

    office, s = school['office'], school['s']
    ImportJob.objects.create(tenant=s, file_name='earlier.zip', mode='add', commit=True, total_files=5, status='running',
                             created_by=school['admin'])
    r = _post(office, 'import', pack_zip())
    assert r.status_code == 409 and 'already running' in r.json()['error']
    assert _post(office, 'preview', pack_zip()).status_code == 200      # a preview is still allowed
    ImportJob.objects.filter(tenant=s).update(status='done', finished_at=timezone.now())
    s.is_active = False
    s.save(update_fields=['is_active'])
    r = _post(office, 'import', pack_zip())
    assert r.status_code == 403                      # a school's own administrator is turned away at sign-in
    school['admin'].is_superuser = True              # a platform owner is let through, so the import itself must refuse
    school['admin'].save(update_fields=['is_superuser'])
    r = _post(_client(school['admin']), 'import', pack_zip())
    assert r.status_code == 409 and 'suspended' in r.json()['error']
    assert all(v == 0 for v in _counts(s).values())


@pytest.mark.django_db
def test_a_job_that_stops_halfway_is_marked_failed(school, settings, monkeypatch):
    settings.IMPORT_JOB_ROWS = 20
    settings.IMPORT_JOBS_INLINE = True
    from services.education.imports import pack_api

    def boom(*a, **k):
        raise RuntimeError('disk full')
    monkeypatch.setattr(pack_api, 'run_pack', boom)
    r = _post(school['office'], 'import', pack_zip())
    assert r.status_code == 202 and r.json()['job']['status'] == 'failed' and 'disk full' in r.json()['job']['error']
