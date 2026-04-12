import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import os

# Cấu hình trang
st.set_page_config(page_title="IR Bot Admin Dashboard", layout="wide", page_icon="📈")

DB_PATH = "data/ir_bot.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

# --- HEADER ---
st.title("🚀 IR Bot - Hệ thống Quản trị Dữ liệu")
st.markdown("Chào Thu, đây là nơi quản lý các mã cổ phiếu và người dùng đăng ký.")

# --- SIDEBAR: THÊM MÃ MỚI ---
st.sidebar.header("➕ Thêm/Sửa Mã Cổ Phiếu")
with st.sidebar.form("add_ticker_form"):
    new_ticker = st.text_input("Mã Ticker (VD: MWG)").upper()
    new_url = st.text_input("Link IR")
    new_sector = st.selectbox("Ngành", ["Ngân hàng", "Thép", "Bán lẻ", "Công nghệ", "Bất động sản", "Khác"])
    new_diff = st.radio("Độ khó (Scraping)", ["easy", "hard"], horizontal=True)
    
    submit_btn = st.form_submit_button("Cập nhật Database")
    
    if submit_btn and new_ticker and new_url:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO tickers (ticker, ir_url, sector, difficulty) 
                          VALUES (?, ?, ?, ?) 
                          ON CONFLICT(ticker) DO UPDATE SET ir_url=excluded.ir_url, sector=excluded.sector, difficulty=excluded.difficulty''', 
                       (new_ticker, new_url, new_sector, new_diff))
        conn.commit()
        conn.close()
        st.sidebar.success(f"✅ Đã lưu mã {new_ticker}")

# --- MAIN CONTENT ---
tab1, tab2, tab3 = st.tabs(["📊 Danh sách Tickers", "👥 Người dùng đăng ký", "🧠 Vector Embeddings"])

with tab1:
    st.subheader("Quản lý danh sách cào tin")
    conn = get_connection()
    df_tickers = pd.read_sql_query("SELECT * FROM tickers", conn)
    conn.close()
    
    # Hiển thị bảng dữ liệu có thể edit
    st.dataframe(df_tickers, use_container_width=True)
    
    # Biểu đồ phân bổ ngành
    if not df_tickers.empty:
        fig = px.pie(df_tickers, names='sector', title='Phân bổ danh mục theo nhóm ngành')
        st.plotly_chart(fig)

with tab2:
    st.subheader("Thống kê User Subscriptions")
    conn = get_connection()
    df_subs = pd.read_sql_query("SELECT * FROM subs", conn)
    conn.close()
    
    if not df_subs.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.write("Dữ liệu chi tiết:")
            st.table(df_subs)
        with col2:
            # Biểu đồ mã nào được sub nhiều nhất
            sub_counts = df_subs['ticker'].value_counts().reset_index()
            sub_counts.columns = ['Ticker', 'Số người sub']
            fig_bar = px.bar(sub_counts, x='Ticker', y='Số người sub', color='Ticker', title="Độ HOT của các mã")
            st.plotly_chart(fig_bar)
    else:
        st.info("Chưa có ai đăng ký nhận tin.")

with tab3:
    st.subheader("Lịch sử lưu trữ Vector (Chống trùng)")
    conn = get_connection()
    # Lấy 20 bản ghi mới nhất
    df_vectors = pd.read_sql_query("SELECT ticker, content_text, created_at FROM embeddings ORDER BY created_at DESC LIMIT 20", conn)
    conn.close()
    
    st.write("20 tin tức gần nhất đã được 'số hóa' thành Vector:")
    st.dataframe(df_vectors, use_container_width=True)

# Nút dọn dẹp Database (Cẩn thận!)
if st.button("🗑️ Dọn dẹp tin cũ (giữ lại 50 tin mỗi mã)"):
    conn = get_connection()
    # Logic dọn dẹp ở đây...
    st.warning("Tính năng đang phát triển để tránh làm đầy bộ nhớ.")