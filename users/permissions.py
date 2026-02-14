# users/permissions.py

from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """
    Giấy phép chỉ dành cho Admin (Role = 'admin' hoặc Superuser)
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.role == 'admin' or request.user.is_superuser))

class IsMember(BasePermission):
    """
    Giấy phép dành cho Thành viên bình thường (Role = 'member')
    Thực ra chỉ cần IsAuthenticated là đủ, nhưng tách ra cho rõ nghĩa.
    """
    def has_permission(self, request, view):
        # Chỉ cần đăng nhập là chat được (bao gồm cả Admin cũng chat được nếu muốn)
        return bool(request.user and request.user.is_authenticated)