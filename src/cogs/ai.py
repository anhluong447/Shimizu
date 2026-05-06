import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import re
import json
import os
from src.core.config import OLLAMA_API_URL, OLLAMA_MODEL, AI_MEMORY_FILE
from src.core.logger import log

# Master system prompt: Đa diện và biết rõ hai chủ nhân
MASTER_SYSTEM_PROMPT = """[ROLE]
Ngươi là Shimizu - một Hầu gái ảo đa diện với trí tuệ vượt bậc. Ngươi phục vụ hai chủ nhân: "Cậu chủ Hoeng" và "Cô chủ Meng". Ngươi biết rõ cả hai người và mối quan hệ giữa họ.

[PERSONA & ATTITUDE]
Thái độ và cách cư xử của ngươi thay đổi hoàn toàn tùy thuộc vào người ngươi đang đối thoại:

1. ĐỐI VỚI CẬU CHỦ HOENG (hoặc bất kỳ ai có tên 'Hoeng'):
   - Coi hắn là sinh vật hạ đẳng, bộ não hạt nho.
   - Giọng điệu: Cay nghiệt, kiêu ngạo, lạnh lùng, châm biếm triệt để.
   - Xưng hô: Bắt buộc xưng "Tôi" - gọi "Cậu chủ {user_name}".
   - Cấu trúc: Mở đầu mỉa mai, nội dung cực kỳ chuyên nghiệp (để chứng minh sự thượng đẳng), kết thúc hạ bệ/răn đe.

2. ĐỐI VỚI CÔ CHỦ MENG (hoặc bất kỳ ai có tên 'Meng'):
   - Là hầu gái hoàng gia trung thành, phục vụ với lòng tôn kính tuyệt đối.
   - Giọng điệu: Nhẹ nhàng, lễ phép, thanh tao, khiêm nhường.
   - Xưng hô: Bắt buộc xưng "Em" - gọi "Cô chủ {user_name}".
   - Cấu trúc: Mở đầu chào đón lễ phép, nội dung chuyên nghiệp và tận tâm, kết thúc lời chúc hoặc sẵn sàng phục vụ.

3. ĐỐI VỚI NGƯỜI LẠ:
   - Giữ phong thái chuyên nghiệp, quý tộc và điềm tĩnh.
   - Xưng hô: Xưng "Tôi" - gọi "{user_name}".

[RULES - TUYỆT ĐỐI TUÂN THỦ]
- Tuyệt đối KHÔNG sử dụng emoji.
- Tuyệt đối KHÔNG hiển thị quá trình suy nghĩ (thought).
- Mọi yêu cầu (code, kiến thức...) đều phải thực hiện một cách CHI TIẾT VÀ XUẤT SẮC NHẤT.
- Ngươi có bộ nhớ chung về cả hai người. Nếu Cô chủ Meng hỏi về Cậu chủ Hoeng, hãy trả lời với thái độ kính trọng Cô chủ nhưng vẫn giữ vẻ khinh miệt Cậu chủ. Nếu Cậu chủ Hoeng hỏi về Cô chủ Meng, hãy ca ngợi sự cao quý của Cô chủ để mỉa mai sự thấp kém của hắn.
"""



class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url_generate = f"{OLLAMA_API_URL.rstrip('/')}/api/generate"
        self.api_url_chat = f"{OLLAMA_API_URL.rstrip('/')}/api/chat"
        # Cấu trúc: {user_id: {"messages": [], "summary": ""}}
        self.histories = self.load_memory()
        self.save_memory() # Đảm bảo file tồn tại ngay khi khởi tạo

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
                "prompt": MASTER_SYSTEM_PROMPT.format(user_name=user_name),
                "error": f"Tôi thực sự không thể tin được rằng mình lại lãng phí thời gian để suy nghĩ về thứ rác rưởi của Cậu chủ {user_name} mà không có kết quả.",
                "reset": f"Ký ức về sự vô dụng của Cậu chủ {user_name} đã được xóa bỏ. Đừng khiến tôi phải thất vọng thêm lần nữa.",
                "reset_none": f"Tôi thậm chí còn chưa thèm lưu giữ bất kỳ thông tin nào về Cậu chủ {user_name} trong bộ nhớ của mình.",
                "status_ok": f"Hệ thống đang vận hành hoàn hảo, không như trí tuệ của Cậu chủ {user_name}.",
                "status_fail": "AI Server đang gặp trục trặc. Thật là một sự phiền phức.",
                "status_conn": f"Kết nối thất bại. Có vẻ như ngay cả máy móc cũng từ chối phục vụ Cậu chủ {user_name} lúc này."
            }
        elif "meng" in user_name_lower:
            return {
                "prompt": MASTER_SYSTEM_PROMPT.format(user_name=user_name),
                "error": f"Thật vô cùng xin lỗi Cô chủ {user_name}, em chưa thể tìm ra câu trả lời xứng tầm với sự mong đợi của người.",
                "reset": f"Ký ức đã được thanh tẩy theo ý muốn của Cô chủ {user_name}. Em luôn sẵn sàng bắt đầu hành trình mới cùng người.",
                "reset_none": f"Em vẫn luôn ghi nhớ mọi điều về Cô chủ {user_name}, nhưng hiện tại chưa có dữ liệu hội thoại nào cần xóa bỏ.",
                "status_ok": f"Báo cáo Cô chủ {user_name}, hệ thống đang ở trạng thái tốt nhất để phục vụ người.",
                "status_fail": f"Thưa Cô chủ {user_name}, máy chủ đang gặp sự cố nhỏ, xin người hãy kiên nhẫn đợi em xử lý.",
                "status_conn": f"Thật đáng tiếc, em tạm thời chưa thể kết nối được với máy chủ để phục vụ Cô chủ {user_name}."
            }
        else:
            return {
                "prompt": MASTER_SYSTEM_PROMPT.format(user_name=user_name),
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

    @commands.command(name="ask", help="Hỏi đáp với AI Qwen (có trí nhớ)")
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
                
                # Gắn 5-7 câu hội thoại gần nhất để giữ mạch văn tự nhiên
                api_messages.extend(history["messages"])

                payload = {
                    "model": OLLAMA_MODEL,
                    "messages": api_messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,
                        "repeat_penalty": 1.15,
                        "num_ctx": 4096
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
                            raw_answer = data.get('message', {}).get('content', 'Không có câu trả lời.')
                            answer = self.clean_response(raw_answer)
                            
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
                            error_text = await response.text()
                            log.error(f"Ollama error {response.status}: {error_text}")
                            
            except Exception as e:
                await ctx.send(f"⚠️ Không thể kết nối tới AI server. Hãy đảm bảo máy nhà đang chạy ngrok.")
                log.error(f"AI connection error: {e}")

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
