"""Sample cumulative records for the Japanese demo school, so the 指導要録 screens are not empty when a visitor opens them.

Every value is invented. The older years (1 to year-1) are filled and sealed, the current year is filled but only the class teacher's seal is
missing, so the whole flow (check, seal, print, export) can be shown. Content is passed through the same checker as real input.
"""
from __future__ import annotations

import random
from datetime import datetime, time, timezone

from django.contrib.auth import get_user_model

from . import forms, prefill
from .models import CumulativeRecord, CumulativeYear

MORAL = ['友達の気持ちを考えて行動しようとする姿が増えました。', '約束やきまりの大切さについて、自分の経験と結び付けて考えを深めました。',
         '命の大切さを学ぶ授業で、自分の思いを丁寧に書くことができました。', '誰にでも親切に接し、学級の仲間から信頼されています。']
INTEGRATED = [('地域の自然や人々について調べる', '課題を見つける力、情報を集めて整理する力', '地域の方への聞き取りを通して、自分の課題を見つけ、分かったことを分かりやすくまとめました。'),
              ('環境を守る活動を考える', '自分で考え、判断し、表現する力', 'ごみの分別について班で話し合い、校内に向けて提案を発表することができました。')]
COMMENTS = ['明るく元気で、学級の活動にも進んで取り組んでいます。', '最後までやり抜く力があり、学習面でも着実に力を伸ばしました。',
            '友達と協力しながら、委員会活動でも責任を果たしました。', '読書が好きで、自分の考えを言葉にして伝えることが上手になりました。']
FOREIGN = ['英語の歌やゲームを楽しみ、簡単な表現を使って挨拶ができました。', '相手の話を聞こうとし、身近な事柄を英語で伝えようとしました。', '積極的に友達に話しかけ、コミュニケーションを楽しみました。']


def _cell(rng, level):
    """A believable set of three viewpoint ratings and an overall rating that agrees with them."""
    marks = [rng.choices(['A', 'B', 'C'], weights=[5, 4, 1])[0] for _ in range(3)]
    score = sum({'A': 3, 'B': 2, 'C': 1}[m] for m in marks) / 3
    if level == 'elementary':
        rating = 3 if score >= 2.5 else 2 if score >= 1.6 else 1
    else:
        rating = 5 if score >= 2.8 else 4 if score >= 2.4 else 3 if score >= 1.8 else 2 if score >= 1.3 else 1
    return {'v1': marks[0], 'v2': marks[1], 'v3': marks[2], 'rating': rating}


def build_content(rng, level: str, grade: int) -> dict:
    spec = forms.LEVELS[level]
    content: dict = {'subjects': {}, 'behaviour': {}, 'special_activities': {}}
    for s in spec['subjects']:
        if grade in s['grades']:
            cell = _cell(rng, level)
            if grade not in s['rating_grades']:
                cell.pop('rating')
            content['subjects'][s['code']] = cell
    if grade in spec['moral_grades']:
        content['moral'] = rng.choice(MORAL)
    if grade in spec['integrated_grades']:
        a, b, c = rng.choice(INTEGRATED)
        content.update(integrated_activity=a, integrated_viewpoint=b, integrated_evaluation=c)
    if grade in spec['foreign_activity_grades']:
        content.update(foreign_v1=rng.choice(FOREIGN), foreign_v2=rng.choice(FOREIGN), foreign_v3=rng.choice(FOREIGN))
    for key, _label in forms.BEHAVIOUR_ITEMS:
        if rng.random() < 0.55:
            content['behaviour'][key] = True
    for key, _label in forms.SPECIAL_ACTIVITIES[level]:
        if rng.random() < 0.8 and not (key == 'club' and grade < 4):
            content['special_activities'][key] = True
    content['comment'] = rng.choice(COMMENTS)
    clean, errors = forms.clean_content(level, grade, content)
    assert not errors, errors
    return clean


def seed_demo_records(school, school_class, user=None, seed: int = 2026) -> int:
    """Records for every student of one class, years 1 to the class's year filled in. Returns how many records were made."""
    from services.education.academics.models import AcademicYear
    from services.education.students.models import Student

    rng = random.Random(seed)
    year = AcademicYear.objects.filter(is_active=True).first()
    staff = user or get_user_model().objects.filter(email='admin@code.com').first()
    students = Student.objects.filter(current_class=school_class, is_active=True).order_by('student_id')
    from services.education.academics.models import Teacher
    teachers = list(Teacher.objects.filter(role__iexact='Teacher').order_by('full_name').values_list('full_name', flat=True)) or ['担任']
    if not school_class.homeroom_teacher_id and not school_class.teacher_name:   # the sample classes have no 担任 yet; the current year needs one to be sealed
        homeroom = Teacher.objects.filter(role__iexact='Teacher').order_by('full_name').first()
        if homeroom:
            school_class.homeroom_teacher = homeroom
            school_class.save(update_fields=['homeroom_teacher'])
    made = 0
    for student in students:
        record, _ = prefill.open_record(student, school, staff)
        record.student_furigana = record.student_furigana or ''
        record.save()
        current = forms.grade_in_level(record.level, school_class.grade_level)
        for grade in range(1, current + 1):
            entry = prefill.fill_year(record, grade, year)
            if grade < current:                                   # earlier years: invented class, same teacher name pattern, attendance made up
                entry.year_label = f'令和{8 - (current - grade)}年度'
                entry.class_name = f'{grade}年{rng.choice(["1組", "2組"])}'
                entry.school_days = rng.randint(195, 205)
                entry.suspended_days = rng.choice([0, 0, 0, 1, 2])
                entry.absent_days = rng.choice([0, 0, 1, 2, 3, 5])
            entry.content = build_content(rng, record.level, grade)
            if grade < current:                                   # sealed by the teacher and the principal at the end of that year
                when = datetime.combine(datetime(2020 + grade, 3, 24).date(), time(9, 0), tzinfo=timezone.utc)
                entry.teacher_confirmed_at = entry.principal_confirmed_at = when
                entry.teacher_confirmed_by = entry.principal_confirmed_by = staff
                entry.principal_name = entry.principal_name or '校長'
                entry.teacher_name = entry.teacher_name or rng.choice(teachers)
            entry.save()
        made += 1
    return made
