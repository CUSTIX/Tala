# Tala

**A class record for Filipino teachers: attendance from the seat plan or QR cards, DepEd grades
computed for you, and item analysis that shows what to reteach.** *Tala* is Filipino for "record"
(and "star").

Portfolio project. Django 5.2, PostgreSQL 17, Docker Compose, GitHub Actions. Free to build and
run. Demo learners are made up.

## What it does

| | |
|---|---|
| **Attendance, three ways** | Tap faces on the seat plan (Present → Late → Excused → Absent), go one by one through the list, or scan learners' QR cards with the phone camera. Any past day can be corrected. Monthly report with CSV export. |
| **Seat plan** | Tap a learner, tap a seat (or drag on a computer). Taken seats swap. Rearrange alphabetically, randomly, or boy-girl alternating. Resize the room, print it. |
| **Grade book** | Written work, performance tasks and quarterly assessment, weighted by subject group, then transmuted to the quarterly grade (DepEd Order No. 8, s. 2015). Final grade, descriptors, CSV export. |
| **Item analysis** | Check a quiz item by item: mean percentage score with its mastery level, and competencies sorted least mastered first. |
| **Recitation picker** | Random learner, only those present today, no repeats. |
| **Parent link** | Each learner has a private, read-only link to their attendance and scores. It can be replaced if it reaches the wrong person. |

"Try the demo" creates a private demo teacher with three classes of made-up learners, a month of
attendance and a quarter of scores. Each visitor gets their own copy, deleted after a day.

## Run it

```bash
cp .env.example .env            # Windows cmd: copy .env.example .env
docker compose up --build       # http://localhost:8000, then "Try the demo"
docker compose run --rm web pytest
docker compose run --rm web ruff check .
```

## Decisions

- **Grades are computed, not stored.** A quarterly grade is a pure function of the scores and the
  section's weights (`grades/services.py`), so it can never disagree with the scores. Decimals
  throughout; the transmutation table is tested at every band edge.
- **A missed quiz is blank, not zero.** Blank scores count as zero in the component total (like a
  paper class record) but are shown as missing, and item checking has a "took it" box per learner.
  Until every component has an assessment, the grade is computed over the components that do and
  labelled "so far".
- **Object-level access everywhere.** Every class page loads the class through one selector that
  filters by teacher, so another teacher's class is a 404. A test walks every `/app/` URL in the
  URLconf: anonymous visitors are sent to sign in, other teachers get 404, the owner gets the page.
- **Works without JavaScript.** Attendance is a form of radio buttons; the seat plan, one-by-one
  roll call and scanner enhance it. Strict Content Security Policy: no inline script or style
  (a test checks every template), jsQR is served from the app, not a CDN.
- **The camera stays on the phone.** The scanner decodes QR cards in the browser (BarcodeDetector,
  or the bundled jsQR) and sends only the card's code. A card from another class is refused.
- **Demo isolation.** One demo teacher per visitor (rate-limited per IP), purged on start after
  `DEMO_TTL_HOURS`. Names are common Filipino first names and surnames combined at random.
- **Stateless web container.** All state in Postgres (sessions, rate-limit counters via the
  database cache). Render free web service + Neon free Postgres; see `docs/deploy.md`.

## Tests

`pytest` covers the grade math against worked examples, seat plan moves and arrangements,
attendance by every method, item analysis, the demo, rate limits, security headers and the access
walk over every URL. CI also runs ruff, a migrations check, `check --deploy`, pip-audit and a
production image build.

## Not included

Real accounts for schools (sign-up is closed; the demo is the way in), offline sync, SF2/SF9 form
layouts, and SHS semester grading. Grading rules can change: check the current DepEd order before
relying on any computed grade.

## License

MIT
