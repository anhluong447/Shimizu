import discord
import yt_dlp
import asyncio
import re
from src.core.config import YTDL_OPTS, FFMPEG_EXE, FFMPEG_OPTIONS
from src.utils.formatters import format_duration
from src.core.logger import log

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)
ytdl_search = yt_dlp.YoutubeDL({**YTDL_OPTS, 'default_search': 'scsearch5', 'noplaylist': True})


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
        loop = loop or asyncio.get_event_loop()

        async def perform_search(q, limit=5):
            search_query = f'scsearch{limit}:{q}'
            try:
                return await loop.run_in_executor(None, lambda: ytdl_search.extract_info(search_query, download=False))
            except Exception as e:
                log.error(f'SoundCloud Search error for "{q}": {e}')
                return None

        # Step 1: Direct search
        data = await perform_search(query)

        # Step 2: Query Refinement
        if not data or 'entries' not in data or not data['entries']:
            log.debug(f'No results for "{query}", refining query...')
            clean_query = re.sub(r'\(.*?\)|\[.*?\]|official|video|lyric|audio|mv|music video|full hd|[^a-zA-Z0-9\sàáạảãâầấnậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', ' ', query, flags=re.IGNORECASE)
            clean_query = ' '.join(clean_query.split())
            if clean_query and clean_query.lower() != query.lower():
                data = await perform_search(clean_query)

        # Step 3: Broad Match
        if (not data or 'entries' not in data or not data['entries']) and ' - ' in query:
            parts = query.split(' - ')
            log.debug(f'Still no results, trying broad match with "{parts[-1]}"...')
            data = await perform_search(parts[-1])

        if not data or 'entries' not in data:
            return []

        return data['entries']
