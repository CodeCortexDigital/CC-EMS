"""Administrator analytics: enrolment forecast, performance trends, staffing signals, written summaries."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.core.cache import cache
from django.utils import timezone

from services.core.tenants.context import use_tenant
from services.core.tenants.models import TenantMembership
from services.education.academics.models import ClassSubject, SchoolClass, Teacher, TeacherLeave, Term
from services.education.admissions.models import Applicant, Application, WaitlistConfig
from services.education.gradebook.models import Assignment, Score
from services.education.hr.models import StaffContract, StaffCredential
from services.education.insights.planning import grade_of, project, summarise_trend
from tests.conftest import StudentFactory, UserFactory
from tests.safety_helpers import make_user
from tests.test_insights import URL, _client, rep  # noqa: F401  (rep is a fixture)

KW = dict(father_name='', mother_name='', guardian_name='', guardian_phone='')


def _llm(*rows):
    from tests.test_ai_platform import FakeLLM

    llm = FakeLLM([])
    llm.structured_results = list(rows)
    return llm


def _member(school, role, email):
    user = UserFactory(email=email)
    TenantMembership.objects.create(user=user, school=school, role=role, is_primary=True)
    return user


class TestForecastArithmetic:
    def test_grade_wording(self):
        assert [grade_of(x) for x in ('Grade 5', 'grade 12', 'Kindergarten', 'K', 'Pre-K', 'Reception')] == [5, 12, 0, 0, -1, None]

    def test_next_years_grade_comes_from_the_one_below_plus_offers_and_waiting(self):
        rows = project({4: 20, 5: 22}, 0.9, {5: 3}, {5: 10}, 0.4, {5: 22}, {5: 30})
        g5 = next(r for r in rows if r['grade'] == 5)
        assert g5['from_below'] == 18.0 and g5['expected'] == round(18 + 3 + 4) == 25
        assert g5['low'] < g5['expected'] < g5['high']
        assert g5['seats_left'] == 5 and g5['sections_needed'] == 2

    def test_the_top_grade_is_assumed_to_graduate(self):
        rows = project({11: 10, 12: 12}, 0.95, {}, {}, 0.3, {}, {})
        assert [r['grade'] for r in rows] == [11, 12]                       # no grade 13 appears
        assert next(r for r in rows if r['grade'] == 12)['expected'] == round(10 * 0.95)

    def test_an_entry_grade_has_only_offers_and_waiting(self):
        rows = project({1: 20}, 0.9, {0: 5}, {0: 10}, 0.5, {}, {0: 8})
        k = next(r for r in rows if r['grade'] == 0)
        assert k['from_below'] == 0 and k['expected'] == 10 and k['seats_left'] == -2


@pytest.mark.django_db
class TestForecastApi:
    def test_returns_the_numbers_with_every_assumption(self, rep):
        d = rep
        res = d['office'].get(f'{URL}/forecast/')
        assert res.status_code == 200, res.content
        body = res.json()
        a = body['assumptions']
        assert a['retention_assumed'] is True and a['conversion_assumed'] is True and 'how' in a
        g7 = next(g for g in body['grades'] if g['grade'] == 7)
        assert g7['this_year'] == 1 and g7['pipeline'] == 1 and g7['label'] == 'Grade 7'
        assert g7['expected'] == round(2 * a['retention'] + 1 * a['conversion'])   # two Grade 6 students feed Grade 7

    def test_approved_offers_and_seats_are_counted(self, rep):
        d = rep
        with use_tenant(d['s']):
            ap = Applicant.objects.create(tenant=d['s'], full_name='Kay', email='k@example.com', gender='F', applying_for_class='Grade 7')
            Application.objects.create(applicant=ap, status='approved')
            WaitlistConfig.objects.create(tenant=d['s'], class_name='Grade 7', academic_year='2026-2027', capacity=3)
        g7 = next(g for g in d['office'].get(f'{URL}/forecast/').json()['grades'] if g['grade'] == 7)
        assert g7['confirmed'] == 1 and g7['seats'] == 3 and g7['seats_left'] == 3 - g7['expected']

    def test_applications_for_an_unreadable_grade_are_reported_not_guessed(self, rep):
        d = rep
        with use_tenant(d['s']):
            Application.objects.create(applicant=Applicant.objects.create(tenant=d['s'], full_name='Q', email='q@example.com', gender='M', applying_for_class='Reception'))
        assert d['office'].get(f'{URL}/forecast/').json()['unmatched_applications'] == 1

    def test_csv_export_and_office_only(self, rep):
        d = rep
        assert d['office'].get(f'{URL}/forecast/?export=csv')['Content-Type'].startswith('text/csv')
        teacher = _member(d['s'], 'teacher', 't@hillside.test')
        assert _client(teacher).get(f'{URL}/forecast/').status_code == 403

    def test_one_school_never_sees_anothers_numbers(self, rep):
        d = rep
        total = d['office'].get(f'{URL}/forecast/').json()['total']['this_year']
        assert total == 3                                                     # Amy, Ben, Cat; not 'Elsewhere'


@pytest.fixture
def two_terms(rep):
    d = rep
    today = timezone.localdate()
    with use_tenant(d['s']):
        c6 = SchoolClass.objects.get(code='G6')
        maths = ClassSubject.objects.get(class_ref=c6)
        year = Term.objects.first().academic_year
        old = Term.objects.create(tenant=d['s'], academic_year=year, name='Term 0', order=0, start_date=today - timedelta(days=170), end_date=today - timedelta(days=61))
        new = Term.objects.get(name='Term 1')
    kids = [StudentFactory(tenant=d['s'], current_class=c6, full_name=f'Kid {i}', **KW) for i in range(10)]
    return {**d, 'maths': maths, 'old': old, 'new': new, 'kids': kids}


def _scores(d, term, points):
    with use_tenant(d['s']):
        a = Assignment.objects.create(tenant=d['s'], class_subject=d['maths'], term=term, title=f'T-{term.name}', points_possible=100)
        for k in d['kids']:
            Score.objects.create(assignment=a, student=k, points=Decimal(points))


class TestTrendArithmetic:
    def test_needs_two_terms_each_with_enough_students(self):
        enough = {'a': [80, 100, set(range(10))], 'b': [60, 100, set(range(10))]}
        assert summarise_trend(enough, ['a', 'b'])['change'] == -20.0
        assert summarise_trend(enough, ['a', 'b'])['declining'] is True
        assert summarise_trend({'a': [80, 100, set(range(10))]}, ['a']) is None
        assert summarise_trend({'a': [80, 100, set(range(9))], 'b': [60, 100, set(range(10))]}, ['a', 'b']) is None

    def test_small_drops_are_not_flagged(self):
        pts = {'a': [80, 100, set(range(10))], 'b': [77, 100, set(range(10))]}
        assert summarise_trend(pts, ['a', 'b'])['declining'] is False


@pytest.mark.django_db
class TestTrendsApi:
    def test_flags_a_decline_between_terms(self, two_terms):
        d = two_terms
        _scores(d, d['old'], 85)
        _scores(d, d['new'], 70)
        body = d['office'].get(f'{URL}/trends/?by=subject').json()
        row = next(r for r in body['groups'] if r['name'] == 'Maths')
        assert abs(row['change'] + 15) < 1 and row['declining'] is True       # the fixture's own quiz nudges the average slightly
        assert True if body['declining'] == 1 else False
        assert row['declining'] is True and body['declining'] == 1
        assert [p['term_name'] for p in row['series']] == ['Term 0', 'Term 1']

    def test_groups_under_ten_students_are_hidden(self, rep):
        d = rep                                                               # only Amy and Ben have scores
        body = d['office'].get(f'{URL}/trends/').json()
        assert body['groups'] == [] and body['min_group'] == 10

    def test_can_be_cut_by_class_and_filtered_by_grade(self, two_terms):
        d = two_terms
        _scores(d, d['old'], 85)
        _scores(d, d['new'], 90)
        body = d['office'].get(f'{URL}/trends/?by=class&grade=6').json()
        assert [r['name'] for r in body['groups']] == ['Grade 6'] and body['groups'][0]['declining'] is False
        assert d['office'].get(f'{URL}/trends/?by=class&grade=7').json()['groups'] == []

    def test_office_only(self, two_terms):
        teacher = _member(two_terms['s'], 'teacher', 't2@hillside.test')
        assert _client(teacher).get(f'{URL}/trends/').status_code == 403


@pytest.mark.django_db
class TestStaffingSignals:
    def _staff(self, d):
        today = timezone.localdate()
        with use_tenant(d['s']):
            t = Teacher.objects.create(tenant=d['s'], full_name='Ms Lee', email='lee@hillside.test', employee_id='T9', joining_date='2020-01-01')
            StaffContract.objects.create(tenant=d['s'], teacher=t, kind='fixed_term', start_date=today - timedelta(days=300), end_date=today + timedelta(days=30))
            StaffCredential.objects.create(tenant=d['s'], teacher=t, name='Teaching licence', expires_on=today - timedelta(days=5))
            TeacherLeave.objects.create(tenant=d['s'], teacher=t, leave_type='sick', start_date=today - timedelta(days=20), end_date=today - timedelta(days=7), status='approved')
        return t

    def test_lists_workload_and_retention_signals_and_says_it_is_not_a_rating(self, rep):
        d = rep
        self._staff(d)
        body = d['office'].get('/api/v1/auth/hr/signals/').json()
        lee = next(r for r in body['staff'] if r['teacher_name'] == 'Ms Lee')
        kinds = {s['kind'] for s in lee['signals']}
        assert {'contract_end', 'credential', 'time_away'} <= kinds
        assert 'not a rating' in body['note']
        away = next(s for s in lee['signals'] if s['kind'] == 'time_away')
        assert '14 days' in away['detail'] and 'sick' not in away['detail'].lower()   # no health reason is shown

    def test_nobody_with_nothing_to_flag_is_listed(self, rep):
        assert rep['office'].get('/api/v1/auth/hr/signals/').json()['staff'] == []

    def test_hr_can_see_it_but_teachers_cannot(self, rep):
        d = rep
        assert _client(make_user(d['s'], 'hr@hillside.test', 'hr')).get('/api/v1/auth/hr/signals/').status_code == 200
        assert _client(_member(d['s'], 'teacher', 't3@hillside.test')).get('/api/v1/auth/hr/signals/').status_code == 403


@pytest.mark.django_db
class TestNarrative:
    def setup_method(self):
        cache.clear()

    def test_without_a_provider_it_reads_the_figures_back_plainly(self, rep):
        res = rep['office'].post(f'{URL}/narrative/', {'report': 'attendance'}, format='json')
        body = res.json()
        assert res.status_code == 200 and body['source'] == 'template'
        assert 'Attendance rate' in body['summary'] and any(f['label'] == 'Absences' for f in body['facts'])

    def test_the_ai_gets_figures_only_and_the_result_is_cached_for_the_day(self, rep):
        d = rep
        llm = _llm({'summary': 'Attendance held steady.'})
        with mock.patch('services.ai.teacher_tools.get_llm_client', return_value=llm):
            first = d['office'].post(f'{URL}/narrative/', {'report': 'overview'}, format='json').json()
            second = d['office'].post(f'{URL}/narrative/', {'report': 'overview'}, format='json').json()
        assert first['source'] == 'ai' and first['summary'] == 'Attendance held steady.' and first['cached'] is False
        assert second['cached'] is True and len(llm.calls) == 1
        prompt = llm.calls[0]['prompt']
        assert 'Students on roll' in prompt and not any(n in prompt for n in ('Amy', 'Ben', 'Cat', 'Gone'))
        assert first['facts']                                                  # the numbers always travel with the words

    def test_a_different_report_is_a_new_request(self, rep):
        d = rep
        llm = _llm({'summary': 'one'}, {'summary': 'two'})
        with mock.patch('services.ai.teacher_tools.get_llm_client', return_value=llm):
            d['office'].post(f'{URL}/narrative/', {'report': 'overview'}, format='json')
            d['office'].post(f'{URL}/narrative/', {'report': 'finance'}, format='json')
        assert len(llm.calls) == 2

    def test_bad_report_and_non_office_are_refused(self, rep):
        d = rep
        assert d['office'].post(f'{URL}/narrative/', {'report': 'salaries'}, format='json').status_code == 400
        assert _client(_member(d['s'], 'teacher', 't4@hillside.test')).post(f'{URL}/narrative/', {'report': 'overview'}, format='json').status_code == 403

    def test_can_be_switched_off(self, rep):
        from services.core.features.models import FeatureFlag

        d = rep
        FeatureFlag.objects.create(name='ai_narrative', tenant=d['s'], is_enabled=False)
        with mock.patch('services.ai.teacher_tools.get_llm_client', return_value=_llm({'summary': 'x'})):
            assert d['office'].post(f'{URL}/narrative/', {'report': 'overview'}, format='json').status_code == 403
