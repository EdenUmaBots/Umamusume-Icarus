"""Dynamic trainee profile and weighted skill scoring helpers.

This module is intentionally standalone so the bot can use generated Game8 data,
manual overrides, and fallback profiles without coupling the career runner to the
scraper.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


RANK_VALUE = {"S": 7, "A": 6, "B": 5, "C": 4, "D": 2, "E": 1, "F": 0, "G": -1}

DEFAULT_WEIGHTS = {
    "character_recommended_bonus": 120,
    "community_tier_bonus": 90,
    "yellow_skill_bonus": 75,
    "style_match_bonus": 60,
    "distance_match_bonus": 55,
    "terrain_match_bonus": 35,
    "unique_synergy_bonus": 50,
    "green_skill_bonus": 10,
    "green_skill_overcap_penalty": -80,
    "wrong_style_penalty": -120,
    "wrong_distance_penalty": -90,
    "dirt_mismatch_penalty": -100,
    "fan_farming_bonus": 0,
    "parent_farming_bonus": 0,
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def normalize_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def load_profiles(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    generated = _load_json(root / "data" / "trainee_skill_profiles.generated.json")
    manual = _load_json(root / "data" / "trainee_skill_profiles.json")

    merged = dict(generated)
    # Manual wins. It is the tuning layer.
    merged.update(manual)
    if "__fallback__" not in merged:
        merged["__fallback__"] = {
            "name": "__fallback__",
            "track_aptitude": {"turf": "A", "dirt": "G"},
            "distance_aptitude": {"sprint": "C", "mile": "C", "medium": "C", "long": "C"},
            "style_aptitude": {"front": "C", "pace": "C", "late": "C", "end": "C"},
            "recommended_style": "front",
            "primary_distances": ["mile", "medium"],
            "secondary_distances": ["sprint", "long"],
            "avoid_distances": [],
            "preferred_skill_fragments": [],
            "avoid_skill_fragments": [],
            "green_skill_cap": 1,
        }
    return merged


def find_profile(root: str | Path, trainee_name: str = "", card_id: Any = None) -> dict[str, Any]:
    profiles = load_profiles(root)
    if trainee_name and trainee_name in profiles:
        return dict(profiles[trainee_name])

    target = normalize_name(trainee_name)
    if target:
        for name, profile in profiles.items():
            if name == "__fallback__":
                continue
            n = normalize_name(name)
            if n == target or target in n or n in target:
                return dict(profile)

    if card_id:
        card_text = str(card_id)
        for name, profile in profiles.items():
            if str(profile.get("card_id", "")) == card_text:
                return dict(profile)

    return dict(profiles.get("__fallback__", {}))


def _contains_any(text: str, fragments: list[str]) -> bool:
    haystack = text.lower()
    return any(str(fragment).lower() in haystack for fragment in fragments if fragment)


def classify_skill_color(skill: dict[str, Any] | str) -> str:
    if isinstance(skill, dict):
        explicit = str(skill.get("color") or skill.get("type") or "").lower()
        if explicit in {"yellow", "green", "blue", "red"}:
            return explicit
        icon_id = str(skill.get("icon_id") or "")
        if icon_id.startswith(("2001", "2004", "2005", "2006", "2009", "3")):
            return "yellow"
        if icon_id.startswith(("1001", "1002", "1003", "1004", "1005", "1006")):
            return "green"
        name = str(skill.get("name") or "")
    else:
        name = str(skill)
    low = name.lower()
    if any(token in low for token in ["◎", "○", "right-handed", "left-handed", "spring", "summer", "fall", "winter", "firm", "soft", "rainy"]):
        return "green"
    return "yellow"


def score_skill(
    skill: dict[str, Any] | str,
    profile: dict[str, Any],
    preset: dict[str, Any] | None = None,
    community_tier_score: int = 0,
    green_skills_already_selected: int = 0,
    trackblazer_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preset = preset or {}
    skill_policy = preset.get("skill_policy") or {}
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(skill_policy.get("weights") or {})

    name = skill.get("name", "") if isinstance(skill, dict) else str(skill)
    score = int(community_tier_score or 0)
    reasons = []

    if score:
        reasons.append(f"community_tier:+{score}")

    preferred = profile.get("preferred_skill_fragments") or []
    avoid = profile.get("avoid_skill_fragments") or []
    primary_distances = profile.get("primary_distances") or []
    secondary_distances = profile.get("secondary_distances") or []
    avoid_distances = profile.get("avoid_distances") or []
    recommended_style = profile.get("recommended_style") or ""

    if _contains_any(name, preferred):
        score += weights["character_recommended_bonus"]
        reasons.append(f"character:+{weights['character_recommended_bonus']}")

    if profile.get("unique_skill") and str(profile["unique_skill"]).lower() in name.lower():
        score += weights["unique_synergy_bonus"]
        reasons.append(f"unique:+{weights['unique_synergy_bonus']}")

    style_labels = {
        "front": ["Front Runner", "Runner", "Lead"],
        "pace": ["Pace Chaser"],
        "late": ["Late Surger"],
        "end": ["End Closer"],
    }
    if recommended_style and _contains_any(name, style_labels.get(recommended_style, [])):
        score += weights["style_match_bonus"]
        reasons.append(f"style:+{weights['style_match_bonus']}")

    wrong_style_labels = []
    for style, labels in style_labels.items():
        if style != recommended_style:
            wrong_style_labels.extend(labels)
    if _contains_any(name, wrong_style_labels):
        score += weights["wrong_style_penalty"]
        reasons.append(f"wrong_style:{weights['wrong_style_penalty']}")

    if _contains_any(name, [d.title() for d in primary_distances]):
        score += weights["distance_match_bonus"]
        reasons.append(f"distance:+{weights['distance_match_bonus']}")
    elif _contains_any(name, [d.title() for d in secondary_distances]):
        score += int(weights["distance_match_bonus"] * 0.45)
        reasons.append(f"secondary_distance:+{int(weights['distance_match_bonus'] * 0.45)}")

    if _contains_any(name, [d.title() for d in avoid_distances]):
        score += weights["wrong_distance_penalty"]
        reasons.append(f"wrong_distance:{weights['wrong_distance_penalty']}")

    track_apt = profile.get("track_aptitude") or {}
    if "dirt" in name.lower() and str(track_apt.get("dirt", "G")).upper() in {"D", "E", "F", "G"}:
        score += weights["dirt_mismatch_penalty"]
        reasons.append(f"dirt_mismatch:{weights['dirt_mismatch_penalty']}")
    if "turf" in name.lower() and str(track_apt.get("turf", "C")).upper() in {"S", "A", "B"}:
        score += weights["terrain_match_bonus"]
        reasons.append(f"terrain:+{weights['terrain_match_bonus']}")

    color = classify_skill_color(skill)
    if color == "yellow":
        score += weights["yellow_skill_bonus"]
        reasons.append(f"yellow:+{weights['yellow_skill_bonus']}")
    elif color == "green":
        max_green = int(skill_policy.get("max_green_skills", profile.get("green_skill_cap", 1)) or 1)
        score += weights["green_skill_bonus"]
        reasons.append(f"green:+{weights['green_skill_bonus']}")
        if green_skills_already_selected >= max_green:
            score += weights["green_skill_overcap_penalty"]
            reasons.append(f"green_cap:{weights['green_skill_overcap_penalty']}")

    mode = preset.get("strategy_mode") or preset.get("mode") or ""
    if mode == "fan_farming":
        # Fan farming values consistent race speed and high-impact passives.
        if color == "yellow":
            score += weights.get("fan_farming_bonus", 0)
            reasons.append(f"fan_mode:+{weights.get('fan_farming_bonus', 0)}")
    elif mode == "parent_farming":
        # Parent farming values compatible hint/factor skills over raw greed.
        if _contains_any(name, preferred):
            score += weights.get("parent_farming_bonus", 0)
            reasons.append(f"parent_mode:+{weights.get('parent_farming_bonus', 0)}")

    if trackblazer_context:
        common_distances = trackblazer_context.get("common_distances") or []
        if _contains_any(name, [d.title() for d in common_distances]):
            score += 30
            reasons.append("trackblazer_schedule:+30")

    return {"skill": name, "score": score, "color": color, "reasons": reasons}
