"""The Japanese cumulative record (指導要録): the form rules, who may use it, filling it from school data, the two seals, export and isolation."""
import csv
import io
from datetime import date

import pytest
from django.apps import apps

from services.core.audit.models import AuditLog
from services.core.tenants.context import use_tenant
from services.education.records import forms
from services.education.records.models import CumulativeRecord, CumulativeYear
from tests.safety_helpers import api, link_parent, make_student, make_user, two_schools

BASE = '/api/v1/auth/records'


def _class_with_students(school, name='6年', grade_level=6, section='1組', students=1):
    A = apps.get_model
    with use_tenant(school):
        year = A('education_academics', 'AcademicYear').objects.create(tenant=school, name='2026年度', start_date=date(2026, 4, 6), end_date=date(2027, 3, 24), is_active=True)
        cls = A('education_academics', 'SchoolClass').objects.create(tenant=school, name=name, code='C6', grade_level=grade_level, academic_year=year, teacher_name='佐藤 花')
        sec = A('education_academics', 'Section').objects.create(tenant=school, class_ref=cls, name=section)
    kids = [make_student(school, full_name=f'山田 太郎{i}', current_class=cls, current_section=sec, father_name='山田 一郎', guardian_name='山田 一郎', address='みどり市 緑町 1-2-3',
                         admission_date=date(2021, 4, 6), previous_school='みどり幼稚園') for i in range(students)]
    return year, cls, sec, kids


def _teacher_of(school, cls, email='sato.teacher@a.test'):
    """A teacher login the way a school's teachers have one: a teacher profile (no named office role), assigned to a class."""
    from services.core.tenants.models import TenantMembership
    from tests.conftest import UserFactory
    user = UserFactory(email=email, full_name='Sato Teacher')
    TenantMembership.objects.create(user=user, school=school, role='teacher', is_primary=True)
    profile = apps.get_model('core_accounts', 'TeacherProfile').objects.create(user=user, employee_id=f'T-{email[:4]}')
    profile.assigned_classes.add(cls)
    return user


@pytest.fixture
def world(db):
    a, b = two_schools()
    year, cls, sec, kids = _class_with_students(a, students=2)
    other_cls = apps.get_model('education_academics', 'SchoolClass').objects.create(tenant=a, name='5年', code='C5', grade_level=5, academic_year=year)
    outsider = make_student(a, full_name='外 生徒', current_class=other_cls)
    return {'a': a, 'b': b, 'year': year, 'cls': cls, 'sec': sec, 'kid': kids[0], 'kid2': kids[1], 'outsider': outsider,
            'admin': make_user(a, 'head@a.test', 'admin'), 'teacher': _teacher_of(a, cls), 'mom': make_user(a, 'mom@a.test', 'parent'),
            'admin_b': make_user(b, 'head@b.test', 'admin'), 'kid_b': make_student(b, full_name='他校 生徒')}


def _open(c, student):
    r = c.post(f'{BASE}/open/', {'student': str(student.pk)}, format='json')
    assert r.status_code in (200, 201), r.content
    return r.json()


# ------------------------------------------------------------------------------------------------ the form rules
class TestFormRules:
    def test_each_level_has_the_years_and_rating_scale_of_the_reference_form(self):
        assert [forms.LEVELS[k]['grades'] for k in ('elementary', 'junior_high', 'high')] == [6, 3, 4]
        assert forms.LEVELS['elementary']['rating_max'] == 3 and forms.LEVELS['junior_high']['rating_max'] == 5

    def test_elementary_subjects_appear_in_the_years_the_form_shows_them(self):
        by = {s['code']: s for s in forms.LEVELS['elementary']['subjects']}
        assert by['LIFE']['grades'] == [1, 2] and by['SCI']['grades'] == [3, 4, 5, 6] and by['ENG']['grades'] == [5, 6]
        assert by['JPN']['rating_grades'] == [3, 4, 5, 6]            # no overall rating (評定) in years 1 and 2

    def test_class_grade_maps_to_a_level_and_a_year_inside_it(self):
        assert forms.level_for_class_grade(6) == 'elementary' and forms.level_for_class_grade(8) == 'junior_high' and forms.level_for_class_grade(11) == 'high'
        assert forms.grade_in_level('junior_high', 8) == 2 and forms.grade_in_level('elementary', 4) == 4

    def test_valid_content_is_kept_and_unknown_or_misplaced_cells_are_refused(self):
        ok, errors = forms.clean_content('elementary', 4, {'subjects': {'JPN': {'v1': 'a', 'v2': 'B', 'v3': 'C', 'rating': 3}}, 'moral': 'よく考えた',
                                                           'behaviour': {'basic_habits': True, 'kindness': '○'}, 'special_activities': {'club': True}})
        assert not errors and ok['subjects']['JPN'] == {'v1': 'A', 'v2': 'B', 'v3': 'C', 'rating': 3}
        assert ok['behaviour'] == {'basic_habits': True, 'kindness': True} and ok['special_activities'] == {'club': True}
        _, errors = forms.clean_content('elementary', 4, {'subjects': {'LIFE': {'v1': 'A'}, 'XXX': {}, 'JPN': {'v1': 'D', 'rating': 4}}, 'behaviour': {'nope': True}})
        assert set(errors) == {'subjects.LIFE', 'subjects.XXX', 'subjects.JPN.v1', 'subjects.JPN.rating', 'behaviour.nope'}

    def test_no_overall_rating_in_the_first_two_years_of_elementary_school_and_five_levels_in_junior_high(self):
        _, errors = forms.clean_content('elementary', 2, {'subjects': {'JPN': {'rating': 2}}})
        assert 'subjects.JPN.rating' in errors
        ok, errors = forms.clean_content('junior_high', 1, {'subjects': {'MATH': {'rating': 5}}})
        assert not errors and ok['subjects']['MATH']['rating'] == 5
        assert 'subjects.MATH.rating' in forms.clean_content('junior_high', 1, {'subjects': {'MATH': {'rating': 6}}})[1]

    def test_text_that_is_too_long_and_text_for_a_year_without_that_box_are_refused(self):
        assert 'comment' in forms.clean_content('elementary', 1, {'comment': 'あ' * 3001})[1]
        ok, _ = forms.clean_content('elementary', 1, {'integrated_activity': 'x', 'foreign_v1': 'y'})     # 総合 starts in year 3, 外国語活動 in year 3
        assert 'integrated_activity' not in ok and 'foreign_v1' not in ok

    def test_high_school_courses_carry_credits(self):
        ok, errors = forms.clean_content('high', 1, {'courses': [{'area': '国語', 'course': '現代の国語', 'v1': 'A', 'rating': 4, 'credits': 2}]})
        assert not errors and ok['courses'][0]['credits'] == 2
        assert 'courses.0' in forms.clean_content('high', 1, {'courses': [{'area': '国語'}]})[1]


# ------------------------------------------------------------------------------------------------------- access
class TestWhoMayUseIt:
    def test_families_students_and_strangers_get_nothing(self, world):
        link_parent(world['mom'], world['kid'])
        assert api(world['mom']).get(f'{BASE}/roster/').status_code == 403
        assert api(world['mom']).post(f'{BASE}/open/', {'student': str(world['kid'].pk)}, format='json').status_code == 403
        assert api().get(f'{BASE}/roster/').status_code == 401

    def test_a_teacher_works_only_on_students_of_their_own_classes(self, world):
        t = api(world['teacher'])
        assert t.post(f'{BASE}/open/', {'student': str(world['outsider'].pk)}, format='json').status_code == 403
        rec = _open(api(world['admin']), world['outsider'])
        assert t.get(f'{BASE}/{rec["id"]}/').status_code == 403
        names = [r['student_name'] for r in t.get(f'{BASE}/roster/').json()['results']]
        assert sorted(names) == ['山田 太郎0', '山田 太郎1']
        assert len(api(world['admin']).get(f'{BASE}/roster/').json()['results']) == 3

    def test_another_school_cannot_see_or_open_a_record(self, world):
        rec = _open(api(world['admin']), world['kid'])
        other = api(world['admin_b'])
        assert other.get(f'{BASE}/{rec["id"]}/').status_code == 404
        assert other.post(f'{BASE}/open/', {'student': str(world['kid'].pk)}, format='json').status_code == 404
        assert [r['student_name'] for r in other.get(f'{BASE}/roster/').json()['results']] == ['他校 生徒']

    def test_reads_and_changes_are_audited(self, world):
        rec = _open(api(world['teacher']), world['kid'])
        api(world['teacher']).get(f'{BASE}/{rec["id"]}/')
        assert AuditLog.objects.filter(user=world['teacher'], action='CREATE', resource_type='records/record').exists()
        assert AuditLog.objects.filter(user=world['teacher'], resource_type__startswith='records/record').count() >= 2


# ----------------------------------------------------------------------------------------- opening and filling
class TestOpeningAndFilling:
    def test_opening_takes_what_the_school_already_holds_and_is_safe_to_repeat(self, world):
        c = api(world['admin'])
        first = _open(c, world['kid'])
        assert first['level'] == 'elementary' and first['guardian_name'] == '山田 一郎' and 'みどり市 緑町 1-2-3' in first['student_address']
        assert first['previous_history'] == 'みどり幼稚園' and first['entry_date'] == '2021-04-06' and first['student_name'] == '山田 太郎0'
        assert _open(c, world['kid'])['id'] == first['id'] and CumulativeRecord.objects.count() == 1

    def test_the_register_part_can_be_edited_and_bad_values_are_refused(self, world):
        c = api(world['teacher'])
        rec = _open(c, world['kid'])
        r = c.patch(f'{BASE}/{rec["id"]}/', {'student_furigana': 'やまだ たろう', 'next_school': 'みどり中学校', 'graduation_date': '2027-03-24'}, format='json')
        assert r.status_code == 200 and r.json()['student_furigana'] == 'やまだ たろう' and r.json()['graduation_date'] == '2027-03-24'
        bad = c.patch(f'{BASE}/{rec["id"]}/', {'graduation_date': 'soon', 'entry_kind': 'x'}, format='json')
        assert bad.status_code == 400 and set(bad.json()) == {'graduation_date', 'entry_kind'}

    def test_prefill_fills_the_class_teacher_and_the_attendance_counts(self, world):
        school, kid = world['a'], world['kid']
        Attendance = apps.get_model('education_attendance', 'AttendanceRecord')
        days = [date(2026, 9, d) for d in (1, 2, 3, 4, 7, 8)]
        for d in days:                                           # a classmate was marked on every school day
            Attendance.objects.create(tenant=school, student=world['kid2'], date=d, status='present')
        Attendance.objects.create(tenant=school, student=world['kid2'], date=date(2026, 9, 9), status='holiday')   # a holiday is not a school day
        Attendance.objects.create(tenant=school, student=kid, date=days[0], status='present')
        Attendance.objects.create(tenant=school, student=kid, date=days[1], status='absent', reason='illness')
        Attendance.objects.create(tenant=school, student=kid, date=days[2], status='late', reason='transport')
        Attendance.objects.create(tenant=school, student=kid, date=days[3], status='absent', reason='bereavement')
        Attendance.objects.create(tenant=school, student=kid, date=days[4], status='absent', reason='suspension')
        c = api(world['teacher'])
        rec = _open(c, kid)
        r = c.post(f'{BASE}/{rec["id"]}/years/6/prefill/')
        assert r.status_code == 200, r.content
        y = r.json()
        assert (y['year_label'], y['class_name'], y['teacher_name']) == ('2026年度', '6年1組', '佐藤 花')
        assert y['roll_number'] == '1' or y['roll_number'] == '2'
        assert (y['school_days'], y['suspended_days'], y['absent_days']) == (6, 2, 1)
        assert (y['required_days'], y['present_days']) == (4, 3)     # 6 school days less 2 suspended, less 1 absent

    def test_prefill_never_overwrites_what_a_teacher_typed(self, world):
        c = api(world['teacher'])
        rec = _open(c, world['kid'])
        c.put(f'{BASE}/{rec["id"]}/years/6/', {'class_name': '6年2組', 'content': {'comment': '落ち着いている'}}, format='json')
        y = c.post(f'{BASE}/{rec["id"]}/years/6/prefill/').json()
        assert y['class_name'] == '6年2組' and y['content']['comment'] == '落ち着いている'


# --------------------------------------------------------------------------------------------- saving a year
class TestSavingAYear:
    def test_ratings_and_marks_are_saved_and_read_back(self, world):
        c = api(world['teacher'])
        rec = _open(c, world['kid'])
        body = {'class_name': '6年1組', 'school_days': 200, 'absent_days': 3, 'suspended_days': 1,
                'content': {'subjects': {'MATH': {'v1': 'A', 'v2': 'B', 'v3': 'A', 'rating': 3}}, 'behaviour': {'kindness': True}, 'comment': 'がんばりました'}}
        r = c.put(f'{BASE}/{rec["id"]}/years/6/', body, format='json')
        assert r.status_code == 200, r.content
        full = c.get(f'{BASE}/{rec["id"]}/').json()
        y = full['years'][0]
        assert y['grade'] == 6 and y['content']['subjects']['MATH']['rating'] == 3 and y['content']['behaviour'] == {'kindness': True}
        assert (y['required_days'], y['present_days']) == (199, 196)
        assert full['definition']['rating_max'] == 3 and any(s['code'] == 'MATH' for s in full['definition']['subjects'])

    def test_a_cell_the_form_does_not_have_is_refused_with_a_clear_message(self, world):
        c = api(world['teacher'])
        rec = _open(c, world['kid'])
        r = c.put(f'{BASE}/{rec["id"]}/years/6/', {'content': {'subjects': {'LIFE': {'v1': 'A'}}}}, format='json')
        assert r.status_code == 400 and 'subjects.LIFE' in r.json()
        assert c.put(f'{BASE}/{rec["id"]}/years/7/', {}, format='json').status_code == 400          # elementary school has six years
        assert c.put(f'{BASE}/{rec["id"]}/years/6/', {'absent_days': 999}, format='json').status_code == 400

    def test_changing_a_year_withdraws_the_class_teachers_seal(self, world):
        c = api(world['teacher'])
        rec = _open(c, world['kid'])
        c.put(f'{BASE}/{rec["id"]}/years/6/', {'year_label': '2026年度', 'class_name': '6年1組', 'teacher_name': '佐藤 花'}, format='json')
        assert c.post(f'{BASE}/{rec["id"]}/years/6/confirm/', {'as': 'teacher'}, format='json').json()['teacher_confirmed_at']
        again = c.put(f'{BASE}/{rec["id"]}/years/6/', {'content': {'comment': '書き直し'}}, format='json').json()
        assert again['teacher_confirmed_at'] is None


# ------------------------------------------------------------------------------------------------- the seals
class TestSeals:
    def _ready(self, world):
        t = api(world['teacher'])
        rec = _open(t, world['kid'])
        t.put(f'{BASE}/{rec["id"]}/years/6/', {'year_label': '2026年度', 'class_name': '6年1組', 'teacher_name': '佐藤 花', 'principal_name': '田中 校長',
                                                'content': {'comment': 'x'}}, format='json')
        return rec['id'], t, api(world['admin'])

    def test_the_principal_seals_only_after_the_class_teacher_and_only_an_administrator_can(self, world):
        rid, teacher, admin = self._ready(world)
        assert teacher.post(f'{BASE}/{rid}/years/6/confirm/', {'as': 'principal'}, format='json').status_code == 403
        assert admin.post(f'{BASE}/{rid}/years/6/confirm/', {'as': 'principal'}, format='json').status_code == 409      # no teacher seal yet
        assert teacher.post(f'{BASE}/{rid}/years/6/confirm/', {'as': 'teacher'}, format='json').status_code == 200
        r = admin.post(f'{BASE}/{rid}/years/6/confirm/', {'as': 'principal'}, format='json')
        assert r.status_code == 200 and r.json()['locked'] is True and r.json()['principal_confirmed_by'] == 'Head'
        assert AuditLog.objects.filter(resource_type='records/seal', action='UPDATE').count() == 2

    def test_a_year_cannot_be_sealed_while_it_is_missing_its_class_or_teacher(self, world):
        t = api(world['teacher'])
        rec = _open(t, world['kid'])
        t.put(f'{BASE}/{rec["id"]}/years/6/', {'year_label': '2026年度'}, format='json')
        r = t.post(f'{BASE}/{rec["id"]}/years/6/confirm/', {'as': 'teacher'}, format='json')
        assert r.status_code == 400 and '学級' in r.json()['detail']

    def test_a_sealed_year_is_locked_until_an_administrator_reopens_it_with_a_reason(self, world):
        rid, teacher, admin = self._ready(world)
        teacher.post(f'{BASE}/{rid}/years/6/confirm/', {'as': 'teacher'}, format='json')
        admin.post(f'{BASE}/{rid}/years/6/confirm/', {'as': 'principal'}, format='json')
        assert teacher.put(f'{BASE}/{rid}/years/6/', {'content': {'comment': 'y'}}, format='json').status_code == 409
        assert teacher.post(f'{BASE}/{rid}/years/6/prefill/').status_code == 409
        assert teacher.patch(f'{BASE}/{rid}/', {'next_school': 'x'}, format='json').status_code == 403
        assert teacher.post(f'{BASE}/{rid}/years/6/reopen/', {'reason': 'x'}, format='json').status_code == 403
        assert admin.post(f'{BASE}/{rid}/years/6/reopen/', {}, format='json').status_code == 400
        r = admin.post(f'{BASE}/{rid}/years/6/reopen/', {'reason': '成績の訂正'}, format='json')
        assert r.status_code == 200 and r.json()['locked'] is False and r.json()['teacher_confirmed_at'] is None
        assert AuditLog.objects.filter(resource_type='records/reopen').exists()
        assert teacher.put(f'{BASE}/{rid}/years/6/', {'content': {'comment': 'y'}}, format='json').status_code == 200


# ---------------------------------------------------------------------------------------------------- export
class TestExport:
    def test_the_csv_export_is_in_japanese_with_one_row_per_year(self, world):
        c = api(world['teacher'])
        rec = _open(c, world['kid'])
        c.put(f'{BASE}/{rec["id"]}/years/6/', {'year_label': '2026年度', 'class_name': '6年1組', 'school_days': 200, 'absent_days': 2,
                                                'content': {'subjects': {'JPN': {'v1': 'A', 'rating': 3}}, 'behaviour': {'kindness': True}, 'comment': '元気'}}, format='json')
        r = c.get(f'{BASE}/{rec["id"]}/export/?type=csv')
        assert r.status_code == 200 and 'text/csv' in r['Content-Type']
        text = r.content.decode('utf-8-sig')
        rows = list(csv.DictReader(io.StringIO(text)))
        assert len(rows) == 1
        row = rows[0]
        assert row['氏名'] == '山田 太郎0' and row['学級'] == '6年1組' and row['国語_知識・技能'] == 'A' and row['国語_評定'] == '3'
        assert row['行動_思いやり・協力'] == '○' and row['出席日数'] == '198' and row['総合所見'] == '元気'

    def test_a_class_export_covers_only_that_class_and_a_teacher_gets_only_their_own(self, world):
        admin = api(world['admin'])
        _open(admin, world['kid'])
        _open(admin, world['outsider'])
        for rid in [r['id'] for r in admin.get(f'{BASE}/export/?all=1').json()['results']]:
            admin.put(f'{BASE}/{rid}/years/1/', {'class_name': 'x'}, format='json')
        assert admin.get(f'{BASE}/export/').status_code == 400
        assert admin.get(f'{BASE}/export/?all=1').json()['count'] == 2
        assert admin.get(f'{BASE}/export/?class={world["cls"].pk}').json()['count'] == 1
        assert api(world['teacher']).get(f'{BASE}/export/?all=1').json()['count'] == 1
        assert api(world['mom']).get(f'{BASE}/export/?all=1').status_code == 403


# --------------------------------------------------------------------------------------- the privacy tools
class TestPrivacy:
    def test_erasing_a_student_removes_names_and_comments_but_keeps_the_ratings(self, world):
        from services.core.security.retention import _anonymise_student
        c = api(world['teacher'])
        rec = _open(c, world['kid'])
        c.patch(f'{BASE}/{rec["id"]}/', {'student_furigana': 'やまだ たろう', 'next_school': 'みどり中学校'}, format='json')
        c.put(f'{BASE}/{rec["id"]}/years/6/', {'attendance_remarks': '長期欠席', 'content': {'subjects': {'MATH': {'rating': 2}}, 'comment': '個人的な所見'}}, format='json')
        with use_tenant(world['a']):
            _anonymise_student(world['kid'])
        record = CumulativeRecord.objects.get(pk=rec['id'])
        year = CumulativeYear.objects.get(record=record)
        assert record.student_furigana == '' and record.guardian_name == '' and record.student_address == '' and record.next_school == ''
        assert 'comment' not in year.content and year.content['subjects']['MATH']['rating'] == 2 and year.attendance_remarks == ''

    def test_the_students_data_copy_includes_the_record(self, world):
        from services.core.privacy.subject import export_student
        _open(api(world['admin']), world['kid'])
        copy = export_student(world['kid'])
        assert 'education_records.CumulativeRecord' in copy['tables']
