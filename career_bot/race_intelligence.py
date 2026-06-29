"""Runtime race intelligence helpers for Pre Icarus.

This module keeps the Smart Race Solver grounded in observed career data without
letting telemetry failures affect an active run.  The helpers intentionally use a
small append/aggregate JSON format so older builds can ignore it safely.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional


def runtime_output_root(base_dir: Any) -> Path:
    override = os.environ.get("UMA_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(base_dir).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate / "uma_runtime"
    return base.parent / "uma_runtime"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return float(default)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        Path(tmp_name).replace(path)
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass


def outcome_path(base_dir: Any) -> Path:
    return runtime_output_root(base_dir) / "race_outcomes.json"


def _empty_outcome_payload() -> Dict[str, Any]:
    return {"version": 1, "updated_at": 0, "programs": {}, "profiles": {}}


def load_outcomes(base_dir: Any) -> Dict[str, Any]:
    path = outcome_path(base_dir)
    if not path.exists():
        return _empty_outcome_payload()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("version", 1)
            data.setdefault("programs", {})
            data.setdefault("profiles", {})
            return data
    except Exception:
        pass
    return _empty_outcome_payload()


def _profile_key(trainee_id: Any = "", preset_name: str = "") -> str:
    tid = str(trainee_id or "").strip()
    preset = str(preset_name or "").strip().lower().replace(" ", "_")
    if tid and preset:
        return f"{preset}:{tid}"
    return tid or preset


def _update_bucket(bucket: Dict[str, Any], rank: int, row: Mapping[str, Any], stats: Optional[Mapping[str, Any]]) -> None:
    bucket["starts"] = _safe_int(bucket.get("starts")) + 1
    if rank == 1:
        bucket["wins"] = _safe_int(bucket.get("wins")) + 1
    else:
        bucket["losses"] = _safe_int(bucket.get("losses")) + 1
    clock_retry = row.get("clock_retry") if isinstance(row.get("clock_retry"), Mapping) else {}
    clocks_used = _safe_int(row.get("clocks_used") or clock_retry.get("used"))
    initial_rank = _safe_int(row.get("initial_rank") or clock_retry.get("initial_rank") or rank, rank)
    user_enabled = bool(clock_retry.get("user_enabled", clock_retry.get("enabled", False)))
    if user_enabled:
        bucket["clock_policy_enabled_starts"] = _safe_int(bucket.get("clock_policy_enabled_starts")) + 1
    else:
        bucket["clock_policy_disabled_starts"] = _safe_int(bucket.get("clock_policy_disabled_starts")) + 1
    if clocks_used:
        bucket["clock_retry_races"] = _safe_int(bucket.get("clock_retry_races")) + 1
        bucket["clocks_used"] = _safe_int(bucket.get("clocks_used")) + clocks_used
    if initial_rank == 1:
        bucket["clean_wins"] = _safe_int(bucket.get("clean_wins")) + 1
    elif rank == 1 and clocks_used:
        bucket["wins_after_clock"] = _safe_int(bucket.get("wins_after_clock")) + 1
    elif rank != 1:
        bucket["unrescued_losses"] = _safe_int(bucket.get("unrescued_losses")) + 1
    ranks = list(bucket.get("ranks") or [])[-49:]
    ranks.append(rank)
    bucket["ranks"] = ranks
    bucket["last_rank"] = rank
    bucket["last_turn"] = _safe_int(row.get("turn"))
    bucket["last_seen_at"] = int(time.time())
    for key in ("name", "grade", "distance_m", "distance_type", "terrain", "race_type", "initial_rank", "final_rank", "clocks_used", "won_after_clock", "won_without_clock", "master_metadata", "performance_hint"):
        if row.get(key) not in (None, ""):
            bucket[key] = row.get(key)
    if stats:
        bucket["last_stats"] = dict(stats)


def record_race_outcome(
    base_dir: Any,
    race_row: Mapping[str, Any],
    stats: Optional[Mapping[str, Any]] = None,
    preset_name: str = "",
    trainee_id: Any = "",
) -> Dict[str, Any]:
    """Record a finished race into a local aggregate used by future planning.

    The function is deliberately best-effort.  Callers may ignore failures.
    """
    pid = _safe_int(race_row.get("program_id"))
    if not pid:
        return {"success": False, "detail": "missing program_id"}
    rank = _safe_int(race_row.get("rank"), 99)
    data = load_outcomes(base_dir)
    programs = data.setdefault("programs", {})
    overall = programs.setdefault(str(pid), {})
    _update_bucket(overall, rank, race_row, stats)
    profile = _profile_key(trainee_id, preset_name)
    if profile:
        profiles = data.setdefault("profiles", {})
        prof = profiles.setdefault(profile, {})
        bucket = prof.setdefault(str(pid), {})
        _update_bucket(bucket, rank, race_row, stats)
    data["updated_at"] = int(time.time())
    _atomic_write_json(outcome_path(base_dir), data)
    return {"success": True, "program_id": pid, "profile": profile}


def _risk_from_bucket(bucket: Mapping[str, Any], min_samples: int = 2) -> Dict[str, Any]:
    starts = _safe_int(bucket.get("starts"))
    wins = _safe_int(bucket.get("wins"))
    losses = max(0, starts - wins)
    ranks = [_safe_int(x, 99) for x in (bucket.get("ranks") or []) if _safe_int(x, 0)]
    avg_rank = sum(ranks) / len(ranks) if ranks else 99.0
    clean_wins = _safe_int(bucket.get("clean_wins"))
    wins_after_clock = _safe_int(bucket.get("wins_after_clock"))
    clock_retry_races = _safe_int(bucket.get("clock_retry_races"))
    clock_policy_enabled = _safe_int(bucket.get("clock_policy_enabled_starts"))
    clock_policy_disabled = _safe_int(bucket.get("clock_policy_disabled_starts"))
    clean_win_rate = clean_wins / max(1, starts)
    clock_dependency_rate = wins_after_clock / max(1, wins) if wins else 0.0
    if starts < min_samples:
        return {
            "samples": starts,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / starts) if starts else None,
            "avg_rank": avg_rank if ranks else None,
            "clean_wins": clean_wins,
            "wins_after_clock": wins_after_clock,
            "clock_retry_races": clock_retry_races,
            "clean_win_rate": clean_win_rate if starts else None,
            "clock_dependency_rate": clock_dependency_rate,
            "clock_policy_enabled_starts": clock_policy_enabled,
            "clock_policy_disabled_starts": clock_policy_disabled,
            "penalty": 0.0,
            "clock_dependency_penalty": 0.0,
            "confidence": "low",
        }
    loss_rate = losses / max(1, starts)
    rank_drag = max(0.0, avg_rank - 1.0)
    clock_dependency_penalty = min(35.0, clock_dependency_rate * 35.0 + (1.0 - clean_win_rate) * 8.0)
    penalty = min(90.0, loss_rate * 55.0 + rank_drag * 7.5)
    return {
        "samples": starts,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / max(1, starts),
        "avg_rank": round(avg_rank, 3),
        "clean_wins": clean_wins,
        "wins_after_clock": wins_after_clock,
        "clock_retry_races": clock_retry_races,
        "clocks_used": _safe_int(bucket.get("clocks_used")),
        "clean_win_rate": round(clean_win_rate, 4),
        "clock_dependency_rate": round(clock_dependency_rate, 4),
        "clock_policy_enabled_starts": clock_policy_enabled,
        "clock_policy_disabled_starts": clock_policy_disabled,
        "penalty": round(penalty, 3),
        "clock_dependency_penalty": round(clock_dependency_penalty, 3),
        "confidence": "high" if starts >= 5 else "medium",
    }


def race_outcome_risk(
    base_dir: Any,
    program_id: Any,
    trainee_id: Any = "",
    preset_name: str = "",
    min_samples: int = 2,
    _data: Any = None,
) -> Dict[str, Any]:
    pid = str(_safe_int(program_id))
    if pid == "0":
        return {"penalty": 0.0, "samples": 0, "confidence": "none"}
    # _data lets hot callers (Smart Race Solver) load the outcomes file once and
    # reuse it across every candidate row instead of re-reading per program_id.
    data = _data if _data is not None else load_outcomes(base_dir)
    profile = _profile_key(trainee_id, preset_name)
    if profile:
        bucket = ((data.get("profiles") or {}).get(profile) or {}).get(pid)
        if bucket and _safe_int(bucket.get("starts")) >= min_samples:
            risk = _risk_from_bucket(bucket, min_samples=min_samples)
            risk["scope"] = "profile"
            return risk
    bucket = (data.get("programs") or {}).get(pid) or {}
    risk = _risk_from_bucket(bucket, min_samples=min_samples)
    risk["scope"] = "program"
    return risk


def validate_json_file(path: Any) -> Dict[str, Any]:
    p = Path(path)
    try:
        json.loads(p.read_text(encoding="utf-8"))
        return {"valid": True, "path": str(p)}
    except Exception as exc:
        return {"valid": False, "path": str(p), "error": str(exc), "error_type": type(exc).__name__}
