import asyncio
import discord
import time
import yt_dlp
from collections import deque
from .models import SongInfo
from .views import build_np_embed, ControllerView
from src.core.config import REPEAT_OFF, REPEAT_ONE, REPEAT_ALL, FFMPEG_OPTIONS, YTDL_OPTS
from src.core.logger import log


class MusicPlayer:
    def __init__(self, bot, guild, channel):
        self.bot = bot
        self.guild = guild
        self.channel = channel
        self.queue = deque()
        self.history = deque(maxlen=10)
        self.next = asyncio.Event()
        self.current = None
        self.np_message = None
        self.repeat_mode = REPEAT_OFF
        self.autoplay = False
        self.auto_paused = False
        self.idle_task = None
        self.filter_name = 'Normal'
        self.volume = 0.5
        self.prefetched_song = None
        self._prefetch_task = None

        # Time tracking
        self.start_time = 0
        self.pause_time = 0
        self.total_paused = 0
        self.seek_offset = 0

        self._task = bot.loop.create_task(self._player_loop())

    def get_current_time(self):
        if not self.start_time:
            return 0
        vc = self.guild.voice_client
        if vc and vc.is_paused():
            return self.pause_time - self.start_time - self.total_paused + self.seek_offset
        return time.time() - self.start_time - self.total_paused + self.seek_offset

    async def fetch_related(self, song):
        """Tìm bài hát liên quan dựa trên SoundCloud Station"""
        try:
            song_id = song._data.get('id')
            if not song_id:
                return await self.fetch_related_fallback(song)

            station_url = f"https://soundcloud.com/discover/sets/track-stations:{song_id}"
            loop = self.bot.loop or asyncio.get_event_loop()

            flat_opts = {**YTDL_OPTS, 'extract_flat': True}
            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(station_url, download=False))

            if data and 'entries' in data:
                # Collect IDs and URLs from history and queue for strict comparison
                played_ids = [str(s._data.get('id')) for s in self.history if s._data.get('id')]
                played_urls = [s.url for s in self.history]
                
                queue_ids = [str(s._data.get('id')) for s in self.queue if s._data.get('id')]
                queue_urls = [s.url for s in self.queue]
                
                if self.current:
                    curr_id = self.current._data.get('id')
                    if curr_id: queue_ids.append(str(curr_id))
                    queue_urls.append(self.current.url)

                all_played_ids = set(played_ids + queue_ids)
                all_played_urls = played_urls + queue_urls

                for entry in data['entries']:
                    entry_url = entry.get('url')
                    entry_id = str(entry.get('id')) if entry.get('id') else None
                    
                    if not entry_url:
                        continue
                        
                    # Skip if ID matches anything in history or queue
                    if entry_id and entry_id in all_played_ids:
                        continue
                        
                    # Skip if URL matches (with basic normalization)
                    normalized_entry = entry_url.replace('api-v2.soundcloud.com/tracks/', 'soundcloud.com/')
                    if any(normalized_entry in url or url in normalized_entry for url in all_played_urls):
                        continue
                        
                    return await SongInfo.from_url(entry_url, requester=self.bot.user, loop=self.bot.loop)

        except Exception as e:
            log.error(f'Fetch related station error: {e}')

        return await self.fetch_related_fallback(song)

    async def fetch_related_fallback(self, song):
        """Dùng tìm kiếm từ khóa làm phương án dự phòng"""
        query = f"{song.title} {song.uploader} related"
        try:
            results = await SongInfo.search(query, loop=self.bot.loop)
            played_ids = [str(s._data.get('id')) for s in self.history if s._data.get('id')]
            played_urls = [s.url for s in self.history]
            queue_ids = [str(s._data.get('id')) for s in self.queue if s._data.get('id')]
            queue_urls = [s.url for s in self.queue]
            
            if self.current:
                curr_id = self.current._data.get('id')
                if curr_id: queue_ids.append(str(curr_id))
                queue_urls.append(self.current.url)

            all_played_ids = set(played_ids + queue_ids)
            all_played_urls = played_urls + queue_urls

            for r in results:
                url = r.get('webpage_url') or r.get('url')
                res_id = str(r.get('id')) if r.get('id') else None
                
                if res_id and res_id in all_played_ids:
                    continue
                    
                if any(url in p_url or p_url in url for p_url in all_played_urls):
                    continue
                    
                return await SongInfo.from_url(r, requester=self.bot.user, loop=self.bot.loop)
        except Exception as e:
            log.error(f'Fetch related fallback error: {e}')
        return None

    async def _run_prefetch(self, delay):
        """Tải trước bài hát khi sắp kết thúc bài hiện tại"""
        try:
            await asyncio.sleep(delay)
            if self.autoplay and not self.queue and not self.prefetched_song:
                # log.info(f"[PREFETCH] Fetching next song for {self.guild.name}")
                self.prefetched_song = await self.fetch_related(self.current)
                if self.prefetched_song:
                    await self.channel.send(f"✨ **Autoplay:** Đã tải sẵn bài tiếp theo: **{self.prefetched_song.title}**", delete_after=10)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Prefetch error: {e}")

    async def _player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()

            if self.repeat_mode == REPEAT_ONE and self.current:
                song = self.current
            elif self.queue:
                song = self.queue.popleft()
                self.prefetched_song = None # Hủy bài tải sẵn nếu có bài trong hàng đợi
            elif self.prefetched_song:
                song = self.prefetched_song
                self.prefetched_song = None
            elif self.autoplay and self.current:
                try:
                    msg = await self.channel.send("✨ **Autoplay:** Đang tìm bài hát liên quan...")
                    song = await self.fetch_related(self.current)
                    if song:
                        await msg.edit(content=f"✨ **Autoplay:** Tiếp theo là **{song.title}**")
                    else:
                        await msg.edit(content="✨ **Autoplay:** Không tìm thấy bài liên quan nào.")
                        await self.next.wait()
                        continue
                except Exception as e:
                    log.error(f'Autoplay loop error: {e}')
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
            source = discord.PCMVolumeTransformer(
                song.make_source(FFMPEG_OPTIONS.get(self.filter_name), seek_time=self.seek_offset),
                volume=self.volume
            )
            vc = self.guild.voice_client
            if not vc:
                await self._cleanup()
                return

            self.start_time = time.time()
            self.total_paused = 0

            vc.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.next.set))

            # Start prefetch task (10s before end)
            if self._prefetch_task:
                self._prefetch_task.cancel()
            
            prefetch_delay = max(0, song.duration - 10)
            self._prefetch_task = self.bot.loop.create_task(self._run_prefetch(prefetch_delay))

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

            # Handle repeat_all
            if self.repeat_mode == REPEAT_ALL:
                self.queue.append(song)

            self.seek_offset = 0
            source.cleanup()

    async def _cleanup(self):
        if self._prefetch_task:
            self._prefetch_task.cancel()
        if self.idle_task:
            self.idle_task.cancel()
            
        try:
            await self.guild.voice_client.disconnect()
        except Exception:
            pass

    def destroy(self):
        self._task.cancel()
