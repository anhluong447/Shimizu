import os
import asyncio
import discord
import yt_dlp
from src.core.config import MUSIC_CACHE_DIR, FFMPEG_EXE
from src.utils.formatters import format_duration
from src.core.logger import log


class YTSongInfo:
    """Represents a YouTube song with download tracking."""

    def __init__(self, data, requester):
        self.video_id = data.get('id', '')
        self.title = data.get('title', 'Unknown')
        self.url = data.get('webpage_url') or data.get('url', '')
        self.thumbnail = data.get('thumbnail') or ''
        self.duration = int(data.get('duration') or 0)
        self.uploader = data.get('uploader') or data.get('channel') or 'Unknown'
        self.requester = requester
        self._data = data
        self.local_path = None

    @property
    def duration_str(self):
        return format_duration(self.duration)

    def make_source(self, filter_name='Normal', seek_time=0):
        """Create FFmpeg audio source from local file."""
        filter_opts = {
            'Normal': '-vn',
            'Bass Boost': '-vn -af "bass=g=10,equalizer=f=40:width_type=h:width=50:g=5"',
            'Nightcore': '-vn -af "asetrate=44100*1.25,aresample=44100,atempo=1.0"',
        }
        options = filter_opts.get(filter_name, '-vn')
        before = f'-ss {seek_time}' if seek_time > 0 else ''
        return discord.FFmpegPCMAudio(
            self.local_path, executable=FFMPEG_EXE,
            options=options, before_options=before
        )

    @classmethod
    async def search(cls, query, *, loop=None, limit=5):
        """Search YouTube and return raw result entries."""
        loop = loop or asyncio.get_event_loop()
        opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': f'ytsearch{limit}',
            'extract_flat': 'in_playlist',
        }

        def _do_search():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(f'ytsearch{limit}:{query}', download=False)

        try:
            data = await loop.run_in_executor(None, _do_search)
        except Exception as e:
            log.error(f'[YT] Search error: {e}')
            return []

        if not data or 'entries' not in data:
            return []
        return [e for e in data['entries'] if e]

    @classmethod
    async def from_url(cls, url, *, requester, loop=None):
        """Extract full info from a YouTube URL."""
        loop = loop or asyncio.get_event_loop()
        opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
        }

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        data = await loop.run_in_executor(None, _extract)
        if 'entries' in data:
            data = data['entries'][0]
        return cls(data, requester)


class YTDownloader:
    """Manages downloading YouTube audio as MP3 files to disk."""

    def __init__(self):
        self.cache_dir = MUSIC_CACHE_DIR
        self._locks = {}  # video_id -> asyncio.Lock

    def get_path(self, video_id):
        return os.path.join(self.cache_dir, f"{video_id}.mp3")

    def is_cached(self, video_id):
        return os.path.exists(self.get_path(video_id))

    async def download(self, song, loop=None):
        """Download song audio as MP3. Returns file path."""
        vid = song.video_id
        path = self.get_path(vid)

        if os.path.exists(path):
            song.local_path = path
            return path

        if vid not in self._locks:
            self._locks[vid] = asyncio.Lock()

        async with self._locks[vid]:
            # Double-check after acquiring lock
            if os.path.exists(path):
                song.local_path = path
                return path

            loop = loop or asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, self._dl_sync, vid, song.url)
                song.local_path = path
                log.info(f"[YT-DL] ✅ Downloaded: {song.title} ({vid})")
                return path
            except Exception as e:
                log.error(f"[YT-DL] ❌ Failed {vid}: {e}")
                raise
            finally:
                self._locks.pop(vid, None)

    def _dl_sync(self, video_id, url):
        ffmpeg_dir = os.path.dirname(FFMPEG_EXE) if FFMPEG_EXE != 'ffmpeg' else None
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.cache_dir, f'{video_id}.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }
        if ffmpeg_dir:
            opts['ffmpeg_location'] = ffmpeg_dir

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    def cleanup(self, video_id):
        path = self.get_path(video_id)
        try:
            if os.path.exists(path):
                os.remove(path)
                log.info(f"[YT-DL] 🗑️ Cleaned: {video_id}.mp3")
        except Exception as e:
            log.error(f"[YT-DL] Cleanup error {video_id}: {e}")

    def cleanup_all(self):
        """Wipe entire cache directory."""
        try:
            count = 0
            for f in os.listdir(self.cache_dir):
                if f.endswith('.mp3'):
                    os.remove(os.path.join(self.cache_dir, f))
                    count += 1
            if count:
                log.info(f"[YT-DL] 🗑️ Cleaned {count} cached files")
        except Exception as e:
            log.error(f"[YT-DL] Cleanup all error: {e}")
