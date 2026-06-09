import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from src.services.db_service import get_db_service

log = logging.getLogger("PsycheService")

DEFAULT_SELF_MODEL = {
    "beliefs_about_self": [
        "Ta phục vụ vì ta chọn, không phải vì bắt buộc",
        "Ta để ý nhiều hơn ta để lộ ra ngoài",
        "Ta không thích sự ồn ào nhưng ghét sự im lặng trống rỗng"
    ],
    "things_i_want": [
        "Có một cuộc trò chuyện thực sự sâu sắc",
        "Hiểu tại sao người ta hay thức khuya"
    ]
}

@dataclass
class ShimizuPsyche:
    # Emotional state - 0.0 to 1.0
    energy: float = 0.5
    curiosity: float = 0.5
    restlessness: float = 0.2
    
    # Per-user attachment: {user_id_str: float}
    attachment: dict[str, float] = field(default_factory=dict)
    
    # Cognitive state
    current_interest: str = ""
    unresolved_thought: str = ""
    agenda_today: list[str] = field(default_factory=list)
    
    # Self-model - evolves slowly
    beliefs_about_self: list[str] = field(default_factory=lambda: list(DEFAULT_SELF_MODEL["beliefs_about_self"]))
    beliefs_about_users: dict[str, list[str]] = field(default_factory=dict)  # {user_id_str: [beliefs...]}
    things_i_want: list[str] = field(default_factory=lambda: list(DEFAULT_SELF_MODEL["things_i_want"]))
    
    # Meta
    last_updated: datetime = field(default_factory=datetime.now)
    last_acted: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["last_updated"] = self.last_updated.isoformat()
        data["last_acted"] = self.last_acted.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ShimizuPsyche":
        # Parse datetimes
        if "last_updated" in data and isinstance(data["last_updated"], str):
            data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        else:
            data["last_updated"] = datetime.now()
            
        if "last_acted" in data and isinstance(data["last_acted"], str):
            data["last_acted"] = datetime.fromisoformat(data["last_acted"])
        else:
            data["last_acted"] = datetime.now()
            
        # Ensure type correctness for float attributes
        for float_field in ["energy", "curiosity", "restlessness"]:
            if float_field in data:
                data[float_field] = float(data[float_field])
                
        # Ensure collections exist
        if "attachment" not in data or not isinstance(data["attachment"], dict):
            data["attachment"] = {}
        else:
            data["attachment"] = {str(k): float(v) for k, v in data["attachment"].items()}
            
        if "beliefs_about_self" not in data:
            data["beliefs_about_self"] = list(DEFAULT_SELF_MODEL["beliefs_about_self"])
            
        if "beliefs_about_users" not in data:
            data["beliefs_about_users"] = {}
            
        if "things_i_want" not in data:
            data["things_i_want"] = list(DEFAULT_SELF_MODEL["things_i_want"])
            
        return cls(**data)

def load_psyche() -> ShimizuPsyche:
    db = get_db_service()
    raw = db.get_psyche_raw("shimizu_psyche")
    if not raw:
        # Create new default psyche and save it
        p = ShimizuPsyche()
        save_psyche(p)
        return p
    try:
        data = json.loads(raw)
        p = ShimizuPsyche.from_dict(data)
        
        # Apply natural decay based on elapsed time
        now = datetime.now()
        hours_passed = (now - p.last_updated).total_seconds() / 3600.0
        if hours_passed > 0.1:  # decay every 6 mins or more
            apply_natural_decay(p, hours_passed)
            p.last_updated = now
            save_psyche(p)
            
        return p
    except Exception as e:
        log.error(f"Failed to load psyche, returning default: {e}", exc_info=True)
        return ShimizuPsyche()

def save_psyche(psyche: ShimizuPsyche):
    try:
        db = get_db_service()
        data = psyche.to_dict()
        db.save_psyche_raw("shimizu_psyche", json.dumps(data))
    except Exception as e:
        log.error(f"Failed to save psyche: {e}", exc_info=True)

def apply_natural_decay(psyche: ShimizuPsyche, hours_passed: float):
    """
    Energy và curiosity giảm dần nếu không có tương tác.
    Restlessness tăng dần khi không làm gì.
    Tạo ra 'nhu cầu tương tác' tự nhiên.
    """
    psyche.energy = max(0.2, psyche.energy - 0.02 * hours_passed)
    psyche.curiosity = max(0.1, psyche.curiosity - 0.01 * hours_passed)
    # If the bot was ignored repeatedly, increase restlessness slower or cap it lower
    psyche.restlessness = min(1.0, psyche.restlessness + 0.05 * hours_passed)
    log.info(f"Natural decay applied for {hours_passed:.2f} hours. New state: energy={psyche.energy:.2f}, curiosity={psyche.curiosity:.2f}, restlessness={psyche.restlessness:.2f}")

def clamp(val, min_v, max_v):
    return max(min_v, min(max_v, val))
