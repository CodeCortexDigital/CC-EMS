"""The term report (通知表): a layout each school sets for itself, and what is kept for each student and term.

Unlike the 指導要録 the 通知表 has no national form: every school and board of education designs its own. So the *layout* is data:
which subjects, the rating scale, whether the three viewpoints show, the behaviour items and the comment boxes. An administrator
edits it; a teacher fills a report for each student and term; the page prints in the layout. A school's own sample layout can then be
copied by editing the layout, without changing code.

Layout (``TermReportLayout.config``):

    {"title": "通知表", "scale": "abc" | "five" | "percent", "viewpoints": true,
     "subjects": ["国語", ...], "conduct_items": ["基本的な生活習慣", ...],
     "comment_fields": [{"key": "homeroom", "label": "担任からの所見"}],
     "sections": {"attendance": true, "conduct": true, "comments": true},
     "thresholds": {"abc": [80, 50], "five": [90, 75, 60, 40]}}

Content of one report (``TermReport.content``):

    {"subjects": {"国語": {"v1": "A", "v2": "B", "v3": "A", "rating": "A"}}, "conduct": {"基本的な生活習慣": true}, "comments": {"homeroom": "..."}}
"""
from __future__ import annotations

from . import forms

SCALES = {'abc': ('A', 'B', 'C'), 'five': ('5', '4', '3', '2', '1')}
SCALE_LABELS = {'abc': 'A・B・C', 'five': '5段階 (5〜1)', 'percent': '点数 (0〜100)'}
MAX_SUBJECTS, MAX_ITEMS, MAX_COMMENTS = 30, 20, 6
DEFAULT_THRESHOLDS = {'abc': [80, 50], 'five': [90, 75, 60, 40]}


def default_config(level: str = 'elementary') -> dict:
    level = level if level in forms.LEVELS else 'elementary'
    subjects = [s['name'] for s in forms.LEVELS[level]['subjects']] or ['国語', '数学', '英語']
    return {
        'title': '通知表', 'scale': 'abc' if level == 'elementary' else 'five', 'viewpoints': True,
        'subjects': subjects, 'conduct_items': [label for _, label in forms.BEHAVIOUR_ITEMS],
        'comment_fields': [{'key': 'homeroom', 'label': '担任からの所見'}, {'key': 'home', 'label': 'ご家庭から'}],
        'sections': {'attendance': True, 'conduct': True, 'comments': True},
        'thresholds': {k: list(v) for k, v in DEFAULT_THRESHOLDS.items()},
    }


def clean_config(raw) -> tuple[dict | None, str | None]:
    """(clean layout, None) or (None, the problem in plain words)."""
    if not isinstance(raw, dict):
        return None, 'The layout must be an object.'
    scale = raw.get('scale', 'abc')
    if scale not in SCALE_LABELS:
        return None, 'Choose a rating scale: A・B・C, 5 levels or points.'
    subjects = [str(s).strip() for s in (raw.get('subjects') or []) if str(s).strip()]
    if not subjects:
        return None, 'Add at least one subject.'
    if len(subjects) > MAX_SUBJECTS or len(set(subjects)) != len(subjects):
        return None, f'Give up to {MAX_SUBJECTS} subjects, each name once.'
    items = [str(s).strip() for s in (raw.get('conduct_items') or []) if str(s).strip()]
    if len(items) > MAX_ITEMS or len(set(items)) != len(items):
        return None, f'Give up to {MAX_ITEMS} behaviour items, each name once.'
    comments, keys = [], set()
    for c in (raw.get('comment_fields') or []):
        key, label = str((c or {}).get('key') or '').strip(), str((c or {}).get('label') or '').strip()
        if not key or not label or key in keys:
            return None, 'Each comment box needs a name and a different key.'
        keys.add(key)
        comments.append({'key': key[:30], 'label': label[:60]})
    if len(comments) > MAX_COMMENTS:
        return None, f'Give up to {MAX_COMMENTS} comment boxes.'
    base = default_config()
    th = raw.get('thresholds') or {}
    thresholds = {k: _numbers(th.get(k), n) or base['thresholds'][k] for k, n in (('abc', 2), ('five', 4))}
    sections = {k: bool((raw.get('sections') or {}).get(k, True)) for k in ('attendance', 'conduct', 'comments')}
    return {'title': str(raw.get('title') or '通知表').strip()[:40], 'scale': scale, 'viewpoints': bool(raw.get('viewpoints', True)),
            'subjects': subjects, 'conduct_items': items, 'comment_fields': comments, 'sections': sections, 'thresholds': thresholds}, None


def _numbers(value, count):
    try:
        nums = [float(x) for x in value]
    except (TypeError, ValueError):
        return None
    ok = len(nums) == count and all(0 <= n <= 100 for n in nums) and nums == sorted(nums, reverse=True)
    return nums if ok else None


def rating_from_percent(config: dict, percent) -> str:
    """The rating a percentage becomes in this layout's scale ('' when there is no percentage)."""
    if percent is None:
        return ''
    p = float(percent)
    scale = config.get('scale', 'abc')
    if scale == 'percent':
        return str(round(p))
    cuts = (config.get('thresholds') or {}).get(scale) or DEFAULT_THRESHOLDS[scale]
    labels = SCALES[scale]
    for label, cut in zip(labels, cuts):
        if p >= cut:
            return label
    return labels[-1]


def clean_content(config: dict, raw) -> tuple[dict | None, str | None]:
    """Check a report's content against the layout; unknown subjects, items and boxes are an error, not silently dropped."""
    if not isinstance(raw, dict):
        return None, 'The report must be an object.'
    scale = config.get('scale', 'abc')
    out: dict = {'subjects': {}, 'conduct': {}, 'comments': {}}
    for name, cell in (raw.get('subjects') or {}).items():
        if name not in config['subjects']:
            return None, f'「{name}」 is not a subject of this layout.'
        cell = cell or {}
        row = {}
        for key in ('v1', 'v2', 'v3'):
            v = str(cell.get(key) or '')
            if v not in ('',) + forms.VIEWPOINT_VALUES:
                return None, f'{name}: a viewpoint is A, B or C.'
            row[key] = v
        rating = str(cell.get('rating') or '')
        if scale == 'percent':
            if rating:
                try:
                    if not 0 <= float(rating) <= 100:
                        raise ValueError
                except ValueError:
                    return None, f'{name}: the score is 0 to 100.'
        elif rating not in ('',) + SCALES[scale]:
            return None, f'{name}: the rating is one of {"・".join(SCALES[scale])}.'
        row['rating'] = rating
        out['subjects'][name] = row
    for item, mark in (raw.get('conduct') or {}).items():
        if item not in config['conduct_items']:
            return None, f'「{item}」 is not a behaviour item of this layout.'
        out['conduct'][item] = bool(mark)
    allowed = {c['key'] for c in config['comment_fields']}
    for key, text in (raw.get('comments') or {}).items():
        if key not in allowed:
            return None, f'「{key}」 is not a comment box of this layout.'
        text = str(text or '')
        if len(text) > 1500:
            return None, 'A comment is at most 1,500 characters.'
        out['comments'][key] = text
    return out, None
