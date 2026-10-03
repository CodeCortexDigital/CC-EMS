"""Safety incident reports: who can report and see them, follow-up tasks, closing rules, parent notice, isolation."""
from datetime import timedelta

import pytest
from django.utils import timezone

from services.core.audit.models import AuditLog
from services.core.user_notifications.models import Notification
from tests.safety_helpers import api, link_parent, make_student, make_user, rows, student_login, two_schools

BASE = '/api/v1/auth/safety'


@pytest.fixture
def school(db):
    a, b = two_schools()
    kid = make_student(a)
    mom = make_user(a, 'mom@a.test', 'parent')
    link_parent(mom, kid)
    return {
        'a': a, 'b': b, 'kid': kid, 'mom': mom,
        'admin': make_user(a, 'head@a.test', 'admin'), 'counsellor': make_user(a, 'carol.counsellor@a.test', 'counsellor'),
        'ann': make_user(a, 'ann.teacher@a.test', 'teacher'), 'ben': make_user(a, 'ben.teacher@a.test', 'teacher'),
        'student_user': student_login(a, 'kid@a.test'), 'admin_b': make_user(b, 'head@b.test', 'admin'),
    }


def _report(c, **kw):
    body = {'title': 'Fall on stairs', 'incident_type': 'injury', 'severity': 'moderate', 'place': 'Main stairs',
            'description': 'Slipped on a wet step.', **kw}
    return c.post(f'{BASE}/incidents/', body, format='json')


def _due(days):
    return str(timezone.localdate() + timedelta(days=days))


class TestWhoMayUseIt:
    def test_parents_and_students_get_nothing(self, school):
        for who in ('mom', 'student_user'):
            c = api(school[who])
            assert c.get(f'{BASE}/incidents/').status_code == 403
            assert _report(c).status_code == 403
        assert api().get(f'{BASE}/incidents/').status_code == 401

    def test_a_reporter_sees_only_their_own_reports(self, school):
        _report(api(school['ann']), title='Ann report')
        _report(api(school['ben']), title='Ben report')
        assert [i['title'] for i in rows(api(school['ann']).get(f'{BASE}/incidents/'))] == ['Ann report']
        assert {i['title'] for i in rows(api(school['admin']).get(f'{BASE}/incidents/'))} == {'Ann report', 'Ben report'}
        assert {i['title'] for i in rows(api(school['counsellor']).get(f'{BASE}/incidents/'))} == {'Ann report', 'Ben report'}

    def test_another_staff_members_report_is_not_reachable_by_id(self, school):
        iid = _report(api(school['ann'])).json()['id']
        assert api(school['ben']).get(f'{BASE}/incidents/{iid}/').status_code == 404
        assert api(school['ben']).patch(f'{BASE}/incidents/{iid}/', {'title': 'x'}, format='json').status_code == 404

    def test_reports_are_never_deleted(self, school):
        c = api(school['admin'])
        iid = _report(c).json()['id']
        assert c.delete(f'{BASE}/incidents/{iid}/').status_code == 405

    def test_only_reviewers_run_the_follow_up(self, school):
        iid = _report(api(school['ann'])).json()['id']
        teacher = api(school['ann'])
        body = {'description': 'Call parent', 'due_date': _due(3)}
        assert teacher.post(f'{BASE}/incidents/{iid}/add_follow_up/', body, format='json').status_code == 403
        assert teacher.post(f'{BASE}/incidents/{iid}/close/', {'closure_note': 'done'}, format='json').status_code == 403
        assert teacher.get(f'{BASE}/incidents/overdue/').status_code == 403


class TestFollowUpAndClosing:
    def test_first_follow_up_moves_the_incident_into_follow_up(self, school):
        c = api(school['counsellor'])
        iid = _report(api(school['ann'])).json()['id']
        r = c.post(f'{BASE}/incidents/{iid}/add_follow_up/', {'description': 'Check the stairs', 'due_date': _due(2), 'owner': str(school['ann'].pk)}, format='json')
        assert r.status_code == 201 and r.json()['owner_name'] == 'Ann Teacher'
        assert c.get(f'{BASE}/incidents/{iid}/').json()['status'] == 'in_follow_up'

    def test_closing_needs_a_note_and_every_task_done(self, school):
        c = api(school['admin'])
        iid = _report(api(school['ann'])).json()['id']
        task = c.post(f'{BASE}/incidents/{iid}/add_follow_up/', {'description': 'Fix step', 'due_date': _due(5)}, format='json').json()
        assert c.post(f'{BASE}/incidents/{iid}/close/', {}, format='json').status_code == 400
        assert 'still open' in str(c.post(f'{BASE}/incidents/{iid}/close/', {'closure_note': 'Fixed'}, format='json').json())
        assert c.post(f'{BASE}/follow-ups/{task["id"]}/complete/').status_code == 200
        closed = c.post(f'{BASE}/incidents/{iid}/close/', {'closure_note': 'Step repaired, parent informed'}, format='json')
        assert closed.status_code == 200 and closed.json()['status'] == 'closed' and closed.json()['closed_at']

    def test_a_closed_incident_cannot_be_edited_until_reopened(self, school):
        c = api(school['admin'])
        iid = _report(c).json()['id']
        c.post(f'{BASE}/incidents/{iid}/close/', {'closure_note': 'No further action'}, format='json')
        assert c.patch(f'{BASE}/incidents/{iid}/', {'title': 'Edited'}, format='json').status_code == 400
        assert c.post(f'{BASE}/incidents/{iid}/add_follow_up/', {'description': 'x', 'due_date': _due(1)}, format='json').status_code == 400
        assert c.post(f'{BASE}/incidents/{iid}/reopen/').status_code == 200
        assert c.patch(f'{BASE}/incidents/{iid}/', {'title': 'Edited'}, format='json').status_code == 200

    def test_cannot_close_or_reopen_in_the_wrong_state(self, school):
        c = api(school['admin'])
        iid = _report(c).json()['id']
        assert c.post(f'{BASE}/incidents/{iid}/reopen/').status_code == 400
        c.post(f'{BASE}/incidents/{iid}/close/', {'closure_note': 'ok'}, format='json')
        assert c.post(f'{BASE}/incidents/{iid}/close/', {'closure_note': 'again'}, format='json').status_code == 400

    def test_overdue_tasks_are_flagged_and_listed(self, school):
        c = api(school['admin'])
        iid = _report(c).json()['id']
        c.post(f'{BASE}/incidents/{iid}/add_follow_up/', {'description': 'Late one', 'due_date': _due(-2)}, format='json')
        c.post(f'{BASE}/incidents/{iid}/add_follow_up/', {'description': 'On time', 'due_date': _due(4)}, format='json')
        detail = c.get(f'{BASE}/incidents/{iid}/').json()
        assert detail['overdue_tasks'] == 1 and sorted(t['is_overdue'] for t in detail['follow_up_tasks']) == [False, True]
        listed = c.get(f'{BASE}/incidents/overdue/').json()
        assert [t['description'] for t in listed] == ['Late one'] and listed[0]['incident_title'] == 'Fall on stairs'

    def test_a_task_owner_can_finish_their_own_task_only(self, school):
        admin = api(school['admin'])
        iid = _report(admin).json()['id']
        mine = admin.post(f'{BASE}/incidents/{iid}/add_follow_up/', {'description': 'Mine', 'due_date': _due(3), 'owner': str(school['ann'].pk)}, format='json').json()
        theirs = admin.post(f'{BASE}/incidents/{iid}/add_follow_up/', {'description': 'Ben', 'due_date': _due(3), 'owner': str(school['ben'].pk)}, format='json').json()
        ann = api(school['ann'])
        assert ann.post(f'{BASE}/follow-ups/{mine["id"]}/complete/').status_code == 200
        assert ann.post(f'{BASE}/follow-ups/{theirs["id"]}/complete/').status_code == 404
        assert ann.post(f'{BASE}/follow-ups/{mine["id"]}/complete/').status_code == 400  # already done


class TestTaskOwners:
    def test_reviewers_can_pick_staff_as_owners_but_never_families(self, school):
        listed = api(school['admin']).get(f'{BASE}/incidents/owners/').json()
        names = {o['name'] for o in listed}
        assert {'Ann Teacher', 'Ben Teacher', 'Carol Counsellor'} <= names
        assert 'Mom' not in names and all(o['role'] != 'parent' for o in listed)
        assert api(school['ann']).get(f'{BASE}/incidents/owners/').status_code == 403

    def test_other_schools_staff_are_not_offered(self, school):
        other = {o['name'] for o in api(school['admin_b']).get(f'{BASE}/incidents/owners/').json()}
        assert 'Ann Teacher' not in other and 'Carol Counsellor' not in other


class TestParentNotice:
    def test_parents_are_told_only_when_asked_and_only_for_their_child(self, school):
        _report(api(school['ann']), students_involved=[str(school['kid'].pk)])
        assert not Notification.objects.filter(recipient=school['mom']).exists()
        r = _report(api(school['ann']), students_involved=[str(school['kid'].pk)], notify_parents=True)
        assert r.status_code == 201 and r.json()['parent_notified_at']
        assert Notification.objects.filter(recipient=school['mom'], message__icontains='Fall on stairs').count() == 1


class TestAuditAndIsolation:
    def test_reads_and_writes_are_audited(self, school):
        c = api(school['admin'])
        iid = _report(c).json()['id']
        c.get(f'{BASE}/incidents/')
        c.get(f'{BASE}/incidents/{iid}/')
        assert AuditLog.objects.filter(user=school['admin'], action='VIEW', resource_type='safety/incident').count() == 2
        assert AuditLog.objects.filter(user=school['admin'], action='CREATE', resource_type='safety/incident').exists()

    def test_another_school_sees_nothing(self, school):
        iid = _report(api(school['ann'])).json()['id']
        task = api(school['admin']).post(f'{BASE}/incidents/{iid}/add_follow_up/', {'description': 'x', 'due_date': _due(3)}, format='json').json()
        other = api(school['admin_b'])
        assert rows(other.get(f'{BASE}/incidents/')) == []
        assert rows(other.get(f'{BASE}/follow-ups/')) == []
        assert other.get(f'{BASE}/incidents/{iid}/').status_code == 404
        assert other.post(f'{BASE}/incidents/{iid}/close/', {'closure_note': 'x'}, format='json').status_code == 404
        assert other.post(f'{BASE}/follow-ups/{task["id"]}/complete/').status_code == 404
        # nor can school B attach school A's student to a report
        assert _report(other, students_involved=[str(school['kid'].pk)]).status_code == 400
