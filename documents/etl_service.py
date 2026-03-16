import json
import time
import traceback
import fitz
import numpy as np
import google.generativeai as genai
from django.db import transaction, connection
from django.conf import settings
from .models import Document
from utils.db_connection import mongo_db, neo4j_driver
from botocore.client import Config
import boto3
import os
import tempfile
import re

s3_client = boto3.client(
    's3',
    endpoint_url=f"{'https' if settings.MINIO_STORAGE_USE_HTTPS else 'http'}://{settings.MINIO_STORAGE_ENDPOINT}",
    aws_access_key_id=settings.MINIO_STORAGE_ACCESS_KEY,
    aws_secret_access_key=settings.MINIO_STORAGE_SECRET_KEY,
    config=Config(signature_version='s3v4'),
    region_name='us-east-1' # Hoặc region bạn cấu hình
)

genai.configure(api_key=settings.GOOGLE_API_KEY)
json_model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
embedding_model = 'models/gemini-embedding-001'



def insert_to_3_databases(grade_track, topic_code, lesson_name, original_id, file_source, chunk_content, chunk_vector, keywords, questions):
    inserted_mongo_chunk_ids = []
    inserted_mongo_question_ids = []
    
    # Rút trích ID Bài học cho Neo4j (VD: "Bài 1. ABC" -> "bai1")
    match_lesson = re.search(r'bài\s*(\d+)', lesson_name, re.IGNORECASE)
    baihoc_id = f"bai{match_lesson.group(1)}" if match_lesson else "bai_unknown"
    
    try:
        with transaction.atomic(): 
            # =========================================================
            # 1. POSTGRESQL (Để Trigger tự động sinh ID)
            # =========================================================
            with connection.cursor() as cursor:
                # Ép Postgres trả về semantic_id vừa được Trigger nặn ra
                cursor.execute("""
                    INSERT INTO content_chunks (file_source, grade_track, topic_code, lesson_name, original_id) 
                    VALUES (%s, %s, %s, %s, %s) RETURNING id, semantic_id;
                """, [file_source, grade_track, topic_code, lesson_name, original_id])
                
                result = cursor.fetchone()
                chunk_db_id = result[0]
                semantic_id = result[1] # <--- ĐÂY LÀ ID 10_chung_chude1_bai1_chunk1 CỦA BẠN!

            # =========================================================
            # 2. MONGODB (Dùng ID của Postgres)
            # =========================================================
            mongo_chunk_doc = {
                "semantic_id": semantic_id, 
                "content": chunk_content,
                "keywords": keywords,
                "metadata": {
                    "grade_track": grade_track,
                    "topic_code": topic_code,
                    "lesson_name": lesson_name
                }
            }
            res_chunk = mongo_db.chunks.insert_one(mongo_chunk_doc)
            inserted_mongo_chunk_ids.append(res_chunk.inserted_id)

            # =========================================================
            # 3. NEO4J (Dùng ID của Postgres)
            # =========================================================
            with neo4j_driver.session() as session:
                cypher_query = """
                MERGE (th:Thing {id: "TH", name: "Tin học"})
                
                MERGE (l:Lop {id: $grade_track, name: "Lớp " + $grade_track})
                MERGE (th)-[:HAS_GRADE]->(l)
                
                MERGE (cd:ChuDe {id: $topic_code})
                MERGE (l)-[:HAS_TOPIC]->(cd)
                
                MERGE (b:BaiHoc {id: $baihoc_id, name: $lesson_name})
                MERGE (cd)-[:HAS_LESSON]->(b)
                
                MERGE (c:Chunk {semantic_id: $semantic_id})
                SET c.vector = $chunk_vector
                MERGE (b)-[:HAS_CHUNK]->(c)
                """
                session.run(cypher_query, 
                            grade_track=grade_track, topic_code=topic_code, 
                            baihoc_id=baihoc_id, lesson_name=lesson_name,
                            semantic_id=semantic_id, chunk_vector=chunk_vector)

            # =========================================================
            # 4. XỬ LÝ CÂU HỎI (Để Trigger tự lo ID)
            # =========================================================
            if questions and isinstance(questions, list):
                for q_data in questions:
                    q_text, q_answer = "", ""
                    
                    if isinstance(q_data, dict):
                        q_text = q_data.get('question', '')
                        q_answer = q_data.get('answer', '')
                    elif isinstance(q_data, list) and len(q_data) >= 2:
                        q_text = str(q_data[0])
                        q_answer = str(q_data[1])
                    else:
                        continue 
                        
                    if not q_text: continue
                    
                    # Cắm vào Postgres, bắt lấy ID sinh ra từ Trigger thứ 2
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO questions (chunk_id, question_text) 
                            VALUES (%s, %s) RETURNING id, semantic_id;
                        """, [chunk_db_id, q_text])
                        
                        res_q = cursor.fetchone()
                        q_semantic_id = res_q[1] # <--- ID CÂU HỎI (VD: 10_chung_chude1_bai1_chunk1_Q1)

                    q_vector = genai.embed_content(model=embedding_model, content=q_text)['embedding']
                    
                    res_mongo_q = mongo_db.questions.insert_one({
                        "semantic_id": q_semantic_id,
                        "chunk_semantic_id": semantic_id,
                        "question_text": q_text,
                        "answer": q_answer
                    })
                    inserted_mongo_question_ids.append(res_mongo_q.inserted_id)
                    
                    with neo4j_driver.session() as session:
                        session.run("""
                        MATCH (c:Chunk {semantic_id: $chunk_semantic_id})
                        MERGE (q:Question {semantic_id: $q_semantic_id})
                        SET q.vector = $q_vector
                        MERGE (c)-[:HAS_QUESTION]->(q)
                        """, chunk_semantic_id=semantic_id, q_semantic_id=q_semantic_id, q_vector=q_vector)

        return semantic_id

    except Exception as e:
        if inserted_mongo_chunk_ids:
            mongo_db.chunks.delete_many({"_id": {"$in": inserted_mongo_chunk_ids}})
        if inserted_mongo_question_ids:
            mongo_db.questions.delete_many({"_id": {"$in": inserted_mongo_question_ids}})
        raise Exception(f"Lỗi nạp DB: {e}")


def update_hierarchical_vectors():
    """ 
    Tính toán Vector Trung Bình từ dưới lên (Bottom-up)
    Dựa trên cấu trúc HAS_CHUNK, HAS_LESSON, HAS_TOPIC, HAS_GRADE
    """
    print("[VECTOR MATH] Đang tính toán Vector phân cấp cho mạng lưới Neo4j...")
    
    with neo4j_driver.session() as session:
        # 1. Bài Học (Trung bình của các Chunk con)
        result_baihoc = session.run("MATCH (b:BaiHoc)-[:HAS_CHUNK]->(c:Chunk) RETURN b.id AS id, c.vector AS vec")
        baihoc_dict = {}
        for record in result_baihoc:
            b_id = record["id"]
            if b_id not in baihoc_dict: baihoc_dict[b_id] = []
            if record["vec"]: baihoc_dict[b_id].append(record["vec"])
            
        for b_id, vectors in baihoc_dict.items():
            if vectors:
                avg_vec = np.mean(vectors, axis=0).tolist()
                session.run("MATCH (b:BaiHoc {id: $id}) SET b.vector = $vec", id=b_id, vec=avg_vec)

        # 2. Chủ Đề (Trung bình của các Bài Học con)
        result_chude = session.run("MATCH (cd:ChuDe)-[:HAS_LESSON]->(b:BaiHoc) RETURN cd.id AS id, b.vector AS vec")
        chude_dict = {}
        for record in result_chude:
            cd_id = record["id"]
            if cd_id not in chude_dict: chude_dict[cd_id] = []
            if record["vec"]: chude_dict[cd_id].append(record["vec"])
            
        for cd_id, vectors in chude_dict.items():
            if vectors:
                avg_vec = np.mean(vectors, axis=0).tolist()
                session.run("MATCH (cd:ChuDe {id: $id}) SET cd.vector = $vec", id=cd_id, vec=avg_vec)

        # 3. Lớp (Trung bình của các Chủ Đề con)
        result_lop = session.run("MATCH (l:Lop)-[:HAS_TOPIC]->(cd:ChuDe) RETURN l.id AS id, cd.vector AS vec")
        lop_dict = {}
        for record in result_lop:
            l_id = record["id"]
            if l_id not in lop_dict: lop_dict[l_id] = []
            if record["vec"]: lop_dict[l_id].append(record["vec"])
            
        for l_id, vectors in lop_dict.items():
            if vectors:
                avg_vec = np.mean(vectors, axis=0).tolist()
                session.run("MATCH (l:Lop {id: $id}) SET l.vector = $vec", id=l_id, vec=avg_vec)

        # 4. Thing (Trung bình của các Lớp)
        result_thing = session.run("MATCH (th:Thing)-[:HAS_GRADE]->(l:Lop) RETURN th.id AS id, l.vector AS vec")
        thing_dict = {}
        for record in result_thing:
            th_id = record["id"]
            if th_id not in thing_dict: thing_dict[th_id] = []
            if record["vec"]: thing_dict[th_id].append(record["vec"])
            
        for th_id, vectors in thing_dict.items():
            if vectors:
                avg_vec = np.mean(vectors, axis=0).tolist()
                session.run("MATCH (th:Thing {id: $id}) SET th.vector = $vec", id=th_id, vec=avg_vec)

        print("[VECTOR MATH] Hoàn tất cập nhật cấu trúc Hierarchical Vectors!")

def run_etl_pipeline(doc_id):
    """ 
    Luồng ETL Two-Pass: Đọc nguyên sách lấy cấu trúc -> Xử lý từng bài học -> Nạp DB -> Tính Vector
    """
    
    uploaded_pdf = None
    local_temp_path = None
    try:
        doc = Document.objects.get(id=doc_id)
        minio_file_path = doc.storage_path # Đây là Key trên MinIO
        grade_track = str(doc.grade)
        
        print(f"[ETL JOB] Bắt đầu xử lý sách: {doc.title} (Lớp {grade_track})")
        doc.status = 'processing'
        doc.save()

        # =================================================================
        # BƯỚC CHUẨN BỊ: TẢI FILE TỪ MINIO VỀ SERVER CỤC BỘ (TẠM THỜI)
        # =================================================================
        print(f"[ETL JOB] Đang tải file từ MinIO về ổ cứng tạm...")
        # Tạo một file tạm thời trên ổ cứng của server
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        local_temp_path = temp_pdf.name
        temp_pdf.close() # Đóng lại để nhường quyền ghi cho boto3
        
        # Tải file từ MinIO xuống file tạm vừa tạo
        s3_client.download_file(settings.MINIO_STORAGE_BUCKET_NAME, minio_file_path, local_temp_path)

        # =================================================================
        # PASS 1: UPLOAD LÊN GOOGLE CLOUD
        # =================================================================
        print("[ETL JOB] Đang tải toàn bộ sách lên Google Cloud...")
        # ĐƯA local_temp_path VÀO ĐÂY THAY VÌ file_path CŨ
        uploaded_pdf = genai.upload_file(path=local_temp_path, display_name=doc.title) 
        
        while uploaded_pdf.state.name == "PROCESSING":
            doc.refresh_from_db()
            if doc.status == 'cancelled':
                print(f"[ETL JOB] 🛑 ĐÃ HỦY: Tiến trình bị dừng bởi người dùng!")
                return # Thoát ngay lập tức, code sẽ nhảy thẳng xuống block 'finally' để dọn rác
            print(".", end="")
            time.sleep(2)
            uploaded_pdf = genai.get_file(uploaded_pdf.name)
            
        print("\n[ETL JOB] Đang nhờ AI phân tích cấu trúc vĩ mô của sách...")
        
        # ... (ĐOẠN PROMPT_PASS_1 VÀ LẤY MỤC LỤC GIỮ NGUYÊN NHƯ CŨ) ...
        prompt_pass_1 = """
        Bạn là chuyên gia giáo dục. Hãy đọc toàn bộ sách giáo khoa này và lập cấu trúc Mục lục.
        Trả về JSON với mảng "topics" (Chủ đề). Mỗi chủ đề gồm:
        - "topic_code": Mã chủ đề viết liền không dấu (VD: "chude1", "chude_mangmaytinh")
        - "lessons": Mảng các bài học thuộc chủ đề này. Mỗi bài học gồm:
            - "lesson_name": Tên bài học
            - "start_page": Trang bắt đầu của bài học (dựa vào số trang vật lý của file PDF, đếm từ 1)
            - "end_page": Trang kết thúc của bài học
        Tuyệt đối không trích xuất nội dung chi tiết để tránh tràn bộ nhớ.
        """
        response_p1 = json_model.generate_content([uploaded_pdf, prompt_pass_1])
        book_structure = json.loads(response_p1.text)
        print(f"[ETL JOB] Tìm thấy {len(book_structure.get('topics', []))} Chủ đề. Bắt đầu xử lý chi tiết...")

        # =================================================================
        # PASS 2: XỬ LÝ SÂU TỪNG BÀI HỌC DỰA TRÊN TỌA ĐỘ TRANG
        # =================================================================
        pdf_document = fitz.open(local_temp_path) # Mở file PDF từ ổ cứng để xử lý từng bài học theo tọa độ trang
        
        for topic in book_structure.get('topics', []):
            topic_code = topic.get('topic_code', 'chude_chung')
            
            for lesson in topic.get('lessons', []):
                doc.refresh_from_db()
                if doc.status == 'cancelled':
                    print(f"[ETL JOB] 🛑 ĐÃ HỦY: Tiến trình dừng trước khi xử lý {lesson['lesson_name']}!")
                    return # Thoát ngay lập tức
                

                lesson_name = lesson['lesson_name']
                # Xử lý Index của PyMuPDF (đếm từ 0)
                start_p = max(0, lesson['start_page'] - 1) 
                end_p = min(len(pdf_document) - 1, lesson['end_page'] - 1)
                
                print(f"[ETL JOB] Đang xử lý: [{topic_code}] - {lesson_name} (Trang {start_p+1} đến {end_p+1})")
                
                # Cắt một đoạn PDF nhỏ chỉ chứa bài học hiện tại
                temp_pdf = fitz.open()
                temp_pdf.insert_pdf(pdf_document, from_page=start_p, to_page=end_p)
                temp_pdf_bytes = temp_pdf.write()
                temp_pdf.close()
                
                prompt_pass_2 = f"""
                Bạn là một chuyên gia giáo dục và thiết kế đề thi môn Tin học. 
                Dưới đây là nội dung của Bài học: "{lesson_name}". 
                Hãy đọc, phân tích và chia nhỏ bài học này thành các đoạn kiến thức (chunks) có ý nghĩa trọn vẹn. 
                
                YÊU CẦU KHẮT KHE ĐỐI VỚI MỖI ĐOẠN (CHUNK):
                1. "content": Trích xuất nội dung văn bản gốc, độ dài lý tưởng khoảng 200 - 500 từ.
                2. "keywords": Trích xuất CHÍNH XÁC 5 từ khóa cốt lõi và quan trọng nhất đại diện cho đoạn văn đó.
                3. "questions": Sinh ra ÍT NHẤT 10 cặp Câu hỏi và Trả lời (Q&A) bám sát tuyệt đối vào nội dung đoạn này. 
                   (Gợi ý: Nếu đoạn văn ngắn, hãy khai thác đa dạng các góc độ như: hỏi về định nghĩa, ví dụ, phân tích đặc điểm, ưu/nhược điểm, hoặc câu hỏi tình huống để ĐẢM BẢO LUÔN ĐỦ HOẶC HƠN 10 CÂU HỎI).
                   
                TRẢ VỀ DUY NHẤT ĐỊNH DẠNG JSON SAU (Tuyệt đối không dùng markdown ```json):
                {{
                    "chunks": [
                        {{
                            "content": "Nội dung đoạn văn...",
                            "keywords": ["từ khóa 1", "từ khóa 2", "từ khóa 3", "từ khóa 4", "từ khóa 5"],
                            "questions": [
                                {{"question": "Nội dung câu hỏi 1?", "answer": "Nội dung đáp án 1"}},
                                {{"question": "Nội dung câu hỏi 2?", "answer": "Nội dung đáp án 2"}},
                                {{"question": "Nội dung câu hỏi 3?", "answer": "Nội dung đáp án 3"}},
                                {{"question": "Nội dung câu hỏi 4?", "answer": "Nội dung đáp án 4"}},
                                {{"question": "Nội dung câu hỏi 5?", "answer": "Nội dung đáp án 5"}},
                                {{"question": "Nội dung câu hỏi 6?", "answer": "Nội dung đáp án 6"}},
                                {{"question": "Nội dung câu hỏi 7?", "answer": "Nội dung đáp án 7"}},
                                {{"question": "Nội dung câu hỏi 8?", "answer": "Nội dung đáp án 8"}},
                                {{"question": "Nội dung câu hỏi 9?", "answer": "Nội dung đáp án 9"}},
                                {{"question": "Nội dung câu hỏi 10?", "answer": "Nội dung đáp án 10"}}
                            ]
                        }}
                    ]
                }}
                """
                
                try:
                    # Gửi riêng file byte bài học này cho Gemini xử lý
                    response_p2 = json_model.generate_content([
                        {"mime_type": "application/pdf", "data": temp_pdf_bytes}, 
                        prompt_pass_2
                    ])
                    lesson_data = json.loads(response_p2.text)
                    
                    # Nạp vào 3 DB
                    for chunk_idx, chunk in enumerate(lesson_data.get('chunks', [])):
                        chunk_vector = genai.embed_content(model=embedding_model, content=chunk['content'])['embedding']
                        original_id = f"PAGE{start_p+1}_TO_{end_p+1}_CHUNK{chunk_idx+1}"
                        file_source = f"{doc.file_name}#page={start_p+1}"
                        
                        insert_to_3_databases(
                            grade_track=grade_track,
                            topic_code=topic_code,
                            lesson_name=lesson_name,
                            original_id=original_id,
                            file_source=file_source,
                            chunk_content=chunk['content'],
                            chunk_vector=chunk_vector,
                            keywords=chunk.get('keywords', []),
                            questions=chunk.get('questions', []) # Đã có cả question và answer
                        )
                except Exception as inner_e:
                    print(f"⚠️ Cảnh báo: Lỗi khi xử lý bài {lesson_name}: {inner_e}. Hệ thống sẽ bỏ qua bài này và chạy tiếp.")
                
                # Giảm xóc Rate Limit (Google API)
                time.sleep(5) 

        # =================================================================
        # PASS 3: TÍNH VECTOR PHÂN CẤP & HOÀN TẤT
        # =================================================================
        update_hierarchical_vectors()

        doc.status = 'completed'
        doc.save()
        print(f"[ETL JOB] ✅ THÀNH CÔNG! Đã nạp dữ liệu xong cho: {doc.title}")

    except Exception as e:
        doc.status = 'failed'
        doc.save()
        print(f"[ETL JOB] ❌ THẤT BẠI: Quá trình ETL gặp lỗi!")
        traceback.print_exc()

    finally:
        # LUÔN LUÔN DỌN RÁC CLOUD DÙ CODE CHẠY THÀNH CÔNG HAY BÁO LỖI
        if uploaded_pdf:
            try:
                genai.delete_file(uploaded_pdf.name)
                print("[ETL JOB] Đã dọn dẹp file PDF tạm trên Google Cloud.")
            except Exception as delete_err:
                print(f"[ETL JOB] Không thể xóa file trên Cloud: {delete_err}")
        # 2. DỌN RÁC FILE TẠM TRÊN Ổ CỨNG MÁY CHỦ LOCAL
        if local_temp_path and os.path.exists(local_temp_path):
            try:
                os.remove(local_temp_path)
                print("[ETL JOB] Đã dọn dẹp ổ cứng máy chủ (xóa file temp).")
            except Exception as e:
                print(f"[ETL JOB] Không thể xóa file tạm trên ổ cứng: {e}")