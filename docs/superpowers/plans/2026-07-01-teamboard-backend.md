# TeamBoard Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the TeamBoard Django + DRF backend: company registration/login with JWT + auto-generated API keys, a JWT-protected knowledge-base search endpoint with usage logging, and an admin-only usage-summary endpoint — backed by a Dockerized Postgres database.

**Architecture:** A single Django project (`teamboard`) with a single app (`api`) containing 3 models (`Company`, `KBEntry`, `QueryLog`), a `post_save` signal that auto-provisions a `Company` + API key whenever a `User` is created, 4 class-based `APIView` endpoints, a custom `IsAdminUser` permission, and a `seed_kb` management command. Postgres runs in Docker; Django runs locally against it via `python-dotenv`-loaded credentials.

**Tech Stack:** Django 5.1.4, djangorestframework 3.15.2, djangorestframework-simplejwt 5.3.1, psycopg2-binary 2.9.10, python-dotenv 1.0.1, PostgreSQL 16 (Docker), Django's built-in test runner (`manage.py test` / DRF `APITestCase`).

## Global Constraints

- `authentication_classes = []` and `permission_classes = []` ONLY on `RegisterView` and `LoginView`. Every other view relies on the global `REST_FRAMEWORK` defaults (JWT required).
- `Company.role` always defaults to `CLIENT` via the model field default. No view ever reads or sets `role` from request data.
- `Company.api_key` is set ONLY inside the `post_save` signal via `secrets.token_urlsafe(32)`. No view ever sets `api_key` manually.
- The signal detects first creation via `instance._state.adding`, not `created` alone being sufficient on its own — both are checked as specified in the brief (`if created:` inside the receiver, which Django guarantees is only `True` on first insert; `_state.adding` is the underlying mechanism Django uses to compute `created`).
- `KBEntry.id` is serialized as a plain integer (`"id": 1`), not a string, per design spec Section 4.
- In `POST /api/kb/query/`, the search, count, and `QueryLog` creation happen inside one `transaction.atomic()` block. A zero-match search still returns `200` and still writes a `QueryLog` row.
- `POST /api/kb/query/` reads the company from `request.user.company` only — never from the request body, even if the body includes a `company` field.
- `IsAdminUser` (in `api/permissions.py`) checks `request.user.company.role == Company.Role.ADMIN`. Never `is_staff` or `is_superuser`.
- All DB credentials and `SECRET_KEY` live in `.env` (gitignored); `.env.example` is committed as a template. Nothing is hardcoded in `settings.py`.
- Postgres runs in Docker (`docker-compose.yml`, single `db` service). Django itself runs locally via a virtualenv, not in a container.
- `requirements.txt` pins exact versions (see Tech Stack above).

---

## Task 1: Project Setup, Docker Postgres, Base Django Config

**Files:**
- Create: `requirements.txt`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.env` (local only — not committed)
- Create: `.gitignore`
- Create: `manage.py`, `teamboard/settings.py`, `teamboard/urls.py`, `teamboard/wsgi.py`, `teamboard/asgi.py`, `teamboard/__init__.py` (via `django-admin startproject`)
- Create: `api/` app skeleton via `manage.py startapp api` (then delete the generated `api/tests.py` in favor of an `api/tests/` package)
- Create: `api/tests/__init__.py`
- Create: `api/urls.py` (empty `urlpatterns` for now)
- Modify: `teamboard/settings.py`
- Modify: `teamboard/urls.py`

**Interfaces:**
- Produces: a running Postgres instance reachable at `localhost:5432` with credentials from `.env`; `INSTALLED_APPS` includes `rest_framework`, `rest_framework_simplejwt`, `api`; `REST_FRAMEWORK` global defaults set; `api.urls` included at `/api/` in the project URLconf. All later tasks add models/views/urls on top of this.

- [ ] **Step 1: Create requirements.txt**

```text
Django==5.1.4
djangorestframework==3.15.2
djangorestframework-simplejwt==5.3.1
psycopg2-binary==2.9.10
python-dotenv==1.0.1
```

- [ ] **Step 2: Create and activate a virtualenv, install dependencies**

Run:
```bash
python -m venv .venv
source .venv/Scripts/activate   # Git Bash on Windows; use .venv\Scripts\Activate.ps1 in PowerShell
pip install -r requirements.txt
```
Expected: all 5 packages (and their transitive deps) install with no errors.

- [ ] **Step 3: Scaffold the Django project and app**

Run:
```bash
django-admin startproject teamboard .
python manage.py startapp api
```
Expected: `manage.py`, `teamboard/` package, and `api/` package now exist in the repo root.

- [ ] **Step 4: Replace the generated api/tests.py with a tests package**

Run:
```bash
rm api/tests.py
mkdir -p api/tests
touch api/tests/__init__.py
```

- [ ] **Step 5: Write docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - teamboard_pgdata:/var/lib/postgresql/data

volumes:
  teamboard_pgdata:
```

- [ ] **Step 6: Write .env.example (committed template)**

```text
DJANGO_SECRET_KEY=change-me-to-a-random-secret-key
DJANGO_DEBUG=True
POSTGRES_DB=teamboard
POSTGRES_USER=teamboard
POSTGRES_PASSWORD=teamboard
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

- [ ] **Step 7: Create .env (local, not committed) with the same keys**

Run:
```bash
cp .env.example .env
```
Then edit `DJANGO_SECRET_KEY` in `.env` to a real random value, e.g. via:
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

- [ ] **Step 8: Write .gitignore**

```text
.venv/
venv/
__pycache__/
*.pyc
.env
db.sqlite3
*.log
```

- [ ] **Step 9: Update teamboard/settings.py**

At the top of the file, add the dotenv loading (before any `os.environ.get` calls):

```python
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
```

Replace the generated `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` with:

```python
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'insecure-dev-key')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']
```

Update `INSTALLED_APPS` to include (in addition to the Django defaults already generated):

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'api',
]
```

Replace the generated `DATABASES` block with:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'teamboard'),
        'USER': os.environ.get('POSTGRES_USER', 'teamboard'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'teamboard'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}
```

Add at the end of the file:

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

- [ ] **Step 10: Create api/urls.py with empty urlpatterns**

```python
from django.urls import path

urlpatterns = []
```

- [ ] **Step 11: Wire api.urls into teamboard/urls.py**

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]
```

- [ ] **Step 12: Start Postgres and verify Django can connect**

Run:
```bash
docker compose up -d
python manage.py migrate
```
Expected: Docker reports the `db` container running/healthy, and `migrate` applies Django's built-in migrations (`admin`, `auth`, `contenttypes`, `sessions`) against Postgres with no connection errors.

- [ ] **Step 13: Commit**

```bash
git add requirements.txt docker-compose.yml .env.example .gitignore manage.py teamboard api
git commit -m "Scaffold Django project, api app, Docker Postgres, and DRF/JWT config"
```

---

## Task 2: Models (Company, KBEntry, QueryLog) + Admin Registration

**Files:**
- Create: `api/models.py`
- Create: `api/admin.py`
- Create: `api/tests/test_models.py`
- Modify: (migrations generated by `makemigrations`, not hand-written)

**Interfaces:**
- Consumes: `django.contrib.auth.models.User` (built-in).
- Produces: `Company` (fields: `user`, `company_name`, `api_key`, `role`, `created_at`; `Company.Role.ADMIN` / `Company.Role.CLIENT` choices), `KBEntry` (fields: `question`, `answer`, `category`, `created_at`; `KBEntry.Category.{API,DATABASE,CLOUD,FRAMEWORK,GENERAL}`), `QueryLog` (fields: `company` FK, `search_term`, `results_count`, `queried_at`). All three are consumed by every later task.

- [ ] **Step 1: Write the model tests**

```python
# api/tests/test_models.py
from django.test import TestCase

from api.models import Company, KBEntry


class KBEntryModelTest(TestCase):
    def test_create_kb_entry(self):
        entry = KBEntry.objects.create(
            question='What is a test?',
            answer='A test verifies behavior.',
            category=KBEntry.Category.GENERAL,
        )
        self.assertEqual(entry.category, 'general')
        self.assertEqual(str(entry), 'What is a test?')


class CompanyModelTest(TestCase):
    def test_role_field_defaults_to_client(self):
        self.assertEqual(Company._meta.get_field('role').default, Company.Role.CLIENT)

    def test_api_key_field_allows_blank_at_field_level(self):
        self.assertTrue(Company._meta.get_field('api_key').blank)
```

- [ ] **Step 2: Run the tests to verify they fail (models don't exist yet)**

Run: `python manage.py test api.tests.test_models -v 2`
Expected: FAIL/ERROR — `ImportError: cannot import name 'Company' from 'api.models'`.

- [ ] **Step 3: Write api/models.py**

```python
from django.contrib.auth.models import User
from django.db import models


class Company(models.Model):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        CLIENT = 'client', 'Client'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='company',
    )
    company_name = models.CharField(max_length=255)
    api_key = models.CharField(max_length=64, unique=True, blank=True)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CLIENT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name


class KBEntry(models.Model):
    class Category(models.TextChoices):
        API = 'api', 'API'
        DATABASE = 'database', 'Database'
        CLOUD = 'cloud', 'Cloud'
        FRAMEWORK = 'framework', 'Framework'
        GENERAL = 'general', 'General'

    question = models.TextField()
    answer = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question[:80]


class QueryLog(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='query_logs',
    )
    search_term = models.CharField(max_length=255)
    results_count = models.IntegerField()
    queried_at = models.DateTimeField(auto_now_add=True)
```

- [ ] **Step 4: Generate and apply the migration**

Run:
```bash
python manage.py makemigrations api
python manage.py migrate
```
Expected: `Migrations for 'api': api/migrations/0001_initial.py` listing the 3 new models, then `migrate` applies it cleanly.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python manage.py test api.tests.test_models -v 2`
Expected: PASS (2 tests).

- [ ] **Step 6: Register models in admin.py**

```python
# api/admin.py
from django.contrib import admin

from .models import Company, KBEntry, QueryLog

admin.site.register(Company)
admin.site.register(KBEntry)
admin.site.register(QueryLog)
```

- [ ] **Step 7: Commit**

```bash
git add api/models.py api/admin.py api/migrations api/tests/test_models.py
git commit -m "Add Company, KBEntry, QueryLog models with admin registration"
```

---

## Task 3: Signal — Company Auto-Creation and API Key Generation

**Files:**
- Create: `api/signals.py`
- Modify: `api/apps.py`
- Create: `api/tests/test_signals.py`

**Interfaces:**
- Consumes: `Company` model (Task 2).
- Produces: on every new `User` creation, a `Company` row with `company_name=''`, `role=Company.Role.CLIENT` (via model default), and a unique `api_key` from `secrets.token_urlsafe(32)`. Later tasks (Register/Login views) rely on `user.company` always existing immediately after `User.objects.create_user(...)`.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_signals.py
from django.contrib.auth.models import User
from django.test import TestCase

from api.models import Company


class CompanyAutoCreationSignalTest(TestCase):
    def test_creating_user_auto_creates_company(self):
        user = User.objects.create_user(username='signaltest', password='pw12345678')

        company = Company.objects.get(user=user)
        self.assertEqual(company.role, Company.Role.CLIENT)
        self.assertEqual(company.company_name, '')
        self.assertGreater(len(company.api_key), 20)

    def test_api_key_is_unique_per_company(self):
        user_a = User.objects.create_user(username='signala', password='pw12345678')
        user_b = User.objects.create_user(username='signalb', password='pw12345678')

        self.assertNotEqual(user_a.company.api_key, user_b.company.api_key)

    def test_saving_existing_user_does_not_duplicate_company(self):
        user = User.objects.create_user(username='signalresave', password='pw12345678')
        original_api_key = user.company.api_key

        user.email = 'updated@example.com'
        user.save()
        user.refresh_from_db()

        self.assertEqual(Company.objects.filter(user=user).count(), 1)
        self.assertEqual(user.company.api_key, original_api_key)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python manage.py test api.tests.test_signals -v 2`
Expected: FAIL — `Company.DoesNotExist` (no signal wired yet).

- [ ] **Step 3: Write api/signals.py**

```python
import secrets

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Company


@receiver(post_save, sender=User)
def create_company_profile(sender, instance, created, **kwargs):
    if created:
        Company.objects.create(
            user=instance,
            company_name='',
            api_key=secrets.token_urlsafe(32),
        )
```

- [ ] **Step 4: Wire the signal in api/apps.py**

```python
from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        import api.signals  # noqa: F401
```

Confirm `teamboard/settings.py`'s `INSTALLED_APPS` entry for the app is `'api'` (not `'api.apps.ApiConfig'`) — Django resolves the config class from `api/apps.py` automatically as long as it's the only `AppConfig` subclass in that file, so no settings change is needed. If `manage.py startapp` generated a different class name than `ApiConfig`, rename it to match the code above.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python manage.py test api.tests.test_signals -v 2`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add api/signals.py api/apps.py api/tests/test_signals.py
git commit -m "Auto-create Company profile and API key via post_save signal on User"
```

---

## Task 4: Register and Login Endpoints

**Files:**
- Create: `api/serializers.py`
- Modify: `api/views.py`
- Modify: `api/urls.py`
- Create: `api/tests/test_auth.py`

**Interfaces:**
- Consumes: `Company`, signal-created `user.company` (Tasks 2–3).
- Produces: `RegisterSerializer`, `LoginSerializer` (consumed only within this task); `RegisterView` at `POST /api/auth/register/`, `LoginView` at `POST /api/auth/login/`. Later tasks (KB Query, Usage Summary) issue their own JWTs the same way (`RefreshToken.for_user(user).access_token`) but do not import these views directly.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_auth.py
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase


class RegisterViewTest(APITestCase):
    def test_register_creates_user_and_returns_jwt_and_api_key(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'acmecorp',
            'password': 'securepass123',
            'company_name': 'Acme Corp',
            'email': 'dev@acmecorp.com',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['username'], 'acmecorp')
        self.assertEqual(response.data['company_name'], 'Acme Corp')
        self.assertIn('api_key', response.data)
        self.assertIn('access', response.data)

        user = User.objects.get(username='acmecorp')
        self.assertEqual(user.company.role, user.company.Role.CLIENT)

    def test_register_rejects_duplicate_username(self):
        User.objects.create_user(username='acmecorp', password='securepass123')

        response = self.client.post('/api/auth/register/', {
            'username': 'acmecorp',
            'password': 'anotherpass123',
            'company_name': 'Acme Corp 2',
            'email': 'dev2@acmecorp.com',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_register_ignores_role_in_request_body(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'sneakycorp',
            'password': 'securepass123',
            'company_name': 'Sneaky Corp',
            'email': 'sneaky@example.com',
            'role': 'admin',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='sneakycorp')
        self.assertEqual(user.company.role, user.company.Role.CLIENT)


class LoginViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='acmecorp', password='securepass123')
        self.user.company.company_name = 'Acme Corp'
        self.user.company.save(update_fields=['company_name'])

    def test_login_success_returns_jwt_and_company_info(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'acmecorp',
            'password': 'securepass123',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['company_name'], 'Acme Corp')
        self.assertEqual(response.data['api_key'], self.user.company.api_key)

    def test_login_rejects_bad_password(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'acmecorp',
            'password': 'wrongpassword',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)

    def test_login_rejects_nonexistent_user(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'nosuchcompany',
            'password': 'whatever123',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python manage.py test api.tests.test_auth -v 2`
Expected: FAIL — `404` responses (no URLs wired yet) / import errors.

- [ ] **Step 3: Write api/serializers.py**

```python
from django.contrib.auth.models import User
from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    company_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('A company with this username already exists.')
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
```

- [ ] **Step 4: Write RegisterView and LoginView in api/views.py**

```python
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, RegisterSerializer


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            user = User.objects.create_user(
                username=data['username'],
                password=data['password'],
                email=data['email'],
            )
            company = user.company
            company.company_name = data['company_name']
            company.save(update_fields=['company_name'])

        access = str(RefreshToken.for_user(user).access_token)

        return Response(
            {
                'username': user.username,
                'company_name': company.company_name,
                'api_key': company.api_key,
                'access': access,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = authenticate(
            request,
            username=data['username'],
            password=data['password'],
        )
        if user is None:
            return Response(
                {'detail': 'Invalid username or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access = str(RefreshToken.for_user(user).access_token)
        company = user.company

        return Response(
            {
                'access': access,
                'company_name': company.company_name,
                'api_key': company.api_key,
            },
            status=status.HTTP_200_OK,
        )
```

- [ ] **Step 5: Wire the URLs in api/urls.py**

```python
from django.urls import path

from .views import LoginView, RegisterView

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python manage.py test api.tests.test_auth -v 2`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add api/serializers.py api/views.py api/urls.py api/tests/test_auth.py
git commit -m "Add register and login endpoints with JWT issuance"
```

---

## Task 5: KB Seed Management Command

**Files:**
- Create: `api/management/__init__.py`
- Create: `api/management/commands/__init__.py`
- Create: `api/management/commands/seed_kb.py`
- Create: `api/tests/test_seed_kb.py`

**Interfaces:**
- Consumes: `KBEntry` (Task 2).
- Produces: a `seed_kb` management command (`python manage.py seed_kb`) that Task 6's KB Query tests rely on to populate searchable data.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_seed_kb.py
from django.core.management import call_command
from django.test import TestCase

from api.models import KBEntry


class SeedKbCommandTest(TestCase):
    def test_seed_kb_creates_at_least_ten_entries(self):
        call_command('seed_kb')
        self.assertGreaterEqual(KBEntry.objects.count(), 10)

    def test_seed_kb_is_idempotent(self):
        call_command('seed_kb')
        first_count = KBEntry.objects.count()

        call_command('seed_kb')
        second_count = KBEntry.objects.count()

        self.assertEqual(first_count, second_count)

    def test_seed_kb_produces_overlapping_search_keywords(self):
        call_command('seed_kb')

        matches = KBEntry.objects.filter(question__icontains='select_related').count() + \
            KBEntry.objects.filter(answer__icontains='select_related').count()
        self.assertGreaterEqual(matches, 2)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python manage.py test api.tests.test_seed_kb -v 2`
Expected: FAIL — `CommandError: Unknown command: 'seed_kb'`.

- [ ] **Step 3: Create the management command package**

```bash
mkdir -p api/management/commands
touch api/management/__init__.py
touch api/management/commands/__init__.py
```

- [ ] **Step 4: Write api/management/commands/seed_kb.py**

```python
from django.core.management.base import BaseCommand

from api.models import KBEntry

KB_ENTRIES = [
    {
        'question': 'What is select_related in Django ORM?',
        'answer': 'select_related performs a SQL JOIN and fetches related objects in the same query, reducing the number of database round-trips for foreign key and one-to-one relationships.',
        'category': KBEntry.Category.DATABASE,
    },
    {
        'question': 'How does prefetch_related differ from select_related?',
        'answer': 'prefetch_related issues a separate query per relation and joins the results in Python, which is used for many-to-many and reverse foreign key relationships where select_related cannot perform a single SQL JOIN.',
        'category': KBEntry.Category.DATABASE,
    },
    {
        'question': 'How does transaction.atomic() work in Django?',
        'answer': 'transaction.atomic() wraps a block of database operations so that they either all succeed and commit together, or all fail and roll back together, preventing partial writes.',
        'category': KBEntry.Category.DATABASE,
    },
    {
        'question': 'What is a JWT token?',
        'answer': 'A JWT (JSON Web Token) is a signed, self-contained token used to authenticate requests. It encodes claims about the user and is verified using a secret key without needing a database lookup.',
        'category': KBEntry.Category.API,
    },
    {
        'question': 'How do I configure JWT authentication in Django REST Framework?',
        'answer': 'Install djangorestframework-simplejwt, add JWTAuthentication to DEFAULT_AUTHENTICATION_CLASSES in REST_FRAMEWORK settings, and issue tokens via RefreshToken.for_user() on login or registration.',
        'category': KBEntry.Category.API,
    },
    {
        'question': 'When should I use Q objects in Django?',
        'answer': 'Q objects let you build complex queries with OR conditions or nested AND/OR logic, such as Q(question__icontains=term) | Q(answer__icontains=term), which cannot be expressed with plain keyword filter arguments.',
        'category': KBEntry.Category.API,
    },
    {
        'question': 'What is a Django signal used for?',
        'answer': 'Signals let decoupled code run in response to model events, such as automatically creating a related profile object whenever a new User instance is saved via a post_save receiver.',
        'category': KBEntry.Category.FRAMEWORK,
    },
    {
        'question': 'What is the difference between IsAuthenticated and a custom permission class in DRF?',
        'answer': 'IsAuthenticated only checks that a request has a valid authenticated user, while a custom BasePermission subclass can implement has_permission() to enforce business rules like role-based access.',
        'category': KBEntry.Category.FRAMEWORK,
    },
    {
        'question': 'How do I run PostgreSQL locally for development?',
        'answer': 'PostgreSQL can be run via Docker using a docker-compose.yml file with a single db service, keeping credentials in a .env file instead of hardcoding them in settings.py.',
        'category': KBEntry.Category.CLOUD,
    },
    {
        'question': 'What is the benefit of storing credentials in a .env file?',
        'answer': 'Keeping credentials in a .env file (loaded via python-dotenv) keeps secrets out of source control and lets different environments use different values without code changes.',
        'category': KBEntry.Category.CLOUD,
    },
    {
        'question': 'What is an API key used for?',
        'answer': 'An API key is a server-issued credential that a client sends with every request to prove its identity, since a client cannot be trusted to self-report who it is in the request body.',
        'category': KBEntry.Category.GENERAL,
    },
    {
        'question': 'Why log queries even when they return zero results?',
        'answer': 'Usage-based billing counts queries made, not answers found, so a query returning no results still consumed platform resources and must be logged like any other query.',
        'category': KBEntry.Category.GENERAL,
    },
]


class Command(BaseCommand):
    help = 'Seed the knowledge base with initial KBEntry records.'

    def handle(self, *args, **options):
        created_count = 0
        for entry in KB_ENTRIES:
            _, created = KBEntry.objects.get_or_create(
                question=entry['question'],
                defaults={
                    'answer': entry['answer'],
                    'category': entry['category'],
                },
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded {created_count} new KB entries ({len(KB_ENTRIES)} total defined).'
            )
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python manage.py test api.tests.test_seed_kb -v 2`
Expected: PASS (3 tests).

- [ ] **Step 6: Seed the local dev database and commit**

Run:
```bash
python manage.py seed_kb
```
Expected: `Seeded 12 new KB entries (12 total defined).`

```bash
git add api/management api/tests/test_seed_kb.py
git commit -m "Add seed_kb management command with 12 seed entries"
```

---

## Task 6: KB Query Endpoint

**Files:**
- Modify: `api/serializers.py`
- Modify: `api/views.py`
- Modify: `api/urls.py`
- Create: `api/tests/test_kb_query.py`

**Interfaces:**
- Consumes: `KBEntry`, `QueryLog`, `Company` (Task 2), `seed_kb` command (Task 5) for test fixtures.
- Produces: `KBQueryRequestSerializer`, `KBEntrySerializer` (consumed only within this task); `KBQueryView` at `POST /api/kb/query/`.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_kb_query.py
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import QueryLog


class KBQueryViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='acmecorp', password='securepass123')
        access = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        call_command('seed_kb')

    def test_query_without_token_returns_401(self):
        self.client.credentials()
        response = self.client.post('/api/kb/query/', {'search': 'select_related'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_query_with_matches_returns_results_and_logs(self):
        response = self.client.post('/api/kb/query/', {'search': 'select_related'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['search'], 'select_related')
        self.assertGreaterEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), response.data['count'])
        self.assertIsInstance(response.data['results'][0]['id'], int)

        log = QueryLog.objects.get(company=self.user.company, search_term='select_related')
        self.assertEqual(log.results_count, response.data['count'])

    def test_query_with_no_matches_returns_zero_count_and_still_logs(self):
        response = self.client.post('/api/kb/query/', {'search': 'nonexistent-xyz'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['results'], [])

        log = QueryLog.objects.get(company=self.user.company, search_term='nonexistent-xyz')
        self.assertEqual(log.results_count, 0)

    def test_query_with_blank_search_returns_400(self):
        response = self.client.post('/api/kb/query/', {'search': ''}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_query_with_missing_search_returns_400(self):
        response = self.client.post('/api/kb/query/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_query_uses_requesting_users_company_not_request_body(self):
        other_user = User.objects.create_user(username='othercorp', password='securepass123')

        response = self.client.post('/api/kb/query/', {
            'search': 'JWT',
            'company': other_user.company.id,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(QueryLog.objects.filter(company=self.user.company, search_term='JWT').exists())
        self.assertFalse(QueryLog.objects.filter(company=other_user.company).exists())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python manage.py test api.tests.test_kb_query -v 2`
Expected: FAIL — `404` (no URL wired yet).

- [ ] **Step 3: Add serializers to api/serializers.py**

Append to the existing file:

```python
from .models import KBEntry


class KBQueryRequestSerializer(serializers.Serializer):
    search = serializers.CharField(allow_blank=False, trim_whitespace=True)


class KBEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = KBEntry
        fields = ['id', 'question', 'answer', 'category']
```

- [ ] **Step 4: Add KBQueryView to api/views.py**

Append to the existing file:

```python
from django.db.models import Q

from .models import KBEntry, QueryLog
from .serializers import KBEntrySerializer, KBQueryRequestSerializer


class KBQueryView(APIView):
    def post(self, request):
        serializer = KBQueryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        search_term = serializer.validated_data['search']

        company = request.user.company

        with transaction.atomic():
            matches = list(
                KBEntry.objects.filter(
                    Q(question__icontains=search_term) | Q(answer__icontains=search_term)
                )
            )
            count = len(matches)
            QueryLog.objects.create(
                company=company,
                search_term=search_term,
                results_count=count,
            )

        return Response(
            {
                'search': search_term,
                'count': count,
                'results': KBEntrySerializer(matches, many=True).data,
            },
            status=status.HTTP_200_OK,
        )
```

- [ ] **Step 5: Wire the URL in api/urls.py**

```python
from .views import KBQueryView, LoginView, RegisterView

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('kb/query/', KBQueryView.as_view(), name='kb-query'),
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python manage.py test api.tests.test_kb_query -v 2`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add api/serializers.py api/views.py api/urls.py api/tests/test_kb_query.py
git commit -m "Add KB query endpoint with atomic search-and-log transaction"
```

---

## Task 7: IsAdminUser Permission & Usage Summary Endpoint

**Files:**
- Create: `api/permissions.py`
- Modify: `api/views.py`
- Modify: `api/urls.py`
- Create: `api/tests/test_usage_summary.py`

**Interfaces:**
- Consumes: `Company`, `QueryLog` (Task 2).
- Produces: `IsAdminUser` permission class; `UsageSummaryView` at `GET /api/admin/usage-summary/`.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_usage_summary.py
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import Company, QueryLog


class UsageSummaryViewTest(APITestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(username='clientcorp', password='securepass123')

        self.admin_user = User.objects.create_user(username='admincorp', password='securepass123')
        self.admin_user.company.role = Company.Role.ADMIN
        self.admin_user.company.save(update_fields=['role'])

        QueryLog.objects.create(company=self.client_user.company, search_term='select_related', results_count=2)
        QueryLog.objects.create(company=self.client_user.company, search_term='select_related', results_count=2)
        QueryLog.objects.create(company=self.admin_user.company, search_term='JWT', results_count=1)

    def _auth_as(self, user):
        access = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def test_client_role_receives_403(self):
        self._auth_as(self.client_user)
        response = self.client.get('/api/admin/usage-summary/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_token_receives_401(self):
        response = self.client.get('/api/admin/usage-summary/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_role_receives_usage_summary(self):
        self._auth_as(self.admin_user)
        response = self.client.get('/api/admin/usage-summary/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_queries'], 3)
        self.assertEqual(response.data['active_companies'], 2)
        self.assertEqual(response.data['top_search_terms'][0]['search_term'], 'select_related')
        self.assertEqual(response.data['top_search_terms'][0]['count'], 2)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python manage.py test api.tests.test_usage_summary -v 2`
Expected: FAIL — `404` (no URL wired yet).

- [ ] **Step 3: Write api/permissions.py**

```python
from rest_framework.permissions import BasePermission

from .models import Company


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        company = getattr(request.user, 'company', None)
        return bool(company and company.role == Company.Role.ADMIN)
```

- [ ] **Step 4: Add UsageSummaryView to api/views.py**

Append to the existing file:

```python
from django.db.models import Count

from .permissions import IsAdminUser


class UsageSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_queries = QueryLog.objects.aggregate(total=Count('id'))['total']
        active_companies = QueryLog.objects.values('company').distinct().count()
        top_search_terms = list(
            QueryLog.objects.values('search_term')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        return Response(
            {
                'total_queries': total_queries,
                'active_companies': active_companies,
                'top_search_terms': top_search_terms,
            },
            status=status.HTTP_200_OK,
        )
```

- [ ] **Step 5: Wire the URL in api/urls.py**

```python
from .views import KBQueryView, LoginView, RegisterView, UsageSummaryView

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('kb/query/', KBQueryView.as_view(), name='kb-query'),
    path('admin/usage-summary/', UsageSummaryView.as_view(), name='usage-summary'),
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python manage.py test api.tests.test_usage_summary -v 2`
Expected: PASS (3 tests).

- [ ] **Step 7: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: All tests across `test_models`, `test_signals`, `test_auth`, `test_seed_kb`, `test_kb_query`, `test_usage_summary` PASS.

- [ ] **Step 8: Commit**

```bash
git add api/permissions.py api/views.py api/urls.py api/tests/test_usage_summary.py
git commit -m "Add IsAdminUser permission and usage-summary endpoint"
```

---

## Task 8: Postman Collection

**Files:**
- Create: `postman/TeamBoard.postman_collection.json`

**Interfaces:**
- Consumes: the 4 live endpoints from Tasks 4, 6, 7 (must be run against a locally running server for manual verification in Postman; this task only produces the importable file).

- [ ] **Step 1: Write postman/TeamBoard.postman_collection.json**

```json
{
  "info": {
    "name": "TeamBoard API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    { "key": "base_url", "value": "http://127.0.0.1:8000" },
    { "key": "access_token", "value": "" },
    { "key": "admin_access_token", "value": "" }
  ],
  "item": [
    {
      "name": "Register - success",
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "pm.test('status is 201', () => pm.response.to.have.status(201));",
              "const body = pm.response.json();",
              "pm.collectionVariables.set('access_token', body.access);"
            ]
          }
        }
      ],
      "request": {
        "method": "POST",
        "header": [{ "key": "Content-Type", "value": "application/json" }],
        "url": "{{base_url}}/api/auth/register/",
        "body": {
          "mode": "raw",
          "raw": "{\n  \"username\": \"acmecorp\",\n  \"password\": \"securepass123\",\n  \"company_name\": \"Acme Corp\",\n  \"email\": \"dev@acmecorp.com\"\n}"
        }
      }
    },
    {
      "name": "Register - duplicate username (400)",
      "event": [
        {
          "listen": "test",
          "script": { "exec": ["pm.test('status is 400', () => pm.response.to.have.status(400));"] }
        }
      ],
      "request": {
        "method": "POST",
        "header": [{ "key": "Content-Type", "value": "application/json" }],
        "url": "{{base_url}}/api/auth/register/",
        "body": {
          "mode": "raw",
          "raw": "{\n  \"username\": \"acmecorp\",\n  \"password\": \"anotherpass123\",\n  \"company_name\": \"Acme Corp 2\",\n  \"email\": \"dev2@acmecorp.com\"\n}"
        }
      }
    },
    {
      "name": "Login - success",
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "pm.test('status is 200', () => pm.response.to.have.status(200));",
              "const body = pm.response.json();",
              "pm.collectionVariables.set('access_token', body.access);"
            ]
          }
        }
      ],
      "request": {
        "method": "POST",
        "header": [{ "key": "Content-Type", "value": "application/json" }],
        "url": "{{base_url}}/api/auth/login/",
        "body": {
          "mode": "raw",
          "raw": "{\n  \"username\": \"acmecorp\",\n  \"password\": \"securepass123\"\n}"
        }
      }
    },
    {
      "name": "Login - bad credentials (401)",
      "event": [
        {
          "listen": "test",
          "script": { "exec": ["pm.test('status is 401', () => pm.response.to.have.status(401));"] }
        }
      ],
      "request": {
        "method": "POST",
        "header": [{ "key": "Content-Type", "value": "application/json" }],
        "url": "{{base_url}}/api/auth/login/",
        "body": {
          "mode": "raw",
          "raw": "{\n  \"username\": \"acmecorp\",\n  \"password\": \"wrongpassword\"\n}"
        }
      }
    },
    {
      "name": "KB Query - with results",
      "event": [
        {
          "listen": "test",
          "script": { "exec": ["pm.test('status is 200', () => pm.response.to.have.status(200));", "pm.test('count > 0', () => pm.expect(pm.response.json().count).to.be.above(0));"] }
        }
      ],
      "request": {
        "method": "POST",
        "header": [
          { "key": "Content-Type", "value": "application/json" },
          { "key": "Authorization", "value": "Bearer {{access_token}}" }
        ],
        "url": "{{base_url}}/api/kb/query/",
        "body": { "mode": "raw", "raw": "{\n  \"search\": \"select_related\"\n}" }
      }
    },
    {
      "name": "KB Query - zero results",
      "event": [
        {
          "listen": "test",
          "script": { "exec": ["pm.test('status is 200', () => pm.response.to.have.status(200));", "pm.test('count is 0', () => pm.expect(pm.response.json().count).to.eql(0));"] }
        }
      ],
      "request": {
        "method": "POST",
        "header": [
          { "key": "Content-Type", "value": "application/json" },
          { "key": "Authorization", "value": "Bearer {{access_token}}" }
        ],
        "url": "{{base_url}}/api/kb/query/",
        "body": { "mode": "raw", "raw": "{\n  \"search\": \"nonexistent-xyz-term\"\n}" }
      }
    },
    {
      "name": "KB Query - missing search field (400)",
      "event": [
        {
          "listen": "test",
          "script": { "exec": ["pm.test('status is 400', () => pm.response.to.have.status(400));"] }
        }
      ],
      "request": {
        "method": "POST",
        "header": [
          { "key": "Content-Type", "value": "application/json" },
          { "key": "Authorization", "value": "Bearer {{access_token}}" }
        ],
        "url": "{{base_url}}/api/kb/query/",
        "body": { "mode": "raw", "raw": "{}" }
      }
    },
    {
      "name": "KB Query - no token (401)",
      "event": [
        {
          "listen": "test",
          "script": { "exec": ["pm.test('status is 401', () => pm.response.to.have.status(401));"] }
        }
      ],
      "request": {
        "method": "POST",
        "header": [{ "key": "Content-Type", "value": "application/json" }],
        "url": "{{base_url}}/api/kb/query/",
        "body": { "mode": "raw", "raw": "{\n  \"search\": \"select_related\"\n}" }
      }
    },
    {
      "name": "Usage Summary - as ADMIN (200)",
      "event": [
        {
          "listen": "test",
          "script": { "exec": ["pm.test('status is 200', () => pm.response.to.have.status(200));"] }
        }
      ],
      "request": {
        "method": "GET",
        "header": [{ "key": "Authorization", "value": "Bearer {{admin_access_token}}" }],
        "url": "{{base_url}}/api/admin/usage-summary/"
      }
    },
    {
      "name": "Usage Summary - as CLIENT (403)",
      "event": [
        {
          "listen": "test",
          "script": { "exec": ["pm.test('status is 403', () => pm.response.to.have.status(403));"] }
        }
      ],
      "request": {
        "method": "GET",
        "header": [{ "key": "Authorization", "value": "Bearer {{access_token}}" }],
        "url": "{{base_url}}/api/admin/usage-summary/"
      }
    },
    {
      "name": "Usage Summary - no token (401)",
      "event": [
        {
          "listen": "test",
          "script": { "exec": ["pm.test('status is 401', () => pm.response.to.have.status(401));"] }
        }
      ],
      "request": {
        "method": "GET",
        "header": [],
        "url": "{{base_url}}/api/admin/usage-summary/"
      }
    }
  ]
}
```

Note: `admin_access_token` must be populated manually in Postman (or via an added "Login as admin" request) after promoting a company to `ADMIN` role in PGAdmin, since no endpoint creates an admin company automatically — this matches the brief's Step 8.5 workflow ("change a company's role to 'admin', log in again").

- [ ] **Step 2: Commit**

```bash
git add postman/TeamBoard.postman_collection.json
git commit -m "Add Postman collection covering all 11 required scenarios"
```

---

## Task 9: README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing (documentation only).

- [ ] **Step 1: Write README.md**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Document setup, testing, and Postman usage in README"
```

---

## Self-Review Notes

- **Spec coverage:** Every spec section maps to a task — project setup/Docker/DRF config → Task 1; models/admin → Task 2; signal → Task 3; register/login → Task 4; seeding → Task 5; KB query → Task 6; permissions/usage-summary → Task 7; Postman → Task 8; README → Task 9. No spec requirement is without a task.
- **Placeholder scan:** No TBD/TODO markers; every step shows complete, runnable code or exact commands with expected output.
- **Type/name consistency:** `Company.Role.CLIENT`/`ADMIN`, `KBEntry.Category.*`, `request.user.company`, `RefreshToken.for_user(user).access_token`, and view/serializer names (`RegisterView`, `LoginView`, `KBQueryView`, `UsageSummaryView`, `IsAdminUser`) are used identically across every task that references them.
- **`_state.adding` note:** the Global Constraints section clarifies that Django's `created` flag (used in the signal) is itself derived from `_state.adding`, satisfying the brief's explicit instruction without redundant code.
