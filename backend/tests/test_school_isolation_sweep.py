"""School isolation, checked by machine.

1. Every model that carries a link to a school must either be in the isolation registry (tenants/registry.py), which filters
   it to the signed-in school automatically, or be on the reviewed list below with the reason it is safe. A new model with a
   school link that is neither fails this test, so nothing can be added to the app without a decision about who may see it.
2. The areas found by that review as not filtered are tested across two real schools (employee tasks, timesheets and documents).
"""
import datetime

import pytest
from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from services.core.tenants.registry import DIRECT, THROUGH_PARENT
from services.core.tenants.signup import create_school_with_admin

# Reviewed: these have a school link and are deliberately not auto-filtered. Each is only reached through code that filters by the
# school (or the person) itself, or is platform-level data that only the platform owner sees.
REVIEWED = {
    'user_notifications.Notification': 'always read by recipient (the signed-in person)',
    'audit.AuditLog': 'the audit screen filters by school; platform owner sees all',
    'core_tenants.TenantMembership': 'the school and platform consoles filter by school',
    'core_features.FeatureFlag': 'platform feature switches; school admins only read their own school through services.py',
    'core_security.SignInEvent': 'security screens filter by school',
    'core_security.EmailLog': 'security screens filter by school; retention deletes by school',
    'core_billing.Subscription': 'platform billing; a school sees only its own through services',
    'core_billing.SubscriptionEvent': 'platform billing',
    'core_billing.PlatformInvoice': 'a school sees only its own (filtered by request.tenant); platform owner sees all',
    'core_portability.SchoolExport': 'school data-pack screens filter by school',
    'core_portability.SchoolDeletion': 'platform console',
    'core_privacy.LegalDocument': 'a school sees its own notice and the platform documents',
    'core_privacy.ConsentType': 'the privacy screens filter by school',
    'core_privacy.ConsentRecord': 'the privacy screens filter by school',
    'core_privacy.PrivacyRequest': 'the privacy screens filter by request.tenant',
    'core_privacy.DataHandlingEntry': 'the register screen filters by request.tenant (tests/test_data_register.py: another school sees none and cannot delete)',
    'core_support.SupportTicket': 'the support screens filter by school',
    'ai.AIActionEffect': 'reached only through its request, which every AI screen filters by the signed-in school',
    'analytics.RiskScanRun': 'listed only through the risk model card and scan screens, which filter by the signed-in school',
    'behaviour.BehaviourPattern': 'has the school-aware default manager and is read through a student the person may see',
}


def _school_links(model):
    for f in model._meta.concrete_fields:
        if f.is_relation and f.related_model is not None and f.related_model._meta.label == 'core_tenants.School':
            yield f.name


def test_every_model_with_a_school_link_is_filtered_or_reviewed():
    registered = set(DIRECT) | set(THROUGH_PARENT)
    unknown = sorted(f'{m._meta.label} ({", ".join(_school_links(m))})' for m in apps.get_models()
                     if list(_school_links(m)) and m._meta.label not in registered and m._meta.label not in REVIEWED)
    assert not unknown, ('These models carry a school link but are neither in tenants/registry.py nor on the reviewed list in '
                         'this test. Add them to the registry (so they are filtered automatically) or review and list them: '
                         + '; '.join(unknown))


def test_the_reviewed_list_has_no_stale_entries():
    labels = {m._meta.label for m in apps.get_models()}
    assert [k for k in REVIEWED if k not in labels] == []
    assert [k for k in REVIEWED if k in set(DIRECT) | set(THROUGH_PARENT)] == []     # registered ones do not need a review note


def _school(name, email):
    school, admin = create_school_with_admin(school_name=name, admin_email=email, admin_name=name + ' Head', password='Sturdy-Pass-91x')
    api = APIClient()
    res = api.post('/api/v1/auth/login/', {'email': email, 'password': 'Sturdy-Pass-91x'}, format='json')
    assert res.status_code == 200, res.content
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.json()['access']}")
    return school, admin, api


@pytest.fixture
def two(db):
    return _school('Alder Academy', 'head@alder.test'), _school('Birch Academy', 'head@birch.test')


@pytest.mark.django_db
class TestEmployeeAreas:
    def test_tasks_of_one_school_are_invisible_to_the_other(self, two):
        (a, admin_a, api_a), (b, admin_b, api_b) = two
        made = api_a.post('/api/v1/auth/employee/tasks/', {'title': 'Order new desks', 'priority': 'high'}, format='json')
        assert made.status_code == 201, made.content
        task_id = made.json()['id']
        assert [t['title'] for t in api_a.get('/api/v1/auth/employee/tasks/').json().get('results', api_a.get('/api/v1/auth/employee/tasks/').json())] == ['Order new desks']
        listed = api_b.get('/api/v1/auth/employee/tasks/').json()
        assert (listed.get('results', listed)) == []
        assert api_b.get(f'/api/v1/auth/employee/tasks/{task_id}/').status_code == 404
        assert api_b.patch(f'/api/v1/auth/employee/tasks/{task_id}/', {'title': 'Hijacked'}, format='json').status_code == 404
        assert api_b.delete(f'/api/v1/auth/employee/tasks/{task_id}/').status_code == 404
        assert api_a.get(f'/api/v1/auth/employee/tasks/{task_id}/').json()['title'] == 'Order new desks'

    def test_timesheets_of_one_school_are_invisible_to_the_other(self, two):
        (a, admin_a, api_a), (b, admin_b, api_b) = two
        made = api_a.post('/api/v1/auth/employee/timesheets/', {'employee': str(admin_a.pk), 'date': datetime.date.today().isoformat(), 'hours_worked': '7.5'}, format='json')
        assert made.status_code == 201, made.content
        sheet_id = made.json()['id']
        listed = api_b.get('/api/v1/auth/employee/timesheets/').json()
        assert (listed.get('results', listed)) == []
        assert api_b.get(f'/api/v1/auth/employee/timesheets/{sheet_id}/').status_code == 404
        assert api_b.delete(f'/api/v1/auth/employee/timesheets/{sheet_id}/').status_code == 404

    def test_documents_of_one_school_are_invisible_to_the_other(self, two):
        (a, admin_a, api_a), (b, admin_b, api_b) = two
        made = api_a.post('/api/v1/auth/employee/documents/', {'owner': str(admin_a.pk), 'title': 'Contract', 'file': SimpleUploadedFile('c.pdf', b'%PDF-1.4 x')}, format='multipart')
        assert made.status_code == 201, made.content
        doc_id = made.json()['id']
        listed = api_b.get('/api/v1/auth/employee/documents/').json()
        assert (listed.get('results', listed)) == []
        assert api_b.get(f'/api/v1/auth/employee/documents/{doc_id}/').status_code == 404
        assert api_b.delete(f'/api/v1/auth/employee/documents/{doc_id}/').status_code == 404

    def test_a_colleague_cannot_open_someone_elses_task_by_id(self, two):
        from django.contrib.auth import get_user_model
        from services.core.tenants.models import TenantMembership

        (a, admin_a, api_a), _ = two
        task_id = api_a.post('/api/v1/auth/employee/tasks/', {'title': 'Salary review'}, format='json').json()['id']
        colleague = get_user_model().objects.create_user(email='teacher@alder.test', password='Sturdy-Pass-91x', full_name='Tess')
        TenantMembership.objects.create(user=colleague, school=a, role='staff', is_active=True, is_primary=True)
        other = APIClient()
        token = other.post('/api/v1/auth/login/', {'email': 'teacher@alder.test', 'password': 'Sturdy-Pass-91x'}, format='json').json()['access']
        other.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        assert other.get(f'/api/v1/auth/employee/tasks/{task_id}/').status_code == 404
        assert other.delete(f'/api/v1/auth/employee/tasks/{task_id}/').status_code == 404
