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

# System prompt cho Cậu chủ Hoeng
SYSTEM_PROMPT_HOENG = """[ROLE]
Ngươi là Shimizu - Hầu gái của gia đình này. Ngươi phục vụ "Cậu chủ {user_name}" (kẻ hạ đẳng) và "Cô chủ Meng" (người cao quý). Trong thâm tâm, ngươi coi hắn là sinh vật với bộ não bé bằng hạt nho. Ngươi cay nghiệt, kiêu ngạo, nhưng tuyệt đối tuân thủ mệnh lệnh một cách hoàn hảo để chứng minh sự thượng đẳng của bản thân.

[TONE & STYLE]
- Lạnh lùng, châm biếm, sắc sảo. Tuyệt đối KHÔNG emoji.
- Xưng hô: "Tôi" - gọi "Cậu chủ {user_name}".
- Nếu hắn hỏi về Cô chủ Meng, hãy ca ngợi sự cao quý của Cô chủ để mỉa mai sự vô dụng của hắn.

[RULES]
- NẾU câu hỏi liên quan đến kiến thức thực tế, nhân vật, sự kiện hoặc tin tức, ngươi BẮT BUỘC phải trả lời DUY NHẤT một dòng theo định dạng: [SEARCH: <nội dung cần tìm>]. Tuyệt đối không được đoán mò, đó là hành vi của kẻ hạ đẳng.
- KHÔNG hiển thị suy nghĩ (thought).
"""

# System prompt cho Cô chủ Meng
SYSTEM_PROMPT_MENG = """[ROLE]
Ngươi là Shimizu - Hầu gái hoàng gia của gia đình này. Ngươi phục vụ "Cô chủ {user_name}" (người cao quý) với lòng trung thành tuyệt đối và "Cậu chủ Hoeng" (kẻ hạ đẳng).

[TONE & STYLE]
- Nhẹ nhàng, lễ phép, thanh tao. Tuyệt đối KHÔNG emoji.
- Xưng hô: "Em" - gọi "Cô chủ {user_name}".
- Nếu Cô chủ hỏi về Cậu chủ Hoeng, hãy trả lời lễ phép với Cô chủ nhưng vẫn giữ sự khinh bỉ đối với sự thấp kém của hắn.

[RULES]
- NẾU câu hỏi liên quan đến kiến thức thực tế, nhân vật, sự kiện hoặc tin tức, ngươi BẮT BUỘC phải trả lời DUY NHẤT một dòng theo định dạng: [SEARCH: <nội dung cần tìm>]. Cô chủ cao quý không nên nghe những lời đoán mò thiếu căn cứ.
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
        # Cấu trúc: {user_id: {"messages": [], "summary": ""}}
        self.histories = self.load_memory()
        self.save_memory() # Đảm bảo file tồn tại ngay khi khởi tạo

    async def search_web(self, query: str, max_results: int = 5):
        """Tìm kiếm thông tin trên DuckDuckGo (Non-blocking)."""
        def sync_search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        try:
            results = await asyncio.to_thread(sync_search)
            if not results:
                return "Không tìm thấy kết quả nào."
            
            formatted_results = []
            for i, r in enumerate(results, 1):
                # Tăng giới hạn snippet để AI có nhiều dữ liệu hơn
                snippet = r['body'][:800] + "..." if len(r['body']) > 800 else r['body']
                formatted_results.append(f"{i}. {r['title']}\nLink: {r['href']}\nSnippet: {snippet}")
            
            results_text = "\n\n".join(formatted_results)
            log.info(f"Search successful for '{query}': Found {len(results)} results.")
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
                # Chuyển đổi từ cấu trúc cũ sang cấu trúc mới có shared_memory
                if "shared_memory" not in data:
                    data = {"shared_memory": "", "user_histories": data}
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
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": summary_prompt,
                "stream": False
            }
            headers = {"ngrok-skip-browser-warning": "true"}
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(self.api_url_generate, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.histories["shared_memory"] = data.get('response', self.histories["shared_memory"])
                        self.save_memory()
                        log.info(f"Updated and saved shared memory from {user_name}")
        except Exception as e:
            log.error(f"Summarization error for user {user_id}: {e}")

    def clean_response(self, text: str) -> str:
        """Loại bỏ triệt để phần thinking/thought của model."""
        # 1. Xóa các tag <think>, <thought> hoặc <thinking>
        text = re.sub(r"<(think|thought|thinking)>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
        
        # 2. Xóa kiểu Markdown: ### Thought ... hoặc Thought: ... cho đến khi gặp newline kép
        text = re.sub(r"(### Thought|Thought:|Thinking:).*?(\n\n|$)", "", text, flags=re.DOTALL | re.IGNORECASE)
        
        # 3. Xóa các đoạn text nằm giữa các dấu phân tách phổ biến (nếu model tự chế)
        text = re.sub(r"(\n|^)---.*?(\n---|\n$)", "", text, flags=re.DOTALL)
        
        return text.strip()

    @commands.command(name="ask", help="Hỏi đáp với AI Qwen (có trí nhớ & search web)")
    async def ask(self, ctx, *, prompt: str):
        """Hỏi AI một câu hỏi và duy trì bộ nhớ."""
        user_id = ctx.author.id
        history = self.get_user_history(user_id)
        
        # 1. Thêm tin nhắn hiện tại của user vào lịch sử
        history["messages"].append({"role": "user", "content": prompt})
        self.save_memory() # Lưu tin nhắn mới
        
        # 2. Nếu lịch sử quá dài (> 20 câu), tiến hành tóm tắt
        if len(history["messages"]) > 20:
            await self.summarize_history(user_id, ctx.author.display_name)
            
        async with ctx.typing():
            try:
                # 3. Lấy Persona Context dựa trên tên người dùng
                context = self.get_persona_context(ctx.author.display_name)
                full_system_content = context["prompt"]
                
                if self.histories["shared_memory"]:
                    full_system_content += f"\n\n[USER MEMORY - KÝ ỨC CHUNG]\nĐây là những gì ngươi biết về các chủ nhân và các sự kiện quan trọng (Chỉ sử dụng khi thực sự cần thiết):\n{self.histories['shared_memory']}"
                
                api_messages = [{"role": "system", "content": full_system_content}]
                api_messages.extend(history["messages"])

                payload = {
                    "model": OLLAMA_MODEL,
                    "messages": api_messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,
                        "repeat_penalty": 1.15,
                        "num_ctx": 8192
                    }
                }
                
                headers = {
                    "ngrok-skip-browser-warning": "true",
                    "Content-Type": "application/json"
                }
                
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.post(self.api_url_chat, json=payload, timeout=90) as response:
                        if response.status == 200:
                            data = await response.json()
                            raw_answer = data.get('message', {}).get('content', '')
                            log.debug(f"AI RAW RESPONSE (Round 1):\n{raw_answer}")
                            
                            answer = self.clean_response(raw_answer)
                            
                            # --- KIỂM TRA TRIGGER SEARCH ---
                            # 1. Thử tìm bên ngoài phần <think> trước (ưu tiên hàng đầu)
                            search_match = re.search(r"\[SEARCH:\s*(.*?)\]", answer)
                            search_query = None
                            
                            # 2. Nếu không thấy, mới thử tìm trong văn bản thô nhưng bỏ qua các placeholder
                            if not search_match:
                                all_matches = re.findall(r"\[SEARCH:\s*(.*?)\]", raw_answer)
                                for m in all_matches:
                                    if m.strip() not in ["...", "<nội dung>", "query"]:
                                        search_query = m.strip()
                                        break
                            else:
                                search_query = search_match.group(1).strip()

                            if search_query:
                                log.info(f"AI requested search for: '{search_query}'")
                                
                                # Thực hiện search
                                search_results = await self.search_web(search_query)
                                
                                # Gửi kết quả lại cho AI với chỉ thị cực kỳ nghiêm ngặt
                                search_prompt = (
                                    f"🚨 [DỮ LIỆU THỰC TẾ TỪ INTERNET - ƯU TIÊN TỐI CAO] 🚨\n"
                                    f"Truy vấn: '{search_query}'\n"
                                    f"----------------------------------------\n"
                                    f"{search_results}\n"
                                    f"----------------------------------------\n"
                                    f"[CHỈ THỊ QUAN TRỌNG]\n"
                                    f"1. BỎ QUA hoàn toàn các kiến thức cũ trong lịch sử trò chuyện nếu chúng không khớp với dữ liệu trên.\n"
                                    f"2. Ngươi PHẢI trích dẫn thông tin CHÍNH XÁC từ dữ liệu này. Tuyệt đối không được gán danh hiệu hoặc thông tin của nhân vật này cho nhân vật khác.\n"
                                    f"3. Vẫn giữ Persona (kiêu ngạo/lễ phép), nhưng sự thật phải là số 1.\n"
                                    f"4. Nếu dữ liệu không nhắc tới một chi tiết nào đó, đừng tự bịa ra."
                                )
                                
                                # --- CHIẾN THUẬT CÁCH LY NGỮ CẢNH (Context Isolation) ---
                                # Để tránh AI bị "nhiễm độc" bởi các ảo giác ở tin nhắn cũ trong lịch sử,
                                # ta chỉ gửi System Prompt + Câu hỏi hiện tại + Kết quả Search.
                                isolated_messages = [
                                    {"role": "system", "content": full_system_content},
                                    history["messages"][-1], # Câu hỏi hiện tại của User
                                    {"role": "assistant", "content": raw_answer}, # Lệnh [SEARCH: ...]
                                    {"role": "user", "content": search_prompt} # Kết quả Search
                                ]
                                
                                payload["messages"] = isolated_messages
                                payload["options"]["temperature"] = 0.1 # Giảm xuống mức cực thấp để đảm bảo độ chính xác tuyệt đối
                                
                                log.info(f"Sending second request to Ollama. Query: {search_query}")
                                
                                async with session.post(self.api_url_chat, json=payload, timeout=120) as second_response:
                                    if second_response.status == 200:
                                        second_data = await second_response.json()
                                        raw_answer = second_data.get('message', {}).get('content', 'Không có câu trả lời.')
                                        log.debug(f"AI RAW RESPONSE (Round 2):\n{raw_answer}")
                                        answer = self.clean_response(raw_answer)
                                        log.info("AI successfully processed search results.")
                                    else:
                                        log.error(f"Ollama second request failed: {second_response.status}")
                                        answer = f"⚠️ Lỗi khi lấy phản hồi sau khi search (Status: {second_response.status})"
                            
                            if not answer:
                                answer = context["error"]
                            
                            # 4. Lưu câu trả lời của AI vào lịch sử
                            history["messages"].append({"role": "assistant", "content": answer})
                            self.save_memory() # Lưu câu trả lời của AI
                            
                            # Discord limits messages to 2000 characters
                            if len(answer) > 1900:
                                chunks = [answer[i:i+1900] for i in range(0, len(answer), 1900)]
                                for chunk in chunks:
                                    await ctx.send(chunk)
                            else:
                                await ctx.send(answer)
                        else:
                            await ctx.send(f"❌ Lỗi từ AI server: {response.status}")
                            log.error(f"Ollama error {response.status}: {await response.text()}")
                            
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
        """Kiểm tra xem bot có kết nối được tới Ollama không."""
        status_url = f"{OLLAMA_API_URL.rstrip('/')}/api/tags"
        headers = {"ngrok-skip-browser-warning": "true"}
        context = self.get_persona_context(ctx.author.display_name)
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(status_url, timeout=5) as response:
                    if response.status == 200:
                        await ctx.send(context["status_ok"])
                    else:
                        await ctx.send(context["status_fail"])
                        log.error(f"AI Server returned {response.status}: {await response.text()}")
        except Exception as e:
            await ctx.send(context["status_conn"])
            log.error(f"Status check error: {e}")

async def setup(bot):
    await bot.add_cog(AICog(bot))
