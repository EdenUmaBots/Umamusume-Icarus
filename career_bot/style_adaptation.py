"""Racing-style adaptation telemetry and conservative learner for Pre Icarus AI.

The live runner remains deterministic by default.  This module observes every
race-style decision, records outcomes in an append-only JSONL stream, and trains
an explainable contextual-bandit style report.  Automatic style switching is
safety-gated and disabled unless the user explicitly enables Auto Apply and the
local evidence passes conservative thresholds.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

STYLE_LABELS = {
    1: "Front Runner",
    2: "Pace Chaser",
    3: "Late Surger",
    4: "End Closer",
}
STYLE_KEYS = {
    1: "front",
    2: "pace",
    3: "late",
    4: "end",
}
STYLE_APT_KEYS = {
    1: "proper_running_style_nige",
    2: "proper_running_style_senko",
    3: "proper_running_style_sashi",
    4: "proper_running_style_oikomi",
}
DISTANCE_APT_KEYS = {
    "sprint": "proper_distance_short",
    "mile": "proper_distance_mile",
    "medium": "proper_distance_middle",
    "long": "proper_distance_long",
}
SURFACE_APT_KEYS = {
    "turf": "proper_ground_turf",
    "dirt": "proper_ground_dirt",
}
APT_LETTERS = {
    1: "G",
    2: "F",
    3: "E",
    4: "D",
    5: "C",
    6: "B",
    7: "A",
    8: "S",
}
APT_TO_NUM = {v: k for k, v in APT_LETTERS.items()}

STYLE_EXPERIENCES_FILE = "style_adaptation_experiences.jsonl"
STYLE_MODEL_FILE = "style_adaptation_model.json"
STYLE_REPORT_FILE = "style_adaptation_report.json"
STYLE_BACKTEST_FILE = "style_adaptation_backtest.json"
STYLE_SHADOW_FILE = "style_adaptation_shadow_report.json"

DEFAULT_STYLE_CONFIG = {
    "style_adaptation_mode": "recommend",  # disabled, shadow, recommend, auto
    "style_adaptation_min_confidence": 0.70,
    "style_adaptation_min_aptitude": 5,  # C
    "style_adaptation_protect_goal_races": True,
    "style_adaptation_protect_forced_epithets": True,
    "style_adaptation_auto_min_experiences": 100,
    "style_adaptation_auto_min_switches": 20,
    "style_adaptation_auto_max_bad_switch_rate": 0.20,
    "style_adaptation_switch_margin": 0.08,
}


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


def _json_default(obj: Any) -> str:
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)


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


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=_json_default)
            fh.write("\n")
        json.loads(tmp.read_text(encoding="utf-8"))
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path, limit: int = 200000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()[-max(1, int(limit)):]
        for line in lines:
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
            except Exception:
                continue
    except Exception:
        return []
    return rows


def load_config(base_dir: Any, override: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(DEFAULT_STYLE_CONFIG)
    auto = _read_json(ai_root(base_dir) / "auto_training_config.json", {})
    if isinstance(auto, Mapping):
        cfg.update({k: auto.get(k) for k in cfg if k in auto})
    if isinstance(override, Mapping):
        cfg.update({k: override.get(k) for k in cfg if k in override})
    mode = str(cfg.get("style_adaptation_mode") or "shadow").lower().strip()
    if mode not in {"disabled", "shadow", "recommend", "auto"}:
        mode = "shadow"
    cfg["style_adaptation_mode"] = mode
    cfg["style_adaptation_min_confidence"] = max(0.0, min(0.99, _safe_float(cfg.get("style_adaptation_min_confidence"), 0.70)))
    cfg["style_adaptation_min_aptitude"] = max(1, min(8, _safe_int(cfg.get("style_adaptation_min_aptitude"), 5)))
    cfg["style_adaptation_auto_min_experiences"] = max(1, _safe_int(cfg.get("style_adaptation_auto_min_experiences"), 100))
    cfg["style_adaptation_auto_min_switches"] = max(1, _safe_int(cfg.get("style_adaptation_auto_min_switches"), 20))
    cfg["style_adaptation_auto_max_bad_switch_rate"] = max(0.0, min(1.0, _safe_float(cfg.get("style_adaptation_auto_max_bad_switch_rate"), 0.20)))
    cfg["style_adaptation_switch_margin"] = max(0.0, min(1.0, _safe_float(cfg.get("style_adaptation_switch_margin"), 0.08)))
    return cfg


def _distance_bucket(distance: Any) -> str:
    n = _safe_int(distance, 0)
    if n <= 0:
        return str(distance or "").strip().lower()
    if n <= 1400:
        return "sprint"
    if n <= 1800:
        return "mile"
    if n <= 2400:
        return "medium"
    return "long"


def _normalise_surface(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"2", "dirt", "ダート"}:
        return "dirt"
    if text in {"1", "turf", "grass", "芝"}:
        return "turf"
    return text


def _apt_grade(value: Any, default: int = 1) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, str) and value.strip().upper() in APT_TO_NUM:
        return APT_TO_NUM[value.strip().upper()]
    return max(1, min(8, _safe_int(value, default)))


def _chara_stats(chara: Mapping[str, Any]) -> Dict[str, int]:
    return {
        "speed": _safe_int(chara.get("speed")),
        "stamina": _safe_int(chara.get("stamina")),
        "power": _safe_int(chara.get("power")),
        "guts": _safe_int(chara.get("guts")),
        "wit": _safe_int(chara.get("wiz") if chara.get("wiz") is not None else chara.get("wit") if chara.get("wit") is not None else chara.get("intelligence")),
        "skill_point": _safe_int(chara.get("skill_point")),
        "fans": _safe_int(chara.get("fans")),
        "motivation": _safe_int(chara.get("motivation"), 3),
        "hp": _safe_int(chara.get("vital") if chara.get("vital") is not None else chara.get("hp")),
        "max_hp": _safe_int(chara.get("max_vital") if chara.get("max_vital") is not None else chara.get("max_hp"), 100),
    }


def _extract_skill_ids(chara: Mapping[str, Any]) -> List[int]:
    candidates = [
        chara.get("skill_array"),
        chara.get("skills"),
        chara.get("skill_id_array"),
        chara.get("learned_skill_array"),
    ]
    out: List[int] = []
    for value in candidates:
        if isinstance(value, list):
            for row in value:
                if isinstance(row, Mapping):
                    sid = _safe_int(row.get("skill_id") or row.get("id"))
                else:
                    sid = _safe_int(row)
                if sid:
                    out.append(sid)
    return sorted(set(out))


def _load_skill_condition_index(base_dir: Any) -> Dict[str, Dict[str, Any]]:
    path = Path(base_dir) / "data" / "skill_condition_core.json"
    data = _read_json(path, [])
    if isinstance(data, Mapping):
        rows = data.get("rows") or data.get("skills") or []
    else:
        rows = data
    index: Dict[str, Dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, Mapping):
                sid = str(row.get("skill_id") or row.get("id") or "")
                if sid:
                    index[sid] = dict(row)
    return index


def _skill_style_summary(base_dir: Any, skill_ids: Iterable[int]) -> Dict[str, Any]:
    index = _load_skill_condition_index(base_dir)
    counts = {str(style): 0 for style in STYLE_LABELS}
    categories = Counter()
    matched = []
    style_terms = {
        1: ("running_style==1", "running_style = 1", "nige", "front"),
        2: ("running_style==2", "running_style = 2", "senko", "leader", "pace"),
        3: ("running_style==3", "running_style = 3", "sashi", "late"),
        4: ("running_style==4", "running_style = 4", "oikomi", "end"),
    }
    for sid in skill_ids:
        row = index.get(str(sid)) or {}
        if not row:
            continue
        cat = str(row.get("skill_category_label") or row.get("skill_category") or "")
        if cat:
            categories[cat] += 1
        text = json.dumps({
            "preconditions": row.get("preconditions"),
            "conditions": row.get("conditions"),
            "tags": row.get("tags"),
        }, ensure_ascii=False).lower()
        for style, terms in style_terms.items():
            if any(term in text for term in terms):
                counts[str(style)] += 1
                matched.append({"skill_id": sid, "style": style, "name": row.get("name") or str(sid)})
    return {
        "skill_count": len(list(skill_ids)),
        "style_counts": counts,
        "category_counts": dict(categories),
        "matched_style_skills": matched[:80],
        "source": "official_table_data:skill_condition_core" if index else "unknown_hidden_formula:no_skill_condition_core",
    }


def _opponent_style_counts(race_start_info: Any, viewer_id: Any = None) -> Dict[str, int]:
    info = _mapping(race_start_info)
    horses = info.get("race_horse_data") or info.get("horses") or []
    counts = {str(k): 0 for k in STYLE_LABELS}
    if isinstance(horses, list):
        for horse in horses:
            if not isinstance(horse, Mapping):
                continue
            if viewer_id is not None and str(horse.get("viewer_id") or "") == str(viewer_id):
                continue
            style = _safe_int(horse.get("running_style") or horse.get("race_running_style") or horse.get("strategy"))
            if style in STYLE_LABELS:
                counts[str(style)] += 1
    return counts


def build_style_context(
    base_dir: Any,
    state: Mapping[str, Any],
    preset: Mapping[str, Any],
    race_summary: Mapping[str, Any],
    base_style: int,
    current_turn: Any,
    race_start_info: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    data = _mapping((state or {}).get("data"))
    chara = _mapping(data.get("chara_info"))
    race_summary = _mapping(race_summary)
    distance = race_summary.get("distance_m") or race_summary.get("distance")
    distance_bucket = str(race_summary.get("distance_type") or _distance_bucket(distance)).lower()
    surface = _normalise_surface(race_summary.get("terrain") or race_summary.get("surface") or race_summary.get("ground"))
    skill_ids = _extract_skill_ids(chara)
    style_apts = {str(style): _apt_grade(chara.get(key), 1) for style, key in STYLE_APT_KEYS.items()}
    distance_apts = {bucket: _apt_grade(chara.get(key), 1) for bucket, key in DISTANCE_APT_KEYS.items()}
    surface_apts = {surf: _apt_grade(chara.get(key), 1) for surf, key in SURFACE_APT_KEYS.items()}
    perf = race_summary.get("performance_hint") if isinstance(race_summary.get("performance_hint"), Mapping) else {}
    meta = race_summary.get("master_metadata") if isinstance(race_summary.get("master_metadata"), Mapping) else {}
    viewer_id = ((state or {}).get("data_headers") or {}).get("viewer_id") or data.get("viewer_id")
    return {
        "schema_version": "style_adaptation_v1",
        "created_at": now_iso(),
        "run_id": str((state or {}).get("run_id") or ""),
        "turn": _safe_int(current_turn),
        "scenario": "Trackblazer" if _safe_int((preset or {}).get("scenario_id") or (preset or {}).get("scenario"), 4) == 4 else str((preset or {}).get("scenario_id") or ""),
        "preset_name": str((preset or {}).get("name") or ""),
        "trainee_id": str(chara.get("card_id") or chara.get("chara_id") or ""),
        "base_user_style": _safe_int(base_style),
        "base_user_style_label": STYLE_LABELS.get(_safe_int(base_style), "Unknown"),
        "race": {
            "program_id": _safe_int(race_summary.get("program_id")),
            "race_name": race_summary.get("name") or race_summary.get("race_name") or "",
            "grade": race_summary.get("grade") or "",
            "distance": _safe_int(distance),
            "distance_bucket": distance_bucket,
            "surface": surface,
            "venue": meta.get("venue"),
            "track_id": meta.get("race_track_id"),
            "fan_requirement": meta.get("need_fan_count"),
            "fans_first": meta.get("fans_first") or race_summary.get("fans"),
            "trackblazer_coin_first": meta.get("trackblazer_coin_first"),
            "trackblazer_win_points_first": meta.get("trackblazer_win_points_first"),
            "race_group_ids": meta.get("race_group_ids") or race_summary.get("race_group_ids") or [],
            "source_labels": ["official_table_data" if meta else "unknown_hidden_formula:no_master_metadata"],
        },
        "current_state": {
            "stats": _chara_stats(chara),
            "style_aptitudes": style_apts,
            "distance_aptitudes": distance_apts,
            "surface_aptitudes": surface_apts,
            "skill_ids": skill_ids,
            "skill_summary": _skill_style_summary(base_dir, skill_ids),
            "condition_flags": chara.get("chara_effect_id_array") or chara.get("condition_array") or [],
            "source_labels": ["api_observed_data"],
        },
        "race_conditions": {
            "performance_hint": dict(perf or {}),
            "weather": race_summary.get("weather"),
            "ground_condition": race_summary.get("ground_condition"),
            "opponent_style_counts": _opponent_style_counts(race_start_info, viewer_id=viewer_id) if race_start_info else {},
            "opponent_style_counts_available_before_entry": bool(race_start_info),
            "source_labels": ["api_observed_data" if race_start_info else "unknown_hidden_formula:opponent_styles_not_available_before_entry"],
        },
        "clock_policy": {
            "burn_clocks_enabled": bool((preset or {}).get("burn_clocks") or False),
            "source": "api_observed_data:career_start_setting",
        },
        "epithet_state": {
            "target_epithets": (preset or {}).get("target_epithets") or [],
            "forced_epithets": (preset or {}).get("forced_epithets") or [],
            "source": "api_observed_data:solver_settings",
        },
    }


def _context_features(context: Mapping[str, Any], style: int) -> List[str]:
    race = _mapping(context.get("race"))
    state = _mapping(context.get("current_state"))
    stats = _mapping(state.get("stats"))
    style_apts = _mapping(state.get("style_aptitudes"))
    dist_apts = _mapping(state.get("distance_aptitudes"))
    surf_apts = _mapping(state.get("surface_aptitudes"))
    distance_bucket = str(race.get("distance_bucket") or "unknown").lower()
    surface = str(race.get("surface") or "unknown").lower()
    features = [
        f"style={style}",
        f"distance={distance_bucket}|style={style}",
        f"surface={surface}|style={style}",
        f"grade={str(race.get('grade') or '').upper()}|style={style}",
        f"program={race.get('program_id')}|style={style}",
        f"trainee={context.get('trainee_id')}|style={style}",
        f"preset={context.get('preset_name')}|style={style}",
        f"style_apt={_safe_int(style_apts.get(str(style)))}|style={style}",
        f"dist_apt={_safe_int(dist_apts.get(distance_bucket))}|style={style}",
        f"surface_apt={_safe_int(surf_apts.get(surface))}|style={style}",
    ]
    for stat_name in ("speed", "stamina", "power", "guts", "wit"):
        band = min(12, max(0, _safe_int(stats.get(stat_name)) // 100))
        features.append(f"{stat_name}_band={band}|style={style}")
    return features


def _baseline_score(context: Mapping[str, Any], style: int, cfg: Mapping[str, Any]) -> Tuple[float, List[str]]:
    race = _mapping(context.get("race"))
    state = _mapping(context.get("current_state"))
    stats = _mapping(state.get("stats"))
    style_apts = _mapping(state.get("style_aptitudes"))
    dist_apts = _mapping(state.get("distance_aptitudes"))
    surf_apts = _mapping(state.get("surface_aptitudes"))
    skill_summary = _mapping(state.get("skill_summary"))
    distance_bucket = str(race.get("distance_bucket") or "unknown").lower()
    surface = str(race.get("surface") or "unknown").lower()
    score = 0.0
    reasons: List[str] = []
    apt = _safe_int(style_apts.get(str(style)), 1)
    score += (apt - 4) * 0.08
    reasons.append(f"{STYLE_LABELS.get(style)} aptitude {APT_LETTERS.get(apt, apt)}")
    dapt = _safe_int(dist_apts.get(distance_bucket), 1)
    sapt = _safe_int(surf_apts.get(surface), 1)
    score += (dapt - 4) * 0.04 + (sapt - 4) * 0.04
    if dapt < 5:
        reasons.append(f"distance aptitude low {APT_LETTERS.get(dapt, dapt)}")
    if sapt < 5:
        reasons.append(f"surface aptitude low {APT_LETTERS.get(sapt, sapt)}")
    style_skills = _safe_int((_mapping(skill_summary.get("style_counts"))).get(str(style)))
    score += min(0.18, style_skills * 0.05)
    if style_skills:
        reasons.append(f"{style_skills} owned skill(s) appear style-compatible")
    # Tiny stat priors by style. These are empirical priors, not official formulas.
    if style == 1:
        score += min(0.12, _safe_int(stats.get("speed")) / 10000.0)
        score += min(0.08, _safe_int(stats.get("power")) / 14000.0)
    elif style == 2:
        score += min(0.10, _safe_int(stats.get("speed")) / 12000.0)
        score += min(0.09, _safe_int(stats.get("wit")) / 13000.0)
    elif style == 3:
        score += min(0.10, _safe_int(stats.get("power")) / 12000.0)
        score += min(0.08, _safe_int(stats.get("guts")) / 14000.0)
    elif style == 4:
        score += min(0.10, _safe_int(stats.get("power")) / 11000.0)
        score += min(0.09, _safe_int(stats.get("guts")) / 12000.0)
    if not _mapping(context.get("clock_policy")).get("burn_clocks_enabled"):
        reasons.append("Burn Clocks disabled; clock-dependent styles/races require higher evidence")
    return round(score, 4), reasons


def _load_model(base_dir: Any) -> Dict[str, Any]:
    data = _read_json(ai_root(base_dir) / STYLE_MODEL_FILE, {})
    return data if isinstance(data, dict) else {}


def _learned_adjustment(model: Mapping[str, Any], context: Mapping[str, Any], style: int) -> Tuple[float, int, List[str]]:
    feature_values = model.get("feature_values") or {}
    total = 0.0
    samples = 0
    hits: List[str] = []
    for feature in _context_features(context, style):
        row = feature_values.get(feature)
        if not isinstance(row, Mapping):
            continue
        count = _safe_int(row.get("samples"))
        avg = _safe_float(row.get("avg_reward"), 0.0)
        if count <= 0:
            continue
        weight = min(0.25, math.log1p(count) / 16.0)
        total += avg * weight
        samples += count
        if len(hits) < 4:
            hits.append(f"{feature}:{avg:+.2f}/{count}")
    return round(max(-0.35, min(0.35, total)), 4), samples, hits


def _confidence(samples: int, floor: int = 10) -> float:
    if samples <= 0:
        return 0.0
    return round(min(0.99, samples / max(float(floor), samples + floor)), 4)


def _safety_gates(context: Mapping[str, Any], style: int, cfg: Mapping[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    state = _mapping(context.get("current_state"))
    style_apts = _mapping(state.get("style_aptitudes"))
    apt = _safe_int(style_apts.get(str(style)), 1)
    min_apt = _safe_int(cfg.get("style_adaptation_min_aptitude"), 5)
    if apt < min_apt:
        reasons.append(f"blocked: {STYLE_LABELS.get(style)} aptitude {APT_LETTERS.get(apt, apt)} below minimum {APT_LETTERS.get(min_apt, min_apt)}")
        return False, reasons
    return True, reasons


def _auto_apply_unlocked(report: Mapping[str, Any], cfg: Mapping[str, Any]) -> bool:
    return bool((report or {}).get("auto_apply_unlocked")) and bool((report or {}).get("safe_for_auto_apply"))


def decide_style(base_dir: Any, context: Mapping[str, Any], config_override: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    cfg = load_config(base_dir, config_override)
    mode = str(cfg.get("style_adaptation_mode") or "shadow")
    base_style = _safe_int(context.get("base_user_style"), 0)
    if base_style not in STYLE_LABELS:
        base_style = 2
    model = _load_model(base_dir)
    report = _read_json(ai_root(base_dir) / STYLE_REPORT_FILE, {})
    candidates = []
    blocked: Dict[str, Any] = {}
    scores: Dict[str, Any] = {}
    for style in STYLE_LABELS:
        ok, gate_reasons = _safety_gates(context, style, cfg)
        if not ok and style != base_style:
            blocked[str(style)] = gate_reasons
            continue
        candidates.append(style)
    if base_style not in candidates:
        candidates.append(base_style)
    for style in candidates:
        baseline, reasons = _baseline_score(context, style, cfg)
        learned, samples, hits = _learned_adjustment(model, context, style)
        total = round(baseline + learned, 4)
        conf = _confidence(samples, floor=20)
        scores[str(style)] = {
            "style": style,
            "label": STYLE_LABELS.get(style),
            "baseline_score": baseline,
            "learned_adjustment": learned,
            "score": total,
            "confidence": conf,
            "samples": samples,
            "reasons": reasons + (["learned evidence " + "; ".join(hits)] if hits else ["no direct learned evidence yet"]),
        }
    best_style = max(candidates, key=lambda s: scores.get(str(s), {}).get("score", -999.0)) if candidates else base_style
    best = scores.get(str(best_style), {})
    base = scores.get(str(base_style), {"score": 0.0, "confidence": 0.0})
    delta = round(_safe_float(best.get("score")) - _safe_float(base.get("score")), 4)
    confidence = _safe_float(best.get("confidence"), 0.0)
    applied = base_style
    action_type = "keep"
    reasons = list(best.get("reasons") or [])[:8]
    if mode == "disabled":
        action_type = "disabled"
        reasons.insert(0, "style adaptation disabled")
    elif mode == "shadow":
        action_type = "shadow_only"
        reasons.insert(0, f"shadow recommendation: {STYLE_LABELS.get(best_style)}; live style kept as {STYLE_LABELS.get(base_style)}")
    elif mode == "recommend":
        action_type = "recommend_only"
        reasons.insert(0, f"recommendation only: {STYLE_LABELS.get(best_style)}; live style kept as {STYLE_LABELS.get(base_style)}")
    elif mode == "auto":
        unlocked = _auto_apply_unlocked(report, cfg)
        min_conf = _safe_float(cfg.get("style_adaptation_min_confidence"), 0.70)
        margin = _safe_float(cfg.get("style_adaptation_switch_margin"), 0.08)
        if unlocked and best_style != base_style and confidence >= min_conf and delta >= margin:
            applied = best_style
            action_type = "auto_switch"
            reasons.insert(0, f"auto-applied {STYLE_LABELS.get(best_style)}; confidence {confidence:.2f}, delta {delta:+.2f}")
        else:
            action_type = "auto_blocked_keep"
            reasons.insert(0, "auto mode requested but safety gates did not allow a style switch")
    decision_id = f"style-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
    out = {
        "schema_version": "style_adaptation_v1",
        "decision_id": decision_id,
        "created_at": now_iso(),
        "mode": mode,
        "action_type": action_type,
        "base_user_style": base_style,
        "base_user_style_label": STYLE_LABELS.get(base_style),
        "recommended_style": best_style,
        "recommended_style_label": STYLE_LABELS.get(best_style),
        "applied_style": applied,
        "applied_style_label": STYLE_LABELS.get(applied),
        "style_changed": applied != base_style,
        "expected_reward_delta": delta,
        "confidence": confidence,
        "scores": scores,
        "blocked": blocked,
        "reason_flags": reasons,
        "context": dict(context or {}),
        "source_labels": ["empirical_estimate", "official_table_data", "api_observed_data"],
    }
    return out


def record_decision(base_dir: Any, decision: Mapping[str, Any]) -> None:
    row = dict(decision or {})
    row["phase"] = "decision"
    _append_jsonl(ai_root(base_dir) / STYLE_EXPERIENCES_FILE, row)


def record_observation(base_dir: Any, decision_id: str, race_start_info: Any, state: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    viewer_id = None
    try:
        viewer_id = ((state or {}).get("data_headers") or {}).get("viewer_id")
    except Exception:
        viewer_id = None
    row = {
        "schema_version": "style_adaptation_v1",
        "phase": "observation",
        "decision_id": decision_id,
        "created_at": now_iso(),
        "opponent_style_counts": _opponent_style_counts(race_start_info, viewer_id=viewer_id),
        "entry_count": len((_mapping(race_start_info).get("race_horse_data") or [])) if isinstance((_mapping(race_start_info).get("race_horse_data") or []), list) else 0,
        "source_labels": ["api_observed_data"],
    }
    _append_jsonl(ai_root(base_dir) / STYLE_EXPERIENCES_FILE, row)
    return row


def compute_reward(outcome: Mapping[str, Any]) -> float:
    rank = _safe_int(outcome.get("final_rank") or outcome.get("rank"), 99)
    clocks_used = _safe_int(outcome.get("clocks_used"))
    reward = 0.0
    if rank == 1:
        reward += 1.0
    elif rank <= 3:
        reward += 0.45
    elif rank <= 5:
        reward += 0.15
    else:
        reward -= 0.40
    if outcome.get("won_after_clock"):
        reward -= 0.25
    reward -= 0.12 * clocks_used
    if outcome.get("goal_passed") is True:
        reward += 0.40
    elif outcome.get("goal_passed") is False:
        reward -= 1.25
    epithet_delta = _mapping(outcome.get("epithet_progress_delta"))
    if epithet_delta.get("completed"):
        reward += 0.25
    if epithet_delta.get("failed"):
        reward -= 0.60
    if outcome.get("style_changed") and rank > 3:
        reward -= 0.10
    return round(max(-2.0, min(2.0, reward)), 4)


def record_outcome(
    base_dir: Any,
    decision: Mapping[str, Any],
    race_result: Mapping[str, Any],
    clock_retry: Optional[Mapping[str, Any]] = None,
    epithet_delta: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    decision_id = str((decision or {}).get("decision_id") or "")
    clock_retry = _mapping(clock_retry)
    rank = _safe_int(race_result.get("rank") or race_result.get("final_rank"), 99)
    outcome = {
        "schema_version": "style_adaptation_v1",
        "phase": "outcome",
        "decision_id": decision_id,
        "created_at": now_iso(),
        "run_id": (decision or {}).get("context", {}).get("run_id"),
        "turn": (decision or {}).get("context", {}).get("turn"),
        "program_id": ((decision or {}).get("context", {}).get("race") or {}).get("program_id") or race_result.get("program_id"),
        "base_user_style": (decision or {}).get("base_user_style"),
        "recommended_style": (decision or {}).get("recommended_style"),
        "applied_style": (decision or {}).get("applied_style"),
        "style_changed": bool((decision or {}).get("style_changed")),
        "initial_rank": _safe_int(clock_retry.get("initial_rank") or race_result.get("initial_rank") or rank, rank),
        "final_rank": rank,
        "rank": rank,
        "won_without_clock": bool(clock_retry.get("won_before_retry") or race_result.get("won_without_clock")),
        "won_after_clock": bool(clock_retry.get("won_after_retry") or race_result.get("won_after_clock")),
        "clocks_used": _safe_int(clock_retry.get("used") or race_result.get("clocks_used")),
        "burn_clocks_enabled": bool(clock_retry.get("user_enabled") if "user_enabled" in clock_retry else clock_retry.get("enabled")),
        "clock_retry": dict(clock_retry),
        "epithet_progress_delta": dict(epithet_delta or {}),
        "fans_gained": race_result.get("fans_gained"),
        "skill_points_gained": race_result.get("skill_points_gained"),
        "source_labels": ["api_observed_data", "empirical_estimate"],
    }
    outcome["reward"] = compute_reward(outcome)
    _append_jsonl(ai_root(base_dir) / STYLE_EXPERIENCES_FILE, outcome)
    return outcome


def _join_experiences(rows: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        did = str(row.get("decision_id") or "")
        if not did:
            continue
        rec = by_id.setdefault(did, {"decision_id": did})
        phase = str(row.get("phase") or "decision")
        if phase == "decision":
            rec["decision"] = dict(row)
        elif phase == "observation":
            rec.setdefault("observations", []).append(dict(row))
        elif phase == "outcome":
            rec["outcome"] = dict(row)
    out = []
    for rec in by_id.values():
        if rec.get("decision") and rec.get("outcome"):
            out.append(rec)
    return out


def _bucket_update(bucket: MutableMapping[str, Any], reward: float, rank: int) -> None:
    bucket["samples"] = _safe_int(bucket.get("samples")) + 1
    bucket["reward_total"] = _safe_float(bucket.get("reward_total")) + reward
    bucket["rank_total"] = _safe_float(bucket.get("rank_total")) + rank
    if rank == 1:
        bucket["wins"] = _safe_int(bucket.get("wins")) + 1
    if rank > 3:
        bucket["bad_results"] = _safe_int(bucket.get("bad_results")) + 1


def train_from_experiences(base_dir: Any, config: Optional[Mapping[str, Any]] = None, limit: int = 300000) -> Dict[str, Any]:
    root = ai_root(base_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows = _read_jsonl(root / STYLE_EXPERIENCES_FILE, limit=limit)
    joined = _join_experiences(rows)
    feature_buckets: Dict[str, Dict[str, Any]] = defaultdict(dict)
    style_buckets: Dict[str, Dict[str, Any]] = defaultdict(dict)
    switch_count = 0
    bad_switches = 0
    clean_wins = 0
    clock_wins = 0
    for rec in joined:
        dec = _mapping(rec.get("decision"))
        out = _mapping(rec.get("outcome"))
        style = _safe_int(out.get("applied_style") or dec.get("applied_style"))
        if style not in STYLE_LABELS:
            continue
        reward = _safe_float(out.get("reward"), compute_reward(out))
        rank = _safe_int(out.get("final_rank") or out.get("rank"), 99)
        if out.get("style_changed") or dec.get("style_changed"):
            switch_count += 1
            if rank > 3:
                bad_switches += 1
        if out.get("won_without_clock"):
            clean_wins += 1
        if out.get("won_after_clock"):
            clock_wins += 1
        context = _mapping(dec.get("context"))
        _bucket_update(style_buckets[str(style)], reward, rank)
        for feature in _context_features(context, style):
            _bucket_update(feature_buckets[feature], reward, rank)
    feature_values = {}
    for key, bucket in feature_buckets.items():
        samples = _safe_int(bucket.get("samples"))
        if samples <= 0:
            continue
        feature_values[key] = {
            "samples": samples,
            "avg_reward": round(_safe_float(bucket.get("reward_total")) / samples, 4),
            "avg_rank": round(_safe_float(bucket.get("rank_total")) / samples, 4),
            "win_rate": round(_safe_int(bucket.get("wins")) / samples, 4),
            "bad_result_rate": round(_safe_int(bucket.get("bad_results")) / samples, 4),
        }
    styles = {}
    for key, bucket in style_buckets.items():
        samples = _safe_int(bucket.get("samples"))
        styles[key] = {
            "style": _safe_int(key),
            "label": STYLE_LABELS.get(_safe_int(key)),
            "samples": samples,
            "avg_reward": round(_safe_float(bucket.get("reward_total")) / max(1, samples), 4),
            "avg_rank": round(_safe_float(bucket.get("rank_total")) / max(1, samples), 4),
            "win_rate": round(_safe_int(bucket.get("wins")) / max(1, samples), 4),
            "bad_result_rate": round(_safe_int(bucket.get("bad_results")) / max(1, samples), 4),
            "confidence": _confidence(samples, floor=20),
        }
    cfg = load_config(base_dir, config)
    total = len(joined)
    bad_switch_rate = round(bad_switches / max(1, switch_count), 4)
    safe_for_auto = (
        total >= _safe_int(cfg.get("style_adaptation_auto_min_experiences"), 100)
        and switch_count >= _safe_int(cfg.get("style_adaptation_auto_min_switches"), 20)
        and bad_switch_rate <= _safe_float(cfg.get("style_adaptation_auto_max_bad_switch_rate"), 0.20)
    )
    model = {
        "version": 1,
        "updated_at": now_iso(),
        "algorithm": "conservative_contextual_bandit_feature_table",
        "source_labels": ["api_observed_data", "official_table_data", "empirical_estimate", "unknown_hidden_formula"],
        "experience_rows": len(rows),
        "completed_experiences": total,
        "style_change_outcomes": switch_count,
        "feature_values": feature_values,
        "styles": styles,
        "notes": [
            "This model learns from observable race outcomes and official table metadata only.",
            "It does not claim exact lane-blocking, acceleration, hidden opponent AI, or server-side race simulation formulas.",
        ],
    }
    report = {
        "success": True,
        "version": 1,
        "updated_at": now_iso(),
        "mode": cfg.get("style_adaptation_mode"),
        "completed_experiences": total,
        "style_change_outcomes": switch_count,
        "bad_switches": bad_switches,
        "bad_switch_rate": bad_switch_rate,
        "clean_wins": clean_wins,
        "clock_rescued_wins": clock_wins,
        "auto_apply_unlocked": bool(safe_for_auto),
        "safe_for_auto_apply": bool(safe_for_auto),
        "recommendation": "Auto Apply remains locked; continue Shadow/Recommend until safety thresholds pass." if not safe_for_auto else "Auto Apply safety thresholds pass. Use only if you are comfortable with style switching.",
        "styles": styles,
        "thresholds": {
            "min_experiences": cfg.get("style_adaptation_auto_min_experiences"),
            "min_style_change_outcomes": cfg.get("style_adaptation_auto_min_switches"),
            "max_bad_switch_rate": cfg.get("style_adaptation_auto_max_bad_switch_rate"),
            "min_confidence": cfg.get("style_adaptation_min_confidence"),
        },
    }
    shadow = {
        "success": True,
        "version": 1,
        "updated_at": now_iso(),
        "evaluated_experiences": total,
        "style_change_outcomes": switch_count,
        "bad_switch_rate": bad_switch_rate,
        "summary": "Shadow report compares observed style decisions and outcomes; counterfactual style results are not assumed.",
    }
    backtest = {
        "success": True,
        "version": 1,
        "updated_at": now_iso(),
        "evaluated_experiences": total,
        "clean_win_rate": round(clean_wins / max(1, total), 4),
        "clock_rescue_rate": round(clock_wins / max(1, total), 4),
        "style_change_bad_result_rate": bad_switch_rate,
        "limitations": ["Only the actually-used style has a true observed outcome; alternate-style outcomes remain estimates."],
    }
    _atomic_write_json(root / STYLE_MODEL_FILE, model)
    _atomic_write_json(root / STYLE_REPORT_FILE, report)
    _atomic_write_json(root / STYLE_SHADOW_FILE, shadow)
    _atomic_write_json(root / STYLE_BACKTEST_FILE, backtest)
    return {"model": model, "report": report, "shadow": shadow, "backtest": backtest}


def latest_payload(base_dir: Any) -> Dict[str, Any]:
    root = ai_root(base_dir)
    report = _read_json(root / STYLE_REPORT_FILE, {})
    model = _read_json(root / STYLE_MODEL_FILE, {})
    backtest = _read_json(root / STYLE_BACKTEST_FILE, {})
    if not report:
        return {
            "success": False,
            "detail": "No style adaptation model has been trained yet. Run in Shadow Mode and click Train Now after races.",
            "mode": load_config(base_dir).get("style_adaptation_mode"),
        }
    return {
        "success": True,
        "report": report,
        "model_summary": {
            "completed_experiences": model.get("completed_experiences", 0),
            "style_change_outcomes": model.get("style_change_outcomes", 0),
            "styles": model.get("styles") or {},
        },
        "backtest": backtest,
    }
