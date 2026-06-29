"""Local LLM adapter for Pre Icarus AI.

The deterministic runner remains the authority.  This module lets a user run a
local OpenAI-compatible server (LM Studio, Ollama, llama.cpp, etc.) and use it
for offline post-run analysis plus shadow turn advice.  Outputs are stored as
append-only JSONL artifacts and are never executed as bot commands.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

import requests

from career_bot.ai_dataset import DATASET_FILES, runtime_output_root, safe_float, safe_int

LOCAL_LLM_VERSION = "SweepyCL Local LLM v1"
CONFIG_FILE = "local_llm_config.json"
STATUS_FILE = "local_llm_status.json"
ADVICE_FILE = "llm_advice.jsonl"
SUMMARY_FILE = "llm_run_summaries.jsonl"
PROMPT_CHAR_BUDGET = 12000
MIN_ANALYSIS_TURNS = 8

ALLOWED_MODES = {"off", "offline", "shadow", "recommend"}
DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "provider": "lmstudio",  # lmstudio, ollama, custom
    "base_url": "http://localhost:1234/v1",
    "model": "",
    "api_key": "lm-studio",
    "mode": "offline",  # off, offline, shadow, recommend
    "timeout_seconds": 30,
    "max_turns_per_prompt": 80,
    "temperature": 0.2,
    "max_tokens": 900,
    "allow_live_override": False,
    "require_json": True,
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ai_root(base_dir: Any) -> Path:
    path = Path(base_dir)
    if path.name == "ai":
        return path
    if path.name == "uma_runtime":
        return path / "ai"
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


def _read_json(path: Path, default: Any) -> Any:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return default


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")


def _read_jsonl(path: Path, limit: int = 1000) -> List[Dict[str, Any]]:
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


def _redact_config(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(cfg or {})
    key = str(out.get("api_key") or "")
    out["api_key_set"] = bool(key)
    if key:
        out["api_key"] = "••••" + key[-4:]
    else:
        out["api_key"] = ""
    return out


def _normalize_config(payload: Mapping[str, Any]) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(payload, Mapping):
        for key in DEFAULT_CONFIG:
            if key in payload:
                cfg[key] = payload[key]
    cfg["enabled"] = bool(cfg.get("enabled"))
    cfg["provider"] = str(cfg.get("provider") or "custom").strip().lower() or "custom"
    if cfg["provider"] not in {"lmstudio", "ollama", "custom"}:
        cfg["provider"] = "custom"
    cfg["base_url"] = str(cfg.get("base_url") or DEFAULT_CONFIG["base_url"]).strip().rstrip("/")
    cfg["model"] = str(cfg.get("model") or "").strip()
    cfg["api_key"] = str(cfg.get("api_key") or "").strip()
    mode = str(cfg.get("mode") or "offline").strip().lower()
    cfg["mode"] = mode if mode in ALLOWED_MODES else "offline"
    cfg["timeout_seconds"] = max(3, min(180, safe_int(cfg.get("timeout_seconds"), 30)))
    cfg["max_turns_per_prompt"] = max(5, min(250, safe_int(cfg.get("max_turns_per_prompt"), 80)))
    cfg["temperature"] = max(0.0, min(1.5, safe_float(cfg.get("temperature"), 0.2)))
    cfg["max_tokens"] = max(128, min(4096, safe_int(cfg.get("max_tokens"), 900)))
    cfg["allow_live_override"] = False  # Deliberately pinned off in this build.
    cfg["require_json"] = True
    return cfg


def load_config(base_dir: Any) -> Dict[str, Any]:
    payload = _read_json(ai_root(base_dir) / CONFIG_FILE, {})
    return _normalize_config(payload if isinstance(payload, Mapping) else {})


def save_config(base_dir: Any, patch: Mapping[str, Any]) -> Dict[str, Any]:
    current = load_config(base_dir)
    incoming = patch or {}
    merged = dict(current)
    for key in DEFAULT_CONFIG:
        if key not in incoming:
            continue
        if key == "api_key":
            key_value = str(incoming.get("api_key") or "").strip()
            # Empty/redacted API key values mean "keep the existing saved key".
            # This prevents the dashboard refresh/save loop from erasing credentials.
            if not key_value or key_value.startswith("••••") or set(key_value) <= {"*"}:
                continue
            merged[key] = key_value
            continue
        merged[key] = incoming[key]
    cfg = _normalize_config(merged)
    cfg["updated_at"] = now_iso()
    _atomic_write_json(ai_root(base_dir) / CONFIG_FILE, cfg)
    return cfg


def _chat_url(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _headers(cfg: Mapping[str, Any]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = str(cfg.get("api_key") or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _extract_message_text(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices") if isinstance(payload, Mapping) else None
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], Mapping) else {}
    msg = first.get("message") if isinstance(first.get("message"), Mapping) else {}
    content = msg.get("content")
    if content is None:
        content = first.get("text")
    return str(content or "").strip()


def _strip_json_fences(text: str) -> str:
    """Remove common Markdown wrappers and chatty prefixes around JSON."""
    value = str(text or "").strip()
    if not value:
        return ""
    # Handles ```json ... ```, ```JSON ... ```, and plain fenced blocks.
    fence = re.match(r"^```(?:json|javascript|js)?\s*(.*?)\s*```$", value, flags=re.I | re.S)
    if fence:
        value = fence.group(1).strip()
    # Some local models prefix the object with labels such as "JSON:".
    value = re.sub(r"^(?:json|result|response)\s*:\s*", "", value, flags=re.I).strip()
    return value


def _json_loads_lenient(value: str) -> Any:
    """Try a few safe JSON cleanups before giving up.

    Local models sometimes return technically-valid JSON inside a JSON string,
    fenced JSON, or JSON with trailing commas.  This stays intentionally small:
    no eval, no YAML, no code execution, just JSON normalization.
    """
    cleaned = _strip_json_fences(value)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # Remove trailing commas before object/array endings.
    no_trailing = re.sub(r",\s*([}\]])", r"\1", cleaned)
    if no_trailing != cleaned:
        try:
            return json.loads(no_trailing)
        except Exception:
            pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                return json.loads(candidate)
            except Exception:
                pass
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start >= 0 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    raise ValueError("not valid JSON")


def parse_jsonish(text: str, *, _depth: int = 0) -> Dict[str, Any]:
    """Parse model text that should contain JSON, including double-encoded JSON.

    Returns a dictionary whenever possible.  If parsing fails, returns
    {"raw_text": ...} so callers still have the original model output.
    """
    text = str(text or "").strip()
    if not text:
        return {}
    if _depth > 4:
        return {"raw_text": text}
    try:
        data = _json_loads_lenient(text)
    except Exception:
        return {"raw_text": _strip_json_fences(text)}
    if isinstance(data, str):
        nested = data.strip()
        if nested and nested != text.strip():
            return parse_jsonish(nested, _depth=_depth + 1)
        return {"raw_text": nested}
    if isinstance(data, dict):
        # If the model nested another JSON object inside raw_text, unpack it.
        raw = data.get("raw_text")
        if isinstance(raw, str) and ("{" in raw or "[" in raw):
            nested = parse_jsonish(raw, _depth=_depth + 1)
            if nested and not (set(nested.keys()) == {"raw_text"}):
                merged = dict(nested)
                merged.setdefault("_source_wrapped_raw_text", True)
                return merged
        return data
    return {"value": data}


def _unwrap_model_payload(parsed: Mapping[str, Any], *, preferred_key: str) -> Dict[str, Any]:
    """Flatten common LLM response envelopes into the useful payload.

    Many models return {"analysis": {...}} even though the dashboard wants the
    contents of that object. Shadow reviews often do the same with {"advice"}.
    """
    if not isinstance(parsed, Mapping):
        return {}
    data: Dict[str, Any] = dict(parsed)
    raw_only = set(data.keys()) == {"raw_text"}
    raw_value = data.get("raw_text")
    if isinstance(raw_value, str) and ("{" in raw_value or "[" in raw_value):
        nested = parse_jsonish(raw_value)
        if nested and not (set(nested.keys()) == {"raw_text"}):
            return _unwrap_model_payload(nested, preferred_key=preferred_key)
    if raw_only:
        return data

    # Unwrap exact or dominant envelope keys.
    for key in (preferred_key, "analysis", "advice", "result", "response", "data"):
        value = data.get(key)
        if isinstance(value, str) and ("{" in value or "[" in value):
            value = parse_jsonish(value)
        if isinstance(value, Mapping):
            envelope_noise = {"task", "version", "model", "created_at"}
            other_keys = set(data.keys()) - {key} - envelope_noise
            if not other_keys or preferred_key == key or key in {"analysis", "advice"}:
                inner = dict(value)
                for meta_key in ("summary", "headline", "overall_assessment"):
                    if meta_key in data and meta_key not in inner:
                        inner[meta_key] = data[meta_key]
                inner.setdefault("_source_envelope", key)
                return inner

    # Normalize common alternate field names into the shapes the UI knows.
    if "key_patterns" not in data and isinstance(data.get("patterns"), list):
        data["key_patterns"] = data.get("patterns")
    if "repeatable_rules" not in data:
        for alias in ("candidate_rules", "suggested_rules", "rules"):
            if isinstance(data.get(alias), list):
                data["repeatable_rules"] = data.get(alias)
                break
    return data


def normalize_analysis_payload(text: str) -> Dict[str, Any]:
    return _unwrap_model_payload(parse_jsonish(text), preferred_key="analysis")


def normalize_advice_payload(text: str) -> Dict[str, Any]:
    return _unwrap_model_payload(parse_jsonish(text), preferred_key="advice")


def _response_error_detail(resp: Any) -> str:
    status = getattr(resp, "status_code", None)
    detail = ""
    try:
        detail = str(getattr(resp, "text", "") or "")
    except Exception:
        detail = ""
    if not detail:
        try:
            payload = resp.json() if hasattr(resp, "json") else None
            detail = json.dumps(payload, ensure_ascii=False, default=_json_default)
        except Exception:
            detail = ""
    detail = re.sub(r"\s+", " ", detail).strip()
    if detail:
        detail = detail[:1200]
    if status:
        return f"HTTP {status}: {detail}" if detail else f"HTTP {status}"
    return detail or "HTTP request failed"


def _prompt_char_count(packet: Mapping[str, Any]) -> int:
    return len(json.dumps(packet, ensure_ascii=False, default=_json_default))


def _fit_recent_turns_to_budget(packet: Dict[str, Any], *, budget: int = PROMPT_CHAR_BUDGET) -> Dict[str, Any]:
    """Keep prompts small enough for local 4k/8k context models.

    LM Studio often returns HTTP 400 when the request is bigger than the loaded
    model's context window. The connection test is tiny, but post-run packets can
    become large after real careers. This trims recent_turns while preserving the
    last turns and a tiny run summary.
    """
    pkt = dict(packet)
    turns = list(pkt.get("recent_turns") or [])
    original_turn_count = len(turns)
    pkt["turns_available"] = original_turn_count
    pkt["prompt_budget_chars"] = budget

    def set_turns(next_turns: List[Mapping[str, Any]]) -> None:
        pkt["recent_turns"] = [dict(t) for t in next_turns]
        pkt["turns_sent_after_budget"] = len(pkt["recent_turns"])

    set_turns(turns)
    if _prompt_char_count(pkt) <= budget:
        return pkt

    # First trim to the latest half until the packet fits or reaches the floor.
    while len(pkt.get("recent_turns") or []) > MIN_ANALYSIS_TURNS and _prompt_char_count(pkt) > budget:
        current = list(pkt.get("recent_turns") or [])
        keep = max(MIN_ANALYSIS_TURNS, len(current) // 2)
        set_turns(current[-keep:])

    if _prompt_char_count(pkt) <= budget:
        pkt["budget_note"] = "Trimmed recent turns to fit local model context."
        return pkt

    # Then remove nonessential nested detail from the remaining turns.
    slim_turns: List[Dict[str, Any]] = []
    for turn in list(pkt.get("recent_turns") or [])[-MIN_ANALYSIS_TURNS:]:
        if not isinstance(turn, Mapping):
            continue
        action = turn.get("action") if isinstance(turn.get("action"), Mapping) else {}
        slim_turns.append({
            "turn": safe_int(turn.get("turn")),
            "state": turn.get("state") if isinstance(turn.get("state"), Mapping) else {},
            "action": {
                "type": str(action.get("type") or "unknown"),
                "reason": str(action.get("reason") or "")[:60],
                "command_type": safe_int(action.get("command_type")),
                "command_id": safe_int(action.get("command_id")),
            },
            "reward": safe_float(turn.get("reward")),
            "race_rank": safe_int(turn.get("race_rank")),
            "clocks_used": safe_int(turn.get("clocks_used")),
        })
    set_turns(slim_turns)
    pkt["budget_note"] = "Trimmed and slimmed recent turns to fit local model context."
    return pkt

def _request_chat(cfg: Mapping[str, Any], messages: List[Mapping[str, str]], *, post_fn: Optional[Callable[..., Any]] = None) -> Tuple[Dict[str, Any], float]:
    post = post_fn or requests.post
    body = {
        "model": cfg.get("model") or "local-model",
        "messages": messages,
        "temperature": safe_float(cfg.get("temperature"), 0.2),
        "max_tokens": safe_int(cfg.get("max_tokens"), 900),
    }
    start = time.time()
    resp = post(_chat_url(str(cfg.get("base_url") or "")), headers=_headers(cfg), json=body, timeout=safe_int(cfg.get("timeout_seconds"), 30))
    elapsed = round((time.time() - start) * 1000.0, 2)
    status_code = getattr(resp, "status_code", None)
    if isinstance(status_code, int) and status_code >= 400:
        raise RuntimeError(_response_error_detail(resp))
    if hasattr(resp, "raise_for_status"):
        try:
            resp.raise_for_status()
        except Exception as exc:
            raise RuntimeError(_response_error_detail(resp)) from exc
    data = resp.json() if hasattr(resp, "json") else {}
    if not isinstance(data, dict):
        data = {}
    return data, elapsed


def _system_prompt() -> str:
    return (
        "You are Pre Icarus's local strategy analyst. The deterministic bot is the final authority. "
        "Return strict JSON only. Do not give click instructions, code execution instructions, memory access instructions, or automation commands. "
        "Analyze gameplay decisions, risks, and repeatable rules from the supplied safe turn data."
    )


def _compact_state(row: Mapping[str, Any]) -> Dict[str, Any]:
    state = row.get("state") if isinstance(row.get("state"), Mapping) else {}
    return {
        "turn": safe_int(row.get("turn")),
        "speed": safe_int(state.get("speed")),
        "stamina": safe_int(state.get("stamina")),
        "power": safe_int(state.get("power")),
        "guts": safe_int(state.get("guts")),
        "wit": safe_int(state.get("wit")),
        "skill_point": safe_int(state.get("skill_point")),
        "hp": safe_int(state.get("hp")),
        "mood": safe_int(state.get("mood")),
        "fans": safe_int(state.get("fans")),
    }


def _compact_turn(row: Mapping[str, Any]) -> Dict[str, Any]:
    action = row.get("action") if isinstance(row.get("action"), Mapping) else {}
    outcome = row.get("outcome") if isinstance(row.get("outcome"), Mapping) else {}
    race_result = outcome.get("race_result") if isinstance(outcome.get("race_result"), Mapping) else {}
    return {
        "turn": safe_int(row.get("turn")),
        "scenario_id": safe_int(row.get("scenario_id")),
        "state": _compact_state(row),
        "action": {
            "type": str(action.get("type") or "unknown"),
            "reason": str(action.get("reason") or "")[:100],
            "program_id": safe_int(action.get("program_id")),
            "command_type": safe_int(action.get("command_type")),
            "command_id": safe_int(action.get("command_id")),
        },
        "reward": round(safe_float(outcome.get("reward")), 3),
        "race_rank": safe_int(race_result.get("rank") or race_result.get("result_rank"), 0),
        "clocks_used": safe_int(outcome.get("clocks_used")),
        "candidate_counts": {
            "training": len(((row.get("candidate_context") or {}).get("training_candidates") or []) if isinstance(row.get("candidate_context"), Mapping) else []),
            "races": len((((row.get("turn_metadata") or {}).get("api_context") or {}).get("available_race_program_ids") or []) if isinstance(row.get("turn_metadata"), Mapping) else []),
        },
    }


def _dataset_paths(base_dir: Any) -> Dict[str, Path]:
    root = ai_root(base_dir)
    return {key: root / name for key, name in DATASET_FILES.items()}


def load_turn_rows(base_dir: Any, limit: int = 500) -> List[Dict[str, Any]]:
    return _read_jsonl(_dataset_paths(base_dir)["turn_decisions"], limit=limit)


def load_career_summaries(base_dir: Any, limit: int = 200) -> List[Dict[str, Any]]:
    return _read_jsonl(_dataset_paths(base_dir)["career_summaries"], limit=limit)


def _latest_run_rows(turn_rows: List[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    if not turn_rows:
        return []
    run_id = str((turn_rows[-1] or {}).get("run_id") or "")
    if not run_id:
        return [row for row in turn_rows[-80:] if isinstance(row, Mapping)]
    rows = [row for row in turn_rows if isinstance(row, Mapping) and str(row.get("run_id") or "") == run_id]
    return rows or [row for row in turn_rows[-80:] if isinstance(row, Mapping)]


def _run_summary(rows: List[Mapping[str, Any]], summaries: List[Mapping[str, Any]]) -> Dict[str, Any]:
    actions = Counter(str(((row.get("action") if isinstance(row.get("action"), Mapping) else {}) or {}).get("type") or "unknown") for row in rows)
    rewards = [safe_float((row.get("outcome") or {}).get("reward")) for row in rows if isinstance(row.get("outcome"), Mapping)]
    races = [row for row in rows if str(((row.get("action") or {}) if isinstance(row.get("action"), Mapping) else {}).get("type") or "").lower() == "race"]
    race_wins = 0
    for row in races:
        outcome = row.get("outcome") if isinstance(row.get("outcome"), Mapping) else {}
        race_result = outcome.get("race_result") if isinstance(outcome.get("race_result"), Mapping) else {}
        if safe_int(race_result.get("rank") or race_result.get("result_rank"), 99) == 1:
            race_wins += 1
    latest_summary = summaries[-1] if summaries else {}
    return {
        "run_id": str((rows[-1] or {}).get("run_id") or (latest_summary or {}).get("run_id") or ""),
        "scenario_id": safe_int((rows[-1] or {}).get("scenario_id") or (latest_summary or {}).get("scenario_id")),
        "turns": len(rows),
        "action_counts": dict(actions),
        "reward_total": round(sum(rewards), 3),
        "reward_avg": round(sum(rewards) / max(1, len(rewards)), 3),
        "race_count": len(races),
        "race_win_rate": round(race_wins / max(1, len(races)), 4) if races else 0.0,
        "final_status": latest_summary.get("status") if isinstance(latest_summary, Mapping) else "",
        "final_stats": (latest_summary.get("final_stats") or {}) if isinstance(latest_summary, Mapping) else {},
        "final_fans": safe_int((latest_summary or {}).get("final_fans") if isinstance(latest_summary, Mapping) else 0),
    }


def test_connection(base_dir: Any, *, post_fn: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    cfg = load_config(base_dir)
    if not cfg.get("base_url"):
        return {"success": False, "detail": "Base URL is required.", "config": _redact_config(cfg)}
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": 'Return exactly JSON: {"ok":true,"label":"local_llm_ready"}'},
    ]
    try:
        raw, elapsed_ms = _request_chat(cfg, messages, post_fn=post_fn)
        text = _extract_message_text(raw)
        parsed = parse_jsonish(text)
        status = {
            "success": True,
            "checked_at": now_iso(),
            "elapsed_ms": elapsed_ms,
            "provider": cfg.get("provider"),
            "base_url": cfg.get("base_url"),
            "model": cfg.get("model"),
            "reply": parsed or {"raw_text": text[:500]},
        }
        _atomic_write_json(ai_root(base_dir) / STATUS_FILE, status)
        return status
    except Exception as exc:
        status = {
            "success": False,
            "checked_at": now_iso(),
            "provider": cfg.get("provider"),
            "base_url": cfg.get("base_url"),
            "model": cfg.get("model"),
            "detail": f"{type(exc).__name__}: {exc}",
        }
        _atomic_write_json(ai_root(base_dir) / STATUS_FILE, status)
        return status


def analyze_latest_run(base_dir: Any, *, post_fn: Optional[Callable[..., Any]] = None, force: bool = False) -> Dict[str, Any]:
    cfg = load_config(base_dir)
    if not force and (not cfg.get("enabled") or cfg.get("mode") == "off"):
        return {"success": False, "detail": "Local LLM is disabled. Enable it or use force for a manual test.", "config": _redact_config(cfg)}
    turn_rows = load_turn_rows(base_dir, limit=max(500, safe_int(cfg.get("max_turns_per_prompt"), 80) * 4))
    summaries = load_career_summaries(base_dir, limit=50)
    rows = _latest_run_rows(turn_rows)
    if not rows:
        return {"success": False, "detail": "No AI turn-decision rows found. Rebuild the AI dataset after completed careers."}
    max_turns = safe_int(cfg.get("max_turns_per_prompt"), 80)
    compact_rows = [_compact_turn(row) for row in rows[-max_turns:]]
    packet = {
        "task": "post_run_analysis",
        "rules": [
            "Return JSON only.",
            "Do not recommend direct bot commands or clicks.",
            "Suggest repeatable rules for Shadow Mode, not automatic overrides.",
        ],
        "summary": _run_summary(list(rows), summaries),
        "recent_turns": compact_rows,
    }
    packet = _fit_recent_turns_to_budget(packet)
    compact_rows = list(packet.get("recent_turns") or [])
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": json.dumps(packet, ensure_ascii=False, default=_json_default)},
    ]
    try:
        raw, elapsed_ms = _request_chat(cfg, messages, post_fn=post_fn)
        text = _extract_message_text(raw)
        parsed = normalize_analysis_payload(text)
        row = {
            "version": LOCAL_LLM_VERSION,
            "created_at": now_iso(),
            "kind": "post_run_analysis",
            "provider": cfg.get("provider"),
            "base_url": cfg.get("base_url"),
            "model": cfg.get("model"),
            "elapsed_ms": elapsed_ms,
            "run_id": packet["summary"].get("run_id"),
            "turns_sent": len(compact_rows),
            "analysis": parsed,
            "raw_text": text[:4000] if parsed.get("raw_text") else "",
        }
        _append_jsonl(ai_root(base_dir) / SUMMARY_FILE, row)
        _atomic_write_json(ai_root(base_dir) / "latest_llm_run_summary.json", row)
        return {"success": True, **row}
    except Exception as exc:
        return {"success": False, "detail": f"{type(exc).__name__}: {exc}", "config": _redact_config(cfg)}


def shadow_advice(base_dir: Any, *, post_fn: Optional[Callable[..., Any]] = None, force: bool = False, limit: int = 12) -> Dict[str, Any]:
    cfg = load_config(base_dir)
    if not force and (not cfg.get("enabled") or cfg.get("mode") not in {"shadow", "recommend"}):
        return {"success": False, "detail": "Local LLM shadow advice requires Shadow Advisor or Recommend Only mode.", "config": _redact_config(cfg)}
    turn_rows = load_turn_rows(base_dir, limit=max(50, limit * 4))
    rows = [row for row in turn_rows[-max(1, limit):] if isinstance(row, Mapping)]
    if not rows:
        return {"success": False, "detail": "No recent AI turn-decision rows found."}
    packet = {
        "task": "shadow_turn_review",
        "rules": [
            "Return JSON only.",
            "Use action_preference only as advisory text.",
            "No direct execution instructions.",
        ],
        "turns": [_compact_turn(row) for row in rows],
    }
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": json.dumps(packet, ensure_ascii=False, default=_json_default)},
    ]
    try:
        raw, elapsed_ms = _request_chat(cfg, messages, post_fn=post_fn)
        text = _extract_message_text(raw)
        parsed = normalize_advice_payload(text)
        row = {
            "version": LOCAL_LLM_VERSION,
            "created_at": now_iso(),
            "kind": "shadow_turn_review",
            "provider": cfg.get("provider"),
            "base_url": cfg.get("base_url"),
            "model": cfg.get("model"),
            "elapsed_ms": elapsed_ms,
            "turns_sent": len(rows),
            "advice": parsed,
            "raw_text": text[:4000] if parsed.get("raw_text") else "",
        }
        _append_jsonl(ai_root(base_dir) / ADVICE_FILE, row)
        _atomic_write_json(ai_root(base_dir) / "latest_llm_advice.json", row)
        return {"success": True, **row}
    except Exception as exc:
        return {"success": False, "detail": f"{type(exc).__name__}: {exc}", "config": _redact_config(cfg)}


def latest_payload(base_dir: Any) -> Dict[str, Any]:
    root = ai_root(base_dir)
    cfg = load_config(base_dir)
    latest_summary = _read_json(root / "latest_llm_run_summary.json", {})
    latest_advice = _read_json(root / "latest_llm_advice.json", {})
    status = _read_json(root / STATUS_FILE, {})
    return {
        "success": True,
        "version": LOCAL_LLM_VERSION,
        "config": _redact_config(cfg),
        "status": status if isinstance(status, dict) else {},
        "latest_summary": latest_summary if isinstance(latest_summary, dict) else {},
        "latest_advice": latest_advice if isinstance(latest_advice, dict) else {},
        "artifacts": {
            "config": str(root / CONFIG_FILE),
            "status": str(root / STATUS_FILE),
            "advice": str(root / ADVICE_FILE),
            "summaries": str(root / SUMMARY_FILE),
        },
    }


def dashboard_summary(base_dir: Any) -> Dict[str, Any]:
    payload = latest_payload(base_dir)
    cfg = payload.get("config") or {}
    status = payload.get("status") or {}
    latest_summary = payload.get("latest_summary") or {}
    latest_advice = payload.get("latest_advice") or {}
    analysis = latest_summary.get("analysis") if isinstance(latest_summary.get("analysis"), Mapping) else {}
    advice = latest_advice.get("advice") if isinstance(latest_advice.get("advice"), Mapping) else {}
    return {
        "enabled": bool(cfg.get("enabled")),
        "mode": cfg.get("mode"),
        "provider": cfg.get("provider"),
        "base_url": cfg.get("base_url"),
        "model": cfg.get("model"),
        "last_connection_success": bool(status.get("success")) if status else False,
        "last_connection_at": status.get("checked_at") if isinstance(status, Mapping) else "",
        "last_summary_at": latest_summary.get("created_at") if isinstance(latest_summary, Mapping) else "",
        "last_advice_at": latest_advice.get("created_at") if isinstance(latest_advice, Mapping) else "",
        "summary_headline": str(analysis.get("summary") or analysis.get("headline") or analysis.get("overall_assessment") or "")[:300] if isinstance(analysis, Mapping) else "",
        "risk_flags": (analysis.get("risk_flags") or analysis.get("risks") or [])[:6] if isinstance(analysis, Mapping) and isinstance((analysis.get("risk_flags") or analysis.get("risks") or []), list) else [],
        "candidate_rules": (analysis.get("candidate_rules") or analysis.get("suggested_rules") or [])[:5] if isinstance(analysis, Mapping) and isinstance((analysis.get("candidate_rules") or analysis.get("suggested_rules") or []), list) else [],
        "shadow_recommendation": str(advice.get("recommendation") or advice.get("action_preference") or advice.get("summary") or "")[:300] if isinstance(advice, Mapping) else "",
    }
