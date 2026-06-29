import json
import re
import traceback
import tempfile
from datetime import datetime
from pathlib import Path

from career_bot.ai_dataset import export_report_ai_datasets
try:
    from career_bot.ai_trainer import after_career_export
except Exception:  # keep report writer import-safe for minimal test harnesses
    after_career_export = None


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def new_report(preset=None, scenario_id=0):
    preset = preset or {}
    return {
        "started_at": now_iso(),
        "ended_at": None,
        "preset_name": preset.get("name", ""),
        "scenario_id": scenario_id,
        "status": "running",
        "error": None,
        "final_turn": 0,
        "turns": [],
    }


def safe_int(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def turn_from_event(event):
    data = event.get("data") or {}
    for key in ("payload", "request_payload"):
        payload = data.get(key) or {}
        if payload.get("current_turn") is not None:
            return safe_int(payload.get("current_turn"))
    if event.get("turn") is not None:
        return safe_int(event.get("turn"))
    return 0


def get_turn(report, turn_number):
    turn_number = safe_int(turn_number)
    for turn in report.setdefault("turns", []):
        if safe_int(turn.get("turn")) == turn_number:
            return turn
    turn = {
        "turn": turn_number,
        "api_calls": [],
        "skill_buy_attempts": [],
        "item_buy_attempts": [],
        "item_usage_attempts": [],
    }
    report.setdefault("turns", []).append(turn)
    report["turns"].sort(key=lambda row: safe_int(row.get("turn")))
    return turn


def merge_turn(report, row):
    turn_number = safe_int(row.get("turn"))
    turn = get_turn(report, turn_number)
    preserved = {
        "api_calls": turn.get("api_calls") or [],
        "skill_buy_attempts": turn.get("skill_buy_attempts") or [],
        "item_buy_attempts": turn.get("item_buy_attempts") or [],
        "item_usage_attempts": turn.get("item_usage_attempts") or [],
    }
    turn.update(row)
    for key, value in preserved.items():
        turn[key] = value
    report["final_turn"] = max(safe_int(report.get("final_turn")), turn_number)
    return turn


def add_event(report, row):
    event = row.get("event")
    turn = get_turn(report, row.get("turn"))
    if event == "turn":
        return merge_turn(report, row)
    if event == "skills_attempt":
        turn.setdefault("skill_buy_attempts", []).append(row)
    elif event == "items_buy_attempt":
        turn.setdefault("item_buy_attempts", []).append(row)
    elif event == "items_use_attempt":
        turn.setdefault("item_usage_attempts", []).append(row)
    else:
        turn.setdefault("events", []).append(row)
    report["final_turn"] = max(safe_int(report.get("final_turn")), safe_int(row.get("turn")))
    return turn


# v2.1: career logs were ~50MB because api_calls stored full raw API payloads
# (~94% of the file) PLUS bot-injected context (runner_context/action_history/
# replan_log) that leaks into the logged response objects. Slim each logged
# api_call to metadata + ONLY the response keys downstream consumers actually
# read, so logs shrink ~95% while staying coherent for AI debugging. Consumers
# (verified): ai_dataset._race_result_from_api_response reads data.data.
# {race_reward_info, chara_info, race_history} on race_end; ai_dataset.
# _api_context_from_turn / _stats_from_turn_payload read data.data.{home_info,
# free_data_set, race_condition_array, unchecked_event_array, chara_info};
# benchmark reads data.data.chara_info. Anything not in the keep-set is dropped.
_API_KEEP_KEYS_ALWAYS = frozenset({
    "chara_info", "home_info", "free_data_set",
    "race_condition_array", "unchecked_event_array",
})
_API_KEEP_KEYS_RACE_END = frozenset({"race_reward_info", "race_history"})


def _slim_api_event(event):
    """Project a logged api_call to metadata + consumer-read response keys only.
    Drops full raw payloads and bot-injected context (runner_context,
    action_history, replan_log, the trained_chara roster, etc.)."""
    if not isinstance(event, dict):
        return event
    slim = {k: event.get(k) for k in ("ts", "direction", "endpoint", "req_id", "turn") if k in event}
    # v2.1: preserve the skill-purchase REQUEST body (a small list of skill ids)
    # so per-skill spending is diagnosable in career logs. Other request bodies
    # stay dropped (they're large and not useful for AI/debug analysis).
    if event.get("direction") == "REQ" and "gain_skills" in str(event.get("endpoint") or ""):
        slim["data"] = event.get("data")
        return slim
    data = event.get("data")
    if isinstance(data, dict):
        if "response_code" in data:
            slim["response_code"] = data.get("response_code")
        if "error" in data:  # keep ERR-call error text -- useful for AI debugging
            slim["error"] = data.get("error")
        inner = data.get("data")
        if isinstance(inner, dict):
            keep = set(_API_KEEP_KEYS_ALWAYS)
            if "race_end" in str(event.get("endpoint") or ""):
                keep |= _API_KEEP_KEYS_RACE_END  # race_history only here (else it's bot-injected bloat)
            proj = {k: inner[k] for k in inner if k in keep}
            if proj:
                slim["data"] = {"data": proj}
    return slim


def add_api_call(report, event):
    turn = get_turn(report, turn_from_event(event))
    turn.setdefault("api_calls", []).append(_slim_api_event(event))
    report["final_turn"] = max(safe_int(report.get("final_turn")), safe_int(turn.get("turn")))


def add_decision(report, state, decision):
    data = (state or {}).get("data") or {}
    chara = data.get("chara_info") or {}
    payload = dict(getattr(decision, "payload", {}) or {})
    runner_context = data.get("runner_context") or {}
    clock_policy = runner_context.get("clock_retry_policy") or {
        "user_enabled": bool(runner_context.get("burn_clocks")),
        "enabled": bool(runner_context.get("burn_clocks")),
        "source": "decision_context",
    }
    turn = get_turn(report, payload.get("current_turn") or chara.get("turn") or 0)
    turn["current_command"] = payload
    turn["selected_action"] = getattr(decision, "action", "")
    turn["decision_reason"] = getattr(decision, "reason", "")
    turn["current_action_taken"] = getattr(decision, "action", "")
    turn["decision_report"] = {
        "action": getattr(decision, "action", ""),
        "reason": getattr(decision, "reason", ""),
        "payload": payload,
        "state": {
            "turn": safe_int(chara.get("turn")),
            "hp": safe_int(chara.get("vital")),
            "max_hp": safe_int(chara.get("max_vital"), 100),
            "mood": safe_int(chara.get("motivation")),
            "fans": safe_int(chara.get("fans")),
            "speed": safe_int(chara.get("speed")),
            "stamina": safe_int(chara.get("stamina")),
            "power": safe_int(chara.get("power")),
            "guts": safe_int(chara.get("guts")),
            "wit": safe_int(chara.get("wiz")),
            "skill_point": safe_int(chara.get("skill_point")),
        },
        "race_context": {
            "program_id": payload.get("program_id"),
            "forced_race": bool(payload.get("_forced_race")),
            "clock_policy": clock_policy,
            "clocks_used_so_far": safe_int(runner_context.get("clocks_used")),
            "clocks_left": safe_int(runner_context.get("clocks_left")),
        },
    }


def set_error(report, exc):
    report["status"] = "error"
    report["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
        "stack_trace": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }


def finish_report(report, status=None):
    if status:
        report["status"] = status
    if report.get("status") == "running":
        report["status"] = "finished"
    report["ended_at"] = now_iso()
    turns = report.get("turns") or []
    if turns:
        report["final_turn"] = max(safe_int(turn.get("turn")) for turn in turns)


# Personal / credential fields that must never appear in a shared career log.
# The first block is the user-specified device/network/Steam identity fields; the
# second is login credentials (sharing these would be an account-takeover risk).
_REDACT_KEYS = frozenset({
    "device_id", "device_name", "graphics_device_name", "ip_address",
    "platform_os_version", "carrier", "keychain", "locale", "button_info",
    "dmm_viewer_id", "dmm_onetime_token", "steam_id", "steam_session_ticket",
    "udid", "auth_key",
})


def _build_version():
    """Read the build/channel label from the top CHANGELOG.md heading (e.g.
    'Icarus v2.1 (Beta 1)' or 'Icarus v2.0'). Stamped into every career log so a
    shared log self-identifies exactly which build produced it."""
    try:
        changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
        for line in changelog.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                return line[3:].strip()
    except Exception:
        pass
    return "unknown"


def _redact_sensitive(obj):
    """Recursively redact personal/credential fields in place, so career logs
    never leak device, network, or Steam/account identifiers."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key in _REDACT_KEYS:
                obj[key] = "[REDACTED]"
            else:
                _redact_sensitive(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            _redact_sensitive(item)
    return obj


def write_report(report, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Scrub personal data before anything is written to disk (covers the career
    # log, the latest_career_log.json copy, and the AI-ready exports below).
    _redact_sensitive(report)
    # Stamp the build/channel so a shared log self-identifies its build.
    report["build_version"] = _build_version()
    if isinstance(report.get("runtime_settings"), dict):
        report["runtime_settings"]["build_version"] = report["build_version"]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"career_log_{stamp}.json"

    def _json_default(obj):
        if isinstance(obj, bytes):
            return obj.hex()
        return str(obj)

    # v5.31: write atomically and validate before replacing the final log.
    # This prevents truncated/malformed JSON exports if Python is killed while
    # the file is being written.
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(output_dir))
    tmp = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=_json_default)
            f.write("\n")
        json.loads(tmp.read_text(encoding="utf-8"))
        tmp.replace(path)
    except Exception:
        try:
            broken = output_dir / f"career_log_{stamp}.broken.json"
            tmp.replace(broken)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        raise

    latest = output_dir / "latest_career_log.json"
    try:
        import shutil
        shutil.copyfile(path, latest)
        json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        pass

    # v5.32: AI-ready learning exports are best-effort observability.
    # They never alter the user-facing career log and must never stop report
    # creation if a derived dataset cannot be written.
    try:
        manifest = export_report_ai_datasets(report, output_dir, build_version=_build_version())
        report["ai_export_manifest"] = manifest
        if after_career_export:
            report["ai_auto_training"] = after_career_export(output_dir, manifest=manifest, build_version=_build_version())
    except Exception as exc:
        report["ai_export_error"] = {"type": type(exc).__name__, "message": str(exc)}
    return path
