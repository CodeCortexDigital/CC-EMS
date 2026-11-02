"""The intervention queue: who sees what, working an intervention through, de-duplication and school isolation."""
from datetime import timedelta

import pytest
from django.utils import timezone

from services.core.audit.models import AuditLog
from services.core.user_notifications.models import Notification
from services.education.interventions import engine
from services.education.interventions.models import Intervention
from tests.safety_helpers import api, link_parent, make_student, make_user, rows, two_schools

BASE = '/api/v1/auth/interventions'


@pytest.fixture
def school(db):
    a, b = two_schools()
    return {'a': a, 'b': b, 'kid': make_student(a, full_name='Noah Smith'), 'kid2': make_student(a, full_name='Ella Jones'), 'kid_b': make_student(b),
            'admin': make_user(a, 'head@a.test', 'admin'), 'counsellor': make_user(a, 'carol.counsellor@a.test', 'counsellor'),
            'ann': make_user(a, 'ann.teacher@a.test', 'teacher'), 'ben': make_user(a, 'ben.teacher@a.test', 'teacher'),
            'mom': make_user(a, 'mom@a.test', 'parent'), 'admin_b': make_user(b, 'head@b.test', 'admin')}


def _open(student, **kw):
    kw.setdefault('source', 'absence')
    kw.setdefault('title', '5 unexcused absences in 30 days')
    return engine.open_intervention(student=student, **kw)[0]


def _create(c, student, **kw):
    return c.post(f'{BASE}/', {'student': str(student.pk), 'title': 'Check in with Noah', **kw}, format='json')


class TestWhoMayUseIt:
    def test_families_students_and_strangers_get_nothing(self, school):
        link_parent(school['mom'], school['kid'])
        assert api(school['mom']).get(f'{BASE}/').status_code == 403
        assert api().get(f'{BASE}/').status_code == 401

    def test_reviewers_see_everything_other_staff_only_what_is_assigned_to_them(self, school):
        mine = _open(school['kid'], owner=school['ann'], dedupe_key='a')
        _open(school['kid2'], dedupe_key='b')
        for who in ('admin', 'counsellor'):
            assert len(rows(api(school[who]).get(f'{BASE}/'))) == 2
        assert [i['id'] for i in rows(api(school['ann']).get(f'{BASE}/'))] == [str(mine.pk)]
        assert rows(api(school['ben']).get(f'{BASE}/')) == []
        assert api(school['ben']).get(f'{BASE}/{mine.pk}/').status_code == 404

    def test_only_reviewers_add_change_dismiss_or_reopen(self, school):
        item = _open(school['kid'], owner=school['ann'], dedupe_key='a')
        ann = api(school['ann'])
        assert _create(ann, school['kid']).status_code == 403
        assert ann.patch(f'{BASE}/{item.pk}/', {'priority': 'high'}, format='json').status_code == 403
        assert ann.post(f'{BASE}/{item.pk}/dismiss/', {'note': 'x'}, format='json').status_code == 403
        assert ann.get(f'{BASE}/owners/').status_code == 403


class TestAddingByHand:
    def test_a_counselor_adds_one_with_an_owner_and_the_owner_is_told(self, school):
        r = _create(api(school['counsellor']), school['kid'], description='Seems withdrawn', owner=str(school['ann'].pk),
                    due_date=str(timezone.localdate() + timedelta(days=3)), priority='high')
        assert r.status_code == 201, r.content
        body = r.json()
        assert body['source'] == 'manual' and body['status'] == 'open' and body['priority'] == 'high' and body['owner_name'] == 'Ann Teacher'
        assert body['student_name'] == 'Noah Smith' and body['is_overdue'] is False
        assert AuditLog.objects.filter(user=school['counsellor'], action='CREATE', resource_type='interventions/item').exists()

    def test_the_owner_must_be_staff_at_this_school_and_the_student_must_be_theirs(self, school):
        c = api(school['admin'])
        assert _create(c, school['kid'], owner=str(school['mom'].pk)).status_code == 400
        assert _create(c, school['kid'], owner=str(school['admin_b'].pk)).status_code == 400
        assert _create(c, school['kid_b']).status_code == 400
        assert _create(c, school['kid'], priority='urgent!').status_code == 400
        assert not Intervention.objects.exists()

    def test_the_owner_picker_lists_staff_not_families_or_other_schools(self, school):
        names = {o['name'] for o in api(school['admin']).get(f'{BASE}/owners/').json()}
        assert {'Ann Teacher', 'Carol Counsellor', 'Ben Teacher'} <= names and 'Mom' not in names
        assert 'Ann Teacher' not in {o['name'] for o in api(school['admin_b']).get(f'{BASE}/owners/').json()}


class TestWorkingIt:
    def test_an_owner_starts_notes_and_completes_their_own(self, school):
        item = _open(school['kid'], owner=school['ann'], dedupe_key='a')
        ann = api(school['ann'])
        assert ann.post(f'{BASE}/{item.pk}/start/').json()['status'] == 'in_progress'
        assert ann.post(f'{BASE}/{item.pk}/start/').status_code == 400                          # already started
        assert ann.post(f'{BASE}/{item.pk}/add_note/', {'text': ' '}, format='json').status_code == 400
        assert ann.post(f'{BASE}/{item.pk}/add_note/', {'text': 'Called mom, she will call back'}, format='json').status_code == 201
        assert ann.post(f'{BASE}/{item.pk}/complete/', {}, format='json').status_code == 400   # a note is needed
        done = ann.post(f'{BASE}/{item.pk}/complete/', {'note': 'Plan agreed with the family'}, format='json')
        assert done.status_code == 200 and done.json()['status'] == 'done' and done.json()['closed_at']
        assert [n['text'] for n in done.json()['notes']] == ['Called mom, she will call back', 'Done: Plan agreed with the family']
        assert ann.post(f'{BASE}/{item.pk}/complete/', {'note': 'again'}, format='json').status_code == 400

    def test_someone_else_cannot_work_on_it(self, school):
        item = _open(school['kid'], owner=school['ann'], dedupe_key='a')
        ben = api(school['ben'])
        assert ben.post(f'{BASE}/{item.pk}/add_note/', {'text': 'hi'}, format='json').status_code == 404       # not even visible
        unowned = _open(school['kid2'], dedupe_key='b')
        assert api(school['ann']).post(f'{BASE}/{unowned.pk}/start/').status_code == 404

    def test_dismiss_and_reopen(self, school):
        c = api(school['counsellor'])
        item = _open(school['kid'], dedupe_key='a')
        assert c.post(f'{BASE}/{item.pk}/dismiss/', {}, format='json').status_code == 400
        assert c.post(f'{BASE}/{item.pk}/dismiss/', {'note': 'Family already supported'}, format='json').json()['status'] == 'dismissed'
        assert c.patch(f'{BASE}/{item.pk}/', {'title': 'x'}, format='json').status_code == 400                # closed
        assert c.post(f'{BASE}/{item.pk}/reopen/').json()['status'] == 'open'
        assert c.post(f'{BASE}/{item.pk}/reopen/').status_code == 400

    def test_a_closed_one_cannot_be_reopened_if_the_same_reason_is_open_again(self, school):
        c = api(school['admin'])
        old = _open(school['kid'], dedupe_key='absence:k:5')
        c.post(f'{BASE}/{old.pk}/complete/', {'note': 'done'}, format='json')
        again = _open(school['kid'], dedupe_key='absence:k:5')
        assert again.pk != old.pk
        assert c.post(f'{BASE}/{old.pk}/reopen/').status_code == 400
        assert Intervention.objects.get(pk=old.pk).status == 'done'

    def test_reviewers_reassign_and_change_the_due_date(self, school):
        item = _open(school['kid'], dedupe_key='a')
        new_due = str(timezone.localdate() + timedelta(days=9))
        r = api(school['admin']).patch(f'{BASE}/{item.pk}/', {'owner': str(school['ben'].pk), 'due_date': new_due, 'priority': 'high'}, format='json')
        assert r.status_code == 200 and r.json()['owner_name'] == 'Ben Teacher' and r.json()['due_date'] == new_due
        assert [i['id'] for i in rows(api(school['ben']).get(f'{BASE}/'))] == [str(item.pk)]


class TestEngine:
    def test_the_same_reason_opens_once_while_active(self, school):
        first, created = engine.open_intervention(student=school['kid'], source='absence', title='t', dedupe_key='k')
        second, created_again = engine.open_intervention(student=school['kid'], source='absence', title='t', dedupe_key='k')
        assert created and not created_again and first.pk == second.pk and Intervention.objects.count() == 1
        Intervention.objects.filter(pk=first.pk).update(status='dismissed')
        _, created_third = engine.open_intervention(student=school['kid'], source='absence', title='t', dedupe_key='k')
        assert created_third and Intervention.objects.count() == 2

    def test_without_a_key_each_one_is_separate(self, school):
        engine.open_intervention(student=school['kid'], source='manual', title='t')
        engine.open_intervention(student=school['kid'], source='manual', title='t')
        assert Intervention.objects.count() == 2

    def test_the_school_is_taken_from_the_student_not_the_request(self, school):
        item = _open(school['kid_b'])
        assert item.tenant_id == school['b'].pk
        assert rows(api(school['admin']).get(f'{BASE}/')) == []

    def test_staff_are_told_about_a_new_one_but_not_families_or_other_teachers(self, school):
        link_parent(school['mom'], school['kid'])
        _open(school['kid'])
        assert Notification.objects.filter(recipient=school['admin'], title__startswith='New intervention').count() == 1
        assert Notification.objects.filter(recipient=school['counsellor']).count() == 1
        assert not Notification.objects.filter(recipient__in=[school['mom'], school['ann'], school['admin_b']]).exists()

    def test_when_there_is_an_owner_only_the_owner_is_told(self, school):
        _open(school['kid'], owner=school['ann'])
        assert Notification.objects.filter(recipient=school['ann']).count() == 1
        assert not Notification.objects.filter(recipient=school['admin']).exists()

    def test_quiet_mode_sends_nothing(self, school):
        _open(school['kid'], notify=False)
        assert not Notification.objects.exists()


class TestFiltersSummaryAndAudit:
    def _seed(self, school):
        late = _open(school['kid'], owner=school['ann'], dedupe_key='late', priority='high', due_days=1)
        Intervention.objects.filter(pk=late.pk).update(due_date=timezone.localdate() - timedelta(days=2))
        _open(school['kid2'], source='risk', dedupe_key='risk')
        done = _open(school['kid'], dedupe_key='done')
        Intervention.objects.filter(pk=done.pk).update(status='done')
        return late

    def test_filters(self, school):
        late = self._seed(school)
        c = api(school['admin'])
        assert [i['id'] for i in rows(c.get(f'{BASE}/?overdue=1'))] == [str(late.pk)]
        assert len(rows(c.get(f'{BASE}/?active=1'))) == 2 and len(rows(c.get(f'{BASE}/?status=done'))) == 1
        assert [i['source'] for i in rows(c.get(f'{BASE}/?source=risk'))] == ['risk']
        assert [i['id'] for i in rows(c.get(f'{BASE}/?owner=none&active=1'))] == [rows(c.get(f'{BASE}/?source=risk'))[0]['id']]
        assert [i['id'] for i in rows(api(school['ann']).get(f'{BASE}/?owner=me'))] == [str(late.pk)]
        assert [i['student_name'] for i in rows(c.get(f'{BASE}/?search=ella'))] == ['Ella Jones']

    def test_the_summary_counts_what_the_screen_needs(self, school):
        self._seed(school)
        s = api(school['admin']).get(f'{BASE}/summary/').json()
        assert s == {'open': 2, 'in_progress': 0, 'overdue': 1, 'unassigned': 1, 'mine': 0, 'high_priority': 1}
        assert api(school['ann']).get(f'{BASE}/summary/').json()['mine'] == 1

    def test_reads_and_changes_are_audited(self, school):
        item = _open(school['kid'], dedupe_key='a')
        c = api(school['counsellor'])
        c.get(f'{BASE}/')
        c.get(f'{BASE}/{item.pk}/')
        c.post(f'{BASE}/{item.pk}/start/')
        assert AuditLog.objects.filter(user=school['counsellor'], action='VIEW', resource_type__startswith='interventions/').count() == 2
        assert AuditLog.objects.filter(user=school['counsellor'], action='UPDATE', resource_type='interventions/item').exists()

    def test_another_school_sees_and_touches_nothing(self, school):
        item = _open(school['kid'], dedupe_key='a')
        other = api(school['admin_b'])
        assert rows(other.get(f'{BASE}/')) == [] and other.get(f'{BASE}/{item.pk}/').status_code == 404
        assert other.post(f'{BASE}/{item.pk}/complete/', {'note': 'x'}, format='json').status_code == 404
        assert other.get(f'{BASE}/summary/').json()['open'] == 0
        assert other.patch(f'{BASE}/{item.pk}/', {'title': 'x'}, format='json').status_code == 404


class TestRecordOfSupport:
    """When support began, how much was delivered, what came of it and when it is looked at again."""

    def test_starting_stamps_the_start_date_and_logging_a_session_counts_it(self, school):
        item = _open(school['kid'], owner=school['ann'], dedupe_key='a')
        ann = api(school['ann'])
        assert ann.get(f'{BASE}/{item.pk}/').json()['started_on'] is None
        assert ann.post(f'{BASE}/{item.pk}/log_session/').json()['sessions_delivered'] == 1     # logging a session also starts it
        body = ann.post(f'{BASE}/{item.pk}/log_session/').json()
        assert (body['status'], body['sessions_delivered'], body['started_on']) == ('in_progress', 2, str(timezone.localdate()))
        assert ann.patch(f'{BASE}/{item.pk}/', {'sessions_delivered': 99}, format='json').status_code == 403   # only reviewers patch, and the count is read-only
        assert api(school['admin']).patch(f'{BASE}/{item.pk}/', {'sessions_delivered': 99}, format='json').json()['sessions_delivered'] == 2

    def test_someone_else_cannot_log_a_session_and_a_closed_one_refuses(self, school):
        item = _open(school['kid'], owner=school['ann'], dedupe_key='a')
        assert api(school['ben']).post(f'{BASE}/{item.pk}/log_session/').status_code == 404
        api(school['ann']).post(f'{BASE}/{item.pk}/complete/', {'note': 'Met twice'}, format='json')
        assert api(school['ann']).post(f'{BASE}/{item.pk}/log_session/').status_code == 400

    def test_finishing_records_the_result_and_the_evidence(self, school):
        item = _open(school['kid'], owner=school['ann'], dedupe_key='a')
        c = api(school['ann'])
        assert c.post(f'{BASE}/{item.pk}/complete/', {'note': 'Done', 'outcome': 'magic'}, format='json').status_code == 400
        body = c.post(f'{BASE}/{item.pk}/complete/', {'note': 'Met weekly', 'outcome': 'improved', 'evidence': 'Absences 6 to 1 in a month'}, format='json').json()
        assert (body['status'], body['outcome'], body['evidence']) == ('done', 'improved', 'Absences 6 to 1 in a month')
        assert body['started_on'] == str(timezone.localdate())

    def test_a_review_date_comes_due_and_only_while_active(self, school):
        today = timezone.localdate()
        item = _open(school['kid'], dedupe_key='a')
        admin = api(school['admin'])
        assert admin.patch(f'{BASE}/{item.pk}/', {'review_on': str(today + timedelta(days=7))}, format='json').json()['is_review_due'] is False
        assert admin.patch(f'{BASE}/{item.pk}/', {'review_on': str(today)}, format='json').json()['is_review_due'] is True
        assert admin.get(f'{BASE}/reach/').json()['reviews_due'] == 1
        admin.post(f'{BASE}/{item.pk}/dismiss/', {'note': 'Not needed'}, format='json')
        assert admin.get(f'{BASE}/reach/').json()['reviews_due'] == 0

    def test_the_reach_report_counts_students_sessions_and_results(self, school):
        a = _open(school['kid'], owner=school['ann'], dedupe_key='a')
        b = _open(school['kid2'], owner=school['ann'], dedupe_key='b')
        _open(school['kid2'], dedupe_key='c', title='Not started')
        ann = api(school['ann'])
        ann.post(f'{BASE}/{a.pk}/log_session/'); ann.post(f'{BASE}/{a.pk}/log_session/')
        ann.post(f'{BASE}/{b.pk}/complete/', {'note': 'Done', 'outcome': 'no_change'}, format='json')
        report = api(school['admin']).get(f'{BASE}/reach/').json()
        assert (report['raised'], report['students_flagged'], report['students_reached'], report['sessions_delivered']) == (3, 2, 2, 2)
        assert report['closed'] == 1 and report['results']['no_change'] == 1 and report['closed_without_result'] == 0
        assert report['average_days_to_start'] == 0
        assert api(school['ann']).get(f'{BASE}/reach/').status_code == 403

    def test_the_report_never_includes_another_school(self, school):
        _open(school['kid_b'], dedupe_key='z')
        assert api(school['admin']).get(f'{BASE}/reach/').json()['raised'] == 0
