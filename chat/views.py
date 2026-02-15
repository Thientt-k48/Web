from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from .models import ChatSession, ChatMessage
from .serializers import ChatSessionSerializer, ChatHistorySerializer
from .rag_service import generate_response

# API 14: Tạo phiên chat
class CreateChatSessionView(APIView):
    def post(self, request):
        # Lấy user_id từ dữ liệu gửi lên (nếu có)
        user_id = request.data.get('user_id')
        user_obj = None

        if user_id:
            try:
                user_obj = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                pass # Nếu không tìm thấy user thì coi như khách
        
        # Tạo session mới
        session = ChatSession.objects.create(user=user_obj)
        
        # Trả về kết quả
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# API 15: Gửi câu hỏi & Nhận câu trả lời (RAG)
class ChatPredictView(APIView):
    def post(self, request):
        """
        Input: { "session_id": "...", "msg": "Câu hỏi của user" }
        Output: { "ans": "...", "src": [...] }
        """
        data = request.data
        session_id = data.get('session_id')
        msg = data.get('msg')

        # 1. Kiểm tra đầu vào
        if not session_id or not msg:
            return Response({"error": "Thiếu session_id hoặc msg"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. (Tùy chọn) Kiểm tra session có tồn tại không
        try:
            session = ChatSession.objects.get(session_id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session không tồn tại"}, status=status.HTTP_404_NOT_FOUND)

        # 3. GỌI RAG ENGINE (Phần này sau này sẽ kết nối Neo4j/Python)
        # Tạm thời giả lập câu trả lời:
        ai_response = f"Tôi đã nhận được câu hỏi: '{msg}'. Đây là câu trả lời giả lập từ Server."
        sources = [
            {"id": 1, "name": "Tin 10.pdf", "page": 5},
            {"id": 2, "name": "Giao_an.pdf", "page": 12}
        ]

        # 4. Trả kết quả về cho Client
        # Lưu ý: Theo CSV của bạn, việc LƯU LOG vào DB là nhiệm vụ của API 16.
        # Nhưng để tiện test, mình khuyên nên lưu luôn ở đây nếu muốn.
        # Tạm thời làm đúng CSV: Chỉ trả lời, không lưu DB.
        
        return Response({
            "ans": ai_response,
            "src": sources
        }, status=status.HTTP_200_OK)

    # API 16: Lưu lịch sử hội thoại
class SaveChatLogView(APIView):
    def post(self, request):
        """
        Input: { 
            "session_id": "...", 
            "msg": "Câu hỏi...", 
            "ans": "Câu trả lời...",
            "src": [...] (Optional)
        }
        Output: { "status": "saved" }
        """
        data = request.data
        session_id = data.get('session_id')
        msg = data.get('msg')
        ans = data.get('ans')
        src = data.get('src', []) # Mặc định là list rỗng nếu không có

        if not session_id or not msg or not ans:
            return Response({"error": "Thiếu thông tin (session_id, msg, ans)"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Tìm phiên chat
            session = ChatSession.objects.get(session_id=session_id)
            
            # 2. Lưu câu hỏi của User
            ChatMessage.objects.create(
                session=session,
                role='user',
                content=msg
            )

            # 3. Lưu câu trả lời của Bot (kèm nguồn)
            ChatMessage.objects.create(
                session=session,
                role='assistant',
                content=ans,
                sources=src 
            )

            return Response({"status": "saved"}, status=status.HTTP_201_CREATED)

        except ChatSession.DoesNotExist:
            return Response({"error": "Session không tồn tại"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 

    # API 17: Xem lịch sử chat
class GetChatHistoryView(APIView):
    def get(self, request):
        """
        Input: URL ?session_id=...
        Output: [{ "role": "user", "msg": "..." }, ...]
        """
        # 1. Lấy session_id từ URL (Query Param)
        session_id = request.query_params.get('session_id')

        if not session_id:
            return Response({"error": "Thiếu tham số session_id"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Lấy danh sách tin nhắn của session đó
        # order_by('created_at'): Sắp xếp từ cũ đến mới
        messages = ChatMessage.objects.filter(session_id=session_id).order_by('created_at')

        # 3. Kiểm tra xem có tin nhắn nào không (Optional)
        if not messages.exists():
             # Có thể trả về mảng rỗng [] hoặc báo lỗi tùy logic bạn muốn
             return Response([], status=status.HTTP_200_OK)

        # 4. Serialize dữ liệu và trả về
        serializer = ChatHistorySerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)   

class ChatAPIView(APIView):
    def post(self, request):
        user_message = request.data.get('message')
        
        if not user_message:
            return Response(
                {"error": "Vui lòng nhập câu hỏi."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Gọi hàm xử lý logic từ service
            result = generate_response(user_message)
            
            return Response({
                "data": result['response'],
                "meta": {
                    "source": result['source'],
                    "score": result.get('score', 0)
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Lỗi Chat API: {e}")
            return Response(
                {"error": "Đã có lỗi xảy ra khi xử lý câu hỏi."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )