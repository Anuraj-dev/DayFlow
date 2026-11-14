<h1 align="center">Dayflow</h1>

<p align="center">
  Attendance, leave and payroll for a small company, in one loop.<br />
  Employees check in and request leave. HR approves it and publishes pay.
</p>

<p align="center">
  <a href="#running-it">Run it locally</a>
  ·
  <a href="#demo-accounts">Demo accounts</a>
  ·
  <a href="#documentation">Documentation</a>
</p>

Dayflow runs the daily loop for one company. Employees check in and out, request paid, sick or unpaid leave, view coworker profiles and download their published payslips. HR manages the directory, reviews attendance exceptions, approves leave and moves each monthly pay period from draft to finalized to published.

This repository is a hackathon MVP. Docker Compose runs it as three containers: a Vue 3 client, a FastAPI API and PostgreSQL 16. The first startup seeds one demo organization. You need Docker. The app has no sign-up page, no outbound email and no API keys.

## What you get

- **Attendance from the server clock.** Check-in and check-out take the time on the API, not from the browser. An employee can hold one open session at a time. Changing a past punch takes a correction request, and HR approves or rejects it.
- **Status from the work policy.** A day with under 4 hours worked counts as absent, and under 8 hours as a half day. A check-in after 10:00 in the organization's timezone is marked late. The seed uses Asia/Kolkata and a Monday to Friday workweek.
- **Leave counted in workdays.** A request counts only the workdays in its date range. Weekends and holidays are skipped. A new request cannot overlap a pending or approved one. New employees get 24 paid and 7 sick days for the calendar year. Unpaid leave has no balance.
- **Payroll in three steps.** HR moves a monthly period from draft to finalized to published. Finalizing is blocked while an attendance session is still open or a correction is pending in that period. Finalizing stores a snapshot of every payslip line. Employees see only their own published payslips, and each one downloads as an HTML file.
- **Pay from salary components.** The default structure pays basic at 50% of the monthly wage, HRA at 50% of basic and a fixed standard allowance. It deducts 12% of basic as employee provident fund, matches it as employer PF and deducts 200 as professional tax. At finalization, pay is prorated by payable days over scheduled workdays. Present, half-day and paid-leave days count as payable.
- **Server checks on every request.** Each business row carries an `organization_id`, and each route checks the caller's membership and role. The Vue app hides HR screens from employees, but the API is the boundary. Employees can read coworker profiles view-only, and they cannot read coworker attendance, leave or pay.
- **An audit event for privileged changes.** Creating or editing an employee, changing salary, approving or rejecting leave, and finalizing or publishing payroll each write an audit event with the acting user.

## Running it

Dayflow is not installed. It runs as a Compose stack that builds from this repository, so there are no images to pull and no Docker Hub login.

### Prerequisites

- Docker Engine or Docker Desktop with Compose v2
- Git
- Host ports 5173, 8000 and 5433 free

### Start the stack

```sh
git clone https://github.com/Anuraj-dev/DayFlow.git
cd DayFlow
cp .env.example .env
docker compose up --build
```

The first build takes a few minutes. The web app is ready when the frontend log reports that Vite is ready.

| Service | Address |
| --- | --- |
| Web app | [http://localhost:5173](http://localhost:5173) |
| API | [http://localhost:8000](http://localhost:8000) |
| API docs | [http://localhost:8000/docs](http://localhost:8000/docs) |
| API health | [http://localhost:8000/api/health](http://localhost:8000/api/health) |
| PostgreSQL | `localhost:5433`, user and database `dayflow` |

To run in the background and check the containers:

```sh
docker compose up --build -d
docker compose ps
```

`docker compose down` stops the stack and keeps the `dayflow_pg` volume, so your data stays. `docker compose down -v` also deletes that volume. The next start then seeds a fresh database.

## Demo accounts

The first startup seeds the Dayflow Demo organization with these accounts, demo employees, leave types and balances, salary setup, and a published July 2026 payroll period. The passwords protect only this local database.

| Role | Work email | Password |
| --- | --- | --- |
| HR | `hr@dayflow.demo` | `ChangeMe_HR12!` |
| Employee | `employee@dayflow.demo` | `ChangeMe_Emp12!` |

Sign-in accepts a work email or an employee code.

HR creates employees on the People page. The API returns a temporary password once, and the page shows it with a copy button. Share the employee code and that password with the new employee.

### Walk through the demo

1. Sign in as HR and open People for the directory.
2. Open Attendance for today's roster and the exception queue.
3. Open Time off and approve or reject a pending request. A rejection needs a comment.
4. Open Payroll to see the salary inputs and the published period.
5. Sign out and sign in as the employee. Check in, open Time off, and download your published payslip.

## Local development

Run the database and API in Compose, and run the Vue dev server on your machine. The frontend needs Node 22.18 or newer, or 24.12 or newer.

```sh
docker compose up -d db backend
npm --prefix frontend install
npm --prefix frontend run dev
```

The dev server serves http://localhost:5173 and proxies `/api` to http://localhost:8000. Do not run the Compose `frontend` service at the same time, because both use port 5173.

## Tests and checks

Frontend checks run on the host:

```sh
npm --prefix frontend run type-check
npm --prefix frontend run test:unit -- --run
npm --prefix frontend run build
```

Backend tests drop and recreate every table in `DATABASE_URL`. The default URL points at the demo database, so run them against a separate database:

```sh
docker compose exec db createdb -U dayflow dayflow_test
docker compose exec -e DATABASE_URL=postgresql+asyncpg://dayflow:dayflow@db:5432/dayflow_test backend pytest -q
```

To run pytest on the host, create `dayflow_test` the same way, then point `DATABASE_URL` at it:

```sh
cd backend
DATABASE_URL=postgresql+asyncpg://dayflow:dayflow@localhost:5433/dayflow_test pytest -q
```

CI runs the frontend type-check and unit tests, and pytest against PostgreSQL 16, on every push and pull request.

## Configuration

Compose reads `.env` for these values. Every variable has a default, so the copy is optional for a local run.

| Variable | Default | Purpose |
| --- | --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `dayflow` | Credentials for the database container |
| `DATABASE_URL` | `postgresql+asyncpg://dayflow:dayflow@db:5432/dayflow` | Database the API connects to |
| `APP_ENV` | `local` | Outside `local`, `test`, `development` and `dev`, the API refuses to start with the placeholder `JWT_SECRET` |
| `JWT_SECRET` | placeholder | Signs session tokens with HS256 |
| `JWT_EXPIRE_MINUTES` | `720` | Session lifetime in minutes |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated origins that may call the API |
| `SEED_HR_EMAIL`, `SEED_HR_PASSWORD` | `hr@dayflow.demo`, `ChangeMe_HR12!` | HR account created on first startup |
| `SEED_EMPLOYEE_EMAIL`, `SEED_EMPLOYEE_PASSWORD` | `employee@dayflow.demo`, `ChangeMe_Emp12!` | Employee account created on first startup |
| `API_PROXY_TARGET` | `http://backend:8000` in Compose | Where the Vite dev server sends `/api` requests. Set it when the API is not at `localhost:8000` |

Seeding runs only when the database is empty.

## How it is built

The client is Vue 3 with Vite, Tailwind CSS and shadcn-vue components. The API is FastAPI on SQLAlchemy 2 with asyncpg. Passwords are hashed with Argon2.

| Area | Location | Responsibility |
| --- | --- | --- |
| Vue application | `frontend/` | Shell, role-aware views and presentation |
| API routes | `backend/app/api/` | Authentication, authorization, loading, persistence and response shapes |
| Domain rules | `backend/app/domain/` | Attendance, leave, roles and payroll rules. These modules import no database or HTTP code |
| Database mappings | `backend/app/models/` | SQLAlchemy models and relationships |
| Contracts | `backend/app/schemas/` and `frontend/src/types/` | Pydantic responses and shared client types |
| Adapters | `backend/app/adapters/` | Seed data, console email and salary persistence |

Routes stay thin. They load organization-scoped records, call the domain, persist the result and return the contract. The frontend owns presentation, not authorization or payroll math.

## Known limits

- The schema comes from `Base.metadata.create_all` at startup. There are no migrations, and `create_all` does not change tables that already exist. After a model change, run `docker compose down -v` to rebuild the local database.
- Email goes to the API console. Forgot-password only logs a message, and no reset link flow exists yet.
- Invite activation exists in the API, and the Vue app has an activation view that no route reaches. Nothing creates invites yet, so employees get a temporary password instead.
- Password change exists only in the API, at `POST /api/auth/change-password`. The Vue app has no screen for it.
- Document and profile-picture upload are not supported. A sick leave request accepts one PDF, JPEG or PNG certificate up to 5 MB through the API. The Vue app does not offer that upload yet.
- Custom settings management is deferred. The seeded work policy and leave types are used.
- Payslips download as HTML, not PDF.
- Reports, analytics, notifications and Docker Hub images are not built.

`docs/STATE.md` lists what is shipped and what is deferred.

## Documentation

- [docs/STATE.md](docs/STATE.md): shipped behavior, deferred work and verification status
- [docs/PRODUCT.md](docs/PRODUCT.md): pages, flows, permissions and the prototype definition of done
- [docs/DOMAIN.md](docs/DOMAIN.md): data model, business rules, payroll math and seed defaults
- [docs/UI.md](docs/UI.md): visual system, layout and component rules
- [docs/SETUP-PROMPT.md](docs/SETUP-PROMPT.md): a setup prompt for a teammate's coding agent
- [AGENTS.md](AGENTS.md): repository rules for coding agents
- [HACKATHON_GUIDE.md](HACKATHON_GUIDE.md): the original problem assessment

## Contributing

Read [AGENTS.md](AGENTS.md) before you change code. It lists the product invariants and the local proof each change needs.

Name branches `feat/<stack>-<slice>`, write Conventional Commits, and open one pull request per slice. Merge only when CI is green. Never commit `.env`.
