import os
import json
import discord
import asyncio
import random
import re
import time
import traceback
import aiohttp
from discord.ext import commands
from .player import MusicPlayer
from .models import SongInfo
from .views import SearchView, ControllerView, build_np_embed
from src.core.config import (
    PLAYLISTS_FILE, REPEAT_OFF, REPEAT_ONE, REPEAT_ALL,
    REPEAT_LABELS, AUTOPLAY_LABELS, FFMPEG_OPTIONS
)
from src.core.logger import log


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        if not os.path.exists(PLAYLISTS_FILE):
            with open(PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    async def is_dj(self, ctx):
        if await self.bot.is_owner(ctx.author): return True
        if ctx.author.guild_permissions.administrator: return True
        return any(role.name.lower() == 'dj' for role in ctx.author.roles)

    def get_player(self, ctx_or_interaction):
        if isinstance(ctx_or_interaction, discord.Interaction):
            guild = ctx_or_interaction.guild
            channel = ctx_or_interaction.channel
        else:
            guild = ctx_or_interaction.guild
            channel = ctx_or_interaction.channel
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(self.bot, guild, channel)
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

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            log.error(f'[ERROR] Command {ctx.command}: {error.original}')
            # print(f'[ERROR] Command {ctx.command}: {error.original}')
            # traceback.print_exception(type(error.original), error.original, error.original.__traceback__)
            await ctx.send(f'❌ Lỗi: `{error.original}`')
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'❌ Thiếu tham số: `{error.param.name}`')

    def _get_artist_title(self, song):
        title = song.title
        artist = song.uploader
        for sep in [' - ', ' – ', ' : ']:
            if sep in title:
                parts = title.split(sep, 1)
                artist, title = parts[0], parts[1]
                break
        clean_regex = r'\(.*?\)|\[.*?\]|official|video|lyric|audio|full hd|mv|music video'
        title = re.sub(clean_regex, '', title, flags=re.IGNORECASE).strip()
        artist = re.sub(clean_regex, '', artist, flags=re.IGNORECASE).strip()
        return artist, title

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        vc = member.guild.voice_client
        if not vc or not vc.channel: return

        if (before.channel and before.channel.id == vc.channel.id) or \
           (after.channel and after.channel.id == vc.channel.id):
            player = self.players.get(member.guild.id)
            if not player: return
            humans = [m for m in vc.channel.members if not m.bot]

            if not humans:
                if vc.is_playing() and not player.auto_paused:
                    vc.pause()
                    player.pause_time = time.time()
                    player.auto_paused = True
                    await player.channel.send("⏸️ **Phòng trống:** Tạm dừng nhạc cho đến khi bồ quay lại.", delete_after=15)
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
                    await player.channel.send("▶️ **Đã có người vào:** Tiếp tục quẩy thôi!", delete_after=10)

    async def _idle_disconnect(self, guild):
        try:
            await asyncio.sleep(900)
            if guild.id in self.players:
                player = self.players[guild.id]
                await player.channel.send("🔇 **Tự động thoát:** Phòng trống quá 15 phút, Shimizu đi ngủ đây!")
            await self.cleanup(guild)
        except asyncio.CancelledError:
            pass

    # ── Commands ────────────────────────────────────────
    @commands.command(name='play', aliases=['p'])
    async def play_(self, ctx, *, query: str):
        """Phát nhạc từ URL hoặc tìm kiếm từ khóa."""
        if not await self._ensure_voice(ctx): return
        is_url = re.match(r'https?://', query)
        if is_url:
            try:
                async with ctx.typing():
                    song = await SongInfo.from_url(query, requester=ctx.author, loop=self.bot.loop)
                player = self.get_player(ctx)
                player.queue.append(song)
                vc = ctx.voice_client
                if vc and not (vc.is_playing() or vc.is_paused()):
                    player.next.set()
                await ctx.send(f'✅ Đã thêm: **{song.title}** `[{song.duration_str}]`', delete_after=10)
            except Exception as e:
                log.error(f'Play error: {e}')
                await ctx.send(f'❌ Lỗi khi tải bài hát: `{e}`')
        else:
            try:
                async with ctx.typing():
                    results = await SongInfo.search(query, loop=self.bot.loop)
                if not results:
                    return await ctx.send('❌ Không tìm thấy kết quả nào!')
                view = SearchView(results, ctx.author)
                await ctx.send('🔍 **Kết quả tìm kiếm:**', view=view, delete_after=35)
            except Exception as e:
                log.error(f'Search error: {e}')
                await ctx.send(f'❌ Lỗi khi tìm kiếm: `{e}`')

    @commands.command(name='playnow', aliases=['pn'])
    async def play_now(self, ctx, *, query: str):
        """Phát ngay lập tức (chèn vào đầu hàng đợi và skip bài hiện tại)."""
        if not await self._ensure_voice(ctx): return
        async with ctx.typing():
            song = await SongInfo.from_url(query, requester=ctx.author, loop=self.bot.loop)
        player = self.get_player(ctx)
        player.queue.appendleft(song)
        vc = ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        else:
            player.next.set()
        await ctx.send(f'⚡ Phát ngay: **{song.title}**', delete_after=10)

    @commands.command(name='join', aliases=['j'])
    async def join(self, ctx):
        """Mời bot vào phòng voice."""
        await self._ensure_voice(ctx)

    @commands.command(name='skip', aliases=['s'])
    async def skip(self, ctx):
        """Bỏ qua bài hát hiện tại."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để skip!')
        vc = ctx.voice_client
        if not vc or not (vc.is_playing() or vc.is_paused()):
            return await ctx.send('❌ Không có nhạc để skip!')
        player = self.get_player(ctx)
        if player.repeat_mode == REPEAT_ONE:
            player.repeat_mode = REPEAT_OFF
        vc.stop()
        await ctx.send('⏭️ Đã skip!', delete_after=5)

    @commands.command(name='seek')
    async def seek(self, ctx, time_str: str):
        """Nhảy đến thời gian cụ thể (ví dụ: 1:30 hoặc 90)."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để seek!')
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('❌ Không có gì đang phát!')
        try:
            if ':' in time_str:
                parts = list(map(int, time_str.split(':')))
                if len(parts) == 2: seconds = parts[0] * 60 + parts[1]
                elif len(parts) == 3: seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
                else: raise ValueError
            else:
                seconds = int(time_str)
        except ValueError:
            return await ctx.send('❌ Định dạng thời gian không hợp lệ!')
        if seconds < 0 or seconds > player.current.duration:
            return await ctx.send(f'❌ Thời gian phải từ 0 đến {player.current.duration_str}!')
        player.seek_offset = seconds
        vc = ctx.voice_client
        if vc:
            player.repeat_mode = REPEAT_ONE
            vc.stop()
            await asyncio.sleep(1)
            player.repeat_mode = REPEAT_OFF
        await ctx.send(f'⏩ Đã nhảy đến `{time_str}`')

    @commands.command(name='pause')
    async def pause(self, ctx):
        """Tạm dừng phát nhạc."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để pause!')
        vc = ctx.voice_client
        if vc and vc.is_playing():
            player = self.get_player(ctx)
            player.auto_paused = False
            player.pause_time = time.time()
            vc.pause()
            await ctx.send('⏸️ Đã tạm dừng.', delete_after=5)

    @commands.command(name='resume')
    async def resume(self, ctx):
        """Tiếp tục phát nhạc."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để resume!')
        vc = ctx.voice_client
        if vc and vc.is_paused():
            player = self.get_player(ctx)
            player.auto_paused = False
            player.total_paused += time.time() - player.pause_time
            vc.resume()
            await ctx.send('▶️ Tiếp tục phát.', delete_after=5)

    @commands.command(name='queue', aliases=['q'])
    async def queue_info(self, ctx, page: int = 1):
        """Xem danh sách bài hát trong hàng đợi."""
        player = self.get_player(ctx)
        if not player.queue and not player.current:
            return await ctx.send('📋 Hàng đợi trống!')
        items_per_page = 10
        pages = max(1, (len(player.queue) + items_per_page - 1) // items_per_page)
        page = max(1, min(page, pages))
        embed = discord.Embed(title='📋 Hàng đợi nhạc', color=discord.Color.from_str('#FF6B9D'))
        if player.current:
            embed.add_field(name='🎵 Đang phát', value=f'**{player.current.title}** `[{player.current.duration_str}]`', inline=False)
        start = (page - 1) * items_per_page
        chunk = list(player.queue)[start:start + items_per_page]
        if chunk:
            desc = '\n'.join(f'`{start+i+1}.` **{s.title}** `[{s.duration_str}]`' for i, s in enumerate(chunk))
            embed.add_field(name=f'Sắp tới ({len(player.queue)} bài)', value=desc, inline=False)
        embed.set_footer(text=f'Trang {page}/{pages} • Lặp: {REPEAT_LABELS[player.repeat_mode]}')
        await ctx.send(embed=embed)

    @commands.command(name='np', aliases=['now'])
    async def now_playing(self, ctx):
        """Xem bài hát đang phát hiện tại."""
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('❌ Không có bài nào đang phát.')
        vc = ctx.voice_client
        paused = vc.is_paused() if vc else False
        embed = build_np_embed(player.current, paused=paused, repeat=player.repeat_mode,
                               audio_filter=player.filter_name, autoplay=player.autoplay,
                               volume=player.volume, current_time=player.get_current_time())
        view = ControllerView(player)
        await ctx.send(embed=embed, view=view)

    @commands.command(name='remove', aliases=['rm'])
    async def remove(self, ctx, index: int):
        """Xóa một bài hát khỏi hàng đợi theo số thứ tự."""
        if not await self.is_dj(ctx): return
        player = self.get_player(ctx)
        if index < 1 or index > len(player.queue):
            return await ctx.send(f'❌ Số thứ tự phải từ 1 đến {len(player.queue)}!')
        removed = player.queue[index - 1]
        del player.queue[index - 1]
        await ctx.send(f'🗑️ Đã xóa: **{removed.title}**', delete_after=5)

    @commands.command(name='clear')
    async def clear_queue(self, ctx):
        """Xóa sạch hàng đợi."""
        if not await self.is_dj(ctx): return
        self.get_player(ctx).queue.clear()
        await ctx.send('🗑️ Đã xóa toàn bộ hàng đợi!', delete_after=5)

    @commands.command(name='move')
    async def move(self, ctx, pos_from: int, pos_to: int):
        """Di chuyển bài hát từ vị trí này sang vị trí khác."""
        player = self.get_player(ctx)
        q_len = len(player.queue)
        if pos_from < 1 or pos_from > q_len or pos_to < 1 or pos_to > q_len:
            return await ctx.send(f'❌ Vị trí phải từ 1 đến {q_len}!')
        song = player.queue[pos_from - 1]
        del player.queue[pos_from - 1]
        player.queue.insert(pos_to - 1, song)
        await ctx.send(f'🗂️ Đã chuyển **{song.title}** từ #{pos_from} sang #{pos_to}')

    @commands.command(name='swap')
    async def swap(self, ctx, pos1: int, pos2: int):
        """Hoán đổi vị trí của hai bài hát trong hàng đợi."""
        player = self.get_player(ctx)
        q_len = len(player.queue)
        if pos1 < 1 or pos1 > q_len or pos2 < 1 or pos2 > q_len:
            return await ctx.send(f'❌ Vị trí phải từ 1 đến {q_len}!')
        player.queue[pos1 - 1], player.queue[pos2 - 1] = player.queue[pos2 - 1], player.queue[pos1 - 1]
        await ctx.send(f'🔄 Đã hoán đổi #{pos1} và #{pos2}')

    @commands.command(name='history')
    async def history(self, ctx):
        """Xem lịch sử 10 bài hát vừa phát gần nhất."""
        player = self.get_player(ctx)
        if not player.history:
            return await ctx.send('📜 Lịch sử trống!')
        desc = '\n'.join(f'`{i+1}.` **{s.title}**' for i, s in enumerate(reversed(player.history)))
        embed = discord.Embed(title='📜 Lịch sử phát nhạc', description=desc, color=discord.Color.from_str('#FF6B9D'))
        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def shuffle(self, ctx):
        """Trộn ngẫu nhiên hàng đợi."""
        if not await self.is_dj(ctx): return
        player = self.get_player(ctx)
        if len(player.queue) < 2:
            return await ctx.send('❌ Cần ít nhất 2 bài!')
        random.shuffle(player.queue)
        await ctx.send('🔀 Đã trộn hàng đợi!', delete_after=5)

    @commands.command(name='repeat', aliases=['loop'])
    async def repeat(self, ctx, mode: str = None):
        """Chế độ lặp: off / one / all."""
        if not await self.is_dj(ctx): return
        player = self.get_player(ctx)
        if mode is None:
            player.repeat_mode = (player.repeat_mode + 1) % 3
        elif mode.lower() in ('off', '0'): player.repeat_mode = REPEAT_OFF
        elif mode.lower() in ('one', '1', 'single'): player.repeat_mode = REPEAT_ONE
        elif mode.lower() in ('all', '2', 'queue'): player.repeat_mode = REPEAT_ALL
        else: return await ctx.send('❌ Dùng: `!repeat off/one/all`')
        await ctx.send(f'🔁 Chế độ lặp: **{REPEAT_LABELS[player.repeat_mode]}**', delete_after=5)

    @commands.command(name='filter', aliases=['fx'])
    async def audio_filter(self, ctx, name: str = None):
        """Áp dụng bộ lọc âm thanh: normal / bass / nightcore."""
        if not await self.is_dj(ctx): return
        player = self.get_player(ctx)
        filters = {
            'normal': (FFMPEG_OPTIONS['Normal'], 'Normal'),
            'bass': (FFMPEG_OPTIONS['Bass Boost'], '🔊 Bass Boost'),
            'nightcore': (FFMPEG_OPTIONS['Nightcore'], '🌙 Nightcore')
        }
        if name is None or name.lower() not in filters:
            return await ctx.send('🔊 **Bộ lọc có sẵn:** `normal`, `bass`, `nightcore`')
        player.filter_name = filters[name.lower()][1]
        await ctx.send(f'🔊 Bộ lọc: **{player.filter_name}** (áp dụng từ bài tiếp theo)', delete_after=8)

    @commands.command(name='autoplay', aliases=['ap'])
    async def autoplay(self, ctx):
        """Bật/Tắt tự động phát bài hát liên quan khi hết hàng đợi."""
        if not await self.is_dj(ctx): return
        player = self.get_player(ctx)
        player.autoplay = not player.autoplay
        status = 'BẬT' if player.autoplay else 'TẮT'
        await ctx.send(f'✨ Chế độ Autoplay đã được **{status}**!', delete_after=10)

    @commands.command(name='volume', aliases=['vol', 'v'])
    async def volume(self, ctx, vol: int = None):
        """Chỉnh âm lượng (0-200)."""
        if not await self.is_dj(ctx): return
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

    @commands.command(name='lyrics', aliases=['ly', 'l'])
    async def lyrics(self, ctx, *, query: str = None):
        """Xem lời bài hát đang phát hoặc tìm theo tên."""
        player = self.get_player(ctx)
        if not query:
            if not player.current:
                return await ctx.send('❌ Không có bài nào đang phát để xem lời!')
            artist, title = self._get_artist_title(player.current)
        else:
            if ' - ' in query:
                parts = query.split(' - ', 1)
                artist, title = parts[0], parts[1]
            else:
                artist, title = '', query

        log.info(f"[LYRICS] Searching for: {artist} - {title}")
        async with ctx.typing():
            async def fetch(a, t):
                url = f"https://api.lyrics.ovh/v1/{a}/{t}"
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=10) as resp:
                            if resp.status == 200:
                                res_json = await resp.json()
                                return res_json.get('lyrics')
                except Exception as e:
                    log.error(f"[LYRICS] Fetch error: {e}")
                return None

            lyrics_text = await fetch(artist, title)
            if not lyrics_text and artist:
                log.info(f"[LYRICS] Not found, trying fallback: {artist} {title}")
                lyrics_text = await fetch('', f"{artist} {title}")

        if not lyrics_text:
            search_name = f"{artist} - {title}" if artist else title
            return await ctx.send(f'❌ Không tìm thấy lời cho: **{search_name}**')

        if len(lyrics_text) > 4000:
            lyrics_text = lyrics_text[:4000] + "\n\n...(còn tiếp)..."

        embed = discord.Embed(
            title=f'📜 Lời bài hát: {title}',
            description=lyrics_text,
            color=discord.Color.from_str('#FF6B9D')
        )
        if artist:
            embed.set_author(name=artist)
        embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name='stop', aliases=['leave', 'dc'])
    async def stop(self, ctx):
        """Dừng phát và thoát phòng voice."""
        if not await self.is_dj(ctx): return
        await self.cleanup(ctx.guild)
        await ctx.send('👋 Tạm biệt bồ!', delete_after=5)

    # ── Playlist Commands ──────────────────────────────
    @commands.command(name='save_playlist', aliases=['sp'])
    async def save_playlist(self, ctx, name: str):
        """Lưu hàng đợi hiện tại thành playlist."""
        player = self.get_player(ctx)
        if not player.current and not player.queue:
            return await ctx.send('❌ Hàng đợi đang trống!')
        songs = []
        if player.current: songs.append(player.current._data)
        for s in player.queue: songs.append(s._data)
        with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data[name] = {'creator': ctx.author.id, 'songs': songs}
        with open(PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        await ctx.send(f'💾 Đã lưu playlist **{name}** với {len(songs)} bài!')

    @commands.command(name='load_playlist', aliases=['lp'])
    async def load_playlist(self, ctx, name: str):
        """Tải một playlist đã lưu vào hàng đợi."""
        if not await self._ensure_voice(ctx): return
        with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if name not in data:
            return await ctx.send(f'❌ Không tìm thấy playlist `{name}`!')
        songs_data = data[name]['songs']
        player = self.get_player(ctx)
        async with ctx.typing():
            for s_data in songs_data:
                song = await SongInfo.from_url(s_data, requester=ctx.author, loop=self.bot.loop)
                player.queue.append(song)
        vc = ctx.voice_client
        if vc and not (vc.is_playing() or vc.is_paused()):
            player.next.set()
        await ctx.send(f'✅ Đã tải {len(songs_data)} bài từ playlist **{name}**!')

    @commands.command(name='list_playlists', aliases=['lps'])
    async def list_playlists(self, ctx):
        """Xem danh sách các playlist đã lưu."""
        with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            return await ctx.send('📂 Chưa có playlist nào!')
        desc = '\n'.join(f'• **{name}** ({len(info["songs"])} bài)' for name, info in data.items())
        embed = discord.Embed(title='📂 Danh sách Playlists', description=desc, color=discord.Color.from_str('#FF6B9D'))
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Music(bot))
