# SufferTracker

SufferTracker is a job application tracker with a FastAPI backend, PostgreSQL persistence, and Angular frontend. The goal is to enable a easy, clean, data minded tracker for job applications. 

## Local development

1. Start PostgreSQL and the API with `docker compose up --build`.
2. Open the Angular app at `http://localhost:4200` with `cd frontend` and `npm install && npm start`, or use the frontend container from Compose.
3. Explore the API contract at `http://localhost:8080/docs` in development. `/swagger` redirects there.

The API applies Alembic migrations on startup. This schema is new and does not read the old .NET tables. Existing accounts need to register again. To drop the old database volume once, run `docker compose down` and remove the `postgres-data` volume before the first FastAPI start.

The admin sign-in map uses CARTO raster tiles. Request a free key at https://carto.com/basemaps/apikey and store it as the GitHub Actions secret `MAP_APIKEY` (or set it in `.env`).

Screenshot OCR is provider-neutral. Set `OCR_ENDPOINT`, `OCR_API_KEY`, and optionally `OCR_API_KEY_HEADER` before starting Compose. The endpoint accepts a multipart field named `image` and may return `{ "text": "..." }`, `{ "content": "..." }`, or Azure Read-style `analyzeResult.readResults[].lines[].text` JSON. Without an endpoint, the API returns a reviewable pending state instead of failing account workflows.

## Project layout

- `backend`: FastAPI service for authentication, JWT authorization, MFA, admin, job CRUD, preferences, and parsing.
- `frontend`: standalone Angular application with guards, interceptor, dashboard, application capture, and settings.
- `.github/workflows/squidgate.yml`: required SquidGate PR security gate configured for DeepSeek V4 Flash.
- `.github/workflows/ci.yml`: FastAPI tests with a 70% coverage gate, Angular build, and Docker build verification.
- `.github/workflows/lint.yml`: Ruff on the API and ESLint on the Angular app.

