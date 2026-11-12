"""The 調査書 (the junior-high report sent to a high school for admission), assembled from the student's 指導要録.

It holds nothing of its own: the ratings (評定) of the three years, the totals, the special-activity and behaviour marks, the general comments and the
attendance all come from the cumulative record, so the school types them once. Boards of Education and prefectures each have their own form, so this is the
*content* (``assemble``); the printed page can be laid out to a board's form without changing it.

A 調査書 is only issued from a record whose three years carry the principal's seal. Until then ``assemble`` still works as a preview and lists what is missing.
"""
from __future__ import annotations

from datetime import date

from . import forms
from .models import CumulativeRecord

LEVEL = 'junior_high'


def _years(record: CumulativeRecord) -> dict[int, object]:
    return {y.grade: y for y in record.years.all()}


def assemble(record: CumulativeRecord, today: date | None = None) -> dict:
    """The content of the 調査書 for a junior-high record, with ``problems`` (what stops it being issued) and ``ready``."""
    if record.level != LEVEL:
        raise ValueError('A 調査書 is made from a junior high school record.')
    spec = forms.LEVELS[LEVEL]
    years = _years(record)
    s = record.student
    subjects, totals = [], {g: {'sum': 0, 'count': 0} for g in (1, 2, 3)}
    for subj in spec['subjects']:
        row = {'code': subj['code'], 'name': subj['name'], 'ratings': {}}
        for g in (1, 2, 3):
            cell = ((years[g].content or {}).get('subjects') or {}).get(subj['code'], {}) if g in years else {}
            r = cell.get('rating')
            row['ratings'][str(g)] = r
            if r and subj['code'] != 'ELEC':          # the five-level total is of the nine required subjects
                totals[g]['sum'] += int(r)
                totals[g]['count'] += 1
        subjects.append(row)

    def marks(field, items):
        return [{'key': k, 'label': label, 'years': {str(g): bool(((years[g].content or {}).get(field) or {}).get(k)) if g in years else False for g in (1, 2, 3)}}
                for k, label in items]

    problems = []
    for g in (1, 2, 3):
        if g not in years:
            problems.append(f'第{g}学年の記録がありません。')
        elif not years[g].is_locked:
            problems.append(f'第{g}学年に校長の印がありません。')
    if not s.date_of_birth:
        problems.append('生年月日がありません。')
    principal = next((years[g].principal_name for g in (3, 2, 1) if g in years and years[g].principal_name), '')
    today = today or date.today()
    return {
        'student': {'name': s.full_name, 'furigana': record.student_furigana, 'gender': s.gender or '', 'date_of_birth': s.date_of_birth.isoformat() if s.date_of_birth else None,
                    'student_number': s.student_id, 'address': record.student_address},
        'school': {'name': record.school_name, 'address': record.school_address, 'principal': principal},
        'graduation': {'date': record.graduation_date.isoformat() if record.graduation_date else None},
        'subjects': subjects,
        'totals': {str(g): {'sum': totals[g]['sum'], 'count': totals[g]['count'], 'max': totals[g]['count'] * spec['rating_max']} for g in (1, 2, 3)},
        'special_activities': marks('special_activities', forms.SPECIAL_ACTIVITIES[LEVEL]),
        'behaviour': marks('behaviour', forms.BEHAVIOUR_ITEMS),
        'comments': {str(g): ((years[g].content or {}).get('comment') or '') if g in years else '' for g in (1, 2, 3)},
        'attendance': {str(g): ({'school_days': years[g].school_days, 'suspended_days': years[g].suspended_days, 'absent_days': years[g].absent_days,
                                 'remarks': years[g].attendance_remarks} if g in years else None) for g in (1, 2, 3)},
        'prepared_on': today.isoformat(), 'problems': problems, 'ready': not problems,
    }
