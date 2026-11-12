"""The 調査書: assembled from the junior-high 指導要録, issued by the principal to a named school, kept as issued."""
from datetime import date

import pytest

from services.core.audit.models import AuditLog
from services.core.tenants.context import use_tenant
from services.education.academics.models import SchoolClass
from tests.safety_helpers import api, make_student, make_user, two_schools
from tests.test_records import _class_with_students, _teacher_of

BASE = '/api/v1/auth/records'
RATINGS = {1: {'JPN': 4, 'MATH': 5, 'SCI': 3, 'SOC': 4, 'MUS': 5, 'ART': 4, 'PE': 4, 'HOME': 3, 'ENG': 5, 'ELEC': 5},
           2: {'JPN': 5, 'MATH': 5, 'SCI': 4, 'SOC': 4, 'MUS': 5, 'ART': 4, 'PE': 5, 'HOME': 3, 'ENG': 5},
           3: {'JPN': 5, 'MATH': 5, 'SCI': 5, 'SOC': 5, 'MUS': 5, 'ART': 5, 'PE': 5, 'HOME': 4, 'ENG': 5}}


@pytest.fixture
def world(db):
    a, b = two_schools()
    _year, cls, _sec, kids = _class_with_students(a, name='3年', grade_level=9, students=1)
    kid = kids[0]
    kid.date_of_birth = date(2011, 5, 1)
    kid.save()
    return {'a': a, 'b': b, 'cls': cls, 'kid': kid, 'admin': make_user(a, 'head@a.test', 'admin'), 'teacher': _teacher_of(a, cls),
            'admin_b': make_user(b, 'head@b.test', 'admin'), 'mom': make_user(a, 'mom@a.test', 'parent')}


def _record(world):
    r = api(world['admin']).post(f'{BASE}/open/', {'student': str(world['kid'].pk)}, format='json')
    assert r.status_code in (200, 201), r.content
    return r.json()['id']


def _fill(world, rec, grade, seal=True, ratings=None):
    body = {'year_label': f'{2023 + grade}年度', 'class_name': f'{grade}年1組', 'teacher_name': '佐藤 花', 'principal_name': '鈴木 一郎',
            'school_days': 200, 'suspended_days': 1, 'absent_days': grade,
            'content': {'subjects': {c: {'rating': v} for c, v in (ratings or RATINGS[grade]).items()}, 'comment': f'{grade}年の所見',
                        'special_activities': {'class_activity': True}, 'behaviour': {'responsibility': True}}}
    r = api(world['teacher']).put(f'{BASE}/{rec}/years/{grade}/', body, format='json')
    assert r.status_code == 200, r.content
    if seal:
        assert api(world['teacher']).post(f'{BASE}/{rec}/years/{grade}/confirm/', {'as': 'teacher'}, format='json').status_code == 200
        assert api(world['admin']).post(f'{BASE}/{rec}/years/{grade}/confirm/', {'as': 'principal'}, format='json').status_code == 200


class TestPreview:
    def test_it_is_assembled_from_the_three_years_with_totals(self, world):
        rec = _record(world)
        for g in (1, 2, 3):
            _fill(world, rec, g)
        d = api(world['teacher']).get(f'{BASE}/{rec}/chosasho/').json()['chosasho']
        assert d['ready'] is True and d['problems'] == []
        by = {s['code']: s['ratings'] for s in d['subjects']}
        assert by['MATH'] == {'1': 5, '2': 5, '3': 5} and by['SCI'] == {'1': 3, '2': 4, '3': 5}
        # the total is of the nine required subjects: the elective (選択教科) is not added
        assert d['totals']['1'] == {'sum': 37, 'count': 9, 'max': 45} and d['totals']['3'] == {'sum': 44, 'count': 9, 'max': 45}
        assert d['student']['name'] == '山田 太郎0' and d['student']['date_of_birth'] == '2011-05-01' and d['school']['principal'] == '鈴木 一郎'
        assert d['comments']['3'] == '3年の所見' and d['attendance']['2'] == {'school_days': 200, 'suspended_days': 1, 'absent_days': 2, 'remarks': ''}
        assert [m['years'] for m in d['special_activities'] if m['key'] == 'class_activity'] == [{'1': True, '2': True, '3': True}]
        assert [m['years'] for m in d['behaviour'] if m['key'] == 'responsibility'] == [{'1': True, '2': True, '3': True}]

    def test_it_lists_what_stops_it_being_issued(self, world):
        rec = _record(world)
        _fill(world, rec, 1)
        _fill(world, rec, 2, seal=False)
        d = api(world['admin']).get(f'{BASE}/{rec}/chosasho/').json()['chosasho']
        assert d['ready'] is False
        assert d['problems'] == ['第2学年に校長の印がありません。', '第3学年の記録がありません。']

    def test_only_a_junior_high_record_has_one(self, world):
        with use_tenant(world['a']):
            cls6 = SchoolClass.objects.create(tenant=world['a'], name='6年', code='C6x', grade_level=6)
        kid = make_student(world['a'], full_name='小学 生', current_class=cls6)
        r = api(world['admin']).post(f'{BASE}/open/', {'student': str(kid.pk)}, format='json').json()
        assert api(world['admin']).get(f'{BASE}/{r["id"]}/chosasho/').status_code == 400


class TestIssue:
    def test_the_principal_issues_it_and_it_is_kept_as_issued(self, world):
        rec = _record(world)
        for g in (1, 2, 3):
            _fill(world, rec, g)
        a = api(world['admin'])
        r = a.post(f'{BASE}/{rec}/chosasho/', {'issued_to': 'みどり県立 第一高等学校', 'note': '推薦入試'}, format='json')
        assert r.status_code == 201, r.content
        issue = r.json()
        assert issue['issued_to'] == 'みどり県立 第一高等学校' and issue['issued_by'] and issue['snapshot']['ready'] is True
        # a correction made afterwards (re-open, change a rating) changes the preview but not what was issued
        assert a.post(f'{BASE}/{rec}/years/3/reopen/', {'reason': '訂正'}, format='json').status_code == 200
        api(world['teacher']).put(f'{BASE}/{rec}/years/3/', {'content': {'subjects': {'MATH': {'rating': 2}}}}, format='json')
        now = a.get(f'{BASE}/{rec}/chosasho/').json()
        assert [s for s in now['chosasho']['subjects'] if s['code'] == 'MATH'][0]['ratings']['3'] == 2
        kept = a.get(f'{BASE}/{rec}/chosasho/{issue["id"]}/').json()
        assert [s for s in kept['snapshot']['subjects'] if s['code'] == 'MATH'][0]['ratings']['3'] == 5
        assert [i['issued_to'] for i in now['issues']] == ['みどり県立 第一高等学校']
        assert AuditLog.objects.filter(resource_type__icontains='chosasho-issue').exists()

    def test_it_cannot_be_issued_before_all_three_years_are_sealed(self, world):
        rec = _record(world)
        _fill(world, rec, 1)
        r = api(world['admin']).post(f'{BASE}/{rec}/chosasho/', {'issued_to': '高校'}, format='json')
        assert r.status_code == 409 and len(r.json()['problems']) == 2

    def test_it_needs_the_receiving_school_and_only_the_principal_may_issue(self, world):
        rec = _record(world)
        for g in (1, 2, 3):
            _fill(world, rec, g)
        assert api(world['admin']).post(f'{BASE}/{rec}/chosasho/', {'issued_to': ' '}, format='json').status_code == 400
        assert api(world['teacher']).post(f'{BASE}/{rec}/chosasho/', {'issued_to': '高校'}, format='json').status_code == 403

    def test_families_and_other_schools_have_no_access(self, world):
        rec = _record(world)
        for g in (1, 2, 3):
            _fill(world, rec, g)
        issue = api(world['admin']).post(f'{BASE}/{rec}/chosasho/', {'issued_to': '高校'}, format='json').json()
        assert api(world['mom']).get(f'{BASE}/{rec}/chosasho/').status_code == 403
        assert api(world['admin_b']).get(f'{BASE}/{rec}/chosasho/').status_code == 404
        assert api(world['admin_b']).get(f'{BASE}/{rec}/chosasho/{issue["id"]}/').status_code == 404
