"""Automatic local AI training and advisor model generation for Pre Icarus.

This module is intentionally local-first and deterministic.  It does not call an
external LLM and it never executes gameplay actions.  It turns the AI-ready JSONL
exports from :mod:`career_bot.ai_dataset` into inspectable analytics tables,
lightweight learned scoring models, post-run reports, synthetic prompt packs, and
confidence-gated policy hints that the deterministic solver may optionally use.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from career_bot.ai_dataset import DATASET_FILES, dataset_status, rebuild_advisor_stats, runtime_output_root, safe_float, safe_int, JSONL_ARCHIVE_MARKER
from career_bot import style_adaptation, local_llm

AI_TRAINER_VERSION = 2
MIN_CONFIDENCE_DEFAULT = 0.65

MODEL_FILES = {
    "race_outcome_table": "race_outcome_table.json",
    "item_effectiveness_table": "item_effectiveness_table.json",
    "event_outcome_table": "event_outcome_table.json",
    "race_risk_model": "race_risk_model.json",
    "item_value_model": "item_value_model.json",
    "event_value_model": "event_value_model.json",
    "policy_adjustments": "policy_adjustments.json",
    "suggested_config_tuning": "suggested_config_tuning.json",
    "shadow_policy_report": "shadow_policy_report.json",
    "backtest_report": "backtest_report.json",
    "epithet_confidence": "epithet_confidence.json",
    "preset_trainee_confidence": "preset_trainee_confidence.json",
    "ai_dashboard": "ai_dashboard.json",
    "style_adaptation_model": "style_adaptation_model.json",
    "style_adaptation_report": "style_adaptation_report.json",
    "style_adaptation_backtest": "style_adaptation_backtest.json",
    "style_adaptation_shadow_report": "style_adaptation_shadow_report.json",
    "latest_training_run": "latest_training_run.json",
    "auto_state": "auto_training_state.json",
}

DEFAULT_AUTO_CONFIG = {
    "enabled": True,
    "train_after_completed_careers": 1,
    "interval_minutes": 60,
    "min_turn_records": 10,
    "min_samples_for_model": 4,
    "enable_live_policy_assistance": False,
    "confidence_threshold": MIN_CONFIDENCE_DEFAULT,
    "max_abs_live_adjustment": 25.0,
    "warn_win_rate_ceiling": 0.50,
    "train_while_runner_active": False,
    "generate_synthetic_prompts": True,
    "generate_post_run_report": True,
    "enable_shadow_mode": True,
    "enable_backtesting": True,
    "style_adaptation_mode": "shadow",
    "style_adaptation_min_confidence": 0.70,
    "style_adaptation_min_aptitude": 5,
    "style_adaptation_protect_goal_races": True,
    "style_adaptation_protect_forced_epithets": True,
    "style_adaptation_auto_min_experiences": 100,
    "style_adaptation_auto_min_switches": 20,
    "style_adaptation_auto_max_bad_switch_rate": 0.20,
    "style_adaptation_switch_margin": 0.08,
}

_BACKGROUND = {
    "started": False,
    "thread": None,
    "stop": False,
    "last_error": "",
    "last_train_at": "",
    "last_skip_reason": "",
}
_LOCK = threading.RLock()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ai_root(base_dir: Any) -> Path:
    return runtime_output_root(base_dir) / "ai"


def _json_default(obj: Any) -> str:
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)


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


def _append_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")
            count += 1
    return count


def _read_json(path: Path, default: Any) -> Any:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return default


def _read_jsonl(path: Path, limit: int = 200000) -> List[Dict[str, Any]]:
    # P5: include rotated archives so training history survives rotation. Files
    # are ordered [oldest archive, ..., newest archive, live]; we read them
    # newest-first and stop once we have `limit` rows, then restore chronological
    # order — same "last N rows" semantics as before, just spanning archives.
    files: List[Path] = []
    try:
        files.extend(sorted(path.parent.glob(f"{path.stem}{JSONL_ARCHIVE_MARKER}*{path.suffix}")))
    except Exception:
        pass
    if path.exists():
        files.append(path)
    if not files:
        return []
    cap = max(1, int(limit))
    rows: List[Dict[str, Any]] = []
    for fp in reversed(files):
        try:
            with fp.open("r", encoding="utf-8") as fh:
                file_lines = fh.readlines()
        except Exception:
            continue
        for line in reversed(file_lines):
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
                    if len(rows) >= cap:
                        break
            except Exception:
                continue
        if len(rows) >= cap:
            break
    rows.reverse()
    return rows


def auto_config_path(base_dir: Any) -> Path:
    return ai_root(base_dir) / "auto_training_config.json"


def load_auto_config(base_dir: Any) -> Dict[str, Any]:
    cfg = dict(DEFAULT_AUTO_CONFIG)
    loaded = _read_json(auto_config_path(base_dir), {})
    if isinstance(loaded, dict):
        cfg.update({k: v for k, v in loaded.items() if k in cfg})
    cfg["enabled"] = bool(cfg.get("enabled"))
    cfg["train_after_completed_careers"] = max(1, safe_int(cfg.get("train_after_completed_careers"), 1))
    cfg["interval_minutes"] = max(5, safe_int(cfg.get("interval_minutes"), 60))
    cfg["min_turn_records"] = max(0, safe_int(cfg.get("min_turn_records"), 10))
    cfg["min_samples_for_model"] = max(1, safe_int(cfg.get("min_samples_for_model"), 4))
    cfg["confidence_threshold"] = max(0.0, min(0.99, safe_float(cfg.get("confidence_threshold"), MIN_CONFIDENCE_DEFAULT)))
    cfg["max_abs_live_adjustment"] = max(0.0, min(100.0, safe_float(cfg.get("max_abs_live_adjustment"), 25.0)))
    cfg["warn_win_rate_ceiling"] = max(0.0, min(1.0, safe_float(cfg.get("warn_win_rate_ceiling"), 0.50)))
    mode = str(cfg.get("style_adaptation_mode") or "shadow").lower().strip()
    cfg["style_adaptation_mode"] = mode if mode in {"disabled", "shadow", "recommend", "auto"} else "shadow"
    cfg["style_adaptation_min_confidence"] = max(0.0, min(0.99, safe_float(cfg.get("style_adaptation_min_confidence"), 0.70)))
    cfg["style_adaptation_min_aptitude"] = max(1, min(8, safe_int(cfg.get("style_adaptation_min_aptitude"), 5)))
    cfg["style_adaptation_auto_min_experiences"] = max(1, safe_int(cfg.get("style_adaptation_auto_min_experiences"), 100))
    cfg["style_adaptation_auto_min_switches"] = max(1, safe_int(cfg.get("style_adaptation_auto_min_switches"), 20))
    cfg["style_adaptation_auto_max_bad_switch_rate"] = max(0.0, min(1.0, safe_float(cfg.get("style_adaptation_auto_max_bad_switch_rate"), 0.20)))
    cfg["style_adaptation_switch_margin"] = max(0.0, min(1.0, safe_float(cfg.get("style_adaptation_switch_margin"), 0.08)))
    return cfg


def save_auto_config(base_dir: Any, patch: Mapping[str, Any]) -> Dict[str, Any]:
    cfg = load_auto_config(base_dir)
    for key in DEFAULT_AUTO_CONFIG:
        if key in patch:
            cfg[key] = patch[key]
    cfg = {**load_auto_config(base_dir), **{k: cfg[k] for k in DEFAULT_AUTO_CONFIG if k in cfg}}
    cfg["updated_at"] = now_iso()
    _atomic_write_json(auto_config_path(base_dir), cfg)
    return cfg




def live_policy_recommendation(config: Mapping[str, Any], health: Mapping[str, Any], policy: Mapping[str, Any], records: Optional[Mapping[str, Any]] = None, confidence: Optional[str] = None, shadow: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Return a user-facing recommendation for Live Policy Assistance.

    Live policy is intentionally conservative: it only nudges legal Smart Race
    Solver candidates.  The recommendation keeps it disabled until the local
    dataset has enough turn records, strong race-result coverage, and at least
    one learned race/item/event adjustment above the configured confidence gate.

    v6.7.8: also gates on shadow-mode precision.  Earlier versions green-lit
    enablement based on data sufficiency alone, which let confidently-wrong
    models slip through (a model can have 80 high-confidence adjustments
    while still being right only 19% of the time).  When shadow has
    evaluated at least 100 race hints, precision must clear the
    ``min_shadow_precision`` threshold (default 0.60) before the
    recommendation flips to ENABLE.
    """
    records = records or {}
    health = health or {}
    policy = policy or {}
    config = config or {}
    shadow = shadow or {}
    turn_records = safe_int(records.get("turn_decisions") or records.get("turn_rows"), 0)
    race_rows = safe_int(health.get("race_rows"), 0)
    race_with_result = safe_int(health.get("race_rows_with_result"), 0)
    coverage = safe_float(health.get("race_result_coverage"), 0.0)
    if not coverage and race_rows:
        coverage = race_with_result / max(1, race_rows)
    adjustment_count = (
        len(policy.get("races") or {})
        + len(policy.get("items") or {})
        + len(policy.get("events") or {})
    )
    threshold = safe_float(config.get("confidence_threshold", policy.get("confidence_threshold", MIN_CONFIDENCE_DEFAULT)), MIN_CONFIDENCE_DEFAULT)
    safe = bool(health.get("safe_for_live_policy", True))
    # v6.7.8: shadow-mode precision floor.  Default 0.60 (60%) -- below
    # this the model's "this race is risky" warnings are net-negative
    # for race count (more good races suppressed than bad ones avoided).
    # Configurable per-deployment via ``min_shadow_precision``.
    min_shadow_precision = safe_float(config.get("min_shadow_precision"), 0.60)
    # ``min_shadow_evaluations`` controls how many race hints must have
    # been evaluated in shadow before precision is trusted as a signal
    # (below this, precision is too noisy to act on -- skip the gate).
    min_shadow_evaluations = safe_int(config.get("min_shadow_evaluations"), 100)
    shadow_evaluated = safe_int(shadow.get("evaluated_races"), 0)
    shadow_precision = safe_float(shadow.get("precision"), 0.0)

    reasons: List[str] = []
    if not safe:
        reasons.append("AI health checks are unsafe; race rows are missing reliable results.")
    if turn_records < max(250, safe_int(config.get("min_turn_records"), 10)):
        reasons.append(f"Only {turn_records} turn records are available; collect more completed careers first.")
    if race_rows and coverage < 0.85:
        reasons.append(f"Race-result coverage is {round(coverage * 100)}%; recommended minimum is 85%.")
    if race_rows < 50:
        reasons.append(f"Only {race_rows} race rows are available; learned race hints may be noisy.")
    if adjustment_count <= 0:
        reasons.append("No learned race/item/event adjustments have enough confidence yet.")
    # v6.7.8: precision gate -- only applies once shadow has evaluated
    # enough hints to be statistically meaningful.
    if shadow_evaluated >= min_shadow_evaluations and shadow_precision < min_shadow_precision:
        reasons.append(
            f"Shadow-mode precision is {round(shadow_precision * 100)}% over {shadow_evaluated} evaluated hints; "
            f"minimum is {round(min_shadow_precision * 100)}%. Enabling would suppress more good races than bad ones."
        )

    enabled = bool(config.get("enable_live_policy_assistance", False)) and bool(policy.get("enabled", True))
    recommend_enable = not reasons
    confidence_label = str(confidence or "").lower()
    if confidence_label == "low" and turn_records < 1000:
        recommend_enable = False
        if not any("confidence" in r.lower() for r in reasons):
            reasons.append("Model confidence is still low.")

    if recommend_enable:
        message = (
            f"Recommended: ENABLE. Model data looks healthy: {turn_records} turn records, "
            f"{race_with_result}/{race_rows} race results, and {adjustment_count} learned adjustments "
            f"above the {threshold:.2f} confidence gate."
        )
        if shadow_evaluated >= min_shadow_evaluations:
            message += f" Shadow precision {round(shadow_precision * 100)}%."
        status = "recommended_on"
    else:
        message = "Recommended: KEEP DISABLED. " + " ".join(reasons[:4])
        status = "recommended_off"

    return {
        "enabled": enabled,
        "recommend_enable": recommend_enable,
        "status": status,
        "message": message,
        "reasons": reasons,
        "turn_records": turn_records,
        "race_rows": race_rows,
        "race_rows_with_result": race_with_result,
        "race_result_coverage": round(coverage, 4),
        "adjustment_count": adjustment_count,
        "confidence_threshold": threshold,
        "shadow_precision": round(shadow_precision, 4),
        "shadow_evaluated_races": shadow_evaluated,
        "min_shadow_precision": min_shadow_precision,
        "min_shadow_evaluations": min_shadow_evaluations,
    }

def _dataset_paths(root: Path) -> Dict[str, Path]:
    return {kind: root / name for kind, name in DATASET_FILES.items()}


def _action_type(row: Mapping[str, Any]) -> str:
    return str(((row.get("action") or {}).get("type") or "unknown")).strip().lower()


def _reward(row: Mapping[str, Any]) -> float:
    return safe_float((row.get("outcome") or {}).get("reward"), 0.0)


def _race_result(row: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(((row.get("outcome") or {}).get("race_result") or {}))


def _clock_retry(row: Mapping[str, Any]) -> Dict[str, Any]:
    outcome = row.get("outcome") or {}
    retry = outcome.get("clock_retry") or _race_result(row).get("clock_retry") or {}
    return dict(retry) if isinstance(retry, Mapping) else {}


def _clock_policy(row: Mapping[str, Any]) -> Dict[str, Any]:
    meta = _turn_metadata(row)
    policy = meta.get("clock_policy") if isinstance(meta.get("clock_policy"), Mapping) else {}
    return dict(policy)


def _program_key(row: Mapping[str, Any]) -> str:
    action = row.get("action") or {}
    pid = action.get("program_id") or _race_result(row).get("program_id")
    return str(safe_int(pid)) if pid not in (None, "", 0, "0") else ""


def _turn_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    meta = row.get("turn_metadata") or row.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}





def _iter_nested_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    """Yield mapping nodes from shallow/nested telemetry structures.

    Item/event telemetry often stores useful rows under keys such as ``selected``
    or ``attempt``.  v5.33 only inspected the top-level object, which made the
    item model empty despite thousands of item attempts in the logs.
    """
    if isinstance(value, Mapping):
        yield value
        for key in ("selected", "attempt", "attempts", "items", "payload", "item", "result"):
            child = value.get(key)
            if isinstance(child, list):
                for elem in child:
                    yield from _iter_nested_mappings(elem)
            elif isinstance(child, Mapping):
                yield from _iter_nested_mappings(child)
    elif isinstance(value, list):
        for elem in value:
            yield from _iter_nested_mappings(elem)


def _item_identity(item: Mapping[str, Any]) -> Tuple[str, str]:
    ident = item.get("item_id") or item.get("id") or item.get("item") or item.get("name") or item.get("item_name")
    if ident in (None, ""):
        return "", ""
    name = str(item.get("name") or item.get("item_name") or item.get("label") or ident)
    return str(ident), name


def _load_events_seen(root: Path) -> List[Mapping[str, Any]]:
    """Load runtime seen-event records when present.

    Depending on profile layout this file can live alongside ``ai/`` or one
    level above the profile runtime.  The parser accepts list or dict shapes.
    """
    candidates = [root.parent / "events_seen.json", root.parent.parent / "events_seen.json"]
    for path in candidates:
        data = _read_json(path, None)
        if data is None:
            continue
        if isinstance(data, list):
            return [row for row in data if isinstance(row, Mapping)]
        if isinstance(data, Mapping):
            rows = data.get("events") or data.get("rows") or data.get("seen")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, Mapping)]
            return [row for row in data.values() if isinstance(row, Mapping)]
    return []


def _read_runtime_race_outcomes(root: Path) -> Mapping[str, Any]:
    for path in (root.parent / "race_outcomes.json", root.parent.parent / "race_outcomes.json"):
        data = _read_json(path, {})
        if isinstance(data, Mapping) and data:
            return data
    return {}


def _normalise_race_outcome_programs(payload: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Convert known race_outcomes.json shapes into program buckets."""
    if not isinstance(payload, Mapping):
        return {}
    src = payload.get("programs") or payload.get("races") or payload
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(src, Mapping):
        return out
    for key, row in src.items():
        if not isinstance(row, Mapping):
            continue
        pid = str(row.get("program_id") or key)
        starts = safe_int(row.get("starts") or row.get("attempts") or row.get("count"))
        wins = safe_int(row.get("wins") or row.get("win_count"))
        losses = safe_int(row.get("losses") or max(0, starts - wins))
        if starts <= 0:
            continue
        out[pid] = {
            "starts": starts,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / max(1, starts), 4),
            "avg_rank": safe_float(row.get("avg_rank"), 1.0 if wins else 99.0),
            "clean_wins": safe_int(row.get("clean_wins")),
            "wins_after_clock": safe_int(row.get("wins_after_clock")),
            "clock_retry_races": safe_int(row.get("clock_retry_races")),
            "clocks_used": safe_int(row.get("clocks_used")),
            "clock_policy_enabled_starts": safe_int(row.get("clock_policy_enabled_starts")),
            "clock_policy_disabled_starts": safe_int(row.get("clock_policy_disabled_starts")),
            "name": row.get("name") or row.get("race_name") or "",
            "source": "race_outcomes.json",
        }
    return out


def _atomic_write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")
        # Validate JSONL before replacing.
        with tmp.open("r", encoding="utf-8") as fh:
            for line in fh:
                json.loads(line)
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    return len(rows)


def _data_health(turn_rows: List[Mapping[str, Any]], summaries: List[Mapping[str, Any]], item_table: Optional[Mapping[str, Any]] = None, event_table: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    race_rows = [row for row in turn_rows if _action_type(row) == "race"]
    race_with_result = [row for row in race_rows if _race_result(row)]
    clock_retry_rows = [row for row in race_rows if safe_int((row.get("outcome") or {}).get("clocks_used") or _clock_retry(row).get("used")) > 0]
    clock_policy_enabled_rows = [row for row in race_rows if bool(_clock_policy(row).get("user_enabled", _clock_policy(row).get("enabled", False)))]
    summaries_with_stats = [row for row in summaries if isinstance(row.get("final_stats"), Mapping) and row.get("final_stats")]
    warnings: List[str] = []
    if race_rows and not race_with_result:
        warnings.append("Race actions exist, but no race result payloads were extracted; live policy disabled.")
    if summaries and len(summaries_with_stats) < len(summaries):
        warnings.append("Some career summaries are missing final stats.")
    items = item_table.get("items", {}) if isinstance(item_table, Mapping) else {}
    events = event_table.get("events", {}) if isinstance(event_table, Mapping) else {}
    return {
        "checked_at": now_iso(),
        "turn_decisions": len(turn_rows),
        "career_summaries": len(summaries),
        "race_rows": len(race_rows),
        "race_rows_with_result": len(race_with_result),
        "race_result_coverage": round(len(race_with_result) / max(1, len(race_rows)), 4),
        "clock_retry_rows": len(clock_retry_rows),
        "clock_policy_enabled_rows": len(clock_policy_enabled_rows),
        "clock_policy_enabled_rate": round(len(clock_policy_enabled_rows) / max(1, len(race_rows)), 4),
        "career_summaries_with_final_stats": len(summaries_with_stats),
        "item_records_parsed": len(items),
        "event_records_parsed": len(events),
        "safe_for_live_policy": not (race_rows and not race_with_result),
        "warnings": warnings,
    }
def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return sum(vals) / max(1, len(vals))


def _confidence(samples: int, floor: int = 2) -> float:
    if samples <= 0:
        return 0.0
    # Saturates gradually: 2 samples ~= .50, 5 ~= .71, 10 ~= .83, 20 ~= .91.
    return round(samples / (samples + max(1, floor)), 4)


def _bucket_finalize(bucket: Dict[str, Any], sample_key: str = "samples") -> Dict[str, Any]:
    samples = safe_int(bucket.get(sample_key))
    rewards = list(bucket.pop("_rewards", []) or [])
    ranks = list(bucket.pop("_ranks", []) or [])
    bucket["avg_reward"] = round(_mean(rewards), 4) if rewards else 0.0
    if ranks:
        bucket["avg_rank"] = round(_mean(ranks), 3)
    bucket["confidence"] = _confidence(samples)
    return bucket


def build_race_outcome_table(turn_rows: List[Mapping[str, Any]], runtime_outcomes: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    programs: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"starts": 0, "wins": 0, "losses": 0, "clean_wins": 0, "wins_after_clock": 0, "clock_retry_races": 0, "clocks_used": 0, "clock_policy_enabled_starts": 0, "clock_policy_disabled_starts": 0, "_rewards": [], "_ranks": [], "turns": Counter()})
    for row in turn_rows:
        if _action_type(row) != "race":
            continue
        key = _program_key(row)
        if not key:
            continue
        result = _race_result(row)
        if not result:
            # Missing result rows should not be treated as losses.  v5.33 did
            # that by defaulting missing ranks to 99, creating false 0% win rates.
            continue
        rank = safe_int(result.get("rank") or result.get("result_rank"), 99)
        bucket = programs[key]
        bucket["starts"] += 1
        bucket["wins"] += 1 if rank == 1 else 0
        bucket["losses"] += 0 if rank == 1 else 1
        retry = _clock_retry(row)
        policy = _clock_policy(row)
        clocks_used = safe_int((row.get("outcome") or {}).get("clocks_used") or retry.get("used"))
        initial_rank = safe_int(result.get("initial_rank") or retry.get("initial_rank") or rank, rank)
        if bool(policy.get("user_enabled", policy.get("enabled", False))):
            bucket["clock_policy_enabled_starts"] += 1
        else:
            bucket["clock_policy_disabled_starts"] += 1
        if clocks_used:
            bucket["clock_retry_races"] += 1
            bucket["clocks_used"] += clocks_used
        if initial_rank == 1:
            bucket["clean_wins"] += 1
        elif rank == 1 and clocks_used:
            bucket["wins_after_clock"] += 1
        bucket["_ranks"].append(rank)
        bucket["_rewards"].append(_reward(row))
        bucket["turns"][str(safe_int(row.get("turn")))] += 1
        for attr in ("name", "grade", "distance_m", "distance", "surface", "race_type", "source", "master_metadata", "performance_hint"):
            val = result.get(attr) or ((row.get("action") or {}).get(attr))
            if val not in (None, ""):
                bucket[attr] = val
    # v5.34: fold in runtime race_outcomes.json as aggregate truth when present.
    for pid, row in _normalise_race_outcome_programs(runtime_outcomes or {}).items():
        bucket = programs[pid]
        if safe_int(bucket.get("starts")) <= 0:
            bucket["starts"] = safe_int(row.get("starts"))
            bucket["wins"] = safe_int(row.get("wins"))
            bucket["losses"] = safe_int(row.get("losses"))
            for key in ("clean_wins", "wins_after_clock", "clock_retry_races", "clocks_used", "clock_policy_enabled_starts", "clock_policy_disabled_starts"):
                bucket[key] = safe_int(row.get(key))
            bucket["_ranks"].append(safe_float(row.get("avg_rank"), 1.0))
            bucket["source"] = row.get("source")
            if row.get("name"):
                bucket["name"] = row.get("name")
    out = {}
    for key, bucket in programs.items():
        starts = max(1, safe_int(bucket.get("starts")))
        wins = safe_int(bucket.get("wins"))
        bucket["win_rate"] = round(wins / starts, 4)
        bucket["clean_win_rate"] = round(safe_int(bucket.get("clean_wins")) / starts, 4)
        bucket["clock_dependency_rate"] = round(safe_int(bucket.get("wins_after_clock")) / max(1, wins), 4) if wins else 0.0
        bucket["clock_retry_rate"] = round(safe_int(bucket.get("clock_retry_races")) / starts, 4)
        bucket["turns"] = dict(bucket.get("turns") or {})
        out[key] = _bucket_finalize(bucket, sample_key="starts")
    return {"version": AI_TRAINER_VERSION, "updated_at": now_iso(), "programs": out}

def build_item_effectiveness_table(turn_rows: List[Mapping[str, Any]]) -> Dict[str, Any]:
    items: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"uses": 0, "buys": 0, "_rewards": [], "turns": Counter(), "names": Counter()})
    for row in turn_rows:
        reward = _reward(row)
        meta = _turn_metadata(row)
        for event_key, count_key in (("item_usage_attempts", "uses"), ("item_buy_attempts", "buys")):
            for event in meta.get(event_key) or []:
                for item in _iter_nested_mappings(event):
                    ident, name = _item_identity(item)
                    if not ident:
                        continue
                    bucket = items[ident]
                    bucket[count_key] += 1
                    bucket["_rewards"].append(reward)
                    bucket["turns"][str(safe_int(row.get("turn")))] += 1
                    bucket["names"][name or ident] += 1
    out = {}
    for key, bucket in items.items():
        samples = safe_int(bucket.get("uses")) + safe_int(bucket.get("buys"))
        bucket["samples"] = samples
        bucket["name"] = bucket["names"].most_common(1)[0][0] if bucket.get("names") else key
        bucket["turns"] = dict(bucket.get("turns") or {})
        bucket.pop("names", None)
        out[key] = _bucket_finalize(bucket, sample_key="samples")
    return {"version": AI_TRAINER_VERSION, "updated_at": now_iso(), "items": out}

def build_event_outcome_table(turn_rows: List[Mapping[str, Any]], events_seen: Optional[List[Mapping[str, Any]]] = None) -> Dict[str, Any]:
    events: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"samples": 0, "choices": defaultdict(lambda: {"samples": 0, "_rewards": []}), "_rewards": []})
    for row in turn_rows:
        reward = _reward(row)
        meta = _turn_metadata(row)
        candidates = []
        candidates.extend(meta.get("events") or [])
        candidates.extend(meta.get("event_choices") or [])
        for ev in candidates:
            if not isinstance(ev, Mapping):
                continue
            ev_name = ev.get("story_id") or ev.get("event_id") or ev.get("title") or ev.get("name")
            if ev_name in (None, ""):
                continue
            key = str(ev_name)
            choice = str(ev.get("choice") or ev.get("selected") or ev.get("option") or ev.get("select") or "unknown")
            bucket = events[key]
            bucket["samples"] += 1
            bucket["_rewards"].append(reward)
            cb = bucket["choices"][choice]
            cb["samples"] += 1
            cb["_rewards"].append(reward)
    # Seed the table from runtime events_seen.json so it is not empty when event
    # choice details are stored outside career logs.
    for ev in events_seen or []:
        if not isinstance(ev, Mapping):
            continue
        ev_name = ev.get("story_id") or ev.get("event_id") or ev.get("title") or ev.get("name") or ev.get("key")
        if ev_name in (None, ""):
            continue
        choice = str(ev.get("choice") or ev.get("selected") or ev.get("option") or ev.get("select") or ev.get("last_choice") or "seen")
        key = str(ev_name)
        bucket = events[key]
        bucket["samples"] += 1
        bucket["_rewards"].append(0.0)
        cb = bucket["choices"][choice]
        cb["samples"] += 1
        cb["_rewards"].append(0.0)
    out = {}
    for key, bucket in events.items():
        choices = {}
        for choice, cb in (bucket.get("choices") or {}).items():
            choices[choice] = _bucket_finalize(cb, sample_key="samples")
        bucket["choices"] = choices
        out[key] = _bucket_finalize(bucket, sample_key="samples")
    return {"version": AI_TRAINER_VERSION, "updated_at": now_iso(), "events": out}

def build_race_risk_model(race_table: Mapping[str, Any], min_samples: int = 2) -> Dict[str, Any]:
    model = {}
    for pid, bucket in (race_table.get("programs") or {}).items():
        starts = safe_int(bucket.get("starts"))
        if starts < min_samples:
            continue
        win_rate = safe_float(bucket.get("win_rate"), 0.0)
        avg_rank = safe_float(bucket.get("avg_rank"), 1.0)
        avg_reward = safe_float(bucket.get("avg_reward"), 0.0)
        loss_rate = 1.0 - win_rate
        clean_win_rate = safe_float(bucket.get("clean_win_rate"), 0.0)
        clock_dependency_rate = safe_float(bucket.get("clock_dependency_rate"), 0.0)
        clock_retry_rate = safe_float(bucket.get("clock_retry_rate"), 0.0)
        clock_dependency_penalty = max(0.0, min(35.0, clock_dependency_rate * 35.0 + max(0.0, 1.0 - clean_win_rate) * 8.0))
        penalty = max(0.0, loss_rate * 45.0 + max(0.0, avg_rank - 1.0) * 6.0 - max(0.0, avg_reward) * 0.25)
        conf = _confidence(starts, floor=min_samples)
        model[str(pid)] = {
            "samples": starts,
            "win_rate": win_rate,
            "clean_win_rate": clean_win_rate,
            "clock_dependency_rate": clock_dependency_rate,
            "clock_retry_rate": clock_retry_rate,
            "wins_after_clock": safe_int(bucket.get("wins_after_clock")),
            "clean_wins": safe_int(bucket.get("clean_wins")),
            "clock_retry_races": safe_int(bucket.get("clock_retry_races")),
            "clocks_used": safe_int(bucket.get("clocks_used")),
            "avg_rank": avg_rank,
            "avg_reward": avg_reward,
            "penalty": round(min(80.0, penalty), 4),
            "clock_dependency_penalty": round(clock_dependency_penalty, 4),
            "confidence": conf,
            "direction": "penalty" if penalty > 0 or clock_dependency_penalty > 0 else "neutral",
            "reason": "Learned from local race outcome table, including clock retry dependency.",
        }
    return {"version": AI_TRAINER_VERSION, "updated_at": now_iso(), "model": model}


def build_item_value_model(item_table: Mapping[str, Any], min_samples: int = 2) -> Dict[str, Any]:
    model = {}
    for key, bucket in (item_table.get("items") or {}).items():
        samples = safe_int(bucket.get("samples"))
        if samples < min_samples:
            continue
        avg_reward = safe_float(bucket.get("avg_reward"), 0.0)
        conf = _confidence(samples, floor=min_samples)
        model[str(key)] = {
            "samples": samples,
            "avg_reward": avg_reward,
            "adjustment": round(max(-20.0, min(20.0, avg_reward)), 4),
            "confidence": conf,
            "name": bucket.get("name") or str(key),
            "reason": "Learned from turns where this item appeared in buy/use telemetry.",
        }
    return {"version": AI_TRAINER_VERSION, "updated_at": now_iso(), "model": model}


def build_event_value_model(event_table: Mapping[str, Any], min_samples: int = 2) -> Dict[str, Any]:
    model = {}
    for key, bucket in (event_table.get("events") or {}).items():
        choices = {}
        for choice, cb in (bucket.get("choices") or {}).items():
            samples = safe_int(cb.get("samples"))
            if samples < min_samples:
                continue
            avg_reward = safe_float(cb.get("avg_reward"), 0.0)
            choices[choice] = {
                "samples": samples,
                "avg_reward": avg_reward,
                "adjustment": round(max(-25.0, min(25.0, avg_reward)), 4),
                "confidence": _confidence(samples, floor=min_samples),
            }
        if choices:
            model[str(key)] = {"choices": choices, "reason": "Learned from local event choice outcomes."}
    return {"version": AI_TRAINER_VERSION, "updated_at": now_iso(), "model": model}


def build_policy_adjustments(race_model: Mapping[str, Any], item_model: Mapping[str, Any], event_model: Mapping[str, Any], cfg: Mapping[str, Any]) -> Dict[str, Any]:
    threshold = safe_float(cfg.get("confidence_threshold"), MIN_CONFIDENCE_DEFAULT)
    max_abs = safe_float(cfg.get("max_abs_live_adjustment"), 25.0)
    warn_win_rate_ceiling = max(0.0, min(1.0, safe_float(cfg.get("warn_win_rate_ceiling"), 0.50)))
    races = {}
    for pid, row in (race_model.get("model") or {}).items():
        conf = safe_float(row.get("confidence"), 0.0)
        if conf < threshold:
            continue
        win_rate = safe_float(row.get("win_rate"), 0.0)
        base_penalty = max(0.0, safe_float(row.get("penalty"), 0.0))
        clock_penalty = max(0.0, safe_float(row.get("clock_dependency_penalty"), 0.0))
        # v6.7.9: only emit a race-risk warning (negative adjustment) when the
        # program genuinely loses often.  A race the bot wins most of the time
        # still accrues a small penalty from the avg-rank term, so warnings used
        # to fire on races that then won anyway -- shadow precision sat ~16%.
        # Suppress the race-risk penalty above the win-rate ceiling; clock
        # dependency is still recorded (adjustment 0, not a warning).
        if win_rate > warn_win_rate_ceiling:
            base_penalty = 0.0
        adjustment = -min(max_abs, base_penalty)
        if adjustment or clock_penalty:
            races[str(pid)] = {
                "adjustment": round(adjustment, 4),
                "confidence": conf,
                "samples": row.get("samples"),
                "reason": row.get("reason") or "Local learned race-risk/clock-dependency penalty.",
                "clean_win_rate": row.get("clean_win_rate"),
                "clock_dependency_rate": row.get("clock_dependency_rate"),
                "clock_dependency_penalty": round(min(max_abs, clock_penalty), 4),
            }
    items = {}
    for key, row in (item_model.get("model") or {}).items():
        conf = safe_float(row.get("confidence"), 0.0)
        if conf >= threshold:
            items[str(key)] = {"adjustment": row.get("adjustment"), "confidence": conf, "reason": row.get("reason")}
    events = {}
    for key, row in (event_model.get("model") or {}).items():
        choices = {}
        for choice, cb in (row.get("choices") or {}).items():
            conf = safe_float(cb.get("confidence"), 0.0)
            if conf >= threshold:
                choices[choice] = {"adjustment": cb.get("adjustment"), "confidence": conf}
        if choices:
            events[key] = {"choices": choices, "reason": row.get("reason")}
    return {
        "version": AI_TRAINER_VERSION,
        "updated_at": now_iso(),
        "enabled": bool(cfg.get("enable_live_policy_assistance", True)),
        "confidence_threshold": threshold,
        "max_abs_live_adjustment": max_abs,
        "warn_win_rate_ceiling": warn_win_rate_ceiling,
        "races": races,
        "items": items,
        "events": events,
        "reversible": True,
        "safety": "AI adjustments only modify scores for legal candidate actions; deterministic gates still choose/execute.",
    }


def build_suggested_config_tuning(turn_rows: List[Mapping[str, Any]], race_table: Mapping[str, Any], cfg: Mapping[str, Any]) -> Dict[str, Any]:
    actions = Counter(_action_type(row) for row in turn_rows)
    senior_race_count = sum(1 for row in turn_rows if _action_type(row) == "race" and 65 <= safe_int(row.get("turn")) <= 72)
    risky_races = [pid for pid, b in (race_table.get("programs") or {}).items() if safe_int(b.get("starts")) >= 3 and safe_float(b.get("win_rate"), 1.0) < 0.6]
    suggestions = []
    if actions.get("rest", 0) + actions.get("recreate", 0) >= 5:
        suggestions.append({
            "setting": "itemRecoverySupportWeight",
            "suggested_delta": +0.25,
            "reason": "Frequent rest/recreation detected; value energy/recovery support more strongly in schedule planning.",
            "confidence": 0.65,
        })
    if senior_race_count <= 2 and len(turn_rows) >= 50:
        suggestions.append({
            "setting": "lateSeniorRacePressure",
            "suggested_delta": +4.0,
            "reason": "Low race count in turns 65-72; increase late Senior race pressure for race-heavy objectives.",
            "confidence": 0.7,
        })
    clock_dependent = [pid for pid, b in (race_table.get("programs") or {}).items() if safe_int(b.get("starts")) >= 3 and safe_float(b.get("clock_dependency_rate"), 0.0) >= 0.25]
    if clock_dependent:
        suggestions.append({
            "setting": "clockAwareRaceRisk",
            "suggested_delta": +0.2,
            "reason": f"{len(clock_dependent)} race program(s) often need clocks to convert losses into wins; apply stronger penalties when Burn Clocks is off.",
            "confidence": 0.78,
            "examples": clock_dependent[:5],
        })
    if risky_races:
        suggestions.append({
            "setting": "outcomeRiskWeight",
            "suggested_delta": +0.2,
            "reason": f"{len(risky_races)} race program(s) have repeated local losses; strengthen learned risk penalties.",
            "confidence": 0.75,
            "examples": risky_races[:5],
        })
    if not suggestions:
        suggestions.append({
            "setting": "collect_more_data",
            "suggested_delta": 0,
            "reason": "No strong tuning signal yet. Keep collecting completed career logs.",
            "confidence": 0.4,
        })
    return {"version": AI_TRAINER_VERSION, "updated_at": now_iso(), "suggestions": suggestions}




def _race_rank_from_row(row: Mapping[str, Any]) -> int:
    result = _race_result(row)
    return safe_int(result.get("rank") or result.get("result_rank"), 0)


def _final_fans(summary: Mapping[str, Any]) -> int:
    final = summary.get("final_result") or summary.get("summary") or {}
    return safe_int(summary.get("final_fans") or final.get("fans") or final.get("final_fans") or summary.get("fans"), 0)


def _final_stats(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    final = summary.get("final_result") or summary.get("summary") or {}
    stats = summary.get("final_stats") or final.get("stats") or summary.get("stats") or {}
    return stats if isinstance(stats, Mapping) else {}


def _summary_key(summary: Mapping[str, Any]) -> str:
    preset = str(summary.get("preset_name") or summary.get("preset") or "unknown").strip() or "unknown"
    trainee = str(summary.get("trainee_id") or summary.get("trainee") or summary.get("chara_id") or "unknown").strip() or "unknown"
    return f"{preset}::{trainee}"


def build_shadow_policy_report(turn_rows: List[Mapping[str, Any]], policy: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate learned policy hints without changing live decisions.

    Pre Icarus does not usually store full candidate sets for every turn, so the
    shadow report focuses on the action that actually happened.  A warning is
    considered useful when the policy would have penalized a race that then lost;
    it is considered a false alarm when the policy would have penalized a race
    that won.  This gives users a clear proof signal before enabling live hints.
    """
    race_hints = policy.get("races") or {}
    evaluated = 0
    warnings = 0
    useful = 0
    false_alarms = 0
    total_adjustment = 0.0
    examples = []
    for row in turn_rows:
        if _action_type(row) != "race":
            continue
        pid = _program_key(row)
        hint = race_hints.get(pid) if pid else None
        if not hint:
            continue
        rank = _race_rank_from_row(row)
        adjustment = safe_float(hint.get("adjustment"), 0.0)
        confidence = safe_float(hint.get("confidence"), 0.0)
        evaluated += 1
        total_adjustment += adjustment
        if adjustment < 0:
            warnings += 1
            if rank and rank != 1:
                useful += 1
            elif rank == 1:
                false_alarms += 1
        if len(examples) < 12:
            examples.append({
                "turn": safe_int(row.get("turn")),
                "program_id": pid,
                "rank": rank,
                "adjustment": round(adjustment, 4),
                "confidence": confidence,
                "reason": hint.get("reason") or "learned race hint",
            })
    precision = useful / max(1, useful + false_alarms)
    return {
        "version": AI_TRAINER_VERSION,
        "updated_at": now_iso(),
        "evaluated_races": evaluated,
        "warnings": warnings,
        "useful_warnings": useful,
        "false_alarms": false_alarms,
        "precision": round(precision, 4),
        "avg_adjustment": round(total_adjustment / max(1, evaluated), 4),
        "examples": examples,
        "mode": "shadow",
        "summary": "Shadow Mode compares learned race-risk hints against historical outcomes without changing live play.",
    }


def build_backtest_report(turn_rows: List[Mapping[str, Any]], race_model: Mapping[str, Any], tuning: Mapping[str, Any]) -> Dict[str, Any]:
    """Replay historical race rows against the learned risk model.

    This is intentionally conservative: it does not claim exact alternate-future
    fan totals.  It measures how often the current model would have warned about
    races that actually lost, and how many winning races it would have penalized.
    """
    model = race_model.get("model") or {}
    race_rows = [row for row in turn_rows if _action_type(row) == "race" and _program_key(row)]
    failed = 0
    warned_failed = 0
    winning_false_warnings = 0
    total_warned = 0
    late_senior_races = 0
    late_senior_failures = 0
    risky_examples = []
    for row in race_rows:
        pid = _program_key(row)
        rank = _race_rank_from_row(row)
        turn = safe_int(row.get("turn"))
        if 65 <= turn <= 72:
            late_senior_races += 1
            if rank and rank != 1:
                late_senior_failures += 1
        lost = bool(rank and rank != 1)
        failed += 1 if lost else 0
        risk = model.get(pid) or {}
        penalty = safe_float(risk.get("penalty"), 0.0)
        conf = safe_float(risk.get("confidence"), 0.0)
        warned = penalty >= 10.0 and conf >= 0.5
        total_warned += 1 if warned else 0
        if warned and lost:
            warned_failed += 1
        if warned and rank == 1:
            winning_false_warnings += 1
        if warned and len(risky_examples) < 15:
            risky_examples.append({
                "turn": turn,
                "program_id": pid,
                "rank": rank,
                "penalty": round(penalty, 4),
                "confidence": conf,
            })
    capture_rate = warned_failed / max(1, failed)
    false_warning_rate = winning_false_warnings / max(1, total_warned)
    return {
        "version": AI_TRAINER_VERSION,
        "updated_at": now_iso(),
        "historical_race_rows": len(race_rows),
        "failed_races": failed,
        "risk_warnings": total_warned,
        "failed_races_captured": warned_failed,
        "capture_rate": round(capture_rate, 4),
        "winning_false_warnings": winning_false_warnings,
        "false_warning_rate": round(false_warning_rate, 4),
        "late_senior_races": late_senior_races,
        "late_senior_failures": late_senior_failures,
        "suggested_config_tuning": tuning.get("suggestions") or [],
        "examples": risky_examples,
        "summary": "Backtest estimates whether learned risk would have flagged historically bad races.",
    }


def build_epithet_confidence(turn_rows: List[Mapping[str, Any]], summaries: List[Mapping[str, Any]]) -> Dict[str, Any]:
    names: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"samples": 0, "completed": 0, "dead": 0, "_rewards": []})
    for row in turn_rows:
        reward = _reward(row)
        out = row.get("outcome") or {}
        action = row.get("action") or {}
        contributions = out.get("epithet_contributions") or action.get("epithet_contributions") or []
        if isinstance(contributions, Mapping):
            contributions = list(contributions.values())
        for item in contributions if isinstance(contributions, list) else []:
            if not isinstance(item, Mapping):
                name = str(item or "").strip()
                state = "in_progress"
            else:
                name = str(item.get("name") or item.get("epithet") or item.get("id") or "").strip()
                state = str(item.get("state") or item.get("status") or "in_progress").lower()
            if not name:
                continue
            bucket = names[name]
            bucket["samples"] += 1
            bucket["completed"] += 1 if state in {"completed", "complete", "done"} else 0
            bucket["dead"] += 1 if state == "dead" else 0
            bucket["_rewards"].append(reward)
    for summary in summaries:
        completed = summary.get("epithets_completed") or (summary.get("final_result") or {}).get("epithets_completed") or []
        if isinstance(completed, list):
            for name in completed:
                key = str(name or "").strip()
                if key:
                    names[key]["samples"] += 1
                    names[key]["completed"] += 1
    out = {}
    for key, bucket in names.items():
        samples = safe_int(bucket.get("samples"))
        completed = safe_int(bucket.get("completed"))
        dead = safe_int(bucket.get("dead"))
        out[key] = {
            "samples": samples,
            "completed": completed,
            "dead": dead,
            "completion_rate": round(completed / max(1, samples), 4),
            "dead_rate": round(dead / max(1, samples), 4),
            "avg_reward": round(_mean(bucket.get("_rewards") or []), 4) if bucket.get("_rewards") else 0.0,
            "confidence": _confidence(samples, floor=3),
        }
    return {"version": AI_TRAINER_VERSION, "updated_at": now_iso(), "epithets": out}


def build_preset_trainee_confidence(summaries: List[Mapping[str, Any]], turn_rows: List[Mapping[str, Any]]) -> Dict[str, Any]:
    groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"careers": 0, "completed": 0, "_fans": [], "_stats": defaultdict(list), "race_rows": 0, "race_wins": 0})
    for summary in summaries:
        key = _summary_key(summary)
        bucket = groups[key]
        bucket["careers"] += 1
        if summary.get("career_completed", True):
            bucket["completed"] += 1
        fans = _final_fans(summary)
        if fans:
            bucket["_fans"].append(fans)
        for stat, value in _final_stats(summary).items():
            bucket["_stats"][str(stat)].append(safe_float(value, 0.0))
    # Best effort fallback for turn-only datasets: group under unknown if no summaries.
    if not groups and turn_rows:
        groups["unknown::unknown"]["careers"] = 0
    for row in turn_rows:
        if _action_type(row) != "race":
            continue
        # Most turn rows do not carry preset metadata, but keep global evidence.
        key = str((row.get("metadata") or {}).get("preset_trainee_key") or "global::global")
        bucket = groups[key]
        bucket["race_rows"] += 1
        if _race_rank_from_row(row) == 1:
            bucket["race_wins"] += 1
    out = {}
    for key, bucket in groups.items():
        careers = safe_int(bucket.get("careers"))
        stats = {stat: round(_mean(vals), 2) for stat, vals in (bucket.get("_stats") or {}).items() if vals}
        race_rows = safe_int(bucket.get("race_rows"))
        race_wins = safe_int(bucket.get("race_wins"))
        out[key] = {
            "careers": careers,
            "completed": safe_int(bucket.get("completed")),
            "completion_rate": round(safe_int(bucket.get("completed")) / max(1, careers), 4) if careers else 0.0,
            "avg_final_fans": round(_mean(bucket.get("_fans") or []), 2) if bucket.get("_fans") else 0.0,
            "avg_final_stats": stats,
            "race_rows": race_rows,
            "race_win_rate": round(race_wins / max(1, race_rows), 4) if race_rows else 0.0,
            "confidence": _confidence(max(careers, race_rows), floor=5),
        }
    return {"version": AI_TRAINER_VERSION, "updated_at": now_iso(), "groups": out}


def build_ai_dashboard_payload(
    root: Path,
    turn_rows: List[Mapping[str, Any]],
    summaries: List[Mapping[str, Any]],
    race_table: Mapping[str, Any],
    item_table: Mapping[str, Any],
    event_table: Mapping[str, Any],
    risk_model: Mapping[str, Any],
    item_model: Mapping[str, Any],
    event_model: Mapping[str, Any],
    tuning: Mapping[str, Any],
    shadow: Mapping[str, Any],
    backtest: Mapping[str, Any],
    epithet: Mapping[str, Any],
    preset_conf: Mapping[str, Any],
    style_payload: Mapping[str, Any],
    health: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> Dict[str, Any]:
    race_programs = race_table.get("programs") or {}
    risky = []
    for pid, row in race_programs.items():
        if safe_int(row.get("starts")) >= 3 and safe_float(row.get("win_rate"), 1.0) < 0.75:
            risky.append({"program_id": pid, "name": row.get("name") or "", "starts": row.get("starts"), "win_rate": row.get("win_rate"), "clean_win_rate": row.get("clean_win_rate"), "clock_dependency_rate": row.get("clock_dependency_rate"), "avg_rank": row.get("avg_rank")})
    risky.sort(key=lambda row: (safe_float(row.get("win_rate"), 1.0), -safe_int(row.get("starts"))))
    item_values = sorted((item_model.get("model") or {}).values(), key=lambda row: safe_float(row.get("adjustment"), 0.0), reverse=True)[:10]
    event_values = []
    for key, row in (event_model.get("model") or {}).items():
        for choice, cb in (row.get("choices") or {}).items():
            event_values.append({"event": key, "choice": choice, **cb})
    event_values.sort(key=lambda row: safe_float(row.get("adjustment"), 0.0), reverse=True)
    groups = preset_conf.get("groups") or {}
    top_groups = sorted(groups.items(), key=lambda kv: (safe_float(kv[1].get("confidence"), 0.0), safe_float(kv[1].get("avg_final_fans"), 0.0)), reverse=True)[:8]
    confidence = "low"
    if safe_int(len(turn_rows)) >= 5000 and safe_float(health.get("race_result_coverage"), 0.0) >= 0.85:
        confidence = "high"
    elif safe_int(len(turn_rows)) >= 1000 and safe_float(health.get("race_result_coverage"), 0.0) >= 0.70:
        confidence = "medium"
    warnings = list(health.get("warnings") or [])
    if risky:
        warnings.append(f"{len(risky)} race programs have local win rate below 75%.")
    if safe_int(backtest.get("late_senior_races")) <= max(2, safe_int(len(summaries))):
        warnings.append("Late Senior race density may still be low; keep late-senior pressure enabled for race-heavy objectives.")
    return {
        "success": True,
        "version": AI_TRAINER_VERSION,
        "updated_at": now_iso(),
        "ai_root": str(root),
        "confidence": confidence,
        "records": {
            "turn_decisions": len(turn_rows),
            "career_summaries": len(summaries),
            "race_programs": len(race_programs),
            "clock_retry_rows": health.get("clock_retry_rows", 0),
            "clock_policy_enabled_rows": health.get("clock_policy_enabled_rows", 0),
            "item_records": len(item_table.get("items") or {}),
            "event_records": len(event_table.get("events") or {}),
            "epithet_records": len(epithet.get("epithets") or {}),
            "style_adaptation_experiences": ((style_payload.get("report") or {}).get("completed_experiences") or 0) if isinstance(style_payload, Mapping) else 0,
            "style_change_outcomes": ((style_payload.get("report") or {}).get("style_change_outcomes") or 0) if isinstance(style_payload, Mapping) else 0,
        },
        "health": dict(health or {}),
        "style_adaptation": dict(style_payload or {}),
        "local_llm": local_llm.dashboard_summary(root),
        "live_policy": {
            "enabled": bool(policy.get("enabled")),
            "race_adjustments": len(policy.get("races") or {}),
            "item_adjustments": len(policy.get("items") or {}),
            "event_adjustments": len(policy.get("events") or {}),
            "confidence_threshold": policy.get("confidence_threshold"),
            "recommendation": live_policy_recommendation(
                policy,
                health,
                policy,
                records={"turn_decisions": len(turn_rows)},
                confidence=confidence,
                shadow=shadow,
            ),
        },
        "shadow_mode": dict(shadow or {}),
        "backtest": dict(backtest or {}),
        "top_risky_races": risky[:10],
        "top_item_values": item_values,
        "top_event_values": event_values[:10],
        "suggestions": tuning.get("suggestions") or [],
        "epithet_confidence": sorted((epithet.get("epithets") or {}).items(), key=lambda kv: safe_float(kv[1].get("confidence"), 0.0), reverse=True)[:10],
        "preset_trainee_confidence": [{"key": key, **val} for key, val in top_groups],
        "warnings": warnings[:12],
    }

def build_llm_prompt_pack(root: Path, turn_rows: List[Mapping[str, Any]], tuning: Mapping[str, Any]) -> Dict[str, Any]:
    prompt_dir = root / "llm_advisor"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    risky = [row for row in turn_rows if _action_type(row) == "race" and ((_race_result(row).get("rank") or _race_result(row).get("result_rank")) not in (None, 1, "1"))]
    for row in risky[-50:]:
        rows.append({
            "schema_version": AI_TRAINER_VERSION,
            "task": "post_run_race_failure_analysis",
            "turn": row.get("turn"),
            "state": row.get("state") or {},
            "action": row.get("action") or {},
            "outcome": row.get("outcome") or {},
            "question": "Explain why this race may have failed and suggest deterministic solver features to reduce repeats.",
            "synthetic_weight": 0.0,
        })
    for suggestion in tuning.get("suggestions") or []:
        rows.append({
            "schema_version": AI_TRAINER_VERSION,
            "task": "config_tuning_review",
            "suggestion": suggestion,
            "question": "Review this local analytics tuning suggestion and propose safe Pre Icarus config defaults.",
            "synthetic_weight": 0.0,
        })
    latest_rows = rows[-200:]
    path = prompt_dir / "latest_prompt_pack.jsonl"
    count = _atomic_write_jsonl(path, latest_rows) if latest_rows else _atomic_write_jsonl(path, [])
    manifest = {"updated_at": now_iso(), "prompt_count": count, "path": str(path)}
    _atomic_write_json(prompt_dir / "latest_prompt_pack_manifest.json", manifest)
    return manifest

def build_post_run_report(root: Path, run_payload: Mapping[str, Any], race_table: Mapping[str, Any], tuning: Mapping[str, Any]) -> Dict[str, Any]:
    report_dir = root / "post_run_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    risky = []
    for pid, bucket in (race_table.get("programs") or {}).items():
        if safe_int(bucket.get("starts")) >= 2 and safe_float(bucket.get("win_rate"), 1.0) < 0.75:
            risky.append({"program_id": pid, "win_rate": bucket.get("win_rate"), "starts": bucket.get("starts"), "avg_rank": bucket.get("avg_rank")})
    risky.sort(key=lambda r: (safe_float(r.get("win_rate"), 1.0), -safe_int(r.get("starts"))))
    payload = {
        "version": AI_TRAINER_VERSION,
        "generated_at": now_iso(),
        "training_reason": run_payload.get("reason"),
        "records": run_payload.get("records") or {},
        "top_risky_races": risky[:10],
        "suggested_config_tuning": tuning.get("suggestions") or [],
        "summary": "Local AI advisor updated analytics tables, learned scoring models, and reversible policy hints.",
    }
    _atomic_write_json(report_dir / "latest_post_run_report.json", payload)
    md_lines = [
        "# Pre Icarus AI Advisor Report",
        "",
        f"Generated: {payload['generated_at']}",
        f"Reason: {payload.get('training_reason') or 'manual'}",
        "",
        "## Risky Races",
    ]
    if risky:
        for row in risky[:10]:
            md_lines.append(f"- Program {row['program_id']}: win rate {round(safe_float(row.get('win_rate')) * 100)}%, starts {row.get('starts')}, avg rank {row.get('avg_rank')}")
    else:
        md_lines.append("- No risky race patterns with enough samples yet.")
    md_lines.extend(["", "## Suggested Config Tuning"])
    for sug in payload["suggested_config_tuning"]:
        md_lines.append(f"- {sug.get('setting')}: {sug.get('suggested_delta')} — {sug.get('reason')}")
    (report_dir / "latest_post_run_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return payload


def train_once(base_dir: Any, reason: str = "manual", rebuild_stats: bool = True) -> Dict[str, Any]:
    """Build local analytics/model artifacts from current AI JSONL datasets."""
    with _LOCK:
        root = ai_root(base_dir)
        root.mkdir(parents=True, exist_ok=True)
        cfg = load_auto_config(base_dir)
        paths = _dataset_paths(root)
        turn_rows = _read_jsonl(paths["turn_decisions"], limit=300000)
        summaries = _read_jsonl(paths["career_summaries"], limit=50000)
        if rebuild_stats:
            try:
                rebuild_advisor_stats(root)
            except Exception:
                pass
        runtime_outcomes = _read_runtime_race_outcomes(root)
        events_seen = _load_events_seen(root)
        item_table = build_item_effectiveness_table(turn_rows)
        event_table = build_event_outcome_table(turn_rows, events_seen=events_seen)
        race_table = build_race_outcome_table(turn_rows, runtime_outcomes=runtime_outcomes)
        health = _data_health(turn_rows, summaries, item_table=item_table, event_table=event_table)
        if not health.get("safe_for_live_policy", True) and cfg.get("enable_live_policy_assistance", True):
            cfg["enable_live_policy_assistance"] = False
            cfg["auto_disabled_reason"] = "AI data health check failed: race rows exist without extracted race results."
            cfg["updated_at"] = now_iso()
            _atomic_write_json(auto_config_path(base_dir), cfg)
        min_samples = safe_int(cfg.get("min_samples_for_model"), 2)
        race_model = build_race_risk_model(race_table, min_samples=min_samples)
        item_model = build_item_value_model(item_table, min_samples=min_samples)
        event_model = build_event_value_model(event_table, min_samples=min_samples)
        policy = build_policy_adjustments(race_model, item_model, event_model, cfg)
        tuning = build_suggested_config_tuning(turn_rows, race_table, cfg)
        shadow = build_shadow_policy_report(turn_rows, policy) if cfg.get("enable_shadow_mode", True) else {}
        backtest = build_backtest_report(turn_rows, race_model, tuning) if cfg.get("enable_backtesting", True) else {}
        epithet_conf = build_epithet_confidence(turn_rows, summaries)
        preset_conf = build_preset_trainee_confidence(summaries, turn_rows)
        style_payload = style_adaptation.train_from_experiences(base_dir, cfg)
        dashboard = build_ai_dashboard_payload(root, turn_rows, summaries, race_table, item_table, event_table, race_model, item_model, event_model, tuning, shadow, backtest, epithet_conf, preset_conf, style_payload, health, policy)
        prompt_manifest = build_llm_prompt_pack(root, turn_rows, tuning) if cfg.get("generate_synthetic_prompts", True) else {"prompt_count": 0}
        records = {"turn_decisions": len(turn_rows), "career_summaries": len(summaries)}
        payload = {
            "version": AI_TRAINER_VERSION,
            "trained_at": now_iso(),
            "reason": reason,
            "records": records,
            "auto_config": cfg,
            "model_files": MODEL_FILES,
            "llm_prompt_pack": prompt_manifest,
            "live_policy_enabled": bool(policy.get("enabled")),
            "live_policy_recommendation": live_policy_recommendation(
                cfg,
                health,
                policy,
                records={"turn_decisions": len(turn_rows), "career_summaries": len(summaries)},
                confidence=dashboard.get("confidence"),
                shadow=shadow,
            ),
            "dataset_ready": len(turn_rows) >= safe_int(cfg.get("min_turn_records"), 10) and bool(health.get("safe_for_live_policy", True)),
            "data_health": health,
            "dashboard": {"confidence": dashboard.get("confidence"), "warnings": dashboard.get("warnings", [])[:4]},
            "shadow_mode": {"evaluated_races": shadow.get("evaluated_races", 0), "precision": shadow.get("precision", 0)},
            "backtest": {"capture_rate": backtest.get("capture_rate", 0), "risk_warnings": backtest.get("risk_warnings", 0)},
            "style_adaptation": {
                "mode": (style_payload.get("report") or {}).get("mode"),
                "completed_experiences": (style_payload.get("report") or {}).get("completed_experiences", 0),
                "style_change_outcomes": (style_payload.get("report") or {}).get("style_change_outcomes", 0),
                "auto_apply_unlocked": (style_payload.get("report") or {}).get("auto_apply_unlocked", False),
                "recommendation": (style_payload.get("report") or {}).get("recommendation", ""),
            },
        }
        _atomic_write_json(root / MODEL_FILES["race_outcome_table"], race_table)
        _atomic_write_json(root / MODEL_FILES["item_effectiveness_table"], item_table)
        _atomic_write_json(root / MODEL_FILES["event_outcome_table"], event_table)
        _atomic_write_json(root / MODEL_FILES["race_risk_model"], race_model)
        _atomic_write_json(root / MODEL_FILES["item_value_model"], item_model)
        _atomic_write_json(root / MODEL_FILES["event_value_model"], event_model)
        _atomic_write_json(root / MODEL_FILES["policy_adjustments"], policy)
        _atomic_write_json(root / MODEL_FILES["suggested_config_tuning"], tuning)
        _atomic_write_json(root / MODEL_FILES["shadow_policy_report"], shadow)
        _atomic_write_json(root / MODEL_FILES["backtest_report"], backtest)
        _atomic_write_json(root / MODEL_FILES["epithet_confidence"], epithet_conf)
        _atomic_write_json(root / MODEL_FILES["preset_trainee_confidence"], preset_conf)
        _atomic_write_json(root / MODEL_FILES["ai_dashboard"], dashboard)
        report = build_post_run_report(root, {"reason": reason, "records": records}, race_table, tuning) if cfg.get("generate_post_run_report", True) else {}
        payload["post_run_report"] = {"path": str(root / "post_run_reports" / "latest_post_run_report.json"), "summary": report.get("summary")}
        _atomic_write_json(root / "ai_data_health.json", health)
        _atomic_write_json(root / MODEL_FILES["latest_training_run"], payload)
        state = _read_json(root / MODEL_FILES["auto_state"], {}) if isinstance(_read_json(root / MODEL_FILES["auto_state"], {}), dict) else {}
        state.update({"last_train_at": payload["trained_at"], "last_reason": reason, "last_records": records, "last_error": ""})
        _atomic_write_json(root / MODEL_FILES["auto_state"], state)
        _BACKGROUND["last_train_at"] = payload["trained_at"]
        _BACKGROUND["last_error"] = ""
        return {"success": True, **payload}


def trainer_status(base_dir: Any) -> Dict[str, Any]:
    root = ai_root(base_dir)
    cfg = load_auto_config(base_dir)
    latest = _read_json(root / MODEL_FILES["latest_training_run"], {})
    auto_state = _read_json(root / MODEL_FILES["auto_state"], {})
    policy = _read_json(root / MODEL_FILES["policy_adjustments"], {})
    health = _read_json(root / "ai_data_health.json", {})
    return {
        "success": True,
        "ai_root": str(root),
        "auto_config": cfg,
        "background": {k: (bool(v) if k == "started" else str(v) if k == "thread" else v) for k, v in _BACKGROUND.items() if k != "thread"},
        "latest_training_run": latest,
        "auto_state": auto_state,
        "data_health": health,
        "style_adaptation": style_adaptation.latest_payload(base_dir),
        "live_policy": {
            "enabled": bool(policy.get("enabled")) and bool(cfg.get("enable_live_policy_assistance", True)),
            "requested_enabled": bool(cfg.get("enable_live_policy_assistance", False)),
            "race_adjustments": len(policy.get("races") or {}),
            "item_adjustments": len(policy.get("items") or {}),
            "event_adjustments": len(policy.get("events") or {}),
            "confidence_threshold": policy.get("confidence_threshold", cfg.get("confidence_threshold")),
            "recommendation": live_policy_recommendation(
                cfg,
                health,
                policy,
                records=((latest or {}).get("records") if isinstance(latest, dict) else {}),
                confidence=(((latest or {}).get("dashboard") or {}).get("confidence") if isinstance(latest, dict) else None),
                shadow=((latest or {}).get("shadow_mode") if isinstance(latest, dict) else None),
            ),
        },
        "dataset_status": dataset_status(base_dir),
    }


def _careers_since_train(root: Path) -> int:
    state = _read_json(root / MODEL_FILES["auto_state"], {})
    last_count = safe_int(state.get("last_career_summary_rows"), 0)
    current = 0
    path = root / DATASET_FILES["career_summaries"]
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as fh:
                current = sum(1 for _ in fh)
        except Exception:
            current = last_count
    return max(0, current - last_count)


def _mark_career_count(root: Path) -> None:
    state = _read_json(root / MODEL_FILES["auto_state"], {})
    path = root / DATASET_FILES["career_summaries"]
    count = 0
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as fh:
                count = sum(1 for _ in fh)
        except Exception:
            count = 0
    if isinstance(state, dict):
        state["last_career_summary_rows"] = count
        _atomic_write_json(root / MODEL_FILES["auto_state"], state)


def after_career_export(output_dir: Any, manifest: Optional[Mapping[str, Any]] = None, build_version: str = "") -> Dict[str, Any]:
    """Schedule automatic local training after a career report export.

    This is deliberately non-blocking for the runner: the actual model/table build
    runs in a daemon thread when enabled.
    """
    out = Path(output_dir)
    runtime = out.parent if out.name == "bot_logs" else out
    root = runtime / "ai"
    cfg = load_auto_config(runtime)
    if not cfg.get("enabled", True):
        return {"scheduled": False, "detail": "auto training disabled"}
    threshold = max(1, safe_int(cfg.get("train_after_completed_careers"), 1))
    due = _careers_since_train(root) >= threshold
    if not due and threshold > 1:
        return {"scheduled": False, "detail": "waiting for more completed careers"}

    def _worker() -> None:
        try:
            train_once(runtime, reason="career_complete", rebuild_stats=True)
            _mark_career_count(root)
        except Exception as exc:
            _BACKGROUND["last_error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=_worker, name="SweepyAiPostCareerTrainer", daemon=True)
    thread.start()
    return {"scheduled": True, "reason": "career_complete"}


def start_background_trainer(base_dir: Any, runner_active: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
    """Start a lightweight periodic trainer loop if it is not already running."""
    with _LOCK:
        if _BACKGROUND.get("started"):
            return {"success": True, "started": True, "detail": "already running"}
        _BACKGROUND["stop"] = False

        def _loop() -> None:
            while not _BACKGROUND.get("stop"):
                cfg = load_auto_config(base_dir)
                sleep_s = max(60, safe_int(cfg.get("interval_minutes"), 60) * 60)
                try:
                    if cfg.get("enabled", True):
                        active = bool(runner_active and runner_active())
                        if active and not cfg.get("train_while_runner_active", False):
                            _BACKGROUND["last_skip_reason"] = "runner active"
                        else:
                            train_once(base_dir, reason="timer", rebuild_stats=True)
                            _mark_career_count(ai_root(base_dir))
                    else:
                        _BACKGROUND["last_skip_reason"] = "auto training disabled"
                except Exception as exc:
                    _BACKGROUND["last_error"] = f"{type(exc).__name__}: {exc}"
                # Sleep in small chunks so tests/shutdown do not hang.
                for _ in range(max(1, int(sleep_s // 5))):
                    if _BACKGROUND.get("stop"):
                        break
                    time.sleep(5)

        thread = threading.Thread(target=_loop, name="SweepyAiAutoTrainer", daemon=True)
        _BACKGROUND["thread"] = thread
        _BACKGROUND["started"] = True
        thread.start()
        return {"success": True, "started": True}


def stop_background_trainer() -> None:
    _BACKGROUND["stop"] = True





def create_safe_debug_bundle(base_dir: Any) -> Path:
    """Create a share-safe AI diagnostics bundle without auth tokens or raw API logs."""
    root = ai_root(base_dir)
    out_dir = root / "safe_debug_bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"sweepymod-ai-safe-debug-{stamp}.zip"
    include_names = {
        "advisor_stats.json",
        "auto_training_config.json",
        "auto_training_state.json",
        "latest_export_manifest.json",
        "latest_training_run.json",
        "ai_data_health.json",
        "race_outcome_table.json",
        "race_risk_model.json",
        "item_effectiveness_table.json",
        "item_value_model.json",
        "event_outcome_table.json",
        "event_value_model.json",
        "policy_adjustments.json",
        "suggested_config_tuning.json",
        "shadow_policy_report.json",
        "backtest_report.json",
        "epithet_confidence.json",
        "preset_trainee_confidence.json",
        "ai_dashboard.json",
        "style_adaptation_model.json",
        "style_adaptation_report.json",
        "style_adaptation_backtest.json",
        "style_adaptation_shadow_report.json",
    }
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", "Safe Pre Icarus AI diagnostics bundle. Auth tokens and raw API logs are intentionally excluded.\n")
        for name in sorted(include_names):
            path = root / name
            if path.exists() and path.is_file():
                zf.write(path, f"ai/{name}")
        for name in ("career_summaries.jsonl", "turn_decisions.jsonl", "style_adaptation_experiences.jsonl"):
            path = root / name
            if path.exists():
                # Include only tails to avoid sharing a massive raw dataset.
                rows = _read_jsonl(path, limit=500 if name in {"turn_decisions.jsonl", "style_adaptation_experiences.jsonl"} else 200)
                text = "".join(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n" for row in rows)
                zf.writestr(f"ai/{name}.tail", text)
        report_md = root / "post_run_reports" / "latest_post_run_report.md"
        if report_md.exists():
            zf.write(report_md, "ai/post_run_reports/latest_post_run_report.md")
    return out



def latest_dashboard(base_dir: Any) -> Dict[str, Any]:
    root = ai_root(base_dir)
    payload = _read_json(root / MODEL_FILES["ai_dashboard"], {})
    if not isinstance(payload, dict) or not payload:
        status = trainer_status(base_dir)
        return {
            "success": False,
            "detail": "AI dashboard has not been generated yet. Click Train Now or wait for auto-training.",
            "auto_training": status,
            "local_llm": local_llm.dashboard_summary(base_dir),
        }
    payload["success"] = True
    return payload


def latest_style_adaptation(base_dir: Any) -> Dict[str, Any]:
    return style_adaptation.latest_payload(base_dir)


def latest_shadow_report(base_dir: Any) -> Dict[str, Any]:
    payload = _read_json(ai_root(base_dir) / MODEL_FILES["shadow_policy_report"], {})
    if isinstance(payload, dict) and payload:
        payload["success"] = True
        return payload
    return {"success": False, "detail": "No shadow-mode report has been generated yet."}


def latest_backtest_report(base_dir: Any) -> Dict[str, Any]:
    payload = _read_json(ai_root(base_dir) / MODEL_FILES["backtest_report"], {})
    if isinstance(payload, dict) and payload:
        payload["success"] = True
        return payload
    return {"success": False, "detail": "No backtest report has been generated yet."}


def latest_config_suggestions(base_dir: Any) -> Dict[str, Any]:
    payload = _read_json(ai_root(base_dir) / MODEL_FILES["suggested_config_tuning"], {})
    if isinstance(payload, dict) and payload:
        payload["success"] = True
        return payload
    return {"success": False, "detail": "No config suggestions have been generated yet."}

def load_policy_adjustments(base_dir: Any) -> Dict[str, Any]:
    payload = _read_json(ai_root(base_dir) / MODEL_FILES["policy_adjustments"], {})
    return payload if isinstance(payload, dict) else {}


def race_policy_adjustment(base_dir: Any, program_id: Any, threshold: Optional[float] = None,
                           _cfg: Optional[Mapping[str, Any]] = None,
                           _policy: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    # _cfg/_policy let hot callers (Smart Race Solver) load these files once and
    # reuse them across every candidate row instead of re-reading per program_id.
    cfg = _cfg if _cfg is not None else load_auto_config(base_dir)
    if not cfg.get("enable_live_policy_assistance", True):
        return {"adjustment": 0.0, "confidence": 0.0, "enabled": False, "reason": "live policy assistance disabled"}
    policy = _policy if _policy is not None else load_policy_adjustments(base_dir)
    if not policy.get("enabled", True):
        return {"adjustment": 0.0, "confidence": 0.0, "enabled": False, "reason": "policy model disabled"}
    row = (policy.get("races") or {}).get(str(safe_int(program_id))) or {}
    conf = safe_float(row.get("confidence"), 0.0)
    gate = safe_float(threshold if threshold is not None else policy.get("confidence_threshold", cfg.get("confidence_threshold", MIN_CONFIDENCE_DEFAULT)), MIN_CONFIDENCE_DEFAULT)
    if conf < gate:
        return {"adjustment": 0.0, "confidence": conf, "enabled": True, "reason": "confidence below live-policy threshold"}
    max_abs = safe_float(policy.get("max_abs_live_adjustment", cfg.get("max_abs_live_adjustment", 25.0)), 25.0)
    adjustment = max(-max_abs, min(max_abs, safe_float(row.get("adjustment"), 0.0)))
    return {
        "adjustment": round(adjustment, 4),
        "confidence": conf,
        "enabled": True,
        "samples": row.get("samples"),
        "reason": row.get("reason") or "local learned policy adjustment",
        "clean_win_rate": row.get("clean_win_rate"),
        "clock_dependency_rate": row.get("clock_dependency_rate"),
        "clock_dependency_penalty": row.get("clock_dependency_penalty"),
    }
