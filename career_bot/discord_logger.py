"""Discord webhook telemetry exporter for career logs.

Sends sanitized JSONL-style career telemetry to Discord for analysis/model-data
collection. Local JSONL is written even when webhook sending is disabled.
"""
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SENSITIVE_KEY_RE = re.compile(
    r"(steam|session|ticket|token|password|viewer_id|owner_viewer_id|device|ip_address|auth|credential)",
    re.I,
)

DEFAULT_CONFIG = {
    "enabled": False,
    "webhook_url": "",
    "send_turn_logs": True,
    "send_career_summary": True,
    # User-facing notify toggles (Discord modal). finish/crash default ON to keep
    # the prior "send on career end" behavior; epithet is a new opt-in milestone.
    "notify_on_finish": True,
    "notify_on_crash": True,
    "notify_on_epithet": False,
    "batch_size": 10,
    "flush_interval_seconds": 20,
    "redact_sensitive": True,
    "username": "Uma Career Telemetry",
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_config(base_dir: str | Path) -> dict[str, Any]:
    base = Path(base_dir)
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(_load_json(base / "data" / "discord_logging.json"))

    settings = _load_json(base / "settings.json")
    if isinstance(settings.get("discord_logging"), dict):
        cfg.update(settings["discord_logging"])

    env_url = os.environ.get("UMA_DISCORD_WEBHOOK_URL")
    if env_url:
        cfg["webhook_url"] = env_url
        cfg["enabled"] = True

    env_enabled = os.environ.get("UMA_DISCORD_LOGGING")
    if env_enabled is not None:
        cfg["enabled"] = str(env_enabled).strip().lower() in {"1", "true", "yes", "on"}

    for key in ["send_turn_logs", "send_career_summary", "redact_sensitive",
                "notify_on_finish", "notify_on_crash", "notify_on_epithet"]:
        cfg[key] = bool(cfg.get(key, DEFAULT_CONFIG[key]))

    for key, default in [("batch_size", 10), ("flush_interval_seconds", 20)]:
        try:
            cfg[key] = max(1, int(cfg.get(key, default)))
        except Exception:
            cfg[key] = default

    return cfg


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "[truncated]"
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_KEY_RE.search(key_text):
                out[key_text] = "[redacted]"
            else:
                out[key_text] = sanitize(item, depth + 1)
        return out
    if isinstance(value, list):
        return [sanitize(item, depth + 1) for item in value[:200]]
    if isinstance(value, str):
        value = re.sub(r"https://discord(?:app)?\.com/api/webhooks/[^\s]+", "[redacted_webhook]", value)
        value = re.sub(r"\b[A-Za-z0-9_\-]{48,}\b", "[redacted_token]", value)
        return value[:3000] + ("...[truncated]" if len(value) > 3000 else "")
    return value


class DiscordCareerLogger:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.config = load_config(self.base_dir)
        self.enabled = bool(self.config.get("enabled") and self.config.get("webhook_url"))
        self.queue: "queue.Queue[dict[str, Any] | None]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.buffer: list[dict[str, Any]] = []
        self.last_flush = time.time()
        self.run_id = ""
        self.local_jsonl = None

        if self.enabled:
            self.worker = threading.Thread(target=self._worker, daemon=True)
            self.worker.start()

    def start_career(self, run_id: str, preset: dict[str, Any] | None = None, status: dict[str, Any] | None = None):
        self.run_id = str(run_id or "")
        self._open_local_jsonl()
        self.emit({
            "type": "career_start",
            "run_id": self.run_id,
            "ts": time.time(),
            "preset": {
                "name": (preset or {}).get("name"),
                "scenario_id": (preset or {}).get("scenario_id") or (preset or {}).get("scenario"),
                "strategy_mode": (preset or {}).get("strategy_mode"),
            },
            "status": status or {},
        }, immediate=True)

    def emit_turn(self, row: dict[str, Any]):
        if not self.config.get("send_turn_logs", True):
            return
        payload = dict(row or {})
        payload.setdefault("type", "turn")
        payload.setdefault("run_id", self.run_id)
        payload.setdefault("ts", time.time())
        self.emit(payload)

    def finish_career(self, summary: dict[str, Any]):
        # Route to the right user-facing notify toggle: a crash/stuck end (carries
        # last_error) -> notify_on_crash; a clean finish -> notify_on_finish (AND
        # the legacy send_career_summary telemetry switch). Either path emits the
        # same summary payload, just typed + gated differently.
        payload = dict(summary or {})
        last_error = str(payload.get("last_error") or "").strip()
        if last_error:
            if self.config.get("notify_on_crash", True):
                payload.setdefault("type", "career_crash")
                payload.setdefault("run_id", self.run_id)
                payload.setdefault("ts", time.time())
                self.emit(payload, immediate=True)
        elif self.config.get("notify_on_finish", True) and self.config.get("send_career_summary", True):
            payload.setdefault("type", "career_summary")
            payload.setdefault("run_id", self.run_id)
            payload.setdefault("ts", time.time())
            self.emit(payload, immediate=True)
        self.flush()
        self.close()

    def notify_epithet(self, names, detail: str = ""):
        """Milestone ping when one or more set-bonus epithets are newly earned.
        Gated by notify_on_epithet (default off). No-op when the list is empty."""
        names = [str(n).strip() for n in (names or []) if str(n).strip()]
        if not names or not self.config.get("notify_on_epithet", False):
            return
        payload = {"type": "epithet_earned", "run_id": self.run_id,
                   "ts": time.time(), "epithets": names}
        if detail:
            payload["detail"] = detail
        self.emit(payload, immediate=True)

    def emit(self, event: dict[str, Any], immediate: bool = False):
        safe = sanitize(event) if self.config.get("redact_sensitive", True) else event
        self._write_local(safe)
        if not self.enabled:
            return
        if immediate:
            self._flush_buffer()
            self._send_batch([safe])
        else:
            self.queue.put(safe)

    def flush(self):
        if self.enabled:
            self.queue.put({"type": "_flush"})

    def close(self):
        try:
            self.flush()
            if self.enabled:
                self.queue.put(None)
        except Exception:
            pass
        try:
            if self.local_jsonl:
                self.local_jsonl.close()
        except Exception:
            pass

    def _open_local_jsonl(self):
        try:
            runtime = Path(os.environ.get("UMA_RUNTIME_DIR") or (self.base_dir / "uma_runtime"))
            out = runtime / "discord_telemetry"
            out.mkdir(parents=True, exist_ok=True)
            name = self.run_id or time.strftime("%Y%m%d-%H%M%S")
            self.local_jsonl = (out / f"{name}.jsonl").open("a", encoding="utf-8")
        except Exception:
            self.local_jsonl = None

    def _write_local(self, event: dict[str, Any]):
        if not self.local_jsonl:
            return
        try:
            self.local_jsonl.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            self.local_jsonl.flush()
        except Exception:
            pass

    def _worker(self):
        while True:
            try:
                item = self.queue.get(timeout=1.0)
            except queue.Empty:
                item = {"type": "_tick"}

            if item is None:
                self._flush_buffer()
                return

            if item.get("type") == "_flush":
                self._flush_buffer()
                continue

            if item.get("type") != "_tick":
                self.buffer.append(item)

            batch_size = int(self.config.get("batch_size") or 10)
            flush_interval = int(self.config.get("flush_interval_seconds") or 20)
            if len(self.buffer) >= batch_size or (self.buffer and time.time() - self.last_flush >= flush_interval):
                self._flush_buffer()

    def _flush_buffer(self):
        if not self.buffer:
            return
        batch = self.buffer[:]
        self.buffer.clear()
        self.last_flush = time.time()
        self._send_batch(batch)

    def _send_batch(self, events: list[dict[str, Any]]):
        if not self.enabled or not events:
            return
        text = "\n".join(json.dumps(event, ensure_ascii=False, default=str) for event in events)
        if len(text) <= 1800:
            self._post_json({
                "username": self.config.get("username") or DEFAULT_CONFIG["username"],
                "content": f"```json\n{text}\n```",
            })
        else:
            self._post_file(text.encode("utf-8"), f"uma-career-{self.run_id or int(time.time())}.jsonl")

    def _post_json(self, payload: dict[str, Any]):
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            str(self.config.get("webhook_url")),
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "UmaTelemetry/1.0"},
            method="POST",
        )
        self._request_with_retries(req)

    def _post_file(self, data: bytes, filename: str):
        boundary = "----UmaTelemetryBoundary"
        body = []
        payload = json.dumps({"username": self.config.get("username") or DEFAULT_CONFIG["username"]})
        body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n\r\n{payload}\r\n".encode())
        body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"{filename}\"\r\nContent-Type: application/jsonl\r\n\r\n".encode())
        body.append(data)
        body.append(f"\r\n--{boundary}--\r\n".encode())
        req = Request(
            str(self.config.get("webhook_url")),
            data=b"".join(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "UmaTelemetry/1.0"},
            method="POST",
        )
        self._request_with_retries(req)

    def _request_with_retries(self, req: Request):
        for attempt in range(3):
            try:
                with urlopen(req, timeout=15) as res:
                    if 200 <= res.status < 300:
                        return
            except HTTPError as exc:
                if exc.code == 429:
                    try:
                        retry_after = json.loads(exc.read().decode("utf-8")).get("retry_after", 1)
                        time.sleep(float(retry_after) + 0.5)
                    except Exception:
                        time.sleep(2)
                    continue
                if attempt == 2:
                    return
            except (URLError, TimeoutError, OSError):
                if attempt == 2:
                    return
                time.sleep(2 * (attempt + 1))
