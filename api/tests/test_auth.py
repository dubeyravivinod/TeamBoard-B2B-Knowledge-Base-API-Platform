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
