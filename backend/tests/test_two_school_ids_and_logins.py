"""Two schools signed up separately: each school numbers its own students and staff, and their portal logins work.

Reproduces a manual test: school one is created and gets student STU0001; school two is created later and its first student was
silently renumbered (student numbers had to be unique across every school), and portal sign-in with the IDs failed.
"""
import datetime

import pytest
from rest_framework.test import APIClient

from services.core.tenants.signup import create_school_with_admin

LOGIN = '/api/v1/auth/login/'


def _signup(name, email):
    school, _ = create_school_with_admin(school_name=name, admin_email=email, admin_name='Head', password='Sturdy-Pass-91x')
    api = APIClient()
    res = api.post(LOGIN, {'email': email, 'password': 'Sturdy-Pass-91x'}, format='json')
    assert res.status_code == 200, res.content
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.json()['access']}")
    return school, api


def _student(api, name, email, student_id=None):
    body = {'full_name': name, 'email': email, 'date_of_birth': '2015-04-02', 'gender': 'female'}
    if student_id is not None:
        body['student_id'] = student_id
    return api.post('/api/v1/students/', body, format='json')


def _staff(api, name, email, employee_id=None):
    body = {'full_name': name, 'email': email, 'joining_date': datetime.date.today().isoformat(), 'phone': '555-0100', 'gender': 'female'}
    if employee_id is not None:
        body['employee_id'] = employee_id
    return api.post('/api/v1/auth/academics/teachers/', body, format='json')


def _credentials(api, kind, pk):
    res = api.get(f'/api/v1/auth/credentials/{kind}/{pk}/')
    assert res.status_code == 200, res.content
    return res.json()


def _sign_in(identifier, password):
    return APIClient().post(LOGIN, {'user_id': identifier, 'password': password}, format='json').status_code


@pytest.fixture
def two(db):
    a, api_a = _signup('Alder Academy', 'head@alder.test')
    b, api_b = _signup('Birch Academy', 'head@birch.test')
    return a, api_a, b, api_b


class TestStudentNumbers:
    def test_two_schools_can_both_start_at_0001_and_neither_is_renumbered(self, two):
        a, api_a, b, api_b = two
        first, second = _student(api_a, 'Amy Alder', 'amy@alder.test', 'STU0001'), _student(api_b, 'Ben Birch', 'ben@birch.test', 'STU0001')
        assert first.status_code == second.status_code == 201, (first.content, second.content)
        assert first.json()['student_id'] == f'{a.tenant_code}-STU0001'
        assert second.json()['student_id'] == f'{b.tenant_code}-STU0001'

    def test_blank_numbers_count_up_for_each_school_on_its_own(self, two):
        a, api_a, b, api_b = two
        ids_a = [_student(api_a, f'A {i}', f'a{i}@alder.test').json()['student_id'] for i in (1, 2, 3)]
        ids_b = [_student(api_b, f'B {i}', f'b{i}@birch.test').json()['student_id'] for i in (1, 2)]
        assert ids_a == [f'{a.tenant_code}-STU000{i}' for i in (1, 2, 3)]
        assert ids_b == [f'{b.tenant_code}-STU000{i}' for i in (1, 2)]

    def test_a_number_already_used_in_the_same_school_is_refused_not_changed(self, two):
        a, api_a, b, api_b = two
        assert _student(api_a, 'Amy', 'amy@alder.test', 'STU0005').status_code == 201
        again = _student(api_a, 'Amy Two', 'amy2@alder.test', 'STU0005')
        assert again.status_code == 400 and 'already in use' in again.content.decode()
        assert _student(api_a, 'Amy Three', 'amy3@alder.test', f'{a.tenant_code}-STU0005').status_code == 400
        assert _student(api_b, 'Ben', 'ben@birch.test', 'STU0005').status_code == 201

    def test_changing_a_student_keeps_the_number_they_already_have(self, two):
        a, api_a, *_ = two
        made = _student(api_a, 'Amy Alder', 'amy@alder.test', 'STU0001').json()
        res = api_a.patch(f"/api/v1/students/{made['id']}/", {'full_name': 'Amy A. Alder', 'student_id': made['student_id']}, format='json')
        assert res.status_code == 200 and res.json()['student_id'] == made['student_id']


class TestEmployeeIds:
    def test_staff_get_the_school_code_and_count_up_per_school(self, two):
        a, api_a, b, api_b = two
        t1, t2 = _staff(api_a, 'Tess Alder', 'tess@alder.test'), _staff(api_a, 'Tia Alder', 'tia@alder.test')
        t3 = _staff(api_b, 'Tom Birch', 'tom@birch.test')
        assert [t.json()['employee_id'] for t in (t1, t2, t3)] == [f'{a.tenant_code}-EMP-0001', f'{a.tenant_code}-EMP-0002', f'{b.tenant_code}-EMP-0001']

    def test_two_schools_can_both_type_emp_0001(self, two):
        a, api_a, b, api_b = two
        x, y = _staff(api_a, 'Tess', 'tess@alder.test', 'EMP-0001'), _staff(api_b, 'Tom', 'tom@birch.test', 'EMP-0001')
        assert x.status_code == y.status_code == 201, (x.content, y.content)
        assert x.json()['employee_id'] != y.json()['employee_id']
        assert _staff(api_a, 'Tara', 'tara@alder.test', 'EMP-0001').status_code == 400


class TestPortalSignIn:
    def test_students_and_staff_of_both_schools_sign_in_with_their_ids_and_issued_passwords(self, two):
        a, api_a, b, api_b = two
        for api, tag in ((api_a, 'alder'), (api_b, 'birch')):
            s = _student(api, f'Stu {tag}', f'stu@{tag}.test', 'STU0001').json()
            t = _staff(api, f'Tea {tag}', f'tea@{tag}.test', 'EMP-0001').json()
            student, staff = _credentials(api, 'student', s['id'])['student'], _credentials(api, 'teacher', t['id'])['staff']
            assert student['username'] == s['student_id'] and staff['username'] == t['employee_id']
            assert _sign_in(s['student_id'], student['password']) == 200, f'student {s["student_id"]} could not sign in'
            assert _sign_in(t['employee_id'], staff['password']) == 200, f'staff {t["employee_id"]} could not sign in'
            assert _sign_in(s['student_id'], 'not-the-password-1') == 401
