# Putting the demo on Render (backend) and Vercel (frontend)

What the client gets: the sample US school, **Maple Grove Academy** (K-8, 214 students, 24 staff, timetable, fees, attendance,
exams, behaviour, health, HR), and **four demo accounts and nothing else**:

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@code.com` | `Admin@123` |
| Teacher | `teacher@code.com` | `Teacher@123` |
| Parent | `parent@code.com` | `Parent@123` |
| Student | `student@code.com` | `Student@123` |

These passwords are public (they are in the README), so use this only for a demo site. It runs as `APP_ENV=staging`; the live site
(`production`) refuses them.

## 1. Backend on Render

**A. Render has an old site with data you want gone** (the usual case)
1. Render dashboard > delete the old web service **and** its Postgres database (this is what removes the data). The demo blueprint does not use Redis.
2. New > **Blueprint** > pick this repository > Blueprint path `deploy/render-demo.yaml` > Apply.

**B. You want to keep the existing service and database**
1. Service > Environment: set `APP_ENV=staging`, `DEMO_RESET=1`, and remove `ADMIN_PASSWORD`/`ADMIN_EMAIL` if they are set.
2. Settings > **Start command**, replace with:
   `python manage.py migrate --noinput && python manage.py collectstatic --noinput && (python manage.py setup_demo > /tmp/setup_demo.log 2>&1 &) && daphne -b 0.0.0.0 -p $PORT erp_core.asgi:application`
3. Save and deploy. This **deletes every school and every account** in that database, then loads the demo.
4. When it is up, **delete `DEMO_RESET`** (otherwise every restart wipes and reloads).

The first start loads the school in the background; give it **3 to 5 minutes** before logging in (logins fail until the accounts
exist). Later restarts do nothing because the school is already there. Free instances sleep when idle and take about a minute to wake.

Then in Render > Environment set:
- `FRONTEND_ORIGINS` = the Vercel address, e.g. `https://ccems-demo.vercel.app` (no trailing slash)
- `PUBLIC_API_URL` = the backend address, e.g. `https://erp-demo-backend.onrender.com`

## 2. Frontend on Vercel
1. Vercel > Add New > Project > this repository > **Root Directory `frontend`**. Framework: Vite (`frontend/vercel.json` sets the rest).
2. Environment variables (Production):
   - `VITE_API_URL` = `https://<your-backend>.onrender.com/api/v1/`
   - `VITE_DEMO_LOGINS` = `true` (shows the four demo accounts on the sign-in page, click to fill in)
3. Deploy. If you use "Continue with Google", add the Vercel address under Firebase console > Authentication > Settings > Authorized domains.

## 3. Check it
- Open `https://<backend>.onrender.com/api/v1/health/live/` (should answer {"status":"alive"}; the plain `/health/` reports 503 here because there is no Celery worker).
- Open the Vercel address, sign in as `admin@code.com`: 214 students, Staff & HR with open cover requests.
- Settings > Import data > Download: the data pack of the school.

## If something is wrong
- Logs of the backend show `setup_demo` output only on the machine (`/tmp/setup_demo.log`). To see it, add a Render shell or temporarily change
  the start command to run `python manage.py setup_demo` in the foreground (the server will not answer until it finishes).
- Wrong data or a half-loaded school: set `DEMO_RESET=1`, redeploy, wait, then remove the variable.
- Real email, SMS, payment or Classroom keys are not set on purpose. The client connects their own test accounts under
  Settings > Integrations; for sign-in redirects the backend address above must be the one registered with Microsoft or Google.
