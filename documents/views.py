from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from users.permissions import IsAdmin
from .models import Document
from .serializers import DocumentSerializer
from utils.db_connection import get_mongo_db, get_neo4j_session


# API 1: Lấy danh sách (GET /api/docs)
class DocumentListView(generics.ListAPIView):
    # Chỉ lấy những file chưa bị xóa (Soft Delete)
    queryset = Document.objects.filter(is_deleted=False).order_by('-uploaded_at')
    serializer_class = DocumentSerializer
    permission_classes = [IsAdmin] # Cho phép mọi người truy cập

# API 2: Upload sách (POST /api/docs/upload)
class DocumentUploadView(generics.CreateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAdmin]
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
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        instance = serializer.instance

        # --- ĐOẠN CODE TEST KẾT NỐI (Thêm vào đây) ---
        try:
            # 1. Test Mongo
            mongo_db = get_mongo_db()
            mongo_db.logs.insert_one({
                "action": "upload",
                "file_id": instance.id,
                "status": "success"
            })
            print("✅ Kết nối MongoDB: THÀNH CÔNG")

            # 2. Test Neo4j
            with get_neo4j_session() as session:
                session.run("MERGE (u:User {name: 'TestConnection'})")
            print("✅ Kết nối Neo4j: THÀNH CÔNG")

        except Exception as e:
            print(f"❌ LỖI KẾT NỐI DB: {str(e)}")
        # ---------------------------------------------

        return Response({
            "id": instance.id,
            "path": instance.file.url,
            "message": "Upload thành công (Đã check kết nối DB)"
        }, status=status.HTTP_201_CREATED)
    
# API 3: Xóa sách (Soft Delete) - Method: DELETE
class DocumentDeleteView(generics.DestroyAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAdmin]

    def perform_destroy(self, instance):
        # Thay vì xóa thật (instance.delete()), ta chỉ đổi flag
        instance.is_deleted = True
        instance.save()