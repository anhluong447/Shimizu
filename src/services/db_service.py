import sqlite3
import os
import json
import logging
import re
from datetime import datetime

log = logging.getLogger("DBService")
DB_PATH = os.path.join("data", "shimizu.db")

class DBService:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.init_db()

    def _get_conn(self):
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 1. user_facts: Semantic facts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    user_id TEXT,
                    key TEXT,
                    value TEXT,
                    updated_at TIMESTAMP,
                    PRIMARY KEY (user_id, key)
                )
            """)
            
            # 2. episodes: Episodic memory summaries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    summary TEXT,
                    keywords TEXT,
                    created_at TIMESTAMP
                )
            """)
            
            # 3. message_history: Short term chat messages
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TIMESTAMP
                )
            """)
            
            # 4. search_cache: Cache for web searches
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    query_hash TEXT PRIMARY KEY,
                    result TEXT,
                    created_at TIMESTAMP
                )
            """)
            
            # 5. responses: Quality scoring logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    user_msg TEXT,
                    bot_reply TEXT,
                    score INTEGER,
                    created_at TIMESTAMP
                )
            """)

            # 6. psyche: Internal emotional and self states
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS psyche (
                    key TEXT PRIMARY KEY,
                    value TEXT,         -- JSON serialized
                    updated_at TIMESTAMP
                )
            """)

            # 7. agenda: Proactive objectives
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agenda (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT,
                    priority INTEGER,   -- 1 (high) to 3 (low)
                    context TEXT,       -- trigger conditions
                    created_at TIMESTAMP,
                    executed_at TIMESTAMP  -- NULL if pending
                )
            """)

            # 8. action_cooldowns: Cooldowns on proactive activities
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_cooldowns (
                    action_type TEXT PRIMARY KEY,
                    last_executed TIMESTAMP
                )
            """)

            # 9. server_patterns: Learned server behavior statistics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS server_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT,      -- "peak_hours", "recurring_topic", "user_behavior"
                    description TEXT,
                    confidence REAL,        -- 0.0 to 1.0
                    observation_count INTEGER DEFAULT 1,
                    first_observed TIMESTAMP,
                    last_observed TIMESTAMP
                )
            """)

            # 10. heartbeat_log: Log each heartbeat tick status
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS heartbeat_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tick_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    gates_passed TEXT,      -- JSON array
                    gates_failed TEXT,      -- JSON array
                    signals_score REAL,
                    action_taken TEXT,
                    action_reason TEXT
                )
            """)

            # 11. psyche_log: Psyche snapshots logged on significant changes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS psyche_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    energy REAL,
                    curiosity REAL,
                    restlessness REAL,
                    current_interest TEXT,
                    unresolved_thought TEXT,
                    trigger TEXT
                )
            """)

            # 12. dream_log: Dream cycle output summary
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dream_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ran_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    episodes_reviewed INTEGER,
                    energy_delta REAL,
                    new_interest TEXT,
                    unresolved TEXT,
                    agenda_created TEXT,    -- JSON array
                    belief_update TEXT      -- JSON
                )
            """)

            conn.commit()
            log.info("Database initialized successfully.")

    # --- message_history ---
    def get_messages(self, user_id: str) -> list:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM message_history WHERE user_id = ? ORDER BY id ASC",
                (str(user_id),)
            )
            rows = cursor.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]

    def save_messages(self, user_id: str, messages: list):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # Delete old messages first
            cursor.execute("DELETE FROM message_history WHERE user_id = ?", (str(user_id),))
            # Insert the new list
            now = datetime.now().isoformat()
            for msg in messages:
                cursor.execute(
                    "INSERT INTO message_history (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (str(user_id), msg["role"], msg["content"], now)
                )
            conn.commit()

    def clear_messages(self, user_id: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM message_history WHERE user_id = ?", (str(user_id),))
            conn.commit()

    # --- user_facts ---
    def save_fact(self, user_id: str, key: str, value: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                """INSERT OR REPLACE INTO user_facts (user_id, key, value, updated_at) 
                   VALUES (?, ?, ?, ?)""",
                (str(user_id), key.strip(), value.strip(), now)
            )
            conn.commit()

    def get_facts(self, user_id: str) -> dict:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_facts WHERE user_id = ?", (str(user_id),))
            rows = cursor.fetchall()
            return {r["key"]: r["value"] for r in rows}

    # --- episodes ---
    def save_episode(self, user_id: str, summary: str, keywords: list):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO episodes (user_id, summary, keywords, created_at) VALUES (?, ?, ?, ?)",
                (str(user_id), summary.strip(), json.dumps(keywords), now)
            )
            conn.commit()

    def get_episodes(self, user_id: str) -> list:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT summary, keywords FROM episodes WHERE user_id = ?", (str(user_id),))
            rows = cursor.fetchall()
            result = []
            for r in rows:
                try:
                    kw = json.loads(r["keywords"])
                except Exception:
                    kw = []
                result.append({"summary": r["summary"], "keywords": kw})
            return result

    def search_episodes(self, user_id: str, query: str, top_k: int = 3) -> list:
        """Simple keyword-overlap search on episodes."""
        episodes = self.get_episodes(user_id)
        if not episodes:
            return []
            
        # Clean and split query words
        query_words = set(re.findall(r'\w+', query.lower()))
        if not query_words:
            return episodes[:top_k]
            
        ranked = []
        for ep in episodes:
            keywords = set(k.lower() for k in ep["keywords"])
            # Calculate intersection
            overlap = len(query_words.intersection(keywords))
            ranked.append((overlap, ep))
            
        # Sort by overlap score descending
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in ranked[:top_k] if item[0] > 0]

    # --- search_cache ---
    def get_search_cache(self, query_hash: str) -> str:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT result, created_at FROM search_cache WHERE query_hash = ?",
                (query_hash,)
            )
            row = cursor.fetchone()
            if row:
                created_at = datetime.fromisoformat(row["created_at"])
                # Expire after 24 hours
                if (datetime.now() - created_at).total_seconds() < 86400:
                    return row["result"]
            return None

    def save_search_cache(self, query_hash: str, result: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT OR REPLACE INTO search_cache (query_hash, result, created_at) VALUES (?, ?, ?)",
                (query_hash, result, now)
            )
            conn.commit()

    # --- responses ---
    def save_response(self, user_id: str, user_msg: str, bot_reply: str, score: int):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO responses (user_id, user_msg, bot_reply, score, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(user_id), user_msg, bot_reply, score, now)
            )
            conn.commit()

    def get_low_scores(self, limit: int = 20) -> list:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_msg, bot_reply, score FROM responses WHERE score < 3 ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [dict(r) for r in cursor.fetchall()]

    # --- psyche ---
    def save_psyche_raw(self, key: str, value: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT OR REPLACE INTO psyche (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now)
            )
            conn.commit()

    def get_psyche_raw(self, key: str) -> str:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM psyche WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    # --- agenda ---
    def get_pending_agenda(self, priority: int = None) -> list:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if priority is not None:
                cursor.execute(
                    "SELECT id, description, priority, context FROM agenda WHERE executed_at IS NULL AND priority = ? ORDER BY priority ASC, created_at ASC",
                    (priority,)
                )
            else:
                cursor.execute(
                    "SELECT id, description, priority, context FROM agenda WHERE executed_at IS NULL ORDER BY priority ASC, created_at ASC"
                )
            return [dict(r) for r in cursor.fetchall()]

    def save_agenda(self, description: str, priority: int = 2, context: str = None):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO agenda (description, priority, context, created_at) VALUES (?, ?, ?, ?)",
                (description, priority, context, now)
            )
            conn.commit()

    def mark_agenda_executed(self, agenda_id: int):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE agenda SET executed_at = ? WHERE id = ?",
                (now, agenda_id)
            )
            conn.commit()

    # --- action_cooldowns ---
    def get_cooldown(self, action_type: str) -> str:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_executed FROM action_cooldowns WHERE action_type = ?", (action_type,))
            row = cursor.fetchone()
            return row["last_executed"] if row else None

    def set_cooldown(self, action_type: str, last_executed: str = None):
        if last_executed is None:
            last_executed = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO action_cooldowns (action_type, last_executed) VALUES (?, ?)",
                (action_type, last_executed)
            )
            conn.commit()

    # --- today data for dream ---
    def get_today_episodes(self) -> list:
        today_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, summary, keywords, created_at FROM episodes WHERE created_at LIKE ? ORDER BY id ASC",
                (f"{today_str}%",)
            )
            rows = cursor.fetchall()
            result = []
            for r in rows:
                try:
                    kw = json.loads(r["keywords"])
                except Exception:
                    kw = []
                result.append({"user_id": r["user_id"], "summary": r["summary"], "keywords": kw, "created_at": r["created_at"]})
            return result

    def get_today_responses(self) -> list:
        today_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, user_msg, bot_reply, score, created_at FROM responses WHERE created_at LIKE ? ORDER BY id ASC",
                (f"{today_str}%",)
            )
            return [dict(r) for r in cursor.fetchall()]

    def dream_done_today(self) -> bool:
        val = self.get_psyche_raw("dream_last_run")
        if not val:
            return False
        today_str = datetime.now().strftime("%Y-%m-%d")
        return val == today_str

    def mark_dream_done_today(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.save_psyche_raw("dream_last_run", today_str)

    # --- server_patterns ---
    def upsert_pattern(self, pattern_type: str, description: str, initial_confidence: float = 0.3):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "SELECT id, confidence, observation_count FROM server_patterns WHERE pattern_type = ? AND description = ?",
                (pattern_type, description)
            )
            row = cursor.fetchone()
            if row:
                new_count = row["observation_count"] + 1
                new_conf = min(1.0, row["confidence"] + 0.15)
                cursor.execute(
                    "UPDATE server_patterns SET confidence = ?, observation_count = ?, last_observed = ? WHERE id = ?",
                    (new_conf, new_count, now, row["id"])
                )
            else:
                cursor.execute(
                    """INSERT INTO server_patterns 
                       (pattern_type, description, confidence, observation_count, first_observed, last_observed) 
                       VALUES (?, ?, ?, 1, ?, ?)""",
                    (pattern_type, description, initial_confidence, now, now)
                )
            conn.commit()

    def get_active_patterns(self, min_confidence: float = 0.5) -> list:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT pattern_type, description, confidence FROM server_patterns WHERE confidence >= ? ORDER BY confidence DESC",
                (min_confidence,)
            )
            return [dict(r) for r in cursor.fetchall()]

    # --- debug logging methods ---
    def log_heartbeat(self, gates_passed: list, gates_failed: list, 
                      signals_score: float, action_taken: str = None, 
                      action_reason: str = None):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO heartbeat_log (gates_passed, gates_failed, signals_score, action_taken, action_reason) VALUES (?,?,?,?,?)",
                (json.dumps(gates_passed), json.dumps(gates_failed), 
                 signals_score, action_taken, action_reason)
            )
            conn.commit()

    def get_heartbeat_log(self, limit: int = 20) -> list:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM heartbeat_log ORDER BY tick_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def log_psyche(self, energy: float, curiosity: float, restlessness: float,
                   current_interest: str, unresolved: str, trigger: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO psyche_log (energy, curiosity, restlessness, current_interest, unresolved_thought, trigger) VALUES (?,?,?,?,?,?)",
                (energy, curiosity, restlessness, current_interest, unresolved, trigger)
            )
            conn.commit()

    def log_dream(self, episodes_reviewed: int, energy_delta: float,
                  new_interest: str, unresolved: str, 
                  agenda_created: list, belief_update: dict = None):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO dream_log (episodes_reviewed, energy_delta, new_interest, unresolved, agenda_created, belief_update) VALUES (?,?,?,?,?,?)",
                (episodes_reviewed, energy_delta, new_interest, unresolved,
                 json.dumps(agenda_created), json.dumps(belief_update) if belief_update else None)
            )
            conn.commit()

    def get_latest_dream(self) -> dict:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dream_log ORDER BY ran_at DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def cleanup_old_logs(self, days: int = 7):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM heartbeat_log WHERE tick_at < datetime('now', ?)", (f'-{days} days',))
            cursor.execute("DELETE FROM psyche_log WHERE logged_at < datetime('now', ?)", (f'-{days} days',))
            cursor.execute("DELETE FROM dream_log WHERE ran_at < datetime('now', ?)", (f'-{days} days',))
            conn.commit()

# Singleton helper
_db_service = None

def get_db_service() -> DBService:
    global _db_service
    if _db_service is None:
        _db_service = DBService()
    return _db_service
