import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime
from src.core.logger import log

class ShimizuHelp(commands.HelpCommand):
    def __init__(self):
        super().__init__()

    async def send_bot_help(self, mapping):
        ctx = self.context
        embed = discord.Embed(
            title="🌸 Bảng Chỉ Dẫn Shimizu",
            description=(
                "Chào mừng bồ! Mình là Shimizu - Hầu gái đa năng của bồ. "
                "Dưới đây là danh sách các lệnh mình có thể thực hiện.\n\n"
                "Sử dụng `!help <lệnh>` hoặc `/help <lệnh>` để xem chi tiết."
            ),
            color=discord.Color.from_rgb(255, 182, 193), # Pink Sakura
            timestamp=discord.utils.utcnow()
        )
        
        # Phân loại các Cog
        categories = {
            "🎵 Âm Nhạc": ["Music"],
            "🤖 AI & Trí Tuệ": ["AICog"],
            "🛠️ Tiện Ích & Fun": ["Utility", "TarotCog", "Trivia"],
            "📋 Hệ Thống": ["General", "Presence"]
        }
        
        is_owner = await ctx.bot.is_owner(ctx.author)
        if is_owner:
            categories["⚙️ Quản Trị & Debug"] = ["Debug"]

        for cat_name, cog_names in categories.items():
            cmd_list = []
            for cog_name in cog_names:
                cog = ctx.bot.get_cog(cog_name)
                if cog:
                    # Lấy cả commands và hybrid_commands
                    cmds = cog.get_commands()
                    for cmd in cmds:
                        if not cmd.hidden:
                            # Hiển thị dưới dạng `!lệnh` hoặc `/lệnh`
                            prefix = "!" if not isinstance(cmd, app_commands.Command) else "/"
                            cmd_list.append(f"`{prefix}{cmd.name}`")
            
            if cmd_list:
                embed.add_field(name=cat_name, value=" ".join(cmd_list), inline=False)

        embed.set_footer(text="Shimizu Bot • Dẫn đầu về trí tuệ & âm nhạc", icon_url=ctx.bot.user.display_avatar.url)
        embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
        
        await ctx.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"Lệnh: !{command.name}",
            description=command.help or "Không có mô tả cho lệnh này.",
            color=discord.Color.blue()
        )
        if command.aliases:
            embed.add_field(name="Viết tắt", value=", ".join(command.aliases))
        
        usage = f"!{command.name} {command.signature}"
        embed.add_field(name="Cách dùng", value=f"`{usage}`", inline=False)
        
        await self.context.send(embed=embed)

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = ShimizuHelp()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @commands.hybrid_command(name='ping', description='Kiểm tra độ trễ của bot.')
    async def ping(self, ctx):
        """Kiểm tra độ trễ của bot"""
        latency = round(self.bot.latency * 1000)
        ai_cog = self.bot.get_cog('AICog')
        if ai_cog:
            context = ai_cog.get_persona_context(ctx.author)
            message = context["ping"](latency)
            await ctx.send(message)
        else:
            await ctx.send(f'🏓 Pong! Latency: {latency}ms')

    @commands.hybrid_command(name='hello', description='Chào hỏi người dùng.')
    async def hello(self, ctx):
        """Chào hỏi người dùng"""
        ai_cog = self.bot.get_cog('AICog')
        if ai_cog:
            context = ai_cog.get_persona_context(ctx.author)
            await ctx.send(context["hello"])
        else:
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
