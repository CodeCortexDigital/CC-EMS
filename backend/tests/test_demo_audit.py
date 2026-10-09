"""The hosted demo, as a visitor uses it: no screen errors in any of the four roles, and no role can see another student's record.

Loads the real demo (the sample US school and the four demo logins), then:
* calls every GET route that takes no arguments, as each role, and fails on any server error (5xx);
* tries to open report cards, transcripts and grades for every student in the school as the student, the parent and the teacher,
  and checks each one gets exactly the students it should, and nobody else's (including a student of another school).
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.tenants.context import use_tenant
from services.core.tenants.models import School
from services.education.academics.models import Term
from services.education.students.models import Student
from tests.conftest import SchoolFactory, StudentFactory

pytestmark = pytest.mark.django_db
SKIP = ('logout', 'delete', 'reset', 'wipe', 'purge', 'export/download', 'stream', 'webhook', 'callback', 'oauth', 'google')


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _routes():
    """Every URL that needs no arguments, as a path."""
    out = []

    def walk(patterns, prefix):
        for p in patterns:
            route = str(p.pattern)
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + route)
            elif isinstance(p, URLPattern):
                full = prefix + route
                if '<' in full or '(?P' in full or '^' in route or '$' in route:
                    continue
                out.append('/' + full.lstrip('/'))

    walk(get_resolver().url_patterns, '')
    return sorted({r for r in out if r.startswith('/api/') and not any(s in r for s in SKIP)})


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    call_command('seed_sample_users', '--force')
    call_command('seed_demo', '--pack', 'us-school')
    school = School.objects.get(tenant_code='MGA')
    User = get_user_model()
    return {'school': school, **{k: User.objects.get(email=f'{k}@code.com') for k in ('admin', 'teacher', 'parent', 'student')}}


def test_no_screen_errors_in_any_role(demo):
    routes = _routes()
    assert len(routes) > 100                                                   # the walk found the real API, not a handful
    errors = []
    for role in ('admin', 'teacher', 'parent', 'student'):
        api = _client(demo[role])
        for path in routes:
            try:
                res = api.get(path)
            except Exception as exc:                                           # a crash the test client re-raises is a 500 for a visitor
                errors.append(f'{role} {path}: {type(exc).__name__}: {str(exc)[:120]}')
                continue
            if res.status_code >= 500:
                errors.append(f'{role} {path}: HTTP {res.status_code}')
    assert not errors, f'{len(errors)} server errors:\n' + '\n'.join(errors[:40])


def test_nobody_sees_another_students_record(demo):
    school = demo['school']
    other = SchoolFactory(name='Another School')
    stranger = StudentFactory(tenant=other, full_name='Other School Kid', father_name='', mother_name='', guardian_name='', guardian_phone='')
    with use_tenant(school):
        everyone = list(Student.objects.all())
        term = Term.objects.order_by('-start_date').first()
        mine_student = Student.objects.get(email='student@code.com')
        kids = set(demo['parent'].parent_profile.linked_students.values_list('id', flat=True))
        from services.core.accounts.decorators import _get_teacher_class_ids
        taught = set(_get_teacher_class_ids(demo['teacher']))
    assert len(everyone) > 100 and term is not None
    base = '/api/v1/auth/gradebook'
    qs = f'?term={term.id}'

    def reachable(user):
        """The students whose report card, transcript or grades this login can open (anything but a 404/403)."""
        api = _client(user)
        seen = set()
        for s in everyone + [stranger]:
            codes = [api.get(f'{base}/report-card/{s.id}/{qs}').status_code, api.get(f'{base}/transcript/{s.id}/').status_code,
                     api.get(f'{base}/students/{s.id}/grades/').status_code]
            assert all(c < 500 for c in codes), f'{user.email} {s.student_id}: {codes}'
            # A report card nobody has released yet answers 403 to a family; "found but held back" is not "denied".
            if any(c == 200 for c in codes) or codes[0] == 403 and 'not been released' in api.get(f'{base}/report-card/{s.id}/{qs}').content.decode():
                seen.add(s.id)
        return seen

    assert reachable(demo['student']) <= {mine_student.id}
    assert reachable(demo['parent']) <= kids
    teacher_seen = reachable(demo['teacher'])
    assert teacher_seen <= {s.id for s in everyone if s.current_class_id in taught}
    assert stranger.id not in teacher_seen
    assert stranger.id not in reachable(demo['admin'])                         # not even the office of another school
