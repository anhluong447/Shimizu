<div align="center">

# 🌸 Shimizu

**A Premium, All-in-One Discord Bot for Couples and Music Lovers**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.4%2B-blue.svg)](https://discordpy.readthedocs.io/en/stable/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![AWS Deployed](https://img.shields.io/badge/Deployed-AWS%20EC2-orange.svg)](https://aws.amazon.com/ec2/)

[Features](#-features) • [Installation](#-installation) • [Commands](#-commands) • [Structure](#-project-structure)

</div>

---

Shimizu isn't just a music bot—she's a highly intelligent virtual maid. She combines high-fidelity audio with a sophisticated AI brain capable of internet-grounded reasoning, memory retention, and performance monitoring.

### 🤖 Advanced AI Intelligence
- **Hybrid AI Infrastructure** — High-performance multi-provider rotation system using **Groq** (primary) and **Gemini** (fallback).
- **Hybrid Memory System (3-Tier)** — Advanced memory management:
    - **Short-term**: Instant recall of the last 5 messages.
    - **Mid-term**: Dynamic summarization of the recent 10 messages for session coherence.
    - **Long-term (Vector RAG)**: Unlimited archival storage using Gemini embeddings and local vector search (Numpy).
- **Semantic Knowledge Cache** — Automatically caches web search results in a persistent Vector DB, allowing instant retrieval of previously learned facts and reducing hallucination.
- **Privacy Partitioning** — Individual, secure memory silos for different owners (e.g., Cậu chủ vs. Cô chủ).
- **Grounded Reasoning** — Integrates with DuckDuckGo and Jina Reader to provide factual, real-time answers for events beyond model training data.
- **Performance Benchmarking** — Real-time GPU/CPU monitoring during AI generation with beautiful visual charts.

### 🎵 High-Fidelity Music
- **Gapless Playback** — Advanced pre-fetching logic loads the next track 10 seconds before the current one ends.
- **Smart Autoplay** — Automatically discovers related tracks using SoundCloud Stations when the queue is empty.
- **Interactive UI** — Beautiful embeds with real-time progress bars, dropdown search results, and button controls.
- **Audio Engineering** — Built-in FFmpeg filters for Bass Boost and Nightcore effects.
- **Persistent Playlists** — Save and load your favorite queues across sessions.

### 🛠️ Modern Interactions
- **Hybrid Commands** — Supports both traditional `!` prefixes and modern `/` Slash Commands.
- **Autocomplete Support** — Intuitive parameter hints and descriptions for all commands.
- **Guild-Specific Syncing** — Instant command updates via specific guild synchronization.

### 🏠 Utility & Couple Features
- **Smart Weather** — Detailed forecasts including Morning/Noon/Evening/Night temperatures and 24h outlook.
- **Couple Trivia** — Encrypted interactive game with a 100-question pool to test how well you know each other.
- **Dynamic Presence** — Bot status updates in real-time based on music playback and random moods.
- **Secret Memories** — Secure, XOR-encrypted data storage for personal notes and memories.
- **Tarot Divination** — Advanced 78-card inspired system (34 detailed cards) with ephemeral results, journaling, and social sharing.

---

## 🛠️ Commands

### 🎵 Music (Slash & Prefix)
| Command | Description |
| --- | --- |
| `/play` | Search and play music (Keywords or URL). |
| `/playnow` | Insert a song at the front and skip to it immediately. |
| `/skip` | Skip the current track. |
| `/seek` | Jump to a specific time (e.g., `1:30` or `90`). |
| `/queue` | View the paginated queue. |
| `/history` | View the 10 most recently played tracks. |
| `/filter` | Apply audio filters: `normal`, `bass`, `nightcore`. |
| `/autoplay` | Toggle automatic discovery of related tracks. |

### 🤖 AI & Intelligence (Prefix)
| Command | Description |
| --- | --- |
| `!ask` | Ask Shimizu anything (Includes web search & memory). |
| `!bench` | Toggle performance benchmarking (GPU/Time charts). |
| `!bench_debug` | Debug GPU detection and NVML status. |
| `!ai_status` | Check status of the Groq & Gemini rotation systems. |
| `!reset_ai` | Clear Short-term & Mid-term conversation history. |
| `!clear_brain` | Permanent wipe of Long-term (Vector) memory archive. |

### 📋 Management & Utility
| Command | Description |
| --- | --- |
| `/weather` | Get detailed weather forecast for any city. |
| `/notify` | Set a recurring daily notification. |
| `/reminders` | View your active notifications. |
| `/trivia` | Play the Couple Trivia game (2 players). |
| `/ping` | Check bot and API latency. |
| `/meng` | Access the encrypted memory box. |
| `/tarot` | Mystical divination system (draw, spread, love, work). |

---

## 🚀 Installation

### Prerequisites
- **Python 3.10+**
- **FFmpeg** (Required for audio processing)
- **Discord Bot Token** (From [Discord Developer Portal](https://discord.com/developers/applications))

### Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/anhluong447/Shimizu.git
   cd Shimizu
   ```

2. **Environment Setup:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # OR
   .\venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

3. **Configuration:**
   Create a `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   GUILD_ID=your_server_id_here
   SECRET_KEY=your_encryption_key_here
   ```

4. **Running the bot:**
   ```bash
   python main.py
   ```

---

## 📂 Project Structure

```text
Shimizu/
├── src/
│   ├── cogs/            # Functional modules
│   │   ├── music/       # Core player logic, UI, and models
│   │   ├── general.py   # Basic commands
│   │   ├── utility.py   # Weather & Notifications
│   │   ├── secret.py    # Encrypted memories
│   │   ├── trivia.py    # Couple Trivia game
│   │   ├── presence.py  # Bot status management
│   │   └── tarot.py     # Mystical Tarot system
│   ├── core/            # Configuration and logging
│   ├── services/        # External API integrations (Groq, Gemini, Unified Rotator)
│   └── utils/           # Shared helper functions
├── data/                # Persistent storage (JSON, TXT, Logs)
├── main.py              # Application entry point
├── .env                 # Environment variables
├── requirements.txt     # Python dependencies
```

---

## 🤝 Contributing
Contributions are welcome! If you have ideas for new features or improvements, feel free to open an issue or submit a pull request.

---

<div align="center">
  <i>Built with ❤️ for couples and music enthusiasts everywhere.</i>
</div>
