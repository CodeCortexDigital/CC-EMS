"""What a careful school (or its lawyer) asks for: a copy of one person's data, a provable erasure, retention that includes AI chat
history, and a recorded human decision on every AI risk flag."""
import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from services.ai.models import AIActionRequest, AIConversation, AIMessage
from services.analytics.models import StudentRisk
from services.core.audit.models import AuditLog
from services.core.privacy.models import PrivacyRequest
from services.core.security import retention
from services.core.tenants.signup import create_school_with_admin
from tests.conftest import InvoiceFactory, StudentFactory

P = '/api/v1/privacy'


def _school(name, email):
    school, admin = create_school_with_admin(school_name=name, admin_email=email, admin_name=name + ' Head', password='Sturdy-Pass-91x')
    api = APIClient()
    res = api.post('/api/v1/auth/login/', {'email': email, 'password': 'Sturdy-Pass-91x'}, format='json')
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.json()['access']}")
    return school, admin, api


@pytest.fixture
def two(db):
    return _school('Alder Academy', 'head@alder.test'), _school('Birch Academy', 'head@birch.test')


def _request(school, admin, student, kind='erasure'):
    return PrivacyRequest.objects.create(school=school, requester=admin, requester_email=admin.email, student=student, kind=kind,
                                         details='Please erase my child.')


@pytest.mark.django_db
class TestCopyOfAPersonsData:
    def test_the_copy_holds_the_record_and_every_table_about_them_and_no_secrets(self, two):
        (a, admin, api), _ = two
        kid = StudentFactory(tenant=a, full_name='Amy Alder', email='amy@alder.test')
        InvoiceFactory(student=kid, amount=100, status='pending', due_date=datetime.date.today())
        r = _request(a, admin, kid, 'access')
        res = api.get(f'{P}/requests/{r.id}/export/')
        assert res.status_code == 200 and 'attachment' in res['Content-Disposition']
        data = res.json()
        assert data['about']['name'] == 'Amy Alder' and data['record']['email'] == 'amy@alder.test'
        assert data['row_counts']['education_finance.Invoice'] == 1
        names = set(data['record']) | {k for rows in data['tables'].values() for row in rows for k in row}
        assert not [n for n in names if any(w in n.lower() for w in ('password', 'token', 'secret', 'hash'))]
        assert AuditLog.objects.filter(resource_type='privacy.export', school=a).exists()

    def test_it_never_includes_another_student_or_school(self, two):
        (a, admin_a, api_a), (b, admin_b, api_b) = two
        mine, theirs = StudentFactory(tenant=a, full_name='Amy Alder'), StudentFactory(tenant=b, full_name='Ben Birch')
        InvoiceFactory(student=theirs, amount=999, status='pending', due_date=datetime.date.today())
        data = api_a.get(f'{P}/requests/{_request(a, admin_a, mine, "access").id}/export/').json()
        assert 'Ben Birch' not in str(data) and 'education_finance.Invoice' not in data['tables']
        # And school B's office cannot reach school A's request at all.
        r = _request(a, admin_a, mine, 'access')
        assert api_b.get(f'{P}/requests/{r.id}/export/').status_code == 404
        assert api_b.post(f'{P}/requests/{r.id}/erase/', {'confirm': mine.student_id}, format='json').status_code == 404

    def test_only_a_request_about_a_student_can_be_exported(self, two):
        (a, admin, api), _ = two
        r = PrivacyRequest.objects.create(school=a, requester=admin, requester_email=admin.email, kind='access', details='x')
        assert api.get(f'{P}/requests/{r.id}/export/').status_code == 400


@pytest.mark.django_db
class TestErasure:
    def test_it_shows_what_will_happen_before_doing_anything(self, two):
        (a, admin, api), _ = two
        kid = StudentFactory(tenant=a, full_name='Amy Alder', email='amy@alder.test')
        StudentRisk.objects.create(student=kid, risk_level='high', risk_score=70)
        r = _request(a, admin, kid)
        res = api.post(f'{P}/requests/{r.id}/erase/', {}, format='json').json()
        assert res['confirm_with'] == kid.student_id
        assert res['preview']['removed'].get('analytics.StudentRisk') == 1
        assert res['preview']['becomes'] == f'Former student {kid.student_id}'
        kid.refresh_from_db()
        assert kid.full_name == 'Amy Alder' and StudentRisk.objects.filter(student=kid).exists()      # nothing was touched

    def test_the_student_id_must_be_typed_to_confirm(self, two):
        (a, admin, api), _ = two
        kid = StudentFactory(tenant=a, full_name='Amy Alder')
        r = _request(a, admin, kid)
        wrong = api.post(f'{P}/requests/{r.id}/erase/', {'confirm': 'yes'}, format='json')
        assert wrong.status_code == 400 and kid.student_id in wrong.json()['error']
        kid.refresh_from_db()
        assert kid.full_name == 'Amy Alder'

    def test_erasing_clears_who_they_were_keeps_the_accounts_closes_the_request_and_is_audited(self, two):
        (a, admin, api), _ = two
        kid = StudentFactory(tenant=a, full_name='Amy Alder', email='amy@alder.test', phone='555-0100', address='1 Elm St')
        inv = InvoiceFactory(student=kid, amount=100, status='paid', due_date=datetime.date.today())
        StudentRisk.objects.create(student=kid, risk_level='high', risk_score=70)
        r = _request(a, admin, kid)
        res = api.post(f'{P}/requests/{r.id}/erase/', {'confirm': kid.student_id.lower()}, format='json')
        assert res.status_code == 200, res.content
        kid.refresh_from_db()
        assert kid.full_name == f'Former student {kid.student_id}' and kid.email == '' and kid.phone == '' and kid.address == ''
        assert not StudentRisk.objects.filter(student=kid).exists()
        inv.refresh_from_db()
        assert inv.student_id == kid.pk                                                       # the accounts still add up
        r.refresh_from_db()
        assert r.status == 'done' and r.closed_at and 'erased' in r.response and r.handled_by == admin
        log = AuditLog.objects.get(resource_type='privacy.erasure')
        assert log.school == a and log.new_data['student_id'] == kid.student_id and 'Amy' not in str(log.new_data)
        again = api.post(f'{P}/requests/{r.id}/erase/', {'confirm': kid.student_id}, format='json')
        assert again.status_code == 400 and 'closed' in again.json()['error']                 # cannot be run twice by mistake

    def test_an_access_request_cannot_be_used_to_erase(self, two):
        (a, admin, api), _ = two
        kid = StudentFactory(tenant=a)
        r = _request(a, admin, kid, 'access')
        assert api.post(f'{P}/requests/{r.id}/erase/', {'confirm': kid.student_id}, format='json').status_code == 400

    def test_the_request_list_tells_the_screen_what_it_may_offer(self, two):
        (a, admin, api), _ = two
        kid = StudentFactory(tenant=a)
        _request(a, admin, kid)
        row = api.get(f'{P}/requests/').json()['results'][0]
        assert row['can_export'] and row['can_erase'] and row['student_ref'] == kid.student_id


@pytest.mark.django_db
class TestRetentionIncludesAI:
    def test_old_chats_and_decided_ai_requests_are_deleted_and_waiting_ones_are_kept(self, two):
        (a, admin, api), (b, admin_b, _) = two
        old = timezone.now() - datetime.timedelta(days=200)
        chat = AIConversation.objects.create(user=admin, tenant=a, title='old')
        AIMessage.objects.create(conversation=chat, role='user', content='What is Amy\'s grade?')
        fresh = AIConversation.objects.create(user=admin, tenant=a, title='fresh')
        other = AIConversation.objects.create(user=admin_b, tenant=b, title='other school')
        AIConversation.objects.filter(pk__in=[chat.pk, other.pk]).update(updated_at=old)
        decided = AIActionRequest.all_objects.create(tenant=a, action='send_fee_reminder', summary='x', requested_by=admin, status='executed',
                                                      expires_at=timezone.now())
        waiting = AIActionRequest.all_objects.create(tenant=a, action='send_fee_reminder', summary='y', requested_by=admin, status='pending',
                                                      expires_at=timezone.now() + datetime.timedelta(days=1))
        AIActionRequest.all_objects.filter(pk__in=[decided.pk, waiting.pk]).update(created_at=old)
        saved, error = retention.save(a, {'ai_chats': 90, 'ai_actions': 120})
        assert error is None and saved['ai_chats'] == 90
        assert retention.preview(a)['ai_chats'] == 1
        done = retention.apply(a)
        assert done['ai_chats'] == 1 and done['ai_actions'] == 1
        assert not AIConversation.objects.filter(pk=chat.pk).exists() and not AIMessage.objects.filter(conversation_id=chat.pk).exists()
        assert AIConversation.objects.filter(pk=fresh.pk).exists()
        assert AIConversation.objects.filter(pk=other.pk).exists()                           # another school's rule is its own
        assert AIActionRequest.all_objects.filter(pk=waiting.pk).exists() and not AIActionRequest.all_objects.filter(pk=decided.pk).exists()

    def test_too_short_a_time_is_refused(self, two):
        (a, *_), _ = two
        saved, error = retention.save(a, {'ai_chats': 3})
        assert saved is None and 'at least' in error


@pytest.mark.django_db
class TestHumanReviewOfAIRiskFlags:
    def _flagged(self, school, level='high'):
        kid = StudentFactory(tenant=school, full_name='Amy Alder')
        risk = StudentRisk.objects.create(student=kid, risk_level=level, risk_score=72, factors={'dropout_risk': 72.0, 'fee_default_risk': 10.0})
        return kid, risk

    def test_a_high_flag_is_marked_advisory_and_needs_a_person_to_review_it(self, two):
        (a, admin, api), _ = two
        kid, _ = self._flagged(a)
        row = next(r for r in api.get('/api/v1/ai/student-predictions/').json() if r['student_id'] == str(kid.pk))
        assert row['advisory'] is True and row['needs_review'] is True and row['review'] is None

    def test_a_person_records_a_decision_with_a_reason_and_it_is_audited(self, two):
        (a, admin, api), _ = two
        kid, risk = self._flagged(a)
        url = f'/api/v1/ai/student-predictions/{kid.pk}/review/'
        assert api.post(url, {'decision': 'maybe'}, format='json').status_code == 400
        assert api.post(url, {'decision': 'dismissed'}, format='json').status_code == 400            # a reason is required
        ok = api.post(url, {'decision': 'dismissed', 'note': 'Late fees only; family on a plan'}, format='json')
        assert ok.status_code == 200 and ok.json()['review']['by'] and ok.json()['review']['decision'] == 'dismissed'
        row = next(r for r in api.get('/api/v1/ai/student-predictions/').json() if r['student_id'] == str(kid.pk))
        assert row['needs_review'] is False and row['review']['note'].startswith('Late fees')
        log = AuditLog.objects.get(resource_type='analytics.risk.review')
        assert log.user == admin and log.new_data['decision'] == 'dismissed' and 'Amy' not in str(log.new_data)

    def test_confirming_needs_no_reason_and_nothing_else_happens_automatically(self, two):
        from services.education.interventions.models import Intervention

        (a, admin, api), _ = two
        kid, _ = self._flagged(a)
        before = Intervention.all_objects.count()
        assert api.post(f'/api/v1/ai/student-predictions/{kid.pk}/review/', {'decision': 'confirmed'}, format='json').status_code == 200
        assert Intervention.all_objects.count() == before

    def test_another_schools_office_cannot_review_this_students_flag(self, two):
        (a, admin, api), (b, admin_b, api_b) = two
        kid, risk = self._flagged(a)
        res = api_b.post(f'/api/v1/ai/student-predictions/{kid.pk}/review/', {'decision': 'confirmed'}, format='json')
        assert res.status_code == 404
        risk.refresh_from_db()
        assert risk.review_decision == ''

    def test_a_review_stops_applying_when_the_score_moves_to_another_level(self, two):
        from services.analytics.ai_views import clear_stale_review

        (a, admin, api), _ = two
        kid, risk = self._flagged(a)
        api.post(f'/api/v1/ai/student-predictions/{kid.pk}/review/', {'decision': 'confirmed'}, format='json')
        risk.refresh_from_db()
        assert risk.review_decision == 'confirmed'
        assert clear_stale_review(risk, previous_level='high') is False and risk.review_decision == 'confirmed'      # same level: kept
        risk.risk_level = 'critical'
        assert clear_stale_review(risk, previous_level='high') is True
        assert risk.review_decision == '' and risk.reviewed_by is None and risk.reviewed_at is None


@pytest.mark.django_db
class TestScanKeepsReviewsAndRunsOnce:
    def test_a_scan_rebuilds_risk_rows_but_a_saved_review_comes_back_when_the_level_is_unchanged(self, two):
        from services.analytics.ai_views import carry_over_review, clear_stale_review, review_snapshot

        (a, admin, api), _ = two
        kid = StudentFactory(tenant=a)
        old = StudentRisk.objects.create(student=kid, risk_level='high', risk_score=70, review_decision='dismissed',
                                         review_note='On a payment plan', reviewed_by=admin, reviewed_at=timezone.now())
        kept = review_snapshot(str(a.id))
        assert set(kept) == {kid.pk}
        old.delete()                                                  # what a scan does: it deletes and rebuilds every risk row
        fresh = StudentRisk.objects.create(student=kid, risk_level='high', risk_score=71)
        previous = carry_over_review(fresh, kept.get(kid.pk))
        assert previous == 'high' and fresh.review_decision == 'dismissed' and fresh.reviewed_by_id == admin.pk
        assert clear_stale_review(fresh, previous) is False and fresh.review_note == 'On a payment plan'
        fresh.risk_level = 'critical'                                 # the new score is at a different level: the old review is dropped
        assert clear_stale_review(fresh, previous) is True and fresh.review_decision == ''

    def test_a_student_with_no_review_is_unaffected(self, two):
        from services.analytics.ai_views import carry_over_review

        (a, *_), _ = two
        risk = StudentRisk.objects.create(student=StudentFactory(tenant=a), risk_level='low', risk_score=5)
        assert carry_over_review(risk, None) == 'low' and risk.review_decision == ''

    def test_only_one_scan_runs_at_a_time_for_a_school(self, two, monkeypatch):
        from django.core.cache import cache
        from services.analytics import ai_views

        (a, admin, api), _ = two
        calls = []
        monkeypatch.setattr(ai_views, 'RISK_ML_AVAILABLE', True)
        monkeypatch.setattr(ai_views, '_run_risk_scan', lambda tenant_id=None, **kw: calls.append(tenant_id) or {})
        cache.add(f'risk-scan:{a.id}', 1, timeout=60)                  # a scan is already running
        busy = api.post('/api/v1/ai/train-models/', {}, format='json')
        assert busy.status_code == 409 and 'already running' in busy.json()['error'] and calls == []
        cache.delete(f'risk-scan:{a.id}')
        ok = api.post('/api/v1/ai/train-models/', {}, format='json')
        assert ok.status_code == 200 and calls == [str(a.id)]
        assert cache.get(f'risk-scan:{a.id}') is None                   # released when done, even though it just finished
