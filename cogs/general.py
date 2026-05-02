import os
import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Kiểm tra độ trễ của bot"""
        await ctx.send(f'🏓 Pong! Latency: {round(self.bot.latency * 1000)}ms')

    @commands.command()
    async def hello(self, ctx):
        """Chào hỏi người dùng"""
        await ctx.send(f'Chào bồ {ctx.author.name}! Mình là Shimizu, hân hạnh được phục vụ! 🌸')

    @commands.command(name='reset')
    @commands.is_owner()
    async def reset(self, ctx):
        """Reset bot về nguyên trạng ban đầu (reload tất cả module)"""
        msg = await ctx.send("🔄 **Đang reset bot...**")
        
        try:
            # 1. Dọn dẹp music players và disconnect voice
            music_cog = self.bot.get_cog('Music')
            if music_cog:
                # Disconnect all voice clients
                for vc in self.bot.voice_clients:
                    await vc.disconnect(force=True)
                # Clear player data
                music_cog.players.clear()

            # 2. Reload all cogs
            print("--- Đang reset và tải lại các module ---")
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    cog_name = f'cogs.{filename[:-3]}'
                    try:
                        await self.bot.reload_extension(cog_name)
                        print(f'✅ Đã nạp lại: {filename}')
                    except Exception as e:
                        # Nếu chưa load thì load mới
                        try:
                            await self.bot.load_extension(cog_name)
                            print(f'✅ Đã tải mới: {filename}')
                        except Exception as e2:
                            print(f'❌ Lỗi khi nạp {filename}: {e2}')

            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!play"))
            await msg.edit(content="✨ **Bot đã được reset về nguyên trạng ban đầu!**")
            
        except Exception as e:
            await msg.edit(content=f"❌ **Lỗi khi reset:** `{e}`")
            print(f"[ERROR] Reset error: {e}")

async def setup(bot):
    await bot.add_cog(General(bot))
