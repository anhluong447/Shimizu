import discord
import os
import json
import re
from discord.ext import commands
from .player import MusicPlayer
from .models import SongInfo
from .views import SearchView
from src.core.config import PLAYLISTS_FILE, REPEAT_LABELS
from src.core.logger import log

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    def get_player(self, ctx):
        if ctx.guild.id not in self.players:
            self.players[ctx.guild.id] = MusicPlayer(self.bot, ctx.guild, ctx.channel)
        return self.players[ctx.guild.id]

    async def is_dj(self, ctx):
        if await self.bot.is_owner(ctx.author): return True
        if ctx.author.guild_permissions.administrator: return True
        return any(role.name.lower() == 'dj' for role in ctx.author.roles)

    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *, query: str):
        """Phát nhạc"""
        if not ctx.author.voice:
            return await ctx.send("❌ Bồ phải vào voice trước!")
        
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        
        is_url = re.match(r'https?://', query)
        async with ctx.typing():
            if is_url:
                song = await SongInfo.from_url(query, requester=ctx.author)
                self.get_player(ctx).queue.append(song)
                if not ctx.voice_client.is_playing():
                    self.get_player(ctx).next.set()
                await ctx.send(f"✅ Đã thêm: **{song.title}**")
            else:
                results = await SongInfo.search(query)
                if not results: return await ctx.send("❌ Không tìm thấy bài nào.")
                await ctx.send("🔍 **Kết quả:**", view=SearchView(results, ctx.author))

    @commands.command(name='skip', aliases=['s'])
    async def skip(self, ctx):
        """Bỏ qua bài hiện tại"""
        if not await self.is_dj(ctx): return
        vc = ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await ctx.send("⏭️ Đã skip!")

    @commands.command(name='stop', aliases=['dc'])
    async def stop(self, ctx):
        """Dừng phát và thoát voice"""
        if not await self.is_dj(ctx): return
        if ctx.guild.id in self.players:
            self.players[ctx.guild.id].destroy()
            del self.players[ctx.guild.id]
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Đã dừng và thoát.")

    @commands.command(name='queue', aliases=['q'])
    async def queue_info(self, ctx):
        """Xem hàng đợi"""
        player = self.get_player(ctx)
        if not player.queue and not player.current:
            return await ctx.send("📋 Hàng đợi trống.")
        
        embed = discord.Embed(title="📋 Hàng đợi nhạc", color=discord.Color.blue())
        if player.current:
            embed.add_field(name="🎵 Đang phát", value=player.current.title, inline=False)
        
        if player.queue:
            q_list = "\n".join([f"{i+1}. {s.title}" for i, s in enumerate(list(player.queue)[:10])])
            embed.add_field(name=f"Sắp tới ({len(player.queue)} bài)", value=q_list, inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))
