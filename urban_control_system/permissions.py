from rest_framework.permissions import BasePermission

class IsConstructionControl(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'construction_control')

class IsForeman(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'foreman')

class IsInspector(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'inspector')