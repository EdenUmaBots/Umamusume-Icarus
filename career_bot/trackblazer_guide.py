
import json
from functools import lru_cache
from pathlib import Path

DEFAULT_GUIDE = {
    "race_bonus_target": 50,
    "target_races_min": 25,
    "target_races_typical": 30,
    "race_pattern": {"race_chain_target": 2, "free_turn_after_chain": 1},
    "summer_camp_turns": [37, 38, 39, 40, 61, 62, 63, 64],
    "summer_strategy": {"summer_training_score_bonus": 0.16, "pre_summer_reserve_coin": 120},
    "shop_priorities": {},
}

@lru_cache(maxsize=4)
def load_guide(base_dir):
    path = Path(base_dir) / "data" / "trackblazer_game8_strategy.json"
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_GUIDE)
            merged.update(data if isinstance(data, dict) else {})
            return merged
    except Exception:
        pass
    return dict(DEFAULT_GUIDE)

def is_summer_turn(turn, guide=None):
    guide = guide or DEFAULT_GUIDE
    return int(turn or 0) in set(int(t) for t in guide.get("summer_camp_turns", []))

def is_pre_summer(turn):
    turn = int(turn or 0)
    return turn in {31, 32, 33, 34, 35, 55, 56, 57, 58, 59}

def race_chain_target(guide=None):
    guide = guide or DEFAULT_GUIDE
    return int(((guide.get("race_pattern") or {}).get("race_chain_target") or 2))
