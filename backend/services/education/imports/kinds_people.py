"""Pack kinds for people records: guardians, student health, immunisations and admission applications."""
from __future__ import annotations

from django.apps import apps

from .pack import col, model_kind, register

RELATIONSHIPS = {'mother': 'Mother', 'father': 'Father', 'stepmother': 'Stepmother', 'stepfather': 'Stepfather',
                 'grandparent': 'Grandparent', 'aunt_uncle': 'Aunt or uncle', 'sibling': 'Sibling', 'legal_guardian': 'Legal guardian',
                 'foster_parent': 'Foster parent', 'other': 'Other'}
APPLICANT_FIELDS = ['full_name', 'email', 'phone', 'date_of_birth', 'gender', 'father_name', 'father_phone', 'mother_name',
                    'mother_phone', 'guardian_name', 'guardian_phone', 'previous_school', 'address', 'city', 'applying_for_class',
                    'applying_for_section']
GUARDIAN_FIELDS = ['first_name', 'last_name', 'relationship', 'email', 'mobile_phone', 'home_phone', 'work_phone', 'occupation',
                   'employer', 'address']


def _g(attr):
    return lambda o: getattr(o.guardian, attr)


def _guardian_before(data, ctx):
    Guardian = apps.get_model('education_students', 'Guardian')
    student = data['student']
    if not student.household_id:
        from services.education.students.households import ensure_household
        ensure_household(student)
        student.refresh_from_db()
    g = Guardian.objects.create(tenant=ctx['school'], household=student.household,
                                **{f: data.get('_g_' + f) or '' for f in GUARDIAN_FIELDS if f != 'relationship'},
                                relationship=data.get('_g_relationship') or 'other')
    data['guardian'] = g
    return data


def _guardian_after_update(obj, clean, ctx):
    g, given, changed = obj.guardian, clean['_given'], False
    for f in GUARDIAN_FIELDS:
        if '_g_' + f in given and getattr(g, f) != clean['_g_' + f]:
            setattr(g, f, clean['_g_' + f])
            changed = True
    if changed:
        g.save()


def _application_validate(clean, ctx):
    """An application without a number is matched to an existing one for the same child, class and year (so a file can be
    loaded twice without adding the application twice)."""
    if clean.get('application_no'):
        return []
    Application = apps.get_model('education_admissions', 'Application')
    email, klass, year = (clean.get('_a_email') or '').lower(), clean.get('_a_applying_for_class') or '', clean.get('academic_year') or ''
    found = Application.objects.filter(applicant__email__iexact=email, applicant__applying_for_class__iexact=klass,
                                       academic_year=year, applicant__full_name__iexact=clean.get('_a_full_name') or '').first()
    if found is not None:
        clean['application_no'] = found.application_no
    return []


def _applicant_before(data, ctx):
    Applicant = apps.get_model('education_admissions', 'Applicant')
    vals = {f: data.get('_a_' + f) for f in APPLICANT_FIELDS}
    for f in ('phone', 'father_name', 'father_phone', 'mother_name', 'mother_phone', 'guardian_name', 'guardian_phone',
              'previous_school', 'address', 'city', 'applying_for_section'):
        vals[f] = vals[f] or ''
    vals['gender'] = vals['gender'] or 'O'
    data['applicant'] = Applicant.objects.create(tenant=ctx['school'], **vals)
    if not data.get('application_no'):
        data.pop('application_no', None)
    return data


def _applicant_after_update(obj, clean, ctx):
    a, given, changed = obj.applicant, clean['_given'], False
    for f in APPLICANT_FIELDS:
        if '_a_' + f in given and getattr(a, f) != clean['_a_' + f]:
            setattr(a, f, clean['_a_' + f])
            changed = True
    if changed:
        a.save()


def _applicant_col(key, label, field, type='text', required=False, aliases=(), choices=None):
    return col(key, label, type, required, aliases, field='_a_' + field, choices=choices, export=lambda o, f=field: getattr(o.applicant, f))


def install():
    guardian_cols = [
        col('student', 'Student number', 'ref', True, ref='student', aliases=['studentid', 'studentno', 'admissionno']),
        col('first_name', 'First name', required=True, field='_g_first_name', aliases=['firstname', 'guardianfirstname'], export=_g('first_name')),
        col('last_name', 'Last name', field='_g_last_name', aliases=['lastname', 'surname'], export=_g('last_name')),
        col('relationship', 'Relationship', 'choice', True, field='_g_relationship', choices=RELATIONSHIPS, export=_g('relationship')),
        col('email', 'Email', field='_g_email', export=_g('email')),
        col('mobile_phone', 'Mobile phone', field='_g_mobile_phone', aliases=['mobile', 'phone'], export=_g('mobile_phone')),
        col('home_phone', 'Home phone', field='_g_home_phone', export=_g('home_phone')),
        col('work_phone', 'Work phone', field='_g_work_phone', export=_g('work_phone')),
        col('occupation', 'Occupation', field='_g_occupation', export=_g('occupation')),
        col('employer', 'Employer', field='_g_employer', export=_g('employer')),
        col('address', 'Address', field='_g_address', export=_g('address')),
        col('is_primary', 'Primary contact (yes/no)', 'bool', default=False, aliases=['primary']),
        col('lives_with', 'Lives with student (yes/no)', 'bool', default=True),
        col('has_custody', 'Has custody (yes/no)', 'bool', default=True, aliases=['custody']),
        col('can_pickup', 'May collect (yes/no)', 'bool', default=True, aliases=['pickup']),
        col('is_emergency_contact', 'Emergency contact (yes/no)', 'bool', default=False, aliases=['emergency']),
        col('receives_billing', 'Receives bills (yes/no)', 'bool', default=False, aliases=['billing']),
        col('receives_messages', 'Receives messages (yes/no)', 'bool', default=True, aliases=['messages']),
        col('portal_access', 'Portal access (yes/no)', 'bool', default=False, aliases=['portal']),
        col('priority', 'Contact order', 'int', default=1),
    ]
    register('guardians', model_kind(
        label='Guardians and parents', order=13, model='education_students.StudentGuardian', filename='guardians.csv', depends=['students'],
        singular='guardian', cols=guardian_cols,
        help='One row per guardian per student: name, relationship, contact details, and what they may do (collect the child, receive bills...). '
             'Parents named on the student file already exist; matching names are updated in update mode.',
        key=['student', 'first_name', 'last_name'], before_create=_guardian_before, after_update=_guardian_after_update,
        queryset=lambda ctx: apps.get_model('education_students', 'StudentGuardian').objects.select_related('guardian', 'student'),
        order_by=('student__student_id', 'priority'),
        example=[['DS-2026001', 'Amna', 'Raza', 'mother', 'amna@example.com', '0300 7654321', '', '', 'Nurse', 'City Hospital', '12 Park Road',
                  'yes', 'yes', 'yes', 'yes', 'yes', 'yes', 'yes', 'yes', '1']]))

    register('student_health', model_kind(
        label='Student health records', order=14, model='education_students.StudentHealth', filename='student_health.csv', depends=['students'],
        singular='health record',
        help='Allergies, conditions, medication, doctor and insurance. One row per student.',
        cols=[col('student', 'Student number', 'ref', True, ref='student', aliases=['studentid', 'studentno']),
              col('allergies', 'Allergies'), col('severe_allergy', 'Severe allergy (yes/no)', 'bool', field='has_severe_allergy', default=False,
                                                    aliases=['epipen', 'severe']),
              col('medical_conditions', 'Medical conditions', aliases=['conditions']), col('medications', 'Medications', aliases=['medication']),
              col('dietary_restrictions', 'Dietary restrictions', aliases=['diet']),
              col('physician_name', 'Doctor', aliases=['physician', 'doctorname']), col('physician_phone', 'Doctor phone', aliases=['doctorphone']),
              col('insurance_provider', 'Insurance provider', aliases=['insurance']),
              col('insurance_policy', 'Insurance policy number', field='insurance_policy_number', aliases=['policynumber']),
              col('emergency_consent', 'Emergency treatment consent (yes/no)', 'bool', field='emergency_treatment_consent', default=False,
                  aliases=['consent']),
              col('notes', 'Notes')],
        key=['student'], order_by=('student__student_id',),
        example=[['DS-2026001', 'Peanuts', 'yes', 'Asthma', 'Inhaler as needed', '', 'Dr. Lee', '555-0100', 'BlueCross', 'BC-123456', 'yes', '']]))

    register('immunizations', model_kind(
        label='Immunisations', order=15, model='education_students.Immunization', filename='immunizations.csv', depends=['students'],
        singular='immunisation',
        help='One row per vaccine dose per student. Mark exemptions with Exempt = yes and a reason.',
        cols=[col('student', 'Student number', 'ref', True, ref='student', aliases=['studentid', 'studentno']),
              col('vaccine', 'Vaccine', required=True), col('dose', 'Dose'), col('date_given', 'Date given', 'date'),
              col('exempt', 'Exempt (yes/no)', 'bool', default=False), col('exemption_reason', 'Exemption reason'), col('notes', 'Notes')],
        key=['student', 'vaccine', 'dose'], order_by=('student__student_id', 'vaccine', 'date_given'),
        example=[['DS-2026001', 'MMR', '1', '2020-03-14', 'no', '', '']]))

    app_cols = [
        col('application_no', 'Application number', aliases=['applicationno', 'appno']),
        _applicant_col('full_name', 'Applicant name', 'full_name', required=True, aliases=['name', 'applicant', 'studentname']),
        _applicant_col('email', 'Email', 'email', required=True, aliases=['emailaddress']),
        _applicant_col('phone', 'Phone', 'phone', aliases=['mobile']),
        _applicant_col('date_of_birth', 'Date of birth', 'date_of_birth', 'date', aliases=['dob']),
        _applicant_col('gender', 'Gender', 'gender', 'choice', choices={'M': 'Male', 'F': 'Female', 'O': 'Other'}),
        _applicant_col('applying_for_class', 'Applying for class', 'applying_for_class', required=True, aliases=['class', 'grade', 'applyingfor']),
        _applicant_col('applying_for_section', 'Section', 'applying_for_section'),
        col('academic_year', 'School year', default='2026-2027', aliases=['year']),
        col('status', 'Status', 'choice', choices={'pending': 'Pending Review', 'reviewing': 'Under Review', 'approved': 'Approved',
                                                       'rejected': 'Rejected', 'waitlisted': 'Waitlisted', 'enrolled': 'Enrolled',
                                                       'withdrawn': 'Withdrawn'}, default='pending'),
        col('program', 'Programme', aliases=['program']), col('status_notes', 'Notes', aliases=['notes']),
        _applicant_col('father_name', 'Father name', 'father_name'), _applicant_col('father_phone', 'Father phone', 'father_phone'),
        _applicant_col('mother_name', 'Mother name', 'mother_name'), _applicant_col('mother_phone', 'Mother phone', 'mother_phone'),
        _applicant_col('guardian_name', 'Guardian name', 'guardian_name'), _applicant_col('guardian_phone', 'Guardian phone', 'guardian_phone'),
        _applicant_col('previous_school', 'Previous school', 'previous_school'), _applicant_col('address', 'Address', 'address'),
        _applicant_col('city', 'City', 'city'),
    ]
    register('admissions', model_kind(
        label='Admission applications', order=16, model='education_admissions.Application', filename='admissions.csv', singular='application',
        help='Applications to the school and where each one stands. Leave the application number empty for new applications; '
             'a number is made for you. Admitted children join the student list through the Admissions screen.',
        cols=app_cols, key=['application_no'], validate=_application_validate, before_create=_applicant_before, after_update=_applicant_after_update,
        queryset=lambda ctx: apps.get_model('education_admissions', 'Application').objects.select_related('applicant'),
        order_by=('application_no',),
        example=[['', 'Noah Miller', 'noah.miller@example.com', '555-0142', '2020-05-02', 'male', 'Kindergarten', '', '2026-2027', 'pending',
                  '', '', 'Emma Miller', '555-0142', '', '', '', '', '', '12 Oak Street', 'Springfield']]))
