# CC-EMS architecture

Diagrams are written in Mermaid, which GitHub and most Markdown viewers draw as pictures. They show how the system is put together today;
file paths are given so each box can be found in the code. For privacy and testing detail see [CLIENT_READINESS.md](CLIENT_READINESS.md) and
[TENANT_ISOLATION_TEST_SUMMARY.md](TENANT_ISOLATION_TEST_SUMMARY.md).

## 1. The system

```mermaid
flowchart LR
  subgraph People
    A[Administrators and office staff]
    T[Teachers]
    F[Parents and students]
  end
  subgraph Browser["Web app (React, TypeScript, Vite) frontend/"]
    UI[Role-based portals, installable as an app, web push]
  end
  subgraph API["Backend (Django REST Framework) backend/"]
    AUTH[Sign-in: JWT, two-step, Google or Microsoft]
    SCOPE[School scoping and role policy]
    MODS[Modules: students, attendance, finance, HR, library, transport, health, safety, admissions, forms, briefs]
    AI[AI layer: tools, knowledge search, approvals]
    DOCS[OpenAPI docs /api/docs/]
  end
  DB[(PostgreSQL, SQLite for local demo)]
  CACHE[(Redis: cache, real-time channels, job queue)]
  JOBS[Scheduled jobs: Celery beat and workers]
  subgraph Optional["Optional services (a school turns them on)"]
    LLM[AI model provider: OpenAI or Anthropic]
    SMS[Twilio SMS and WhatsApp]
    PAY[Stripe payments]
    PUSH[Web push, VAPID]
    FILES[Object storage, S3-compatible]
  end
  A & T & F --> UI --> AUTH --> SCOPE --> MODS
  SCOPE --> AI
  MODS --> DB
  AI --> DB
  MODS --> CACHE
  JOBS --> MODS
  AI -.-> LLM
  MODS -.-> SMS & PAY & PUSH & FILES
```

In the hosted demo the web app runs on Vercel and the backend on Render. The free demo plan has no job worker, so scheduled jobs (daily briefs,
retention, library reminders) are run by hand or by a cron there.

## 2. How one request stays inside one school

```mermaid
sequenceDiagram
  participant B as Browser
  participant J as TenantJWTAuthentication
  participant V as View (DRF)
  participant M as Model manager
  participant D as Database
  B->>J: request with the signed-in person's token
  J->>J: find the person's school (never taken from the request body)
  J->>V: school set for this request
  V->>M: read rows
  M->>D: query filtered to that school (registry.py)
  D-->>V: only that school's rows
  V->>M: save a new row
  M->>M: stamp the school; refuse a row that names another school
  Note over J,M: A person with no school gets no school data at all. A test fails if a model with a school link is neither in the registry nor on the reviewed list.
```

## 3. How the AI assistant acts: it can only ask

```mermaid
flowchart TD
  U[Person asks the assistant something] --> R{Question about school data or policy?}
  R -- data --> T[Role-checked read-only tools, scoped to the person's school, audited]
  R -- policy --> K[Search the school's own documents, shown with the document name]
  U --> W{Asks it to do something?}
  W -- yes --> P[Stored as a pending request. Nothing has happened.]
  P --> H[Administrator reviews it in AI Approvals]
  H -- rejects --> X[Nothing runs]
  H -- approves --> C[Checks again: approver role, school, age, asker still allowed]
  C --> E[Registered action runs once, result and decision audited]
  T & K --> A[Answer is a draft for the person to use or ignore]
```

AI risk scores follow the same rule: they are labelled advice, and each high flag waits for a person's recorded decision.

## 4. Data lifecycle

```mermaid
flowchart LR
  IN[Entered by staff, imported by data pack, or created by families] --> STORE[(School's data)]
  STORE --> USE[Used by the school's modules and portals]
  STORE --> RET[Daily retention job: delete or anonymise by the school's own rules, preview first]
  STORE --> REQ[Privacy request: download a copy of one student's data, or erase it after a preview and typed confirmation]
  STORE --> EXP[Data pack and technical export: CSV and full export]
  RET & REQ --> LOG[(Audit log)]
```

## 5. Repository map

| Folder | What is in it |
|---|---|
| `frontend/src/pages`, `components`, `services` | Screens, shared parts and API calls |
| `backend/services/core` | Accounts, school scoping, security, privacy, billing, audit, notifications, backups |
| `backend/services/education` | School modules (students, attendance, finance, HR, library, transport, and so on) |
| `backend/services/ai` | AI assistant, tools, document search, approvals |
| `backend/services/analytics`, `ai-ml/` | Risk scoring and prediction models |
| `backend/tests` | Automated tests (including the school isolation tests) |
| `docs/` | This and the other guides |
| `deploy/` | Hosting notes for the hosted demo |
