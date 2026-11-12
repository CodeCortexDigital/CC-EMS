"""The school's data handling register (個人情報取扱台帳)."""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from services.core.privacy.models import DataHandlingEntry
from services.core.tenants.models import TenantMembership
from tests.conftest import SchoolFactory, UserFactory

URL = '/api/v1/privacy/register/'


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


@pytest.fixture
def two_schools(db):
    out = {}
    for code, name in (('AAA', 'School A'), ('BBB', 'School B')):
        s = SchoolFactory(name=name, tenant_code=code)
        admin = UserFactory(email=f'admin@{code.lower()}.test')
        TenantMembership.objects.create(user=admin, school=s, role='admin', is_primary=True)
        teacher = UserFactory(email=f'teacher@{code.lower()}.test')
        TenantMembership.objects.create(user=teacher, school=s, role='teacher', is_primary=True)
        out[code] = (s, admin, teacher)
    return out


def test_starts_empty_and_loads_japanese_defaults(two_schools):
    s, admin, _ = two_schools['AAA']
    c = _client(admin)
    assert c.get(URL).json()['entries'] == []
    r = c.post(URL, {'action': 'load_defaults', 'lang': 'ja'}, format='json').json()
    names = {e['key']: e for e in r['entries']}
    assert len(names) == 13
    assert names['record']['name'] == '指導要録'
    assert '20年' in names['record']['retention'] and '5年' in names['record']['retention']
    assert {k for k, e in names.items() if e['sensitive']} == {'health', 'support', 'family', 'guidance'}
    assert names['photos']['needs_consent'] is True


def test_defaults_in_english_and_never_overwrite_edits(two_schools):
    s, admin, _ = two_schools['AAA']
    c = _client(admin)
    c.post(URL, {'action': 'load_defaults', 'lang': 'en'}, format='json')
    e = c.get(URL).json()['entries'][0]
    assert e['name'] == 'Student identity and enrolment'
    c.post(URL, {**e, 'purpose': 'Our own wording'}, format='json')
    again = c.post(URL, {'action': 'load_defaults', 'lang': 'en'}, format='json').json()['entries']
    assert len(again) == 13
    assert [x for x in again if x['id'] == e['id']][0]['purpose'] == 'Our own wording'


def test_add_edit_and_delete_a_line(two_schools):
    s, admin, _ = two_schools['AAA']
    c = _client(admin)
    r = c.post(URL, {'name': 'Bus rider list', 'purpose': 'Planning bus routes', 'sensitive': False}, format='json').json()['entries']
    assert [x['name'] for x in r] == ['Bus rider list']
    line = r[0]
    c.post(URL, {**line, 'retention': 'One year', 'sensitive': True}, format='json')
    saved = DataHandlingEntry.objects.get(pk=line['id'])
    assert saved.retention == 'One year' and saved.sensitive is True and saved.updated_by == admin
    assert c.post(URL, {'name': 'No purpose'}, format='json').status_code == 400
    assert c.delete(f'{URL}?id={line["id"]}').json()['entries'] == []


def test_each_school_sees_only_its_own_register(two_schools):
    (sa, admin_a, _), (sb, admin_b, _) = two_schools['AAA'], two_schools['BBB']
    _client(admin_a).post(URL, {'action': 'load_defaults', 'lang': 'ja'}, format='json')
    assert len(_client(admin_a).get(URL).json()['entries']) == 13
    assert _client(admin_b).get(URL).json()['entries'] == []
    line = DataHandlingEntry.objects.filter(school=sa).first()
    assert _client(admin_b).delete(f'{URL}?id={line.id}').status_code == 404
    assert DataHandlingEntry.objects.filter(pk=line.id).exists()


def test_only_the_school_administrator_can_use_it(two_schools):
    _, _, teacher = two_schools['AAA']
    c = _client(teacher)
    assert c.get(URL).status_code == 403
    assert c.post(URL, {'action': 'load_defaults'}, format='json').status_code == 403
    assert APIClient().get(URL).status_code in (401, 403)


def test_csv_export_has_the_lines(two_schools):
    s, admin, _ = two_schools['AAA']
    c = _client(admin)
    c.post(URL, {'action': 'load_defaults', 'lang': 'ja'}, format='json')
    r = c.get(URL + '?export=csv')
    text = r.content.decode('utf-8-sig')
    assert r['Content-Type'].startswith('text/csv')
    assert '指導要録' in text and text.count('\n') >= 14
