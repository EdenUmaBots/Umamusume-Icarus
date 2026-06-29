"""Launch, health-check, and supervise multiple Icarus instances.

Example accounts.json:
[
  {"name": "main", "port": 1616, "auto_restart": true, "stale_restart_seconds": 900},
  {"name": "alt", "port": 1617, "auto_restart": true}
]
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def resolve_userdata_dir():
    """Resolve the userdata folder the dashboard uses, so the manager reads the
    SAME accounts.json the UI writes.

    Mirrors main.py's resolution order. When the manager is launched from the
    dashboard, ICARUS_USERDATA_DIR is set explicitly for an exact match;
    otherwise we fall back through the same env vars / pointer files / sibling
    folders main.py checks. Without this the manager would read a stale or
    sample accounts.json from the build folder while the dashboard writes the
    real roster to the (usually external) userdata folder.
    """
    for env_name in ("ICARUS_USERDATA_DIR", "SWEEPYCL_USERDATA_DIR", "SWEEPYCLAUDE_USERDATA_DIR"):
        v = (os.environ.get(env_name) or "").strip()
        if v:
            try:
                p = Path(v).expanduser()
                if p.is_dir():
                    return p
            except Exception:
                pass
    for pointer_dir in (Path.home() / ".icarus", Path.home() / ".sweepycl"):
        try:
            ptr = pointer_dir / "userdata_pointer.json"
            if ptr.exists():
                target = (json.loads(ptr.read_text(encoding="utf-8")).get("userdata_path") or "").strip()
                if target and Path(target).expanduser().is_dir():
                    return Path(target).expanduser()
        except Exception:
            pass
    for sibling in ("Icarus_userdata", "SweepyCL_userdata", "SweepyClaude_userdata"):
        cand = ROOT.parent / sibling
        if cand.is_dir():
            return cand
    return ROOT


USERDATA = resolve_userdata_dir()
ACCOUNTS = USERDATA / "accounts.json"
RUNTIME = ROOT / "uma_runtime"
LOG_DIR = RUNTIME / "manager_logs"
STATUS_PATH = RUNTIME / "manager_status.json"

# Ceiling on supervisor restarts per child in a rolling 1h window. A bricked
# instance (e.g. main.py fails at startup) would otherwise restart-loop forever;
# once this is hit the child is marked failed and left dead instead.
MAX_RESTARTS_PER_HOUR = 10


def load_accounts():
    if not ACCOUNTS.exists():
        sample = [
            {"name": "main", "port": 1616, "auto_restart": True, "stale_restart_seconds": 900},
            {"name": "alt", "port": 1617, "auto_restart": True, "stale_restart_seconds": 900},
        ]
        ACCOUNTS.write_text(json.dumps(sample, indent=2), encoding="utf-8")
        print(f"Created {ACCOUNTS}. Edit it, then run manager.py again.")
        return []
    try:
        data = json.loads(ACCOUNTS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        backup = ACCOUNTS.with_suffix(ACCOUNTS.suffix + f".bad-{int(time.time())}")
        try:
            ACCOUNTS.replace(backup)
        except Exception:
            pass
        raise SystemExit(
            f"accounts.json is invalid JSON ({exc}); moved it to {backup.name}. "
            f"Fix the file and rerun the manager."
        )
    if not isinstance(data, list):
        raise SystemExit("accounts.json must be a list of account objects")
    return data


def safe_name(value):
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(value or "default")).strip("_") or "default"


def atomic_write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def write_instance_config(account):
    name = safe_name(account.get("name") or "default")
    port = int(account.get("port") or 1616)
    path = ROOT / f"{name}.json"
    current = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            backup = path.with_suffix(path.suffix + f".bad-{int(time.time())}")
            path.replace(backup)
            print(f"Invalid JSON in {path.name}; moved it to {backup.name}")
            current = {}
    current.update(account)
    current["name"] = name
    current["port"] = port
    atomic_write_json(path, current)
    return path, port


def start_child(account):
    cfg, port = write_instance_config(account)
    env = os.environ.copy()
    # Children must resolve the same userdata folder as the dashboard/manager so
    # each per-account profile reads/writes its auth under the shared userdata
    # (auth is isolated per-profile inside it). Inherited from the dashboard when
    # set; otherwise pin it to the folder the manager resolved.
    if not env.get("ICARUS_USERDATA_DIR"):
        env["ICARUS_USERDATA_DIR"] = str(USERDATA)
    if account.get("stuck_turn_threshold"):
        env["UMA_STUCK_TURN_THRESHOLD"] = str(account.get("stuck_turn_threshold"))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{cfg.stem}.log"
    log = log_path.open("a", encoding="utf-8", buffering=1)
    log.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} port={port} ---\n")
    cmd = [sys.executable, "main.py", str(cfg)]
    print(f"Starting {cfg.stem} on http://127.0.0.1:{port}  log={log_path}")
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    return {
        "account": account,
        "config": cfg,
        "port": port,
        "proc": proc,
        "log": log,
        "log_path": str(log_path),
        "restarts": 0,
        "last_start": time.time(),
        "last_health": {},
        "last_health_at": 0,
        "last_health_error": "",
    }


def fetch_health(port: int, timeout: float = 6.0):
    url = f"http://127.0.0.1:{port}/api/health"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def stop_child(child, kill_after=6):
    proc = child["proc"]
    if proc.poll() is None:
        proc.terminate()
        deadline = time.time() + kill_after
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.25)
    if proc.poll() is None:
        proc.kill()
    try:
        child["log"].close()
    except Exception:
        pass


def restart_child(children, child, reason: str):
    account = child["account"]
    name = child["config"].stem
    now = time.time()
    times = child.setdefault("restart_times", [])
    times[:] = [t for t in times if now - t < 3600]
    if len(times) >= MAX_RESTARTS_PER_HOUR:
        child["failed"] = True
        child["fail_reason"] = (
            f"hit the {MAX_RESTARTS_PER_HOUR} restarts/hour ceiling -- instance is "
            f"likely bricked at startup; halting to avoid a restart flood"
        )
        print(f"{name}: {child['fail_reason']}")
        stop_child(child)
        return
    print(f"Restarting {name}: {reason}")
    stop_child(child)
    child["restarts"] += 1
    times.append(now)
    delay = min(180, 5 * (2 ** min(child["restarts"] - 1, 5)))
    time.sleep(delay)
    replacement = start_child(account)
    replacement["restarts"] = child["restarts"]
    replacement["restart_times"] = times
    replacement["failed"] = False
    replacement.pop("fail_reason", None)
    children[children.index(child)] = replacement


def write_status(children):
    rows = []
    now = time.time()
    for child in children:
        proc = child["proc"]
        restart_times = [t for t in child.get("restart_times", []) if now - t < 3600]
        rows.append({
            "name": child["config"].stem,
            "port": child["port"],
            "pid": proc.pid,
            "running": proc.poll() is None,
            "returncode": proc.returncode,
            "restarts": child["restarts"],
            "restarts_last_hour": len(restart_times),
            "failed": bool(child.get("failed")),
            "fail_reason": child.get("fail_reason", ""),
            "last_start": child["last_start"],
            "last_health_at": child.get("last_health_at", 0),
            "last_health_error": child.get("last_health_error", ""),
            "last_health": child.get("last_health", {}),
            "log_path": child.get("log_path", ""),
        })
    atomic_write_json(STATUS_PATH, {"updated_at": now, "children": rows})


def main():
    accounts = load_accounts()
    if not accounts:
        return 1
    children = [start_child(account) for account in accounts]
    stopping = False

    def stop_all(*_):
        nonlocal stopping
        stopping = True
        print("Stopping bot instances...")
        for child in list(children):
            stop_child(child)
        write_status(children)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    while True:
        for child in list(children):
            proc = child["proc"]
            account = child["account"]
            auto_restart = bool(account.get("auto_restart", True))
            name = child["config"].stem

            if proc.poll() is not None:
                runtime = time.time() - child["last_start"]
                print(f"{name} exited with code {proc.returncode} after {int(runtime)}s")
                try:
                    child["log"].close()
                except Exception:
                    pass
                if child.get("failed"):
                    # Already marked failed (e.g. restart budget exhausted) -- leave
                    # it dead rather than retrying every loop tick.
                    continue
                if stopping or not auto_restart:
                    children.remove(child)
                    continue
                restart_child(children, child, f"process exited code={proc.returncode}")
                continue

            interval = int(account.get("health_check_interval_seconds") or 30)
            if time.time() - float(child.get("last_health_at") or 0) >= interval:
                try:
                    health = fetch_health(child["port"])
                    child["last_health"] = health
                    child["last_health_error"] = ""
                    child["last_health_at"] = time.time()
                    stale_limit = int(account.get("stale_restart_seconds") or 0)
                    stale = int(health.get("runner_stale_seconds") or 0)
                    runner_running = bool(health.get("runner_running"))
                    # Opt-in: restart an instance whose runner crashed. The process
                    # stays alive on a career crash, so the supervisor would otherwise
                    # never restart it (it only restarts on process death). Off by
                    # default to avoid surprise restart loops.
                    if (auto_restart and account.get("restart_on_runner_crash")
                            and health.get("runner_crashed")):
                        restart_child(children, child, f"runner crashed: {str(health.get('runner_last_error', ''))[:120]}")
                    # Only stale-restart an actually running runner. A logged-in idle dashboard
                    # should not be treated as timed out.
                    elif auto_restart and stale_limit > 0 and runner_running and stale >= stale_limit:
                        restart_child(children, child, f"runner stale for {stale}s")
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                    child["last_health_error"] = str(exc)
                    child["last_health_at"] = time.time()
                    grace = int(account.get("startup_grace_seconds") or 120)
                    if auto_restart and (time.time() - child["last_start"]) > grace:
                        failures = int(child.setdefault("health_failures", 0)) + 1
                        child["health_failures"] = failures
                        if failures >= int(account.get("health_failure_restart_count") or 5):
                            restart_child(children, child, f"health endpoint failed {failures} times: {exc}")
                    continue
                child["health_failures"] = 0

        write_status(children)
        if not children:
            return 0
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
