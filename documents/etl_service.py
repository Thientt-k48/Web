# documents/etl_service.py
import json
import time
import traceback
import fitz  # PyMuPDF
import google.generativeai as genai

# ĐÂY CHÍNH LÀ ĐƯỜNG ỐNG TỰ ĐỘNG NỐI VỚI POSTGRESQL QUA SETTINGS.PY
from django.db import transaction, connection 
from django.conf import settings
from .models import Document

# Kết nối NoSQL (Do tự cấu hình)
from utils.db_connection import mongo_db, neo4j_driver

# Cấu hình AI
genai.configure(api_key=settings.GEMINI_API_KEY)
json_model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
embedding_model = 'models/text-embedding-004'

def insert_to_3_databases(grade_track, lesson_name, original_id, file_source, chunk_content, chunk_vector, keywords, questions):
    """ Hàm bọc lỗi 3 lớp đã thiết kế - Cập nhật đúng Table và Collection mới """
    inserted_mongo_chunk_ids = []
    inserted_mongo_question_ids = []
    inserted_neo4j_semantic_ids = []

    try:
        # BẬT KHIÊN BẢO VỆ CỦA DJANGO CHO POSTGRESQL
        with transaction.atomic(): 
            
            # ==========================================
            # 1. POSTGRESQL - BẢNG CHUNK
            # ==========================================
            with connection.cursor() as cursor:
                # Dùng đúng tên bảng chat_content_chunks
                cursor.execute("""
                    INSERT INTO chat_content_chunks (file_source, grade_track, lesson_name, original_id) 
                    VALUES (%s, %s, %s, %s) 
                    RETURNING id, semantic_id;
                """, [file_source, grade_track, lesson_name, original_id])
                
                row = cursor.fetchone()
                chunk_db_id = row[0]
                semantic_id = row[1] 

            # ==========================================
            # 2. MONGODB - COLLECTION CHUNKS
            # ==========================================
            mongo_chunk_doc = {
                "semantic_id": semantic_id, 
                "content": chunk_content,
                "vector": chunk_vector,
                "keywords": keywords, # CÓ TỪ KHÓA ĐỂ TÌM KIẾM THEO NGỮ CẢNH
                "metadata": {
                    "grade_track": grade_track,
                    "lesson_name": lesson_name
                }
            }
            res_chunk = mongo_db.chunks.insert_one(mongo_chunk_doc)
            inserted_mongo_chunk_ids.append(res_chunk.inserted_id)

            # ==========================================
            # 3. NEO4J - VẼ ĐỒ THỊ
            # ==========================================
            with neo4j_driver.session() as session:
                cypher_query = """
                MERGE (l:Lesson {name: $lesson_name})
                MERGE (c:Chunk {semantic_id: $semantic_id})
                MERGE (c)-[:BELONGS_TO]->(l)
                WITH c
                UNWIND $keywords AS kw
                MERGE (k:Keyword {name: toLower(kw)})
                MERGE (k)-[:MENTIONED_IN]->(c)
                """
                session.run(cypher_query, lesson_name=lesson_name, semantic_id=semantic_id, keywords=keywords)
                inserted_neo4j_semantic_ids.append(semantic_id)

            # ==========================================
            # 4. XỬ LÝ QUESTIONS (Cả Postgres và Mongo)
            # ==========================================
            if questions:
                mongo_question_docs = []
                for q_text in questions:
                    # 4.1. Nạp Question vào Postgres để Trigger tự sinh semantic_id
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO chat_questions (chunk_id, question_text) 
                            VALUES (%s, %s) 
                            RETURNING id, semantic_id;
                        """, [chunk_db_id, q_text])
                        q_row = cursor.fetchone()
                        q_semantic_id = q_row[1]

                    # 4.2. Nhúng Vector cho Question
                    q_vector = genai.embed_content(model=embedding_model, content=q_text)['embedding']
                    
                    # 4.3. Nạp Question vào Mongo (KHÔNG CÓ TỪ KHÓA)
                    mongo_question_docs.append({
                        "semantic_id": q_semantic_id,
                        "chunk_semantic_id": semantic_id,
                        "question_text": q_text,
                        "vector": q_vector
                    })
                
                if mongo_question_docs:
                    res_q = mongo_db.questions.insert_many(mongo_question_docs)
                    inserted_mongo_question_ids.extend(res_q.inserted_ids)

        # Xong trót lọt tất cả -> Postgres tự động Commit
        return semantic_id

    except Exception as e:
        # Nếu Postgres lỗi -> Tự động Rollback nhờ transaction.atomic()
        # Dọn rác thủ công cho Mongo và Neo4j
        if inserted_mongo_chunk_ids:
            mongo_db.chunks.delete_many({"_id": {"$in": inserted_mongo_chunk_ids}})
        if inserted_mongo_question_ids:
            mongo_db.questions.delete_many({"_id": {"$in": inserted_mongo_question_ids}})
        if inserted_neo4j_semantic_ids:
            with neo4j_driver.session() as session:
                session.run("MATCH (c:Chunk) WHERE c.semantic_id IN $ids DETACH DELETE c", ids=inserted_neo4j_semantic_ids)
        raise Exception(f"Lỗi nạp DB: {e}")


def run_etl_pipeline(doc_id):
    """ Luồng chạy ngầm xử lý PDF """
    try:
        doc = Document.objects.get(id=doc_id)
        file_path = doc.file.path
        grade_track = str(doc.grade)
        
        print(f"[ETL JOB] Bắt đầu xử lý: {doc.title}")
        pdf_document = fitz.open(file_path)
        
        # DEMO: Đang để max 3 trang để test chống cháy túi API.
        for page_num in range(min(3, len(pdf_document))):
            page = pdf_document.load_page(page_num)
            page_text = page.get_text().strip()
            if not page_text: continue
            
            # 1. Gọi Gemini phân tích văn bản
            prompt = f"""
            Phân tích đoạn văn bản sách giáo khoa sau: '{page_text[:1500]}'
            Trả về định dạng JSON nghiêm ngặt gồm mảng "chunks". Mỗi chunk có:
            - "lesson_name": Tên bài học.
            - "content": Nội dung chi tiết.
            - "keywords": Mảng tối đa 3 từ khóa chuyên ngành.
            - "questions": Mảng tối đa 2 câu hỏi học sinh có thể thắc mắc.
            """
            
            response = json_model.generate_content(prompt)
            ai_data = json.loads(response.text)
            
            # 2. Xử lý và lưu 3 DB
            for chunk_idx, chunk in enumerate(ai_data.get('chunks', [])):
                chunk_vector = genai.embed_content(model=embedding_model, content=chunk['content'])['embedding']
                
                original_id = f"PAGE{page_num+1}_CHUNK{chunk_idx+1}"
                file_source = f"{doc.file.name}#page={page_num+1}"
                
                # Hàm này sẽ gánh toàn bộ trách nhiệm phân phối data an toàn
                insert_to_3_databases(
                    grade_track=grade_track,
                    lesson_name=chunk.get('lesson_name', 'Chung'),
                    original_id=original_id,
                    file_source=file_source,
                    chunk_content=chunk['content'],
                    chunk_vector=chunk_vector,
                    keywords=chunk.get('keywords', []),
                    questions=chunk.get('questions', [])
                )
            
            time.sleep(4) # Giảm xóc Rate Limit của Google API

        # Cập nhật trạng thái khi hoàn tất
        doc.status = 'completed'
        doc.save()
        print(f"[ETL JOB] ✅ THÀNH CÔNG nạp sách: {doc.title}")

    except Exception as e:
        doc.status = 'failed'
        doc.save()
        print("[ETL JOB] ❌ THẤT BẠI TRONG QUÁ TRÌNH XỬ LÝ SÁCH!")
        traceback.print_exc()