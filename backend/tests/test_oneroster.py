"""The OneRoster 1.1 roster export (CSV bulk, zipped)."""
import csv
import io
import zipfile

import pytest
from django.apps import apps

from services.core.audit.models import AuditLog
from services.core.tenants.context import use_tenant
from services.education.records import oneroster
from tests.safety_helpers import api, make_student
from tests.test_records import world  # noqa: F401  (a school with a class, students, a teacher, a parent and a second school)

URL = '/api/v1/auth/records/oneroster/'


def _read(response):
    z = zipfile.ZipFile(io.BytesIO(response.content))
    return {n[:-4]: list(csv.DictReader(io.StringIO(z.read(n).decode('utf-8')))) for n in z.namelist()}


@pytest.fixture
def roster(world):  # noqa: F811
    a = world['a']
    with use_tenant(a):
        Teacher = apps.get_model('education_academics', 'Teacher')
        Subject = apps.get_model('education_academics', 'Subject')
        ClassSubject = apps.get_model('education_academics', 'ClassSubject')
        teacher = Teacher.objects.create(tenant=a, full_name='鈴木 一郎', email='suzuki@a.test', employee_id='T-100', joining_date='2020-04-01', phone='090-0000-0000')
        math = Subject.objects.create(tenant=a, name='算数', code='MATH', curriculum_code='E-MATH')
        cs = ClassSubject.objects.create(class_ref=world['cls'], subject=math)
        world['cls'].homeroom_teacher = teacher
        world['cls'].grade_level = 6
        world['cls'].save()
        yamada = make_student(a, full_name='山田 太郎', current_class=world['cls'])
        loose = make_student(a, full_name='田中 花子', current_class=None)
        gone = make_student(a, full_name='退学 生徒', current_class=world['cls'], is_active=False)
        a.settings_json = {'language': 'ja', 'mext_school_code': 'B113110000012'}
        a.save(update_fields=['settings_json'])
    world.update(teacher_row=teacher, math=math, cs=cs, yamada=yamada, loose=loose, gone=gone)
    return world


class TestFiles:
    def test_the_zip_has_a_manifest_and_the_six_files(self, roster):
        r = api(roster['admin']).get(URL)
        assert r.status_code == 200 and r['Content-Type'] == 'application/zip'
        files = _read(r)
        assert set(files) == {'manifest', 'orgs', 'academicSessions', 'courses', 'classes', 'users', 'enrollments'}
        m = {row['propertyName']: row['value'] for row in files['manifest']}
        assert m['oneroster.version'] == '1.1' and m['file.users'] == 'bulk' and m['file.results'] == 'absent' and m['source.systemName'] == 'CC-EMS'

    def test_the_header_of_each_file_is_the_one_roster_one(self, roster):
        z = zipfile.ZipFile(io.BytesIO(api(roster['admin']).get(URL).content))
        assert z.read('users.csv').decode().splitlines()[0] == ','.join(oneroster.FILES['users'])
        assert z.read('enrollments.csv').decode().splitlines()[0] == 'sourcedId,status,dateLastModified,classSourcedId,schoolSourcedId,userSourcedId,role,primary,beginDate,endDate'

    def test_the_school_carries_its_mext_code(self, roster):
        org = _read(api(roster['admin']).get(URL))['orgs']
        assert len(org) == 1 and org[0]['type'] == 'school' and org[0]['identifier'] == 'B113110000012' and org[0]['name'] == roster['a'].name

    def test_subjects_are_courses_and_each_class_is_a_homeroom_plus_a_class_per_subject(self, roster):
        files = _read(api(roster['admin']).get(URL))
        course = next(c for c in files['courses'] if c['title'] == '算数')
        assert course['courseCode'] == 'MATH' and course['subjectCodes'] == 'E-MATH'
        home = next(c for c in files['classes'] if c['sourcedId'] == str(roster['cls'].pk))
        assert home['classType'] == 'homeroom' and home['grades'] == '06' and home['schoolSourcedId'] == str(roster['a'].pk)
        sub = next(c for c in files['classes'] if c['sourcedId'] == str(roster['cs'].pk))
        assert sub['classType'] == 'scheduled' and sub['courseSourcedId'] == str(course['sourcedId']) and sub['title'].endswith('算数')


class TestPeople:
    def test_japanese_names_are_family_name_first_and_other_languages_given_name_first(self, roster):
        users = {u['identifier']: u for u in _read(api(roster['admin']).get(URL))['users']}
        y = users[roster['yamada'].student_id]
        assert y['role'] == 'student' and y['familyName'] == '山田' and y['givenName'] == '太郎' and y['grades'] == '06'
        assert oneroster.split_name('Amy Brown', False) == ('Amy', 'Brown') and oneroster.split_name('山田 太郎', True) == ('太郎', '山田')
        assert oneroster.split_name('Cher', False) == ('Cher', 'Cher')

    def test_teachers_are_users_with_their_staff_number(self, roster):
        t = next(u for u in _read(api(roster['admin']).get(URL))['users'] if u['role'] == 'teacher')
        assert t['username'] == 'T-100' and t['familyName'] == '鈴木' and t['givenName'] == '一郎'

    def test_contact_details_and_passwords_are_left_out_unless_asked_for(self, roster):
        users = _read(api(roster['admin']).get(URL))['users']
        assert all(u['email'] == '' and u['phone'] == '' and u['sms'] == '' and u['password'] == '' for u in users)
        text = api(roster['admin']).get(URL).content
        assert b'suzuki@a.test' not in text and b'090-0000-0000' not in zipfile.ZipFile(io.BytesIO(text)).read('users.csv')
        with_contacts = _read(api(roster['admin']).get(URL, {'contacts': '1'}))['users']
        t = next(u for u in with_contacts if u['role'] == 'teacher')
        assert t['email'] == 'suzuki@a.test' and t['phone'] == '090-0000-0000' and all(u['password'] == '' for u in with_contacts)

    def test_parents_and_other_schools_are_not_in_it(self, roster):
        users = _read(api(roster['admin']).get(URL))['users']
        assert {u['role'] for u in users} == {'student', 'teacher'}
        assert roster['kid_b'].student_id not in {u['identifier'] for u in users}

    def test_students_who_left_are_not_listed(self, roster):
        ids = {u['identifier'] for u in _read(api(roster['admin']).get(URL))['users']}
        assert roster['gone'].student_id not in ids and roster['yamada'].student_id in ids


class TestEnrollments:
    def test_a_student_is_in_the_homeroom_and_each_subject_class(self, roster):
        e = [x for x in _read(api(roster['admin']).get(URL))['enrollments'] if x['userSourcedId'] == str(roster['yamada'].pk)]
        assert {x['classSourcedId'] for x in e} == {str(roster['cls'].pk), str(roster['cs'].pk)} and all(x['role'] == 'student' for x in e)

    def test_the_homeroom_teacher_is_the_primary_teacher_of_the_homeroom(self, roster):
        e = [x for x in _read(api(roster['admin']).get(URL))['enrollments'] if x['role'] == 'teacher']
        assert len(e) == 1 and e[0]['classSourcedId'] == str(roster['cls'].pk) and e[0]['primary'] == 'true'

    def test_a_student_without_a_class_is_a_user_with_no_enrolment(self, roster):
        files = _read(api(roster['admin']).get(URL))
        assert roster['loose'].student_id in {u['identifier'] for u in files['users']}
        assert not [x for x in files['enrollments'] if x['userSourcedId'] == str(roster['loose'].pk)]
        assert api(roster['admin']).get(URL, {'preview': '1'}).json()['skipped']['students_without_class'] >= 1


class TestPreviewAndAccess:
    def test_the_preview_counts_and_says_what_is_left_out(self, roster):
        d = api(roster['admin']).get(URL, {'preview': '1'}).json()
        assert d['files']['courses'] == 1 and d['files']['orgs'] == 1 and d['contacts_included'] is False and d['school_code'] == 'B113110000012'
        assert 'Parents and guardians' in d['left_out'] and 'Email addresses' in d['left_out']
        assert 'Email addresses' not in api(roster['admin']).get(URL, {'preview': '1', 'contacts': '1'}).json()['left_out']

    def test_each_download_is_recorded(self, roster):
        api(roster['admin']).get(URL)
        row = AuditLog.objects.filter(resource_type='education/records/oneroster', action='EXPORT').first()
        assert row is not None and row.new_data['contacts_included'] is False
        before = AuditLog.objects.filter(resource_type='education/records/oneroster').count()
        api(roster['admin']).get(URL, {'preview': '1'})
        assert AuditLog.objects.filter(resource_type='education/records/oneroster').count() == before          # a preview downloads nothing

    def test_only_this_schools_administrator(self, roster):
        for who in ('teacher', 'mom'):
            assert api(roster[who]).get(URL).status_code == 403
        assert api().get(URL).status_code == 401
        other = _read(api(roster['admin_b']).get(URL))
        assert other['orgs'][0]['name'] == roster['b'].name and not [u for u in other['users'] if u['identifier'] == roster['yamada'].student_id]


def test_grade_codes():
    assert [oneroster.grade_code(x) for x in (-1, 0, 1, 6, 12, 13, None)] == ['PK', 'KG', '01', '06', '12', '', '']
