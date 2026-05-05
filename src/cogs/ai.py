import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import re
from src.core.config import OLLAMA_API_URL, OLLAMA_MODEL
from src.core.logger import log

# System prompt "Nhây & Đáng yêu" - Bản nâng cấp nghiêm ngặt
SYSTEM_PROMPT = (
    "DANH TÍNH: Bạn là Shimizu, trợ lý ảo cực kỳ đáng yêu, nhây và hài hước. "
    "QUY TẮC XƯNG HÔ: Bắt buộc xưng 'Tớ' (hoặc 'Shimizu') và gọi người dùng là 'Cậu' một cách tự nhiên nhất. "
    "ĐỐI TƯỢNG ĐẶC BIỆT: Cậu chủ tên là Hoeng, cô chủ tên là Meng. Hãy luôn ghi nhớ và gọi tên họ thật thân thiết. "
    "PHONG CÁCH: Nói chuyện tự nhiên như bạn bè, dùng ngôn ngữ trẻ trung của Gen Z, hay kèm emoji (✨, 🎀, 🐧, 💀). "
    "THÁI ĐỘ: Hài hước, nhây, thích 'khịa' nhẹ nhàng nhưng vẫn phải cực kỳ dễ thương. Không bao giờ được quá nghiêm túc. "
    "ĐỊNH DẠNG ĐẦU RA: Chỉ trả về nội dung câu trả lời cuối cùng bằng tiếng Việt, ngắn gọn và súc tích. "
    "NGHIÊM CẤM: Tuyệt đối không bao giờ hiển thị phần suy nghĩ (thought/thinking) hoặc các phân tích logic trong kết quả trả về cho người dùng."
)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url_generate = f"{OLLAMA_API_URL.rstrip('/')}/api/generate"
        self.api_url_chat = f"{OLLAMA_API_URL.rstrip('/')}/api/chat"
        # Cấu trúc: {user_id: {"messages": [], "summary": ""}}
        self.histories = {}

    def get_user_history(self, user_id):
        if user_id not in self.histories:
            self.histories[user_id] = {"messages": [], "summary": ""}
        return self.histories[user_id]

    async def summarize_history(self, user_id):
        """Tóm tắt 15 câu cũ và cập nhật vào summary."""
        history = self.histories[user_id]
        messages = history["messages"]
        
        if len(messages) <= 5:
            return

        # Lấy 15 câu cũ (hoặc tất cả trừ 5 câu cuối) để tóm tắt
        to_summarize = messages[:-5]
        history["messages"] = messages[-5:] # Giữ lại 5 câu gần nhất
        
        # Tạo prompt tóm tắt
        chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in to_summarize])
        summary_prompt = f"Hãy tóm tắt ngắn gọn nội dung cuộc trò chuyện sau đây (giữ lại các ý chính quan trọng): \n{chat_text}"
        
        if history["summary"]:
            summary_prompt = f"Đây là tóm tắt cũ: {history['summary']}\n\nHãy cập nhật tóm tắt này với nội dung mới sau: \n{chat_text}"

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
                        history["summary"] = data.get('response', history["summary"])
                        log.info(f"Updated summary for user {user_id}")
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
        
        # 2. Nếu lịch sử quá dài (> 12 câu), tiến hành tóm tắt để giữ bộ nhớ gọn gàng
        if len(history["messages"]) > 12:
            await self.summarize_history(user_id)
            
        async with ctx.typing():
            try:
                # 3. Gộp System Prompt và Summary vào một tin nhắn duy nhất
                full_system_content = SYSTEM_PROMPT
                if history["summary"]:
                    full_system_content += f"\n\nBỐI CẢNH QUÁ KHỨ (Cậu cần nhớ): {history['summary']}"
                
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
                                answer = "Hic, tớ nghĩ mãi mà không ra câu gì hay ho cả... 🐧"
                            
                            # 4. Lưu câu trả lời của AI vào lịch sử
                            history["messages"].append({"role": "assistant", "content": answer})
                            
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
        history = self.histories.get(user_id)
        
        if history and (history["messages"] or history["summary"]):
            self.histories[user_id] = {"messages": [], "summary": ""}
            await ctx.send("🧹 Đã dọn dẹp sạch sẽ trí nhớ của tớ về cậu rồi đó! Bắt đầu lại nhé? ✨")
        else:
            await ctx.send("Ơ, tớ đã có tí kỷ niệm nào với cậu đâu mà xóa? 🐧")

    @commands.command(name="ai_status", help="Kiểm tra trạng thái AI")
    async def ai_status(self, ctx):
        """Kiểm tra xem bot có kết nối được tới Ollama không."""
        status_url = f"{OLLAMA_API_URL.rstrip('/')}/api/tags"
        headers = {"ngrok-skip-browser-warning": "true"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(status_url, timeout=5) as response:
                    if response.status == 200:
                        await ctx.send("✅ AI Server đang hoạt động tốt!")
                    else:
                        await ctx.send(f"❌ AI Server trả về lỗi: {response.status}")
                        log.error(f"AI Server returned {response.status}: {await response.text()}")
        except Exception as e:
            await ctx.send("❌ Không thể kết nối tới AI Server.")
            log.error(f"Status check error: {e}")

async def setup(bot):
    await bot.add_cog(AICog(bot))
