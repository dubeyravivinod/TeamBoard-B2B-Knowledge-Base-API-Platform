from rest_framework.permissions import BasePermission

from .models import Company


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        company = getattr(request.user, 'company', None)
        return bool(company and company.role == Company.Role.ADMIN)
