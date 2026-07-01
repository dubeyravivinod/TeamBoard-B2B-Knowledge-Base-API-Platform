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
