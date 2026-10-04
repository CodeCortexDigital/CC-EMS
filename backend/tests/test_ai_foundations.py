"""AI foundations: prompts follow the school's region, and the school's daily jobs are really scheduled and runnable."""
from unittest import mock

import pytest

from services.ai import generation


class FakeLLM:
    """Captures what would be sent to the model."""
    provider = 'fake'

    def __init__(self):
        self.calls = []

    def structured(self, *, system, prompt, schema):
        self.calls.append({'system': system, 'prompt': prompt})
        usage = mock.Mock(input_tokens=1, output_tokens=1, cached_input_tokens=0)
        return ({'duration_minutes': 40, 'learning_objectives': [], 'materials_needed': [], 'introduction': '', 'main_activities': [],
                 'group_work': '', 'differentiation': '', 'assessment': [], 'homework': '', 'title': 'Q', 'comment': 'ok',
                 'questions': [{'question_type': 'mcq', 'question_text': 'q', 'options': ['a', 'b', 'c', 'd'], 'correct_answer': 'a',
                                'explanation': 'e', 'bloom_level': 'remember'}],
                 'score': 50, 'summary': 's', 'concerns': [], 'strengths': []}, usage, 'fake-model')


class TestRegionAwarePrompts:
    def test_a_school_that_never_chose_keeps_the_original_wording(self):
        assert 'in Pakistan' in generation.teacher_system()
        assert generation.TEACHER_SYSTEM == generation.teacher_system('pk')
        assert generation.REPORT_WRITER_SYSTEM == generation.report_writer_system('pk')
        assert generation.ADMISSIONS_SYSTEM == generation.admissions_system('pk')
        assert 'keep content aligned with standard textbooks' in generation.teacher_system('pk')

    def test_a_us_school_is_described_as_american_with_common_core(self):
        text = generation.teacher_system('us')
        assert 'in the United States' in text and 'Common Core' in text and 'American spelling' in text
        assert 'Pakistan' not in text
        assert 'in the United States' in generation.report_writer_system('us')
        assert 'in the United States' in generation.admissions_system('us')

    @pytest.mark.parametrize('region,expected', [('uk', 'United Kingdom'), ('intl', 'international school')])
    def test_other_regions_have_their_own_voice(self, region, expected):
        assert expected in generation.teacher_system(region)

    @pytest.mark.parametrize('region', ['', None, 'zz', 'US'])
    def test_unknown_or_missing_regions_fall_back_safely(self, region):
        text = generation.teacher_system(region)
        assert text and ('Pakistan' in text or 'United States' in text)

    def test_every_generator_sends_the_regions_prompt_to_the_model(self):
        llm = FakeLLM()
        generation.generate_lesson_plan(llm, subject='Math', grade='Grade 5', topic='Fractions', objectives=[], region='us')
        generation.generate_quiz(llm, subject='Math', topic='Fractions', difficulty='easy', count=3, grade='Grade 5', region='us')
        generation.generate_report_comment(llm, student_name='Ava', subject_name='Math', grade_summary='A', attendance_summary='ok',
                                           behaviour_summary='ok', region='us')
        generation.generate_admission_screening(llm, applicant_summary='x', documents_summary='y', criteria=[], region='us')
        assert len(llm.calls) == 4 and all('in the United States' in c['system'] for c in llm.calls)
        other = FakeLLM()
        generation.generate_lesson_plan(other, subject='Math', grade='Grade 5', topic='Fractions', objectives=[])
        assert 'in Pakistan' in other.calls[0]['system']                # default is unchanged


JOBS = {
    'admissions-daily': ('services.education.admissions.tasks.admissions_daily', 'admissions_daily'),
    'immunization-reminders-daily': ('services.education.students.tasks.immunization_reminders', 'send_immunization_reminders'),
    'hr-alerts-daily': ('services.education.hr.tasks.hr_alerts', 'send_hr_alerts'),
    'refresh-cover-daily': ('services.education.hr.tasks.refresh_cover', 'refresh_cover'),
}


class TestScheduledJobs:
    def _celery(self):
        from erp_core.celery import app
        app.loader.import_default_modules()
        return app

    def test_every_school_job_is_on_the_schedule_and_registered_with_celery(self):
        app = self._celery()
        for key, (task, _command) in JOBS.items():
            assert app.conf.beat_schedule[key]['task'] == task
            assert task in app.tasks, f'{task} is scheduled but Celery cannot find it'
        assert 'ai-risk-scan-nightly' in app.conf.beat_schedule and app.conf.beat_schedule['ai-risk-scan-nightly']['task'] in app.tasks

    @pytest.mark.parametrize('key', list(JOBS))
    def test_each_task_runs_its_management_command(self, key):
        task_name, command = JOBS[key]
        app = self._celery()
        with mock.patch('services.core.tasks.scheduled_jobs.call_command') as run:
            result = app.tasks[task_name]()
        run.assert_called_once_with(command)
        assert result == {'command': command, 'ok': True}

    def test_a_failing_job_is_reported_not_raised(self):
        app = self._celery()
        with mock.patch('services.core.tasks.scheduled_jobs.call_command', side_effect=RuntimeError('boom')):
            result = app.tasks['services.education.hr.tasks.hr_alerts']()
        assert result == {'command': 'send_hr_alerts', 'ok': False}

    def test_the_commands_the_jobs_call_really_exist(self):
        from django.core.management import get_commands
        known = get_commands()
        for _task, command in JOBS.values():
            assert command in known, command
