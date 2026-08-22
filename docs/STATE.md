# Dayflow state

## 2026-08-22 — selected route designs implemented

- Rebuilt the shared shell and every implemented employee/HR route against the selected Odoo-style references.
- Desktop navigation is centered. Mobile navigation, account menu, route actions, filters, tables, and responsive record lists are working.
- Removed the public `/activate-account` page and route. Sign-in accepts either work email or employee code. Forgot password now has a non-disclosing API response.
- Employee directory search covers code, name, email, phone, role, title, department, employment type, and location.
- Employee and HR profile, attendance, time-off, payroll, and settings states now use the selected split-sheet and review-workspace layouts.
- Deferred by explicit UI state: document upload and settings editing. Employee creation also remains deferred because the backend has no `POST /api/employees` contract.
- Verification: frontend production build passed, 70 frontend tests passed, focused backend auth tests passed, design detector returned no findings, and desktop/mobile route renders completed without console errors.

## 2026-08-22 — implementer-only, merge on green

- Reviewers removed. One implementer per slice: TDD, then GitHub PR, squash-merge if Actions is green.
- grok-4.5 for smaller slices (frontend `auth-ui`, backend `employees`); grok-4.6 for the rest.
- CI already on `main` (`.github/workflows/frontend.yml` and `backend.yml`); do not rebuild it.

## 2026-08-22 — UI and delivery

- Frontend workflow cancelled and rewritten: Odoo 19 product UI, shadcn-vue, no decorative cards, no emoji.
- Each finished slice opens a GitHub PR and squash-merges if Actions is green.
- Frontend CI already exists (`.github/workflows/frontend.yml`); do not rebuild it.

## 2026-08-22 — repository initialized

Scaffolded for the hackathon:

- Vue 3 + TypeScript SPA in `frontend/` with the 9 route templates and role-aware shell.
- FastAPI in `backend/` with domain/adapter layout, SQLAlchemy models, seed HR and employee accounts, and auth on `/api/auth/sign-in`.
- Docker Compose runs Postgres, API, and Vite together.
- Product and domain docs are in `docs/PRODUCT.md` and `docs/DOMAIN.md`.

Still deferred: live check-in mutations, leave approval transactions, payroll finalization, document upload, settings UI, SMTP, Alembic.
