"""Invoices made through the API must bill something, and a student is not billed the same month's tuition twice."""
from datetime import date

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.tenants.models import TenantMembership
from tests.conftest import SchoolFactory, StudentFactory, UserFactory

URL = '/api/v1/auth/finance/invoices/'
pytestmark = pytest.mark.django_db


@pytest.fixture
def office():
    s = SchoolFactory(name='Invoice Rules School')
    admin = UserFactory(email='office@rules-invoice.test')
    TenantMembership.objects.create(user=admin, school=s, role='admin', is_primary=True)
    kw = dict(father_name='', mother_name='', guardian_name='', guardian_phone='')
    student = StudentFactory(tenant=s, full_name='Ivy Invoice', **kw)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(admin).access_token}')
    return c, student


def body(student, **extra):
    return {'student': str(student.id), 'amount': '1200', 'due_date': '2026-10-12', 'invoice_month': '2026-10-01', 'invoice_type': 'tuition',
            'status': 'issued', **extra}


def test_an_invoice_for_nothing_is_refused(office):
    c, student = office
    r = c.post(URL, body(student, amount='0'), format='json')
    assert r.status_code == 400 and 'more than zero' in str(r.json())


def test_a_balance_brought_forward_alone_is_a_valid_invoice(office):
    c, student = office
    assert c.post(URL, body(student, amount='0', opening_balance='300', invoice_type='miscellaneous'), format='json').status_code == 201


def test_the_same_months_tuition_is_not_billed_twice(office):
    c, student = office
    first = c.post(URL, body(student), format='json')
    assert first.status_code == 201, first.content
    again = c.post(URL, body(student), format='json')
    assert again.status_code == 400 and 'already has a tuition invoice for October 2026' in str(again.json())
    # Another month, or another kind of invoice, is fine.
    assert c.post(URL, body(student, invoice_month='2026-11-01', due_date='2026-11-12'), format='json').status_code == 201
    assert c.post(URL, body(student, invoice_type='transport'), format='json').status_code == 201
