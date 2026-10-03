"""Small builders shared by the front desk, health office, incident, forms and admissions tests."""
from django.apps import apps
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.tenants.context import use_tenant
from services.core.tenants.models import TenantMembership
from tests.conftest import SchoolFactory, StudentFactory, UserFactory


def api(user=None):
    c = APIClient()
    if user is not None:
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def rows(response):
    data = response.json()
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def make_user(school, email, role):
    """role: admin | front_desk | nurse | teacher | staff | parent (a parent is linked to students afterwards)."""
    user = UserFactory(email=email, full_name=email.split('@')[0].replace('.', ' ').title())
    if role == 'admin':
        TenantMembership.objects.create(user=user, school=school, role='admin', is_primary=True)
    elif role == 'parent':
        TenantMembership.objects.create(user=user, school=school, role='parent', is_primary=True)
        apps.get_model('core_accounts', 'ParentProfile').objects.create(user=user)
    else:
        TenantMembership.objects.create(user=user, school=school, role='staff', is_primary=True)
        Role = apps.get_model('rbac_models', 'Role')
        Profile = apps.get_model('core_accounts', 'UserProfile')
        named, _ = Role.objects.get_or_create(name=role)
        Profile.objects.get_or_create(user=user, defaults={'role': named})
    return user


def make_student(school, **kw):
    kw.setdefault('current_class', None)
    kw.setdefault('current_section', None)
    kw.setdefault('is_active', True)
    return StudentFactory(tenant=school, **kw)


def link_parent(user, student):
    user.parent_profile.linked_students.add(student)


def make_guardian(school, student, first='Mary', last='Smith', can_pickup=True, notes=''):
    Guardian = apps.get_model('education_students', 'Guardian')
    Link = apps.get_model('education_students', 'StudentGuardian')
    with use_tenant(school):
        g = Guardian.objects.create(tenant=school, first_name=first, last_name=last, relationship='mother', mobile_phone='555-0101')
        Link.objects.create(tenant=school, student=student, guardian=g, can_pickup=can_pickup, custody_notes=notes)
    return g


def two_schools():
    return SchoolFactory(name='Maple Grove Academy'), SchoolFactory(name='Other School')


def student_login(school, email):
    """A real student login. Creating a Student with an email creates its portal account, so find that user."""
    from django.contrib.auth import get_user_model
    make_student(school, email=email)
    return get_user_model().objects.get(email=email)
