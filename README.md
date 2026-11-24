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
- **Mobile app planned (later).** The API lives under `/api/v1/` so published app versions
  keep working while the web evolves. Web uses session cookies; the mobile app signs in with
  `POST /api/v1/auth/token/` and sends `Authorization: Token <key>` (the app itself is not built). Business rules stay in Django services,
  never in React, so a mobile client gets identical behaviour.
- **Hosted locally until the system is finished.** No production deployment yet; run the
  steps below. Production hardening (gunicorn behind a reverse proxy, backups) comes later.
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

Tests: `cd backend && pytest` (set `DJANGO_DB=sqlite` if you have no Postgres; `DJANGO_DEBUG=1` for local runs) and
`cd frontend && npm test`.

After changing the API: `cd backend && python manage.py spectacular --file schema.yml`
then `cd frontend && npm run api:types`.

## Status

**Ported from the old project (phase A, accounting core):**
chart of accounts, customers/suppliers, journal entries, posting rules, trial balance,
general ledger, customer/supplier statement, roles. Everything is per company.

- Rules live in `backend/accounting/services.py` (the API only calls them). Posted
  entries are immutable, enforced in the model as well as the service. Posting locks the
  entry row. A line is debit or credit, positive, on a leaf account, and lines on
  receivable/payable accounts need a customer/supplier.
- Reports live in `backend/accounting/reports.py` and are scoped to one company.
- Roles are per company (`core.Membership`): accountant, reviewer, chief accountant,
  system admin. The capability map is `backend/core/permissions.py`.
- Every request names its company with the `X-Company-Id` header (optional when the user
  belongs to only one). A user can never act in a company they are not a member of.

New company with the default chart of accounts:

```bash
python manage.py seed_company "My Company" --user yourusername --role chief_accountant
```

**Treasury (phase B):** vouchers (collect, refund, deposit, fund the expenses box, pay an
expense, pay a supplier) are journal entries built by `backend/treasury/services.py`; cash
counts by denomination with book-vs-counted difference and an optional draft shortage/overage
entry (account 510). Box figures show posted, pending (draft) and book balance.

**Inventory (phase C):** units, warehouses, products; goods receipts (each creates FIFO layers,
item-card movements and a draft entry DR 105 Inventory / CR 210 Goods received not invoiced);
transfers that move the consumed layers with their cost; stock counts; stock levels with a
comparison against the ledger; item card; a single-user lock per company (15 minutes idle).
A receipt or transfer is locked once its entry is posted or its stock has been used.

**Sign-in:** `GET /api/v1/auth/csrf/`, then `POST /api/v1/auth/login/` with the token in
`X-CSRFToken`; `POST /api/v1/auth/logout/`. Logged-out requests answer 403 (session auth).

**Journal links:** entries made by a stock receipt or a cash count carry a `source`. Receipt
entries are edited only from the receipt; cash-count entries cannot be edited (post or delete
only). Receipts, transfers and counts are numbered per company (RC-/TR-/CNT-00001).

**Users:** a system admin manages the company's members in the app or at `/api/v1/users/`
(add, change role, reset password, remove). Nobody can change their own access.

**Mobile sign-in:** `POST /api/v1/auth/token/` returns a key; `POST /api/v1/auth/token/revoke/`
signs out. Same permissions as the web.

**Arabic messages:** API errors follow `Accept-Language` (the web app sends it). After adding
or changing any user-facing backend text run `python scripts/make_messages.py` (extracts,
merges, compiles, and lists what still needs an Arabic translation); CI runs it with `--check`
and fails if anything is untranslated or the committed files are stale.

**Frontend:** sign-in, company switcher, Arabic RTL / English LTR, and screens for journal
entries, customers & suppliers, chart of accounts, treasury (vouchers, cash counts), inventory
(stock levels, item card, receipts, transfers, counts, products/warehouses/units), reports
(trial balance, ledger, statement) and users. Browser tests: `cd frontend && npx playwright test`
against a running backend and Vite (see `playwright.config.ts`; set `LOGIN_THROTTLE=1000/min`
on the backend for the test run, because every test signs in).

**Not built yet:** AI draft features, the mobile app, production deployment (gunicorn, HTTPS,
backups). Accounts 504 and 505 exist in the chart but nothing posts to them yet.
