import os
import discord
from discord.ext import commands
from src.core.logger import log

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='ping', description='Kiểm tra độ trễ của bot.')
    async def ping(self, ctx):
        """Kiểm tra độ trễ của bot"""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f'🏓 Pong! Latency: {latency}ms')

    @commands.hybrid_command(name='hello', description='Chào hỏi người dùng.')
    async def hello(self, ctx):
        """Chào hỏi người dùng"""
        await ctx.send(f'Chào bồ {ctx.author.name}! Mình là Shimizu, hân hạnh được phục vụ! 🌸')

    @commands.command(name='reset')
    @commands.is_owner()
    async def reset(self, ctx):
        """Reset bot (reload tất cả module)"""
        msg = await ctx.send("🔄 **Đang reset bot...**")
        log.info(f"Bot reset triggered by {ctx.author}")
        
        try:
            # 1. Dọn dẹp music players
            music_cog = self.bot.get_cog('Music')
            if music_cog:
                for vc in self.bot.voice_clients:
                    await vc.disconnect(force=True)
                music_cog.players.clear()

            # 2. Reload cogs
            await self.bot.reload_all_cogs()
            
            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!play"))
            await msg.edit(content="✨ **Bot đã được reset về nguyên trạng ban đầu!**")
            
        except Exception as e:
            log.error(f"Reset error: {e}")
            await msg.edit(content=f"❌ **Lỗi khi reset:** `{e}`")

async def setup(bot):
    await bot.add_cog(General(bot))
