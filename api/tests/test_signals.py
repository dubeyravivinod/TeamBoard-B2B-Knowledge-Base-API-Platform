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
