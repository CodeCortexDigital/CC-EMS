# CC-EMS: how AI is governed (what is built, and what is not)

Written 5 Nov 2026 for someone checking the claims against the code. CC-EMS is an early-stage product, tested on sample data. It has had no
independent security audit and holds no certification. Every statement below names the code or test that shows it; where something is not built,
it says so. The working list of gaps is in [AI_GOVERNANCE_GAPS.md](AI_GOVERNANCE_GAPS.md).

## 1. The path from AI to action

```
person asks  ->  assistant proposes  ->  request stored (pending)  ->  approver(s) decide  ->  action runs once  ->  result recorded
                  (cannot execute)       decision record opened        (not the asker)
```

* The assistant has no way to act. It can only call `propose_<action>`, for actions registered in code (today two: send a fee reminder, open a student
  support case). Anything else is refused. `services/ai/actions.py`.
* A request waits at most two days, then expires.
* **The person who asked can never approve their own request** (they may withdraw it). The school can require **two different approvers** and can **name
  who may approve**; with nobody named, any administrator may. The rule cannot be set to something nobody can meet. `actions.decide_problem`,
  `settings_api._validate_approval`, `tests/test_dual_approval.py`.
* At approval the asker's role and the request are checked again against today's data, and the request is locked so it runs exactly once.
* The fee-reminder action sends the same email as the fee office's own button, with the approver recorded as the sender.
* "Request reminder" in the risk forecasts table creates the same kind of request, so a person's click there does not email a family either.
  `governance_api.request_fee_reminder`, `tests/test_remind_approval.py`.
* "Counsel" in the same table opens a to-do for staff and notifies them. It is an internal task, not contact with a family, and has no approval step.

## 2. The decision trail

Decisions (an AI request, each approval, the result, a person's review of a risk flag, a change to the AI settings, acceptance of the AI use notice) are
written to a hash-chained trail, one chain per school: each record carries the hash of the one before it. `core/audit/chain.py`.

* The application cannot change or delete these records; the admin screen cannot either; the 90-day cleanup and the archive job skip them.
* `python manage.py verify_audit_chain` reports a record that was changed, removed or inserted, and prints each school's newest hash.
* **Fail-closed:** each step is saved in the same transaction as its record. If the record cannot be saved, the step does not happen (nothing is sent, the review
  is not kept, the setting is not changed). `tests/test_audit_chain.py`, `tests/test_governed_ai.py`.
* **Limit:** tamper-evident, not tamper-proof. Someone with direct database access who rewrites a whole chain and its newest hash together is not caught unless
  that hash was copied somewhere outside the database. Routine audit rows (views, logins) and AI lookup logs are not chained, and rows from before this build
  are not protected.

## 3. The decision record (one page per request)

AI Approvals and Documents > "Decision record" (API `GET /api/v1/ai/governance/approvals/<id>/record/`, `?download=1` for a file). It shows:

| Item | Where it comes from |
|---|---|
| Time and request id | the request and every trail step |
| Provider and model | the configured model name (not a provider-pinned version) |
| Instructions given to the model | a SHA-256 fingerprint of the system prompt |
| What the person asked | the last message, up to 2,000 characters |
| Data sent to the model | tool results after masking, up to 3,000 characters each |
| Sources used | school documents quoted |
| Controls on at the time | assistant switched on, contact masking, use notice version and acceptance, rate limit, monthly cap, approvals required, named approvers |
| Human decisions | each approval with who, when and note; rejection; result |
| Does it still verify | the chain check, and a check that the stored basis matches the hash written when the request was made |

`tests/test_decision_record.py`. Records exist for AI action requests. A chat answer that proposes nothing, and a risk-flag review, are in the trail but have no page of their own.

## 4. Switches

* One switch turns off all AI for a school, including risk scoring and its flags. Each feature keeps its own setting for when it is turned back on. Every change is
  a recorded decision. `tests/test_ai_master_switch.py`.
* Face-recognition attendance is **off until a school turns it on**. It is biometric data and several US states restrict it for students. The hosted demo does not run it.
* A school must accept the AI use notice, which says what is sent to a provider and that everything the AI writes is a draft.

## 5. What is sent to a provider

* Phone numbers, emails, addresses and similar contact fields are masked unless the school allows them.
* Social security numbers, birth dates and health details are **always** masked, and a social-security-number pattern inside free text is masked too.
* The student ID is sent (the assistant needs it to name a student). Text a person types is sent as typed.
* **Not in place:** a signed zero-retention agreement with a provider. The school is responsible for choosing a provider whose terms meet its own and its
  district's requirements (the notice says so). Provider supported today: OpenAI, Anthropic and Gemini (through Google's OpenAI-compatible endpoint). No provider is connected on the hosted demo.

## 6. The risk scoring (see also the model card inside the app)

* Scores are advice. A person reviews each high or critical flag and records worth acting on, need more information, or not a concern, with a reason; the
  decision is in the trail with their name and time. Nothing is done to a student because of a score.
* **The scores are not learned from recorded outcomes.** The models are fitted to fixed, written scoring rules (dropout: attendance, exam average and behaviour notes;
  fee default: the share of the amount billed that is overdue and unpaid), using the school's own students plus generated example rows, so they reproduce those
  rules. There are no accuracy figures because there is nothing real to measure against.
* Family income and number of siblings are not used. Holidays are not counted; late, early-dismissal and excused days count as attended.
* The attendance anomaly check flags about 15% of students by design.
* Each scan is recorded (training facts, library versions, level counts, missing data) and each score carries the id of the scan that made it. A first check of
  flag rates by gender and class is shown; it cannot show that flags are fair or unfair.
* The scan needs scikit-learn and XGBoost. It runs in the full build and is not switched on in the free hosted demo.
* Education risk scoring is likely to be classed as high-risk AI in some places (for example the EU AI Act). CC-EMS makes no claim of compliance.

## 7. What is not built

Independent security audit or penetration test · certification (SOC 2 or similar) · single sign-on · provider zero-retention terms on file · a real fairness and
validation study of the risk models · model files stored as pickles next to the code (a signed or isolated store is not built) · retention for library, transport
and visitor logs · a decision-record page for chat answers and risk-flag reviews.
