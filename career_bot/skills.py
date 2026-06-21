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
IRRELEVANT_STYLE_TAGS = {SKILL_TAG_FRONT, SKILL_TAG_PACE, SKILL_TAG_LATE, SKILL_TAG_END}
IRRELEVANT_DISTANCE_TAGS = {SKILL_TAG_SPRINT, SKILL_TAG_MILE, SKILL_TAG_MEDIUM, SKILL_TAG_LONG}


def norm(text):
    return re.sub(r'[^a-z0-9]+', '', str(text or '').lower())


def strip_mark(text):
    if not text:
        return ""
    for m in [MARK_WHITE_CIRCLE, MARK_DOUBLE_CIRCLE, MARK_X, MARK_LARGE_CIRCLE,
              MOJI_WHITE_CIRCLE, MOJI_DOUBLE_CIRCLE, MOJI_X, MOJI_LARGE_CIRCLE]:
        text = text.replace(m, "")
    return text.strip()


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
        self.last_attempt = []
        self.last_result = {}
        self.recover_after_error = False
        self.attempt_events = []
        self._load()

    def _load(self):
        path = self.base_dir / "data" / "skill_data.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.skill_names = {}
            self.skill_rarities = {}
            self.skill_costs = {}
            self.skill_grade_values = {}
            self.skill_tags = {}
            self.skill_categories = {}
            self.skill_icons = {}
            self.official_skill_weights = {}
            self.skill_to_group_id = {}
            for raw_id, raw_info in data.items():
                skill_id = int(raw_id)
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
            return
        self._load_community_tiers()
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
            if int(row.get("disable_singlemode") or condition_row.get("disable_singlemode") or 0):
                score -= 120
            if int(row.get("is_general_skill") or condition_row.get("is_general_skill") or 0):
                score += 6
            self.official_skill_weights[skill_id] = {
                "score": round(score, 2),
                "cost": cost,
                "grade_value": grade,
                "ability_types": ability_types,
                "conditions": conditions,
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
        return {norm(item) for item in preset.get("learn_skill_blacklist") or []}

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

        tier_score, tier = self._community_tier_score(name, base_name)
        if tier_score:
            score += tier_score * float(weights.get("community", 1.0))
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

    def _candidates(self, chara, preset):
        owned = {int(item.get("skill_id") or 0) for item in chara.get("skill_array") or []}
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
        for tip in chara.get("skill_tips_array") or []:
            resolved = self.resolve_skill_tip(tip, owned, owned_groups, priority, blacklist, preset, profile)
            if not resolved or resolved.get("skip_reason"):
                continue
            if profile and resolved.get("priority", 999) >= 999 and float(resolved.get("smart_score") or 0) < smart_min_score:
                continue
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
        plan_check_enabled = bool(preset.get("enable_skill_point_check_plan", True))
        if not plan_check_enabled:
            tier_map = self._manual_tier_lookup(preset)
            if tier_map:
                filtered = [item for item in result if item.get("name") in tier_map]
                if filtered:
                    filtered.sort(key=lambda item: (
                        tier_map.get(item.get("name"), 999),  # tier ascending
                        -float(item.get("smart_score") or 0),
                        int(item.get("cost") or 9999),
                        item["skill_id"],
                    ))
                    result = filtered
        
        if preset.get("learn_skill_only_user_provided"):
            if not any(row for row in (preset.get("learn_skill_list") or [])):
                return []
            return [item for item in result if item["priority"] < 999]
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
        valid_ranked = []
        for sid in normal:
            s_name = self.skill_names.get(sid, "")
            base_name = strip_mark(s_name)
            if norm(s_name) in blacklist or norm(base_name) in blacklist:
                row["skip_reason"] = "blacklist"
                return row
            p_val = self._priority_value(sid, s_name, base_name, priority)
            profile_order = self._profile_name_priority(s_name, base_name, profile or {})
            if profile_order < 999:
                # Maruzensky-specific recommendations are the first shelf.
                p_val = min(p_val, 40 + min(profile_order, 39))
            else:
                p_val = min(p_val, self._community_priority_bucket(s_name, base_name))
            selected_style = self._selected_style_key(preset or {}, profile or {})
            mismatch, mismatch_reason = self._skill_style_mismatch(sid, selected_style)
            if mismatch:
                # Style-exclusive skills that contradict Racing Settings should
                # never be purchased.  Neutral skills and matching-style skills
                # remain eligible.
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

        try:
            result = client.gain_skills(payload, turn)
            self.last_result = {"result": "ok", "turn": turn, "count": len(valid_candidates), "payload": payload}
            event["result"] = self.last_result
            self._failed_for_turn(turn).clear()
            return self._merge_state(state, result), len(valid_candidates)
        except Exception as exc:
            print(f"Skill Purchase Error at turn {turn}: {exc}")
            if any(code in str(exc) for code in ("201", "205", "208")):
                self.recover_after_error = True
            self._failed_for_turn(turn).update(int(item["skill_id"]) for item in valid_candidates)
            self.last_result = {"result": "failed", "turn": turn, "error": str(exc), "payload": payload}
            event["result"] = self.last_result
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


    def _select_skill_id(self, group_id, priority, owned, rarity=0):
        owned_groups = {self.skill_to_group_id.get(sid, sid // 10) for sid in owned}
        resolved = self.resolve_skill_tip({"group_id": group_id, "rarity": rarity, "level": 0}, set(owned), owned_groups, priority, set(), {}, None)
        return int((resolved or {}).get("resolved_skill_id") or 0)

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

