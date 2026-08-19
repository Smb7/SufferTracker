# SufferTracker

SufferTracker is a job application tracker with a .NET 8 API, PostgreSQL persistence, and Angular frontend.

## Local development

1. Start PostgreSQL and the API with `docker compose up --build`.
2. Open the Angular app at `http://localhost:4200` with `cd frontend` and `npm install && npm start`, or use the frontend container from Compose.
3. Explore the API contract at `http://localhost:8080/swagger` in Development.

The API applies EF Core migrations on startup for a frictionless local database. `src/JobTracker.Api/Database/001_initial.sql` is also retained as the reviewed PostgreSQL baseline for managed deployments.

## Project layout

- `src/JobTracker.Api`: authentication, JWT authorization, job CRUD, preferences, and parsing endpoints.
- `src/JobTracker.Tests`: xUnit tests for parsing behavior.
- `frontend`: standalone Angular application with guards, interceptor, dashboard, application capture, and settings.
- `.github/workflows/squidgate.yml`: required SquidGate PR security gate configured for DeepSeek V4 Flash.
- `.github/workflows/ci.yml`: backend tests, Angular build, and Docker build verification.
