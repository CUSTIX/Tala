# Tala

Class record for Filipino teachers: attendance (seat plan, list, one by one, QR scan), seat plan
editor, DepEd grade computation, item analysis, recitation picker, read-only parent link.
Portfolio project: small, working end to end, free to build and run. Same conventions as RestoCore,
Abot and Batas. Original name, design and code; don't copy any existing app's branding or screens.

## Stack

Django 5.2, PostgreSQL 17, Docker Compose, pytest + pytest-django, ruff, GitHub Actions.
Server-rendered templates; `core/static/core/app.js` only enhances (every page works without it).
Strict CSP: no inline script, no inline style attribute (a test enforces it). QR codes: segno (SVG);
scanning: the browser's BarcodeDetector, else the vendored jsQR.

## Apps

- `core`: base model, security headers, rate limit, demo seeding (`demo.py`), QR helper, templates.
- `accounts`: custom `User` (teacher; `is_demo`), sign-in, "Try the demo", `purge_demo`.
- `classroom`: `Section`, `Learner`, seat plan services, picker, learner and parent pages.
- `attendance`: `Meeting` (class day), `Mark`; taking attendance, QR marking, monthly report.
- `grades`: `Assessment`, `Score`, `Item`, `Response`; DepEd math and item analysis in `services.py`.

## Commands

```
cp .env.example .env            # set WEB_PORT if 8000 is taken
docker compose up --build
docker compose run --rm web pytest
docker compose run --rm web ruff check . && docker compose run --rm web ruff format --check .
docker compose run --rm web python manage.py makemigrations
docker compose run --rm web python manage.py purge_demo
```

## Rules

- Every class URL loads the section with `selectors.section_for(request.user, pk)`: another
  teacher's class is a 404. `core/tests/test_access.py` walks every `/app/` URL; keep it passing.
- Grade math follows DepEd Order No. 8, s. 2015. Decimals only, never floats. Change weights or
  the transmutation only with a test from the order's tables.
- Demo data is made up (name lists in `core/demo.py`); never real learners. Demo accounts expire.
- Never commit `.env`, keys or real personal data.
- Stage explicit paths only. Never push without the owner confirming.
