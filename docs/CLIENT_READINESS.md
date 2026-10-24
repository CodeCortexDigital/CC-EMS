# CC-EMS: privacy, school isolation and AI review (client readiness)

Checked on 24 Oct 2026 against the questions a careful education client asks: school isolation, retention and deletion, human review of AI,
who built what, documentation and ownership. Every line below names the code or the test that shows it. Where something is not built, it says so.

**Status in one sentence:** an early-stage product, tested on sample data (a sample US school), with the controls below built and covered by automated
tests. It has not had an independent security audit and is not certified for any standard.

## 1. Tenant (school) isolation

| What | How it works | Evidence |
|---|---|---|
| Every school's data is filtered to that school on the server | The school comes from the signed-in person, never from the browser. Models are listed in `backend/services/core/tenants/registry.py` and filtered automatically on read, and stamped and checked on write. | `tests/test_tenant_isolation.py`, `tests/test_school_isolation_sweep.py` |
| A new model cannot be added without a decision | A test fails if any model with a link to a school is neither in the registry nor on a reviewed list with the reason it is safe. | `test_every_model_with_a_school_link_is_filtered_or_reviewed` |
| Student numbers and staff IDs cannot collide between schools | Each school's own code is put in front (`ABC-STU0001`) and each school numbers from 1. | `tests/test_two_school_ids_and_logins.py` |
| Cross-school probing is tested | Tests sign in as school B and try to read, change and delete school A's records. | the files above, `tests/test_governed_ai.py` |

**Found and fixed by this check (24 Oct 2026):** employee tasks, timesheets and HR documents were not filtered by school, so an administrator of one
school could list another school's rows, and the detail pages did not work. They are now filtered, a non-administrator sees only their own, and an
administrator can only assign work to someone in the same school. Earlier fixes in the same area: the finance and student-record leaks in `7721fc9`.

**Limits:** isolation is by school column and server-side filtering in one shared database, not separate databases or schemas. It is tested on sample data;
no independent penetration test has been done.

## 2. Retention and deletion

| What | How | Evidence |
|---|---|---|
| Each school chooses how long each kind of record is kept | Settings > Security (Retention). Nothing is removed until the school sets a period, with a minimum for each kind. A preview shows what each rule would remove before it runs. Run daily by `apply_retention`. | `backend/services/core/security/retention.py` |
| Kinds covered | Students who left or graduated (anonymised), declined admission applications, conversations, announcements, delivery logs, attendance alerts and absence notes, paid invoices (at least 5 years), **AI assistant chat history**, **decided AI action requests**. Daily briefs keep about three months by design. | `tests/test_client_trust.py::TestRetentionIncludesAI` |
| A copy of one person's data (a "see my data" request) | From a privacy request, the office downloads a file holding the student's record and every table that points at them (found from the database's own relations, so a module added later is covered). Passwords, tokens and keys are never written; files appear by name only. Logged. | `privacy/subject.py`, `TestCopyOfAPersonsData` |
| Erasing one person's data (an "erase my data" request) | A preview lists exactly what will be removed and what is kept without a name. The office types the student's ID to confirm. Name, contacts, ID numbers, address, health notes, documents, face template, AI risk scores and portal login are cleared; guardians with no other child here too. Marks, attendance and invoices stay without a name so school statistics and accounts add up. The request is closed with a reply, and the erasure is in the audit log (without the name). | `privacy/api.py::request_erase`, `TestErasure` |
| Privacy requests are tracked with a 30-day clock | Access, correction, restriction, erasure and objection requests, with overdue warnings. | `core/privacy/models.py` |
| Consent, privacy notice, sub-processor list, incident register | Consent questions per school; versioned privacy notice people must accept; a published list of companies that handle data; a record for reporting a security or privacy problem with the 72-hour clock. | `core/privacy/` |

**Limits:** deleted data can still sit in backups until the backup expires (the backup schedule is set by the school or host). Retention does not yet cover
every kind of record (for example library, transport and visitor logs); those can be exported or removed through the data pack or by hand. Legal retention
periods differ by country; the school sets them with its own adviser.

## 3. Human review of AI

| What | How | Evidence |
|---|---|---|
| AI output is a draft | Drafts (lesson plans, messages, report comments, briefs) are shown to a person, who edits and sends. Nothing the AI writes is sent automatically. | README "AI Features" |
| The AI assistant cannot change anything | It can only ask. An asked action is stored as a pending request and runs only after an administrator approves it. Approver and requester roles are checked again at approval. Everything is audited. | `services/ai/actions.py`, `tests/test_governed_ai.py` |
| AI risk scores need a person | Scores are labelled **advice only**. Each high or critical flag lists the reasons and waits for a person to choose "worth acting on", "need more information" or "not a concern", with a reason; the decision, who and when are recorded and audited. A new scan that moves a student to a different level clears the old review. No decision about a student is made by the score alone. | `analytics/ai_views.py::review_student_risk`, `TestHumanReviewOfAIRiskFlags`, panel on Reports > AI Predictive Analytics |
| What the AI sees | Daily briefs and their AI summaries use counts only, with no names. Phone numbers, emails and addresses are masked before data goes to an AI provider (switchable). Every AI lookup is audited. | `briefs/metrics.py`, `ai/tools.py` |
| AI answers from the school's own documents | Administrators add policies; the assistant quotes them and names the document. Each document has an audience, enforced on the server, and no school can search another's. | `services/ai/knowledge.py` |
| Schools can turn AI off | Per school, per feature (the school's AI settings). Without an AI key the app runs in a plain mode. | `services/ai/settings_api.py` |

**Limits:** the risk models are simple (random forest, logistic regression, XGBoost) and trained on the school's own history; with a small or new school the scores
are weak. There is no bias or fairness testing yet. The records of a review show a decision was made, not that it was a good one. A risk flag that is high
still opens a to-do for a counsellor (a task for staff, not an action on the student).

## 4. Security basics that are built

Role-based access enforced on the server by area (admin, accountant, teacher, parent, student, and named roles front desk, nurse, counsellor, manager, HR);
an audit log of sensitive reads and changes; two-step sign-in; sign-in history; secrets read from the environment, not stored in code; encrypted backups
with restore; rate limits on sign-up and on AI use; the cross-school and same-school record-access fixes listed in the git history. Not done: an independent security audit,
penetration test or certification.

## 5. Documentation, compatibility and ownership

* **Documentation in the repository:** `README.md`, `docs/USER_MANUAL.md`, `docs/Future Plan.md`, `docs/DISASTER_RECOVERY_PLAN.md`, `docs/KEY_ROTATION.md`,
  `docs/DATA_PACK_SPEC.md`, backend and frontend structure notes, and this file. Help articles are built into the app.
* **API documentation:** generated OpenAPI with Swagger and ReDoc at `/api/docs/`, versioned `/api/v1/` and `/api/v2/`.
* **Compatibility:** React, Django REST and PostgreSQL. Data comes in and out through a documented CSV data pack (students, staff, classes, fees and more),
  a technical export, and the REST API. Email, SMS and WhatsApp (Twilio), web push, Stripe and an AI provider of the school's choice are optional.
  Not built: single sign-on for districts, OneRoster, and a ready-made connector to any particular student information system.
* **Ownership:** a contract matter, not something the code decides. Our standard terms: the client owns the code and documentation written for them and
  receives them in their own repositories; we keep our general tools and know-how. Put it in writing before work starts.

## 6. Who built it, and how we work

*(Owner: confirm each line is true before sending.)* The platform was built by our own small engineering team using AI-assisted development
(Claude Code), with no subcontractors on the core platform. Third-party services it uses: hosting (Render and Vercel in the demo), the database, and the
AI model provider. Engagement model: a small paid milestone first, with a short review of the client's system, one agreed piece of work, written acceptance
tests and a fixed price; anything larger only after that.

## 7. Corrections to earlier sales wording

Do not use these phrases until they are true: "GDPR-ready" (say: designed with privacy in mind, not certified), "14 permission areas" (not verified),
"complete IP handover" (a contract term, see above), and "RAG pipelines, computer vision" as one project's features (the app has keyword-ranked retrieval
over the school's own documents and optional face-recognition attendance, which is not available on the hosted demo).

## 8. Still open (honest list)

* Retention for the remaining kinds of record (library, transport, visitor and health logs).
* Bias and fairness checks for the risk models; a model card page inside the app.
* An independent security review.
* Single sign-on and district-system imports (only when a client asks).
* A tested test-restore of a backup on the hosted demo.
