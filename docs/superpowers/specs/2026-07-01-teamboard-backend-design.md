# TeamBoard Backend — Design Spec

Date: 2026-07-01

## 1. Purpose

TeamBoard is a B2B Knowledge Base API platform. Companies register, receive an
API key + JWT, and query a curated Q&A knowledge base through a JWT-protected
endpoint. Every query is logged for usage-based billing. A platform admin can
view aggregate usage statistics. This spec covers the initial backend: 4
endpoints, 3 models, JWT auth, and Docker-based Postgres.

## 2. Project layout & tooling

```
teamboard/                  # Django project root
├── manage.py
├── requirements.txt
├── .env                    # gitignored — DB creds, SECRET_KEY
├── .env.example            # committed template
├── docker-compose.yml       # Postgres only
├── README.md
├── postman/
│   └── TeamBoard.postman_collection.json
├── teamboard/               # project package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
└── api/                     # single app, per brief
    ├── models.py            # Company, KBEntry, QueryLog
    ├── signals.py           # post_save on User
    ├── apps.py              # ready() wires signals
    ├── permissions.py       # IsAdminUser
    ├── serializers.py
    ├── views.py             # 4 APIViews
    ├── urls.py
    ├── admin.py             # register models for easy inspection
    ├── management/commands/seed_kb.py
    └── tests/
        ├── test_auth.py
        ├── test_kb_query.py
        └── test_usage_summary.py
```

- Postgres runs via `docker-compose.yml` (single `db` service, named volume,
  port 5432 exposed). Django runs locally (`venv` + `runserver`), reading
  connection settings from `.env` via `python-dotenv`.
- `requirements.txt` pins exact versions of: `Django`, `djangorestframework`,
  `djangorestframework-simplejwt`, `psycopg2-binary`, `python-dotenv` (latest
  stable versions resolved at implementation time).
- Global DRF config in `settings.py`:
  ```python
  REST_FRAMEWORK = {
      'DEFAULT_AUTHENTICATION_CLASSES': [
          'rest_framework_simplejwt.authentication.JWTAuthentication',
      ],
      'DEFAULT_PERMISSION_CLASSES': [
          'rest_framework.permissions.IsAuthenticated',
      ],
  }
  ```
  Register and Login override both to `[]` per-view, since they must be
  reachable without a token.

## 3. View architecture decision

All 4 endpoints are implemented as class-based `rest_framework.views.APIView`
subclasses (not function-based `@api_view` or DRF generics/viewsets). Three of
the four endpoints do more than plain CRUD (register composes User + Company +
JWT; query wraps search + atomic logging; usage-summary does aggregation), so
generics would fight the requirements rather than simplify them. APIView also
matches the brief's literal pattern of setting `authentication_classes = []`
and `permission_classes = []` per view — the auth posture of every endpoint is
explicit and visible at the class definition, not inherited implicitly.

## 4. Models & signal

Models are implemented exactly as specified in the brief (Section 3 of the
brief) — no field name changes.

**Signal behavior clarification:** the brief's sample `signals.py` sets
`company_name=instance.email` as a placeholder value that the register view
then overwrites. To avoid depending on execution order between the signal and
the view, the signal instead creates the `Company` with `company_name=""`
(blank). The register view is the only place that meaningfully sets
`company_name`. `role` is never touched by the signal or the view from
request data — it always uses the model's `default=Role.CLIENT`. `api_key` is
generated in the signal via `secrets.token_urlsafe(32)`, detected via
`instance._state.adding`, and connected in `AppConfig.ready()`.

**id field type:** `KBEntry.id` is a standard Django `AutoField` (integer).
The brief's example response shows `"id": "1"` (string), but this is treated
as informal example formatting, not a deliberate requirement — the serializer
emits the natural integer type (`"id": 1`).

## 5. Endpoints

### 5.1 `POST /api/auth/register/`
- `authentication_classes = []`, `permission_classes = []`.
- Validates request body (`username`, `password`, `company_name`, `email`)
  via a serializer.
- Duplicate `username` → `400` with a clear field error, checked explicitly
  before creation (not via a caught `IntegrityError`).
- Creates the `User` inside `transaction.atomic()` so a mid-request failure
  (e.g. token generation) can't leave an orphaned `User`/`Company` row. The
  `post_save` signal auto-creates the `Company` inside the same transaction.
- View updates `company.company_name` from the request payload after
  creation (`api_key` is never set manually).
- Generates a JWT access token via SimpleJWT (`RefreshToken.for_user` or
  equivalent) and returns `{username, company_name, api_key, access}` — `201`.

### 5.2 `POST /api/auth/login/`
- `authentication_classes = []`, `permission_classes = []`.
- Validates credentials via Django's `authenticate()`.
- Invalid credentials → `401 {"detail": "Invalid username or password."}`.
- Success → `{access, company_name, api_key}` — `200`.

### 5.3 `POST /api/kb/query/`
- Default global auth/permissions apply (JWT required) → no token yields
  `401` automatically via DRF.
- `search` missing/blank → `400` via serializer field validation.
- Company is taken from `request.user.company`, never from the request body.
- Inside a single `transaction.atomic()` block: run
  `Q(question__icontains=search) | Q(answer__icontains=search)`, get
  `.count()`, and create the `QueryLog` row (`company`, `search_term`,
  `results_count`) — all three happen together or not at all.
- Zero matches → `200` with `count: 0`, `results: []`; the `QueryLog` is still
  written (usage-based billing counts queries made, not answers found).

### 5.4 `GET /api/admin/usage-summary/`
- `permission_classes = [IsAdminUser]` (custom class in `permissions.py`,
  extends `BasePermission`, overrides `has_permission()` to check
  `request.user.company.role == Company.Role.ADMIN`). Never uses `is_staff`
  or `is_superuser`.
- CLIENT role → `403` (DRF default detail message).
- Aggregates via:
  - `QueryLog.objects.aggregate(total=Count('id'))` → `total_queries`
  - `QueryLog.objects.values('company').distinct().count()` → `active_companies`
  - `QueryLog.objects.values('search_term').annotate(count=Count('id')).order_by('-count')[:5]` → `top_search_terms`

## 6. Error handling summary

| Case | Status | Body shape |
|---|---|---|
| Register — duplicate username | 400 | `{"username": [...]}` |
| Login — bad credentials | 401 | `{"detail": "Invalid username or password."}` |
| Query — missing/blank search | 400 | `{"search": [...]}` |
| Query — no token | 401 | DRF default |
| Query — zero matches | 200 | `{"search", "count": 0, "results": []}` (QueryLog still written) |
| Usage summary — CLIENT role | 403 | DRF default |
| Usage summary — no token | 401 | DRF default |

No endpoint returns 404 for a "nothing found" case — that scenario is only
the empty-search-results case, which is explicitly a 200.

## 7. KB seeding

A Django management command, `api/management/commands/seed_kb.py`, inserts at
least 10 `KBEntry` rows spanning all 5 categories, with deliberate keyword
overlap (e.g. multiple entries mentioning "select_related", "JWT", "Q
objects") so searches return multiple results. The command is idempotent
(safe to re-run without duplicating rows, e.g. via `get_or_create` keyed on
`question`).

## 8. Testing strategy

DRF `APITestCase` suites under `api/tests/`, grouped by endpoint:

- **`test_auth.py`**: register success (JWT + api_key present), duplicate
  username → 400, role always CLIENT regardless of payload; login success,
  wrong password → 401, nonexistent user → 401.
- **`test_kb_query.py`**: 401 without token, 200 with matches, 200 with zero
  results (and confirms a `QueryLog` row was still written), blank search →
  400, confirms the logged `company` is `request.user.company` and cannot be
  overridden from the request body.
- **`test_usage_summary.py`**: 403 for CLIENT, 200 with correct aggregates
  for ADMIN, verifies top-5 ordering by count.

This suite is a development safety net; it does not replace the required
Postman collection deliverable.

## 9. Postman collection

`postman/TeamBoard.postman_collection.json` (Collection format v2.1),
hand-authored, with 11 named requests:

1. Register — success
2. Register — duplicate username (400)
3. Login — success
4. Login — bad credentials (401)
5. KB Query — with results
6. KB Query — zero results
7. KB Query — missing search field (400)
8. KB Query — no token (401)
9. Usage Summary — as ADMIN (200)
10. Usage Summary — as CLIENT (403)
11. Usage Summary — no token (401)

Uses a collection variable `{{access_token}}`, populated by a test script on
the register/login requests, so the chain is runnable end-to-end without
manual copy-paste of tokens.

## 10. README

Covers: Docker Postgres setup (`docker-compose up -d`), creating `.env` from
`.env.example`, Python venv setup, `pip install -r requirements.txt`,
`manage.py migrate`, `manage.py seed_kb`, running the dev server, and how to
import/run the Postman collection.

## 11. Out of scope

- Refresh token flow (brief only asks for `access` tokens).
- Rate limiting / throttling.
- Company self-service key rotation.
- Pagination on `/api/kb/query/` results (brief's example implies a full
  result list; no page size is specified).
