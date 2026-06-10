import time
from dataclasses import dataclass, field
from datetime import datetime
import logging

log = logging.getLogger("WorldState")

from src.core.config import vietnam_now

@dataclass
class WorldState:
    # Server awareness
    online_members: dict = field(default_factory=dict)            # {user_id: {"since": float, "activity": str}}
    last_message_per_channel: dict = field(default_factory=dict)  # {channel_id: {"author": str, "content": str, "at": float}}
    active_conversation: bool = False                             # is there back-and-forth between users
    active_conversation_members: set = field(default_factory=set)  # set of active user IDs
    
    # Server energy
    message_count_30min: int = 0
    server_energy: float = 0.0                                    # 0.0 (silent) to 1.0 (very active)
    
    # Context
    current_topics: list[str] = field(default_factory=list)
    time_of_day: str = "morning"                                  # "morning", "afternoon", "evening", "night"
    weather_context: str = "Thời tiết mát mẻ"
    
    # Shimizu self-awareness
    last_shimizu_spoke: datetime = field(default_factory=vietnam_now)
    times_ignored_recently: int = 0
    
    # Internal sliding windows
    _msg_timestamps_30m: list[float] = field(default_factory=list) # timestamps of messages in last 30 minutes
    _recent_msg_details: list[dict] = field(default_factory=list)  # [{"author_id": int, "timestamp": float}] in last 5 minutes
 
    def update_time_of_day(self):
        hour = vietnam_now().hour
        if 5 <= hour < 12:
            self.time_of_day = "morning"
        elif 12 <= hour < 18:
            self.time_of_day = "afternoon"
        elif 18 <= hour < 22:
            self.time_of_day = "evening"
        else:
            self.time_of_day = "night"

    def record_message(self, author_id: int, author_name: str, channel_id: int, content: str):
        now = time.time()
        
        # Update last message per channel
        self.last_message_per_channel[channel_id] = {
            "author": author_name,
            "content": content,
            "at": now
        }
        
        # Append to 30 min sliding window
        self._msg_timestamps_30m.append(now)
        # Append to 5 min details window
        self._recent_msg_details.append({
            "author_id": author_id,
            "timestamp": now
        })
        
        self.clean_windows(now)
        self.recompute_state()

    def clean_windows(self, now: float):
        # Clean 30 min window
        cutoff_30m = now - 1800
        self._msg_timestamps_30m = [t for t in self._msg_timestamps_30m if t > cutoff_30m]
        
        # Clean 5 min window
        cutoff_5m = now - 300
        self._recent_msg_details = [d for d in self._recent_msg_details if d["timestamp"] > cutoff_5m]

    def recompute_state(self):
        self.update_time_of_day()
        now = time.time()
        self.clean_windows(now)
        
        self.message_count_30min = len(self._msg_timestamps_30m)
        # 30 messages in 30 minutes = 1.0 energy, scaled down linearly
        self.server_energy = min(1.0, self.message_count_30min / 30.0)
        
        # Check if active conversation (>= 2 distinct users in 5 minutes)
        authors = {d["author_id"] for d in self._recent_msg_details}
        self.active_conversation_members = authors
        if len(authors) >= 2:
            self.active_conversation = True
        else:
            self.active_conversation = False

    def get_last_message_any(self) -> float:
        """Returns timestamp of the last message across all channels, or 0 if none."""
        if not self.last_message_per_channel:
            return 0.0
        return max(info["at"] for info in self.last_message_per_channel.values())

# Singleton instance
_world_state = None

def get_world_state() -> WorldState:
    global _world_state
    if _world_state is None:
        _world_state = WorldState()
        _world_state.update_time_of_day()
    return _world_state
