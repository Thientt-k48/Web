from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer, RegisterSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from users.permissions import IsAdmin, IsMember
from rest_framework import generics
from .models import User

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# 1. API XEM: Ai đăng nhập cũng xem được (hoặc chỉ Manager)
class DocumentListView(generics.ListAPIView):
    queryset = ...
    permission_classes = [IsAdmin] # Ai có tài khoản là xem được

# 2. API UPLOAD: Chỉ Manager hoặc Admin mới được up
class DocumentUploadView(generics.CreateAPIView):
    queryset = ...
    permission_classes = [IsAdmin] # <--- Áp dụng ở đây

# 3. API XÓA: Chỉ Admin mới được xóa (Quyền lực tối cao)
class DocumentDeleteView(generics.DestroyAPIView):
    queryset = ...
    permission_classes = [IsAdmin] # <--- Chỉ Admin mới qua cửa này

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,) # Ai cũng được đăng ký
    serializer_class = RegisterSerializer