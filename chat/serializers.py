from rest_framework import serializers
from .models import ChatSession, ChatMessage

class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ['session_id', 'user', 'created_at']

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'sources', 'created_at']

class ChatHistorySerializer(serializers.ModelSerializer):
    msg = serializers.CharField(source='content') 
    class Meta:
        model = ChatMessage
        fields = ['role', 'msg', 'created_at']