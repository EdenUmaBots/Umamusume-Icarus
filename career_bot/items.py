import json

from pathlib import Path

from career_bot.trackblazer_guide import load_guide, is_pre_summer, is_summer_turn
from career_bot import trackblazer_rules as tb_rules

ITEM_NAMES = {
    1001: "Speed Notepad",
    1002: "Stamina Notepad",
    1003: "Power Notepad",
    1004: "Guts Notepad",
    1005: "Wit Notepad",
    1101: "Speed Manual",
    1102: "Stamina Manual",
    1103: "Power Manual",
    1104: "Guts Manual",
    1105: "Wit Manual",
    1201: "Speed Scroll",
    1202: "Stamina Scroll",
    1203: "Power Scroll",
    1204: "Guts Scroll",
    1205: "Wit Scroll",
    2001: "Vita 20",
    2002: "Vita 40",
    2003: "Vita 65",
    2101: "Royal Kale Juice",
    2201: "Energy Drink MAX",
    2202: "Energy Drink MAX EX",
    2301: "Plain Cupcake",
    2302: "Berry Sweet Cupcake",
    3001: "Yummy Cat Food",
    3101: "Grilled Carrots",
    4001: "Pretty Mirror",
    4002: "Reporter's Binoculars",
    4003: "Master Practice Guide",
    4004: "Scholar's Hat",
    4101: "Fluffy Pillow",
    4102: "Pocket Planner",
    4103: "Rich Hand Cream",
    4104: "Smart Scale",
    4105: "Aroma Diffuser",
    4106: "Practice Drills DVD",
    4201: "Miracle Cure",
    5001: "Speed Training Application",
    5002: "Stamina Training Application",
    5003: "Power Training Application",
    5004: "Guts Training Application",
    5005: "Wit Training Application",
    7001: "Reset Whistle",
    8001: "Coaching Megaphone",
    8002: "Motivating Megaphone",
    8003: "Empowering Megaphone",
    9001: "Speed Ankle Weights",
    9002: "Stamina Ankle Weights",
    9003: "Power Ankle Weights",
    9004: "Guts Ankle Weights",
    10001: "Good-Luck Charm",
    11001: "Artisan Cleat Hammer",
    11002: "Master Cleat Hammer",
    11003: "Glow Sticks",
}

DISPLAY_TO_ID = {v: k for k, v in ITEM_NAMES.items()}

SLUG_TO_DISPLAY = {name.lower().replace("'", "").replace(" ", "_"): name for name in ITEM_NAMES.values()}

SHOP_ITEM_COSTS = {
    "Speed Notepad": 10, "Stamina Notepad": 10, "Power Notepad": 10, "Guts Notepad": 10, "Wit Notepad": 10,
    "Speed Manual": 15, "Stamina Manual": 15, "Power Manual": 15, "Guts Manual": 15, "Wit Manual": 15,
    "Speed Scroll": 30, "Stamina Scroll": 30, "Power Scroll": 30, "Guts Scroll": 30, "Wit Scroll": 30,
    "Vita 20": 35, "Vita 40": 55, "Vita 65": 75, "Royal Kale Juice": 70,
    "Energy Drink MAX": 30, "Energy Drink MAX EX": 50,
    "Plain Cupcake": 30, "Berry Sweet Cupcake": 55,
    "Yummy Cat Food": 10, "Grilled Carrots": 40,
    "Pretty Mirror": 150, "Reporter's Binoculars": 150, "Master Practice Guide": 150, "Scholar's Hat": 280,
    "Fluffy Pillow": 15, "Pocket Planner": 15, "Rich Hand Cream": 15, "Smart Scale": 15,
    "Aroma Diffuser": 15, "Practice Drills DVD": 15, "Miracle Cure": 40,
    "Speed Training Application": 150, "Stamina Training Application": 150,
    "Power Training Application": 150, "Guts Training Application": 150, "Wit Training Application": 150,
    "Reset Whistle": 20,
    "Coaching Megaphone": 40, "Motivating Megaphone": 55, "Empowering Megaphone": 70,
    "Speed Ankle Weights": 50, "Stamina Ankle Weights": 50, "Power Ankle Weights": 50, "Guts Ankle Weights": 50,
    "Good-Luck Charm": 40,
    "Artisan Cleat Hammer": 25, "Master Cleat Hammer": 40,
    "Glow Sticks": 15,
}

AILMENT_CURE_MAP = {
    "Night Owl": "Fluffy Pillow",
    "Slacker": "Pocket Planner",
    "Skin Outbreak": "Rich Hand Cream",
    "Slow Metabolism": "Smart Scale",
    "Migraine": "Aroma Diffuser",
    "Practice Poor": "Practice Drills DVD",
}

BAD_EFFECT_NAMES = {
    1: "Night Owl",
    2: "Slacker",
    3: "Skin Outbreak",
    4: "Slow Metabolism",
    5: "Migraine",
    6: "Practice Poor",
}

AILMENT_CURE_ALL = "Miracle Cure"

CURE_ITEMS = set(AILMENT_CURE_MAP.values()) | {AILMENT_CURE_ALL}

# v5 smart-shop guardrails: buy toward usefulness,
# not toward a museum shelf. Most items cap at 5, one-shot cures cap lower.
DEFAULT_INVENTORY_CAP = 5
ITEM_INVENTORY_CAPS = {
    "Fluffy Pillow": 1,
    "Pocket Planner": 1,
    "Smart Scale": 1,
    "Aroma Diffuser": 1,
    "Practice Drills DVD": 1,
    "Pretty Mirror": 1,
    "Reporter's Binoculars": 1,
    "Master Practice Guide": 1,
    "Scholar's Hat": 1,
    "Good-Luck Charm": 3,
    "Reset Whistle": 5,
    "Coaching Megaphone": 5,
    "Motivating Megaphone": 5,
    "Empowering Megaphone": 5,
    # P1: anklets/weights over-buy left ~3 unused per run.  Cap each type at 3
    # (the per-name cap), with a combined "keep ~2 main +1 sub" stock ceiling
    # enforced separately in _skip_buy via trackblazer_anklet_max_stock.
    "Speed Ankle Weights": 3,
    "Stamina Ankle Weights": 3,
    "Power Ankle Weights": 3,
    "Guts Ankle Weights": 3,
}

INSTANT_USE_ITEMS = [
    "Grilled Carrots",
    "Yummy Cat Food",
    "Energy Drink MAX EX",
    "Pretty Mirror",
    "Scholar's Hat",
    "Reporter's Binoculars",
    "Master Practice Guide",
    "Speed Notepad", "Stamina Notepad", "Power Notepad", "Guts Notepad", "Wit Notepad",
    "Speed Manual", "Stamina Manual", "Power Manual", "Guts Manual", "Wit Manual",
    "Speed Scroll", "Stamina Scroll", "Power Scroll", "Guts Scroll", "Wit Scroll",
    "Speed Training Application", "Stamina Training Application",
    "Power Training Application", "Guts Training Application", "Wit Training Application",
]

ONE_TIME_BUFF_ITEMS = {
    "Pretty Mirror",
    "Scholar's Hat",
    "Reporter's Binoculars",
    "Master Practice Guide",
}

ENERGY_ITEMS = {
    "Vita 20": 20,
    "Vita 40": 40,
    "Vita 65": 65,
    "Royal Kale Juice": 100,
}

# Lv5 summer-camp facility turns. MUST equal mant.RACE_VALUE_CAMP_TURNS (a test
# asserts parity): the strategy's summer all-out gate and the item layer reason
# about the same set of camp turns.
SUMMER_TRAINING_TURNS = frozenset({37, 38, 39, 40, 61, 62, 63, 64})

# Per-item ENERGY contribution of the dedicated energy-top-up consumables.
# The game owner confirmed Energy Drink MAX is a SMALL top-up item (value 5) that
# exists only to escape 0 energy before a race -- it is not a full Vita-class
# refill.  Vita 20/40/65 and Energy Drink MAX EX keep their established values.
# This registry is consulted by the pre-race "smallest sufficient energy item"
# logic so a tiny +5 EDM is preferred over a +20 Vita when both are owned.
ENERGY_VALUES = {
    "Energy Drink MAX": 5,
    "Energy Drink MAX EX": 100,
}

# Late-game whistle policy (turn >= 65): reroll the training with a Reset Whistle
# when the best available training's TOTAL stat gain falls below this threshold
# (i.e. the training is lackluster).  Configurable via mant_config.
DEFAULT_LATE_WHISTLE_LACKLUSTER_THRESHOLD = 30

# Global stat cap (Trackblazer: all five stats cap at 1200).  Used by the
# late-game "highest-priority NON-CAPPED stat" gates (R2 turn >= 71).
GLOBAL_STAT_CAP = 1200

# training_stat_priority list names -> the chara_info stat field + the
# TRAINING_COMMAND_MAIN_TARGET index used by the training command payload.
_STAT_FIELD_BY_NAME = {
    "speed": ("speed", 1),
    "stamina": ("stamina", 2),
    "power": ("power", 3),
    "guts": ("guts", 4),
    "wit": ("wiz", 5),
    "wiz": ("wiz", 5),
}

# Energy/vitality-restore items that live on the INSTANT_USE_ITEMS path.  These
# must be gated by the energy threshold (and the vital cap) instead of firing
# every turn -- otherwise the bot drinks an Energy Drink MAX EX at vital 95-112,
# wasting it well over the cap.  Mood-only items are intentionally excluded.
INSTANT_ENERGY_RESTORE_ITEMS = frozenset({"Energy Drink MAX EX"})

MEGAPHONE_TIERS = {
    "Coaching Megaphone": (1, 4),
    "Motivating Megaphone": (2, 3),
    "Empowering Megaphone": (3, 2),
}

TRAINING_TYPE_ANKLET = {
    101: "Speed Ankle Weights",
    601: "Speed Ankle Weights",
    105: "Stamina Ankle Weights",
    602: "Stamina Ankle Weights",
    102: "Power Ankle Weights",
    603: "Power Ankle Weights",
    103: "Guts Ankle Weights",
    604: "Guts Ankle Weights",
}

TRAINING_COMMAND_MAIN_TARGET = {
    101: 1,
    601: 1,
    105: 2,
    602: 2,
    102: 3,
    603: 3,
    103: 4,
    604: 4,
    106: 5,
    605: 5,
}

TRAINING_ITEM_DECK_TYPE_INDEX = {
    "Speed Ankle Weights": 0,
    "Stamina Ankle Weights": 1,
    "Power Ankle Weights": 2,
    "Guts Ankle Weights": 3,
    "Speed Training Application": 0,
    "Stamina Training Application": 1,
    "Power Training Application": 2,
    "Guts Training Application": 3,
    "Wit Training Application": 4,
}

DEFAULT_ITEM_TIERS = dict(tb_rules.TRACKBLAZER_SHOP_TIERS)


def display_to_slug(name):
    return str(name or "").lower().replace("'", "").replace(" ", "_")


def _cfg_num(cfg, key, default, cast=int):
    """0-safe config read.

    The historic ``int(cfg.get(key) or DEFAULT)`` idiom treats a configured 0 as
    "unset" (0 is falsy) and silently reverts to DEFAULT.  This broke user
    presets that set e.g. ``energy_recovery_threshold: 0``.  Read the value
    explicitly so an intentional 0 is honored; only fall back to DEFAULT when the
    key is absent or the value is None/blank/unparseable.
    """
    value = (cfg or {}).get(key, None)
    if value is None or value == "":
        return cast(default)
    try:
        return cast(value)
    except (TypeError, ValueError):
        return cast(default)


# Items that get auto-consumed before races where they give no benefit (e.g. a
# pre-New-Year race with no stamina penalty), wasting coins better spent on
# impactful items.  Never purchased unless mant_config.allow_wasteful_consumables
# is set true.  IDs: Yummy Cat Food 3001, Energy Drink MAX EX 2202, Reporter's
# Binoculars 4002, Master Practice Guide 4003.
ALWAYS_EXCLUDE_ITEM_IDS = (3001, 2202, 4002, 4003)
ALWAYS_EXCLUDE_SLUGS = frozenset(
    display_to_slug(ITEM_NAMES[item_id]) for item_id in ALWAYS_EXCLUDE_ITEM_IDS
)


MASTER_SHOP_CACHE = {}


def load_master_shop_core(base_dir):
    """Load master.mdb-derived MANT shop data exported by career_bot.master_data."""
    if not base_dir:
        return {}
    key = str(Path(base_dir))
    if key in MASTER_SHOP_CACHE:
        return MASTER_SHOP_CACHE[key]
    path = Path(base_dir) / "data" / "mant_shop_core.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        data = {}
    by_id = {}
    by_name = {}
    for row in data.get("items", []) if isinstance(data, dict) else []:
        try:
            item_id = int(row.get("item_id") or 0)
        except Exception:
            continue
        name = row.get("name") or ITEM_NAMES.get(item_id) or str(item_id)
        if item_id:
            by_id[item_id] = row
        if name:
            by_name[str(name)] = row
    result = {"raw": data, "by_id": by_id, "by_name": by_name}
    MASTER_SHOP_CACHE[key] = result
    return result


class MantItemManager:
    def __init__(self):
        self.used_buffs = set()
        self.failed_exchange_this_snapshot = set()
        self.failed_use_this_turn = set()
        self.current_turn = None
        self.used_whistle_turn = None
        self.shop_snapshot_key = None
        self.last_shop_check_turn = None
        self.recover_after_exchange_error = False
        self.recover_after_use_error = False
        self.last_buy_options = []
        self.last_buy_selected = []
        self.last_buy_attempt = []
        self.last_buy_result = {}
        self.last_use_options = []
        self.last_use_selected = []
        self.last_use_attempt = []
        self.last_use_result = {}
        self.last_pre_race_use_selected = []
        self.last_pre_race_use_attempt = []
        self.last_pre_race_use_result = {}
        self.buy_attempt_events = []
        self.use_attempt_events = []
        # Turn the most recent handle_pre_race() ran on (-1 = never). Lets the
        # runner's turn-debug record surface PRE-RACE item use (cleat hammers /
        # glow sticks) on race turns instead of the empty decision-phase selection.
        self._pre_race_ran_turn = -1
        self.guide_cache = None
        self.trackblazer_race_catalog_cache = {}

    def _guide(self, preset=None):
        base_dir = (preset or {}).get("_base_dir") or (preset or {}).get("base_dir")
        if not base_dir:
            base_dir = Path(__file__).resolve().parents[1]
        try:
            return load_guide(str(base_dir))
        except Exception:
            return load_guide(str(Path(__file__).resolve().parents[1]))

    def reset_scoped_failures(self):
        self.failed_exchange_this_snapshot = set()
        self.failed_use_this_turn = set()
        self.current_turn = None
        self.used_whistle_turn = None
        self.shop_snapshot_key = None
        self.last_shop_check_turn = None
        self.last_buy_options = []
        self.last_buy_selected = []
        self.last_buy_attempt = []
        self.last_buy_result = {}
        self.last_use_options = []
        self.last_use_selected = []
        self.last_use_attempt = []
        self.last_use_result = {}
        self.buy_attempt_events = []
        self.use_attempt_events = []

    def _set_turn(self, turn):
        turn = int(turn or 0)
        if self.current_turn != turn:
            self.current_turn = turn
            self.failed_use_this_turn = set()

    def _set_shop_snapshot(self, rows):
        key = tuple(
            (
                int(row.get("shop_item_id") or 0),
                int(row.get("item_id") or 0),
                int(row.get("coin_num") or 0),
                int(row.get("item_buy_num") or 0),
                int(row.get("limit_buy_count") or 0),
                int(row.get("limit_turn") or 0),
            )
            for row in rows or []
        )
        if self.shop_snapshot_key != key:
            self.shop_snapshot_key = key
            self.failed_exchange_this_snapshot = set()

    def handle(self, client, state, preset, best_command=None, status=None, race_planner=None):
        current = state
        # Per-turn (train/rest) path never suppresses energy items -- the year-end
        # energy skip is scoped to the pre-race path only (set in handle_pre_race).
        self._skip_energy_items = False
        self.recover_after_exchange_error = False
        current, bought = self.buy_shop_items(client, current, preset, race_planner, status)

        self.recover_after_use_error = False
        current, used = self.use_items(client, current, preset, best_command, status, race_planner)

        return current, bought, used

    def handle_pre_race(self, client, state, preset, payload, status=None, race_planner=None,
                        consecutive_race_position=1):
        # v2.1 R5: ``consecutive_race_position`` is the CURRENT race's 1-indexed
        # position in its consecutive-race chain (1 = first race of a new chain,
        # 2 = second, ...).  Threaded in from runner._race via the strategy's
        # _recent_race_chain_count helper (position = preceding_races + 1).  Used
        # to decide whether a 0-energy pre-race top-up is worth the item.
        self._consecutive_race_position = int(consecutive_race_position or 1)
        self.recover_after_exchange_error = False
        current, bought = self.buy_shop_items(client, state, preset, race_planner, status)

        # v2.1: year-end races (Hopeful Stakes ~t24, Arima ~t72, finale >=73) are
        # safe to chain into -- the year/career ends right after, so energy topped
        # up here is pure waste. Opt-in via Scenario Overrides
        # (mant_config.skip_energy_items_year_end). Scoped to THIS pre-race path so
        # per-turn training energy is unaffected. Restricted to {24,48,72,>=73}
        # (NOT 23/47/71, whose next turn is still a real training turn).
        _chara0 = (state.get("data") or {}).get("chara_info") or {}
        _turn0 = int(_chara0.get("turn") or 0)
        _mc0 = (preset or {}).get("mant_config") or {}
        self._skip_energy_items = (
            (bool(_mc0.get("skip_energy_items_year_end", False))
             and tb_rules.is_year_end_energy_waste_turn(_turn0))
            or _turn0 >= 71  # v2.1 R5: post-70 races cost no energy and carry no
                             # 0-energy punishment -> NO pre-race energy management.
                             # Suppresses the _energy_targets late-spend path too (it
                             # has no upper turn cutoff), which would otherwise still
                             # spend Vitas pre-race past turn 70.
        )

        self.recover_after_use_error = False
        # 2026-06-29: suppress the general (>0 threshold) energy-restore path on the
        # race turn -- a race only needs >0 energy, so pre-race energy is decided
        # SOLELY by the vital==0 rule below. Other pre-race items (mood/charm/mega/
        # anklet/hammers) are unaffected.
        current, instant_used = self.use_items(client, current, preset, None, status, race_planner, suppress_energy=True)
        data = current.get("data") or {}
        free = data.get("free_data_set") or {}
        chara = data.get("chara_info") or {}
        owned = self._owned_map(free)
        self.last_pre_race_use_selected = []
        self.last_pre_race_use_attempt = []
        self.last_pre_race_use_result = {}

        turn = int(chara.get("turn") or 0)
        self._set_turn(turn)
        self._pre_race_ran_turn = turn
        program_id = int((payload or {}).get("program_id") or 0)

        if not owned:
            self.last_pre_race_use_result = {"skip": "no_owned"}
            return current, instant_used

        targets = []

        vital = int(chara.get("vital") or 0)
        # 2026-06-29 doctrine: a race only needs >0 energy to avoid punishment, so
        # the SOLE pre-race energy spend is at exactly 0 energy -- same turn, before
        # the race (like a hammer) -- regardless of the race's position in a
        # consecutive chain. (turn>=71 and opt-in year-end are suppressed via
        # _skip_energy_items / the turn gate inside _prerace_energy_target.)
        energy_item = self._prerace_energy_target(owned, turn, vital)
        if energy_item:
            targets.append((energy_item, 1))

        targets.extend(self._trackblazer_race_item_targets(owned, turn, program_id, preset, race_planner))

        targets = self._merge_targets(targets, owned)
        self.last_pre_race_use_selected = [{"name": name, "item_id": DISPLAY_TO_ID.get(name), "use_num": count} for name, count in targets]
        if not targets:
            self.last_pre_race_use_result = {"skip": "no_targets"}
            return current, instant_used

        use_payload = []
        for name, count in targets:
            item_id = DISPLAY_TO_ID.get(name)
            if not item_id or item_id in self.failed_use_this_turn:
                continue
            item_count = int(owned.get(name) or 0)
            if item_count <= 0:
                continue
            use_payload.append({"item_id": item_id, "use_num": min(count, item_count), "current_num": item_count})

        if use_payload:
            self.last_pre_race_use_attempt = list(use_payload)
            event = {
                "turn": turn,
                "phase": "pre_race",
                "selected": list(self.last_pre_race_use_selected),
                "attempt": list(use_payload),
                "payload": list(use_payload),
                "result": {},
            }
            self.use_attempt_events.append(event)
            try:
                self.last_pre_race_use_result = client.use_items(use_payload, turn)
                current = self._merge_state(current, self.last_pre_race_use_result)
                self.last_pre_race_use_result = {"result": "ok", "turn": turn, "payload": use_payload}
                event["result"] = self.last_pre_race_use_result
                return current, instant_used + len(use_payload)
            except Exception as exc:
                print(f"Pre-Race Item Use Error at turn {turn}: {exc}")
                if "205" in str(exc):
                    for item in use_payload:
                        self.failed_use_this_turn.add(item["item_id"])
                self.last_pre_race_use_result = {"result": "failed", "turn": turn, "error": str(exc), "payload": use_payload}
                event["result"] = self.last_pre_race_use_result
                return current, instant_used

        return current, instant_used

    def _should_check_shop(self, current_turn, preset, data=None, status=None, race_planner=None):
        cfg = self._mant_cfg(preset)
        freq = int(cfg.get("trackblazer_shop_check_frequency") or 1)
        if freq <= 1:
            return True
        if self.last_shop_check_turn is None:
            return True
        if int(current_turn or 0) - int(self.last_shop_check_turn or 0) < freq:
            return False
        grades = cfg.get("trackblazer_shop_check_grades") or ["G1", "G2", "G3"]
        if isinstance(grades, str):
            grades = [part.strip().upper() for part in grades.split(",") if part.strip()]
        else:
            grades = [str(g).strip().upper() for g in grades]
        if not grades:
            return True
        # Best effort: use recent runner history if it includes a program id, otherwise allow.
        rows = []
        if isinstance(status, dict):
            rows = status.get("action_history") or []
        if not isinstance(rows, list) or not rows:
            return True
        latest = None
        for row in reversed(rows[-10:]):
            if not isinstance(row, dict):
                continue
            if "race" in str(row.get("action") or row.get("type") or "").lower():
                latest = row
                break
        if not latest or not race_planner:
            return True
        program_id = latest.get("program_id") or latest.get("race_program_id")
        if not program_id:
            return True
        try:
            info = race_planner._program_info(program_id)
            grade = tb_rules.normalize_grade(info.get("grade") or info.get("race_instance_id"))
            return grade in grades
        except Exception:
            return True

    def buy_shop_items(self, client, state, preset, race_planner=None, status=None):
        data = state.get("data") or {}
        free = data.get("free_data_set") or {}
        chara = data.get("chara_info") or {}
        current_turn = int(chara.get("turn") or 0)
        pickups = free.get("pick_up_item_info_array") or []
        self._set_turn(current_turn)
        self._set_shop_snapshot(pickups)
        cfg = self._mant_cfg(preset)
        tiers = cfg.get("item_tiers") or DEFAULT_ITEM_TIERS
        tier_count = int(cfg.get("tier_count") or 8)
        coin_val = free.get("coin_num")
        if coin_val is None:
            coin_val = free.get("gained_coin_num")
        budget = int(coin_val or 0)
        start_budget = budget
        self.last_buy_options = []
        self.last_buy_selected = []
        self.last_buy_attempt = []
        self.last_buy_result = {"mant_coin": budget}
        self.buy_attempt_events = []
        if not self._should_check_shop(current_turn, preset, data, status, race_planner):
            self.last_buy_result = {"skip": "shop_frequency_gate", "turn": current_turn, "last_shop_check_turn": self.last_shop_check_turn}
            return state, 0
        if not pickups:
            self.last_buy_result = {"skip": "no_pickups", "mant_coin": budget}
            return state, 0
        if budget <= 0:
            self.last_buy_result = {"skip": "no_mant_coin", "mant_coin": budget}
            return state, 0

        owned = self._owned_map(free)
        any_sale = any(int(row.get("coin_num") or 0) < int(row.get("original_coin_num") or 0) for row in pickups if int(row.get("original_coin_num") or 0) > 0)
        sale_modifier = 0.9 if any_sale else 1.0
        motivation = int(chara.get("motivation") or 3)
        non_rainbow_count = 0
        for row in chara.get("evaluation_info_array") or []:
            if int(row.get("target_id") or 0) in {1, 2, 3, 4, 5, 6} and int(row.get("evaluation") or 0) < 80:
                non_rainbow_count += 1
        bbq_threshold = int(cfg.get("bbq_unmaxxed_cards") or 3)
        bbq_shift = non_rainbow_count - bbq_threshold
        charm_owned = owned.get("Good-Luck Charm", 0)
        is_senior_or_later = current_turn > 48
        charm_stop_qty = self._item_cap("Good-Luck Charm", preset)
        charm_stop = charm_owned >= charm_stop_qty
        cupcake_names = {"Plain Cupcake", "Berry Sweet Cupcake"}
        total_cupcakes = sum(owned.get(n, 0) for n in cupcake_names)
        skip_cupcakes = total_cupcakes >= 2 or (is_senior_or_later and total_cupcakes >= 1) or motivation >= 5
        cupcake_shift = total_cupcakes - 1 if skip_cupcakes else 0
        active_ailments = self._active_bad_statuses(data)
        has_miracle = owned.get("Miracle Cure", 0) > 0

        available = []
        for row in pickups:
            shop_item_id = int(row.get("shop_item_id") or 0)
            item_id = int(row.get("item_id") or 0)
            name = ITEM_NAMES.get(item_id)
            if not name:
                continue
            cost = int(row.get("coin_num") or SHOP_ITEM_COSTS.get(name, 9999))
            limit_turn = int(row.get("limit_turn") or 0)
            limit = int(row.get("limit_buy_count") or 1)
            current_num = int(row.get("item_buy_num") or 0)
            skip_reason = None
            if shop_item_id <= 0 or shop_item_id in self.failed_exchange_this_snapshot:
                skip_reason = "failed_snapshot"
            elif limit_turn > 0 and limit_turn < current_turn:
                skip_reason = "expired"
            elif current_num >= limit:
                skip_reason = "limit_reached"
            elif self._skip_buy(name, owned, preset, current_turn, start_budget, data, race_planner):
                skip_reason = "skip_buy"
            official = (load_master_shop_core((preset or {}).get("_base_dir") or (preset or {}).get("base_dir")).get("by_id") or {}).get(item_id, {})
            self.last_buy_options.append({
                "name": name,
                "item_id": item_id,
                "shop_item_id": shop_item_id,
                "cost": cost,
                "official_master": bool(official),
                "official_effects": official.get("effects", []),
                "current_num": current_num,
                "limit": limit,
                "limit_turn": limit_turn,
                "turns_left": (limit_turn - current_turn) if limit_turn > 0 else None,
                "skip_reason": skip_reason,
            })
            if not skip_reason:
                available.append((name, row))

        if not available:
            self.last_buy_result = {"skip": "no_available", "mant_coin": budget}
            return state, 0

        effective_rows = []
        for name, row in available:
            slug = display_to_slug(name)
            base_t = int(tiers.get(slug) or 999)
            eff_t = base_t
            guide = self._guide(preset)
            shop_cfg = guide.get("shop_priorities") or {}
            immediate_stat_names = set(((shop_cfg.get("immediate_stat_items") or {}).get("names") or []))
            if name in immediate_stat_names:
                # Stats are excellent, but the Trackblazer race/item economy kit
                # still comes first.  Do not let guide data lift them above tier 2.
                eff_t = min(eff_t, max(2, int((shop_cfg.get("immediate_stat_items") or {}).get("tier") or 2)))
            fast_cfg = shop_cfg.get("fast_learner") or {}
            if cfg.get("enable_fast_learner_shop_boost", False) and name == fast_cfg.get("item", "Scholar's Hat") and current_turn <= int(fast_cfg.get("reserve_until_turn") or 64):
                eff_t = min(eff_t, int(fast_cfg.get("tier") or 1))
            # ---- Cure items: buy ONLY for an active bad condition -------------
            # v6.8: TRACKBLAZER_SHOP_TIERS lists cures at base tier 1, which made
            # Icarus pre-stock Miracle Cures / Rich Hand Cream with no condition
            # present (the "why do I have 2 cure-alls and a cream" complaint).
            # Gate them: a cure is top priority only when its condition is active
            # and not already covered; otherwise it is demoted out of the buy
            # list.  ``preemptive_cure_reserve: true`` (preset mant_config)
            # restores the old keep-one-cure-all/cream-on-hand behaviour.
            if name in CURE_ITEMS:
                cured_ailment = next(
                    (a for a in active_ailments if AILMENT_CURE_MAP.get(a) == name), None)
                is_cure_all = name == AILMENT_CURE_ALL
                needed_now = (
                    (cured_ailment is not None and not has_miracle and owned.get(name, 0) <= 0)
                    or (is_cure_all and active_ailments and not has_miracle)
                )
                if needed_now:
                    eff_t = 1
                elif (cfg.get("preemptive_cure_reserve", False)
                      and name in (AILMENT_CURE_ALL, "Rich Hand Cream")
                      and owned.get(name, 0) <= 0):
                    eff_t = 1
                else:
                    eff_t = 999  # no active condition -> do not stock cures
            if slug == "grilled_carrots":
                eff_t = min(eff_t, base_t - bbq_shift)
            elif slug == "good-luck_charm":
                eff_t = 999 if charm_stop else min(eff_t, base_t - charm_owned)
            elif slug in {"plain_cupcake", "berry_sweet_cupcake"}:
                eff_t = min(eff_t, base_t - cupcake_shift)
            elif slug in {"artisan_cleat_hammer", "master_cleat_hammer", "glow_sticks"}:
                eff_t = min(eff_t, base_t)
            effective_rows.append((max(1, eff_t), name, row))

        targets = []
        selected_ids = set()

        for tier in range(1, tier_count + 1):
            tier_rows = [(name, row) for eff_t, name, row in effective_rows if eff_t == tier and id(row) not in selected_ids]
            tier_rows.sort(key=lambda item: (
                int(item[1].get("limit_turn") or 99),
                -self._item_buy_value(item[0], item[1], owned, current_turn, start_budget, data, preset, race_planner),
                int(item[1].get("coin_num") or SHOP_ITEM_COSTS.get(item[0], 9999)),
            ))
            for name, row in tier_rows:
                cost = int(row.get("coin_num") or SHOP_ITEM_COSTS.get(name, 9999))
                remaining = budget - cost
                if remaining < 0:
                    continue
                threshold = 0
                thresholds = cfg.get("tier_thresholds") or {}
                if tier > 1 and current_turn <= 64:
                    raw_threshold = int(thresholds.get(str(tier), thresholds.get(tier, (tier - 1) * 50)) or 0)
                    threshold = int(raw_threshold * sale_modifier)
                floor = self._buy_floor(name, tier, current_turn, start_budget, budget, threshold, cfg)
                if remaining < floor:
                    continue
                targets.append(row)
                selected_ids.add(id(row))
                budget = remaining

        if not targets:
            self.last_buy_result = {"skip": "no_targets", "mant_coin": budget, "start_mant_coin": start_budget}
            return state, 0

        self.last_buy_selected = [{
            "name": ITEM_NAMES.get(int(row.get("item_id") or 0), ""),
            "item_id": int(row.get("item_id") or 0),
            "shop_item_id": int(row.get("shop_item_id") or 0),
            "cost": int(row.get("coin_num") or SHOP_ITEM_COSTS.get(ITEM_NAMES.get(int(row.get("item_id") or 0), ""), 9999)),
            "current_num": int(row.get("item_buy_num") or 0),
            "limit_turn": int(row.get("limit_turn") or 0),
        } for row in targets]

        payload = []
        for row in targets:
            sid = int(row.get("shop_item_id") or 0)
            if sid > 0 and sid not in self.failed_exchange_this_snapshot:
                payload.append({"shop_item_id": sid, "current_num": 0})

        if not payload:
            self.last_buy_result = {"skip": "empty_payload", "mant_coin": budget, "start_mant_coin": start_budget}
            return state, 0

        return self._exchange_batch(client, state, payload, current_turn)

    def _exchange_batch(self, client, state, payload, current_turn):
        if not payload:
            return state, 0

        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        source_turn = int(chara.get("turn") or 0)

        if source_turn != current_turn:
            self.last_buy_result = {"skip": "stale_turn_detected", "request_current_turn": current_turn, "source_state_turn": source_turn}
            return state, 0

        free = data.get("free_data_set") or {}
        coin_val = free.get("coin_num")
        if coin_val is None:
            coin_val = free.get("gained_coin_num")
        budget = int(coin_val or 0)

        valid_shop_rows = {int(row.get("shop_item_id") or 0): row for row in free.get("pick_up_item_info_array") or []}

        owned_by_id = {}
        for row in free.get("user_item_info_array") or []:
            owned_by_id[int(row.get("item_id") or 0)] = int(row.get("num") or row.get("current_num") or row.get("item_num") or 0)

        valid_payload = []
        attempt_items = []
        total_cost = 0
        for item in payload:
            shop_item_id = int(item.get("shop_item_id") or 0)
            if shop_item_id <= 0:
                continue
            shop_row = valid_shop_rows.get(shop_item_id)
            if not shop_row:
                continue
            cost = int(shop_row.get("coin_num") or SHOP_ITEM_COSTS.get(ITEM_NAMES.get(int(shop_row.get("item_id") or 0), ""), 9999))
            limit_turn = int(shop_row.get("limit_turn") or 0)
            if limit_turn > 0 and limit_turn < current_turn:
                continue
            if int(shop_row.get("item_buy_num") or 0) >= int(shop_row.get("limit_buy_count") or 1):
                continue
            if total_cost + cost > budget:
                continue
            total_cost += cost

            valid_payload.append({
                "shop_item_id": shop_item_id,
                "current_num": owned_by_id.get(int(shop_row.get("item_id") or 0), 0)
            })
            attempt_items.append({
                "shop_item_id": shop_item_id,
                "cost": cost,
                "current_num": owned_by_id.get(int(shop_row.get("item_id") or 0), 0)
            })

        if not valid_payload:
            self.last_buy_result = {"skip": "preflight_failed", "mant_coin": budget}
            return state, 0

        self.last_buy_attempt = list(valid_payload)
        event = {
            "turn": current_turn,
            "selected": list(self.last_buy_selected),
            "attempt": list(attempt_items),
            "payload": list(valid_payload),
            "result": {},
        }
        self.buy_attempt_events.append(event)
        try:
            result = client.exchange_items(valid_payload, current_turn)
            self.last_shop_check_turn = current_turn
            self.last_buy_result = {"result": "ok", "turn": current_turn, "payload": valid_payload}
            event["result"] = self.last_buy_result
            self.failed_exchange_this_snapshot = set()
            return self._merge_state(state, result), len(valid_payload)
        except Exception as e:
            print(f"Item Exchange Error at turn {current_turn}: {e}")
            if any(code in str(e) for code in ("201", "205", "208")):
                self.recover_after_exchange_error = True
            for item in valid_payload:
                self.failed_exchange_this_snapshot.add(int(item.get("shop_item_id") or 0))
            self.last_buy_result = {"result": "failed", "turn": current_turn, "error": str(e), "payload": valid_payload}
            event["result"] = self.last_buy_result
            return state, 0


    def _smallest_sufficient_prerace_energy(self, owned):
        """At 0 energy before a race, pick the SMALLEST SUFFICIENT energy item to
        escape 0 (doctrine: a race only needs >0 energy; any energy item works).
        Energy Drink MAX (+5) is the small dedicated top-up -- preferred -- then
        the smallest Vita; Energy Drink MAX EX (+100 full refill) is the wasteful
        last resort so a 0-energy race is never left unrescued. Returns the item
        name or None when no energy item is owned."""
        if int(owned.get("Energy Drink MAX", 0) or 0) > 0:
            return "Energy Drink MAX"
        # Smallest Vita first (Vita 20 < Vita 40 < Vita 65).
        for name in ("Vita 20", "Vita 40", "Vita 65"):
            if int(owned.get(name, 0) or 0) > 0:
                return name
        # Last resort: the full-refill instant item, so 0 energy is always escaped.
        if int(owned.get("Energy Drink MAX EX", 0) or 0) > 0:
            return "Energy Drink MAX EX"
        return None

    def _prerace_energy_target(self, owned, turn, vital):
        """2026-06-29 doctrine: a race only needs >0 energy. Return the smallest
        sufficient energy item ONLY when vital is exactly 0 (any consecutive-race
        position), else None. Suppressed for post-70 races (no punishment) and for
        opt-in year-end skip via _skip_energy_items."""
        if (getattr(self, "_skip_energy_items", False)
                or int(turn or 0) >= 71
                or int(vital or 0) > 0):
            return None
        return self._smallest_sufficient_prerace_energy(owned)

    def _trackblazer_race_item_targets(self, owned, turn, program_id, preset, race_planner):
        info = self._program_race_info(program_id, race_planner)
        grade = tb_rules.normalize_grade(info.get("grade") or info.get("race_instance_id"))
        fans = int(info.get("fans") or 0)
        cfg = self._mant_cfg(preset)
        targets = []

        # P0: climax/finale rows have race_instance_id starting "92" and no grade
        # field, so normalize_grade now yields "CLIMAX".  Detect either signal and
        # let _hammer_target_for_race swing unconditionally on these races.
        is_climax = grade == "CLIMAX" or str(info.get("race_instance_id") or "").startswith("92")

        if not is_climax and (not grade or grade in {"OP", "PRE-OP", "800", "900"}):
            return targets
        if turn < 13:
            return targets

        hammer = self._hammer_target_for_race(owned, turn, grade, cfg, is_climax=is_climax)
        if hammer:
            targets.append((hammer, 1))

        if self._should_use_glow_stick(owned, turn, grade, fans, cfg):
            targets.append(("Glow Sticks", 1))
        return targets

    def _program_race_info(self, program_id, race_planner):
        if not race_planner or not program_id:
            return {}
        pid = int(program_id or 0)
        info = {}
        info.update((race_planner.program or {}).get(pid) or {})
        info.update((getattr(race_planner, "official_races", {}) or {}).get(pid) or {})
        name = str(info.get("name") or "").strip()
        if name and not info.get("fans"):
            catalog = self._trackblazer_race_catalog(getattr(race_planner, "base_dir", None))
            rows = catalog.get(self._race_name_key(name), [])
            turn = int(info.get("turn") or 0)
            match = None
            if turn:
                for row in rows:
                    if int(row.get("turn") or 0) == turn:
                        match = row
                        break
            if not match and rows:
                match = rows[0]
            if match:
                info.setdefault("fans", int(match.get("fans") or 0))
                info.setdefault("grade", match.get("grade") or info.get("grade"))
                info.setdefault("distance", match.get("distance") or info.get("distance"))
                info.setdefault("surface", match.get("surface") or info.get("terrain"))
        return info

    def _trackblazer_race_catalog(self, base_dir):
        key = str(base_dir or "")
        if key in self.trackblazer_race_catalog_cache:
            return self.trackblazer_race_catalog_cache[key]
        result = {}
        if base_dir:
            path = Path(base_dir) / "data" / "trackblazer" / "races.json"
            try:
                rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            except Exception:
                rows = []
            for row in rows if isinstance(rows, list) else []:
                name = self._race_name_key(row.get("name"))
                if name:
                    result.setdefault(name, []).append(row)
        self.trackblazer_race_catalog_cache[key] = result
        return result

    def _race_name_key(self, name):
        return "".join(ch.lower() for ch in str(name or "") if ch.isalnum())

    def _hammer_target_for_race(self, owned, turn, grade, cfg, is_climax=False):
        master_qty = int(owned.get("Master Cleat Hammer", 0) or 0)
        artisan_qty = int(owned.get("Artisan Cleat Hammer", 0) or 0)
        if master_qty + artisan_qty <= 0:
            return None

        is_final_race = turn >= tb_rules.TRACKBLAZER_FINAL_RACE_TURN
        conservation = turn >= tb_rules.RACE_ITEM_CONSERVATION_START_TURN

        # P0: CLIMAX/finale race -> swing the best hammer unconditionally.  This is
        # the payoff for the conservation reserves enforced on regular G1s below.
        if is_climax or grade == "CLIMAX":
            if master_qty > 0:
                return "Master Cleat Hammer"
            if artisan_qty > 0:
                return "Artisan Cleat Hammer"
            return None

        if grade not in {"G1", "G2", "G3"}:
            return None

        total = master_qty + artisan_qty

        # Before conservation opens (or on the final race):
        # G1 always swings the best it has (Artisan is always considered for a G1).
        # G2/G3 respect the configured per-grade Artisan min-stock threshold (spec,
        # Medium) so early-season races like Niigata Junior Stakes (turn 16) do NOT
        # swing freely below the user's floor. Masters are never spent here (banked
        # for the climax / G1s).
        if not conservation or is_final_race:
            if grade == "G1":
                if master_qty > 0:
                    return "Master Cleat Hammer"
                if artisan_qty > 0:
                    return "Artisan Cleat Hammer"
                return None
            if artisan_qty > 0:
                if grade == "G2" and artisan_qty < _cfg_num(cfg, "trackblazer_artisan_hammer_min_stock_for_g2", 0):
                    return None
                if grade == "G3" and artisan_qty < _cfg_num(cfg, "trackblazer_artisan_hammer_min_stock_for_g3", 0):
                    return None
                return "Artisan Cleat Hammer"
            return None

        # v2.0: during conservation, bank exactly `finale_reserve` hammers
        # (Master-preferred) for the 3 climax races; spend any SURPLUS on regular
        # graded races, weakest (Artisan) first, so Masters stay for the climax and
        # nothing is stranded unused at career end.
        # v2.1: the finale reserve + per-grade Artisan gates are configurable via
        # the Item Conservation sliders. Defaults preserve v2.0 behavior (reserve
        # DEFAULT_HAMMER_FINALE_RESERVE; no per-grade Artisan minimum). The legacy
        # trackblazer_hammer_finale_reserve key is still honored as a fallback.
        finale_reserve = _cfg_num(cfg, "trackblazer_master_hammer_finale_reserve",
                                  _cfg_num(cfg, "trackblazer_hammer_finale_reserve",
                                           tb_rules.DEFAULT_HAMMER_FINALE_RESERVE))
        # Spec (High): Artisan Hammers are ALWAYS considered for a G1, independent
        # of BOTH the G3/G2 min-stock threshold AND this finale-reserve bank that
        # gates G2/G3 below. Spend an Artisan if any is owned (banking Masters for
        # the climax); only dip into a SURPLUS Master when no Artisan is available,
        # so the climax reserve stays protected. (Master-on-G1 behavior is left as
        # the prior surplus-only design -- the spec only frees Artisan for G1.)
        if grade == "G1":
            if artisan_qty > 0:
                return "Artisan Cleat Hammer"
            if total > finale_reserve and master_qty > 0:
                return "Master Cleat Hammer"
            return None
        if total <= finale_reserve:
            return None
        reserved_master = min(master_qty, finale_reserve)
        surplus_master = master_qty - reserved_master
        surplus_artisan = max(0, artisan_qty - max(0, finale_reserve - reserved_master))
        if surplus_artisan > 0:
            # Don't drain the Artisan bank on weaker graded races below the
            # configured minimum stock (default 0 = no gate).
            if grade == "G2" and artisan_qty < _cfg_num(cfg, "trackblazer_artisan_hammer_min_stock_for_g2", 0):
                return None
            if grade == "G3" and artisan_qty < _cfg_num(cfg, "trackblazer_artisan_hammer_min_stock_for_g3", 0):
                return None
            return "Artisan Cleat Hammer"
        # Only G1 may dip into surplus Masters; G2/G3 never spend a Master (saved
        # for the climax / G1s).
        if grade == "G1" and surplus_master > 0:
            return "Master Cleat Hammer"
        return None

    def _should_use_glow_stick(self, owned, turn, grade, fans, cfg):
        qty = int(owned.get("Glow Sticks", 0) or 0)
        # v1.5: allow G1/G2/G3 (was G1-only), using a grade-agnostic
        # glow-stick use.  The effective-fan floor below still gates out small
        # races, so this only adds the big-fan G2/G3 races to the fan boost.
        allowed_grades = cfg.get("glow_stick_grades") or ("G1", "G2", "G3")
        if qty <= 0 or grade not in allowed_grades:
            return False
        is_finale = turn in tb_rules.TRACKBLAZER_FINALE_RACE_TURNS
        is_final_race = turn >= tb_rules.TRACKBLAZER_FINAL_RACE_TURN
        min_fans = _cfg_num(cfg, "trackblazer_glow_stick_min_fans", tb_rules.DEFAULT_GLOW_STICK_MIN_FANS)
        # Glow-stick fan gate.  The solver compares the race's ACTUAL fan
        # gain against the 20000 threshold (DEFAULT_GLOW_STICK_MIN_FANS).  The
        # only fan figure we have here is ``fans`` = the race's fan reward from
        # the race catalog / race_map, which IS the real awarded-fan figure for
        # the race (not a separate "base" number).  The old code multiplied it by
        # an arbitrary x2.0 fudge to fabricate an "effective" value, which made
        # the gate fire on the wrong races.  Compare the real fan figure directly
        # (multiplier defaults to 1.0 now); the knob stays tunable for anyone who
        # wants to re-scale.
        fan_mult = _cfg_num(cfg, "glow_stick_fan_multiplier", 1.0, cast=float)
        eff_fans = int(fans * fan_mult) if fans else 0

        # LATE/FINALE DUMP (fixes "not used at all if bought after turn 72"): in
        # the finale or once past the late-dump turn (item-strategy doctrine:
        # dump items after turn 64, unless save_items_lategame), spend it
        # regardless of the fan figure or the final-reserve -- a glow stick held
        # back to the very last turn is pure waste. This deliberately overrides
        # the reserve, which previously trapped a single late-bought glow stick.
        dump_late = is_final_race or is_finale or (
            (not cfg.get("save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME))
            and turn > 64
        )
        if dump_late:
            return True

        # Early phase (before conservation): use on big OR unknown-fan races.
        if turn < tb_rules.RACE_ITEM_CONSERVATION_START_TURN:
            return (eff_fans == 0) or eff_fans >= min_fans

        # Conservation phase (turns 25-64): require a KNOWN fan figure at/above
        # the threshold. eff_fans == 0 means the race's fan reward is UNKNOWN ->
        # do NOT spend (this was the path that mis-fired on an 11k race whose
        # catalog fan figure read 0, the "used at 11k when set to 20k" bug).
        if eff_fans < min_fans:
            return False
        if eff_fans >= tb_rules.TOP_TIER_G1_GLOW_FAN_FLOOR:
            return True
        reserve = _cfg_num(cfg, "trackblazer_glow_stick_final_reserve", tb_rules.DEFAULT_GLOW_STICK_FINAL_RESERVE)
        return qty > reserve



    def use_items(self, client, state, preset, best_command=None, status=None, race_planner=None, suppress_energy=False):
        data = state.get("data") or {}
        free = data.get("free_data_set") or {}
        chara = data.get("chara_info") or {}
        owned = self._owned_map(free)
        current_turn = int(chara.get("turn") or 0)
        self._set_turn(current_turn)
        self.last_use_options = []
        self.last_use_selected = []
        self.last_use_attempt = []
        self.last_use_result = {}
        self.use_attempt_events = []
        if not owned:
            self.last_use_result = {"skip": "no_owned"}
            return state, 0
        # Energy gate for the instant-use energy-restore items (Energy Drink MAX
        # EX): root cause of the "fires every turn at vital 95-112" bug was that
        # the instant-use loop queued these unconditionally.  Reuse the same
        # 0-safe energy_recovery_threshold and never overcap past max vital.
        _energy_cfg = self._mant_cfg(preset)
        _energy_threshold = _cfg_num(_energy_cfg, "energy_recovery_threshold", tb_rules.DEFAULT_ENERGY_RECOVERY_THRESHOLD)
        if current_turn in (35, 59):
            _energy_threshold = max(_energy_threshold, _cfg_num(_energy_cfg, "pre_camp_energy_threshold", 65))
        _vital = int(chara.get("vital") or 0)
        _max_vital = max(1, int(chara.get("max_vital") or 100))

        # Doctrine (2026-06-29): energy/recovery items are only worth using when
        # THIS turn's chosen action is TRAINING (command_type 1) and energy is the
        # limiter -- NEVER as a top-up on a rest/recreation/medic turn, and never
        # on the pre-race general pass (suppress_energy=True; the 0-energy pre-race
        # rule in handle_pre_race is the sole pre-race energy decision). Late-game
        # dump (turn>64, save_items_lategame off) still empties energy items on any
        # turn so nothing is stranded at career end.
        _is_training_turn = int((best_command or {}).get("command_type") or 0) == 1
        _dump_late_energy = (not _energy_cfg.get(
            "save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME)) and current_turn > 64
        _allow_energy_restore = (_is_training_turn or _dump_late_energy) and not suppress_energy

        targets = []
        for name in INSTANT_USE_ITEMS:
            qty = owned.get(name, 0)
            if qty <= 0:
                continue
            if DISPLAY_TO_ID.get(name) in self.failed_use_this_turn:
                continue
            if name in INSTANT_ENERGY_RESTORE_ITEMS:
                # v2.1: skip pre-race energy restore on year-end race turns (waste).
                if getattr(self, "_skip_energy_items", False):
                    continue
                # 2026-06-29: only on training turns (or late dump) -- not rest.
                if not _allow_energy_restore:
                    continue
                # Only drink when actually low on energy, and never over the cap.
                if _vital >= _max_vital or _vital >= _energy_threshold:
                    continue
                targets.append((name, 1))
                continue
            if name in ONE_TIME_BUFF_ITEMS:
                if name in self.used_buffs:
                    continue
                targets.append((name, 1))
            else:

                targets.append((name, qty))

        # 2026-06-29: late-game dump for the small +5 "Energy Drink MAX" (non-EX).
        # It has NO other training-turn use (only the 0-energy pre-race rescue), so
        # past turn 64 it strands otherwise. Dump one per turn while below max vital;
        # never on the pre-race general pass (suppress_energy) or a year-end skip.
        if (_dump_late_energy and not suppress_energy
                and not getattr(self, "_skip_energy_items", False)
                and int(owned.get("Energy Drink MAX", 0) or 0) > 0
                and _vital < _max_vital
                and DISPLAY_TO_ID.get("Energy Drink MAX") not in self.failed_use_this_turn):
            targets.append(("Energy Drink MAX", 1))

        whistle = self._whistle_target(best_command, owned, preset, status, current_turn)
        # 2026-06-29: a Reset Whistle turn IS a training turn. Outside the late-game
        # dump it stays exclusive (its reroll is the turn's action). But in dump mode
        # (turn>64, save_items_lategame off) it must NOT short-circuit the megaphone/
        # anklet/charm block -- that stranded leftover megaphones (T69 confirmed). So
        # keep the whistle AND fall through to also dump the rest on the same turn.
        if whistle and not _dump_late_energy:
            targets = [whistle]
        else:
            if whistle:
                targets.append(whistle)
            charm = self._charm_target(best_command, owned, preset, status, current_turn)
            save_energy_under_charm = bool((preset or {}).get("save_energy_under_charm", True))
            # Late-game dump: past turn 64 (unless save_items_lategame) a charm and
            # an energy item on the same turn is not wasteful -- the goal is to
            # empty the inventory, and vitality is deducted after the protected
            # training resolves -- so don't reserve energy under the charm.
            if (not _energy_cfg.get("save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME)) and current_turn > 64:
                save_energy_under_charm = False

            if not (charm and save_energy_under_charm) and _allow_energy_restore:
                targets.extend(self._energy_targets(chara, owned, preset, best_command, status))
            targets.extend(self._ailment_cure_targets(data, owned))

            kale_queued = any(name == "Royal Kale Juice" for name, _ in targets)
            mood_target = self._mood_target(chara, owned, preset, kale_queued)
            if mood_target:
                targets.append(mood_target)

            if charm:
                targets.append(charm)
                # A Good-Luck Charm guarantees the training succeeds regardless of
                # energy, so energy items spent this same turn are wasted on a turn
                # that was already safe. Drop them so they can be saved for an
                # unprotected low-energy turn. Opt out with save_energy_under_charm=false.
                if save_energy_under_charm:
                    targets = [t for t in targets if t[0] not in ENERGY_ITEMS]
            mega = self._megaphone_target(state, best_command, owned, preset, status, current_turn, race_planner)
            if mega:
                targets.append(mega)
            anklet = self._anklet_target(state, best_command, owned, preset)
            if anklet:
                targets.append(anklet)

        targets = self._merge_targets(targets, owned)
        selected_names = {name for name, _ in targets}
        for name, count in sorted(owned.items()):
            item_id = DISPLAY_TO_ID.get(name)
            if not item_id or count <= 0:
                continue
            failed = item_id in self.failed_use_this_turn
            selected = name in selected_names and not failed
            reason = None if selected else ("failed_this_turn" if failed else "not_useful_now")
            self.last_use_options.append({
                "name": name,
                "item_id": item_id,
                "current_num": int(count),
                "selected": selected,
                "skip_reason": reason,
                "reason": "selected" if selected else reason,
                "turn": current_turn,
                "context": {
                    "command_type": int((best_command or {}).get("command_type") or 0),
                    "command_id": int((best_command or {}).get("command_id") or 0),
                    "command_group_id": int((best_command or {}).get("command_group_id") or 0),
                },
            })
        if not targets:
            self.last_use_result = {"skip": "no_targets"}
            return state, 0

        payload = []
        valid_targets = []
        for name, count in targets:
            item_id = DISPLAY_TO_ID.get(name)
            if not item_id or item_id in self.failed_use_this_turn:
                continue
            have = int(owned.get(name) or 0)
            if have < count or have <= 0:
                continue

            valid_targets.append((name, count))
            payload.append({
                "item_id": item_id,
                "use_num": count,
                "current_num": have
            })

        if not payload:
            self.last_use_result = {"skip": "empty_payload"}
            return state, 0

        self.last_use_selected = [{"name": name, "item_id": DISPLAY_TO_ID.get(name), "use_num": count} for name, count in valid_targets]
        self.last_use_attempt = list(payload)
        event = {
            "turn": current_turn,
            "phase": "decision",
            "selected": list(self.last_use_selected),
            "attempt": list(payload),
            "payload": list(payload),
            "result": {},
        }
        self.use_attempt_events.append(event)
        try:
            res = client.use_items(payload, current_turn)
            self.failed_use_this_turn = set()
            if any(name == "Reset Whistle" for name, _ in valid_targets):
                self.used_whistle_turn = current_turn
            for name, _ in valid_targets:
                if name in ONE_TIME_BUFF_ITEMS:
                    self.used_buffs.add(name)
            self.last_use_result = {"result": "ok", "turn": current_turn, "payload": payload}
            event["result"] = self.last_use_result
            return self._merge_state(state, res), len(payload)
        except Exception as exc:
            print(f"Item Use Error at turn {current_turn}: {exc}")
            if any(code in str(exc) for code in ("201", "205", "208")):
                self.recover_after_use_error = True
                for item in payload:
                    self.failed_use_this_turn.add(int(item.get("item_id") or 0))
            self.last_use_result = {"result": "failed", "turn": current_turn, "error": str(exc), "payload": payload}
            event["result"] = self.last_use_result
            return state, 0

    def _merge_state(self, state, res):
        if res and isinstance(res, dict) and "data" in res:
            if not state: state = {}
            if "data" not in state: state["data"] = {}
            for k, v in res["data"].items():
                if isinstance(v, dict) and isinstance(state["data"].get(k), dict):
                    state["data"][k].update(v)
                else:
                    state["data"][k] = v
        return state

    def _is_instant_stat_item(self, name):
        slug = display_to_slug(name)
        return slug.endswith("_notepad") or slug.endswith("_manual") or slug.endswith("_scroll")

    def _coin_reserve(self, turn, budget, cfg):
        # v1.5+: BUY-TIME coin reserve removed -- spend down to ~0 at purchase
        # time to match the reference behavior, which holds NO buy-time hoard.  Unspent
        # coins were unbought glow sticks / hammers = fewer fans.  USE-TIME
        # reserves (finale hammer / glow-stick / min-stock floors) are SEPARATE
        # functions and are intentionally left untouched.  Still honors an
        # explicit mant_coin_reserve override if the user sets one.
        if "mant_coin_reserve" in (cfg or {}):
            return max(0, _cfg_num(cfg, "mant_coin_reserve", 0))
        # P0: pre-finale coin reserve.  Spend-to-zero is correct mid-career, but it
        # left the bot broke at the T73/74 finale shop where new hammers spawn.
        # Hold a reserve across the short pre-finale window so we arrive with money
        # to buy them.  Window/amount are config-overridable.
        start = _cfg_num(cfg, "trackblazer_finale_coin_reserve_start_turn", 65)
        end = _cfg_num(cfg, "trackblazer_finale_coin_reserve_end_turn", 73)
        if start <= int(turn or 0) <= end:
            reserve = max(0, _cfg_num(cfg, "trackblazer_finale_coin_reserve", 150))
            # Late-game dump mode: don't hoard coins for finals (finale races pay
            # no coins, and the only turn-71 must-buy is a ~55-coin Master Cleat
            # Hammer). Keep just enough to cover that, so surplus converts to items.
            if not cfg.get("save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME):
                reserve = min(reserve, _cfg_num(cfg, "trackblazer_finale_master_hammer_reserve", 60))
            return reserve
        return 0

    def _coin_cap(self, turn, cfg):
        if turn <= 20:
            return int(cfg.get("mant_coin_cap_t20", 999999))
        if turn <= 35:
            return int(cfg.get("mant_coin_cap_t35", 300))
        if turn <= 45:
            return int(cfg.get("mant_coin_cap_t45", 260))
        if turn <= 55:
            return int(cfg.get("mant_coin_cap_t55", 200))
        if turn <= 64:
            return int(cfg.get("mant_coin_cap_t64", 140))
        if turn <= 72:
            return int(cfg.get("mant_coin_cap_t72", 80))
        return int(cfg.get("mant_coin_cap_final", 0))

    def _buy_floor(self, name, tier, turn, start_budget, budget, threshold, cfg):
        reserve = self._coin_reserve(turn, start_budget, cfg)
        cap = self._coin_cap(turn, cfg)
        floor = max(int(threshold or 0), reserve) if tier > 1 else 0
        if self._is_instant_stat_item(name):
            if turn >= 46:
                return 0
            if turn >= 36 and start_budget > cap:
                return min(floor, 40)
            if start_budget > cap:
                return min(floor, reserve // 2)
            return min(floor, reserve)
        if turn >= 73:
            return 0
        if start_budget > cap:
            floor = min(floor, max(0, reserve // 2))
        if start_budget >= reserve + 400:
            floor = min(floor, max(0, reserve // 3))
        elif start_budget >= reserve + 250:
            floor = min(floor, max(0, reserve // 2))
        if turn >= 65:
            floor = min(floor, 40)
        elif turn >= 56:
            floor = min(floor, 80)
        elif turn >= 46:
            floor = min(floor, 120)
        # P0: re-assert the pre-finale coin reserve as a HARD floor.  The clamps
        # above (and the cap-based reductions) would otherwise shave it back down
        # to ~40 during turns 65-72, undoing the reserve and arriving broke at the
        # finale shop.  Only applies while the finale reserve window is active.
        f_start = _cfg_num(cfg, "trackblazer_finale_coin_reserve_start_turn", 65)
        f_end = _cfg_num(cfg, "trackblazer_finale_coin_reserve_end_turn", 73)
        if f_start <= int(turn or 0) <= f_end and not self._is_instant_stat_item(name):
            finale_reserve = max(0, _cfg_num(cfg, "trackblazer_finale_coin_reserve", 150))
            # Mirror _coin_reserve: in dump mode keep only the Master Cleat Hammer
            # floor, not the full 150-coin finale hoard.
            if not cfg.get("save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME):
                finale_reserve = min(finale_reserve, _cfg_num(cfg, "trackblazer_finale_master_hammer_reserve", 60))
            floor = max(floor, finale_reserve)
        return max(0, int(floor))

    def _mant_cfg(self, preset):
        cfg = dict((preset or {}).get("mant_config") or {})
        base_dir = (preset or {}).get("_base_dir") or (preset or {}).get("base_dir")
        master_shop = load_master_shop_core(base_dir)
        official_tiers = dict(DEFAULT_ITEM_TIERS)
        for name, row in (master_shop.get("by_name") or {}).items():
            slug = display_to_slug(name)
            if not slug:
                continue
            # Lower cost and direct-use items are generally higher priority.
            cost = int(row.get("coin_num") or SHOP_ITEM_COSTS.get(name, 999))
            use_flag = int(row.get("use_flag") or 0)
            effect_priority = int(row.get("effect_priority") or 0)
            tier = 8 if use_flag else 5
            if cost <= 20:
                tier = min(tier, 3)
            if effect_priority:
                tier = min(tier, max(1, 8 - effect_priority))
            official_tiers.setdefault(slug, tier)
            if cost > 0 and name not in SHOP_ITEM_COSTS:
                SHOP_ITEM_COSTS[name] = cost
        cfg.setdefault("item_tiers", official_tiers)
        cfg.setdefault("tier_count", 8)
        cfg.setdefault("tier_thresholds", {"3": 31, "7": 100, "8": 99999999999})
        cfg.setdefault("charm_failure_rate", tb_rules.DEFAULT_CHARM_FAILURE_THRESHOLD)
        cfg.setdefault("mega_small_threshold", 11)
        cfg.setdefault("mega_medium_threshold", 21)
        cfg.setdefault("mega_large_threshold", 35)
        cfg.setdefault("mega_late_buy_buffer", 5)
        cfg.setdefault("training_weights_threshold", 40)
        cfg.setdefault("energy_recovery_threshold", tb_rules.DEFAULT_ENERGY_RECOVERY_THRESHOLD)
        cfg.setdefault("trackblazer_energy_item_reserve", tb_rules.DEFAULT_ENERGY_ITEM_RESERVE)
        cfg.setdefault("trackblazer_cupcake_reserve", tb_rules.DEFAULT_CUPCAKE_RESERVE)
        cfg.setdefault("charm_min_main_gain", tb_rules.DEFAULT_CHARM_MIN_MAIN_GAIN)
        cfg.setdefault("trackblazer_skip_bad_mood_items_below_gain", tb_rules.DEFAULT_LOW_MOOD_ITEM_GAIN_FLOOR)
        cfg.setdefault("trackblazer_master_hammer_finale_reserve", tb_rules.DEFAULT_MASTER_HAMMER_FINALE_RESERVE)
        cfg.setdefault("trackblazer_artisan_hammer_min_stock_for_g3", tb_rules.DEFAULT_ARTISAN_HAMMER_MIN_STOCK_FOR_G3)
        cfg.setdefault("trackblazer_artisan_hammer_min_stock_for_g2", tb_rules.DEFAULT_ARTISAN_HAMMER_MIN_STOCK_FOR_G2)
        cfg.setdefault("trackblazer_glow_stick_final_reserve", tb_rules.DEFAULT_GLOW_STICK_FINAL_RESERVE)
        cfg.setdefault("trackblazer_glow_stick_min_fans", tb_rules.DEFAULT_GLOW_STICK_MIN_FANS)
        cfg.setdefault("glow_stick_fan_multiplier", 1.0)
        cfg.setdefault("late_whistle_lackluster_threshold", DEFAULT_LATE_WHISTLE_LACKLUSTER_THRESHOLD)
        return cfg

    def _owned_map(self, free):
        result = {}
        for row in free.get("user_item_info_array") or []:
            item_id = int(row.get("item_id") or 0)
            name = ITEM_NAMES.get(item_id)
            if name:

                qty = int(row.get("num") or row.get("current_num") or row.get("item_num") or 0)
                result[name] = result.get(name, 0) + qty
        return result

    def _active_bad_statuses(self, data):
        result = []
        for effect_id in (data.get("chara_info") or {}).get("chara_effect_id_array") or []:
            try:
                effect_id = int(effect_id)
            except (TypeError, ValueError):
                continue
            name = BAD_EFFECT_NAMES.get(effect_id)
            if name:
                result.append(name)
        return result


    def _ailment_cure_targets(self, data, owned):
        result = []
        active_ailments = self._active_bad_statuses(data)
        if not active_ailments:
            return result

        unhandled_ailments = []
        for ailment in active_ailments:
            cure = AILMENT_CURE_MAP.get(ailment)
            if cure and owned.get(cure, 0) > 0:
                result.append((cure, 1))
            else:
                unhandled_ailments.append(ailment)

        if unhandled_ailments and owned.get(AILMENT_CURE_ALL, 0) > 0:
            result.append((AILMENT_CURE_ALL, 1))
        return result

    def _energy_targets(self, chara, owned, preset, best_command=None, status=None):
        """Choose recovery items using Trackblazer conservation rules.

        Native Pre Icarus payloads already tell us vitality and inventory, so this
        is the standard policy without OCR: reserve one low-tier Vita, avoid
        over-healing past ~110%, and treat Royal Kale Juice as a guarded full
        restore because it costs motivation.
        """
        # v2.1: in the pre-race path on a year-end race turn, skip recovery items
        # entirely (energy is wasted -- the year/career ends right after the race).
        if getattr(self, "_skip_energy_items", False):
            return []
        # Late-game dump: after turn 64 (unless save_items_lategame) spend energy
        # items rather than stranding them at career end -- the small-gap floor
        # below would otherwise refuse a top-up on a nearly-full bar.
        _dump_late = ((not self._mant_cfg(preset).get(
            "save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME))
            and int(chara.get("turn") or 0) > 64)
        hp = int(chara.get("vital") or 0)
        max_hp = max(1, int(chara.get("max_vital") or 100))
        gap = max_hp - hp
        if gap < 20 and not _dump_late:
            return []

        cfg = self._mant_cfg(preset)
        # 0-safe: honor a user-set energy_recovery_threshold of 0.
        threshold = _cfg_num(cfg, "energy_recovery_threshold", tb_rules.DEFAULT_ENERGY_RECOVERY_THRESHOLD)
        turn = int(chara.get("turn") or 0)
        if turn in (35, 59):
            threshold = max(threshold, _cfg_num(cfg, "pre_camp_energy_threshold", 65))
        # v2.1 R3 late-game Vita policy:
        #  * turns 60-64 (summer peak): use Vitas freely (no conservation reserve).
        #  * turns >= 65: the energy-rescue path prefers energy items over resting,
        #    so relax the threshold toward max-vital -- whenever HP is meaningfully
        #    below max, spend an item rather than letting the strategy rest.
        _late_summer = 60 <= turn <= 64
        _late_spend = turn >= 65
        if _late_spend:
            threshold = max(threshold, max_hp - 10)
        # Never spend energy/recovery items once vital is already at/above the
        # threshold, and never overcap (waste) at/over max vital. In dump mode
        # the threshold is ignored (spend down to any non-full bar); the
        # hp>=max_hp / overshoot-cap guards still prevent pure overcap waste.
        if hp >= max_hp or (hp >= threshold and not _dump_late):
            return []

        # Charm turns should not spend recovery items; failure is already zero and
        # vitality is deducted after the training resolves.
        if (not _dump_late) and (preset or {}).get("save_energy_under_charm", True) and self._charm_target(best_command, owned, preset, status, turn):
            return []

        motivation = int(chara.get("motivation") or 3)
        if _late_summer or _late_spend:
            # R3: spend Vitas freely -- no low-tier reserve in the late game.
            reserve = 0
        else:
            reserve = max(0, _cfg_num(cfg, "trackblazer_energy_item_reserve", tb_rules.DEFAULT_ENERGY_ITEM_RESERVE))
        cupcake_reserve = max(0, _cfg_num(cfg, "trackblazer_cupcake_reserve", tb_rules.DEFAULT_CUPCAKE_RESERVE))
        # Spec (Low): the kale mood-offset must be patched with a PLAIN cupcake;
        # Berry Sweet is reserved for the mood/Recovery path. Only count kale as
        # "safe" when a Plain is actually available.
        has_plain_for_kale = self._available_cupcake(
            owned, reserve=cupcake_reserve, allow_reserved=True, kind="plain"
        ) == "Plain Cupcake"

        # Royal Kale is a full refill with a mood bite. Use it as the panic lever
        # at critical HP, or when a Plain cupcake can patch the mood loss.
        if owned.get("Royal Kale Juice", 0) > 0:
            critical = hp <= _cfg_num(cfg, "kale_critical_threshold", tb_rules.ENERGY_CRITICAL_KALE_THRESHOLD)
            safe_mood = has_plain_for_kale or motivation <= 1
            # The cupcake+kale combo is locked to summer turns. After turn 64
            # (dump mode) leftover kale is used as recovery instead of resting --
            # even with no cupcake on hand -- but only when there's a real bar to
            # refill (gap>=20 or critical) so a full kale is not wasted near max.
            # Outside summer mid-career the combo is held back.
            if _dump_late:
                if critical or gap >= 20:
                    return [("Royal Kale Juice", 1)]
            elif is_summer_turn(turn, self._guide(preset)) and (critical or safe_mood):
                return [("Royal Kale Juice", 1)]

        usable_vitas = self._usable_vita_counts(owned, reserve)
        if not usable_vitas:
            return []
        # 0-safe read; the small overshoot allowance lets a final Vita top-up land
        # near the cap, but the hp>=max_hp gate above already blocks pure overcap.
        ratio = _cfg_num(cfg, "energy_overshoot_cap_ratio", tb_rules.ENERGY_OVERSHOOT_CAP_RATIO, cast=float)
        target_cap = int(max_hp * ratio)
        picked = []
        total = hp
        # Greedy descending: the policy wants useful top-ups, not a tiny-item drip.
        for name, gain in sorted(tb_rules.VITA_GAINS.items(), key=lambda item: item[1], reverse=True):
            for _ in range(int(usable_vitas.get(name, 0) or 0)):
                if total + gain <= target_cap:
                    picked.append((name, 1))
                    total += gain
                if total >= max_hp:
                    return self._merge_targets(picked, owned)
        return self._merge_targets(picked, owned)

    def _usable_vita_counts(self, owned, reserve):
        counts = {name: int(owned.get(name, 0) or 0) for name in tb_rules.VITA_GAINS}
        if reserve <= 0:
            return counts
        for name in tb_rules.ENERGY_CONSERVATION_ORDER:
            if counts.get(name, 0) > 0:
                counts[name] = max(0, counts[name] - reserve)
                break
        return counts

    def _available_cupcake(self, owned, reserve=0, allow_reserved=False, kind=None):
        # kind=None     -> Berry-Sweet-first pick (mood recovery / Recreation
        #                  substitution): Berry Sweet is the mood resource.
        # kind="plain"  -> kale-juice mood offset ONLY: spend Plain Cupcake first,
        #                  fall back to Berry Sweet only if no Plain is available.
        if kind == "plain":
            order = ("Plain Cupcake", "Berry Sweet Cupcake")
        else:
            order = tb_rules.CUPCAKE_ORDER
        for name in order:
            qty = int(owned.get(name, 0) or 0)
            if qty <= 0:
                continue
            if not allow_reserved and qty <= int(reserve or 0):
                continue
            return name
        return None

    def _mood_target(self, chara, owned, preset=None, kale_queued=False):
        motivation = int(chara.get("motivation") or 3)
        hp = int(chara.get("vital") or 0)
        turn = int(chara.get("turn") or 0)
        cfg = self._mant_cfg(preset)
        reserve = max(0, _cfg_num(cfg, "trackblazer_cupcake_reserve", tb_rules.DEFAULT_CUPCAKE_RESERVE))
        threshold = _cfg_num(cfg, "cupcake_energy_threshold", 70)

        # v2.1 late-game cupcake policy (turn >= 60):
        #  * Past turn 59 Plain Cupcake is NOT held back for the kale-juice mood
        #    offset (the reserve that protects it mid-career no longer matters --
        #    few training turns remain, spend freely).
        #  * Use any cupcake for mood whenever motivation < 4.  Turns 60-64 and
        #    65+ share this branch; "any cupcake type" = allow_reserved so a kept-
        #    back copy is also eligible.
        late_game = turn >= 60
        # Late-game dump (after turn 64, unless save_items_lategame): spend
        # cupcakes for mood up to GREAT (mood<5), not just below GOOD (mood<4), so
        # leftover cupcakes are not stranded at career end. A cupcake at max mood
        # is still genuinely wasted, so that one stays excluded.
        _dump_late = (not cfg.get("save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME)) and turn > 64
        mood_ceiling = 5 if _dump_late else 4
        if late_game and motivation < mood_ceiling:
            cupcake = self._available_cupcake(owned, reserve=reserve, allow_reserved=True)
            if not cupcake:
                return None
            return (cupcake, 1)

        if not kale_queued:
            if motivation >= 5:
                return None
            # Keep cupcakes for low-energy training recovery / Kale offsets. If
            # energy is already comfortable, mood can usually wait.
            if hp >= threshold:
                return None
            # Non-kale mood path: Berry Sweet is the dedicated mood resource
            # (Berry-Sweet-first order).
            cupcake = self._available_cupcake(owned, reserve=reserve, allow_reserved=False)
        elif late_game:
            # R1: past turn 59 do NOT reserve Plain Cupcake for the kale offset.
            # Spend whatever cupcake is on hand (plain-first), but do not dip into
            # the protected reserve -- mid-career reservation is simply disabled.
            cupcake = self._available_cupcake(
                owned, reserve=0, allow_reserved=True, kind="plain"
            )
            if not cupcake:
                return None
        else:
            # Kale just lowered mood; patch it with a PLAIN cupcake (the kale
            # offset resource) so the full restore does not sabotage the training
            # turn AND Berry Sweet stays preserved for Recreation substitution.
            cupcake = self._available_cupcake(
                owned, reserve=reserve, allow_reserved=True, kind="plain"
            )
            if cupcake != "Plain Cupcake":
                # No Plain available -> do NOT burn a Berry Sweet on a kale offset.
                return None

        if not cupcake:
            return None
        if cupcake == "Plain Cupcake" and not kale_queued:
            needed = max(1, 5 - motivation)
            return ("Plain Cupcake", min(int(owned.get(cupcake) or 0), needed))
        return (cupcake, 1)

    def _whistle_target(self, best_command, owned, preset, status, turn):
        if owned.get("Reset Whistle", 0) <= 0:
            return None
        if int(turn or 0) < int(((preset or {}).get("mant_config") or {}).get("whistle_min_turn") or tb_rules.DEFAULT_WHISTLE_MIN_TURN):
            return None
        if self.used_whistle_turn == int(turn or 0):
            return None
        if not best_command or int(best_command.get("command_type") or 0) != 1:
            return None
        if best_command.get("_irregular_training") or str(best_command.get("_decision_reason") or "").lower().startswith("irregular training"):
            return None

        cfg = self._mant_cfg(preset)
        # v2.0: hold whistles for summer camp and the end-of-career stretch, where
        # they're used to reroll into turns worth spending megaphones + anklets on.
        # Don't burn them rerolling random mid-career turns.
        SUMMER = {36, 37, 38, 39, 40, 60, 61, 62, 63, 64}
        whistle_late_turn = int(_cfg_num(cfg, "whistle_late_turn", 65))
        if int(turn or 0) not in SUMMER and int(turn or 0) < whistle_late_turn:
            return None
        current_chara = None
        if isinstance(status, dict):
            current_chara = status.get("current_chara") or status.get("chara_info")
        current_chara = current_chara or {}
        vitality = int(current_chara.get("vital") or current_chara.get("current_vital") or 0)
        motivation = int(current_chara.get("motivation") or 3)
        # If the problem is obviously HP or mood, a reshuffle does not solve it.
        if vitality and vitality <= _cfg_num(cfg, "energy_recovery_threshold", tb_rules.DEFAULT_ENERGY_RECOVERY_THRESHOLD):
            return None
        if motivation <= _cfg_num(cfg, "whistle_motivation_floor", 2):
            return None

        total_gain = self._command_stat_gain(best_command, sp_weight=0.5)
        main_gain = self._command_main_stat_gain(best_command)
        failure = int(best_command.get("failure_rate") or 0)
        # v2.1 R4 late-game whistle policy:
        #  * turns 60-64 (summer): spend freely -- the existing poor_gain logic
        #    below already rerolls lackluster summer turns.
        #  * turns >= 65: reroll ONLY when the best training's TOTAL stat gain is
        #    below late_whistle_lackluster_threshold (default 30) -- i.e. the
        #    training is lackluster.  Above the threshold, CONSERVE the whistle.
        if int(turn or 0) >= 65:
            lackluster = _cfg_num(cfg, "late_whistle_lackluster_threshold", DEFAULT_LATE_WHISTLE_LACKLUSTER_THRESHOLD)
            if total_gain < int(lackluster):
                return ("Reset Whistle", 1)
            return None
        threshold = int(cfg.get("whistle_score_threshold") or tb_rules.DEFAULT_WHISTLE_SCORE_THRESHOLD)
        max_failure = int(cfg.get("whistle_max_failure") or tb_rules.DEFAULT_WHISTLE_MAX_FAILURE)
        # Genuine dead-turn definition: low total gain, low main gain, or an
        # unsafe failure rate without enough reward to justify Charm support.
        poor_gain = total_gain < threshold or main_gain < int(cfg.get("whistle_min_main_gain") or tb_rules.DEFAULT_LOW_MOOD_ITEM_GAIN_FLOOR)
        unsafe_failure = failure > max_failure and total_gain < int(cfg.get("whistle_force_safe_score") or tb_rules.DEFAULT_WHISTLE_FORCE_SAFE_SCORE)
        if int(turn or 0) <= 72 and (poor_gain or (unsafe_failure and cfg.get("whistle_forces_training", True))):
            return ("Reset Whistle", 1)
        return None

    def _charm_target(self, best_command, owned, preset, status, turn=0):
        if owned.get("Good-Luck Charm", 0) <= 0:
            return None
        if not best_command or int(best_command.get("command_type") or 0) != 1:
            return None
        fail_rate = int(best_command.get("failure_rate") or 0)
        cfg = self._mant_cfg(preset)
        _dump_late = (not cfg.get("save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME)) and int(turn or 0) > 64
        main_gain = self._command_main_stat_gain(best_command)
        # 2026-06-29: in dump mode (past turn 64) spend charms EXTREMELY aggressively
        # -- fire on ANY training that does SOMETHING, bypassing the failure /
        # main-gain / low-mood floors so leftovers don't strand at career end
        # (finale gives no coins). The ONLY skip is a literal 0%-failure AND 0-gain
        # pick, where a charm protects nothing and secures nothing (pure waste).
        if _dump_late:
            if fail_rate < 1 and main_gain < 1:
                return None
            return ("Good-Luck Charm", 1)

        # Normal (mid-career) charm policy below.
        threshold = _cfg_num(cfg, "charm_failure_rate", tb_rules.DEFAULT_CHARM_FAILURE_THRESHOLD)
        if fail_rate < threshold:
            return None

        min_gain = _cfg_num(cfg, "charm_min_main_gain", tb_rules.DEFAULT_CHARM_MIN_MAIN_GAIN)
        # Aggressiveness (fixes "fails despite high failure rate"): on a HIGH
        # failure-rate turn, protect even a modest-gain training -- a wasted-turn
        # failure costs the whole turn, so the gain bar shouldn't block the charm.
        high_fail = _cfg_num(cfg, "charm_failure_rate_high", tb_rules.DEFAULT_CHARM_FAILURE_RATE_HIGH)
        if fail_rate >= high_fail:
            min_gain = 1
        if main_gain < min_gain:
            return None

        low_mood_floor = _cfg_num(cfg, "trackblazer_skip_bad_mood_items_below_gain", tb_rules.DEFAULT_LOW_MOOD_ITEM_GAIN_FLOOR)
        current_chara = (status or {}).get("current_chara") if isinstance(status, dict) else {}
        motivation = int((current_chara or {}).get("motivation") or 3)
        if motivation <= 2 and main_gain < low_mood_floor and not _dump_late:
            return None
        return ("Good-Luck Charm", 1)

    def _rainbow_partner_count(self, best_command, current_chara):
        """Count friendship/rainbow partners on this training: support partners
        (slots 1-6) present whose bond is rainbow-ready (>=80)."""
        partners = (best_command or {}).get("training_partner_array") or []
        bonds = {}
        for ev in (current_chara or {}).get("evaluation_info_array") or []:
            try:
                bonds[int(ev.get("target_id") or 0)] = int(ev.get("evaluation") or 0)
            except Exception:
                pass
        n = 0
        for pid in partners:
            try:
                p = int(pid or 0)
            except Exception:
                continue
            if 1 <= p <= 6 and bonds.get(p, 0) >= 80:
                n += 1
        return n

    def _megaphone_target(self, state, best_command, owned, preset, status, turn, race_planner):
        if not best_command or int(best_command.get("command_type") or 0) != 1:
            return None

        data = state.get("data") or {}
        free_data = data.get("free_data_set") or {}
        item_effects = free_data.get("item_effect_array") or []
        current_mega_tier = self._active_megaphone_tier(state)

        score = self._command_stat_gain(best_command, sp_weight=0.5)
        cfg = self._mant_cfg(preset)
        # Late-game dump (after turn 64, unless save_items_lategame): in the
        # finale window (turn>=71) keep firing megaphones on any non-zero training
        # instead of hoarding them behind the priority-stat gate / fire_window.
        _dump_late = (not cfg.get("save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME)) and int(turn or 0) > 64
        # v2.1 late-game item policy windows (R2):
        #  * turns 60-64 (summer peak): fire on ANY non-zero training.
        #  * turns 65-70: stop conserving -- spend remaining stock on training.
        #  * turns >= 71: fire only when the training raises the current
        #    highest-priority NON-CAPPED stat.
        LATE_SUMMER = turn in {60, 61, 62, 63, 64}
        LATE_SPEND = 65 <= turn <= 70
        LATE_FINAL = turn >= 71
        small_threshold = float(cfg.get("mega_small_threshold") or 11)
        medium_threshold = float(cfg.get("mega_medium_threshold") or 21)
        large_threshold = float(cfg.get("mega_large_threshold") or 35)
        if LATE_SUMMER:
            # R2: "fire on ANY training (even a small gain)".  Drop thresholds to
            # ~0 so any non-zero score qualifies, AND (below) disable the summer
            # hold so strong megaphones are spent freely.
            small_threshold = 0.0
            medium_threshold = 0.0
            large_threshold = 0.0
        elif turn in {36, 37, 38, 39, 40}:
            small_threshold *= 0.82
            medium_threshold *= 0.82
            large_threshold *= 0.82
        elif turn >= 49:
            small_threshold *= 0.88
            medium_threshold *= 0.88
            large_threshold *= 0.88
        dump_mode = self._megaphone_dump_mode(data, owned, turn, race_planner, preset)
        slots_left = self._remaining_megaphone_slots(data, turn, race_planner, preset)
        owned_count = self._owned_megaphone_count(owned)
        inventory_pressure = slots_left > 0 and owned_count >= slots_left
        has_upgrade_pair = owned.get("Motivating Megaphone", 0) > 0 and owned.get("Empowering Megaphone", 0) > 0 and slots_left >= 2

        # P2: don't burn the summer-reserved strong megaphones on ordinary training
        # turns before the first summer-camp turn.  Below the reserve and before
        # camp, hold the Empowering for the camp turns (35 / 59) unless inventory
        # pressure / dump mode forces a release.
        summer_reserve = _cfg_num(cfg, "megaphone_summer_reserve", 2)
        first_summer_turn = _cfg_num(cfg, "megaphone_summer_first_turn", 35)
        strong_owned = int(owned.get("Empowering Megaphone", 0) or 0) + int(owned.get("Motivating Megaphone", 0) or 0)
        # R2: during the late-summer (60-64) / late-spend (65-70) windows the
        # stock-conservation caps are lifted, so never hold strong megaphones back.
        hold_summer_strong = (
            turn < first_summer_turn
            and strong_owned <= summer_reserve
            and not (inventory_pressure or dump_mode)
            and not (LATE_SUMMER or LATE_SPEND)
        )

        # v2.0: megaphones only fire in summer camp, on strong rainbow turns (2+
        # friendship partners), or when burning excess at end of career
        # (dump/inventory pressure). Stops the year-round +25-gain misfires.
        SUMMER = {36, 37, 38, 39, 40, 60, 61, 62, 63, 64}
        current_chara = (status or {}).get("current_chara") if isinstance(status, dict) else {}
        rainbow = self._rainbow_partner_count(best_command, current_chara or {})
        min_rainbow = int(_cfg_num(cfg, "megaphone_min_rainbow_partners", 2))
        # R2 65-70: stop conserving -- allow firing on any training (spend
        # remaining stock with no reserve), like dump mode but unconditional.
        if LATE_SPEND or (LATE_FINAL and _dump_late):
            fire_window = True
        else:
            fire_window = (turn in SUMMER) or dump_mode or inventory_pressure or rainbow >= min_rainbow
        if not fire_window:
            return None

        # R2 >= 71: fire ONLY on training that raises the current highest-priority
        # NON-CAPPED stat (the first stat in training_stat_priority below its cap).
        if LATE_FINAL and not _dump_late and not self._training_raises_priority_stat(state, best_command, preset):
            return None

        # R2 late-game: during 60-64 (fire on ANY non-zero training) and 65-70
        # (spend remaining stock), fire the best owned megaphone immediately,
        # bypassing the tier-threshold ladder and the summer hold.  LATE_FINAL's
        # priority-stat gate already filtered above.
        # 2026-06-29: in DUMP mode (save_items_lategame off) past turn 64, dump a
        # megaphone on ANY training turn -- drop the score>0 floor so capped-stat /
        # low-gain trainings still empty the stock. With the toggle ON, keep the
        # original score>0 windows. Late-summer (60-64) always keeps score>0.
        if ((_dump_late and (LATE_SPEND or LATE_FINAL))
                or ((LATE_SUMMER or LATE_SPEND or (LATE_FINAL and _dump_late)) and score > 0)):
            if owned.get("Empowering Megaphone", 0) > 0:
                return ("Empowering Megaphone", 1)
            if owned.get("Motivating Megaphone", 0) > 0:
                return ("Motivating Megaphone", 1)
            if owned.get("Coaching Megaphone", 0) > 0:
                return ("Coaching Megaphone", 1)
            return None

        target_tier = 0
        if current_mega_tier <= 0:
            if has_upgrade_pair and score >= medium_threshold:
                return ("Motivating Megaphone", 1)
            if score >= large_threshold and owned.get("Empowering Megaphone", 0) > 0 and not hold_summer_strong:
                return ("Empowering Megaphone", 1)
            if score >= medium_threshold and owned.get("Motivating Megaphone", 0) > 0 and not hold_summer_strong:
                return ("Motivating Megaphone", 1)
            # P2: never auto-fire the small Coaching megaphone unless nothing
            # better is owned -- it is the weakest tier and is best saved.
            if (score >= small_threshold and owned.get("Coaching Megaphone", 0) > 0
                    and owned.get("Motivating Megaphone", 0) <= 0
                    and owned.get("Empowering Megaphone", 0) <= 0):
                return ("Coaching Megaphone", 1)
            if inventory_pressure or dump_mode:
                # P2: dump ladder prefers Empowering > Motivating > Coaching.
                if has_upgrade_pair:
                    return ("Empowering Megaphone", 1)
                if owned.get("Empowering Megaphone", 0) > 0:
                    return ("Empowering Megaphone", 1)
                if owned.get("Motivating Megaphone", 0) > 0:
                    return ("Motivating Megaphone", 1)
                if owned.get("Coaching Megaphone", 0) > 0:
                    return ("Coaching Megaphone", 1)
            else:
                if score >= large_threshold:
                    target_tier = 3
                elif score >= medium_threshold:
                    target_tier = 2
                elif score >= small_threshold:
                    target_tier = 1
        elif current_mega_tier == 1:
            if score >= large_threshold * 1.2:
                target_tier = 3
            elif score >= medium_threshold * 1.1:
                target_tier = 2
        elif current_mega_tier == 2:
            if score >= large_threshold * 1.1:
                target_tier = 3

        if target_tier >= 3 and current_mega_tier < 3 and owned.get("Empowering Megaphone", 0) > 0:
            return ("Empowering Megaphone", 1)
        if target_tier >= 2 and current_mega_tier < 2 and owned.get("Motivating Megaphone", 0) > 0:
            return ("Motivating Megaphone", 1)
        if target_tier >= 1 and current_mega_tier < 1 and owned.get("Coaching Megaphone", 0) > 0:
            return ("Coaching Megaphone", 1)

        return None

    def _megaphone_dump_mode(self, data, owned, turn, race_planner, preset):
        training_turns_left = self._remaining_megaphone_slots(data, turn, race_planner, preset)
        total_duration = 0
        for name, (_, duration) in MEGAPHONE_TIERS.items():
            total_duration += int(owned.get(name, 0) or 0) * duration
        return training_turns_left > 0 and total_duration >= training_turns_left

    def _owned_megaphone_count(self, owned):
        total = 0
        for name in MEGAPHONE_TIERS:
            total += int(owned.get(name, 0) or 0)
        return total

    def _megaphone_buy_surplus(self, data, owned, turn, race_planner, preset):
        slots_left = self._remaining_megaphone_slots(data, turn, race_planner, preset)
        if slots_left <= 0:
            return False
        cfg = self._mant_cfg(preset)
        buffer = int(cfg.get("mega_late_buy_buffer") or 3)
        target = max(0, slots_left - buffer)
        # P2: keep a small summer reserve of strong megaphones (Empowering/Large)
        # so we never dump-buy them past the count we want banked for the summer
        # camp turns.  Counts only the top-tier megaphones against the reserve.
        summer_reserve = _cfg_num(cfg, "megaphone_summer_reserve", 2)
        strong_owned = int(owned.get("Empowering Megaphone", 0) or 0) + int(owned.get("Motivating Megaphone", 0) or 0)
        if strong_owned >= summer_reserve:
            return True
        return self._owned_megaphone_count(owned) >= target

    def _remaining_megaphone_slots(self, data, turn, race_planner, preset):
        return self._remaining_training_turns_to_77(data, turn, race_planner, preset)

    def _remaining_training_turns_to_77(self, data, turn, race_planner, preset):
        planned_race_turns = self._planned_race_turns_to_77(data, turn, race_planner, preset)
        race_condition_array = data.get("race_condition_array") or []
        remaining = 0
        for t in range(int(turn or 0), 77):
            if t in (74, 76):
                continue
            if t not in planned_race_turns:
                remaining += 1
        return remaining

    def _planned_race_turns_to_77(self, data, turn, race_planner, preset):
        current_turn = int(turn or 0)
        wanted_pids = set()
        if race_planner and preset:
            wanted_pids = race_planner.wanted_programs(preset)
        result = set()
        for item in data.get("race_condition_array") or []:
            item_turn = int(item.get("turn") or 0)
            program_id = int(item.get("program_id") or 0)
            if item_turn >= current_turn and item_turn < 77 and (not wanted_pids or program_id in wanted_pids):
                result.add(item_turn)
        if race_planner and wanted_pids:
            for program_id in wanted_pids:
                info = (race_planner.program or {}).get(int(program_id or 0)) or {}
                race_turn = self._program_turn_from_month_half(info, current_turn)
                if race_turn >= current_turn and race_turn < 77:
                    result.add(race_turn)
        return result

    def _program_turn_from_month_half(self, program_info, current_turn):
        month = int((program_info or {}).get("month") or 0)
        half = int((program_info or {}).get("half") or 0)
        if month <= 0 or half <= 0:
            return 0
        base_turn = (month - 1) * 2 + half
        candidates = [base_turn + 24 * year for year in range(4)]
        for candidate in candidates:
            if candidate >= int(current_turn or 0):
                return candidate
        return candidates[-1]

    def _anklet_target(self, state, best_command, owned, preset):
        if not best_command or int(best_command.get("command_type") or 0) != 1:
            return None

        cmd_id = int(best_command.get("command_id") or 0)
        anklet = TRAINING_TYPE_ANKLET.get(cmd_id)
        if not anklet or owned.get(anklet, 0) <= 0:
            return None

        data = state.get("data") or {}
        free_data = data.get("free_data_set") or {}
        item_effects = free_data.get("item_effect_array") or []
        for eff in item_effects:
            if eff.get("item_id") in (9001, 9002, 9003, 9004, 9005):
                return None

        score = self._command_stat_gain(best_command, sp_weight=0.5)
        threshold = 30 * (1 - (0.2 * self._active_megaphone_tier(state)))
        turn = int(((state.get("data") or {}).get("chara_info") or {}).get("turn") or 0)
        # v2.1 R2 late-game anklet policy:
        #  * 60-64: fire on ANY non-zero training (lift the conservation caps so
        #    anklet stock is spent freely during the summer peak).
        #  * 65-70: stop conserving -- spend remaining stock on any training.
        #  * >= 71: fire ONLY on training that raises the current highest-priority
        #    NON-CAPPED stat.
        # 2026-06-29: in DUMP mode (save_items_lategame off) past turn 64, fire the
        # anklet on ANY matching-stat training -- drop the score>0 floor so leftover
        # anklets empty instead of stranding at career end.
        _dump_late = (not self._mant_cfg(preset).get(
            "save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME)) and turn > 64
        if turn in {60, 61, 62, 63, 64}:
            if score > 0:
                return (anklet, 1)
            return None
        if 65 <= turn <= 70:
            if _dump_late or score > 0:
                return (anklet, 1)
            return None
        if turn >= 71:
            # Late-game dump: after turn 64 fire the anklet on any matching-stat
            # training, bypassing the priority gate AND the score floor.
            if _dump_late or (score > 0 and self._training_raises_priority_stat(state, best_command, preset)):
                return (anklet, 1)
            return None
        if turn in {36, 37, 38, 39, 40}:
            threshold *= 0.80
        elif turn >= 49:
            threshold *= 0.88
        if score > threshold:
            return (anklet, 1)
        return None

    def _active_megaphone_tier(self, state):
        current_mega_tier = 0
        for eff in ((state.get("data") or {}).get("free_data_set") or {}).get("item_effect_array") or []:
            item_id = eff.get("item_id")
            if item_id == 8001: current_mega_tier = max(current_mega_tier, 1)
            elif item_id == 8002: current_mega_tier = max(current_mega_tier, 2)
            elif item_id == 8003: current_mega_tier = max(current_mega_tier, 3)
        return current_mega_tier

    def _command_main_stat_gain(self, cmd):
        if not cmd:
            return 0
        main_target = TRAINING_COMMAND_MAIN_TARGET.get(int(cmd.get("command_id") or 0))
        if main_target:
            for item in cmd.get("params_inc_dec_info_array") or []:
                if int(item.get("target_type") or 0) == main_target:
                    return int(item.get("value") or 0)
        # Fallback for payloads that expose direct stat fields but not the
        # params_inc_dec_info_array shape.
        field_by_target = {1: "speed", 2: "stamina", 3: "power", 4: "guts", 5: "wiz"}
        field = field_by_target.get(main_target)
        if field:
            return int(cmd.get(field) or 0)
        return int(self._command_stat_gain(cmd))

    def _training_stat_priority(self, preset):
        """Return the lower-cased training_stat_priority list from the preset
        (preset.training_stat_priority, then mant_config.training_stat_priority),
        or [] when unset."""
        priority = (
            (preset or {}).get("training_stat_priority")
            or ((preset or {}).get("mant_config") or {}).get("training_stat_priority")
            or []
        )
        if isinstance(priority, str):
            priority = [p.strip() for p in priority.split(",") if p.strip()]
        return [str(p).strip().lower() for p in (priority or []) if str(p).strip()]

    def _training_raises_priority_stat(self, state, best_command, preset):
        """R2 (turn >= 71): True when the training's main stat is the current
        HIGHEST-PRIORITY NON-CAPPED stat (the first entry in
        training_stat_priority whose live value is below GLOBAL_STAT_CAP) and the
        command actually gains that stat.

        If every priority stat is already capped there is nothing left to push, so
        the gate is satisfied (the caller then applies its own score checks).
        """
        if not best_command:
            return False
        priority = self._training_stat_priority(preset)
        if not priority:
            return True
        chara = ((state or {}).get("data") or {}).get("chara_info") or {}
        main_idx = TRAINING_COMMAND_MAIN_TARGET.get(int(best_command.get("command_id") or 0))
        chosen = None
        for name in priority:
            mapping = _STAT_FIELD_BY_NAME.get(name)
            if not mapping:
                continue
            field, idx = mapping
            current = int(chara.get(field) or 0)
            if current < GLOBAL_STAT_CAP:
                chosen = idx
                break
        # All priority stats capped -> nothing left to push; allow the gate.
        if chosen is None:
            return True
        if main_idx != chosen:
            return False
        return self._command_main_stat_gain(best_command) > 0

    def _command_stat_gain(self, cmd, sp_weight=0):
        if not cmd: return 0
        total = 0
        for item in cmd.get("params_inc_dec_info_array") or []:
            tt = item.get("target_type")
            if tt in [1, 2, 3, 4, 5]:
                total += int(item.get("value") or 0)
            elif (tt == 6 or tt == 30) and sp_weight > 0:
                total += int(item.get("value") or 0) * sp_weight
        if total == 0:
            for field in ["speed", "stamina", "power", "guts", "wiz"]:
                total += int(cmd.get(field) or 0)
            if sp_weight > 0:
                total += int(cmd.get("lp") or cmd.get("skill_point") or 0) * sp_weight
        return total

    def _merge_targets(self, targets, owned):
        counts = {}
        for name, count in targets:
            counts[name] = counts.get(name, 0) + count
        result = []
        for name, count in counts.items():
            actual = min(count, owned.get(name, 0))
            if actual > 0:
                result.append((name, actual))
        return result

    def _item_cap(self, name, preset=None):
        caps = ((preset or {}).get("mant_config") or {}).get("item_caps") or {}
        if name in caps:
            try:
                return max(0, int(caps[name]))
            except Exception:
                pass
        return int(ITEM_INVENTORY_CAPS.get(name, DEFAULT_INVENTORY_CAP))

    def _item_buy_value(self, name, row, owned, turn, budget, data, preset, race_planner):
        """Relative usefulness inside the same tier. Higher is better.

        This keeps the existing tier system intact, but gives the shop a little
        judgment: sales, urgency, active ailments, late-run dump pressure, and
        planned training/racing windows all move the needle.
        """
        cost = int(row.get("coin_num") or SHOP_ITEM_COSTS.get(name, 9999))
        original = int(row.get("original_coin_num") or cost)
        limit_turn = int(row.get("limit_turn") or 0)
        turns_left = (limit_turn - int(turn or 0)) if limit_turn > 0 else 99
        qty = int(owned.get(name) or 0)
        value = 100.0
        if original > cost:
            value += min(60.0, (original - cost) * 2.0)
        if turns_left <= 2:
            value += 45.0
        elif turns_left <= 6:
            value += 18.0
        if name in CURE_ITEMS and self._active_bad_statuses(data or {}):
            value += 120.0
        if name in ENERGY_ITEMS:
            hp = int(((data or {}).get("chara_info") or {}).get("vital") or 0)
            if hp <= 35:
                value += 70.0
            elif hp <= 55:
                value += 25.0
        if name in {"Plain Cupcake", "Berry Sweet Cupcake"}:
            motivation = int(((data or {}).get("chara_info") or {}).get("motivation") or 3)
            if motivation < 4:
                value += 70.0
            elif motivation >= 5:
                value -= 60.0
        if name in MEGAPHONE_TIERS:
            slots = self._remaining_megaphone_slots(data or {}, turn, race_planner, preset)
            if turn >= 49 or slots <= self._owned_megaphone_count(owned) + 3:
                value += 40.0
            value -= qty * 18.0
        if name in TRAINING_ITEM_DECK_TYPE_INDEX:
            counts = (preset or {}).get("_deck_type_counts") or []
            idx = TRAINING_ITEM_DECK_TYPE_INDEX.get(name)
            deck_count = int(counts[idx] or 0) if idx is not None and len(counts) > idx else 0
            # P1: strong decks kept buying anklets forever (+18/card vs -12/qty).
            # Trim the per-card bonus and steepen the per-owned penalty so value
            # falls off after the first couple of copies.
            value += deck_count * 12.0
            value -= qty * 20.0
        guide = self._guide(preset)
        shop_cfg = guide.get("shop_priorities") or {}
        immediate_cfg = shop_cfg.get("immediate_stat_items") or {}
        if name in set(immediate_cfg.get("names") or []):
            value += float(immediate_cfg.get("value_bonus") or 55)
            # Early stat scrolls/manuals stabilize first-place race wins, which protects the shop-coin economy.
            if turn <= 24:
                value += 35.0
        fast_cfg = shop_cfg.get("fast_learner") or {}
        if (preset or {}).get("mant_config", {}).get("enable_fast_learner_shop_boost", False) and name == fast_cfg.get("item", "Scholar's Hat"):
            value += float(fast_cfg.get("value_bonus") or 180)
            if turn > int(fast_cfg.get("reserve_until_turn") or 64):
                value -= 80.0
        if name in set((shop_cfg.get("training_boost_items") or {}).get("names") or []):
            if is_pre_summer(turn):
                value += 45.0
            elif is_summer_turn(turn, guide):
                value += 70.0
        if name.endswith("Training Application"):
            if turn > int((shop_cfg.get("applications") or {}).get("avoid_late_after_turn") or 64):
                value -= 95.0
            if is_pre_summer(turn):
                value += 35.0
        if self._is_instant_stat_item(name):
            # P3: keep the late-game +20 for the worthwhile Medium Manual (+7) and
            # Large Scroll (+15), but NOT for the small +3 notepads -- those should
            # not get a value boost that keeps them in the buy list.
            if not display_to_slug(name).endswith("_notepad"):
                value += 20.0 if turn >= 46 else 0.0
        value -= cost * 0.35
        return value

    def _skip_buy(self, name, owned, preset=None, turn=0, budget=0, data=None, race_planner=None):
        cfg = ((preset or {}).get("mant_config") or {})
        excluded = cfg.get("exclude_shop_items") or []
        if isinstance(excluded, str):
            excluded = [part.strip() for part in excluded.split(",") if part.strip()]
        excluded_slugs = {display_to_slug(item) for item in excluded}
        if display_to_slug(name) in excluded_slugs:
            return True
        # Hard exclusions: wasteful pre-race auto-consumed items (see
        # ALWAYS_EXCLUDE_SLUGS).  Never bought unless explicitly re-enabled.
        if (display_to_slug(name) in ALWAYS_EXCLUDE_SLUGS
                and not cfg.get("allow_wasteful_consumables", False)):
            return True
        # P3: small +3 stat notepads (ids 1001-1005) are skip-by-default -- their
        # tiny stat gain isn't worth the coins.  Medium Manual (+7) / Large Scroll
        # (+15) are unaffected (different slug suffixes).  Opt back in via config.
        if display_to_slug(name).endswith("_notepad") and not cfg.get("trackblazer_buy_notepads", False):
            # v2.1: the tiny +3 notepads are normally skipped, BUT when the bot is
            # flush with coins (otherwise hoarded to career end -- the "~500 coins
            # left over every run" complaint), a permanent +3 stat beats hoarding.
            # Buy them once coins exceed the flush threshold so surplus coins convert
            # into stats instead of being wasted.
            if int(budget or 0) < _cfg_num(cfg, "trackblazer_notepad_flush_coin", 250):
                return True
        if int(owned.get(name, 0) or 0) >= self._item_cap(name, preset):
            return True
        # v2.1 R2: during the late-summer window (turns 60-64) lift the
        # stock-conservation caps so anklets/megaphones are bought freely and the
        # use logic has stock to spend.  Past turn 64 (R6) conservation is off
        # entirely, so the gates below also no longer apply from 65 on.
        _late_summer = 60 <= int(turn or 0) <= 64
        # Late-game dump (after turn 64, unless save_items_lategame): lift the
        # stock-conservation buy caps so the use logic has megaphones/anklets to
        # spend, mirroring the 60-64 summer window.
        _dump_late = (not cfg.get("save_items_lategame", tb_rules.DEFAULT_SAVE_ITEMS_LATEGAME)) and int(turn or 0) > 64
        _lift_conservation = _late_summer or _dump_late
        if name in MEGAPHONE_TIERS and not _lift_conservation and self._megaphone_buy_surplus(data or {}, owned, turn, race_planner, preset):
            return True
        # v2.0 megaphone buy policy: never buy small (Coaching); buy big
        # (Empowering) freely; buy medium (Motivating) only if still short on big
        # megaphones for the upcoming summer.
        if name == "Coaching Megaphone" and not _lift_conservation and not cfg.get("trackblazer_buy_small_megaphone", False):
            return True
        if name == "Motivating Megaphone" and not _lift_conservation:
            big_target = _cfg_num(cfg, "megaphone_big_summer_target", 2)
            if int(owned.get("Empowering Megaphone", 0) or 0) >= big_target:
                return True
        # P1: anklet over-buy guard.  Keep only ~2 anklets in stock total (main +
        # sub); once we hold that many across all types, stop buying more.
        if name in set(TRAINING_TYPE_ANKLET.values()) and not _lift_conservation:
            anklet_max = _cfg_num(cfg, "trackblazer_anklet_max_stock", 2)
            total_anklets = sum(int(owned.get(a, 0) or 0) for a in set(TRAINING_TYPE_ANKLET.values()))
            if total_anklets >= anklet_max:
                return True
        if name in CURE_ITEMS:
            # Rich Hand Cream and Miracle Cure are Trackblazer-critical race/run
            # insurance and may be stocked up to their normal cap. Other specific
            # cures are one-copy safety valves, and are skipped if Miracle Cure
            # already covers the same emergency.
            if name in {"Rich Hand Cream", AILMENT_CURE_ALL}:
                return False
            if owned.get(name, 0) > 0 or (name != AILMENT_CURE_ALL and owned.get(AILMENT_CURE_ALL, 0) > 0):
                return True
        guide = self._guide(preset)
        fast_cfg = ((guide.get("shop_priorities") or {}).get("fast_learner") or {})
        if name == fast_cfg.get("item", "Scholar's Hat"):
            min_coin = int(fast_cfg.get("min_coin_before_buy") or 280)
            if int(budget or 0) < min_coin:
                return True
        # Preserve coins before summer unless the item is a high-impact guide priority.
        reserve = int(((guide.get("summer_strategy") or {}).get("pre_summer_reserve_coin") or 0))
        if is_pre_summer(turn) and budget < reserve and name not in set(((guide.get("shop_priorities") or {}).get("training_boost_items") or {}).get("names") or []):
            if name not in set(((guide.get("shop_priorities") or {}).get("immediate_stat_items") or {}).get("names") or []):
                return True
        type_idx = TRAINING_ITEM_DECK_TYPE_INDEX.get(name)
        if type_idx is not None:
            counts = (preset or {}).get("_deck_type_counts") or []
            count = int(counts[type_idx] or 0) if len(counts) > type_idx else 0
            if count < 2:
                return True
            return False
        if name in ONE_TIME_BUFF_ITEMS and name in self.used_buffs:
            return True
        return False
