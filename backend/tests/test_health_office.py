"""Health office: nurse visits, medication permissions and doses, parent notices, privacy and audit."""
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from services.core.audit.models import AuditLog
from services.core.user_notifications.models import Notification
from services.education.students.models import Immunization
from tests.safety_helpers import api, link_parent, make_student, make_user, rows, two_schools

BASE = '/api/v1/education/students'


@pytest.fixture
def clinic(db):
    a, b = two_schools()
    kid, other = make_student(a), make_student(a)
    mom, other_mom = make_user(a, 'mom@a.test', 'parent'), make_user(a, 'other.mom@a.test', 'parent')
    link_parent(mom, kid)
    link_parent(other_mom, other)
    return {
        'a': a, 'b': b, 'kid': kid, 'other': other, 'mom': mom, 'other_mom': other_mom,
        'nurse': make_user(a, 'nora.nurse@a.test', 'nurse'), 'admin': make_user(a, 'head@a.test', 'admin'),
        'teacher': make_user(a, 'tim.teacher@a.test', 'teacher'), 'nurse_b': make_user(b, 'nurse@b.test', 'nurse'),
        'kid_b': make_student(b),
    }


def _visit(c, student, **kw):
    return c.post(f'{BASE}/health-visits/', {'student': str(student.pk), 'visit_type': 'illness', 'complaint': 'Headache', 'action_taken': 'rested', **kw}, format='json')


def _auth(c, student, **kw):
    body = {'student': str(student.pk), 'medication_name': 'Ibuprofen', 'dose': '200 mg', 'route': 'oral', 'times': '12:00',
            'start_date': str(timezone.localdate() - timedelta(days=1)), 'parent_consent': True, **kw}
    return c.post(f'{BASE}/medication-authorizations/', body, format='json')


def _dose(c, auth_id, **kw):
    return c.post(f'{BASE}/medication-logs/', {'authorization': auth_id, 'status': 'given', 'dose_given': '200 mg', **kw}, format='json')


class TestWhoMaySee:
    def test_a_teacher_and_a_stranger_get_nothing(self, clinic):
        _visit(api(clinic['nurse']), clinic['kid'])
        for url in ('health-visits', 'medication-authorizations', 'medication-logs'):
            assert api(clinic['teacher']).get(f'{BASE}/{url}/').status_code == 403
            assert api().get(f'{BASE}/{url}/').status_code == 401

    def test_a_parent_sees_only_their_own_child_and_cannot_write(self, clinic):
        nurse = api(clinic['nurse'])
        _visit(nurse, clinic['kid'], complaint='Scraped knee')
        _visit(nurse, clinic['other'], complaint='Nosebleed')
        mom = api(clinic['mom'])
        seen = rows(mom.get(f'{BASE}/health-visits/'))
        assert [v['complaint'] for v in seen] == ['Scraped knee']
        other_visit = rows(nurse.get(f'{BASE}/health-visits/?student={clinic["other"].pk}'))[0]['id']
        assert mom.get(f'{BASE}/health-visits/{other_visit}/').status_code == 404
        assert _visit(mom, clinic['kid']).status_code == 403
        assert _auth(mom, clinic['kid']).status_code == 403

    def test_nurse_and_admin_can_work(self, clinic):
        assert _visit(api(clinic['nurse']), clinic['kid']).status_code == 201
        assert _visit(api(clinic['admin']), clinic['kid']).status_code == 201


class TestVisits:
    def test_parent_is_told_and_visit_is_marked_notified(self, clinic):
        r = _visit(api(clinic['nurse']), clinic['kid'], sent_home=True, action_taken='sent_home')
        assert r.status_code == 201 and r.json()['parent_notified_at']
        n = Notification.objects.get(recipient=clinic['mom'])
        assert 'health office' in n.message.lower() and 'sent home' in n.message.lower()
        assert not Notification.objects.filter(recipient=clinic['other_mom']).exists()

    def test_school_can_choose_to_tell_parents_only_when_sent_home(self, clinic):
        clinic['a'].settings_json = {'health_office': {'notify': 'sent_home'}}
        clinic['a'].save()
        _visit(api(clinic['nurse']), clinic['kid'])
        assert not Notification.objects.filter(recipient=clinic['mom']).exists()
        _visit(api(clinic['nurse']), clinic['kid'], sent_home=True)
        assert Notification.objects.filter(recipient=clinic['mom']).count() == 1

    def test_time_out_cannot_be_before_time_in(self, clinic):
        now = timezone.now()
        r = _visit(api(clinic['nurse']), clinic['kid'], time_in=now.isoformat(), time_out=(now - timedelta(hours=1)).isoformat())
        assert r.status_code == 400


class TestMedication:
    def test_dose_needs_a_current_parent_permission(self, clinic):
        nurse = api(clinic['nurse'])
        no_consent = _auth(nurse, clinic['kid'], parent_consent=False).json()
        assert _dose(nurse, no_consent['id']).status_code == 400
        expired = _auth(nurse, clinic['kid'], start_date=str(timezone.localdate() - timedelta(days=10)),
                        end_date=str(timezone.localdate() - timedelta(days=2))).json()
        assert _dose(nurse, expired['id']).status_code == 400
        future = _auth(nurse, clinic['kid'], start_date=str(timezone.localdate() + timedelta(days=3))).json()
        assert _dose(nurse, future['id']).status_code == 400
        off = _auth(nurse, clinic['kid']).json()
        nurse.patch(f'{BASE}/medication-authorizations/{off["id"]}/', {'is_active': False}, format='json')
        assert _dose(nurse, off['id']).status_code == 400
        good = _auth(nurse, clinic['kid']).json()
        assert good['is_current'] is True and good['parent_consent_on']
        assert _dose(nurse, good['id']).status_code == 201

    def test_second_dose_too_soon_is_blocked_unless_a_reason_is_typed(self, clinic):
        nurse = api(clinic['nurse'])
        auth = _auth(nurse, clinic['kid'], min_hours_between_doses=6).json()
        first = timezone.now() - timedelta(hours=2)
        assert _dose(nurse, auth['id'], given_at=first.isoformat()).status_code == 201
        too_soon = _dose(nurse, auth['id'])
        assert too_soon.status_code == 400 and 'override_reason' in too_soon.json() and '6 hours' in str(too_soon.json())
        assert _dose(nurse, auth['id'], override_reason='  ').status_code == 400
        ok = _dose(nurse, auth['id'], override_reason='Fever spiked, parent phoned to approve')
        assert ok.status_code == 201
        assert AuditLog.objects.filter(user=clinic['nurse'], resource_type='health/medication_log', new_data__override=True).exists()

    def test_a_dose_far_enough_apart_needs_no_reason(self, clinic):
        nurse = api(clinic['nurse'])
        auth = _auth(nurse, clinic['kid'], min_hours_between_doses=4).json()
        assert _dose(nurse, auth['id'], given_at=(timezone.now() - timedelta(hours=5)).isoformat()).status_code == 201
        assert _dose(nurse, auth['id']).status_code == 201

    def test_a_dose_record_cannot_be_edited_or_removed(self, clinic):
        nurse = api(clinic['nurse'])
        auth = _auth(nurse, clinic['kid']).json()
        log = _dose(nurse, auth['id']).json()
        assert nurse.patch(f'{BASE}/medication-logs/{log["id"]}/', {'notes': 'x'}, format='json').status_code == 405
        assert nurse.delete(f'{BASE}/medication-logs/{log["id"]}/').status_code == 405

    def test_authorisation_end_before_start_is_refused(self, clinic):
        assert _auth(api(clinic['nurse']), clinic['kid'], end_date=str(timezone.localdate() - timedelta(days=30))).status_code == 400

    def test_parent_can_read_their_childs_medication_only(self, clinic):
        nurse = api(clinic['nurse'])
        _auth(nurse, clinic['kid'], medication_name='Inhaler')
        _auth(nurse, clinic['other'], medication_name='Other drug')
        assert [a['medication_name'] for a in rows(api(clinic['mom']).get(f'{BASE}/medication-authorizations/'))] == ['Inhaler']


class TestAuditAndIsolation:
    def test_every_read_is_audited(self, clinic):
        nurse = api(clinic['nurse'])
        vid = _visit(nurse, clinic['kid']).json()['id']
        nurse.get(f'{BASE}/health-visits/?student={clinic["kid"].pk}')
        nurse.get(f'{BASE}/health-visits/{vid}/')
        api(clinic['mom']).get(f'{BASE}/health-visits/')
        reads = AuditLog.objects.filter(action='VIEW', resource_type='health/visit')
        assert reads.filter(user=clinic['nurse']).count() == 2 and reads.filter(user=clinic['mom']).count() == 1
        assert AuditLog.objects.filter(action='CREATE', resource_type='health/visit', user=clinic['nurse']).exists()

    def test_another_school_sees_and_changes_nothing(self, clinic):
        nurse, nurse_b = api(clinic['nurse']), api(clinic['nurse_b'])
        vid = _visit(nurse, clinic['kid']).json()['id']
        auth = _auth(nurse, clinic['kid']).json()
        _dose(nurse, auth['id'])
        for url in ('health-visits', 'medication-authorizations', 'medication-logs'):
            assert rows(nurse_b.get(f'{BASE}/{url}/')) == []
        assert nurse_b.get(f'{BASE}/health-visits/{vid}/').status_code == 404
        assert _visit(nurse_b, clinic['kid']).status_code == 400     # cannot record a visit for school A's student
        assert _dose(nurse_b, auth['id']).status_code == 400          # nor give a dose on school A's permission


class TestImmunizationReminders:
    def _record(self, clinic, days, **kw):
        return Immunization.objects.create(tenant=clinic['a'], student=clinic['kid'], vaccine='MMR', dose='2',
                                           next_due_date=timezone.localdate() + timedelta(days=days), **kw)

    def test_reminds_once_per_due_date(self, clinic):
        rec = self._record(clinic, 10)
        call_command('send_immunization_reminders')
        assert Notification.objects.filter(recipient=clinic['mom'], title__icontains='immunization').count() == 1
        call_command('send_immunization_reminders')
        assert Notification.objects.filter(recipient=clinic['mom'], title__icontains='immunization').count() == 1
        rec.refresh_from_db()
        rec.next_due_date += timedelta(days=90)
        rec.save()
        call_command('send_immunization_reminders', days=200)
        assert Notification.objects.filter(recipient=clinic['mom'], title__icontains='immunization').count() == 2

    def test_skips_far_off_exempt_and_other_childrens_parents(self, clinic):
        self._record(clinic, 120)
        self._record(clinic, 5, exempt=True)
        call_command('send_immunization_reminders')
        assert not Notification.objects.filter(title__icontains='immunization').exists()
        self._record(clinic, -3)
        call_command('send_immunization_reminders')
        n = Notification.objects.get(recipient=clinic['mom'])
        assert 'overdue' in n.message and not Notification.objects.filter(recipient=clinic['other_mom']).exists()
