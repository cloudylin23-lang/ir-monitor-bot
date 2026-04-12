import sqlite3
import os
from datetime import datetime, timedelta

# Đảm bảo thư mục data tồn tại
os.makedirs("data", exist_ok=True)
DB_PATH = "data/ir_bot.db"

def init_db():
    """Khởi tạo cơ sở dữ liệu SQLite quản lý cấu hình, người dùng và bộ nhớ đệm"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. BẢNG TICKERS: Lưu cấu hình từng mã
    cursor.execute('''CREATE TABLE IF NOT EXISTS tickers (
                        ticker TEXT PRIMARY KEY, 
                        ir_url TEXT, 
                        sector TEXT, 
                        difficulty TEXT DEFAULT 'easy')''')

    # 2. BẢNG SUBS: Lưu danh sách người dùng đăng ký nhận tin
    cursor.execute('''CREATE TABLE IF NOT EXISTS subs (
                        user_id INTEGER, 
                        ticker TEXT,
                        PRIMARY KEY (user_id, ticker))''') 
    
    # 3. NEW: BẢNG NEWS_CACHE: Lưu tóm tắt từ Gemini để tránh gọi API liên tục
    cursor.execute('''CREATE TABLE IF NOT EXISTS news_cache (
                        ticker TEXT PRIMARY KEY,
                        summary TEXT,
                        sentiment REAL,
                        updated_at TIMESTAMP)''')
    
    # Seed data mẫu
    sample_tickers = [
        ('HPG', 'https://www.hoaphat.com.vn/quan-he-co-dong/cong-bo-thong-tin', 'Thép', 'easy'),
        ('VNM', 'https://www.vinamilk.com.vn/investor/reports/shareholder', 'Thực phẩm', 'easy'),
    ]
    cursor.executemany("INSERT OR IGNORE INTO tickers (ticker, ir_url, sector, difficulty) VALUES (?, ?, ?, ?)", sample_tickers)
    
    conn.commit()
    conn.close()
    print("✅ SQLite initialized (Config, Subs & Cache tables).")

# --- CÁC HÀM XỬ LÝ CACHE (BƯỚC 2) ---

def save_to_cache(ticker, summary, sentiment):
    """Lưu kết quả tóm tắt vào database - Đã fix lỗi List data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 🛡️ BƯỚC XỬ LÝ DỮ LIỆU (FIX LỖI)
    # Nếu summary là list, gộp lại thành một đoạn văn bản
    if isinstance(summary, list):
        summary = " ".join(map(str, summary))
    
    # Nếu sentiment là list, lấy giá trị đầu tiên (thường là số)
    if isinstance(sentiment, list):
        sentiment = sentiment[0] if sentiment else 0
        
    try:
        cursor.execute('''INSERT OR REPLACE INTO news_cache (ticker, summary, sentiment, updated_at)
                          VALUES (?, ?, ?, ?)''', (ticker.upper(), str(summary), sentiment, now))
        conn.commit()
    except Exception as e:
        print(f"❌ Lỗi save_to_cache: {e}")
    finally:
        conn.close()

def get_from_cache(ticker, expire_minutes=60):
    """Lấy tin từ cache nếu chưa quá thời gian quy định"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT summary, sentiment, updated_at FROM news_cache WHERE ticker = ?", (ticker.upper(),))
        row = cursor.fetchone()
        if row:
            summary, sentiment, updated_at = row
            update_time = datetime.strptime(updated_at, '%Y-%m-%d %H:%M:%S')
            # Nếu thời gian hiện tại - thời gian cập nhật < số phút hết hạn
            if datetime.now() - update_time < timedelta(minutes=expire_minutes):
                return {"summary": summary, "sentiment": sentiment}
        return None
    except Exception as e:
        print(f"❌ Lỗi get_from_cache: {e}")
        return None
    finally:
        conn.close()

# --- CÁC HÀM CŨ CỦA THƯ (GIỮ NGUYÊN) ---

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT user_id FROM subs")
        users = [row[0] for row in cursor.fetchall()]
        return users
    except Exception as e:
        print(f"❌ Lỗi get_all_users: {e}")
        return []
    finally:
        conn.close()

def get_all_ticker_configs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, ir_url, sector, difficulty FROM tickers")
    rows = cursor.fetchall()
    conn.close()
    return [{"ticker": r[0], "url": r[1], "sector": r[2], "difficulty": r[3]} for r in rows]

def update_ticker_url(ticker, url, difficulty='easy', sector='Mới'):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO tickers (ticker, ir_url, difficulty, sector) VALUES (?, ?, ?, ?)
                      ON CONFLICT(ticker) DO UPDATE SET ir_url=excluded.ir_url''', 
                   (ticker.upper(), url, difficulty, sector))
    conn.commit()
    conn.close()

def add_subscription(user_id, ticker):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO subs (user_id, ticker) VALUES (?, ?)", (user_id, ticker.upper()))
    conn.commit()
    conn.close()

def get_subscribers(ticker):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM subs WHERE ticker = ?", (ticker.upper(),))
    uids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return uids

def get_user_subscriptions(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM subs WHERE user_id = ?", (user_id,))
    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tickers