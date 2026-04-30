# 🌸 Shimizu Music Bot

A professional, modular Discord Music Bot built with Python and `discord.py`.

## ✨ Features

- **High-Quality Audio**: Powered by `yt-dlp` and `FFmpeg`.
- **Music Queue**: Add multiple songs to the queue and skip through them.
- **Smart Search**: Search for songs by title or keywords without needing a link.
- **Modular Structure**: Easily extendable using the Discord Cogs system.
- **Auto-Cleanup**: Bot automatically leaves the voice channel after 5 minutes of inactivity.

## 🛠️ Commands

| Command | Aliases | Description |
| --- | --- | --- |
| `!play <search>` | `!p` | Search and play music from YouTube. |
| `!skip` | `!s` | Skip the current song. |
| `!queue` | `!q` | View the current music queue. |
| `!pause` | - | Pause the current playback. |
| `!resume` | - | Resume playback. |
| `!stop` | `!leave` | Stop music and disconnect. |
| `!ping` | - | Check bot latency. |
| `!hello` | - | Say hello to Shimizu! |

## 🚀 Installation

### Prerequisites
- Python 3.8+
- [FFmpeg](https://ffmpeg.org/download.html)

### Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/anhluong447/Shimizu.git
   cd Shimizu
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install davey  # Required for Discord DAVE protocol
   ```

4. **Configure environment**:
   Create a `.env` file in the root directory and add your bot token:
   ```env
   DISCORD_TOKEN=your_token_here
   ```

5. **Run the bot**:
   ```bash
   python main.py
   ```

## 📂 Project Structure

```text
Shimizu/
├── cogs/               # Modular features (Music, General)
├── utils/              # Helper functions
├── main.py             # Entry point
├── .env                # Private configuration
└── requirements.txt    # Dependencies
```

## 🤝 Contributing
Feel free to fork this project and submit pull requests for new features or bug fixes!

---
*Built with ❤️ by Shimizu Team*
