from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    # Hiển thị thêm cột 'role' ở danh sách User
    list_display = ('username', 'email', 'role', 'is_staff')
    
    # Thêm trường 'role' vào form chỉnh sửa chi tiết
    fieldsets = UserAdmin.fieldsets + (
        ('Phân quyền (Role)', {'fields': ('role',)}),
    )

# Đăng ký model User vào trang Admin
admin.site.register(User, CustomUserAdmin)