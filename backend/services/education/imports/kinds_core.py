"""Gives the five original import kinds (classes, subjects, staff, students, opening balances) an exporter, an update
mode and a place in the pack, without changing how their files are read."""
from __future__ import annotations

from django.apps import apps

from .pack import cell_text
from .specs import KINDS, norm, parse_gender, text
from .specs import OPENING  # noqa: F401  (re-exported for the finance kinds)


def _given(row):
    return {k for k, v in row.items() if v is not None and text(v) != ''}


def _wrap_check(check, extra=None):
    def wrapped(row, ctx):
        clean, errors, duplicate, note = check(row, ctx)
        clean['_given'] = _given(row)
        return clean, errors, duplicate, note
    return wrapped


def _wrap_create(create):
    def wrapped(clean, ctx):
        data = {k: v for k, v in clean.items() if not k.startswith('_')}
        return create(data, ctx)
    return wrapped


def _rows(model, order=None):
    qs = apps.get_model(model).objects.all()
    return qs.order_by(*order) if order else qs


# ---- classes ---------------------------------------------------------------------------------------------------------

def _export_classes(ctx):
    Section = apps.get_model('education_academics', 'Section')
    sections = {}
    for s in Section.objects.all().order_by('name'):
        sections.setdefault(s.class_ref_id, []).append(s.name)
    out = []
    for c in _rows('education_academics.SchoolClass', ('grade_level', 'name')):
        out.append([c.name, ', '.join(sections.get(c.pk, [])), '' if c.grade_level is None else c.grade_level, c.max_students,
                    cell_text(c.tuition_fee, {'type': 'money'}), c.code])
    return out


def _update_class(clean, ctx):
    cls = clean.get('existing')
    if cls is None:
        return None
    given = clean['_given']
    if 'grade_level' in given and clean['grade_level'] is not None:
        cls.grade_level = clean['grade_level']
    if 'capacity' in given:
        cls.max_students = clean['max_students']
    if 'tuition_fee' in given:
        cls.tuition_fee = clean['tuition_fee']
    if 'code' in given:
        cls.code = clean['code']
    cls.save()
    Section = apps.get_model('education_academics', 'Section')
    for s in clean['sections']:
        Section.objects.create(tenant=ctx['school'], class_ref=cls, name=s)
    return cls


# ---- subjects --------------------------------------------------------------------------------------------------------

def _export_subjects(ctx):
    return [[s.name, s.code, s.department, 'yes' if s.is_elective else 'no'] for s in _rows('education_academics.Subject', ('name',))]


def _update_subject(clean, ctx):
    Subject = apps.get_model('education_academics', 'Subject')
    s = next((x for x in Subject.objects.all() if norm(x.name) == norm(clean['name'])), None)
    if s is None:
        return None
    if 'department' in clean['_given']:
        s.department = clean['department']
    if 'elective' in clean['_given']:
        s.is_elective = clean['is_elective']
    s.save()
    return s


# ---- staff -----------------------------------------------------------------------------------------------------------

STAFF_EXTRA = [('teacher_type', 'Staff type (regular or relief)', False, ['type', 'stafftype']),
               ('manager', 'Manager (employee number)', False, ['reportsto', 'managerid', 'supervisor'])]


def _staff_check(inner):
    def check(row, ctx):
        clean, errors, duplicate, note = inner(row, ctx)
        kind = norm(row.get('teacher_type'))
        if kind and kind not in ('regular', 'relief'):
            errors.append('Staff type should be regular or relief')
        clean['teacher_type'] = 'relief' if kind == 'relief' else 'regular'
        clean['_manager'] = text(row.get('manager'))
        clean['_subject_names'] = clean.get('specializations') or []
        clean['_given'] = _given(row)
        return clean, errors, duplicate, note
    return check


def _link_subjects(teacher, names, ctx):
    from .pack import find_ref
    found = [find_ref(ctx, 'subject', n) for n in names]
    found = [s for s in found if s is not None]
    if found:
        teacher.subjects.set(found)


def _staff_create(inner):
    def create(clean, ctx):
        data = {k: v for k, v in clean.items() if not k.startswith('_')}
        teacher = inner(data, ctx)
        _link_subjects(teacher, clean.get('_subject_names') or [], ctx)
        if clean.get('_manager'):
            ctx.setdefault('managers', []).append((teacher, clean['_manager']))
        return teacher
    return create


def _staff_update(clean, ctx):
    Teacher = apps.get_model('education_academics', 'Teacher')
    t = Teacher.objects.filter(email__iexact=clean['email']).first() or Teacher.objects.filter(employee_id=clean['employee_id']).first()
    if t is None:
        return None
    given = clean['_given']
    mapping = {'phone': 'phone', 'role': 'role', 'department': 'department', 'joining_date': 'joining_date', 'gender': 'gender',
               'date_of_birth': 'date_of_birth', 'monthly_salary': 'monthly_salary', 'national_id': 'national_id',
               'home_address': 'home_address', 'qualifications': 'qualifications', 'full_name': 'full_name',
               'teacher_type': 'teacher_type'}
    for key, field in mapping.items():
        if key in given:
            setattr(t, field, clean[key])
    if 'subjects' in given:
        t.specializations = clean['specializations']
        _link_subjects(t, clean['_subject_names'], ctx)
    t.save()
    if clean.get('_manager'):
        ctx.setdefault('managers', []).append((t, clean['_manager']))
    return t


def _staff_finish(ctx):
    """Reporting lines, once everyone in the file exists."""
    Teacher = apps.get_model('education_academics', 'Teacher')
    for teacher, manager_no in ctx.get('managers', []):
        boss = Teacher.objects.filter(employee_id=manager_no).first() or Teacher.objects.filter(email__iexact=manager_no).first()
        if boss is not None and boss.pk != teacher.pk and not _loops(boss, teacher):
            teacher.manager = boss
            teacher.save(update_fields=['manager', 'updated_at'])


def _loops(boss, teacher):
    seen, up = set(), boss
    while up is not None and up.pk not in seen:
        if up.pk == teacher.pk:
            return True
        seen.add(up.pk)
        up = up.manager
    return False


def _export_staff(ctx):
    out = []
    for t in _rows('education_academics.Teacher', ('full_name',)).select_related('manager').prefetch_related('subjects'):
        names = sorted(s.name for s in t.subjects.all()) or (t.specializations if isinstance(t.specializations, list) else [])
        out.append([t.full_name, t.email, t.phone, t.employee_id, t.role, t.department, ', '.join(names),
                    cell_text(t.joining_date, {'type': 'date'}), t.gender, cell_text(t.date_of_birth, {'type': 'date'}),
                    cell_text(t.monthly_salary, {'type': 'money'}), ', '.join(t.qualifications or []), t.national_id, t.home_address,
                    t.teacher_type, t.manager.employee_id if t.manager_id else ''])
    return out


# ---- students --------------------------------------------------------------------------------------------------------

def _student_update(clean, ctx):
    Student = apps.get_model('education_students', 'Student')
    s = Student.objects.filter(student_id=clean['student_id']).first() if clean.get('student_id') else None
    if s is None:
        s = next((x for x in Student.objects.filter(full_name__iexact=clean['full_name'], date_of_birth=clean['date_of_birth'])), None)
    if s is None:
        return None
    given = clean['_given']
    mapping = {'full_name': 'full_name', 'gender': 'gender', 'date_of_birth': 'date_of_birth', 'admission_date': 'admission_date',
               'email': 'email', 'phone': 'phone', 'father_name': 'father_name', 'mother_name': 'mother_name',
               'guardian_name': 'guardian_name', 'guardian_phone': 'guardian_phone', 'address': 'address', 'city': 'city',
               'religion': 'religion', 'blood_group': 'blood_group', 'birth_form_id': 'birth_form_id', 'previous_school': 'previous_school',
               'family': 'select_family'}
    for key, field in mapping.items():
        if key in given:
            # The family column is checked into clean['select_family'], not clean['family'].
            setattr(s, field, clean['select_family'] if key == 'family' else clean[key])
    if 'class' in given or 'section' in given:
        if clean.get('current_class') is not None:
            s.current_class = clean['current_class']
        if clean.get('current_section') is not None or 'section' in given:
            s.current_section = clean.get('current_section')
    s.save()
    return s


def _export_students(ctx):
    out = []
    for s in _rows('education_students.Student', ('current_class__name', 'full_name')).select_related('current_class', 'current_section'):
        out.append([s.full_name, s.current_class.name if s.current_class_id else '', s.current_section.name if s.current_section_id else '',
                    s.student_id, s.gender or '', cell_text(s.date_of_birth, {'type': 'date'}), cell_text(s.admission_date, {'type': 'date'}),
                    s.email, s.phone, s.father_name, s.mother_name, s.guardian_name, s.guardian_phone, s.address, s.city, s.religion,
                    s.blood_group, s.birth_form_id, s.previous_school, s.select_family])
    return out


# ---- opening balances ------------------------------------------------------------------------------------------------

def _export_balances(ctx):
    Invoice = apps.get_model('education_finance', 'Invoice')
    out = []
    for i in Invoice.objects.filter(description__startswith=OPENING).select_related('student').order_by('student__student_id'):
        detail = i.description[len(OPENING):].lstrip(': ').replace('brought forward', '').strip()
        out.append([i.student.student_id, cell_text(i.amount, {'type': 'money'}), cell_text(i.due_date, {'type': 'date'}), detail])
    return out


# ---- register -------------------------------------------------------------------------------------------------------

def install():
    classes, subjects, staff, students, balances = (KINDS[k] for k in ('classes', 'subjects', 'staff', 'students', 'balances'))
    classes.update(order=3, filename='classes.csv', depends=['academic_years'], tier=1, export=_export_classes, update=_update_class,
                   check=_wrap_check(classes['check']), create=_wrap_create(classes['create']))
    subjects.update(order=4, filename='subjects.csv', depends=[], tier=1, export=_export_subjects, update=_update_subject,
                    check=_wrap_check(subjects['check']), create=_wrap_create(subjects['create']))
    staff['columns'] = list(staff['columns']) + STAFF_EXTRA
    staff['example'] = [r + ['regular', ''] for r in staff['example']]
    staff.update(order=10, filename='staff.csv', depends=['subjects'], tier=1, export=_export_staff, update=_staff_update,
                 check=_staff_check(staff['check']), create=_staff_create(staff['create']), finish=_staff_finish)
    students.update(order=12, filename='students.csv', depends=['classes'], tier=1, export=_export_students, update=_student_update,
                    check=_wrap_check(students['check']), create=_wrap_create(students['create']))
    balances.update(order=20, filename='opening_balances.csv', depends=['students'], tier=1, export=_export_balances, update=None,
                    finish=None)
    for k in (classes, subjects, staff, students, balances):
        k.setdefault('finish', None)
        k.setdefault('update', None)
