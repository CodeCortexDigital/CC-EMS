"""The sample US school ("Maple Grove Academy", K-8) as a data pack.

``build()`` makes every file from a fixed random seed, so the same files come out each time. The timetable is made by
the real timetable generator: the base files are loaded into a scratch school (rolled back afterwards) and the
generator is run on it. The files are then what a school would upload, and what ``load_pack`` loads for the demo.
"""
from __future__ import annotations

import csv
import io
import random
from collections import defaultdict
from datetime import date, timedelta

from django.db import transaction

from . import engine
from .specs import KINDS

SCHOOL = 'Maple Grove Academy'
YEAR = '2026-27'
PREFIX = 'MG26-'
DOMAIN = 'maplegrove.example'

FIRST_M = ['Liam', 'Noah', 'Ethan', 'Mason', 'Lucas', 'Jackson', 'Aiden', 'Logan', 'Caleb', 'Ryan', 'Nathan', 'Owen', 'Wyatt', 'Dylan', 'Carter',
           'Isaac', 'Hunter', 'Connor', 'Evan', 'Jordan', 'Henry', 'Sebastian', 'Jack', 'Gabriel', 'Miles', 'Elijah', 'Julian', 'Leo', 'Theo', 'Asher']
FIRST_F = ['Emma', 'Olivia', 'Ava', 'Sophia', 'Isabella', 'Mia', 'Charlotte', 'Amelia', 'Harper', 'Ella', 'Grace', 'Chloe', 'Lily', 'Zoe', 'Hannah',
           'Layla', 'Natalie', 'Addison', 'Aubrey', 'Savannah', 'Nora', 'Maya', 'Ruby', 'Violet', 'Stella', 'Hazel', 'Ivy', 'Willow', 'Aria', 'Penelope']
LAST = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Wilson', 'Anderson', 'Taylor', 'Thomas',
        'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson', 'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker', 'Young',
        'Allen', 'King', 'Wright', 'Scott', 'Torres', 'Nguyen', 'Hill', 'Flores', 'Green', 'Adams', 'Nelson', 'Baker', 'Hall', 'Rivera', 'Campbell', 'Mitchell',
        'Carter', 'Roberts', 'Gomez', 'Phillips', 'Evans']
STREETS = ['Maple Ave', 'Oak Street', 'Pine Road', 'Cedar Lane', 'Elm Drive', 'Birch Court', 'Willow Way', 'Lakeview Blvd', 'Hillcrest Rd', 'Sunset Ave']
BLOOD = ['O+', 'O-', 'A+', 'A-', 'B+', 'AB+', '']

# (class, code, grade level, sections, monthly tuition)
CLASSES = [('Kindergarten', 'K', 0, ['A'], 1150), ('Grade 1', 'G1', 1, ['A', 'B'], 1200), ('Grade 2', 'G2', 2, ['A', 'B'], 1200),
           ('Grade 3', 'G3', 3, ['A', 'B'], 1250), ('Grade 4', 'G4', 4, ['A'], 1300), ('Grade 5', 'G5', 5, ['A'], 1350),
           ('Grade 6', 'G6', 6, ['A'], 1500), ('Grade 7', 'G7', 7, ['A'], 1550), ('Grade 8', 'G8', 8, ['A'], 1650)]
# subject name, code, department, elective, periods a week by stage (K-2, 3-5, 6-8)
SUBJECTS = [('Mathematics', 'MATH', 'Math', False, (5, 5, 5)), ('English Language Arts', 'ELA', 'English', False, (5, 5, 5)),
            ('Science', 'SCI', 'Science', False, (3, 3, 3)), ('Social Studies', 'SOC', 'Social Studies', False, (3, 3, 3)),
            ('Art', 'ART', 'Arts', False, (1, 1, 1)), ('Music', 'MUS', 'Arts', False, (1, 1, 1)),
            ('Physical Education', 'PE', 'Physical Education', False, (2, 2, 2)), ('Spanish', 'SPA', 'World Languages', False, (0, 2, 2)),
            ('Computer Science', 'CS', 'Technology', False, (0, 0, 2))]
TEACHERS_PER_SUBJECT = {'MATH': 3, 'ELA': 3, 'SCI': 2, 'SOC': 2, 'ART': 1, 'MUS': 1, 'PE': 1, 'SPA': 1, 'CS': 1}
NON_TEACHING = [('Principal', 'Administration', 'Dr.'), ('Assistant Principal', 'Administration', ''), ('Office Manager', 'Administration', ''),
                ('School Nurse', 'Health', ''), ('School Counselor', 'Student Support', ''), ('Librarian', 'Library', ''), ('Bookkeeper', 'Finance', '')]
HOLIDAYS = [('Labor Day', 'holiday', '2026-09-07', '2026-09-07'), ('Indigenous Peoples Day', 'holiday', '2026-10-12', '2026-10-12'),
            ('Teacher in-service day', 'holiday', '2026-10-30', '2026-10-30'), ('Veterans Day', 'holiday', '2026-11-11', '2026-11-11'),
            ('Thanksgiving break', 'holiday', '2026-11-25', '2026-11-27'), ('Winter break', 'holiday', '2026-12-21', '2027-01-01'),
            ('Martin Luther King Jr. Day', 'holiday', '2027-01-18', '2027-01-18'), ('Presidents Day', 'holiday', '2027-02-15', '2027-02-15'),
            ('Spring break', 'holiday', '2027-03-29', '2027-04-02'), ('Memorial Day', 'holiday', '2027-05-31', '2027-05-31')]
VACCINES = [('MMR', '1'), ('DTaP', '1'), ('Polio', '1')]


def R(file_kind, /, **values):
    """A row for this kind, in its column order, from column keys."""
    out = []
    for key, *_ in KINDS[file_kind]['columns']:
        v = values.get(key, '')
        out.append('' if v is None else ('yes' if v is True else 'no' if v is False else v))
    return out


def stage(grade):
    return 0 if grade <= 2 else 1 if grade <= 5 else 2


def phone(rng):
    return f'555-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}'


def school_days(start, end, closed):
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in closed:
            yield d
        d += timedelta(days=1)


def closed_dates():
    out = set()
    for _n, _k, a, b in HOLIDAYS:
        d, e = date.fromisoformat(a), date.fromisoformat(b)
        while d <= e:
            out.add(d)
            d += timedelta(days=1)
    return out


def build(seed=2026):
    """{kind: rows} for the whole pack. Needs a migrated database (a scratch school is made and rolled back)."""
    rng = random.Random(seed)
    files = defaultdict(list)

    # -- academic set-up ---------------------------------------------------------------------------------------
    files['academic_years'].append(R('academic_years', name=YEAR, start_date='2026-08-17', end_date='2027-06-04', active=True))
    files['terms'] += [R('terms', year=YEAR, name='Semester 1', kind='semester', order=1, start_date='2026-08-17', end_date='2027-01-22'),
                       R('terms', year=YEAR, name='Semester 2', kind='semester', order=2, start_date='2027-01-25', end_date='2027-06-04')]
    for name, code, grade, sections, fee in CLASSES:
        files['classes'].append(R('classes', name=name, sections=', '.join(sections), grade_level=grade, capacity=22, tuition_fee=fee, code=code))
    for name, code, dept, elective, _p in SUBJECTS:
        files['subjects'].append(R('subjects', name=name, code=code, department=dept, elective=elective))
    for i in range(1, 13):
        files['rooms'].append(R('rooms', code=f'R{100 + i}', name=f'Room {100 + i}', capacity=24, category='classroom', floor='first' if i <= 6 else 'second',
                                location='Main building'))
    files['rooms'] += [R('rooms', code='GYM', name='Gymnasium', capacity=60, category='sports', floor='ground', location='Sports hall'),
                       R('rooms', code='LAB1', name='Computer Lab', capacity=26, category='lab', floor='second', location='Main building'),
                       R('rooms', code='ART', name='Art Room', capacity=24, category='classroom', floor='ground', location='Main building')]
    bell = [('08:15', '08:55'), ('09:00', '09:40'), ('09:45', '10:25'), ('10:40', '11:20'), ('11:25', '12:05'), ('12:50', '13:30'), ('13:35', '14:15'),
            ('14:20', '15:00')]
    num = 0
    for i, (a, b) in enumerate(bell, 1):
        if i == 6:                      # lunch sits between the fifth and sixth lesson of the day
            num += 1
            files['periods'].append(R('periods', year=YEAR, number=num, name='Lunch', start_time='12:05', end_time='12:50', **{'break': True}))
        num += 1
        files['periods'].append(R('periods', year=YEAR, number=num, name=f'Period {i}', start_time=a, end_time=b, **{'break': False}))
    for i, day in enumerate(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'], 1):
        files['weekdays'].append(R('weekdays', day=day, active=True, half_day=False, order=i))
    sec_count = {code: len(sections) for _n, code, _g, sections, _f in CLASSES}
    for name, code, grade, _s, _f in CLASSES:
        for sname, scode, _d, _e, ppw in SUBJECTS:
            p = ppw[stage(grade)]
            if p:
                files['class_subjects'].append(R('class_subjects', **{'class': name, 'subject': scode, 'periods_per_week': p, 'marks': 100}))

    # -- staff ---------------------------------------------------------------------------------------------------
    pay = [('Teacher Level 1', 3800, 'Under five years'), ('Teacher Level 2', 4300, 'Five years or more'), ('Lead Teacher', 5000, 'Department lead'),
           ('Administration', 4600, 'Office and support staff'), ('Leadership', 7200, 'Principal and assistant principal')]
    for nme, amount, note in pay:
        files['pay_grades'].append(R('pay_grades', name=nme, base_salary=amount, notes=note))
    used = set()

    def person(female=None):
        while True:
            f = rng.random() < 0.5 if female is None else female
            first = rng.choice(FIRST_F if f else FIRST_M)
            last = rng.choice(LAST)
            if (first, last) not in used:
                used.add((first, last))
                return first, last, 'female' if f else 'male'

    staff = []   # dicts
    eid = 0

    def add_staff(role, dept, subject_name, kind='regular', grade=None, title=''):
        nonlocal eid
        eid += 1
        first, last, gender = person()
        joined = date(2026, 8, 3) - timedelta(days=rng.randint(30, 3200))
        staff.append(dict(id=f'E-{eid:03d}', first=first, last=last, gender=gender, role=role, dept=dept, subject=subject_name, kind=kind,
                          joined=joined, grade=grade or ('Teacher Level 2' if kind == 'regular' else 'Teacher Level 1'), title=title))
        return staff[-1]

    principal = add_staff('Principal', 'Administration', '', grade='Leadership', title='Dr.')
    assistant = add_staff('Assistant Principal', 'Administration', '', grade='Leadership')
    for role, dept, title in NON_TEACHING[2:]:
        add_staff(role, dept, '', grade='Administration', title=title)
    by_subject = defaultdict(list)
    for sname, scode, dept, _e, _p in SUBJECTS:
        for k in range(TEACHERS_PER_SUBJECT[scode]):
            t = add_staff('Teacher', dept, sname, grade='Lead Teacher' if k == 0 else rng.choice(['Teacher Level 1', 'Teacher Level 2']))
            by_subject[scode].append(t)
    relief = [add_staff('Substitute teacher', 'Math and English', 'Mathematics, English Language Arts', kind='relief', grade='Teacher Level 1'),
              add_staff('Substitute teacher', 'Science and Social Studies', 'Science, Social Studies', kind='relief', grade='Teacher Level 1')]
    for t in staff:
        if t is principal:
            continue
        t['manager'] = principal['id'] if t is assistant or t['dept'] in ('Administration', 'Health', 'Student Support', 'Library', 'Finance') else assistant['id']
    for t in staff:
        t['email'] = f'{t["first"].lower()}.{t["last"].lower()}@{DOMAIN}'
        t['phone'] = phone(rng)
        t['salary'] = {n: a for n, a, _ in pay}[t['grade']]
        files['staff'].append(R('staff', full_name=f'{t["title"] + " " if t["title"] else ""}{t["first"]} {t["last"]}', email=t['email'], phone=t['phone'],
                                employee_id=t['id'], role=t['role'], department=t['dept'], subjects=t['subject'], joining_date=t['joined'].isoformat(),
                                gender=t['gender'], date_of_birth=(date(1965, 1, 1) + timedelta(days=rng.randint(0, 11000))).isoformat(),
                                monthly_salary=t['salary'], qualifications='MEd' if t['role'] == 'Teacher' and rng.random() < 0.4 else 'BA' if t['role'] == 'Teacher' else '',
                                home_address=f'{rng.randint(10, 999)} {rng.choice(STREETS)}', teacher_type=t['kind'], manager=t.get('manager', '')))

    # who teaches which class and subject: fill the least busy qualified teacher, never past the weekly limit
    load = defaultdict(int)
    for name, code, grade, sections, _f in CLASSES:
        for sname, scode, _d, _e, ppw in sorted(SUBJECTS, key=lambda s: -s[4][1]):
            p = ppw[stage(grade)]
            if not p:
                continue
            need = p * sec_count[code]
            pool = sorted(by_subject[scode], key=lambda t: load[t['id']])
            pick = next((t for t in pool if load[t['id']] + need <= 27), pool[0])
            load[pick['id']] += need
            files['teacher_assignments'].append(R('teacher_assignments', teacher=pick['id'], **{'class': name, 'subject': scode}, year=YEAR, primary=True))

    # -- people and families -----------------------------------------------------------------------------------------
    students, families = [], []
    nsid = 0
    for name, code, grade, sections, _fee in CLASSES:
        for section in sections:
            for _ in range(rng.randint(6, 8)):             # a small school: it is invented, so it only needs to be enough to show the screens
                nsid += 1
                if families and rng.random() < 0.12:
                    fam = rng.choice([f for f in families if f['grade'] != grade and f['kids'] < 3] or families)
                else:
                    ln = rng.choice(LAST)
                    fam = dict(last=ln, name=f'{ln} family ({len(families) + 1})', father=f'{rng.choice(FIRST_M)} {ln}', mother=f'{rng.choice(FIRST_F)} {ln}', phone=phone(rng), phone2=phone(rng),
                               street=f'{rng.randint(10, 999)} {rng.choice(STREETS)}', grade=grade, kids=0)
                    families.append(fam)
                fam['kids'] += 1
                female = rng.random() < 0.5
                first = rng.choice(FIRST_F if female else FIRST_M)
                born = date(2021 - grade, rng.randint(1, 12), rng.randint(1, 28))
                students.append(dict(no=f'{PREFIX}{nsid:03d}', first=first, last=fam['last'], gender='female' if female else 'male', born=born, cls=name,
                                     grade=grade, section=section, fam=fam, admitted=date(2026, 8, 17) if grade < 3 or rng.random() < 0.3 else date(2026 - min(grade, 5), 8, 17)))
    for s in students:
        f = s['fam']
        files['students'].append(R('students', full_name=f'{s["first"]} {s["last"]}', **{'class': s['cls']}, section=s['section'], student_id=s['no'],
                                   gender=s['gender'], date_of_birth=s['born'].isoformat(), admission_date=s['admitted'].isoformat(), father_name=f['father'],
                                   mother_name=f['mother'], guardian_phone=f['phone'], address=f['street'], city='Springfield', blood_group=rng.choice(BLOOD),
                                   previous_school=rng.choice(['', '', 'Lincoln Elementary', 'Riverside Montessori', 'Oakwood Primary']), family=f['name']))
        for who, relation, first_last in ((f['mother'], 'mother', f['mother'].split(' ', 1)), (f['father'], 'father', f['father'].split(' ', 1))):
            files['guardians'].append(R('guardians', student=s['no'], first_name=first_last[0], last_name=first_last[1], relationship=relation,
                                        email=f'{first_last[0].lower()}.{first_last[1].lower()}.{s["no"][-3:]}@family.example',
                                        mobile_phone=f['phone'] if relation == 'mother' else f['phone2'], occupation=rng.choice(['Nurse', 'Engineer', 'Teacher', 'Accountant', 'Electrician', 'Designer', 'Manager']),
                                        is_primary=relation == 'mother', lives_with=True, has_custody=True, can_pickup=True, is_emergency_contact=True,
                                        receives_billing=relation == 'mother', receives_messages=True, portal_access=relation == 'mother',
                                        priority=1 if relation == 'mother' else 2))
    allergies = ['Peanuts', 'Tree nuts', 'Dairy', 'Eggs', 'Shellfish', 'Penicillin', 'Bee stings']
    # Every student has a health record (doctor, insurance, emergency consent); about a quarter have something the nurse must know.
    flagged = {x['no'] for x in rng.sample(students, 55)}
    for s in students:
        needs = s['no'] in flagged
        sev = needs and rng.random() < 0.3
        cond = rng.choice(['Asthma', 'ADHD', 'Type 1 diabetes', 'Eczema', '']) if needs else ''
        files['student_health'].append(R('student_health', student=s['no'], allergies=rng.choice(allergies) if needs and (sev or rng.random() < 0.7) else 'None known',
                                         severe_allergy=sev, medical_conditions=cond,
                                         medications='EpiPen' if sev else 'Inhaler as needed' if cond == 'Asthma' else '',
                                         dietary_restrictions=rng.choice(['', '', 'Vegetarian', 'No pork', 'Gluten free']) if needs else '',
                                         physician_name=f'Dr. {rng.choice(LAST)}', physician_phone=phone(rng),
                                         insurance_provider=rng.choice(['BlueCross', 'Aetna', 'Cigna', 'United', 'Medicaid']),
                                         insurance_policy=f'POL-{rng.randint(100000, 999999)}', emergency_consent=rng.random() < 0.97,
                                         notes='Care plan on file with the school nurse' if sev or cond in ('Type 1 diabetes', 'Asthma') else ''))
    exempt = {s['no'] for s in rng.sample(students, 4)}
    for s in students:
        for vaccine, dose in VACCINES:
            ex = s['no'] in exempt and vaccine == 'MMR'
            files['immunizations'].append(R('immunizations', student=s['no'], vaccine=vaccine, dose=dose, date_given='' if ex else date(s['born'].year, 6, 15).isoformat(),
                                            exempt=ex, exemption_reason='Religious exemption on file' if ex else ''))

    # -- admissions ------------------------------------------------------------------------------------------------
    stages = ['pending'] * 8 + ['reviewing'] * 8 + ['approved'] * 5 + ['waitlisted'] * 4 + ['rejected'] * 2 + ['withdrawn'] * 1
    for i, st in enumerate(stages):
        female = rng.random() < 0.5
        first, last = rng.choice(FIRST_F if female else FIRST_M), rng.choice(LAST)
        grade = rng.randint(0, 8)
        files['admissions'].append(R('admissions', full_name=f'{first} {last}', email=f'{last.lower()}.family{i}@example.org', phone=phone(rng),
                                     date_of_birth=date(2021 - grade, rng.randint(1, 12), rng.randint(1, 28)).isoformat(), gender='female' if female else 'male',
                                     applying_for_class=CLASSES[grade][0], academic_year='2027-2028', status=st,
                                     status_notes={'pending': 'Waiting for transcripts', 'reviewing': 'Campus visit booked', 'approved': 'Offer sent',
                                                   'waitlisted': 'Class is full this year', 'rejected': '', 'withdrawn': 'Family moved'}[st],
                                     father_name=f'{rng.choice(FIRST_M)} {last}', father_phone=phone(rng), mother_name=f'{rng.choice(FIRST_F)} {last}',
                                     mother_phone=phone(rng), previous_school=rng.choice(['Lincoln Elementary', 'Home school', 'Riverside Montessori']),
                                     address=f'{rng.randint(10, 999)} {rng.choice(STREETS)}', city='Springfield'))

    # -- fees --------------------------------------------------------------------------------------------------------
    for name, code, grade, sections, fee in CLASSES:
        files['fee_structure'].append(R('fee_structure', **{'class': name}, fee_name='Monthly Tuition Fee', amount=fee, due_date='2026-09-10', academic_year=YEAR,
                                        recurring=True, frequency='monthly'))
        files['fee_structure'].append(R('fee_structure', **{'class': name}, fee_name='Registration fee', amount=150, due_date='2026-08-17', academic_year=YEAR,
                                        recurring=False, frequency='yearly'))
    fees = {c[0]: c[4] for c in CLASSES}
    inv, rc = 0, 0
    for month, due, issued, paid_share in (('09', '2026-09-10', '2026-09-01', 0.88), ('10', '2026-10-10', '2026-10-01', 0.82)):
        for s in students:
            inv += 1
            amount = fees[s['cls']]
            number = f'MGA-INV-2026-{month}-{inv:04d}'      # invoice numbers are unique across all schools, so this school has its own prefix
            files['invoices'].append(R('invoices', invoice_number=number, student=s['no'], invoice_type='tuition', amount=amount, opening_balance=0, discount_amount=0,
                                       late_fee_amount=0, due_date=due, issue_date=issued, status='issued', description=f'{"September" if month == "09" else "October"} 2026 tuition'))
            roll = rng.random()
            if roll < paid_share:
                rc += 1
                files['payments'].append(R('payments', invoice=number, reference=f'RCPT-26-{rc:04d}', amount=amount, payment_date=f'2026-{month}-{rng.randint(2, 9):02d}',
                                           payment_method=rng.choice(['bank_transfer', 'credit_card', 'cheque', 'online']), notes=''))
            elif roll < paid_share + 0.07:
                rc += 1
                files['payments'].append(R('payments', invoice=number, reference=f'RCPT-26-{rc:04d}', amount=round(amount / 2), payment_date=f'2026-{month}-{rng.randint(5, 12):02d}',
                                           payment_method='bank_transfer', notes='Part payment'))
    for s in rng.sample(students, 6):
        files['balances'].append(R('balances', student_id=s['no'], amount=rng.choice([150, 275, 400, 600]), due_date='2026-10-15', description='Summer camp and supplies'))

    # -- pay and leave ---------------------------------------------------------------------------------------------
    for t in staff:
        files['payroll_profiles'].append(R('payroll_profiles', employee=t['id'], pay_grade=t['grade'], tax_rate_percent=12,
                                           benefits='Health plan:180:deduction; Retirement plan:150:deduction' + ('; Technology stipend:50:allowance' if t['role'] == 'Teacher' else '')))
        for month in ('2026-08-01', '2026-09-01'):
            tax = round(t['salary'] * 0.12)
            files['payslips'].append(R('payslips', employee=t['id'], month=month, basic_salary=t['salary'], allowances=50 if t['role'] == 'Teacher' else 0,
                                       deductions=330 + tax, paid_amount=t['salary'] + (50 if t['role'] == 'Teacher' else 0) - 330 - tax if month == '2026-08-01' else 0,
                                       payment_date='2026-08-31' if month == '2026-08-01' else '', payment_method='bank_transfer' if month == '2026-08-01' else ''))
        files['leave_balances'].append(R('leave_balances', employee=t['id'], sick=8, casual='', annual=12, personal=3, bereavement=3, jury=3, professional=3,
                                         carried_over=rng.choice([0, 0, 2, 3])))
    teachers = [t for t in staff if t['role'] == 'Teacher']
    leaves = [(teachers[0], 'sick', '2026-09-14', '2026-09-15', 'approved', 'Flu'), (teachers[3], 'personal', '2026-09-25', '2026-09-25', 'approved', 'Family event'),
              (teachers[6], 'professional', '2026-10-02', '2026-10-02', 'approved', 'Math conference'), (teachers[1], 'sick', '2026-10-08', '2026-10-09', 'approved', 'Surgery recovery'),
              (teachers[8], 'annual', '2026-10-19', '2026-10-23', 'pending', 'Family trip'), (teachers[11], 'jury', '2026-10-13', '2026-10-14', 'approved', 'Jury summons')]
    for t, kind, a, b, status, reason in leaves:
        files['leave_requests'].append(R('leave_requests', employee=t['id'], leave_type=kind, start_date=a, end_date=b, day_part='full', status=status, reason=reason))

    # -- the school year so far ---------------------------------------------------------------------------------------
    closed = closed_dates()
    days = list(school_days(date(2026, 8, 17), date(2026, 10, 2), closed))
    ill = ['illness', 'illness', 'medical', 'family', 'transport']
    for d in days[-20:]:             # four school weeks of attendance is enough to show the reports
        for s in students:
            r = rng.random()
            if r < 0.945:
                status, reason, exc, late = 'present', '', False, ''
            elif r < 0.975:
                status, reason, exc, late = 'absent', rng.choice(ill), rng.random() < 0.6, ''
            else:
                status, reason, exc, late = 'late', 'transport', False, rng.choice([5, 10, 15])
            files['attendance'].append(R('attendance', student=s['no'], date=d.isoformat(), status=status, reason=reason, excused=exc, minutes_late=late))
    for d in days[-12:]:
        for t in staff:
            files['staff_attendance'].append(R('staff_attendance', employee=t['id'], date=d.isoformat(), status='present'))
    code = 0
    for name, ccode, grade, sections, _f in CLASSES:
        for subj, total, passing, title, when in (('MATH', 50, 25, 'Unit 1 test', '2026-09-25'), ('ELA', 20, 10, 'Reading quiz', '2026-09-18')):
            code += 1
            ec = f'EXM-2026-{code:04d}'
            files['exams'].append(R('exams', exam_code=ec, title=f'{name} {title}', exam_type='test' if total > 20 else 'quiz', **{'class': name}, subject=subj,
                                    total_marks=total, passing_marks=passing, exam_date=when, academic_year=YEAR, term='first', is_published=True, is_active=True))
            for s in [x for x in students if x['cls'] == name]:
                marks = max(0, min(total, round(rng.gauss(total * 0.78, total * 0.14), 1)))
                files['exam_results'].append(R('exam_results', exam=ec, student=s['no'], obtained_marks=marks))
    for nme, kind, a, b in HOLIDAYS:
        files['calendar_events'].append(R('calendar_events', title=nme, kind=kind, start_date=a, end_date=b, audience='everyone', closes_school=True, description='No school'))
    files['calendar_events'] += [R('calendar_events', title='Back to school night', kind='event', start_date='2026-09-17', end_date='2026-09-17', location='Gymnasium', audience='families'),
                                 R('calendar_events', title='Parent-teacher conferences', kind='meeting', start_date='2026-11-05', end_date='2026-11-06', audience='families'),
                                 R('calendar_events', title='Fall fundraiser', kind='event', start_date='2026-10-24', end_date='2026-10-24', location='Gymnasium', audience='everyone')]

    # -- HR records ------------------------------------------------------------------------------------------------
    for t in staff:
        files['contracts'].append(R('contracts', employee=t['id'], kind='part_time' if t['kind'] == 'relief' else 'full_time', start_date=t['joined'].isoformat(),
                                    end_date='2027-06-30' if t['kind'] == 'relief' or t['joined'].year >= 2026 else '', probation_end='2027-01-31' if t['joined'].year >= 2026 else ''))
    for i, t in enumerate(teachers):
        files['credentials'].append(R('credentials', employee=t['id'], name='State teaching license', issuer='State Board of Education', number=f'TL-{4400 + i}',
                                      issued_on='2022-07-01', expires_on={0: '2026-09-15', 1: '2026-10-28'}.get(i, '2029-06-30')))
    for t in [x for x in staff if x['role'] in ('School Nurse', 'Teacher') and (x['subject'] in ('Physical Education', '') )]:
        files['credentials'].append(R('credentials', employee=t['id'], name='CPR and first aid', issuer='Red Cross', number=f'CPR-{rng.randint(1000, 9999)}',
                                      issued_on='2025-01-15', expires_on='2026-11-20'))
    for i, t in enumerate(teachers[:8]):
        files['reviews'].append(R('reviews', employee=t['id'], kind='annual', period_label='2025-26', review_date='2026-06-10', rating=rng.choice([3, 4, 4, 5]),
                                  strengths='Strong rapport with students and families', improvements='Share more resources with the team', status='shared'))
        files['goals'].append(R('goals', employee=t['id'], title=rng.choice(['Run a weekly study club', 'Complete the technology integration course', 'Pilot project-based units']),
                                due_date='2027-03-01', progress=rng.choice([10, 25, 40, 60]), status='open'))
    files['job_openings'] += [R('job_openings', title='Middle school science teacher', department='Science', positions=1, status='open', closes_on='2026-11-30',
                                description='Grades 6 to 8, state licence required'),
                              R('job_openings', title='Part-time Spanish teacher', department='World Languages', positions=1, status='open', closes_on='2026-12-15')]
    for i, (op, stg) in enumerate([('Middle school science teacher', 'interview'), ('Middle school science teacher', 'screening'), ('Middle school science teacher', 'applied'),
                                   ('Part-time Spanish teacher', 'offer'), ('Part-time Spanish teacher', 'applied'), ('Part-time Spanish teacher', 'rejected')]):
        first, last = rng.choice(FIRST_F + FIRST_M), rng.choice(LAST)
        files['job_candidates'].append(R('job_candidates', opening=op, full_name=f'{first} {last}', email=f'{first.lower()}.{last.lower()}@example.org', phone=phone(rng),
                                         source=rng.choice(['Website', 'Referral', 'Job board']), stage=stg, rating=rng.choice([3, 4, 5])))

    # -- behaviour ------------------------------------------------------------------------------------------------
    cats = [('Helping others', 'positive', 2, 'low', False), ('Excellent effort', 'positive', 3, 'low', False), ('Leadership', 'positive', 2, 'low', False),
            ('Kindness', 'positive', 2, 'low', False), ('Great teamwork', 'positive', 2, 'low', False),
            ('Disrupting class', 'negative', -1, 'low', False), ('Late to class', 'negative', -1, 'low', False), ('Homework missing', 'negative', -1, 'low', False),
            ('Unkind words', 'negative', -2, 'medium', True), ('Physical conflict', 'negative', -4, 'high', True)]
    for i, (nme, kind, pts, sev, notify) in enumerate(cats, 1):
        files['behaviour_categories'].append(R('behaviour_categories', name=nme, kind=kind, points=pts, severity=sev, notify_family=notify, order=i))
    places = ['Classroom', 'Playground', 'Hallway', 'Cafeteria', 'Gym', 'Library']
    pos_text = {'Helping others': 'Helped a classmate with their work', 'Excellent effort': 'Worked hard on the unit project', 'Leadership': 'Led the group activity',
                'Kindness': 'Included a new student at lunch', 'Great teamwork': 'Shared materials and finished the task together'}
    neg_text = {'Disrupting class': 'Calling out during the lesson', 'Late to class': 'Arrived after the bell', 'Homework missing': 'Homework not handed in',
                'Unkind words': 'Said something hurtful to a classmate', 'Physical conflict': 'Pushing during a game at recess'}
    action_for = {'Disrupting class': 'verbal_warning', 'Homework missing': 'verbal_warning', 'Unkind words': 'parent_meeting', 'Physical conflict': 'detention'}
    for d in days[-20:]:
        for s in rng.sample(students, rng.randint(7, 11)):
            nme, kind, pts, sev, _n = rng.choice([c for c in cats if c[1] == 'positive' or rng.random() < 0.25])
            text = pos_text.get(nme) or neg_text[nme]
            acted = kind == 'negative' and nme in action_for and rng.random() < 0.7
            files['behaviour_incidents'].append(R(
                'behaviour_incidents', student=s['no'], category=nme, date=d.isoformat(), time=f'{rng.randint(9, 14):02d}:{rng.choice(["05", "20", "40"])}',
                location=rng.choice(places), description=text, points=pts, severity=sev, status='resolved' if kind == 'positive' or acted else rng.choice(['open', 'in_review']),
                visible_to_family=True, action=action_for[nme] if acted else '', action_notes='Talked it through with the student' if acted else ''))
    skills = [('Punctuality', 'affective'), ('Respect', 'affective'), ('Teamwork', 'affective'), ('Neatness', 'affective'), ('Self-control', 'affective'),
              ('Handwriting', 'psychomotor'), ('Sports', 'psychomotor'), ('Drawing', 'psychomotor')]
    for i, (nme, dom) in enumerate(skills, 1):
        files['skills'].append(R('skills', name=nme, domain=dom, description=f'{nme} in everyday school life', max_rating=5, order=i))
    for s in students:
        for dom in ('affective', 'psychomotor'):
            names = [n for n, d in skills if d == dom]
            files['behaviour_ratings'].append(R('behaviour_ratings', student=s['no'], domain=dom, term='first', academic_year='2026-2027',
                                                ratings='; '.join(f'{n}:{max(1, min(5, round(rng.gauss(4.0, 0.8))))}' for n in names),
                                                comments=rng.choice(['A thoughtful, hard-working student', 'Settling in well', 'Needs encouragement to join in', 'Shows real leadership', ''])))
    for s in rng.sample(students, 16):
        kind = rng.choice(['counselling', 'meeting', 'incident'])
        files['observations'].append(R('observations', student=s['no'], observation_type=kind,
                                       title={'counselling': 'Check-in with the school counselor', 'meeting': 'Parent meeting', 'incident': 'Playground incident follow-up'}[kind],
                                       date=rng.choice(days[-25:]).isoformat(), description='Discussed how the first weeks of school are going.',
                                       severity='low', status=rng.choice(['open', 'resolved']), parent_notified=True, action_taken='Weekly check-ins agreed',
                                       outcome=rng.choice(['', 'Going well', 'Review in October'])))

    files['timetable'] = _timetable(files)
    return dict(files)


def _timetable(files):
    """Load the base files into a scratch school, run the timetable generator, and read the timetable back. Rolled back."""
    from services.core.tenants.context import use_tenant
    from services.core.tenants.models import School

    from services.education.academics import scheduler

    base = ['academic_years', 'classes', 'subjects', 'rooms', 'periods', 'weekdays', 'class_subjects', 'pay_grades', 'staff', 'teacher_assignments']
    with transaction.atomic():
        school = School.objects.create(tenant_code='ZZB', name='Sample pack builder', subdomain='zz-pack-builder', is_active=True)
        with use_tenant(school):
            for kind in base:
                spec = KINDS[kind]
                rows = [[c[1] for c in spec['columns']]] + files[kind]
                result, message = engine.check_rows(kind, spec, rows, school, 'add')
                if message:
                    raise RuntimeError(f'{kind}: {message}')
                bad = [r for r in result['rows'] if r['state'] == 'error']
                if bad:
                    raise RuntimeError(f'{kind} row {bad[0]["row"]}: {bad[0]["messages"]}')
                engine.apply_rows(spec, result)
            year = __import__('django.apps', fromlist=['apps']).apps.get_model('education_academics', 'AcademicYear').objects.get(name=YEAR)
            out = scheduler.run(year.pk, tenant_id=str(school.pk), seed=2026, restarts=10, commit=True)
            if out.get('error') or out.get('unscheduled'):
                raise RuntimeError(f'timetable could not be completed: {out.get("error") or out["unscheduled"][:3]}')
            rows = KINDS['timetable']['export']({'school': school})
        transaction.set_rollback(True)
    return rows


def to_csv(kind, rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([label + (' *' if req else '') for _k, label, req, _a in KINDS[kind]['columns']])
    for r in rows:
        w.writerow(r)
    return '﻿' + out.getvalue()
