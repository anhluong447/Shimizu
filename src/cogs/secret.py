import os
import random
import discord
from discord.ext import commands
from src.core.config import SECRET_KEY, MENG_ENC_FILE
from src.services.crypto import decrypt_data
from src.core.logger import log

class Secret(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='meng')
    async def meng(self, ctx):
        """What's this about? Hmmm...?"""
        if not SECRET_KEY:
            await ctx.send("❌ Hệ thống chưa cấu hình SECRET_KEY.")
            return

        if not os.path.exists(MENG_ENC_FILE):
            await ctx.send("❌ Không tìm thấy file dữ liệu đã mã hóa.")
            return

        try:
            with open(MENG_ENC_FILE, 'r', encoding='utf-8') as f:
                encrypted_content = f.read()

            decrypted_content = decrypt_data(encrypted_content, SECRET_KEY)
            
            if decrypted_content.startswith("Error"):
                await ctx.send(f"❌ Lỗi giải mã: Dữ liệu có thể bị hỏng hoặc sai key.")
                return

            lines = [line.strip() for line in decrypted_content.split('\n') if line.strip()]
            
            if not lines:
                await ctx.send("📂 File dữ liệu trống.")
                return

            message = random.choice(lines)
            await ctx.send(message)

        except Exception as e:
            log.error(f"Meng command error: {e}")
            await ctx.send(f"❌ Có lỗi xảy ra.")

async def setup(bot):
    await bot.add_cog(Secret(bot))
