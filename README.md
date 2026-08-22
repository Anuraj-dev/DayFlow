# Dayflow

Small-company HR operations: employees check in, request leave, and read payroll; HR reviews exceptions, approvals, and pay periods.

The original hackathon problem write-up is in `HACKATHON_GUIDE.md`. How we actually built it is in `AGENTS.md` and `docs/`.

## Run with Docker

You need Docker Engine or Docker Desktop. You do **not** need a Docker Hub account.

```bash
git clone https://github.com/Anuraj-dev/DayFlow.git
cd DayFlow
git checkout main
git pull
cp .env.example .env
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173).

| Account | Email | Password |
|---|---|---|
| HR | `hr@dayflow.demo` | `ChangeMe_HR12!` |
| Employee | `employee@dayflow.demo` | `ChangeMe_Emp12!` |

| Service | URL |
|---|---|
| Vue app | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Postgres | localhost:5433 (container 5432) |

Stop only this stack with `docker compose down`. Data stays in the `dayflow_pg` volume until you run `docker compose down -v`.

## Share with a teammate

Add them as a GitHub collaborator. They clone and run the same commands. Do not publish images to Docker Hub for this hackathon.

A copy-paste agent prompt for their machine is in `docs/SETUP-PROMPT.md`.

## Local UI against compose API

```bash
docker compose up -d db backend
cd frontend && npm install && npm run dev
```

Vite proxies `/api` to `http://localhost:8000`.

## Tests

```bash
docker compose exec backend pytest
npm --prefix frontend run test:unit -- --run
```

Host pytest against published Postgres:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://dayflow:dayflow@localhost:5433/dayflow pytest
```

## Docs

| File | For |
|---|---|
| `AGENTS.md` | Coding agents working in this repo |
| `docs/PRODUCT.md` | Pages, flows, definition of done |
| `docs/DOMAIN.md` | Tables and business rules |
| `docs/UI.md` | Odoo 19 shell and tokens |
| `docs/STATE.md` | What is shipped vs deferred |
| `HACKATHON_GUIDE.md` | Original problem assessment |
