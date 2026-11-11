# The Japanese demo site (for Masato Yamano)

A separate site from the US demo: its own Render backend, database and screens, so the other client's demo is not touched.
It loads the sample Japanese school **Wakaba Gakuen** (みどり市立 若葉学園: 109 students in grades 1-9, staff, timetable, school-lunch fees in yen,
attendance, exams, and sample 指導要録 for class 6年) and one administrator login for Masato.

| Role | Email | Password |
|------|-------|----------|
| Administrator (Masato) | `masato@admin.com` | set by you in Render (`DEMO_ADMIN_PASSWORD`); give it to him privately, for example on WhatsApp |
| Teacher / Parent / Student | `teacher@code.com`, `parent@code.com`, `student@code.com` | the public demo passwords in the README |

The password is never stored in this repository. The public administrator logins (`admin@code.com`, `deputy@code.com`) are switched off on this site.
The site runs as `APP_ENV=staging` (no real email or payments).

## 1. Put it on Render (backend, database and screens in one go)
1. Render > New > **Blueprint** > this repository, branch `feat/japan-demo` > Blueprint path `deploy/render-demo-jp.yaml` > Apply.
2. When asked for `DEMO_ADMIN_PASSWORD`, type the password for Masato. (Later: backend service > Environment, change it and redeploy to change the password.)
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
- Server-made PDFs (invoices) do not show Japanese yet (browser-print pages, including 指導要録, do). Say so if he opens an invoice PDF.
