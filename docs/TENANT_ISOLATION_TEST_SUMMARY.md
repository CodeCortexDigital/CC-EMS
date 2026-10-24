# CC-EMS tenant (school) isolation: test summary

Date: 24 Oct 2026. Written for a technical reader. All tests use synthetic data created by the tests themselves (two or more made-up schools
with made-up students and staff). No real client or student data is involved.

## How isolation works

One shared database. Every school-owned record carries its school. The school is taken from the signed-in person on the server, never from the
browser. Models listed in `backend/services/core/tenants/registry.py` are filtered to that school on every read, stamped with it on every write,
and refused if a write names another school. A few platform-level tables are not auto-filtered; each is on a reviewed list with the reason it is safe.

## What the tests cover

**1. Two-school read, write and delete (`tests/test_tenant_isolation.py`, 8 tests)**
- A school B administrator never sees school A's data in lists, and school A still sees its own.
- Opening a school A record by its ID from school B returns "not found".
- Writing into another school (changing or creating a row that belongs to another school) is refused.
- New rows are stamped with the creator's school.
- The same codes (for example a subject or room code) are allowed in different schools.
- A signed-in user with no school sees nothing.
- A request header naming a school you do not belong to cannot switch you into it.

**2. Registry completeness (`tests/test_school_isolation_sweep.py`)**
- Every model with a link to a school must be in the registry or on a reviewed list. A new model that is neither fails the test, so it cannot be added without a decision.
- The reviewed list must not contain stale entries.
- This check found that employee tasks, timesheets and HR documents were not filtered by school. That was fixed on 24 Oct 2026 and now has its own tests: list, read by ID, change and delete from the other school all fail, and a colleague in the same school cannot open someone else's task by ID.

**3. Same-ID collisions across schools (`tests/test_two_school_ids_and_logins.py`)**
- Two schools can both start student and staff numbers at 0001 without either being renumbered (each school's code is part of the ID).
- A number already used inside one school is refused, not silently changed.
- Students and staff of both schools can sign in with their own IDs, and a wrong password fails.

**4. Feature-level two-school cases**
- AI assistant documents and approvals: a school never finds another school's documents; another school's administrator gets "not found" on its approval requests; approval re-checks the school (`tests/test_governed_ai.py`).
- Privacy: another school's office cannot download or erase a student's data; a data copy never contains another student's or school's rows (`tests/test_client_trust.py`).
- AI risk flags: another school's office cannot record a review on a flag (`tests/test_client_trust.py`).
- Retention: one school's retention rule never removes another school's records (`tests/test_client_trust.py`).
- Other areas build two schools in their tests as well (daily briefs, health office, safety incidents, front desk, permission slips, interventions, admissions, push, parents with children in two schools, school signup).

## Known exclusions (not covered, or covered differently)

- **Shared database.** Isolation is by a school column and server-side filtering, not separate databases or schemas, and database-level row security is not used. A mistake in the filtering layer would affect all schools; the registry test and the cross-school tests are the guard against that.
- **Not every endpoint is probed.** There is no automated sweep that calls every URL as a second school. Coverage is the registry check plus the scenarios above, so a new endpoint that bypasses the standard filtering could be missed.
- **Reviewed, not auto-filtered.** 17 tables (for example audit log, sign-in history, billing, support tickets, notifications) are filtered by their own screens or by the person, not by the registry. They are listed with reasons in the test file; they are checked by review, with few dedicated cross-school tests.
- **No dedicated cross-school tests yet** for: direct access to uploaded files by URL, real-time (WebSocket) channels, background jobs, the cache, and exported reports.
- **By design:** the platform owner and superusers can see every school. A parent with children in two different schools shares one account.
- **Environment.** Tests run on SQLite in the development and CI setup. Behaviour on PostgreSQL has been checked for migrations but not by running this whole suite there.
- **No independent verification.** No external penetration test or security audit has been done. The tests are written and run by the team that built the system.

## How to run them

```
cd backend
USE_SQLITE=1 DEBUG=1 pytest tests/test_tenant_isolation.py tests/test_school_isolation_sweep.py tests/test_two_school_ids_and_logins.py tests/test_client_trust.py tests/test_governed_ai.py
```
