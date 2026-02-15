import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase
from django.conf import settings

# 1. Khởi tạo Model Embedding (Chỉ load 1 lần khi chạy server)
print("⏳ Đang tải model Embedding...")
embedding_model = SentenceTransformer('keepitreal/vietnamese-sbert')

# 2. Khởi tạo Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# 3. Kết nối Neo4j
neo4j_driver = GraphDatabase.driver(settings.NEO4J_URI, auth=settings.NEO4J_AUTH)

def search_neo4j(query_text, threshold=0.9):
    """
    Tìm kiếm vector trong Neo4j.
    Trả về: (Nội dung tìm thấy, Score) hoặc (None, 0)
    """
    query_vector = embedding_model.encode(query_text).tolist()
    
    cypher_query = """
    CALL db.index.vector.queryNodes('question_embeddings', 1, $vec)
    YIELD node, score
    
    // Chỉ lấy kết quả nếu score >= ngưỡng (0.9)
    WHERE score >= $threshold
    
    // Tìm ngược lại Chunk gốc để lấy ngữ cảnh đầy đủ hơn
    MATCH (node)<-[:HAS_QUESTION]-(c:Chunk)
    
    RETURN 
        node.question_text AS similar_q,
        node.answer_text AS answer,
        c.content AS context,
        score
    """
    
    with neo4j_driver.session() as session:
        result = session.run(cypher_query, vec=query_vector, threshold=threshold)
        record = result.single()
        
        if record:
            # Gom thông tin lại để đưa cho AI
            context_data = {
                "similar_question": record['similar_q'],
                "db_answer": record['answer'],
                "chunk_content": record['context'],
                "score": record['score']
            }
            return context_data, record['score']
            
    return None, 0.0

def generate_response(user_question):
    """
    Hàm xử lý chính cho Chatbot
    """
    # Bước 1: Tìm kiếm trong Neo4j với ngưỡng 0.9 (90%)
    found_data, score = search_neo4j(user_question, threshold=0.9)
    
    if found_data:
        # --- TRƯỜNG HỢP 1: TÌM THẤY (SCORE >= 0.9) ---
        print(f"✅ Tìm thấy trong DB (Score: {score:.4f})")
        
        # Prompt yêu cầu Gemini diễn đạt lại dựa trên thông tin tìm thấy
        prompt = f"""
        Bạn là một trợ lý ảo giáo dục thân thiện.
        Người dùng hỏi: "{user_question}"
        
        Tôi đã tìm thấy thông tin chính xác trong cơ sở dữ liệu như sau:
        - Câu hỏi gốc trong DB: {found_data['similar_question']}
        - Câu trả lời trong DB: {found_data['db_answer']}
        - Ngữ cảnh sách giáo khoa: {found_data['chunk_content']}
        
        Yêu cầu: Hãy sử dụng thông tin trên để trả lời người dùng một cách tự nhiên, mượt mà, đúng trọng tâm câu hỏi của họ. 
        Không được bịa thêm thông tin sai lệch ngoài ngữ cảnh cung cấp.
        """
        
        response = gemini_model.generate_content(prompt)
        return {
            "response": response.text,
            "source": "database",
            "score": score,
            "context": found_data['similar_question'] # Để debug nếu cần
        }
        
    else:
        # --- TRƯỜNG HỢP 2: KHÔNG TÌM THẤY (SCORE < 0.9) ---
        print(f"⚠️ Không khớp đủ ngưỡng (Score cao nhất < 0.9). Gọi Gemini trả lời tự do.")
        
        prompt = f"""
        Bạn là một trợ lý ảo giáo dục.
        Người dùng hỏi: "{user_question}"
        
        Hiện tại trong sách giáo khoa không có câu trả lời khớp hoàn toàn. 
        Hãy trả lời câu hỏi này dựa trên kiến thức chung của bạn một cách chính xác và hữu ích.
        Nếu câu hỏi không thuộc lĩnh vực tin học/giáo dục, hãy khéo léo từ chối.
        """
        
        response = gemini_model.generate_content(prompt)
        return {
            "response": response.text,
            "source": "gemini_knowledge",
            "score": 0.0
        }