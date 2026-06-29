"""Shared Umamusume running-style helpers.

The game expects numeric running-style ids in the race-entry payload.  A few
older Pre Icarus surfaces used labels or zero-based UI positions, which can make
"Pace Chaser" accidentally become "Late Surger".  Keep all style conversion in
this tiny module so race entry and skill buying use the same source of truth.
"""

from __future__ import annotations

from typing import Any

STYLE_FRONT = 1  # Front Runner / Nige
STYLE_PACE = 2   # Pace Chaser / Senko
STYLE_LATE = 3   # Late Surger / Sashi
STYLE_END = 4    # End Closer / Oikomi

STYLE_ID_TO_KEY = {
    STYLE_FRONT: "front",
    STYLE_PACE: "pace",
    STYLE_LATE: "late",
    STYLE_END: "end",
}

STYLE_KEY_TO_ID = {value: key for key, value in STYLE_ID_TO_KEY.items()}

STYLE_LABELS = {
    STYLE_FRONT: "Front Runner",
    STYLE_PACE: "Pace Chaser",
    STYLE_LATE: "Late Surger",
    STYLE_END: "End Closer",
}

STYLE_ALIASES = {
    "front": STYLE_FRONT,
    "front runner": STYLE_FRONT,
    "nige": STYLE_FRONT,
    "escape": STYLE_FRONT,
    "pace": STYLE_PACE,
    "pace chaser": STYLE_PACE,
    "pace-chaser": STYLE_PACE,
    "leader": STYLE_PACE,
    "senko": STYLE_PACE,
    "senkou": STYLE_PACE,
    "late": STYLE_LATE,
    "late surger": STYLE_LATE,
    "late-surger": STYLE_LATE,
    "betweener": STYLE_LATE,
    "sashi": STYLE_LATE,
    "end": STYLE_END,
    "end closer": STYLE_END,
    "end-closer": STYLE_END,
    "chaser": STYLE_END,
    "oikomi": STYLE_END,
}


def normalize_running_style(value: Any, default: int | None = STYLE_PACE) -> int | None:
    """Return the game payload id for a running style.

    Accepts ids, numeric strings, internal keys (``front``/``pace``/``late``/``end``),
    and user-facing labels.  ``0``/``auto`` return ``default``.
    """

    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        if value in STYLE_LABELS:
            return value
        if value == 0:
            return default
        return default

    text = str(value or "").strip().lower().replace("_", " ")
    if not text or text in {"0", "auto", "automatic", "default"}:
        return default
    if text.isdigit():
        parsed = int(text)
        return parsed if parsed in STYLE_LABELS else default
    return STYLE_ALIASES.get(text, default)


def running_style_key(value: Any, default: str = "pace") -> str:
    style_id = normalize_running_style(value, STYLE_KEY_TO_ID.get(default, STYLE_PACE))
    return STYLE_ID_TO_KEY.get(style_id or STYLE_PACE, default)


def running_style_label(value: Any, default: str = "Pace Chaser") -> str:
    style_id = normalize_running_style(value, None)
    return STYLE_LABELS.get(style_id or 0, default)


def _lookup_distance_strategy(mapping: dict[str, Any], bucket: str | None) -> Any:
    if not isinstance(mapping, dict) or not bucket:
        return None
    bucket = str(bucket).lower()
    aliases = {
        "short": ("short", "sprint"),
        "sprint": ("sprint", "short"),
        "middle": ("middle", "medium"),
        "medium": ("medium", "middle"),
        "mile": ("mile",),
        "long": ("long",),
    }
    for key in aliases.get(bucket, (bucket,)):
        value = mapping.get(key) or mapping.get(str(key).title())
        if value not in (None, "", 0, "0", "auto"):
            return value
    return None


def resolve_running_style_for_race(
    preset: dict[str, Any] | None,
    distance_bucket: str | None = None,
    turn: int | None = None,
    default: int | None = None,
) -> int | None:
    """Resolve the running style for an actual race entry.

    Priority:
    1. Per-distance strategy when enabled.
    2. Junior-year strategy during Junior turns.
    3. Main Racing Settings style.
    4. Legacy ``original_running_style`` fallback.
    """

    preset = preset or {}
    cfg = preset.get("mant_config") or {}
    if not isinstance(cfg, dict):
        cfg = {}

    per_distance_enabled = bool(cfg.get("enable_per_distance_strategy") or preset.get("enable_per_distance_strategy"))
    if per_distance_enabled:
        by_distance = cfg.get("race_strategy_by_distance") or preset.get("race_strategy_by_distance") or {}
        style = normalize_running_style(_lookup_distance_strategy(by_distance, distance_bucket), None)
        if style in STYLE_LABELS:
            return style

    try:
        turn_i = int(turn or 0)
    except Exception:
        turn_i = 0
    if 0 < turn_i <= 24:
        style = normalize_running_style(cfg.get("junior_running_style") or preset.get("junior_running_style"), None)
        if style in STYLE_LABELS:
            return style

    return normalize_running_style(
        preset.get("running_style") or cfg.get("original_running_style") or cfg.get("running_style"),
        default,
    )


def resolve_skill_running_style(preset: dict[str, Any] | None, default: int | None = STYLE_PACE) -> int | None:
    """Resolve the style the skill buyer should respect.

    Skill strategy may still be set to ``auto``; in that case Racing Settings are
    the single source of truth.
    """

    preset = preset or {}
    strategy = preset.get("skill_strategy") or {}
    if isinstance(strategy, dict):
        style = normalize_running_style(strategy.get("running_style"), None)
        if style in STYLE_LABELS:
            return style
    return resolve_running_style_for_race(preset, None, None, default)
