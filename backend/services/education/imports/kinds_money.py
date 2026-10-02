"""Pack kinds for money and pay: fee structure, invoices, payments, pay grades, payroll profiles, payslips; and for leave:
balances and requests."""
from __future__ import annotations

from datetime import timedelta

from django.apps import apps

from .pack import cell_text, col, model_kind, register

INVOICE_TYPES = {'tuition': 'Tuition', 'transport': 'Transport', 'hostel': 'Hostel', 'miscellaneous': 'Miscellaneous', 'composite': 'Composite'}
INVOICE_STATUS = {'draft': 'Draft', 'issued': 'Issued', 'paid': 'Paid', 'partial': 'Partially paid', 'overdue': 'Overdue',
                  'cancelled': 'Cancelled', 'carried_forward': 'Carried forward'}
PAY_METHODS = {'cash': 'Cash', 'bank_transfer': 'Bank transfer', 'credit_card': 'Credit card', 'cheque': 'Cheque', 'online': 'Online payment',
               'account_credit': 'Account credit'}
LEAVE_TYPES = {'sick': 'Sick', 'casual': 'Casual', 'annual': 'Annual', 'maternity': 'Maternity', 'emergency': 'Emergency',
               'personal': 'Personal day', 'bereavement': 'Bereavement', 'jury': 'Jury duty', 'professional': 'Professional development',
               'unpaid': 'Unpaid', 'other': 'Other'}
LEAVE_STATUS = {'pending': 'Pending', 'recommended': 'Recommended', 'approved': 'Approved', 'rejected': 'Rejected', 'cancelled': 'Cancelled'}
DAY_PARTS = {'full': 'Full day', 'am': 'Morning only', 'pm': 'Afternoon only'}


# ---- fee structure ------------------------------------------------------------------------------------------------

def _fee_validate(clean, ctx):
    section_name = clean.get('_section_name')
    clean['section'] = None
    if section_name and clean.get('class_ref') is not None:
        Section = apps.get_model('education_academics', 'Section')
        sec = Section.objects.filter(class_ref=clean['class_ref'], name__iexact=section_name).first()
        if sec is None:
            return [f'Section "{section_name}" does not exist in {clean["class_ref"].name}']
        clean['section'] = sec
    return []


# ---- invoices and payments ----------------------------------------------------------------------------------------

def _invoice_after_create(obj, clean, ctx):
    Invoice = apps.get_model('education_finance', 'Invoice')
    if clean.get('_issue_date'):
        Invoice.objects.filter(pk=obj.pk).update(issue_date=clean['_issue_date'])


def _invoice_validate(clean, ctx):
    if clean.get('amount') is None:
        return []
    return []


def _payment_validate(clean, ctx):
    inv = clean.get('invoice')
    if inv is not None and clean.get('amount') is not None and clean['amount'] <= 0:
        return ['Amount must be more than zero']
    return []


def _payment_after_create(obj, clean, ctx):
    Payment = apps.get_model('education_finance', 'Payment')
    if clean.get('_paid_on'):
        Payment.objects.filter(pk=obj.pk).update(payment_date=clean['_paid_on'])


def _payment_ref(o):
    """The receipt reference; payments without one get a stable one made from the invoice and their order."""
    if o.transaction_id:
        return o.transaction_id
    Payment = apps.get_model('education_finance', 'Payment')
    earlier = Payment.objects.filter(invoice=o.invoice).filter(created_at__lt=o.created_at).count() + 1
    return f'{o.invoice.invoice_number}-{earlier}'


# ---- payroll --------------------------------------------------------------------------------------------------------

def _benefits_text(o):
    return '; '.join(f'{b.get("name")}:{b.get("amount")}:{b.get("kind", "allowance")}' for b in (o.benefits or []))


def _payroll_validate(clean, ctx):
    raw = (clean.get('_benefits') or '').strip()
    out = []
    errs = []
    for part in [p for p in raw.split(';') if p.strip()]:
        bits = [b.strip() for b in part.split(':')]
        if len(bits) < 2 or not bits[0]:
            errs.append(f'Benefit "{part.strip()}" should look like Transport:200:allowance')
            continue
        kind = (bits[2] if len(bits) > 2 else 'allowance').lower()
        if kind not in ('allowance', 'deduction'):
            errs.append(f'Benefit "{bits[0]}": kind should be allowance or deduction')
        try:
            amount = float(bits[1])
        except ValueError:
            errs.append(f'Benefit "{bits[0]}": amount "{bits[1]}" is not a number')
            continue
        out.append({'name': bits[0][:80], 'amount': str(amount if amount != int(amount) else int(amount)), 'kind': kind})
    clean['benefits'] = out
    rate = clean.get('tax_rate_percent')
    if rate is not None and not 0 <= rate <= 60:
        errs.append('Tax rate must be between 0 and 60')
    return errs


def _payroll_after_update(obj, clean, ctx):
    if '_benefits' in clean['_given']:
        obj.benefits = clean['benefits']
        obj.save()


def _payslip_validate(clean, ctx):
    if clean.get('month'):
        clean['month'] = clean['month'].replace(day=1)
    return []


# ---- leave ----------------------------------------------------------------------------------------------------------

def _leave_before(data, ctx):
    t = data['teacher']
    data['applicant_name'], data['applicant_email'] = t.full_name, t.email
    return data


def _leave_validate(clean, ctx):
    if clean.get('start_date') and clean.get('end_date') and clean['end_date'] < clean['start_date']:
        return ['End date is before the start date']
    if clean.get('day_part') in ('am', 'pm') and clean.get('start_date') != clean.get('end_date'):
        return ['A half day must start and end on the same day']
    return []


def install():
    register('fee_structure', model_kind(
        label='Fee structure', order=17, model='education_finance.FeeStructure', filename='fee_structure.csv', depends=['classes'],
        singular='fee',
        help='The fees each class is charged: name, amount, due date and how often. The class must already exist.',
        cols=[col('class', 'Class', 'ref', True, field='class_ref', ref='class', aliases=['classname', 'grade']),
              col('section', 'Section', field='_section_name', export=lambda o: o.section.name if o.section_id else ''),
              col('fee_name', 'Fee', required=True, aliases=['name', 'feename']), col('amount', 'Amount', 'money', True),
              col('due_date', 'Due date', 'date', True), col('academic_year', 'School year', aliases=['year']),
              col('recurring', 'Recurring (yes/no)', 'bool', field='is_recurring', default=False),
              col('frequency', 'Frequency', 'choice', choices={'monthly': 'Monthly', 'quarterly': 'Quarterly', 'yearly': 'Yearly'},
                  default='monthly')],
        key=['class', 'section', 'fee_name', 'academic_year'], validate=_fee_validate, order_by=('class_ref__name', 'fee_name'),
        queryset=lambda ctx: apps.get_model('education_finance', 'FeeStructure').objects.select_related('class_ref', 'section'),
        example=[['Grade 5', '', 'Tuition', '2500', '2026-09-10', '2026-27', 'yes', 'monthly']]))

    register('invoices', model_kind(
        label='Invoices', order=18, model='education_finance.Invoice', filename='invoices.csv', depends=['students'], singular='invoice',
        silent=True, after_create=_invoice_after_create,
        help='Fee invoices already issued. What was paid comes from the payments file, so import payments after invoices. '
             'Families are not notified when invoices are loaded this way.',
        cols=[col('invoice_number', 'Invoice number', required=True, aliases=['invoiceno', 'number']),
              col('student', 'Student number', 'ref', True, ref='student', aliases=['studentid', 'studentno']),
              col('invoice_type', 'Type', 'choice', choices=INVOICE_TYPES, default='tuition', aliases=['type']),
              col('amount', 'Amount', 'money', True), col('opening_balance', 'Balance brought forward', 'money', default=0),
              col('discount_amount', 'Discount', 'money', default=0, aliases=['discount']),
              col('late_fee_amount', 'Late fee', 'money', default=0, aliases=['latefee']),
              col('due_date', 'Due date', 'date', True), col('issue_date', 'Issue date', 'date', field='_issue_date',
                                                                export=lambda o: o.issue_date),
              col('invoice_month', 'Invoice month', 'date', aliases=['month']),
              col('status', 'Status', 'choice', choices=INVOICE_STATUS, default='issued'), col('description', 'Description', aliases=['details'])],
        key=['invoice_number'], validate=_invoice_validate, order_by=('invoice_number',),
        queryset=lambda ctx: apps.get_model('education_finance', 'Invoice').objects.select_related('student'),
        no_update=('invoice_number', 'student'),
        example=[['INV-2026-09-0001', 'DS-2026001', 'tuition', '2500', '0', '0', '0', '2026-09-10', '2026-09-01', '2026-09-01', 'issued', 'September fees']]))

    register('payments', model_kind(
        label='Payments', order=19, model='education_finance.Payment', filename='payments.csv', depends=['invoices'], singular='payment',
        silent=True, after_create=_payment_after_create, validate=_payment_validate,
        help='Money received against invoices. Each payment needs the invoice number, the amount and a reference (receipt or '
             'transaction number). A payment cannot be more than the invoice still owes.',
        cols=[col('invoice', 'Invoice number', 'ref', True, ref='invoice', aliases=['invoiceno']),
              col('reference', 'Receipt reference', field='transaction_id', aliases=['receipt', 'transactionid', 'receiptno'], export=_payment_ref),
              col('amount', 'Amount', 'money', True), col('payment_date', 'Date paid', 'date', field='_paid_on', export=lambda o: o.payment_date),
              col('payment_method', 'Method', 'choice', choices=PAY_METHODS, default='cash', aliases=['method']), col('notes', 'Notes')],
        key=['invoice', 'reference'], order_by=('invoice__invoice_number', 'created_at'),
        queryset=lambda ctx: apps.get_model('education_finance', 'Payment').objects.select_related('invoice'),
        example=[['INV-2026-09-0001', 'RCPT-1001', '2500', '2026-09-05', 'bank_transfer', '']]))

    register('pay_grades', model_kind(
        label='Pay grades', order=9, model='education_hr.PayGrade', filename='pay_grades.csv', singular='pay grade',
        help='Salary bands for staff, for example Teacher Level 2.',
        cols=[col('name', 'Pay grade', required=True, aliases=['grade']), col('base_salary', 'Monthly base salary', 'money', True, aliases=['salary']),
              col('notes', 'Notes')],
        key=['name'], order_by=('base_salary', 'name'), example=[['Teacher Level 2', '4200', 'Five or more years']]))

    register('payroll_profiles', model_kind(
        label='Staff pay set-up', order=21, model='education_hr.PayrollProfile', filename='payroll_profiles.csv', depends=['staff', 'pay_grades'],
        singular='pay set-up',
        help='Each person\'s pay grade, tax withholding percentage and benefits. Benefits look like Transport:200:allowance; Health plan:100:deduction.',
        cols=[col('employee', 'Employee number', 'ref', True, field='teacher', ref='teacher', aliases=['employeeid', 'staff']),
              col('pay_grade', 'Pay grade', 'ref', ref='paygrade', aliases=['grade']),
              col('tax_rate_percent', 'Tax withheld %', 'decimal', default=0, aliases=['tax', 'taxrate']),
              col('benefits', 'Benefits', field='_benefits', export=_benefits_text)],
        key=['employee'], validate=_payroll_validate, after_update=_payroll_after_update, order_by=('teacher__employee_id',),
        example=[['EMP-001', 'Teacher Level 2', '10', 'Transport:200:allowance; Health plan:100:deduction']]))

    register('payslips', model_kind(
        label='Salary payslips', order=22, model='education_finance.Payslip', filename='payslips.csv', depends=['staff'], singular='payslip',
        help='Monthly salary records. Net pay is worked out for you: basic + allowances - deductions.',
        cols=[col('employee', 'Employee number', 'ref', True, field='employee', ref='teacher', aliases=['employeeid', 'staff']),
              col('month', 'Month (first day)', 'date', True), col('basic_salary', 'Basic salary', 'money', True, aliases=['basic']),
              col('allowances', 'Allowances', 'money', default=0), col('deductions', 'Deductions', 'money', default=0),
              col('paid_amount', 'Paid so far', 'money', default=0, aliases=['paid']),
              col('payment_date', 'Date paid', 'date'), col('payment_method', 'Payment method'), col('notes', 'Notes')],
        key=['employee', 'month'], validate=_payslip_validate, order_by=('month', 'employee__employee_id'),
        queryset=lambda ctx: apps.get_model('education_finance', 'Payslip').objects.select_related('employee'),
        example=[['EMP-001', '2026-09-01', '4200', '200', '420', '0', '', '', '']]))

    leave_keys = [('sick', 'Sick days', 'sick_entitlement'), ('casual', 'Casual days', 'casual_entitlement'),
                  ('annual', 'Annual days', 'annual_type_entitlement'), ('personal', 'Personal days', 'personal_entitlement'),
                  ('bereavement', 'Bereavement days', 'bereavement_entitlement'), ('jury', 'Jury duty days', 'jury_entitlement'),
                  ('professional', 'Professional development days', 'professional_entitlement'), ('maternity', 'Maternity days', 'maternity_entitlement'),
                  ('emergency', 'Emergency days', 'emergency_entitlement'), ('other', 'Other days', 'other_entitlement')]
    register('leave_balances', model_kind(
        label='Leave allowances', order=23, model='education_academics.LeaveBalance', filename='leave_allowances.csv', depends=['staff'],
        singular='leave allowance',
        help='How many days of each kind of leave a person has per year, plus any days carried over from last year.',
        cols=[col('employee', 'Employee number', 'ref', True, field='teacher', ref='teacher', aliases=['employeeid', 'staff'])]
             + [col(k, label, 'int', default=0, field=f) for k, label, f in leave_keys]
             + [col('carried_over', 'Carried over days', 'int', default=0, field='carried_over_days')],
        key=['employee'], order_by=('teacher__employee_id',),
        queryset=lambda ctx: apps.get_model('education_academics', 'LeaveBalance').objects.filter(teacher__isnull=False).select_related('teacher'),
        example=[['EMP-001', '5', '5', '15', '3', '3', '', '', '', '', '', '2']]))

    register('leave_requests', model_kind(
        label='Leave requests', order=24, model='education_academics.TeacherLeave', filename='leave_requests.csv', depends=['staff'],
        singular='leave request',
        help='Leave taken or booked. Loading approved leave records it only; it does not arrange substitute cover.',
        cols=[col('employee', 'Employee number', 'ref', True, field='teacher', ref='teacher', aliases=['employeeid', 'staff']),
              col('leave_type', 'Type', 'choice', True, choices=LEAVE_TYPES, aliases=['type']),
              col('start_date', 'First day', 'date', True, aliases=['start']), col('end_date', 'Last day', 'date', True, aliases=['end']),
              col('day_part', 'Day part', 'choice', choices=DAY_PARTS, default='full'),
              col('status', 'Status', 'choice', choices=LEAVE_STATUS, default='approved'), col('reason', 'Reason')],
        key=['employee', 'start_date', 'end_date'], validate=_leave_validate, before_create=_leave_before, order_by=('start_date', 'teacher__employee_id'),
        queryset=lambda ctx: apps.get_model('education_academics', 'TeacherLeave').objects.filter(teacher__isnull=False).select_related('teacher'),
        example=[['EMP-001', 'sick', '2026-10-05', '2026-10-06', 'full', 'approved', 'Flu']]))
