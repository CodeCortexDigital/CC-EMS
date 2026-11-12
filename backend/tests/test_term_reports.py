"""The term report (通知表): the school's layout, opening and filling a report, finalising, re-opening, who may use it and school isolation."""
from datetime import date
from types import SimpleNamespace

import pytest
from django.apps import apps

from services.core.audit.models import AuditLog
from services.core.tenants.context import use_tenant
from services.education.records import termreport
from services.education.records.models import TermReport
from tests.safety_helpers import api
from tests.test_records import world  # noqa: F401  (the same school, class, teacher and family the cumulative-record tests use)

BASE = '/api/v1/auth/records'


@pytest.fixture
def terms(world):  # noqa: F811
    with use_tenant(world['a']):
        T = apps.get_model('education_academics', 'Term')
        t1 = T.objects.create(tenant=world['a'], academic_year=world['year'], name='1学期', order=1, start_date=date(2026, 4, 6), end_date=date(2026, 7, 20))
        t2 = T.objects.create(tenant=world['a'], academic_year=world['year'], name='2学期', order=2, start_date=date(2026, 9, 1), end_date=date(2026, 12, 25))
    return t1, t2


def _open(c, student, term):
    r = c.post(f'{BASE}/term/open/', {'student': str(student.pk), 'term': str(term.pk)}, format='json')
    assert r.status_code in (200, 201), r.content
    return r.json()


# ------------------------------------------------------------------------------------------------ the engine
class TestEngine:
    def test_default_layouts_follow_the_reference_subjects(self):
        e, j = termreport.default_config('elementary'), termreport.default_config('junior_high')
        assert e['scale'] == 'abc' and '算数' in e['subjects'] and '数学' not in e['subjects']
        assert j['scale'] == 'five' and '数学' in j['subjects']
        assert len(e['conduct_items']) == 10 and e['comment_fields'][0]['key'] == 'homeroom'

    @pytest.mark.parametrize('scale,percent,expected', [('abc', 92, 'A'), ('abc', 80, 'A'), ('abc', 79.9, 'B'), ('abc', 50, 'B'), ('abc', 12, 'C'),
                                                        ('five', 95, '5'), ('five', 75, '4'), ('five', 60, '3'), ('five', 40, '2'), ('five', 10, '1'),
                                                        ('percent', 87.4, '87'), ('abc', None, '')])
    def test_a_percentage_becomes_a_rating_in_the_layouts_scale(self, scale, percent, expected):
        cfg = {**termreport.default_config(), 'scale': scale}
        assert termreport.rating_from_percent(cfg, percent) == expected

    @pytest.mark.parametrize('change,fragment', [({'subjects': []}, 'at least one subject'), ({'subjects': ['国語', '国語']}, 'each name once'),
                                                 ({'scale': 'stars'}, 'rating scale'), ({'comment_fields': [{'key': 'a', 'label': ''}]}, 'comment box'),
                                                 ({'comment_fields': [{'key': 'a', 'label': 'x'}, {'key': 'a', 'label': 'y'}]}, 'different key')])
    def test_a_bad_layout_is_refused_in_plain_words(self, change, fragment):
        cfg, problem = termreport.clean_config({**termreport.default_config(), **change})
        assert cfg is None and fragment in problem

    def test_content_is_checked_against_the_layout(self):
        cfg = termreport.default_config('elementary')
        ok, problem = termreport.clean_content(cfg, {'subjects': {'国語': {'v1': 'A', 'v2': 'B', 'v3': '', 'rating': 'C'}}, 'conduct': {'責任感': True},
                                                     'comments': {'homeroom': 'よくがんばりました'}})
        assert problem is None and ok['subjects']['国語']['rating'] == 'C' and ok['conduct'] == {'責任感': True}
        for bad in ({'subjects': {'体操': {}}}, {'subjects': {'国語': {'v1': 'D'}}}, {'subjects': {'国語': {'rating': '5'}}},
                    {'conduct': {'遅刻': True}}, {'comments': {'other': 'x'}}, {'comments': {'homeroom': 'あ' * 1501}}):
            assert termreport.clean_content(cfg, bad)[0] is None, bad


# ------------------------------------------------------------------------------------------------ layouts
class TestLayouts:
    def test_the_first_visit_makes_a_starting_layout_for_each_level(self, world):  # noqa: F811
        data = api(world['teacher']).get(f'{BASE}/term-layouts/').json()
        assert {x['level'] for x in data['layouts']} == {'elementary', 'junior_high'} and all(x['is_default'] for x in data['layouts'])
        assert 'abc' in data['scales'] and len(data['viewpoints']) == 3

    def test_only_an_administrator_changes_it(self, world):  # noqa: F811
        lay = api(world['admin']).get(f'{BASE}/term-layouts/').json()['layouts'][0]
        body = {**lay, 'name': '若葉 通知表', 'config': {**lay['config'], 'subjects': ['国語', '算数']}}
        assert api(world['teacher']).post(f'{BASE}/term-layouts/', body, format='json').status_code == 403
        r = api(world['admin']).post(f'{BASE}/term-layouts/', body, format='json')
        assert r.status_code == 200 and r.json()['config']['subjects'] == ['国語', '算数'] and r.json()['name'] == '若葉 通知表'
        assert api(world['admin']).post(f'{BASE}/term-layouts/', {**body, 'config': {**body['config'], 'subjects': []}}, format='json').status_code == 400

    def test_a_new_default_replaces_the_old_one(self, world):  # noqa: F811
        c = api(world['admin'])
        c.get(f'{BASE}/term-layouts/')
        new = c.post(f'{BASE}/term-layouts/', {'name': '別の様式', 'level': 'elementary', 'config': termreport.default_config(), 'is_default': True}, format='json').json()
        rows = [x for x in c.get(f'{BASE}/term-layouts/').json()['layouts'] if x['level'] == 'elementary']
        assert [x['id'] for x in rows if x['is_default']] == [new['id']]

    def test_families_and_other_schools_see_nothing(self, world):  # noqa: F811
        assert api(world['mom']).get(f'{BASE}/term-layouts/').status_code == 403
        api(world['admin']).get(f'{BASE}/term-layouts/')
        assert api(world['admin_b']).get(f'{BASE}/term-layouts/').json()['layouts'][0]['name'] == '小学校 通知表'
        with use_tenant(world['b']):
            assert apps.get_model('education_records', 'TermReportLayout').objects.count() == 2


# ------------------------------------------------------------------------------------------------ a report
class TestReport:
    def test_opening_fills_the_class_teacher_and_attendance_of_the_term(self, world, terms):  # noqa: F811
        school, kid = world['a'], world['kid']
        A = apps.get_model('education_attendance', 'AttendanceRecord')
        for d in (date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)):
            A.objects.create(tenant=school, student=world['kid2'], date=d, status='present')
        A.objects.create(tenant=school, student=kid, date=date(2026, 9, 1), status='present')
        A.objects.create(tenant=school, student=kid, date=date(2026, 9, 2), status='absent', reason='illness')
        A.objects.create(tenant=school, student=kid, date=date(2026, 9, 3), status='absent', reason='bereavement')
        r = api(world['teacher']).post(f'{BASE}/term/open/', {'student': str(kid.pk), 'term': str(terms[1].pk)}, format='json')
        assert r.status_code == 201, r.content
        rep = r.json()
        assert (rep['year_label'], rep['term_label'], rep['class_name'], rep['teacher_name']) == ('2026年度', '2学期', '6年1組', '佐藤 花')
        assert (rep['school_days'], rep['suspended_days'], rep['absent_days']) == (3, 1, 1)
        assert rep['layout']['subjects'][0] == '国語' and rep['is_locked'] is False

    def test_opening_twice_gives_the_same_report(self, world, terms):  # noqa: F811
        c = api(world['teacher'])
        a, b = _open(c, world['kid'], terms[0]), _open(c, world['kid'], terms[0])
        assert a['id'] == b['id']
        assert _open(c, world['kid'], terms[1])['id'] != a['id']

    def test_ratings_come_from_the_gradebook_but_a_typed_rating_stays(self, world, terms, monkeypatch):  # noqa: F811
        school, kid = world['a'], world['kid']
        with use_tenant(school):
            subj = apps.get_model('education_academics', 'Subject').objects.create(tenant=school, name='国語', code='JPN6')
            apps.get_model('education_academics', 'ClassSubject').objects.create(class_ref=world['cls'], subject=subj)
        monkeypatch.setattr('services.education.gradebook.calc.term_grade', lambda *a, **k: SimpleNamespace(percent=88))
        c = api(world['teacher'])
        rep = _open(c, kid, terms[0])
        assert rep['content']['subjects']['国語']['rating'] == 'A'
        assert '算数' in rep['content']['subjects'] and rep['content']['subjects']['算数']['rating'] == ''   # no gradebook subject: left for the teacher
        content = {'subjects': {'国語': {'v1': 'B', 'v2': 'B', 'v3': 'B', 'rating': 'B'}}}
        assert c.put(f'{BASE}/term/{rep["id"]}/', {'content': content}, format='json').status_code == 200
        again = c.post(f'{BASE}/term/{rep["id"]}/prefill/').json()
        assert again['content']['subjects']['国語']['rating'] == 'B'

    def test_saving_checks_the_layout_and_reads_back(self, world, terms):  # noqa: F811
        c = api(world['teacher'])
        rep = _open(c, world['kid'], terms[0])
        body = {'content': {'subjects': {'算数': {'v1': 'A', 'v2': 'A', 'v3': 'B', 'rating': 'A'}}, 'conduct': {'思いやり・協力': True},
                            'comments': {'homeroom': 'みんなに優しい子です。'}}, 'attendance_remarks': '', 'absent_days': '2'}
        r = c.put(f'{BASE}/term/{rep["id"]}/', body, format='json')
        assert r.status_code == 200, r.content
        got = c.get(f'{BASE}/term/{rep["id"]}/').json()
        assert got['content']['comments']['homeroom'] == 'みんなに優しい子です。' and got['absent_days'] == 2
        assert c.put(f'{BASE}/term/{rep["id"]}/', {'content': {'subjects': {'国語': {'rating': 'E'}}}}, format='json').status_code == 400
        assert c.put(f'{BASE}/term/{rep["id"]}/', {'absent_days': '400'}, format='json').status_code == 400
        assert c.put(f'{BASE}/term/{rep["id"]}/', {'absent_days': 'many'}, format='json').status_code == 400

    def test_an_old_report_keeps_its_layout_when_the_school_changes_it(self, world, terms):  # noqa: F811
        c = api(world['teacher'])
        rep = _open(c, world['kid'], terms[0])
        lay = [x for x in api(world['admin']).get(f'{BASE}/term-layouts/').json()['layouts'] if x['level'] == 'elementary'][0]
        api(world['admin']).post(f'{BASE}/term-layouts/', {**lay, 'config': {**lay['config'], 'subjects': ['国語']}}, format='json')
        assert len(c.get(f'{BASE}/term/{rep["id"]}/').json()['layout']['subjects']) > 1
        assert len(_open(c, world['kid2'], terms[0])['layout']['subjects']) == 1

    def test_the_roster_lists_the_class_and_who_has_a_report(self, world, terms):  # noqa: F811
        c = api(world['teacher'])
        _open(c, world['kid'], terms[0])
        r = c.get(f'{BASE}/term/roster/', {'class': str(world['cls'].pk), 'term': str(terms[0].pk)}).json()
        assert [t['name'] for t in r['terms']] == ['1学期', '2学期'] and r['year'] == '2026年度'
        assert {x['student_name']: bool(x['report_id']) for x in r['results']} == {'山田 太郎0': True, '山田 太郎1': False}
        assert api(world['teacher']).get(f'{BASE}/term/roster/', {'class': str(world['outsider'].current_class.pk), 'term': str(terms[0].pk)}).status_code == 403


# ------------------------------------------------------------------------------------------------ finalise, re-open, access
class TestFinalise:
    def test_finalising_locks_the_report_and_an_administrator_can_reopen_it(self, world, terms):  # noqa: F811
        c = api(world['teacher'])
        rep = _open(c, world['kid'], terms[0])
        fin = c.post(f'{BASE}/term/{rep["id"]}/finalise/')
        assert fin.status_code == 200 and fin.json()['is_locked'] and fin.json()['finalised_by']
        assert c.put(f'{BASE}/term/{rep["id"]}/', {'attendance_remarks': 'x'}, format='json').status_code == 409
        assert c.post(f'{BASE}/term/{rep["id"]}/finalise/').status_code == 409
        assert c.post(f'{BASE}/term/{rep["id"]}/prefill/').status_code == 409
        assert c.post(f'{BASE}/term/{rep["id"]}/reopen/', {'reason': 'x'}, format='json').status_code == 403
        a = api(world['admin'])
        assert a.post(f'{BASE}/term/{rep["id"]}/reopen/', {}, format='json').status_code == 400
        r = a.post(f'{BASE}/term/{rep["id"]}/reopen/', {'reason': '保護者面談後の訂正'}, format='json')
        assert r.status_code == 200 and r.json()['is_locked'] is False
        assert c.put(f'{BASE}/term/{rep["id"]}/', {'attendance_remarks': 'x'}, format='json').status_code == 200
        assert AuditLog.objects.filter(resource_type__icontains='term-report-reopen').exists()

    def test_a_report_without_a_class_teacher_cannot_be_finalised(self, world, terms):  # noqa: F811
        rep = _open(api(world['teacher']), world['kid'], terms[0])
        api(world['teacher']).put(f'{BASE}/term/{rep["id"]}/', {'teacher_name': ''}, format='json')
        r = api(world['teacher']).post(f'{BASE}/term/{rep["id"]}/finalise/')
        assert r.status_code == 400 and '学級担任者' in r.json()['detail']

    def test_a_teacher_cannot_touch_another_classs_student_and_families_have_no_access(self, world, terms):  # noqa: F811
        t = api(world['teacher'])
        assert t.post(f'{BASE}/term/open/', {'student': str(world['outsider'].pk), 'term': str(terms[0].pk)}, format='json').status_code == 403
        rep = _open(api(world['admin']), world['outsider'], terms[0])
        assert t.get(f'{BASE}/term/{rep["id"]}/').status_code == 403
        for who in ('mom', ):
            assert api(world[who]).post(f'{BASE}/term/open/', {'student': str(world['kid'].pk), 'term': str(terms[0].pk)}, format='json').status_code == 403

    def test_another_school_cannot_see_the_report(self, world, terms):  # noqa: F811
        rep = _open(api(world['admin']), world['kid'], terms[0])
        assert api(world['admin_b']).get(f'{BASE}/term/{rep["id"]}/').status_code == 404
        with use_tenant(world['b']):
            assert TermReport.objects.count() == 0

    def test_every_read_and_change_is_audited(self, world, terms):  # noqa: F811
        c = api(world['teacher'])
        rep = _open(c, world['kid'], terms[0])
        c.get(f'{BASE}/term/{rep["id"]}/')
        c.post(f'{BASE}/term/{rep["id"]}/finalise/')
        kinds = set(AuditLog.objects.values_list('resource_type', flat=True))
        assert any('term-report' in k for k in kinds) and any('finalise' in k for k in kinds)
