"""Front desk: pickup authorisation, the release log (with its do-not-release hard stop) and visitor sign-in."""
import pytest

from services.core.audit.models import AuditLog
from services.core.tenants.context import use_tenant
from tests.safety_helpers import api, link_parent, make_guardian, make_student, make_user, rows, two_schools

BASE = '/api/v1/education/students'


@pytest.fixture
def desk(db):
    a, b = two_schools()
    return {
        'a': a, 'b': b,
        'admin': make_user(a, 'head@a.test', 'admin'),
        'front': make_user(a, 'desk@a.test', 'front_desk'),
        'teacher': make_user(a, 'ann.teacher@a.test', 'teacher'),
        'parent': make_user(a, 'mom@a.test', 'parent'),
        'front_b': make_user(b, 'desk@b.test', 'front_desk'),
        'kid': make_student(a), 'kid2': make_student(a), 'kid_b': make_student(b),
    }


def _adult(c, student, **kw):
    body = {'student': str(student.pk), 'name': 'Uncle Joe', 'relationship': 'Uncle', 'phone': '555-0102', 'id_checked': True, **kw}
    return c.post('/api/v1/education/students/authorized-adults/', body, format='json')


def _release(c, student, **kw):
    return c.post('/api/v1/education/students/pickup-releases/', {'student': str(student.pk), 'id_confirmed': True, 'reason': 'Dentist', **kw}, format='json')


class TestWhoMayUseIt:
    def test_only_front_desk_and_admin(self, desk):
        for who in ('teacher', 'parent'):
            c = api(desk[who])
            assert c.get('/api/v1/education/students/authorized-adults/').status_code == 403
            assert c.get('/api/v1/education/students/pickup-releases/').status_code == 403
            assert c.get('/api/v1/education/students/visitors/').status_code == 403
            assert c.get('/api/v1/education/students/pickup-list/' + f'?student={desk["kid"].pk}').status_code == 403
        assert api().get('/api/v1/education/students/visitors/').status_code == 401
        for who in ('front', 'admin'):
            assert api(desk[who]).get('/api/v1/education/students/visitors/').status_code == 200


class TestPickupList:
    def test_shows_guardians_who_can_collect_and_extra_adults(self, desk):
        make_guardian(desk['a'], desk['kid'], 'Mary', 'Smith', can_pickup=True, notes='Mother')
        make_guardian(desk['a'], desk['kid'], 'Pete', 'Barred', can_pickup=False, notes='Court order 2025')
        assert _adult(api(desk['front']), desk['kid'], do_not_release=True, court_order_note='Restraining order').status_code == 201
        data = api(desk['front']).get('/api/v1/education/students/pickup-list/' + f'?student={desk["kid"].pk}').json()
        by_name = {g['name']: g for g in data['guardians']}
        assert by_name['Mary Smith']['can_pickup'] is True and by_name['Pete Barred']['can_pickup'] is False
        assert data['authorized_adults'][0]['do_not_release'] is True
        assert data['authorized_adults'][0]['court_order_note'] == 'Restraining order'

    def test_listing_a_students_pickup_list_is_audited(self, desk):
        api(desk['front']).get('/api/v1/education/students/pickup-list/' + f'?student={desk["kid"].pk}')
        assert AuditLog.objects.filter(user=desk['front'], action='VIEW', resource_type='pickup/pickup_list').exists()

    def test_bad_student_is_a_clean_error_not_a_crash(self, desk):
        c = api(desk['front'])
        assert c.get('/api/v1/education/students/pickup-list/' + '?student=not-a-uuid').status_code == 400
        assert c.get('/api/v1/education/students/pickup-list/').status_code in (400, 404)


class TestRelease:
    def test_release_to_a_listed_adult_and_to_a_guardian(self, desk):
        c = api(desk['front'])
        adult = _adult(c, desk['kid']).json()
        r = _release(c, desk['kid'], authorized_adult=adult['id'])
        assert r.status_code == 201, r.content
        assert r.json()['released_to_name'] == 'Uncle Joe' and r.json()['override_used'] is False
        g = make_guardian(desk['a'], desk['kid'])
        r = _release(c, desk['kid'], guardian=str(g.pk), early_dismissal=True)
        assert r.status_code == 201 and r.json()['released_to_name'] == 'Mary Smith'

    def test_cannot_release_to_someone_not_on_this_students_list(self, desk):
        c = api(desk['front'])
        other_kids_adult = _adult(c, desk['kid2']).json()
        assert _release(c, desk['kid'], authorized_adult=other_kids_adult['id']).status_code == 400
        stranger = make_guardian(desk['a'], desk['kid2'], 'Stranger', 'Danger')
        assert _release(c, desk['kid'], guardian=str(stranger.pk)).status_code == 400
        barred = make_guardian(desk['a'], desk['kid'], 'Pete', 'Barred', can_pickup=False)
        assert _release(c, desk['kid'], guardian=str(barred.pk)).status_code == 400

    def test_needs_exactly_one_person_and_a_photo_id_check(self, desk):
        c = api(desk['front'])
        adult = _adult(c, desk['kid']).json()
        g = make_guardian(desk['a'], desk['kid'])
        assert _release(c, desk['kid']).status_code == 400
        assert _release(c, desk['kid'], authorized_adult=adult['id'], guardian=str(g.pk)).status_code == 400
        assert _release(c, desk['kid'], authorized_adult=adult['id'], id_confirmed=False).status_code == 400

    def test_do_not_release_is_a_hard_stop_for_the_front_desk(self, desk):
        c = api(desk['front'])
        barred = _adult(c, desk['kid'], name='Barred Bob', do_not_release=True, court_order_note='Order 12').json()
        r = _release(c, desk['kid'], authorized_adult=barred['id'], override_reason='He says it is fine')
        assert r.status_code == 400 and 'DO NOT RELEASE' in str(r.json())
        assert not rows(c.get('/api/v1/education/students/pickup-releases/'))

    def test_admin_needs_a_typed_reason_and_it_is_audited(self, desk):
        barred = _adult(api(desk['front']), desk['kid'], name='Barred Bob', do_not_release=True).json()
        c = api(desk['admin'])
        assert _release(c, desk['kid'], authorized_adult=barred['id']).status_code == 400
        assert _release(c, desk['kid'], authorized_adult=barred['id'], override_reason='  ').status_code == 400
        r = _release(c, desk['kid'], authorized_adult=barred['id'], override_reason='Court order lifted, copy on file')
        assert r.status_code == 201 and r.json()['override_used'] is True
        entry = AuditLog.objects.get(user=desk['admin'], action='SECURITY', resource_type='pickup/release')
        assert 'Court order lifted' in str(entry.new_data)

    def test_the_release_log_cannot_be_edited_or_deleted(self, desk):
        c = api(desk['front'])
        adult = _adult(c, desk['kid']).json()
        rid = _release(c, desk['kid'], authorized_adult=adult['id']).json()['id']
        url = f'/api/v1/education/students/pickup-releases/{rid}/'
        assert c.patch(url, {'reason': 'changed'}, format='json').status_code == 405
        assert c.delete(url).status_code == 405

    def test_removing_an_adult_who_was_released_to_keeps_the_record(self, desk):
        c = api(desk['front'])
        adult = _adult(c, desk['kid']).json()
        _release(c, desk['kid'], authorized_adult=adult['id'])
        assert c.delete(f"/api/v1/education/students/authorized-adults/{adult['id']}/").status_code == 204
        assert c.get(f"/api/v1/education/students/authorized-adults/{adult['id']}/").json()['is_active'] is False
        # and they can no longer be released to
        assert _release(c, desk['kid'], authorized_adult=adult['id']).status_code == 400

    def test_changing_the_do_not_release_flag_is_audited(self, desk):
        c = api(desk['front'])
        adult = _adult(c, desk['kid']).json()
        c.patch(f"/api/v1/education/students/authorized-adults/{adult['id']}/", {'do_not_release': True}, format='json')
        assert AuditLog.objects.filter(user=desk['front'], action='SECURITY', resource_type='pickup/authorized_adult').exists()


class TestVisitors:
    def test_sign_in_on_site_list_and_sign_out(self, desk):
        c = api(desk['front'])
        v = c.post('/api/v1/education/students/visitors/', {'name': 'Pat Plumber', 'visiting': 'Office', 'purpose': 'Repair', 'badge_number': '14'}, format='json')
        assert v.status_code == 201, v.content
        vid = v.json()['id']
        assert v.json()['on_site'] is True
        c.post('/api/v1/education/students/visitors/', {'name': 'Second Guest', 'badge_number': '15'}, format='json')
        assert {r['name'] for r in rows(c.get('/api/v1/education/students/visitors/' + '?on_site=1'))} == {'Pat Plumber', 'Second Guest'}
        out = c.post(f'/api/v1/education/students/visitors/{vid}/check_out/')
        assert out.status_code == 200 and out.json()['on_site'] is False
        assert [r['name'] for r in rows(c.get('/api/v1/education/students/visitors/' + '?on_site=1'))] == ['Second Guest']
        assert c.post(f'/api/v1/education/students/visitors/{vid}/check_out/').status_code == 400  # already out

    def test_a_visitor_row_cannot_be_forged_out_or_edited(self, desk):
        c = api(desk['front'])
        vid = c.post('/api/v1/education/students/visitors/', {'name': 'Pat'}, format='json').json()['id']
        assert c.patch(f'/api/v1/education/students/visitors/{vid}/', {'name': 'X'}, format='json').status_code == 405
        v = c.post('/api/v1/education/students/visitors/', {'name': 'Sneaky', 'checked_out_at': '2020-01-01T00:00:00Z'}, format='json').json()
        assert v['on_site'] is True


class TestSchoolIsolation:
    def test_another_school_sees_and_touches_nothing(self, desk):
        c, cb = api(desk['front']), api(desk['front_b'])
        adult = _adult(c, desk['kid']).json()
        _release(c, desk['kid'], authorized_adult=adult['id'])
        vid = c.post('/api/v1/education/students/visitors/', {'name': 'Pat'}, format='json').json()['id']

        assert rows(cb.get('/api/v1/education/students/authorized-adults/')) == []
        assert rows(cb.get('/api/v1/education/students/pickup-releases/')) == []
        assert rows(cb.get('/api/v1/education/students/visitors/')) == []
        assert rows(cb.get('/api/v1/education/students/visitors/' + '?on_site=1')) == []
        assert cb.get(f"/api/v1/education/students/authorized-adults/{adult['id']}/").status_code == 404
        assert cb.post(f'/api/v1/education/students/visitors/{vid}/check_out/').status_code == 404
        # school B cannot add a pickup adult or release a student of school A
        assert _adult(cb, desk['kid']).status_code == 400
        assert cb.get('/api/v1/education/students/pickup-list/' + f'?student={desk["kid"].pk}').status_code == 404


class TestStudentLookup:
    def test_staff_find_students_with_minimal_details(self, desk):
        from tests.safety_helpers import make_student
        sam = make_student(desk['a'], full_name='Samantha Lookup')
        make_student(desk['a'], full_name='Someone Else', is_active=False)
        for who in ('front', 'admin', 'teacher'):
            found = api(desk[who]).get(f'{BASE}/lookup/?q=samant').json()
            assert [f['name'] for f in found] == ['Samantha Lookup'] and found[0]['id'] == str(sam.pk)
            assert set(found[0]) == {'id', 'student_id', 'name', 'class_name'}          # nothing more than that
        assert api(desk['front']).get(f'{BASE}/lookup/?q=sam').json()[0]['student_id'] == sam.student_id

    def test_short_queries_return_nothing_and_inactive_students_are_hidden(self, desk):
        assert api(desk['front']).get(f'{BASE}/lookup/?q=s').json() == []
        assert api(desk['front']).get(f'{BASE}/lookup/').json() == []
        from tests.safety_helpers import make_student
        make_student(desk['a'], full_name='Gone Student', is_active=False)
        assert api(desk['front']).get(f'{BASE}/lookup/?q=gone').json() == []

    def test_families_and_other_schools_get_nothing(self, desk):
        from tests.safety_helpers import make_student
        make_student(desk['a'], full_name='Samantha Lookup')
        assert api(desk['parent']).get(f'{BASE}/lookup/?q=samant').status_code == 403
        assert api().get(f'{BASE}/lookup/?q=samant').status_code == 401
        assert api(desk['front_b']).get(f'{BASE}/lookup/?q=samant').json() == []
