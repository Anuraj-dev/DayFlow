# Dayflow state

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
