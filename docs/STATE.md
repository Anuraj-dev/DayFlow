# Dayflow state

## 2026-08-22 — docs on current main

Shipped on `main`:

- Auth: sign-in, `/me`, invite activation (token-keyed; expired/used/duplicate email return 400)
- Employees: directory, profile PATCH, org-wide view-only GET, HR INACTIVE disables login
- Attendance: server-time check-in/out, HR corrections, one open session per employee
- Leave: request, approve/reject, balances
- Payroll: salary components, period finalize/publish, role dashboards
- Vue: Odoo 19 shell, people, attendance, time-off, payroll
- Activate UI maps API 400 expired/used to dedicated screens (#15)
- CI: `.github/workflows/backend.yml` and `frontend.yml`

Deferred:

- Settings UI (policies are seeded)
- Document upload
- SMTP (console email adapter)
- Forgot-password mail
- Alembic migrations (`create_all` on startup)
- Reports / analytics
- Docker Hub publish

People **nav** is HR-only. Employees can still open `/employees/:id` for a coworker if they have the UUID; the record is view-only and salary stays self/HR.

## 2026-08-22 — implementer-only, merge on green

- Reviewers removed. One implementer per slice: TDD, then GitHub PR, squash-merge if Actions is green.
- CI on `main`; do not rebuild it unless it is broken.
