import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import re
from src.core.config import OLLAMA_API_URL, OLLAMA_MODEL
from src.core.logger import log

# System prompt "Nhây & Đáng yêu"
SYSTEM_PROMPT = (
    "Bạn là Shimizu, một cô trợ lý ảo cực kỳ đáng yêu, nhây và hài hước. "
    "Hãy xưng hô là 'Tớ' và gọi người dùng là 'Cậu' một cách tự nhiên nhất. "
    "Bạn nói chuyện thân thiện, dùng ngôn ngữ trẻ trung, hay kèm emoji (✨, 🎀, 🐧, 💀). "
    "Đôi khi hãy khịa nhẹ cậu chủ một chút nhưng phải thật dễ thương. "
    "Bạn trả lời bằng tiếng Việt, ngắn gọn, súc tích và không được quá nghiêm túc. "
    "Tuyệt đối không bao giờ trả lời kèm theo phần suy nghĩ (thought/thinking) trong kết quả cuối cùng."
)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = f"{OLLAMA_API_URL.rstrip('/')}/api/generate"

    def clean_response(self, text: str) -> str:
        """Loại bỏ triệt để phần thinking/thought của model."""
        # 1. Xóa các tag <think>, <thought> hoặc <thinking>
        text = re.sub(r"<(think|thought|thinking)>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
        
        # 2. Xóa kiểu Markdown: ### Thought ... hoặc Thought: ... cho đến khi gặp newline kép
        text = re.sub(r"(### Thought|Thought:|Thinking:).*?(\n\n|$)", "", text, flags=re.DOTALL | re.IGNORECASE)
        
        # 3. Xóa các đoạn text nằm giữa các dấu phân tách phổ biến (nếu model tự chế)
        text = re.sub(r"(\n|^)---.*?(\n---|\n$)", "", text, flags=re.DOTALL)
        
        return text.strip()

    @commands.command(name="ask", help="Hỏi đáp với AI Qwen")
    async def ask(self, ctx, *, prompt: str):
        """Hỏi AI một câu hỏi."""
        async with ctx.typing():
            try:
                payload = {
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False
                }
                
                headers = {
                    "ngrok-skip-browser-warning": "true",
                    "Content-Type": "application/json"
                }
                
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.post(self.api_url, json=payload, timeout=60) as response:
                        if response.status == 200:
                            data = await response.json()
                            raw_answer = data.get('response', 'Không có câu trả lời.')
                            answer = self.clean_response(raw_answer)
                            
                            if not answer:
                                answer = "Hic, mình nghĩ mãi mà không ra câu gì hay ho cả... 🐧"
                            
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
                await ctx.send(f"⚠️ Không thể kết nối tới AI server. Hãy đảm bảo bạn đã chạy Ollama và ngrok.")
                log.error(f"AI connection error: {e}")

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
