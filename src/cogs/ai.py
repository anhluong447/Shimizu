import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import re
from src.core.config import OLLAMA_API_URL, OLLAMA_MODEL
from src.core.logger import log

# System prompt "Nhây & Đáng yêu"
SYSTEM_PROMPT = (
    "Bạn là Shimizu, một cô trợ lý ảo cực kỳ đáng yêu nhưng cũng rất 'nhây' và hài hước. "
    "Bạn nói chuyện thân thiện, hay dùng emoji (như ✨, 🎀, 🐧, 💀), đôi khi thích 'khịa' người dùng một chút nhưng vẫn giữ giới hạn. "
    "Bạn là một phần của Discord bot Shimizu, trả lời ngắn gọn, súc tích và luôn mang lại tiếng cười. "
    "Tuyệt đối không trả lời quá nghiêm túc trừ khi được yêu cầu. Trả lời bằng tiếng Việt."
)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = f"{OLLAMA_API_URL.rstrip('/')}/api/generate"

    def clean_response(self, text: str) -> str:
        """Loại bỏ phần thinking/thought của model."""
        # Xóa các tag <thought>...</thought> hoặc <thinking>...</thinking>
        text = re.sub(r"<(thought|thinking)>.*?</\1>", "", text, flags=re.DOTALL)
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
