"""Runtime diagnostics helpers for Icarus.

These helpers intentionally read only bot-owned files under uma_runtime. They do
not inspect game memory, protected traffic, or client files.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List


MAX_TEXT_BYTES = 750_000


def runtime_root(base_dir: str | os.PathLike[str]) -> Path:
    override = os.environ.get("UMA_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(base_dir).resolve() / "uma_runtime"


def _safe_read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": str(exc), "_path": str(path)}


def _tail_lines(path: Path, limit: int = 80) -> List[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-limit:]
    except Exception as exc:
        return [f"<unable to read {path.name}: {exc}>"]


def _latest_file(paths: Iterable[Path]) -> Path | None:
    candidates = [p for p in paths if p.exists() and p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def snapshot_summary(base_dir: str | os.PathLike[str], limit: int = 200) -> Dict[str, Any]:
    root = runtime_root(base_dir)
    snap_dir = root / "state_snapshots"
    latest = _latest_file(snap_dir.glob("*.jsonl")) if snap_dir.exists() else None
    if not latest:
        return {"exists": False, "rows": 0, "summary": {}}

    rows = []
    try:
        raw = latest.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, min(limit, 2000)):]
        for line in raw:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    except Exception as exc:
        return {"exists": True, "path": str(latest), "error": str(exc), "rows": 0, "summary": {}}

    turns = [int(r.get("turn") or 0) for r in rows if isinstance(r, dict)]
    fans = [int(r.get("fans") or 0) for r in rows if isinstance(r, dict)]
    vitals = [int(r.get("vital") or 0) for r in rows if isinstance(r, dict)]
    summary = {
        "first_turn": turns[0] if turns else 0,
        "last_turn": turns[-1] if turns else 0,
        "max_turn": max(turns) if turns else 0,
        "first_fans": fans[0] if fans else 0,
        "last_fans": fans[-1] if fans else 0,
        "fan_delta_in_window": max(0, (fans[-1] - fans[0])) if len(fans) >= 2 else 0,
        "last_vital": vitals[-1] if vitals else 0,
        "unique_turns_in_window": len(set(turns)),
    }
    return {"exists": True, "path": str(latest), "mtime": latest.stat().st_mtime, "rows": len(rows), "summary": summary}


def build_summary(base_dir: str | os.PathLike[str], runner: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base = Path(base_dir)
    root = runtime_root(base)
    report_dir = root / "bot_logs"
    latest_report = _latest_file(report_dir.glob("*.json")) if report_dir.exists() else None
    manager_log_dir = root.parent / "manager_logs"
    manager_logs = sorted(manager_log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:5] if manager_log_dir.exists() else []

    return {
        "success": True,
        "generated_at": time.time(),
        "runtime_root": str(root),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "runner": runner or {},
        "snapshot": snapshot_summary(base),
        "latest_report": str(latest_report) if latest_report else "",
        "latest_report_mtime": latest_report.stat().st_mtime if latest_report else 0,
        "manager_logs": [str(p) for p in manager_logs],
        "settings_exists": (base / "settings.json").exists(),
        "accounts_exists": (base / "accounts.json").exists(),
    }


def create_bundle(base_dir: str | os.PathLike[str], runner: Dict[str, Any] | None = None) -> Path:
    base = Path(base_dir)
    root = runtime_root(base)
    out_dir = root / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"diagnostics-{stamp}.zip"
    summary = build_summary(base, runner)

    def add_text(zf: zipfile.ZipFile, name: str, text: str):
        zf.writestr(name, text[:MAX_TEXT_BYTES])

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        add_text(zf, "summary.json", json.dumps(summary, indent=2, ensure_ascii=False))
        for rel in ["IMPROVEMENTS.md", "README.md", "settings.json", "accounts.json"]:
            path = base / rel
            if path.exists() and path.is_file():
                add_text(zf, rel, path.read_text(encoding="utf-8", errors="replace"))
        latest_snap = _latest_file((root / "state_snapshots").glob("*.jsonl")) if (root / "state_snapshots").exists() else None
        if latest_snap:
            add_text(zf, f"state_snapshots/{latest_snap.name}.tail.txt", "\n".join(_tail_lines(latest_snap, 300)))
        latest_report = _latest_file((root / "bot_logs").glob("*.json")) if (root / "bot_logs").exists() else None
        if latest_report:
            add_text(zf, f"bot_logs/{latest_report.name}", latest_report.read_text(encoding="utf-8", errors="replace"))
        manager_dir = root.parent / "manager_logs"
        if manager_dir.exists():
            for log in sorted(manager_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]:
                add_text(zf, f"manager_logs/{log.name}.tail.txt", "\n".join(_tail_lines(log, 300)))
    return out
