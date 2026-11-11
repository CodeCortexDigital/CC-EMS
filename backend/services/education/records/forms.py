"""The shape of the Japanese cumulative record (指導要録), one definition per school level.

The three levels follow MEXT's reference forms (参考様式): 様式1 is the register of the pupil (学籍に関する記録) and 様式2 is the record of
guidance (指導に関する記録: ratings by subject, moral education, integrated study, special activities, behaviour, comments and attendance).
This one definition drives everything: what the screen asks for, what the server accepts, what is printed and what is exported.

What a cell holds:

* a viewpoint rating (観点別学習状況) is A, B or C: 知識・技能, 思考・判断・表現, 主体的に学習に取り組む態度;
* the overall rating (評定) is 1-3 in elementary school (from grade 3) and 1-5 in junior high school and high school;
* special activities and behaviour are marked with a circle (○) or left empty;
* the rest is text written by the class teacher.

Boards of Education and prefectures may adapt the reference forms, so the subjects and grades below are what the reference forms show, kept in
one place to be changed.
"""
from __future__ import annotations

VIEWPOINTS = [('v1', '知識・技能'), ('v2', '思考・判断・表現'), ('v3', '主体的に学習に取り組む態度')]
VIEWPOINT_VALUES = ('A', 'B', 'C')

# The ten items of 行動の記録, the same at every level.
BEHAVIOUR_ITEMS = [
    ('basic_habits', '基本的な生活習慣'), ('health_fitness', '健康・体力の向上'), ('self_reliance', '自主・自律'), ('responsibility', '責任感'),
    ('creativity', '創意工夫'), ('kindness', '思いやり・協力'), ('life_nature', '生命尊重・自然愛護'), ('service', '勤労・奉仕'),
    ('fairness', '公正・公平'), ('public_spirit', '公共心・公徳心'),
]

SPECIAL_ACTIVITIES = {
    'elementary': [('class_activity', '学級活動'), ('council', '児童会活動'), ('club', 'クラブ活動'), ('school_event', '学校行事')],
    'junior_high': [('class_activity', '学級活動'), ('council', '生徒会活動'), ('school_event', '学校行事')],
    'high': [('homeroom', 'ホームルーム活動'), ('council', '生徒会活動'), ('school_event', '学校行事')],
}

ALL_GRADES_ELEM = (1, 2, 3, 4, 5, 6)


def _s(code, name, grades, rating_from=3):
    """A subject: shown in these grades, with an overall rating (評定) from this grade on."""
    return {'code': code, 'name': name, 'grades': list(grades), 'rating_grades': [g for g in grades if g >= rating_from]}


LEVELS = {
    'elementary': {
        'label': '小学校児童指導要録', 'person': '児童', 'grades': 6, 'rating_max': 3,
        'subjects': [
            _s('JPN', '国語', ALL_GRADES_ELEM), _s('SOC', '社会', (3, 4, 5, 6)), _s('MATH', '算数', ALL_GRADES_ELEM), _s('SCI', '理科', (3, 4, 5, 6)),
            _s('LIFE', '生活', (1, 2)), _s('MUS', '音楽', ALL_GRADES_ELEM), _s('ART', '図画工作', ALL_GRADES_ELEM), _s('HOME', '家庭', (5, 6)),
            _s('PE', '体育', ALL_GRADES_ELEM), _s('ENG', '外国語', (5, 6)),
        ],
        'foreign_activity_grades': [3, 4],        # 外国語活動の記録
        'integrated_grades': [3, 4, 5, 6],        # 総合的な学習の時間の記録
        'moral_grades': list(ALL_GRADES_ELEM),
    },
    'junior_high': {
        'label': '中学校生徒指導要録', 'person': '生徒', 'grades': 3, 'rating_max': 5,
        'subjects': [
            _s('JPN', '国語', (1, 2, 3), 1), _s('SOC', '社会', (1, 2, 3), 1), _s('MATH', '数学', (1, 2, 3), 1), _s('SCI', '理科', (1, 2, 3), 1),
            _s('MUS', '音楽', (1, 2, 3), 1), _s('ART', '美術', (1, 2, 3), 1), _s('PE', '保健体育', (1, 2, 3), 1), _s('HOME', '技術・家庭', (1, 2, 3), 1),
            _s('ENG', '外国語', (1, 2, 3), 1), _s('ELEC', '選択教科', (1, 2, 3), 1),
        ],
        'foreign_activity_grades': [],
        'integrated_grades': [1, 2, 3],
        'moral_grades': [1, 2, 3],
    },
    'high': {
        'label': '高等学校生徒指導要録', 'person': '生徒', 'grades': 4, 'rating_max': 5,
        'subjects': [],                           # high school records courses (科目) with credits, not a fixed list of subjects
        'foreign_activity_grades': [],
        'integrated_grades': [1, 2, 3, 4],        # 総合的な探究の時間
        'moral_grades': [],
    },
}

# 教科 (subject areas) of the high school form, for the 修得単位数 table on the back of 様式1.
HIGH_SUBJECT_AREAS = ['国語', '地理歴史', '公民', '数学', '理科', '保健体育', '芸術', '外国語', '家庭', '情報', '理数', '農業', '工業', '商業', '水産', '看護',
                      '福祉', '体育', '音楽', '美術', '英語', '学校設定教科']

TEXT_LIMITS = {'moral': 1500, 'comment': 3000, 'integrated_activity': 800, 'integrated_viewpoint': 800, 'integrated_evaluation': 1500,
               'foreign_v1': 600, 'foreign_v2': 600, 'foreign_v3': 600}


def level_definition(level: str) -> dict:
    """The form of one school level, with the lists the screen needs (a plain, JSON-safe dictionary)."""
    if level not in LEVELS:
        raise KeyError(level)
    d = dict(LEVELS[level])
    d['level'] = level
    d['viewpoints'] = [{'key': k, 'label': v} for k, v in VIEWPOINTS]
    d['behaviour_items'] = [{'key': k, 'label': v} for k, v in BEHAVIOUR_ITEMS]
    d['special_activities'] = [{'key': k, 'label': v} for k, v in SPECIAL_ACTIVITIES[level]]
    d['high_subject_areas'] = HIGH_SUBJECT_AREAS if level == 'high' else []
    d['text_limits'] = TEXT_LIMITS
    return d


def level_for_class_grade(grade_level) -> str:
    """The school level for a class's grade_level (1-6 elementary, 7-9 junior high, 10-12 high school; 1-9 are used as year numbers here)."""
    try:
        g = int(grade_level)
    except (TypeError, ValueError):
        return 'elementary'
    if g >= 10:
        return 'high'
    if g >= 7:
        return 'junior_high'
    return 'elementary'


def grade_in_level(level: str, grade_level) -> int:
    """The year number inside its level (a class with grade_level 8 is year 2 of junior high)."""
    try:
        g = int(grade_level)
    except (TypeError, ValueError):
        return 1
    if level == 'junior_high':
        return max(1, min(3, g - 6))
    if level == 'high':
        return max(1, min(4, g - 9))
    return max(1, min(6, g))


# -------------------------------------------------------------------------------------------------------- validation
def clean_content(level: str, grade: int, content) -> tuple[dict, dict]:
    """Check one year's guidance record against the form. Returns (clean content, {field: message})."""
    errors: dict[str, str] = {}
    if level not in LEVELS:
        return {}, {'level': 'Unknown school level.'}
    spec = LEVELS[level]
    if not isinstance(content, dict):
        return {}, {'content': 'Content must be an object.'}
    out: dict = {}

    subjects = content.get('subjects') or {}
    if not isinstance(subjects, dict):
        errors['subjects'] = 'Subjects must be an object.'
        subjects = {}
    by_code = {s['code']: s for s in spec['subjects']}
    clean_subjects = {}
    for code, cell in subjects.items():
        subj = by_code.get(code)
        if subj is None:
            errors[f'subjects.{code}'] = 'This subject is not on the form.'
            continue
        if grade not in subj['grades']:
            errors[f'subjects.{code}'] = f'{subj["name"]} is not recorded in year {grade}.'
            continue
        cell = cell if isinstance(cell, dict) else {}
        item = {}
        for key, _label in VIEWPOINTS:
            v = str(cell.get(key) or '').strip().upper()
            if v and v not in VIEWPOINT_VALUES:
                errors[f'subjects.{code}.{key}'] = 'Use A, B or C.'
            elif v:
                item[key] = v
        rating = cell.get('rating')
        if rating not in (None, ''):
            try:
                r = int(rating)
            except (TypeError, ValueError):
                r = 0
            if grade not in subj['rating_grades']:
                errors[f'subjects.{code}.rating'] = f'No overall rating (評定) is given for {subj["name"]} in year {grade}.'
            elif not 1 <= r <= spec['rating_max']:
                errors[f'subjects.{code}.rating'] = f'The overall rating must be 1 to {spec["rating_max"]}.'
            else:
                item['rating'] = r
        if item:
            clean_subjects[code] = item
    out['subjects'] = clean_subjects

    if level == 'high':
        courses = content.get('courses') or []
        clean_courses = []
        if not isinstance(courses, list):
            errors['courses'] = 'Courses must be a list.'
            courses = []
        for i, c in enumerate(courses[:80]):
            if not isinstance(c, dict):
                continue
            area, name = str(c.get('area') or '').strip(), str(c.get('course') or '').strip()
            if not name:
                errors[f'courses.{i}'] = 'Give the course name (科目).'
                continue
            item = {'area': area[:20], 'course': name[:40]}
            for key, _label in VIEWPOINTS:
                v = str(c.get(key) or '').strip().upper()
                if v and v not in VIEWPOINT_VALUES:
                    errors[f'courses.{i}.{key}'] = 'Use A, B or C.'
                elif v:
                    item[key] = v
            for key, hi in (('rating', 5), ('credits', 20)):
                raw = c.get(key)
                if raw in (None, ''):
                    continue
                try:
                    n = int(raw)
                except (TypeError, ValueError):
                    n = -1
                if not (1 if key == 'rating' else 0) <= n <= hi:
                    errors[f'courses.{i}.{key}'] = f'Must be a whole number up to {hi}.'
                else:
                    item[key] = n
            clean_courses.append(item)
        out['courses'] = clean_courses

    def text(key, label, limit):
        v = content.get(key)
        if v in (None, ''):
            return
        v = str(v)
        if len(v) > limit:
            errors[key] = f'{label} is too long (at most {limit} characters).'
        else:
            out[key] = v

    if grade in spec['moral_grades']:
        text('moral', '道徳', TEXT_LIMITS['moral'])
    text('comment', '総合所見', TEXT_LIMITS['comment'])
    if grade in spec['integrated_grades']:
        for key, label in (('integrated_activity', '学習活動'), ('integrated_viewpoint', '観点'), ('integrated_evaluation', '評価')):
            text(key, label, TEXT_LIMITS[key])
    if grade in spec['foreign_activity_grades']:
        for key, label in (('foreign_v1', '知識・技能'), ('foreign_v2', '思考・判断・表現'), ('foreign_v3', '主体的に学習に取り組む態度')):
            text(key, f'外国語活動 {label}', TEXT_LIMITS[key])

    for field, items in (('special_activities', SPECIAL_ACTIVITIES[level]), ('behaviour', BEHAVIOUR_ITEMS)):
        given = content.get(field) or {}
        if not isinstance(given, dict):
            errors[field] = 'Must be an object.'
            continue
        known = {k for k, _ in items}
        marks = {}
        for key, val in given.items():
            if key not in known:
                errors[f'{field}.{key}'] = 'Not on the form.'
            elif val in (True, 'true', 1, '1', '○'):
                marks[key] = True
        out[field] = marks
    return out, errors
