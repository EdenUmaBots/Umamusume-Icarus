"""Event Outcome Knowledge Base for SweepyCL.

This module imports already-collected, static event outcome data (for example the
safe ``outcomes.json`` produced by external research/dumper tools) and normalizes
it into SweepyCL's event-choice scoring schema.  It deliberately contains no
Frida hooks, packet interception, memory access, or game-process integration.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

VERSION = "SweepyCL Event Outcome KB v1"
BUNDLED_IMPORT = "dumper_outcomes_import.json"
OUTCOMES_FILE = "event_outcomes.json"
IMPORT_REPORT = "event_outcome_import_report.json"
DATASET_FILE = "event_outcome_rows.jsonl"

STAT_KEYS = ("speed", "stamina", "power", "guts", "wiz")
NUMERIC_KEYS = STAT_KEYS + ("vital", "max_vital", "skill_point", "motivation", "playing_state")
LIST_KEYS = ("gained_conditions", "lost_conditions")
DICT_KEYS = ("gained_skill_hints",)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def runtime_output_root(base_dir: Any) -> Path:
    override = os.environ.get("UMA_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(base_dir).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate / "uma_runtime"
    return base.parent / "uma_runtime"


def ai_root(base_dir: Any) -> Path:
    return runtime_output_root(base_dir) / "ai"


def project_base(base_dir: Any) -> Path:
    base = Path(base_dir).resolve()
    for candidate in (base, *base.parents):
        if (candidate / "data" / OUTCOMES_FILE).exists() or (candidate / "data" / BUNDLED_IMPORT).exists():
            return candidate
    # Common case when called with uma_runtime/ai.
    if base.name == "ai" and base.parent.name == "uma_runtime":
        return base.parent.parent
    if base.name == "uma_runtime":
        return base.parent
    return base


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        json.loads(tmp.read_text(encoding="utf-8"))
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _append_jsonl_rows(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
            count += 1
    return count


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return float(default)


def _clean_event_name(name: Any) -> str:
    return " ".join(str(name or "").strip().split())


def _slug_event_name(name: str) -> str:
    keep = []
    for ch in _clean_event_name(name).lower():
        if ch.isalnum():
            keep.append(ch)
        elif ch in {" ", "-", "_", "'", "!", "?", "."}:
            keep.append("_")
    slug = "".join(keep).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "event"


def _normalize_reward(raw: Mapping[str, Any]) -> Dict[str, Any]:
    reward: Dict[str, Any] = {}
    if not isinstance(raw, Mapping):
        return reward
    for key in NUMERIC_KEYS:
        if key in raw:
            val = _safe_float(raw.get(key))
            reward[key] = int(val) if float(val).is_integer() else val
    for key in LIST_KEYS:
        val = raw.get(key)
        if isinstance(val, list):
            reward[key] = sorted({_safe_int(v) for v in val})
    for key in DICT_KEYS:
        val = raw.get(key)
        if isinstance(val, Mapping):
            reward[key] = {str(k): _safe_int(v) for k, v in val.items()}
    if reward.get("gained_skill_hints"):
        reward["skill_hint"] = True
    return reward


def _merge_rewards(current: Optional[Mapping[str, Any]], incoming: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(current or {})
    for key, value in incoming.items():
        if key in NUMERIC_KEYS:
            old = out.get(key)
            if old is None or abs(_safe_float(value)) > abs(_safe_float(old)):
                out[key] = value
        elif key in LIST_KEYS:
            merged = set(out.get(key) or [])
            if isinstance(value, list):
                merged.update(_safe_int(v) for v in value)
            out[key] = sorted(merged)
        elif key == "gained_skill_hints" and isinstance(value, Mapping):
            hints = dict(out.get(key) or {})
            for sid, level in value.items():
                hints[str(sid)] = max(_safe_int(hints.get(str(sid))), _safe_int(level))
            out[key] = hints
            out["skill_hint"] = True
        elif key == "skill_hint":
            out[key] = bool(out.get(key) or value)
        else:
            out[key] = value
    return out


def _reward_label(reward: Mapping[str, Any]) -> str:
    parts: List[str] = []
    for key in STAT_KEYS:
        val = _safe_float(reward.get(key), 0.0)
        if val:
            parts.append(f"{key} {val:+g}")
    for key, label in (("skill_point", "SP"), ("vital", "energy"), ("max_vital", "max energy"), ("motivation", "motivation")):
        val = _safe_float(reward.get(key), 0.0)
        if val:
            parts.append(f"{label} {val:+g}")
    hints = reward.get("gained_skill_hints") if isinstance(reward, Mapping) else None
    if isinstance(hints, Mapping) and hints:
        parts.append(f"skill hints {len(hints)}")
    if reward.get("gained_conditions"):
        parts.append(f"conditions +{len(reward.get('gained_conditions') or [])}")
    if reward.get("lost_conditions"):
        parts.append(f"conditions -{len(reward.get('lost_conditions') or [])}")
    return ", ".join(parts) if parts else "known outcome"


def _outcome_score_hint(reward: Mapping[str, Any]) -> float:
    score = 0.0
    for key in STAT_KEYS:
        score += _safe_float(reward.get(key), 0.0)
    score += _safe_float(reward.get("skill_point"), 0.0) * 0.35
    score += _safe_float(reward.get("vital"), 0.0) * 1.4
    score += _safe_float(reward.get("max_vital"), 0.0) * 2.0
    score += _safe_float(reward.get("motivation"), 0.0) * 25.0
    if reward.get("gained_skill_hints"):
        score += 12.0 * len(reward.get("gained_skill_hints") or {})
    return round(score, 4)


def normalize_dumper_outcomes(payload: Mapping[str, Any], *, source: str = "dumper_outcomes_import") -> Dict[str, Dict[str, Any]]:
    """Normalize the public/static dumper ``outcomes.json`` structure.

    Source shape:
        event_name -> choice_slot -> select_index -> reward deltas

    Sweepy shape:
        key -> {event_name, details, outcomes, choice_slots, source, confidence}
    """
    normalized: Dict[str, Dict[str, Any]] = {}
    if not isinstance(payload, Mapping):
        return normalized
    for event_name_raw, slot_map in payload.items():
        event_name = _clean_event_name(event_name_raw)
        if not event_name or not isinstance(slot_map, Mapping):
            continue
        key = f"event:{_slug_event_name(event_name)}"
        entry = {
            "event_name": event_name,
            "source": source,
            "confidence": "imported_static",
            "details": {},
            "outcomes": {},
            "choice_slots": {},
            "observations": 0,
        }
        for slot_key, choices in slot_map.items():
            if not isinstance(choices, Mapping):
                continue
            slot_id = str(slot_key)
            entry["choice_slots"].setdefault(slot_id, {})
            for select_index_raw, raw_reward in choices.items():
                reward = _normalize_reward(raw_reward if isinstance(raw_reward, Mapping) else {})
                if not reward:
                    continue
                select_index = str(select_index_raw)
                entry["choice_slots"][slot_id][select_index] = reward
                entry["details"][select_index] = _merge_rewards(entry["details"].get(select_index), reward)
                entry["observations"] += 1
        for select_index, reward in sorted(entry["details"].items(), key=lambda kv: _safe_int(kv[0], 999)):
            entry["outcomes"][select_index] = _reward_label(reward)
        if entry["details"]:
            entry["choice_count"] = len(entry["details"])
            normalized[key] = entry
    return normalized


def _is_dumper_shape(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping) or not payload:
        return False
    sample = next(iter(payload.values()))
    return isinstance(sample, Mapping) and not any(k in sample for k in ("event_name", "details", "outcomes"))


def load_outcomes(base_dir: Any) -> Dict[str, Any]:
    path = project_base(base_dir) / "data" / OUTCOMES_FILE
    data = _read_json(path, {})
    return data if isinstance(data, dict) else {}


def load_bundled_import(base_dir: Any) -> Dict[str, Any]:
    path = project_base(base_dir) / "data" / BUNDLED_IMPORT
    data = _read_json(path, {})
    return data if isinstance(data, dict) else {}


def import_outcomes(base_dir: Any, *, source_path: Optional[Any] = None, replace: bool = False) -> Dict[str, Any]:
    base = project_base(base_dir)
    existing = {} if replace else load_outcomes(base)
    path = Path(source_path).expanduser() if source_path else base / "data" / BUNDLED_IMPORT
    payload = _read_json(path, {})
    if not isinstance(payload, Mapping) or not payload:
        raise ValueError(f"No importable outcome data found at {path}")
    normalized = normalize_dumper_outcomes(payload, source=f"dumper:{path.name}") if _is_dumper_shape(payload) else dict(payload)
    merged = dict(existing)
    imported_keys = []
    for key, entry in normalized.items():
        if not isinstance(entry, Mapping):
            continue
        merged[str(key)] = dict(entry)
        imported_keys.append(str(key))
    out_path = base / "data" / OUTCOMES_FILE
    _atomic_write_json(out_path, merged)
    rows = event_outcome_dataset_rows(merged, imported_keys=imported_keys)
    rows_written = _append_jsonl_rows(ai_root(base) / DATASET_FILE, rows)
    report = {
        "success": True,
        "version": VERSION,
        "created_at": now_iso(),
        "source_path": str(path),
        "replace": bool(replace),
        "imported_events": len(imported_keys),
        "known_events": count_known_events(merged),
        "known_choices": count_known_choices(merged),
        "dataset_rows_written": rows_written,
        "outcomes_file": str(out_path),
    }
    _atomic_write_json(ai_root(base) / IMPORT_REPORT, report)
    return report


def count_known_events(outcomes: Mapping[str, Any]) -> int:
    return sum(1 for _, row in (outcomes or {}).items() if isinstance(row, Mapping) and (row.get("event_name") or row.get("details") or row.get("outcomes")))


def count_known_choices(outcomes: Mapping[str, Any]) -> int:
    total = 0
    for _, row in (outcomes or {}).items():
        if not isinstance(row, Mapping):
            continue
        details = row.get("details") if isinstance(row.get("details"), Mapping) else {}
        choices = row.get("outcomes") if isinstance(row.get("outcomes"), Mapping) else {}
        total += max(len(details), len(choices))
    return total


def _event_name_index(outcomes: Mapping[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, row in (outcomes or {}).items():
        if not isinstance(row, Mapping):
            continue
        name = _clean_event_name(row.get("event_name") or (str(key)[6:] if str(key).startswith("event:") else ""))
        if name:
            out[name.lower()] = str(key)
    return out


def unknown_seen_events(base_dir: Any, outcomes: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    outcomes = outcomes if outcomes is not None else load_outcomes(base_dir)
    idx = _event_name_index(outcomes)
    seen_path = runtime_output_root(base_dir) / "events_seen.json"
    seen = _read_json(seen_path, {})
    if not isinstance(seen, Mapping):
        return []
    unknown: List[Dict[str, Any]] = []
    for sid, row in seen.items():
        if not isinstance(row, Mapping):
            continue
        story_known = str(sid) in outcomes
        name = _clean_event_name(row.get("event_name"))
        name_known = bool(name and name.lower() in idx)
        if not story_known and not name_known:
            unknown.append({
                "story_id": str(sid),
                "event_name": name,
                "num_choices": _safe_int(row.get("num_choices")),
                "count": _safe_int(row.get("count")),
            })
    unknown.sort(key=lambda row: (-row.get("count", 0), row.get("event_name") or "~"))
    return unknown


def event_outcome_dataset_rows(outcomes: Optional[Mapping[str, Any]] = None, *, imported_keys: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    outcomes = outcomes or {}
    allow = set(str(k) for k in imported_keys) if imported_keys else None
    rows: List[Dict[str, Any]] = []
    for key, entry in outcomes.items():
        if allow is not None and str(key) not in allow:
            continue
        if not isinstance(entry, Mapping):
            continue
        details = entry.get("details") if isinstance(entry.get("details"), Mapping) else {}
        for select_index, reward in details.items():
            if not isinstance(reward, Mapping):
                continue
            rows.append({
                "version": VERSION,
                "created_at": now_iso(),
                "kind": "event_outcome",
                "event_key": str(key),
                "event_name": entry.get("event_name") or str(key),
                "select_index": str(select_index),
                "reward": dict(reward),
                "label": (entry.get("outcomes") or {}).get(str(select_index)) if isinstance(entry.get("outcomes"), Mapping) else "",
                "score_hint": _outcome_score_hint(reward),
                "source": entry.get("source") or "event_outcomes",
                "confidence": entry.get("confidence") or "unknown",
            })
    return rows


def summary(base_dir: Any) -> Dict[str, Any]:
    outcomes = load_outcomes(base_dir)
    unknown = unknown_seen_events(base_dir, outcomes)
    imported = [row for row in outcomes.values() if isinstance(row, Mapping) and str(row.get("source") or "").startswith("dumper")]
    report = _read_json(ai_root(base_dir) / IMPORT_REPORT, {})
    top = []
    for key, row in outcomes.items():
        if not isinstance(row, Mapping):
            continue
        top.append({
            "event_key": str(key),
            "event_name": row.get("event_name") or str(key),
            "choices": max(len(row.get("details") or {}), len(row.get("outcomes") or {})),
            "source": row.get("source") or "bundled",
            "confidence": row.get("confidence") or "unknown",
        })
    top.sort(key=lambda row: (-row.get("choices", 0), row.get("event_name") or "~"))
    return {
        "success": True,
        "version": VERSION,
        "known_events": count_known_events(outcomes),
        "known_choices": count_known_choices(outcomes),
        "imported_static_events": len(imported),
        "unknown_event_choices_seen": len(unknown),
        "unknown_events": unknown[:12],
        "top_events": top[:12],
        "last_import": report if isinstance(report, Mapping) else {},
        "artifacts": {
            "outcomes": str(project_base(base_dir) / "data" / OUTCOMES_FILE),
            "bundled_import": str(project_base(base_dir) / "data" / BUNDLED_IMPORT),
            "event_dataset": str(ai_root(base_dir) / DATASET_FILE),
            "import_report": str(ai_root(base_dir) / IMPORT_REPORT),
        },
    }


def llm_context(base_dir: Any, *, limit: int = 8) -> Dict[str, Any]:
    data = summary(base_dir)
    return {
        "known_events": data.get("known_events", 0),
        "known_choices": data.get("known_choices", 0),
        "unknown_event_choices_seen": data.get("unknown_event_choices_seen", 0),
        "top_known_events": [
            {"event_name": row.get("event_name"), "choices": row.get("choices")}
            for row in (data.get("top_events") or [])[:limit]
        ],
    }


# ===========================================================================
# v7.6.2 — Native event-outcome capture.
#
# SweepyCL is an API bot: it sends the game's API calls itself and already
# receives chara_info before and after every event choice it makes. That is the
# exact data the external Frida dumper extracts by hooking the game — so the bot
# can build and auto-update this KB from its OWN runs, with no Frida, no separate
# tool, and no game-memory access. The diff mirrors the community dumper's
# calculate_diff (generic integer deltas + conditions + skill hints).
# ===========================================================================

NATIVE_SOURCE = "native:bot"
# chara_info integer fields that are run/account state, not event rewards. We
# diff every int field generically (like the dumper) then drop the noise here;
# _normalize_reward keeps only the KB-relevant keys anyway, this just avoids
# surprising labels.
_DELTA_IGNORE_KEYS = frozenset({
    "turn", "fans", "rank", "rank_score", "card_id", "scenario_id", "viewer_id",
    "chara_id", "trained_chara_id", "playing_time", "vital_max",
})


def compute_chara_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> Dict[str, Any]:
    """Event reward delta from chara_info before/after a choice.

    Mirrors the community dumper's ``calculate_diff``: generic integer deltas,
    plus gained/lost conditions (``chara_effect_id_array``) and gained skill
    hints (``skill_tips_array``). Pass the result through ``_normalize_reward``
    to keep only KB-relevant keys.
    """
    delta: Dict[str, Any] = {}
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        return delta
    for key, bval in before.items():
        if key in _DELTA_IGNORE_KEYS:
            continue
        if isinstance(bval, bool) or not isinstance(bval, int):
            continue
        aval = after.get(key)
        if isinstance(aval, int) and not isinstance(aval, bool) and aval != bval:
            delta[key] = aval - bval
    try:
        eff_before = set(before.get("chara_effect_id_array", []) or [])
        eff_after = set(after.get("chara_effect_id_array", []) or [])
        gained = sorted(eff_after - eff_before)
        lost = sorted(eff_before - eff_after)
        if gained:
            delta["gained_conditions"] = gained
        if lost:
            delta["lost_conditions"] = lost
    except Exception:
        pass
    try:
        tips_before = {t.get("group_id"): t.get("level", 1) for t in (before.get("skill_tips_array") or []) if isinstance(t, Mapping)}
        tips_after = {t.get("group_id"): t.get("level", 1) for t in (after.get("skill_tips_array") or []) if isinstance(t, Mapping)}
        gained_tips: Dict[str, int] = {}
        for sid, after_lvl in tips_after.items():
            if sid is None:
                continue
            if _safe_int(after_lvl) > _safe_int(tips_before.get(sid, 0)):
                gained_tips[str(sid)] = _safe_int(after_lvl) - _safe_int(tips_before.get(sid, 0))
        if gained_tips:
            delta["gained_skill_hints"] = gained_tips
    except Exception:
        pass
    return delta


def record_observation(
    base_dir: Any,
    *,
    story_id: Any,
    select_index: Any,
    before: Optional[Mapping[str, Any]] = None,
    after: Optional[Mapping[str, Any]] = None,
    reward: Optional[Mapping[str, Any]] = None,
    event_name: str = "",
) -> Dict[str, Any]:
    """Record one natively-observed event outcome into the live KB.

    Keyed by ``story_id`` — the EventManager checks story_id before event-name,
    so observed data takes precedence over imported/static data for events the
    bot has actually played. Merges like the dumper (keeps the larger-magnitude
    delta). Atomic write; callers should treat any failure as non-fatal.
    """
    story_id = str(story_id or "").strip()
    if not story_id:
        return {"success": False, "detail": "missing story_id"}
    if reward is None:
        reward = compute_chara_delta(before or {}, after or {})
    reward = _normalize_reward(reward)
    if not reward:
        return {"success": False, "detail": "no measurable delta"}
    select_index = str(select_index)
    base = project_base(base_dir)
    outcomes = load_outcomes(base)
    existing = outcomes.get(story_id)
    if isinstance(existing, Mapping):
        entry = dict(existing)
    else:
        entry = {
            "event_name": _clean_event_name(event_name),
            "story_id": story_id,
            "source": NATIVE_SOURCE,
            "confidence": "observed_live",
        }
    if event_name and not entry.get("event_name"):
        entry["event_name"] = _clean_event_name(event_name)
    src = str(entry.get("source") or "")
    if not src or src.startswith("native"):
        entry["source"] = NATIVE_SOURCE
        entry["confidence"] = "observed_live"
    details = dict(entry.get("details") or {})
    slots = dict(entry.get("choice_slots") or {})
    slot = dict(slots.get("0") or {})
    details[select_index] = _merge_rewards(details.get(select_index), reward)
    slot[select_index] = _merge_rewards(slot.get(select_index), reward)
    slots["0"] = slot
    entry["details"] = details
    entry["choice_slots"] = slots
    entry["observations"] = _safe_int(entry.get("observations")) + 1
    outcomes_map = dict(entry.get("outcomes") or {})
    for idx, rw in details.items():
        outcomes_map[str(idx)] = _reward_label(rw)
    entry["outcomes"] = outcomes_map
    entry["choice_count"] = len(details)
    entry["updated_at"] = now_iso()
    merged = dict(outcomes)
    merged[story_id] = entry
    _atomic_write_json(base / "data" / OUTCOMES_FILE, merged)
    try:
        rows = event_outcome_dataset_rows({story_id: entry}, imported_keys=[story_id])
        _append_jsonl_rows(ai_root(base) / DATASET_FILE, rows)
    except Exception:
        pass
    return {"success": True, "story_id": story_id, "select_index": select_index, "observations": entry["observations"]}
