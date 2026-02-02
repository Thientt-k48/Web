from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from .models import Document
from .serializers import DocumentSerializer

from rest_framework.permissions import AllowAny

# API 1: Lấy danh sách (GET /api/docs)
class DocumentListView(generics.ListAPIView):
    # Chỉ lấy những file chưa bị xóa (Soft Delete)
    queryset = Document.objects.filter(is_deleted=False).order_by('-uploaded_at')
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated] # Cho phép mọi người truy cập

# API 2: Upload sách (POST /api/docs/upload)
class DocumentUploadView(generics.CreateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser] # Quan trọng: Để xử lý upload file


    def create(self, request, *args, **kwargs):
        # Logic tùy chỉnh để trả về đúng format file Excel yêu cầu
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Format trả về theo STT 4: { "id": ..., "path": ... }
        instance = serializer.instance
        return Response({
            "id": instance.id,
            "path": instance.file.url,
            "message": "Upload thành công"
        }, status=status.HTTP_201_CREATED)
    
# API 3: Xóa sách (Soft Delete) - Method: DELETE
class DocumentDeleteView(generics.DestroyAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        # Thay vì xóa thật (instance.delete()), ta chỉ đổi flag
        instance.is_deleted = True
        instance.save()