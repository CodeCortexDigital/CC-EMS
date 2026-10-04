"""The absence ladder, the intervention queue it feeds, and the chronic absenteeism rate."""
from datetime import date, timedelta
from unittest import mock

import pytest
from django.core import mail
from django.utils import timezone

from services.core.tenants.context import use_tenant
from services.core.user_notifications.models import Notification
from services.education.attendance import escalation
from services.education.attendance.models import AbsenceEscalation, AttendanceNotice, AttendanceRecord
from services.education.attendance.register import alert_for_record, clean_settings
from services.education.interventions.models import Intervention
from services.education.students.models import Guardian, StudentGuardian
from tests.safety_helpers import api, link_parent, make_student, make_user, rows, two_schools

TODAY = date(2026, 10, 2)
LADDER = [{'count': 3, 'days': 30, 'staff': False, 'intervention': False},
          {'count': 5, 'days': 30, 'staff': True, 'intervention': True},
          {'count': 10, 'days': 60, 'staff': True, 'intervention': True}]


@pytest.fixture
def school(db):
    a, b = two_schools()
    kid = make_student(a, full_name='Noah Smith')
    mom = Guardian.objects.create(tenant=a, first_name='Emma', last_name='Smith', relationship='mother', email='emma@example.com')
    StudentGuardian.objects.create(tenant=a, student=kid, guardian=mom, is_primary=True, receives_messages=True)
    return {'a': a, 'b': b, 'kid': kid, 'admin': make_user(a, 'head@a.test', 'admin'), 'counsellor': make_user(a, 'carol.counsellor@a.test', 'counsellor'),
            'teacher': make_user(a, 'ann.teacher@a.test', 'teacher'), 'admin_b': make_user(b, 'head@b.test', 'admin')}


def absent(student, day, excused=False):
    """An absence on file without triggering any alert (history)."""
    rec = AttendanceRecord(tenant=student.tenant, student=student, date=day, status='absent', is_excused=excused)
    rec._silent = True
    rec.save()
    return rec


def absences(student, n, end=TODAY, excused=False):
    for i in range(n):
        absent(student, end - timedelta(days=i), excused)


def fire(student, day=TODAY, cfg=None):
    return escalation.run(student, day, {'chronic_threshold': 3, 'escalation': LADDER, **(cfg or {})})


class TestSteps:
    def test_steps_are_cleaned_and_sorted(self):
        out = escalation.clean_steps([{'count': '10', 'days': 90}, {'count': 3, 'days': 1, 'staff': 'true'}, {'count': 3}, {'count': 0}, 'junk', {'count': 'x'}])
        assert out == [{'count': 3, 'days': 7, 'staff': True, 'intervention': False}, {'count': 10, 'days': 90, 'staff': False, 'intervention': False}]
        assert escalation.clean_steps('nope') is None and escalation.clean_steps(None) is None and escalation.clean_steps([]) == []
        assert len(escalation.clean_steps([{'count': n} for n in range(1, 20)])) == escalation.MAX_STEPS

    def test_with_nothing_saved_the_old_single_threshold_still_works(self):
        assert [s['count'] for s in escalation.steps_for({'chronic_threshold': 3, 'escalation': None})] == [3, 5, 10]
        assert [s['count'] for s in escalation.steps_for({'chronic_threshold': 2, 'escalation': None})] == [2, 5, 10]
        assert [s['count'] for s in escalation.steps_for({'chronic_threshold': 7, 'escalation': None})] == [7, 10]
        assert escalation.steps_for({'chronic_threshold': 0, 'escalation': None}) == []
        assert escalation.steps_for({'chronic_threshold': 3, 'escalation': []}) == []              # an empty ladder switches it off
        assert clean_settings({})['escalation'] is None


class TestLadder:
    def test_nothing_happens_below_the_first_step(self, school):
        absences(school['kid'], 2)
        assert fire(school['kid']) is None
        assert not AbsenceEscalation.objects.exists() and not mail.outbox

    def test_the_first_step_tells_the_family_only(self, school):
        absences(school['kid'], 3)
        assert fire(school['kid'])['count'] == 3
        assert len(mail.outbox) == 1 and 'emma@example.com' in mail.outbox[0].to and 'missed 3 school days' in mail.outbox[0].body
        assert not Intervention.objects.exists() and not Notification.objects.filter(recipient=school['admin']).exists()

    def test_a_step_does_not_fire_twice_for_the_same_run_of_absences(self, school):
        absences(school['kid'], 3)
        fire(school['kid'])
        mail.outbox.clear()
        absent(school['kid'], TODAY + timedelta(days=1))
        assert fire(school['kid'], TODAY + timedelta(days=1)) is None                     # 4 absences: still the same step, already fired
        assert AbsenceEscalation.objects.count() == 1 and not mail.outbox

    def test_the_second_step_warns_staff_and_opens_an_intervention(self, school):
        absences(school['kid'], 3)
        fire(school['kid'])
        mail.outbox.clear()
        for i in (1, 2):
            absent(school['kid'], TODAY + timedelta(days=i))
        top = fire(school['kid'], TODAY + timedelta(days=2))
        assert top['count'] == 5
        assert 'We would like to work with you' in mail.outbox[0].body and 'meeting' in mail.outbox[0].body
        for who in ('admin', 'counsellor'):
            assert Notification.objects.filter(recipient=school[who], title__startswith='Attendance concern').count() == 1
        assert not Notification.objects.filter(recipient=school['teacher']).exists()
        item = Intervention.objects.get()
        assert item.source == 'absence' and item.status == 'open' and item.student_id == school['kid'].pk
        assert item.priority == 'normal' and item.dedupe_key == f'absence:{school["kid"].pk}:5'
        assert item.due_date == timezone.localdate() + timedelta(days=5)
        assert len(item.suggested_actions) == 3

    def test_jumping_straight_to_a_high_step_fires_it_once_and_marks_the_lower_ones(self, school):
        absences(school['kid'], 6)                                                         # e.g. a backlog entered at once
        assert fire(school['kid'])['count'] == 5
        assert sorted(AbsenceEscalation.objects.values_list('step', flat=True)) == [3, 5]
        assert len(mail.outbox) == 1 and Intervention.objects.count() == 1
        absent(school['kid'], TODAY + timedelta(days=1))
        assert fire(school['kid'], TODAY + timedelta(days=1)) is None                      # step 3 does not fire late

    def test_the_top_step_is_high_priority(self, school):
        absences(school['kid'], 10)
        assert fire(school['kid'])['count'] == 10
        assert Intervention.objects.get().priority == 'high'

    def test_excused_absences_never_count(self, school):
        absences(school['kid'], 4, excused=True)
        absent(school['kid'], TODAY - timedelta(days=10))
        assert fire(school['kid']) is None and not mail.outbox

    def test_old_absences_outside_the_window_do_not_count(self, school):
        absences(school['kid'], 2)
        for i in range(40, 43):
            absent(school['kid'], TODAY - timedelta(days=i))
        assert fire(school['kid']) is None

    def test_a_step_can_fire_again_after_its_window_passes(self, school):
        absences(school['kid'], 3)
        fire(school['kid'])
        later = TODAY + timedelta(days=35)
        absences(school['kid'], 3, end=later)
        assert fire(school['kid'], later)['count'] == 3
        assert AbsenceEscalation.objects.filter(step=3).count() == 2

    def test_no_ladder_means_no_alerts(self, school):
        absences(school['kid'], 12)
        assert fire(school['kid'], cfg={'escalation': []}) is None
        assert fire(school['kid'], cfg={'escalation': None, 'chronic_threshold': 0}) is None
        assert not mail.outbox and not Intervention.objects.exists()

    def test_the_same_run_never_opens_two_interventions(self, school):
        absences(school['kid'], 5)
        fire(school['kid'])
        AbsenceEscalation.objects.all().delete()                  # as if the job ran again before the record was kept
        fire(school['kid'])
        assert Intervention.objects.count() == 1

    def test_recording_an_absence_runs_the_ladder_end_to_end(self, school):
        absences(school['kid'], 2, end=TODAY - timedelta(days=1))
        rec = absent(school['kid'], TODAY)
        with use_tenant(school['a']):
            alert_for_record(AttendanceRecord.objects.select_related('student__tenant').get(pk=rec.pk))
        kinds = sorted(AttendanceNotice.objects.values_list('kind', flat=True))
        assert kinds == ['absent', 'chronic']
        assert any('missed 3 school days' in m.body for m in mail.outbox)

    def test_loading_history_sends_nothing(self, school):
        absences(school['kid'], 12)                              # _silent: the importer's way of loading history
        assert not mail.outbox and not AbsenceEscalation.objects.exists() and not Intervention.objects.exists()


class TestAbsenteeismRate:
    def _insights(self, c, **params):
        return c.get('/api/v1/auth/insights/attendance/', {'start': '2026-09-01', 'end': '2026-10-02', **params})

    def test_counts_students_missing_a_tenth_or_more_of_their_days(self, school):
        a = school['a']
        steady, chronic = make_student(a, full_name='Steady Sam'), make_student(a, full_name='Away Anna')
        for i in range(20):
            rec = AttendanceRecord(tenant=a, student=steady, date=TODAY - timedelta(days=i), status='absent' if i == 0 else 'present')
            rec._silent = True
            rec.save()
            rec = AttendanceRecord(tenant=a, student=chronic, date=TODAY - timedelta(days=i), status='absent' if i < 3 else 'present', is_excused=i == 0)
            rec._silent = True
            rec.save()
        data = self._insights(api(school['admin'])).json()['chronic']
        assert data['threshold_percent'] == 10 and data['students'] == 1 and data['measured'] == 2 and data['rate'] == 50.0
        assert self._insights(api(school['admin']), chronic_percent=5).json()['chronic']['students'] == 2      # steady Sam misses 5%
        assert self._insights(api(school['admin']), chronic_percent=99).json()['chronic']['threshold_percent'] == 50.0

    def test_new_arrivals_with_few_days_are_not_counted(self, school):
        newbie = make_student(school['a'])
        absences(newbie, 3)
        assert self._insights(api(school['admin'])).json()['chronic'] == {'threshold_percent': 10.0, 'students': 0, 'measured': 0, 'rate': None, 'by_class': []}

    def test_another_school_is_not_included(self, school):
        absences(school['kid'], 12)
        assert self._insights(api(school['admin_b'])).json()['chronic']['measured'] == 0


class TestRiskScanOpensInterventions:
    def _risk(self, student, level, dropout):
        from services.analytics.models import StudentRisk
        return StudentRisk.objects.create(student=student, risk_level=level, risk_score=dropout, factors={'dropout_risk': dropout})

    def test_a_high_dropout_risk_becomes_one_intervention(self, school):
        from services.education.interventions.engine import from_risk
        risk = self._risk(school['kid'], 'high', 62.0)
        item, created = from_risk(school['kid'], risk)
        assert created and item.source == 'risk' and item.priority == 'normal' and 'Dropout risk 62%' in item.title
        again, created_again = from_risk(school['kid'], risk)                   # the next nightly scan
        assert not created_again and again.pk == item.pk and Intervention.objects.count() == 1

    def test_critical_is_high_priority_and_low_risk_opens_nothing(self, school):
        from services.education.interventions.engine import from_risk
        item, _ = from_risk(school['kid'], self._risk(school['kid'], 'critical', 88.0))
        assert item.priority == 'high'
        other = make_student(school['a'])
        assert from_risk(other, self._risk(other, 'medium', 30.0)) == (None, False)
        third = make_student(school['a'])
        assert from_risk(third, self._risk(third, 'high', 40.0)) == (None, False)      # high overall but not a dropout signal

    def test_a_new_one_can_open_after_the_old_one_is_finished(self, school):
        from services.education.interventions.engine import from_risk
        risk = self._risk(school['kid'], 'high', 70.0)
        item, _ = from_risk(school['kid'], risk)
        Intervention.objects.filter(pk=item.pk).update(status='done')
        again, created = from_risk(school['kid'], risk)
        assert created and again.pk != item.pk


class TestSettingsApi:
    URL = '/api/v1/auth/attendance/settings/'

    def test_the_default_ladder_is_shown_and_a_custom_one_is_saved_cleaned_and_resettable(self, school):
        c = api(school['admin'])
        first = c.get(self.URL).json()
        assert first['escalation'] is None and [s['count'] for s in first['escalation_effective']] == [3, 5, 10]
        saved = c.put(self.URL, {'escalation': [{'count': 4, 'days': 3, 'staff': True}, {'count': 8, 'days': 45, 'intervention': True}, {'count': 8}]}, format='json').json()
        assert saved['escalation'] == [{'count': 4, 'days': 7, 'staff': True, 'intervention': False}, {'count': 8, 'days': 45, 'staff': False, 'intervention': True}]
        assert saved['escalation_effective'] == saved['escalation']
        assert c.put(self.URL, {'escalation': []}, format='json').json()['escalation_effective'] == []        # switched off
        reset = c.put(self.URL, {'escalation': None}, format='json').json()
        assert reset['escalation'] is None and [s['count'] for s in reset['escalation_effective']] == [3, 5, 10]

    def test_only_administrators_change_it_and_other_schools_are_unaffected(self, school):
        assert api(school['teacher']).put(self.URL, {'escalation': []}, format='json').status_code == 403
        api(school['admin']).put(self.URL, {'escalation': []}, format='json')
        assert [s['count'] for s in api(school['admin_b']).get(self.URL).json()['escalation_effective']] == [3, 5, 10]
