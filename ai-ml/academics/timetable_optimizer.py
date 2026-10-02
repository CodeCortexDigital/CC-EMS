"""Kept so older imports keep working. The generator now lives in services/education/academics/scheduler.py
(hard rules for teachers, rooms and classes; only qualified teachers; seeded; undo)."""


def optimize_timetable(academic_year_id, tenant_id=None, generations: int = 50, pop_size: int = 50,
                       commit: bool = True, seed=None) -> dict:
    from services.education.academics import scheduler
    restarts = max(1, min(int(generations) // 10, 12))
    return scheduler.run(academic_year_id, tenant_id=tenant_id, seed=seed, restarts=restarts, commit=commit)
