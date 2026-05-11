import re
import time
import asyncio
import random
import discord
import traceback
from discord.ext import commands
from discord import app_commands
from .player import YTPlayer
from .downloader import YTSongInfo
from .views import YTSearchView, YTControllerView, build_yt_np_embed
from src.core.config import (
    REPEAT_OFF, REPEAT_ONE, REPEAT_ALL,
    REPEAT_LABELS, AUTOPLAY_LABELS, FFMPEG_OPTIONS
)
from src.core.logger import log


class YouTube(commands.Cog):
    """🎬 YouTube Music — Download & Play engine (tách biệt với SoundCloud)."""

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def is_dj(self, ctx):
        if await self.bot.is_owner(ctx.author):
            return True
        if ctx.author.guild_permissions.administrator:
            return True
        return any(role.name.lower() == 'dj' for role in ctx.author.roles)

    def get_player(self, ctx_or_interaction):
        if isinstance(ctx_or_interaction, discord.Interaction):
            guild = ctx_or_interaction.guild
            channel = ctx_or_interaction.channel
        else:
            guild = ctx_or_interaction.guild
            channel = ctx_or_interaction.channel

        if guild.id not in self.players:
            self.players[guild.id] = YTPlayer(self.bot, guild, channel)
        return self.players[guild.id]

    async def cleanup(self, guild):
        if guild.id in self.players:
            self.players[guild.id].destroy()
            del self.players[guild.id]
        try:
            await guild.voice_client.disconnect()
        except Exception:
            pass

    async def _ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send('❌ Bồ phải vào phòng voice trước!')
            return False
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        elif ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        return True

    # ── Voice state listener (auto-pause/resume) ──────
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        vc = member.guild.voice_client
        if not vc or not vc.channel:
            return
        if not ((before.channel and before.channel.id == vc.channel.id) or
                (after.channel and after.channel.id == vc.channel.id)):
            return

        player = self.players.get(member.guild.id)
        if not player:
            return

        humans = [m for m in vc.channel.members if not m.bot]
        if not humans:
            if vc.is_playing() and not player.auto_paused:
                vc.pause()
                player.pause_time = time.time()
                player.auto_paused = True
                await player.channel.send("⏸️ **Phòng trống:** Tạm dừng nhạc.", delete_after=15)
            if not player.idle_task or player.idle_task.done():
                player.idle_task = self.bot.loop.create_task(self._idle_disconnect(member.guild))
        else:
            if player.idle_task:
                player.idle_task.cancel()
                player.idle_task = None
            if player.auto_paused and vc.is_paused():
                player.total_paused += time.time() - player.pause_time
                vc.resume()
                player.auto_paused = False
                await player.channel.send("▶️ **Có người vào:** Tiếp tục phát!", delete_after=10)

    async def _idle_disconnect(self, guild):
        try:
            await asyncio.sleep(900)
            if guild.id in self.players:
                player = self.players[guild.id]
                await player.channel.send("🔇 **Tự động thoát:** Phòng trống 15 phút.")
            await self.cleanup(guild)
        except asyncio.CancelledError:
            pass

    # ══════════════════════════════════════════════════
    #  COMMANDS
    # ══════════════════════════════════════════════════

    @commands.hybrid_command(name='yt', aliases=['youtube'], description='🎬 Phát nhạc từ YouTube (tải về → phát).')
    @app_commands.describe(query='Tên bài hát hoặc URL YouTube')
    async def yt_play(self, ctx, *, query: str):
        """Tìm kiếm và phát nhạc từ YouTube. Tải MP3 về trước khi phát."""
        if not await self._ensure_voice(ctx):
            return

        is_url = re.match(r'https?://', query)
        if is_url:
            try:
                async with ctx.typing():
                    song = await YTSongInfo.from_url(query, requester=ctx.author, loop=self.bot.loop)
                player = self.get_player(ctx)
                player.queue.append(song)
                vc = ctx.voice_client
                if vc and not (vc.is_playing() or vc.is_paused()):
                    player.next.set()
                await ctx.send(f'✅ Đã thêm: **{song.title}** `[{song.duration_str}]` 📥', delete_after=10)
            except Exception as e:
                log.error(f"[YT] URL error: {e}")
                await ctx.send(f"❌ Lỗi: `{e}`")
        else:
            try:
                async with ctx.typing():
                    results = await YTSongInfo.search(query, loop=self.bot.loop)
                if not results:
                    return await ctx.send('❌ Không tìm thấy kết quả nào trên YouTube!')
                view = YTSearchView(results[:5], ctx.author)
                await ctx.send('🎬 **Kết quả từ YouTube:**', view=view, delete_after=35)
            except Exception as e:
                log.error(f'[YT] Search error: {e}')
                await ctx.send(f'❌ Lỗi tìm kiếm: `{e}`')

    @commands.hybrid_command(name='ytskip', aliases=['yts'], description='Bỏ qua bài YouTube hiện tại.')
    async def yt_skip(self, ctx):
        """Bỏ qua bài hát YouTube hiện tại."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Cần role `DJ` hoặc `Admin`!')
        vc = ctx.voice_client
        if not vc or not (vc.is_playing() or vc.is_paused()):
            return await ctx.send('❌ Không có nhạc để skip!')
        player = self.get_player(ctx)
        if player.repeat_mode == REPEAT_ONE:
            player.repeat_mode = REPEAT_OFF
        vc.stop()
        await ctx.send('⏭️ Đã skip!', delete_after=5)

    @commands.hybrid_command(name='ytpause', description='Tạm dừng nhạc YouTube.')
    async def yt_pause(self, ctx):
        """Tạm dừng phát nhạc YouTube."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Cần role `DJ` hoặc `Admin`!')
        vc = ctx.voice_client
        if vc and vc.is_playing():
            player = self.get_player(ctx)
            player.auto_paused = False
            player.pause_time = time.time()
            vc.pause()
            await ctx.send('⏸️ Đã tạm dừng.', delete_after=5)

    @commands.hybrid_command(name='ytresume', description='Tiếp tục phát nhạc YouTube.')
    async def yt_resume(self, ctx):
        """Tiếp tục phát nhạc YouTube."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Cần role `DJ` hoặc `Admin`!')
        vc = ctx.voice_client
        if vc and vc.is_paused():
            player = self.get_player(ctx)
            player.auto_paused = False
            player.total_paused += time.time() - player.pause_time
            vc.resume()
            await ctx.send('▶️ Tiếp tục phát.', delete_after=5)

    @commands.hybrid_command(name='ytqueue', aliases=['ytq'], description='Xem hàng đợi YouTube.')
    @app_commands.describe(page='Số trang')
    async def yt_queue(self, ctx, page: int = 1):
        """Xem hàng đợi nhạc YouTube."""
        player = self.get_player(ctx)
        if not player.queue and not player.current:
            return await ctx.send('📋 Hàng đợi YouTube trống!')
        items_per_page = 10
        pages = max(1, (len(player.queue) + items_per_page - 1) // items_per_page)
        page = max(1, min(page, pages))
        embed = discord.Embed(title='📋 Hàng đợi YouTube', color=discord.Color.from_str('#FF0000'))
        if player.current:
            cached = '📥' if player.downloader.is_cached(player.current.video_id) else '⏳'
            embed.add_field(
                name=f'🎬 Đang phát {cached}',
                value=f'**{player.current.title}** `[{player.current.duration_str}]`',
                inline=False
            )
        start = (page - 1) * items_per_page
        chunk = list(player.queue)[start:start + items_per_page]
        if chunk:
            lines = []
            for i, s in enumerate(chunk):
                cached = '📥' if player.downloader.is_cached(s.video_id) else '⏳'
                lines.append(f'`{start+i+1}.` {cached} **{s.title}** `[{s.duration_str}]`')
            embed.add_field(name=f'Sắp tới ({len(player.queue)} bài)', value='\n'.join(lines), inline=False)
        embed.set_footer(text=f'Trang {page}/{pages} • 📥=đã tải ⏳=đang chờ • Lặp: {REPEAT_LABELS[player.repeat_mode]}')
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='ytnp', description='Xem bài YouTube đang phát.')
    async def yt_np(self, ctx):
        """Xem bài hát YouTube đang phát."""
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('❌ Không có bài nào đang phát.')
        vc = ctx.voice_client
        paused = vc.is_paused() if vc else False
        embed = build_yt_np_embed(
            player.current, paused=paused, repeat=player.repeat_mode,
            audio_filter=player.filter_name, autoplay=player.autoplay,
            volume=player.volume, current_time=player.get_current_time()
        )
        view = YTControllerView(player)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name='ytstop', aliases=['ytdc', 'ytleave'], description='Dừng YouTube và thoát voice.')
    async def yt_stop(self, ctx):
        """Dừng phát YouTube và thoát phòng voice."""
        if not await self.is_dj(ctx):
            return
        await self.cleanup(ctx.guild)
        await ctx.send('👋 YouTube player đã tắt!', delete_after=5)

    @commands.hybrid_command(name='ytvolume', aliases=['ytv', 'ytvol'], description='Chỉnh âm lượng YouTube (0-200).')
    @app_commands.describe(vol='Âm lượng (0-200)')
    async def yt_volume(self, ctx, vol: int = None):
        """Chỉnh âm lượng YouTube (0-200)."""
        if not await self.is_dj(ctx):
            return
        player = self.get_player(ctx)
        if vol is None:
            return await ctx.send(f'🔊 Âm lượng hiện tại: **{int(player.volume * 100)}%**')
        if vol < 0 or vol > 200:
            return await ctx.send('❌ Âm lượng phải từ 0 đến 200!')
        player.volume = vol / 100
        vc = ctx.voice_client
        if vc and vc.source:
            vc.source.volume = player.volume
        await ctx.send(f'🔊 Đã chỉnh âm lượng: **{vol}%**', delete_after=5)

    @commands.hybrid_command(name='ytfilter', aliases=['ytfx'], description='Bộ lọc âm thanh YouTube.')
    @app_commands.describe(name='normal / bass / nightcore')
    async def yt_filter(self, ctx, name: str = None):
        """Áp dụng bộ lọc: normal / bass / nightcore."""
        if not await self.is_dj(ctx):
            return
        player = self.get_player(ctx)
        filters = {'normal': 'Normal', 'bass': '🔊 Bass Boost', 'nightcore': '🌙 Nightcore'}
        if name is None or name.lower() not in filters:
            return await ctx.send('🔊 **Bộ lọc có sẵn:** `normal`, `bass`, `nightcore`')
        player.filter_name = filters[name.lower()]
        await ctx.send(f'🔊 Bộ lọc: **{player.filter_name}** (áp dụng từ bài tiếp)', delete_after=8)

    @commands.hybrid_command(name='ytautoplay', aliases=['ytap'], description='Bật/Tắt autoplay YouTube.')
    async def yt_autoplay(self, ctx):
        """Bật/Tắt tự động phát bài liên quan trên YouTube."""
        if not await self.is_dj(ctx):
            return
        player = self.get_player(ctx)
        player.autoplay = not player.autoplay
        status = 'BẬT' if player.autoplay else 'TẮT'
        await ctx.send(f'✨ YouTube Autoplay: **{status}**!', delete_after=10)

    @commands.hybrid_command(name='ytrepeat', aliases=['ytloop'], description='Chế độ lặp YouTube: off/one/all.')
    @app_commands.describe(mode='off / one / all')
    async def yt_repeat(self, ctx, mode: str = None):
        """Chế độ lặp YouTube: off / one / all."""
        if not await self.is_dj(ctx):
            return
        player = self.get_player(ctx)
        if mode is None:
            player.repeat_mode = (player.repeat_mode + 1) % 3
        elif mode.lower() in ('off', '0'):
            player.repeat_mode = REPEAT_OFF
        elif mode.lower() in ('one', '1', 'single'):
            player.repeat_mode = REPEAT_ONE
        elif mode.lower() in ('all', '2', 'queue'):
            player.repeat_mode = REPEAT_ALL
        else:
            return await ctx.send('❌ Dùng: `!ytrepeat off/one/all`')
        await ctx.send(f'🔁 Chế độ lặp: **{REPEAT_LABELS[player.repeat_mode]}**', delete_after=5)

    @commands.hybrid_command(name='ytshuffle', description='Trộn hàng đợi YouTube.')
    async def yt_shuffle(self, ctx):
        """Trộn ngẫu nhiên hàng đợi YouTube."""
        if not await self.is_dj(ctx):
            return
        player = self.get_player(ctx)
        if len(player.queue) < 2:
            return await ctx.send('❌ Cần ít nhất 2 bài!')
        random.shuffle(player.queue)
        await ctx.send('🔀 Đã trộn hàng đợi YouTube!', delete_after=5)

    @commands.hybrid_command(name='ytseek', description='Nhảy đến thời gian (VD: 1:30 hoặc 90).')
    @app_commands.describe(time_str='Thời gian (VD: 1:30 hoặc 90)')
    async def yt_seek(self, ctx, time_str: str):
        """Nhảy đến thời gian cụ thể."""
        if not await self.is_dj(ctx):
            return
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('❌ Không có gì đang phát!')
        try:
            if ':' in time_str:
                parts = list(map(int, time_str.split(':')))
                if len(parts) == 2:
                    seconds = parts[0] * 60 + parts[1]
                elif len(parts) == 3:
                    seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
                else:
                    raise ValueError
            else:
                seconds = int(time_str)
        except ValueError:
            return await ctx.send('❌ Định dạng không hợp lệ!')
        if seconds < 0 or seconds > player.current.duration:
            return await ctx.send(f'❌ Phải từ 0 đến {player.current.duration_str}!')
        player.seek_offset = seconds
        vc = ctx.voice_client
        if vc:
            player.repeat_mode = REPEAT_ONE
            vc.stop()
            await asyncio.sleep(1)
            player.repeat_mode = REPEAT_OFF
        await ctx.send(f'⏩ Đã nhảy đến `{time_str}`')

    @commands.hybrid_command(name='ytremove', aliases=['ytrm'], description='Xóa bài khỏi hàng đợi YouTube.')
    @app_commands.describe(index='Số thứ tự')
    async def yt_remove(self, ctx, index: int):
        """Xóa bài hát khỏi hàng đợi YouTube theo số thứ tự."""
        if not await self.is_dj(ctx):
            return
        player = self.get_player(ctx)
        if index < 1 or index > len(player.queue):
            return await ctx.send(f'❌ Số thứ tự phải từ 1 đến {len(player.queue)}!')
        removed = player.queue[index - 1]
        del player.queue[index - 1]
        # Cleanup downloaded file if exists
        player.downloader.cleanup(removed.video_id)
        await ctx.send(f'🗑️ Đã xóa: **{removed.title}**', delete_after=5)

    @commands.hybrid_command(name='ytclear', description='Xóa sạch hàng đợi YouTube.')
    async def yt_clear(self, ctx):
        """Xóa sạch hàng đợi YouTube."""
        if not await self.is_dj(ctx):
            return
        player = self.get_player(ctx)
        # Cleanup downloaded files
        for song in player.queue:
            player.downloader.cleanup(song.video_id)
        player.queue.clear()
        await ctx.send('🗑️ Đã xóa toàn bộ hàng đợi YouTube!', delete_after=5)

    @commands.hybrid_command(name='ythistory', description='Xem lịch sử phát YouTube.')
    async def yt_history(self, ctx):
        """Xem lịch sử 10 bài YouTube vừa phát."""
        player = self.get_player(ctx)
        if not player.history:
            return await ctx.send('📜 Lịch sử trống!')
        desc = '\n'.join(f'`{i+1}.` **{s.title}**' for i, s in enumerate(reversed(player.history)))
        embed = discord.Embed(title='📜 Lịch sử YouTube', description=desc, color=discord.Color.from_str('#FF0000'))
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(YouTube(bot))
