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
        cookies_file = os.path.join(os.path.dirname(MUSIC_CACHE_DIR), 'cookies.txt')
        proxy = os.getenv('YTDL_PROXY')
        
        def _do_search():
            # Thử android client vì nó rất ổn định
            opts = {
                'format': 'bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'default_search': f'ytsearch{limit}',
                'extract_flat': 'in_playlist',
                'extractor_args': {'youtube': {'player_client': ['android']}},
            }
            if os.path.exists(cookies_file):
                opts['cookiefile'] = cookies_file
            if proxy:
                opts['proxy'] = proxy
                
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
        cookies_file = os.path.join(os.path.dirname(MUSIC_CACHE_DIR), 'cookies.txt')
        proxy = os.getenv('YTDL_PROXY')
        
        def _extract():
            # Thử xoay vòng client cho extraction
            for client in ['android', 'web_embedded', 'ios']:
                try:
                    opts = {
                        'format': 'bestaudio/best',
                        'noplaylist': True,
                        'quiet': True,
                        'no_warnings': True,
                        'extractor_args': {'youtube': {'player_client': [client]}},
                    }
                    if os.path.exists(cookies_file):
                        opts['cookiefile'] = cookies_file
                    if proxy:
                        opts['proxy'] = proxy
                        
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(url, download=False)
                except Exception:
                    continue
            raise Exception("YouTube chặn toàn bộ client extraction. Vui lòng kiểm tra lại IP hoặc Cookies.")

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
                await loop.run_in_executor(None, self._dl_sync, vid, song.url, song.title)
                song.local_path = path
                log.info(f"[YT-DL] ✅ Downloaded: {song.title} ({vid})")
                return path
            except Exception as e:
                log.error(f"[YT-DL] ❌ Failed {vid}: {e}")
                raise
            finally:
                self._locks.pop(vid, None)

    def _dl_sync(self, video_id, url, title=None):
        ffmpeg_dir = os.path.dirname(FFMPEG_EXE) if FFMPEG_EXE != 'ffmpeg' else None
        
        # --- PHASE 1: NO-COOKIE EMBED + ANDROID_VR (CHIẾN THUẬT TỐI THƯỢNG) ---
        # Sử dụng domain nhúng và client thực tế ảo để lách bộ lọc bot
        embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}"
        log.info(f"[YT-DL] ⚡ Đang dùng 'Cửa hậu' (No-Cookie Embed) cho: {video_id}")
        
        try:
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
                'extractor_args': {'youtube': {'player_client': ['android_vr', 'web_embedded']}},
                'source_address': '0.0.0.0', # Force IPv4
                'cachedir': False,
            }
            if ffmpeg_dir:
                opts['ffmpeg_location'] = ffmpeg_dir
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([embed_url])
            return # Thành công
        except Exception as e:
            log.warning(f"[YT-DL] Phase 1 thất bại: {e}")

        # --- PHASE 2: THIRD-PARTY API FALLBACK (LOADER.TO) ---
        # Đây là "Bên trung gian" theo yêu cầu của Cậu chủ
        log.info(f"[YT-DL] ⚡ Đang nhờ 'Bên thứ 3' (Loader.to) tải hộ cho: {video_id}")
        try:
            import requests
            import time
            
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://loader.to/"}
            init_url = "https://loader.to/ajax/download.php"
            init_params = {"url": url, "format": "mp3", "button": 1, "start": 1, "end": 1}
            
            r = requests.get(init_url, params=init_params, headers=headers, timeout=15)
            data = r.json()
            if data.get("id"):
                task_id = data["id"]
                progress_url = "https://loader.to/api/progress"
                for _ in range(20): # Max 40s
                    p_resp = requests.get(progress_url, params={"id": task_id}, headers=headers, timeout=10)
                    p_data = p_resp.json()
                    if p_data.get("success") == 1:
                        dl_url = p_data.get("download_url")
                        file_resp = requests.get(dl_url, stream=True, timeout=60)
                        final_path = self.get_path(video_id)
                        with open(final_path, 'wb') as f:
                            for chunk in file_resp.iter_content(chunk_size=16384):
                                f.write(chunk)
                        log.info(f"[YT-DL] ✅ Tải thành công qua Loader.to: {video_id}")
                        return
                    if p_data.get("error"): break
                    time.sleep(2)
        except Exception as e:
            log.error(f"[YT-DL] ❌ Loader.to thất bại: {e}")

        # --- PHASE 3: INVIDIOUS REDIRECT FALLBACK (MẠNG LƯỚI PROXY) ---
        log.info(f"[YT-DL] ⚡ Đang thử 'Cổng Invidious' cho: {video_id}")
        try:
            import requests
            instances = ["https://invidious.lunar.icu", "https://inv.vern.cc", "https://invidious.jing.rocks"]
            for inst in instances:
                try:
                    # Endpoint /latest/ của Invidious sẽ redirect thẳng tới link googlevideo
                    api_url = f"{inst}/latest/{video_id}?quality=audio"
                    r = requests.head(api_url, allow_redirects=True, timeout=10)
                    if "googlevideo.com" in r.url:
                        file_resp = requests.get(r.url, stream=True, timeout=60)
                        final_path = self.get_path(video_id)
                        with open(final_path, 'wb') as f:
                            for chunk in file_resp.iter_content(chunk_size=16384):
                                f.write(chunk)
                        log.info(f"[YT-DL] ✅ Tải thành công qua Invidious Proxy ({inst})")
                        return
                except: continue
        except Exception as e:
            log.error(f"[YT-DL] ❌ Invidious thất bại: {e}")

        raise Exception("Mọi phương thức tải (Embed, Loader.to, Invidious) đều bị YouTube chặn đứng.")
        
        if last_error:
            raise last_error

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
