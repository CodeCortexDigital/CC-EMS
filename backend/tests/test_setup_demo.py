"""`setup_demo`: a hosted demo has the sample US school and the four demo accounts, and nothing else."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from services.core.tenants.context import use_tenant
from services.core.tenants.models import School, TenantMembership
from services.education.students.models import Student
from tests.conftest import SchoolFactory, StudentFactory, UserFactory

pytestmark = pytest.mark.django_db
DEMO = {'admin@code.com', 'teacher@code.com', 'parent@code.com', 'student@code.com'}


def test_it_refuses_to_run_on_the_live_site(settings):
    settings.APP_ENV = 'production'
    with pytest.raises(CommandError):
        call_command('setup_demo')


def test_reset_leaves_only_the_demo_school_and_the_demo_accounts(settings, monkeypatch):
    settings.APP_ENV = 'staging'
    # An old site with its own school, a student and a platform owner.
    old = SchoolFactory(name='Old Test School')
    StudentFactory(tenant=old, full_name='Old Student', father_name='', mother_name='', guardian_name='', guardian_phone='')
    owner = UserFactory(email='owner@old.test', is_superuser=True, is_staff=True)
    TenantMembership.objects.create(user=owner, school=old, role='admin', is_primary=True)

    monkeypatch.setenv('DEMO_RESET', '1')
    call_command('setup_demo')

    assert set(School.objects.exclude(tenant_code='DEF').values_list('tenant_code', flat=True)) == {'MGA'}
    assert not get_user_model().objects.filter(email='owner@old.test').exists()
    assert not School.objects.filter(name='Old Test School').exists()
    school = School.objects.get(tenant_code='MGA')
    with use_tenant(school):
        assert Student.objects.count() == 214
    assert DEMO <= set(get_user_model().objects.values_list('email', flat=True))
    assert get_user_model().objects.get(email='admin@code.com').check_password('Admin@123')
    assert not Student.all_objects.filter(full_name='Old Student').exists()

    # Running it again (a restart) changes nothing and does not wipe anything.
    monkeypatch.delenv('DEMO_RESET')
    before = get_user_model().objects.count()
    call_command('setup_demo')
    assert get_user_model().objects.count() == before
    with use_tenant(school):
        assert Student.objects.count() == 214
