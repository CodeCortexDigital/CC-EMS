"""Fill a cumulative record from what CC-EMS already knows, so a school does not type it twice.

Nothing here is final: the class teacher checks and corrects every value, and the principal's seal (印) is what makes a year official.
"""
from __future__ import annotations

from datetime import date

from django.db.models import Count, Q

from services.education.academics.models import AcademicYear, Teacher
from services.education.attendance.models import AttendanceRecord

from .forms import grade_in_level, level_for_class_grade
from .models import CumulativeRecord, CumulativeYear

SUSPENDED_REASONS = ('suspension', 'bereavement')   # 出席停止・忌引等


def _full_address(student) -> str:
    address, city = student.address or '', student.city or ''
    parts = (getattr(student, 'postal_code', '') or '', address, '' if city and city in address else city)
    return ' '.join(p for p in parts if p).strip()


def _school_profile(school) -> tuple[str, str]:
    cfg = (getattr(school, 'settings_json', None) or {})
    return (cfg.get('institute_name') or cfg.get('name') or getattr(school, 'name', '') or ''), cfg.get('address') or ''


def open_record(student, school, user=None) -> tuple[CumulativeRecord, bool]:
    """The student's record, made (with what the school already holds) when there is none yet."""
    existing = CumulativeRecord.objects.filter(student=student).first()
    if existing:
        return existing, False
    cls = student.current_class
    level = level_for_class_grade(cls.grade_level if cls else None)
    name, address = _school_profile(school)
    guardian = student.guardian_name or student.father_name or student.mother_name or ''
    record = CumulativeRecord.objects.create(
        student=student, level=level, student_address=_full_address(student), guardian_name=guardian, guardian_address=_full_address(student),
        previous_history=student.previous_school or '', entry_date=student.admission_date, school_name=name, school_address=address,
        updated_by=user)
    return record, True


def _teacher_for(cls, student) -> str:
    if cls is None:
        return ''
    if cls.homeroom_teacher_id:
        return cls.homeroom_teacher.full_name
    if cls.teacher_name:
        return cls.teacher_name
    return ''


def _principal_name() -> str:
    t = Teacher.objects.filter(role__iexact='Principal').order_by('full_name').first()
    return t.full_name if t else ''


def _class_label(student) -> str:
    cls, sec = student.current_class, student.current_section
    return f'{cls.name}{sec.name}' if cls and sec else (cls.name if cls else '')


def _roll_number(student) -> str:
    """The student's place in the class list (by student number), as a starting 整理番号 the teacher can change."""
    from services.education.students.models import Student
    ids = list(Student.objects.filter(current_class=student.current_class, current_section=student.current_section, is_active=True)
               .order_by('student_id').values_list('pk', flat=True))
    return str(ids.index(student.pk) + 1) if student.pk in ids else ''


def attendance_counts(student, start: date, end: date) -> dict:
    """授業日数, 出席停止・忌引等の日数 and 欠席日数 for the student over a date range, from the attendance register.

    A school day is a day on which the student's class has any attendance marked (holidays are not school days). Lateness and early
    dismissal count as present. Suspension and bereavement are kept apart from absence, as the form asks.
    """
    cls_students = type(student).objects.filter(current_class=student.current_class, current_section=student.current_section)
    days = (AttendanceRecord.objects.filter(student__in=cls_students, date__gte=start, date__lte=end)
            .exclude(status='holiday').values('date').distinct().count())
    mine = AttendanceRecord.objects.filter(student=student, date__gte=start, date__lte=end)
    suspended = mine.filter(Q(status__in=('absent', 'excused')) & Q(reason__in=SUSPENDED_REASONS)).count()
    absent = mine.filter(status__in=('absent', 'excused')).exclude(reason__in=SUSPENDED_REASONS).count()
    return {'school_days': days, 'suspended_days': suspended, 'absent_days': absent}


def fill_year(record: CumulativeRecord, grade: int, year: AcademicYear | None = None, today: date | None = None) -> CumulativeYear:
    """Make or update the year entry for ``grade`` with the class, teacher, principal and attendance the system has.

    Only values the system can work out are written; text the teacher has already typed (comments, ratings) is never touched, and a year that
    has the principal's seal is returned unchanged.
    """
    student = record.student
    entry, _ = CumulativeYear.objects.get_or_create(record=record, grade=grade)
    if entry.is_locked:
        return entry
    today = today or date.today()
    year = year or AcademicYear.objects.filter(is_active=True).first()
    if year:
        entry.academic_year, entry.year_label = year, year.name
    if student.current_class_id and grade == grade_in_level(record.level, student.current_class.grade_level):
        entry.class_name = entry.class_name or _class_label(student)
        entry.roll_number = entry.roll_number or _roll_number(student)
        entry.teacher_name = entry.teacher_name or _teacher_for(student.current_class, student)
    entry.principal_name = entry.principal_name or _principal_name()
    if year:
        counts = attendance_counts(student, year.start_date, min(year.end_date, today))
        for key, value in counts.items():
            setattr(entry, key, value)
    entry.save()
    return entry


def class_summary(school_class, section=None):
    """Student rows for the roster: who has a record and how far it has got."""
    from services.education.students.models import Student
    qs = Student.objects.filter(is_active=True)
    if school_class is not None:
        qs = qs.filter(current_class=school_class)
    if section is not None:
        qs = qs.filter(current_section=section)
    return qs.select_related('current_class', 'current_section').annotate(
        years_total=Count('cumulative_record__years', distinct=True),
        years_sealed=Count('cumulative_record__years', filter=Q(cumulative_record__years__principal_confirmed_at__isnull=False), distinct=True))
