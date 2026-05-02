import os
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv
from utils.crypto_utils import decrypt_data

class SecretMeng(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        self.key = os.getenv('SECRET_KEY')
        self.enc_file = 'meng.ann'

    @commands.command(name='meng')
    async def meng(self, ctx):
        """Randomly pick a line from the encrypted meng.ann file and display it."""
        if not self.key:
            await ctx.send("❌ Hệ thống chưa cấu hình SECRET_KEY.")
            return

        if not os.path.exists(self.enc_file):
            await ctx.send("❌ Không tìm thấy file dữ liệu đã mã hóa (meng.ann).")
            return

        try:
            # Đọc file mã hóa
            with open(self.enc_file, 'r', encoding='utf-8') as f:
                encrypted_content = f.read()

            # Giải mã
            decrypted_content = decrypt_data(encrypted_content, self.key)
            
            if decrypted_content.startswith("Error"):
                await ctx.send(f"❌ Lỗi giải mã: Dữ liệu có thể bị hỏng hoặc sai key.")
                return

            # Tách dòng và chọn ngẫu nhiên
            lines = [line.strip() for line in decrypted_content.split('\n') if line.strip()]
            
            if not lines:
                await ctx.send("📂 File dữ liệu trống.")
                return

            message = random.choice(lines)
            
            # Gửi tin nhắn với phong cách "bí mật"
            embed = discord.Embed(
                description=f"**{message}**",
                color=discord.Color.from_rgb(255, 182, 193) # Màu hồng nhẹ (Pink)
            )
            embed.set_footer(text="🔐 Decrypted from Shimizu Archive")
            
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Có lỗi xảy ra: {e}")

async def setup(bot):
    await bot.add_cog(SecretMeng(bot))
