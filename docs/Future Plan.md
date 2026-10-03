# CC-EMS Future Plan: developer briefs

Each numbered brief (P1, P2, ...) is one task for one developer. Read **Part A (rules for everyone)** first, then your brief.

When you finish, update your row in **Part E (tracker)** and hand the work over for review. We check every task against its
**"Done when"** list, so build to that list.

Estimates are working days for a mid-level developer who knows the codebase, including screens and tests:
**with Claude Code / without AI help.** Add 3-5 days if you are new to the repo, and about 20% for review rounds.

**Status labels:** **New** = nothing like it exists. **Extend** = part exists; the brief says what, so do not rebuild it.

---

## Part A. Rules for everyone

### A1. Where things live

| Thing | Location |
|-------|----------|
| Backend apps | `backend/services/education/<app>/` (school features), `backend/services/core/<app>/` (platform). Use `education/hr/` as the template for a new app: models, serializers, views, `urls.py`, `migrations/`, management commands. |
| Multi-tenant data | Every school-owned model inherits `TenantScopedModel`. Register new models in `backend/services/core/tenants/registry.py`. Never query across schools. |
| Frontend pages | `frontend/src/pages/education/<area>/`, API calls in `frontend/src/services/<area>.service.ts` |
| Menus and routes | `components/layout/Sidebar.tsx` (menu), `components/layout/moduleTabs.ts` (tab bars), `App.tsx` (routes, wrap in `RoleBasedRoute`), `config/searchPages.ts` (search), `types/permissions.ts` (permissions) |
| Notifications | `backend/services/core/user_notifications/`; SMS/WhatsApp in `education/communication/texts.py` |
| Data pack (import/export) | `backend/services/education/imports/kinds_*.py`, registered in `specs.py`. See `docs/DATA_PACK_SPEC.md`. |
| Audit log | `backend/services/core/audit/`; screen at **Security & privacy, Activity log** (`/settings/security?tab=activity`) |
| User guide | `docs/USER_MANUAL.md` |

### A2. Every task must have all of this

1. **Research first.** Search the code for what exists before writing. Many "new" features already have a piece (noted in each brief).
2. **A real screen.** Reachable by clicking in the app. A backend endpoint alone is not done.
3. **Roles and permissions.** Decide who sees and who changes. Parents see only their own children; teachers see only their classes unless the brief says otherwise. Enforce on the **server**, not only by hiding menu items.
4. **Tenant safety.** A school never sees another school's data. Add a test that proves it.
5. **Tests you ran.** Backend `backend/tests/test_<feature>.py`; frontend a vitest test for the main screen. Paste the passing output in your hand-over.
6. **Empty and loading states.** Every list has a friendly "nothing here yet" message and a loading state.
7. **Import/export.** If a school would want to move or restore the records, add a data pack kind (A1). If not, say why in the hand-over.
8. **Docs.** Add the screen to `docs/USER_MANUAL.md` (where to click, who sees it).
9. **Quiet history loads.** Importers and seeders set `obj._silent = True` so loading history sends no notifications. Respect that in every signal you add.
10. **Fix blockers, flag the rest.** If an existing bug blocks your task, fix it and say so. Report unrelated bugs in the hand-over instead of fixing them.
11. **Sensitive data** (health, pickup, special needs): only the roles named in the brief may see it, and every view and change is written to the audit log.

### A3. How to run things

* **Backend tests** (SQLite, no Postgres needed):
  `cd backend` then `USE_SQLITE=1 DEBUG=1 python -m pytest tests/test_<feature>.py -q --no-cov -p no:cacheprovider -o addopts=""`
* **Migrations.** The shared dev Postgres has a broken migration history, so generate migrations on a throwaway SQLite file:
  `USE_SQLITE=1 DEBUG=1 SQLITE_PATH=$TEMP/x.sqlite3 python manage.py makemigrations <app>`, then delete the file. Check with `makemigrations --check --dry-run`.
* **Frontend:** `cd frontend`, then `npx tsc --noEmit -p tsconfig.app.json`, `npx vitest run <path>`, and `npm run build` must pass.
* **The full backend suite** rewrites `ai-ml/predictions/*_default.pkl`. Run `git checkout -- ai-ml/predictions` afterwards.
* **Local demo:** `demo.bat` (ports 8009 and 5179). Sample school: `python manage.py seed_demo --pack us-school`.

### A4. Working agreement

* One branch per task, named `feature/<short-name>`. **Do not push to `main` and do not touch the live demo** (Render and Vercel). The demo stays frozen until the project owner decides to update it.
* Small commits. Say in the hand-over what changed, what you tested and what you left out.
* If a brief is unclear, ask before building a guess.
* Two developers must not edit the same app at the same time without telling each other.

### A5. Hand-over note (copy into your pull request)

```
Task: <ID and name>
What I built: <3-5 lines>
Where to click: <menu path, which role to log in as>
Tests run: <command and result>
Import/export kind added: yes / no (why)
Docs updated: USER_MANUAL.md section <x>
Left out on purpose: <list>
Bugs found elsewhere (not fixed): <list>
```

---

## Part B. Foundation work (done by the project owner, not the developers)

These are being done first. Developers can start before they finish, but briefs marked **needs F2** use the scheduler.

| ID | Task |
|----|------|
| F1 | Make every GitHub check green (backend tests, frontend CI, CodeQL, npm audit) |
| F2 | Register the daily/hourly jobs (including the new HR jobs `send_hr_alerts` and `refresh_cover`) in the existing scheduler, with a list of last-run results |
| F3 | Split the 3.5 MB frontend bundle |
| F4 | Written hosting runbook for a real pilot (paid database with backups, always-on backend, Redis) |

---

## Part C. First phase: briefs

Build in this order. Items marked ✔ at the end of Part D are already built and are **not** tasks.

### P1. Visitor sign-in and safe pickup
* **Status:** Extend. `StudentGuardian.can_pickup` exists (`education/students/models.py`). There is no extra authorised-adult list, no release log and no visitor log.
* **Goal:** know who may collect each child, record who did, and record every visitor.
* **Build:**
  * Pickup list per student: guardians with `can_pickup` plus extra authorised adults (name, phone, photo, ID checked), and a **do-not-release** flag with a court-order note.
  * Front-desk screen **Pickup**: search student, pick the adult, confirm photo/ID, press **Released**. Early dismissal records time and reason.
  * Visitor screen: sign in (name, who they visit, purpose, badge number), sign out, **On site now** list for emergencies, printable.
  * New permission "front desk" for office staff.
* **Data:** `AuthorizedAdult`, `PickupRelease`, `VisitorLog`.
* **Rules:** a do-not-release adult cannot be released (hard stop; admin override needs a typed reason and is audit-logged). Logs are kept for a configurable number of years.
* **Done when:** releasing to an unlisted adult is blocked; the do-not-release flag stops a release; the On-site list is correct after sign-in and sign-out; a teacher cannot see court-order notes; tests cover all of these. **Estimate:** 4-5 / 7-9 days.

### P2. Health office: visit log, medication log, immunisation reminders
* **Status:** Extend. `StudentHealth` (allergies, conditions, medication) and `Immunization` exist and show on the student's **Health** tab. There is no visit or administration log and no reminders.
* **Goal:** the nurse records each visit and each dose given; parents are told automatically.
* **Build:**
  * New permission/role "nurse". Page **Health Office**: quick student search, **New visit** (time in/out, complaint, action taken, sent home yes/no), **Give medication** (drug, dose, time, given by, chosen from the student's authorised medications).
  * Parent notification on each visit (setting: always / only if sent home).
  * The student's Health tab shows the visit history.
  * Immunisation due-date reminders to parents (**needs F2**).
* **Data:** `HealthVisit`, `MedicationAuthorization` (drug, dose, times, start/end, parent consent), `MedicationLog`.
* **Rules:** visible to nurse, admin and the child's parents only. Medication can only be logged against an active authorisation; a second dose too soon shows a warning and needs a typed reason.
* **Done when:** a teacher cannot open any health record; an out-of-window dose is blocked without a reason; the parent notice sends once; the audit log shows who viewed what. **Estimate:** 3-4 / 6-7 days.

### P3. Safety incident reports with follow-up
* **Status:** New. Behaviour records are conduct, not safety. **Do not reuse the name `Incident`**: `core/privacy/models.py` already has an `Incident` model for data-breach handling. Call yours `SafetyIncident`.
* **Build:** report (date, place, people involved, type: injury, bullying, property, other; description; witnesses; action taken); severity; follow-up tasks with owner and due date; status open / in follow-up / closed; parent notification option; attachments.
* **Rules:** reporter and admin see it; students involved are visible only to admin and counsellor; closing needs a note.
* **Done when:** a follow-up task past its due date shows as overdue; a closed incident cannot be edited without reopening; tests cover permissions. **Estimate:** 3 / 5 days.

### P4. Permission slips and e-signature forms
* **Status:** New.
* **Goal:** the school publishes a form (field trip, photo consent, medical consent); each family signs online; staff see who has not.
* **Build:**
  * Admin builds a form: title, body, questions (yes/no, text, choice), audience (a class, a grade, everyone), due date.
  * Parents see it under **Documents** and as a notification, and sign by typing their name plus a tick box. One response per child.
  * Admin/teacher tracker: signed, not signed, declined; **Remind** button; export to CSV and PDF.
  * Each signature stores who, when, and the exact text version signed.
* **Data:** `FormTemplate`, `FormAssignment`, `FormResponse`.
* **Rules:** a signed response cannot be edited; a changed form creates a new version; only a guardian linked to that student may sign.
* **Done when:** a trip form sent to Grade 5 reaches only Grade 5 families; a guardian signs only for their own child; the tracker counts match; Remind goes only to unsigned; tests cover wrong-guardian and edited-form cases. **Estimate:** 4-5 / 7-9 days.

### P5. Admissions: automatic waitlist offers, tours, documents, application fee
* **Status:** Extend. A waitlist status, the online form and `StudentDocument` exist. Do these as four small tasks.
  1. **Waitlist offers.** Capacity per grade/year; rank rule (date, sibling priority, staff child); when a seat opens the top applicant gets an offer with a deadline; if declined or expired the next is offered (**needs F2**). 3-4 / 6-7 days.
  2. **Tours and interviews.** Admin publishes slots; the family books from the application link; reminders. 3 / 5 days.
  3. **Document checklist.** Admin lists required documents; family uploads; staff mark received / redo; reminders for missing items; documents move to the student's Documents tab on enrolment. 3-4 / 6-7 days.
  4. **Application fee.** Optional fee on the online form, paid through the existing Stripe gateway; the application is held until paid. 2 / 4 days. Needs a Stripe account.
* **Done when:** a declined offer moves to the next applicant exactly once; capacity never goes below zero; documents appear in the applicant's file; a successful fee marks the application paid and a failed card does not. **Total:** 11-13 / 21-25 days.

### P6. Installable app and push notifications
* **Status:** New. No web app manifest, no service worker and no push code today.
* **Build:** PWA (manifest, icons, service worker with an offline shell), web push (VAPID keys from environment variables), device registration under **Account Settings**, and push as another channel in `user_notifications`. Optional phase 2: wrap in a store app.
* **Rules:** push is opt-in; each notification type can be turned off; iOS works only when installed to the home screen (document this).
* **Done when:** it installs on Android and iOS; a notification arrives with the app closed; turning it off stops delivery. **Estimate:** 6-8 / 10-14 days.

### P7. In-app guided tour
* **Status:** New. The dashboard has a setup checklist but no tour.
* **Build:** a first-login walkthrough per role, based on `docs/USER_MANUAL.md`, with **Help, Take the tour** to replay it. Skippable; remembers it was seen.
* **Done when:** each role (admin, teacher, parent, student) gets its own steps; skipping works; no step points at a page the role cannot open. **Estimate:** 2 / 3-4 days.

---

## Part D. Later items and the status of every suggested feature

### D1. Later briefs (build when a client asks)

* **IEP/504 plans (New).** Plan per student (type, dates, goals, accommodations, services, case manager), an **Accommodations** banner visible to that student's teachers (never the full plan), review-due reminders (needs F2). Full plan visible only to case manager, admin and guardians; every view is audit-logged. Build against a real district's needs. 5-6 / 9-10 days.
* **Scheduled email reports (New).** Pick a report, schedule, recipients, format (PDF/Excel). Needs F2. 1-2 / 2-3 days.
* **Dashboard drill-down (Extend).** Export exists. Add click-through from a chart to its rows. 3-4 / 5-7 days.
* **Duty swaps (Extend).** Bus-duty and till roles exist. Add a duty rota (lunch, recess, car line) and swap requests approved by a manager; respect leave and teaching load. 4-5 / 7-9 days.
* **Outside substitute pool (Extend).** Cover requests exist for staff only. Add on-call outside substitutes with availability and subjects; offer cover to them when no qualified staff are free. 3-4 / 5-7 days.
* **Automatic sibling and staff-child discounts (Extend).** Today it is a manual credit note. Add rules applied automatically by family. 1-2 / 2-3 days.
* **Cafeteria pre-orders (Extend).** Allergy warnings at the till exist. Add pre-orders from the parent portal. 3-4 / 5-7 days.
* **Lesson-plan library (Extend).** The AI planner makes one plan at a time. Add sharing between teachers: copy, search by subject/grade/tag. 3 / 5 days.
* **Standards charts for parents (Extend).** Add progress-against-standards charts per child on the parent portal. 3 / 5 days.
* **Student portfolio (New).** 3 / 5 days.
* **Timesheets and overtime (New).** Clock-in time tracking feeding payroll (payroll itself exists). 3-4 / 5-7 days.
* **Professional-development hours (New).** 2-3 / 4-5 days.
* **Offboarding checklist and exit interview (New).** Reuse the HR onboarding checklist. 2 / 3-4 days.
* **Year-end family statements and tax receipts (New).** 2-3 / 4-5 days.
* **Department budgeting (New).** 4-5 / 7-9 days.
* **OneRoster-style district import (New).** Only when a district asks. 4-5 per system / 7-9.
* **Facility booking and maintenance tickets, event ticketing, bus GPS tracking (New).** Only when a customer asks. 4-5, 5-6 and 8-12 days with Claude Code.
* **Multi-campus (Built in a different shape).** Today each school is separate and the platform console manages many schools. Clarify with the client whether they mean several buildings sharing one roster before any work; that would be 10-15 days plus a design review.

### D2. Already built: do not rebuild

Verified against the code on 2 Oct 2026.

| Feature | Where |
|---------|-------|
| Parent-teacher conference booking | `MeetingsPage.tsx`, `MeetingSlot` in `schoolcalendar` |
| Message and announcement translation | `messaging.service.ts`, `communication/inbox.py` |
| Automatic absence, late and frequent-absence alerts | SMS/WhatsApp in `communication/texts.py` |
| Emergency broadcast (pinned announcements with delivery report) | Announcements |
| Online card payments, saved cards, auto-pay, refunds | Stripe gateway in `finance/payments`, `finance/billing.py` |
| Late-fee rules and reminders | Fees |
| Scholarships and financial aid | `Scholarship`, `StudentScholarship` |
| Inventory reorder alerts | `reorder_level` and the `/reorder/` list |
| Cafeteria allergy warnings at the till | `cafeteria/api.py` |
| Plagiarism check | `PlagiarismCheck.tsx` |
| Audit log viewer | **Security & privacy, Activity log** |
| Google and Microsoft sign-in | Sign-in page |
| Data retention and deletion | `core/security/retention.py`, nightly job, off by default |
| Encrypted backups and monthly restore test | `core/backup` |

Live restore from inside the app is **deliberately not built**. Restoring over live data should stay a server command.

**Items to double-check before relying on them** (the audit marks them built; the reviewer saw only part): late-fee rules (an invoice `late_fee_amount` field exists; confirm the rules), Stripe end to end in test mode, and Microsoft sign-in.

---

## Part E. Tracker (update as you go)

Statuses: Not started, In build, In review, Changes needed, Accepted.

| ID | Task | Owner | Status | Branch / PR | Reviewed by | Notes |
|----|------|-------|--------|-------------|-------------|-------|
| P1 | Visitor sign-in and safe pickup | | In review | | | Reworked after review: tenant-safe, do-not-release hard stop, audit, 18 backend + 6 frontend tests. Not yet clicked through in a browser. Retention years for these logs not built. |
| P2 | Health office | | In review | | | Reworked: nurse/parent access, dose rules, parent notice, audit, immunisation reminder job (needs F2), 16 backend + 5 frontend tests. Notice setting ("always" / "only if sent home") has no screen yet. |
| P3 | Safety incident reports | | In review | | | Reworked: reporter/reviewer views, follow-up, close/reopen rules, owner picker, 16 backend + 3 frontend tests. File attachments not built. |
| P4 | Permission slips and e-signature | | In review | | | Rebuilt: versions, final signatures, tracker, reminders, CSV export (no PDF), 16 backend + 4 frontend tests. |
| P5a | Waitlist offers | | In review | | | Rebuilt and tested (25 backend tests cover all of P5). Expiry needs `admissions_daily` scheduled (F2). |
| P5b | Tours and interviews | | In review | | | Family booking page and staff tab built. |
| P5c | Document checklist | | In review | | | Review states, family re-upload, weekly reminders, documents move to the student on enrolment. |
| P5d | Application fee | | In review | | | Tested with a mocked Stripe and signed webhooks only. Needs a live Stripe test-mode run and the `online_payments` switch checked (see Part H). |
| P6 | Installable app and push | | In review | | | Real icons, safe service worker, subscribe/preferences/delivery, 16 backend + 6 frontend tests. Needs VAPID keys and a test on a real Android and iPhone. |
| P7 | Guided tour | | In review | | | Per-role tours, remembered per person, replay from Help. 9 backend + 8 frontend tests. |
| D1 | Each later item | | Not started | | | one row per item when assigned |

**Suggested split for two developers:** one on health and safety (P2, P3, P1); one on families and admissions (P4, P5, P6, P7).

## Part F. How we review

For each task handed over we will:
1. Read the hand-over note and compare the branch with the brief's **"Done when"** list.
2. Run the feature's backend test file and the frontend type check, tests and build.
3. Log in locally as each role named in the brief and click the path, including failure cases (wrong role, wrong school, empty state, double-click).
4. Check that the import/export decision, the user manual entry and the audit logging are present.
5. Mark the row **Accepted**, or **Changes needed** with a short list.

## Part G. Review of the first submission (3 Oct 2026)

The first submission said "all seven accepted". Checking it against the code and the "Done when" lists found the work was
a partial backend skeleton, so it was rebuilt. What was wrong, and the state now:

| Found | Now |
|---|---|
| Every new endpoint used `request.user.school`, which does not exist, so list screens crashed with server errors | Replaced with the repo's tenant mechanism; new models are registered in the tenant registry |
| Pickup and visitor logs could be read across schools; three safety models were not tenant-scoped | Tenant-scoped, with cross-school tests for every area |
| The do-not-release rule was not enforced anywhere | Hard stop on the server; administrator override needs a typed reason and is audited |
| No role checks beyond "signed in": a parent could list every incident | Per-area roles (front desk, nurse, counsellor, reporter, parent) enforced on the server, with tests |
| Frontend screens used a UI library the app does not have, were not routed, and one never existed | Rebuilt in the app's own stack, routed, in the menus and search |
| Push: wrong library calls, keys written into the repo folder, wrong URLs, worker never registered, icons missing | Keys from environment, correct URLs, worker registered, real icons |
| No tests, no manual entries, no audit logging | Tests for every area, manual updated, sensitive reads and changes audited |

## Part H. Open items and cautions

* **Run the daily jobs (F2).** Schedule `python manage.py admissions_daily` and `python manage.py send_immunization_reminders` once a day, alongside `send_hr_alerts` and `refresh_cover`.
* **Push needs keys.** Run `python manage.py generate_vapid_keys` and set `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_CONTACT` on the server. Also set `FRONTEND_URL` so emails link to the family page.
* **Stripe webhook switch.** The Stripe webhook URL sits behind the school's `online_payments` feature switch, which is looked up by school, and Stripe's call has no school. Confirm in staging that webhooks arrive (invoices and application fees both use it).
* **Roles.** `front_desk`, `nurse` and `counsellor` are named roles. Create a role with that name and give it to the person; they land on their own tool after sign-in.
* **Import/export.** No data pack kinds were added for these records: they are logs and signatures rather than set-up data. The authorised-adults list is the one candidate if a school wants to bulk-load it.
* **Not built, by design or for later:** retention years for pickup and visitor logs, PDF export of form results, incident file attachments, a screen for the health notice setting.
* **Not yet done:** a click-through on a real browser and phone for every screen, and a full run of the backend and frontend suites after the final changes.
