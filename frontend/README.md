# Dayflow frontend

Vue 3 + TypeScript single-page application for Dayflow.

Run the complete application from the repository root with:

```bash
docker compose up --build
```

For host-side frontend development against the Compose API:

```bash
docker compose up -d db backend
npm install
npm run dev
```

The Vite server proxies `/api` to `http://localhost:8000` by default. See the root
[README](../README.md) for setup, demo accounts, product flows, tests, and documentation links.
