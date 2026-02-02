from django.contrib import admin
from .models import ChatSession, ChatMessage

class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'user', 'created_at')
    inlines = [ChatMessageInline] 
    search_fields = ('session_id',)

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    # Hiển thị các cột này ra ngoài danh sách
    list_display = ('id', 'role', 'short_content', 'session_link', 'created_at')
    
    # Bộ lọc bên tay phải (Lọc theo vai trò hoặc ngày tháng)
    list_filter = ('role', 'created_at')
    
    # Thanh tìm kiếm (Tìm theo nội dung tin nhắn)
    search_fields = ('content',)

    # Hàm rút gọn nội dung nếu quá dài (cho đẹp giao diện)
    def short_content(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Nội dung'

    # Hàm hiển thị Session ID (chỉ lấy vài số đuôi cho gọn)
    def session_link(self, obj):
        return str(obj.session.session_id)[:8] + "..."
    session_link.short_description = 'Session'