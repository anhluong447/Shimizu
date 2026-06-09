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
│   └── shimizu.db              # SQLite Database holding history, memories, psyche, cooldowns, patterns, and logs.
│
├── docs/                       # Project documentation.
│   ├── architecture.md         # Architecture and structural overview.
│   └── usage.md                # Usage manual (how bot's mind, proactive engine, and debug system works).
│
├── updates/                    # Project roadmaps and planning guides.
│   ├── SHIMIZU_ROADMAP.md      # Future feature roadmaps.
│   └── SHIMIZU_UPDATES.md      # Living Entity upgrade design doc.
│
├── scratch/                    # Temporary developer scripts (ignored by Git).
│   ├── test_simple_ai.py       # AICog integration testing.
│   ├── test_refusal.py         # Refusal testing harness.
│   ├── test_psyche.py          # Psyche and WorldState dry-run tester.
│   └── test_observability.py   # Observability and database logging tester.
│
└── src/                        # Core codebase.
    ├── core/                   # System core configurations.
    │   ├── config.py           # Loads environment variables, sets constants.
    │   ├── logger.py           # Configures unified logging.
    │   └── benchmark.py        # Latency & GPU metric logger for responses.
    │
    ├── cogs/                   # Discord Cogs (Command categories).
    │   ├── ai.py               # AICog: Chatbot prompt generation and interactive ask command.
    │   ├── awareness.py        # AwarenessCog: Real-time listeners, Heartbeat proactive loops, and Dream Cycles.
    │   └── debug.py            # DebugCog: Owner-only administrative and observability commands.
    │
    └── services/               # API clients, state engines, and services.
        ├── openrouter_client.py# OpenRouter chat client with model rotation.
        ├── gemini_rotator.py   # Google GenAI client with key/model rotation & embedding.
        ├── groq_rotator.py     # Groq Async Client with key/model rotation.
        ├── unified_rotator.py  # Unified interface to access OpenRouter/Gemini/Groq.
        ├── weather.py          # Weather lookup helper.
        ├── db_service.py       # SQLite interface for facts, messages, cooldowns, agendas, patterns, and logs.
        ├── psyche_service.py   # ShimizuPsyche dataclass, natural decay formulas, and serialization.
        └── world_state.py      # WorldState RAM tracker for rolling server energy and active conversations.
```

---

## Core Components & Data Flow

### 1. Bot Shell (`main.py`)
- Initializes the `discord.ext.commands.Bot` instance.
- Configures gateway intents (including `members`, `presences`, `reactions`, and `voice_states`).
- Dynamically loads cogs located under `src/cogs/` (including `DebugCog` automatically).
- Starts the bot connection using `DISCORD_TOKEN`.

### 2. Living Entity Core Services (`src/services/`)

#### A. SQLite DB Service (`db_service.py`)
Provides persistent storage for memories, short-term history, caching, and cognitive records:
- `user_facts`: Key-value user traits extracted by the LLM judge.
- `episodes`: Summarized historical interactions.
- `psyche`: Serialized JSON of Shimizu's internal emotional levels.
- `agenda`: Action items queue for proactive tasks.
- `action_cooldowns`: Strict rate limit trackers for bot proactive messages.
- `server_patterns`: Statistical metrics (peak hours, common topics).
- `heartbeat_log`: Log records of every heartbeat tick containing gate flags, signal score, actions, and reasonings.
- `psyche_log`: Snaphots of emotional states triggered by decay, manual settings, dream cycles, or user chats.
- `dream_log`: Daily summaries, energy delta, new interests, unresolved thoughts, tomorrow's agendas, and belief updates.

#### B. Psyche Engine (`psyche_service.py`)
- Holds `ShimizuPsyche` representing emotional variables (`energy`, `curiosity`, `restlessness`), user attachments (`attachment`), self-beliefs (`beliefs_about_self`), and user-specific beliefs (`beliefs_about_users`).
- Drives natural decay over time (e.g., restlessness rises, energy and curiosity decrease when the server is inactive).

#### C. WorldState RAM Tracker (`world_state.py`)
- Maintains real-time server activity metrics in memory:
  - `online_members`: Track who is online and active.
  - `server_energy`: Rolling average metric based on message counts over a 30-minute window.
  - `active_conversation`: Flag signifying if multiple non-bot users are actively talking in a short window.
  - `time_of_day` & `weather_context`: Real-time contextual parameters.

---

## Loop Dynamics & Cognitive Processing

### 1. Real-time Listening (`src/cogs/awareness.py`)
- Updates WorldState RAM upon Discord events (`on_message`, `on_member_update`, `on_reaction_add`, `on_voice_state_update`).
- Adapts psyche immediately when direct interactions occur (energy boost, restlessness reduction, attachment increase).

### 2. Proactive Heartbeat Loop (5-Minute Cycle)
- Runs a multi-gate check (night gate, action cooldown, active conversation exclusion, ignored-user exclusion).
- Evaluates signals (long silence, known user online, high energy) to calculate a signal score.
- Executes pending agenda tasks if appropriate.
- Triggers **Entropy Engine** actions (sharing random unresolved thoughts, interests, philosophical queries) if restlessness exceeds `0.75`.
- Calls LLM to decide if a proactive response is suitable and generates context-relevant remarks.

### 3. Dream Cycle Loop (30-Minute Check / Daily Execution)
- Activates when the server has been silent for at least 2 hours.
- Summarizes daily interactions and scores conversation quality.
- Performs nightly LLM-based self-reflection to update long-term self-beliefs, user attachment adjustments, and schedule next-day agendas.
- Runs **Epistemic Memory** statistical learning to index peak server hours, recurring topics, and co-presence user pairs without API fees.

### 4. Interactive Chat Cog (`src/cogs/ai.py`)
- Processes user messages (`!ask`).
- Injects facts, related episodes, web search results, bot self-beliefs, learned server patterns, and current interests into the LLM system prompt.
- Dynamically shifts persona tone (warmth, verbosity) based on current `energy` and `attachment` metrics.
- Updates bot state upon successful query completion.
