import os
import platform
import pytz
from dotenv import load_dotenv

load_dotenv()

# --- Bot Config ---
TOKEN = os.getenv('DISCORD_TOKEN')
SECRET_KEY = os.getenv('SECRET_KEY')
GUILD_ID = os.getenv('GUILD_ID')
PREFIX = '!'
TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

# --- Ollama Config ---
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'shimizu-qwen')

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

# Data Files
PLAYLISTS_FILE = os.path.join(DATA_DIR, 'playlists.json')
NOTIFICATIONS_FILE = os.path.join(DATA_DIR, 'notifications.json')
MENG_ENC_FILE = os.path.join(DATA_DIR, 'meng.ann')

# --- Music Config ---
if platform.system() == 'Windows':
    FFMPEG_EXE = os.path.join(BASE_DIR, r'ffmpeg-8.1-essentials_build\bin\ffmpeg.exe')
else:
    FFMPEG_EXE = 'ffmpeg'

YTDL_OPTS = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'Normal': {
        'options': '-vn',
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    },
    'Bass Boost': {
        'options': '-vn -af "bass=g=10,equalizer=f=40:width_type=h:width=50:g=5"',
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    },
    'Nightcore': {
        'options': '-vn -af "asetrate=44100*1.25,aresample=44100,atempo=1.0"',
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    }
}

REPEAT_OFF, REPEAT_ONE, REPEAT_ALL = 0, 1, 2
REPEAT_LABELS = {0: 'Tắt', 1: '🔂 Lặp bài', 2: '🔁 Lặp hàng đợi'}
AUTOPLAY_LABELS = {False: 'Tắt', True: '✨ Đang bật'}
