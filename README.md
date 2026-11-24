# Accounting ERP

Django + React rebuild of the accounting/inventory ERP. Django is the backend only
(REST API, business rules, PostgreSQL). React is the frontend. Arabic (right-to-left)
and English are both first-class.

## Stack (versions checked 2026-11-24)

| Layer | Choice | Version |
|---|---|---|
| Language | Python | 3.13 |
| Backend | Django | 6.1.3 |
| API | Django REST Framework | 3.18.3 |
| API schema | drf-spectacular | 0.30.0 |
| Audit history | django-simple-history | 3.13.0 |
| Database driver | psycopg | 3.3.9 |
| Database | PostgreSQL | 18 by default (19.0 released 2026-11-19; see note) |
| App server | gunicorn | 27.0.1 |
| Excel export | openpyxl | 3.1.5 |
| Backend tests | pytest-django | 4.14.0 |
| Frontend | React | 19.3.1 |
| Build tool | Vite | 8.3.x |
| Language | TypeScript | **6.0.3** (7.0.2 is out, see note) |
| Routing | react-router | 8.5.2 |
| Server state | TanStack Query | 5.108.4 |
| Tables | TanStack Table | 9.3.1 |
| Forms | react-hook-form + zod | 7.92.0 / 4.6.7 |
| Styling | Tailwind CSS | 4.3.5 |
| Translations | i18next + react-i18next | 27.2.7 / 18.0.3 |
| Money | decimal.js | 10.6.0 |
| API types | @hey-api/openapi-ts | 0.97.0 (types only) |
| Frontend tests | Vitest, Playwright | 5.1.1 / 1.65.1 |

### Version decisions

- **TypeScript 6, not 7.** TS 7.0.2 is the newest, but it removed the old JavaScript
  compiler API that OpenAPI code generators use. `@hey-api/openapi-ts` crashes on it
  (`ts.NewLineKind` is undefined) and `openapi-typescript` declares TS 5 only. Move to
  TS 7 once the generator supports it.
- **PostgreSQL 18 by default.** 19.0 is days old; for an accounting database wait for
  the first point releases. Set `POSTGRES_VERSION=19` to try it.
- **`@hey-api/openapi-ts` 0.97.0 is pinned** and `npm audit` still reports one moderate
  finding (prototype pollution in the generated client template). We only generate
  types, never the client, and it runs at build time on our own schema. Newer versions
  fix that finding but pull in a vulnerable `js-yaml` (high, CPU exhaustion). Revisit.

## Design decisions

- **Same-origin session auth.** React and `/api` share one origin (Vite proxy in dev,
  reverse proxy in production), so cookies + CSRF work and there is no CORS or JWT.
- **Multi-company from day one.** `core.Company`, `core.Membership` and the abstract
  `core.CompanyOwned` base every business table must inherit. Changing this later
  touches every table.
- **Money is a string in JSON** and a `Decimal` in Python and `decimal.js`. Never a float.
- **AI never posts entries.** Later features save drafts that an accountant approves.

## Run it

```bash
# Postgres
docker compose up -d db

# Backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env       # then edit; docker compose reads it for the database
set -a; . ../.env; set +a        # Django reads real environment variables, not the file
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Frontend (another terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173, proxies /api to :8000
```

Tests: `cd backend && pytest` (set `DJANGO_DB=sqlite` if you have no Postgres) and
`cd frontend && npm test`.

After changing the API: `cd backend && python manage.py spectacular --file schema.yml`
then `cd frontend && npm run api:types`.

## Status

Skeleton only: tenancy models, health and `me` endpoints, translations, RTL switch,
money helpers, CI. The accounting and inventory domain code from the old Django
project is not ported yet. Planned order: services first (move rules out of views and
admin), then the API, then one React screen at a time.
