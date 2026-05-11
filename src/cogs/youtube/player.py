import asyncio
import discord
import time
from collections import deque
from .downloader import YTSongInfo, YTDownloader
from .views import build_yt_np_embed, YTControllerView
from src.core.config import REPEAT_OFF, REPEAT_ONE, REPEAT_ALL
from src.core.logger import log


class YTPlayer:
    """YouTube music player — downloads MP3s to disk and plays locally."""

    def __init__(self, bot, guild, channel):
        self.bot = bot
        self.guild = guild
        self.channel = channel
        self.downloader = YTDownloader()

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

        # Time tracking
        self.start_time = 0
        self.pause_time = 0
        self.total_paused = 0
        self.seek_offset = 0

        self._task = bot.loop.create_task(self._player_loop())
        self._buffer_task = bot.loop.create_task(self._buffer_loop())

    def get_current_time(self):
        if not self.start_time:
            return 0
        vc = self.guild.voice_client
        if vc and vc.is_paused():
            return self.pause_time - self.start_time - self.total_paused + self.seek_offset
        return time.time() - self.start_time - self.total_paused + self.seek_offset

    # ── Buffer: pre-download next 2 songs ──────────────
    async def _buffer_loop(self):
        """Background task that pre-downloads the next 2 songs in queue."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                for song in list(self.queue)[:2]:
                    if not song.local_path and not self.downloader.is_cached(song.video_id):
                        try:
                            await self.downloader.download(song, loop=self.bot.loop)
                        except Exception as e:
                            log.error(f"[YT-Buffer] Download failed: {e}")
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                return
            except Exception as e:
                log.error(f"[YT-Buffer] Error: {e}")
                await asyncio.sleep(5)

    # ── Autoplay: find related song ────────────────────
    async def _fetch_related(self):
        """Search YouTube for a related song based on current track."""
        if not self.current:
            return None
        query = f"{self.current.title} {self.current.uploader}"
        try:
            results = await YTSongInfo.search(query, loop=self.bot.loop)
            played_ids = {s.video_id for s in self.history}
            queue_ids = {s.video_id for s in self.queue}
            if self.current:
                played_ids.add(self.current.video_id)

            for r in results:
                vid = r.get('id', '')
                if vid and vid not in played_ids and vid not in queue_ids:
                    song = YTSongInfo(r, self.bot.user)
                    return song
        except Exception as e:
            log.error(f"[YT-Autoplay] Error: {e}")
        return None

    # ── Main player loop ───────────────────────────────
    async def _player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()

            if self.repeat_mode == REPEAT_ONE and self.current:
                song = self.current
            elif self.queue:
                song = self.queue.popleft()
            elif self.autoplay and self.current:
                try:
                    msg = await self.channel.send("✨ **Autoplay:** Đang tìm bài liên quan trên YouTube...")
                    song = await self._fetch_related()
                    if song:
                        await msg.edit(content=f"✨ **Autoplay:** Tiếp theo là **{song.title}**")
                    else:
                        await msg.edit(content="✨ **Autoplay:** Không tìm thấy bài liên quan.")
                        await self.next.wait()
                        continue
                except Exception as e:
                    log.error(f"[YT-Autoplay] Loop error: {e}")
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

            # ── Ensure song is downloaded ──
            if not song.local_path or not self.downloader.is_cached(song.video_id):
                dl_msg = await self.channel.send(f"⏳ **Đang tải:** {song.title}...", delete_after=15)
                try:
                    await self.downloader.download(song, loop=self.bot.loop)
                except Exception as e:
                    await self.channel.send(f"❌ Không tải được: **{song.title}** — `{e}`", delete_after=10)
                    continue

            self.current = song

            # ── Play from local file ──
            source = discord.PCMVolumeTransformer(
                song.make_source(self.filter_name, seek_time=self.seek_offset),
                volume=self.volume
            )
            vc = self.guild.voice_client
            if not vc:
                await self._cleanup()
                return

            self.start_time = time.time()
            self.total_paused = 0
            vc.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.next.set))

            # ── Now Playing embed ──
            if self.np_message:
                try:
                    await self.np_message.delete()
                except discord.HTTPException:
                    pass

            embed = build_yt_np_embed(
                song, repeat=self.repeat_mode, audio_filter=self.filter_name,
                autoplay=self.autoplay, volume=self.volume, current_time=self.seek_offset
            )
            view = YTControllerView(self)
            self.np_message = await self.channel.send(embed=embed, view=view)

            await self.next.wait()

            # ── Post-playback cleanup ──
            old_song = self.current
            if old_song:
                self.history.append(old_song)

            if self.repeat_mode == REPEAT_ALL:
                # Re-queue — file will be re-downloaded by buffer if needed
                old_song.local_path = None
                self.queue.append(old_song)
            elif self.repeat_mode != REPEAT_ONE:
                # Delete the file — song is done
                self.downloader.cleanup(old_song.video_id)

            self.seek_offset = 0
            source.cleanup()

    async def _cleanup(self):
        if self._buffer_task:
            self._buffer_task.cancel()
        if self.idle_task:
            self.idle_task.cancel()
        # Clean all cached files on disconnect
        self.downloader.cleanup_all()
        try:
            await self.guild.voice_client.disconnect()
        except Exception:
            pass

    def destroy(self):
        self._task.cancel()
        if self._buffer_task:
            self._buffer_task.cancel()
