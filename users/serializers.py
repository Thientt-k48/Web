from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Lấy kết quả mặc định (access/refresh token)
        data = super().validate(attrs)
        
        # LOGIC PHÂN QUYỀN ĐƠN GIẢN:
        # Nếu là superuser -> role là "admin", ngược lại là "user"
        if self.user.is_superuser:
            data['role'] = 'admin'
        else:
            data['role'] = 'user'
            
        # Bạn có thể thêm các thông tin khác nếu muốn
        data['username'] = self.user.username
        data['user_id'] = self.user.id
        
        return data