# Setup prompt for a teammate's coding agent

Paste the following prompt into a coding agent on a machine with Docker installed.

```text
Set up the Dayflow repository so I can run the hackathon MVP locally.

Repository: https://github.com/Anuraj-dev/DayFlow.git

Read README.md, AGENTS.md, and docker-compose.yml before changing anything.

1. Clone the repository if it is not already the current workspace.
2. Check out main and pull the latest changes.
3. Copy .env.example to .env only when .env does not already exist. Never commit .env.
4. Confirm Docker Engine and Compose v2 are available.
5. From the repository root, run:

   docker compose up --build -d

6. Wait until db is healthy and backend/frontend are running.
7. Verify:

   curl -fsS http://localhost:8000/api/health
   curl -fsS http://localhost:5173/

8. Report the application URLs and the two demo accounts from README.md.

Rules:

- Use the Git repository and Compose source build. Do not docker login, docker pull project images,
  docker push, or publish to Docker Hub.
- Use Compose project dayflow, ports 5173, 8000, and 5433, and volume dayflow_pg.
- If a host port is taken, change only the host-side mapping and report the replacement port.
- Never stop or remove another Docker project.
- Do not run backend pytest against the presentation database; backend tests recreate their database.
- Do not implement product features in this setup pass.
- If the repository is private and cloning fails, stop and report that GitHub access is required.
```
