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
