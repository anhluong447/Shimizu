import os
import json
import discord
import asyncio
import yt_dlp
import itertools
import random
import re
import traceback
from collections import deque
from discord.ext import commands

# ─── Config ─────────────────────────────────────────────
# Tìm file cookies bằng đường dẫn tuyệt đối
def get_cookie_file():
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for f in os.listdir(base_path):
        if 'cookies.txt' in f.lower():
            cookie_path = os.path.join(base_path, f)
            print(f'[INFO] Đã tìm thấy file cookies tại: {cookie_path}')
            return cookie_path
    return None

YTDL_OPTS = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch', # Chuyển sang SoundCloud
    'source_address': '0.0.0.0',
}

YTDL_SEARCH_OPTS = {**YTDL_OPTS, 'default_search': 'scsearch5', 'noplaylist': True}

FFMPEG_BASE = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}
FFMPEG_BASS = {
    'options': '-vn -af "bass=g=10,equalizer=f=40:width_type=h:width=50:g=5"',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}
FFMPEG_NIGHTCORE = {
    'options': '-vn -af "asetrate=44100*1.25,aresample=44100,atempo=1.0"',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

import platform

# Tự động nhận diện đường dẫn FFmpeg theo hệ điều hành
if platform.system() == 'Windows':
    FFMPEG_EXE = r'ffmpeg-8.1-essentials_build\bin\ffmpeg.exe'
else:
    FFMPEG_EXE = 'ffmpeg' # Trên Linux (AWS) đã cài qua apt

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)
ytdl_search = yt_dlp.YoutubeDL(YTDL_SEARCH_OPTS)

REPEAT_OFF, REPEAT_ONE, REPEAT_ALL = 0, 1, 2
REPEAT_LABELS = {0: 'Tắt', 1: '🔂 Lặp bài', 2: '🔁 Lặp hàng đợi'}
AUTOPLAY_LABELS = {False: 'Tắt', True: '✨ Đang bật'}

# ─── Song Info (lightweight, re-creatable) ──────────────
class SongInfo:
    def __init__(self, data, requester):
        self.title = data.get('title', 'Unknown')
        self.url = data.get('webpage_url') or data.get('url', '')
        self.stream_url = data.get('url', '')
        self.thumbnail = data.get('thumbnail', '')
        self.duration = int(data.get('duration') or 0)
        self.uploader = data.get('uploader', 'Unknown')
        self.requester = requester
        self._data = data

    @property
    def duration_str(self):
        if not self.duration:
            return 'Live'
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'

    def make_source(self, ff_opts=None, seek_time=0):
        opts = (ff_opts or FFMPEG_BASE).copy()
        if seek_time > 0:
            # Chèn -ss vào trước đầu vào
            opts['before_options'] = f"{opts['before_options']} -ss {seek_time}"
        return discord.FFmpegPCMAudio(self.stream_url, executable=FFMPEG_EXE, **opts)

    @classmethod
    async def from_url(cls, query, *, requester, loop=None):
        loop = loop or asyncio.get_event_loop()
        if isinstance(query, dict):
            return cls(query, requester)
            
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        if 'entries' in data:
            data = data['entries'][0]
        return cls(data, requester)

    @classmethod
    async def search(cls, query, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        
        async def perform_search(q, limit=5):
            search_query = f'scsearch{limit}:{q}'
            try:
                return await loop.run_in_executor(None, lambda: ytdl_search.extract_info(search_query, download=False))
            except Exception as e:
                print(f'[DEBUG] SoundCloud Search error for "{q}": {e}')
                return None

        # Bước 1: Tìm kiếm nguyên bản (Deep Search)
        data = await perform_search(query)
        
        # Bước 2: Nếu không có kết quả, thử làm sạch query (Query Refinement)
        if not data or 'entries' not in data or not data['entries']:
            print(f'[DEBUG] No results for "{query}", refining query...')
            # Xóa các ký tự đặc biệt, emoji và các tag thừa
            clean_query = re.sub(r'\(.*?\)|\[.*?\]|official|video|lyric|audio|mv|music video|full hd|[^a-zA-Z0-9\sàáạảãâầấnậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', ' ', query, flags=re.IGNORECASE)
            clean_query = ' '.join(clean_query.split()) # Xóa khoảng trắng thừa
            
            if clean_query and clean_query.lower() != query.lower():
                data = await perform_search(clean_query)
                
        # Bước 3: Nếu vẫn không có kết quả, thử tìm theo từng phần (Broad Match)
        if (not data or 'entries' not in data or not data['entries']) and ' - ' in query:
            parts = query.split(' - ')
            print(f'[DEBUG] Still no results, trying broad match with "{parts[-1]}"...')
            data = await perform_search(parts[-1])

        if not data or 'entries' not in data:
            return []
            
        return data['entries']

# ─── Progress Bar Helper ────────────────────────────────
def create_bar(current, total, length=15):
    if total <= 0: return '──' + '🔘' + '──'
    percent = current / total
    filled = int(length * percent)
    bar = '▬' * filled + '🔘' + '─' * (length - filled - 1)
    return bar

# ─── Now Playing Embed Builder ──────────────────────────
def build_np_embed(song: SongInfo, paused=False, repeat=REPEAT_OFF, audio_filter='Normal', autoplay=False, volume=0.5, current_time=0):
    status = '⏸️ Đang tạm dừng' if paused else '🎵 Đang phát'
    embed = discord.Embed(
        title=song.title,
        url=song.url,
        color=discord.Color.from_str('#FF6B9D') if not paused else discord.Color.greyple(),
    )
    embed.set_author(name=status, icon_url='https://i.imgur.com/JfETopg.png')
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    
    # Progress Bar
    bar = create_bar(current_time, song.duration)
    cur_str = f'{int(current_time // 60)}:{int(current_time % 60):02d}'
    dur_str = song.duration_str
    
    embed.add_field(name='⏱️ Tiến trình', value=f'`{cur_str}` {bar} `{dur_str}`', inline=False)
    embed.add_field(name='🎤 Kênh', value=f'`{song.uploader}`', inline=True)
    embed.add_field(name='🔊 Âm lượng', value=f'`{int(volume * 100)}%`', inline=True)
    embed.add_field(name='🔊 Bộ lọc', value=f'`{audio_filter}`', inline=True)
    embed.add_field(name='🔁 Lặp lại', value=f'`{REPEAT_LABELS[repeat]}`', inline=True)
    embed.add_field(name='✨ Autoplay', value=f'`{AUTOPLAY_LABELS[autoplay]}`', inline=True)
    embed.set_footer(text=f'Yêu cầu bởi {song.requester.display_name}', icon_url=song.requester.display_avatar.url)
    return embed

# ─── Controller View (Buttons) ─────────────────────────
class ControllerView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(emoji='⏸️', style=discord.ButtonStyle.secondary, custom_id='ctrl_pause')
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message('Bot không ở trong voice!', ephemeral=True)
        self.player.auto_paused = False # Reset auto-pause when manual toggle
        
        import time
        if vc.is_playing():
            vc.pause()
            self.player.pause_time = time.time()
            button.emoji = '▶️'
        elif vc.is_paused():
            self.player.total_paused += time.time() - self.player.pause_time
            vc.resume()
            button.emoji = '⏸️'
        await self._update_np(interaction)

    @discord.ui.button(emoji='⏭️', style=discord.ButtonStyle.primary, custom_id='ctrl_skip')
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            self.player.repeat_mode = REPEAT_OFF if self.player.repeat_mode == REPEAT_ONE else self.player.repeat_mode
            vc.stop()
            await interaction.response.send_message('⏭️ Đã bỏ qua!', ephemeral=True, delete_after=3)
        else:
            await interaction.response.send_message('Không có gì để skip!', ephemeral=True)

    @discord.ui.button(emoji='⏹️', style=discord.ButtonStyle.danger, custom_id='ctrl_stop')
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.queue.clear()
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
        await interaction.response.send_message('⏹️ Đã dừng và xóa hàng đợi!', ephemeral=True, delete_after=3)

    @discord.ui.button(emoji='🔀', style=discord.ButtonStyle.secondary, custom_id='ctrl_shuffle')
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.player.queue) < 2:
            return await interaction.response.send_message('Hàng đợi quá ít để trộn!', ephemeral=True)
        random.shuffle(self.player.queue)
        await interaction.response.send_message('🔀 Đã trộn hàng đợi!', ephemeral=True, delete_after=3)

    @discord.ui.button(emoji='🔁', style=discord.ButtonStyle.secondary, custom_id='ctrl_repeat')
    async def repeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.repeat_mode = (self.player.repeat_mode + 1) % 3
        await self._update_np(interaction)

    @discord.ui.button(emoji='✨', style=discord.ButtonStyle.secondary, custom_id='ctrl_autoplay')
    async def autoplay(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.autoplay = not self.player.autoplay
        await self._update_np(interaction)

    @discord.ui.button(emoji='🔉', style=discord.ButtonStyle.secondary, custom_id='ctrl_voldown')
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.volume = max(0.0, self.player.volume - 0.1)
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = self.player.volume
        await self._update_np(interaction)

    @discord.ui.button(emoji='🔊', style=discord.ButtonStyle.secondary, custom_id='ctrl_volup')
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.volume = min(2.0, self.player.volume + 0.1)
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = self.player.volume
        await self._update_np(interaction)

    async def _update_np(self, interaction):
        if not self.player.current:
            return await interaction.response.defer()
        vc = interaction.guild.voice_client
        paused = vc.is_paused() if vc else False
        embed = build_np_embed(
            self.player.current, 
            paused=paused, 
            repeat=self.player.repeat_mode, 
            audio_filter=self.player.filter_name, 
            autoplay=self.player.autoplay, 
            volume=self.player.volume,
            current_time=self.player.get_current_time()
        )
        await interaction.response.edit_message(embed=embed, view=self)

# ─── Search Select View ────────────────────────────────
class SearchSelect(discord.ui.Select):
    def __init__(self, results, requester):
        self.results = results
        self.requester = requester
        options = []
        for i, r in enumerate(results):
            dur = int(r.get('duration') or 0)
            dur_str = f'{dur // 60}:{dur % 60:02d}' if dur else 'Live'
            uploader = r.get('uploader') or r.get('channel') or 'Unknown'
            options.append(discord.SelectOption(
                label=r.get('title', 'Unknown')[:100],
                description=f'{uploader} • {dur_str}'[:100],
                value=str(i),
            ))
        super().__init__(placeholder='🔍 Chọn bài hát...', options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        chosen_raw_data = self.results[idx]
        cog = interaction.client.get_cog('Music')
        if not cog:
            return
        
        player = cog.get_player(interaction)
        await interaction.response.edit_message(content=f'⏳ Đang thêm: **{chosen_raw_data.get("title", "Unknown")}**...', view=None)
        
        # Gửi thẳng raw data vào from_url để không phải fetch lại
        song = await SongInfo.from_url(chosen_raw_data, requester=self.requester, loop=interaction.client.loop)
        player.queue.append(song)
        # Chỉ kick-start loop nếu bot đang rảnh
        vc = interaction.guild.voice_client
        if vc and not (vc.is_playing() or vc.is_paused()):
            player.next.set()
        
        await interaction.edit_original_response(content=f'✅ Đã thêm: **{song.title}** `[{song.duration_str}]`')

class SearchView(discord.ui.View):
    def __init__(self, results, requester):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(results, requester))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ─── Music Player (per guild) ──────────────────────────
class MusicPlayer:
    def __init__(self, bot, guild, channel):
        self.bot = bot
        self.guild = guild
        self.channel = channel
        self.queue: deque[SongInfo] = deque()
        self.history: deque[SongInfo] = deque(maxlen=10)
        self.next = asyncio.Event()
        self.current: SongInfo | None = None
        self.np_message: discord.Message | None = None
        self.repeat_mode = REPEAT_OFF
        self.autoplay = False
        self.auto_paused = False
        self.idle_task: asyncio.Task | None = None
        self.filter_name = 'Normal'
        self.volume = 0.5
        
        # Time tracking
        self.start_time = 0
        self.pause_time = 0
        self.total_paused = 0
        self.seek_offset = 0
        
        self._ff_opts = FFMPEG_BASE
        self._task = bot.loop.create_task(self._player_loop())

    def get_current_time(self):
        if not self.start_time: return 0
        vc = self.guild.voice_client
        if vc and vc.is_paused():
            return self.pause_time - self.start_time - self.total_paused + self.seek_offset
        import time
        return time.time() - self.start_time - self.total_paused + self.seek_offset

    def get_ff_opts(self):
        return self._ff_opts

    async def fetch_related(self, song: SongInfo):
        """Tìm bài hát liên quan dựa trên SoundCloud Station (giống mục Related tracks)"""
        try:
            # Lấy ID bài hát hiện tại từ metadata
            song_id = song._data.get('id')
            if not song_id:
                return await self.fetch_related_fallback(song)
            
            station_url = f"https://soundcloud.com/discover/sets/track-stations:{song_id}"
            
            # Sử dụng ytdl với extract_flat để lấy danh sách cực nhanh
            loop = self.bot.loop or asyncio.get_event_loop()
            
            # Cấu hình extract_flat tạm thời
            flat_opts = {**YTDL_OPTS, 'extract_flat': True}
            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(station_url, download=False))
                
            if data and 'entries' in data:
                # Lọc bỏ các bài trong history hoặc queue để tránh loop
                played_urls = [s.url for s in self.history]
                queue_urls = [s.url for s in self.queue]
                if self.current:
                    queue_urls.append(self.current.url)

                for entry in data['entries']:
                    entry_url = entry.get('url')
                    if not entry_url:
                        continue
                    
                    # Bỏ qua bài hiện tại và bài vừa phát
                    if entry_url in played_urls or entry_url in queue_urls:
                        continue
                        
                    # Fetch full metadata cho bài liên quan được chọn
                    return await SongInfo.from_url(entry_url, requester=self.bot.user, loop=self.bot.loop)
                        
        except Exception as e:
            print(f'[DEBUG] Fetch related station error: {e}')
            
        return await self.fetch_related_fallback(song)

    async def fetch_related_fallback(self, song: SongInfo):
        """Dùng tìm kiếm từ khóa làm phương án dự phòng"""
        query = f"{song.title} {song.uploader} related"
        try:
            results = await SongInfo.search(query, loop=self.bot.loop)
            played_urls = [s.url for s in self.history]
            queue_urls = [s.url for s in self.queue]
            if self.current:
                queue_urls.append(self.current.url)

            for r in results:
                url = r.get('webpage_url') or r.get('url')
                if url not in played_urls and url not in queue_urls:
                    return await SongInfo.from_url(r, requester=self.bot.user, loop=self.bot.loop)
        except Exception as e:
            print(f'[DEBUG] Fetch related fallback error: {e}')
        return None

    async def _player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()

            if self.repeat_mode == REPEAT_ONE and self.current:
                song = self.current
            elif self.queue:
                song = self.queue.popleft()
            elif self.autoplay and self.current:
                # Autoplay logic: fetch related song
                try:
                    msg = await self.channel.send("✨ **Autoplay:** Đang tìm bài hát liên quan...")
                    song = await self.fetch_related(self.current)
                    if song:
                        await msg.edit(content=f"✨ **Autoplay:** Tiếp theo là **{song.title}**")
                    else:
                        await msg.edit(content="✨ **Autoplay:** Không tìm thấy bài liên quan nào.")
                        # Nếu không tìm thấy thì đợi 300s như bình thường
                        await self.next.wait()
                        continue
                except Exception as e:
                    print(f'[ERROR] Autoplay loop: {e}')
                    await self.next.wait()
                    continue
            else:
                try:
                    async with asyncio.timeout(300):
                        await self.next.wait()
                        continue
                except asyncio.TimeoutError:
                    await self._cleanup()
                    return

            self.current = song
            source = discord.PCMVolumeTransformer(song.make_source(self.get_ff_opts(), seek_time=self.seek_offset), volume=self.volume)
            vc = self.guild.voice_client
            if not vc:
                await self._cleanup()
                return

            import time
            self.start_time = time.time()
            self.total_paused = 0
            # Giữ nguyên seek_offset nếu đang seek, nếu không reset về 0
            # Lưu ý: seek command sẽ stop vc và trigger loop lại, chúng ta sẽ xử lý seek_offset ở command
            
            vc.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.next.set))

            # Delete old NP message
            if self.np_message:
                try:
                    await self.np_message.delete()
                except discord.HTTPException:
                    pass

            embed = build_np_embed(song, repeat=self.repeat_mode, audio_filter=self.filter_name, autoplay=self.autoplay, volume=self.volume, current_time=self.seek_offset)
            view = ControllerView(self)
            self.np_message = await self.channel.send(embed=embed, view=view)

            await self.next.wait()

            # Thêm vào history trước khi sang bài mới
            if self.current:
                self.history.append(self.current)

            # Handle repeat_all: put song back at end
            if self.repeat_mode == REPEAT_ALL:
                self.queue.append(song)
            
            self.seek_offset = 0 # Reset seek offset for next song
            source.cleanup()

    async def _cleanup(self):
        try:
            await self.guild.voice_client.disconnect()
        except Exception:
            pass

    def destroy(self):
        self._task.cancel()

# ─── Music Cog ──────────────────────────────────────────
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}
        self.playlist_file = 'playlists.json'
        if not os.path.exists(self.playlist_file):
            with open(self.playlist_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    async def is_dj(self, ctx):
        """Kiểm tra quyền DJ: Owner, Admin, hoặc có role 'DJ'"""
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
            print(f'[ERROR] Command {ctx.command}: {error.original}')
            traceback.print_exception(type(error.original), error.original, error.original.__traceback__)
            await ctx.send(f'❌ Lỗi: `{error.original}`')
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'❌ Thiếu tham số: `{error.param.name}`')

    def _get_artist_title(self, song):
        """Tách Artist và Title từ thông tin bài hát"""
        title = song.title
        artist = song.uploader
        
        # Nếu tiêu đề có dạng "Artist - Title" hoặc "Artist: Title"
        for sep in [' - ', ' – ', ' : ']:
            if sep in title:
                parts = title.split(sep, 1)
                artist, title = parts[0], parts[1]
                break
            
        # Clean các tag thừa
        clean_regex = r'\(.*?\)|\[.*?\]|official|video|lyric|audio|full hd|mv|music video'
        title = re.sub(clean_regex, '', title, flags=re.IGNORECASE).strip()
        artist = re.sub(clean_regex, '', artist, flags=re.IGNORECASE).strip()
        
        return artist, title

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Tự động pause/resume và disconnect khi phòng trống."""
        if member.bot:
            return

        vc = member.guild.voice_client
        if not vc or not vc.channel:
            return

        # Chỉ xử lý nếu có thay đổi liên quan đến channel của bot
        if (before.channel and before.channel.id == vc.channel.id) or (after.channel and after.channel.id == vc.channel.id):
            player = self.players.get(member.guild.id)
            if not player:
                return

            humans = [m for m in vc.channel.members if not m.bot]

            import time
            if not humans:
                # Không còn người: Pause và bắt đầu đếm ngược 15p
                if vc.is_playing() and not player.auto_paused:
                    vc.pause()
                    player.pause_time = time.time()
                    player.auto_paused = True
                    await player.channel.send("⏸️ **Phòng trống:** Tạm dừng nhạc cho đến khi bồ quay lại.", delete_after=15)

                if not player.idle_task or player.idle_task.done():
                    player.idle_task = self.bot.loop.create_task(self._idle_disconnect(member.guild))
            else:
                # Có người: Huỷ đếm ngược và Resume nếu đang auto-pause
                if player.idle_task:
                    player.idle_task.cancel()
                    player.idle_task = None

                if player.auto_paused and vc.is_paused():
                    player.total_paused += time.time() - player.pause_time
                    vc.resume()
                    player.auto_paused = False
                    await player.channel.send("▶️ **Đã có người vào:** Tiếp tục quẩy thôi!", delete_after=10)

    async def _idle_disconnect(self, guild):
        """Task chờ 15 phút rồi thoát."""
        try:
            await asyncio.sleep(900) # 15 phút
            if guild.id in self.players:
                player = self.players[guild.id]
                await player.channel.send("🔇 **Tự động thoát:** Phòng trống quá 15 phút, Shimizu đi ngủ đây!")
            await self.cleanup(guild)
        except asyncio.CancelledError:
            pass

    # ── Commands ────────────────────────────────────────
    @commands.command(name='play', aliases=['p'])
    async def play_(self, ctx, *, query: str):
        """Phát nhạc (link hoặc từ khóa). Nếu là từ khóa sẽ hiện menu chọn bài."""
        if not await self._ensure_voice(ctx):
            return

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
                print(f'[ERROR] play URL: {e}')
                traceback.print_exc()
                await ctx.send(f'❌ Lỗi khi tải bài hát: `{e}`')
        else:
            try:
                async with ctx.typing():
                    print(f'[DEBUG] Searching for: {query}')
                    results = await SongInfo.search(query, loop=self.bot.loop)
                    print(f'[DEBUG] Found {len(results)} results')
                if not results:
                    return await ctx.send('❌ Không tìm thấy kết quả nào!')
                view = SearchView(results, ctx.author)
                await ctx.send('🔍 **Kết quả tìm kiếm:**', view=view, delete_after=35)
            except Exception as e:
                print(f'[ERROR] play search: {e}')
                traceback.print_exc()
                await ctx.send(f'❌ Lỗi khi tìm kiếm: `{e}`')

    @commands.command(name='playnow', aliases=['pn'])
    async def play_now(self, ctx, *, query: str):
        """Phát ngay lập tức, nhảy cóc hàng đợi."""
        if not await self._ensure_voice(ctx):
            return
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
        """Vào phòng voice."""
        await self._ensure_voice(ctx)

    @commands.command(name='skip', aliases=['s'])
    async def skip(self, ctx):
        """Bỏ qua bài hiện tại."""
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
        """Nhảy đến một thời điểm trong bài (ví dụ: 1:30 hoặc 90)."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để seek!')
            
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('❌ Không có gì đang phát!')
            
        # Parse time string
        try:
            if ':' in time_str:
                parts = list(map(int, time_str.split(':')))
                if len(parts) == 2: # mm:ss
                    seconds = parts[0] * 60 + parts[1]
                elif len(parts) == 3: # hh:mm:ss
                    seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
                else: raise ValueError
            else:
                seconds = int(time_str)
        except ValueError:
            return await ctx.send('❌ Định dạng thời gian không hợp lệ! (Dùng: `mm:ss` hoặc số giây)')
            
        if seconds < 0 or seconds > player.current.duration:
            return await ctx.send(f'❌ Thời gian phải từ 0 đến {player.current.duration_str}!')
            
        player.seek_offset = seconds
        vc = ctx.voice_client
        if vc:
            # Trick: stop then start again with offset
            # We need to preserve current song for the loop
            player.repeat_mode = REPEAT_ONE
            vc.stop()
            # Loop will start again, we'll reset repeat_mode after it starts
            await asyncio.sleep(1)
            player.repeat_mode = REPEAT_OFF
            
        await ctx.send(f'⏩ Đã nhảy đến `{time_str}`')

    @commands.command(name='pause')
    async def pause(self, ctx):
        """Tạm dừng nhạc."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để pause!')
        vc = ctx.voice_client
        if vc and vc.is_playing():
            player = self.get_player(ctx)
            player.auto_paused = False
            import time
            player.pause_time = time.time()
            vc.pause()
            await ctx.send('⏸️ Đã tạm dừng.', delete_after=5)

    @commands.command(name='resume')
    async def resume(self, ctx):
        """Phát tiếp."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để resume!')
        vc = ctx.voice_client
        if vc and vc.is_paused():
            player = self.get_player(ctx)
            player.auto_paused = False
            import time
            player.total_paused += time.time() - player.pause_time
            vc.resume()
            await ctx.send('▶️ Tiếp tục phát.', delete_after=5)

    @commands.command(name='queue', aliases=['q'])
    async def queue_info(self, ctx, page: int = 1):
        """Xem hàng đợi (có phân trang)."""
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
        end = start + items_per_page
        queue_list = list(player.queue)
        chunk = queue_list[start:end]

        if chunk:
            desc = '\n'.join(f'`{start+i+1}.` **{s.title}** `[{s.duration_str}]`' for i, s in enumerate(chunk))
            embed.add_field(name=f'Sắp tới ({len(player.queue)} bài)', value=desc, inline=False)

        embed.set_footer(text=f'Trang {page}/{pages} • !queue <số trang> • Lặp: {REPEAT_LABELS[player.repeat_mode]}')
        await ctx.send(embed=embed)

    @commands.command(name='np', aliases=['now'])
    async def now_playing(self, ctx):
        """Xem bài đang phát."""
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('❌ Không có bài nào đang phát.')
        vc = ctx.voice_client
        paused = vc.is_paused() if vc else False
        embed = build_np_embed(
            player.current, 
            paused=paused, 
            repeat=player.repeat_mode, 
            audio_filter=player.filter_name, 
            autoplay=player.autoplay,
            volume=player.volume,
            current_time=player.get_current_time()
        )
        view = ControllerView(player)
        await ctx.send(embed=embed, view=view)

    @commands.command(name='remove', aliases=['rm'])
    async def remove(self, ctx, index: int):
        """Xóa bài theo số thứ tự trong hàng đợi."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để remove bài!')
        player = self.get_player(ctx)
        if index < 1 or index > len(player.queue):
            return await ctx.send(f'❌ Số thứ tự phải từ 1 đến {len(player.queue)}!')
        removed = player.queue[index - 1]
        del player.queue[index - 1]
        await ctx.send(f'🗑️ Đã xóa: **{removed.title}**', delete_after=5)

    @commands.command(name='clear')
    async def clear_queue(self, ctx):
        """Xóa toàn bộ hàng đợi."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để clear queue!')
        player = self.get_player(ctx)
        player.queue.clear()
        await ctx.send('🗑️ Đã xóa toàn bộ hàng đợi!', delete_after=5)

    @commands.command(name='move')
    async def move(self, ctx, pos_from: int, pos_to: int):
        """Di chuyển vị trí bài hát trong hàng đợi."""
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
        """Hoán đổi vị trí hai bài hát trong hàng đợi."""
        player = self.get_player(ctx)
        q_len = len(player.queue)
        if pos1 < 1 or pos1 > q_len or pos2 < 1 or pos2 > q_len:
            return await ctx.send(f'❌ Vị trí phải từ 1 đến {q_len}!')
            
        player.queue[pos1 - 1], player.queue[pos2 - 1] = player.queue[pos2 - 1], player.queue[pos1 - 1]
        await ctx.send(f'🔄 Đã hoán đổi bài hát ở vị trí #{pos1} và #{pos2}')

    @commands.command(name='history')
    async def history(self, ctx):
        """Xem các bài hát vừa phát gần đây."""
        player = self.get_player(ctx)
        if not player.history:
            return await ctx.send('📜 Lịch sử trống!')
            
        desc = '\n'.join(f'`{i+1}.` **{s.title}**' for i, s in enumerate(reversed(player.history)))
        embed = discord.Embed(title='📜 Lịch sử phát nhạc', description=desc, color=discord.Color.from_str('#FF6B9D'))
        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def shuffle(self, ctx):
        """Trộn ngẫu nhiên hàng đợi."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để shuffle!')
        player = self.get_player(ctx)
        if len(player.queue) < 2:
            return await ctx.send('❌ Cần ít nhất 2 bài trong hàng đợi!')
        random.shuffle(player.queue)
        await ctx.send('🔀 Đã trộn hàng đợi!', delete_after=5)

    @commands.command(name='repeat', aliases=['loop'])
    async def repeat(self, ctx, mode: str = None):
        """Chế độ lặp: off / one / all"""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để chỉnh loop!')
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
            return await ctx.send('❌ Dùng: `!repeat off/one/all`')
        await ctx.send(f'🔁 Chế độ lặp: **{REPEAT_LABELS[player.repeat_mode]}**', delete_after=5)

    @commands.command(name='filter', aliases=['fx'])
    async def audio_filter(self, ctx, name: str = None):
        """Bộ lọc âm thanh: normal / bass / nightcore"""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để dùng bộ lọc!')
        player = self.get_player(ctx)
        filters = {'normal': (FFMPEG_BASE, 'Normal'), 'bass': (FFMPEG_BASS, '🔊 Bass Boost'), 'nightcore': (FFMPEG_NIGHTCORE, '🌙 Nightcore')}
        if name is None or name.lower() not in filters:
            return await ctx.send('🔊 **Bộ lọc có sẵn:** `normal`, `bass`, `nightcore`\nDùng: `!filter <tên>`')
        player._ff_opts, player.filter_name = filters[name.lower()]
        await ctx.send(f'🔊 Bộ lọc đã chuyển sang: **{player.filter_name}**\n_Áp dụng từ bài tiếp theo._', delete_after=8)

    @commands.command(name='autoplay', aliases=['ap'])
    async def autoplay(self, ctx):
        """Bật/Tắt tự động phát bài hát liên quan."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để dùng autoplay!')
        player = self.get_player(ctx)
        player.autoplay = not player.autoplay
        status = 'BẬT' if player.autoplay else 'TẮT'
        await ctx.send(f'✨ Chế độ Autoplay đã được **{status}**!', delete_after=10)

    @commands.command(name='volume', aliases=['vol', 'v'])
    async def volume(self, ctx, vol: int = None):
        """Chỉnh âm lượng (0-200)."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để chỉnh âm lượng!')
        player = self.get_player(ctx)
        if vol is None:
            return await ctx.send(f'🔊 Âm lượng hiện tại: **{int(player.volume * 100)}%**')
        
        if vol < 0 or vol > 200:
            return await ctx.send('❌ Âm lượng phải từ 0 đến 200!')
        
        player.volume = vol / 100
        vc = ctx.voice_client
        if vc and vc.source:
            vc.source.volume = player.volume
        
        await ctx.send(f'🔊 Đã chỉnh âm lượng thành: **{vol}%**', delete_after=5)

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
                artist, title = query.split(' - ', 1)
            else:
                artist, title = '', query

        async with ctx.typing():
            # Thử với artist + title trước, nếu không được thì thử title đơn thuần
            async def fetch(a, t):
                url = f"https://api.lyrics.ovh/v1/{a}/{t}"
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=10) as resp:
                            if resp.status == 200:
                                return (await resp.json()).get('lyrics')
                except: pass
                return None

            lyrics = await fetch(artist, title)
            if not lyrics and artist: # Fallback: đảo ngược hoặc bỏ artist
                lyrics = await fetch('', f"{artist} {title}")

        if not lyrics:
            search_name = f"{artist} - {title}" if artist else title
            return await ctx.send(f'❌ Không tìm thấy lời cho: **{search_name}**')

        # Cắt bớt nếu quá dài (Discord limit 4096)
        if len(lyrics) > 4000:
            lyrics = lyrics[:4000] + "\n\n...(còn tiếp)..."

        embed = discord.Embed(
            title=f'📜 Lời bài hát: {title}',
            description=lyrics,
            color=discord.Color.from_str('#FF6B9D')
        )
        if artist:
            embed.set_author(name=artist)
        embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name='stop', aliases=['leave', 'dc'])
    async def stop(self, ctx):
        """Dừng phát và thoát phòng voice."""
        if not await self.is_dj(ctx):
            return await ctx.send('❌ Bồ cần role `DJ` hoặc quyền `Admin` để stop bot!')
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
        if player.current:
            songs.append(player.current._data)
        for s in player.queue:
            songs.append(s._data)
            
        with open(self.playlist_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        data[name] = {
            'creator': ctx.author.id,
            'songs': songs
        }
        
        with open(self.playlist_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        await ctx.send(f'💾 Đã lưu playlist **{name}** với {len(songs)} bài hát!')

    @commands.command(name='load_playlist', aliases=['lp'])
    async def load_playlist(self, ctx, name: str):
        """Tải một playlist đã lưu vào hàng đợi."""
        if not await self._ensure_voice(ctx):
            return
            
        with open(self.playlist_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if name not in data:
            return await ctx.send(f'❌ Không tìm thấy playlist tên `{name}`!')
            
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
        with open(self.playlist_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not data:
            return await ctx.send('📂 Chưa có playlist nào được lưu!')
            
        desc = '\n'.join(f'• **{name}** ({len(info["songs"])} bài)' for name, info in data.items())
        embed = discord.Embed(title='📂 Danh sách Playlists', description=desc, color=discord.Color.from_str('#FF6B9D'))
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))
