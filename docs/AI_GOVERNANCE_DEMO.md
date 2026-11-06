# Demo script: AI drafts, a person approves, everything is recorded

For a screen-share on the **local build** (the hosted free demo has no AI provider and does not run the risk scoring). About 7 minutes.
Before starting: run it once the same day. The free Gemini key can answer "high demand", and the first request after a quiet period is slower.

## Setup (once)

1. Start with `demo.bat` (backend :8009, frontend :5179). Open http://localhost:5179 in a private window and choose English if the page opens in another language.
2. Put the AI key in `backend/.env` only (never in `.env.example`): `AI_PROVIDER=gemini`, `GEMINI_API_KEY=...`.
3. Logins on the sample school (Maple Grove Academy): `admin@code.com` / `Admin@123` (asks), `deputy@code.com` / `Deputy@123` (a second administrator, approves).
   The deputy account exists only in the local demo database. Use two browser windows, one per person.
4. The sample school is on the plan that includes AI. A school on a lower plan gets "AI assistant is not included in your plan" for everyone except the platform owner's account.

## The story

| Step | Where | What to say and show |
|---|---|---|
| 1. Detect | Reports > AI Predictive Analytics > Run AI Risk Scan | The scan scores students from attendance, marks, overdue fees and behaviour notes. Open **How these scores are made**: they are fitted to written rules, not learned from outcomes; there are no accuracy figures; the flag-rate-by-group check is a first look only. |
| 2. Draft | Reports > AI Risk & Review (panel under the scan) | Each high flag lists its reasons. "Advice only." Use a flag with a concrete reason (low attendance), not a fee flag, and do not scroll the whole list. |
| 3. Ask | As admin, open the AI assistant and write: *Please ask for a fee reminder to be sent to the family for invoice INV-...* (use an open invoice). Or use **Request reminder** in the forecasts table. | The assistant answers that the request is waiting for approval. It cannot send anything. |
| 4. Approve | AI Approvals and Documents, as the second person | The request shows who asked and when. The asker cannot approve it (try it, it is refused). The deputy approves with a note. The demo school starts with one approval. Switch AI settings to "Two different people" to show the stricter rule: then a teacher asks (the "Counsel" button in the forecasts table) and both administrators approve; the person who asked never counts. |
| 5. Record | Same page > **Decision record** | Provider and model, instruction fingerprint, what the person asked, data sent after masking, controls on at the time, each approval with name and time, and "The trail verifies". Download the file. |
| 6. Prove | `python manage.py verify_audit_chain` | Passes. Edit a row in the database by hand and run it again: it reports the changed record. Say plainly that this is tamper-evident, not tamper-proof (the newest hash should be copied outside the database). |
| 7. Stop | AI assistant settings > **All AI** switch | Turn it off: the assistant, the risk scoring and its flags stop. The change is itself a recorded decision. |

## What not to say

* Do not say the models "predict" or are "accurate", or that they were "trained on your school's outcomes".
* Do not say "compliant", "certified", "enterprise-grade" or "tamper-proof".
* "Counsel" and "Request reminder" both create requests; nothing is sent or opened until a second person approves. Schools need two different approvers by default.
* If a send ends as "result not confirmed" the app does not try again by itself: say that this is deliberate.
* Contact details are masked before text goes to a provider, and social security numbers, birth dates and health details always are. The student ID is sent. Text a person types is sent as typed.
* Free Gemini terms are not suitable for real student data. The sample school is invented.

## If something goes wrong

* "AI is switched off for your school": turn on **All AI** in AI assistant settings.
* "High demand" or a 503 from the provider: wait a moment and repeat; the app shows the error, it does not invent an answer.
* A reminder shows as failed: the message says why (for example the family has no email address). That is the honest outcome, not a fault in the approval.
