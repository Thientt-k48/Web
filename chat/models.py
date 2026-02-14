from django.db import models
from django.contrib.auth.models import User
import uuid
from django.conf import settings

# 1. Bảng lưu phiên chat (Session) - API 14
class ChatSession(models.Model):
    # Dùng UUID để tạo mã session ngẫu nhiên, bảo mật hơn số thứ tự 1,2,3
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User có thể Null (nếu là khách vãng lai)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session {self.session_id}"

# 2. Bảng lưu nội dung tin nhắn - API 16, 17
class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Bot'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    
    # Lưu nguồn trích dẫn (JSON) cho tính năng RAG
    sources = models.JSONField(null=True, blank=True) 
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:20]}..."