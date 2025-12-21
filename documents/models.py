from django.db import models

class Document(models.Model):
    title = models.CharField(max_length=255, verbose_name="Tên tài liệu")
    # File sẽ được lưu vào thư mục 'media/pdfs/'
    file = models.FileField(upload_to='pdfs/', verbose_name="File đính kèm")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày upload")
    
    # Soft Delete: Thay vì xóa thật, ta chỉ ẩn nó đi (theo yêu cầu STT 5)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.title