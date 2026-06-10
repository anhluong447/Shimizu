import asyncio
import hashlib
import logging
import aiohttp
import re
from ddgs import DDGS
from src.services.db_service import get_db_service

log = logging.getLogger("SearchService")

JINA_BASE = "https://r.jina.ai/"
JINA_TIMEOUT = 5  # seconds — đủ cho wiki page, không block quá lâu
SNIPPET_MIN_LENGTH = 300  # dưới mức này thì fetch full page

# Domain blacklist & whitelist scoring
BLACKLIST = ["youtube.com", "youtu.be", "reddit.com", "twitter.com", "tiktok.com", "instagram.com", "facebook.com"]
WHITELIST = ["fandom.com", "wiki", "wikipedia.org", "ign.com", "gamespot.com", "vnexpress.net", "tuoitre.vn", "thanhnien.vn"]

def score_url(url: str) -> int:
    url_lower = url.lower()
    if any(b in url_lower for b in BLACKLIST):
        return -1      # loại hoàn toàn
    if any(w in url_lower for w in WHITELIST):
        return 2       # ưu tiên fetch trước
    return 1           # bình thường

def clean_markdown(text: str) -> str:
    """Loại bỏ các thành phần dư thừa như link, ảnh và tag HTML từ Markdown cào về."""
    # 1. Remove images: ![alt](url)
    text = re.sub(r'!\[.*?\]\((?:[^()]|\([^()]*\))*\)', '', text)
    # 2. Convert links: [text](url) -> text
    text = re.sub(r'\[(.*?)\]\((?:[^()]|\([^()]*\))*\)', r'\1', text)
    # 3. Remove raw HTML tags: <img>
    text = re.sub(r'<img\s+[^>]*>', '', text)
    # Convert <a ...>text</a> -> text
    text = re.sub(r'<a\s+[^>]*>(.*?)</a>', r'\1', text, flags=re.IGNORECASE)
    # 4. Collapse multiple empty lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

async def fetch_full_content(url: str, max_chars: int = 6000) -> str:
    """
    Fetch nội dung đầy đủ của một URL qua Jina Reader.
    Trả về plain text, cắt ở max_chars.
    Trả về None nếu timeout hoặc lỗi.
    """
    try:
        jina_url = JINA_BASE + url
        headers = {"Accept": "text/plain"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                jina_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=JINA_TIMEOUT)
            ) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()
                # Dọn dẹp nội dung markdown cào về
                cleaned_text = clean_markdown(text)
                # Cắt bớt, giữ phần đầu là relevant nhất
                return cleaned_text[:max_chars] if len(cleaned_text) > max_chars else cleaned_text
    except asyncio.TimeoutError:
        log.warning(f"Jina fetch timeout for: {url}")
        return None
    except Exception as e:
        log.warning(f"Jina fetch failed for {url}: {e}")
        return None

async def determine_search_intent(prompt: str, rotator) -> bool:
    """Quyết định xem câu hỏi có cần tìm kiếm Web hay không."""
    decision_prompt = f"""Quyết định xem câu hỏi sau có cần tìm kiếm thông tin trên Web không.

Cần search (trả về SEARCH) nếu:
- Hỏi về sự kiện/tin tức/số liệu gần đây hoặc các sự kiện đang diễn ra.
- Thông tin cụ thể có thể thay đổi theo thời gian (thời tiết, tỷ số bóng đá, giá cả thị trường hiện tại).
- Hỏi về thông tin của một người/sản phẩm/sự kiện/tổ chức cụ thể cần cập nhật.

Không cần search (trả về SKIP) nếu:
- Câu hỏi thuộc về cảm xúc cá nhân, tâm sự, hoặc trò chuyện phiếm thông thường.
- Hỏi về bản thân bot Shimizu (ví dụ: "Em là ai?", "Em khỏe không?").
- Câu hỏi giải thích các khái niệm cơ bản không đổi theo thời gian (ví dụ: "Thế nào là lập trình hướng đối tượng?").
- Các câu chào hỏi xã giao thông thường.

Trả về duy nhất một từ: SEARCH hoặc SKIP.
Câu hỏi: {prompt}"""
    try:
        response = await rotator.generate_content_async(
            messages=[{"role": "user", "content": decision_prompt}],
            temperature=0.0
        )
        cleaned = response.strip().upper()
        return "SEARCH" in cleaned
    except Exception as e:
        log.error(f"Error determining search intent: {e}")
        return False

async def rewrite_query(prompt: str, rotator) -> str:
    """Viết lại câu hỏi thành một query tìm kiếm tối ưu."""
    rewrite_prompt = f"""Viết lại câu hỏi sau thành một search query duy nhất, ngắn gọn bằng tiếng Anh hoặc tiếng Việt (3-6 từ).
Bỏ hết các từ thừa (ví dụ: "mày biết", "cho tao hỏi", "nhỉ", "không"), chỉ giữ lại các từ khóa quan trọng để tìm kiếm hiệu quả trên Google/DuckDuckGo.
Chỉ trả về duy nhất chuỗi từ khóa tìm kiếm (search query), không thêm dấu ngoặc kép, không thêm lời dẫn giải, không giải thích, không liệt kê danh sách các phương án.

Câu hỏi: {prompt}
Search query:"""
    try:
        response = await rotator.generate_content_async(
            messages=[{"role": "user", "content": rewrite_prompt}],
            temperature=0.0
        )
        return response.strip().strip('"').strip("'")
    except Exception as e:
        log.error(f"Error rewriting query: {e}")
        return prompt

def _ddg_text_search(query: str, max_results: int = 5) -> list:
    """Gọi DuckDuckGo Search đồng bộ."""
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        log.error(f"DuckDuckGo search raw call failed: {e}")
        return []

async def search_web_async(prompt: str, rotator) -> str:
    """Thực hiện toàn bộ pipeline tìm kiếm thông tin trực tuyến có bộ nhớ đệm (caching)."""
    # 1. Xác định intent
    need_search = await determine_search_intent(prompt, rotator)
    if not need_search:
        return None
        
    # 2. Viết lại query
    query = await rewrite_query(prompt, rotator)
    log.info(f"Search query rewritten to: '{query}'")
    
    # 3. Kiểm tra cache
    query_hash = hashlib.sha256(query.lower().strip().encode('utf-8')).hexdigest()
    db = get_db_service()
    cached = db.get_search_cache(query_hash)
    if cached:
        log.info("Search cache hit!")
        return cached
        
    # 4. Tìm kiếm DuckDuckGo (lấy 10 kết quả)
    results = await asyncio.to_thread(_ddg_text_search, query, 10)
    if not results:
        return None
        
    # 5. Filter & Score Results
    scored_results = []
    for r in results:
        url = r.get('href', '')
        score = score_url(url)
        if score > 0:
            scored_results.append((score, r))
            
    # Sắp xếp theo score giảm dần
    scored_results.sort(key=lambda x: x[0], reverse=True)
    sorted_results = [r for score, r in scored_results]
    
    if not sorted_results:
        return None
        
    context_parts = []
    
    # Fetch top 2 song song qua Jina
    top_results = sorted_results[:2]
    tasks = [fetch_full_content(r.get('href', '')) for r in top_results]
    fetched_contents = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Xử lý kết quả fetch của top 2
    for idx, r in enumerate(top_results):
        title = r.get('title', '')
        url = r.get('href', '')
        snippet = r.get('body', '')
        content = fetched_contents[idx]
        
        # Kiểm tra nếu cào Jina thành công
        if isinstance(content, str) and content.strip():
            context_parts.append(
                f"[Nguồn {idx+1}] {title} ({url})\n{content}"
            )
        else:
            log.info(f"Jina fetch failed or timed out for {url}, falling back to snippet.")
            context_parts.append(
                f"[Nguồn {idx+1}] {title}\n{snippet}"
            )
            
    # Thêm snippet trực tiếp cho các nguồn còn lại (từ nguồn 3 đến 5)
    for idx, r in enumerate(sorted_results[2:5], 2):
        title = r.get('title', '')
        snippet = r.get('body', '')
        context_parts.append(
            f"[Nguồn {idx+1}] {title}\n{snippet}"
        )
        
    formatted = "\n\n".join(context_parts)
    
    # 6. Lưu cache
    db.save_search_cache(query_hash, formatted)
    return formatted
