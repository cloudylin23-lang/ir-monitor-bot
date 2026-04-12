# 🤖 AI-Powered Investor Relations (IR) Monitoring Bot

Dự án Trợ lý ảo thông minh giúp tự động hóa quy trình theo dõi, thu thập và phân tích thông tin Quan hệ cổ đông (Investor Relations) từ các doanh nghiệp niêm yết trên sàn chứng khoán Việt Nam. Hệ thống kết hợp sức mạnh của **Large Language Models (Gemini API)** và kiến trúc **RAG (Retrieval-Augmented Generation)** trên nền tảng **Weaviate Cloud**.

---

## 📌 Tổng quan dự án
Trong thị trường tài chính, thông tin IR (thông cáo báo chí, báo cáo tài chính, nghị quyết HĐQT) thường phân tán và có khối lượng dữ liệu cực lớn. Bot IR được xây dựng để giải quyết bài toán:

* **Chủ động:** Tự động quét tin tức từ các nguồn chính thống và trích xuất dữ liệu từ PDF.
* **Tri thức hóa:** Lưu trữ vector hóa toàn bộ dữ liệu lịch sử lên đám mây.
* **Thông minh:** Phân tích chuyên sâu dựa trên ngữ nghĩa (Semantic Search) thay vì chỉ tìm kiếm từ khóa đơn thuần.

---

## 🏗 Kiến trúc hệ thống & Luồng dữ liệu (RAG Workflow)
Hệ thống được thiết kế theo mô hình **Hybrid AI Architecture**:

1.  **Ingestion Pipeline:** Sử dụng `Playwright` và `BeautifulSoup4` để cào dữ liệu, tích hợp `PyMuPDF` để xử lý các thông cáo dạng PDF chuyên sâu.
2.  **Vector Storage (Weaviate Cloud):** * Sử dụng mô hình `all-MiniLM-L6-v2` để chuyển đổi (Embedding) văn bản thành vector.
    * Lưu trữ trên **Weaviate Cloud Cluster**, cho phép truy xuất dữ liệu lịch sử mọi lúc với độ trễ thấp.
3.  **RAG Engine:** Khi nhận yêu cầu phân tích, hệ thống thực hiện *Vector Search* trên Weaviate để tìm các ngữ cảnh liên quan nhất, sau đó đưa vào Prompt để **Gemini 1.5 Flash** xử lý và phản hồi.

---

## ✨ Tính năng nổi bật
* 🚀 **Weaviate Cloud Integration:** Tối ưu hóa việc lưu trữ tri thức dài hạn trên nền tảng Vector Database chuyên dụng.
* ⚡ **Smart Caching (SQLite):** Cơ chế bộ nhớ đệm 2 lớp giúp giảm 90% chi phí gọi API và tăng tốc độ phản hồi.
* 📄 **Multi-modal Processing:** Xử lý linh hoạt từ HTML thô đến các cấu trúc phức tạp trong file báo cáo tài chính (PDF).
* 📊 **Sentiment Analysis:** Tự động đánh giá sắc thái thị trường (Tích cực/Tiêu cực/Trung tính) cho từng bản tin bằng AI.

---

## 🛠 Cài đặt và Triển khai

### 1. Yêu cầu hệ thống
* Python 3.10 - 3.12
* Google AI Studio API Key (Gemini)
* Weaviate Cloud Services (WCS) Cluster URL & API Key
* Telegram Bot Token (via @BotFather)

### 2. Các bước cài đặt
```bash
# Clone dự án
git clone [https://github.com/cloudylin23-lang/ir-monitor-bot.git](https://github.com/cloudylin23-lang/ir-monitor-bot.git)
cd ir-monitor-bot

# Khởi tạo môi trường ảo và cài đặt thư viện
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Cài đặt trình duyệt cho Playwright
playwright install chromium

3. Cấu hình biến môi trường (.env)

Tạo file `.env` tại thư mục gốc của dự án và cấu hình các biến sau:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
GEMINI_API_KEY=your_gemini_key

# Cấu hình Weaviate Cloud
WEAVIATE_URL=https://your-cluster-id.weaviate.network
WEAVIATE_API_KEY=your_wcs_api_key

📂 Cấu trúc mã nguồn
src/database.py
Quản lý SQLite (lưu trữ Tickers, Subscribers và Cache Layer).
src/engine.py
Xử lý logic AI, kết nối Weaviate Cloud và thực hiện quy trình RAG.
src/scraper.py
Thực hiện cào dữ liệu từ web và trích xuất nội dung từ các file PDF.
main.py
Entry point của hệ thống, điều phối luồng Bot và lập lịch quét tin định kỳ (Scheduler).