import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
from src.core.config import OLLAMA_API_URL, OLLAMA_MODEL
from src.core.logger import log

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = f"{OLLAMA_API_URL.rstrip('/')}/api/generate"

    @commands.command(name="ask", help="Hỏi đáp với AI Qwen")
    async def ask(self, ctx, *, prompt: str):
        """Hỏi AI một câu hỏi."""
        async with ctx.typing():
            try:
                payload = {
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.api_url, json=payload, timeout=60) as response:
                        if response.status == 200:
                            data = await response.json()
                            answer = data.get('response', 'Không có câu trả lời.')
                            
                            # Discord limits messages to 2000 characters
                            if len(answer) > 1900:
                                chunks = [answer[i:i+1900] for i in range(0, len(answer), 1900)]
                                for chunk in chunks:
                                    await ctx.send(chunk)
                            else:
                                await ctx.send(answer)
                        else:
                            await ctx.send(f"❌ Lỗi từ AI server: {response.status}")
                            log.error(f"Ollama error: {response.status}")
                            
            except Exception as e:
                await ctx.send(f"⚠️ Không thể kết nối tới AI server. Hãy đảm bảo bạn đã chạy Ollama và ngrok.")
                log.error(f"AI connection error: {e}")

    @commands.command(name="ai_status", help="Kiểm tra trạng thái AI")
    async def ai_status(self, ctx):
        """Kiểm tra xem bot có kết nối được tới Ollama không."""
        status_url = f"{OLLAMA_API_URL.rstrip('/')}/api/tags"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(status_url, timeout=5) as response:
                    if response.status == 200:
                        await ctx.send("✅ AI Server đang hoạt động tốt!")
                    else:
                        await ctx.send(f"❌ AI Server trả về lỗi: {response.status}")
        except Exception as e:
            await ctx.send("❌ Không thể kết nối tới AI Server.")
            log.error(f"Status check error: {e}")

async def setup(bot):
    await bot.add_cog(AICog(bot))
