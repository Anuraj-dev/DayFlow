# Dayflow state

Last updated: 2026-08-22

This document records what the current `main` branch can demonstrate and what remains intentionally
deferred. Product requirements are in `docs/PRODUCT.md`; domain rules are in `docs/DOMAIN.md`.

## Current release

Dayflow is a working hackathon MVP for one seeded organization. The Vue shell, FastAPI API, and
PostgreSQL schema are implemented together and run with Docker Compose.

## Shipped

### Identity and access

- Seeded HR and employee accounts
- Email/password sign-in and `/me`
- Invite-bound employee activation
- Console email adapter for activation and password-reset requests
- Password change for signed-in users
- Role-aware navigation and dashboards
- Organization-scoped server authorization

### People

- HR employee directory and employee creation
- Invite tokens tied to employee, organization, email, and role
- Self and HR profile access
- Employee self-edit limited to permitted personal fields
- Coworker profiles are view-only
- HR inactive status disables login

### Attendance

- Server-time check-in and check-out
- One open attendance session per employee
- Employee monthly attendance view
- HR current-day roster and exception queue
- Attendance correction requests and HR decisions
- Text-based attendance statuses and audit events

### Time off

- Paid, sick, and unpaid leave types
- Organization-local counted days and balances
- Employee request and pending cancellation
- HR approve/reject flow with required rejection comments
- Leave events, balance updates, and audit events
- Optional PDF/JPEG/PNG certificate for sick leave

### Payroll

- Wage and salary component configuration
- Monthly payroll periods: draft, finalized, and published
- Attendance and leave validation before finalization
- Prorated earning calculations, PF, professional tax, and employer PF
- Immutable finalized records with snapshot lines
- Employees see only their own published payroll records
- HR can review all records and publish a period

### Frontend and delivery

- Odoo 19-style product shell with responsive employee views
- HR-only People and Settings navigation
- Loading, empty, validation, permission, and error states on core views
- Frontend and backend CI workflows
- Focused authorization and domain tests

## Deferred

- Custom Settings UI; seeded work policies are used
- Document and profile-picture upload
- Downloadable payslip files; payroll breakdowns are available in the UI
- Full SMTP delivery and a complete password-reset link flow
- Alembic migrations; startup uses `Base.metadata.create_all`
- Reports, analytics, notifications, and Docker Hub publishing

## Seed and data behavior

On an empty database, API startup creates the schema and seeds the demo organization, HR account,
employee account, leave types, balances, salary components, and one published payroll period.

The Compose volume is persistent. Extra presentation records remain until `docker compose down -v`
is run. Never load production people, payroll, or documents into this prototype.

## Verification

Local frontend proof:

```bash
npm --prefix frontend run test:unit -- --run
npm --prefix frontend run type-check
npm --prefix frontend run build
```

Backend proof runs against disposable PostgreSQL because the test fixture recreates its configured
database. CI provides an isolated PostgreSQL service for every run.

## Operational notes

- Compose project name: `dayflow`
- PostgreSQL volume: `dayflow_pg`
- Web app: `localhost:5173`
- API: `localhost:8000`
- PostgreSQL host port: `localhost:5433`
- Stop only this project with `docker compose down`
