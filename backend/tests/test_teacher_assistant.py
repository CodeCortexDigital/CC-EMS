"""Teacher assistant: standards in lesson plans, parent message drafts, rubrics saved on an assignment."""
from unittest import mock

import pytest

from services.ai.generation import clean_rubric, parent_message_warnings
from services.ai.models import AIUsage
from tests.test_gradebook import _client as gb_client, setup  # noqa: F401  (setup is a fixture)
from tests.test_messaging import _client, school  # noqa: F401  (school is a fixture)

MSG = '/api/v1/ai/parent-message/'
RUBRIC = '/api/v1/ai/rubric/'
PLAN = '/api/v1/ai/lesson-plan/'


def _llm(*rows):
    from tests.test_ai_platform import FakeLLM

    llm = FakeLLM([])
    llm.structured_results = list(rows)
    return llm


def _accept_notice(school_obj):
    school_obj.settings_json = {**(school_obj.settings_json or {}), 'ai_notice': {'version': 1}}
    school_obj.save()


def _body(d, **over):
    return {'student': str(d['kid4'].id), 'template': 'missed_assignments', 'details': 'Three worksheets are outstanding since September.',
            'tone': 'warm', **over}


@pytest.mark.django_db
class TestLessonPlanStandards:
    def test_standards_are_sent_and_the_alignment_comes_back(self, school):
        d = school
        plan = {'duration_minutes': 40, 'learning_objectives': ['a'], 'materials_needed': [], 'introduction': 'i', 'main_activities': ['10 min - x'],
                'group_work': 'g', 'differentiation': 'd', 'assessment': ['q'], 'homework': 'h',
                'standards_alignment': ['CCSS.4.NF.1 - the main activity']}
        llm = _llm(plan)
        with mock.patch('services.analytics.ai_views.get_llm_client', return_value=llm):
            res = _client(d['green']).post(PLAN, {'subject': 'Math', 'grade': '4', 'topic': 'Fractions', 'standards': ['CCSS.4.NF.1']}, format='json')
        assert res.status_code == 200, res.content
        assert res.json()['standards_alignment'] == ['CCSS.4.NF.1 - the main activity']
        assert 'CCSS.4.NF.1' in llm.calls[0]['prompt'] and 'never add or invent' in llm.calls[0]['prompt']

    def test_without_standards_nothing_changes(self, school):
        d = school
        llm = _llm({'duration_minutes': 40, 'learning_objectives': [], 'materials_needed': [], 'introduction': 'i', 'main_activities': [],
                    'group_work': '', 'differentiation': '', 'assessment': [], 'homework': ''})
        with mock.patch('services.analytics.ai_views.get_llm_client', return_value=llm):
            res = _client(d['green']).post(PLAN, {'subject': 'Math', 'grade': '4', 'topic': 'Fractions'}, format='json')
        assert 'standards_alignment' not in res.json()
        assert 'standards' not in llm.calls[0]['prompt'].lower()

    def test_stand_in_plan_still_lists_the_standards(self, school):
        res = _client(school['green']).post(PLAN, {'subject': 'Math', 'grade': '4', 'topic': 'Fractions', 'standards': 'CCSS.4.NF.1\nCCSS.4.NF.2'}, format='json')
        body = res.json()
        assert body['source'] == 'template' and len(body['standards_alignment']) == 2


@pytest.mark.django_db
class TestParentMessage:
    def test_drafts_a_message_and_records_use(self, school):
        d = school
        _accept_notice(d['s'])
        llm = _llm({'subject': 'Catching up on worksheets', 'body': 'Dear family, ...'})
        with mock.patch('services.ai.teacher_tools.get_llm_client', return_value=llm):
            res = _client(d['green']).post(MSG, _body(d), format='json')
        assert res.status_code == 200, res.content
        assert res.json()['source'] == 'ai' and res.json()['subject'] == 'Catching up on worksheets' and res.json()['warnings'] == []
        prompt = llm.calls[0]['prompt']
        assert 'Kid' in prompt and 'Three worksheets' in prompt
        assert 'Kid Four' not in prompt                      # first name only
        assert AIUsage.objects.get(user=d['green'], feature='ai_parent_message')

    def test_needs_the_school_to_have_accepted_the_notice(self, school):
        d = school
        llm = _llm({'subject': 's', 'body': 'b'})
        with mock.patch('services.ai.teacher_tools.get_llm_client', return_value=llm):
            res = _client(d['green']).post(MSG, _body(d), format='json')
        assert res.status_code == 403 and 'notice' in res.json()['error']
        assert llm.calls == []

    def test_without_a_provider_it_is_a_plain_template_and_nothing_leaves(self, school):
        res = _client(school['green']).post(MSG, _body(school, template='positive_note', details='Helped a classmate.'), format='json')
        body = res.json()
        assert res.status_code == 200 and body['source'] == 'template'
        assert 'Kid' in body['subject'] and 'Helped a classmate.' in body['body'] and 'Ms Green' in body['body']

    def test_warns_when_the_notes_touch_health_or_discipline(self, school):
        res = _client(school['green']).post(MSG, _body(school, details='He was suspended and takes ADHD medication.'), format='json')
        assert len(res.json()['warnings']) == 1
        assert parent_message_warnings('Three worksheets') == []

    def test_a_teacher_cannot_draft_about_a_student_outside_their_classes(self, school):
        d = school
        res = _client(d['green']).post(MSG, _body(d, student=str(d['kid5'].id)), format='json')
        assert res.status_code == 404

    def test_parents_and_students_cannot_use_it(self, school):
        assert _client(school['p4']).post(MSG, _body(school), format='json').status_code == 403

    def test_bad_input_is_refused_before_anything_is_called(self, school):
        api = _client(school['green'])
        assert api.post(MSG, _body(school, template='nonsense'), format='json').status_code == 400
        assert api.post(MSG, _body(school, details='  '), format='json').status_code == 400
        assert api.post(MSG, _body(school, tone='angry'), format='json').status_code == 400

    def test_can_be_switched_off_for_the_school(self, school):
        from services.core.features.models import FeatureFlag

        d = school
        _accept_notice(d['s'])
        FeatureFlag.objects.create(name='ai_parent_message', tenant=d['s'], is_enabled=False)
        res = _client(d['green']).post(MSG, _body(d), format='json')
        assert res.status_code == 403


@pytest.mark.django_db
class TestRubric:
    def _criteria(self):
        return {'criteria': [{'name': 'Accuracy', 'levels': [{'label': 'Exceeds', 'description': 'No errors.'}, {'label': 'Meets', 'description': 'Few errors.'}]}]}

    def test_drafts_a_rubric_with_the_requested_levels(self, school):
        llm = _llm(self._criteria())
        with mock.patch('services.ai.teacher_tools.get_llm_client', return_value=llm):
            res = _client(school['green']).post(RUBRIC, {'title': 'Fractions project', 'levels': ['Exceeds', 'Meets'], 'standards': ['CCSS.4.NF.1']}, format='json')
        assert res.status_code == 200 and res.json()['source'] == 'ai'
        assert res.json()['criteria'][0]['levels'][0]['label'] == 'Exceeds'
        assert 'Exceeds, Meets' in llm.calls[0]['prompt'] and 'CCSS.4.NF.1' in llm.calls[0]['prompt']

    def test_stand_in_rubric_without_a_provider(self, school):
        res = _client(school['green']).post(RUBRIC, {'title': 'Fractions project'}, format='json')
        body = res.json()
        assert body['source'] == 'template' and len(body['criteria']) == 3 and len(body['criteria'][0]['levels']) == 4

    def test_needs_a_title_and_two_levels(self, school):
        api = _client(school['green'])
        assert api.post(RUBRIC, {'title': ''}, format='json').status_code == 400
        assert api.post(RUBRIC, {'title': 'x', 'levels': ['Only one']}, format='json').status_code == 400

    def test_clean_rubric_drops_anything_malformed(self):
        raw = [{'name': 'Good', 'levels': [{'label': 'A', 'description': 'd'}, {'label': 'B'}]},
               {'name': '', 'levels': [{'label': 'A'}, {'label': 'B'}]},
               {'name': 'One level', 'levels': [{'label': 'A'}]}, 'junk', {'name': 'No levels'}]
        assert [c['name'] for c in clean_rubric(raw)] == ['Good']
        assert clean_rubric('not a list') == []

    def test_saved_on_the_assignment_and_returned_with_it(self, setup):
        d = setup
        api = gb_client(d['admin'])
        base = '/api/v1/auth/gradebook'
        rubric = [{'name': 'Accuracy', 'levels': [{'label': 'Meets', 'description': 'ok'}, {'label': 'Beginning', 'description': 'no'}]}]
        a = api.post(f'{base}/assignments/', {'class_subject': str(d['cs_math'].id), 'term': str(d['t1'].id), 'title': 'Project', 'rubric': rubric}, format='json')
        assert a.status_code == 201, a.content
        assert a.json()['rubric'] == rubric
        aid = a.json()['id']
        # junk is dropped, not stored
        b = api.patch(f'{base}/assignments/{aid}/', {'rubric': [{'name': 'x'}, 'junk']}, format='json')
        assert b.json()['rubric'] == []
        grid = api.get(f'{base}/grid/?class_subject={d["cs_math"].id}&term={d["t1"].id}').json()
        assert grid['assignments'][0]['rubric'] == []

    def test_a_rubric_never_changes_a_score(self, setup):
        d = setup
        api = gb_client(d['admin'])
        base = '/api/v1/auth/gradebook'
        rubric = [{'name': 'Accuracy', 'levels': [{'label': 'Meets', 'description': 'ok'}, {'label': 'Beginning', 'description': 'no'}]}]
        aid = api.post(f'{base}/assignments/', {'class_subject': str(d['cs_math'].id), 'term': str(d['t1'].id), 'title': 'P', 'rubric': rubric}, format='json').json()['id']
        api.post(f'{base}/scores/', {'assignment': aid, 'scores': [{'student': str(d['kid'].id), 'points': 80}]}, format='json')
        before = api.get(f'{base}/grid/?class_subject={d["cs_math"].id}&term={d["t1"].id}').json()['students']
        api.patch(f'{base}/assignments/{aid}/', {'rubric': []}, format='json')
        after = api.get(f'{base}/grid/?class_subject={d["cs_math"].id}&term={d["t1"].id}').json()['students']
        assert [s['grade'] for s in before] == [s['grade'] for s in after]
