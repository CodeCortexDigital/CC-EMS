"""One parent login with children in two schools: it opens one school, always the same one, and never mixes the two."""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.accounts.models import ParentProfile
from tests.safety_helpers import rows
from tests.conftest import SchoolFactory, StudentFactory, UserFactory

KW = dict(father_name='', mother_name='', guardian_name='', guardian_phone='')


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


@pytest.mark.django_db
def test_a_parent_with_children_in_two_schools_sees_one_school_consistently():
    a, b = SchoolFactory(name='School A'), SchoolFactory(name='School B')
    first = StudentFactory(tenant=a, full_name='Alice A', **KW)
    second = StudentFactory(tenant=b, full_name='Bob B', **KW)
    parent = UserFactory(email='both@family.test')
    profile = ParentProfile.objects.create(user=parent)
    profile.linked_students.add(second, first)                                  # linked in the "wrong" order on purpose
    for _ in range(3):                                                           # same answer every time
        api = _client(parent)
        names = {s['full_name'] for s in rows(api.get('/api/v1/auth/students/'))}
        assert names in ({'Alice A'}, {'Bob B'}), names                          # never both
    chosen = 'Alice A' if first.created_at <= second.created_at else 'Bob B'
    other = second if chosen == 'Alice A' else first
    api = _client(parent)
    shown = {s['full_name'] for s in rows(api.get('/api/v1/auth/students/'))}
    assert shown == {chosen}
    assert api.get(f'/api/v1/auth/gradebook/students/{other.id}/grades/').status_code == 404   # the other school's child stays closed
