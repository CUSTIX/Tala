# Deploying Tala (free)

| Piece | Service | Notes |
|---|---|---|
| Web | Render free web service (Docker, Singapore) | `render.yaml`; sleeps after 15 min idle, the heartbeat keeps it awake |
| Database | Neon free Postgres 17 | use the direct host (without `-pooler`) |

Render's free plan gives 750 instance hours per workspace per month, enough for one always-on
service. Put Tala in its own workspace if another always-on demo already uses the hours.

## One-time setup

1. **Neon**: create a project (Singapore, Postgres 17), copy the connection string with pooling
   off.
2. **Render**: New > Blueprint > pick this repo. Paste the Neon string as `DATABASE_URL` (set only
   in the dashboard, never in the repo).
3. Check `https://tala-ph.onrender.com/livez/` and `/healthz/`, then "Try the demo".

## What runs on start (`bin/start.sh`)

1. `migrate`
2. `createcachetable` (rate-limit counters use the database cache, shared by every worker)
3. `purge_demo` (deletes demo teachers older than `DEMO_TTL_HOURS`, with their classes)
4. gunicorn: 2 workers x 4 threads, no query strings in the access log

## Environment variables

Every variable is documented in `.env.example` (a test enforces it).

## Before every deploy

`pytest`, `ruff check .`, `ruff format --check .`, and `python manage.py check --deploy` with
production settings. CI runs all of them, and Render deploys only after CI passes.
