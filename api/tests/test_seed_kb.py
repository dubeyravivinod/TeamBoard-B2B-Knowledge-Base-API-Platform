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
