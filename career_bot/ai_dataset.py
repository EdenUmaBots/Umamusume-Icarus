"""AI-ready data exports for Pre Icarus.

The live runner remains deterministic.  This module converts finished career
reports into safe, append-only learning datasets that can be consumed by local
analytics, reward models, or offline LLM tooling.

Design goals:
- never block or break an active career because telemetry failed;
- keep records JSONL so partially-written data is easy to recover;
- store only gameplay state/action/outcome fields, not account credentials;
- make every record self-describing with schema/build metadata.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

SCHEMA_VERSION = 1
AI_DATASET_VERSION = "SweepyCL AI Dataset v2"
DATASET_FILES = {
    "turn_decisions": "turn_decisions.jsonl",
    "career_summaries": "career_summaries.jsonl",
    "failed_runs": "failed_runs.jsonl",
    "synthetic_scenarios": "synthetic_scenarios.jsonl",
}


def runtime_output_root(base_dir: Any) -> Path:
    override = os.environ.get("UMA_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(base_dir).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate / "uma_runtime"
    return base.parent / "uma_runtime"


def ai_root_from_output_dir(output_dir: Any) -> Path:
    """Return the AI export directory for a career report output directory.

    Career reports are normally written into ``uma_runtime/bot_logs``.  Keeping
    AI exports one level up under ``uma_runtime/ai`` avoids mixing training data
    with human-facing logs while preserving portability.
    """
    out = Path(output_dir)
    if out.name == "bot_logs":
        return out.parent / "ai"
    return out / "ai"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except Exception:
        return int(default)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return float(default)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_default(obj: Any) -> str:
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)


# P5: roll AI dataset jsonl files past this size into timestamped archives so the
# live file stays small (fast to read/count). Archives are KEPT INDEFINITELY (no
# cap) and stay readable by the trainer via _read_jsonl's archive globbing.
JSONL_ROTATE_BYTES = 50 * 1024 * 1024
JSONL_ARCHIVE_MARKER = ".archive-"


def _rotate_if_large(path: Path) -> None:
    """Rename an oversized dataset file to ``<stem>.archive-<ts><suffix>``.

    Best-effort: a failure here must never block the append that follows.
    """
    try:
        if not path.exists() or path.stat().st_size < JSONL_ROTATE_BYTES:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = path.with_name(f"{path.stem}{JSONL_ARCHIVE_MARKER}{stamp}{path.suffix}")
        n = 1
        while archive.exists():  # two rotations in the same second
            archive = path.with_name(f"{path.stem}{JSONL_ARCHIVE_MARKER}{stamp}_{n}{path.suffix}")
            n += 1
        path.replace(archive)
    except Exception:
        pass


def _archive_paths(path: Path):
    """All rotated archives for a dataset path, oldest-first by name."""
    try:
        return sorted(path.parent.glob(f"{path.stem}{JSONL_ARCHIVE_MARKER}*{path.suffix}"))
    except Exception:
        return []


def _append_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_large(path)
    count = 0
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")
            count += 1
    return count


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


def _stats_from_decision_report(turn: Mapping[str, Any]) -> Dict[str, Any]:
    report = turn.get("decision_report") or {}
    state = report.get("state") or {}
    return {
        "speed": safe_int(state.get("speed")),
        "stamina": safe_int(state.get("stamina")),
        "power": safe_int(state.get("power")),
        "guts": safe_int(state.get("guts")),
        "wit": safe_int(state.get("wit")),
        "skill_point": safe_int(state.get("skill_point")),
        "hp": safe_int(state.get("hp")),
        "max_hp": safe_int(state.get("max_hp"), 100),
        "mood": safe_int(state.get("mood")),
        "fans": safe_int(state.get("fans")),
    }


def _action_from_turn(turn: Mapping[str, Any]) -> Dict[str, Any]:
    report = turn.get("decision_report") or {}
    payload = dict(report.get("payload") or turn.get("current_command") or {})
    action = str(turn.get("selected_action") or report.get("action") or turn.get("current_action_taken") or "").strip()
    if not action:
        action = "unknown"
    return {
        "type": action,
        "reason": turn.get("decision_reason") or report.get("reason") or "",
        "payload": payload,
        "program_id": payload.get("program_id"),
        "command_type": payload.get("command_type"),
        "command_id": payload.get("command_id"),
        "command_group_id": payload.get("command_group_id"),
    }





def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _race_result_from_api_response(call: Mapping[str, Any], turn_number: int, program_id: Any = None) -> Optional[Dict[str, Any]]:
    """Extract a race result from a logged ``single_mode_free/race_end`` response.

    v5.33 exported AI rows from high-level report fields only, but real Pre Icarus
    logs often keep the authoritative result inside ``turn.api_calls`` as the
    response body for ``single_mode_free/race_end``.  This parser intentionally
    reads only gameplay fields and does not copy request/session metadata into AI
    datasets.
    """
    if str(call.get("direction") or "").upper() != "RES":
        return None
    if "race_end" not in str(call.get("endpoint") or ""):
        return None
    envelope = _mapping(call.get("data"))
    data = _mapping(envelope.get("data"))
    reward = _mapping(data.get("race_reward_info"))
    if not reward:
        return None
    chara = _mapping(data.get("chara_info"))
    race_history = data.get("race_history") if isinstance(data.get("race_history"), list) else []
    hist = {}
    for row in race_history:
        if not isinstance(row, Mapping):
            continue
        if safe_int(row.get("turn")) == safe_int(turn_number):
            hist = dict(row)
    inferred_program = program_id or chara.get("race_program_id") or hist.get("program_id")
    if program_id not in (None, "", 0, "0") and inferred_program not in (None, "", 0, "0"):
        # If the action payload and API response disagree, keep the action ID but
        # still surface the actual response as source data for diagnostics.
        inferred_program = program_id
    rank = safe_int(reward.get("result_rank") or hist.get("result_rank"), 99)
    return {
        "turn": safe_int(turn_number),
        "program_id": safe_int(inferred_program),
        "rank": rank,
        "result_rank": rank,
        "fans_gained": safe_int(reward.get("gained_fans")),
        "fans_after": safe_int(chara.get("fans")),
        "weather": hist.get("weather"),
        "ground_condition": hist.get("ground_condition"),
        "running_style": hist.get("running_style") or chara.get("race_running_style"),
        "source": "api_calls:single_mode_free/race_end",
    }


def _race_result_from_api_calls(turn: Mapping[str, Any], program_id: Any = None) -> Optional[Dict[str, Any]]:
    for call in turn.get("api_calls") or []:
        if not isinstance(call, Mapping):
            continue
        row = _race_result_from_api_response(call, safe_int(turn.get("turn")), program_id=program_id)
        if row:
            return row
    return None


def _clock_retry_from_turn(turn: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract per-turn clock retry telemetry from events or race results.

    Newer reports store a compact ``race_clock_summary`` event.  This fallback
    also recognizes legacy ``race_clock``/``race_rank_retry`` events when they
    are present, but never invents a clock use when the log does not prove it.
    """
    for event in turn.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        if str(event.get("event") or "") == "race_clock_summary":
            out = dict(event)
            out.pop("event", None)
            return out
    # Lightweight legacy fallback from event text.
    retry_events = []
    initial_rank = None
    final_rank = None
    for event in turn.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        name = str(event.get("event") or "")
        detail = str(event.get("detail") or "")
        if name == "race_clock":
            retry_events.append({"attempt": len(retry_events) + 1, "detail": detail})
        elif name == "race_rank":
            import re
            m = re.search(r"rank\s+(\d+)", detail)
            if m:
                initial_rank = safe_int(m.group(1), 99)
        elif name == "race_rank_retry":
            import re
            m = re.search(r"rank\s+(\d+)", detail)
            if m:
                final_rank = safe_int(m.group(1), 99)
    if retry_events:
        return {
            "user_enabled": True,
            "enabled": True,
            "attempts": len(retry_events),
            "used": len(retry_events),
            "initial_rank": initial_rank or 99,
            "final_rank": final_rank or initial_rank or 99,
            "won_before_retry": (initial_rank or 99) == 1,
            "won_after_retry": (initial_rank or 99) > 1 and (final_rank or 99) == 1,
            "retry_events": retry_events,
            "source": "turn:events",
        }
    return {}


def _clock_policy_from_turn(report: Mapping[str, Any], turn: Mapping[str, Any]) -> Dict[str, Any]:
    decision = turn.get("decision_report") or {}
    race_context = decision.get("race_context") if isinstance(decision.get("race_context"), Mapping) else {}
    policy = race_context.get("clock_policy") if isinstance(race_context.get("clock_policy"), Mapping) else None
    if policy:
        return dict(policy)
    runtime = report.get("runtime_settings") if isinstance(report.get("runtime_settings"), Mapping) else {}
    policy = runtime.get("clock_retry_policy") if isinstance(runtime.get("clock_retry_policy"), Mapping) else None
    if policy:
        return dict(policy)
    burn = bool(runtime.get("burn_clocks"))
    return {"user_enabled": burn, "enabled": burn, "source": "report_runtime_settings"}


def _api_context_from_turn(turn: Mapping[str, Any]) -> Dict[str, Any]:
    """Collect compact useful direct-API context without copying whole payloads."""
    latest = {}
    for call in turn.get("api_calls") or []:
        if not isinstance(call, Mapping) or str(call.get("direction") or "").upper() != "RES":
            continue
        data = _mapping(_mapping(call.get("data")).get("data"))
        if data:
            latest = data
    home = _mapping(latest.get("home_info"))
    free = _mapping(latest.get("free_data_set"))
    race_conditions = latest.get("race_condition_array") if isinstance(latest.get("race_condition_array"), list) else []
    return {
        "available_race_program_ids": [safe_int(row.get("program_id")) for row in race_conditions if isinstance(row, Mapping) and safe_int(row.get("program_id"))],
        "available_race_count": len([row for row in race_conditions if isinstance(row, Mapping) and safe_int(row.get("program_id"))]),
        "available_continue_num": safe_int(home.get("available_continue_num")),
        "available_free_continue_num": safe_int(home.get("available_free_continue_num")),
        "coin_num": safe_int(free.get("coin_num") if free.get("coin_num") is not None else free.get("gained_coin_num")),
        "unchecked_event_count": len(latest.get("unchecked_event_array") or []) if isinstance(latest.get("unchecked_event_array"), list) else 0,
    }


def _all_race_results_from_report(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Return every race result that can be safely reconstructed from a report."""
    seen = set()
    out: List[Dict[str, Any]] = []
    for row in list(report.get("race_results") or (report.get("runner_status") or {}).get("race_results") or []):
        if not isinstance(row, Mapping):
            continue
        result = dict(row)
        result.setdefault("rank", result.get("result_rank"))
        key = (safe_int(result.get("turn")), safe_int(result.get("program_id")), safe_int(result.get("rank") or result.get("result_rank"), 99))
        if key not in seen:
            seen.add(key)
            out.append(result)
    for turn in report.get("turns") or []:
        if not isinstance(turn, Mapping):
            continue
        action = _action_from_turn(turn)
        result = _race_result_from_api_calls(turn, program_id=action.get("program_id"))
        if not result:
            continue
        key = (safe_int(result.get("turn")), safe_int(result.get("program_id")), safe_int(result.get("rank") or result.get("result_rank"), 99))
        if key not in seen:
            seen.add(key)
            out.append(result)
    out.sort(key=lambda r: (safe_int(r.get("turn")), safe_int(r.get("program_id"))))
    return out


def _stats_from_turn_payload(turn: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract a compact final/turn stat snapshot from common report shapes."""
    # Prefer the latest API response chara_info when present because it is the
    # post-action server truth.  The turn-level ``stats`` block can represent the
    # pre-action snapshot.
    for call in reversed(turn.get("api_calls") or []):
        if not isinstance(call, Mapping) or str(call.get("direction") or "").upper() != "RES":
            continue
        data = _mapping(_mapping(call.get("data")).get("data"))
        chara = _mapping(data.get("chara_info"))
        if chara:
            return {
                "speed": safe_int(chara.get("speed")),
                "stamina": safe_int(chara.get("stamina")),
                "power": safe_int(chara.get("power")),
                "guts": safe_int(chara.get("guts")),
                "wit": safe_int(chara.get("wiz")),
                "skill_point": safe_int(chara.get("skill_point")),
                "hp": safe_int(chara.get("vital")),
                "max_hp": safe_int(chara.get("max_vital"), 100),
                "mood": safe_int(chara.get("motivation")),
                "fans": safe_int(chara.get("fans")),
            }
    stats = _mapping(turn.get("stats"))
    if stats:
        return {
            "speed": safe_int(stats.get("speed")),
            "stamina": safe_int(stats.get("stamina")),
            "power": safe_int(stats.get("power")),
            "guts": safe_int(stats.get("guts")),
            "wit": safe_int(stats.get("wit") or stats.get("wiz")),
            "skill_point": safe_int(turn.get("skill_point") or stats.get("skill_point")),
            "hp": safe_int(stats.get("hp") or stats.get("vital")),
            "mood": safe_int(turn.get("motivation") or stats.get("mood") or stats.get("motivation")),
            "fans": safe_int(stats.get("fans")),
        }
    report_stats = _stats_from_decision_report(turn)
    if any(safe_int(report_stats.get(k)) for k in ("speed", "stamina", "power", "guts", "wit", "fans")):
        return report_stats
    return {}

def _race_result_for_turn(report: Mapping[str, Any], turn_number: int, program_id: Any = None) -> Optional[Dict[str, Any]]:
    status = report.get("runner_status") or report.get("status_snapshot") or {}
    race_results = list(report.get("race_results") or status.get("race_results") or [])
    # Some builds store race results in final status rather than the report root.
    for row in race_results:
        if safe_int(row.get("turn")) != safe_int(turn_number):
            continue
        if program_id not in (None, "", 0) and safe_int(row.get("program_id")) != safe_int(program_id):
            continue
        out = dict(row)
        out.setdefault("rank", out.get("result_rank"))
        out.setdefault("source", "report:race_results")
        if not out.get("clock_retry"):
            # Match the report turn, if available, to attach retry metadata.
            for turn in report.get("turns") or []:
                if safe_int(turn.get("turn")) == safe_int(turn_number):
                    retry = _clock_retry_from_turn(turn)
                    if retry:
                        out["clock_retry"] = retry
                    break
        return out
    # Fall back to events attached to the turn.
    turns = report.get("turns") or []
    matching_turn: Optional[Mapping[str, Any]] = None
    for turn in turns:
        if safe_int(turn.get("turn")) != safe_int(turn_number):
            continue
        matching_turn = turn
        for event in turn.get("events") or []:
            if str(event.get("event") or "") in {"race_result", "race_rank"}:
                out = dict(event)
                out.setdefault("rank", out.get("result_rank"))
                out.setdefault("source", "turn:events")
                return out
    # v5.34: real Pre Icarus logs keep the authoritative result in race_end RES.
    if matching_turn:
        from_api = _race_result_from_api_calls(matching_turn, program_id=program_id)
        if from_api:
            retry = _clock_retry_from_turn(matching_turn)
            if retry:
                from_api["clock_retry"] = retry
                from_api.setdefault("initial_rank", retry.get("initial_rank"))
                from_api.setdefault("final_rank", retry.get("final_rank"))
                from_api.setdefault("clocks_used", retry.get("used"))
                from_api.setdefault("won_after_clock", retry.get("won_after_retry"))
                from_api.setdefault("won_without_clock", retry.get("won_before_retry"))
            return from_api
    return None

def _turn_reward(turn: Mapping[str, Any], next_turn: Optional[Mapping[str, Any]], report: Mapping[str, Any]) -> float:
    """A conservative first-pass reward signal for offline learning.

    This is intentionally transparent and hand-tuned.  It is not meant to be the
    final policy objective; it is a starting reward model that can be inspected,
    graphed, and replaced later.
    """
    stats = _stats_from_decision_report(turn)
    next_stats = _stats_from_decision_report(next_turn or {}) if next_turn else {}
    action = _action_from_turn(turn)
    reward = 0.0

    # Local stat/fan progress.
    for key in ("speed", "stamina", "power", "guts", "wit"):
        reward += max(0, safe_int(next_stats.get(key)) - safe_int(stats.get(key))) * 0.025
    reward += max(0, safe_int(next_stats.get("skill_point")) - safe_int(stats.get("skill_point"))) * 0.015
    reward += max(0, safe_int(next_stats.get("fans")) - safe_int(stats.get("fans"))) / 10000.0

    if action["type"] == "race":
        result = _race_result_for_turn(report, safe_int(turn.get("turn")), action.get("program_id"))
        if result:
            rank = safe_int(result.get("rank") or result.get("result_rank"), 99)
            clock_retry = result.get("clock_retry") if isinstance(result.get("clock_retry"), Mapping) else {}
            clocks_used = safe_int(result.get("clocks_used") or clock_retry.get("used"))
            won_after_clock = bool(result.get("won_after_clock") or clock_retry.get("won_after_retry"))
            reward += 8.0 if rank == 1 else -12.0 - min(8.0, max(0, rank - 2) * 2.0)
            if clocks_used:
                reward -= min(8.0, clocks_used * 2.0)
            if won_after_clock:
                # A clock-rescued win is useful but riskier than a clean win.
                reward -= 3.0
        else:
            # Unresolved planned race: leave neutral-ish, but note the lack of outcome.
            reward -= 0.5
    elif action["type"] == "train":
        reward += 1.0
    elif action["type"] in {"rest", "recreate", "recover"}:
        # Rest can be correct, but it should have to earn its keep via next state.
        reward -= 1.0
    elif action["type"] == "finish":
        reward += 20.0 if str(report.get("status")) == "finished" else -20.0

    return round(reward, 4)




def _style_adaptation_from_turn(turn: Mapping[str, Any]) -> Dict[str, Any]:
    events = [event for event in (turn.get("events") or []) if isinstance(event, Mapping) and str(event.get("event") or "").startswith("style_adaptation_")]
    out: Dict[str, Any] = {"events": events}
    for event in events:
        name = str(event.get("event") or "")
        if name == "style_adaptation_decision":
            out["decision"] = {k: v for k, v in event.items() if k != "event"}
        elif name == "style_adaptation_observation":
            out["observation"] = {k: v for k, v in event.items() if k != "event"}
        elif name == "style_adaptation_outcome":
            out["outcome"] = {k: v for k, v in event.items() if k != "event"}
    return out

def turn_decision_records(report: Mapping[str, Any], build_version: str = "") -> List[Dict[str, Any]]:
    turns = sorted((report.get("turns") or []), key=lambda row: safe_int((row or {}).get("turn")))
    rows: List[Dict[str, Any]] = []
    run_id = str(report.get("run_id") or report.get("started_at") or "").replace(" ", "_")
    for idx, turn in enumerate(turns):
        if not isinstance(turn, Mapping):
            continue
        action = _action_from_turn(turn)
        if action["type"] == "unknown" and not turn.get("decision_report"):
            continue
        next_turn = turns[idx + 1] if idx + 1 < len(turns) else None
        turn_number = safe_int(turn.get("turn"))
        race_result = _race_result_for_turn(report, turn_number, action.get("program_id"))
        clock_retry = (race_result or {}).get("clock_retry") if isinstance(race_result, Mapping) else {}
        clock_policy = _clock_policy_from_turn(report, turn)
        api_context = _api_context_from_turn(turn)
        style_adaptation = _style_adaptation_from_turn(turn)
        record = {
            "schema_version": SCHEMA_VERSION,
            "dataset": "turn_decisions",
            "build_version": build_version,
            "run_id": run_id,
            "preset_name": report.get("preset_name") or "",
            "scenario_id": safe_int(report.get("scenario_id")),
            "turn": turn_number,
            "state": _stats_from_decision_report(turn),
            "action": action,
            "outcome": {
                "reward": _turn_reward(turn, next_turn, report),
                "next_turn": safe_int((next_turn or {}).get("turn")) if next_turn else None,
                "race_result": race_result,
                "clock_retry": clock_retry or {},
                "clocks_used": safe_int((race_result or {}).get("clocks_used") or (clock_retry or {}).get("used")) if isinstance(race_result, Mapping) else 0,
                "won_after_clock": bool((race_result or {}).get("won_after_clock") or (clock_retry or {}).get("won_after_retry")) if isinstance(race_result, Mapping) else False,
                "won_without_clock": bool((race_result or {}).get("won_without_clock") or (clock_retry or {}).get("won_before_retry")) if isinstance(race_result, Mapping) else False,
                "style_adaptation": style_adaptation.get("outcome") or {},
            },
            "decision_report": turn.get("decision_report") or {},
            "candidate_context": {
                "training_candidates": (turn.get("decision_report") or {}).get("training_candidates") or [],
                "race_context": (turn.get("decision_report") or {}).get("race_context") or {},
            },
            "turn_metadata": {
                "events": list(turn.get("events") or []),
                "item_usage_attempts": list(turn.get("item_usage_attempts") or []),
                "item_buy_attempts": list(turn.get("item_buy_attempts") or []),
                "skill_buy_attempts": list(turn.get("skill_buy_attempts") or []),
                "event_choices": list((turn.get("decision_report") or {}).get("event_choices") or []),
                "clock_policy": clock_policy,
                "api_context": api_context,
                "style_adaptation": style_adaptation,
            },
        }
        rows.append(record)
    return rows


def career_summary_record(report: Mapping[str, Any], build_version: str = "") -> Dict[str, Any]:
    turns = report.get("turns") or []
    action_counts = Counter(_action_from_turn(turn).get("type") for turn in turns if isinstance(turn, Mapping))
    final_stats: Dict[str, Any] = {}
    status_snapshot = report.get("runner_status") or report.get("status_snapshot") or {}

    # final_chara is the dict produced by ``runner._compact_final_chara`` -- it
    # holds the headline fields (fans, rating, rank, card_id, title, aptitudes)
    # at the top level and a nested ``stats`` sub-dict.  v6.0 only pulled the
    # nested stats and looked for ``fans`` inside them, which is why the
    # summary always recorded ``final_fans: 0``.
    final_chara_sources = [
        report.get("final_chara") or {},
        status_snapshot.get("final_chara") or {},
        status_snapshot,
    ]

    for source in final_chara_sources:
        stats = (source or {}).get("stats") if isinstance(source, Mapping) else None
        if isinstance(stats, Mapping):
            final_stats = dict(stats)
            break
    if not final_stats and turns:
        for turn in reversed(turns):
            if isinstance(turn, Mapping):
                final_stats = _stats_from_turn_payload(turn)
                if final_stats:
                    break

    # Pull headline fields from the same final_chara cascade.  Each source
    # may be partial; first non-empty value wins.
    def _pick(field: str, default=None):
        for source in final_chara_sources:
            if not isinstance(source, Mapping):
                continue
            value = source.get(field)
            if value not in (None, "", 0):
                return value
        return default

    final_fans = safe_int(_pick("fans"))
    final_rating = _pick("rating")
    final_rank = _pick("rank")
    card_id = safe_int(_pick("card_id"))
    chara_title = _pick("title") or ""

    race_results = _all_race_results_from_report(report)
    wins = [row for row in race_results if safe_int(row.get("rank") or row.get("result_rank"), 99) == 1]
    clocked = [row for row in race_results if safe_int(row.get("clocks_used") or (_mapping(row.get("clock_retry")).get("used"))) > 0]
    clock_saved = [row for row in race_results if bool(row.get("won_after_clock") or _mapping(row.get("clock_retry")).get("won_after_retry"))]
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": "career_summaries",
        "build_version": build_version,
        "run_id": str(report.get("run_id") or report.get("started_at") or ""),
        "started_at": report.get("started_at"),
        "ended_at": report.get("ended_at"),
        "preset_name": report.get("preset_name") or "",
        "scenario_id": safe_int(report.get("scenario_id")),
        "status": report.get("status"),
        "final_turn": safe_int(report.get("final_turn")),
        "turn_count": len(turns),
        "action_counts": dict(action_counts),
        "final_stats": final_stats,
        "final_fans": final_fans,
        "final_rating": final_rating,
        "final_rank": final_rank,
        "card_id": card_id,
        "chara_title": chara_title,
        "race_results": race_results,
        "race_count": len(race_results),
        "race_wins": len(wins),
        "race_win_rate": round(len(wins) / max(1, len(race_results)), 4),
        "clock_retry_races": len(clocked),
        "clock_saved_wins": len(clock_saved),
        "clock_retry_rate": round(len(clocked) / max(1, len(race_results)), 4),
        "major_wins": [row for row in wins if str(row.get("grade") or "").upper() == "G1"],
        "rest_count": safe_int(action_counts.get("rest")),
        "recreation_count": safe_int(action_counts.get("recreate")),
        "error": report.get("error"),
    }

def _read_jsonl_tail(path: Path, limit: int = 2000) -> List[Dict[str, Any]]:
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


def _turn_phase(turn: int) -> str:
    """Career-turn bucket used by the hierarchical advisor.

    Boundaries match the existing ``turn_bands`` aggregation so the band
    semantics stay consistent across the v1 and v2 stats payloads.
    """
    if turn < 25:
        return "early"
    if turn < 49:
        return "classic"
    if turn < 73:
        return "senior"
    return "finale"


def _bump_program_bucket(bucket: Dict[str, Any], won: bool, reward: float) -> None:
    bucket["starts"] += 1
    bucket["reward_sum"] += reward
    if won:
        bucket["wins"] += 1


def _finalize_program_bucket(bucket: Dict[str, Any]) -> None:
    starts = max(1, bucket["starts"])
    bucket["win_rate"] = round(bucket["wins"] / starts, 4)
    bucket["avg_reward"] = round(bucket["reward_sum"] / starts, 4)
    bucket["reward_sum"] = round(bucket["reward_sum"], 4)


def rebuild_advisor_stats(ai_root: Path) -> Dict[str, Any]:
    """Build compact local statistics from JSONL datasets.

    Layout:
      - ``actions`` / ``turn_bands`` / ``race_programs`` -- v1-compatible
        flat aggregations keyed by action type, turn band, and program id.
      - ``race_programs_context`` (v2) -- hierarchical race-program
        aggregations at four levels of increasing specificity::

            by_program                       -> "<program_id>"
            by_program_scenario              -> "<pid>:<scenario_id>"
            by_program_scenario_preset       -> "<pid>:<sid>:<preset_name>"
            by_program_scenario_preset_phase -> "<pid>:<sid>:<preset>:<phase>"

        ``hierarchical_race_program_hint`` in ``ai_advisor`` walks these
        levels least-to-most-specific, letting a sparse leaf inherit its
        parent's posterior instead of producing an uninformative estimate.

    These statistics are intentionally simple enough to inspect in a text
    editor.  Later builds can train richer models from the same JSONL data.
    """
    turn_rows = _read_jsonl_tail(ai_root / DATASET_FILES["turn_decisions"], limit=100000)
    summaries = _read_jsonl_tail(ai_root / DATASET_FILES["career_summaries"], limit=20000)
    actions: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "reward_sum": 0.0, "avg_reward": 0.0})
    race_programs: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"starts": 0, "wins": 0, "reward_sum": 0.0, "avg_reward": 0.0})
    turn_bands: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "reward_sum": 0.0, "avg_reward": 0.0})

    # v2 hierarchical buckets, parallel to race_programs.
    by_program: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"starts": 0, "wins": 0, "reward_sum": 0.0})
    by_program_scenario: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"starts": 0, "wins": 0, "reward_sum": 0.0})
    by_program_scenario_preset: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"starts": 0, "wins": 0, "reward_sum": 0.0})
    by_program_scenario_preset_phase: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"starts": 0, "wins": 0, "reward_sum": 0.0})

    for row in turn_rows:
        action = str(((row.get("action") or {}).get("type") or "unknown")).lower()
        reward = safe_float(((row.get("outcome") or {}).get("reward")), 0.0)
        actions[action]["count"] += 1
        actions[action]["reward_sum"] += reward
        turn = safe_int(row.get("turn"))
        phase = _turn_phase(turn)
        turn_bands[phase]["count"] += 1
        turn_bands[phase]["reward_sum"] += reward

        pid = (row.get("action") or {}).get("program_id")
        if action != "race" or not pid:
            continue

        key = str(safe_int(pid))
        result = ((row.get("outcome") or {}).get("race_result") or {})
        rank = safe_int(result.get("rank") or result.get("result_rank"), 99)
        won = rank == 1

        # v1 flat bucket
        _bump_program_bucket(race_programs[key], won, reward)

        # v2 hierarchical buckets
        scenario_id = safe_int(row.get("scenario_id"))
        preset = str(row.get("preset_name") or "").strip() or "_unknown"

        _bump_program_bucket(by_program[key], won, reward)
        _bump_program_bucket(by_program_scenario[f"{key}:{scenario_id}"], won, reward)
        _bump_program_bucket(by_program_scenario_preset[f"{key}:{scenario_id}:{preset}"], won, reward)
        _bump_program_bucket(by_program_scenario_preset_phase[f"{key}:{scenario_id}:{preset}:{phase}"], won, reward)

    for bucket in actions.values():
        bucket["avg_reward"] = round(bucket["reward_sum"] / max(1, bucket["count"]), 4)
        bucket["reward_sum"] = round(bucket["reward_sum"], 4)
    for bucket in turn_bands.values():
        bucket["avg_reward"] = round(bucket["reward_sum"] / max(1, bucket["count"]), 4)
        bucket["reward_sum"] = round(bucket["reward_sum"], 4)
    for bucket in race_programs.values():
        _finalize_program_bucket(bucket)
    for collection in (by_program, by_program_scenario, by_program_scenario_preset, by_program_scenario_preset_phase):
        for bucket in collection.values():
            _finalize_program_bucket(bucket)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": AI_DATASET_VERSION,
        "updated_at": now_iso(),
        "records": {
            "turn_decisions": len(turn_rows),
            "career_summaries": len(summaries),
        },
        "actions": dict(actions),
        "turn_bands": dict(turn_bands),
        "race_programs": dict(race_programs),
        "race_programs_context": {
            "by_program": dict(by_program),
            "by_program_scenario": dict(by_program_scenario),
            "by_program_scenario_preset": dict(by_program_scenario_preset),
            "by_program_scenario_preset_phase": dict(by_program_scenario_preset_phase),
        },
    }
    _atomic_write_json(ai_root / "advisor_stats.json", payload)
    return payload


def synthetic_scenario_records(report: Mapping[str, Any], build_version: str = "") -> List[Dict[str, Any]]:
    """Generate small validated edge-case prompts for offline advisor training.

    These are not treated as real gameplay outcomes.  They are scenario prompts
    that can be fed to an LLM or reward-model labeling workflow to improve edge
    case coverage.
    """
    summary = career_summary_record(report, build_version=build_version)
    preset_name = summary.get("preset_name") or ""
    rows: List[Dict[str, Any]] = []
    templates = [
        {
            "case": "low_energy_high_value_race",
            "turn": 68,
            "state_overrides": {"hp": 28, "mood": 4},
            "question": "Race, train, rest, or use an energy item before a high-value Senior G1?",
        },
        {
            "case": "long_distance_low_stamina",
            "turn": 56,
            "state_overrides": {"stamina": 420, "hp": 75},
            "question": "Should a 3000m+ race be scheduled or should stamina be trained first?",
        },
        {
            "case": "forced_epithet_branch_at_risk",
            "turn": 66,
            "state_overrides": {"hp": 45, "mood": 3},
            "question": "How should the solver re-plan when a forced epithet branch is almost dead?",
        },
    ]
    for tpl in templates:
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "dataset": "synthetic_scenarios",
            "synthetic": True,
            "source": "template",
            "build_version": build_version,
            "run_id": summary.get("run_id"),
            "preset_name": preset_name,
            "case": tpl["case"],
            "turn": tpl["turn"],
            "state_overrides": tpl["state_overrides"],
            "question": tpl["question"],
            "validation": {
                "requires_real_calendar_check": True,
                "weight_hint": 0.2,
            },
        })
    return rows


def export_report_ai_datasets(report: Mapping[str, Any], output_dir: Any, build_version: str = "") -> Dict[str, Any]:
    """Export a finished career report into AI-ready JSONL datasets.

    Returns a manifest. Exceptions are allowed to bubble to the caller so they can
    be logged, but runner code should treat this as best-effort observability.
    """
    ai_root = ai_root_from_output_dir(output_dir)
    ai_root.mkdir(parents=True, exist_ok=True)
    turn_rows = turn_decision_records(report, build_version=build_version)
    summary = career_summary_record(report, build_version=build_version)
    synthetic_rows = synthetic_scenario_records(report, build_version=build_version)

    counts = {
        "turn_decisions": _append_jsonl(ai_root / DATASET_FILES["turn_decisions"], turn_rows),
        "career_summaries": _append_jsonl(ai_root / DATASET_FILES["career_summaries"], [summary]),
        "synthetic_scenarios": _append_jsonl(ai_root / DATASET_FILES["synthetic_scenarios"], synthetic_rows),
    }
    if str(summary.get("status") or "") != "finished":
        counts["failed_runs"] = _append_jsonl(ai_root / DATASET_FILES["failed_runs"], [summary])
    else:
        counts["failed_runs"] = 0

    stats = rebuild_advisor_stats(ai_root)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": AI_DATASET_VERSION,
        "exported_at": now_iso(),
        "ai_root": str(ai_root),
        "counts": counts,
        "advisor_stats_path": str(ai_root / "advisor_stats.json"),
        "records": stats.get("records", {}),
    }
    _atomic_write_json(ai_root / "latest_export_manifest.json", manifest)
    return manifest





def _read_jsonl_rows(path: Path, limit: int = 300000) -> List[Dict[str, Any]]:
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


def dataset_health(ai_root: Path) -> Dict[str, Any]:
    """Return safety/readiness checks for the AI training data."""
    turn_rows = _read_jsonl_rows(ai_root / DATASET_FILES["turn_decisions"], limit=300000)
    summaries = _read_jsonl_rows(ai_root / DATASET_FILES["career_summaries"], limit=50000)
    race_rows = [r for r in turn_rows if str(((r.get("action") or {}).get("type") or "")).lower() == "race"]
    race_with_result = [r for r in race_rows if isinstance((r.get("outcome") or {}).get("race_result"), Mapping) and (r.get("outcome") or {}).get("race_result")]
    clock_retry_rows = [r for r in race_rows if safe_int((r.get("outcome") or {}).get("clocks_used") or _mapping((r.get("outcome") or {}).get("clock_retry")).get("used")) > 0]
    clock_policy_enabled_rows = [r for r in race_rows if bool(_mapping((_mapping(r.get("turn_metadata")).get("clock_policy"))).get("user_enabled", _mapping((_mapping(r.get("turn_metadata")).get("clock_policy"))).get("enabled", False)))]
    item_attempts = 0
    event_records = 0
    for row in turn_rows:
        meta = row.get("turn_metadata") or {}
        for key in ("item_usage_attempts", "item_buy_attempts"):
            vals = meta.get(key) or []
            item_attempts += len(vals) if isinstance(vals, list) else 0
        events = meta.get("events") or []
        choices = meta.get("event_choices") or []
        event_records += (len(events) if isinstance(events, list) else 0) + (len(choices) if isinstance(choices, list) else 0)
    summaries_with_stats = [s for s in summaries if isinstance(s.get("final_stats"), Mapping) and s.get("final_stats")]
    warnings: List[str] = []
    if race_rows and not race_with_result:
        warnings.append("Race actions exist, but no race results were extracted. Live policy is unsafe.")
    if summaries and len(summaries_with_stats) < len(summaries):
        warnings.append("Some career summaries are missing final stat snapshots.")
    safe_for_live = not (race_rows and not race_with_result)
    return {
        "schema_version": SCHEMA_VERSION,
        "checked_at": now_iso(),
        "turn_decisions": len(turn_rows),
        "career_summaries": len(summaries),
        "race_rows": len(race_rows),
        "race_rows_with_result": len(race_with_result),
        "race_result_coverage": round(len(race_with_result) / max(1, len(race_rows)), 4),
        "clock_retry_rows": len(clock_retry_rows),
        "clock_policy_enabled_rows": len(clock_policy_enabled_rows),
        "clock_policy_enabled_rate": round(len(clock_policy_enabled_rows) / max(1, len(race_rows)), 4),
        "item_attempt_records": item_attempts,
        "event_records": event_records,
        "career_summaries_with_final_stats": len(summaries_with_stats),
        "safe_for_live_policy": safe_for_live,
        "warnings": warnings,
    }

# v5.37 previous-log import helpers -------------------------------------------------

def _read_json_file(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normal_log_target_name(original_name: str, digest: str) -> str:
    """Return a bot-log filename that still matches career_log_*.json.

    ``rebuild_from_career_logs`` intentionally scans only top-level
    ``career_log_*.json`` files. Imported logs therefore keep that prefix while
    gaining a hash suffix that prevents collisions between build folders.
    """
    clean = Path(original_name).name
    if clean.startswith("career_log_") and clean.endswith(".json"):
        return clean
    stem = clean.rsplit(".", 1)[0]
    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in stem)[:80] or "imported"
    return f"career_log_imported_{digest[:10]}_{safe}.json"


def _write_imported_log(target_logs: Path, name: str, payload: bytes, digest: str) -> Tuple[str, bool]:
    """Write a validated imported career log, avoiding duplicate/collision bugs."""
    target_logs.mkdir(parents=True, exist_ok=True)
    target = target_logs / _normal_log_target_name(name, digest)
    if target.exists():
        try:
            if _sha256_bytes(target.read_bytes()) == digest:
                return str(target), False
        except Exception:
            pass
        base = target.stem
        target = target_logs / f"{base}.imported_{digest[:10]}{target.suffix}"
        if not target.name.startswith("career_log_"):
            target = target_logs / f"career_log_{target.name}"
    target.write_bytes(payload)
    return str(target), True


def _merge_numeric_bucket(dst: MutableMapping[str, Any], src: Mapping[str, Any]) -> MutableMapping[str, Any]:
    for key in ("starts", "wins", "losses", "attempts", "clean_wins", "wins_after_clock", "clock_retry_races", "clocks_used", "clock_policy_enabled_starts", "clock_policy_disabled_starts"):
        if key in src:
            dst[key] = safe_int(dst.get(key)) + safe_int(src.get(key))
    ranks = []
    for value in (dst.get("ranks"), src.get("ranks")):
        if isinstance(value, list):
            ranks.extend(value)
    if ranks:
        dst["ranks"] = ranks[-500:]
    for key in ("last_rank", "last_turn", "last_seen_at", "name", "distance_m", "race_type", "last_stats"):
        if key in src and src.get(key) not in (None, ""):
            if key == "last_seen_at":
                if safe_float(src.get(key)) >= safe_float(dst.get(key)):
                    dst[key] = src.get(key)
            else:
                dst[key] = src.get(key)
    return dst


def _merge_race_outcomes_file(runtime: Path, incoming: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge a previous runtime race_outcomes.json into the active profile."""
    if not isinstance(incoming, Mapping) or not incoming:
        return {"merged_programs": 0, "merged_profiles": 0}
    target = runtime / "race_outcomes.json"
    current = _read_json_file(target, {})
    if not isinstance(current, dict):
        current = {}
    current.setdefault("version", incoming.get("version", 1))
    current["updated_at"] = int(time.time())
    cur_programs = current.setdefault("programs", {}) if isinstance(current.setdefault("programs", {}), dict) else {}
    merged_programs = 0
    for pid, row in (incoming.get("programs") or {}).items():
        if not isinstance(row, Mapping):
            continue
        key = str(pid)
        before = dict(cur_programs.get(key) or {})
        cur_programs[key] = dict(_merge_numeric_bucket(before, row))
        merged_programs += 1
    current["programs"] = cur_programs
    cur_profiles = current.setdefault("profiles", {}) if isinstance(current.setdefault("profiles", {}), dict) else {}
    merged_profiles = 0
    for key, row in (incoming.get("profiles") or {}).items():
        if not isinstance(row, Mapping):
            continue
        dst = cur_profiles.setdefault(str(key), {})
        if isinstance(dst, MutableMapping):
            _merge_numeric_bucket(dst, row)
            merged_profiles += 1
    current["profiles"] = cur_profiles
    _atomic_write_json(target, current)
    return {"merged_programs": merged_programs, "merged_profiles": merged_profiles}


def _event_key(row: Mapping[str, Any]) -> str:
    for names in (("story_id", "choice"), ("event_id", "choice"), ("title", "choice"), ("name", "choice")):
        parts = [str(row.get(name) or "").strip() for name in names]
        if any(parts):
            return "|".join(parts)
    return hashlib.sha1(json.dumps(row, sort_keys=True, default=_json_default).encode("utf-8")).hexdigest()


def _normalise_events_seen_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        rows = payload.get("events") or payload.get("rows") or payload.get("seen")
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, Mapping)]
        return [dict(row) for row in payload.values() if isinstance(row, Mapping)]
    return []


def _merge_events_seen_file(runtime: Path, incoming: Any) -> Dict[str, Any]:
    rows = _normalise_events_seen_payload(incoming)
    if not rows:
        return {"merged_events": 0}
    target = runtime / "events_seen.json"
    existing_rows = _normalise_events_seen_payload(_read_json_file(target, []))
    by_key = {_event_key(row): row for row in existing_rows}
    merged = 0
    for row in rows:
        key = _event_key(row)
        if key in by_key:
            # Preserve existing fields while accumulating a generic seen/count value
            old = by_key[key]
            old["seen_count"] = safe_int(old.get("seen_count") or old.get("count"), 1) + safe_int(row.get("seen_count") or row.get("count"), 1)
            for k, v in row.items():
                old.setdefault(k, v)
        else:
            by_key[key] = dict(row)
        merged += 1
    _atomic_write_json(target, {"events": list(by_key.values()), "updated_at": now_iso(), "source": "import_previous_logs"})
    return {"merged_events": merged}



def _normalise_settings_presets_payload(payload: Any) -> Tuple[str, List[Dict[str, Any]]]:
    """Return (active, presets) from modern or legacy preset payloads.

    Import sources can be a v5.27+ ``settings_presets.json`` object, an older
    list of presets, or an individual legacy preset object.  The result is kept
    deliberately narrow: only settings-preset fields are imported here, while
    auth/session/runtime files remain ignored.
    """
    if isinstance(payload, Mapping):
        active = str(payload.get("active") or "").strip()
        rows = payload.get("presets")
        if isinstance(rows, list):
            return active, [dict(row) for row in rows if isinstance(row, Mapping)]
        # Legacy single-preset JSON files often have a name plus settings at root.
        if payload.get("name") or payload.get("mant_config") or payload.get("training_stat_priority"):
            return str(payload.get("name") or "").strip(), [dict(payload)]
    if isinstance(payload, list):
        return "", [dict(row) for row in payload if isinstance(row, Mapping)]
    return "", []


def _settings_preset_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    def scrub(row: Mapping[str, Any]) -> Dict[str, Any]:
        data = dict(row or {})
        data.pop("name", None)
        return data
    return json.dumps(scrub(left), sort_keys=True, default=_json_default) == json.dumps(scrub(right), sort_keys=True, default=_json_default)


def _unique_imported_preset_name(existing: Mapping[str, Mapping[str, Any]], name: str) -> str:
    from .presets import slugify

    base = slugify(str(name or "Imported Preset").strip() or "Imported Preset")
    if base.lower() not in existing:
        return base
    imported = slugify(f"{base} Imported")
    if imported.lower() not in existing:
        return imported
    idx = 2
    while True:
        candidate = slugify(f"{base} Imported {idx}")
        if candidate.lower() not in existing:
            return candidate
        idx += 1


def _merge_settings_presets_file(base_dir: Any, incoming: Any) -> Dict[str, Any]:
    """Merge settings presets from an imported build into the current install.

    Existing user presets are never overwritten.  If an imported preset has the
    same name but different content, it is saved with an ``Imported`` suffix so
    the user can compare/rename/delete it from the normal preset UI.
    """
    from .config_store import _default_settings_preset, _is_legacy_settings_preset, _only_keys, SETTING_PRESET_KEYS

    active, rows = _normalise_settings_presets_payload(incoming)
    if not rows:
        return {"imported_presets": 0, "duplicate_presets": 0, "skipped_presets": 0, "active_imported": ""}

    settings_path = Path(base_dir) / "data" / "settings_presets.json"
    target = _read_json_file(settings_path, {"active": "", "presets": []})
    if not isinstance(target, Mapping):
        target = {"active": "", "presets": []}
    existing_rows = [dict(row) for row in target.get("presets", []) if isinstance(row, Mapping)]
    existing_by_name = {str(row.get("name") or "").strip().lower(): row for row in existing_rows if row.get("name")}

    imported = 0
    duplicates = 0
    skipped = 0
    imported_names: List[str] = []
    for row in rows:
        if _is_legacy_settings_preset(row):
            skipped += 1
            continue
        name = str(row.get("name") or "Imported Preset").strip() or "Imported Preset"
        clean = _default_settings_preset(name)
        clean.update(_only_keys(row, SETTING_PRESET_KEYS))
        clean["name"] = str(clean.get("name") or name).strip() or name
        key = clean["name"].lower()
        if key in existing_by_name:
            if _settings_preset_equal(existing_by_name[key], clean):
                duplicates += 1
                continue
            clean["name"] = _unique_imported_preset_name(existing_by_name, clean["name"])
            key = clean["name"].lower()
        existing_rows.append(clean)
        existing_by_name[key] = clean
        imported_names.append(clean["name"])
        imported += 1

    current_active = str(target.get("active") or "").strip()
    active_imported = ""
    # If the current install is still on a neutral Default, let the imported
    # active preset become active. Otherwise preserve the user's current choice.
    if imported_names and (not current_active or current_active.lower() == "default"):
        for candidate in imported_names:
            if active and candidate.lower() == active.lower():
                active_imported = candidate
                break
        if not active_imported:
            active_imported = imported_names[0]
        current_active = active_imported

    target_payload = {
        "active": current_active or (existing_rows[0].get("name") if existing_rows else "Default"),
        "presets": sorted(existing_rows, key=lambda row: str(row.get("name") or "").lower()),
    }
    _atomic_write_json(settings_path, target_payload)
    return {
        "imported_presets": imported,
        "duplicate_presets": duplicates,
        "skipped_presets": skipped,
        "active_imported": active_imported,
        "imported_names": imported_names[:25],
    }


def _is_legacy_preset_path(rel_name: str) -> bool:
    norm = str(rel_name or "").replace("\\", "/").lower()
    return "/data/presets/" in f"/{norm}" and norm.endswith(".json")

def _load_import_manifest(ai_root: Path) -> Dict[str, Any]:
    path = ai_root / "import_manifest.json"
    data = _read_json_file(path, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("imports", [])
    data.setdefault("hashes", {})
    return data


def _save_import_manifest(ai_root: Path, manifest: Mapping[str, Any]) -> None:
    _atomic_write_json(ai_root / "import_manifest.json", manifest)


def _iter_import_sources_from_dir(source: Path) -> Iterable[Tuple[str, bytes]]:
    wanted_names = {"race_outcomes.json", "events_seen.json", "settings_presets.json"}
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        name = path.name
        if name.startswith("career_log_") and name.endswith(".json"):
            yield str(path), path.read_bytes()
        elif name in wanted_names or _is_legacy_preset_path(str(path)):
            yield str(path), path.read_bytes()


def _iter_import_sources_from_zip(source: Path) -> Iterable[Tuple[str, bytes]]:
    wanted_names = {"race_outcomes.json", "events_seen.json", "settings_presets.json"}
    with zipfile.ZipFile(source, "r") as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            name = Path(info.filename).name
            if not name or info.filename.startswith("__MACOSX/"):
                continue
            if (name.startswith("career_log_") and name.endswith(".json")) or name in wanted_names or _is_legacy_preset_path(info.filename):
                yield info.filename, zf.read(info)


def import_previous_logs(base_dir: Any, source_path: str, rebuild: bool = True, build_version: str = "", import_presets: bool = True) -> Dict[str, Any]:
    """Import previous Pre Icarus career logs into the active runtime profile.

    The importer accepts either a previous build folder, a previous ``uma_runtime``
    folder, a ``bot_logs`` folder, or a zip containing those files. Only AI-safe
    gameplay logs/aggregates and user settings presets are imported: auth configs, Steam tokens, raw account
    configs, and unrelated files are ignored.
    """
    raw = str(source_path or "").strip().strip('"')
    if not raw:
        return {"success": False, "detail": "No source path provided."}
    source = Path(raw).expanduser()
    if not source.exists():
        return {"success": False, "detail": f"Source path does not exist: {source}"}
    runtime = runtime_output_root(base_dir)
    target_logs = runtime / "bot_logs"
    ai_root = runtime / "ai"
    ai_root.mkdir(parents=True, exist_ok=True)
    manifest = _load_import_manifest(ai_root)
    known_hashes = set((manifest.get("hashes") or {}).keys())
    imported_logs = 0
    duplicates = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []
    merged_race = {"merged_programs": 0, "merged_profiles": 0}
    merged_events = {"merged_events": 0}
    merged_presets = {"imported_presets": 0, "duplicate_presets": 0, "skipped_presets": 0, "active_imported": "", "imported_names": []}
    iterator = _iter_import_sources_from_zip(source) if source.is_file() and source.suffix.lower() == ".zip" else _iter_import_sources_from_dir(source)
    for rel_name, data in iterator:
        digest = _sha256_bytes(data)
        name = Path(rel_name).name
        if digest in known_hashes:
            duplicates += 1
            continue
        try:
            payload = json.loads(data.decode("utf-8"))
        except Exception as exc:
            skipped += 1
            errors.append({"path": rel_name, "error": f"invalid JSON: {exc}"})
            continue
        try:
            if name.startswith("career_log_") and name.endswith(".json"):
                if not isinstance(payload, Mapping):
                    raise ValueError("career log root must be a JSON object")
                target, wrote = _write_imported_log(target_logs, name, data, digest)
                if wrote:
                    imported_logs += 1
                else:
                    duplicates += 1
                manifest.setdefault("hashes", {})[digest] = {"kind": "career_log", "source": rel_name, "target": target, "imported_at": now_iso()}
                known_hashes.add(digest)
            elif name == "race_outcomes.json":
                result = _merge_race_outcomes_file(runtime, payload if isinstance(payload, Mapping) else {})
                merged_race["merged_programs"] += safe_int(result.get("merged_programs"))
                merged_race["merged_profiles"] += safe_int(result.get("merged_profiles"))
                manifest.setdefault("hashes", {})[digest] = {"kind": "race_outcomes", "source": rel_name, "imported_at": now_iso()}
                known_hashes.add(digest)
            elif name == "events_seen.json":
                result = _merge_events_seen_file(runtime, payload)
                merged_events["merged_events"] += safe_int(result.get("merged_events"))
                manifest.setdefault("hashes", {})[digest] = {"kind": "events_seen", "source": rel_name, "imported_at": now_iso()}
                known_hashes.add(digest)
            elif import_presets and (name == "settings_presets.json" or _is_legacy_preset_path(rel_name)):
                result = _merge_settings_presets_file(base_dir, payload)
                merged_presets["imported_presets"] += safe_int(result.get("imported_presets"))
                merged_presets["duplicate_presets"] += safe_int(result.get("duplicate_presets"))
                merged_presets["skipped_presets"] += safe_int(result.get("skipped_presets"))
                if result.get("active_imported"):
                    merged_presets["active_imported"] = result.get("active_imported")
                merged_presets.setdefault("imported_names", []).extend(result.get("imported_names") or [])
                manifest.setdefault("hashes", {})[digest] = {"kind": "settings_presets", "source": rel_name, "imported_at": now_iso(), "result": result}
                known_hashes.add(digest)
        except Exception as exc:
            skipped += 1
            errors.append({"path": rel_name, "error": f"{type(exc).__name__}: {exc}"})
    entry = {
        "source": str(source),
        "imported_at": now_iso(),
        "imported_logs": imported_logs,
        "duplicates": duplicates,
        "skipped": skipped,
        **merged_race,
        **merged_events,
        **{k: v for k, v in merged_presets.items() if k != "imported_names"},
    }
    manifest.setdefault("imports", []).append(entry)
    manifest["last_import"] = entry
    _save_import_manifest(ai_root, manifest)
    rebuild_status: Dict[str, Any] = {}
    if rebuild:
        rebuild_status = rebuild_from_career_logs(base_dir, build_version=build_version)
    return {
        "success": True,
        "source": str(source),
        "target_logs": str(target_logs),
        "imported_logs": imported_logs,
        "duplicates": duplicates,
        "skipped": skipped,
        "errors": errors[:25],
        "race_outcomes": merged_race,
        "events_seen": merged_events,
        "presets": {**merged_presets, "imported_names": (merged_presets.get("imported_names") or [])[:25]},
        "rebuild": rebuild_status,
        "manifest": str(ai_root / "import_manifest.json"),
    }

_LINE_COUNT_MEMO: Dict[str, Any] = {}


def _count_lines_cached(path) -> int:
    """Count newlines, memoized by (size, mtime). Append-only datasets only get
    re-read when they actually change, so repeated status polls cost a stat()."""
    try:
        st = path.stat()
    except OSError:
        return 0
    key = str(path)
    sig = (st.st_size, st.st_mtime_ns)
    ent = _LINE_COUNT_MEMO.get(key)
    if ent is not None and ent[0] == sig:
        return ent[1]
    try:
        with path.open("rb") as fh:
            count = sum(1 for _ in fh)
    except Exception:
        return -1
    _LINE_COUNT_MEMO[key] = (sig, count)
    return count


def dataset_status(base_dir: Any) -> Dict[str, Any]:
    root = runtime_output_root(base_dir) / "ai"
    files: Dict[str, Dict[str, Any]] = {}
    for kind, name in DATASET_FILES.items():
        path = root / name
        exists = path.exists()
        live = _count_lines_cached(path) if exists else 0
        archived = 0
        for ap in _archive_paths(path):
            ac = _count_lines_cached(ap)
            if ac > 0:
                archived += ac
        # "rows" stays the cumulative total (live + rotated archives) so the UI
        # count keeps climbing across rotations; live_rows is the on-disk file.
        files[kind] = {"path": str(path), "exists": exists, "rows": live + archived,
                       "live_rows": live, "archived_rows": archived}
    stats_path = root / "advisor_stats.json"
    stats = {}
    if stats_path.exists():
        try:
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
        except Exception as exc:
            stats = {"error": str(exc)}
    import_manifest = _read_json_file(root / "import_manifest.json", {}) if (root / "import_manifest.json").exists() else {}
    return {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "dataset_version": AI_DATASET_VERSION,
        "ai_root": str(root),
        "files": files,
        "advisor_stats": stats,
        "health": dataset_health(root),
        "import_manifest": import_manifest if isinstance(import_manifest, dict) else {},
        "latest_manifest": str(root / "latest_export_manifest.json"),
    }


def rebuild_from_career_logs(base_dir: Any, build_version: str = "") -> Dict[str, Any]:
    """Rebuild AI JSONL exports from existing career logs.

    This is useful after upgrading from an older Pre Icarus build.  Existing AI
    dataset files are rotated with a timestamp rather than destroyed.
    """
    runtime = runtime_output_root(base_dir)
    logs = runtime / "bot_logs"
    ai_root = runtime / "ai"
    ai_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for name in DATASET_FILES.values():
        path = ai_root / name
        if path.exists():
            path.replace(ai_root / f"{path.stem}.{stamp}.bak{path.suffix}")
    processed = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []
    for path in sorted(logs.glob("career_log_*.json")) if logs.exists() else []:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            export_report_ai_datasets(report, logs, build_version=build_version)
            processed += 1
        except Exception as exc:
            skipped += 1
            errors.append({"path": str(path), "error": str(exc), "type": type(exc).__name__})
    status = dataset_status(base_dir)
    status.update({"processed": processed, "skipped": skipped, "errors": errors[:20]})
    return status
