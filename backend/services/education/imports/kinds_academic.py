"""Pack kinds for the academic set-up: years, terms, rooms, periods, weekdays, class subjects and teacher assignments."""
from __future__ import annotations

from datetime import date, timedelta

from django.apps import apps

from .pack import col, model_kind, register

TERM_KINDS = {'term': 'Term', 'semester': 'Semester', 'trimester': 'Trimester', 'quarter': 'Quarter'}


def _years_validate(clean, ctx):
    if clean['start_date'] and clean['end_date'] and clean['end_date'] < clean['start_date']:
        return ['End date is before the start date']
    return []


def _terms_validate(clean, ctx):
    errs = []
    if clean['start_date'] and clean['end_date'] and clean['end_date'] < clean['start_date']:
        errs.append('End date is before the start date')
    return errs


def _periods_validate(clean, ctx):
    s, e = clean.get('start_time'), clean.get('end_time')
    if s and e and e <= s:
        return ['End time must be after the start time']
    return []


def _periods_before(data, ctx):
    if not data.get('duration_minutes'):
        s, e = data['start_time'], data['end_time']
        data['duration_minutes'] = (e.hour * 60 + e.minute) - (s.hour * 60 + s.minute)
    if not data.get('name'):
        data['name'] = f'Period {data["period_number"]}'
    return data


def _weekday_before(data, ctx):
    data['name'] = data['day_code'].title()
    data['day_code'] = data['day_code'].lower()
    return data


def _weekday_validate(clean, ctx):
    word = (clean.get('day_code') or '').lower()[:3]
    if word not in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'):
        return ['Day should be a weekday name such as Monday']
    return []


def _assignment_validate(clean, ctx):
    from services.education.academics.eligibility import get_policy, is_qualified, why_not
    ClassSubject = apps.get_model('education_academics', 'ClassSubject')
    cls, subj, teacher = clean.get('_class'), clean.get('_subject'), clean.get('teacher')
    if cls is None or subj is None or teacher is None:
        return []
    cs = ClassSubject.objects.filter(class_ref=cls, subject=subj).first()
    if cs is None:
        return [f'{cls.name} does not have {subj.name} as a subject (import class subjects first)']
    clean['class_subject'] = cs
    if clean.get('academic_year') is None:
        year = apps.get_model('education_academics', 'AcademicYear').objects.filter(is_active=True).first()
        if year is None:
            return ['School year is missing and there is no active year to use']
        clean['academic_year'] = year
    if get_policy(ctx['school']).enforce_subject_match and not (clean.get('override_reason') or '').strip():
        if not is_qualified(teacher, subj):
            return [why_not(teacher, subj) + ' Fix their subjects in staff.csv, or give an override reason.']
    return []


def install():
    register('academic_years', model_kind(
        label='School years', order=1, model='education_academics.AcademicYear', filename='academic_years.csv', singular='school year',
        help='One row per school year, for example 2026-27. Mark the current one with Active = yes.',
        cols=[col('name', 'School year', required=True, aliases=['year']), col('start_date', 'Start date', 'date', True),
              col('end_date', 'End date', 'date', True), col('active', 'Active (yes/no)', 'bool', field='is_active', default=False,
                                                              aliases=['current', 'isactive'])],
        key=['name'], validate=_years_validate, order_by=('-start_date',),
        example=[['2026-27', '2026-08-17', '2027-06-04', 'yes']]))

    register('terms', model_kind(
        label='Terms and semesters', order=2, model='education_academics.Term', filename='terms.csv', depends=['academic_years'], singular='term',
        help='Grading periods inside a school year. The school year must already exist.',
        cols=[col('year', 'School year', 'ref', True, field='academic_year', ref='year', aliases=['schoolyear']),
              col('name', 'Term', required=True), col('kind', 'Type', 'choice', choices=TERM_KINDS, default='term', aliases=['kind']),
              col('order', 'Order', 'int', default=1), col('start_date', 'Start date', 'date', True), col('end_date', 'End date', 'date', True)],
        key=['year', 'name'], validate=_terms_validate, order_by=('academic_year__start_date', 'order'),
        example=[['2026-27', 'Semester 1', 'semester', '1', '2026-08-17', '2026-12-18']]))

    register('rooms', model_kind(
        label='Rooms', order=5, model='education_academics.Classroom', filename='rooms.csv', singular='room',
        help='Classrooms and special rooms. Category: classroom, lab, sports, hall or other (labs and gyms are used for the matching subjects).',
        cols=[col('code', 'Room code', required=True, aliases=['roomcode']), col('name', 'Room name', required=True, aliases=['room']),
              col('capacity', 'Capacity', 'int', default=30, aliases=['seats']), col('category', 'Category', default='classroom', aliases=['type']),
              col('floor', 'Floor'), col('location', 'Location', aliases=['building'])],
        key=['code'], order_by=('code',),
        example=[['R101', 'Room 101', '28', 'classroom', 'first', 'Main building'], ['LAB1', 'Science Lab', '24', 'lab', 'first', 'Main building']]))

    register('periods', model_kind(
        label='Daily periods', order=6, model='education_academics.Period', filename='periods.csv', depends=['academic_years'], singular='period',
        help='The bell schedule for a school year: one row per period, with start and end times.',
        cols=[col('year', 'School year', 'ref', True, field='academic_year', ref='year', aliases=['schoolyear']),
              col('number', 'Period number', 'int', True, field='period_number', aliases=['period']),
              col('name', 'Name'), col('start_time', 'Start time', 'time', True), col('end_time', 'End time', 'time', True),
              col('break', 'Break (yes/no)', 'bool', field='is_break', default=False, aliases=['isbreak', 'lunch'])],
        key=['year', 'number'], validate=_periods_validate, before_create=_periods_before, order_by=('academic_year__start_date', 'period_number'),
        example=[['2026-27', '1', 'Period 1', '08:00', '08:45', 'no'], ['2026-27', '4', 'Lunch', '11:30', '12:10', 'yes']]))

    register('weekdays', model_kind(
        label='School days', order=7, model='education_finance.WeekdayConfig', filename='weekdays.csv', singular='school day',
        help='Which days the school is open, and which are half days. Without this file Monday to Friday is used.',
        cols=[col('day', 'Day', required=True, field='day_code', aliases=['weekday', 'name']),
              col('active', 'Open (yes/no)', 'bool', field='is_active', default=True, aliases=['isactive']),
              col('half_day', 'Half day (yes/no)', 'bool', field='is_half_day', default=False, aliases=['half']),
              col('order', 'Order', 'int', default=0)],
        key=['day'], validate=_weekday_validate, before_create=_weekday_before, order_by=('order',),
        example=[['Monday', 'yes', 'no', '1'], ['Friday', 'yes', 'yes', '5']]))

    register('class_subjects', model_kind(
        label='Subjects taught in each class', order=8, model='education_academics.ClassSubject', filename='class_subjects.csv',
        depends=['classes', 'subjects'], singular='class subject',
        help='Which subjects each class takes, and how many periods a week. Both the class and the subject must already exist.',
        cols=[col('class', 'Class', 'ref', True, field='class_ref', ref='class', aliases=['classname', 'grade']),
              col('subject', 'Subject code', 'ref', True, ref='subject', aliases=['subjectcode', 'code']),
              col('periods_per_week', 'Periods per week', 'int', default=1, aliases=['periods', 'lessonsperweek']),
              col('marks', 'Total marks', 'int', default=100)],
        key=['class', 'subject'], order_by=('class_ref__name', 'subject__code'),
        example=[['Grade 5', 'MATH', '5', '100'], ['Grade 5', 'ART', '2', '100']]))

    def ta_cols():
        ClassSubject = None
        return [
            col('teacher', 'Employee number', 'ref', True, ref='teacher', aliases=['employee', 'employeeid', 'teacher']),
            col('class', 'Class', 'ref', True, field='_class', ref='class', aliases=['classname', 'grade'],
                export=lambda o: o.class_subject.class_ref),
            col('subject', 'Subject code', 'ref', True, field='_subject', ref='subject', aliases=['subjectcode', 'code'],
                export=lambda o: o.class_subject.subject),
            col('year', 'School year', 'ref', field='academic_year', ref='year', aliases=['schoolyear']),
            col('primary', 'Main teacher (yes/no)', 'bool', field='is_primary', default=True, aliases=['isprimary']),
            col('override_reason', 'Override reason', aliases=['reason']),
        ]

    register('teacher_assignments', model_kind(
        label='Teacher assignments', order=11, model='education_academics.TeacherSubjectAssignment', filename='teacher_assignments.csv',
        depends=['staff', 'class_subjects'], singular='assignment', cols=ta_cols(),
        help='Which teacher teaches which subject in which class. The teacher must be qualified for the subject (listed in staff.csv) '
             'unless you give an override reason.',
        key=['teacher', 'class', 'subject', 'year'], validate=_assignment_validate,
        order_by=('teacher__employee_id', 'class_subject__class_ref__name'),
        example=[['EMP-001', 'Grade 5', 'MATH', '2026-27', 'yes', '']]))
