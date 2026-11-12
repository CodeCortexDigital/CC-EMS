"""MEXT education data standards: the school code, IDs other systems use, and the curriculum code of a subject."""
import pytest
from django.apps import apps

from services.core.audit.models import AuditLog
from services.core.tenants.context import use_tenant
from services.education.academics.serializers import SubjectSerializer
from services.education.records.models import ExternalId
from tests.safety_helpers import api, make_user
from tests.test_records import world  # noqa: F401  (a school with a class, two students, a teacher, a parent and a second school)

BASE = '/api/v1/auth/records'


def _teacher_row(school, employee_id='T-100', name='鈴木 一郎'):
    with use_tenant(school):
        return apps.get_model('education_academics', 'Teacher').objects.create(tenant=school, full_name=name, email='suzuki@a.test', employee_id=employee_id,
                                                                               joining_date='2020-04-01')


class TestSchoolCode:
    def test_it_is_saved_in_capitals_and_read_back(self, world):  # noqa: F811
        a = api(world['admin'])
        assert a.get(f'{BASE}/standards/').json()['school_code'] == ''
        r = a.put(f'{BASE}/standards/', {'school_code': 'b113110000012'}, format='json')
        assert r.status_code == 200 and r.json()['school_code'] == 'B113110000012'
        assert a.get(f'{BASE}/standards/').json()['school_code'] == 'B113110000012'
        assert AuditLog.objects.filter(resource_type__icontains='mext-school-code').exists()

    @pytest.mark.parametrize('bad', ['113110000012', 'B11311', 'BB13110000012', 'B11311000001X', 'ｂ113110000012'.replace('ｂ', 'あ')])
    def test_a_wrongly_shaped_code_is_refused(self, world, bad):  # noqa: F811
        r = api(world['admin']).put(f'{BASE}/standards/', {'school_code': bad}, format='json')
        assert r.status_code == 400 and 'twelve digits' in r.json()['school_code']

    def test_an_empty_code_clears_it(self, world):  # noqa: F811
        a = api(world['admin'])
        a.put(f'{BASE}/standards/', {'school_code': 'B113110000012'}, format='json')
        assert a.put(f'{BASE}/standards/', {'school_code': ''}, format='json').json()['school_code'] == ''

    def test_each_school_has_its_own_and_only_administrators_may_change_it(self, world):  # noqa: F811
        api(world['admin']).put(f'{BASE}/standards/', {'school_code': 'B113110000012'}, format='json')
        assert api(world['admin_b']).get(f'{BASE}/standards/').json()['school_code'] == ''
        for who in ('teacher', 'mom'):
            assert api(world[who]).get(f'{BASE}/standards/').status_code == 403
            assert api(world[who]).put(f'{BASE}/standards/', {'school_code': 'B113110000012'}, format='json').status_code == 403


class TestExternalIds:
    def test_ids_are_saved_by_our_id_and_listed(self, world):  # noqa: F811
        a = api(world['admin'])
        t = _teacher_row(world['a'])
        r = a.post(f'{BASE}/external-ids/', {'system': '教育委員会', 'rows': [
            {'kind': 'student', 'local_id': world['kid'].student_id, 'external_id': 'S-0001'},
            {'kind': 'teacher', 'local_id': t.employee_id, 'external_id': 'K-9'}]}, format='json').json()
        assert r['saved'] == 2 and r['errors'] == []
        got = {x['kind']: x for x in r['results']}
        assert got['student']['external_id'] == 'S-0001' and got['student']['name'] == world['kid'].full_name
        assert got['teacher']['external_id'] == 'K-9' and got['teacher']['local_id'] == 'T-100'
        assert r['systems'] == ['教育委員会']

    def test_csv_text_can_be_pasted_and_a_header_is_skipped(self, world):  # noqa: F811
        a = api(world['admin'])
        text = f"kind,local_id,external_id\nstudent,{world['kid'].student_id},A1\nstudent,{world['kid2'].student_id},A2\n"
        r = a.post(f'{BASE}/external-ids/', {'system': 'MEXT', 'csv': text}, format='json').json()
        assert r['saved'] == 2 and sorted(x['external_id'] for x in r['results']) == ['A1', 'A2']

    def test_a_person_has_one_id_per_system_and_a_new_one_replaces_it(self, world):  # noqa: F811
        a = api(world['admin'])
        row = {'kind': 'student', 'local_id': world['kid'].student_id, 'external_id': 'OLD'}
        a.post(f'{BASE}/external-ids/', {'system': 'MEXT', 'rows': [row]}, format='json')
        r = a.post(f'{BASE}/external-ids/', {'system': 'MEXT', 'rows': [{**row, 'external_id': 'NEW'}]}, format='json').json()
        assert [x['external_id'] for x in r['results']] == ['NEW']
        with use_tenant(world['a']):
            assert ExternalId.objects.count() == 1

    def test_the_same_id_cannot_be_given_to_two_students_in_one_system(self, world):  # noqa: F811
        a = api(world['admin'])
        r = a.post(f'{BASE}/external-ids/', {'system': 'MEXT', 'rows': [
            {'kind': 'student', 'local_id': world['kid'].student_id, 'external_id': 'X1'},
            {'kind': 'student', 'local_id': world['kid2'].student_id, 'external_id': 'X1'}]}, format='json').json()
        assert r['saved'] == 1 and len(r['errors']) == 1 and 'already used' in r['errors'][0]['message'] and r['errors'][0]['row'] == 2

    def test_bad_rows_are_reported_in_plain_words_and_the_good_ones_still_save(self, world):  # noqa: F811
        r = api(world['admin']).post(f'{BASE}/external-ids/', {'system': 'MEXT', 'rows': [
            {'kind': 'student', 'local_id': 'NOPE', 'external_id': 'X'}, {'kind': 'pet', 'local_id': 'a', 'external_id': 'b'},
            {'kind': 'student', 'local_id': world['kid'].student_id, 'external_id': ''},
            {'kind': 'student', 'local_id': world['kid'].student_id, 'external_id': 'OK'}]}, format='json').json()
        assert r['saved'] == 1 and [e['row'] for e in r['errors']] == [1, 2, 3] and 'No student with the ID NOPE' in r['errors'][0]['message']

    def test_a_system_name_and_some_rows_are_required(self, world):  # noqa: F811
        a = api(world['admin'])
        assert a.post(f'{BASE}/external-ids/', {'rows': [{}]}, format='json').status_code == 400
        assert a.post(f'{BASE}/external-ids/', {'system': 'X', 'rows': []}, format='json').status_code == 400

    def test_export_and_delete(self, world):  # noqa: F811
        a = api(world['admin'])
        r = a.post(f'{BASE}/external-ids/', {'system': 'MEXT', 'rows': [{'kind': 'student', 'local_id': world['kid'].student_id, 'external_id': 'Z9'}]}, format='json').json()
        csv_text = a.get(f'{BASE}/external-ids/', {'system': 'MEXT', 'export': 'csv'}).content.decode('utf-8-sig')
        assert csv_text.splitlines()[0] == 'kind,local_id,name,system,external_id' and 'Z9' in csv_text
        assert a.delete(f'{BASE}/external-ids/?id={r["results"][0]["id"]}').json()['results'] == []

    def test_other_schools_and_other_roles_see_and_change_nothing(self, world):  # noqa: F811
        a = api(world['admin'])
        r = a.post(f'{BASE}/external-ids/', {'system': 'MEXT', 'rows': [{'kind': 'student', 'local_id': world['kid'].student_id, 'external_id': 'Z9'}]}, format='json').json()
        b = api(world['admin_b'])
        assert b.get(f'{BASE}/external-ids/').json()['results'] == []
        assert b.delete(f'{BASE}/external-ids/?id={r["results"][0]["id"]}').status_code == 404
        # the same ID may be used in another school: IDs are only unique within a school and system
        assert b.post(f'{BASE}/external-ids/', {'system': 'MEXT', 'rows': [{'kind': 'student', 'local_id': world['kid_b'].student_id, 'external_id': 'Z9'}]},
                      format='json').json()['saved'] == 1
        for who in ('teacher', 'mom'):
            assert api(world[who]).get(f'{BASE}/external-ids/').status_code == 403

    def test_a_student_cannot_be_matched_to_someone_in_another_school(self, world):  # noqa: F811
        r = api(world['admin']).post(f'{BASE}/external-ids/', {'system': 'MEXT', 'rows': [{'kind': 'student', 'local_id': world['kid_b'].student_id, 'external_id': 'Q'}]},
                                     format='json').json()
        assert r['saved'] == 0 and 'No student' in r['errors'][0]['message']


def test_a_subject_has_a_curriculum_code(db):
    assert 'curriculum_code' in SubjectSerializer().fields
    s = SubjectSerializer(data={'name': '算数', 'code': 'MATH', 'credits': 1, 'curriculum_code': '1020'})
    assert s.is_valid(), s.errors
    assert s.validated_data['curriculum_code'] == '1020'
    assert SubjectSerializer(data={'name': '国語', 'code': 'JPN', 'credits': 1}).is_valid()      # the code is optional
