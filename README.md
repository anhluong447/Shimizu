# 🌸 Shimizu — Discord Music Bot

A premium, interactive Discord Music Bot built with Python and `discord.py`.  
Features a rich embed UI with buttons, search selection, queue management, and audio filters.

---

## ✨ Features

- 🎵 **Interactive Now Playing** — Rich embeds with thumbnail, duration, clickable control buttons, and a **Visual Progress Bar**.
- 🔍 **Smart Search** — Search by keywords and pick from a dropdown of top 5 results.
- 📋 **Queue System** — Paginated queue with add, remove, clear, shuffle, **move**, and **swap** support.
- 🗂️ **Playlist Management** — Save your current queue as a custom playlist and load it back anytime.
- ⏩ **Seek / Jump** — Skip to any part of a song using timestamps.
- 🎖️ **DJ Role System** — Restrict music controls to users with a "DJ" role or Administrator permissions.
- 🔁 **Repeat Modes** — Off / Single Track / Entire Queue.
- 🔊 **Audio Filters** — Bass Boost and Nightcore effects via FFmpeg.
- ⚡ **Play Now** — Skip the queue and play a song immediately.
- ✨ **Autoplay** — Automatically finds and plays "Related Tracks" from SoundCloud Stations when the queue ends.
- 🧹 **Smart Presence** — Auto-pauses when the channel is empty, auto-resumes when members join, and auto-disconnects after 15 minutes of inactivity.
- 🔄 **Quick Reset** — Admin-only command to reload all modules and clear bot state.

---

## 🛠️ Commands

### Music
| Command | Aliases | Description |
| --- | --- | --- |
| `!play <query>` | `!p` | Search & play (link or keywords). |
| `!playnow <query>` | `!pn` | Play immediately, skipping the queue. |
| `!skip` | `!s` | Skip current song. |
| `!seek <time>` | — | Jump to part of a song (e.g., `1:30` or `90`). |
| `!pause` | — | Pause playback. |
| `!resume` | — | Resume playback. |
| `!stop` | `!leave`, `!dc` | Stop & disconnect. |
| `!np` | `!now` | Show Now Playing with controls & progress. |

### Queue
| Command | Aliases | Description |
| --- | --- | --- |
| `!queue [page]` | `!q` | View queue (paginated). |
| `!remove <index>` | `!rm` | Remove a song by index. |
| `!move <from> <to>` | — | Move a song in the queue. |
| `!swap <p1> <p2>` | — | Swap two songs in the queue. |
| `!history` | — | View recently played tracks. |
| `!clear` | — | Clear the entire queue. |
| `!shuffle` | — | Shuffle the queue randomly. |

### Settings
| Command | Aliases | Description |
| --- | --- | --- |
| `!repeat [off/one/all]` | `!loop` | Toggle repeat mode. |
| `!volume <0-200>` | `!vol`, `!v` | Get or set playback volume. |
| `!filter <name>` | `!fx` | Audio filter: `normal`, `bass`, `nightcore`. |
| `!autoplay` | `!ap` | Toggle automatic related track playback. |

### Playlist
| Command | Aliases | Description |
| --- | --- | --- |
| `!save_playlist <name>` | `!sp` | Save current queue to a playlist. |
| `!load_playlist <name>` | `!lp` | Load a saved playlist. |
| `!list_playlists` | `!lps` | View all saved playlists. |

### General
| Command | Description |
| --- | --- |
| `!ping` | Check bot latency. |
| `!hello` | Say hi to Shimizu! |
| `!reset` | Reload all modules (Admin only). |

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
│   └── general.py        # 💬 Basic & System commands
├── utils/                # 🔧 Helpers
├── main.py               # 🚀 Entry point
├── playlists.json        # 📂 User saved playlists
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
