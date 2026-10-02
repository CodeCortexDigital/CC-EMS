"""Timetable generator.

Builds a week for every section of the school. Hard rules are never broken in the result: a lesson is only placed
when the class, a *qualified* teacher and a suitable room are all free, the teacher is available and within their
daily, weekly and in-a-row limits. What cannot be placed is reported with the reason, never forced.

Method: place the hardest lessons first (fewest qualified teachers, most periods), each at the lowest-cost free slot;
when a lesson finds no slot, try moving one blocking lesson elsewhere ("ejection"); repeat from several random starts
and keep the best week. Everything is seeded, so the same data and seed give the same timetable: the preview and the
commit that follows it are identical.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from django.apps import apps
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .eligibility import canonical, get_policy, qualified_subject_ids

DAY_NAMES = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
DEFAULT_DAYS = DAY_NAMES[:5]
HEAVY = {'mathematics', 'english', 'science', 'physics', 'chemistry', 'biology', 'maths'}
# Subjects that need a particular kind of room, when the school has such rooms.
ROOM_KIND = [
    ({'chemistry', 'physics', 'biology', 'science lab', 'laboratory'}, {'lab'}),
    ({'computer science', 'computer', 'ict', 'computing'}, {'lab', 'computer'}),
    ({'physical education', 'sports', 'games', 'pe'}, {'sports', 'hall', 'gym'}),
]


@dataclass
class Lesson:
    key: int
    section_id: object
    class_ref_id: str
    cs_id: object
    subject: str
    subject_id: object
    class_name: str
    section_name: str
    size: int
    heavy: bool
    home: object = None          # the teacher who normally takes this subject for this section
    candidates: list = field(default_factory=list)
    kind: set = field(default_factory=set)   # required room categories (empty = any)
    n_candidates: int = 0


class Problem:
    """Everything the solver needs, loaded once."""

    def __init__(self, year_id, tenant_id=None):
        A = lambda name: apps.get_model('education_academics', name)  # noqa: E731
        self.year_id = year_id
        self.tenant_id = tenant_id
        flt = (lambda qs: qs.filter(Q(tenant_id=tenant_id) | Q(tenant_id__isnull=True))) if tenant_id else (lambda qs: qs)
        self.warnings: list[str] = []
        self.policy = get_policy(self._tenant())

        self.sections = list(flt(A('Section').objects.select_related('class_ref')))
        self.rooms = list(flt(A('Classroom').objects.filter(is_active=True)).order_by('capacity', 'name'))
        self.periods = list(A('Period').objects.filter(academic_year_id=year_id, is_active=True, is_break=False).order_by('period_number'))
        self.teachers = {t.id: t for t in flt(A('Teacher').objects.filter(is_active=True)).prefetch_related('subjects')}
        self._days()
        subjects = list(flt(A('Subject').objects.all()))
        self.assigned = defaultdict(list)
        for a in A('TeacherSubjectAssignment').objects.filter(academic_year_id=year_id, is_active=True):
            if a.teacher_id in self.teachers:
                self.assigned[a.class_subject_id].append(a.teacher_id)
        self.qualified = defaultdict(list)
        for t in self.teachers.values():
            for sid in qualified_subject_ids(t, subjects):
                self.qualified[sid].append(t.id)
        self.avail = defaultdict(lambda: defaultdict(set))
        has_rows = set()
        period_by_id = {p.id: p for p in self.periods}
        for ta in A('TeacherAvailability').objects.filter(academic_year_id=year_id):
            day = ta.day_of_week.lower()
            has_rows.add((ta.teacher_id, day))
            if ta.is_available:
                for p in self.periods:
                    if ta.start_time <= p.start_time and ta.end_time >= p.end_time:
                        self.avail[ta.teacher_id][day].add(p.id)
        self.restricted = has_rows
        self.period_ids = [p.id for p in self.periods]
        self.period_idx = {p.id: i for i, p in enumerate(self.periods)}
        self._period_by_id = period_by_id
        self.lessons: list[Lesson] = []
        self.unplannable: list[dict] = []
        self._build_lessons(flt, A)

    def _tenant(self):
        if not self.tenant_id:
            return None
        return apps.get_model('core_tenants', 'School').objects.filter(pk=self.tenant_id).first()

    def _days(self):
        """The school's working days (from its weekday setup when it has one) and which are half days."""
        WeekdayConfig = apps.get_model('education_finance', 'WeekdayConfig')
        rows = list(WeekdayConfig.objects.filter(tenant_id=self.tenant_id) if self.tenant_id else WeekdayConfig.objects.all())
        days, half = [], set()
        for r in sorted(rows, key=lambda r: r.order):
            code = (r.day_code or r.name or '').strip().lower()[:3]
            full = next((d for d in DAY_NAMES if d.startswith(code)), None) if code else None
            if full and r.is_active:
                days.append(full)
                if r.is_half_day:
                    half.add(full)
        self.days = days or list(DEFAULT_DAYS)
        self.half_days = half

    def periods_on(self, day):
        """Period indexes used on a day: all of them, or the first half on a half day."""
        n = len(self.periods)
        return range(math.ceil(n / 2) if day in self.half_days else n)

    def _build_lessons(self, flt, A):
        policy = self.policy
        class_subjects = defaultdict(list)
        class_ids = {s.class_ref_id for s in self.sections}
        for cs in A('ClassSubject').objects.filter(class_ref_id__in=class_ids).select_related('subject', 'class_ref'):
            class_subjects[cs.class_ref_id].append(cs)
        slots_per_week = sum(len(self.periods_on(d)) for d in self.days)
        regular = [t.id for t in self.teachers.values() if t.teacher_type != 'relief']
        key = 0
        # Home teacher per (section, class-subject): the assigned one, else the least loaded qualified one.
        projected = Counter()
        entries = []
        for section in self.sections:
            size = section.capacity or getattr(section.class_ref, 'max_students', None) or 30
            for cs in class_subjects.get(section.class_ref_id, []):
                n = max(1, min(cs.periods_per_week or 1, slots_per_week))
                subj = cs.subject.name
                cands = list(dict.fromkeys(self.assigned.get(cs.id, []) + [t for t in self.qualified.get(cs.subject_id, [])
                                                                             if self.teachers[t].teacher_type != 'relief']))
                if not cands and not policy.enforce_subject_match:
                    cands = list(regular)
                    if cands:
                        self.warnings.append(f'{section.class_ref.name} {subj}: nobody is qualified, so any teacher was used because the subject rule is switched off.')
                kinds = set()
                for words, cats in ROOM_KIND:
                    if canonical(subj) in words or canonical(cs.subject.code) in words:
                        kinds = cats
                entries.append((section, cs, n, size, subj, cands, kinds))
        entries.sort(key=lambda e: (len(e[5]) or 99, -e[2]))
        for section, cs, n, size, subj, cands, kinds in entries:
            home = None
            if cands:
                assigned_first = [t for t in cands if t in self.assigned.get(cs.id, [])]
                pool = assigned_first or cands
                under = [t for t in pool if projected[t] + n <= policy.max_periods_per_week]
                home = min(under or pool, key=lambda t: (projected[t], str(t)))
                projected[home] += n
            if kinds and not any((r.category or '').lower() in kinds for r in self.rooms):
                self.warnings.append(f'{subj} needs a {"/".join(sorted(kinds))} room but the school has none set up; any room was used.')
                kinds = set()
            for _ in range(n):
                self.lessons.append(Lesson(
                    key=key, section_id=section.id, class_ref_id=str(section.class_ref_id), cs_id=cs.id, subject=subj,
                    subject_id=cs.subject_id, class_name=section.class_ref.name, section_name=section.name, size=size,
                    heavy=canonical(subj) in HEAVY, home=home, candidates=cands, kind=kinds, n_candidates=len(cands)))
                key += 1
        # Dedupe repeated room-kind warnings and keep them short.
        self.warnings = list(dict.fromkeys(self.warnings))[:20]


class Solution:
    def __init__(self, problem: Problem, rng: random.Random):
        self.p = problem
        self.rng = rng
        self.placed: dict[int, tuple] = {}                    # lesson key -> (day, pi, teacher, room)
        self.sec_busy: dict[tuple, int] = {}                  # (section, day, pi) -> lesson key
        self.t_busy: dict[tuple, int] = {}                    # (teacher, day, pi) -> lesson key
        self.r_busy: dict[tuple, int] = {}                    # (room, day, pi) -> lesson key
        self.t_day = Counter()
        self.t_week = Counter()
        self.sec_day = Counter()
        self.sec_subject_day = Counter()
        self.cost = 0.0
        self.why: dict[int, Counter] = defaultdict(Counter)

    # ---- rule checks -----------------------------------------------------------------------------------------
    def _teacher_ok(self, t, day, pi):
        """None when the teacher can take this slot, else the name of the rule that stops them."""
        p = self.p
        pol = p.policy
        if (t, day) in p.restricted and p.period_ids[pi] not in p.avail[t][day]:
            return 'availability'
        if (t, day, pi) in self.t_busy:
            return 'teacher'
        if self.t_day[(t, day)] >= pol.max_periods_per_day:
            return 'day limit'
        if self.t_week[t] >= pol.max_periods_per_week:
            return 'week limit'
        run, i = 1, pi - 1
        while i >= 0 and (t, day, i) in self.t_busy:
            run += 1
            i -= 1
        i = pi + 1
        while i < len(p.periods) and (t, day, i) in self.t_busy:
            run += 1
            i += 1
        if run > pol.max_consecutive:
            return 'in a row'
        return None

    def _room(self, lesson, day, pi):
        """The free room that fits best (smallest that holds the class), or None."""
        best, fallback = None, None
        for r in self.p.rooms:
            if lesson.kind and (r.category or '').lower() not in lesson.kind:
                continue
            if (r.id, day, pi) in self.r_busy:
                continue
            if r.capacity >= lesson.size:
                best = r
                break
            fallback = r  # largest too-small room (rooms are sorted by capacity)
        return best or fallback

    def _cost(self, lesson, day, pi, teacher):
        p = self.p
        c = 4.0 * self.sec_subject_day[(lesson.section_id, lesson.cs_id, day)]
        c += 1.5 * self.sec_day[(lesson.section_id, day)]
        c += 0.5 * self.t_day[(teacher, day)]
        n = len(p.periods)
        c += (0.2 * pi) if lesson.heavy else (0.08 * (n - pi))
        if lesson.home is not None and teacher != lesson.home:
            c += 6.0
        return c + self.rng.random() * 0.4

    def _options(self, lesson):
        """Every feasible (cost, day, pi, teacher, room) for the lesson, counting why others failed."""
        p = self.p
        out = []
        cands = ([lesson.home] if lesson.home is not None else []) + [t for t in lesson.candidates if t != lesson.home]
        for day in p.days:
            for pi in p.periods_on(day):
                if (lesson.section_id, day, pi) in self.sec_busy:
                    self.why[lesson.key]['class busy'] += 1
                    continue
                room = None
                for t in cands:
                    bad = self._teacher_ok(t, day, pi)
                    if bad:
                        self.why[lesson.key][bad] += 1
                        continue
                    room = room or self._room(lesson, day, pi)
                    if room is None:
                        self.why[lesson.key]['room'] += 1
                        break
                    out.append((self._cost(lesson, day, pi, t), day, pi, t, room))
        return out

    # ---- placing and removing ----------------------------------------------------------------------------------
    def put(self, lesson, day, pi, t, room, cost=0.0):
        self.placed[lesson.key] = (day, pi, t, room)
        self.sec_busy[(lesson.section_id, day, pi)] = lesson.key
        self.t_busy[(t, day, pi)] = lesson.key
        self.r_busy[(room.id, day, pi)] = lesson.key
        self.t_day[(t, day)] += 1
        self.t_week[t] += 1
        self.sec_day[(lesson.section_id, day)] += 1
        self.sec_subject_day[(lesson.section_id, lesson.cs_id, day)] += 1
        self.cost += cost

    def remove(self, lesson):
        day, pi, t, room = self.placed.pop(lesson.key)
        del self.sec_busy[(lesson.section_id, day, pi)]
        del self.t_busy[(t, day, pi)]
        del self.r_busy[(room.id, day, pi)]
        self.t_day[(t, day)] -= 1
        self.t_week[t] -= 1
        self.sec_day[(lesson.section_id, day)] -= 1
        self.sec_subject_day[(lesson.section_id, lesson.cs_id, day)] -= 1
        return day, pi, t, room

    def place(self, lesson):
        opts = self._options(lesson)
        if not opts:
            return False
        c, day, pi, t, room = min(opts, key=lambda o: o[0])
        self.put(lesson, day, pi, t, room, c)
        return True

    def eject(self, lesson, by_key):
        """Free a slot by moving one blocking lesson somewhere else, then take it. Returns True on success."""
        p = self.p
        slots = [(d, i) for d in p.days for i in p.periods_on(d)]
        self.rng.shuffle(slots)
        for day, pi in slots[:40]:
            blocker_key = self.sec_busy.get((lesson.section_id, day, pi))
            if blocker_key is None:  # the class is free here, so a qualified teacher is what blocks
                for t in lesson.candidates:
                    blocker_key = self.t_busy.get((t, day, pi))
                    if blocker_key is not None:
                        break
            if blocker_key is None or blocker_key not in self.placed:
                continue
            blocker = by_key[blocker_key]
            old = self.remove(blocker)
            opts = self._options(lesson)
            if opts:
                c, d, i, t, room = min(opts, key=lambda o: o[0])
                self.put(lesson, d, i, t, room, c)
                if self.place(blocker):
                    return True
                self.remove(lesson)
            self.put(blocker, *old)
        return False


def _solve(problem: Problem, seed: int):
    rng = random.Random(seed)
    sol = Solution(problem, rng)
    by_key = {l.key: l for l in problem.lessons}
    order = sorted(problem.lessons, key=lambda l: (l.n_candidates or 99, -(1 if l.heavy else 0), rng.random()))
    left = []
    for lesson in order:
        if not lesson.candidates:
            left.append(lesson)
            continue
        if not sol.place(lesson):
            left.append(lesson)
    still = []
    for lesson in left:
        if lesson.candidates and (sol.place(lesson) or sol.eject(lesson, by_key)):
            continue
        still.append(lesson)
    return sol, still


def _diagnose(problem, sol, lesson):
    if not lesson.candidates:
        return (f'Nobody is qualified to teach {lesson.subject}. Tick it on a teacher profile (Staff > edit > Subjects they teach) '
                f'or assign someone.')
    sol.why.pop(lesson.key, None)
    sol._options(lesson)  # look again at the finished week, so the reason is about the final state
    why = sol.why.get(lesson.key, Counter())
    if why:
        # The reason a person can act on first; "class busy" and "teacher busy" are the general case.
        order = ['week limit', 'day limit', 'in a row', 'availability', 'room', 'teacher', 'class busy']
        reason = next(r for r in order if why.get(r))
        text = {
            'week limit': 'every qualified teacher is already at the weekly limit',
            'day limit': 'every qualified teacher is already at the daily limit on the free days',
            'in a row': 'every qualified teacher would exceed the lessons-in-a-row limit',
            'teacher': 'the qualified teachers are busy in every period the class is free',
            'availability': 'the qualified teachers are not available in the periods the class is free',
            'class busy': 'the class has no free period left',
            'room': 'no suitable room is free',
        }[reason]
        return f'No place found: {text}. Qualify another teacher for {lesson.subject}, raise the limits, or reduce the periods per week.'
    return 'No place found.'


def build(year_id, tenant_id=None, seed=None, restarts=6):
    """Solve and return (problem, best solution, unscheduled lessons, seed used)."""
    problem = Problem(year_id, tenant_id)
    if not problem.rooms or not problem.periods:
        return problem, None, [], seed
    base = seed if seed is not None else random.SystemRandom().randrange(1, 10 ** 9)
    best = None
    for i in range(max(1, restarts)):
        sol, left = _solve(problem, base + i)
        score = (len(left), sol.cost)
        if best is None or score < best[0]:
            best = (score, sol, left, base + i)
        if not left and best[0][0] == 0 and i >= 1:
            break
    return problem, best[1], best[2], base


def _rows(problem, sol):
    out = []
    for lesson in problem.lessons:
        if lesson.key in sol.placed:
            day, pi, t, room = sol.placed[lesson.key]
            out.append({'class_subject_id': lesson.cs_id, 'class_ref_id': lesson.class_ref_id, 'teacher_id': t,
                        'section_id': lesson.section_id, 'classroom_id': room.id, 'room_capacity': room.capacity,
                        'day_of_week': day, 'period_id': problem.period_ids[pi]})
    return out


def _workloads(problem, sol):
    per = defaultdict(lambda: Counter())
    for day, pi, t, room in sol.placed.values():
        per[t][day] += 1
    rows = []
    for t, days in per.items():
        rows.append({'teacher': problem.teachers[t].full_name, 'periods': sum(days.values()),
                     'max_day': max(days.values()), 'days': len(days)})
    return sorted(rows, key=lambda r: (-r['periods'], r['teacher']))


def _snapshot_entries(qs):
    return [{'class_subject_id': str(e.class_subject_id), 'teacher_id': str(e.teacher_id), 'classroom_id': str(e.classroom_id),
             'day_of_week': e.day_of_week, 'period_id': str(e.period_id), 'section_id': str(e.section_id) if e.section_id else None,
             'is_active': e.is_active} for e in qs]


def _classes_in_scope(problem):
    return {s.class_ref_id for s in problem.sections}


def run(year_id, tenant_id=None, seed=None, restarts=6, commit=False, user=None):
    """Generate a timetable. With commit=False nothing is saved and the proposal is returned for review."""
    TimetableEntry = apps.get_model('education_academics', 'TimetableEntry')
    TimetableSnapshot = apps.get_model('education_academics', 'TimetableSnapshot')

    problem, sol, left, used_seed = build(year_id, tenant_id, seed, restarts)
    if sol is None or not problem.lessons:
        if not problem.rooms or not problem.periods:
            return {'error': 'Missing set-up: the school needs classrooms and time periods for this year before a timetable can be made.'}
        return {'error': 'No class-subjects to schedule for this school and year.'}

    rows = _rows(problem, sol)
    unscheduled = {}
    for lesson in left:
        k = (lesson.class_name, lesson.section_name, lesson.subject)
        e = unscheduled.setdefault(k, {'class_name': lesson.class_name, 'section': lesson.section_name, 'subject': lesson.subject,
                                       'missing': 0, 'reason': _diagnose(problem, sol, lesson)})
        e['missing'] += 1
    requested = len(problem.lessons)
    fitness = max(0.0, 1000.0 - 25.0 * len(left) - min(200.0, sol.cost / max(1, requested) * 4))
    result = {
        'status': 'success', 'committed': bool(commit), 'seed': used_seed, 'generations_run': restarts,
        'fitness_score': round(fitness, 1), 'slots_scheduled': len(rows), 'slots_requested': requested,
        'conflicts_resolved': not left, 'unscheduled': sorted(unscheduled.values(), key=lambda e: (-e['missing'], e['class_name'])),
        'workloads': _workloads(problem, sol), 'warnings': problem.warnings,
    }
    if commit:
        with transaction.atomic():
            classes = _classes_in_scope(problem)
            existing = TimetableEntry.objects.filter(academic_year_id=year_id, class_subject__class_ref_id__in=classes)
            snap = TimetableSnapshot.objects.create(
                tenant=problem._tenant(), academic_year_id=year_id, created_by=user, entries=_snapshot_entries(existing),
                class_ids=[str(c) for c in classes])
            existing.delete()
            TimetableEntry.objects.bulk_create([
                TimetableEntry(academic_year_id=year_id, class_subject_id=r['class_subject_id'], teacher_id=r['teacher_id'],
                               classroom_id=r['classroom_id'], day_of_week=r['day_of_week'], period_id=r['period_id'],
                               section_id=r['section_id']) for r in rows])
        result['snapshot_id'] = str(snap.id)
    else:
        result['slots'] = rows
    return result


def undo(snapshot):
    """Put the timetable back as it was before the generation that made this snapshot."""
    TimetableEntry = apps.get_model('education_academics', 'TimetableEntry')
    TimetableSnapshot = apps.get_model('education_academics', 'TimetableSnapshot')
    if snapshot.undone:
        raise ValueError('This change has already been undone.')
    with transaction.atomic():
        current = TimetableEntry.objects.filter(academic_year_id=snapshot.academic_year_id,
                                                class_subject__class_ref_id__in=snapshot.class_ids)
        TimetableSnapshot.objects.create(tenant_id=snapshot.tenant_id, academic_year_id=snapshot.academic_year_id,
                                         created_by=None, entries=_snapshot_entries(current), class_ids=snapshot.class_ids,
                                         label='Before undo', undone=True)
        current.delete()
        TimetableEntry.objects.bulk_create([
            TimetableEntry(academic_year_id=snapshot.academic_year_id, class_subject_id=e['class_subject_id'],
                           teacher_id=e['teacher_id'], classroom_id=e['classroom_id'], day_of_week=e['day_of_week'],
                           period_id=e['period_id'], section_id=e['section_id'], is_active=e['is_active'])
            for e in snapshot.entries])
        snapshot.undone = True
        snapshot.save(update_fields=['undone'])
    return len(snapshot.entries)


def prune_snapshots(days=30):
    TimetableSnapshot = apps.get_model('education_academics', 'TimetableSnapshot')
    return TimetableSnapshot.objects.filter(created_at__lt=timezone.now() - timezone.timedelta(days=days)).delete()[0]
