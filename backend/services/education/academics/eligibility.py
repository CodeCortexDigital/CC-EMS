"""Who may teach what.

A teacher is qualified for a subject when the subject is on their ``subjects`` list. A teacher with no list yet is
matched by the free-text ``specializations`` against subject names and codes (exact words, plus a few common short
forms such as "maths"), never by loose substring matching, so "Art" does not qualify someone for "Martial Arts".
"""
import re

ALIASES = {
    'math': 'mathematics', 'maths': 'mathematics', 'mathematic': 'mathematics',
    'ela': 'english', 'english language': 'english', 'english language arts': 'english', 'language arts': 'english',
    'pe': 'physical education', 'phys ed': 'physical education', 'physed': 'physical education', 'gym': 'physical education',
    'cs': 'computer science', 'ict': 'computer science', 'computing': 'computer science', 'computers': 'computer science',
    'sci': 'science', 'social': 'social studies', 'sst': 'social studies',
    'bio': 'biology', 'chem': 'chemistry', 'phys': 'physics',
}


def norm(text) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', str(text or '').lower())).strip()


def canonical(text) -> str:
    n = norm(text)
    return ALIASES.get(n, n)


def subject_keys(subject) -> set:
    keys = {canonical(subject.name), canonical(subject.code)}
    keys.discard('')
    return keys


def text_entries(teacher) -> set:
    """The canonical words in a teacher's free-text specializations ("Physics, Maths" gives physics and mathematics)."""
    raw = teacher.specializations if isinstance(teacher.specializations, list) else [teacher.specializations or '']
    out = set()
    for item in raw:
        for part in re.split(r'[,;/&|]| and ', str(item)):
            c = canonical(part)
            if c:
                out.add(c)
    return out


def qualified_subject_ids(teacher, subjects=None):
    """Ids of the subjects this teacher may teach. `subjects` (all of the school's Subject rows) saves a query."""
    from .models import Subject
    listed = {s.id for s in teacher.subjects.all()} if teacher.pk else set()
    if listed:
        return listed
    words = text_entries(teacher)
    if not words:
        return set()
    pool = subjects if subjects is not None else Subject.objects.all()
    return {s.id for s in pool if subject_keys(s) & words}


def is_qualified(teacher, subject, subjects=None) -> bool:
    return subject.id in qualified_subject_ids(teacher, subjects)


def why_not(teacher, subject) -> str:
    """A sentence for the screen when the teacher is not qualified."""
    if teacher.pk and teacher.subjects.exists():
        names = ', '.join(sorted(teacher.subjects.values_list('name', flat=True)))
        return f'{teacher.full_name} is qualified for {names}, not {subject.name}.'
    return (f'{teacher.full_name} has no subjects set. Add {subject.name} to their profile '
            f'(Staff > edit > Subjects they teach) first.')


def qualified_teachers(subject, tenant=None, only_active=True):
    """Every teacher qualified for the subject (relief teachers included)."""
    from .models import Subject, Teacher
    subjects = list(Subject.objects.all())
    qs = Teacher.objects.all()
    if only_active:
        qs = qs.filter(is_active=True)
    return [t for t in qs.prefetch_related('subjects') if subject.id in qualified_subject_ids(t, subjects)]


def get_policy(tenant):
    """The school's scheduling policy, or an unsaved one carrying the defaults."""
    from .models import SchedulingPolicy
    found = SchedulingPolicy._base_manager.filter(tenant=tenant).first() if tenant else None
    return found or SchedulingPolicy(tenant=tenant)
