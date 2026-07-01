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
