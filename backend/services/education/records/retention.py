"""How long a 指導要録 is kept, and which ones may now be disposed of.

The School Education Act Enforcement Regulations (学校教育法施行規則 第28条) set the retention of a cumulative record by part:
 * 学籍に関する記録 (様式1, the register of the pupil): 20 years;
 * 指導に関する記録 (様式2, the record of guidance): 5 years.
The clock starts when the pupil has left (graduated, transferred out or withdrawn). This module counts from the **first day of the school
year after the one in which the pupil left** (an April 1): the later of the readings in use, so a record is never disposed of early.
Confirm the starting day with your board of education; the periods and the starting rule are in one place here.

Nothing is disposed of automatically. ``due`` lists what has passed its period; an administrator disposes of it on purpose (the guidance part is
cleared, the register is deleted after its 20 years) and the action is recorded without the child's name.
"""
from __future__ import annotations

from datetime import date, timedelta

REGISTER_YEARS = 20     # 学籍に関する記録
GUIDANCE_YEARS = 5      # 指導に関する記録


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:                      # 29 February
        return d.replace(year=d.year + years, day=28)


def exit_day(record) -> date | None:
    """The day the pupil left the school: graduation, else transfer out (None while still enrolled)."""
    return record.graduation_date or record.transfer_out_date


def start_day(exit_on: date) -> date:
    """April 1 of the school year after the one the pupil left in (the school year runs April to March)."""
    school_year = exit_on.year if exit_on.month >= 4 else exit_on.year - 1
    return date(school_year + 1, 4, 1)


def dates(record) -> dict:
    """The retention dates of a record as ISO dates (all None while the pupil is still enrolled)."""
    left = exit_day(record)
    if left is None:
        return {'left_on': None, 'counted_from': None, 'guidance_until': None, 'register_until': None,
                'guidance_disposed_at': record.guidance_disposed_at.isoformat() if record.guidance_disposed_at else None}
    start = start_day(left)
    return {'left_on': left.isoformat(), 'counted_from': start.isoformat(), 'guidance_until': _add_years(start, GUIDANCE_YEARS).isoformat(),
            'register_until': _add_years(start, REGISTER_YEARS).isoformat(),
            'guidance_disposed_at': record.guidance_disposed_at.isoformat() if record.guidance_disposed_at else None}


def guidance_expired(record, today: date | None = None) -> bool:
    d = dates(record)['guidance_until']
    return bool(d) and date.fromisoformat(d) < (today or date.today()) and record.guidance_disposed_at is None


def register_expired(record, today: date | None = None) -> bool:
    d = dates(record)['register_until']
    return bool(d) and date.fromisoformat(d) < (today or date.today())


def soon(record, today: date | None = None, days: int = 365) -> str | None:
    """'guidance' or 'register' when that part reaches the end of its period within ``days`` days (and is not already past)."""
    today = today or date.today()
    d = dates(record)
    for part in ('guidance', 'register'):
        until = d[f'{part}_until']
        if until and part == 'guidance' and record.guidance_disposed_at:
            continue
        if until and today <= date.fromisoformat(until) <= today + timedelta(days=days):
            return part
    return None
