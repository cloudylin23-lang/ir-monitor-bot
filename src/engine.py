import os
import requests
import pdfplumber
import weaviate
import json
import re
import asyncio
from datetime import datetime
from weaviate.auth import AuthApiKey 
from io import BytesIO
from dotenv import load_dotenv
from google.genai import Client
from sentence_transformers import SentenceTransformer
from weaviate.classes.query import MetadataQuery, Filter

load_dotenv()

class AIEngine:
    def __init__(self):
        # ===== 1. GEMINI CONFIG =====
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = Client(api_key=self.api_key) if self.api_key else None
        self.model_id = "gemini-2.5-flash-lite" # Đảm bảo model id đúng
        
        # ===== 2. EMBEDDING MODEL =====
        print("📦 Loading local embedding model...")
        self.embed_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Embedding model loaded!")

        # ===== 3. WEAVIATE CLOUD CONFIG =====
        self.vector_db = None
        try:
            url = os.getenv("WEAVIATE_URL", "").strip()
            key = os.getenv("WEAVIATE_API_KEY", "").strip()
            if url and key:
                self.vector_db = weaviate.connect_to_weaviate_cloud(
                    cluster_url=url, auth_credentials=AuthApiKey(key), skip_init_checks=True 
                )
                if self.vector_db.is_live():
                    self._setup_weaviate_schema()
                    print("✅ Weaviate Cloud is ready!")
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Weaviate: {e}")

    def _setup_weaviate_schema(self):
        if not self.vector_db.collections.exists("FinancialNews"):
            self.vector_db.collections.create(name="FinancialNews")

    async def _call_gemini_with_retry(self, prompt, retries=5):
        for i in range(retries):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, 
                    lambda: self.client.models.generate_content(model=self.model_id, contents=prompt)
                )
                return response
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "ResourceExhausted" in err_msg:
                    wait_time = (2 ** i) + 2 
                    print(f"⚠️ Gemini bị nghẽn (429). Đang đợi {wait_time}s để thử lại lần {i+1}...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ Lỗi AI: {err_msg}")
                    break
        return None

    def _safe_json_parse(self, text):
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return None
        except:
            return None

    def get_embedding(self, text):
        if not text or len(str(text).strip()) < 10: return None
        return self.embed_model.encode(text[:1000])

    async def process_chat(self, user_input):
        if not self.client: 
            return {"type": "error", "msg": "Chưa cấu hình Gemini API."}

        intent_prompt = f"""
        Phân tích câu lệnh: "{user_input}"
        Ngữ cảnh: Chứng khoán Việt Nam. Nếu thấy các mã như CTG, HPG, VHM... hãy hiểu là mã cổ phiếu.

        Trả về JSON:
        {{
          "action": "scrape" | "query" | "report" | "other",
          "ticker": "Mã CP",
          "focus": "Chủ đề yêu cầu (ví dụ: rủi ro, kết quả kinh doanh)"
        }}
        """
        
        response = await self._call_gemini_with_retry(intent_prompt)
        intent = self._safe_json_parse(response.text) if response else None
        
        if not intent:
            chat_res = await self._call_gemini_with_retry(user_input)
            return {"type": "chat", "msg": chat_res.text[:3500] if chat_res else "Mình nghe đây!"}

        action = intent.get("action", "other")
        ticker = str(intent.get("ticker", "")).upper().strip() if intent.get("ticker") else None
        focus = intent.get("focus")

        if action == "scrape" and ticker:
            return {"type": "cmd_scrape", "ticker": ticker}
        elif action == "query" and ticker:
            msg = await self.query_historical_news(ticker, focus)
            return {"type": "cmd_query", "ticker": ticker, "msg": msg}
        else:
            res = await self._call_gemini_with_retry(user_input)
            return {"type": "chat", "msg": res.text[:3500] if res else "Thư cần mình hỗ trợ gì không?"}

    async def query_historical_news(self, ticker, focus=None):
        if not self.vector_db: return "Database chưa kết nối."
        try:
            news_coll = self.vector_db.collections.get("FinancialNews")
            response = news_coll.query.fetch_objects(
                filters=Filter.by_property("ticker").equal(ticker.upper()),
                limit=5 # Lấy nhiều hơn một chút để AI có dữ liệu
            )
            objs = response.objects
            if not objs: return f"Mình chưa lưu dữ liệu cũ của {ticker}."
            
            context = "\n".join([o.properties.get("content", "") for o in objs])
            
            # ƯU TIÊN: Prompt khống chế độ dài để tránh lỗi Telegram
            query_prompt = f"""
            Dựa trên dữ liệu sau: {context[:4000]}
            Yêu cầu: {focus if focus else 'Phân tích tin tức'} cho mã {ticker}.
            Phong cách: Chuyên gia phân tích chứng khoán, súc tích, chia đầu dòng.
            QUY ĐỊNH: 
            - Tuyệt đối không viết quá 3000 ký tự.
            - SỬ DỤNG thẻ <b> để in đậm các con số, phần trăm và từ khóa quan trọng.
            - Phân tích rõ ràng giữa 'Sự kiện' và 'Ý nghĩa đối với nhà đầu tư'.
            """
            
            res = await self._call_gemini_with_retry(query_prompt)
            if res:
                final_text = res.text
                return final_text[:3500] + "\n...(Bản tin đã được rút gọn để hiển thị)" if len(final_text) > 3500 else final_text
            return "AI không phản hồi."
        except Exception as e:
            return f"Lỗi truy vấn: {str(e)}"

    def extract_text_from_pdf(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=20)
            with pdfplumber.open(BytesIO(resp.content)) as pdf:
                return "".join([p.extract_text() or "" for p in pdf.pages[:3]]).strip()
        except: return ""

    def check_duplicate_and_save(self, ticker, content, threshold=0.92):
        if not self.vector_db: return False
        current_vector = self.get_embedding(content)
        if current_vector is None: return False
        try:
            news_coll = self.vector_db.collections.get("FinancialNews")
            response = news_coll.query.near_vector(
                near_vector=current_vector.tolist(), 
                limit=1, 
                return_metadata=MetadataQuery(distance=True)
            )
            if response.objects:
                if (1 - response.objects[0].metadata.distance) >= threshold: return True
            
            news_coll.data.insert(
                properties={"ticker": ticker.upper(), "content": content[:1500], "timestamp": str(datetime.now())}, 
                vector=current_vector.tolist()
            )
            return False
        except: return False

    async def generate_summary_with_analysis(self, ticker, content):
        """Hàm tóm tắt: Đóng vai chuyên gia, ép số liệu, in đậm chuẩn HTML"""
        prompt = f"""
        Bạn là Giám đốc Phân tích Đầu tư tại Yuanta Securities Vietnam. 
        Hãy tóm tắt tin tức IR cho mã {ticker.upper()} với phong cách chuyên nghiệp, sắc sảo.

        YÊU CẦU ĐỊNH DẠNG & NỘI DUNG:
        1. Chỉ lấy thông tin TÀI CHÍNH/DOANH NGHIỆP thực tế. TUYỆT ĐỐI KHÔNG lấy tin Y tế/Sản khoa.
        2. Ưu tiên hàng đầu: Các con số (%, doanh thu, lợi nhuận, ngày chốt quyền, kế hoạch cổ tức).
        3. Định dạng: Trả về 3-4 gạch đầu dòng ngắn gọn. Mỗi dòng < 12 từ.
        4. Cú pháp: In đậm keyword bằng thẻ <b> (Ví dụ: <b>Lợi nhuận tăng 25%</b>).
        5. Không chào hỏi, không kết luận sáo rỗng kiểu 'triển vọng'. Nếu tin cũ (> 1 năm), hãy báo "Không có tin mới".
        
        Dữ liệu: {content[:3000]}

        Trả về JSON:
        {{
        "summary": "Dùng <b> cho keyword. Ví dụ: • <b>{ticker.upper()}</b> chốt quyền trả cổ tức <b>15%</b>",
        "sentiment": 1.0
        }}
        """
        response = await self._call_gemini_with_retry(prompt)
        return self._safe_json_parse(response.text) if response else None
        
# --- EXPORT INTERFACE ---
ai_engine = AIEngine()
async def handle_chat(u): return await ai_engine.process_chat(u)
def extract_text_from_pdf(url): return ai_engine.extract_text_from_pdf(url)
def check_duplicate(t, c): return ai_engine.check_duplicate_and_save(t, c)

# Hàm này main.py đang gọi đây:
async def generate_summary(t, c): 
    return await ai_engine.generate_summary_with_analysis(t, c)

async def query_historical_news(ticker, focus): 
    return await ai_engine.query_historical_news(ticker, focus)