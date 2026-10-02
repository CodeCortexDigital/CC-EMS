"""Pack kinds for what happens during the year: attendance, exams and results, the timetable, calendar events and the HR records."""
from __future__ import annotations

from django.apps import apps

from .pack import col, lookup, model_kind, ref_name, register

ATTENDANCE_STATUS = {'present': 'Present', 'absent': 'Absent', 'late': 'Late', 'excused': 'Excused', 'holiday': 'Holiday',
                     'early_dismissal': 'Early dismissal'}
ATTENDANCE_REASON = {'illness': 'Illness', 'medical': 'Medical appointment', 'family': 'Family', 'religious': 'Religious',
                     'school_activity': 'School activity', 'transport': 'Transport', 'unknown': 'Unknown', 'other': 'Other'}
EXAM_TYPES = {'midterm': 'Midterm', 'final': 'Final', 'quiz': 'Quiz', 'test': 'Test', 'assignment': 'Assignment'}
DAYS = {'monday': 'Monday', 'tuesday': 'Tuesday', 'wednesday': 'Wednesday', 'thursday': 'Thursday', 'friday': 'Friday',
        'saturday': 'Saturday', 'sunday': 'Sunday'}
EVENT_KINDS = {'event': 'Event', 'holiday': 'Holiday / no school', 'meeting': 'Meeting', 'deadline': 'Deadline', 'exam': 'Exam period',
               'trip': 'Trip', 'sports': 'Sports', 'other': 'Other'}
AUDIENCES = {'everyone': 'Everyone', 'staff': 'Staff only', 'families': 'Families and students'}
CONTRACT_KINDS = {'full_time': 'Full time', 'part_time': 'Part time', 'fixed_term': 'Fixed term', 'temporary': 'Temporary', 'contractor': 'Contractor'}
REVIEW_KINDS = {'annual': 'Annual review', 'mid_year': 'Mid-year review', 'probation': 'Probation review', 'observation': 'Classroom observation'}
REVIEW_STATUS = {'draft': 'Draft', 'shared': 'Shared', 'acknowledged': 'Acknowledged'}
GOAL_STATUS = {'open': 'In progress', 'done': 'Achieved', 'dropped': 'Dropped'}
OPENING_STATUS = {'draft': 'Draft', 'open': 'Open', 'closed': 'Closed'}
STAGES = {'applied': 'Applied', 'screening': 'Screening', 'interview': 'Interview', 'offer': 'Offer', 'hired': 'Hired', 'rejected': 'Not taken forward'}


@lookup('exam')
def _exam(ctx):
    from .pack import _by
    return _by('education_exams.Exam', 'exam_code')


@ref_name('exam')
def _exam_name(o):
    return o.exam_code


@lookup('opening')
def _opening(ctx):
    from .pack import _by
    return _by('education_hr.JobOpening', 'title')


@ref_name('opening')
def _opening_name(o):
    return o.title


# ---- exams ---------------------------------------------------------------------------------------------------------

def _exam_validate(clean, ctx):
    errs = []
    if clean.get('total_marks') is not None and clean.get('passing_marks') is not None and clean['passing_marks'] > clean['total_marks']:
        errs.append('Passing marks are more than the total marks')
    clean['section'] = None
    if clean.get('_section_name') and clean.get('class_ref') is not None:
        sec = apps.get_model('education_academics', 'Section').objects.filter(class_ref=clean['class_ref'], name__iexact=clean['_section_name']).first()
        if sec is None:
            errs.append(f'Section "{clean["_section_name"]}" does not exist in {clean["class_ref"].name}')
        clean['section'] = sec
    if not clean.get('exam_code') and not errs:
        Exam = apps.get_model('education_exams', 'Exam')
        found = Exam.objects.filter(title__iexact=clean['title'], class_ref=clean['class_ref'], subject=clean['subject'], exam_date=clean['exam_date']).first()
        if found is not None:
            clean['exam_code'] = found.exam_code      # the same exam again: matched, not added twice
    return errs


def _result_validate(clean, ctx):
    exam, marks = clean.get('exam'), clean.get('obtained_marks')
    if exam is not None and marks is not None:
        if marks < 0 or marks > exam.total_marks:
            return [f'Marks must be between 0 and {exam.total_marks}']
    return []


# ---- timetable -----------------------------------------------------------------------------------------------------

def _timetable_validate(clean, ctx):
    from services.education.academics.eligibility import get_policy, is_qualified, why_not
    A = lambda n: apps.get_model('education_academics', n)  # noqa: E731
    year, cls, subj, teacher, room = clean.get('academic_year'), clean.get('_class'), clean.get('_subject'), clean.get('teacher'), clean.get('classroom')
    if None in (year, cls, subj, teacher, room):
        return []
    period = A('Period').objects.filter(academic_year=year, period_number=clean['_period_number']).first()
    if period is None:
        return [f'Period {clean["_period_number"]} does not exist in {year.name} (import periods first)']
    cs = A('ClassSubject').objects.filter(class_ref=cls, subject=subj).first()
    if cs is None:
        return [f'{cls.name} does not have {subj.name} as a subject (import class subjects first)']
    section = None
    if clean.get('_section_name'):
        section = A('Section').objects.filter(class_ref=cls, name__iexact=clean['_section_name']).first()
        if section is None:
            return [f'Section "{clean["_section_name"]}" does not exist in {cls.name}']
    clean.update(period=period, class_subject=cs, section=section)
    errs = []
    if get_policy(ctx['school']).enforce_subject_match and not is_qualified(teacher, subj) and not A('TeacherSubjectAssignment').objects.filter(
            teacher=teacher, class_subject=cs, is_active=True).exists():
        errs.append(why_not(teacher, subj))
    busy = ctx.setdefault('busy', {'t': {}, 'r': {}, 'c': {}})
    if 'seeded' not in busy:
        for e in A('TimetableEntry').objects.select_related('class_subject__class_ref'):
            busy['t'][(e.teacher_id, e.academic_year_id, e.day_of_week, e.period_id)] = e.class_subject.class_ref.name
            busy['r'][(e.classroom_id, e.academic_year_id, e.day_of_week, e.period_id)] = e.class_subject.class_ref.name
        busy['seeded'] = True
    day, slot = clean['day_of_week'], (year.pk, clean['day_of_week'], period.pk)
    for kind, who, label in (('t', teacher, 'teacher'), ('r', room, 'room')):
        k = (who.pk, *slot)
        if k in busy[kind]:
            errs.append(f'{who.full_name if label == "teacher" else who.name} is already booked in that period ({busy[kind][k]})')
        elif not errs:
            busy[kind][k] = cls.name
    return errs


@lookup('bcategory')
def _bcategory(ctx):
    from .pack import _by
    return _by('behaviour.BehaviourCategory', 'name')


@ref_name('bcategory')
def _bcategory_name(o):
    return o.name


def _incident_before(data, ctx):
    cat = data['category']
    data['kind'] = cat.kind
    if data.get('points') is None:
        data['points'] = cat.points
    if not data.get('severity'):
        data['severity'] = cat.severity
    return data


def _incident_after(obj, clean, ctx):
    if clean.get('_action'):
        apps.get_model('behaviour', 'BehaviourAction').objects.create(
            tenant=ctx['school'], incident=obj, action_type=clean['_action'], notes=clean.get('_action_notes') or '', completed=True)


def _first_action(o):
    a = o.behaviouraction_set.order_by('created_at').first() if hasattr(o, 'behaviouraction_set') else None
    return a.action_type if a else ''


def _first_action_notes(o):
    a = o.behaviouraction_set.order_by('created_at').first() if hasattr(o, 'behaviouraction_set') else None
    return a.notes if a else ''


def _ratings_text(o):
    return '; '.join(f'{k}:{v}' for k, v in (o.ratings or {}).items())


def _rating_validate(clean, ctx):
    student = clean.get('student')
    if student is None:
        return []
    if student.current_class_id is None:
        return [f'{student.full_name} is not in a class yet']
    clean['class_ref'] = student.current_class
    out, errs = {}, []
    for part in [p for p in (clean.get('_ratings') or '').split(';') if p.strip()]:
        name, _, value = part.rpartition(':')
        try:
            out[name.strip()] = float(value) if '.' in value else int(value)
        except ValueError:
            errs.append(f'Rating "{part.strip()}" should look like Respect:4')
    clean['ratings'] = out
    return errs


def _entry_period(o):
    return o.period.period_number


def install():
    # ---- attendance -----------------------------------------------------------------------------
    register('attendance', model_kind(
        label='Student attendance', order=30, model='education_attendance.AttendanceRecord', filename='attendance.csv', depends=['students'], tier=2,
        singular='attendance record', silent=True,
        help='One row per student per day. Loading history does not send absence alerts to families.',
        cols=[col('student', 'Student number', 'ref', True, ref='student', aliases=['studentid', 'studentno']), col('date', 'Date', 'date', True),
              col('status', 'Status', 'choice', True, choices=ATTENDANCE_STATUS), col('reason', 'Reason', 'choice', choices=ATTENDANCE_REASON),
              col('excused', 'Excused (yes/no)', 'bool', field='is_excused', default=False), col('minutes_late', 'Minutes late', 'int'), col('remarks', 'Remarks')],
        key=['student', 'date'], order_by=('date', 'student__student_id'),
        queryset=lambda ctx: apps.get_model('education_attendance', 'AttendanceRecord').objects.select_related('student'),
        example=[['S-0001', '2026-09-08', 'present', '', 'no', '', ''], ['S-0002', '2026-09-08', 'late', 'transport', 'no', '10', 'Bus delayed']]))

    register('staff_attendance', model_kind(
        label='Staff attendance', order=31, model='education_academics.TeacherAttendance', filename='staff_attendance.csv', depends=['staff'], tier=2,
        singular='attendance record', help='One row per staff member per day.',
        cols=[col('employee', 'Employee number', 'ref', True, field='teacher', ref='teacher', aliases=['employeeid']), col('date', 'Date', 'date', True),
              col('status', 'Status', 'choice', True, choices={'present': 'Present', 'on_leave': 'On leave', 'absent': 'Absent'}), col('reason', 'Reason')],
        key=['employee', 'date'], order_by=('date', 'teacher__employee_id'),
        queryset=lambda ctx: apps.get_model('education_academics', 'TeacherAttendance').objects.select_related('teacher'),
        example=[['T-001', '2026-09-08', 'present', '']]))

    # ---- exams ---------------------------------------------------------------------------------
    register('exams', model_kind(
        label='Exams and tests', order=32, model='education_exams.Exam', filename='exams.csv', depends=['classes', 'subjects'], tier=2, singular='exam',
        help='Exams, tests and quizzes. Leave the exam code empty for new ones; a code is made. Results go in exam_results.csv, using the exam code.',
        cols=[col('exam_code', 'Exam code', aliases=['code']), col('title', 'Title', required=True),
              col('exam_type', 'Type', 'choice', True, choices=EXAM_TYPES, aliases=['type']),
              col('class', 'Class', 'ref', True, field='class_ref', ref='class', aliases=['classname', 'grade']),
              col('section', 'Section', field='_section_name', export=lambda o: o.section.name if o.section_id else ''),
              col('subject', 'Subject code', 'ref', True, ref='subject', aliases=['subjectcode']),
              col('total_marks', 'Total marks', 'int', True), col('passing_marks', 'Passing marks', 'int', True),
              col('exam_date', 'Exam date', 'date', True, aliases=['date']), col('start_time', 'Start time', 'time'), col('end_time', 'End time', 'time'),
              col('duration_minutes', 'Minutes', 'int'), col('academic_year', 'School year', aliases=['year']),
              col('term', 'Term', 'choice', choices={'first': 'First', 'second': 'Second'}),
              col('is_published', 'Published (yes/no)', 'bool', default=False), col('is_active', 'Active (yes/no)', 'bool', default=True)],
        key=['exam_code'], validate=_exam_validate, order_by=('exam_code',),
        queryset=lambda ctx: apps.get_model('education_exams', 'Exam').objects.select_related('class_ref', 'section', 'subject'),
        example=[['', 'Unit 1 test', 'test', 'Grade 5', '', 'MATH', '50', '25', '2026-09-30', '', '', '', '2026-27', 'first', 'yes', 'yes']]))

    register('exam_results', model_kind(
        label='Exam results', order=33, model='education_exams.ExamResult', filename='exam_results.csv', depends=['exams', 'students'], tier=2,
        singular='result', silent=True, validate=_result_validate,
        help='Marks per student per exam. The grade and percentage are worked out. Families are not notified when results are loaded this way.',
        cols=[col('exam', 'Exam code', 'ref', True, ref='exam', aliases=['examcode', 'code']),
              col('student', 'Student number', 'ref', True, ref='student', aliases=['studentid', 'studentno']),
              col('obtained_marks', 'Marks', 'decimal', True, aliases=['obtained', 'score']), col('remarks', 'Remarks')],
        key=['exam', 'student'], order_by=('exam__exam_code', 'student__student_id'),
        queryset=lambda ctx: apps.get_model('education_exams', 'ExamResult').objects.select_related('exam', 'student'),
        example=[['EXM-2026-0001', 'S-0001', '44', '']]))

    # ---- timetable -----------------------------------------------------------------------------
    register('timetable', model_kind(
        label='Timetable', order=34, model='education_academics.TimetableEntry', filename='timetable.csv', depends=['class_subjects', 'periods', 'staff', 'rooms'],
        tier=2, singular='timetable slot',
        help='One row per lesson: school year, class, section, day, period, subject, teacher and room. Teachers must be qualified for the subject, '
             'and nobody (teacher, room or class) can be in two places in one period.',
        cols=[col('year', 'School year', 'ref', True, field='academic_year', ref='year', aliases=['schoolyear']),
              col('class', 'Class', 'ref', True, field='_class', ref='class', aliases=['classname', 'grade'], export=lambda o: o.class_subject.class_ref),
              col('section', 'Section', field='_section_name', export=lambda o: o.section.name if o.section_id else ''),
              col('day', 'Day', 'choice', True, field='day_of_week', choices=DAYS, aliases=['weekday']),
              col('period', 'Period number', 'int', True, field='_period_number', aliases=['periodnumber'], export=_entry_period),
              col('subject', 'Subject code', 'ref', True, field='_subject', ref='subject', aliases=['subjectcode'], export=lambda o: o.class_subject.subject),
              col('teacher', 'Employee number', 'ref', True, ref='teacher', aliases=['employee', 'employeeid']),
              col('room', 'Room code', 'ref', True, field='classroom', ref='room', aliases=['roomcode', 'classroom'])],
        key=['year', 'class', 'section', 'day', 'period'], validate=_timetable_validate,
        order_by=('academic_year__start_date', 'class_subject__class_ref__name', 'section__name', 'day_of_week', 'period__period_number'),
        queryset=lambda ctx: apps.get_model('education_academics', 'TimetableEntry').objects.select_related(
            'class_subject__class_ref', 'class_subject__subject', 'teacher', 'classroom', 'period', 'section', 'academic_year'),
        example=[['2026-27', 'Grade 5', 'A', 'Monday', '1', 'MATH', 'T-001', 'R101']]))

    # ---- calendar -------------------------------------------------------------------------------
    register('calendar_events', model_kind(
        label='School calendar', order=35, model='education_calendar.CalendarEvent', filename='calendar_events.csv', tier=2, singular='event',
        help='Holidays, closures, trips and meetings. Holidays and closures are not counted against leave and need no attendance.',
        cols=[col('title', 'Title', required=True), col('kind', 'Type', 'choice', choices=EVENT_KINDS, default='event', aliases=['type']),
              col('start_date', 'First day', 'date', True, aliases=['start']), col('end_date', 'Last day', 'date', True, aliases=['end']),
              col('location', 'Location'), col('audience', 'For', 'choice', choices=AUDIENCES, default='everyone'),
              col('closes_school', 'School closed (yes/no)', 'bool', default=False, aliases=['closed']), col('description', 'Description')],
        key=['title', 'start_date'], order_by=('start_date', 'title'),
        example=[['Fall break', 'holiday', '2026-10-12', '2026-10-12', '', 'everyone', 'yes', 'No school']]))

    # ---- HR records -----------------------------------------------------------------------------
    employee = lambda: col('employee', 'Employee number', 'ref', True, field='teacher', ref='teacher', aliases=['employeeid', 'staff'])  # noqa: E731
    register('contracts', model_kind(
        label='Staff contracts', order=40, model='education_hr.StaffContract', filename='contracts.csv', depends=['staff'], tier=2, singular='contract',
        help='Employment contracts, with the end date and probation end used for expiry alerts.',
        cols=[employee(), col('kind', 'Type', 'choice', choices=CONTRACT_KINDS, default='full_time', aliases=['type']),
              col('start_date', 'Starts', 'date', True), col('end_date', 'Ends', 'date'), col('probation_end', 'Probation ends', 'date'), col('notes', 'Notes')],
        key=['employee', 'start_date'], order_by=('teacher__employee_id', 'start_date'),
        queryset=lambda ctx: apps.get_model('education_hr', 'StaffContract').objects.select_related('teacher'),
        example=[['T-001', 'full_time', '2024-08-01', '', '2025-02-01', '']]))
    register('credentials', model_kind(
        label='Licences and certificates', order=41, model='education_hr.StaffCredential', filename='credentials.csv', depends=['staff'], tier=2,
        singular='credential', help='Teaching licences, first aid, background checks. Expiry dates drive the alerts.',
        cols=[employee(), col('name', 'Credential', required=True), col('issuer', 'Issued by'), col('number', 'Number'),
              col('issued_on', 'Issued on', 'date'), col('expires_on', 'Expires on', 'date'), col('notes', 'Notes')],
        key=['employee', 'name', 'number'], order_by=('teacher__employee_id', 'name'),
        queryset=lambda ctx: apps.get_model('education_hr', 'StaffCredential').objects.select_related('teacher'),
        example=[['T-001', 'State teaching licence', 'State Board', 'TL-4471', '2023-07-01', '2028-06-30', '']]))
    register('reviews', model_kind(
        label='Performance reviews', order=42, model='education_hr.PerformanceReview', filename='reviews.csv', depends=['staff'], tier=2, singular='review',
        validate=lambda clean, ctx: [] if clean.get('rating') in (None, 1, 2, 3, 4, 5) else ['Rating must be from 1 to 5'],
        help='Reviews and observations. Drafts stay private to HR until shared.',
        cols=[employee(), col('kind', 'Type', 'choice', choices=REVIEW_KINDS, default='annual', aliases=['type']), col('period_label', 'Period'),
              col('review_date', 'Date', 'date', True), col('rating', 'Rating (1-5)', 'int'), col('strengths', 'Strengths'),
              col('improvements', 'Areas to improve'), col('observed_class', 'Lesson observed'),
              col('status', 'Status', 'choice', choices=REVIEW_STATUS, default='draft'), col('employee_comment', 'Employee comment')],
        key=['employee', 'kind', 'period_label', 'review_date'], order_by=('review_date', 'teacher__employee_id'),
        queryset=lambda ctx: apps.get_model('education_hr', 'PerformanceReview').objects.select_related('teacher'),
        example=[['T-001', 'annual', '2025-26', '2026-06-10', '4', 'Great rapport with students', 'Use more group work', '', 'shared', '']]))
    register('goals', model_kind(
        label='Staff goals', order=43, model='education_hr.StaffGoal', filename='goals.csv', depends=['staff'], tier=2, singular='goal',
        validate=lambda clean, ctx: [] if clean.get('progress') is None or 0 <= clean['progress'] <= 100 else ['Progress must be from 0 to 100'],
        help='Professional goals and how far along they are.',
        cols=[employee(), col('title', 'Goal', required=True), col('description', 'Details'), col('due_date', 'Due', 'date'),
              col('progress', 'Progress %', 'int', default=0), col('status', 'Status', 'choice', choices=GOAL_STATUS, default='open')],
        key=['employee', 'title'], order_by=('teacher__employee_id', 'title'),
        queryset=lambda ctx: apps.get_model('education_hr', 'StaffGoal').objects.select_related('teacher'),
        example=[['T-001', 'Run a maths club', 'Weekly after school', '2027-03-01', '40', 'open']]))
    register('job_openings', model_kind(
        label='Job openings', order=44, model='education_hr.JobOpening', filename='job_openings.csv', tier=2, singular='opening',
        help='Positions the school is hiring for.',
        cols=[col('title', 'Job title', required=True), col('department', 'Department'), col('positions', 'Positions', 'int', default=1),
              col('status', 'Status', 'choice', choices=OPENING_STATUS, default='open'), col('closes_on', 'Closes on', 'date'), col('description', 'Description')],
        key=['title'], order_by=('title',), example=[['Science teacher', 'Science', '1', 'open', '2026-11-30', 'Grades 6 to 8']]))
    register('job_candidates', model_kind(
        label='Job candidates', order=45, model='education_hr.JobCandidate', filename='job_candidates.csv', depends=['job_openings'], tier=2, singular='candidate',
        help='People who applied for an opening and where they stand. Hiring is done in the Recruitment screen.',
        cols=[col('opening', 'Job title', 'ref', True, ref='opening', aliases=['job', 'position']), col('full_name', 'Name', required=True, aliases=['candidate']),
              col('email', 'Email'), col('phone', 'Phone'), col('source', 'Source'), col('stage', 'Stage', 'choice', choices=STAGES, default='applied'),
              col('rating', 'Rating (1-5)', 'int'), col('notes', 'Notes')],
        key=['opening', 'full_name', 'email'], order_by=('opening__title', 'full_name'),
        queryset=lambda ctx: apps.get_model('education_hr', 'JobCandidate').objects.select_related('opening'),
        example=[['Science teacher', 'Dana Rivers', 'dana@example.com', '555-0177', 'Website', 'interview', '4', '']]))

    # ---- behaviour ------------------------------------------------------------------------------
    SEVERITY = {'low': 'Low', 'medium': 'Medium', 'high': 'High', 'critical': 'Critical'}
    KINDS2 = {'positive': 'Positive (merit)', 'negative': 'Negative (incident)'}
    ACTIONS = {'verbal_warning': 'Verbal warning', 'written_warning': 'Written warning', 'detention': 'Detention', 'parent_meeting': 'Parent meeting',
               'counselling': 'Counselling', 'loss_of_privilege': 'Loss of privilege', 'community_service': 'Community service',
               'in_school_suspension': 'In-school suspension', 'suspension': 'Suspension', 'reward': 'Reward', 'follow_up': 'Follow-up', 'other': 'Other'}
    register('behaviour_categories', model_kind(
        label='Behaviour categories', order=50, model='behaviour.BehaviourCategory', filename='behaviour_categories.csv', tier=2, singular='category',
        help='The merits and incidents teachers can log, with their points.',
        cols=[col('name', 'Category', required=True), col('kind', 'Type', 'choice', True, choices=KINDS2, aliases=['type']), col('points', 'Points', 'int', default=0),
              col('severity', 'Severity', 'choice', choices=SEVERITY, default='low'), col('notify_family', 'Tell the family (yes/no)', 'bool', default=False),
              col('order', 'Order', 'int', default=0)],
        key=['name'], order_by=('kind', 'order', 'name'),
        example=[['Helping others', 'positive', '2', 'low', 'no', '1'], ['Physical conflict', 'negative', '-4', 'high', 'yes', '9']]))

    register('behaviour_incidents', model_kind(
        label='Behaviour log', order=51, model='behaviour.BehaviourIncident', filename='behaviour_incidents.csv', depends=['students', 'behaviour_categories'],
        tier=2, singular='behaviour entry', silent=True, before_create=_incident_before, after_create=_incident_after,
        help='One row per merit or incident for a student, with the action the school took. Families are not notified when history is loaded this way.',
        cols=[col('student', 'Student number', 'ref', True, ref='student', aliases=['studentid', 'studentno']),
              col('category', 'Category', 'ref', True, ref='bcategory'), col('date', 'Date', 'date', True), col('time', 'Time', 'time'),
              col('location', 'Where'), col('description', 'What happened', aliases=['details']), col('points', 'Points', 'int'),
              col('severity', 'Severity', 'choice', choices=SEVERITY), col('status', 'Status', 'choice', choices={'open': 'Open', 'in_review': 'In review', 'resolved': 'Resolved'}, default='open'),
              col('follow_up_date', 'Follow up on', 'date'), col('visible_to_family', 'Family can see (yes/no)', 'bool', default=True),
              col('action', 'Action taken', 'choice', choices=ACTIONS, field='_action', export=_first_action),
              col('action_notes', 'Action notes', field='_action_notes', export=_first_action_notes)],
        key=['student', 'category', 'date', 'description'], order_by=('date', 'student__student_id'),
        queryset=lambda ctx: apps.get_model('behaviour', 'BehaviourIncident').objects.select_related('student', 'category'),
        no_update=('student', 'category'),
        example=[['S-0001', 'Helping others', '2026-09-10', '10:30', 'Playground', 'Helped a new student find the library', '', '', 'resolved', '', 'yes', '', '']]))

    register('skills', model_kind(
        label='Skills to rate', order=52, model='behaviour.Skill', filename='skills.csv', tier=2, singular='skill',
        help='The skills teachers rate each term (affective: behaviour and attitude; psychomotor: physical and creative).',
        cols=[col('name', 'Skill', required=True), col('domain', 'Domain', 'choice', choices={'affective': 'Affective', 'psychomotor': 'Psychomotor'}, default='affective'),
              col('description', 'Description'), col('max_rating', 'Top rating', 'int', default=5), col('order', 'Order', 'int', default=0)],
        key=['name'], order_by=('domain', 'order', 'name'), example=[['Respect', 'affective', 'Treats others politely', '5', '1']]))

    register('behaviour_ratings', model_kind(
        label='Skill ratings', order=53, model='behaviour.BehaviourRating', filename='behaviour_ratings.csv', depends=['students', 'skills'], tier=2,
        singular='rating', validate=_rating_validate,
        help='Each student\'s ratings for a term. Ratings look like Respect:4; Teamwork:5 (the skill name, a colon, the rating).',
        cols=[col('student', 'Student number', 'ref', True, ref='student', aliases=['studentid', 'studentno']),
              col('domain', 'Domain', 'choice', choices={'affective': 'Affective', 'psychomotor': 'Psychomotor'}, default='affective'),
              col('term', 'Term', default='first'), col('month', 'Month'), col('academic_year', 'School year', default='2026-2027', aliases=['year']),
              col('ratings', 'Ratings', field='_ratings', export=_ratings_text), col('comments', 'Comments')],
        key=['student', 'domain', 'term', 'academic_year', 'month'], order_by=('student__student_id', 'domain'),
        queryset=lambda ctx: apps.get_model('behaviour', 'BehaviourRating').objects.select_related('student'),
        example=[['S-0001', 'affective', 'first', '', '2026-2027', 'Respect:4; Teamwork:5', 'A thoughtful student']]))

    register('observations', model_kind(
        label='Counselling and meeting notes', order=54, model='behaviour.Observation', filename='observations.csv', depends=['students'], tier=2,
        singular='note', help='Counselling sessions, parent meetings and incident write-ups for a student.',
        cols=[col('student', 'Student number', 'ref', True, ref='student', aliases=['studentid', 'studentno']),
              col('observation_type', 'Type', 'choice', True, choices={'incident': 'Incident', 'meeting': 'Meeting', 'counselling': 'Counselling'}, aliases=['type']),
              col('title', 'Title', required=True), col('date', 'Date', 'date', True), col('description', 'Notes'),
              col('severity', 'Severity', 'choice', choices=SEVERITY, default='low'), col('status', 'Status', default='open'),
              col('parent_notified', 'Parent told (yes/no)', 'bool', default=False), col('action_taken', 'Action taken'),
              col('follow_up_date', 'Follow up on', 'date'), col('outcome', 'Outcome')],
        key=['student', 'title', 'date'], order_by=('date', 'student__student_id'),
        queryset=lambda ctx: apps.get_model('behaviour', 'Observation').objects.select_related('student'),
        example=[['S-0001', 'counselling', 'Settling in', '2026-09-12', 'First check-in after the move', 'low', 'resolved', 'yes', 'Weekly check-ins', '', 'Settled well']]))
