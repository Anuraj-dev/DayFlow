# Dayflow Agent Guide

Dayflow is a small-company HR operations app. Employees check in, request leave, and read payroll; HR officers manage people, review exceptions, approve leave, and publish pay. The product center is that daily attendance → leave → payroll loop, not a generic employee database.

## What must remain true

- The server authorizes every read and mutation. Hiding a control in the Vue UI is not authorization.
- Every business row is scoped by `organization_id`. A request never returns or mutates another organization's data.
- Roles come from invites or a seeded first HR account. Public sign-up never grants `HR`.
- Privileged changes leave an audit event: role changes, employee edits, attendance corrections, leave decisions, salary changes, and payroll finalization.
- Employee and HR land on different dashboards. People **nav** is HR-only. Employees may read coworker profiles view-only; they cannot edit them or see unpublished payroll.
- Attendance timestamps come from the server. Historical punches change only through a correction request that HR reviews.
- Finalized payroll records are immutable. A correction is a new revision or adjustment period.
- Status always includes text or an icon, not color alone.
- Product UI follows `docs/UI.md`: Odoo 19 enterprise shell, shadcn-vue, dense sheets and tables, no decorative cards, no emoji.
- The Vue shell, FastAPI API, and Postgres schema move together. A route, permission, or field that exists on one surface exists on the others or is marked deferred in `docs/STATE.md`.

If a requested change conflicts with an invariant, explain the conflict and get Raja's decision before breaking it.

## Vocabulary

| Term | Meaning here |
|---|---|
| You | The coding agent changing this repository |
| We / maintainers | Raja and the hackathon teammate who own this repo |
| User | An employee or HR officer using Dayflow, not the person prompting |
| Organization | The tenancy boundary. Demo ships one org; every table still carries `organization_id` |
| Membership | A user's role inside an organization: `EMPLOYEE` or `HR` |
| Employee record | The person record HR manages. Distinct from the login `User` |
| Invite | Single-use token tying organization, employee record, work email, and role |
| Attendance session | One check-in/check-out window for one work date. MVP: at most one open session per employee |
| Leave request | A dated leave range with type, counted days, status, and review audit |
| Payroll period | A dated pay window that moves draft → finalized → published |
| Settings | HR policy configuration. Seeded for the prototype; `/settings` may stay unimplemented |

Use these terms in code, docs, and reports. Do not invent synonyms for established concepts.

Read `docs/PRODUCT.md` before adding a route, page state, or navigation item. Read `docs/UI.md` before changing layout, tokens, or components. Read `docs/DOMAIN.md` before changing a table, business rule, permission, or seed. Write dated status to `docs/STATE.md`, not this file.

## Architecture and ownership

```text
frontend/            -> Vue 3 + TypeScript SPA: shell, role-aware views, presentation
backend/app/domain  -> Attendance, leave, payroll, and identity rules
backend/app/api     -> HTTP routes, auth dependencies, request/response shapes
backend/app/models  -> SQLAlchemy mapping of the domain tables
backend/app/adapters-> Postgres, console email, private file storage
backend/app/core    -> Settings, security, database engine
docs/PRODUCT.md      -> Pages, flows, definition of done (agents + maintainers)
docs/UI.md           -> Odoo 19 product tokens, shell, shadcn-vue, no-card rule
docs/DOMAIN.md       -> Data model, business rules, MVP defaults (agents + maintainers)
docs/STATE.md        -> Current work and dated status
```

- Domain logic belongs in `backend/app/domain`.
- External complexity terminates at `backend/app/adapters`.
- Orchestration in `backend/app/api` stays thin: load, call domain, persist, return.
- UI owns presentation and interaction, not authorization, attendance math, leave counting, or payroll finalization.
- Shared contracts change whenever a Pydantic schema or a field the Vue client consumes changes. Update `frontend/src/types` in the same change.

## Working in this repository

Discover ordinary commands from `frontend/package.json` and `backend/requirements.txt`. Record only non-obvious commands and traps here.

| Task | Correct command | Non-obvious reason |
|---|---|---|
| Install / run the stack | `docker compose up --build` from repo root | Teammates share Git, not images. Compose builds frontend, API, and Postgres together. |
| Copy env | `cp .env.example .env` | Compose reads `.env`. Never commit `.env`. |
| Focused frontend test | `npm --prefix frontend run test:unit -- src/__tests__/router.spec.ts` | Vitest defaults to watch; pass a file for a single run in CI or agents. |
| Frontend type-check | `npm --prefix frontend run type-check` | `npm run build` also type-checks; use this when you only need types. |
| Backend tests | `docker compose exec backend pytest` | Host Python may be 3.14; images pin 3.12. Host pytest needs `DATABASE_URL=...@localhost:5433/dayflow`. |
| API only, UI on host | `docker compose up -d db backend` then `npm --prefix frontend run dev` | Vite proxies `/api` to `localhost:8000` unless `API_PROXY_TARGET` is set. |
| Stop this stack | `docker compose down` | Stops only the `dayflow` compose project. Leaves other Docker workloads alone. |

### Protect the active environment

- Use compose project `dayflow`, Postgres volume `dayflow_pg`, and published ports `5173` (Vite), `8000` (API), `5433` (Postgres on the host; container still uses 5432). Host 5432 is often already taken. If a port is taken, change only the *host* mapping in `docker-compose.yml`.
- Local (non-compose) processes write PIDs to `.local/pids/` and you stop only those PIDs.
- Never restart, kill, or `docker compose down` a project that is not `dayflow`. Never point the API at a non-compose Postgres.
- Seed accounts come from `.env.example`. Never load production people, payroll, or documents.

## Completion checklist

Before declaring a feature complete, decide which rows apply and account for each applicable row.

| Dimension | Surfaces to consider |
|---|---|
| Entry points | Vue routes, AppShell nav, avatar menu (My Profile / Log out), FastAPI routers, seed/invite activation |
| Clients | Vue SPA at 360 px employee viewport; HR tables at 1024 px desktop |
| Providers/adapters | Postgres, console email, private object storage (documents/payslips are deferred unless the task says otherwise) |
| Contracts | Pydantic schemas, `frontend/src/types`, JWT claims, seed passwords |
| Reverse state | Sign-in/sign-out, check-in/check-out, submit/cancel pending leave, approve/reject, draft/finalize/publish |
| Modes | Employee vs HR, invite valid/expired/used, attendance open/closed/on-leave, payroll draft/finalized/published |
| Documentation | User-facing README commands; `docs/PRODUCT.md` / `docs/DOMAIN.md` if behavior or rules changed; `docs/STATE.md` for deferred work |
| Proof | Focused unit/API test for the rule; `docker compose` boot; employee and HR can complete the flow |

“Not supported” is a valid explicit decision. Silently omitting a surface is not.

Prototype done-when checks live in `docs/PRODUCT.md`.

## Failure traps learned from this project

1. **Signup role** — Public registration offered Employee vs HR. Cause: treating role as a form field. Correct path: first HR is seeded; every later role arrives on an invite.
2. **UI-only permission** — Employee opens another person's **payroll** or **edits** a coworker by URL. Cause: route guard without a matching server check. Correct path: FastAPI filters payroll and PATCH by self/HR; coworker profile GET is view-only. People nav stays HR-only.
3. **Punch overwrite** — Check-in form lets a user edit yesterday's times. Cause: attendance session treated as a writable timesheet. Correct path: create/close sessions with server time; corrections are a separate request HR reviews, with an audit event.
4. **Compose vs Hub** — Teammate asked to `docker pull` from Docker Hub and could not start. Cause: this repo ships source and a compose file, not published images. Correct path: clone Git, `cp .env.example .env`, `docker compose up --build`.

Only include traps that have occurred or are expensive enough to justify permanent context.

## Documentation boundary

- User documentation explains observable behavior and tasks. That is `README.md`.
- Maintainer documentation explains architecture, operations, and implementation constraints. That is this file plus `docs/PRODUCT.md` and `docs/DOMAIN.md`.
- Dated status and current work belong in `docs/STATE.md`, not this file.

## Project-specific delivery

- Base branch is `main`. Never commit to `main` directly.
- Each finished feature slice is its own branch and Pull Request (`feat/<stack>-<slice>`). Conventional Commits. No AI attribution.
- After the slice is implemented and local tests pass, open the PR. If GitHub Actions is green, squash-merge to `main` and delete the branch. There is no reviewer gate. If CI is red, one fix pass on that PR; if still red, leave the PR open. Never merge red CI.
- Stage only that slice's owned files. Do not stash, reset, or revert the other stack's in-progress work.
- Required local proof before opening the PR: the slice tests and type-check/pytest pass.
- No production deploy, public DNS, or Docker Hub publish unless Raja and the teammate explicitly ask.
