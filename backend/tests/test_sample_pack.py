"""The sample US school pack in sample-data/us-school/: it loads cleanly, its timetable is sound, it is up to date with its
generator, and `seed_demo --pack` wires the demo logins to it."""
import hashlib
from collections import Counter
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from services.core.tenants.context import use_tenant
from services.core.tenants.models import School
from services.education.academics.eligibility import is_qualified
from services.education.academics.models import Teacher, TeacherSubjectAssignment, TimetableEntry
from services.education.academics.substitution import refresh_cover
from services.education.hr.models import SubstituteRequest
from services.education.imports import loader, sample_pack
from services.education.imports.specs import KINDS
from services.education.students.models import Household, Student

PACK = Path(__file__).resolve().parents[2] / 'sample-data' / 'us-school'

pytestmark = pytest.mark.django_db


def test_the_committed_files_are_what_the_generator_makes():
    """If this fails, rebuild with `manage.py build_sample_pack` (and commit the new files)."""
    files = sample_pack.build()
    assert set(files) == {k for k, s in KINDS.items() if s.get('export') is not None and (PACK / s['filename']).exists()}
    stale = []
    for kind, rows in files.items():
        fresh = sample_pack.to_csv(kind, rows).encode('utf-8')
        if hashlib.sha256(fresh).hexdigest() != hashlib.sha256((PACK / KINDS[kind]['filename']).read_bytes()).hexdigest():
            stale.append(KINDS[kind]['filename'])
    assert not stale, f'out of date: {stale}'


def test_the_pack_loads_with_no_problems_and_makes_a_sound_school():
    school = School.objects.create(tenant_code='SPK', name='Pack Test School', subdomain='pack-test', is_active=True)
    results = loader.load(PACK, school, 'update')
    assert sum(r['error'] for r in results.values()) == 0
    assert {k: v['ready'] + v['update'] for k, v in results.items()}['students'] == 83
    with use_tenant(school):
        assert Student.objects.count() == 83 and Teacher.objects.count() == 24
        assert Household.objects.count() < 83                                     # siblings share a household
        from services.education.behaviour.models import BehaviourIncident, BehaviourRating
        from services.education.students.models import StudentHealth
        assert StudentHealth.objects.count() == 83                                 # every student has a health record
        assert BehaviourIncident.objects.count() > 100 and BehaviourRating.objects.count() == 166
        entries = list(TimetableEntry.objects.select_related('teacher', 'class_subject__subject'))
        assert len(entries) == 260
        for key in (lambda e: (e.teacher_id, e.day_of_week, e.period_id), lambda e: (e.classroom_id, e.day_of_week, e.period_id),
                    lambda e: (e.section_id, e.day_of_week, e.period_id)):
            assert max(Counter(key(e) for e in entries).values()) == 1              # no one in two places at once
        assigned = {(a.teacher_id, a.class_subject_id) for a in TeacherSubjectAssignment.objects.all()}
        assert all((e.teacher_id, e.class_subject_id) in assigned or is_qualified(e.teacher, e.class_subject.subject) for e in entries)
        assert not any(e.teacher.teacher_type == 'relief' for e in entries)
        # The upcoming approved leave gets dated cover from the qualified free teachers; what nobody qualified can take stays open.
        from datetime import date
        assert refresh_cover(60, today=date(2026, 10, 2)) >= 3
        counts = Counter(SubstituteRequest.objects.values_list('status', flat=True))
        assert counts['filled'] > 0 and counts['open'] > 0
        for r in SubstituteRequest.objects.filter(status='filled').select_related('substitute', 'entry__class_subject__subject'):
            assert is_qualified(r.substitute, r.entry.class_subject.subject)


def test_seed_demo_pack_links_the_demo_logins(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    call_command('seed_sample_users', '--force')
    call_command('seed_demo', '--pack', 'us-school')
    school = School.objects.get(tenant_code='MGA')
    User = get_user_model()
    with use_tenant(school):
        assert Student.objects.count() == 83
        teacher = Teacher.objects.get(email='teacher@code.com')
        assert teacher.role == 'Teacher' and teacher.subjects.filter(code='MATH').exists()
        assert Student.objects.get(email='student@code.com').current_class.name == 'Grade 8'
        assert SubstituteRequest.objects.filter(status='filled', filled_how='auto').exists()
        # One saved lesson plan, so the Lesson Planner is not empty for a visitor.
        from services.education.academics.models import LessonPlan
        plan = LessonPlan.objects.get()
        assert plan.teacher.email == 'teacher@code.com' and plan.class_subject.class_ref.name == 'Grade 6' and plan.status == 'planned'
    parent = User.objects.get(email='parent@code.com')
    assert parent.parent_profile.linked_students.count() >= 2
    assert User.objects.get(email='admin@code.com').tenant_memberships.filter(school=school, role='admin').exists()
    call_command('seed_demo', '--pack', 'us-school')                          # running it again changes nothing
    with use_tenant(school):
        assert LessonPlan.objects.count() == 1
    with use_tenant(school):
        assert Student.objects.count() == 83
