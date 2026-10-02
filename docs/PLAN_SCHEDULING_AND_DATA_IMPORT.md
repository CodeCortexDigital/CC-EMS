# Plan: timetable and cover rules, one data format for import / export / restore, sample school pack

Status: **built** (2026-10-02). Sections 1 and 2 are the plan and the findings it was based on, kept as written; section 7 at the end records what was built and where it differs from the plan. Every "finding" was checked in the source.

Context: a US private-school prospect asked for a pre-loaded sample US school, and the team wants every kind of school data (students, teachers, staff, fees, admissions, salary, classes) to be loadable from CSV files, with the same files usable to export and restore a school.

---

## 1. What the code does today

### 1.1 Timetable generator

Entry point: `POST /api/v1/auth/ai/generate-timetable/` ([ai_views.py:510](../backend/services/analytics/ai_views.py)), which calls the genetic algorithm in [ai-ml/academics/timetable_optimizer.py](../ai-ml/academics/timetable_optimizer.py). There is also a separate management command, `generate_full_timetable`, that wipes and rebuilds sections, entries and assignments for the demo school.

| # | Finding | Where | Effect |
|---|---|---|---|
| T1 | When a class-subject has **no** teacher assignment, the generator uses `Teacher.objects.first()` as a fallback, whatever they teach. | optimizer.py:166-170 | A maths lesson can be given to the art teacher. This breaks the "only the related-subject teacher" rule. |
| T2 | One teacher per class-subject (`matching_assigns[0]`). Other qualified teachers are never considered, so the algorithm cannot move a lesson to a free qualified teacher. | optimizer.py:163-165 | One overloaded teacher while others sit idle. |
| T3 | The algorithm only moves day, period and room. Teacher clashes, room clashes and teacher-availability misses are *penalised in the score*, not forbidden. After the loop only **section** double-bookings are dropped. | optimizer.py:13-70, 236-245 | A committed timetable can still contain a teacher in two rooms at once. |
| T4 | No limit on a teacher's periods per day or per week, no gaps/consecutive-lesson rules, no "heavy subject early" preference. | whole file | Teachers can get 8 periods in a row or 40 a week. |
| T5 | Weekdays are hard-coded Monday to Friday. The school's own weekday setup (`WeekdayConfig`, half days) is ignored. | optimizer.py:129 | Wrong for schools that work Sunday-Thursday or have a half day. |
| T6 | Rooms are chosen at random; there is no room type (lab, gym) per subject. | optimizer.py:188 | Chemistry in the gym. |
| T7 | `commit=true` deletes the school's whole timetable for the year with no undo, no snapshot. Preview exists, but the preview does not list the problems it contains. | optimizer.py:247-262 | One click can lose a hand-edited timetable. |
| T8 | Generated timetable ignores approved leave and the cover that already exists. | n/a | Acceptable (leave is handled separately) but should be stated in the UI. |

### 1.2 Teacher, class and subject assignment

- `TeacherSubjectAssignment` ([models.py:391](../backend/services/education/academics/models.py)) links teacher, class-subject and year. **Nothing checks that the teacher teaches that subject.** The create view and serializer accept any teacher for any subject (checked: no validation in `TeacherSubjectAssignmentSerializer` or its list/create view).
- What a teacher teaches is `Teacher.specializations`, a free-text JSON list (`["Physics, Maths"]`, `["maths"]`, `["Mathematics"]` all appear). Matching elsewhere is fuzzy substring matching (`_subject_matches` in [substitution.py](../backend/services/education/academics/substitution.py)). There is no link from a specialization to a real `Subject` row, and no "can teach grades 6-8" level restriction.
- A dead duplicate model file, [class_subject.py](../backend/services/education/academics/class_subject.py), defines another `ClassSubject` that is not used. It should be removed so nobody wires to it by mistake.

### 1.3 Automatic cover when a teacher goes on leave

[substitution.py](../backend/services/education/academics/substitution.py), called when leave is approved.

| # | Finding | Effect |
|---|---|---|
| L1 | `TimetableSubstitution` has **no date**. On approval it creates a substitute for *every* timetable entry the teacher has in the week, whatever the leave dates are. A one-day Tuesday leave reassigns Monday to Friday. | Wrong cover for any leave shorter than a week; the cover list is misleading. |
| L2 | Only teachers marked `teacher_type = relief` are considered. Free *regular* teachers are never used. | Matches "adjust some free teachers": not done. |
| L3 | If no relief teacher matches the subject, it falls back to **any** relief teacher. | Irrelevant-subject cover, against the rule. |
| L4 | Availability is checked against the weekly timetable and other substitutions, but not against the free teacher's own approved leave or half-day leave. | A teacher on leave can be assigned cover. |
| L5 | Periods that cannot be covered are silently skipped; nobody is told. | Uncovered lessons go unnoticed. (The new Staff & HR cover requests exist but are not fed from this.) |

What already exists and should be reused: the cover-request workflow, free-teacher search and notifications built in `services/education/hr/substitutes.py` (candidates are ranked subject match first, then relief pool).

### 1.4 Import, export and restore: three unrelated formats

| Piece | Format | Coverage |
|---|---|---|
| **Import** (`services/education/imports`, `/education/import`) | Friendly CSV/Excel with human headers (`Name`, `Class`, `Guardian phone`), matched case-insensitively, with preview, per-row errors and a downloadable problems file | **5 kinds only**: classes and sections, subjects, teachers and staff, students and guardians, opening fee balances |
| **Export** (`services/core/portability`, Settings > Security > Data) | A zip of raw table dumps: one CSV/JSON/Excel sheet per database table, internal column names, UUIDs as keys, JSON in cells, passwords/tokens removed | **159 record types**, all of the school's data |
| **Restore** (`services/core/backup`) | Encrypted platform-wide database dump, and a Postgres-level per-school restore script | Operator-only; not available to a school, cannot read the export zip or any CSV |

So: an exported zip cannot be re-imported (different headers, UUID keys, no importer for 154 of the 159 record types), and the importer's files cannot be produced by the exporter. There is no school-level restore. This is the mismatch the team noticed.

### 1.5 Demo data

- `seed_demo` ([seed_demo.py](../backend/services/core/accounts/management/commands/seed_demo.py)) builds a Pakistani-style school (Grade 1-8, 6 teachers, 120 students, Urdu-first names) directly into the database. It is not importable, not US, and cannot be shared as files.
- The repository root and `backend/` hold about 25 one-off generator scripts (`generate_data.py`, `create_students.py`, ...). Several reset shared passwords (README warns about this). They overlap and none produce CSV.
- `backend/create_sample_applicants.py` seeds admissions applicants. `students_seed.csv` (230 rows) is the only CSV sample, and only for students.
- The new Staff & HR data (contracts, reviews, pay grades, cover) has no sample data at all.

---

## 2. Target design

### 2.1 One format: the "School Data Pack"

A zip of CSV files, **the same files are what the importer reads and what the exporter writes**. Rules:

1. **Human keys, never UUIDs.** Rows refer to each other by what a person would write: class name, section, subject code, student number, employee number, invoice number. Example: `attendance.csv` has `student_number,date,status`.
2. **One file per kind, fixed names and column order**, with a header row, UTF-8 with BOM (so Excel opens it), ISO dates, plain numbers.
3. **`manifest.json`** inside the pack: pack version, school name, export date, row count per file, and a checksum per file. The importer refuses a pack from a newer version and warns on older ones.
4. **Import order is defined by dependency** (a table of "needs"), so uploading a whole pack works in one go: academic years, then classes, subjects, rooms, periods, staff, class-subjects, assignments, students, guardians, fees, ...
5. **Three modes** per import: *add only* (skip rows that already exist), *update* (overwrite matching rows by natural key), *restore* (empty school only, keeps original numbers and dates). Every mode starts with a dry run that reports what would be created, updated, skipped or rejected, row by row.
6. **Never imported from a pack:** passwords, tokens, API keys, payment-gateway secrets. People get new random logins on import (existing behaviour for students and staff).
7. Existing 5 importers keep their headers as accepted aliases, so old files still work.

### 2.2 Record kinds in the pack

Tier 1 is what the client asked for; later tiers can follow after the first release.

| Tier | File | Keyed by | Notes |
|---|---|---|---|
| 1 | `academic_years`, `terms` | year name | needed before anything dated |
| 1 | `classes`, `sections` | class name, section | exists today as one file; split on export, accept both |
| 1 | `subjects` | subject code | exists |
| 1 | `class_subjects` | class + subject code | periods per week, marks, core/elective |
| 1 | `rooms`, `periods`, `weekdays` | name / number | feed the generator |
| 1 | `staff` | employee number | exists; add manager employee number, pay grade, teacher type (regular / relief), `teaches` mapped to real subjects |
| 1 | `teacher_assignments` | employee + class + subject | **validated** (see 3.1) |
| 1 | `students`, `guardians` | student number | students exists; guardians as their own file with relationship and flags |
| 1 | `student_health`, `immunizations` | student number | US schools need these |
| 1 | `admission_applications` | application number | stage, documents are not carried |
| 1 | `fee_structure` (fee heads, plans, discounts), `invoices`, `payments`, `opening_balances` | invoice / receipt number | balances exists |
| 1 | `pay_grades`, `payroll_profiles`, `payslips` | grade name / employee + month | salary |
| 1 | `leave_balances`, `leave_requests` | employee + dates | |
| 2 | `attendance`, `staff_attendance` | student number + date | large; chunked |
| 2 | `exams`, `exam_results`, `gradebook_scores` | exam name + student number | |
| 2 | `timetable` | class + section + day + period | lets a school bring its own timetable |
| 2 | `contracts`, `credentials`, `reviews`, `goals`, `openings`, `candidates` | employee number | the new HR module |
| 3 | library, transport, cafeteria, inventory, calendar, behaviour, certificates | per module | |

### 2.3 Export = the same pack

The "Export school data" button gains a **"Re-importable pack (CSV)"** choice, built from the same specs the importer uses, so a round trip (export, empty school, import in restore mode, export again) gives identical files. The existing raw table dump stays as "Technical export (everything, for audit and for leaving the platform)", because it contains record types the pack does not cover (audit logs, AI usage, ...).

### 2.4 Restore

- **School self-service restore:** import a pack in *restore* mode into an empty (or newly signed-up) school. Admin only, preview first, all-or-nothing per file inside a transaction, a result report that can be downloaded.
- **Operator restore:** unchanged (database-level), documented in `docs/DISASTER_RECOVERY_PLAN.md`.
- Partial restore (for example "only fee invoices") is just uploading that one file in *update* mode.

### 2.5 Assignment and scheduling rules (target behaviour)

**Eligibility** is one function used everywhere: `eligible_teachers(class_subject)`.
A teacher is eligible when all hold: active; has the subject among their *real* subjects (a many-to-many `Teacher.subjects` replaces the free text; the old text is migrated by matching names, anything unmatched is listed for an admin to fix, never guessed); and, if the school sets grade bands on the teacher (for example 6-8), the class's grade level is inside the band.

1. **Assigning a teacher to a class/subject** (UI, API and import) is refused unless eligible, with a message naming what is missing. An admin can override with a typed reason, which is recorded.
2. **Generator** only ever picks from the eligible list; with no eligible teacher it **stops that lesson and reports it** ("Grade 6 Chemistry has no qualified teacher"), instead of using `Teacher.objects.first()`.
3. **Hard constraints** (never broken in the result): teacher, room and section free in that period; teacher's availability and leave; room type matches the subject; school's own weekdays and periods. **Soft goals** (scored): even spread across the week, maximum periods per day and per week per teacher, no more than N consecutive, balanced load between eligible teachers, subject spread (not the same subject twice a day), heavy subjects earlier.
4. **Algorithm change:** keep the genetic algorithm's search but add a repair step and teacher choice as part of the search (so it can move a lesson to another eligible free teacher), or replace it with a constraint solver (OR-Tools CP-SAT is the standard tool; it makes hard constraints real). Recommendation: prototype CP-SAT on the demo school first; keep the GA as a fallback if the dependency is a problem on the host.
5. **Preview before commit**, listing unscheduled lessons, conflicts, teacher workloads and room use; **commit makes a snapshot** and a one-click **undo** (restore previous timetable) for 30 days.
6. **Leave auto-adjust, date-aware:** a new per-date table (`CoverAssignment`: leave, entry, date, substitute). On approval, for every date in the leave that is a working day, for every period the teacher has that weekday: choose the best eligible free teacher in this order: (a) teaches the subject and has a free period, (b) relief pool, subject match, (c) teaches the subject but over their load cap (flag), then **never** an unrelated teacher. Anything not covered becomes an **open cover request** (the Staff & HR workflow) and notifies HR, so nothing is silent. Cancelling or shortening leave removes the future assignments only. Fairness: prefer the teacher with the fewest cover periods this term.
7. The existing `TimetableSubstitution` rows are migrated into dated assignments, then retired.

### 2.6 Sample data

- **A US sample school, shipped as a School Data Pack** (CSV files in `sample-data/us-school/`, plus a README and a zip), loaded through the importer. That doubles as the most realistic importer test. Proposed contents: K-8 or K-12 (decision below), school year 2026-27 with semesters, ~14 classes with sections, ~20 subjects, ~25 teachers and staff (with real subject mappings, two relief teachers, managers, pay grades), ~250 students with guardians (US names, addresses, phone formats), health and immunisation records, ~30 admissions applicants across stages, a fee structure with invoices and payments (USD), payroll profiles and one month of payslips, leave balances and a few leave requests, attendance for 30 days, two exams with results, the timetable, HR records (contracts, credentials with some expiring, reviews, goals, two job openings).
- A generator script (`scripts/build_sample_pack.py`) with a fixed random seed makes the pack reproducibly, and a test loads it into an empty school and checks counts and relationships.
- `seed_demo` becomes "load a pack": `seed_demo --pack us-school` (default for the demo) or `--pack pk-school` (the current school, exported once to the same format). The 25 loose scripts are deleted after the pack covers their cases.
- Sample logins and the README walkthrough are updated for the US school.

---

## 3. Work breakdown

Estimates are working days for one developer including tests; they are approximate.

| Phase | Deliverable | Days |
|---|---|---|
| 0 | Decisions (section 5), freeze the pack spec (file names, columns, keys) as `docs/DATA_PACK_SPEC.md` | 1 |
| 1 | **Eligibility and assignment rules.** `Teacher.subjects` (+ optional grade band), data migration from the free text with an "unmatched" report, `eligible_teachers()`, validation in API/UI/import, override-with-reason, remove dead `class_subject.py`, teacher form uses a subject picker | 4 |
| 2 | **Generator.** Prototype CP-SAT vs improved GA on the demo school; hard/soft constraints, `WeekdayConfig`, room types, workload caps, unschedulable-lesson report, preview with conflicts/workloads, snapshot and undo, tests (no clashes, no ineligible teacher, deterministic with a seed) | 8 |
| 3 | **Date-aware cover.** `CoverAssignment` model, new assigner (order in 2.5), open cover request for anything uncovered, notify HR and the substitute, handle edit/shorten/cancel of leave, migrate old substitutions, update leave pages and timetable view, tests incl. one-day leave, half-day leave, no eligible teacher | 5 |
| 4 | **Pack engine.** Generalise `imports/specs.py` into a registry of kinds (columns, keys, dependencies, check, create, update, export-rows); pack upload (zip or single CSV), dependency ordering, three modes, dry-run report, problems file, manifest and checksums; Excel and CSV; size and row limits; background job for large files with progress | 8 |
| 5 | **Tier 1 kinds**, each with template, importer, exporter and round-trip test: academic years/terms, classes/sections, subjects, class-subjects, rooms/periods/weekdays, staff (extended), teacher assignments (validated), students, guardians, health, admissions, fee structure/invoices/payments/balances, pay grades/payroll/payslips, leave balances/requests | 14 |
| 6 | **Export and restore.** "Re-importable pack" export from the same specs; restore mode into an empty school with report; import/export/restore screen redesign (one page: *Download templates*, *Upload*, *Export*, *Restore*); round-trip test over the whole sample pack | 5 |
| 7 | **Sample US school pack** and generator, loader test, `seed_demo --pack`, delete legacy scripts, README and walkthrough update | 5 |
| 8 | **Tier 2 kinds** (attendance, exams/results/gradebook, timetable, HR records) | 8 |
| 9 | Hardening: performance on 5,000-student file, permission and tenant-isolation tests for every importer, audit log entries for imports and restores, docs for schools (how to prepare files) | 3 |
| | **Total** | **~61** |

Suggested order for the client demo: Phase 7's pack of the Tier-1 kinds first would be the fastest way to *show* a loaded US school, but it needs Phases 4-5. A faster interim (about 5 days) is to build the US school directly with a seed script now and convert it into a pack when Phase 4 lands. Phases 1-3 are independent of the data work and can run in parallel with Phases 4-5 if there is a second developer.

Release slices that each stand on their own:
1. **Rules** (Phases 1, 3): no wrong-subject teachers anywhere, cover that matches the leave dates. Smallest change that removes the correctness bugs.
2. **Data in and out** (Phases 4-7): the pack, restore, and the US sample school.
3. **Smarter timetable** (Phase 2): can ship after 1 because it relies on the eligibility function.
4. **Tier 2** (Phase 8).

---

## 4. Testing strategy

- **Round trip:** export pack, wipe, restore, export again; every file byte-identical (after sorting). Run on the US sample pack and on the existing demo school.
- **Per importer:** good rows, every error type (missing key, unknown class, duplicate, wrong date), update mode, add-only mode, restore mode, rerun is a no-op.
- **Isolation:** a pack from school A imported into school B creates nothing in A; every importer endpoint is added to `test_tenant_isolation.py`.
- **Scheduling properties** (generated random schools, fixed seeds): no teacher/room/section double booking, no ineligible teacher, no teacher over their caps, unschedulable lessons reported, snapshot/undo restores exactly.
- **Cover:** one-day, multi-day, half-day, weekend inside leave, holiday inside leave, only teacher for a subject on leave (open request created), substitute on leave themselves, leave shortened or cancelled.
- **Performance:** 5,000 students and 200,000 attendance rows import within the time limit and without exhausting memory (streamed, batched).

## 5. Decisions needed before building

1. **School level for the US sample:** K-8, K-12 or high school only? (Changes the subjects, the credit/GPA data and the number of staff.)
2. **Timetable engine:** are you comfortable adding OR-Tools (a compiled dependency) to the backend, or must it stay pure Python? (Decides CP-SAT vs improved genetic algorithm.)
3. **Grade bands on teachers:** needed (for example "licensed for grades 6-8 only"), or is subject enough?
4. **Cover when nobody qualified is free:** open a request for HR (recommended), or allow an unqualified free teacher as "supervision only" with a flag?
5. **Restore scope:** may a school admin restore into a school that already has data (update mode), or only into an empty school? (Update mode is more useful and riskier.)
6. **Pack versions of existing demo:** keep the Pakistani demo school as a second pack, or retire it?
7. **Money and dates in files:** one format for all schools (ISO dates, plain decimals) is proposed; locale-specific formats would be accepted on import only.

## 6. Risks

- **Existing data with free-text specializations** will not all map to subjects; the migration reports instead of guessing, and an admin has to resolve the list before strict validation is switched on (it is switched on per school, off by default for existing schools).
- **Solver time** on very large schools: set a time limit and return the best feasible timetable plus a report.
- **Importing fee and payment history** can create duplicate money if run twice; invoices and payments are keyed by invoice and receipt number, and a rerun is a no-op.
- **Scope:** the pack covers many kinds; Tier 1 is deliberately limited to what the client named, and each kind ships only with its round-trip test.


---

## 7. What was built (2026-10-02), and where it differs from the plan

| Phase | Built | Notes |
|---|---|---|
| 1 Eligibility and assignment rules | `Teacher.subjects`, `eligibility.py`, `SchedulingPolicy`, validation on teacher assignments and timetable slots (admin override with a reason), Subject picker on the staff forms, **Timetable > Teaching Rules** coverage page, dead `class_subject.py` removed | Subject only (no grade bands). The migration fills each teacher's list from their free-text specializations where a word matches a subject exactly (job titles never match); the rest are listed on the Teaching Rules page. |
| 2 Generator | `scheduler.py`: hard rules by construction, workload limits, school weekdays and half days, lab/gym rooms, unplaced-lesson report, workloads, seeded and repeatable, snapshot and undo (30 days), UI preview with problems | **Pure Python** (constructive placement with ejection chains and random restarts), not OR-Tools: no new dependency, and the hard rules hold by construction. `academics/timetable_optimizer.py` is now a thin wrapper. |
| 3 Date-aware cover | Cover is a dated `SubstituteRequest` linked to the leave; qualified free teachers only; relief teachers first, then fair share; over-limit teachers skipped unless the school allows; open request plus a notice to the administrators when nobody qualified is free; moving or cancelling leave removes future cover; `refresh_cover` command; old week-long substitutions migrated | The order is relief pool first (cover is their job), then regular teachers by least recent cover, rather than regular first. |
| 4-6 Pack engine, Tier 1 kinds, export and restore | `imports/engine.py`, `pack.py`, `kinds_*.py`, `pack_api.py`; 36 kinds; modes add / update / restore; preview of a whole pack in one rolled-back transaction; zip with manifest and checksums; re-importable export; one Import/Export/Restore screen | Restore = update into a school with no students or staff. The pack export is a separate button from the technical export (Settings > Security > Data), which stays for records the pack does not cover. |
| 7 Sample school | `sample-data/us-school/` (K-8, 214 students, 24 staff, timetable made by the real generator), `build_sample_pack`, `load_pack`, `seed_demo --pack us-school`, 24 loose generator scripts deleted | Decision 1 answered as K-8. The old demo school (`seed_demo` without `--pack`) is kept as is; it was not converted to a pack. |
| 8 Tier 2 | attendance, staff attendance, exams, results, timetable, calendar events, contracts, credentials, reviews, goals, job openings and candidates | Gradebook scores, library, transport, cafeteria, inventory, behaviour and certificates are not in the pack yet. |
| 9 Hardening | Background jobs with progress for packs over 400 rows (`ImportJob`; runs in a thread, or inline with `IMPORT_JOBS_INLINE`), no notifications while loading, `docs/DATA_PACK_SPEC.md` generated from the code | A 5,000-student file takes about four minutes, because each student creates family records (25 queries each); attendance loads at about 1,000 rows a second. |

Tests: `test_scheduling_rules.py`, `test_scheduler.py`, `test_leave_cover.py`, `test_data_pack.py` (including an export, wipe, restore, export round trip that compares every file), `test_sample_pack.py` (the committed sample files load with no problems, are current with their generator, and the demo logins are wired).
