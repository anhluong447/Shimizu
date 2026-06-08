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

# Singleton helper
_db_service = None

def get_db_service() -> DBService:
    global _db_service
    if _db_service is None:
        _db_service = DBService()
    return _db_service
