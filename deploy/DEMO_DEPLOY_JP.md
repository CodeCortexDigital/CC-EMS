# The Japanese demo school (for Masato Yamano)

## Option A (recommended): a second school in the existing demo database
The app keeps every school's data apart in one database (each row belongs to a school and every screen only shows the signed-in school's rows),
so the Japanese school can sit next to the schools already on the demo. Masato signs in with his own administrator and lands in Wakaba Gakuen only; the existing
logins and schools are not touched. Each school's country style (USA, Pakistan, Japan: currency, date format, language, terms) is that school's own setting under
**Settings > Language & currency > Region style**.

On the existing demo **backend** (Render > Environment), add:

| Variable | Value |
|---|---|
| `DEMO_EXTRA_PACKS` | `jp-school` |
| `DEMO_EXTRA_ADMIN_EMAIL` | `masato@admin.com` |
| `DEMO_EXTRA_ADMIN_NAME` | `Masato Yamano` |
| `DEMO_EXTRA_ADMIN_PASSWORD` | the password for Masato (typed in Render only; never in the repository) |

Deploy the branch `feat/japan-demo` to that backend and restart it (the start command already runs `setup_demo`, which now loads the extra school once,
in the background: allow 5 to 8 minutes; the existing school is not reloaded and `DEMO_RESET` stays unset). Or run it by hand in a Render shell:
`python manage.py add_demo_school --pack jp-school --admin-email masato@admin.com --admin-password '...' --admin-name 'Masato Yamano'`.
Changing `DEMO_EXTRA_ADMIN_PASSWORD` and restarting changes his password.

The school also gets its own teacher, parent and student logins: `teacher@wakaba.example`, `parent@wakaba.example`, `student@wakaba.example`
(passwords `Teacher@123`, `Parent@123`, `Student@123`).

The sign-in page of a demo site (`VITE_DEMO_LOGINS=true`) can offer both schools with two buttons, **USA school** and **Japanese school**. Choosing one lists that
school's accounts to click and switches the page language (English or 日本語). The Japanese button appears when you build the **frontend** with
`VITE_DEMO_ADMIN_EMAIL=masato@admin.com`, `VITE_DEMO_ADMIN_PASSWORD=<same password>` and `VITE_DEMO_ADMIN_LABEL=Admin (Masato)`
(his login is then listed first under the Japanese school), or with just `VITE_DEMO_JAPAN_SCHOOL=true` (then only the teacher, parent and student logins are listed).
The password is visible on the page, so keep the demo to sample data.

## Option B: a separate Japanese site (its own backend, database and screens)
Use this only if you want Masato's site apart from the other client's.

A separate site from the US demo: its own Render backend, database and screens, so the other client's demo is not touched.
It loads the sample Japanese school **Wakaba Gakuen** (みどり市立 若葉学園: 109 students in grades 1-9, staff, timetable, school-lunch fees in yen,
attendance, exams, and sample 指導要録 for class 6年) and one administrator login for Masato, listed on the sign-in page.

| Role | Email | Password |
|------|-------|----------|
| Administrator (Masato) | `masato@admin.com` | set by you in Render (`DEMO_ADMIN_PASSWORD`); give it to him privately, for example on WhatsApp |
| Teacher / Parent / Student | `teacher@code.com`, `parent@code.com`, `student@code.com` | the public demo passwords in the README |

The password is never stored in this repository. The public administrator logins (`admin@code.com`, `deputy@code.com`) are switched off on this site.
The site runs as `APP_ENV=staging` (no real email or payments).

## 1. Put it on Render (backend, database and screens in one go)
1. Render > New > **Blueprint** > this repository, branch `feat/japan-demo` > Blueprint path `deploy/render-demo-jp.yaml` > Apply.
2. When asked for `DEMO_ADMIN_PASSWORD` (backend) and `VITE_DEMO_ADMIN_PASSWORD` (screens), type the same password for Masato in both. The sign-in page then lists his administrator login (and the teacher, parent and student logins) to click, so the password is visible on the page: that is fine for sample data, but do not reuse it anywhere. (Later: backend service > Environment, change it and redeploy to change the password.)
3. It creates three things: `erp-jp-demo-db`, `erp-jp-demo-backend`, `erp-jp-demo-web`. Wait **5 to 8 minutes** for the school to load (logins fail until it is done).
4. Check the two addresses Render shows. If the backend is not exactly `https://erp-jp-demo-backend.onrender.com`, set `VITE_API_URL` on `erp-jp-demo-web` to `https://<backend address>/api/v1/` and redeploy it.
5. Backend service > Environment, set:
   - `FRONTEND_ORIGINS` = the address of `erp-jp-demo-web` (no trailing slash), e.g. `https://erp-jp-demo-web.onrender.com`
   - `PUBLIC_API_URL` = the backend address, e.g. `https://erp-jp-demo-backend.onrender.com`
6. Check `https://<backend>/api/v1/health/live/` answers `{"status":"alive"}`.

(Vercel is not used for this site: its free plan refuses repositories owned by an organisation, which is the red "Vercel" check on GitHub. That check can be ignored.)

## 2. Check it
- Open the `erp-jp-demo-web` address, choose 日本語 with the globe button, sign in as `masato@admin.com`.
- Academics > 指導要録 (Cumulative Records) > class 6年: 9 students; open one: the register, years 1-5 sealed, year 6 open; print page.
- Dashboard, students, timetable, fees in yen.

## Notes
- A free Render service sleeps after about 15 minutes idle; open the backend address a few minutes before he looks.
- Wrong or half-loaded data: set `DEMO_RESET=1`, redeploy, wait, then remove the variable.
- Server-made PDFs (invoices, receipts, result cards, finance reports) now show Japanese.
