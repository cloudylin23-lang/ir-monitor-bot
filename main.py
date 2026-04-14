import asyncio
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery

# 1. QUẢN LÝ DATABASE (Đã thêm các hàm Cache)
from src.database import (
    init_db, add_subscription, get_subscribers, 
    get_all_ticker_configs, update_ticker_url, get_all_users,
    save_to_cache, get_from_cache  # Hàm mới Thư vừa thêm vào db_manager
)

# 2. QUẢN LÝ CÀO TIN
from src.scraper import get_ir_html, find_ir_url

# 3. QUẢN LÝ AI & VECTOR
from src.engine import (
    handle_chat, check_duplicate, generate_summary, 
    query_historical_news, extract_text_from_pdf
)

logging.basicConfig(level=logging.INFO)

# Chỉ load .env khi chạy local
if os.path.exists(".env"):
    load_dotenv()

# Lấy token và dùng .strip() để xóa bỏ khoảng trắng/dấu xuống dòng thừa
raw_token = os.getenv("TELEGRAM_BOT_TOKEN")
TOKEN = raw_token.strip() if raw_token else None

# Debug để check
print(f"TOKEN EXISTS: {TOKEN is not None}")
if TOKEN:
    print(f"TOKEN LENGTH: {len(TOKEN)}") # Để kiểm tra độ dài có khớp ~46 ký tự không

# Fail sớm nếu thiếu
if not TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN")

# Khởi tạo Bot với token đã được làm sạch
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- UTILS: GIAO DIỆN NÚT BẤM ---
def get_investment_markup(ticker):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text=f"📈 Biểu đồ kỹ thuật {ticker.upper()}", 
        url=f"https://vn.tradingview.com/symbols/HOSE-{ticker.upper()}/")
    )
    builder.row(
        types.InlineKeyboardButton(text="💎 Phân tích cơ bản", callback_data=f"rag_{ticker}"),
        types.InlineKeyboardButton(text="⚠️ Rủi ro", callback_data=f"risk_{ticker}")
    )
    builder.row(types.InlineKeyboardButton(
        text="📊 Hồ sơ tài chính", 
        url=f"https://finance.vietstock.vn/{ticker.upper()}/ho-so-doanh-nghiep.htm")
    )
    return builder.as_markup()

def get_sentiment_emoji(score):
    if score >= 0.2: return "🟢 Tích cực"
    if score <= -0.2: return "🔴 Tiêu cực"
    return "🟡 Trung tính"

# --- CORE LOGIC: XỬ LÝ VÀ GỬI TIN ---
async def process_and_send_news(ticker, data, user_ids=None):
    if not data or not data.get("text"): return False

    pdf_links = data.get("pdfs", [])
    content_to_analyze = data["text"]
    pdf_attached = None

    # Ưu tiên đọc nội dung từ PDF nếu có
    for link in pdf_links:
        pdf_text = extract_text_from_pdf(link)
        if pdf_text and len(pdf_text) > 150: 
            content_to_analyze = pdf_text[:4000]
            pdf_attached = link
            break

    # Kiểm tra trùng lặp tin tức để tránh spam
    if check_duplicate(ticker, content_to_analyze): 
        return False

    # AI Phân tích (Bọc trong check None để tránh lỗi 429 làm sập bot)
    analysis = await generate_summary(ticker, content_to_analyze)
    
    if analysis is None:
        logging.warning(f"⚠️ Gemini trả về None cho mã {ticker}. Có thể bị nghẽn API.")
        return False

    summary = analysis.get("summary", "Không thể tóm tắt nội dung.")
    sentiment_score = analysis.get("sentiment", 0)
    sentiment_label = get_sentiment_emoji(sentiment_score)

    # --- LƯU VÀO CACHE---
    save_to_cache(ticker, summary, sentiment_score)

    time_str = datetime.now().strftime("%H:%M %d/%m/%Y")
    
    msg_text = (
        f"🔔 <b>TIN IR MỚI: {ticker}</b>\n"
        f"🕒 <i>{time_str}</i>\n"
        f"🎭 Đánh giá: <b>{sentiment_label}</b>\n"
        f"────────────────\n"
        f"{summary}\n\n"
    )
    
    if pdf_attached:
        msg_text += f"📄 <a href='{pdf_attached}'>Tài liệu gốc (PDF)</a>\n"
    else:
        msg_text += f"🔗 <a href='{data['url']}'>Nguồn doanh nghiệp</a>\n"

    if user_ids:
        for uid in user_ids:
            try:
                await bot.send_message(
                    uid, msg_text, 
                    parse_mode="HTML", 
                    reply_markup=get_investment_markup(ticker),
                    disable_web_page_preview=True
                )
            except Exception as e:
                logging.error(f"Lỗi gửi tin cho {uid}: {e}")
    return True

# --- HANDLERS: XỬ LÝ NÚT BẤM ---
@dp.callback_query(F.data.startswith("rag_"))
async def handle_rag_button(callback: CallbackQuery):
    ticker = callback.data.split("_")[1]
    await callback.answer(f"Đang phân tích sâu {ticker}...")
    response = await query_historical_news(ticker, focus="Phân tích xu hướng và triển vọng dài hạn")
    await callback.message.answer(f"🚀 <b>Phân tích chuyên sâu {ticker}:</b>\n\n{response}", parse_mode="HTML")

@dp.callback_query(F.data.startswith("risk_"))
async def handle_risk_button(callback: CallbackQuery):
    ticker = callback.data.split("_")[1]
    await callback.answer(f"Đang rà soát rủi ro {ticker}...")
    response = await query_historical_news(ticker, focus="Các yếu tố rủi ro và cảnh báo quản trị")
    await callback.message.answer(f"⚠️ <b>Cảnh báo rủi ro {ticker}:</b>\n\n{response}", parse_mode="HTML")

# --- SCHEDULER: QUÉT ĐỊNH KỲ ---
async def scheduler():
    print("⏲️ Scheduler started...")
    while True:
        try:
            now = datetime.now()
            # Gửi Morning Note lúc 8:30
            if now.hour == 8 and now.minute == 30:
                users = get_all_users()
                if users:
                    result = await handle_chat("Viết bản tin MORNING NOTE chuyên nghiệp.")
                    msg = f"☀️ <b>MORNING NOTE - {now.strftime('%d/%m/%Y')}</b>\n\n{result.get('msg')}"
                    for uid in users:
                        try: await bot.send_message(uid, msg, parse_mode="HTML")
                        except: pass
                await asyncio.sleep(60)

            # Quét tin IR (Nghỉ 45s giữa mỗi mã để tránh lỗi 429)
            configs = get_all_ticker_configs()
            for item in configs:
                uids = get_subscribers(item['ticker'])
                if uids:
                    data = await get_ir_html(item['url'], item['ticker'], item['difficulty'])
                    if data:
                        await process_and_send_news(item['ticker'], data, uids)
                    await asyncio.sleep(45) 
            
            await asyncio.sleep(1800) # Nghỉ 30p sau mỗi vòng quét
        except Exception as e:
            logging.error(f"Lỗi Scheduler: {e}")
            await asyncio.sleep(60)

# --- CHAT & COMMANDS ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    init_db()
    await message.answer("Chào bạn! Mình là Trợ lý IR. Gõ tên mã (VD: HPG) để mình check tin mới nhé!")

@dp.message()
async def handle_user_chat(message: Message):
    if not message.text or message.text.startswith("/"): return
    user_id = message.from_user.id
    await bot.send_chat_action(message.chat.id, "typing")
    
    result = await handle_chat(message.text)
    
    if result.get("type") == "cmd_scrape" or result.get("ticker"):
        ticker = result.get("ticker", "").upper()
        if not ticker:
             await message.answer("Thư muốn check mã nào vậy?")
             return

        # --- BƯỚC 1: CHECK CACHE TRƯỚC (QUAN TRỌNG NHẤT) ---
        cached_data = get_from_cache(ticker, expire_minutes=60)
        if cached_data:
            label = get_sentiment_emoji(cached_data['sentiment'])
            await message.answer(
                f"🔔 <b>TIN IR: {ticker} (Bản tin lưu trữ)</b>\n"
                f"🎭 Đánh giá: <b>{label}</b>\n"
                f"────────────────\n"
                f"{cached_data['summary']}\n\n"
                f"🕒 <i>Dữ liệu được cập nhật trong 60 phút qua.</i>",
                parse_mode="HTML",
                reply_markup=get_investment_markup(ticker)
            )
            return

        # --- BƯỚC 2: NẾU KHÔNG CÓ CACHE MỚI ĐI CÀO TIN ---
        await message.answer(f"🔍 Đang quét tin mới cho <b>{ticker}</b>...", parse_mode="HTML")
        add_subscription(user_id, ticker)
        
        configs = get_all_ticker_configs()
        config = next((c for c in configs if c['ticker'] == ticker), None)
        url = config['url'] if config else await find_ir_url(ticker)
        
        if url:
            if not config: update_ticker_url(ticker, url)
            data = await get_ir_html(url, ticker, config['difficulty'] if config else 'easy')
            if data:
                sent = await process_and_send_news(ticker, data, [user_id])
                if not sent:
                    await message.answer(f"✅ Tin tức <b>{ticker}</b> đã là mới nhất hoặc AI đang bận chút.", parse_mode="HTML")
            else:
                await message.answer("❌ Không lấy được dữ liệu. Bạn thử lại sau nhé.")
        else:
            await message.answer(f"❌ Không tìm thấy trang IR của {ticker}.")
    else:
        await message.answer(result.get("msg", "Bạn cần mình hỗ trợ gì không?"), parse_mode="HTML")

async def main():
    init_db()
    print("🚀 Bot IR is Online...")
    await asyncio.gather(
        dp.start_polling(bot),
        scheduler()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
