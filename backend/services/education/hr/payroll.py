"""Pay setup: grades, tax withholding and benefits, and the calculation payslip generation uses.

Mounted under ``/api/v1/auth/hr/payroll/``. Only administrators and the HR role may see or change any of it.
This builds the figures a payslip starts from; it is not tax-filing software, so withholding is a flat percentage
the school sets per person.
"""
from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from services.education.academics.models import Teacher

from .access import err, is_payroll
from .models import PayGrade, PayrollProfile

CENT = Decimal('0.01')


class IsPayroll(BasePermission):
    message = 'Only administrators and HR can see or change pay.'

    def has_permission(self, request, view):
        return is_payroll(request.user)


def compute_pay(teacher, profile='lookup'):
    """What a payslip for this person starts from: basic, allowances, deductions (tax included) and net."""
    if profile == 'lookup':
        profile = PayrollProfile.objects.filter(teacher=teacher).select_related('pay_grade').first()
    basic = Decimal('0')
    if profile and profile.pay_grade_id:
        basic = profile.pay_grade.base_salary
    elif teacher.monthly_salary is not None:
        basic = teacher.monthly_salary
    allowances = deductions = Decimal('0')
    for b in (profile.benefits if profile else []) or []:
        amount = Decimal(str(b.get('amount') or 0))
        if b.get('kind') == 'deduction':
            deductions += amount
        else:
            allowances += amount
    tax = ((basic + allowances) * (profile.tax_rate_percent if profile else Decimal('0')) / Decimal('100')).quantize(CENT)
    return {'basic': basic, 'allowances': allowances, 'benefit_deductions': deductions, 'tax': tax,
            'deductions': deductions + tax, 'net': basic + allowances - deductions - tax}


class GradeSerializer(serializers.ModelSerializer):
    people = serializers.SerializerMethodField()

    class Meta:
        model = PayGrade
        exclude = ['tenant']

    def get_people(self, obj):
        return obj.profiles.count()

    def validate_name(self, v):
        clash = PayGrade.objects.filter(name__iexact=v.strip())
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError('There is already a grade with that name.')
        return v.strip()

    def validate_base_salary(self, v):
        if v < 0:
            raise serializers.ValidationError('Salary cannot be negative.')
        return v


class GradeList(generics.ListCreateAPIView):
    permission_classes = [IsPayroll]
    serializer_class = GradeSerializer
    queryset = PayGrade.objects.all()


class GradeDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsPayroll]
    serializer_class = GradeSerializer
    queryset = PayGrade.objects.all()


def _clean_benefits(raw):
    if not isinstance(raw, list):
        raise ValueError('Benefits must be a list.')
    out = []
    for b in raw:
        name = str((b or {}).get('name') or '').strip()
        if not name:
            raise ValueError('Every benefit needs a name.')
        kind = (b or {}).get('kind') or 'allowance'
        if kind not in ('allowance', 'deduction'):
            raise ValueError('A benefit is either an allowance or a deduction.')
        try:
            amount = Decimal(str(b.get('amount'))).quantize(CENT)
        except (InvalidOperation, TypeError):
            raise ValueError(f'"{name}" needs an amount.')
        if amount < 0:
            raise ValueError(f'"{name}" cannot be negative.')
        out.append({'name': name[:80], 'amount': str(amount), 'kind': kind})
    return out


def _row(teacher, profile):
    pay = compute_pay(teacher, profile)
    return {
        'teacher_id': str(teacher.id), 'name': teacher.full_name, 'employee_id': teacher.employee_id,
        'role': teacher.role, 'department': teacher.department,
        'pay_grade': str(profile.pay_grade_id) if profile and profile.pay_grade_id else None,
        'pay_grade_name': profile.pay_grade.name if profile and profile.pay_grade_id else '',
        'tax_rate_percent': float(profile.tax_rate_percent) if profile else 0,
        'benefits': profile.benefits if profile else [],
        'monthly_salary': float(teacher.monthly_salary) if teacher.monthly_salary is not None else None,
        **{k: float(v) for k, v in pay.items()},
    }


@api_view(['GET'])
@permission_classes([IsPayroll])
def profiles(request):
    """Every active staff member with the pay figures a payslip would start from."""
    by_teacher = {p.teacher_id: p for p in PayrollProfile.objects.select_related('pay_grade')}
    return Response([_row(t, by_teacher.get(t.id)) for t in Teacher.objects.filter(is_active=True).order_by('full_name')])


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsPayroll])
def profile(request, teacher_id):
    teacher = get_object_or_404(Teacher, pk=teacher_id)
    prof = PayrollProfile.objects.filter(teacher=teacher).select_related('pay_grade').first()
    if request.method == 'GET':
        return Response(_row(teacher, prof))
    d = request.data
    prof = prof or PayrollProfile(teacher=teacher)
    if 'pay_grade' in d:
        if d['pay_grade']:
            prof.pay_grade = get_object_or_404(PayGrade, pk=d['pay_grade'])
        else:
            prof.pay_grade = None
    if 'tax_rate_percent' in d:
        try:
            rate = Decimal(str(d['tax_rate_percent']))
        except InvalidOperation:
            return err('Tax rate must be a number.')
        if not Decimal('0') <= rate <= Decimal('60'):
            return err('Tax rate must be between 0 and 60 percent.')
        prof.tax_rate_percent = rate
    if 'benefits' in d:
        try:
            prof.benefits = _clean_benefits(d['benefits'])
        except ValueError as e:
            return err(str(e))
    prof.save()
    prof = PayrollProfile.objects.select_related('pay_grade').get(pk=prof.pk)
    return Response(_row(teacher, prof))
