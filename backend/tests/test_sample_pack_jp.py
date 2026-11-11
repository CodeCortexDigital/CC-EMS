"""The sample Japanese school pack in sample-data/jp-school/: it loads cleanly into a school, and names written in Japanese
are kept apart (the importer's keys used to reduce every non-Latin name to an empty string)."""
from pathlib import Path

import pytest

from services.core.tenants.context import use_tenant
from services.core.tenants.models import School
from services.education.academics.models import TimetableEntry
from services.education.imports import loader
from services.education.imports.specs import norm
from services.education.students.models import Student

PACK = Path(__file__).resolve().parents[2] / 'sample-data' / 'jp-school'

pytestmark = pytest.mark.django_db


def test_names_in_any_script_make_different_keys():
    assert norm('国語') != norm('算数・数学') != ''
    assert norm('Student number') == 'studentnumber'
    assert norm('  Reg. No * ') == 'regno'


def test_the_japanese_pack_loads_with_no_problems():
    school = School.objects.create(tenant_code='WKG', name='Wakaba Test', subdomain='wakaba-test', is_active=True)
    results = loader.load(PACK, school, 'update')
    problems = {k: r['error'] for k, r in results.items() if r['error']}
    assert not problems
    with use_tenant(school):
        assert Student.objects.count() == results['students']['ready']
        assert Student.objects.filter(full_name__regex='[぀-ヿ一-鿿]').count() == results['students']['ready']
        assert TimetableEntry.objects.count() > 200
