# Dayflow

Small-company HR operations: employees check in, request leave, and read payroll; HR reviews exceptions, approvals, and pay periods.

## Run with Docker

You need Docker Engine or Docker Desktop. You do **not** need a Docker Hub account.

```bash
git clone https://github.com/Anuraj-dev/DayFlow.git
cd DayFlow
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

Add them as a GitHub collaborator on this repo. They clone and run the same four commands. Do not publish images to Docker Hub for this hackathon.

A copy-paste agent prompt for their machine is in `docs/SETUP-PROMPT.md`.

## Local UI against compose API

```bash
docker compose up db backend
cd frontend && npm install && npm run dev
```

Vite proxies `/api` to `http://localhost:8000`.

## Agent guide

Coding agents should read `AGENTS.md` first.
