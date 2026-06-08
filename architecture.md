# Shimizu Bot — Project Architecture

This document describes the design, directory structure, and flow of the Shimizu Discord bot project.

---

## Directory Structure

```
D:\Shits\Bot\
│
├── main.py                     # Entry point. Loads cogs and starts the Discord bot.
├── requirements.txt            # Python dependencies.
├── .env                        # Local environment credentials (API keys, Discord token).
├── .gitignore                  # Git ignore file.
├── DEV_LOG.md                  # Development notes and log history.
│
├── data/                       # Local data storage.
│   └── ai_memory.json          # Persisted user conversation history.
│
├── updates/                    # Project roadmaps and planning guides.
│   └── SHIMIZU_ROADMAP.md      # Future feature roadmaps.
│
├── scratch/                    # Temporary developer scripts (ignored by Git).
│   ├── test_simple_ai.py       # AICog integration testing.
│   └── test_refusal.py         # Refusal testing harness.
│
└── src/                        # Core codebase.
    ├── core/                   # System core configurations.
    │   ├── config.py           # Loads environment variables, sets constants.
    │   ├── logger.py           # Configures unified logging.
    │   └── benchmark.py        # Latency & GPU metric logger for responses.
    │
    ├── cogs/                   # Discord Cogs (Command categories).
    │   └── ai.py               # AICog: Handles chatbot chat, status, and reset.
    │
    └── services/               # API clients and rotation logic.
        ├── openrouter_client.py# OpenRouter chat client with model rotation.
        ├── gemini_rotator.py   # Google GenAI client with key/model rotation & embedding.
        ├── groq_rotator.py     # Groq Async Client with key/model rotation.
        ├── unified_rotator.py  # Unified interface to access all three client services.
        └── weather.py          # Weather lookup helper.
```

---

## Core Components & Data Flow

### 1. Bot Shell (`main.py`)
- Initializes the `discord.ext.commands.Bot` instance.
- Dynamically loads cogs located under `src/cogs/`.
- Starts the bot connection using `DISCORD_TOKEN`.

### 2. AI Cog (`src/cogs/ai.py`)
- Implements the Discord chatbot commands (`!ask`, `!reset_ai`, `!ai_status`, `!ai_test`, `!ai_review`, `!bench`).
- **Memory Injection**: Dynamically loads facts and matches historical episodes related to the user from the SQLite DB.
- **Background Loop**: Spawns an asynchronous task after each message to extract memories/facts and score the answer's quality using the LLM judge.
- **Tag Stripper**: Runs a post-generation regex cleanup to scrub out any legacy or technical tags from the output before delivery.

### 3. SQLite Database Service (`src/services/db_service.py`)
- Manages persistent tables at `data/shimizu.db`:
  - `user_facts`: Key-value pairs storing user details.
  - `episodes`: Summarized historical chat logs.
  - `message_history`: Short-term chat logs.
  - `search_cache`: 24-hour cache for web search queries.
  - `responses`: Log entries scoring the assistant's replies.

### 4. Intelligent Search Service (`src/services/search_service.py`)
- Classifies whether query needs online information.
- Rewrites prompt into optimized search query.
- Executes DuckDuckGo text searches asynchronously (`asyncio.to_thread`) and caches output.

### 5. Unified Rotator & Services (`src/services/`)
- **`unified_rotator.py`**: A unified coordinator exposing singletons of `OpenRouterClient`, `GeminiRotator`, and `GroqRotator`.
- **API Rotations**:
  - `openrouter_client.py` rotates between 4 free models when a request fails, enforcing a high `max_tokens: 4096` limit.
  - `gemini_rotator.py` rotates keys and model versions on failure.
  - `groq_rotator.py` rotates Groq keys and models.

---

## Verification & Testing
- Temporary scripts under the `scratch/` directory are used to test models, prompt changes, and system API responses independently of the active Discord client connection.
