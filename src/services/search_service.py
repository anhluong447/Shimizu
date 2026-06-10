import asyncio
import hashlib
import logging
import aiohttp
from ddgs import DDGS
from src.services.db_service import get_db_service

log = logging.getLogger("SearchService")

JINA_BASE = "https://r.jina.ai/"
JINA_TIMEOUT = 5  # seconds — đủ cho wiki page, không block quá lâu
SNIPPET_MIN_LENGTH = 300  # dưới mức này thì fetch full page

async def fetch_full_content(url: str, max_chars: int = 3000) -> str:
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
                # Cắt bớt, giữ phần đầu là relevant nhất
                return text[:max_chars] if len(text) > max_chars else text
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
    rewrite_prompt = f"""Viết lại câu hỏi sau thành một search query ngắn gọn bằng tiếng Anh hoặc tiếng Việt (3-6 từ).
Bỏ hết các từ thừa (ví dụ: "mày biết", "cho tao hỏi", "nhỉ", "không"), chỉ giữ lại các từ khóa quan trọng để tìm kiếm hiệu quả trên Google/DuckDuckGo.

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
        
    # 4. Tìm kiếm DuckDuckGo
    results = await asyncio.to_thread(_ddg_text_search, query, 5)
    if not results:
        return None
        
    # 5. Build context: snippet trước, fetch full nếu snippet ngắn
    context_parts = []

    for i, r in enumerate(results[:3]):  # chỉ xử lý top 3
        title = r.get('title', '')
        url = r.get('href', '')
        snippet = r.get('body', '')

        if len(snippet) >= SNIPPET_MIN_LENGTH:
            # Snippet đủ dài → dùng luôn, không cần fetch
            context_parts.append(
                f"[Nguồn {i+1}] {title}\n{snippet}"
            )
        else:
            # Snippet quá ngắn → fetch full page qua Jina
            log.info(f"Snippet too short ({len(snippet)} chars), fetching full: {url}")
            full_content = await fetch_full_content(url)

            if full_content:
                context_parts.append(
                    f"[Nguồn {i+1}] {title} ({url})\n{full_content}"
                )
            else:
                # Jina fail → fallback về snippet dù ngắn
                context_parts.append(
                    f"[Nguồn {i+1}] {title}\n{snippet}"
                )

        # Chỉ cần 1 full content là đủ cho hầu hết queries
        # Nếu đã có full content từ result đầu tiên, skip fetch cho các result sau
        if i == 0 and len(context_parts[0]) > 1000:
            # Thêm snippets của các result còn lại không cần fetch
            for j, remaining in enumerate(results[1:3], 2):
                context_parts.append(
                    f"[Nguồn {j}] {remaining.get('title', '')}\n{remaining.get('body', '')}"
                )
            break

    formatted = "\n\n".join(context_parts)
    
    # 6. Lưu cache
    db.save_search_cache(query_hash, formatted)
    return formatted
