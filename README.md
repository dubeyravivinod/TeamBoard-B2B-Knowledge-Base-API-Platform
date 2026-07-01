# TeamBoard — B2B Knowledge Base API Platform

Django + DRF backend powering TeamBoard: company registration/login with JWT
and API keys, a JWT-protected knowledge-base search endpoint with usage
logging, and an admin-only usage-summary endpoint.

## Setup

1. Create and activate a virtualenv, then install dependencies:
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate   # or .venv\Scripts\Activate.ps1 in PowerShell
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and set a real `DJANGO_SECRET_KEY`:
   ```bash
   cp .env.example .env
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
3. Start Postgres in Docker:
   ```bash
   docker compose up -d
   ```
4. Apply migrations:
   ```bash
   python manage.py migrate
   ```
5. Seed the knowledge base (12 entries across all 5 categories):
   ```bash
   python manage.py seed_kb
   ```
6. Run the dev server:
   ```bash
   python manage.py runserver
   ```

## Running tests

```bash
python manage.py test -v 2
```

## Promoting a company to ADMIN

The admin usage-summary endpoint requires `Company.role == 'admin'`. There is
no self-service way to become an admin (by design). To promote a company:
1. Register normally via `POST /api/auth/register/`.
2. In PGAdmin, open the `api_company` table and change that row's `role`
   column from `client` to `admin`.
3. Log in again via `POST /api/auth/login/` to get a fresh JWT reflecting
   the new role (the JWT itself doesn't encode role, but `has_permission()`
   re-reads `request.user.company.role` from the database on every request,
   so re-login isn't strictly required — it's just how the brief's manual
   test flow is written).

## API endpoints

- `POST /api/auth/register/` — public. Create a company account, receive a JWT + API key.
- `POST /api/auth/login/` — public. Log in, receive a fresh JWT + API key.
- `POST /api/kb/query/` — JWT required. Search the knowledge base; every call is logged.
- `GET /api/admin/usage-summary/` — JWT required, `role=admin` only. Platform-wide usage stats.

## Postman collection

Import `postman/TeamBoard.postman_collection.json` into Postman. Run
"Register - success" and "Login - success" first to populate the
`access_token` collection variable used by the KB Query requests. For the
Usage Summary "as ADMIN" request, manually set the `admin_access_token`
collection variable to a JWT obtained by logging in as a company promoted to
`admin` (see above).
