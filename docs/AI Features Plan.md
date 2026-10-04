# AI features for US schools: what exists, what is missing, how to build it

Checked against the code on 4 Oct 2026 by reading it, not by running each feature. The percentages in the source article
were not checked here; verify them before using them in sales material.

**Status labels:** **Built** = works end to end in the app. **Partial** = some of it exists. **Not built** = nothing found.

## 1. What already exists (the AI layer is real)

* **Providers and safety:** OpenAI or Anthropic through `AI_PROVIDER` and keys in the environment (`backend/services/ai/`), per-feature switches, per-user rate limits, token budgets, usage records, and `redact_for_llm` (personal data is stripped before text goes to the model).
* **No keys = still works:** every feature has a template or keyword fallback and the screen says it is not AI-written.
* **Role-aware assistant** with tools over school data (students, fees, attendance, exams, homework).
* **ML models** for dropout and fee-default risk, trained per school (`ai-ml/`, `analytics/`).
* **Scheduler:** Celery Beat exists (`erp_core/celery.py`).

## 2. Feature by feature

### 2.1 Attendance alerts and early warning

| Item | Status | Where / what is missing |
|---|---|---|
| Automatic absence, late and frequent-absence texts to parents (SMS, WhatsApp) | **Built** | `education/communication/texts.py`, school-editable wording, delivery status from Twilio. Needs the school's Twilio account. |
| Escalation after 3, 5, 10 absences | **Partial** | Only one "frequent absence" step (default 3 unexcused in 30 days, not repeated within the window) in `attendance/register.py`. No ladder, no staff notification per step. |
| Predictive at-risk flags | **Built, with limits** | `analytics/ai_views.py` risk scan, `StudentRisk`, `attendance/detect_patterns`. Needs the ML packages and enough history. The nightly task `nightly_risk_scan` **is** in the Beat schedule (`ai-risk-scan-nightly`), but the demo has no Celery worker, so there it only runs from the "Run AI Risk Scan" button. |
| Intervention queue for counselors | **Partial** | `notify_dropout_risk` creates a `Recommendation` and notifies teachers and admins. No owner, due date, status flow or counselor screen. The new safety follow-up (owner, due date, overdue) is the pattern to copy. |

### 2.2 Teacher assistant

| Item | Status | Where / what is missing |
|---|---|---|
| Lesson plan generator | **Built, needs US work** | `ai/generation.py` and `LessonPlannerPage`. The system prompt says "teacher in Pakistan". No standards input (the Gradebook already has Standards). |
| Parent communication drafter | **Not built** | Nothing drafts a parent email from a template such as "behavior concern" or "positive note". |
| Rubric generator | **Not built** | Nothing found. |
| Bonus, already built | **Built** | Quiz generator, report-card comments, homework hints, admission screening, behaviour pattern explanation. |

### 2.3 Administrator analytics

| Item | Status | Where / what is missing |
|---|---|---|
| Dashboards (overview, enrolment, attendance, finance, academics, teachers) | **Built** | `education/insights`, Reports pages. |
| Predictive enrolment forecast | **Not built** | Only a moving-average revenue forecast in finance (feature-gated). |
| Performance trends with decline flags | **Partial** | Academics insights exist; no automatic decline flags, no teacher or demographic cuts. |
| AI narrative summary ("Enrollment is up 5% in Grade 3...") | **Not built** | |
| Educator analytics | **Partial** | A teachers insights page exists. No retention or development signals. |

### 2.4 Family communication and translation

| Item | Status | Where / what is missing |
|---|---|---|
| Translate a message or announcement | **Built (on request)** | Translate button, uses the guardian's `preferred_language` (`communication/inbox.py`). |
| Automatic translation when sent; report cards and newsletters | **Not built** | Parents must press translate; nothing is translated on send. |
| Summarise a long message | **Built** | Conversations and announcements. No suggested reply. |
| Sentiment or urgency detection | **Not built** | |

## 3. How to build the missing parts

Order: X (foundations) first, then A, C, B, D. Estimates are working days for one developer using Claude Code; without
AI help multiply by about 1.7. These are smaller than the article's weeks because the base exists.

### X. Foundations (3-4 days, do first)
1. **Make prompts region-aware.** Replace "Pakistan" in the system prompts with the school's country and standards (US: Common Core or the state's standards, American spelling), from the school locale.
2. **AI settings screen for administrators.** Which features are on (flags exist), usage this month (`AIUsage` exists), and a one-time **AI use notice** the school accepts (the privacy module's consent types can hold it). Student-level text is redacted by default.
3. **Scheduling.** Add `nightly_risk_scan` and the daily jobs (`admissions_daily`, `send_immunization_reminders`, `send_hr_alerts`, `refresh_cover`) to the Beat schedule, and run a Celery worker in production.
4. **Rules for all AI output:** it is a draft, a person sends or accepts it, and AI never writes final grades or evaluations. Label AI text as AI-generated.
5. **Quality gate.** For each feature keep about 20 sample inputs and check the outputs before release.

### A. Absence escalation and the counselor queue (8-12 days)
* **A1 Escalation ladder.** School-level steps (default 3, 5, 10 unexcused absences in a chosen window), each with channels, wording, and which staff are told. Runs where the single "frequent absence" check runs today, once per student per step per period, and ignores excused absences.
* **A2 Interventions.** A model with student, source (absence, risk scan, behaviour, manual), owner, due date, status, suggested actions. Created automatically from step 2 and above and from high or critical risk. A **counselor screen** with filters, assign, complete and overdue flags. Copy the safety follow-up design.
* **A3 Chronic absenteeism rate.** Show the share of students missing 10% or more of enrolled days (the usual US definition) in Reports, with the threshold set by the school.
* **Done when:** each step fires once and not again; excused absences never count; a counselor sees only their school's queue; history loads send nothing; tests cover all of these.

### C. Translation for families (7-10 days)
* **C1 Translate on send.** For each recipient's `preferred_language`, store a translation per (message, language), show it with "show original", and cache it. Absence and fee texts use a once-translated template per language.
* **C2 Report cards and newsletters.** Translate on view in the parent portal, cached, labelled "machine translated".
* **C3 Suggested reply and urgency.** Extend the summary with a suggested reply. Classify each parent message as neutral, frustrated or urgent using a small fast model, with a keyword fallback; show a badge and sort by it. Store only the label.
* **Done when:** a Spanish-speaking parent receives Spanish and can see the original; the cache stops repeat charges; no keys means a clear "not available" message.

### B. Teacher assistant additions (6-9 days)
* **B1 Lesson plans:** optional standards (pick from Gradebook Standards or type), a standards-alignment section in the result.
* **B2 Parent message drafter.** `POST /ai/parent-message/` with the student, a template (behavior concern, positive note, missed assignments, attendance concern, custom), details and tone; returns a subject and body for the teacher to edit and send through the existing messaging. Excludes health and discipline details by default; a template fallback works without keys.
* **B3 Rubric generator.** `POST /ai/rubric/` with assignment text, grade, subject, standards and levels; returns a rubric table, saved on the assignment and shown when grading.
* **Done when:** teachers only, within quota, no personal data in prompts, drafts are never sent automatically.

### D. Administrator analytics (15-20 days, the largest)
* **D1 Enrolment forecast.** A transparent model, not a black box: next year's grade N = this year's grade N-1 times the retention rate (from history and re-enrolment answers) plus expected new students (approved applications and the usual conversion of applications), with a range. Compare with seats (`WaitlistConfig`) and suggest sections needed. Birth-rate and housing data come later, only if a district asks.
* **D2 Narrative summaries.** The language model turns already-computed numbers into 3-5 sentences, shown with the numbers beside it; a template fallback; cached daily; administrators only; labelled AI-generated.
* **D3 Performance trends.** Filters by grade, subject and teacher, term-over-term change, and decline flags. Show demographic cuts only if the school records them, and hide groups smaller than 10 students.
* **D4 Educator signals.** An "attention" list from HR data (contract end, credential expiry, leave patterns, development hours once built). Presented as workload and retention signals, not as a rating of teachers.

## 4. What to avoid (matches the article)
* Student-facing AI tutors without teacher oversight.
* AI that writes or decides grades.
* Sending any student's personal details to a model without redaction and the school's notice.
* Running risk scans without checking the model's accuracy on the school's own data first.

## 5. Totals
Foundations 3-4, A 8-12, C 7-10, B 6-9, D 15-20: about **40-55 working days** with Claude Code for one developer
(roughly 8-11 weeks), or about 5-6 weeks with two developers working on A and C, then B and D.


## Build status (4 Oct 2026)

* **X1 region-aware prompts, X2 AI settings screen with notice, X3 scheduled daily jobs (admissions, immunization reminders, HR alerts, cover refresh): done and tested.**
* **A absence ladder, interventions queue, chronic absenteeism: done and tested** (backend and frontend).
* **C family messages: partly done and tested.** Translations are now kept (one AI call per text per language, "show original" toggle, labelled machine translated). Incoming messages get a normal / upset / urgent label by a keyword check (not an AI call, so nothing is sent to a provider; staff only see it, and it sorts the inbox). Staff get a suggested reply on conversation summaries, never sent for them. **Not done yet:** translating absence and fee texts and report cards per family language (C1 templates, C2).
* **B teacher assistant: done and tested.** Lesson plans take optional standards (typed one per line) and return an alignment section; a "Draft with AI" panel in New message drafts a family message (first name only, health and discipline words trigger a warning, needs the AI notice accepted, a plain template when no provider is set up); assignments can carry a rubric (AI draft or typed), shown from the gradebook header and never changing a score. Not done: picking standards from the Gradebook Standards list (typed for now).
* **D admin analytics: done and tested.** Planning tab under Reports: enrolment forecast (transparent arithmetic, range, seats, sections, assumptions shown and flagged when assumed), score trends by subject or class with decline flags (groups under 10 students hidden), written summaries of the figures (cached daily, figures sent only, template fallback), and staff workload signals under HR (not a rating; no leave reasons shown). Not done: filtering trends by teacher (left out on purpose to avoid rating individuals), demographic cuts, birth-rate data, and a link to staff signals for the HR role from the web app.
* **Remaining overall:** C's translated absence and fee texts and report cards; quality gate with a golden set (X5); standards picker for lesson plans.
