# The Japanese demo site (for Masato Yamano)

A separate site from the US demo: its own Render backend and database and its own Vercel frontend, so the other client's demo is not touched.
It loads the sample Japanese school **Wakaba Gakuen** (みどり市立 若葉学園: 109 students in grades 1-9, staff, timetable, school-lunch fees in yen,
attendance, exams, and sample 指導要録 for class 6年) and one administrator login for Masato.

| Role | Email | Password |
|------|-------|----------|
| Administrator (Masato) | `masato@admin.com` | set by you in Render (`DEMO_ADMIN_PASSWORD`); give it to him privately, for example on WhatsApp |
| Teacher / Parent / Student | `teacher@code.com`, `parent@code.com`, `student@code.com` | the public demo passwords in the README |

The password is never stored in this repository. The public administrator logins (`admin@code.com`, `deputy@code.com`) are switched off on this site.
The site runs as `APP_ENV=staging` (no real email or payments).

## 1. Backend on Render
1. Render > New > **Blueprint** > this repository, branch with this file > Blueprint path `deploy/render-demo-jp.yaml` > Apply.
2. When asked for `DEMO_ADMIN_PASSWORD`, type the password for Masato. (Later: service > Environment, change it and redeploy to change the password.)
3. Wait **5 to 8 minutes** for the school to load (the first start loads it in the background; logins fail until it is done).
4. Service > Environment, set:
   - `FRONTEND_ORIGINS` = the Vercel address of step 2 (no trailing slash)
   - `PUBLIC_API_URL` = this backend's address, e.g. `https://erp-jp-demo-backend.onrender.com`
5. Check `https://<backend>.onrender.com/api/v1/health/live/` answers `{"status":"alive"}`.

## 2. Frontend on Vercel (a new project)
1. Vercel > Add New > Project > this repository, **Root Directory `frontend`**, branch with this file.
2. Environment variables: `VITE_API_URL` = `https://<backend>.onrender.com/api/v1/`, and `VITE_DEMO_LOGINS` = `false`
   (so the sign-in page does not list accounts; Masato types his own).
3. Deploy. Go back to Render step 4 with the Vercel address.

## 3. Check it
- Open the Vercel address, choose 日本語 with the globe button, sign in as `masato@admin.com`.
- Academics > 指導要録 (Cumulative Records) > class 6年: 9 students; open one: the register, years 1-5 sealed, year 6 open; print page.
- Dashboard, students, timetable, fees in yen.

## Notes
- A free Render service sleeps after about 15 minutes idle; open the backend address a few minutes before he looks.
- Wrong or half-loaded data: set `DEMO_RESET=1`, redeploy, wait, then remove the variable.
- Server-made PDFs (invoices) do not show Japanese yet (browser-print pages, including 指導要録, do). Say so if he opens an invoice PDF.
