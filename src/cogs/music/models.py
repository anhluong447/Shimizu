import discord
import yt_dlp
import asyncio
from src.core.config import YTDL_OPTS, FFMPEG_EXE, FFMPEG_OPTIONS
from src.utils.formatters import format_duration

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

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
        return format_duration(self.duration)

    def make_source(self, ff_opts=None, seek_time=0):
        opts = (ff_opts or FFMPEG_OPTIONS['Normal']).copy()
        if seek_time > 0:
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
        # We'll use a simplified search or move the complex search logic here
        # For brevity in refactor, keeping the logic similar
        loop = loop or asyncio.get_event_loop()
        search_opts = {**YTDL_OPTS, 'default_search': 'scsearch5'}
        
        async def perform_search(q):
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                return await loop.run_in_executor(None, lambda: ydl.extract_info(f"scsearch5:{q}", download=False))

        data = await perform_search(query)
        if not data or 'entries' not in data:
            return []
        return data['entries']
