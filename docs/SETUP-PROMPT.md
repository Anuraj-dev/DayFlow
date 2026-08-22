# Setup prompt for a teammate's coding agent

Paste this into the agent's first message on a machine that has Docker installed.

```text
Set up the Dayflow hackathon repo on this machine so I can run the app locally.

Repo: https://github.com/Anuraj-dev/DayFlow.git
Read AGENTS.md, README.md, and docker-compose.yml before changing anything.

Do this and then stop:

1. Clone the repo if it is not already the current workspace. Do not fork unless GitHub access fails.
2. Copy `.env.example` to `.env` only if `.env` does not exist. Do not commit `.env`.
3. Confirm Docker Engine is running (`docker compose version`). If it is not, tell me how to start it on this OS and stop.
4. From the repo root run `docker compose up --build -d` and wait until `db`, `backend`, and `frontend` are healthy or running.
5. Prove it:
   - `curl -sS http://localhost:8000/api/health`
   - `curl -sS -X POST http://localhost:8000/api/auth/sign-in -H 'Content-Type: application/json' -d '{"email":"hr@dayflow.demo","password":"ChangeMe_HR12!"}'`
   - Open or curl `http://localhost:5173` and confirm the sign-in page is served.
6. Report the URLs and the two seed accounts from `.env.example`.

Rules:

- Share and run source through Git + Compose. Do not docker login, docker push, or use Docker Hub.
- Do not kill, restart, or `docker compose down` any project except compose project `dayflow`.
- Do not change published host ports unless a port is already taken; if a port is taken, change only the host side and tell me the new ports. Dayflow already publishes Postgres on host 5433 for this reason.
- Do not implement product features in this pass.
- If clone fails because the repo is private, stop and tell me to add this GitHub user as a collaborator.
```
