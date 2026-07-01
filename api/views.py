from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import KBEntry, QueryLog
from .permissions import IsAdminUser
from .serializers import KBEntrySerializer, KBQueryRequestSerializer, LoginSerializer, RegisterSerializer


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
