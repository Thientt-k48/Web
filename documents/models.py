from django.db import models
import uuid

class Document(models.Model):
    id = models.CharField(max_length=50, primary_key=True, editable=False) 
    
    title = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    grade = models.CharField(max_length=50, blank=True, null=True) 
    subject_orientation = models.CharField(max_length=50, blank=True, null=True) 
    storage_path = models.CharField(max_length=500) 
    status = models.CharField(max_length=50, default='uploaded') 
    uploaded_at = models.DateTimeField(auto_now_add=True)

    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.id 

class DataIngestionJob(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Đang chờ xử lý'),
        ('PROCESSING', 'Đang xử lý'),
        ('COMPLETED', 'Hoàn thành'),
        ('FAILED', 'Thất bại'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_name = models.CharField(max_length=255)
    grade_track = models.CharField(max_length=10, help_text="Khối lớp (VD: 10, 11, 12)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    total_chunks = models.IntegerField(default=0)
    processed_chunks = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.file_name} - {self.status} ({self.processed_chunks}/{self.total_chunks})"