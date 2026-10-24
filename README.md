# CC-EMS — Code Cortex Education Management System

A full-stack, multi-tenant school/ERP management platform with a **React + TypeScript (Vite/Tailwind)** frontend and a **Django REST (Python)** backend featuring role-based portals, real-time WebSockets, finance & payroll, and AI/ML-powered analytics.

## Features

- **Role-based portals** — Admin, Teacher/Employee, Student, and Parent dashboards with RBAC-scoped navigation and route guards.
- **Academics** — classes, sections, subjects, curriculum (syllabus → topic → sub-topic), homework, class tests. **Timetable** with a generator that follows teaching rules (only qualified teachers, no clashes, workload limits) with preview and undo. See [Timetable and teaching rules](#timetable-and-teaching-rules).
- **Students & Teachers** — full lifecycle management: admission, profiles, history timelines, promotions, ID cards, letters, login management.
- **Admissions & student health** — public application form, review pipeline with history, one-click enrolment, re-enrolment campaigns; per-student health record (allergies, medications, physician, insurance) and immunisation log.
- **Staff & HR** — cover (substitute) requests, leave with US leave types, half days, two-step approval and a "who is out" calendar, recruitment and onboarding, contracts and credential expiry alerts, performance reviews and goals, pay grades with tax and benefits, directory and org chart. See [Staff & HR](#staff--hr).
- **Exams & Results** — exam hub, marks entry, result cards, mark-sheets, grade scales, report cards, admit cards.
- **Attendance** — student & staff attendance with bulk entry, reports, and facial-recognition embeddings.
- **Finance & Payroll** — fee structure, invoices, installments, discounts, late fees, online card payments (Stripe; the JazzCash and Easypaisa wallets are offered only to schools set to the Pakistan region), salary generation and slips. Fee receipts and invoice PDFs belong to one family; the school-wide finance PDFs are for finance staff.
- **Communication** — in-app chat, SMS/WhatsApp broadcast (Meta Graph API), notifications, announcements; translate a message on demand (kept so each text is translated once per language), summaries with a suggested reply for staff, and an urgency label on incoming messages (staff only).
- **Student support** — a configurable absence ladder (default 3, 5 and 10 unexcused absences) that warns families and can open **interventions**: a counsellor's to-do list with owners, notes and due dates. Chronic-absenteeism reporting. See [Daily briefs, student support and planning](#daily-briefs-student-support-and-planning).
- **Daily briefs** — an administrator's morning brief and evening summary: counts only, drafted then approved, kept for about three months, with weekly, fortnightly and monthly roll-ups.
- **Analytics & AI** — executive dashboard with real-time KPIs, an AI assistant that answers questions from live school data (streaming, chat history, English/Urdu voice), AI drafts for teachers (lesson plans with standards, family messages, rubrics, quizzes, report comments), planning reports (enrolment forecast, score trends, staff signals) and ML risk scoring / anomaly detection. Everything the AI writes is a draft. See [AI Features](#ai-features).
- **Real-time** — WebSocket KPI/attendance/notification broadcasts.
- **Multi-tenancy** — tenant resolution via header/subdomain/session with per-tenant data scoping.

- **Data in and out** — one set of CSV files (a *data pack*) loads, updates, exports and restores a whole school: students, staff, classes, admissions, fees, salary, attendance, exams, timetable and more. See [Data pack](#data-pack-import-export-and-restore).

See [docs/README.md](docs/README.md) for the full feature breakdown.

## Tech Stack

| Layer      | Technologies |
|------------|--------------|
| Frontend   | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, React Router v6, Recharts, Framer Motion, Sonner |
| Backend    | Django 5, Django REST Framework, SimpleJWT, PostgreSQL, Celery, Redis, Django Channels, drf-spectacular, ReportLab |
| AI/ML      | OpenAI or Anthropic Claude via a provider-agnostic client (`backend/services/ai/llm/`); optional ML pipeline (`ai-ml/`) — Random Forest predictor, Isolation-Forest anomaly detection, facial embeddings |
| Infra      | Docker, GitHub Actions CI/CD, S3/R2 object storage, Sentry, Prometheus |

## Repository Structure

```
├── backend/                 # Django REST API
│   ├── api/                 # Versioned API endpoints (/api/v1, /api/v2)
│   ├── erp_core/            # Core project (settings, URLs, ASGI, consumers)
│   ├── services/            # Domain apps: accounts, education, finance, analytics, ai, pdf, core
│   └── tests/
├── frontend/                # React + Vite SPA
│   └── src/
│       ├── components/      # Shared UI + dashboard widgets
│       ├── pages/           # Feature pages grouped by module/role
│       ├── services/        # API clients
│       └── store/           # Zustand stores
├── ai-ml/                   # ML training, infra verification & data audit
├── docs/                    # Feature documentation
├── scripts/                 # Backup/restore & ops scripts
└── .github/workflows/       # CI/CD, security & backup pipelines
```

## Run the demo locally (no API keys needed)

On Windows, double-click **`demo.bat`** in the project root (or run it from a terminal). It:

1. Creates the Python environment and installs packages (first run only).
2. Sets up a local SQLite database and fills it with the sample US school, **Maple Grove Academy** (first run only, about a minute plus setup; later runs start in seconds): K-8, 214 students, 24 staff, timetable, fees, attendance, exams, HR and one saved lesson plan. It is loaded through the same importer a school would use.
3. Starts the backend on **http://localhost:8009** and the frontend on **http://localhost:5179** in two windows, then opens the login page.

**The demo school.** `python manage.py seed_demo` loads *Maple Grove Academy* from `sample-data/us-school/` (it is the only demo school; the old built-in Pakistani-style school is gone). The four demo logins below are wired to it (`teacher@code.com` is a maths teacher, `student@code.com` a Grade 8 student, `parent@code.com` a parent of two). `demo.bat` loads it on a first run; if you have an older demo database, run **`load-us-school.bat`** (it migrates, loads Maple Grove and makes the demo logins open it), then `restart-demo.bat`. The files are in [sample-data/us-school/](sample-data/us-school/); upload `us-school-pack.zip` in the app to load them into any school.

To stop, run **`stop-demo.bat`** (or close the two server windows); **`restart-demo.bat`** stops and starts again. Both only touch the demo ports 8009 and 5179. On this machine there are desktop shortcuts: *ERP Demo - Start / Stop / Restart*. To rebuild the demo data from scratch: `cd backend` then `.venv\Scripts\python manage.py seed_demo --reset`.

**Demo logins**

| Role | Email | Password | What they see |
|------|-------|----------|---------------|
| Admin | `admin@code.com` | `Admin@123` | Whole school: dashboard, fees, attendance, analytics |
| Teacher | `teacher@code.com` | `Teacher@123` | A maths teacher (Grade 6): classes, timetable, cover, drafts with AI |
| Parent | `parent@code.com` | `Parent@123` | A parent of two children: their attendance, fees, forms, health records |
| Student | `student@code.com` | `Student@123` | A Grade 8 student: own timetable, homework, results |

**Suggested walkthrough (about 10 minutes)**

1. **Admin → Dashboard:** live totals (students, staff, fee collection, today's attendance).
2. **Admin → AI assistant** (purple button, bottom right): ask *"Fee defaulters & finance summary"*, then *"How many students are absent today?"*.
3. **Admin → Reports (Analytics):** click **Run AI Risk Scan**. The ML models score every student for dropout and fee-default risk; the at-risk list and charts update.
4. **Teacher → Lesson Planner:** a saved sample plan is already there. Add one: pick a class and subject, enter a topic (and, optionally, standards to address), generate a draft. **Messages → New message → Draft with AI** writes a message to a family for you to edit.
5. **Parent → Dashboard:** the child's attendance and fee history; ask the assistant *"My fees & dues"*. It only ever shows this family's data.
6. **Student → assistant:** *"My attendance"*. Then ask *"finance summary"*: students can't see school-wide data.
7. **Admin → Daily Briefs:** press **Prepare it now** on the morning brief, read the draft, edit if you like and **Approve**; try **Headlines** and **Mark as read**. **Reports → Planning** shows next year's enrolment forecast and score trends.
8. **Admin → Interventions:** students who need support, opened by the absence ladder or by staff.
9. **Any role → moon icon (top right):** switch to dark mode. **Settings → Theme** changes the accent colour, header and sidebar style, fonts and corner roundness for the whole app. The default look is light: a white header, a light sidebar, white cards and the Inter font. The dark sidebar and coloured header are still there as options.

**Portal logins for students, parents and staff.** Adding a student or employee creates their portal account on the server with its own random password (for example `kqmz-4827`). Usernames are the IDs people already have:

| Who | Username | Where the login is printed |
|-----|----------|----------------------------|
| Student | Student ID (e.g. `DS-2026061`) | Admission letter |
| Parent | The parent email on the admission letter | Admission letter |
| Staff | Employee ID (e.g. `EMP-001`) | Job offer letter |

Admins see the logins under **Students → Portal Logins** and **Employees → Portal Logins**, where they can issue a new password (the old one stops working) or open the letter to print. Once someone changes their own password, the letter shows "Changed by user" instead. Accounts created before this existed show a **Generate missing logins** button.

**Without API keys** the assistant runs in *quick-answer mode* (keyword matching over the same live data and role rules), and the drafting features (lesson plans, family messages, rubrics, brief summaries) give a standard template and say so. Add `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to the backend environment to switch to full AI; the assistant then also shows natural-language example questions. No other change is needed. Face-recognition attendance needs DeepFace/OpenCV, so its scan button is hidden automatically on a server without them (as on the hosted demo).

> Ports 8009 and 5179 are used so the demo doesn't clash with other local dev servers on 8000/5173.

**Theming (for developers).** One accent colour drives the header, active navigation, primary buttons, page titles and focus rings. `frontend/src/utils/theme.ts` reads Settings → Theme and sets the `--app-accent-*` CSS variables; use the `bg-brand`, `bg-brand-soft` and `text-brand` classes for new UI rather than a fixed colour. Dark mode sets `html.dark`, and `src/styles/dark-theme.css` remaps the common light utilities (`bg-white`, `text-slate-800`, `bg-emerald-50`, and so on), so existing pages work in dark mode without `dark:` variants. That file is generated: edit `frontend/scripts/gen-dark-theme.cjs` and run `node scripts/gen-dark-theme.cjs`.

**Look and feel.** The defaults are a light sidebar, a white header and Inter (`DEFAULT_THEME` in `frontend/src/utils/theme.ts`; people who saved their own theme keep it). `frontend/src/styles/modern.css` is loaded last and sets the shared look: sentence-case labels, quiet table headings, underline tabs, solid accent buttons, neutral headings and a 12px floor for small print. Shared building blocks follow it: `StatCard` (white card with an accent icon chip, no gradients), `ModuleTabsLayout` (the section name and its underline tabs on one slim row; tabs that do not fit go under a "More" menu, built by `components/common/OverflowTabs.tsx`, which `kit.tsx` Tabs also uses) and `components/common/kit.tsx` (buttons, cards, tabs, pills and page heads use the accent colour). Page code should use these rather than fixed colours, so a page restyles when the theme does.

## Timetable and teaching rules

**Who may teach what.** Each teacher has a list of subjects they are qualified for (Staff > edit > *Subjects they teach*). **Timetable > Teaching Rules** shows what is missing (teachers with no subjects, subjects nobody can teach, subjects with only one teacher) and sets the limits: periods per day, per week and in a row. With the rule on (default), assigning a teacher to a subject they are not qualified for, or putting them in a timetable slot for it, is refused; an administrator can override an assignment with a reason (recorded).

**Timetable generator** (`backend/services/education/academics/scheduler.py`, used by Timetable > Create Timetable > *Run AI Timetable Optimizer*). It builds a week for every section: a lesson is only placed when the class, a *qualified* teacher and a suitable room (labs, gym) are free, the teacher is available and within their limits, and the school's own weekdays and half days are used. Lessons that cannot be placed are listed with the reason ("nobody qualified", "every qualified teacher is at the weekly limit"), never forced. The preview shows workloads; applying it keeps the old timetable so **Restore this** undoes it (30 days). The same seed gives the same week, so what you previewed is what is saved.

**Cover when a teacher is away.** When leave is approved, each lesson the teacher has on each working day of the leave becomes a dated cover request. It is given to a free colleague qualified for the subject: relief teachers first, then whoever has covered least lately, never someone over their limits. If nobody qualified is free, the period stays an open cover request and the administrators are told; HR can assign someone not qualified only with a reason. `python manage.py refresh_cover --days 14` (run daily) fills open periods as people become free. Cancelling or moving leave removes future cover only.

## Data pack: import, export and restore

**Settings > Import data** (`/education/import`). A *data pack* is a zip of CSV files, one per kind of record (36 kinds: school years, classes, subjects, rooms, periods, staff, teacher assignments, students, guardians, health, immunisations, admissions, fee structure, invoices, payments, opening balances, pay grades, payroll, payslips, leave, attendance, exams and results, timetable, calendar, contracts, credentials, reviews, goals, job openings and candidates).

* **Load:** upload a zip (or one CSV and say what it holds). Every row is checked first and nothing is saved until you press Import. Modes: *Add only*, *Add and update* (empty cells never erase data) and *Restore* (empty school). Big packs run in the background with progress.
* **Export:** Download > *Download data pack* gives the school's data in exactly the layout the importer reads, so an exported pack can be edited and loaded again, or used to restore the school (a test exports, wipes, restores and exports again and compares every file). For a complete technical copy (audit logs, uploaded files) use Settings > Security > Data.
* **Templates:** a blank pack with headings and an example row per file, plus a README with the order to fill them in.
* **Format:** [docs/DATA_PACK_SPEC.md](docs/DATA_PACK_SPEC.md) lists every file and column (generated from the code). Records refer to each other by class name, subject code, student number, employee number, invoice number: never ids.
* **Command line:** `python manage.py load_pack <folder or zip> --school "Name" [--mode update|add|restore]`; `python manage.py build_sample_pack` rebuilds the sample school; `python manage.py pack_spec_doc` rewrites the spec.
* **Loading does not notify families:** invoices, attendance and exam results loaded this way send no emails or alerts.
* **Code:** `backend/services/education/imports/` (`engine.py`, `pack.py` builder, `kinds_*.py` one file per area, `pack_api.py`).

## Staff & HR

Open **Staff & HR** in the sidebar (teachers see **Cover & My HR**). Administrators, HR and managers see everything; every staff member sees cover requests, who is out, the directory and their own HR page.

| Area | What it does | Who |
|------|--------------|-----|
| **Cover requests** | A teacher (or the office) asks for a period, or a whole day, to be covered. Free colleagues are notified, best subject match first. A colleague accepts, or HR assigns from a list of people who are free. Covers can be given back or cancelled. | Everyone; assigning is HR |
| **Leave** | Timetable > My Leave / Staff Leave. Sick, casual, annual, personal, bereavement, jury duty, professional development, maternity, emergency, unpaid. Half days. Weekends and school holidays are not counted. Approved leave auto-arranges relief cover. | Everyone applies; managers decide |
| **Leave policy** | Timetable > Leave Limits: skip weekends/holidays, two-step approval (manager or HR recommends, an administrator approves), year-end carry-over of annual leave. | Administrators |
| **Who is out** | Month calendar of approved leave (pending requests are shown to reviewers only). | Everyone |
| **Recruitment** | Job openings, candidate pipeline (applied, screening, interview, offer, hired) with history. *Hire* creates the staff record and login and a 9-step onboarding checklist. | HR |
| **Contracts & credentials** | Contracts, probation dates, licences and certificates. Anything ending within 60 days is flagged; `python manage.py send_hr_alerts --days 30` notifies administrators (schedule it daily). | HR; staff see their own |
| **Performance** | Reviews and classroom observations stay private until shared; staff acknowledge them and update their own goals. | HR; staff see their own |
| **Pay setup** | Pay grades, flat tax withholding and benefits per person. Salary > Generate starts each payslip from these. | Administrators and HR only |
| **Directory & org chart** | Who works here and who reports to whom (reporting loops are refused). | Everyone sees; HR edits |

API: `/api/v1/auth/hr/` (cover, openings, candidates, onboarding, contracts, credentials, reviews, goals, payroll, directory, org-chart, overview, alerts, me) and `/api/v1/auth/academics/` (leave-policy, leave-calendar, leave-days, leave-balances/carry-over). Code: `backend/services/education/hr/`, `frontend/src/pages/education/hr/`. Tests: `backend/tests/test_hr.py`, `frontend/src/pages/education/hr/hr.test.tsx`.

**Not built yet:** a public careers page (HR enters candidates), tax filing (withholding is a flat percentage), and a school-nurse visit log. Periods that automatic leave cover cannot fill become open cover requests. The timetable, teaching-rule, cover and data-pack work is described in [docs/PLAN_SCHEDULING_AND_DATA_IMPORT.md](docs/PLAN_SCHEDULING_AND_DATA_IMPORT.md).

## Daily briefs, student support and planning

**Daily briefs** (`/education/briefs`, administrators only). A morning brief and an evening summary for the school day, so an administrator can look at one page instead of everywhere.

* **Counts only.** Every figure is a count, an amount or a percentage for the whole school. No student or staff name is stored in a brief or sent to the AI. The list of figures and how each rolls up is in `backend/services/education/briefs/metrics.py`.
* **Draft, then approve.** A brief is always created as a draft with a short written summary (AI-written if a provider is set and `ai_daily_brief` is on, otherwise a plain summary of the same figures; the page says which). An administrator may edit the words and approves it. An approved brief is locked: it can be printed or deleted, not changed. Approval, edits, creation and deletion go to the audit log.
* **Headlines and read stamps.** Each brief has a one-screen *Headlines* view, and administrators can mark it as read (name and time shown to the others).
* **Time zone.** Briefs are prepared at the times in the school's settings (default 06:30 and 17:00) in the *school's* time zone. The scheduled job `daily-briefs` (Celery Beat, every 15 minutes, `services.education.briefs.tasks.run_due_briefs`) makes whatever is due and not yet made. Without a worker (for example the free demo host) press **Prepare it now**.
* **Roll-ups.** Weekly, fortnightly and monthly briefs are worked out from the daily ones (events add up, rates average, "how many are open" takes the latest day) and follow the same approve and lock rules. The latest finished week, fortnight and month are made automatically.
* **Kept for about three months.** Daily briefs and roll-ups older than 92 days are deleted by the same job, so the oldest are overwritten instead of piling up. Any can be printed or deleted at any time.
* API: `/api/v1/auth/briefs/` (today, list, generate, detail, approve, read, settings, rollups). Code: `backend/services/education/briefs/`, `frontend/src/pages/education/briefs/`. Tests: `backend/tests/test_daily_briefs.py`, `test_daily_briefs_extras.py`.

**Absence ladder and interventions.** *Attendance → Absence Reports* sets what happens as unexcused absences add up (default 3, 5 and 10; each step can warn the family, tell staff and open an intervention). *Interventions* (`/education/interventions`; staff see *My Interventions*) is the counsellor's list: owner, due date, notes, done or dismissed with a reason. The early-warning model opens one too when it flags a student. School Reports → Attendance shows chronic absenteeism (10% or more of days recorded). Code: `backend/services/education/interventions/`, `attendance/escalation.py`.

**Planning** (*Reports → Planning*, administrators). A written read of the figures, next year's enrolment forecast (plain arithmetic: last year's grade below × retention + approved offers + waiting applications × conversion, with a range, seats, sections and every assumption shown), score trends term over term (groups under 10 students are never shown), and staff workload signals (served under `/api/v1/auth/hr/signals/`; not a rating). Code: `backend/services/education/insights/planning.py`.

## Front desk, health, safety, forms, admissions extras and the installable app

* **Front Desk** (`/education/front-desk`): who may collect each child (guardians plus extra authorised adults), a do-not-release hard stop that only an administrator can override with a recorded reason, a release log that cannot be edited, and a visitor book with an "on site now" list.
* **Health Office** (`/education/health-office`): nurse visits (parents are told), medication permissions and a dose log that warns when a dose is too soon, and immunisation due-date reminders (`manage.py send_immunization_reminders`). Parents see their own child's records read only at **Health**.
* **Safety Reports** (`/education/safety`): any staff member files an incident; administrators and the counsellor run follow-up tasks and close with a note.
* **Forms** (`/education/forms`) and **Forms to Sign** for parents: permission slips with typed-name signatures that are final, a tracker, reminders and CSV export.
* **Admissions**: a waiting list with ranked, automatic seat offers (`manage.py admissions_daily` expires offers and sends reminders), tour and interview booking, a per-application document checklist, an optional application fee paid by card, and a family page at `/apply/manage` that needs only the application number and tracking code.
* **Installable app and push**: manifest, safe service worker, and Web Push. Generate keys with `manage.py generate_vapid_keys` and set `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CONTACT` (and `FRONTEND_URL` for email links). A guided tour runs on first sign-in and is replayable from Help.
* Named roles `front_desk`, `nurse` and `counsellor` give a staff member one of these tools. Where to click for each is in [docs/USER_MANUAL.md](docs/USER_MANUAL.md); open items are in [docs/Future Plan.md](docs/Future%20Plan.md).

## Library

Campus services > Library (`backend/services/education/library/`, `frontend/src/pages/education/library/`). Catalogue with numbered copies and barcode labels, members and library cards, the circulation desk (issue, return, renew), reservations and holds, fines and reports. Families see their children's loans under **Library**.

- **Lock a copy in the safe.** A copy on the shelf can be locked with a required reason (for example "rare first edition"). Locked copies are not counted as available and cannot be lent; the catalogue shows the reason, who locked it and when. Unlocking puts it back on the shelf. Locking and unlocking are written to the audit log. Only a copy that is on the shelf can be locked.
- **Return check.** The Return button on a loan asks for the barcode of the book in hand. If it is not the book on that loan, nothing is returned and the message names both books. If a label is torn, the desk can confirm by hand; the loan records whether it was returned by scan or by hand. Scanning a barcode on the Desk's "Returns" box still works as before.
- **Library notices on phones.** Borrowing, "due tomorrow", overdue and "ready to collect" notices are a separate *Library* notification type, so they appear in the app and are pushed to phones that have turned on web push (VAPID keys needed, see Notifications). Tapping one opens the Library page, and people can switch Library notices off on their own. `send_library_reminders` runs daily at 07:00 through Celery beat (or run the management command from cron).
- **Not built:** a phone-camera scanning screen for librarians.

## Multiple schools

One installation serves many schools. Each school's data is kept separate: staff, students and parents only ever see their own school.

**How a school joins.** On the sign-in page, **Create your school** opens `/signup`. The person signing up enters the school's name, then either creates a password or uses **Sign up with Google**. The server creates the school, makes that person its administrator and signs them in. A new school starts empty, and its dashboard shows a setup checklist (profile, classes, subjects, staff, students, fees). Everyone the admin adds (staff, students, parents) belongs to that school and gets their own login (see "Portal logins" above).

**How the data is kept apart.**

- Every school-owned record carries its school, either in its own column or through its parent record (a payment through its invoice and student). The list is in `backend/services/core/tenants/registry.py`.
- Each API request works out the user's school once the login token is checked (`tenants/authentication.py`). Every query on those records is then filtered to that school automatically (`tenants/scoping.py`).
- New records are stamped with the school. Writing a record that points at another school's data is refused.
- A signed-in user with no school sees no school data at all. Cached responses and live dashboard updates are kept per school too.
- `backend/tests/test_tenant_isolation.py` calls every list endpoint in the API as a second school and fails if any of the first school's data appears.

**Google sign-in** uses the Firebase project in `frontend/src/services/firebase.ts`. The backend only needs that project's id: set `FIREBASE_PROJECT_ID` (it's public, not a secret). A Google account that isn't registered is sent to "create your school". It is never given an account automatically.

**Currency and language per school.**

- **Setting them.** The school's currency, default language and time zone are chosen at signup. A new school defaults to US dollars and Eastern time (the form offers the U.S. zones, and suggests the visitor's own currency); a school that signs up in pounds starts UK-style, in rupees Pakistan-style. The school admin can change them later in **Settings → Language & currency**. A school that existed before these defaults and never saved a currency or time zone keeps showing what it always did. The server's own clock zone is `TIME_ZONE` (default `America/New_York`); a deployment for schools elsewhere sets it in its environment, for example `TIME_ZONE=Asia/Karachi`.
- **Supported.** 45 currencies and 23 interface languages: English, German, Spanish, French, Italian, Portuguese, Dutch, Polish, Czech, Slovenian, Serbian, Croatian, Hungarian, Romanian, Albanian, Turkish, Russian, Ukrainian, Arabic, Urdu, Chinese, Japanese and Korean. Arabic and Urdu switch the layout to right-to-left.
- **Personal choice.** Everyone can pick their own language from the globe button in the header or on the sign-in page. It falls back to the school's default.
- **Where currency applies.** Money on every screen, AI answers, fee PDFs and invoice text uses the school's currency. Changing the currency relabels amounts; it doesn't convert them.
- **Code.**
  - Backend lists: `backend/services/core/tenants/localization.py`.
  - Frontend: translation files in `frontend/src/i18n/locales/<code>.json` (a test checks they all have the same keys).
  - Use `t('…')` from `react-i18next` for new text, and `cur()` / `formatMoney()` from `@/utils/currency` for money.
- **Status.** Menus, sign-in, signup, dashboard, setup checklist and settings are translated; other screens show English until translated. Have a native speaker review each language before selling in that market.

**Platform owner.** Superusers get **All Schools** in the sidebar (`/platform/schools`): every school with student and staff counts and its admins. A school can be suspended there, after which its users can't sign in. A superuser who belongs to a school sees that school's data on the normal pages. Send `X-Tenant-ID: <school id>` to act for another school through the API.

**Existing data.** The upgrade migration assigns every record that had no school to the school most users belong to, and links superusers without a school to it. Nothing else changes for a single-school installation.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL (or SQLite for quick local dev)
- Redis (optional for dev — required for Celery/WebSockets in production)

### Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate  |  macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

On Windows you can also run `setup.bat` for a scripted fresh install (venv, deps, migrations, superuser, sample data).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment Configuration

Copy the example env files and fill in your values:

- Backend: `.env.example` → `.env` (database, Redis/Celery, email, S3, WhatsApp, payment gateways, JWT, feature flags)
- Frontend: `frontend/.env.example` → `frontend/.env.local` (API/WS URLs, Firebase, app settings)

**Never commit real secrets** — keep production credentials out of the repository.

### API Docs

Versioned OpenAPI docs are auto-generated with drf-spectacular:

- `/api/v1/schema/swagger-ui/`
- `/api/v1/schema/redoc/`

## AI Features

All AI endpoints live under `/api/v1/ai/` and require a logged-in user. The user's role (admin, accountant, teacher, student, parent) and school are worked out on the server from their login, so the browser can't claim a different role.

### AI assistant (chat)

The floating **CodeCortex** assistant is available in every portal.

- **Answers from live school data.** The AI looks things up with read-only tools: student search and profiles, class strength, attendance, fee defaulters, finance summary, exams, homework, behaviour, certificates, payroll, timetable and notifications. It can use several tools in a row to answer one question.
- **Role and school limits.** Every lookup is checked centrally:
  - Admins see their whole school.
  - Accountants see finance and student lookups.
  - Teachers see only their own classes, and no fee data.
  - Students and parents see only their own (or their children's) records.
  - Data from other schools is never returned.
- **Privacy.** Phone numbers, emails, CNIC and addresses are masked before any data is sent to the AI provider (turn this off with `AI_SHARE_CONTACT_INFO=true`). Every lookup the AI makes is recorded in the audit log.
- **Chat experience.** Answers stream in as they're written, with a status such as "Checking attendance…" while the AI looks things up. Also: a stop button, saved chat history (open, continue, delete), copy, 👍/👎 feedback, tables in answers, and voice input/output in English or Urdu.
- **Basic mode.** If no AI provider is configured, or the provider is down, the assistant answers common questions ("fee defaulters", "my attendance", …) with simple keyword matching, under the same role limits.

### Governed AI: school documents and approvals (administrators)

Page: **AI Approvals & Documents** (`/education/ai-governance`). Code: `backend/services/ai/` (`knowledge.py`, `actions.py`, `governed.py`, `governance_api.py`).

- **Answers from the school's own documents (retrieval-augmented).** An administrator adds the handbook, policies or fee rules as text (paste, or load a `.txt` / `.md` file). They are split into passages and searched with keyword ranking (BM25), so this needs no extra service and also works without an AI provider. The assistant names the documents it used ("Sources: ...") and says so when nothing matches. Each document has an audience (everyone, staff only, administrators only) that is enforced on the server by role and school, and one school's documents are never searched for another. Passages are given to the model as reference text, not instructions. *Not built yet: PDF upload and meaning-based (embedding) search.*
- **The assistant can only ask; a person approves.** Actions are registered in code (`actions.py`), each with who may ask, who may approve and its own checks. Today: send a fee reminder for one unpaid invoice, and open a student support case. When someone asks the assistant to do one, it stores a pending request and tells the user nothing has been done. An administrator approves or rejects it on the Approvals tab. Before it runs, the approver's role, the school, the request's age (two days) and the asker's own permission are checked again, and it runs once. Requests, decisions and results go to the audit log. An asker cannot approve their own request unless they are an administrator, and a school can never see or decide another school's requests.
- **Limits.** This is a small, tested set of actions, not a general agent platform: there is no per-agent identity or policy language, and it has been tested on sample data only.

### Lesson plans and quizzes (teachers and admins)

- **Lesson plans** (Lesson Planner page): the AI drafts objectives, materials, an introduction, timed activities, group work, support for weaker and stronger students, check-for-understanding questions and homework. The teacher reviews and edits the fields before saving.
- **Quizzes** (`POST /api/v1/ai/generate-quiz/`): the AI writes MCQ, true/false and short-answer questions with explanations, at the chosen difficulty. Questions with a broken answer key are dropped automatically. Quizzes are saved as drafts and published to a specific class with `publish-quiz`; teachers can only publish to their own classes. There is no quiz screen in the app yet, so this is API-only for now.

Lesson plans take optional standards (one per line) and return an alignment section; without a provider they give a standard template and say so. Quizzes need an AI provider key.

### Drafts for teachers and the office

Everything here is a draft for a person to read and edit. Nothing AI-written is sent or saved without staff action, and the AI never decides grades, admissions or discipline.

- **Message to a family** (`POST /ai/parent-message/`; *Messages → New message → Draft with AI*): a type (behaviour concern, positive note, missing assignments, attendance concern, custom), a tone and a few notes. Only the student's first name and the notes are sent. Notes that mention health, support plans, discipline or family matters trigger a warning. It needs the school's AI use notice accepted (*Settings → AI Assistant*); without a provider it returns a plain template.
- **Rubric** (`POST /ai/rubric/`; Gradebook → assignment → Rubric): criteria by performance level, saved on the assignment, shown from the gradebook header, and never changing a score.
- **Messages:** translate on demand (saved per text and language, with *Show original*), summaries with a suggested reply for staff, and an urgency label from a keyword check (staff see it; it is not an AI call).
- **Written summaries of school figures** (*Reports → Planning* and the daily briefs): figures only, never names.
- **Settings and notice** (`/ai/settings/`, administrators): a switch per AI feature for the school, this month's use, and the AI use notice. `GET /ai/capabilities/` tells the screens whether a provider is set and whether face recognition is available.

### Analytics (ML)

- **Risk scan** (admins): scores each student's dropout and fee-default risk. Results appear as "At-Risk Students" on the Analytics page.
- **Attendance anomalies** and **face-recognition attendance** (teachers and admins).

These need the packages in `ai-ml/requirements.txt` (scikit-learn, XGBoost, pandas, DeepFace). If they aren't installed on the server, the endpoints return **503 "not available"** instead of producing fake results.

### Usage limits and cost control

- Each user can send `AI_RATE_LIMIT` requests every `AI_RATE_WINDOW` seconds (default: 30 per 10 minutes).
- Each school has an optional monthly token cap (`AI_TENANT_MONTHLY_TOKENS`; 0 = unlimited).
- Token usage is stored per user, per feature and per day (`AIUsage`), and per message (`AIMessage`).
- AI features can be switched off per school (*Settings → AI Assistant*, or a feature flag such as `ai_chat`, `ai_lesson_plans`, `ai_quiz`, `ai_parent_message`, `ai_rubric`, `ai_narrative`, `ai_daily_brief`, `ai_translation`, `ai_message_summary`). With no flag set, a feature is on.

### Configuration

Set these in `.env` (or in the Render dashboard):

| Variable | Default | Purpose |
|----------|---------|---------|
| `AI_PROVIDER` | *(empty)* | `openai` or `anthropic`. Empty = whichever key is set (OpenAI first). |
| `OPENAI_API_KEY` | — | Enables OpenAI. |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model. |
| `ANTHROPIC_API_KEY` | — | Enables Claude (default model `claude-opus-5`). |
| `AI_MODEL_FAST` / `AI_MODEL_SMART` | provider default | Override the chat model (fast) and the lesson/quiz model (smart). |
| `AI_CLAUDE_EFFORT` | `medium` | Claude effort level (`low` … `max`). |
| `AI_SHARE_CONTACT_INFO` | `false` | Send phone/email/CNIC/address to the AI provider. |
| `AI_RATE_LIMIT` / `AI_RATE_WINDOW` | `30` / `600` | Per-user request limit and window (seconds). |
| `AI_TENANT_MONTHLY_TOKENS` | `0` | Monthly token cap per school (0 = unlimited). |
| `TIME_ZONE` | `America/New_York` | The server's clock zone (each school also keeps its own). |
| `DEMO_RESET_TOKEN` | *(empty)* | Demo or staging server only: enables the nightly demo reset call. Leave unset elsewhere. |

### API endpoints

Paths are relative to `/api/v1`.

| Method | Path | Who | What |
|--------|------|-----|------|
| POST | `/ai/chat/` | all roles | Ask a question (`{"message", "conversation_id"?}`) and get a JSON answer |
| POST | `/ai/chat/stream/` | all roles | Same, as Server-Sent Events (`token`, `tool_start`, `tool_end`, `done`) |
| GET | `/ai/conversations/` | all roles | Your saved chats |
| GET / PATCH / DELETE | `/ai/conversations/<id>/` | owner | Open, rename or delete a chat |
| POST | `/ai/messages/<id>/feedback/` | owner | Rate an answer (`1`, `-1` or `null`) |
| POST | `/ai/lesson-plan/` | teacher, admin | Draft a lesson plan (optional `standards`) |
| POST | `/ai/parent-message/` | teacher, admin | Draft a message to a family |
| POST | `/ai/rubric/` | teacher, admin | Draft a rubric |
| GET / PUT | `/ai/settings/`, POST `/ai/settings/accept-notice/` | admin | AI switches, usage and the use notice |
| GET | `/ai/capabilities/` | all roles | Whether an AI provider and face recognition are available |
| POST | `/ai/generate-quiz/` | teacher, admin | Draft a quiz |
| POST | `/ai/publish-quiz/` | teacher, admin | Publish a quiz to a class |
| POST | `/ai/train-models/` | admin | Run the ML risk scan |
| GET | `/ai/student-predictions/` | all roles (scoped) | Risk scores you're allowed to see |
| GET | `/ai/attendance-anomalies/` | teacher, admin | Unresolved attendance alerts |
| POST | `/ai/face-register/`, `/ai/face-attendance/` | teacher, admin | Face recognition |

The code lives in `backend/services/ai/` (assistant, tools, AI providers, limits) and `backend/services/analytics/ai_views.py` (content generation and ML). The roadmap for further AI work is below, under [Pending actions](#pending-actions).

### Pending actions

#### Setup (to do now)

- [ ] **Add an AI key on Render.** Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` on the backend service (Environment tab). Until then, the assistant runs in basic keyword mode and lesson plans and quizzes return "not configured".
- [ ] **Check the deploy.** Log in, open the assistant and ask "fee defaulters". Also confirm that `/api/v1/ai/chat/` refuses requests from someone who isn't logged in.
- [ ] **Optional: set limits.** `AI_RATE_LIMIT`, `AI_TENANT_MONTHLY_TOKENS`.
- [ ] **Turn on Google sign-in.** Set `FIREBASE_PROJECT_ID=school-erp-c53b4` on the Render backend (Environment tab). In the Firebase console (Authentication → Sign-in method), enable **Google** and add the live frontend domain under **Authorized domains**.
- [ ] **Portal logins for existing students and staff.** Open Students → Portal Logins and Employees → Portal Logins, click **Generate missing logins**, and reprint the letters.

#### Decisions needed

- [ ] **Main AI provider:** OpenAI or Claude. Current behaviour: OpenAI if its key is set, otherwise Claude (`claude-opus-5`).
- [ ] **Model choice:** a cheaper "fast" model for chat and a stronger "smart" model for lesson plans and grading.
- [ ] **Monthly AI budget:** overall and per school.
- [ ] **Where heavy ML runs:** a separate paid Render worker, a scheduled job, or dropping face recognition for now. The ML packages are not installed on Render today.
- [ ] **Parent message languages:** English, Urdu, or Roman Urdu.
- [ ] **Data sent to the AI provider:** contact details are masked by default. Confirm what else must never be sent.
- [ ] **Knowledge-base search:** allow `pgvector` on the Render Postgres database.

#### Not finished from the current work

- [ ] Gemini support (only OpenAI and Claude are built).
- [ ] Switching to a second AI provider automatically when the first one fails.
- [ ] Error tracking and performance metrics for AI calls (Sentry/Prometheus).
- [ ] Charts inside chat answers (tables already work).
- [ ] Removing basic keyword mode once an AI key is live and stable.
- [ ] Basing lesson plans and quizzes on the school's own syllabus.
- [ ] Lesson plan versioning and PDF export.
- [ ] A quiz screen: teachers review, edit and publish AI quizzes (the backend is ready).
- [ ] Splitting the AI tools into separate files when more are added.

#### Planned new AI features (Phase 3)

Two items sometimes proposed for this list are **already built**, not planned: dropout risk and fee-default risk are the existing ML risk scan (`ai-ml/predictions/dropout_fee_model.py`, `POST /ai/train-models/`, `GET /ai/student-predictions/`) — see [Analytics (ML)](#analytics-ml) above.

- [ ] Search over school documents (policies, circulars, syllabus) with answers that cite the source.
- [x] AI report card remarks for each student, drawn from grades, attendance and behaviour, reviewed by the teacher before saving.
- [~] Parent message drafts: built for teachers (*Messages → Draft with AI*, edited and sent through messaging). Not built: drafts for fee reminders and sending over SMS/WhatsApp.
- [x] An AI summary of a long parent message or conversation thread, for a busy staff member (with a suggested reply for staff to edit).
- [x] At-risk alerts that explain why a student was flagged and suggest what to do (they open an intervention).
- [ ] AI help with grading written answers (teacher confirms every mark).
- [ ] Plain-language analytics questions, e.g. "compare fee collection this term vs last".
- [ ] Actions the AI prepares and a person confirms, e.g. "send reminders to defaulters".
- [x] A server-side timetable generator with teaching rules, preview and undo (`academics/scheduler.py`; rules-based, not plain-language constraints).
- [x] A homework helper for students: hints limited to their own syllabus, not the final answer.
- [x] Screening admission applications against the school's stated criteria, with a reason for each suggestion, before office review (not an automatic accept/reject).
- [x] Flagging behaviour patterns (repeated incident types, a rising trend for one student or class) before they escalate, from the existing behaviour records.
- [~] Translation: a message or announcement can be translated on demand (saved per language). Not built: translating every notice, absence or fee text, and report card into each family's own language automatically.

#### Later (Phases 4–5)

- [ ] Run ML training and bulk AI jobs as background jobs, with progress shown in the app.
- [ ] Retrain the risk models on real school data and track model versions.
- [ ] Consent and data-deletion handling for face recognition.
- [ ] Automated AI quality tests: sample questions per role, prompt-injection and role-escalation checks.
- [ ] An admin dashboard for AI usage, cost per school and feedback.
- [ ] Privacy note for schools, per-school AI opt-out, and a retention policy for saved chats.

#### Known issues (not caused by the AI work)

- [ ] `tests/test_finance.py` hangs after `test_retrieve_invoice`.
- [x] Report cards, transcripts, grades and fee documents (receipts, invoice PDFs, the older result-card and fee-receipt downloads) are checked on the server so a family or student only gets their own, and the school-wide finance PDFs are for finance staff (tests: `test_demo_audit.py`, `test_finance_documents_access.py`). The Analytics page can only list students the login is allowed to see.
- [ ] `npm run lint` doesn't run: ESLint 9 needs an `eslint.config.js`.
- [ ] `frontend/src/i18n/locales.test.ts` fails for most languages: the locale files are out of sync with `en.json`.
- [x] Timetable and cover rules, teacher-to-subject validation, and one import/export format are done (see the two sections above).
- [ ] The data pack does not yet cover gradebook scores, library, transport, cafeteria, inventory, behaviour or certificates; use the technical export in Settings > Security > Data for those.
- [ ] Gradebook, library and similar modules are not in the pack; very large packs (over about 5,000 new students) take several minutes because creating a student sets up their family records.
#### Multiple schools: limits to know

- [x] Student IDs and employee IDs are login usernames, so they must be unique across all schools. Each school's own three-letter code is now put in front automatically (`GVS-STU0001`, `GVS-EMP-0001`) and each school numbers from 1 on its own, so two schools can both start at 0001. A number that is already used is refused with a clear message instead of being silently changed (`backend/services/core/tenants/identifiers.py`). IDs that already exist are left as they are. User emails are still unique across all schools.
- [ ] Parent accounts are matched by phone number (`parent.<phone>@school.edu`). A parent with children in two different schools shares one account; it opens the school of the child linked first, every time, and never shows the two schools together. There is no school switcher yet.
- [ ] Billing and plans for schools are not built yet (the platform page only lists, suspends and re-activates schools).
- [x] The 24 one-off generator scripts that used to sit in `backend/` (some reset everyone to shared default passwords) are removed. Demo and sample data now come from `seed_demo` and the sample data pack in `sample-data/`.

## Deployment

**Client demo (Render + Vercel):** [deploy/DEMO_DEPLOY.md](deploy/DEMO_DEPLOY.md) puts the sample US school and the four demo accounts online with `deploy/render-demo.yaml` (`python manage.py setup_demo` loads it; `DEMO_RESET=1` wipes an old site first). Set `VITE_DEMO_LOGINS=true` on Vercel to show the demo accounts on the sign-in page.

*Demo notes.* A free Render web service sleeps after about 15 minutes without traffic (the first request then takes up to a minute), so open the backend address a few minutes before a demo, or have a free uptime monitor request `/api/v1/health/live/` every 5 minutes. A nightly reset is available (`.github/workflows/demo-reset.yml` calls `POST /api/v1/demo/reset/` with `DEMO_RESET_TOKEN`; it exists only on a demo or staging server and does nothing until `DEMO_BACKEND_URL` and the secret are set). The free host has no Celery worker, so scheduled jobs (including the daily briefs) do not run there: use **Prepare it now**. Details in [deploy/DEMO_DEPLOY.md](deploy/DEMO_DEPLOY.md).

The backend (Django + PostgreSQL + Redis + Celery + WebSockets) cannot run on static-only hosts. Use one of the prepared options:

### Recommended — Vercel (frontend) + Oracle Cloud Free ARM (backend)

Fully free, always-on, no expiry:

- **Frontend** → Vercel Hobby (static SPA, `frontend/vercel.json`)
- **Backend** → Oracle Cloud Always Free ARM VM running `docker compose up -d --build` (Django/daphne + PostgreSQL + Redis + Celery, all self-contained)

Step-by-step instructions: **[deploy/oracle-setup.md](deploy/oracle-setup.md)**

### Option A — Self-hosted with Docker (full stack, recommended)

```bash
cp .env.example .env   # set SECRET_KEY and DB_PASSWORD
docker compose up -d --build
```

Starts PostgreSQL, Redis, Django (daphne/ASGI), Celery worker + beat, and the Nginx-served frontend on port 80. Media and collected static files live in shared Docker volumes.

### Option B — Render blueprint

Import this repo into [Render](https://render.com) as a Blueprint (`render.yaml`). It provisions PostgreSQL, Redis, the Django web service and the frontend static site (Celery workers are not included on the free plan). After first deploy, set `VITE_API_URL` on the frontend to `https://<your-backend>.onrender.com/api`, and set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` on the backend to turn on the AI features.

### Option C — Vercel (frontend) + backend elsewhere

The SPA can be deployed to [Vercel](https://vercel.com) using the included `frontend/vercel.json`. Host the Django backend separately (Render/Railway/VPS) and set `VITE_API_URL` to its URL during the Vercel build.

> Production checklist: set a strong `SECRET_KEY`, restrict `ALLOWED_HOSTS` and CORS to your real domains, enable HTTPS, and set `USE_S3_STORAGE=true` for media once you have S3/R2 credentials.

## Testing

```bash
# Backend (pytest + coverage). Same setup as CI: SQLite, no Postgres needed.
cd backend
pip install -r requirements.txt -r requirements-dev.txt
# Windows PowerShell: $env:USE_SQLITE='1'; $env:DEBUG='1'     macOS/Linux: export USE_SQLITE=1 DEBUG=1
pytest tests/ --cov=services --cov=auth_api
pytest tests/ -q -n 4 --no-cov        # faster: parallel, no coverage (the first run builds the test database)
pytest tests/test_hr.py               # Staff & HR only
pytest tests/test_daily_briefs.py tests/test_daily_briefs_extras.py   # Daily briefs
# Run the whole suite WITH migrations (leave out --nomigrations): some tests need data the migrations create, such as the subscription plans.

# AI features only (no API key needed — the AI provider is faked in tests)
pytest tests/test_ai_security.py tests/test_ai_platform.py tests/test_ai_generation.py

# Frontend (Vitest)
cd frontend
npm run test
npx tsc --noEmit -p tsconfig.app.json   # type check
npm run lint

# Migrations: new model changes need a migration. If the dev Postgres history is inconsistent, generate on a scratch SQLite file:
# USE_SQLITE=1 SQLITE_PATH=/tmp/x.sqlite3 python manage.py makemigrations <app>
```

## CI/CD

GitHub Actions runs backend/frontend tests, linting (flake8, ESLint), type checking (mypy), security audits (bandit, safety, npm audit), migration safety checks, and build artifacts on push/PR to `main`, `staging`, and `develop`.

## License

Proprietary — all rights reserved.




















AI Inside CC-EMS (Schools)
AI Feature	What It Does	Value

✅AI Report Card Comments	Generates personalized teacher comments from grades, attendance, and behaviour	Saves teachers hours per term

✅AI Attendance Insights	Predicts which students are at risk of dropping out	Early intervention saves students

✅AI Fee Default Prediction	Predicts which families are likely to default on fees	Improves collection rate

✅AI Admission Screening	Screens applications against school criteria	Speeds up admissions

✅AI Homework Helper	Students get step-by-step help on homework	Parent-facing value

✅AI Parent Message Summarizer	Summarizes long messages into key points	Saves parents time

✅AI Timetable Generator	Creates optimal timetables from constraints	Saves admin weeks of work

✅AI Behaviour Pattern Detection	Identifies patterns before they escalate	Protects students

✅AI Translation	Translates communications into every parent's language	Improves inclusion