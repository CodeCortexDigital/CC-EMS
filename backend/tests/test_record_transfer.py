"""Sending a 指導要録 to another school (転学 / 進学), and its retention (20 years for the register, 5 for the guidance part)."""
from datetime import date

import pytest

from services.core.audit.models import AuditLog
from services.core.tenants.context import use_tenant
from services.education.records import retention
from services.education.records.models import CumulativeRecord, CumulativeYear, RecordTransfer
from tests.safety_helpers import api
from tests.test_chosasho import _fill, _record, world  # noqa: F401  (a junior-high school with a class, a teacher, a family and a second school)

BASE = '/api/v1/auth/records'


def _sealed(world):  # noqa: F811
    rec = _record(world)
    for g in (1, 2, 3):
        _fill(world, rec, g)
    return rec


def _set(world, rec, **fields):  # noqa: F811
    with use_tenant(world['a']):
        CumulativeRecord.objects.filter(pk=rec).update(**fields)


class TestRetentionDates:
    @pytest.mark.parametrize('left,start', [(date(2027, 3, 15), date(2027, 4, 1)), (date(2026, 4, 1), date(2027, 4, 1)), (date(2026, 3, 31), date(2026, 4, 1)),
                                            (date(2026, 12, 20), date(2027, 4, 1))])
    def test_the_count_starts_on_the_first_day_of_the_school_year_after_leaving(self, left, start):
        assert retention.start_day(left) == start

    def test_twenty_years_for_the_register_and_five_for_the_guidance_part(self):
        rec = type('R', (), {'graduation_date': date(2027, 3, 15), 'transfer_out_date': None, 'guidance_disposed_at': None})()
        d = retention.dates(rec)
        assert (d['counted_from'], d['guidance_until'], d['register_until']) == ('2027-04-01', '2032-04-01', '2047-04-01')

    def test_a_pupil_still_enrolled_has_no_dates(self):
        rec = type('R', (), {'graduation_date': None, 'transfer_out_date': None, 'guidance_disposed_at': None})()
        assert retention.dates(rec)['guidance_until'] is None and not retention.guidance_expired(rec)

    def test_a_transfer_out_counts_too_and_graduation_wins_when_both_are_set(self):
        out = type('R', (), {'graduation_date': None, 'transfer_out_date': date(2020, 9, 1), 'guidance_disposed_at': None})()
        assert retention.dates(out)['counted_from'] == '2021-04-01'
        both = type('R', (), {'graduation_date': date(2024, 3, 20), 'transfer_out_date': date(2020, 9, 1), 'guidance_disposed_at': None})()
        assert retention.dates(both)['counted_from'] == '2024-04-01'

    def test_the_end_of_the_period_itself_is_still_inside_it(self):
        rec = type('R', (), {'graduation_date': date(2018, 3, 15), 'transfer_out_date': None, 'guidance_disposed_at': None})()
        assert not retention.guidance_expired(rec, today=date(2023, 4, 1)) and retention.guidance_expired(rec, today=date(2023, 4, 2))


class TestSending:
    def test_a_transfer_is_kept_as_sent_and_starts_the_retention_clock(self, world):  # noqa: F811
        rec = _sealed(world)
        a = api(world['admin'])
        r = a.post(f'{BASE}/{rec}/transfer/', {'kind': 'transfer', 'to_school': 'みどり市立 北中学校', 'sent_on': '2026-12-20', 'note': '転居のため'}, format='json')
        assert r.status_code == 201, r.content
        t = r.json()
        assert t['kind_label'] == '転学 (写し)' and t['to_school'] == 'みどり市立 北中学校' and len(t['snapshot']['years']) == 3
        got = a.get(f'{BASE}/{rec}/').json()
        assert got['transfer_out_date'] == '2026-12-20' and '転学先: みどり市立 北中学校' in got['transfer_out_note']
        assert got['retention']['counted_from'] == '2027-04-01' and got['retention']['guidance_until'] == '2032-04-01'
        # a correction made afterwards does not change what was sent
        a.post(f'{BASE}/{rec}/years/3/reopen/', {'reason': '訂正'}, format='json')
        api(world['teacher']).put(f'{BASE}/{rec}/years/3/', {'class_name': '3年9組'}, format='json')
        kept = a.get(f'{BASE}/{rec}/transfer/{t["id"]}/').json()
        assert [y['class_name'] for y in kept['snapshot']['years'] if y['grade'] == 3] == ['3年1組']

    def test_an_advance_records_the_next_school_and_does_not_mark_the_pupil_as_leaving(self, world):  # noqa: F811
        rec = _sealed(world)
        r = api(world['admin']).post(f'{BASE}/{rec}/transfer/', {'kind': 'advance', 'to_school': '県立第一高等学校', 'sent_on': '2027-03-25'}, format='json')
        assert r.status_code == 201 and r.json()['kind_label'] == '進学 (抄本)'
        got = api(world['admin']).get(f'{BASE}/{rec}/').json()
        assert got['next_school'] == '県立第一高等学校' and got['transfer_out_date'] is None

    def test_it_cannot_be_sent_while_a_year_lacks_the_principals_seal(self, world):  # noqa: F811
        rec = _record(world)
        _fill(world, rec, 1)
        _fill(world, rec, 2, seal=False)
        d = api(world['admin']).get(f'{BASE}/{rec}/transfer/').json()
        assert d['ready'] is False and d['problems'] == ['第2学年に校長の印がありません。']
        r = api(world['admin']).post(f'{BASE}/{rec}/transfer/', {'kind': 'transfer', 'to_school': '北中', 'sent_on': '2026-12-20'}, format='json')
        assert r.status_code == 409 and r.json()['problems'] == d['problems']
        with use_tenant(world['a']):
            assert RecordTransfer.objects.count() == 0

    def test_it_needs_a_kind_a_school_and_a_date(self, world):  # noqa: F811
        rec = _sealed(world)
        a = api(world['admin'])
        ok = {'kind': 'transfer', 'to_school': '北中', 'sent_on': '2026-12-20'}
        for bad, key in (({**ok, 'kind': 'other'}, 'kind'), ({**ok, 'to_school': ' '}, 'to_school'), ({**ok, 'sent_on': 'soon'}, 'sent_on')):
            r = a.post(f'{BASE}/{rec}/transfer/', bad, format='json')
            assert r.status_code == 400 and key in r.json()

    def test_only_the_principal_sends_and_families_and_other_schools_see_nothing(self, world):  # noqa: F811
        rec = _sealed(world)
        body = {'kind': 'transfer', 'to_school': '北中', 'sent_on': '2026-12-20'}
        assert api(world['teacher']).get(f'{BASE}/{rec}/transfer/').status_code == 200        # a class teacher may look
        assert api(world['teacher']).post(f'{BASE}/{rec}/transfer/', body, format='json').status_code == 403
        assert api(world['mom']).get(f'{BASE}/{rec}/transfer/').status_code == 403
        t = api(world['admin']).post(f'{BASE}/{rec}/transfer/', body, format='json').json()
        assert api(world['admin_b']).get(f'{BASE}/{rec}/transfer/').status_code == 404
        assert api(world['admin_b']).get(f'{BASE}/{rec}/transfer/{t["id"]}/').status_code == 404

    def test_sending_and_opening_a_copy_are_audited(self, world):  # noqa: F811
        rec = _sealed(world)
        a = api(world['admin'])
        t = a.post(f'{BASE}/{rec}/transfer/', {'kind': 'transfer', 'to_school': '北中', 'sent_on': '2026-12-20'}, format='json').json()
        a.get(f'{BASE}/{rec}/transfer/{t["id"]}/')
        kinds = set(AuditLog.objects.values_list('resource_type', flat=True))
        assert {'records/transfer', 'records/transfer-copy'} <= kinds


class TestDisposal:
    URL = f'{BASE}/retention/'

    def test_it_lists_what_has_passed_its_period_and_what_is_close(self, world):  # noqa: F811
        rec = _sealed(world)
        a = api(world['admin'])
        assert a.get(self.URL).json()['guidance_due'] == []
        _set(world, rec, graduation_date=date(2018, 3, 15))             # guidance part: until 2023-04-01 (passed); register: 2038
        d = a.get(self.URL).json()
        assert [r['id'] for r in d['guidance_due']] == [rec] and d['register_due'] == [] and d['guidance_years'] == 5 and d['register_years'] == 20
        assert d['guidance_due'][0]['guidance_until'] == '2023-04-01' and d['guidance_due'][0]['register_until'] == '2038-04-01'
        _set(world, rec, graduation_date=date.today().replace(year=date.today().year - 5))
        soon = a.get(self.URL).json()
        assert [r['id'] for r in soon['soon']] == [rec] and soon['guidance_due'] == []

    def test_the_guidance_part_is_cleared_but_the_register_is_kept(self, world):  # noqa: F811
        rec = _sealed(world)
        _set(world, rec, graduation_date=date(2018, 3, 15))
        a = api(world['admin'])
        assert a.post(self.URL, {'dispose': 'guidance', 'ids': [rec], 'confirm': 2}, format='json').status_code == 400          # the count is typed to confirm
        r = a.post(self.URL, {'dispose': 'guidance', 'ids': [rec], 'confirm': 1}, format='json')
        assert r.status_code == 200 and r.json() == {'disposed': 1, 'part': 'guidance'}
        got = a.get(f'{BASE}/{rec}/').json()
        assert got['retention']['guidance_disposed_at'] and len(got['years']) == 3
        assert all(y['content'] == {} and y['school_days'] is None and y['attendance_remarks'] == '' for y in got['years'])
        assert all(y['class_name'] and y['principal_confirmed_at'] for y in got['years'])           # the register part (class, teacher, seals) stays
        assert a.get(self.URL).json()['guidance_due'] == []
        assert AuditLog.objects.filter(resource_type='records/retention-guidance').count() == 1

    def test_the_register_is_deleted_only_after_twenty_years(self, world):  # noqa: F811
        rec = _sealed(world)
        a = api(world['admin'])
        _set(world, rec, graduation_date=date(2018, 3, 15))
        r = a.post(self.URL, {'dispose': 'register', 'ids': [rec], 'confirm': 1}, format='json')
        assert r.status_code == 409 and 'not reached' in r.json()['detail']
        with use_tenant(world['a']):
            assert CumulativeRecord.objects.filter(pk=rec).exists()
        _set(world, rec, graduation_date=date(2005, 3, 15))             # register: until 2025-04-01
        assert [x['id'] for x in a.get(self.URL).json()['register_due']] == [rec]
        assert a.post(self.URL, {'dispose': 'register', 'ids': [rec], 'confirm': 1}, format='json').status_code == 200
        with use_tenant(world['a']):
            assert not CumulativeRecord.objects.filter(pk=rec).exists() and CumulativeYear.objects.count() == 0
        row = AuditLog.objects.get(resource_type='records/retention-register')
        assert row.new_data['count'] == 1 and '山田' not in str(row.new_data)         # recorded without the child's name

    def test_nothing_is_changed_when_any_record_is_too_early(self, world):  # noqa: F811
        rec = _sealed(world)
        _set(world, rec, graduation_date=date.today().replace(year=date.today().year - 1))
        r = api(world['admin']).post(self.URL, {'dispose': 'guidance', 'ids': [rec], 'confirm': 1}, format='json')
        assert r.status_code == 409 and r.json()['ids'] == [rec]
        with use_tenant(world['a']):
            assert CumulativeYear.objects.exclude(content={}).count() == 3

    def test_only_administrators_and_only_their_own_school(self, world):  # noqa: F811
        rec = _sealed(world)
        _set(world, rec, graduation_date=date(2005, 3, 15))
        assert api(world['teacher']).get(self.URL).status_code == 403
        assert api(world['teacher']).post(self.URL, {'dispose': 'register', 'ids': [rec], 'confirm': 1}, format='json').status_code == 403
        assert api(world['mom']).get(self.URL).status_code == 403
        b = api(world['admin_b'])
        assert b.get(self.URL).json()['register_due'] == []
        assert b.post(self.URL, {'dispose': 'register', 'ids': [rec], 'confirm': 1}, format='json').status_code == 409          # not found for this school
        with use_tenant(world['a']):
            assert CumulativeRecord.objects.filter(pk=rec).exists()
        assert api(world['admin']).post(self.URL, {'dispose': 'nothing', 'ids': []}, format='json').status_code == 400
