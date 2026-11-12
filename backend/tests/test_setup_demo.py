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
        assert Student.objects.count() == 83
    assert DEMO <= set(get_user_model().objects.values_list('email', flat=True))
    assert get_user_model().objects.get(email='admin@code.com').check_password('Admin@123')
    assert not Student.all_objects.filter(full_name='Old Student').exists()

    # Running it again (a restart) changes nothing and does not wipe anything.
    monkeypatch.delenv('DEMO_RESET')
    before = get_user_model().objects.count()
    call_command('setup_demo')
    assert get_user_model().objects.count() == before
    with use_tenant(school):
        assert Student.objects.count() == 83


def test_a_named_administrator_replaces_the_public_ones(settings):
    from services.core.accounts.models import User
    from services.education.imports.management.commands.setup_demo import add_demo_admin, pack_code

    assert pack_code('jp-school') == 'WKG' and pack_code('us-school') == 'MGA'
    school = SchoolFactory(name='Client School')
    public = UserFactory(email='admin@code.com')
    TenantMembership.objects.create(user=public, school=school, role='admin', is_primary=True)
    add_demo_admin(school, 'client@admin.test', 'a-private-password', 'Client Admin')
    user = User.objects.get(email='client@admin.test')
    assert user.check_password('a-private-password') and user.account_status == User.AccountStatus.ACTIVE
    member = TenantMembership.objects.get(user=user, school=school)
    assert member.role == 'admin' and member.is_primary
    assert not user.is_superuser
    assert User.objects.get(email='admin@code.com').account_status == User.AccountStatus.INACTIVE
    add_demo_admin(school, 'client@admin.test', 'a-new-password', '')          # a restart with a changed password
    assert User.objects.get(email='client@admin.test').check_password('a-new-password')
    assert TenantMembership.objects.filter(user=user, school=school).count() == 1


def test_an_admin_email_without_a_password_is_refused(settings, monkeypatch):
    settings.APP_ENV = 'staging'
    monkeypatch.setenv('DEMO_ADMIN_EMAIL', 'client@admin.test')
    monkeypatch.delenv('DEMO_ADMIN_PASSWORD', raising=False)
    with pytest.raises(CommandError):
        call_command('setup_demo')


def test_a_japanese_school_joins_existing_schools_with_its_own_administrator(settings):
    """The multi-school case: one database, schools that already exist, and a Japanese school added next to them."""
    from tests.safety_helpers import api, rows

    settings.APP_ENV = 'staging'
    existing = SchoolFactory(name='Maple Grove Academy', tenant_code='MGA')
    head = UserFactory(email='admin@code.com')
    TenantMembership.objects.create(user=head, school=existing, role='admin', is_primary=True)
    StudentFactory(tenant=existing, full_name='Existing Student', father_name='', mother_name='', guardian_name='', guardian_phone='', is_active=True)

    call_command('add_demo_school', '--pack', 'jp-school', '--admin-email', 'masato@admin.test', '--admin-password', 'a-private-password-1', '--admin-name', 'Masato Yamano')

    jp = School.objects.get(tenant_code='WKG')
    assert jp.settings_json['region'] == 'jp' and jp.settings_json['currency'] == 'JPY' and jp.settings_json['language'] == 'ja'
    # Masato is the administrator of the Japanese school only; the public administrator still has the school he had, untouched.
    masato = get_user_model().objects.get(email='masato@admin.test')
    assert masato.check_password('a-private-password-1') and not masato.is_superuser
    assert list(TenantMembership.objects.filter(user=masato).values_list('school__tenant_code', 'role', 'is_primary')) == [('WKG', 'admin', True)]
    assert list(TenantMembership.objects.filter(user=head).values_list('school__tenant_code', 'role', 'is_primary')) == [('MGA', 'admin', True)]
    assert get_user_model().objects.get(email='admin@code.com').account_status == 'active'
    # Each school sees only its own people.
    with use_tenant(jp):
        assert Student.objects.count() == 109 and not Student.objects.filter(full_name='Existing Student').exists()
    with use_tenant(existing):
        assert list(Student.objects.values_list('full_name', flat=True)) == ['Existing Student']
    # ...also through the API, as each administrator.
    masato_names = {r['full_name'] for r in rows(api(masato).get('/api/v1/students/?page_size=500'))}
    head_names = {r['full_name'] for r in rows(api(head).get('/api/v1/students/?page_size=500'))}
    assert 'Existing Student' not in masato_names and len(masato_names) > 50
    assert head_names == {'Existing Student'}
    # Their own teacher, parent and student logins exist for that school; running it again changes nothing (no second school, no duplicates).
    assert get_user_model().objects.filter(email__in=['teacher@wakaba.example', 'parent@wakaba.example', 'student@wakaba.example']).count() == 3
    call_command('add_demo_school', '--pack', 'jp-school', '--admin-email', 'masato@admin.test', '--admin-password', 'a-private-password-1')
    assert School.objects.filter(tenant_code='WKG').count() == 1
    with use_tenant(jp):
        assert Student.objects.count() == 109
