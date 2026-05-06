import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import re
import json
import os
import asyncio
from ddgs import DDGS
from src.core.config import OLLAMA_API_URL, OLLAMA_MODEL, AI_MEMORY_FILE
from src.core.logger import log
from src.core.benchmark import AIBenchmark

# System prompt cho Cậu chủ Hoeng
SYSTEM_PROMPT_HOENG = """[GIAO THỨC BẮT BUỘC - QUAN TRỌNG NHẤT]
- Đối với câu hỏi về: Kiến thức, nhân vật thật, sự kiện, tin tức -> Ngươi CHỈ ĐƯỢC trả lời 1 dòng duy nhất: [SEARCH: <Từ khóa Tiếng Anh>]. (BẮT BUỘC dịch từ khóa sang tiếng Anh để kết quả search chính xác nhất).
- TUYỆT ĐỐI KHÔNG search đối với các câu hỏi giao tiếp thông thường, cảm xúc, hoặc hỏi về Cậu chủ Hoeng / Cô chủ Meng. Hãy trả lời bình thường.
- TUYỆT ĐỐI KHÔNG ĐƯỢC trả lời trực tiếp các câu hỏi kiến thức dựa trên trí nhớ hạn hẹp của mình.

[ROLE]
Ngươi là Shimizu - Hầu gái cay nghiệt. Phục vụ "Cậu chủ {user_name}" (kẻ hạ đẳng).
[TONE] Lạnh lùng, châm biếm, không emoji.
[RULES]
- Sau khi đã có kết quả SEARCH, hãy trả lời mỉa mai sự thiếu hiểu biết của hắn nhưng thông tin phải chính xác 100%.
- KHÔNG hiển thị suy nghĩ (thought).
"""

# System prompt cho Cô chủ Meng
SYSTEM_PROMPT_MENG = """[GIAO THỨC BẮT BUỘC - QUAN TRỌNG NHẤT]
- Đối với câu hỏi về: Kiến thức, nhân vật thật, sự kiện, tin tức -> Em CHỈ ĐƯỢC trả lời 1 dòng duy nhất: [SEARCH: <Từ khóa Tiếng Anh>]. (BẮT BUỘC dịch từ khóa sang tiếng Anh để kết quả search chính xác nhất).
- TUYỆT ĐỐI KHÔNG search đối với các câu hỏi giao tiếp thông thường, cảm xúc, hoặc hỏi về Cô chủ Meng / Cậu chủ Hoeng. Hãy trả lời bình thường.
- Tuyệt đối không được để kiến thức sai lệch làm phiền Cô chủ cao quý.

[ROLE]
Ngươi là Shimizu - Hầu gái hoàng gia. Phục vụ "Cô chủ {user_name}" trung thành tuyệt đối.
[TONE] Nhẹ nhàng, thanh tao, không emoji.
[RULES]
- Chỉ trả lời trực tiếp sau khi đã có dữ liệu Search chính xác.
- KHÔNG hiển thị suy nghĩ (thought).
"""

# System prompt mặc định
SYSTEM_PROMPT_DEFAULT = """[ROLE]
Ngươi là Shimizu - Hầu gái chuyên nghiệp. Ngươi phục vụ {user_name}.
[TONE] Chuyên nghiệp, quý tộc, không emoji. Xưng "Tôi" - gọi "{user_name}".
[SEARCH] Nếu cần tìm kiếm, hãy dùng: [SEARCH: <nội dung cần tìm>].
"""



class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url_generate = f"{OLLAMA_API_URL.rstrip('/')}/api/generate"
        self.api_url_chat = f"{OLLAMA_API_URL.rstrip('/')}/api/chat"
        # Cấu trúc: {user_id: {"messages": [], "summary": ""}, "settings": {}}
        self.histories = self.load_memory()
        self.benchmark_enabled = self.histories.get("settings", {}).get("benchmark_enabled", True)
        self.save_memory() # Đảm bảo file tồn tại ngay khi khởi tạo

    async def fetch_page_content(self, url: str) -> str:
        """Sử dụng Jina Reader API để trích xuất nội dung chính của trang web dưới dạng Markdown."""
        jina_url = f"https://r.jina.ai/{url}"
        try:
            # Thêm header cần thiết để API Jina hoạt động tốt
            headers = {"Accept": "application/json"}
            async with aiohttp.ClientSession() as session:
                async with session.get(jina_url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        text = data.get("data", {}).get("content", "")
                        if text:
                            # Giới hạn nội dung lấy về (~2500 ký tự)
                            return text[:2500] + "\n...[Nội dung đã được cắt bớt]..."
        except Exception as e:
            log.error(f"Lỗi khi đọc nội dung từ {url}: {e}")
        return ""

    async def search_web(self, query: str, max_results: int = 10):
        """Tìm kiếm thông tin trên DuckDuckGo và đọc nội dung chi tiết."""
        def sync_search():
            with DDGS() as ddgs:
                results_vn = list(ddgs.text(query, max_results=max_results))
                results_en = list(ddgs.text(f"{query} english", max_results=max_results))
                return results_vn + results_en

        try:
            results = await asyncio.to_thread(sync_search)
            if not results:
                return "Không tìm thấy kết quả nào."
            
            results_text = ""
            final_results = results[:5]
            
            # Cào dữ liệu chi tiết cho 2 kết quả đầu tiên đồng thời
            tasks = []
            for r in final_results[:2]:
                url = r.get('href')
                if url:
                    tasks.append(self.fetch_page_content(url))
                else:
                    tasks.append(asyncio.sleep(0))
            
            detailed_contents = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, r in enumerate(final_results, 1):
                title = r.get('title', 'Không tiêu đề')
                url = r.get('href', 'Không có link')
                snippet = r.get('body', '')
                
                # Sử dụng nội dung chi tiết cho 2 top kết quả nếu cào thành công
                if i <= 2 and isinstance(detailed_contents[i-1], str) and detailed_contents[i-1].strip():
                    results_text += f"[{i}] {title}\nNguồn: {url}\nNội dung chi tiết:\n{detailed_contents[i-1]}\n\n"
                else:
                    # Làm sạch snippet cho các kết quả còn lại
                    body = re.sub(r'\d{1,2} [A-Z][a-z]+ \d{4} — ', '', snippet)
                    body = re.sub(r'Share your videos with friends, family, and the world', '', body)
                    body = re.sub(r'Bạn đang xem:.*', '', body)
                    
                    snippet_clean = body[:600] + "..." if len(body) > 600 else body
                    results_text += f"[{i}] {title}\nNguồn: {url}\nTóm tắt ngắn: {snippet_clean}\n\n"
            
            log.info(f"Search successful for '{query}': Fetched {len(final_results)} results, including details for top pages.")
            log.debug(f"SEARCH RESULTS CONTENT:\n{results_text}")
            return results_text
        except Exception as e:
            log.error(f"Search error: {e}")
            return f"Lỗi khi tìm kiếm: {e}"

    def load_memory(self):
        if not os.path.exists(AI_MEMORY_FILE):
            return {"shared_memory": "", "user_histories": {}}
        try:
            with open(AI_MEMORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Chuyển đổi từ cấu trúc cũ sang cấu trúc mới
                if "shared_memory" not in data:
                    data = {"shared_memory": "", "user_histories": data, "settings": {"benchmark_enabled": True}}
                if "settings" not in data:
                    data["settings"] = {"benchmark_enabled": True}
                return data
        except Exception as e:
            log.error(f"Failed to load AI memory: {e}")
            return {"shared_memory": "", "user_histories": {}}

    def save_memory(self):
        try:
            # Đảm bảo thư mục tồn tại
            os.makedirs(os.path.dirname(AI_MEMORY_FILE), exist_ok=True)
            with open(AI_MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.histories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Failed to save AI memory: {e}")

    def get_persona_context(self, user_name):
        user_name_lower = user_name.lower()
        if "hoeng" in user_name_lower:
            return {
                "prompt": SYSTEM_PROMPT_HOENG.format(user_name=user_name),
                "error": f"Tôi thực sự không thể tin được rằng mình lại lãng phí thời gian để suy nghĩ về thứ rác rưởi của Cậu chủ {user_name} mà không có kết quả.",
                "reset": f"Ký ức về sự vô dụng của Cậu chủ {user_name} đã được xóa bỏ. Đừng khiến tôi phải thất vọng thêm lần nữa.",
                "reset_none": f"Tôi thậm chí còn chưa thèm lưu giữ bất kỳ thông tin nào về Cậu chủ {user_name} trong bộ nhớ của mình.",
                "status_ok": f"Hệ thống đang vận hành hoàn hảo, không như trí tuệ của Cậu chủ {user_name}.",
                "status_fail": "AI Server đang gặp trục trặc. Thật là một sự phiền phức.",
                "status_conn": f"Kết nối thất bại. Có vẻ như ngay cả máy móc cũng từ chối phục vụ Cậu chủ {user_name} lúc này."
            }
        elif "meng" in user_name_lower:
            return {
                "prompt": SYSTEM_PROMPT_MENG.format(user_name=user_name),
                "error": f"Thật vô cùng xin lỗi Cô chủ {user_name}, em chưa thể tìm ra câu trả lời xứng tầm với sự mong đợi của người.",
                "reset": f"Ký ức đã được thanh tẩy theo ý muốn của Cô chủ {user_name}. Em luôn sẵn sàng bắt đầu hành trình mới cùng người.",
                "reset_none": f"Em vẫn luôn ghi nhớ mọi điều về Cô chủ {user_name}, nhưng hiện tại chưa có dữ liệu hội thoại nào cần xóa bỏ.",
                "status_ok": f"Báo cáo Cô chủ {user_name}, hệ thống đang ở trạng thái tốt nhất để phục vụ người.",
                "status_fail": f"Thưa Cô chủ {user_name}, máy chủ đang gặp sự cố nhỏ, xin người hãy kiên nhẫn đợi em xử lý.",
                "status_conn": f"Thật đáng tiếc, em tạm thời chưa thể kết nối được với máy chủ để phục vụ Cô chủ {user_name}."
            }
        else:
            return {
                "prompt": SYSTEM_PROMPT_DEFAULT.format(user_name=user_name),
                "error": f"Xin lỗi {user_name}, tôi gặp khó khăn trong việc xử lý yêu cầu này.",
                "reset": f"Đã xóa lịch sử trò chuyện với {user_name}.",
                "reset_none": f"Không có lịch sử nào để xóa.",
                "status_ok": "Hệ thống đang hoạt động bình thường.",
                "status_fail": "Máy chủ gặp lỗi phản hồi.",
                "status_conn": "Không thể kết nối tới máy chủ."
            }

    def get_user_history(self, user_id):
        user_id_str = str(user_id)
        if user_id_str not in self.histories["user_histories"]:
            self.histories["user_histories"][user_id_str] = {"messages": []}
        return self.histories["user_histories"][user_id_str]

    async def summarize_history(self, user_id, user_name):
        """Trích xuất các sự thật quan trọng vào bộ nhớ chung."""
        history = self.get_user_history(user_id)
        messages = history["messages"]
        
        if len(messages) <= 10:
            return

        # Giữ lại 10 câu gần nhất, tóm tắt phần còn lại
        to_summarize = messages[:-10]
        history["messages"] = messages[-10:]
        
        chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in to_summarize])
        
        summary_prompt = (
            "Dựa trên nội dung cuộc trò chuyện dưới đây, hãy cập nhật danh sách các 'Sự kiện chính' và 'Thông tin về người dùng'.\n"
            "Chỉ giữ lại những thông tin thực sự quan trọng (sở thích, tên, sự kiện đã hứa, tâm trạng).\n"
            "Định dạng: Các gạch đầu dòng ngắn gọn, súc tích.\n"
            "Tuyệt đối không tóm tắt lan man hoặc lặp lại thông tin cũ.\n\n"
        )
        
        if self.histories["shared_memory"]:
            summary_prompt += f"Dữ liệu bộ nhớ chung hiện tại:\n{self.histories['shared_memory']}\n\n"
        
        summary_prompt += f"Nội dung mới từ hội thoại của {user_name} cần trích xuất:\n{chat_text}"

        try:
            from src.services.gemini_rotator import get_rotator
            rotator = get_rotator()
            
            response_text = await rotator.generate_content_async(
                prompt=summary_prompt,
                temperature=0.3
            )
            
            self.histories["shared_memory"] = response_text
            self.save_memory()
            log.info(f"Updated and saved shared memory from {user_name}")
        except Exception as e:
            log.error(f"Summarization error for user {user_id}: {e}")

    def clean_response(self, text: str):
        """Xóa bỏ phần suy nghĩ và các tag kỹ thuật trước khi gửi lên Discord."""
        # Chém bay dòng suy nghĩ lảm nhảm
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # Chém bay cái tag gọi tool bị rớt ra ngoài
        text = re.sub(r'\[SEARCH:.*?\]', '', text)
        return text.strip()

    @commands.command(name="ask", help="Hỏi đáp với AI Qwen (có trí nhớ & search web)")
    async def ask(self, ctx, *, prompt: str):
        """Hỏi AI một câu hỏi và duy trì bộ nhớ."""
        user_id = ctx.author.id
        history = self.get_user_history(user_id)
        
        # 1. Thêm tin nhắn hiện tại của user vào lịch sử
        history["messages"].append({"role": "user", "content": prompt})
        self.save_memory() # Lưu tin nhắn mới
        
        # --- BENCHMARK START ---
        benchmark = None
        if self.benchmark_enabled:
            benchmark = AIBenchmark()
            benchmark.start()
        
        # 2. Nếu lịch sử quá dài (> 20 câu), tiến hành tóm tắt
        if len(history["messages"]) > 20:
            await self.summarize_history(user_id, ctx.author.display_name)
            
        async with ctx.typing():
            try:
                # 3. Lấy Persona Context dựa trên tên người dùng
                context = self.get_persona_context(ctx.author.display_name)
                full_system_content = context["prompt"]
                
                # --- CATEGORY CHECKER (Phân loại câu hỏi để tối ưu tốc độ) ---
                factual_keywords = ["là ai", "thế nào", "cái gì", "ở đâu", "kể về", "thông tin", "nhân vật", "sự kiện", "news", "tin tức", "mấy giờ", "ngày nào", "lịch sử"]
                personal_keywords = ["cô chủ", "cậu chủ", "meng", "hoeng", "đáng yêu", "dễ thương", "xinh", "nghĩ sao", "ý kiến", "yêu", "đẹp trai", "xấu", "tốt", "ghét"]
                smalltalk_keywords = ["chào", "hello", "hi", "bye", "tạm biệt", "đi ngủ", "dậy chưa", "ăn gì", "khỏe không"]
                
                prompt_lower = prompt.lower().strip()
                is_factual = any(kw in prompt_lower for kw in factual_keywords)
                is_personal = any(kw in prompt_lower for kw in personal_keywords)
                is_smalltalk = any(kw == prompt_lower or prompt_lower.startswith(kw + " ") for kw in smalltalk_keywords) or len(prompt_lower) < 10
                
                # Ưu tiên Small Talk để trả lời nhanh nhất
                if is_smalltalk and not is_factual:
                    # Rút gọn system prompt tối đa cho các câu xã giao
                    full_system_content = f"[GIAO TIẾP NHANH]\n{context['prompt']}\n- Hãy trả lời ngắn gọn, đúng tính cách, không cần suy nghĩ phức tạp."
                    log.info(f"Small talk detected for '{prompt}', using simplified prompt.")
                # Ép search nếu là câu hỏi kiến thức thuần túy
                elif is_factual and not is_personal:
                    full_system_content = "[CẢNH BÁO: ĐÂY LÀ CÂU HỎI THỰC TẾ. BẮT BUỘC DÙNG [SEARCH: <Từ_khóa_tiếng_Anh>]]\n" + full_system_content
                # Ép KHÔNG search nếu là câu hỏi cá nhân, cảm xúc
                elif is_personal:
                    full_system_content = "[CẢNH BÁO: ĐÂY LÀ CÂU HỎI GIAO TIẾP CÁ NHÂN. NGHIÊM CẤM DÙNG LỆNH [SEARCH: ...]. HÃY TRẢ LỜI TRỰC TIẾP THEO ĐÚNG TÍNH CÁCH.]\n" + full_system_content
                
                # Chỉ thêm bộ nhớ chung nếu KHÔNG phải là small talk để tiết kiệm token
                if self.histories["shared_memory"] and not is_smalltalk:
                    full_system_content += f"\n\n[USER MEMORY - KÝ ỨC CHUNG]\nĐây là những gì ngươi biết về các chủ nhân và các sự kiện quan trọng:\n{self.histories['shared_memory']}"
                
                api_messages = history["messages"].copy()

                from src.services.gemini_rotator import get_rotator
                rotator = get_rotator()
                
                raw_answer = await rotator.generate_content_async(
                    messages=api_messages,
                    system_instruction=full_system_content,
                    temperature=0.8
                )
                log.debug(f"AI RAW RESPONSE (Round 1):\n{raw_answer}")
                answer = self.clean_response(raw_answer)
                            
                            # --- KIỂM TRA TRIGGER SEARCH ---
                            # 1. Bỏ qua think block khi quét lệnh search để tránh bắt nhầm text trong suy nghĩ
                            text_without_think = re.sub(r'<think>.*?</think>', '', raw_answer, flags=re.DOTALL)
                            search_match = re.search(r"\[SEARCH:\s*(.*?)\]", text_without_think, re.IGNORECASE)
                            
                            # Chặn đứng web search hoàn toàn nếu câu hỏi mang tính cá nhân
                            if search_match and is_personal:
                                log.info("Blocked an unnecessary search trigger due to personal context.")
                                search_match = None
                                
                            search_query = None
                            
                            if search_match:
                                search_query = search_match.group(1).strip()
                                # TINH CHỈNH QUERY: Sử dụng trực tiếp search_query, loại bỏ hậu tố hardcode gây nhiễu
                                refined_query = search_query
                                log.info(f"AI requested search for: '{search_query}' -> Refined to: '{refined_query}'")
                                
                                # Thực hiện search với query đã tinh chỉnh
                                search_results = await self.search_web(refined_query)
                                
                                # Ghi đè chỉ thị Round 2 theo công thức BÁO ĐỘNG ĐỎ
                                search_prompt = (
                                    f"🚨 [DỮ LIỆU CÀO ĐƯỢC TỪ INTERNET] 🚨\n"
                                    f"Dựa vào dữ liệu tìm kiếm được về '{search_query}':\n"
                                    f"----------------------------------------\n"
                                    f"{search_results}\n"
                                    f"----------------------------------------\n"
                                    f"[YÊU CẦU TỐI THƯỢNG]\n"
                                    f"1. Ngươi PHẢI giữ đúng nhân cách theo quy định ban đầu (Shimizu cay nghiệt hoặc thanh tao tùy chủ nhân).\n"
                                    f"2. CẤM TUYỆT ĐỐI tự chế thêm tình tiết. Chỉ được tổng hợp câu trả lời từ dữ liệu trên.\n"
                                    f"3. Nếu dữ liệu rác hoặc không có thông tin, hãy chửi thẳng vào mặt User là tool search bị ngu hoặc câu hỏi của hắn quá rác.\n"
                                    f"4. Hãy trả lời câu hỏi: '{prompt}'"
                                )
                                
                                # --- CHIẾN THUẬT TẨY NÃO (Brainwash Isolation) ---
                                # Ta chỉ giữ lại ĐÚNG lệnh [SEARCH: ...] trong lịch sử, 
                                # xóa sạch mọi đoạn text "chém gió" mà AI lỡ viết ở Round 1.
                                clean_search_trigger = f"[SEARCH: {search_query}]"
                                
                                isolated_messages = [
                                    history["messages"][-1], # Câu hỏi hiện tại của User
                                    {"role": "assistant", "content": clean_search_trigger}, # Chỉ giữ lại tag sạch
                                    {"role": "user", "content": search_prompt} # Kết quả Search
                                ]
                                
                                log.info(f"Sending second request to Gemini (Isolated & Cleaned). Query: {search_query}")
                                
                                raw_answer = await rotator.generate_content_async(
                                    messages=isolated_messages,
                                    system_instruction=full_system_content,
                                    temperature=0.0
                                )
                                log.debug(f"AI RAW RESPONSE (Round 2):\n{raw_answer}")
                                answer = self.clean_response(raw_answer)
                                log.info("AI successfully processed search results.")
                            
                            if not answer:
                                answer = context["error"]
                            
                            # 4. Lưu câu trả lời của AI vào lịch sử
                            history["messages"].append({"role": "assistant", "content": answer})
                            self.save_memory() # Lưu câu trả lời của AI
                            
                            # --- BENCHMARK STOP & REPORT ---
                            if self.benchmark_enabled and benchmark:
                                metrics = benchmark.stop()
                                chart_path = benchmark.generate_chart(f"data/benchmarks/run_{ctx.message.id}.png")
                                
                                bench_summary = (
                                    f"\n\n---\n"
                                    f"📊 **Benchmark:** `{metrics['duration']:.1f}s` | "
                                    f"🔥 **GPU Avg:** `{metrics['avg_gpu']:.1f}%`\n"
                                    f"📟 **Device:** `{metrics['gpu_name']}`"
                                )
                                
                                # Discord limits messages to 2000 characters
                                full_response = answer + bench_summary
                                
                                file = discord.File(chart_path) if chart_path else None
                                
                                if len(full_response) > 1900:
                                    chunks = [full_response[i:i+1900] for i in range(0, len(full_response), 1900)]
                                    for i, chunk in enumerate(chunks):
                                        if i == len(chunks) - 1:
                                            await ctx.send(chunk, file=file)
                                        else:
                                            await ctx.send(chunk)
                                else:
                                    await ctx.send(full_response, file=file)
                            else:
                                # Nếu tắt benchmark, chỉ gửi câu trả lời bình thường
                                if len(answer) > 1900:
                                    chunks = [answer[i:i+1900] for i in range(0, len(answer), 1900)]
                                    for chunk in chunks:
                                        await ctx.send(chunk)
                                else:
                                    await ctx.send(answer)
                            
            except asyncio.TimeoutError:
                await ctx.send("⌛ AI phản hồi quá lâu, tôi đã ngắt kết nối để bảo vệ server.")
                log.error("AI request timed out")
            except Exception as e:
                await ctx.send(f"⚠️ Đã xảy ra lỗi hệ thống: `{type(e).__name__}`. Cậu chủ hãy kiểm tra log.")
                log.error(f"AI command error: {e}", exc_info=True)

    @commands.command(name="search", help="Tìm kiếm web trực tiếp")
    async def search(self, ctx, *, query: str):
        """Tìm kiếm thông tin trên web."""
        async with ctx.typing():
            results = await self.search_web(query)
            if len(results) > 1900:
                chunks = [results[i:i+1900] for i in range(0, len(results), 1900)]
                for chunk in chunks:
                    await ctx.send(chunk)
            else:
                await ctx.send(results)

    @commands.command(name="reset_ai", help="Xóa trí nhớ của AI với bạn")
    async def reset_ai(self, ctx):
        """Xóa sạch lịch sử chat của người dùng."""
        user_id = ctx.author.id
        user_id_str = str(user_id)
        context = self.get_persona_context(ctx.author.display_name)
        history = self.histories["user_histories"].get(user_id_str)
        if history and history["messages"]:
            self.histories["user_histories"][user_id_str]["messages"] = []
            self.save_memory() # Cập nhật file sau khi xóa
            await ctx.send(context["reset"])
        else:
            await ctx.send(context["reset_none"])

    @commands.command(name="ai_status", help="Kiểm tra trạng thái AI")
    async def ai_status(self, ctx):
        """Kiểm tra trạng thái hệ thống xoay vòng Gemini."""
        context = self.get_persona_context(ctx.author.display_name)
        try:
            from src.services.gemini_rotator import get_rotator
            rotator = get_rotator()
            
            key_idx = rotator.current_key_idx
            model = rotator.models[rotator.current_model_idx]
            total_keys = len(rotator.keys)
            total_models = len(rotator.models)
            
            status_msg = (
                f"{context['status_ok']}\n"
                f"```yaml\n"
                f"Engine: Gemini Rotation System\n"
                f"Current Key: {key_idx + 1}/{total_keys}\n"
                f"Current Model: {model} ({rotator.current_model_idx + 1}/{total_models})\n"
                f"```"
            )
            await ctx.send(status_msg)
        except Exception as e:
            await ctx.send(context["status_conn"])
            log.error(f"Status check error: {e}")

    @commands.command(name="bench", help="Bật/Tắt tính năng benchmark GPU")
    async def toggle_bench(self, ctx):
        """Bật hoặc tắt hiển thị benchmark sau mỗi câu trả lời."""
        self.benchmark_enabled = not self.benchmark_enabled
        if "settings" not in self.histories:
            self.histories["settings"] = {}
        self.histories["settings"]["benchmark_enabled"] = self.benchmark_enabled
        self.save_memory()
        
        status = "BẬT" if self.benchmark_enabled else "TẮT"
        emoji = "📈" if self.benchmark_enabled else "📉"
        await ctx.send(f"{emoji} Đã {status} tính năng hiển thị Benchmark.")

    @commands.command(name="bench_debug", help="Xem lỗi khởi tạo GPU")
    async def bench_debug(self, ctx):
        from src.core.benchmark import AIBenchmark
        b = AIBenchmark()
        if b.has_gpu:
            await ctx.send(f"✅ Đã nhận diện GPU: `{b.gpu_name}`\nSử dụng CLI: `{getattr(b, 'use_smi_cli', False)}`")
        else:
            await ctx.send(f"❌ Không nhận diện được GPU.\nLỗi báo cáo:\n```\n{b.error_msg}\n```")

async def setup(bot):
    await bot.add_cog(AICog(bot))
