# users/permissions.py

from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """
    Chỉ cho phép Admin truy cập
    """
    def has_permission(self, request, view):
        # Kiểm tra: Đã đăng nhập VÀ có role là 'admin'
        return bool(request.user and request.user.is_authenticated and request.user.role == 'admin')

class IsManagerOrAdmin(BasePermission):
    """
    Cho phép Admin hoặc Manager truy cập
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ['admin', 'manager'])