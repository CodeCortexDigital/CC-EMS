"""Fee documents belong to one family: a receipt or invoice PDF is only for the people it is about, and the school-wide
finance reports are for the office. (A demo audit found these answered to any signed-in user.)"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.accounts.models import ParentProfile
from services.core.tenants.context import use_tenant
from services.core.tenants.models import TenantMembership
from services.education.finance.models import Invoice, Payment
from tests.conftest import SchoolFactory, StudentFactory, UserFactory

BASE = '/api/v1/auth/finance'
KW = dict(father_name='', mother_name='', guardian_name='', guardian_phone='')


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


@pytest.fixture
def fam(db):
    s = SchoolFactory(name='Fee School')
    admin = UserFactory(email='office@fee.test')
    TenantMembership.objects.create(user=admin, school=s, role='admin', is_primary=True)
    amy = StudentFactory(tenant=s, full_name='Amy', email='amy@fee.test', **KW)
    ben = StudentFactory(tenant=s, full_name='Ben', email='ben@fee.test', **KW)
    pa, pb = UserFactory(email='pa@fee.test'), UserFactory(email='pb@fee.test')
    ParentProfile.objects.create(user=pa).linked_students.add(amy)
    ParentProfile.objects.create(user=pb).linked_students.add(ben)
    # Adding a student already creates their portal login; reuse it.
    amy_user, ben_user = (get_user_model().objects.filter(email=e).first() or UserFactory(email=e) for e in ('amy@fee.test', 'ben@fee.test'))
    for u in (amy_user, ben_user):
        TenantMembership.objects.get_or_create(user=u, school=s, defaults={'role': 'student', 'is_primary': True})
    with use_tenant(s):
        ia = Invoice.objects.create(student=amy, amount=Decimal('500'), due_date=timezone.localdate() + timedelta(days=5), status='issued', invoice_type='tuition')
        ib = Invoice.objects.create(student=ben, amount=Decimal('700'), due_date=timezone.localdate() + timedelta(days=5), status='issued', invoice_type='tuition')
        pay_a = Payment.objects.create(invoice=ia, amount=Decimal('100'), payment_method='cash')
        pay_b = Payment.objects.create(invoice=ib, amount=Decimal('100'), payment_method='cash')
    return dict(s=s, admin=_client(admin), pa=_client(pa), pb=_client(pb), amy=_client(amy_user), ben=_client(ben_user),
                ia=ia, ib=ib, pay_a=pay_a, pay_b=pay_b)


@pytest.mark.django_db
class TestOneFamilysDocuments:
    def test_a_family_opens_its_own_invoice_and_receipt_and_pdf(self, fam):
        assert fam['pa'].get(f"{BASE}/invoices/{fam['ia'].id}/receipt/").status_code == 200
        assert fam['pa'].get(f"{BASE}/payments/{fam['pay_a'].id}/receipt/").status_code == 200
        assert fam['pa'].get(f"{BASE}/reports/invoice/{fam['ia'].id}/pdf/")['Content-Type'] == 'application/pdf'

    def test_another_family_gets_nothing(self, fam):
        for url in (f"/invoices/{fam['ia'].id}/receipt/", f"/payments/{fam['pay_a'].id}/receipt/", f"/reports/invoice/{fam['ia'].id}/pdf/"):
            assert fam['pb'].get(BASE + url).status_code == 404, url
        # Nor does a student see a classmate's fees.
        assert fam['ben'].get(f"{BASE}/invoices/{fam['ia'].id}/receipt/").status_code == 404
        assert fam['ben'].get(f"{BASE}/invoices/{fam['ib'].id}/receipt/").status_code == 200

    def test_the_office_sees_every_family(self, fam):
        assert fam['admin'].get(f"{BASE}/invoices/{fam['ia'].id}/receipt/").status_code == 200
        assert fam['admin'].get(f"{BASE}/invoices/{fam['ib'].id}/receipt/").status_code == 200


@pytest.mark.django_db
class TestSchoolWideReports:
    PATHS = ('/reports/pdf/', '/reports/defaulters/pdf/', '/reports/monthly/pdf/')

    def test_only_finance_staff_get_them(self, fam):
        for path in self.PATHS:
            for who in ('pa', 'amy'):
                assert fam[who].get(BASE + path).status_code == 403, (who, path)
            res = fam['admin'].get(BASE + path)
            assert res.status_code == 200 and res['Content-Type'] == 'application/pdf', path

    def test_a_missing_pdf_library_is_not_a_crash(self, fam, monkeypatch):
        import builtins

        real = builtins.__import__

        def no_reportlab(name, *a, **k):
            if name.startswith('reportlab'):
                raise ImportError(name)
            return real(name, *a, **k)

        monkeypatch.setattr(builtins, '__import__', no_reportlab)
        res = fam['admin'].get(BASE + '/reports/pdf/')
        assert res.status_code == 503 and 'not available' in res.json()['error']


@pytest.mark.django_db
class TestLegacyPdfRoutes:
    """/auth/pdf/... (the older result card and fee receipt downloads) follow the same rule."""

    def test_result_card_is_only_for_the_childs_own_family(self, fam):
        from services.education.students.models import Student

        with use_tenant(fam['s']):
            amy = Student.objects.get(full_name='Amy')
        url = f'/api/v1/auth/pdf/result-card/{amy.id}/'
        assert fam['pb'].get(url).status_code == 404 and fam['ben'].get(url).status_code == 404
        assert fam['pa'].get(url).status_code == 200 and fam['amy'].get(url).status_code == 200
        assert fam['admin'].get(url).status_code == 200

    def test_fee_receipt_is_only_for_the_invoices_own_family(self, fam):
        url = f"/api/v1/auth/pdf/fee-receipt/{fam['ia'].id}/"
        assert fam['pb'].get(url).status_code == 404 and fam['ben'].get(url).status_code == 404
        assert fam['pa'].get(url).status_code == 200
        assert fam['admin'].get(url).status_code == 200
