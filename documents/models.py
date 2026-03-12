from django.db import models

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