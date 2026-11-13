"""The access log for personal information: staff views of student records, prints, and the review of who looked at what."""
from datetime import timedelta

import pytest
from django.utils import timezone

from services.core.audit.models import AuditLog
from tests.safety_helpers import api, link_parent
from tests.test_records import world  # noqa: F401  (a school with a class, two students, a teacher, a parent, and a second school)

REVIEW = '/api/v1/security/access-review/'
PRINT = '/api/v1/security/print-log/'


def _views(user=None, what=None):
    qs = AuditLog.objects.filter(action='VIEW')
    if user is not None:
        qs = qs.filter(user=user)
    if what:
        qs = qs.filter(resource_type=what)
    return qs


class TestViewsAreRecorded:
    def test_opening_a_student_record_is_logged_with_who_and_which_student(self, world):  # noqa: F811
        r = api(world['teacher']).get(f'/api/v1/students/{world["kid"].id}/')
        assert r.status_code == 200
        row = _views(world['teacher'], 'students/profile').get()
        assert row.resource_id == world['kid'].id and row.school_id == world['a'].id

    def test_the_full_profile_and_the_older_route_are_logged_too(self, world):  # noqa: F811
        c = api(world['admin'])
        assert c.get(f'/api/v1/students/{world["kid"].id}/profile/').status_code == 200
        assert c.get(f'/api/v1/auth/students/{world["kid2"].id}/').status_code == 200
        assert set(_views(world['admin'], 'students/profile').values_list('resource_id', flat=True)) == {world['kid'].id, world['kid2'].id}

    def test_opening_the_same_record_again_soon_is_one_entry_but_a_different_student_is_another(self, world):  # noqa: F811
        c = api(world['teacher'])
        for _ in range(3):
            c.get(f'/api/v1/students/{world["kid"].id}/')
        c.get(f'/api/v1/students/{world["kid2"].id}/')
        assert _views(world['teacher'], 'students/profile').count() == 2

    def test_after_a_while_the_same_record_is_logged_again(self, world):  # noqa: F811
        c = api(world['teacher'])
        c.get(f'/api/v1/students/{world["kid"].id}/')
        first = _views(world['teacher'], 'students/profile').get()
        type(first).objects.filter(pk=first.pk).update(timestamp=timezone.now() - timedelta(minutes=30))   # an unprotected, unchained row
        c.get(f'/api/v1/students/{world["kid"].id}/')
        assert _views(world['teacher'], 'students/profile').count() == 2

    def test_a_list_of_students_is_logged_once(self, world):  # noqa: F811
        c = api(world['teacher'])
        assert c.get('/api/v1/students/').status_code == 200
        c.get('/api/v1/students/')
        assert _views(world['teacher'], 'students/list').count() == 1

    def test_a_family_looking_at_its_own_child_is_not_staff_access(self, world):  # noqa: F811
        link_parent(world['mom'], world['kid'])
        api(world['mom']).get(f'/api/v1/students/{world["kid"].id}/')
        assert _views(world['mom']).count() == 0

    def test_a_refused_look_is_not_logged_as_a_view(self, world):  # noqa: F811
        # another school's student: not found for this teacher, so nothing was looked at
        api(world['teacher']).get(f'/api/v1/students/{world["kid_b"].id}/')
        assert _views(world['teacher'], 'students/profile').count() == 0

    def test_views_do_not_count_as_changes_on_the_security_overview(self, world):  # noqa: F811
        api(world['teacher']).get(f'/api/v1/students/{world["kid"].id}/')
        before = api(world['admin']).get('/api/v1/security/overview/').json()['week']['changes']
        for k in (world['kid'], world['kid2']):
            api(world['admin']).get(f'/api/v1/students/{k.id}/')
        assert api(world['admin']).get('/api/v1/security/overview/').json()['week']['changes'] == before

    def test_views_can_be_found_in_the_activity_log(self, world):  # noqa: F811
        api(world['teacher']).get(f'/api/v1/students/{world["kid"].id}/')
        data = api(world['admin']).get('/api/v1/security/activity/', {'action': 'VIEW'}).json()
        assert data['actions']['VIEW'] == 'Viewed'
        assert [r['action_label'] for r in data['results']] == ['Viewed'] and data['results'][0]['who']


class TestPrints:
    def test_a_print_is_logged_as_an_export_with_what_was_printed(self, world):  # noqa: F811
        r = api(world['teacher']).post(PRINT, {'what': 'records', 'id': str(world['kid'].id)}, format='json')
        assert r.status_code == 200
        row = AuditLog.objects.get(resource_type='print/records')
        assert row.action == 'EXPORT' and row.user == world['teacher'] and row.school_id == world['a'].id and row.resource_id == world['kid'].id
        assert row.new_data['label'] == '指導要録'

    def test_only_known_things_can_be_logged_and_only_by_staff(self, world):  # noqa: F811
        assert api(world['teacher']).post(PRINT, {'what': 'something'}, format='json').status_code == 400
        assert api(world['mom']).post(PRINT, {'what': 'records'}, format='json').status_code == 403
        assert api().post(PRINT, {'what': 'records'}, format='json').status_code == 401
        assert AuditLog.objects.filter(resource_type__startswith='print/').count() == 0


class TestReview:
    def _activity(self, world):  # noqa: F811
        t, a = api(world['teacher']), api(world['admin'])
        t.get(f'/api/v1/students/{world["kid"].id}/')
        t.get(f'/api/v1/students/{world["kid2"].id}/')
        t.post(PRINT, {'what': 'term-report', 'id': str(world['kid'].id)}, format='json')
        a.get(f'/api/v1/students/{world["kid"].id}/')

    def test_it_counts_views_students_prints_per_person(self, world):  # noqa: F811
        self._activity(world)
        d = api(world['admin']).get(REVIEW).json()
        by = {r['email']: r for r in d['results']}
        t = by['sato.teacher@a.test']
        assert (t['views'], t['students_viewed'], t['prints'], t['exports'], t['refused']) == (2, 2, 1, 0, 0)
        assert by['head@a.test']['views'] == 1 and by['head@a.test']['role']
        assert d['days'] == 30 and d['totals']['views'] == 3 and d['totals']['prints'] == 1
        assert d['results'][0]['email'] == 'sato.teacher@a.test'          # the busiest first

    def test_the_period_can_be_chosen_and_old_entries_drop_out(self, world):  # noqa: F811
        self._activity(world)
        AuditLog.objects.filter(user=world['teacher']).update(timestamp=timezone.now() - timedelta(days=40))
        assert [r['email'] for r in api(world['admin']).get(REVIEW).json()['results']] == ['head@a.test']
        wide = api(world['admin']).get(REVIEW, {'days': 90}).json()
        assert wide['days'] == 90 and {r['email'] for r in wide['results']} == {'head@a.test', 'sato.teacher@a.test'}
        assert api(world['admin']).get(REVIEW, {'days': 'x'}).json()['days'] == 30
        assert api(world['admin']).get(REVIEW, {'days': 9999}).json()['days'] == 365

    def test_it_exports_to_csv(self, world):  # noqa: F811
        self._activity(world)
        r = api(world['admin']).get(REVIEW, {'export': 'csv'})
        text = r.content.decode('utf-8-sig')
        assert r['Content-Type'].startswith('text/csv') and text.splitlines()[0].startswith('Who,Email,Role,Records viewed')
        assert 'sato.teacher@a.test' in text

    def test_only_this_schools_administrator_sees_it(self, world):  # noqa: F811
        self._activity(world)
        assert api(world['teacher']).get(REVIEW).status_code == 403
        assert api(world['mom']).get(REVIEW).status_code == 403
        assert api().get(REVIEW).status_code == 401
        assert api(world['admin_b']).get(REVIEW).json()['results'] == []
