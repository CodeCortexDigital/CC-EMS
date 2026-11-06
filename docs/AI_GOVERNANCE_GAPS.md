# AI governance build: gaps, status and what to verify

Working ledger for the AI governance build (5 to 6 Nov 2026). Each line is a gap found or a limit we chose, with what must be checked before any claim
about it is made to a client. Nothing here is a promise to a client. Tick a check only after it was done in a real run.

Status key: **Built** (in code, tests written) · **Open** (not done) · **Limit** (a known limit we state honestly) · **Decision** (waiting on the owner)

## A. Audit and decision record

| # | Gap or limit | Status | Verify at the end |
|---|---|---|---|
| A1 | Audit log could be edited or deleted; no proof of tampering | Built: decision records are hash-chained, protected from change and delete (app, admin, cleanup, archive) | [ ] `verify_audit_chain` passes after a full demo run; [ ] migration `audit/0005` applied on Postgres |
| A1b | Audit write failure was ignored and the action still ran | Built: each step is saved with its record or not at all | [ ] stop the audit write in a live run: nothing is sent |
| A1c | Someone who rewrites a whole chain and its newest hash is not caught | Limit: copy the printed newest hash outside the database now and then (nobody is assigned to do this) | [ ] state it in every explanation |
| A1d | Routine audit rows and AI lookup logs are not chained; older rows are not protected | Limit (chosen for speed) | [ ] say "decisions are chained", never "all logs" |
| A1e | AI lookups (`ai.tool.*`) were written without the school | Built: school is now recorded | [ ] |
| A2 | Decision record lacked provider, model, instruction fingerprint, what was sent, controls | Built (`AIActionRequest.record`, hash in the trail; migration `ai/0003`). Model is the configured name, not a provider-pinned version | [ ] one real Gemini request holds all items; [ ] migration on Postgres |
| A3 | No single page or export per decision | Built: "Decision record" on AI Approvals, JSON download | [ ] read it in a browser as an outsider would |
| A3b | Chat answers and risk-flag reviews have no record page | Limit | [ ] decide if needed (see H) |

## B. Controls

| # | Gap or limit | Status | Verify at the end |
|---|---|---|---|
| B1 | No single AI-off switch; risk scan not behind a toggle | Built: master switch, `ai_risk_scan` switch; risk endpoints, model card and the reminder request refuse while off; changes are recorded | [ ] what the Analytics page shows while AI is off (may be a raw error); [ ] timetable and quiz endpoints while off |
| B2 | "Remind" emailed a family on one click | Built: "Request reminder" creates a request for approval; the approved action sends the email (it used to text only) | [ ] click it in a browser, approve as a second person, see the email path with a real address |
| B2a | The old direct reminder endpoint still exists for API callers | Open (see H) | [ ] |
| B2b | "Counsel" notifies staff and opens a to-do with no approval | Limit: internal task, not contact with a family | [ ] say so when demonstrating |
| B2c | One person could ask and approve | Built: the asker can never approve; the school can require two different approvers and can name approvers (migration `ai/0004`) | [ ] two-person run in a browser with two logins; [ ] with only one admin, requests wait (the demo needs a second admin) |
| B3 | Approval flow needed a provider to show | Built: Gemini provider (OpenAI-compatible endpoint); model `gemini-flash-lite-latest` | [ ] one full chat, approval, audit run on Gemini |
| B4 | US identifiers were not masked | Built: SSN, birth date, health details always masked; SSN pattern in free text. Student ID is sent on purpose | [ ] decide whether to also mask the student ID (see H) |
| B5 | Face recognition on by default | Built: off until a school turns it on; endpoints gated | [ ] |

## C. Risk model

| # | Gap or limit | Status | Verify at the end |
|---|---|---|---|
| C1 | Identical scores and 105 of 213 flagged high | Built (partly): fee model uses only the overdue share (no income, no siblings), excused and late days count as attended, list order is stable. On the sample school the count is still 105 because 89 students have overdue invoices in the sample data | [ ] decide the threshold or the sample data (see H) |
| C2 | Models are fitted to written rules, not learned from outcomes | Limit: stated on the model card, in the readiness doc and in the governance doc. **Earlier wording ("trained on the school's own records") overstated this** | [ ] every outside statement says "fitted to written scoring rules" |
| C3 | No bias or fairness study | Limit: model card shows flag rates by gender and class per scan; no study | [ ] |
| C4 | Model version and scan not stamped on scores | Built: each scan is a `RiskScanRun` (migration `analytics/0003`); each score carries the scan id | [ ] migration on Postgres |
| C5 | Education risk scoring is likely high-risk AI under the EU AI Act | Limit: stated; no compliance claim | [ ] wording |
| C6 | Model files are pickles stored next to the code | Limit: not built (signed or isolated store) | [ ] |
| C7 | Anomaly check flags about 15% by design | Limit: stated on the card | [ ] |

## D. Hosted demo (shared with another client, do not disturb)

| # | Gap or limit | Status | Verify at the end |
|---|---|---|---|
| D1 | Risk scan unavailable on the hosted build (ML packages not installed; free tier memory) | Built: clear message ("runs in the full build, not switched on in the free hosted demo") | [ ] email says so |
| D2 | Hosted demo has no AI provider | Limit | [ ] email says so |
| D3 | Pending front-end changes not deployed (login prefill, side-menu default, Excused attendance, all the governance work) | Open: deploy only on the owner's go-ahead. A backend redeploy also runs 4 new migrations on the hosted database | [ ] Vercel and Render builds green; [ ] smoke test; [ ] timing agreed with the other client's review |
| D4 | About 130 rows with no school on the hosted database | Open (optional) | [ ] |
| D5 | Free Render restarts and free Gemini limits can interrupt a live demo | Limit | [ ] run the flow once just before any demo |

## E. Provider and keys

| # | Gap or limit | Status | Verify at the end |
|---|---|---|---|
| E1 | Gemini through the OpenAI-compatible endpoint | Built; direct request with tools worked on the free key | [ ] full chat run; [ ] unit test for the provider choice |
| E2 | The test key was written into a tracked file (never committed) and shown in chat | Owner to rotate | [ ] new key in `backend/.env` only; [ ] `.env.example` holds placeholders only |
| E3 | Free Gemini terms may allow Google to use content | Open: use sample data only; for real student data use a paid tier with terms the school accepts | [ ] |
| E4 | Tests must never use a real key | Built: autouse fixture clears all provider settings in tests | [ ] |
| E5 | Default Anthropic model name (`claude-opus-5`) in the code is unverified | Open | [ ] |

## F. Not built, already in the readiness document (do not claim)

Independent security audit or penetration test · certification (SOC 2 or similar) · single sign-on · OneRoster and district imports · zero-retention provider
terms on file · a real fairness and validation study · signed or isolated model store · retention for library, transport and visitor logs.

## G. Final claims check (last step before sending anything to a client)

- [ ] Every sentence in the client email matches this ledger (the email must say the scores are fitted to written rules, not learned from outcomes).
- [ ] No use of "compliant", "certified", "defensible", "tamper-proof" or "enterprise-grade".
- [x] `docs/CLIENT_READINESS.md` and `docs/AI_GOVERNANCE.md` updated to match the build.
- [ ] Full backend suite, front-end type check, front-end tests and build all pass (build passes; full suite last run before the changes above).

## H. Owner decisions (6 Nov 2026) and what was done

| # | Question | Decision | Status |
|---|---|---|---|
| 1 | Gemini key shown in chat | New key placed in `backend/.env` | Done by owner; [ ] old key revoked at Google |
| 2 | Risk scoring direction | Keep it, with the honest model card | Done |
| 3 | 105 high flags on the sample school | Make the sample data realistic for a proper demo | Done: October invoices are 82% paid (was 50%); [ ] re-seed local and check the count |
| 4 | Deploy to Neon | Yes, Neon free tier has room; push later, owner will confirm at the end | **Waiting for an explicit "push now"**: the hosted demo is shared with another client; 5 new migrations (audit 0005, ai 0003/0004/0005, analytics 0003) run on deploy |
| 5 | Old direct reminder endpoint | Remove | Done: `communication/student-reminder/` removed (view, route, front-end method, its tests). The Fee Defaulters page's invoice reminder and bulk reminders are the finance module, used by a person at the finance desk, and are unchanged |
| 6 | "Counsel" without approval | Require approval | Done: now the `notify_counsel` request; the assistant can also ask for it |
| 7 | Approvals | Two different people by default; the administrator can name delegates (for example the second in command) | Done: default is now 2. A school with one administrator must add a second (the sample school has `deputy@code.com`) |
| 8 | Student ID | School-specific student-ID format (a prefix per school) so IDs cannot be confused across schools | Done: students added by hand already got the school's code (`GVS-STU0007`) and IDs are unique across all schools; the spreadsheet import now does the same for a school with no students yet (it used a plain `STU-`). A school that already numbers students its own way keeps that pattern. The ID is still sent to the AI provider on purpose |
| 9 | Who copies the newest chain hash | Administrators only | Documented; no extra control built |
| 10 | Provider and legal terms | Skipped | Open (not a code item) |
| 11 | Anthropic default model | Sonnet 5.5 | Done: `claude-sonnet-5-5` for fast and smart |
| 12 | Reply to Andrii | Ok | Draft to be updated with this build |
| 13 | Record pages | Chat answers and risk-flag reviews need them | Done: "Decision records" tab lists answers, risk reviews, approval steps and setting changes (administrators only), each opens with hashes and the verify result and downloads as a file. Answers are saved together with their record or not shown |
| 14 | Model files (pickles) | Schedule a safer store | Scheduled, not built (C6) |

### From the conversation with Jozsef Fodor (runtime governance)

| Point | Status |
|---|---|
| Object continuity: is this still the exact action that was approved? | Built: a SHA-256 of action, school and checked arguments is written into the verified trail when the request is made and compared before anything runs; a request edited afterwards does not run |
| Current admissibility: is it still allowed now? | Already built and kept separate: the same checks are re-run against today's data (invoice still open, asker still allowed, approver still eligible, not expired) |
| Intent saved before the effect, with a key that can exist once | Built for approved actions: one `AIActionEffect` row per request (unique key) saved before the action runs; the action runs after that is committed |
| Honest state after an unconfirmed result | Built: dispatching, confirmed, not_done, unknown. An exception after the attempt starts is kept as UNKNOWN and is not retried; asking again is a new request and a new decision |
| Provider idempotency key; delivery lookup to settle UNKNOWN | **Not built**: the email path (SMTP) offers neither. UNKNOWN is settled by a person checking. [ ] decide if an SMS/email provider with idempotency keys is worth adopting |
| Database uniqueness for the text-message effect key (look-then-create today) | **Not built** (`communication/texts.py`): [ ] add a unique constraint and a create-first flow |
| Request vs intent vs external-effect deduplication | Request and intent: built. External effect: limited as above. We do not claim exactly-once |

