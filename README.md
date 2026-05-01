# 🌸 Shimizu — Discord Music Bot

A premium, interactive Discord Music Bot built with Python and `discord.py`.  
Features a rich embed UI with buttons, search selection, queue management, and audio filters.

---

## ✨ Features

- 🎵 **Interactive Now Playing** — Rich embeds with thumbnail, duration, and clickable control buttons.
- 🔍 **Smart Search** — Search by keywords and pick from a dropdown of top 5 results.
- 📋 **Queue System** — Paginated queue with add, remove, clear, and shuffle support.
- 🔁 **Repeat Modes** — Off / Single Track / Entire Queue.
- 🔊 **Audio Filters** — Bass Boost and Nightcore effects via FFmpeg.
- ⚡ **Play Now** — Skip the queue and play a song immediately.
- 🧹 **Auto-Cleanup** — Bot leaves after 5 minutes of inactivity.

---

## 🛠️ Commands

### Music
| Command | Aliases | Description |
| --- | --- | --- |
| `!play <query>` | `!p` | Search & play (link or keywords). |
| `!playnow <query>` | `!pn` | Play immediately, skipping the queue. |
| `!skip` | `!s` | Skip current song. |
| `!pause` | — | Pause playback. |
| `!resume` | — | Resume playback. |
| `!stop` | `!leave`, `!dc` | Stop & disconnect. |
| `!np` | `!now` | Show Now Playing with controls. |

### Queue
| Command | Aliases | Description |
| --- | --- | --- |
| `!queue [page]` | `!q` | View queue (paginated). |
| `!remove <index>` | `!rm` | Remove a song by index. |
| `!clear` | — | Clear the entire queue. |
| `!shuffle` | — | Shuffle the queue randomly. |

### Settings
| Command | Aliases | Description |
| --- | --- | --- |
| `!repeat [off/one/all]` | `!loop` | Toggle repeat mode. |
| `!filter <name>` | `!fx` | Audio filter: `normal`, `bass`, `nightcore`. |

### General
| Command | Description |
| --- | --- |
| `!ping` | Check bot latency. |
| `!hello` | Say hi to Shimizu! |

---

## 🚀 Installation

### Prerequisites
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html)

### Setup
```bash
git clone https://github.com/anhluong447/Shimizu.git
cd Shimizu
python -m venv venv
.\venv\Scripts\activate        # Windows
pip install -r requirements.txt
pip install davey               # Required for Discord voice (DAVE protocol)
```

### Configure
Create a `.env` file:
```env
DISCORD_TOKEN=your_token_here
```

### Run
```bash
python main.py
```

---

## 📂 Project Structure

```
Shimizu/
├── cogs/
│   ├── music.py          # 🎵 Music player, queue, filters, UI
│   └── general.py        # 💬 Basic commands (ping, hello)
├── utils/                # 🔧 Helpers (future use)
├── main.py               # 🚀 Entry point
├── .env                  # 🔒 Bot token (private)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🤝 Contributing
Feel free to fork and submit pull requests!

---
*Built with ❤️ by Shimizu Team*
