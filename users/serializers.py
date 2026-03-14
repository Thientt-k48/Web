from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User

# 1. Serializer để Custom Token (Thêm role vào token)
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['username'] = user.username   
        return token
    def validate(self, attrs):
        data = super().validate(attrs)
        # Lấy thông tin user hiện tại
        data['role'] = self.user.role
        data['username'] = self.user.username
        return data

# 2. Serializer để Đăng ký (Register)
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'role')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data.get('email', ''),
            role=validated_data.get('role', 'member')
        )
        return user