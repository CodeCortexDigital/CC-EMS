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
- **Governed AI** — the assistant can only ask; people approve (two different people by default), the approval is tied to the exact action asked for, and every answer, risk-flag review, approval step and AI setting change is kept in a hash-chained decision trail with a readable record page and a one-switch "All AI" off. See [Governed AI](#governed-ai-school-documents-and-approvals-administrators) and [docs/AI_GOVERNANCE.md](docs/AI_GOVERNANCE.md).
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
2. Sets up a local SQLite database and fills it with the sample US school, **Maple Grove Academy** (first run only, about a minute plus setup; later runs start in seconds): K-8, 83 students, 24 staff, timetable, fees, attendance, exams, HR and one saved lesson plan. It is loaded through the same importer a school would use.
3. Starts the backend on **http://localhost:8009** and the frontend on **http://localhost:5179** in two windows, then opens the login page.

**The demo school.** `python manage.py seed_demo` loads *Maple Grove Academy* from `sample-data/us-school/` (it is the only demo school; the old built-in Pakistani-style school is gone). The four demo logins below are wired to it (`teacher@code.com` is a maths teacher, `student@code.com` a Grade 8 student, `parent@code.com` a parent of two). `demo.bat` loads it on a first run; if you have an older demo database, run **`load-us-school.bat`** (it migrates, loads Maple Grove and makes the demo logins open it), then `restart-demo.bat`. The files are in [sample-data/us-school/](sample-data/us-school/); upload `us-school-pack.zip` in the app to load them into any school.

**Japanese demo school.** *Wakaba Gakuen* (みどり市立 若葉学園, a public nine-year school, grades 1 to 9) is a second sample school in [sample-data/jp-school/](sample-data/jp-school/): 109 students with names written family name first, 27 staff, six lessons a day with school lunch, an April to March year in three terms, Japanese holidays and events, school lunch fees in yen, attendance, exams and payroll. Run **`load-jp-school.bat`** (then `restart-demo.bat`) to make the demo logins open it, and choose 日本語 with the globe button on the sign-in page; `load-us-school.bat` switches back. The Japanese page wording is in `frontend/src/i18n/phrases/ja.json`. The demo school also has sample **指導要録** (cumulative records) for the 6年 class. Not done yet: the junior-high 調査書; see the [Japan to-do list](#japan-to-do-list).

**Cumulative record (指導要録).** Menu: Academics > Cumulative Records (`/education/records`, administrators and teachers). It follows MEXT's reference forms for elementary, junior high and high school: 様式1 (the register: furigana, guardian, entry, transfer, graduation, next school, the class and the two seals for each year) and 様式2 (A/B/C ratings on the three viewpoints and the overall 評定 for each subject, 道徳, 総合的な学習の時間, 外国語活動, 特別活動 and 行動 marks, 総合所見 and 出欠の記録). *Fill from school data* takes the class, teacher, principal and the attendance counts from the register (出席停止・忌引 are two new attendance reasons). Each year is sealed first by the class teacher and then by the principal (an administrator); a sealed year is locked until an administrator re-opens it with a reason, and every change is audited. *Print / PDF* prints the form with era dates (令和) through the browser, and *CSV* gives one row per student and year. A teacher sees only their own classes; families and students have no access; an erasure request blanks the names and comments but keeps the ratings. High school keeps a list of courses with credits (単位) instead of fixed subjects. The subjects and years of each level are defined in one place, `backend/services/education/records/forms.py`, because Boards may adapt the reference forms. Code: `backend/services/education/records/`, API `/api/v1/auth/records/`, tests `backend/tests/test_records.py` and `frontend/src/pages/education/records/`.

To stop, run **`stop-demo.bat`** (or close the two server windows); **`restart-demo.bat`** stops and starts again. Both only touch the demo ports 8009 and 5179. On this machine there are desktop shortcuts: *ERP Demo - Start / Stop / Restart*. To rebuild the demo data from scratch: `cd backend` then `.venv\Scripts\python manage.py seed_demo --reset`.

**Demo logins**

| Role | Email | Password | What they see |
|------|-------|----------|---------------|
| Admin | `admin@code.com` | `Admin@123` | Whole school: dashboard, fees, attendance, analytics |
| Deputy admin | `deputy@code.com` | `Deputy@123` | A second administrator, so the two-approver rule can be shown |
| Teacher | `teacher@code.com` | `Teacher@123` | A maths teacher (Grade 6): classes, timetable, cover, drafts with AI |
| Parent | `parent@code.com` | `Parent@123` | A parent of two children: their attendance, fees, forms, health records |
| Student | `student@code.com` | `Student@123` | A Grade 8 student: own timetable, homework, results |

**Suggested walkthrough (about 10 minutes)**

1. **Admin → Dashboard:** live totals (students, staff, fee collection, today's attendance).
2. **Admin → AI assistant** (purple button, bottom right): ask *"Fee defaulters & finance summary"*, then *"How many students are absent today?"*.
3. **Admin → Reports → the AI Risk & Review tab:** click **Run AI Risk Scan**. The ML models score every student for dropout and fee-default risk; the at-risk list and charts update.
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

**Look and feel (the CC-IMS style).** A calm mint page, white cards and one brand colour: CodeCortex Teal `#0b6e66` is the default accent (a school can still pick another in Settings > Theme), with system fonts only so the app looks the same offline (`DEFAULT_THEME` in `frontend/src/utils/theme.ts`; people who saved their own theme keep it). `frontend/src/styles/modern.css` is loaded last and holds the shared rules: soft page glow, selection and focus colours, an autofill fix, sentence-case labels, quiet tables, underline tabs, solid accent buttons and a 12px floor for small print.

- **Top menu.** Staff roles (administrators, teachers, office staff) get a text-only menu bar (`components/layout/TopNav.tsx`). Pointing at an area opens a wide panel of its pages after about 70 ms and closes it about 220 ms after the pointer leaves; Escape, a click outside or going to a page also close it, and on a touch screen the first tap opens and the second goes. **Admin** holds security and privacy, importing data, integrations, the AI assistant and All Schools; **Settings** is its own tab (profile, theme, language and currency, account, plan and billing, help). The tabs are centred on one line, and anything that does not fit goes under **More**. Every page has a star to add it to **Favourites** (at most 8, with a message when full). A button at the right switches to the side menu and back (remembered per computer). Students and parents keep the compact side menu. The menu data comes from one place, `components/layout/useNavItems.tsx`, which the side menu also uses, so the two always agree and each role sees only its own entries.
- **Settings in the menu.** Each settings section (Profile, Theme, Language and currency, Account, Plan and billing, Security and privacy) is its own entry under Admin, so the Settings page shows only the chosen section and no second row of tabs.
- **Sign-in page.** `pages/auth/LoginPage.tsx` with `components/auth/LoginFrame.tsx`: a greeting by the hour, a large headline and a short "What you get" card on wide screens, one sign-in card with a three-way switch (Admin, Staff, Student and Parent), a light/dark switch that carries into the app, Google and Microsoft options, and a calm full-page "loading your profile" message after sign-in. Tall inputs, placeholder text, labels for screen readers, and the demo accounts block when `VITE_DEMO_LOGINS=true`.
- Shared building blocks follow the same rules: `StatCard` (white card with an accent icon chip), `ModuleTabsLayout` (section name and underline tabs on one row, with `OverflowTabs` putting tabs that do not fit under a More menu) and `components/common/kit.tsx`. Page code should use these and the accent colour, not fixed colours, so a page restyles when the theme does.
- **Not copied from CC-IMS** (they do not fit a school app, or already exist here): the company-days counter in the header, the Staff/Client door switch (CC-EMS has three doors), sidebar pinning (the side menu here is collapsed by a click, not by hovering), and the sessions, device-limit, edit-conflict and assistant features, which CC-EMS already covers in its own way or does not need yet.

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

**Absence ladder and interventions.** *Attendance → Absence Reports* sets what happens as unexcused absences add up (default 3, 5 and 10; each step can warn the family, tell staff and open an intervention). *Interventions* (`/education/interventions`; staff see *My Interventions*) is the counsellor's list: owner, due date, notes, done or dismissed with a reason. The early-warning model opens one too when it flags a student. School Reports → Attendance shows chronic absenteeism (10% or more of days recorded). **Record of support:** each intervention also records the day support began (set when it is started or the first session is logged), the sessions delivered (**Log a session**), a result (improved, no change, got worse, not measured yet) with the evidence, and a review date that shows **review due** when it arrives. A panel at the top (administrators and counselors) shows students flagged, students reached, sessions delivered, average days from flag to start, results and reviews due, from `GET /auth/interventions/reach/`. The hosted demo shows a "Sample data" bar on every page (any build with `VITE_DEMO_LOGINS=true`). Code: `backend/services/education/interventions/`, `attendance/escalation.py`.

**Planning** (*Reports → Planning*, administrators). A written read of the figures, next year's enrolment forecast (plain arithmetic: last year's grade below × retention + approved offers + waiting applications × conversion, with a range, seats, sections and every assumption shown), score trends term over term (groups under 10 students are never shown), and staff workload signals (served under `/api/v1/auth/hr/signals/`; not a rating). Code: `backend/services/education/insights/planning.py`.

## Front desk, health, safety, forms, admissions extras and the installable app

* **Front Desk** (`/education/front-desk`): who may collect each child (guardians plus extra authorised adults), a do-not-release hard stop that only an administrator can override with a recorded reason, a release log that cannot be edited, and a visitor book with an "on site now" list.
* **Health Office** (`/education/health-office`): nurse visits (parents are told), medication permissions and a dose log that warns when a dose is too soon, and immunisation due-date reminders (`manage.py send_immunization_reminders`). Parents see their own child's records read only at **Health**.
* **Safety Reports** (`/education/safety`): any staff member files an incident; administrators and the counsellor run follow-up tasks and close with a note.
* **Forms** (`/education/forms`) and **Forms to Sign** for parents: permission slips with typed-name signatures that are final, a tracker, reminders and CSV export.
* **Admissions**: a waiting list with ranked, automatic seat offers (`manage.py admissions_daily` expires offers and sends reminders), tour and interview booking, a per-application document checklist, an optional application fee paid by card, and a family page at `/apply/manage` that needs only the application number and tracking code.
* **Installable app and push**: manifest, safe service worker, and Web Push. Generate keys with `manage.py generate_vapid_keys` and set `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CONTACT` (and `FRONTEND_URL` for email links). A guided tour shows at every sign-in until every step is finished (**Skip** hides it for that sign-in only, then it returns); it is replayable from Help.
* Named roles `front_desk`, `nurse` and `counsellor` give a staff member one of these tools. Where to click for each is in [docs/USER_MANUAL.md](docs/USER_MANUAL.md); open items are in [docs/Future Plan.md](docs/Future%20Plan.md).

## Library

Campus services > Library (`backend/services/education/library/`, `frontend/src/pages/education/library/`). Catalogue with numbered copies and barcode labels, members and library cards, the circulation desk (issue, return, renew), reservations and holds, fines and reports. Families see their children's loans under **Library**.

- **Lock a copy in the safe.** A copy on the shelf can be locked with a required reason (for example "rare first edition"). Locked copies are not counted as available and cannot be lent; the catalogue shows the reason, who locked it and when. Unlocking puts it back on the shelf. Locking and unlocking are written to the audit log. Only a copy that is on the shelf can be locked.
- **Return check.** The Return button on a loan asks for the barcode of the book in hand. If it is not the book on that loan, nothing is returned and the message names both books. If a label is torn, the desk can confirm by hand; the loan records whether it was returned by scan or by hand. Scanning a barcode on the Desk's "Returns" box still works as before.
- **Library notices on phones.** Borrowing, "due tomorrow", overdue and "ready to collect" notices are a separate *Library* notification type, so they appear in the app and are pushed to phones that have turned on web push (VAPID keys needed, see Notifications). Tapping one opens the Library page, and people can switch Library notices off on their own. `send_library_reminders` runs daily at 07:00 through Celery beat (or run the management command from cron).
- **Not built:** a phone-camera scanning screen for librarians.

## Privacy, school isolation and AI review

The full answers, with the code and tests behind each, are in **[docs/CLIENT_READINESS.md](docs/CLIENT_READINESS.md)**. In short:

- **Schools are kept apart by machine-checked rules.** Every model that links to a school is either filtered to the signed-in school automatically or listed with the reason it is safe; a test fails when a new model is neither (`tests/test_school_isolation_sweep.py`). That check found that employee tasks, timesheets and HR documents were not filtered by school; they now are.
- **Retention and deletion.** Each school sets how long each kind of record is kept (Settings > Security), including AI chat history and decided AI requests, with a preview before anything is removed. From a **privacy request** the office can **download a copy of one student's data** and **erase it** (a preview, then the student ID typed to confirm, then audited). Marks, attendance and invoices stay without a name.
- **A person reviews AI risk flags.** Scores are labelled advice only; each high or critical flag waits for a person to confirm it, ask for more information or dismiss it with a reason, and the decision is recorded (Reports > AI Risk & Review > AI Predictive Analytics). Nothing is decided or sent by a score alone.
- **AI decisions leave a verifiable trail.** Assistant answers, risk-flag reviews, approval steps and AI setting changes are written to a per-school hash chain (tamper-evident, not tamper-proof); `python manage.py verify_audit_chain` checks it, and administrators read it in **AI Approvals > Decision records**. Details and limits: [docs/AI_GOVERNANCE.md](docs/AI_GOVERNANCE.md).
- **For Japanese schools:** a data handling register and a record of the AI provider's no-training confirmation (see [Japan](#japan-school-region-demo-site-and-privacy-records)).
- **Not claimed:** an independent audit, certification, or "GDPR compliance". The document lists what is still open.
- **More:** how the system fits together, with diagrams, is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); the school-isolation scenarios and known exclusions are in [docs/TENANT_ISOLATION_TEST_SUMMARY.md](docs/TENANT_ISOLATION_TEST_SUMMARY.md).

## Japan: school region, demo site and privacy records

Built on branch `feat/japan-demo` for a Japanese school partner. The 指導要録 and the Wakaba Gakuen sample school are described under [Run the demo locally](#run-the-demo-locally-no-api-keys-needed).

- **School region.** **Settings > Language & currency > Region style** now offers **USA, Pakistan and Japan** (currency, date format, language and wording). Each school keeps its own region.
- **A Japanese school next to the others, in one database.** Schools are kept apart row by row (see [Multiple schools](#multiple-schools)), so Wakaba Gakuen sits beside the existing demo schools with its own administrator. `python manage.py add_demo_school --pack jp-school --admin-email ... --admin-password ... --admin-name ...` adds it (it also gets `teacher@`, `parent@` and `student@wakaba.example`). On a hosted demo, set these on the **backend**: `DEMO_EXTRA_PACKS=jp-school`, `DEMO_EXTRA_ADMIN_EMAIL`, `DEMO_EXTRA_ADMIN_NAME`, `DEMO_EXTRA_ADMIN_PASSWORD`; the start command loads it once in the background (5 to 8 minutes; logins fail until it is done). For a site with only the Japanese school use `DEMO_PACK=jp-school` with `DEMO_ADMIN_EMAIL` and `DEMO_ADMIN_PASSWORD`. The administrator's password is typed only in the host's settings and is never kept in the repository. Full steps, including a separate Japanese site: [deploy/DEMO_DEPLOY_JP.md](deploy/DEMO_DEPLOY_JP.md).
- **Demo sign-in page.** With `VITE_DEMO_LOGINS=true` the page shows two buttons, **USA school** and **Japanese school**. Each lists its own accounts to click, and the Japanese button also switches the page to 日本語. Optional build settings: `VITE_DEMO_ADMIN_EMAIL`, `VITE_DEMO_ADMIN_PASSWORD` and `VITE_DEMO_ADMIN_LABEL` list that administrator first under the Japanese school (the password is then printed on the page, so use it only for sample data); `VITE_DEMO_ADMIN_REPLACE=true` shows only the Japanese school; `VITE_DEMO_JAPAN_SCHOOL=false` hides the Japanese button. These are read **when the site is built**, so change them and redeploy. On Vercel a variable applies only to the environments ticked (Production, Preview): a branch deploys as Preview.
- **Data handling register (個人情報取扱台帳).** **Settings > Security & privacy > Privacy** (administrators): for each kind of data, the purpose of use, how it is collected, retention, who it is given to and where it is stored, with health, support, family and guidance data marked as sensitive (要配慮個人情報). *Add the standard list* fills 13 lines in the page language (the 指導要録 line says 20 years for the register part and 5 years for the guidance part); lines can be edited, added, removed, downloaded as CSV or printed. The Wakaba demo starts with it filled in. Code: `backend/services/core/privacy/` (`register_defaults.py`, API `/api/v1/privacy/register/`), tests `backend/tests/test_data_register.py`.
- **AI provider does not train on your data.** **Settings > AI assistant** records the provider's written confirmation (provider, date, who gave it, where it is kept), shows what is always hidden before text is sent, and warns when the server uses a different provider from the one confirmed. It records the confirmation; it does not check it or block AI use. API `/api/v1/ai/settings/training-confirmation/`, tests in `backend/tests/test_ai_settings.py`.
- **Term report (通知表).** Menu: Academics > Term Reports (`/education/term-reports`, administrators and teachers). There is no national form, so the **layout is data**: an administrator sets, under *Edit the layout*, the subjects, the rating scale (A・B・C, five levels or points), whether the three viewpoints show, the behaviour items, the comment boxes and which sections print (attendance, behaviour, comments), separately for elementary and junior high; one layout is the default for new reports. A teacher picks a class and a term (from the school year's terms), opens a student's report and fills the ratings, behaviour and comments. *Fill from school data* writes the class, teacher, principal, the attendance counts for the term (same rules as the 指導要録) and a rating for each subject that has a gradebook grade (a percentage turned into a rating by the layout's thresholds, 80 and 50 for A・B・C by default); a rating a teacher has typed is never replaced. *Finalise* locks the report; only an administrator can re-open it, with a reason. Each report keeps a copy of the layout it started with, so changing the layout later does not rewrite old reports. *Print / PDF* uses the browser, so Japanese always prints. A teacher sees only their own classes; families and students have no access yet (a release to families is not built). Every read and change is audited. Code: `backend/services/education/records/` (`termreport.py`, `termreport_views.py`), API `/api/v1/auth/records/term-layouts/` and `/term/...`, tests `backend/tests/test_term_reports.py` and `frontend/src/pages/education/records/termReports.test.tsx`.
- **Page translation.** The page asks Chrome not to translate it (`notranslate` meta in `frontend/index.html`); Chrome's own translation broke React with a `removeChild` error on the Japanese screens. Do not set `translate="no"` on the `<html>` element: the app's own text swap treats it as "skip" and would stop translating.
- **Not done yet:** see the [Japan to-do list](#japan-to-do-list) below.

### Japan to-do list

Priorities: **P0** blocks the Japanese market, **P1** needed soon after, **P2** strengthens what exists. Tick a box when it is built, tested and described above.

**1. Statutory records and Japanese output**
- [x] **P0. Japanese font in server-made PDFs.** Built: invoices, fee receipts, result cards and finance reports use an embedded Noto Sans JP (regular and bold, SIL Open Font License, `backend/assets/fonts/`, helper `backend/services/pdf/fonts.py`). The font is trimmed to Latin, kana and the JIS X 0208 kanji (about 2.2 MB each); a character outside that set prints as a blank box. To rebuild the font files: `backend/scripts/build_jp_font.py`. If the font files are missing the PDFs fall back to Helvetica. Tests: `backend/tests/test_pdf_japanese.py`.
- [x] **P0. 通知表 (term report) with school-specific layouts.** Built as an engine: the layout is data an administrator edits, so a school's own sample can be matched without code. It still needs the client's real sample layouts to be matched and checked against; until then the starting layouts follow the 指導要録 reference subjects. See "Term report (通知表)" under the Japan section.
- [ ] **P1. 調査書 (junior-high report for high-school entrance).** Pull grades, attendance, special activities and behaviour from the 指導要録 and print in the format the receiving high school or board asks for. Needs the Japanese PDF font above.
- [ ] **P1. 指導要録 retention and transfer.** Statutory retention (学籍 20 years, 指導 5 years) applied by the retention tool, and an export when a student transfers or advances (転学・進学) that the receiving school can use.

**2. MEXT education data standards (interoperability)**
- [ ] **P1. School code, student ID and staff ID.** A MEXT school-code field, and a mapping between local IDs and standard IDs on import and export.
- [ ] **P1. Curriculum code (学習指導要領コード).** A code on subjects and syllabus data, and mapping when importing from a board of education or another system.
- [ ] **Later. OneRoster** roster exchange, and **xAPI Japan Profile** for learning logs (keep room for it in the data model).

**3. Personal information protection (APPI) deepening**
- [ ] **P2. Access log for personal information.** Record teacher views of student records, exports and prints (today the hash-chained trail covers AI actions and changes), and let administrators view and export it for regular review.
- [ ] **P2. Breach detection and report.** Alerts for unusual access, bulk exports and unauthorised sharing, and a draft initial report (what happened, who is affected, cause, what was done) built from the existing incident screen.
- [ ] **P2. Purpose-of-use notice to guardians.** Generate the notice at enrolment and when a new feature is switched on, let the guardian confirm it, and keep the delivery record. Sensitive data (health, support, family) needs the extra consent step.

**4. Generative AI guidelines (MEXT)**
- [ ] **P2. Mask student names typed into AI questions** (a name list from the school's own students, swapped for tokens before sending and restored in the reply), and flag answers that contain a student name for the teacher to check.
- [ ] **P2. Make the AI use notice mandatory** before a teacher uses an AI feature for the first time (it is recorded today, per school, but individual users are not asked).
- [ ] **P2. Enforce the no-training confirmation.** It is recorded today; optionally keep AI features off until it is recorded.

**5. Hosting and trust**
- [ ] A **third-party audit** or a self-assessment against the MEXT and PPC guidelines before a Japanese school signs.
- [ ] A **trusted off-site timestamp** for the hash chain, because 指導要録 are kept for years.
- [ ] A dedicated **demo environment** clearly labelled as sample data (the hosted demo is shared with another client).

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
- **Text written into pages.** Menus and the shell use `t()` and `locales/<code>.json`. Everything else (page titles, tabs, buttons, labels, placeholders, messages) is translated at the page by `frontend/src/i18n/pageText.ts`, which looks each piece of English up in `i18n/phrases/<code>.json` (about 7,400 phrases each for **Spanish, Portuguese, French, German and Arabic**; other languages fall back to English there) and puts the English back when English is chosen. The school's regional wording (Date Sheet / Exam Schedule, Challan / Invoice and so on) is applied on every page the same way. Limits: wording assembled from values ("Owner: Ann", "5 students"), lowercase status words, dates' month names and anything a person typed stay as they are; the translations are machine-made and need a native speaker's review before a client relies on them. To find new untranslated wording run `python scripts/i18n_extract.py out.json` from `frontend/`; to add translations put them in the phrase files (`scripts/i18n_merge.py` merges and checks batches).
- **Personal choice.** Everyone can pick their own language from the globe button in the header or on the sign-in page. It falls back to the school's default.
- **Where currency applies.** Money on every screen, AI answers, fee PDFs and invoice text uses the school's currency. Changing the currency relabels amounts; it doesn't convert them.
- **Code.**
  - Backend lists: `backend/services/core/tenants/localization.py`.
  - Frontend: translation files in `frontend/src/i18n/locales/<code>.json` (a test checks they all have the same keys).
  - Use `t('…')` from `react-i18next` for new text, and `cur()` / `formatMoney()` from `@/utils/currency` for money.
- **Status.** Menus, sign-in, signup, dashboard, setup checklist and settings are translated; other screens show English until translated. Have a native speaker review each language before selling in that market.

**Platform owner.** Superusers get **All Schools** in the sidebar (`/platform/schools`): every school with student and staff counts and its admins. A school can be suspended there, after which its users can't sign in. A superuser who belongs to a school sees that school's data on the normal pages. Send `X-Tenant-ID: <school id>` to act for another school through the API.

**Existing data.** The upgrade migration assigns every record that had no school to the school most users belong to, and links superusers without a school to it. Nothing else changes for a single-school installation.

## Future upgrades (pending)

Planned, not built. Full briefs with sizes are in [docs/Future Plan.md](docs/Future%20Plan.md); AI items are under [Pending actions](#pending-actions).

- [ ] **Live bus tracking** (Campus services > Transport). Today transport covers fleet, routes, stops, riders, daily trips, boarding events, family notices, monthly fees and reports, but it has no live location. Plan, about 5 days: (1) the driver's phone sends GPS from a web page and the server keeps only the latest position, (2) a live map and ETA for the office and for families, (3) a once-per-trip "bus is about 10 minutes away" alert, also pushed to phones, (4) a screen to set stop and school coordinates by clicking the map, (5) privacy, offline handling, tests and a labelled demo trip. The ETA, stale-location and alert-once logic can be taken from the SecureCampus project's `bus_eta` service. A native driver app is not planned.
- [ ] **Library phone-camera scanning for librarians** (the library lock, return check and notices are built; this part is not).
- [x] **Stronger controls on what the AI assistant may do**: built (Nov 2026): hash-chained decision trail, a record page and file per decision, two different approvers by default with named delegates, approval tied to a fingerprint of the exact action, one switch that pauses all AI, and an approval policy set by each school. What is **not** built yet is in [Next plan and gaps](#next-plan-and-gaps-ai-governance).

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
- **Privacy.** Phone numbers, emails, CNIC and addresses are masked before any data is sent to the AI provider (turn this off with `AI_SHARE_CONTACT_INFO=true`). Social security numbers, birth dates and health details are **always** masked, including a social-security-shaped number typed into free text; the student ID is sent on purpose so the assistant can refer to a student. Every lookup the AI makes is recorded in the audit log, and each answer is saved with a decision record.
- **Chat experience.** Answers stream in as they're written, with a status such as "Checking attendance…" while the AI looks things up. Also: a stop button, saved chat history (open, continue, delete), copy, 👍/👎 feedback, tables in answers, and voice input/output in English or Urdu.
- **Basic mode.** If no AI provider is configured, or the provider is down, the assistant answers common questions ("fee defaulters", "my attendance", …) with simple keyword matching, under the same role limits.

### Governed AI: school documents and approvals (administrators)

Page: **AI Approvals & Documents** (`/education/ai-governance`). Code: `backend/services/ai/` (`knowledge.py`, `actions.py`, `governed.py`, `governance_api.py`).

- **Answers from the school's own documents (retrieval-augmented).** An administrator adds the handbook, policies or fee rules as text (paste, or load a `.txt` / `.md` file). They are split into passages and searched with keyword ranking (BM25), so this needs no extra service and also works without an AI provider. The assistant names the documents it used ("Sources: ...") and says so when nothing matches. Each document has an audience (everyone, staff only, administrators only) that is enforced on the server by role and school, and one school's documents are never searched for another. Passages are given to the model as reference text, not instructions. *Not built yet: PDF upload and meaning-based (embedding) search.*
- **The assistant can only ask; a person approves.** Actions are registered in code (`actions.py`), each with who may ask, who may approve and its own checks. Today there are three: send a fee reminder for one unpaid invoice (the same email as the fee office's button), open a student support case, and tell the counsellors about a risk finding. The reminder and counsel can also be asked for from the risk forecasts table (**Request reminder**, **Counsel**); both only create a request. Nothing is sent or opened until approval.
- **Two different approvers by default.** The person who asked never approves; a school can name delegates (for example a second in command) or lower the rule to one approver (AI settings). A school with a single administrator must add a second.
- **Two checks before anything runs.** (1) *Is it still the exact action asked for?* A SHA-256 of the action, school and arguments is written into the trail at request time and compared again; an edited request does not run. (2) *Is it still allowed now?* Roles, eligibility, expiry (two days) and today's data (for example the invoice is still open) are checked again. The first never replaces the second.
- **Intent saved, outcome honest.** The last approval saves one row per request under a unique key, commits, and only then runs the action. Outcomes: done, not done, or **unknown** (attempted, result could not be confirmed). Unknown is not retried by itself; asking again is a new decision. Exactly-once delivery is **not** claimed (see the gaps below).
- **Decision records.** Each approval has a **Decision record** (provider, model, instruction fingerprint, what was asked, the data sent after masking, controls on at the time, every approval with name and time, and whether the trail verifies; downloadable as JSON). The **Decision records** tab lists assistant answers, risk-flag reviews, approval steps and setting changes (administrators only).
- **Switches.** *All AI* in AI settings stops the assistant, the risk scoring and its flags for the school (the change is itself recorded). Face recognition is off until a school turns it on.
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

- **Risk scan** (admins): scores each student's dropout and fee-default risk. Results appear as "At-Risk Students" on the Analytics page. The scores are **fitted to written scoring rules, not learned from recorded outcomes**; they are advice for staff and have not been validated against real outcomes. A **model card** (Reports > AI Risk & Review) states the rules, the inputs, the library versions and a first look at flag rates by group; every scan is recorded with its version. The scan needs the ML packages, so it is **not switched on in the free hosted demo** (it says so); it runs in the full build.
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
| `AI_PROVIDER` | *(empty)* | `openai`, `anthropic` or `gemini`. Empty = whichever key is set (OpenAI first). |
| `OPENAI_API_KEY` | — | Enables OpenAI. |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model. |
| `ANTHROPIC_API_KEY` | — | Enables Claude (default model `claude-sonnet-5-5`). |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | — / `gemini-flash-lite-latest` | Enables Gemini through Google's OpenAI-compatible endpoint. Keys go in `backend/.env` only, never in `.env.example`. The free tier is for sample data only. |
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

- [ ] **Main AI provider:** OpenAI or Claude. Current behaviour: OpenAI if its key is set, otherwise Claude (`claude-sonnet-5-5`), otherwise Gemini.
- [ ] **Model choice:** a cheaper "fast" model for chat and a stronger "smart" model for lesson plans and grading.
- [ ] **Monthly AI budget:** overall and per school.
- [ ] **Where heavy ML runs:** a separate paid Render worker, a scheduled job, or dropping face recognition for now. The ML packages are not installed on Render today.
- [ ] **Parent message languages:** English, Urdu, or Roman Urdu.
- [ ] **Data sent to the AI provider:** contact details are masked by default. Confirm what else must never be sent.
- [ ] **Knowledge-base search:** allow `pgvector` on the Render Postgres database.

#### Not finished from the current work

- [x] Gemini support (OpenAI, Claude and Gemini are built).
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
- [x] Privacy note for schools, per-school AI opt-out, and a retention rule for saved AI chats (Settings > Security; see [docs/CLIENT_READINESS.md](docs/CLIENT_READINESS.md)).

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

## Next plan and gaps (AI governance)

The working ledger, with the owner's decisions, is [docs/AI_GOVERNANCE_GAPS.md](docs/AI_GOVERNANCE_GAPS.md).

**Built since the first governance build (Nov 2026):** the text-message duplicate check is now a database rule (a second row with the same key is refused, so two requests arriving together cannot both send); a person can settle a request whose result could not be confirmed (**It was done / It was not done**, with what they checked, recorded in the trail); risk model files are saved with a signature and loaded only when it matches (a swapped file is not run); `verify_audit_chain --keep-file` keeps the newest hashes outside the database and next time catches a whole chain rewritten in step; the sample school is smaller (83 students, four weeks of attendance).

**Not built, in the order to do them:**

1. **Deploy** the governance build to the hosted demo (Neon + Render + Vercel): new migrations (audit 0005, ai 0003 to 0005, analytics 0003, communication 0008). The demo is shared with another client, so only on the owner's go-ahead, then a smoke test.
2. **Walk it through in a browser** as an outsider would, and test the new migrations on Postgres (needs Docker running or a throwaway Neon branch).
3. **Provider idempotency key and delivery lookup** so an "unknown" outcome can be settled by the system. Email and SMS here offer neither, so a person settles it.
4. **Run the keep-file check on a schedule** and store the file somewhere the database administrator cannot change.
5. **A model registry** (versions, who trained what, approvals) beyond signed files.
6. **Real validation of the risk scores**: outcome data, a fairness and validation study. Until then every outside statement says "fitted to written rules".
7. **Provider and legal terms** for real student data (zero-retention terms, a data-processing agreement, a privacy policy). The free Gemini tier must not be used for real data.
8. **Four older tests fail on their dates** (insights x2, absence rate, behaviour follow-ups): they assume it is early October 2026 or the start of a month. They need a clock-freeze fixture; not caused by the AI work.
9. **Not claimed and not built:** independent security audit or penetration test, certification (SOC 2 or similar), single sign-on, OneRoster and district imports.

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