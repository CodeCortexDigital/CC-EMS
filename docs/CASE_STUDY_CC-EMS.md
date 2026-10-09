# CC-EMS: a multi-tenant school ERP with role-aware AI

*Case study for the Code Cortex website. Every claim below can be checked in the code or the live demo.*

## The problem

Schools run on a patchwork: one tool for attendance, a spreadsheet for fees, a messaging app for parents, a separate HR file. Data is duplicated, families get several logins, and nobody can ask a plain question such as "which students are slipping?" without exporting three files.

We set out to build one system that covers a whole school, can serve many schools at once without ever mixing their data, and uses AI only where it saves staff time, always as a draft a person approves.

## What we built

**CC-EMS** is a SaaS school management system. A US sample school (Maple Grove Academy, K-8) is live as a demo.

- **Academics:** gradebook with weighted categories, letter, percentage or standards scales and GPA; report cards and transcripts; a rules-based timetable generator with preview and undo; exams; lesson planner.
- **Families and students:** household-based accounts, several guardians per child, admissions with a waiting list and offers, immunisation reminders.
- **Operations:** fees and payments, payroll, HR and substitute cover, library, transport, inventory, cafeteria.
- **Safety:** authorised pickup list with a do-not-release stop, visitor book, nurse visits and medication log, incident reports, permission slips.
- **Student support:** configurable absence steps, a counsellor's intervention queue, chronic-absenteeism reporting.
- **AI, as drafts:** report-card comments, lesson plans with standards, rubric drafts, family-message drafts, message summaries with suggested replies, on-demand translation, written summaries of school figures, early-warning scores.
- **Platform:** four subscription plans, trials, limits and read-only mode; a platform owner console.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python, Django 5, Django REST Framework, Daphne (ASGI) |
| Data | PostgreSQL; SQLite for local development and tests |
| Background work | Celery with Redis (scheduled jobs: reminders, alerts, risk scans) |
| Frontend | React, TypeScript, Vite, Tailwind CSS; installable PWA |
| AI | Provider-neutral layer for OpenAI or Anthropic Claude, with per-school switches and monthly limits |
| Integrations | Stripe payments, Twilio SMS and WhatsApp, push notifications |
| Quality | pytest and Vitest suites, CI on every push, dependency scanning |

## The hardest problems, and how we solved them

### 1. Tenant isolation
Many schools share one database, and one school must never see another's records.

- Every school-owned record carries its school. A registry lists each model and how it reaches its school, including records that only reach it through a parent record.
- Every query is filtered to the signed-in school automatically, and writing a record that points at another school's data is refused.
- Automated tests sign in as a second school and try every list endpoint, plus targeted tests for the sensitive paths (report cards, transcripts, health records, pickup release).

### 2. AI that respects roles
A parent asking "how is my child doing?" must only ever reach their own children's data, even through an AI.

- The assistant's tools run under the asking user's role and school, so the same permission checks apply as in the screens.
- Contact details are masked before record data goes to the model provider.
- Everything the AI writes is a draft: nothing AI-written is sent or saved without a person acting, and the AI never decides grades, admissions or discipline.
- Each school can switch each AI feature off, accept an AI-use notice, and is subject to monthly usage limits.
- Without a provider key every feature falls back to a plain template and says so, rather than pretending.

### 3. Getting a school's data in (and out)
Schools arrive with years of records in spreadsheets.

- A CSV data pack imports students, families, staff, classes, fees and history through one engine, with validation and duplicate checks, and the same engine exports and restores a school.
- Historic imports are "silent": loading ten years of invoices does not email every family.
- A test rebuilds the sample US school from its spreadsheets and fails if the sample data and the generator drift apart.

## Where it stands

CC-EMS is early-stage. It was built and tested with a school in Pakistan, and the US mode and the Maple Grove demo are tested with sample data only. We are looking for design-partner schools.

## Try it

The live demo shows one-click demo accounts for an administrator, a teacher, a parent and a student on its sign-in page.

*Contact: Azhar, Founder & CEO, Code Cortex. ceo@codecortexdigital.com*
