"""Online admissions, review pipeline, enrolment and re-enrolment (Phase 2)."""
import json
from unittest import mock

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.tenants.models import TenantMembership
from services.education.admissions.models import Applicant, Application, ReEnrollmentResponse
from services.education.students.models import Student, StudentGuardian
from tests.conftest import ClassFactory, SchoolFactory, StudentFactory, UserFactory


def _client(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _admin(school):
    user = UserFactory(email=f'admin@{school.tenant_code.lower()}.test')
    TenantMembership.objects.create(user=user, school=school, role='admin', is_primary=True)
    return user


FORM = {
    'first_name': 'Maya', 'last_name': 'Brooks', 'date_of_birth': '2017-03-14', 'gender': 'female',
    'applying_for_class': 'Grade 3', 'city': 'Austin', 'country': 'United States',
    'medical_notes': 'Asthma (inhaler)',
    'guardians': [
        {'first_name': 'Erin', 'last_name': 'Brooks', 'relationship': 'mother', 'email': 'erin@example.com',
         'mobile_phone': '512-555-0100', 'receives_billing': True},
        {'first_name': 'Sam', 'last_name': 'Brooks', 'relationship': 'father', 'mobile_phone': '512-555-0101',
         'can_pickup': True},
    ],
    'signature_name': 'Erin Brooks', 'agree_declaration': True, 'agree_privacy': True, 'consent_photos': True,
}


@pytest.fixture
def school(db):
    s = SchoolFactory(name='Lakeside Academy')
    ClassFactory(school=s, name='Grade 3')
    return s


def _open_admissions(school):
    school.settings_json = {**(school.settings_json or {}), 'admissions': {'online_open': True, 'academic_year': '2027-2028'}}
    school.save()


@pytest.mark.django_db
def test_public_form_is_closed_until_the_school_opens_it(school):
    anon = _client()
    info = anon.get(f'/api/v1/auth/admissions/public/{school.subdomain}/').json()
    assert info['open'] is False and 'Grade 3' in info['classes']
    res = anon.post(f'/api/v1/auth/admissions/public/{school.subdomain}/apply/', {'data': json.dumps(FORM)})
    assert res.status_code == 403


@pytest.mark.django_db
def test_online_application_review_and_enrolment(school):
    _open_admissions(school)
    anon = _client()
    doc = SimpleUploadedFile('birth.pdf', b'%PDF-1.4 test', content_type='application/pdf')
    res = anon.post(f'/api/v1/auth/admissions/public/{school.subdomain}/apply/',
                    {'data': json.dumps(FORM), 'doc:Birth certificate': doc}, format='multipart')
    assert res.status_code == 201, res.content
    number, token = res.json()['application_no'], res.json()['tracking_token']

    status = anon.get('/api/v1/auth/admissions/public/status/', {'no': number, 'token': token}).json()
    assert status['status'] == 'pending' and status['student'] == 'Maya Brooks'
    assert anon.get('/api/v1/auth/admissions/public/status/', {'no': number, 'token': 'wrong'}).status_code == 404

    admin = _client(_admin(school))
    listing = admin.get('/api/v1/auth/admissions/applications/?source=online').json()
    rows = listing['results']
    assert len(rows) == 1 and listing['counts'] == {'pending': 1}
    app_id = rows[0]['id']
    detail = admin.get(f'/api/v1/auth/admissions/applications/{app_id}/').json()
    assert detail['documents'][0]['doc_type'] == 'Birth certificate'
    assert detail['signature_name'] == 'Erin Brooks' and detail['events'][0]['note'] == 'Submitted online'

    # Enrolling before acceptance is refused; invalid jumps are refused.
    assert admin.post(f'/api/v1/auth/admissions/applications/{app_id}/enroll/').status_code == 400
    assert admin.post(f'/api/v1/auth/admissions/applications/{app_id}/update-status/',
                      {'status': 'enrolled'}, format='json').status_code == 400
    assert admin.post(f'/api/v1/auth/admissions/applications/{app_id}/update-status/',
                      {'status': 'approved', 'note': 'Great interview'}, format='json').status_code == 200

    res = admin.post(f'/api/v1/auth/admissions/applications/{app_id}/enroll/', {}, format='json')
    assert res.status_code == 200, res.content
    student = Student.all_objects.get(pk=res.json()['student_uuid'])
    assert student.tenant_id == school.id and student.current_class.name == 'Grade 3'
    links = StudentGuardian.all_objects.filter(student=student).select_related('guardian').order_by('priority')
    assert [l.guardian.first_name for l in links] == ['Erin', 'Sam']
    assert links[0].is_primary and links[0].receives_billing
    assert student.household.name == 'Brooks family'
    assert student.health.medical_conditions == 'Asthma (inhaler)'
    assert Application.objects.get(pk=app_id).status == 'enrolled'
    assert admin.post(f'/api/v1/auth/admissions/applications/{app_id}/enroll/').status_code == 400
    assert anon.get('/api/v1/auth/admissions/public/status/', {'no': number, 'token': token}).json()['status'] == 'enrolled'


@pytest.mark.django_db
def test_only_admins_manage_admissions(school):
    teacher_like = _client(UserFactory(email='someone@example.com'))
    assert teacher_like.get('/api/v1/auth/admissions/applications/').status_code == 403
    assert teacher_like.put('/api/v1/auth/admissions/settings/', {'online_open': True}, format='json').status_code == 403


@pytest.mark.django_db
def test_settings_and_reenrollment(school):
    admin_user = _admin(school)
    admin = _client(admin_user)
    res = admin.put('/api/v1/auth/admissions/settings/', {
        'online_open': True, 'academic_year': '2027-2028', 'required_documents': 'Birth certificate\nPhoto',
    }, format='json')
    assert res.status_code == 200 and res.json()['required_documents'] == ['Birth certificate', 'Photo']
    assert res.json()['public_slug'] == school.subdomain

    kid = StudentFactory(tenant=school, full_name='Leo Park')
    StudentFactory(tenant=school, full_name='Old Kid', is_active=False)
    res = admin.post('/api/v1/auth/admissions/reenrollment/', {'title': 'Returning for 2027-28?', 'academic_year': '2027-2028'},
                     format='json')
    assert res.status_code == 201 and res.json()['total'] == 1  # only active students
    campaign_id = res.json()['id']

    parent = UserFactory(email='parent.park@example.com')
    from services.core.accounts.models import ParentProfile

    ParentProfile.objects.create(user=parent).linked_students.add(kid)
    mine = _client(parent).get('/api/v1/auth/admissions/reenrollment/mine/').json()
    assert len(mine) == 1 and mine[0]['student'] == 'Leo Park'
    rid = mine[0]['id']
    assert _client(parent).post(f'/api/v1/auth/admissions/reenrollment/responses/{rid}/respond/',
                                {'intent': 'returning'}, format='json').status_code == 400  # needs signature
    assert _client(parent).post(f'/api/v1/auth/admissions/reenrollment/responses/{rid}/respond/',
                                {'intent': 'returning', 'signature_name': 'Jin Park'}, format='json').status_code == 200
    stranger = _client(UserFactory(email='stranger@example.com'))
    assert stranger.post(f'/api/v1/auth/admissions/reenrollment/responses/{rid}/respond/',
                         {'intent': 'not_returning', 'signature_name': 'X'}, format='json').status_code in (403, 404)

    summary = admin.get(f'/api/v1/auth/admissions/reenrollment/{campaign_id}/').json()
    assert summary['counts']['returning'] == 1
    assert ReEnrollmentResponse.objects.get(pk=rid).signature_name == 'Jin Park'


def _application(school, **kwargs):
    applicant = Applicant.objects.create(
        tenant=school, full_name='Nora Ali', email='nora@example.com', gender='F',
        applying_for_class='Grade 3', **kwargs)
    return Application.objects.create(applicant=applicant, academic_year='2027-2028')


@pytest.mark.django_db
class TestAiScreening:
    """docs table "AI Admission Screening": a draft score/summary for a human reviewer."""

    @pytest.fixture(autouse=True)
    def _clean(self, settings):
        settings.OPENAI_API_KEY = ''
        settings.ANTHROPIC_API_KEY = ''
        settings.AI_RATE_LIMIT = 30
        cache.clear()

    def test_template_without_provider(self, school):
        app = _application(school)
        admin = _client(_admin(school))
        res = admin.post(f'/api/v1/auth/admissions/applications/{app.id}/ai-screen/')
        assert res.status_code == 200, res.content
        assert res.json()['source'] == 'template'
        app.refresh_from_db()
        assert app.ai_screening_score is not None and app.ai_screened_at is not None

    def test_screens_against_the_schools_criteria_and_logs_an_event(self, school):
        from services.ai.models import AIUsage
        from tests.test_ai_platform import FakeLLM

        school.settings_json = {**(school.settings_json or {}), 'admissions': {
            'criteria': ['Sibling already enrolled gets priority', 'Previous school report required']}}
        school.save()
        app = _application(school, sibling_at_school='Leo Ali (Grade 5)', previous_school='Oak Elementary')
        admin_user = _admin(school)
        admin = _client(admin_user)

        llm = FakeLLM([])
        llm.structured_results = [{'score': 82, 'summary': 'Strong match: sibling already enrolled.', 'concerns': ['No report card uploaded yet.']}]
        with mock.patch('services.ai.llm.get_llm_client', return_value=llm):
            res = admin.post(f'/api/v1/auth/admissions/applications/{app.id}/ai-screen/')
        assert res.status_code == 200, res.content
        body = res.json()
        assert body['source'] == 'ai' and body['score'] == 82 and 'sibling' in body['summary'].lower()
        assert body['concerns'] == ['No report card uploaded yet.']
        assert 'Sibling already enrolled gets priority' in llm.calls[0]['prompt']
        assert 'Leo Ali' in llm.calls[0]['prompt']

        app.refresh_from_db()
        assert app.ai_screening_score == 82
        assert app.events.filter(note__icontains='AI screening: 82/100').exists()
        assert AIUsage.objects.get(user=admin_user, feature='ai_admission_screening').output_tokens == 50

    def test_only_admins_can_screen(self, school):
        app = _application(school)
        stranger = _client(UserFactory(email='stranger2@example.com'))
        assert stranger.post(f'/api/v1/auth/admissions/applications/{app.id}/ai-screen/').status_code == 403
