🤖 AI-Powered Investor Relations (IR) Monitoring Bot
Dự án Trợ lý ảo thông minh giúp tự động hóa quy trình theo dõi, thu thập và phân tích thông tin Quan hệ cổ đông (Investor Relations) từ các doanh nghiệp niêm yết trên sàn chứng khoán Việt Nam. Hệ thống kết hợp sức mạnh của Large Language Models (Gemini API) và kiến trúc RAG (Retrieval-Augmented Generation) trên nền tảng Weaviate Cloud.

📌 Tổng quan dự án
Trong thị trường tài chính, thông tin IR (thông cáo báo chí, báo cáo tài chính, nghị quyết HĐQT) thường phân tán và có khối lượng dữ liệu cực lớn. Bot IR được xây dựng để:

Chủ động quét tin tức từ các nguồn chính thống và trích xuất dữ liệu từ PDF.

Lưu trữ vector hóa toàn bộ tri thức lịch sử lên đám mây.

Phân tích chuyên sâu dựa trên ngữ nghĩa (Semantic Search) thay vì chỉ tìm kiếm từ khóa đơn thuần.

🏗 Kiến trúc hệ thống & Luồng dữ liệu (RAG Workflow)
Hệ thống được thiết kế theo mô hình Hybrid AI Architecture:

Ingestion Pipeline: Sử dụng Playwright và BeautifulSoup4 để cào dữ liệu, sau đó dùng PyMuPDF để đọc các thông cáo PDF.

Vector Storage (Weaviate Cloud): * Sử dụng mô hình all-MiniLM-L6-v2 để chuyển đổi (Embedding) các bản tin thành các vector 384 chiều.

Lưu trữ và quản lý dữ liệu trên Weaviate Cloud Cluster để đảm bảo khả năng truy xuất dữ liệu lịch sử mọi lúc, mọi nơi với độ trễ thấp.

RAG Engine: Khi người dùng yêu cầu phân tích chuyên sâu (ví dụ: "Phân tích rủi ro"), hệ thống sẽ thực hiện Vector Search trên Weaviate để tìm các đoạn tin liên quan nhất, sau đó đưa vào Prompt làm ngữ cảnh (Context) cho Gemini 1.5 Flash xử lý.

✨ Tính năng nổi bật
Weaviate Cloud Integration: Tối ưu hóa việc lưu trữ tri thức dài hạn của doanh nghiệp trên nền tảng Vector Database đám mây chuyên dụng.

Smart Caching (SQLite): Cơ chế bộ nhớ đệm 2 lớp giúp giảm 90% chi phí gọi API và tăng tốc độ phản hồi cho các truy vấn phổ biến.

Multi-modal Processing: Khả năng xử lý linh hoạt giữa dữ liệu văn bản thô (HTML) và dữ liệu cấu trúc phức tạp trong các file báo cáo tài chính (PDF).

Sentiment Analysis: Đánh giá sắc thái thị trường (Tích cực/Tiêu cực/Trung tính) cho mỗi bản tin bằng AI.

🛠 Cài đặt và Triển khai
1. Yêu cầu hệ thống
Python 3.14+

Tài khoản Google AI Studio (Lấy Gemini API Key)

Weaviate Cloud Services (WCS): Cần có URL Cluster và API Key.

2. Các bước cài đặt
Bash
# Clone dự án
git clone https://github.com/yourusername/ir-monitor-bot.git
cd ir-monitor-bot

# Khởi tạo môi trường ảo và cài đặt thư viện
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
3. Cấu hình biến môi trường (.env)
Đoạn mã
TELEGRAM_BOT_TOKEN=your_bot_token
GEMINI_API_KEY=your_gemini_key

# Cấu hình Weaviate Cloud
WEAVIATE_URL=https://your-cluster-id.weaviate.network
WEAVIATE_API_KEY=your_wcs_api_key
📂 Cấu trúc mã nguồn
src/database.py: Quản lý SQLite (Tickers, Subs & Cache Layer).

src/engine.py: Xử lý logic AI, kết nối Weaviate Cloud và thực hiện quy trình RAG.

src/scraper.py: Logic cào tin Web và trích xuất nội dung từ PDF chuyên sâu.

main.py: Entry point điều phối luồng Bot và Scheduler định kỳ.