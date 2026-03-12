import boto3
from django.conf import settings
from pymongo import MongoClient
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from users.permissions import IsAdmin
from .models import Document
from .serializers import DocumentSerializer
from utils.db_connection import get_mongo_db, get_neo4j_session

mongo_client = MongoClient(settings.MONGO_URI)
mongo_db = mongo_client[settings.MONGO_DB_NAME]
metadata_collection = mongo_db['document_metadata']

protocol = "https" if settings.MINIO_STORAGE_USE_HTTPS else "http"
s3_client = boto3.client(
    's3',
    endpoint_url=f"{protocol}://{settings.MINIO_STORAGE_ENDPOINT}",
    aws_access_key_id=settings.MINIO_STORAGE_ACCESS_KEY,
    aws_secret_access_key=settings.MINIO_STORAGE_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4')
)
BUCKET_NAME = settings.MINIO_STORAGE_BUCKET_NAME

# API 1: Lấy danh sách (GET /api/docs)
class DocumentListView(generics.ListAPIView):
    # Chỉ lấy những file chưa bị xóa (Soft Delete)
    queryset = Document.objects.filter(is_deleted=False).order_by('-uploaded_at')
    serializer_class = DocumentSerializer
    permission_classes = [IsAdmin] # Cho phép mọi người truy cập

# API 2: Upload sách (POST /api/docs/upload)
class DocumentUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "Vui lòng đính kèm file PDF."}, status=status.HTTP_400_BAD_REQUEST)

        title = request.data.get('title', file_obj.name)
        grade = request.data.get('grade', '10')
        orientation = request.data.get('orientation', 'ICT')
        
        # 1. TẠO ID THEO QUY TẮC: {Lớp}_{Định Hướng} (VD: "11_CS", "12_ICT")
        doc_id = f"{grade}_{orientation}"
        
        # 2. KIỂM TRA TỒN TẠI (Chặn upload đè)
        if Document.objects.filter(id=doc_id).exists():
            return Response({
                "error": f"Sách cho Lớp {grade} định hướng {orientation} đã tồn tại trong hệ thống. Vui lòng xóa sách cũ trước khi tải lên sách mới."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Đảm bảo Bucket tồn tại trên MinIO
        try:
            s3_client.head_bucket(Bucket=BUCKET_NAME)
        except Exception:
            s3_client.create_bucket(Bucket=BUCKET_NAME)

        # 3. Upload file gốc lên MinIO (Sử dụng doc_id mới làm tên thư mục cho gọn)
        file_path = f"lop-{grade}/{orientation}/{doc_id}/original_{file_obj.name}"
        try:
            s3_client.upload_fileobj(file_obj, BUCKET_NAME, file_path)
        except Exception as e:
            return Response({"error": f"Lỗi lưu trữ MinIO: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 4. Lưu thông tin quản lý vào PostgreSQL
        document = Document.objects.create(
            id=doc_id,
            title=title,
            file_name=file_obj.name,
            grade=grade,
            subject_orientation=orientation,
            storage_path=file_path,
            status='uploaded'
        )

        # 5. Lưu Metadata chi tiết vào MongoDB
        metadata = {
            "document_id": doc_id,
            "title": title,
            "original_file_name": file_obj.name,
            "grade": grade,
            "orientation": orientation,
            "file_size": file_obj.size,
            "content_type": file_obj.content_type,
            "extracted_pages": 0,
            "processed": False
        }
        metadata_collection.insert_one(metadata)

        serializer = DocumentSerializer(document)
        return Response({
            "message": f"Upload tài liệu thành công với ID: {doc_id}",
            "document": serializer.data
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