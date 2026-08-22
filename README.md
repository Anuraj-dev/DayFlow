# DayFlow

Hackathon HRMS. Backend is FastAPI on Postgres; frontend is Vue. See `HACKATHON_GUIDE.md` for the product spec.

## Backend

```bash
docker compose up -d db
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --port 8000
```

Seed logins: `hr@dayflow.demo` / `ChangeMe_HR12!` and `employee@dayflow.demo` / `ChangeMe_Emp12!`.

```bash
cd backend && pytest
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```
