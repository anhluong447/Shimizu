import asyncio
import discord
import time
from collections import deque
from .models import SongInfo
from .views import build_np_embed, ControllerView
from src.core.config import REPEAT_OFF, REPEAT_ONE, REPEAT_ALL, FFMPEG_OPTIONS
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
        
        self.start_time = 0
        self.pause_time = 0
        self.total_paused = 0
        self.seek_offset = 0
        
        self._task = bot.loop.create_task(self._player_loop())

    def get_current_time(self):
        if not self.start_time: return 0
        vc = self.guild.voice_client
        if vc and vc.is_paused():
            return self.pause_time - self.start_time - self.total_paused + self.seek_offset
        return time.time() - self.start_time - self.total_paused + self.seek_offset

    async def _player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()

            if self.repeat_mode == REPEAT_ONE and self.current:
                song = self.current
            elif self.queue:
                song = self.queue.popleft()
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
            if not vc: return

            self.start_time = time.time()
            self.total_paused = 0
            
            vc.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.next.set))

            if self.np_message:
                try: await self.np_message.delete()
                except: pass

            embed = build_np_embed(song, repeat=self.repeat_mode, audio_filter=self.filter_name, autoplay=self.autoplay, volume=self.volume, current_time=self.seek_offset)
            self.np_message = await self.channel.send(embed=embed, view=ControllerView(self))

            await self.next.wait()
            self.history.append(song)
            if self.repeat_mode == REPEAT_ALL:
                self.queue.append(song)
            self.seek_offset = 0

    async def _cleanup(self):
        try: await self.guild.voice_client.disconnect()
        except: pass

    def destroy(self):
        self._task.cancel()
