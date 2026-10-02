"""Give every teacher a real subject list where their free-text specializations name a subject exactly.

Anything that does not match (a job title such as "Teacher", a typo) is left alone: nothing is guessed. The Teaching
coverage screen lists those people so an administrator can fix them.
"""
import re

from django.db import migrations

ALIASES = {
    'math': 'mathematics', 'maths': 'mathematics', 'mathematic': 'mathematics',
    'ela': 'english', 'english language': 'english', 'english language arts': 'english', 'language arts': 'english',
    'pe': 'physical education', 'phys ed': 'physical education', 'physed': 'physical education', 'gym': 'physical education',
    'cs': 'computer science', 'ict': 'computer science', 'computing': 'computer science', 'computers': 'computer science',
    'sci': 'science', 'social': 'social studies', 'sst': 'social studies',
    'bio': 'biology', 'chem': 'chemistry', 'phys': 'physics',
}


def canonical(text):
    n = re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', str(text or '').lower())).strip()
    return ALIASES.get(n, n)


def fill(apps, schema_editor):
    Teacher = apps.get_model('education_academics', 'Teacher')
    Subject = apps.get_model('education_academics', 'Subject')
    by_tenant = {}
    for s in Subject.objects.all():
        by_tenant.setdefault(s.tenant_id, []).append(s)
    for t in Teacher.objects.all():
        raw = t.specializations if isinstance(t.specializations, list) else [t.specializations or '']
        words = {canonical(p) for item in raw for p in re.split(r'[,;/&|]| and ', str(item)) if canonical(p)}
        if not words:
            continue
        matched = [s for s in by_tenant.get(t.tenant_id, []) + (by_tenant.get(None, []) if t.tenant_id else [])
                   if {canonical(s.name), canonical(s.code)} & words]
        if matched:
            t.subjects.add(*matched)


class Migration(migrations.Migration):

    dependencies = [
        ('education_academics', '0029_teacher_subjects_scheduling_policy'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
