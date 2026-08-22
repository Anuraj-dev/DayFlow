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
- Profile picture upload (`profile_image_key` is unused)
- SMTP (console email adapter)
- Forgot-password mail
- Alembic migrations (`create_all` on startup)
- Reports / analytics
- Docker Hub publish

Sick-leave requests may attach one optional PDF/JPEG/PNG certificate. Download is requester or same-org HR only. Seed and hire grants are Paid 24 / Sick 7 / Unpaid 0.

People **nav** is HR-only. Employees can still open `/employees/:id` for a coworker if they have the UUID; the record is view-only and salary stays self/HR. Private and bank fields are omitted from directory and coworker GET; self and same-org HR may read them. Employees still self-edit only phone and address. Change password is `POST /api/auth/change-password` and requires the current password.

## 2026-08-22 — implementer-only, merge on green

- Reviewers removed. One implementer per slice: TDD, then GitHub PR, squash-merge if Actions is green.
- CI on `main`; do not rebuild it unless it is broken.
