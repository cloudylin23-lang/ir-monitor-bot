import asyncio
from playwright.async_api import async_playwright
from vnstock import *
import re
import httpx
from bs4 import BeautifulSoup

async def find_ir_url(ticker):
    """Tự động tìm kiếm link quan hệ cổ đông (IR) qua Google"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            query = f"{ticker} quan hệ cổ đông công bố thông tin ir"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            await page.goto(search_url, wait_until="networkidle", timeout=45000)
            await page.wait_for_selector('a', timeout=10000)
            
            links = await page.evaluate('''() => Array.from(document.querySelectorAll('a')).map(a => a.href)''')
            
            bad_domains = ["cafef.vn", "vietstock.vn", "fireant.vn", "google.com", "facebook.com", "youtube.com"]
            for link in links:
                if link and "http" in link and not any(d in link for d in bad_domains):
                    if ticker.lower() in link.lower() or "ir" in link.lower() or "investor" in link.lower():
                        return link
            return None
        except Exception as e:
            print(f"❌ Lỗi tự động tìm URL {ticker}: {e}")
            return None
        finally:
            await browser.close()

# --- NEW: CÀO TIN THỊ TRƯỜNG TỪ CAFEF ---
async def get_market_news(ticker):
    """
    Scraper thế hệ mới: Không đợi selector, tự lọc tin nóng, chặn tin cũ 2023-2024.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        page = await context.new_page()
        
        try:
            # Ưu tiên Vietstock vì cấu trúc dễ bốc hơn
            url = f"https://vietstock.vn/{ticker.lower()}/tin-tuc-su-kien.htm"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # Đợi một chút cho JS chạy nhưng không dùng wait_for_selector cứng nhắc
            await asyncio.sleep(2) 

            # Bốc tất cả các thẻ <a> có khả năng là tiêu đề tin tức
            news_list = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll('a'));
                return links
                    .map(a => a.innerText.trim())
                    .filter(text => text.length > 25); // Chỉ lấy câu dài (tiêu đề)
            }''')
            
            # Bộ lọc: Loại bỏ tin cũ và tin rác
            filtered_news = []
            seen = set()
            for n in news_list:
                # Chặn tin từ năm 2023, 2024 để tránh lỗi như mã TGG vừa nãy
                if any(year in n for year in ["2023", "2024", "2025"]):
                    continue
                if n.lower() not in seen:
                    filtered_news.append(n)
                    seen.add(n.lower())

            if len(filtered_news) > 0:
                return "\n".join(filtered_news[:5])
            
            # Nếu Vietstock trắng trơn, thử qua CafeF với cơ chế tương tự
            await page.goto(f"https://cafef.vn/ma-chung-khoan/{ticker.lower()}.chn", timeout=15000)
            await asyncio.sleep(2)
            
            cafef_news = await page.evaluate('''() => {
                const titles = Array.from(document.querySelectorAll('h3 a, .tinmoi a, .list-news-category a'));
                return titles.map(el => el.innerText.trim()).filter(t => t.length > 25);
            }''')
            
            # Tiếp tục lọc tin cũ cho CafeF
            final_cafef = [n for n in cafef_news if not any(y in n for y in ["2023", "2024"])]
            return "\n".join(final_cafef[:5])

        except Exception as e:
            # Trả về trống để không làm dừng cả hệ thống
            print(f"⚠️ {ticker} Scraper bypass: {str(e)[:50]}")
            return ""
        finally:
            await browser.close()

def get_financial_data(ticker):
    """Lấy các chỉ số tài chính cơ bản từ vnstock"""
    try:
        df = financial_ratio(ticker, report_range='quarterly', is_all=False)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            pe = round(latest.get('priceToEarning', 0), 2)
            pb = round(latest.get('priceToBook', 0), 2)
            roe = round(latest.get('roe', 0) * 100, 1) 
            return f"P/E: {pe}, P/B: {pb}, ROE: {roe}%"
        return "N/A"
    except Exception:
        return "Thiếu dữ liệu tài chính"

async def get_ir_html(url, ticker, difficulty='easy'):
    """Cào dữ liệu IR + Tích hợp thêm tin thị trường từ CafeF"""
    async with async_playwright() as p:
        browser_args = ["--disable-blink-features=AutomationControlled"]
        if difficulty == 'hard':
            browser_args.append("--disable-http2")
            
        browser = await p.chromium.launch(headless=True, args=browser_args)
        context = await browser.new_context(
            ignore_https_errors=(difficulty == 'hard'),
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print(f"🚀 Scraping {ticker} tại: {url}...")
            wait_type = "networkidle" if difficulty == 'hard' else "domcontentloaded"
            await page.goto(url, wait_until=wait_type, timeout=60000)
            await asyncio.sleep(4 if difficulty == 'hard' else 2)

            # 1. LẤY LINK PDF & TIÊU ĐỀ IR
            links_data = await page.evaluate('''() => {
                const results = [];
                const anchors = document.querySelectorAll('a');
                anchors.forEach(a => {
                    const href = a.href;
                    const text = a.innerText.replace(/\\n/g, ' ').trim();
                    if (href && (href.toLowerCase().endsWith('.pdf') || href.includes('download') || href.includes('Attachment'))) {
                        if (text.length > 10) {
                            results.push({ href: href, text: text });
                        }
                    }
                });
                return results;
            }''')

            pdf_links = []
            ir_titles = []
            for item in links_data:
                if item["href"] not in pdf_links:
                    pdf_links.append(item["href"])
                    ir_titles.append(item["text"])

            # 2. CÀO TIN THỊ TRƯỜNG (CafeF) ĐỂ BỔ TRỢ
            market_news = await get_market_news(ticker)

            # 3. LẤY TEXT DỰ PHÒNG
            raw_text = await page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in raw_text.split('\n') if len(l.strip()) > 40]
            web_text = "\n".join(lines[:15])

            fin_data = get_financial_data(ticker)

            return {
                # Kết hợp cả tin IR chính thống và tin thị trường báo chí
                "text": f"--- TIN IR ---\n" + ("\n".join(ir_titles[:5]) if ir_titles else web_text) + 
                        f"\n\n--- TIN THỊ TRƯỜNG (CafeF) ---\n{market_news}",
                "pdfs": pdf_links[:5],
                "financials": fin_data,
                "url": url 
            }

        except Exception as e:
            print(f"❌ Lỗi scraper tại mã {ticker}: {e}")
            return None
        finally:
            await browser.close()