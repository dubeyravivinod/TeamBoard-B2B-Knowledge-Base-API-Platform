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
