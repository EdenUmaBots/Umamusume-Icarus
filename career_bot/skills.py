import json
import re
from pathlib import Path

from career_bot.running_style import (
    STYLE_ID_TO_KEY,
    STYLE_KEY_TO_ID,
    STYLE_LABELS,
    normalize_running_style,
    resolve_skill_running_style,
    running_style_key,
)
try:
    from career_bot import skill_intercept  # DEV-ONLY web skill-buy intercept
except Exception:  # excluded from beta/public builds -> intercept always off
    class skill_intercept:  # type: ignore
        @staticmethod
        def is_enabled():
            return False
MARK_WHITE_CIRCLE = "○"
MARK_DOUBLE_CIRCLE = "◎"
MARK_X = "×"
MARK_LARGE_CIRCLE = "◯"
MOJI_WHITE_CIRCLE = "â—‹"
MOJI_LARGE_CIRCLE = "â—¯"
MOJI_DOUBLE_CIRCLE = "â—Ž"
MOJI_X = "Ã—"

SKILL_LEARN_PRIORITY_LIST = [
    [
        'Corner Acceleration ○', 'Corner Adept ○', 'Slipstream', 'Tail Held High',
        'Straightaway Spurt', 'Ramp Up', 'Inside Scoop', 'Passing Pro', 'Homestretch Haste',
        'Fast-Paced', 'Outer Swell', 'Sprinting Gear', 'Slick Surge', 'Corner Recovery ○',
        'Hydrate', 'After-School Stroll', 'Clean Heart', 'Dominator', 'All-Seeing Eyes', 'Mystifying Murmur'
    ],
    [
        'Acceleration', 'Focus', 'Go with the Flow', 'I Can See Right Through You',
        'Nimble Navigator', 'Straightaway Recovery', 'Deep Breaths', 'Preferred Position',
        'Groundwork', 'Up-Tempo', 'Unyielding Spirit', 'Pressure', 'Strategist', 'Triple 7s',
        'Shake It Out', 'Intimidate', 'Stamina Eater', 'Intense Gaze', 'Speed Star',
        'Staggering Lead', 'Blinding Flash', 'Restless', 'Trackblazer', 'Meticulous Measures',
        'Keeping the Lead', 'Leader\'s Pride', 'Wait-and-See', 'A Small Breather'
    ],
    [
        'Levelheaded', 'Stop Right There!', 'Super Lucky Seven', 'Maverick ○', 'Sympathy',
        'Long Shot ○', 'Inner Post Proficiency ○', 'Outer Post Proficiency ○', 'Right-Handed ○',
        'Left-Handed ○', 'Firm Conditions ○', 'Wet Conditions ○', 'Standard Distance ○',
        'Non-Standard Distance ○', 'Competitive Spirit ○', 'Target in Sight ○', 'Lone Wolf'
    ]
]


SKILL_TAG_FRONT = 101
SKILL_TAG_PACE = 102
SKILL_TAG_LATE = 103
SKILL_TAG_END = 104
SKILL_TAG_SPRINT = 201
SKILL_TAG_MILE = 202
SKILL_TAG_MEDIUM = 203
SKILL_TAG_LONG = 204
SKILL_TAG_DIRT = 502

# These lightweight profiles let the buyer make useful decisions even when the
# preset only has a sparse manual priority list.  They are deliberately data
# driven and can be overridden from a preset with ``skill_profile``.
DEFAULT_TRAINEE_SKILL_PROFILES = {
    "maruzensky_formula_r": {
        "match_names": ["maruzensky"],
        "running_style": "front",
        "primary_distances": ["mile"],
        "secondary_distances": ["sprint", "medium"],
        "avoid_distances": ["long"],
        "track": "turf",
        "preferred_skill_names": [
            "Focus",
            "Fast-Paced",
            "Front Runner Corners ○",
            "Front Runner Corners ◯",
            "Front Runner Savvy ○",
            "Front Runner Savvy ◯",
            "Groundwork",
            "Playtime's Over!",
            "Mile Corners ○",
            "Mile Corners ◯",
            "Professor of Curvature",
            "Changing Gears",
            "Taking the Lead",
            "Mile Maven",
            "Professor of Curvature",
            "Slipstream",
            "Front Runner Straightaways ◎",
            "Front Runner Straightaways ○",
            "Mile Straightaways ◎",
            "Mile Straightaways ○",
            "Top Runner",
            "Runaway",
            "Angling and Scheming",
            "Early Lead",
            "Shifting Gears",
            "Straightaway Adept",
            "Acceleration",
            "Step on the Gas!",
        ],
        "preferred_name_fragments": [
            "front runner", "mile", "corner", "curvature", "lead",
            "gear", "paced", "groundwork", "focus", "acceleration",
        ],
        "notes": "Front Runner / Mile profile based on Maruzensky (Formula R) guide data.",
    }
}

STYLE_TAGS = {
    "front": SKILL_TAG_FRONT,
    "pace": SKILL_TAG_PACE,
    "late": SKILL_TAG_LATE,
    "end": SKILL_TAG_END,
}
DISTANCE_TAGS = {
    "sprint": SKILL_TAG_SPRINT,
    "mile": SKILL_TAG_MILE,
    "medium": SKILL_TAG_MEDIUM,
    "long": SKILL_TAG_LONG,
}

# Community tier anchors.  This is intentionally editable via
# data/community_skill_tiers.json so you can update it as Game8 or your club
# consensus changes without touching code.  The buyer uses these as a fallback
# after Maruzensky-specific recommendations.
DEFAULT_COMMUNITY_SKILL_TIERS = {
    "SS": [
        "Mile Maven", "Taking the Lead", "Groundwork", "Professor of Curvature",
        "Slipstream", "Front Runner Corners ◎", "Front Runner Corners ○",
        "Front Runner Straightaways ◎", "Front Runner Straightaways ○",
        "Mile Corners ◎", "Mile Corners ○", "Mile Straightaways ◎",
        "Mile Straightaways ○", "Red Shift/LP1211-M",
    ],
    "S": [
        "Focus", "Concentration", "Changing Gears", "Top Runner", "Speed Star",
        "Corner Connoisseur", "Playtime's Over!", "Lead the Charge!",
        "Killer Tunes", "Runaway", "Angling and Scheming", "Early Lead",
        "Shifting Gears", "Straightaway Adept",
    ],
    "A": [
        "Acceleration", "Fast-Paced", "Groundwork", "Up-Tempo",
        "Corner Acceleration ○", "Corner Adept ○", "Tail Held High",
        "Homestretch Haste", "Mile Straightaways ○", "Mile Corners ○",
    ],
}
TIER_SCORE = {"SS": 115, "S": 86, "A": 52, "B": 25}

# Skill-purchase redesign Stage 3: graded tier from the community spreadsheet
# (data/skill_tiers_normalized.json). The sheet ranks skills with symbols
# (essential -> useless): U+235F > U+25CE > U+25EF > U+25B2 > U+25B3 > U+2715.
# Each symbol maps to a heuristic bonus (a TIEBREAKER, same layer as the legacy
# community tier; the PRIMARY key remains real eval-points-per-SP). Editable per
# preset via "skill_tier_multipliers".
DEFAULT_SHEET_TIER_BONUS = {
    "⍟": 140,   # essential
    "◎": 110,   # best (double circle)
    "◯": 60,    # good (large circle)
    "▲": 20,    # situational (filled triangle)
    "△": 5,     # excess SP (open triangle)
    "✕": -60,   # useless
}

IRRELEVANT_STYLE_TAGS = {SKILL_TAG_FRONT, SKILL_TAG_PACE, SKILL_TAG_LATE, SKILL_TAG_END}
IRRELEVANT_DISTANCE_TAGS = {SKILL_TAG_SPRINT, SKILL_TAG_MILE, SKILL_TAG_MEDIUM, SKILL_TAG_LONG}

# --- Schedule-aware activation-condition gate (skill-purchase redesign Stage 1) ---
# A skill activates only when its conditions hold. Some condition keys are
# TRAINEE-DETERMINABLE up front -- running_style (1 front / 2 pace / 3 late / 4 end)
# and distance_type (1 sprint / 2 mile / 3 medium / 4 long). If those can NEVER be
# satisfied by THIS trainee/schedule, the skill is a dead SP sink. All OTHER keys
# (order_rate, distance_rate, order, corner, phase, remain_distance, ...) are in-race
# DYNAMIC and are deliberately NOT gated -- they can occur in any race, so gating on
# them would wrongly demote good situational skills.
_COND_PRED_RE = re.compile(r'^([a-z_]+)(>=|<=|==|!=|>|<)(-?\d+)$')
_DISTANCE_TYPE_KEY = {1: "sprint", 2: "mile", 3: "medium", 4: "long"}


def _condition_predicate_blocked(key, op, val, style_id, distance_keys):
    """True iff this single predicate is a determinable gate that is PROVABLY
    unsatisfiable for the trainee. Unknown/dynamic keys -> False (not blocked)."""
    if key == "running_style" and style_id:
        if op == "==":
            return val != style_id
        if op == "!=":
            return val == style_id
        return False
    if key == "distance_type" and distance_keys:
        dk = _DISTANCE_TYPE_KEY.get(val)
        if dk is None:
            return False
        if op == "==":
            return dk not in distance_keys
        if op == "!=":
            return False  # "not this distance" is satisfiable as long as others are raced
        return False
    return False


def _condition_group_blocked(group, style_id, distance_keys):
    """An AND-group is blocked if ANY of its determinable predicates is unsatisfiable."""
    for pred in group.split("&"):
        m = _COND_PRED_RE.match(pred.strip())
        if not m:
            continue
        if _condition_predicate_blocked(m.group(1), m.group(2), int(m.group(3)), style_id, distance_keys):
            return True
    return False


def evaluate_skill_conditions(conditions, style_id, distance_keys):
    """Can a skill with these `conditions` EVER activate for this trainee?

    conditions: list of condition strings ("@" = OR of alt groups, "&" = AND).
    style_id: the trainee's running-style id (1-4) or None/0 if unknown.
    distance_keys: set of distance keys the trainee races (sprint/mile/medium/long);
                   empty set = unknown (never gate on distance then).
    Returns True (can fire / be conservative) unless EVERY @-group across the
    conditions is blocked by a provably-unsatisfiable running_style/distance_type.
    """
    distance_keys = {str(d).lower() for d in (distance_keys or set())}
    saw_group = False
    for cstr in (conditions or []):
        for group in str(cstr).split("@"):
            saw_group = True
            if not _condition_group_blocked(group, style_id, distance_keys):
                return True
    return not saw_group  # no parsable groups -> conservative True; all blocked -> False


def norm(text):
    return re.sub(r'[^a-z0-9]+', '', str(text or '').lower())


def strip_mark(text):
    if not text:
        return ""
    for m in [MARK_WHITE_CIRCLE, MARK_DOUBLE_CIRCLE, MARK_X, MARK_LARGE_CIRCLE,
              MOJI_WHITE_CIRCLE, MOJI_DOUBLE_CIRCLE, MOJI_X, MOJI_LARGE_CIRCLE]:
        text = text.replace(m, "")
    return text.strip()


def _normalize_skill_target(value):
    """Normalize the skill-purchase optimization target to one of
    career | team_trials | champions. Default (and any unknown value) -> career,
    which preserves the fans-first single-mode behavior."""
    v = norm(value)
    if v in {"teamtrials", "trials", "tt", "team"}:
        return "team_trials"
    if v in {"champions", "championsmeeting", "champion", "cm", "cm9", "pvp"}:
        return "champions"
    return "career"


class SkillBuyer:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.skill_names = {}
        self.skill_rarities = {}
        self.skill_costs = {}
        self.skill_grade_values = {}
        self.skill_tags = {}
        self.skill_categories = {}
        self.skill_icons = {}
        self.official_skill_weights = {}
        self.official_skill_sources = {}
        self.official_skill_conditions = {}
        self.community_tiers = {}
        self.community_tier_by_name = {}
        self.race_context_cache = {}
        self.skill_id_exists = set()
        self.group_to_skill_ids = {}
        self.skill_to_group_id = {}
        self.failed_this_turn = {}
        self.current_turn = None
        self.last_candidates = []
        self.last_selected = []
        self.last_actual_spent = 0
        self.last_attempt = []
        self.last_result = {}
        self.recover_after_error = False
        self.attempt_events = []
        # Career-persistent union of every skill id ever owned or bought.
        # chara_info.skill_array is a PARTIAL rotating view (a handful of skills),
        # not the full owned set, so the only reliable "owned" set is the union
        # accumulated across the whole career. Without this the bot re-buys skills
        # that rotated out of the partial view (the Fast-Paced / 200542 re-buy bug:
        # sent to gain_skills 15x in one career despite being owned early on).
        self._acquired_skill_ids = set()
        self._load()

    def _load(self):
        path = self.base_dir / "data" / "skill_data.json"
        # Initialize tables up front so a parse failure leaves consistent EMPTY
        # tables (and these attrs always exist) rather than a half-populated or
        # missing set that would silently disable ALL skill buying with no clue.
        self.skill_names = {}
        self.skill_rarities = {}
        self.skill_costs = {}
        self.skill_grade_values = {}
        self.skill_tags = {}
        self.skill_categories = {}
        self.skill_icons = {}
        self.official_skill_weights = {}
        self.skill_to_group_id = {}
        self.load_error = None
        if not path.exists():
            self.load_error = "skill_data.json not found"
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            # A corrupt/truncated skill_data.json must not silently kill skill
            # buying for the whole career. Record + log it, run with empty tables.
            self.load_error = f"skill_data.json parse failed: {exc}"
            print(f"[SkillBuyer] {self.load_error}")
            return
        for raw_id, raw_info in data.items():
            try:
                skill_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            try:
                if isinstance(raw_info, dict):
                    self.skill_names[skill_id] = raw_info.get("name") or str(skill_id)
                    self.skill_rarities[skill_id] = int(raw_info.get("rarity") or 0)
                    self.skill_costs[skill_id] = int(raw_info.get("need_skill_point") or 0)
                    self.skill_grade_values[skill_id] = int(raw_info.get("grade_value") or 0)
                    self.skill_tags[skill_id] = set(int(tag) for tag in (raw_info.get("tags") or []) if str(tag).lstrip("-").isdigit())
                    self.skill_categories[skill_id] = int(raw_info.get("skill_category") or -1)
                    self.skill_icons[skill_id] = str(raw_info.get("icon_id") or raw_info.get("iconId") or "")
                    group_id = int(raw_info.get("group_id") or 0)
                    if group_id:
                        self.skill_to_group_id[skill_id] = group_id
                else:
                    self.skill_names[skill_id] = raw_info
                    self.skill_tags[skill_id] = set()
                    self.skill_categories[skill_id] = -1
                    self.skill_icons[skill_id] = ""
            except Exception:
                # One malformed row must not abort the whole ~8000-row table.
                continue
        self._load_community_tiers()
        self._load_sheet_tiers()
        self._load_official_skill_weights()
        self.skill_id_exists = set(self.skill_names)
        self.group_to_skill_ids = {}
        for skill_id in self.skill_names:
            group_id = self.skill_to_group_id.get(skill_id) or (skill_id if skill_id < 100000 else skill_id // 10)
            self.skill_to_group_id[skill_id] = group_id
            self.group_to_skill_ids.setdefault(group_id, []).append(skill_id)
        
        for group_id, ids in self.group_to_skill_ids.items():
            children = [sid for sid in ids if sid >= 100000]
            if children:
                self.group_to_skill_ids[group_id] = sorted(children, key=self._tier_sort_key)
            else:
                self.group_to_skill_ids[group_id] = sorted(ids, key=self._tier_sort_key)

    def _tier_sort_key(self, skill_id):
        grade_value = int(self.skill_grade_values.get(skill_id) or 0)
        return (
            int(self.skill_rarities.get(skill_id) or 99),
            1 if grade_value <= 0 else 0,
            grade_value if grade_value > 0 else 999999,
            int(skill_id),
        )

    def _tier_ids(self, group_id, rarity):
        ids = [
            sid for sid in self.group_to_skill_ids.get(group_id, [])
            if self.skill_rarities.get(sid, 0) == rarity and self.skill_grade_values.get(sid, 0) > 0
        ]
        return sorted(ids, key=self._tier_sort_key)

    def _resolve_buyable_tier(self, group_id, rarity, owned_skill_ids):
        tiers = self._tier_ids(group_id, rarity)
        if not tiers:
            candidates = [
                sid for sid in self.group_to_skill_ids.get(group_id, [])
                if self.skill_rarities.get(sid, 0) == rarity and sid not in owned_skill_ids
            ]
            return sorted(candidates, key=self._tier_sort_key)[0] if candidates else 0
        for index, sid in enumerate(tiers):
            if sid in owned_skill_ids:
                continue
            if index == 0 or tiers[index - 1] in owned_skill_ids:
                return sid
            return 0
        return 0

    def _unowned_white_tiers(self, group_id, owned_skill_ids):
        return [sid for sid in self._tier_ids(group_id, 1) if sid not in owned_skill_ids]

    def _load_official_skill_weights(self):
        """Load master.mdb-derived skill metadata for smarter weighted scoring."""
        self.official_skill_weights = {}
        self.official_skill_sources = {}
        self.official_skill_conditions = {}

        source_path = self.base_dir / "data" / "skill_sources_core.json"
        try:
            source_payload = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else {}
            raw_sources = source_payload.get("skill_to_sources") if isinstance(source_payload, dict) else {}
            for raw_id, sources in (raw_sources or {}).items():
                try:
                    self.official_skill_sources[int(raw_id)] = list(sources or [])
                except Exception:
                    continue
        except Exception:
            self.official_skill_sources = {}

        condition_path = self.base_dir / "data" / "skill_condition_core.json"
        try:
            condition_rows = json.loads(condition_path.read_text(encoding="utf-8")) if condition_path.exists() else []
            for row in condition_rows if isinstance(condition_rows, list) else []:
                try:
                    self.official_skill_conditions[int(row.get("skill_id") or 0)] = row
                except Exception:
                    continue
        except Exception:
            self.official_skill_conditions = {}

        path = self.base_dir / "data" / "skill_weighting_core.json"
        if not path.exists():
            return
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        for row in rows if isinstance(rows, list) else []:
            try:
                skill_id = int(row.get("skill_id") or 0)
            except Exception:
                continue
            if not skill_id:
                continue
            condition_row = self.official_skill_conditions.get(skill_id) or {}
            sources = self.official_skill_sources.get(skill_id) or []
            support_sources = [src for src in sources if src.get("source_type") in {"support", "support_hint"}]
            trainee_sources = [src for src in sources if src.get("source_type") == "trainee"]
            cost = max(1, int(row.get("cost") or condition_row.get("cost") or 0))
            grade = int(row.get("grade_value") or condition_row.get("grade_value") or 0)
            ability_types = row.get("ability_types") or condition_row.get("ability_types") or []
            conditions = row.get("conditions") or condition_row.get("conditions") or []
            ability_count = len(ability_types or [])
            condition_count = len(conditions or [])
            score = 0
            if grade:
                score += min(45, grade / cost * 10)
            score += ability_count * 4
            score += condition_count * 2
            if support_sources:
                score += min(12, len(support_sources) * 1.5)
            if trainee_sources:
                score += min(8, len(trainee_sources) * 1.0)
            disable_singlemode = int(row.get("disable_singlemode") or condition_row.get("disable_singlemode") or 0)
            # NOTE: the single-mode-disable penalty is NOT baked into this score
            # anymore -- it is applied at scoring time via
            # _disable_singlemode_adjustment so it can be mode-dependent (hard-drop
            # in career, kept in Team Trials / Champions).
            if int(row.get("is_general_skill") or condition_row.get("is_general_skill") or 0):
                score += 6
            self.official_skill_weights[skill_id] = {
                "score": round(score, 2),
                "cost": cost,
                "grade_value": grade,
                "ability_types": ability_types,
                "conditions": conditions,
                "disable_singlemode": disable_singlemode,
                "source_count": len(sources),
                "support_source_count": len(support_sources),
                "trainee_source_count": len(trainee_sources),
                "skill_category_label": condition_row.get("skill_category_label", ""),
            }

    def _load_community_tiers(self):
        self.community_tiers = {tier: list(names) for tier, names in DEFAULT_COMMUNITY_SKILL_TIERS.items()}
        path = self.base_dir / "data" / "community_skill_tiers.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for tier, names in raw.items():
                        if isinstance(names, list):
                            self.community_tiers[str(tier).upper()] = [str(n) for n in names]
            except Exception:
                pass
        self.community_tier_by_name = {}
        for tier, names in self.community_tiers.items():
            for name in names:
                key = norm(strip_mark(name))
                if key:
                    self.community_tier_by_name[key] = tier


    def _load_trainee_skill_profiles(self):
        profiles = {key: dict(value) for key, value in DEFAULT_TRAINEE_SKILL_PROFILES.items()}

        # Generated Game8 scrape data provides broad coverage. Manual profiles
        # are loaded afterward and win as the tuning/override layer.
        for filename in ["trainee_skill_profiles.generated.json", "trainee_skill_profiles.json"]:
            path = self.base_dir / "data" / filename
            if not path.exists():
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key, profile in raw.items():
                        if isinstance(profile, dict):
                            normalized = self._normalize_external_profile(key, profile)
                            profiles[str(key)] = normalized
            except Exception:
                pass
        return profiles

    def _normalize_external_profile(self, key, profile):
        profile = dict(profile or {})
        profile.setdefault("key", norm(key) or norm(profile.get("name")) or "generated_profile")

        # New generated profiles use recommended_style / aptitude maps.  The old
        # buyer expects running_style, track, primary_distances, and name fragments.
        if not profile.get("running_style"):
            profile["running_style"] = profile.get("recommended_style") or "front"

        if not profile.get("track"):
            track = profile.get("track_aptitude") or {}
            dirt = str(track.get("dirt", "G")).upper()
            turf = str(track.get("turf", "C")).upper()
            profile["track"] = "dirt" if dirt in {"S", "A", "B"} and turf not in {"S", "A", "B"} else "turf"

        if not profile.get("primary_distances"):
            dist = profile.get("distance_aptitude") or {}
            order = {"S": 8, "A": 7, "B": 6, "C": 5, "D": 3, "E": 2, "F": 1, "G": 0}
            ranked = sorted(["sprint", "mile", "medium", "long"], key=lambda d: order.get(str(dist.get(d, "G")).upper(), 0), reverse=True)
            profile["primary_distances"] = [d for d in ranked if str(dist.get(d, "")).upper() in {"S", "A", "B"}][:2] or ranked[:1]
            profile["secondary_distances"] = [d for d in ranked if d not in profile["primary_distances"] and str(dist.get(d, "")).upper() in {"B", "C"}]
            profile["avoid_distances"] = [d for d in ranked if str(dist.get(d, "")).upper() in {"E", "F", "G"}]

        preferred_fragments = list(profile.get("preferred_name_fragments") or profile.get("preferred_skill_fragments") or [])
        if not preferred_fragments:
            style = str(profile.get("running_style") or "").lower()
            style_label = {"front": "front runner", "pace": "pace chaser", "late": "late surger", "end": "end closer"}.get(style, style)
            preferred_fragments.extend([style_label, "corner", "straightaway", "acceleration"])
            preferred_fragments.extend(str(d) for d in profile.get("primary_distances") or [])
        profile["preferred_name_fragments"] = preferred_fragments

        # Keep exact recommended skills as the highest shelf.
        preferred_names = list(profile.get("preferred_skill_names") or [])
        for item in profile.get("preferred_skill_fragments") or []:
            if len(str(item)) > 3:
                preferred_names.append(str(item))
        if profile.get("unique_skill"):
            preferred_names.append(str(profile.get("unique_skill")))
        profile["preferred_skill_names"] = list(dict.fromkeys(preferred_names))

        return profile

    def _profile_from_aptitudes(self, name, aptitudes, source="aptitudes"):
        def best_grade(mapping, keys):
            order = {"S": 8, "A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1}
            best_key, best_val = None, -1
            for key in keys:
                val = order.get(str((mapping or {}).get(key, "")).upper(), 0)
                if val > best_val:
                    best_key, best_val = key, val
            return best_key, best_val
        distances = ["sprint", "mile", "medium", "long"]
        styles = ["front", "pace", "late", "end"]
        primary, pv = best_grade(aptitudes, distances)
        style, sv = best_grade(aptitudes, styles)
        secondary = [d for d in distances if d != primary and str((aptitudes or {}).get(d, "")).upper() in {"A", "B"}]
        avoid = [d for d in distances if str((aptitudes or {}).get(d, "")).upper() in {"E", "F", "G"}]
        track = "dirt" if str((aptitudes or {}).get("dirt", "")).upper() in {"A", "B"} and str((aptitudes or {}).get("turf", "")).upper() not in {"A", "B"} else "turf"
        if not primary and not style:
            return {}
        fragments = [x for x in [style, primary, "corner", "straight", "acceleration", "lead" if style == "front" else "position"] if x]
        return {
            "key": norm(name) or "auto_profile",
            "source": source,
            "match_names": [name] if name else [],
            "running_style": style or "front",
            "primary_distances": [primary] if primary else [],
            "secondary_distances": secondary,
            "avoid_distances": avoid,
            "track": track,
            "preferred_name_fragments": fragments,
            "notes": "Generated from trainee aptitudes/running style.",
        }

    def _merge_skill_strategy(self, profile, preset):
        strategy = preset.get("skill_strategy") or {}
        if not isinstance(strategy, dict):
            return profile
        merged = dict(profile or {})
        # Manual overrides from the redesigned Skill Configuration UI.
        # If the skill UI is left on Auto, inherit Racing Settings so skills and
        # race-entry strategy cannot drift apart.
        manual_style = strategy.get("running_style") if isinstance(strategy, dict) else None
        if manual_style and manual_style != "auto":
            merged["running_style"] = running_style_key(manual_style, "pace")
        else:
            merged["running_style"] = running_style_key(resolve_skill_running_style(preset, default=2), "pace")
        primary = strategy.get("primary_distances") or strategy.get("primary_distance")
        if isinstance(primary, str):
            primary = [primary]
        if primary and "auto" not in primary:
            merged["primary_distances"] = primary
        secondary = strategy.get("secondary_distances")
        if isinstance(secondary, str):
            secondary = [secondary]
        if secondary:
            merged["secondary_distances"] = secondary
        if strategy.get("track") and strategy.get("track") != "auto":
            merged["track"] = strategy.get("track")
        forced = strategy.get("forced_skills") or []
        if forced:
            existing = list(merged.get("preferred_skill_names") or [])
            merged["preferred_skill_names"] = list(dict.fromkeys([*forced, *existing]))
        merged.setdefault("source", "skill_strategy")
        return merged

    def _skill_color(self, skill_id, name=""):
        """Return a coarse skill color bucket from icon/category/name.

        This is intentionally conservative.  The English master data exposes icon
        families more reliably than category labels across versions:
        100x = green, 200x = yellow/active, 300x = red/debuff, 900x = unique.
        """
        icon = str(self.skill_icons.get(skill_id) or "")
        lowered = str(name or self.skill_names.get(skill_id, "")).lower()
        if icon.startswith(("1001", "1002", "1003", "1004", "1005", "1006")):
            return "green"
        if icon.startswith(("2001", "2004", "2005", "2006", "2009")):
            return "yellow"
        if icon.startswith(("3001", "3002", "3004", "3005", "3007")):
            return "red"
        if "red shift" in lowered or "lp1211" in lowered:
            return "unique"
        category = int(self.skill_categories.get(skill_id, -1))
        if category == 0:
            return "green"
        if category in {1, 2, 4, 5}:
            return "yellow"
        return "other"

    def _community_priority_bucket(self, name, base_name):
        """Recommended Maruzensky skills should win first, then tier-list skills.

        Generic green circle variants used to land in priority 500, which made the
        buyer hoover up greens before strong yellow SS/S skills.  Tier buckets fix
        that ordering while still letting score choose inside the tier.
        """
        _, tier = self._community_tier_score(name, base_name)
        return {"SS": 110, "S": 170, "A": 260, "B": 360}.get(tier, 999)

    def _community_tier_score(self, name, base_name):
        tier = self.community_tier_by_name.get(norm(base_name)) or self.community_tier_by_name.get(norm(name))
        if not tier:
            return 0, ""
        return TIER_SCORE.get(tier, 0), tier

    def _load_sheet_tiers(self):
        """Load the graded community-spreadsheet tiers (Stage 3). Keyed by
        norm(strip_mark(name)) to match the scorer's lookups. Best-effort: a
        missing or malformed file just yields an empty map (legacy tier remains)."""
        self.sheet_tier_by_norm = {}
        path = self.base_dir / "data" / "skill_tiers_normalized.json"
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        tiers = raw.get("tiers") if isinstance(raw, dict) else None
        if not isinstance(tiers, dict):
            return
        for key, rec in tiers.items():
            if isinstance(rec, dict):
                self.sheet_tier_by_norm[str(key)] = rec

    def _skill_tier_multipliers(self, preset):
        """Symbol -> heuristic bonus map, with optional per-preset overrides."""
        mult = dict(DEFAULT_SHEET_TIER_BONUS)
        override = (preset or {}).get("skill_tier_multipliers")
        if isinstance(override, dict):
            for sym, val in override.items():
                try:
                    mult[str(sym)] = float(val)
                except Exception:
                    continue
        return mult

    def _sheet_tier_score(self, name, base_name, target, preset=None):
        """Graded tier bonus for a skill from the community spreadsheet.

        `target` (career|team_trials|champions) selects the rank column:
        career/team_trials -> Team-Trials rank; champions -> Champions/PvP rank
        (with a fall back to the Team-Trials rank when the PvP cell is blank).
        Returns (bonus, symbol); (0.0, "") when the skill is not in the sheet."""
        rec = (self.sheet_tier_by_norm.get(norm(base_name))
               or self.sheet_tier_by_norm.get(norm(name)))
        if not rec:
            return 0.0, ""
        if target == "champions":
            sym = rec.get("cm") or rec.get("tt") or ""
        else:
            sym = rec.get("tt") or rec.get("cm") or ""
        if not sym:
            return 0.0, ""
        return float(self._skill_tier_multipliers(preset).get(sym, 0.0)), sym

    def _disable_singlemode_adjustment(self, official, target):
        """`disable_singlemode` skills are turned off by the game in single-mode
        CAREER (buying them there is 100% wasted SP) but DO work on the finished
        uma in Team Trials / Champions. So: hard-drop in career, keep (no
        penalty) otherwise. Returns (score_delta, reason_or_None)."""
        if not official or not int(official.get("disable_singlemode") or 0):
            return 0.0, None
        if target == "career":
            return -10000.0, "disable_singlemode(career_drop)"
        return 0.0, "disable_singlemode(kept:%s)" % target

    def _race_context(self, preset):
        # Count the planned races by distance/terrain so skill buying can lean
        # into what Trackblazer actually scheduled.  Cache by race id list.
        race_ids = tuple(int(x) for x in (preset.get("extra_race_list") or []) if str(x).isdigit())
        if race_ids in self.race_context_cache:
            return self.race_context_cache[race_ids]
        context = {"distance_counts": {}, "terrain_counts": {}, "total": 0}
        if not race_ids:
            self.race_context_cache[race_ids] = context
            return context
        path = self.base_dir / "assets" / "data" / "uma_race_data.json"
        if not path.exists():
            path = self.base_dir / "data" / "uma_race_data.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            races = data.get("races") if isinstance(data, dict) else data
            lookup = {}
            for race in races or []:
                ids = [race.get("id"), *(race.get("legacy_ids") or [])]
                for rid in ids:
                    try:
                        lookup[int(rid)] = race
                    except Exception:
                        pass
            for rid in race_ids:
                race = lookup.get(rid)
                if not race:
                    continue
                context["total"] += 1
                distance = str(race.get("distance") or "").lower()
                if "mile" in distance or "1600" in distance or "1800" in distance:
                    key = "mile"
                elif "short" in distance or "sprint" in distance or "1200" in distance or "1400" in distance:
                    key = "sprint"
                elif "long" in distance or "2500" in distance or "2600" in distance or "3000" in distance or "3200" in distance:
                    key = "long"
                else:
                    key = "medium"
                context["distance_counts"][key] = context["distance_counts"].get(key, 0) + 1
                terrain = str(race.get("terrain") or "").lower()
                if terrain:
                    context["terrain_counts"][terrain] = context["terrain_counts"].get(terrain, 0) + 1
        except Exception:
            pass
        self.race_context_cache[race_ids] = context
        return context

    def _race_context_score(self, tags, name, base_name, preset):
        ctx = self._race_context(preset)
        total = max(1, int(ctx.get("total") or 0))
        if total <= 1:
            return 0, []
        reasons = []
        score = 0
        distance_counts = ctx.get("distance_counts") or {}
        for dist, tag in DISTANCE_TAGS.items():
            if tag in tags:
                ratio = float(distance_counts.get(dist, 0)) / total
                if ratio >= 0.5:
                    score += 45 * ratio
                    reasons.append(f"trackblazer_{dist}:{ratio:.0%}")
                elif ratio <= 0.1:
                    score -= 25
                    reasons.append(f"rare_schedule_{dist}")
        # Green course/condition skills are often schedule-specific.  Without
        # full course parsing, give a small value bump instead of blindly buying.
        lowered = str(base_name or name or "").lower()
        if any(word in lowered for word in ["right-handed", "left-handed", "firm conditions", "wet conditions", "standard distance", "non-standard distance"]):
            score += 12
            reasons.append("green_schedule_candidate")
        return round(score, 2), reasons

    def reset_scoped_failures(self):
        self.failed_this_turn = {}
        self.current_turn = None
        self.last_candidates = []
        self.last_selected = []
        self.last_attempt = []
        self.last_result = {}

    def _set_turn(self, turn):
        turn = int(turn or 0)
        if self.current_turn != turn:
            self.current_turn = turn
            self.failed_this_turn = {turn: set()}
        self.failed_this_turn.setdefault(turn, set())

    def _failed_for_turn(self, turn=None):
        turn = int(turn if turn is not None else self.current_turn or 0)
        return self.failed_this_turn.setdefault(turn, set())

    def _skill_config(self, preset):
        preset = preset or {}
        return {
            "enable_skill_point_check": bool(preset.get("enable_skill_point_check", True)),
            "learn_skill_threshold": int(preset.get("learn_skill_threshold") or 888),
            "enable_skill_point_check_plan": bool(preset.get("enable_skill_point_check_plan", True)),
            "purchase_negative_skills": bool(preset.get("purchase_negative_skills", False)),
            "skip_green_skills": bool(preset.get("skip_green_skills", False)),
            "skip_red_skills": bool(preset.get("skip_red_skills", False)),
            "skip_unique_skills": bool(preset.get("skip_unique_skills", False)),
            "skill_spending_strategy": str(preset.get("skill_spending_strategy") or "best_skills_first"),
            "skill_stop_after_recommended": bool(preset.get("skill_stop_after_recommended", False)),
            "skill_manual_auto_fallback": bool(preset.get("skill_manual_auto_fallback", False)),
            # Stage 1 condition gate: penalize (dampen eval/SP) | enforce (hard drop) | ignore.
            "skill_condition_gating": str(preset.get("skill_condition_gating") or "penalize").lower(),
            "skill_condition_dead_factor": float(preset.get("skill_condition_dead_factor", 0.15)),
            # Stage 3 optimization target: career (default, fans-first single-mode)
            # | team_trials | champions. Selects which spreadsheet rank column
            # weights the graded tier, and whether single-mode-disabled skills are
            # dropped (career) or kept (TT/CM).
            "skill_optimization_target": _normalize_skill_target(preset.get("skill_optimization_target")),
            "skill_tier_multipliers": dict(preset.get("skill_tier_multipliers") or {}),
        }

    def _candidate_allowed_by_skill_config(self, candidate, preset):
        cfg = self._skill_config(preset)
        color = candidate.get("skill_color") or self._skill_color(candidate.get("skill_id"), candidate.get("name"))
        if color == "green" and cfg["skip_green_skills"]:
            return False
        if color == "red" and cfg["skip_red_skills"]:
            return False
        if color == "unique" and cfg["skip_unique_skills"]:
            return False
        return True

    def buy(self, client, state, preset, force=False):
        data = state.get("data") or {}
        chara = data.get("chara_info") or data.get("single_mode_chara_light") or {}
        self.recover_after_error = False
        self.attempt_events = []
        if not chara:
            return state, 0

        points = int(chara.get("skill_point") or 0)
        turn = int(chara.get("turn") or 0)
        self._set_turn(turn)
        cfg = self._skill_config(preset)
        if not cfg["enable_skill_point_check"] and not force:
            self.last_candidates = []
            self.last_selected = []
            self.last_attempt = []
            self.last_result = {"skip": "skill_point_check_disabled"}
            return state, 0
        is_hoarding = points > 1500
        threshold = cfg["learn_skill_threshold"]
        # v1.5 pre-finals dump (the reference preFinals plan): on the turns just
        # before the Twinkle Star Climax (finale races at 74/76/78), spend the
        # accumulated SP on the best skills even if below the normal threshold,
        # so the trainee enters the finals fully kitted instead of carrying SP
        # past the last races it can affect.
        pre_finals_turn = int(cfg.get("pre_finals_skill_turn") or 73)
        if not force and cfg.get("enable_pre_finals_skill_dump", True) and turn >= pre_finals_turn and points > 0:
            force = True
        if not force and not is_hoarding and points <= threshold:
            self.last_candidates = []
            self.last_selected = []
            self.last_attempt = []
            self.last_result = {"skip": "threshold", "points": points, "threshold": threshold}
            return state, 0

        if preset.get("manual_purchase_at_end") and not force:
            self.last_candidates = []
            self.last_selected = []
            self.last_attempt = []
            self.last_result = {"skip": "manual_purchase_at_end"}
            return state, 0

        candidates = self._candidates(chara, preset)
        if force and not candidates:
            candidates = self._candidates(chara, {**preset, "learn_skill_only_user_provided": False})

        self.last_candidates = [dict(item) for item in candidates]
        if not candidates:
            self.last_selected = []
            self.last_attempt = []
            self.last_result = {"skip": "no_candidates", "points": points}
            return state, 0

        selected = []
        spent = 0
        green_count = 0
        max_green = int(preset.get("smart_skill_max_green_per_purchase", 1)) if preset else 1
        for candidate in candidates:
            if not self._candidate_allowed_by_skill_config(candidate, preset):
                continue
            cost = int(candidate.get("cost") or self._estimate_cost(candidate))
            color = candidate.get("skill_color") or self._skill_color(candidate.get("skill_id"), candidate.get("name"))
            if color == "green" and max_green >= 0 and green_count >= max_green:
                continue
            if spent + cost > points:
                continue
            selected.append(candidate)
            spent += cost
            if color == "green":
                green_count += 1

        if not selected:
            self.last_selected = []
            self.last_attempt = []
            self.last_result = {"skip": "not_enough_points", "points": points}
            return state, 0

        self.last_selected = [dict(item) for item in selected]
        
        current_state, total_bought = self._buy_batch(client, state, selected, turn)
            
        return current_state, total_bought

    def preview(self, state, preset, force=False):
        data = state.get("data") or {}
        chara = data.get("chara_info") or data.get("single_mode_chara_light") or {}
        if not chara:
            self.last_candidates = []
            self.last_selected = []
            return
        turn = int(chara.get("turn") or 0)
        self._set_turn(turn)
        points = int(chara.get("skill_point") or 0)
        cfg = self._skill_config(preset)
        threshold = cfg["learn_skill_threshold"]
        if not force and points <= threshold:
            self.last_candidates = []
            self.last_selected = []
            return
        if preset.get("manual_purchase_at_end") and not force:
            self.last_candidates = []
            self.last_selected = []
            return
        candidates = self._candidates(chara, preset)
        selected = []
        spent = 0
        green_count = 0
        max_green = int(preset.get("smart_skill_max_green_per_purchase", 1)) if preset else 1
        for candidate in candidates:
            if not self._candidate_allowed_by_skill_config(candidate, preset):
                continue
            cost = int(candidate.get("cost") or self._estimate_cost(candidate))
            color = candidate.get("skill_color") or self._skill_color(candidate.get("skill_id"), candidate.get("name"))
            if color == "green" and max_green >= 0 and green_count >= max_green:
                continue
            if spent + cost > points:
                continue
            selected.append(candidate)
            spent += cost
            if color == "green":
                green_count += 1
        self.last_candidates = [dict(item) for item in candidates]
        self.last_selected = [dict(item) for item in selected]

    def _priority(self, rows):
        result = {}
        for index, row in enumerate(rows):
            for name in row:
                key = norm(name)
                result[key] = min(index, result.get(key, index))
        return result

    def _priority_value(self, skill_id, name, base_name, priority):
        values = [priority.get(str(skill_id)), priority.get(norm(name)), priority.get(norm(base_name))]
        values = [v for v in values if v is not None]
        return min(values) if values else 999

    def _priority_context(self, preset):
        raw_priority = preset.get("learn_skill_list") or []
        if not raw_priority and not preset.get("learn_skill_only_user_provided"):
            raw_priority = SKILL_LEARN_PRIORITY_LIST
        return self._priority(raw_priority)

    def _blacklist(self, preset):
        # v2.1: read BOTH legacy top-level learn_skill_blacklist AND the newer
        # skill_strategy.blacklist (the Configure Skills UI writes to the latter),
        # and accept skill IDs as well as names so the blacklist works regardless
        # of which form the UI stored. The returned set mixes normalized names and
        # integer skill ids; resolve_skill_tip checks both.
        entries = list(preset.get("learn_skill_blacklist") or [])
        strategy = preset.get("skill_strategy")
        if isinstance(strategy, dict):
            entries.extend(strategy.get("blacklist") or [])
        result = set()
        for item in entries:
            if item is None:
                continue
            if isinstance(item, bool):
                continue
            if isinstance(item, int):
                result.add(item)
                continue
            s = str(item).strip()
            if not s:
                continue
            if s.isdigit():
                result.add(int(s))
            result.add(norm(s))
        return result

    def _infer_skill_profile(self, chara, preset):
        raw = preset.get("skill_profile") or {}
        external_profiles = self._load_trainee_skill_profiles()
        if isinstance(raw, str):
            raw_key = norm(raw)
            for key, profile in external_profiles.items():
                if norm(key) == raw_key:
                    return self._merge_skill_strategy(dict(profile, key=key, source="preset_name"), preset)
            raw = {}
        if isinstance(raw, dict) and raw:
            profile = dict(raw)
            profile.setdefault("source", "preset")
            return self._merge_skill_strategy(profile, preset)

        card_id = str(chara.get("card_id") or "")
        chara_name = str(
            preset.get("trainee_name")
            or preset.get("chara_name")
            or preset.get("character_name")
            or ""
        )
        # External profile table wins when available.  It can be generated from
        # Game8's character list / individual pages with tools/game8_profile_scraper.py.
        for key, profile in external_profiles.items():
            raw_ids = profile.get("card_ids")
            if raw_ids is None:
                raw_ids = profile.get("card_id")
            if raw_ids is None:
                ids = set()
            elif isinstance(raw_ids, (list, tuple, set)):
                ids = {str(x) for x in raw_ids}
            else:
                # Generated master-data profiles may provide card_id as a single int.
                # Treat scalars as one card id instead of trying to iterate them.
                ids = {str(raw_ids)}
            if card_id and card_id in ids:
                return self._merge_skill_strategy(dict(profile, key=key, source="card_id"), preset)
            if chara_name and any(norm(name) and norm(name) in norm(chara_name) for name in profile.get("match_names", [])):
                return self._merge_skill_strategy(dict(profile, key=key, source="name"), preset)
        # Card names are not always present in the live career payload, so keep
        # Maruzensky as a built-in known-good fallback.
        if card_id in {"100402", "100401"}:
            return self._merge_skill_strategy(dict(DEFAULT_TRAINEE_SKILL_PROFILES["maruzensky_formula_r"], key="maruzensky_formula_r", source="card_id"), preset)
        # If the UI provided aptitudes, make a live profile from them.
        strategy = preset.get("skill_strategy") or {}
        if isinstance(strategy, dict) and isinstance(strategy.get("aptitudes"), dict):
            built = self._profile_from_aptitudes(chara_name, strategy.get("aptitudes"), source="ui_aptitudes")
            if built:
                return self._merge_skill_strategy(built, preset)
        # Final fallback: use selected running style/distance from the new UI.
        if isinstance(strategy, dict) and (strategy.get("running_style") or strategy.get("primary_distances")):
            built = self._profile_from_aptitudes(chara_name, {
                self._selected_style_key(preset, {}) or "pace": "A",
                str((strategy.get("primary_distances") or ["mile"])[0] if isinstance(strategy.get("primary_distances"), list) else strategy.get("primary_distances") or "mile"): "A",
                str(strategy.get("track") or "turf"): "A",
            }, source="ui_strategy")
            return self._merge_skill_strategy(built, preset)
        return {}

    def _profile_name_priority(self, name, base_name, profile):
        if not profile:
            return 999
        n_name = norm(name)
        n_base = norm(base_name)
        for idx, preferred in enumerate(profile.get("preferred_skill_names") or []):
            p = norm(preferred)
            if p and (p == n_name or p == n_base):
                return idx
        return 999

    def _selected_style_key(self, preset, profile=None):
        """Return the style key the skill buyer must respect.

        Racing Settings are the source of truth unless the user explicitly sets
        a non-auto style in Configure Skills.
        """
        style_id = resolve_skill_running_style(preset or {}, default=None)
        if style_id:
            return STYLE_ID_TO_KEY.get(style_id)
        if profile:
            return running_style_key(profile.get("running_style"), "pace")
        return "pace"

    def _skill_style_mismatch(self, skill_id, selected_style_key):
        tags = set(self.skill_tags.get(int(skill_id or 0)) or set())
        style_tags = {
            "front": SKILL_TAG_FRONT,
            "pace": SKILL_TAG_PACE,
            "late": SKILL_TAG_LATE,
            "end": SKILL_TAG_END,
        }
        required_tags = tags & set(style_tags.values())
        if not required_tags:
            return False, ""
        selected_tag = style_tags.get(str(selected_style_key or "").lower())
        if selected_tag in required_tags:
            return False, ""
        selected_id = STYLE_KEY_TO_ID.get(str(selected_style_key or "").lower())
        selected_label = STYLE_LABELS.get(selected_id or 0, str(selected_style_key or "selected style"))
        return True, f"style_mismatch:{selected_label}"

    def _skill_distance_mismatch(self, skill_id, profile):
        """Hard distance filter for the auto plan: a distance-exclusive skill whose
        distance(s) are all outside the trainee's primary+secondary distances should
        never be bought (e.g. a Long-only skill on a Miler). Returns (False, "") for
        skills that carry no distance tag, or when the profile has no distance data
        (so we never brick purchasing when aptitudes are unknown)."""
        tags = set(self.skill_tags.get(int(skill_id or 0)) or set())
        distance_tags = tags & IRRELEVANT_DISTANCE_TAGS
        if not distance_tags:
            return False, ""
        allowed = {DISTANCE_TAGS.get(str(d).lower()) for d in (profile.get("primary_distances") or [])}
        allowed |= {DISTANCE_TAGS.get(str(d).lower()) for d in (profile.get("secondary_distances") or [])}
        allowed.discard(None)
        if not allowed:
            return False, ""
        if distance_tags & allowed:
            return False, ""
        return True, "distance_mismatch"

    def _trainee_distance_keys(self, profile, preset):
        """Distance keys (sprint/mile/medium/long) the trainee actually races -
        the union of the profile's primary+secondary distances and the scheduled
        races. Empty set = unknown (caller then never gates on distance)."""
        keys = set()
        for d in (profile.get("primary_distances") or []):
            keys.add(str(d).lower())
        for d in (profile.get("secondary_distances") or []):
            keys.add(str(d).lower())
        try:
            for k in (self._race_context(preset or {}).get("distance_counts") or {}):
                keys.add(str(k).lower())
        except Exception:
            pass
        keys.discard("")
        return keys

    def _skill_condition_can_fire(self, skill_id, profile, preset):
        """Stage 1 gate: can this skill EVER activate for this trainee? False only
        when every condition group is blocked by an unsatisfiable running_style /
        distance_type (dynamic in-race conditions are never gated)."""
        row = self.official_skill_conditions.get(int(skill_id or 0)) or {}
        conditions = row.get("conditions") or []
        if not conditions:
            return True
        style_id = STYLE_KEY_TO_ID.get(str(self._selected_style_key(preset or {}, profile) or "").lower())
        return evaluate_skill_conditions(conditions, style_id, self._trainee_distance_keys(profile, preset))

    # Aptitude multiplier.  The reference optimiser scales a skill's
    # raw evaluation points by the trainee's aptitude grade for the dimension the
    # skill belongs to: S/A 1.1, B/C 0.9, D/E/F 0.8, G 0.7.  We mirror that mapping
    # exactly and default to 1.0 (neutral) when no aptitude data is available.
    _APTITUDE_MULTIPLIER = {
        "S": 1.1, "A": 1.1,
        "B": 0.9, "C": 0.9,
        "D": 0.8, "E": 0.8, "F": 0.8,
        "G": 0.7,
    }

    def _aptitude_grades(self, profile, preset):
        """Collect the trainee's per-dimension aptitude grades.

        Generated profiles carry distance_aptitude/track_aptitude maps; the live
        Skill Configuration UI passes a flat aptitudes map on the preset's
        skill_strategy.  Merge whatever is available into one lower-cased lookup
        keyed by dimension name (sprint/mile/medium/long/turf/dirt/front/...).
        """
        grades = {}
        strategy = (preset or {}).get("skill_strategy") if isinstance((preset or {}).get("skill_strategy"), dict) else {}
        for src in (
            (strategy or {}).get("aptitudes"),
            (profile or {}).get("distance_aptitude"),
            (profile or {}).get("track_aptitude"),
            (profile or {}).get("style_aptitude"),
            (profile or {}).get("aptitudes"),
        ):
            if isinstance(src, dict):
                for key, val in src.items():
                    g = str(val or "").strip().upper()[:1]
                    if g in self._APTITUDE_MULTIPLIER:
                        grades.setdefault(str(key).lower(), g)
        return grades

    def _skill_aptitude_multiplier(self, skill_id, profile, preset):
        """Return the aptitude multiplier for this skill.

        The skill's relevant aptitude is read from its distance/style/track tags;
        we take the BEST (highest) grade across the dimensions the skill touches so
        a well-suited skill is not penalised by an unrelated weak aptitude.  When
        the skill has no aptitude-bearing tags or the trainee has no aptitude data,
        the multiplier is neutral (1.0) so the eval/SP ratio drives ordering.
        """
        grades = self._aptitude_grades(profile, preset)
        if not grades:
            return 1.0
        tags = set(self.skill_tags.get(int(skill_id or 0)) or set())
        tag_dimension = {
            SKILL_TAG_FRONT: "front", SKILL_TAG_PACE: "pace",
            SKILL_TAG_LATE: "late", SKILL_TAG_END: "end",
            SKILL_TAG_SPRINT: "sprint", SKILL_TAG_MILE: "mile",
            SKILL_TAG_MEDIUM: "medium", SKILL_TAG_LONG: "long",
            SKILL_TAG_DIRT: "dirt",
        }
        best = None
        for tag, dim in tag_dimension.items():
            if tag in tags and dim in grades:
                mult = self._APTITUDE_MULTIPLIER.get(grades[dim], 1.0)
                if best is None or mult > best:
                    best = mult
        return best if best is not None else 1.0

    def _skill_smart_score(self, skill_id, name, base_name, hint_level, profile, preset=None):
        if not profile:
            return 0, []
        tags = set(self.skill_tags.get(skill_id) or set())
        reasons = []
        score = 0
        weights = (preset.get("skill_strategy") or {}).get("weights", {}) if isinstance(preset.get("skill_strategy"), dict) else {}
        n_name = norm(name)
        n_base = norm(base_name)

        preferred_names = {norm(item) for item in profile.get("preferred_skill_names") or []}
        if n_name in preferred_names or n_base in preferred_names:
            score += float(weights.get("recommended", 190))
            reasons.append("character_recommended")

        target = _normalize_skill_target((preset or {}).get("skill_optimization_target"))
        community_weight = float(weights.get("community", 1.0))
        sheet_bonus, sheet_sym = self._sheet_tier_score(name, base_name, target, preset)
        if sheet_sym:
            # The graded spreadsheet tier (289 skills) supersedes the coarse
            # 3-tier legacy list when it has an entry; legacy is the fallback.
            score += sheet_bonus * community_weight
            reasons.append(f"sheet_tier[{target}]:{sheet_sym}")
        else:
            tier_score, tier = self._community_tier_score(name, base_name)
            if tier_score:
                score += tier_score * community_weight
                reasons.append(f"community_tier:{tier}")

        color = self._skill_color(skill_id, name)
        if color == "yellow":
            score += float(preset.get("smart_skill_yellow_bonus", weights.get("yellow", 100)) if preset else 100)
            reasons.append("yellow_priority")
        elif color == "green":
            # Greens are useful seasoning, not the whole meal.  Recommended or
            # high-tier greens can still pass, but generic condition/stat greens
            # need a much stronger reason to beat yellow actives.
            score -= float(preset.get("smart_skill_green_penalty", weights.get("green_penalty", 90)) if preset else 90)
            reasons.append("green_deprioritized")
        elif color == "red":
            score -= float(preset.get("smart_skill_red_penalty", 45) if preset else 45)
            reasons.append("red_deprioritized")

        for frag in profile.get("preferred_name_fragments") or []:
            if norm(frag) and norm(frag) in n_base:
                score += 18
                reasons.append(f"name:{frag}")
                break

        style = self._selected_style_key(preset or {}, profile) or str(profile.get("running_style") or "pace").lower()
        style_tag = STYLE_TAGS.get(style)
        if style_tag and style_tag in tags:
            score += float(weights.get("style", 70))
            reasons.append(f"style:{style}")
        mismatch, mismatch_reason = self._skill_style_mismatch(skill_id, style)
        if mismatch:
            score -= 10000
            reasons.append(mismatch_reason or "wrong_style")

        primary_distance_tags = {DISTANCE_TAGS.get(str(item).lower()) for item in profile.get("primary_distances") or []}
        primary_distance_tags.discard(None)
        secondary_distance_tags = {DISTANCE_TAGS.get(str(item).lower()) for item in profile.get("secondary_distances") or []}
        secondary_distance_tags.discard(None)
        avoid_distance_tags = {DISTANCE_TAGS.get(str(item).lower()) for item in profile.get("avoid_distances") or []}
        avoid_distance_tags.discard(None)

        if tags & primary_distance_tags:
            score += float(weights.get("distance", 75))
            reasons.append("primary_distance")
        if tags & secondary_distance_tags:
            score += 24
            reasons.append("secondary_distance")
        if tags & avoid_distance_tags:
            score -= 45
            reasons.append("avoid_distance")

        if str(profile.get("track") or "").lower() == "turf" and SKILL_TAG_DIRT in tags:
            score -= 140
            reasons.append("wrong_track")

        race_score, race_reasons = self._race_context_score(tags, name, base_name, preset or {})
        if race_score:
            score += race_score
            reasons.extend(race_reasons)

        category = int(self.skill_categories.get(skill_id, -1))
        # Skill categories vary by master data version, but these observed values
        # are useful: 0 green, 1 acceleration/start, 2 velocity, 4 corner/position,
        # 5 unique/inherited.  Maruzensky wants front acceleration and velocity.
        if category in {1, 2, 4, 5}:
            score += 24
            reasons.append("useful_category")
        if category == 0 and (style_tag and style_tag in tags):
            score += 8
            reasons.append("style_green_limited")

        if hint_level:
            score += min(5, int(hint_level)) * 7
            reasons.append("hint")

        official = self.official_skill_weights.get(int(skill_id or 0))
        if official:
            official_score = float(official.get("score") or 0)
            if official_score:
                score += official_score
                reasons.append(f"official_master:{round(official_score, 1)}")
            # Single-mode-disabled skills: dead SP in career, kept in TT/CM.
            dsm_adj, dsm_reason = self._disable_singlemode_adjustment(official, target)
            if dsm_adj:
                score += dsm_adj
            if dsm_reason:
                reasons.append(dsm_reason)
            if official.get("conditions"):
                reasons.append("official_conditions")
            if int(official.get("support_source_count") or 0):
                reasons.append(f"support_sources:{int(official.get('support_source_count') or 0)}")
            if int(official.get("trainee_source_count") or 0):
                reasons.append(f"trainee_sources:{int(official.get('trainee_source_count') or 0)}")

        # --- PRIMARY SORT KEY ---------------------------------------------------
        # Everything accumulated above is Icarus's hand-tuned additive heuristic
        # (recommended / community tier / color / style / distance / track / race
        # / category / official-master).  As of v1.5 it is DEMOTED
        # to a tiebreaker.  The PRIMARY ordering now mirrors the reference bot:
        #
        #     primary = (grade_value / need_skill_point) * aptitude_multiplier
        #
        # grade_value is the REAL in-game skill evaluation-points value from
        # data/skill_data.json; need_skill_point is the SP cost.  This is true
        # eval-points-per-SP, not a proxy.  The aptitude multiplier is the reference
        # mapping (S/A 1.1, B/C 0.9, D/E/F 0.8, G 0.7) applied to the skill's
        # relevant aptitude dimension.  We scale by PRIMARY_SCALE so the primary
        # term dominates the heuristic, which only breaks ties between skills of
        # similar eval/SP efficiency.  Hard exclusions accumulated above (wrong
        # style -10000, wrong track) stay additive and still override the primary.
        heuristic = score
        grade = int(self.skill_grade_values.get(skill_id) or 0)
        cost = max(1, int(self.skill_costs.get(skill_id) or 160))
        apt_mult = self._skill_aptitude_multiplier(skill_id, profile, preset)
        eval_per_sp = (grade / cost) * apt_mult  # negative for ✗ debuff skills
        # Stage 1: schedule-aware activation-condition gate. A skill whose
        # running_style/distance_type conditions can NEVER fire for this trainee is
        # dead SP. Feasibility is computed ALWAYS so the buy log can MEASURE the
        # leak (the reason tag) even in 'ignore' mode; the score penalty is applied
        # only in penalize (dampen eval/SP) / enforce (hard drop) modes.
        gate_mode = str((preset or {}).get("skill_condition_gating") or "penalize").lower()
        if not self._skill_condition_can_fire(skill_id, profile, preset):
            if gate_mode == "enforce":
                heuristic += -10000
                reasons.append("condition_dead(enforce)")
            elif gate_mode == "ignore":
                reasons.append("condition_unsatisfiable(ignore)")
            else:  # penalize (default)
                try:
                    eval_per_sp *= float((preset or {}).get("skill_condition_dead_factor", 0.15))
                except Exception:
                    eval_per_sp *= 0.15
                reasons.append("condition_dead(penalize)")
        primary_scale = float((preset or {}).get("skill_eval_primary_scale", 1000)) if preset else 1000
        score = eval_per_sp * primary_scale + heuristic
        reasons.append(f"eval_per_sp:{round(eval_per_sp, 3)}")
        if apt_mult != 1.0:
            reasons.append(f"aptitude_x{apt_mult}")

        return round(score, 2), reasons

    def _smart_min_score(self, preset, profile):
        if not profile:
            return -9999
        return float(preset.get("smart_skill_min_score", 18))

    def _recommended_skill_names(self, preset, profile):
        """Base names of the character's recommended/best skills (the profile's
        preferred_skill_names plus community SS/S tiers). Drives the auto
        stop-after-recommended gate."""
        names = set()
        for n in (profile or {}).get("preferred_skill_names") or []:
            names.add(norm(strip_mark(str(n))))
        for tier in ("SS", "S"):
            for n in self.community_tiers.get(tier, []):
                names.add(norm(strip_mark(str(n))))
        return names

    def _candidates(self, chara, preset):
        current_owned = {int(item.get("skill_id") or 0) for item in chara.get("skill_array") or []}
        # skill_array is a PARTIAL rotating view (a few skills), NOT the full owned
        # set, so union it into a career-persistent acquired set and treat the union
        # as owned. This is what stops the bot re-buying a skill that rotated out of
        # the partial view (e.g. Fast-Paced/200542 re-bought 15x in one career).
        self._acquired_skill_ids |= current_owned
        owned = current_owned | self._acquired_skill_ids
        owned_groups = {self.skill_to_group_id.get(skill_id, skill_id // 10) for skill_id in owned}
        priority = self._priority_context(preset)
        blacklist = self._blacklist(preset)
        profile = self._infer_skill_profile(chara, preset)
        # For smart profiles, the old generic fallback list should not outrank
        # a strong trainee/tier/race fit.  User-provided lists still win.
        if profile and not preset.get("learn_skill_list"):
            priority = {}
        smart_min_score = self._smart_min_score(preset, profile)
        result = []
        # DIAGNOSTIC (2026-06-26): trace why the candidate set ends up empty — the
        # bot evaluates affordable skills but selects 0, hoards SP, buys nothing.
        # Logs ONLY when the final set is empty, so it's silent on healthy turns.
        _dbg = {"turn": int(chara.get("turn") or 0), "tips": len(chara.get("skill_tips_array") or []),
                "resolved": 0, "resolve_skipped": 0, "smart_dropped": 0, "min_score": smart_min_score,
                "profile": bool(profile), "style": (profile or {}).get("running_style"),
                "prim_dist": (profile or {}).get("primary_distances")}
        def _log_funnel(reason, n_final):
            if n_final == 0:
                print(f"[skill-candidates] t{_dbg['turn']} EMPTY ({reason}): tips={_dbg['tips']} "
                      f"resolved={_dbg['resolved']} resolve_skipped={_dbg['resolve_skipped']} "
                      f"smart_dropped={_dbg['smart_dropped']} min_score={_dbg['min_score']} "
                      f"profile={_dbg['profile']} style={_dbg['style']} prim_dist={_dbg['prim_dist']}")
        for tip in chara.get("skill_tips_array") or []:
            resolved = self.resolve_skill_tip(tip, owned, owned_groups, priority, blacklist, preset, profile)
            if not resolved or resolved.get("skip_reason"):
                _dbg["resolve_skipped"] += 1
                continue
            if profile and resolved.get("priority", 999) >= 999 and float(resolved.get("smart_score") or 0) < smart_min_score:
                _dbg["smart_dropped"] += 1
                continue
            _dbg["resolved"] += 1
            result.append({
                "skill_id": resolved["resolved_skill_id"],
                "group_id": resolved["group_id"],
                "tip_rarity": resolved["tip_rarity"],
                "hint_level": resolved["hint_level"],
                "name": resolved["resolved_name"],
                "priority": resolved["priority"],
                "cost": resolved["cost"],
                "bundled_skill_ids": resolved.get("bundled_skill_ids") or [],
                "resolution_reason": resolved["resolution_reason"],
                "failed_scope": resolved["failed_scope"],
                "candidate_skill_ids": resolved["candidate_skill_ids"],
                "smart_score": resolved.get("smart_score", 0),
                "smart_reasons": resolved.get("smart_reasons", []),
                "skill_profile": resolved.get("skill_profile", ""),
                "skill_color": resolved.get("skill_color", "other"),
            })
        cfg = self._skill_config(preset)
        if cfg["skill_spending_strategy"] == "optimize_rank":
            # smart_score now already embeds the (grade/cost)*aptitude
            # primary key, so we no longer divide by cost again here (that would
            # over-penalise cost as grade/cost^2).  Cheaper skill breaks ties.
            result.sort(key=lambda item: (
                -float(item.get("smart_score") or 0),
                int(item.get("cost") or 9999),
                item["skill_id"],
            ))
        else:
            result.sort(key=lambda item: (item["priority"], -float(item.get("smart_score") or 0), -item["hint_level"], item["cost"], item["skill_id"]))
        
        deduped = []
        seen = set()
        for item in result:
            if item["skill_id"] not in seen:
                seen.add(item["skill_id"])
                deduped.append(item)
        result = deduped

        # v2.1 - Owned-by-name backstop. A skill already owned (by base name,
        # ignoring rarity/tier marks) can never be re-selected: skills are
        # single-purchase, so a re-selection is a redundant, never-charged
        # attempt that pollutes the per-skill spend log (the "1,890 on one
        # skill" symptom). resolve_skill_tip already drops owned ids; this
        # catches name/group mismatches.
        if owned:
            owned_base_names = {norm(strip_mark(self.skill_names.get(sid, ""))) for sid in owned if sid}
            result = [item for item in result if norm(strip_mark(item.get("name", ""))) not in owned_base_names]

        # v7.3 — Manual skill tier override.
        #
        # When the user has disabled "Enable Skill Point Check Plan (Beta)"
        # AND populated at least one tier in manual_skill_tiers, the bot
        # short-circuits the smart scorer above and uses the tier list
        # directly. Each candidate's name is looked up in the user's tier
        # map; tiers are sorted ascending (tier 1 highest priority), with
        # smart_score / cost as tiebreakers within a tier so the same skill
        # at multiple available hint levels still picks the highest-impact
        # variant first.
        #
        # If the plan-check toggle is off but all tiers are empty, this
        # block silently no-ops and the smart-scorer ordering above is used —
        # so flipping the toggle never bricks skill purchasing if the user
        # hasn't built a tier list yet.
        # v2.1: manual skill tiers are now MANUAL MODE and no longer require the
        # "Enable Skill Point Check Plan" toggle to be off (that gating silently
        # ignored the user's tier list under the default). When the user has
        # populated manual_skill_tiers, those are the skills to buy, ordered by
        # tier. The "don't spend extra skill points" toggle (default ON) then
        # makes the bot STOP after the listed skills, leaving remaining SP unspent;
        # turn it OFF to let the auto plan spend the rest (distance/style filtered).
        tier_map = self._manual_tier_lookup(preset)
        if tier_map:
            manual_items = [item for item in result if item.get("name") in tier_map]
            manual_items.sort(key=lambda item: (
                tier_map.get(item.get("name"), 999),  # tier ascending (tier 1 first)
                -float(item.get("smart_score") or 0),
                int(item.get("cost") or 9999),
                item["skill_id"],
            ))
            # v2.1 - Manual mode buys ONLY the listed skills. Once every listed
            # skill is owned, the bot stops -- unless the user enabled the
            # auto-fallback toggle (then the auto plan spends the rest). Legacy
            # manual_skill_tiers_dont_spend_extra=False also enables fallback.
            auto_fallback = bool(preset.get("skill_manual_auto_fallback", False))
            if not auto_fallback and preset.get("manual_skill_tiers_dont_spend_extra", True) is False:
                auto_fallback = True
            if manual_items:
                result = manual_items
            elif not auto_fallback:
                result = []
            # else: auto_fallback + no listed skills left -> keep the full auto result
        
        # v2.1 - Auto stop-after-recommended. Once the character's recommended /
        # best skills (preferred_skill_names + community SS/S) are all owned,
        # stop generating candidates so SP isn't dumped into marginal skills.
        # Bypassed pre-finals (turn >= pre_finals_skill_turn) so the trainee
        # still gets kitted for the climax, and skipped in manual / user-list mode.
        if cfg["skill_stop_after_recommended"]:
            _turn_now = int(chara.get("turn") or 0)
            _pre_finals = int(preset.get("pre_finals_skill_turn") or 73)
            if _turn_now < _pre_finals and not tier_map:
                _recommended = self._recommended_skill_names(preset, profile)
                if _recommended and result and not any(
                    norm(strip_mark(item.get("name", ""))) in _recommended for item in result
                ):
                    _log_funnel("stop_after_recommended: none of the resolved skills are character-recommended", 0)
                    return []

        if preset.get("learn_skill_only_user_provided"):
            if not any(row for row in (preset.get("learn_skill_list") or [])):
                _log_funnel("learn_skill_only_user_provided but learn_skill_list is empty", 0)
                return []
            _user = [item for item in result if item["priority"] < 999]
            _log_funnel("learn_skill_only_user_provided filter", len(_user))
            return _user
        _log_funnel("smart-score gate / post-resolve filters", len(result))
        return result

    def _manual_tier_lookup(self, preset):
        """Return {skill_name: tier_int} from preset.manual_skill_tiers.

        Lower tier numbers = higher priority. If a skill appears in multiple
        tiers (the UI shouldn't allow this but be defensive), the LOWER tier
        (higher priority) wins.
        """
        tiers = (preset or {}).get("manual_skill_tiers") or {}
        if not isinstance(tiers, dict):
            return {}
        lookup = {}
        for tier_key, names in tiers.items():
            try:
                tier_num = int(tier_key)
            except (TypeError, ValueError):
                continue
            if tier_num < 1 or tier_num > 5:
                continue
            for name in (names or []):
                if not name: continue
                name_str = str(name)
                if name_str not in lookup or tier_num < lookup[name_str]:
                    lookup[name_str] = tier_num
        return lookup

    def resolve_skill_tip(self, tip, owned_skill_ids, owned_groups, priority, blacklist, preset, profile=None):
        group_id = int(tip.get("group_id") or 0)
        tip_rarity = int(tip.get("rarity") or 0)
        hint_level = int(tip.get("level") or 0)
        failed = self._failed_for_turn()
        if tip_rarity:
            buyable_tier = self._resolve_buyable_tier(group_id, tip_rarity, owned_skill_ids)
            candidate_skill_ids = [buyable_tier] if buyable_tier else []
        else:
            candidate_skill_ids = [
                sid for sid in self.group_to_skill_ids.get(group_id, [])
                if sid not in owned_skill_ids
            ]
        
        row = {
            "group_id": group_id,
            "tip_rarity": tip_rarity,
            "hint_level": hint_level,
            "candidate_skill_ids": list(candidate_skill_ids),
            "resolved_skill_id": 0,
            "resolved_name": "",
            "cost": 0,
            "priority": 999,
            "resolution_reason": "",
            "master_exists": False,
            "skip_reason": None,
            "failed_scope": None,
            "smart_score": 0,
            "smart_reasons": [],
            "skill_profile": (profile or {}).get("key", ""),
            "skill_color": "other",
        }
        if not candidate_skill_ids:
            row["skip_reason"] = "unknown_master"
            return row

        usable = [sid for sid in candidate_skill_ids if sid not in failed]
        if not usable:
            row["skip_reason"] = "failed_this_turn"
            row["failed_scope"] = "this_turn"
            return row

        cfg = self._skill_config(preset)
        if cfg["purchase_negative_skills"]:
            normal = usable
        else:
            normal = [sid for sid in usable if not (self.skill_names.get(sid, "").endswith(MARK_X) or self.skill_names.get(sid, "").endswith(MOJI_X))]
        if not normal:
            row["skip_reason"] = "no_normal_skills"
            return row

        normal.sort(key=self._tier_sort_key)
        # Skills the user explicitly placed in manual_skill_tiers are honored even
        # if they are off-distance/off-style -- a manual choice overrides the auto
        # hard filters (but never the blacklist).
        manual_names = {norm(n) for n in self._manual_tier_lookup(preset or {})}
        valid_ranked = []
        for sid in normal:
            s_name = self.skill_names.get(sid, "")
            base_name = strip_mark(s_name)
            if sid in blacklist or norm(s_name) in blacklist or norm(base_name) in blacklist:
                row["skip_reason"] = "blacklist"
                return row
            manually_listed = norm(s_name) in manual_names or norm(base_name) in manual_names
            p_val = self._priority_value(sid, s_name, base_name, priority)
            profile_order = self._profile_name_priority(s_name, base_name, profile or {})
            if profile_order < 999:
                # Maruzensky-specific recommendations are the first shelf.
                p_val = min(p_val, 40 + min(profile_order, 39))
            else:
                p_val = min(p_val, self._community_priority_bucket(s_name, base_name))
            selected_style = self._selected_style_key(preset or {}, profile or {})
            mismatch, mismatch_reason = self._skill_style_mismatch(sid, selected_style)
            if mismatch and not manually_listed:
                # Style-exclusive skills that contradict Racing Settings should
                # never be purchased.  Neutral skills and matching-style skills
                # remain eligible.  Manually-tiered skills bypass this filter.
                continue
            dist_mismatch, dist_reason = self._skill_distance_mismatch(sid, profile or {})
            if dist_mismatch and not manually_listed:
                # Off-distance exclusive skills (e.g. a Long-only skill on a Miler)
                # are never auto-bought.  Manually-tiered skills bypass this filter.
                continue
            smart_score, smart_reasons = self._skill_smart_score(sid, s_name, base_name, hint_level, profile or {}, preset)
            if mismatch_reason:
                smart_reasons = [*smart_reasons, mismatch_reason]
            color = self._skill_color(sid, s_name)
            if p_val == 999 and any(s_name.endswith(m) for m in [MARK_WHITE_CIRCLE, MARK_LARGE_CIRCLE, MOJI_WHITE_CIRCLE, MOJI_LARGE_CIRCLE]):
                p_val = 720 if color == "green" else 500
            # Favor yellow inside equal buckets; greens can still win only when
            # they are explicitly recommended or much higher-scored.
            color_rank = {"yellow": 0, "unique": 0, "other": 1, "green": 2, "red": 3}.get(color, 1)
            valid_ranked.append((p_val, color_rank, -smart_score, self._tier_sort_key(sid), sid, smart_score, smart_reasons, color))

        if not valid_ranked:
            row["skip_reason"] = "style_mismatch_or_unknown_master"
            return row

        valid_ranked.sort()
        best_priority, _color_rank, neg_smart, _, resolved, smart_score, smart_reasons, skill_color = valid_ranked[0]
        name = self.skill_names.get(resolved, "")
        reason = "priority_match" if best_priority < 500 else ("smart_profile" if smart_score > 0 else "circle_variant" if best_priority == 500 else "first_valid_variant")

        if not name:
            row["skip_reason"] = "unknown_master"
            return row
            
        is_double = name.endswith(MARK_DOUBLE_CIRCLE) or name.endswith(MOJI_DOUBLE_CIRCLE)
        if preset.get("skip_double_circle_unless_high_hint", False) and is_double and hint_level < 4:
            row["skip_reason"] = "rule_rejected"
            return row

        row["resolved_skill_id"] = resolved
        row["resolved_name"] = name
        bundled_skill_ids = []
        cost = self._estimate_cost({"skill_id": resolved, "hint_level": hint_level, "name": name})
        if self.skill_rarities.get(resolved, 0) == 2:
            bundled_skill_ids = self._unowned_white_tiers(group_id, owned_skill_ids)
            for bundled_id in bundled_skill_ids:
                cost += self._estimate_cost({
                    "skill_id": bundled_id,
                    "hint_level": 0,
                    "name": self.skill_names.get(bundled_id, ""),
                })

        row["priority"] = best_priority
        row["smart_score"] = smart_score
        row["smart_reasons"] = smart_reasons
        row["cost"] = cost
        row["bundled_skill_ids"] = bundled_skill_ids
        row["resolution_reason"] = reason
        row["master_exists"] = resolved in self.skill_id_exists
        row["skill_color"] = skill_color
        if resolved in failed:
            row["failed_scope"] = "this_turn"

        return row

    def _buy_batch(self, client, state, candidates, turn):
        if not candidates:
            return state, 0

        data = state.get("data") or {}
        chara = data.get("chara_info") or data.get("single_mode_chara_light") or {}
        current_turn = int(chara.get("turn") or 0)
        
        if current_turn != turn:
            self.last_result = {"skip": "stale_turn_detected", "request_current_turn": turn, "source_state_turn": current_turn}
            return state, 0

        valid_tips = set()
        for tip in chara.get("skill_tips_array") or []:
            group_id = int(tip.get("group_id") or 0)
            valid_tips.update(self.group_to_skill_ids.get(group_id, []))

        points = int(chara.get("skill_point") or 0)
        selected_total_cost = 0
        valid_candidates = []

        for item in candidates:
            skill_id = item["skill_id"]
            cost = int(item.get("cost") or 0)
            if skill_id <= 0 or item.get("skip_reason"):
                item["preflight_error"] = "invalid_skill"
                continue
            if skill_id not in valid_tips:
                item["preflight_error"] = "not_in_tips"
                continue
            if selected_total_cost + cost > points:
                item["preflight_error"] = "unaffordable"
                continue
            item["preflight_passed"] = True
            selected_total_cost += cost
            valid_candidates.append(item)

        if not valid_candidates:
            self.last_result = {"skip": "preflight_failed", "turn": turn, "points": points}
            return state, 0

        payload = []
        payload_ids = set()
        for item in valid_candidates:
            for skill_id in [item["skill_id"], *(item.get("bundled_skill_ids") or [])]:
                skill_id = int(skill_id or 0)
                if skill_id > 0 and skill_id not in payload_ids:
                    payload.append({"skill_id": skill_id, "level": 1})
                    payload_ids.add(skill_id)
        self.last_attempt = [dict(item) for item in valid_candidates]
        event = {
            "turn": turn,
            "selected": [dict(item) for item in candidates],
            "attempt": [dict(item) for item in valid_candidates],
            "payload": payload,
            "result": {},
        }
        self.attempt_events.append(event)

        # DEV-ONLY web skill intercept (broker). When enabled (dev dashboard
        # toggle), block until the user confirms / edits / skips in the browser;
        # when disabled (the default), proceed with the computed payload.
        intercept_used = False
        if skill_intercept.is_enabled():
            cost_by_id = {int(c.get("skill_id") or 0): int(c.get("cost") or 0) for c in valid_candidates}
            cands = [{"id": int(it["skill_id"]),
                      "name": self.skill_names.get(it["skill_id"], "Unknown"),
                      "cost": cost_by_id.get(int(it["skill_id"]), 0)} for it in payload]
            # Catalog of every skill the trainee can buy this turn (all variants of
            # each available tip group) with name + cost, so the popup can show what
            # a typed-in ID is / costs and warn before the SP budget is exceeded.
            catalog = self._intercept_catalog(chara, valid_candidates, cost_by_id)
            decision = skill_intercept.request_decision(cands, turn, skill_point=points, catalog=catalog)
            action = decision.get("action")
            if action == "skip":
                self.last_result = {"skip": "user_skipped", "turn": turn, "points": points}
                event["result"] = self.last_result
                return state, 0
            # A confirm/proceed means the user spent time in the modal, so the
            # runner thread was blocked (possibly for minutes). That stales the
            # per-turn skill-buy state and the game then refuses the late buy with
            # result_code 205 -> refresh the state before buying (below).
            intercept_used = True
            if action == "confirm":
                # Keep the user's chosen ids that are real/buyable this turn AND fit
                # the SP budget. ids arrive ticked-first then typed-last, so the
                # affordability trim drops the typed extras first. This fixes
                # "ticked a skill + typed the gold's ID -> bought NEITHER": gain_skills
                # is all-or-nothing, so one unaffordable/un-buyable extra used to fail
                # the WHOLE purchase. Now we drop it and still buy the rest.
                _cost = {int(k): int(v.get("cost") or 0) for k, v in (catalog or {}).items()}
                _cost.update(cost_by_id)
                _buyable = set(_cost.keys())
                kept_ids, dropped, running = [], [], 0
                for raw in (decision.get("ids") or []):
                    sid = int(raw or 0)
                    if sid <= 0 or sid in kept_ids:
                        continue
                    if sid not in _buyable:
                        dropped.append([sid, "not_buyable_this_turn"]); continue
                    c = _cost.get(sid, 0)
                    if running + c > points:
                        dropped.append([sid, "over_budget"]); continue
                    running += c
                    kept_ids.append(sid)
                if dropped:
                    print(f"[skill-intercept] turn {turn}: SP {points}; buying {kept_ids} "
                          f"(~{running} SP); skipped {dropped}")
                payload = [{"skill_id": i, "level": 1} for i in kept_ids]
                payload_ids = set(kept_ids)
                event["payload"] = payload
                if not payload:
                    self.last_result = {"skip": "empty_payload", "turn": turn, "points": points, "dropped": dropped}
                    event["result"] = self.last_result
                    return state, 0
            # action == "proceed": keep the bot's computed payload unchanged.

        # Refresh-then-buy (fix #1): the web intercept can block the runner for
        # minutes while the user decides; a gain_skills issued that long after the
        # skill phase opened is refused by the game (result_code 205). When the
        # intercept was used, reload the single-mode state so the buy is fresh.
        if intercept_used:
            state = self._reload_state(client, state)
            ref_chara = (state.get("data") or {}).get("chara_info") or (state.get("data") or {}).get("single_mode_chara_light") or {}
            points = int(ref_chara.get("skill_point") or points)

        # Verify-and-retry (fix #2): gain_skills can return a 205 refusal or a 208
        # 'busy' envelope that grants nothing yet looks non-fatal (client.py returns
        # the 208 res for gain_skills instead of raising). The old code then recorded
        # "ok" with 0 skills AND marked them acquired -> a silent failure that also
        # blocked any retry. Now: confirm the grant against the reloaded state, retry
        # on a genuine non-grant, and only record "ok" / mark acquired once confirmed.
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                result = client.gain_skills(payload, turn)
            except Exception as exc:
                if attempt < max_attempts and any(code in str(exc) for code in ("201", "205", "208")):
                    print(f"[skill-buy] gain_skills raised '{exc}' (attempt {attempt}/{max_attempts}); refreshing + retrying")
                    state = self._reload_state(client, state)
                    continue
                print(f"Skill Purchase Error at turn {turn}: {exc}")
                if any(code in str(exc) for code in ("201", "205", "208")):
                    self.recover_after_error = True
                self._failed_for_turn(turn).update(int(item["skill_id"]) for item in valid_candidates)
                self.last_result = {"result": "failed", "turn": turn, "error": str(exc), "payload": payload}
                event["result"] = self.last_result
                return state, 0

            rc = int(((result or {}).get("data_headers") or {}).get("result_code") or 0) if isinstance(result, dict) else 0
            merged = self._merge_state(state, result)
            confirmed, sp_after, actual_spent = self._confirm_purchases(merged, valid_candidates, points)

            # Clean success that the (possibly partial) skill_array didn't list yet:
            # reload once to get the authoritative owned set before recording.
            if rc == 1 and not confirmed:
                merged = self._reload_state(client, merged)
                confirmed, sp_after, actual_spent = self._confirm_purchases(merged, valid_candidates, points)

            if rc == 1 or confirmed:
                self._acquired_skill_ids |= payload_ids   # mark only on a real buy
                self.last_selected = [dict(item) for item in confirmed]
                self.last_actual_spent = actual_spent
                self.last_result = {"result": "ok", "turn": turn, "count": len(confirmed),
                                    "requested": len(valid_candidates), "actual_spent": actual_spent,
                                    "payload": payload, "attempts": attempt}
                event["result"] = self.last_result
                event["actual_spent"] = actual_spent
                event["confirmed_count"] = len(confirmed)
                self._failed_for_turn(turn).clear()
                return merged, len(confirmed)

            # Nothing granted (e.g. 205 refusal / 208 busy envelope): reload to be
            # sure it truly didn't go through, then retry the buy against fresh state.
            print(f"[skill-buy] turn {turn}: gain_skills granted nothing (rc={rc}), attempt {attempt}/{max_attempts}")
            state = self._reload_state(client, state)
            confirmed, sp_after, actual_spent = self._confirm_purchases(state, valid_candidates, points)
            if confirmed:
                self._acquired_skill_ids |= payload_ids
                self.last_selected = [dict(item) for item in confirmed]
                self.last_actual_spent = actual_spent
                self.last_result = {"result": "ok", "turn": turn, "count": len(confirmed),
                                    "requested": len(valid_candidates), "actual_spent": actual_spent,
                                    "payload": payload, "attempts": attempt}
                event["result"] = self.last_result
                event["actual_spent"] = actual_spent
                event["confirmed_count"] = len(confirmed)
                self._failed_for_turn(turn).clear()
                return state, len(confirmed)

        # Exhausted all attempts without a confirmed grant: record a CLEAR failure
        # and do NOT mark acquired, so these skills are retried on a later turn.
        self.recover_after_error = True
        self._failed_for_turn(turn).update(int(item["skill_id"]) for item in valid_candidates)
        self.last_result = {"result": "failed", "turn": turn,
                            "error": f"no skills granted after {max_attempts} attempts (likely 205/stale skill state)",
                            "requested": len(valid_candidates), "payload": payload, "attempts": max_attempts}
        event["result"] = self.last_result
        return state, 0

    def _intercept_catalog(self, chara, valid_candidates, cost_by_id=None):
        """DEV intercept: {str(skill_id): {"name","cost"}} for every skill the
        trainee can buy this turn (all variants of each available tip group), so the
        popup can resolve a typed-in ID to its name + cost and check the SP budget.
        Costs are estimated at each tip's hint level; the bot's own picks carry their
        authoritative cost."""
        catalog = {}
        cost_by_id = cost_by_id or {}
        for tip in (chara.get("skill_tips_array") or []):
            gid = int(tip.get("group_id") or 0)
            hint = int(tip.get("level") or tip.get("hint_level") or 0)
            for sid in (self.group_to_skill_ids.get(gid, []) or []):
                sid = int(sid or 0)
                if sid <= 0 or str(sid) in catalog:
                    continue
                name = self.skill_names.get(sid, "")
                try:
                    cost = int(self._estimate_cost({"skill_id": sid, "name": name, "hint_level": hint}))
                except Exception:
                    cost = int(self.skill_costs.get(sid, 0) or 0)
                catalog[str(sid)] = {"name": name or f"Skill {sid}", "cost": cost}
        for c in (valid_candidates or []):
            sid = int(c.get("skill_id") or 0)
            if sid > 0:
                catalog[str(sid)] = {"name": self.skill_names.get(sid, f"Skill {sid}"),
                                     "cost": int(cost_by_id.get(sid, c.get("cost") or 0))}
        return catalog

    def _reload_state(self, client, state):
        """Best-effort reload of the single-mode state (single_mode_free/load) so a
        following gain_skills is issued against a fresh server context. The web
        intercept can block the runner for minutes, staling the per-turn skill-buy
        state and making the game refuse the purchase with result_code 205. Mirrors
        the runner's reload-and-reconcile pattern for race_entry 205/208."""
        loader = getattr(client, "load_career", None)
        if not callable(loader):
            return state
        try:
            return self._merge_state(state, loader())
        except Exception as exc:
            print(f"[skill-buy] state refresh failed (continuing with cached state): {exc}")
            return state

    def _confirm_purchases(self, state_after, valid_candidates, points_before):
        """Return (confirmed_items, sp_after, actual_spent): which of the attempted
        skills the server actually granted. Skills are single-purchase, so the server
        silently no-ops already-owned ids; only confirmed grants are recorded."""
        after_chara = (state_after.get("data") or {}).get("chara_info") or (state_after.get("data") or {}).get("single_mode_chara_light") or {}
        sp_after = int(after_chara.get("skill_point") or 0)
        actual_spent = max(0, int(points_before) - sp_after)
        owned_after = {int(item.get("skill_id") or 0) for item in (after_chara.get("skill_array") or [])}
        confirmed = [
            item for item in valid_candidates
            if int(item["skill_id"]) in owned_after
            or any(int(b) in owned_after for b in (item.get("bundled_skill_ids") or []))
        ]
        return confirmed, sp_after, actual_spent

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



    def _estimate_cost(self, candidate):
        name = candidate.get("name") or ""
        skill_id = candidate.get("skill_id") or 0
        level = candidate.get("hint_level") or 0
        
        is_circle = any(m in name for m in [MARK_WHITE_CIRCLE, MARK_LARGE_CIRCLE, MOJI_WHITE_CIRCLE, MOJI_LARGE_CIRCLE])
        
        if is_circle:
            base = 130
        elif skill_id >= 900000:
            base = 200
        else:
            base = self.skill_costs.get(skill_id)
            if not base:
                base = 200 if self.skill_rarities.get(skill_id, 0) >= 2 else 160
        return max(1, int(base * (100 - min(level, 5) * 10) / 100))

