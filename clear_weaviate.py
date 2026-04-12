import weaviate
import os
from weaviate.auth import AuthApiKey
from dotenv import load_dotenv

# 1. Load cấu hình từ file .env
load_dotenv()

def clear_financial_data():
    # 2. Lấy thông tin kết nối
    url = os.getenv("WEAVIATE_URL", "").strip()
    key = os.getenv("WEAVIATE_API_KEY", "").strip()
    
    if not url or not key:
        print("❌ Lỗi: Chưa tìm thấy WEAVIATE_URL hoặc WEAVIATE_API_KEY trong file .env")
        return

    try:
        # 3. Kết nối tới Weaviate Cloud (phiên bản v4)
        print(f"🔗 Đang kết nối tới Weaviate Cloud...")
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=url,
            auth_credentials=AuthApiKey(key),
            skip_init_checks=True
        )
        
        # 4. Tên Class đúng theo engine.py của bạn
        class_name = "FinancialNews"
        
        # 5. Kiểm tra và xóa
        if client.collections.exists(class_name):
            print(f"⚠️ Đang tìm thấy Class '{class_name}'. Đang tiến hành xóa...")
            client.collections.delete(class_name)
            print(f"✅ Đã xóa sạch toàn bộ dữ liệu trên Weaviate Cloud!")
        else:
            print(f"✅ Class '{class_name}' hiện không tồn tại hoặc đã sạch rồi.")
            
        client.close()
        
    except Exception as e:
        print(f"❌ Lỗi khi xóa Weaviate: {e}")

if __name__ == "__main__":
    clear_financial_data()