# Dayflow

Dayflow is a small-company HR operations app for the daily attendance → leave → payroll loop.
Employees manage their own attendance, leave, profile, and published payroll. HR manages people,
reviews exceptions, approves leave, and finalizes pay periods.

This repository contains the hackathon MVP: a Vue 3 client, a FastAPI API, and PostgreSQL running
together with Docker Compose.

## What is implemented

### Employee experience

- Sign in and invited account activation
- Personal dashboard with attendance status and leave balances
- Server-time check-in and check-out
- Monthly attendance history and correction requests
- Leave requests, cancellation of pending requests, and balance tracking
- View-only coworker profiles
- Read-only access to the employee's own published payroll
- Personal phone, address, and password updates

### HR experience

- Role-specific HR dashboard
- People directory and employee profile management
- Employee hiring and invite activation
- Organization-wide attendance roster and correction review
- Leave approval and rejection with comments
- Salary component and wage management
- Payroll draft → finalized → published workflow
- Audit events for privileged changes

The server enforces authorization and organization isolation for every read and mutation. The UI
does not act as the security boundary.

## Run the application

### Prerequisites

- Docker Engine or Docker Desktop with Compose v2
- Git
- Ports `5173`, `8000`, and `5433` available on the host

You do not need Docker Hub credentials. The project builds its own frontend and backend images and
uses the official PostgreSQL image.

### First run

```bash
git clone https://github.com/Anuraj-dev/DayFlow.git
cd DayFlow
git checkout main
git pull
cp .env.example .env
docker compose up --build
```

The first build may take a few minutes. Open the app when the frontend reports that Vite is ready:

| Service | URL |
|---|---|
| Dayflow web app | [http://localhost:5173](http://localhost:5173) |
| API | [http://localhost:8000](http://localhost:8000) |
| Interactive API docs | [http://localhost:8000/docs](http://localhost:8000/docs) |
| API health | [http://localhost:8000/api/health](http://localhost:8000/api/health) |
| PostgreSQL | `localhost:5433` |

To run the stack in the background:

```bash
docker compose up --build -d
docker compose ps
```

Stop only the Dayflow stack:

```bash
docker compose down
```

The named `dayflow_pg` volume keeps database data between normal stops. To intentionally delete the
local database and start fresh, run `docker compose down -v`.

## Demo accounts

The first startup seeds one organization, one HR account, and one employee account. The passwords
below are for local demonstration only.

| Role | Email | Password |
|---|---|---|
| HR | `hr@dayflow.demo` | `ChangeMe_HR12!` |
| Employee | `employee@dayflow.demo` | `ChangeMe_Emp12!` |

When HR creates an employee, the API returns the employee code and one-time invite token. The
activation verification message is printed by the console email adapter. Existing local
presentation data remains in the `dayflow_pg` volume until that volume is removed.

## Suggested presentation flow

1. Sign in as HR and open **People** to show the organization directory.
2. Open **Attendance** to show today's roster and exception queue.
3. Open **Time off** and approve or reject a pending request with a comment.
4. Open **Payroll** to review salary inputs and the published period.
5. Sign out and sign in as the employee.
6. Check in from the shared attendance action, open **Time off**, and review the employee's own
   published payroll.
7. Use a coworker profile URL to demonstrate view-only access; salary and HR controls stay
   protected by the API.

## Local development

Run PostgreSQL and the API with Compose, then run the Vue client on the host:

```bash
docker compose up -d db backend
npm --prefix frontend install
npm --prefix frontend run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000` by default. Set
`API_PROXY_TARGET` if the API runs elsewhere.

### Tests and checks

Frontend checks:

```bash
npm --prefix frontend run test:unit -- --run
npm --prefix frontend run type-check
npm --prefix frontend run build
```

Backend tests require PostgreSQL and recreate the configured test database. Never run them against
a database that contains presentation or personal data. CI runs them against an isolated
PostgreSQL service:

```bash
docker compose exec backend pytest
```

For a host Python environment, point `DATABASE_URL` at a disposable PostgreSQL database before
running `pytest`:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://dayflow:dayflow@localhost:5433/dayflow pytest -q
```

## Architecture

| Area | Location | Responsibility |
|---|---|---|
| Vue application | `frontend/` | Shell, role-aware views, interaction, and presentation |
| API routes | `backend/app/api/` | Authentication, authorization, loading, persistence, and response shapes |
| Domain rules | `backend/app/domain/` | Attendance, leave, identity, roles, and payroll business logic |
| Database mappings | `backend/app/models/` | SQLAlchemy models and relationships |
| Contracts | `backend/app/schemas/` and `frontend/src/types/` | Pydantic responses and shared client types |
| Adapters | `backend/app/adapters/` | Seed data, console email, salary persistence, and storage boundary |
| Product guidance | `docs/` | Product flows, domain rules, UI rules, and current state |

Routes should stay thin: load organization-scoped records, call domain logic, persist the result,
and return the contract. The frontend owns presentation, not authorization or payroll math.

## Security and tenancy rules

- Every business row is scoped by `organization_id`.
- Every server read and mutation checks the current membership and role.
- Public registration never grants the HR role; HR access comes from the seeded HR account or an
  invite.
- Privileged changes create audit events.
- Attendance timestamps come from the server. Historical changes use correction requests.
- Finalized payroll records are immutable snapshots.
- Employees can read coworker profiles in view-only form, but cannot edit them or read coworker
  attendance, leave, documents, or salary.

## Prototype boundaries

The following items are intentionally deferred:

- Custom settings management; policies are seeded for the prototype
- Document and profile-picture upload
- Downloadable payslip files; payroll records and line breakdowns are available
- Full SMTP delivery and completed password-reset links; email uses the console adapter
- Alembic migrations; startup currently uses `Base.metadata.create_all`
- Reports, analytics, notifications, and Docker Hub image publishing

These are documented as deferred work rather than silently implied to be available.

## Documentation map

| Document | Purpose |
|---|---|
| `AGENTS.md` | Repository rules for coding agents and feature delivery |
| `docs/PRODUCT.md` | Product pages, flows, permissions, and prototype definition of done |
| `docs/DOMAIN.md` | Data model, domain rules, payroll math, and MVP defaults |
| `docs/UI.md` | Odoo 19 visual system, layout, tokens, and component rules |
| `docs/STATE.md` | Current shipped behavior, deferred work, and verification status |
| `docs/SETUP-PROMPT.md` | Copy-paste setup instructions for a teammate's coding agent |
| `HACKATHON_GUIDE.md` | Original problem assessment and historical source material |

## Team workflow

Feature slices use branches named `feat/<stack>-<slice>` and Conventional Commits. Each slice gets
its own pull request, required local proof, and green CI before squash-merging to `main`.
