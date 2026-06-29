import os
import json
import re
import subprocess
import sys
import glob as _glob


def _check_required_packages():
    """Fail fast with a useful message instead of mutating the env on every launch."""
    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "frida": "frida",
        "pydantic": "pydantic",
        "msgpack": "msgpack",
        "requests": "requests",
    }
    missing = []
    for import_name, package_name in required.items():
        try:
            __import__(import_name)
        except Exception:
            missing.append(package_name)
    if missing:
        joined = ", ".join(sorted(set(missing)))
        raise RuntimeError(
            "Missing Python dependencies: " + joined +
            ". Install them once with: python -m pip install -r requirements.txt"
        )


_check_required_packages()

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
try:
    from career_bot import skill_intercept  # DEV-ONLY web skill-buy intercept (not for beta/public)
    _SKILL_INTERCEPT_AVAILABLE = True
except Exception:  # excluded from beta/public builds -> inert stub, feature absent
    _SKILL_INTERCEPT_AVAILABLE = False

    class skill_intercept:  # type: ignore
        @staticmethod
        def is_enabled():
            return False
        @staticmethod
        def get_pending():
            return None
        @staticmethod
        def set_enabled(_x):
            return False
        @staticmethod
        def submit_decision(_a, _i=None):
            return None
        @staticmethod
        def cancel():
            return None
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from pathlib import Path
from copy import deepcopy
import random
import time
import threading
import asyncio
import requests
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest, urlopen
import frida
from career_bot import master_data
from career_bot import trackblazer
from career_bot import diagnostics
from career_bot import ai_dataset, ai_advisor, ai_trainer, local_llm
from career_bot.config_store import ConfigStore
from career_bot.runner import CareerRunner, runtime_output_root
from career_bot.career_start_recovery import resume_career_fields
from career_bot.report import _build_version
from career_bot.item_helpers import (
    _coerce_int,
    _first_present,
    _item_id_from_payload,
    _item_count_from_payload,
    get_item_count,
    find_item_count,
)
from uma_api.client import UmaClient, get_ticket
from uma_api.career_recovery import is_career_in_progress_error, resume_active_career

PROCESS_NAME = "UmamusumePrettyDerby.exe"
APP_ID = "3224770"

JS_CODE = r"""
'use strict';
(function() {
    var buffers = {};
    var attached = {};
    function hex2(n) { return ('0' + (n & 255).toString(16)).slice(-2); }
    function uuidFromHex(h) {
        return h.substring(0, 8) + '-' + h.substring(8, 12) + '-' + h.substring(12, 16) + '-' + h.substring(16, 20) + '-' + h.substring(20);
    }
    function b64(s) {
        var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
        var out = [];
        var buffer = 0;
        var bits = 0;
        for (var i = 0; i < s.length; i++) {
            var c = s.charAt(i);
            if (c === '=') break;
            var idx = chars.indexOf(c);
            if (idx < 0) continue;
            buffer = (buffer << 6) | idx;
            bits += 6;
            if (bits >= 8) {
                bits -= 8;
                out.push((buffer >> bits) & 255);
            }
        }
        return out;
    }
    function parseWire(endpoint, viewerId, body, appVer, resVer) {
        var decoded = b64(body);
        if (decoded.length < 140) return;
        var headerLen = decoded[0] | (decoded[1] << 8) | (decoded[2] << 16) | (decoded[3] << 24);
        var blob1End = 4 + headerLen;
        if (headerLen < 120 || headerLen > 2048 || decoded.length < blob1End) return;
        
        var udidHex = '';
        for (var i = blob1End - 96; i < blob1End - 80; i++) udidHex += hex2(decoded[i]);
        var authHex = '';
        for (var j = blob1End - 48; j < blob1End; j++) authHex += hex2(decoded[j]);
        
        if (!viewerId || !authHex || authHex.length < 64 || udidHex.length !== 32) return;
        
        send({
            type: 'creds',
            endpoint: endpoint,
            viewer_id: parseInt(viewerId, 10),
            udid: uuidFromHex(udidHex),
            auth_key: authHex,
            auth_key_len: authHex.length / 2,
            app_ver: appVer,
            res_ver: resVer,
            body: body
        });
    }
    function parseHttp(text) {
        if (text.indexOf('/umamusume/') < 0) return;
        var em = text.match(/POST\s+\/umamusume\/([^\s]+)\s+HTTP/i);
        var vm = text.match(/(?:^|\r\n)(?:ViewerID|ViewerId):\s*(\d+)/i);
        var appVer = text.match(/(?:^|\r\n)APP-VER:\s*([^\r\n]+)/i);
        var resVer = text.match(/(?:^|\r\n)RES-VER:\s*([^\r\n]+)/i);
        var idx = text.indexOf('\r\n\r\n');
        if (!em || !vm || idx < 0) return;
        parseWire(em[1], vm[1], text.substring(idx + 4), appVer ? appVer[1].trim() : '', resVer ? resVer[1].trim() : '');
    }
    function parseChunk(key, chunk) {
        var buf = (buffers[key] || '') + chunk;
        if (buf.length > 2097152) buf = buf.substring(buf.length - 1048576);
        var start = buf.indexOf('POST ');
        if (start < 0) {
            buffers[key] = buf.slice(-4096);
            return;
        }
        if (start > 0) buf = buf.substring(start);
        var headerEnd = buf.indexOf('\r\n\r\n');
        if (headerEnd < 0) {
            buffers[key] = buf;
            return;
        }
        var headers = buf.substring(0, headerEnd);
        var lm = headers.match(/Content-Length:\s*(\d+)/i);
        var length = lm ? parseInt(lm[1], 10) : 0;
        var total = headerEnd + 4 + length;
        if (length > 0 && buf.length < total) {
            buffers[key] = buf;
            return;
        }
        parseHttp(length > 0 ? buf.substring(0, total) : buf);
        buffers[key] = buf.length > total ? buf.substring(total) : '';
    }
    function hookTls() {
        var ga = Process.findModuleByName('GameAssembly.dll');
        if (!ga) return false;
        var installFn = ga.findExportByName('il2cpp_unity_install_unitytls_interface');
        if (!installFn) return false;
        var rb = new Uint8Array(installFn.readByteArray(16));
        var realFn = installFn;
        if (rb[0] === 0xe9) {
            var off = rb[1] | (rb[2] << 8) | (rb[3] << 16) | (rb[4] << 24);
            if (off > 0x7fffffff) off -= 0x100000000;
            realFn = installFn.add(5 + off);
            rb = new Uint8Array(realFn.readByteArray(16));
        }
        var globalPtr = null;
        if (rb[0] === 0x48 && rb[1] === 0x89 && rb[2] === 0x0d) {
            var disp = rb[3] | (rb[4] << 8) | (rb[5] << 16) | (rb[6] << 24);
            if (disp > 0x7fffffff) disp -= 0x100000000;
            globalPtr = realFn.add(7 + disp);
        }
        if (!globalPtr) return false;
        var iface = globalPtr.readPointer();
        if (!iface || iface.isNull()) return false;
        var hookedTls = 0;
        [0xd0, 0xd8, 0xe0, 0xe8].forEach(function(off) {
            var addr = iface.add(off).readPointer();
            if (!addr || addr.isNull()) return;
            var key = 'tls_' + addr.toString();
            if (attached[key]) return;
            try {
                Interceptor.attach(addr, {
                    onEnter: function(args) {
                        var len = args[2].toInt32();
                        if (len <= 0 || len > 1048576 || args[1].isNull()) return;
                        try {
                            var bytes = args[1].readByteArray(len);
                            var u8 = new Uint8Array(bytes);
                            var s = '';
                            for (var i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
                            parseChunk(args[0].toString(), s);
                        } catch (e) {}
                    }
                });
                attached[key] = true;
                hookedTls++;
            } catch (e) {}
        });
        return hookedTls > 0;
    }
    var tlsDone = false;
    var timer = setInterval(function() {
        try {
            if (!tlsDone) tlsDone = hookTls();
            if (tlsDone) clearInterval(timer);
        } catch (e) {}
    }, 1000);
})();
"""


DIR = os.path.dirname(os.path.abspath(__file__))


def _userdata_pointer_dir():
    """OS-user-scoped directory holding the cross-version userdata pointer.

    Lives at ``~/.icarus`` on every OS (with ``~/.sweepycl`` honored as a
    legacy fallback for reads). Independent of the build folder so a fresh
    install can find the userdata path the user configured under a previous
    version, even if they didn't overwrite the old build.
    """
    return Path.home() / ".icarus"


def _userdata_pointer_path():
    return _userdata_pointer_dir() / "userdata_pointer.json"


def _legacy_userdata_pointer_paths():
    # Older builds wrote the pointer under ~/.sweepycl; still read it so a
    # rebrand never orphans a user-configured userdata location.
    return [Path.home() / ".sweepycl" / "userdata_pointer.json"]


def _read_userdata_pointer():
    """Read the pointer file (primary, then legacy). Returns dict or empty."""
    for p in [_userdata_pointer_path(), *_legacy_userdata_pointer_paths()]:
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def _write_userdata_pointer(patch):
    """Merge ``patch`` into the pointer file. Creates the dir if needed."""
    p = _userdata_pointer_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        existing = _read_userdata_pointer()
        merged = {**existing, **(patch or {})}
        p.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return merged
    except Exception as exc:
        print(f"Icarus: writing userdata pointer failed: {exc}")
        return None


def _resolve_userdata_dir():
    """Return the directory holding user-customizable files that should
    persist across Pre Icarus version upgrades (presets, settings,
    accounts, steam token).

    Resolution order (v7.1 — adds the user-configurable pointer file):

      1. ``$SWEEPYCL_USERDATA_DIR`` -- explicit env var override (new name).
      2. ``$SWEEPYCLAUDE_USERDATA_DIR`` -- legacy env var, still honored.
      3. ``~/.sweepycl/userdata_pointer.json`` -- user-configured path set
         via the dashboard. Lives outside the build folder so a fresh
         install of a new version automatically picks up where the user
         told the previous version their data lives.
      4. ``<DIR>/../SweepyCL_userdata`` -- sibling folder convention.
      5. ``<DIR>/../SweepyClaude_userdata`` -- legacy sibling folder.
      6. Fallback: ``DIR`` itself (in-build paths).

    Also populates module-level ``USERDATA_SOURCE`` and
    ``USERDATA_DETECTION_WARNING`` so the dashboard can show the user
    where their data is coming from and whether anything looks off.
    """
    global USERDATA_SOURCE, USERDATA_DETECTION_WARNING
    USERDATA_SOURCE = "fallback_build_dir"
    USERDATA_DETECTION_WARNING = None

    # 1-2: env vars
    for env_name, source_label in (
        ("ICARUS_USERDATA_DIR", "env_icarus"),
        ("SWEEPYCL_USERDATA_DIR", "env_legacy_sweepycl"),
        ("SWEEPYCLAUDE_USERDATA_DIR", "env_legacy_sweepyclaude"),
    ):
        env = os.environ.get(env_name, "").strip()
        if env:
            try:
                p = Path(env).expanduser().resolve()
                p.mkdir(parents=True, exist_ok=True)
                USERDATA_SOURCE = source_label
                return str(p)
            except Exception as exc:
                print(f"Icarus: env {env_name} resolution failed: {exc}")
                USERDATA_DETECTION_WARNING = f"Env var {env_name} is set but failed to resolve: {exc}"

    # 3: cross-version pointer file
    pointer = _read_userdata_pointer()
    pointer_target = (pointer.get("userdata_path") or "").strip()
    if pointer_target:
        try:
            p = Path(pointer_target).expanduser().resolve()
            if p.exists() and p.is_dir():
                USERDATA_SOURCE = "pointer_file"
                return str(p)
            else:
                # The user configured a path under a previous install but it's
                # not reachable from this machine/install. This is exactly the
                # "can't detect previous userdata folder" case the popup
                # warns about.
                USERDATA_DETECTION_WARNING = (
                    f"Your saved userdata path ({p}) doesn't exist or isn't "
                    f"a folder. Settings will fall back to a default location "
                    f"until you fix this."
                )
        except Exception as exc:
            USERDATA_DETECTION_WARNING = f"Saved userdata path is invalid: {exc}"

    # 4-5: sibling folder conventions
    for sibling_name, source_label in (
        ("Icarus_userdata", "sibling_icarus"),
        ("SweepyCL_userdata", "sibling_legacy_sweepycl"),
        ("SweepyClaude_userdata", "sibling_legacy_sweepyclaude"),
    ):
        sibling = Path(DIR).parent / sibling_name
        if sibling.exists() and sibling.is_dir():
            USERDATA_SOURCE = source_label
            return str(sibling.resolve())

    # 6: fallback
    USERDATA_SOURCE = "fallback_build_dir"
    if not USERDATA_DETECTION_WARNING:
        USERDATA_DETECTION_WARNING = (
            "No userdata folder is configured. Settings will be saved inside "
            "the build folder, which means they'll be lost when you upgrade "
            "to a new version unless you overwrite the install."
        )
    return DIR


# Populated by _resolve_userdata_dir() below. Strings used by the dashboard.
USERDATA_SOURCE = "fallback_build_dir"
USERDATA_DETECTION_WARNING = None


USERDATA_DIR = _resolve_userdata_dir()


def _user_settings_path():
    return os.path.join(USERDATA_DIR, "settings.json")


def _user_accounts_path():
    return Path(USERDATA_DIR) / "accounts.json"


def _user_presets_dir():
    p = Path(USERDATA_DIR) / "data" / "presets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _user_steam_token_path(profile_name):
    p = Path(USERDATA_DIR) / "auth" / (profile_name or "default")
    p.mkdir(parents=True, exist_ok=True)
    return p / "steam_token.txt"


def _user_auth_config_path(profile_name):
    """Userdata location for the headless-bypass auth_config.json.

    v6.7.18: the v6.7.6 work only persisted steam_token.txt to userdata,
    but check_saved_auth() actually reads auth_config.json -- which was
    only ever written to RUNTIME_DIR (the build folder).  Since
    RUNTIME_DIR is wiped on every version upgrade, the headless bypass
    broke on upgrade and fell back to a manual Steam launch.  Persisting
    the full auth_config.json here lets the bypass survive upgrades.
    """
    p = Path(USERDATA_DIR) / "auth" / (profile_name or "default")
    p.mkdir(parents=True, exist_ok=True)
    return p / "auth_config.json"


def _save_auth_config_both(save_cfg, profile_name):
    """Persist the (already-obfuscated) auth_config to BOTH the runtime
    build folder and userdata.  Best-effort: a failure on either side is
    logged but never raised, so saving auth never blocks login."""
    try:
        payload = json.dumps(save_cfg, indent=4)
    except Exception as exc:
        print(f"[-] auth_config serialize failed: {exc}")
        return
    try:
        with open(os.path.join(RUNTIME_DIR, "auth_config.json"), "w") as f:
            f.write(payload)
    except Exception as exc:
        print(f"[-] runtime auth_config write failed: {exc}")
    try:
        _user_auth_config_path(profile_name).write_text(payload, encoding="utf-8")
    except Exception as exc:
        print(f"[-] userdata auth_config write failed: {exc}")


def _persist_refreshed_ticket(sid, tkt):
    """Persist a mid-run-refreshed Steam session ticket back to auth_config so it
    survives to the next run. Preserves all other (obfuscated) fields. Wired as
    UmaClient.on_ticket_refreshed; best-effort, never raises."""
    try:
        path = _user_auth_config_path(PROFILE_NAME)
        cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(cfg, dict):
            cfg = {}
        cfg["steam_id"] = str(sid)
        cfg["steam_session_ticket"] = tkt
        _save_auth_config_both(cfg, PROFILE_NAME)
        print("[+] Refreshed Steam ticket persisted to auth_config.", flush=True)
    except Exception as exc:
        print(f"[-] Failed to persist refreshed Steam ticket: {exc}")


def _migrate_to_userdata_dir():
    """One-way migration: copy in-build default files into the userdata
    folder when the userdata folder is in use but doesn't already have
    them.  Never overwrites existing userdata files (the user's customized
    state wins).  Safe to call repeatedly -- second-and-later calls are
    no-ops for already-migrated files.
    """
    if USERDATA_DIR == DIR:
        return  # No external folder configured; nothing to migrate.
    try:
        # accounts.json
        src = Path(DIR) / "accounts.json"
        dst = _user_accounts_path()
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
        # settings.json
        src = Path(DIR) / "settings.json"
        dst = Path(_user_settings_path())
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
        # data/presets/*.json -- copy any preset that doesn't already
        # exist in userdata.  Lets the user keep custom presets across
        # versions while still getting any new defaults the build ships.
        src_presets = Path(DIR) / "data" / "presets"
        dst_presets = _user_presets_dir()
        if src_presets.exists():
            for f in src_presets.glob("*.json"):
                target = dst_presets / f.name
                if not target.exists():
                    target.write_bytes(f.read_bytes())
    except Exception as exc:
        print(f"Icarus: userdata migration partial: {exc}")


PROFILE_NAME = "default"
INSTANCE_CONFIG = {}
PORT = 1616

import base64


def _obfuscate_creds(s):
    if not s or not isinstance(s, str) or s.startswith("enc:"):
        return s
    return "enc:" + base64.b64encode(s[::-1].encode("utf-8")).decode("utf-8")


def _deobfuscate_creds(s):
    if not s or not isinstance(s, str) or not s.startswith("enc:"):
        return s
    try:
        return base64.b64decode(s[4:]).decode("utf-8")[::-1]
    except Exception:
        return s


def generate_spoofed_hardware(profile_name):
    import hashlib
    import uuid
    import random

    h = hashlib.sha256(profile_name.encode("utf-8")).hexdigest()
    rng = random.Random(h)
    gpus = [
        "NVIDIA GeForce RTX 3060",
        "NVIDIA GeForce RTX 3070",
        "NVIDIA GeForce RTX 3080",
        "NVIDIA GeForce RTX 4090",
        "AMD Radeon RX 6700 XT",
        "AMD Radeon RX 6800 XT",
    ]
    ip_addr = f"192.168.{rng.randint(1, 254)}.{rng.randint(1, 254)}"
    dev_name = (
        f"DESKTOP-{''.join(rng.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=7))}"
    )
    return {
        "device_name": dev_name,
        "graphics_device_name": rng.choice(gpus),
        "platform_os_version": "Windows 10  (10.0.19045) 64bit",
        "ip_address": ip_addr,
    }


if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
    config_path = sys.argv[1]
    PROFILE_NAME = os.path.splitext(os.path.basename(config_path))[0]

    needs_save = False
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                INSTANCE_CONFIG = json.load(f)
            except Exception:
                INSTANCE_CONFIG = {}
    else:
        needs_save = True

    if "port" not in INSTANCE_CONFIG:
        used_ports = set()
        for fname in os.listdir(DIR):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(DIR, fname), "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        if (
                            isinstance(cfg, dict)
                            and "port" in cfg
                            and isinstance(cfg["port"], int)
                        ):
                            used_ports.add(cfg["port"])
                except Exception:
                    pass

        assign_port = PORT
        while assign_port in used_ports:
            assign_port += 1

        INSTANCE_CONFIG["port"] = assign_port
        needs_save = True

    PORT = INSTANCE_CONFIG["port"]

    # Auto-fill missing hardware details for consistency per instance
    spoofed = generate_spoofed_hardware(PROFILE_NAME)
    for key in [
        "device_name",
        "graphics_device_name",
        "platform_os_version",
        "ip_address",
    ]:
        if key not in INSTANCE_CONFIG:
            INSTANCE_CONFIG[key] = spoofed[key]
            needs_save = True

    if needs_save:
        config_file = Path(config_path)
        backup_dir = Path(DIR) / "uma_runtime" / "config_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        if config_file.exists():
            try:
                backup = backup_dir / f"{config_file.stem}-{int(time.time())}.json"
                backup.write_text(config_file.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
        tmp_path = config_file.with_suffix(config_file.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(INSTANCE_CONFIG, f, indent=4)
        tmp_path.replace(config_file)

RUNTIME_DIR = os.path.join(DIR, "uma_runtime", PROFILE_NAME)
os.makedirs(RUNTIME_DIR, exist_ok=True)
os.environ["UMA_RUNTIME_DIR"] = RUNTIME_DIR


from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(app):
    # Startup: regenerate master.mdb-derived data tables (moved here from module
    # scope so a bare `import main` is cheap + side-effect-free). Best-effort: a
    # generation failure must not prevent the server from starting.
    try:
        _md_status = master_data.status(base_dir)
        if _md_status.get("exists"):
            _md_result = master_data.generate(base_dir)
            if _md_result.get("success"):
                print(f"master.mdb data generated: {_md_status.get('master_mdb_path')}")
            else:
                print(f"master.mdb data generation failed: {_md_result.get('detail')}")
        elif _md_status.get("requires_user_action"):
            print(f"master.mdb requires user action: {_md_status.get('master_mdb_path')}")
    except Exception as exc:
        print(f"master.mdb data generation skipped: {exc}")
    if STARTUP_WARNINGS:
        print("Startup warnings (some data loaded empty):")
        for _w in STARTUP_WARNINGS:
            print(f"  - {_w}")
    # Kick off the background AI auto-trainer (best-effort).
    # (Replaces the deprecated @app.on_event("startup") hook.)
    try:
        ai_trainer.start_background_trainer(
            base_dir, runner_active=lambda: bool(career_runner.snapshot().get("running"))
        )
    except Exception as exc:
        print(f"AI auto-trainer startup skipped: {exc}")
    yield


app = FastAPI(lifespan=_lifespan)

chara_map = {}
support_map = {}
active_client = None
active_account = None
active_dashboard_data = None
active_start_state = {}
active_parent_cards = {}
active_parent_rank_points = {}
pending_game_auth_config = {}
raw_load_index_response = None
active_selection = {"deck": None, "friend": None, "trainee": None, "veterans": [], "guestParents": []}




def _empty_ui_selection():
    return {"deck": None, "friend": None, "trainee": None, "veterans": [], "guestParents": []}


def _clear_finished_career_setup_state(clear_selection=True):
    """Clear stale setup locks after a career has fully finished.

    The runner status and dashboard account can disagree after a natural finish or
    a manual stop: the runner says finished, while the setup page still sees an
    active account career and blocks friend/parent refresh.  This helper only
    clears the local dashboard/session state; it does not call game endpoints.
    """
    global active_account, active_dashboard_data, active_selection
    if isinstance(active_account, dict):
        active_account["career"] = None
    if isinstance(active_dashboard_data, dict):
        account = active_dashboard_data.get("account")
        if isinstance(account, dict):
            account["career"] = None
        elif isinstance(active_account, dict):
            active_dashboard_data["account"] = active_account
    if clear_selection:
        active_selection = _empty_ui_selection()
    return {
        "account": active_account,
        "selection": active_selection,
        "selection_cleared": bool(clear_selection),
    }
turn_delay_min_sec = 2.5
turn_delay_max_sec = 5.0
turn_delay_restore_min_sec = 2.5
turn_delay_restore_max_sec = 5.0
turn_delay_disabled = False
# Speed dropdown (replaces the old Tempt-Fate on/off toggle). Each level maps to
# the inter-turn pacing (disabled?), the client's raw min-call-spacing floor, AND
# an api_scale that multiplies the per-call API delay budget (the dominant pacing
# lever). Before v1.5 all three non-Safe levels set disabled=True, which zeroed
# the API delays identically, so Fast/Faster/Ludicrous ran at the same real
# speed. Now api_scale graduates them: Safe 1.0 → Fast 0.4 → Faster 0.15 →
# Ludicrous 0.0 (fully off, the old non-Safe behavior).
SPEED_PRESETS = {
    "safe":      {"label": "Safe",      "disabled": False, "call_floor": 0.14, "api_scale": 1.0},
    "fast":      {"label": "Fast",      "disabled": True,  "call_floor": 0.14, "api_scale": 0.4},
    "faster":    {"label": "Faster",    "disabled": True,  "call_floor": 0.05, "api_scale": 0.15},
    "ludicrous": {"label": "Ludicrous", "disabled": True,  "call_floor": 0.0,  "api_scale": 0.0},
}
speed_level = "safe"
# Multiplier applied to per-call API delays (set by set_speed_level). 1.0 = full
# human-like timing; 0.0 = no API delay. Read live in wait_for_game_turn_delay.
api_delay_scale = 1.0
preset_store = ConfigStore(DIR, userdata_dir=USERDATA_DIR)
career_runner = CareerRunner(DIR)

# DEV-ONLY raw game-endpoint debug route (POST /api/debug/call). Exposes the
# generic UmaClient.call() so a sniffer-discovered endpoint is callable without a
# wrapper. EXCLUDED from public/beta builds -> when career_bot/raw_api.py is
# absent this import fails and the route simply doesn't exist (404), same as the
# skill-buy intercept. Guards (logged-in, not-mid-career, secret-masking) live in
# raw_api.raw_call. active_client/career_runner are read lazily at request time.
try:
    from career_bot import raw_api as _raw_api
    _raw_api.register(
        app,
        lambda: active_client,
        lambda: bool(career_runner.snapshot().get("running")),
    )
except Exception:
    pass

base_dir = Path(__file__).parent.absolute()
# master.mdb-derived data tables are (re)generated in _lifespan at startup, not
# at import time, so importing this module stays cheap and side-effect-free
# (which is what unblocks real behavioral route tests instead of source-grep).
STARTUP_WARNINGS = []
chara_path = base_dir / "data" / "chara_list.json"
support_path = base_dir / "data" / "support_list.json"
images_dir = base_dir / "data" / "images"
skill_icons_dir = base_dir / "data" / "skill_icons"

if chara_path.exists():
    try:
        with open(chara_path, "r", encoding="utf-8") as f:
            chara_map = json.load(f)
    except Exception as exc:
        chara_map = {}
        STARTUP_WARNINGS.append(f"chara_list.json failed to load: {exc}")

# Per-card VERSIONED trainee names (card_id -> "Name (Version)", e.g.
# "Air Shakur (unsigned)") from data/card_names_core.json (tools/extract_card_names.py).
# Used for the Setup trainee picker so each owned version shows its own version name
# (its outfit icon is already per-card_id). Falls back to chara_map when absent.
card_names_map = {}
_card_names_path = base_dir / "data" / "card_names_core.json"
if _card_names_path.exists():
    try:
        with open(_card_names_path, "r", encoding="utf-8") as f:
            card_names_map = json.load(f)
    except Exception as exc:
        card_names_map = {}
        STARTUP_WARNINGS.append(f"card_names_core.json failed to load: {exc}")
if support_path.exists():
    try:
        with open(support_path, "r", encoding="utf-8") as f:
            support_map = json.load(f)
    except Exception as exc:
        support_map = {}
        STARTUP_WARNINGS.append(f"support_list.json failed to load: {exc}")



PROFILE_REFRESH_STATUS = {
    "enabled": True,
    "running": False,
    "last_started": 0,
    "last_finished": 0,
    "last_result": None,
    "last_error": None,
}


# Session-only completed career history. This intentionally lives only in RAM
# and is cleared whenever python main.py exits/restarts.
COMPLETED_CAREER_HISTORY = []
COMPLETED_CAREER_RUN_IDS = set()


def _env_truthy(name, default=True):
    value = os.environ.get(name)
    if value is None:
        return bool(default)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return int(default)


def _profile_cache_age_days(base_dir):
    profile_path = Path(base_dir) / "data" / "trainee_skill_profiles.generated.json"
    if not profile_path.exists():
        return None
    try:
        return max(0.0, (time.time() - profile_path.stat().st_mtime) / 86400.0)
    except Exception:
        return None


def _profile_refresh_needed(base_dir, max_age_days):
    profile_path = Path(base_dir) / "data" / "trainee_skill_profiles.generated.json"
    url_path = Path(base_dir) / "data" / "game8_character_urls.txt"
    if not url_path.exists():
        return False, "missing-url-list"
    if not profile_path.exists():
        return True, "missing-generated-profiles"
    age = _profile_cache_age_days(base_dir)
    if age is None:
        return True, "unknown-cache-age"
    if age >= float(max_age_days):
        return True, f"cache-stale-{age:.1f}d"
    return False, f"cache-fresh-{age:.1f}d"


def _run_profile_refresh(base_dir, force=False):
    PROFILE_REFRESH_STATUS["running"] = True
    PROFILE_REFRESH_STATUS["last_started"] = time.time()
    PROFILE_REFRESH_STATUS["last_error"] = None
    try:
        from tools import game8_character_profile_scraper

        delay = float(os.environ.get("UMA_PROFILE_REFRESH_DELAY", "1.0"))
        limit = _env_int("UMA_PROFILE_REFRESH_LIMIT", 0)

        # Call the scraper's public functions instead of shelling out, so this
        # works from multi-account manager processes too.
        root = Path(base_dir)
        url_path = root / "data" / "game8_character_urls.txt"
        out_path = root / "data" / "trainee_skill_profiles.generated.json"
        urls = [u.strip() for u in url_path.read_text(encoding="utf-8").splitlines() if u.strip()]
        if limit > 0:
            urls = urls[:limit]

        profiles = {}
        errors = []
        for idx, url in enumerate(urls, 1):
            try:
                html = game8_character_profile_scraper.fetch(url)
                profile = game8_character_profile_scraper.extract_profile(url, html)
                profiles[profile["name"]] = profile
                print(f"[profile-refresh] {idx}/{len(urls)} {profile['name']}", flush=True)
            except Exception as exc:
                errors.append({"url": url, "error": str(exc)})
                print(f"[profile-refresh] ERROR {url}: {exc}", flush=True)
            if delay > 0:
                time.sleep(delay)

        profiles.setdefault("__fallback__", {
            "name": "__fallback__",
            "profile_source": "fallback",
            "track_aptitude": {"turf": "A", "dirt": "G"},
            "distance_aptitude": {"sprint": "C", "mile": "C", "medium": "C", "long": "C"},
            "style_aptitude": {"front": "C", "pace": "C", "late": "C", "end": "C"},
            "recommended_style": "front",
            "primary_distances": ["mile", "medium"],
            "secondary_distances": ["sprint", "long"],
            "avoid_distances": [],
            "preferred_skill_fragments": [],
            "avoid_skill_fragments": [],
            "green_skill_cap": 1,
        })

        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(out_path)

        report = {
            "source_urls": len(urls),
            "profiles_generated": len([k for k in profiles if k != "__fallback__"]),
            "errors": len(errors),
            "generated_names": sorted(k for k in profiles if k != "__fallback__"),
            "finished_at": int(time.time()),
        }
        (root / "data" / "trainee_skill_profiles.report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        if errors:
            (root / "data" / "trainee_skill_profiles.errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")

        PROFILE_REFRESH_STATUS["last_result"] = report
        print(f"[profile-refresh] wrote {len(profiles)} profiles", flush=True)
    except Exception as exc:
        PROFILE_REFRESH_STATUS["last_error"] = str(exc)
        print(f"[profile-refresh] failed: {exc}", flush=True)
    finally:
        PROFILE_REFRESH_STATUS["running"] = False
        PROFILE_REFRESH_STATUS["last_finished"] = time.time()


def maybe_start_profile_refresh(base_dir, force=False):
    enabled = _env_truthy("UMA_PROFILE_AUTO_REFRESH", True)
    PROFILE_REFRESH_STATUS["enabled"] = enabled
    if not enabled and not force:
        PROFILE_REFRESH_STATUS["last_result"] = {"skipped": "disabled"}
        return {"success": True, "started": False, "reason": "disabled"}

    max_age_days = max(1, _env_int("UMA_PROFILE_REFRESH_DAYS", 7))
    needed, reason = _profile_refresh_needed(base_dir, max_age_days)
    if not force and not needed:
        PROFILE_REFRESH_STATUS["last_result"] = {"skipped": reason}
        return {"success": True, "started": False, "reason": reason}

    if PROFILE_REFRESH_STATUS.get("running"):
        return {"success": True, "started": False, "reason": "already-running"}

    thread = threading.Thread(target=_run_profile_refresh, args=(base_dir, force), daemon=True)
    thread.start()
    return {"success": True, "started": True, "reason": "force" if force else reason}


@app.get("/api/trainee/profile-refresh/status")
def api_profile_refresh_status():
    status = dict(PROFILE_REFRESH_STATUS)
    status["cache_age_days"] = _profile_cache_age_days(DIR)
    return {"success": True, "status": status}


@app.post("/api/trainee/profile-refresh")
def api_profile_refresh(force: bool = True):
    return maybe_start_profile_refresh(DIR, force=force)


def display_support_type(value):
    return {"Friends": "Pal", "Wisdom": "Wit"}.get(value, value)


def normalize_turn_delay(min_value, max_value, disabled=False):
    left = max(0.0, float(min_value or 0.0))
    right = max(0.0, float(max_value or 0.0))
    if left > right:
        right = left
    if disabled:
        left = 0.0
        right = 0.0
    return left, right, bool(disabled)


def set_turn_delay(min_value, max_value, disabled=False):
    global turn_delay_min_sec, turn_delay_max_sec, turn_delay_restore_min_sec, turn_delay_restore_max_sec, turn_delay_disabled
    next_min, next_max, next_disabled = normalize_turn_delay(
        min_value, max_value, disabled
    )
    if not next_disabled:
        turn_delay_restore_min_sec = next_min
        turn_delay_restore_max_sec = next_max
    turn_delay_min_sec = next_min
    turn_delay_max_sec = next_max
    turn_delay_disabled = next_disabled
    return get_turn_delay()


def get_turn_delay():
    return {
        "success": True,
        "min": turn_delay_min_sec,
        "max": turn_delay_max_sec,
        "restore_min": turn_delay_restore_min_sec,
        "restore_max": turn_delay_restore_max_sec,
        "disabled": turn_delay_disabled,
    }


def set_speed_level(level):
    """Apply a Speed dropdown level: toggles inter-turn pacing AND the client's
    raw min-call-spacing floor. Higher levels = fewer/zero delays = faster careers."""
    global speed_level, api_delay_scale
    level = str(level or "").strip().lower()
    if level not in SPEED_PRESETS:
        level = "safe"
    speed_level = level
    spec = SPEED_PRESETS[level]
    if spec["disabled"]:
        set_turn_delay(0, 0, disabled=True)
    else:
        set_turn_delay(turn_delay_restore_min_sec, turn_delay_restore_max_sec, disabled=False)
    # v1.5: the dominant pacing lever — scales the per-call API delay budget so the
    # levels are actually distinct (previously all non-Safe levels collapsed to 0).
    api_delay_scale = float(spec.get("api_scale", 1.0 if level == "safe" else 0.0))
    import uma_api.client as _uma_client
    _uma_client.MIN_CALL_SPACING = float(spec["call_floor"])
    return get_speed()


def get_speed():
    return {
        "success": True,
        "level": speed_level,
        "levels": [{"id": k, "label": v["label"]} for k, v in SPEED_PRESETS.items()],
        "disabled": turn_delay_disabled,
    }


# Umabot-compatible TP recovery settings. This intentionally replaces the old
# Toughness/Carats restore selector with a single item-aware mode stored in
# settings.json so the browser UI and loop runner share the same policy.
SETTINGS_PATH = _user_settings_path()
# v6.7.6: copy in-build defaults to userdata on first run so upgrades
# don't lose pre-existing configuration.  No-op when userdata == DIR.
_migrate_to_userdata_dir()
TP_RECOVERY_MODES = ("potion_first", "potion_only", "jewels_only")


def _read_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"Failed to write settings.json: {e}")
        return False


def load_tp_recovery_mode():
    mode = _read_settings().get("tp_recovery", "potion_first")
    return mode if mode in TP_RECOVERY_MODES else "potion_first"


def set_tp_recovery_mode(mode):
    if mode not in TP_RECOVERY_MODES:
        mode = "potion_first"
    data = _read_settings()
    data["tp_recovery"] = mode
    _write_settings(data)
    return mode


def tp_recovery_label(mode):
    return {
        "potion_first": "TP items first, Jewels fallback",
        "potion_only": "TP items only",
        "jewels_only": "Jewels only",
    }.get(mode, "TP items first, Jewels fallback")


def _runtime_json_path(name):
    return Path(RUNTIME_DIR) / name


def _read_json_file(path):
    try:
        path = Path(path)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _write_json_file(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data if isinstance(data, dict) else {}, ensure_ascii=False, indent=2), encoding="utf-8")


def _event_choice_paths():
    return (
        _runtime_json_path("events_seen.json"),
        _runtime_json_path("event_overrides.json"),
    )


def _discord_logging_config(redacted=False):
    cfg = _read_settings().get("discord_logging") or {}
    if not isinstance(cfg, dict):
        cfg = {}
    result = {
        "enabled": bool(cfg.get("enabled", False)),
        "webhook_url": str(cfg.get("webhook_url") or ""),
        "send_turn_logs": bool(cfg.get("send_turn_logs", True)),
        "send_career_summary": bool(cfg.get("send_career_summary", True)),
        "redact_sensitive": bool(cfg.get("redact_sensitive", True)),
        "notify_on_finish": bool(cfg.get("notify_on_finish", True)),
        "notify_on_crash": bool(cfg.get("notify_on_crash", True)),
        "notify_on_epithet": bool(cfg.get("notify_on_epithet", False)),
    }
    if redacted and result["webhook_url"]:
        tail = result["webhook_url"][-8:]
        result["webhook_url_redacted"] = "••••" + tail
    return result


def _save_discord_logging_config(patch):
    data = _read_settings()
    current = data.get("discord_logging") if isinstance(data.get("discord_logging"), dict) else {}
    current = {**current, **(patch or {})}
    current["enabled"] = bool(current.get("enabled") and str(current.get("webhook_url") or "").strip())
    data["discord_logging"] = current
    _write_settings(data)
    return _discord_logging_config(redacted=True)


def _send_discord_webhook_test(url):
    payload = {
        "username": "Icarus",
        "content": "Icarus Discord webhook test: configuration saved successfully.",
    }
    req = UrlRequest(
        str(url),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Icarus/1.0"},
        method="POST",
    )
    with urlopen(req, timeout=12) as resp:
        code = getattr(resp, "status", None) or resp.getcode()
        return 200 <= int(code) < 300


import hashlib
import uuid

_mac_seed = str(uuid.getnode()).encode("utf-8")
_m_hash = int(hashlib.md5(_mac_seed).hexdigest()[:8], 16)
_m_rng = random.Random(_m_hash)
_T_M = [_m_rng.uniform(0.85, 1.15) for _ in range(7)]
_S_M = [_m_rng.uniform(0.9, 1.1) for _ in range(7)]
_C_P = random.uniform(2160, 2520)

GLOBAL_SESSION_JITTER = random.uniform(-0.08, 0.08)


def wait_for_game_turn_delay(delay_type="turn", endpoint=None):
    # v1.5: API call delays are governed by the Speed level's api_delay_scale
    # (set by set_speed_level), NOT by the inter-turn pacing toggle. Previously a
    # single `if turn_delay_disabled: return 0.0` zeroed BOTH, which made every
    # non-Safe speed level identical. Now the inter-turn ("turn"/"complex") path
    # still honors turn_delay_disabled, while the "api" path scales by api_delay_scale.
    if delay_type == "api":
        if api_delay_scale <= 0.0:
            return 0.0
    elif turn_delay_disabled:
        return 0.0

    import math
    import random
    import time

    cycle_time = time.time() % _C_P
    fatigue = 1.0 + (math.sin((cycle_time / _C_P) * math.pi * 2) * 0.15)

    if delay_type == "api":
        target_mean = 0.6
        sigma = 0.5
        max_cap = 8.0
        min_cap = 0.1

        if endpoint:
            if any(
                endpoint.endswith(ep)
                for ep in ["tool/pre_signup", "tool/start_session"]
            ):
                seconds = random.uniform(0.011, 0.021)
                return seconds * api_delay_scale
            elif any(endpoint.endswith(ep) for ep in ["race_entry", "read_info/index"]):
                target_mean = 0.05 * _T_M[1]
                sigma = 0.3 * _S_M[1]
                min_cap = 0.025
                max_cap = 0.1
            elif any(
                endpoint.endswith(ep)
                for ep in [
                    "check_event",
                    "continue",
                    "race_end",
                    "race_out",
                    "minigame_end",
                    "mission/receive",
                    "start_career",
                ]
            ):
                target_mean = 1.5 * _T_M[2]
                sigma = 0.55 * _S_M[2]
                min_cap = 0.2
                max_cap = 4.6
            elif any(
                endpoint.endswith(ep)
                for ep in [
                    "load/index",
                    "home/index",
                    "single_mode_free/load",
                    "single_mode_free/start",
                    "tool/signup",
                    "user/recovery_trainer_point",
                ]
            ):
                target_mean = 3.6 * _T_M[3]
                sigma = 0.6 * _S_M[3]
                min_cap = 0.7
                max_cap = 18.0
            elif any(
                endpoint.endswith(ep)
                for ep in [
                    "exec_command",
                    "race_start",
                    "reserve_race",
                    "finish_career",
                    "finish",
                    "single_mode_free/pre",
                    "pre_single_mode/index",
                ]
            ):
                target_mean = 4.0 * _T_M[4]
                sigma = 0.65 * _S_M[4]
                min_cap = 1.0
                max_cap = 19.3
            elif any(
                endpoint.endswith(ep)
                for ep in [
                    "multi_item_use",
                    "multi_item_exchange",
                    "exchange/item",
                    "support_card/enhance",
                    "friend/add",
                ]
            ):
                target_mean = 7.0 * _T_M[5]
                sigma = 0.7 * _S_M[5]
                min_cap = 3.1
                max_cap = 17.0
            elif any(
                endpoint.endswith(ep)
                for ep in [
                    "gain_skills",
                    "chara/nickname",
                    "chara/talent",
                    "item/use",
                    "team/evaluation",
                ]
            ):
                target_mean = 30.0 * _T_M[6]
                sigma = 0.8 * _S_M[6]
                min_cap = 6.0
                max_cap = 75.0

        target_mean *= fatigue
        target_mean += GLOBAL_SESSION_JITTER * (target_mean * 0.5)
        target_mean = max(0.01, target_mean)

        mu = math.log(target_mean) - (sigma**2) / 2.0
        roll = random.lognormvariate(mu, sigma)
        seconds = min(max_cap, max(min_cap, roll))
        return seconds * api_delay_scale

    elif delay_type == "complex":
        range_span = turn_delay_max_sec - turn_delay_min_sec
        target_mean = (
            ((turn_delay_min_sec + turn_delay_max_sec) / 2.0)
            + (GLOBAL_SESSION_JITTER * range_span)
        ) * _T_M[0]
        target_mean = max(0.1, target_mean) * 2.0
        sigma = 1.1 * _S_M[0]
        mu = math.log(target_mean) - (sigma**2) / 2.0
        roll = random.lognormvariate(mu, sigma)
        seconds = min(45.0, max(turn_delay_min_sec * 0.2, roll))
        return seconds
    else:
        range_span = turn_delay_max_sec - turn_delay_min_sec
        target_mean = (
            ((turn_delay_min_sec + turn_delay_max_sec) / 2.0)
            + (GLOBAL_SESSION_JITTER * range_span)
        ) * _T_M[0]
        target_mean = max(0.1, target_mean)
        sigma = 0.75 * _S_M[0]
        mu = math.log(target_mean) - (sigma**2) / 2.0
        roll = random.lognormvariate(mu, sigma)
        seconds = min(turn_delay_max_sec * 5.0, max(turn_delay_min_sec * 0.5, roll))
        return seconds


def attach_turn_delay(client):
    if getattr(client, "_turn_delay_wrapped", False):
        return client

    client._last_api_call_ts = time.time()

    original_call = client.call

    def wrapped_call(ep, args=None, **kwargs):
        target_delay = wait_for_game_turn_delay(delay_type="api", endpoint=ep)
        elapsed = time.time() - client._last_api_call_ts
        if elapsed < target_delay:
            time.sleep(target_delay - elapsed)

        print(
            f"Last Endpoint: {ep.split('/')[-1]} | Delay: {target_delay:.3f}s",
            flush=True,
        )

        res = original_call(ep, args, **kwargs)
        client._last_api_call_ts = time.time()
        return res

    client.call = wrapped_call
    client.wait_turn_delay = lambda: time.sleep(
        wait_for_game_turn_delay(delay_type="turn")
    )
    client.wait_complex_delay = lambda: time.sleep(
        wait_for_game_turn_delay(delay_type="complex")
    )
    client._turn_delay_wrapped = True
    return client


def update_start_state(data):
    global active_start_state
    if not data:
        return
    if data.get("tp_info"):
        tp_info = dict(data.get("tp_info"))
        active_start_state["tp_info"] = tp_info
    item_list = data.get("item_list") or data.get("user_item_array")
    if isinstance(item_list, list) and item_list:
        active_start_state["current_money"] = get_item_count(item_list, 59)
        active_start_state["succession_rank_point"] = get_item_count(item_list, 75)



def _iter_nested_arrays(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_path = f"{path}.{key}" if path else str(key)
            if isinstance(value, list):
                yield next_path, value
                for idx, item in enumerate(value[:1000]):
                    yield from _iter_nested_arrays(item, f"{next_path}[{idx}]")
            elif isinstance(value, dict):
                yield from _iter_nested_arrays(value, next_path)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj[:1000]):
            yield from _iter_nested_arrays(item, f"{path}[{idx}]")


def _candidate_card_id(item):
    if not isinstance(item, dict):
        return 0
    for key in (
        "card_id", "chara_card_id", "trained_card_id", "rental_card_id",
        "guest_card_id", "parent_card_id", "favorite_chara_card_id",
        "favorite_card_id", "chara_id", "support_card_id",
    ):
        value = item.get(key)
        if value:
            return value
    nested_keys = ("chara_info", "trained_chara", "rental_chara", "guest_chara", "parent_chara", "succession_chara")
    for key in nested_keys:
        value = item.get(key)
        if isinstance(value, dict):
            nested = _candidate_card_id(value)
            if nested:
                return nested
    return 0


def _candidate_instance_id(item):
    if not isinstance(item, dict):
        return 0
    for key in (
        "trained_chara_id", "succession_chara_id", "rental_chara_id", "guest_chara_id",
        "trained_chara_uuid", "rental_chara_uuid", "guest_chara_uuid", "parent_chara_id",
        "id", "viewer_id", "owner_viewer_id",
    ):
        value = item.get(key)
        if value:
            return value
    return 0


def _guest_parent_like(item, path=""):
    """Return True for full guest/rental parent rows or lightweight followed rows.

    The Guests tab has changed payload shape across builds. This intentionally
    accepts a broader set of card/user rows, then marks incomplete ones later.
    """
    if not isinstance(item, dict):
        return False
    keys = set(item.keys())
    path_low = str(path or "").lower()

    # Guest Parents must be succession/trained-chara rows, not friend support
    # cards. A pure support-card row has support_card_id but no trained/rental
    # character payload, so it is intentionally rejected even if it came from a
    # friend/follow path.
    if "support_card_id" in keys and not any(k in keys for k in (
        "trained_chara_id", "succession_chara_id", "rental_chara_id", "guest_chara_id",
        "chara_info", "trained_chara", "rental_chara", "guest_chara",
        "succession_trained_chara_id", "trained_chara", "succession_chara_array",
    )):
        return False

    has_card = bool(_candidate_card_id(item))
    has_instance = bool(_candidate_instance_id(item))
    has_lineage = any(k in keys for k in (
        "succession_chara_array", "factor_id_array", "win_saddle_id_array",
        "parent_chara_array", "parents", "parent1", "parent2",
    ))
    has_user = any(k in keys for k in ("viewer_id", "owner_viewer_id", "user_id", "trainer_name", "name"))
    path_hint = any(token in path_low for token in ("follow", "friend", "guest", "rental", "succession", "parent"))
    return has_card and (has_instance or has_lineage or (path_hint and has_user))


def _empty_lineage(card_id=0, name=""):
    return {
        "card_id": card_id or 0,
        "name": name or (chara_map.get(str(card_id), f"Unknown ({card_id})") if card_id else ""),
        "factors": [],
        "wins": get_win_summary([]),
    }


def _normalize_guest_parent_item(item, owner_info=None, source="guest", path=""):
    owner_info = owner_info or {}

    # Some payloads wrap the actual chara under nested keys.
    wrapped = item
    for key in ("chara_info", "trained_chara", "rental_chara", "guest_chara", "parent_chara", "succession_chara"):
        if isinstance(item.get(key), dict):
            wrapped = {**item, **item[key]}
            break

    raw_id = _candidate_card_id(wrapped)
    cid = str(raw_id or 0)
    instance_id = _candidate_instance_id(wrapped) or f"{source}:{cid}:{owner_info.get('viewer_id') or wrapped.get('viewer_id') or ''}"

    display_name = (
        wrapped.get("chara_name")
        or wrapped.get("card_name")
        or wrapped.get("name")
        or wrapped.get("support_name")
        or chara_map.get(cid, f"Unknown ({cid})")
    )

    tree = {
        "self": {
            "card_id": cid,
            "name": chara_map.get(cid, display_name),
            "factors": get_factors(get_chara_factor_ids(wrapped), cid),
            "wins": get_win_summary(wrapped.get("win_saddle_id_array", [])),
        },
        "p1": _empty_lineage(),
        "p2": _empty_lineage(),
        "gp1": _empty_lineage(),
        "gp2": _empty_lineage(),
        "gp3": _empty_lineage(),
        "gp4": _empty_lineage(),
    }

    succession = wrapped.get("succession_chara_array") or wrapped.get("parent_chara_array") or []
    for i, sc in enumerate(succession or []):
        if not isinstance(sc, dict):
            continue
        pos = sc.get("position_id")
        key = {10: "p1", 20: "p2", 11: "gp1", 12: "gp2", 21: "gp3", 22: "gp4"}.get(pos)
        if not key:
            key = ["p1", "p2", "gp1", "gp2", "gp3", "gp4"][i] if i < 6 else None
        if not key:
            continue
        sc_cid = _candidate_card_id(sc)
        tree[key]["card_id"] = sc_cid
        tree[key]["name"] = chara_map.get(str(sc_cid), f"Unknown ({sc_cid})")
        tree[key]["factors"] = get_factors(sc.get("factor_id_array", []), sc_cid)
        tree[key]["wins"] = get_win_summary(sc.get("win_saddle_id_array", []))

    has_full_lineage = bool(
        (wrapped.get("factor_id_array") or wrapped.get("succession_chara_array") or wrapped.get("parent_chara_array"))
        or tree["p1"]["card_id"]
        or tree["p2"]["card_id"]
    )

    viewer_id = (
        owner_info.get("viewer_id")
        or wrapped.get("viewer_id")
        or wrapped.get("owner_viewer_id")
        or wrapped.get("user_id")
        or item.get("viewer_id")
        or item.get("owner_viewer_id")
        or 0
    )
    trainer_name = (
        owner_info.get("name")
        or owner_info.get("trainer_name")
        or wrapped.get("trainer_name")
        or wrapped.get("owner_name")
        or wrapped.get("user_name")
        or item.get("name")
        or ""
    )

    return {
        "instance_id": instance_id,
        "card_id": cid,
        "name": chara_map.get(cid, display_name),
        "rank": wrapped.get("rank", wrapped.get("evaluation_rank", 0)),
        "tree": tree,
        "viewer_id": viewer_id,
        "trainer_name": trainer_name,
        "source": source,
        "path": path,
        "incomplete": not has_full_lineage,
    }


def _array_score_for_guest_path(path):
    low = str(path or "").lower()
    score = 0
    for token, pts in [
        ("guest", 80), ("rental", 75), ("follow", 70), ("friend", 50),
        ("succession", 45), ("parent", 40), ("trained_chara", 25), ("chara", 10),
    ]:
        if token in low:
            score += pts
    if "support" in low:
        score -= 25
    return score


def discover_guest_parent_sources(data):
    """Return candidate guest-parent arrays with diagnostics."""
    sources = []
    for path, arr in _iter_nested_arrays(data):
        if not isinstance(arr, list) or not arr:
            continue
        score = _array_score_for_guest_path(path)
        if score <= 0:
            continue
        candidates = [item for item in arr if _guest_parent_like(item, path)]
        if candidates:
            sources.append({
                "path": path,
                "score": score,
                "count": len(candidates),
                "items": candidates,
            })
    sources.sort(key=lambda x: (x["score"], x["count"]), reverse=True)
    return sources


def _collect_owned_parent_identity_keys(data):
    """Collect owned/veteran parent identities so Guest Parents can exclude them."""
    owned = set()
    own_viewer = (
        data.get("viewer_id")
        or data.get("user_id")
        or ((data.get("user_info") or {}).get("viewer_id"))
        or ((data.get("trained_chara") or {}).get("viewer_id"))
    )

    def add_identity(item):
        if not isinstance(item, dict):
            return
        cid = _candidate_card_id(item)
        iid = _candidate_instance_id(item)
        viewer = item.get("viewer_id") or item.get("owner_viewer_id") or item.get("user_id") or own_viewer
        if iid:
            owned.add(("instance", str(iid)))
        if viewer and cid:
            owned.add(("viewer_card", str(viewer), str(cid)))
        if cid and not viewer:
            owned.add(("card", str(cid)))

    own_arrays = [
        "trained_chara_array",
        "trained_chara_data_array",
        "own_trained_chara_array",
        "user_trained_chara_array",
        "succession_trained_chara_array",
        "trained_chara",
        "directory_card_array",
        "directory_chara_array",
        "scenario_record_array",
    ]
    for key in own_arrays:
        value = data.get(key)
        if isinstance(value, list):
            for item in value:
                add_identity(item)
        elif isinstance(value, dict):
            add_identity(value)
    return owned


def _guest_identity_keys(item):
    cid = str(item.get("card_id") or "")
    iid = str(item.get("instance_id") or "")
    viewer = str(item.get("viewer_id") or "")
    keys = set()
    if iid:
        keys.add(("instance", iid))
    if viewer and cid:
        keys.add(("viewer_card", viewer, cid))
    if cid and not viewer:
        keys.add(("card", cid))
    return keys


def _guest_dedupe_key(item):
    """Stable key that collapses the same rental shown from many API paths."""
    cid = str(item.get("card_id") or "")
    iid = str(item.get("instance_id") or "")
    viewer = str(item.get("viewer_id") or "")
    trainer = str(item.get("trainer_name") or "").strip().lower()
    if iid and not iid.lower().startswith(("trained_chara[", "scenario_record_array", "directory_card_array")):
        return ("iid", iid)
    if viewer and cid:
        return ("viewer_card", viewer, cid)
    if cid and trainer:
        return ("trainer_card", trainer, cid)
    return ("card_name_rank", cid, str(item.get("name") or "").strip().lower(), str(item.get("rank") or ""))


def normalize_guest_parents(data, strict=False):
    """Extract unique real guests/rentals while excluding owned veteran parents.

    The API can surface the same rental through many paths. It can also expose
    local trained characters in generic arrays. This normalizer keeps only one
    display card per guest identity and filters likely owned/veteran rows.

    strict=True restricts extraction to the dedicated rental/guest/follow arrays
    (``known_arrays``) only. Use it against the LOGIN home payload (which lacks
    real guest arrays): the broad summary_user_info_array scan +
    discover_guest_parent_sources heuristic otherwise mis-classifies arbitrary
    umas (friends/recommended/own chara) as guest parents -- the "random umas"
    bug. The full heuristic is correct ONLY against the pre_single_mode payload,
    which genuinely carries borrowable guest/rental parents.
    """
    guests = []
    seen = set()
    owned_keys = _collect_owned_parent_identity_keys(data or {})

    def add_item(item, owner=None, source="guest", path=""):
        path_l = str(path or source or "").lower()
        if any(token in path_l for token in ("directory_card_array", "directory_chara_array", "scenario_record_array")):
            return
        if not _guest_parent_like(item, path):
            return
        normalized = _normalize_guest_parent_item(item, owner_info=owner, source=source, path=path)
        identity = _guest_identity_keys(normalized)
        if identity and any(key in owned_keys for key in identity):
            return
        key = _guest_dedupe_key(normalized)
        if key in seen:
            return
        seen.add(key)
        guests.append(normalized)

    known_arrays = [
        "rental_chara_data_array",
        "rental_succession_chara_array",
        "guest_chara_data_array",
        "guest_parent_array",
        "guest_parent_chara_array",
        "follow_chara_data_array",
        "follow_succession_chara_array",
        "friend_succession_chara_array",
        "follow_trained_chara_array",
        "follow_parent_chara_array",
        "follow_rental_chara_array",
        "rental_trained_chara_array",
        "rental_parent_chara_array",
        "succession_chara_data_array",
        "parent_chara_data_array",
        "friend_trained_chara_array",
        "friend_parent_chara_array",
    ]
    for key in known_arrays:
        for item in data.get(key, []) or []:
            add_item(item, source=key, path=key)

    for user in (data.get("summary_user_info_array", []) or []) if not strict else []:
        for path, arr in _iter_nested_arrays(user):
            if any(token in path.lower() for token in ("rental", "succession", "guest", "parent", "chara", "follow")):
                for item in arr:
                    add_item(item, owner=user, source=f"summary_user_info_array.{path}", path=path)
        if _guest_parent_like(user, "summary_user_info_array"):
            add_item(user, owner=user, source="summary_user_info_array", path="summary_user_info_array")

    for source in (discover_guest_parent_sources(data) if not strict else []):
        for item in source["items"]:
            add_item(item, source=source["path"], path=source["path"])

    # Final safety pass: remove any support-card fallback entries that slipped
    # through nested payloads.
    guests = [
        g for g in guests
        if "support" not in str(g.get("source") or "").lower()
        and "support" not in str(g.get("path") or "").lower()
        and not str(g.get("instance_id") or "").startswith("fallback")
    ]
    return guests





def normalize_friend_cards(data):
    source = "refresh"
    friend_data = data.get("friend_support_card_data")
    if friend_data:
        source = "initial"
        summaries = friend_data.get("summary_user_info_array", [])
        support_cards = friend_data.get("support_card_data_array", [])
    else:
        summaries = data.get("summary_user_info_array", [])
        support_cards = data.get("support_card_data_array", [])

    support_by_key = {}
    for sc in support_cards or []:
        key = (sc.get("viewer_id"), sc.get("support_card_id"))
        support_by_key[key] = sc

    friends = []
    exclude_viewer_ids = []
    seen = set()
    for info in summaries or []:
        viewer_id = info.get("viewer_id")
        support_card_id = info.get("support_card_id")
        if not viewer_id or not support_card_id:
            continue
        key = (viewer_id, support_card_id)
        if key in seen:
            continue
        seen.add(key)
        exclude_viewer_ids.append(viewer_id)
        card_data = support_by_key.get(key) or info.get("user_support_card") or {}
        support_info = support_map.get(str(support_card_id), {})
        friends.append(
            {
                "viewer_id": viewer_id,
                "name": info.get("name", ""),
                "support_card_id": support_card_id,
                "support_name": support_info.get(
                    "name", f"Unknown ({support_card_id})"
                ),
                "rarity": support_info.get("rarity", "?"),
                "type": display_support_type(support_info.get("type", "Unknown")),
                "exp": card_data.get(
                    "exp", info.get("user_support_card", {}).get("exp")
                ),
                "limit_break_count": card_data.get(
                    "limit_break_count",
                    info.get("user_support_card", {}).get("limit_break_count"),
                ),
                "favorite_flag": card_data.get("favorite_flag", 0),
                "friend_state": info.get("friend_state", 0),
            }
        )
    return friends, exclude_viewer_ids, source


def normalize_card_name(name):
    return re.sub(r"[^a-z0-9]+", "", re.sub(r"\([^)]*\)", "", str(name or "").lower()))


def validate_start_selection(req):
    support_ids = [int(card_id) for card_id in req.support_card_ids]
    friend_card_id = int(req.friend_card_id)
    parent_id_1 = int(getattr(req, "parent_id_1", 0) or 0)
    parent_id_2 = int(getattr(req, "parent_id_2", 0) or 0)
    rental_viewer_id = int(getattr(req, "rental_viewer_id", 0) or 0)
    rental_trained_chara_id = int(getattr(req, "rental_trained_chara_id", 0) or 0)
    rental_card_id = int(getattr(req, "rental_card_id", 0) or 0)
    has_rental = bool(rental_viewer_id or rental_trained_chara_id)

    if has_rental:
        if not parent_id_1:
            return "Guest parent requires one owned parent"
        if parent_id_2:
            return "Guest parent cannot be combined with two owned parents"
        if not rental_viewer_id or not rental_trained_chara_id:
            return "Guest parent is missing viewer or trained character id"
    elif not (parent_id_1 and parent_id_2):
        return "Select parents: 2 own, or 1 own + 1 guest"

    if friend_card_id in support_ids:
        return "Friend support card is already in selected deck"

    friend_info = support_map.get(str(friend_card_id), {})
    friend_name = normalize_card_name(friend_info.get("name"))
    if not friend_name:
        return None

    for support_id in support_ids:
        support_name = normalize_card_name(
            support_map.get(str(support_id), {}).get("name")
        )
        if support_name and support_name == friend_name:
            return "Friend support card has same character as selected deck"

    trainee_name = normalize_card_name(chara_map.get(str(req.card_id), ""))
    if trainee_name and trainee_name == friend_name:
        return "Friend support card has same character as trainee"

    if trainee_name:
        for support_id in support_ids:
            support_name = normalize_card_name(
                support_map.get(str(support_id), {}).get("name")
            )
            if support_name and support_name == trainee_name:
                return "Selected deck contains a support card with the same character as the trainee"

    parent1_cards = active_parent_cards.get(parent_id_1, [])
    parent2_cards = active_parent_cards.get(parent_id_2, []) if parent_id_2 else []
    direct_parent_cards = [cards[0] for cards in (parent1_cards, parent2_cards) if cards]
    if rental_card_id:
        direct_parent_cards.append(rental_card_id)
    if direct_parent_cards and int(req.card_id) in direct_parent_cards:
        return "Selected direct parent is same character as trainee"

    return None


def deck_type_counts_from_ids(support_ids, friend_card_id=0):
    counts = [0] * 5
    for sid_int in list(support_ids or []) + (
        [friend_card_id] if friend_card_id else []
    ):
        info = support_map.get(str(sid_int))
        if not info:
            continue
        ctype = info.get("type")
        if ctype == "Speed":
            counts[0] += 1
        elif ctype == "Stamina":
            counts[1] += 1
        elif ctype == "Power":
            counts[2] += 1
        elif ctype == "Guts":
            counts[3] += 1
        elif ctype == "Wisdom":
            counts[4] += 1
    return counts


def deck_type_counts_from_chara(chara_info):
    ids = []
    for card in (chara_info or {}).get("support_card_array") or []:
        sid = int(card.get("support_card_id") or 0)
        if sid:
            ids.append(sid)
    return deck_type_counts_from_ids(ids)


def apply_deck_type_counts(preset, req=None, chara_info=None):
    counts = None
    if req and (req.support_card_ids or req.friend_card_id):
        counts = deck_type_counts_from_ids(req.support_card_ids, req.friend_card_id)
    elif chara_info:
        counts = deck_type_counts_from_chara(chara_info)
    if counts is not None:
        preset["_deck_type_counts"] = counts
        scale_table = [0.0, 0.02, 0.05, 0.09, 0.14, 0.20]
        preset["_deck_multipliers"] = [1.0 + scale_table[min(5, c)] for c in counts]


def parent_rank_point(parent_id):
    parent = active_parent_rank_points.get(int(parent_id))
    if not parent:
        return 0

    rank = int(parent.get("rank") or 0)
    if rank == 13:
        return 62
    return int(parent.get("rank_point") or 0)


def selected_succession_rank_point(req):
    # Rank points are locally cached only for owned veteran parents. Rental/guest
    # parent costs are represented by the rental payload and by the live start
    # endpoint, so do not treat a rental trained_chara_id as an owned parent id.
    selected_total = parent_rank_point(getattr(req, "parent_id_1", 0)) + parent_rank_point(
        getattr(req, "parent_id_2", 0)
    )
    if selected_total:
        return selected_total
    return active_start_state.get("succession_rank_point", 0)


def _safe_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _has_rental_parent(req):
    return bool(
        _safe_int(getattr(req, "rental_viewer_id", 0))
        or _safe_int(getattr(req, "rental_trained_chara_id", 0))
    )


def friendly_steam_login_error(msg):
    """Turn a raw Steam/login error into user-facing guidance + a suggested UI
    cooldown (seconds). The Steam node helper surfaces errors like
    'ERROR:RateLimitExceeded' verbatim; show something actionable instead."""
    text = str(msg or "")
    low = text.lower()
    if "ratelimit" in low or "rate limit" in low:
        return (
            "Steam temporarily blocked sign-ins after too many attempts. Wait about "
            "15-30 minutes, then try again. Double-check your password and that the "
            "Steam Guard code is current (codes refresh every 30 seconds).",
            60,
        )
    if "invalidpassword" in low or "invalid password" in low:
        return ("Steam rejected the username or password. Re-check both and try again.", 20)
    if "invalidcode" in low or "twofactor" in low or "two_factor" in low or "invalid code" in low:
        return (
            "That Steam Guard code wasn't accepted. Wait for a fresh code in your "
            "authenticator (they refresh every 30 seconds), then try again.",
            20,
        )
    # Unknown error: strip the node helper's 'ERROR:' prefix for readability.
    cleaned = text.split("ERROR:", 1)[-1].strip() if "ERROR:" in text else text
    return (cleaned or "Login failed.", 15)


def _rental_trained_chara_id(guest, viewer_id):
    """Return a *genuine* trained_chara_id for a rental/guest entry, else 0.

    Lightweight "followed trainer" rows can carry a synthetic instance_id
    (e.g. ``follow-123`` or ``src:card:viewer``) or fall back to the viewer_id.
    Sending any of those as ``rental_succession_trained_chara.trained_chara_id``
    makes ``single_mode_free/start`` return result_code 500 (the chara isn't
    borrowable).  A real trained-chara id is numeric, > 0, and never equals the
    viewer_id -- enforce that so we only ever send a borrowable id.
    """
    if not isinstance(guest, dict):
        return 0
    viewer_id = _safe_int(viewer_id)
    for key in ("trained_chara_id", "instance_id", "id"):
        tid = _safe_int(guest.get(key))
        if tid and tid != viewer_id:
            return tid
    return 0


def _guest_matches_start_request(req, guest):
    if not isinstance(guest, dict):
        return False
    req_viewer = _safe_int(getattr(req, "rental_viewer_id", 0))
    req_card = _safe_int(getattr(req, "rental_card_id", 0))
    req_trained = str(getattr(req, "rental_trained_chara_id", "") or "")
    guest_viewer = _safe_int(guest.get("viewer_id"))
    guest_card = _safe_int(guest.get("card_id"))
    guest_trained = str(guest.get("instance_id") or guest.get("trained_chara_id") or guest.get("id") or "")
    if req_trained and guest_trained and req_trained == guest_trained:
        return True
    # Only confirm a viewer+card match when the row is actually borrowable --
    # i.e. it exposes a real trained-chara id.  Otherwise the refresh would
    # rewrite the request with a viewer_id/synthetic value and 500 at start.
    if req_viewer and req_card and guest_viewer == req_viewer and guest_card == req_card:
        return _rental_trained_chara_id(guest, guest_viewer) > 0
    return False


def _refresh_guest_parent_for_start(req, data):
    """Verify a selected rental parent against a fresh pre-start payload.

    Rental/guest parent entries can expire or be removed after a career completes.
    Reusing a stale `rental_succession_trained_chara` can make
    `single_mode_free/start` return 501. Before each looped career start, refresh
    the available guest list and rewrite the request with the fresh trained-chara
    id if the same viewer/card is still available.
    """
    if not _has_rental_parent(req):
        return None
    guests = normalize_guest_parents(data or {})
    if active_dashboard_data is not None:
        active_dashboard_data["guestParents"] = guests
        active_dashboard_data["guestParentsLoaded"] = True
    match = None
    for guest in guests:
        if _guest_matches_start_request(req, guest):
            match = guest
            break
    if not match:
        return {
            "success": False,
            "fatal_start": True,
            "detail": (
                "Selected guest parent is no longer available in the fresh pre-start "
                "rental list. Refresh Guest Parents and reselect before starting another loop."
            ),
        }
    viewer_id = _safe_int(match.get("viewer_id"), _safe_int(getattr(req, "rental_viewer_id", 0)))
    card_id = _safe_int(match.get("card_id"), _safe_int(getattr(req, "rental_card_id", 0)))
    # Use only a genuine trained-chara id (never a viewer_id/synthetic fallback);
    # sending those is the cause of the result_code 500 on guest-parent starts.
    trained_id = _rental_trained_chara_id(match, viewer_id)
    if not viewer_id or not trained_id:
        return {
            "success": False,
            "fatal_start": True,
            "detail": (
                "The selected guest parent is not currently borrowable (no valid "
                "trained-chara id in the fresh rental list -- it may have expired or "
                "be a follow-only entry). Refresh Guest Parents and reselect, or start "
                "without a guest parent."
            ),
        }
    req.rental_viewer_id = viewer_id
    req.rental_trained_chara_id = trained_id
    req.rental_card_id = card_id
    req.parent_id_2 = 0
    return None


def _pre_start_refresh(req):
    """Refresh pre-start state and validate guest rental availability."""
    try:
        result = active_client.pre_single_mode([req.friend_viewer_id] if req.friend_viewer_id else [])
        data = result.get("data", {}) or {}
        update_start_state(data)
        rental_error = _refresh_guest_parent_for_start(req, data)
        if rental_error:
            return rental_error
    except Exception as exc:
        if _has_rental_parent(req):
            return {
                "success": False,
                "fatal_start": True,
                "detail": f"Could not refresh selected guest parent before start: {exc}",
            }
    return {"success": True}


skill_data = {}
skill_data_path = base_dir / "data" / "skill_data.json"
if skill_data_path.exists():
    try:
        with open(skill_data_path, "r", encoding="utf-8") as f:
            skill_data = json.load(f)
    except Exception as exc:
        skill_data = {}
        STARTUP_WARNINGS.append(f"skill_data.json failed to load: {exc}")

factor_map = {}
factor_map_path = base_dir / "data" / "factor_map.json"
if factor_map_path.exists():
    try:
        with open(factor_map_path, "r", encoding="utf-8") as f:
            factor_map = json.load(f)
    except Exception as exc:
        factor_map = {}
        STARTUP_WARNINGS.append(f"factor_map.json failed to load: {exc}")

race_map = {}
race_map_path = base_dir / "data" / "race_map.json"
if race_map_path.exists():
    try:
        with open(race_map_path, "r", encoding="utf-8") as f:
            race_map = json.load(f)
    except Exception as exc:
        race_map = {}
        STARTUP_WARNINGS.append(f"race_map.json failed to load: {exc}")

win_saddle_core = {}
win_saddle_path = base_dir / "data" / "win_saddle_core.json"
if win_saddle_path.exists():
    try:
        with open(win_saddle_path, "r", encoding="utf-8") as f:
            win_saddle_core = {str(row.get("id")): row for row in json.load(f) or []}
    except Exception:
        win_saddle_core = {}

career_rank_thresholds = []
career_rank_thresholds_path = base_dir / "data" / "career_rank_thresholds_core.json"
if career_rank_thresholds_path.exists():
    try:
        with open(career_rank_thresholds_path, "r", encoding="utf-8") as f:
            career_rank_thresholds = list(json.load(f) or [])
    except Exception:
        career_rank_thresholds = []

tp_restore_items_core = []
tp_restore_items_path = base_dir / "data" / "tp_restore_items_core.json"
if tp_restore_items_path.exists():
    try:
        with open(tp_restore_items_path, "r", encoding="utf-8") as f:
            tp_restore_items_core = list(json.load(f) or [])
    except Exception:
        tp_restore_items_core = []

succession_scoring_core = {}
succession_scoring_path = base_dir / "data" / "succession_scoring_core.json"
if succession_scoring_path.exists():
    try:
        with open(succession_scoring_path, "r", encoding="utf-8") as f:
            succession_scoring_core = json.load(f) or {}
    except Exception:
        succession_scoring_core = {}

succession_initial_points_by_star = {}
for row in succession_scoring_core.get("initial_factors") or []:
    try:
        if int(row.get("factor_type") or 0) == 1:
            succession_initial_points_by_star[int(row.get("value_1") or 0)] = int(row.get("add_point") or 0)
    except Exception:
        continue

career_progression_core = []
career_progression_path = base_dir / "data" / "career_progression_core.json"
if career_progression_path.exists():
    try:
        with open(career_progression_path, "r", encoding="utf-8") as f:
            payload = json.load(f) or {}
            career_progression_core = list(payload.get("grades") or [])
    except Exception:
        career_progression_core = []


def skill_entry_name(entry):
    if isinstance(entry, dict):
        return entry.get("name") or ""
    return entry


def get_win_summary(win_saddle_ids):
    summary = {"g1": 0, "g2": 0, "g3": 0, "total": 0, "names": []}

    for saddle_id in win_saddle_ids or []:
        sid = str(saddle_id)
        core = win_saddle_core.get(sid) or {}
        if core:
            name = str(core.get("name") or "").strip()
            if name and name not in summary["names"]:
                summary["names"].append(name)
            for grade in core.get("grades") or []:
                g = str(grade or "").upper()
                if g == "G1":
                    summary["g1"] += 1
                elif g == "G2":
                    summary["g2"] += 1
                elif g == "G3":
                    summary["g3"] += 1
            continue

        # Legacy fallback: older race_map.json builds were sometimes flat.
        race = race_map.get(sid) if isinstance(race_map, dict) else None
        grade = race.get("grade") if race else None
        if grade == "G1":
            summary["g1"] += 1
        elif grade == "G2":
            summary["g2"] += 1
        elif grade == "G3":
            summary["g3"] += 1

    summary["total"] = summary["g1"] + summary["g2"] + summary["g3"]
    return summary


def clean_factor_name(name, base_id=None, category=None):
    if not isinstance(name, str):
        return name

    if category == "skill" and "?" in name and base_id is not None:
        skill_name = skill_entry_name(skill_data.get(f"{base_id}2"))
        if skill_name:
            return skill_name
    return name.replace(" ?", " ○")


def get_factors(fid_array, owner_card_id=None):
    results = []
    category_order = {
        "stat": 0,
        "aptitude": 1,
        "unique": 2,
        "race": 3,
        "skill": 4,
        "scenario": 5,
        "other": 6,
    }
    stat_map = {
        1: "Speed",
        2: "Stamina",
        3: "Power",
        4: "Guts",
        5: "Wit",
        11: "Turf",
        12: "Dirt",
        21: "Short",
        22: "Mile",
        23: "Medium",
        24: "Long",
        31: "Front Runner",
        32: "Pace Chaser",
        33: "Late Surger",
        34: "End Closer",
    }

    owner_cid_str = str(owner_card_id) if owner_card_id else ""
    if len(owner_cid_str) > 4:
        owner_cid_str = owner_cid_str[:4]

    for fid in fid_array:
        if not fid or fid <= 0:
            continue

        fid_str = str(fid)
        factor_info = factor_map.get(fid_str)
        if factor_info:
            base_id = fid // 100
            category = factor_info.get("category", "other")
            name = clean_factor_name(
                factor_info.get("name", f"Unknown({fid})"), base_id, category
            )
            stars = factor_info.get("stars", fid % 100)
            initial_points = succession_initial_points_by_star.get(int(stars or 0), 0)
            results.append(
                {
                    "name": name,
                    "stars": stars,
                    "id": fid,
                    "category": category,
                    "initial_points": initial_points,
                }
            )
            continue

        base_id = fid // 100
        stars = fid % 100
        bid_str = str(base_id)
        name = f"Unknown({base_id})"
        category = "other"

        if base_id <= 34:
            category = "stat" if base_id <= 5 else "aptitude"
            name = stat_map.get(base_id, name)

        elif bid_str in skill_data:
            category = "skill"
            name = skill_entry_name(skill_data[bid_str])

        initial_points = succession_initial_points_by_star.get(int(stars or 0), 0)
        results.append(
            {
                "name": name,
                "stars": stars,
                "id": base_id,
                "category": category,
                "initial_points": initial_points,
            }
        )

    return [
        factor
        for _, factor in sorted(
            enumerate(results),
            key=lambda item: (category_order.get(item[1]["category"], 99), item[0]),
        )
    ]


def get_chara_factor_ids(chara):
    factor_ids = chara.get("factor_id_array")
    if isinstance(factor_ids, list) and factor_ids:
        return factor_ids
    return [f.get("factor_id", 0) for f in chara.get("factor_info_array", [])]


# Item-count helpers (_coerce_int, _first_present, _item_id_from_payload,
# _item_count_from_payload, get_item_count, find_item_count) extracted to
# career_bot/item_helpers.py and re-imported at the top of this module so
# main.<name> and intra-main.py callers resolve unchanged.


def _master_mdb_path_for_lookup():
    try:
        db_path = master_data.configured_master_mdb_path(base_dir)
        if db_path and Path(db_path).exists():
            return Path(db_path)
    except Exception:
        pass
    return None


def _detect_toughness_item_ids_from_core():
    """Return exact Toughness 30 item IDs from generated master-data JSON."""
    ids = []
    for row in tp_restore_items_core or []:
        try:
            if str(row.get("kind") or "").lower() != "toughness_30":
                continue
            item_id = int(row.get("item_id") or 0)
        except Exception:
            continue
        if item_id and item_id not in ids:
            ids.append(item_id)
    return ids


def _detect_toughness_item_ids_from_master():
    """Lookup the exact Toughness 30 item ID from master.mdb.

    master.mdb stores generic item names in text_data category 23 using
    text_data.index = item_data.id. The previous broad scanner could mistakenly
    return text_data.id/category (23) instead of the actual item ID (32). This
    direct query intentionally returns item_data.id only.
    """
    db_path = _master_mdb_path_for_lookup()
    if not db_path:
        return []
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                '''
                SELECT i.id
                FROM item_data i
                LEFT JOIN text_data n
                  ON n.category = 23 AND n."index" = i.id
                LEFT JOIN text_data d
                  ON d.category = 10 AND d."index" = i.id
                WHERE i.item_category = 20
                  AND i.effect_type_1 = 2
                  AND i.effect_value_1 = 30
                  AND n.text = 'Toughness 30'
                ORDER BY i.id
                '''
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return []
    result = []
    for row in rows:
        try:
            item_id = int(row[0])
        except Exception:
            continue
        if item_id and item_id not in result:
            result.append(item_id)
    return result


def _parse_toughness_configured_ids():
    raw = os.environ.get("UMA_TOUGHNESS_ITEM_IDS", "")
    source = "env" if raw else ""
    if not raw:
        cfg_path = Path(DIR) / "data" / "toughness_item_ids.json"
        try:
            if cfg_path.exists():
                payload = json.loads(cfg_path.read_text(encoding="utf-8"))
                raw_values = payload.get("item_ids") if isinstance(payload, dict) else payload
                raw = ",".join(str(x) for x in (raw_values or []))
                source = str(payload.get("source") or "data/toughness_item_ids.json") if isinstance(payload, dict) else "data/toughness_item_ids.json"
        except Exception:
            raw = ""
            source = ""
    ids = []
    for part in str(raw or "").replace(";", ",").split(","):
        try:
            value = int(part.strip())
            if value > 0 and value not in ids:
                ids.append(value)
        except Exception:
            pass
    return ids, source


def _canonical_toughness_item_ids():
    # master.mdb says Toughness 30 is item_data.id 32.  Prefer the generated
    # core export because it is bundled with the release, and fall back to the
    # active local master.mdb if the export is unavailable.
    return _detect_toughness_item_ids_from_core() or _detect_toughness_item_ids_from_master()


def get_toughness_item_ids():
    """Return validated Toughness 30 item ids.

    Older builds could write or recommend stale ids such as text_data.category
    23 instead of item_data.id 32.  Configured ids are now accepted only when
    they match the authoritative master-data Toughness 30 id.  This keeps a
    stale local config from overriding the fixed detector.
    """
    configured, source = _parse_toughness_configured_ids()
    canonical = _canonical_toughness_item_ids()
    if configured and canonical:
        valid = [iid for iid in configured if iid in set(canonical)]
        invalid = [iid for iid in configured if iid not in set(canonical)]
        if invalid:
            try:
                out_path = Path(DIR) / "data" / "toughness_item_ids.invalid.json"
                out_path.write_text(
                    json.dumps(
                        {
                            "ignored_item_ids": invalid,
                            "accepted_item_ids": valid or canonical,
                            "configured_source": source,
                            "reason": "Configured ids did not match the master-data Toughness 30 item_data.id.",
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass
        if valid:
            return valid
        return canonical
    if configured:
        return configured
    detected = canonical
    if detected:
        try:
            out_path = Path(DIR) / "data" / "toughness_item_ids.detected.json"
            out_path.write_text(json.dumps({"item_ids": detected, "source": "master.mdb auto-detect"}, indent=2), encoding="utf-8")
        except Exception:
            pass
    return detected


def get_toughness_count(item_list=None):
    try:
        ids = get_toughness_item_ids()
        if not ids:
            return 0, []
        total = 0
        for iid in ids:
            if item_list is None and active_client:
                count = int(active_client.item_map.get(int(iid), 0) or 0)
            else:
                count = int(get_item_count(item_list or [], int(iid)) or 0)
            total += count
        return total, ids
    except Exception:
        # Account status must never fail because an optional resource counter did.
        return 0, []


def get_account_status(data, career_data=None):
    tp_info = data.get("tp_info") or (active_client.tp_info if active_client else {})
    coin_info = data.get("coin_info") or (
        active_client.coin_info if active_client else {}
    )
    item_list = data.get("item_list") or data.get("user_item_array")
    # Umabot TP item cache behavior: partial career item arrays do not reset
    # absent items to zero. Only update item 32/59 when explicitly present.
    cache = active_client.item_map if active_client else {}
    gold_seen = find_item_count(item_list, 59)
    potions_seen = find_item_count(item_list, 32)
    gold = gold_seen if gold_seen is not None else cache.get(59, 0)
    potions = potions_seen if potions_seen is not None else cache.get(32, 0)
    if active_client:
        if gold_seen is not None:
            active_client.item_map[59] = gold_seen
        if potions_seen is not None:
            active_client.item_map[32] = potions_seen
    career = data.get("single_mode_chara_light") or None

    if career_data:
        career_payload = (
            career_data.get("data") if career_data.get("data") else career_data
        )
        if career_payload.get("chara_info"):
            career = career_payload.get("chara_info")

    status = {
        "tp": {
            "current": tp_info.get("current_tp", 0),
            "max": tp_info.get("max_tp", 0),
        },
        "carrots": {
            "free": coin_info.get("fcoin", 0) or 0,
            "paid": coin_info.get("coin", 0) or 0,
            "total": (coin_info.get("fcoin", 0) or 0) + (coin_info.get("coin", 0) or 0),
        },
        "gold": gold,
        "potions": potions,
        "tp_recovery": {
            "mode": load_tp_recovery_mode(),
            "label": tp_recovery_label(load_tp_recovery_mode()),
        },
        "clocks": active_client.item_map.get(95, 0) if active_client else 0,
        "career": None,
    }
    if career:
        card_id = str(career.get("card_id", ""))

        p1 = career.get("succession_trained_chara_id_1")
        p2 = career.get("succession_trained_chara_id_2")

        friend_viewer_id = None
        friend_card_id = None
        friend_support = None
        current_deck_cards = []
        current_deck_supports = []

        support_array = career.get("support_card_array") or []
        for sc in support_array:
            pos = sc.get("position")
            if pos == 6:
                friend_viewer_id = sc.get("owner_viewer_id")
                friend_card_id = sc.get("support_card_id")
                friend_info = support_map.get(str(friend_card_id))
                friend_support = {
                    "viewer_id": friend_viewer_id,
                    "support_card_id": friend_card_id,
                    "support_name": (
                        friend_info["name"]
                        if friend_info
                        else f"Unknown ({friend_card_id})"
                    ),
                    "rarity": friend_info["rarity"] if friend_info else "?",
                    "type": (
                        display_support_type(friend_info["type"])
                        if friend_info
                        else "?"
                    ),
                    "limit_break_count": sc.get("limit_break_count"),
                }
            elif 1 <= pos <= 5:
                support_card_id = sc.get("support_card_id")
                current_deck_cards.append(support_card_id)
                support_info = support_map.get(str(support_card_id))
                current_deck_supports.append(
                    {
                        "id": str(support_card_id),
                        "name": (
                            support_info["name"]
                            if support_info
                            else f"Unknown ({support_card_id})"
                        ),
                        "rarity": support_info["rarity"] if support_info else "?",
                        "type": (
                            display_support_type(support_info["type"])
                            if support_info
                            else "?"
                        ),
                    }
                )

        matched_deck_id = None
        user_decks = data.get("support_card_deck_array") or []
        if current_deck_cards:
            current_deck_set = set(current_deck_cards)
            for deck in user_decks:
                deck_cards = deck.get("support_card_id_array") or []
                if set(deck_cards) == current_deck_set:
                    matched_deck_id = deck.get("deck_id")
                    break

        status["career"] = {
            "active": True,
            "card_id": card_id,
            "name": chara_map.get(card_id, f"Unknown ({card_id})"),
            "turn": career.get("turn", 0),
            "scenario_id": career.get("scenario_id", 0),
            "fans": career.get("fans", 0),
            "vital": career.get("vital", 0),
            "max_vital": career.get("max_vital", 0),
            "deck_id": matched_deck_id,
            "support_card_ids": current_deck_cards,
            "support_cards": current_deck_supports,
            "friend_viewer_id": friend_viewer_id,
            "friend_card_id": friend_card_id,
            "friend": friend_support,
            "parent_id_1": p1,
            "parent_id_2": p2,
        }

    return status


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""
    code: str = ""
    steam_id: str = ""
    steam_session_ticket: str = ""


class DeleteCareerRequest(BaseModel):
    current_turn: int = 0



@app.get("/api/settings/tp-recovery")
async def get_tp_recovery_settings():
    mode = load_tp_recovery_mode()
    potions = None
    if active_client is not None:
        try:
            potions = active_client.tp_potion_count()
        except Exception:
            potions = None
    return {
        "success": True,
        "mode": mode,
        "label": tp_recovery_label(mode),
        "modes": list(TP_RECOVERY_MODES),
        "potions": potions,
    }


class TpRecoveryRequest(BaseModel):
    mode: str = "potion_first"


@app.post("/api/settings/tp-recovery")
async def set_tp_recovery_settings(req: TpRecoveryRequest):
    mode = set_tp_recovery_mode(req.mode)
    return {"success": True, "mode": mode, "label": tp_recovery_label(mode)}


# v7.1 — Userdata folder management.
#
# The dashboard pops up a window on first load to walk the user through
# choosing a stable, version-independent userdata folder. The pointer file
# at ~/.sweepycl/userdata_pointer.json remembers their choice so a fresh
# install of a future version automatically finds it.
class UserdataSetPathRequest(BaseModel):
    path: str = ""
    migrate_current: bool = False  # copy currently-loaded settings to new path


class UserdataIntroDismissRequest(BaseModel):
    dont_show_again: bool = True
    suppress_permanently: bool = False  # v7.6: "Do not show again" checkbox


def _userdata_info_payload():
    """Build the status payload the dashboard popup reads."""
    pointer = _read_userdata_pointer()
    pointer_target = (pointer.get("userdata_path") or "").strip() or None
    pointer_exists_on_disk = False
    if pointer_target:
        try:
            pointer_exists_on_disk = Path(pointer_target).expanduser().is_dir()
        except Exception:
            pointer_exists_on_disk = False
    is_fallback = (USERDATA_DIR == DIR)
    is_legacy = USERDATA_SOURCE in (
        "env_legacy_sweepycl", "sibling_legacy_sweepycl",
        "env_legacy_sweepyclaude", "sibling_legacy_sweepyclaude",
    )
    intro_seen = bool(pointer.get("intro_seen"))
    intro_suppressed = bool(pointer.get("intro_suppressed"))
    # The user has a working, version-stable userdata folder when the pointer
    # resolves to a real directory and we aren't on the in-build fallback.
    has_valid_userdata = pointer_exists_on_disk and not is_fallback
    needs_attention = bool(USERDATA_DETECTION_WARNING) or is_fallback
    # v7.6: don't nag users who are already set up.
    #   - If they ticked "Do not show again", never auto-show again.
    #   - If a valid userdata folder is already configured (and there's no
    #     detection warning), they're set up -> skip the popup entirely.
    #   - Otherwise fall back to first-run / needs-attention behavior.
    if intro_suppressed:
        should_show_intro = False
    elif has_valid_userdata and not USERDATA_DETECTION_WARNING:
        should_show_intro = False
    else:
        should_show_intro = needs_attention or not intro_seen
    return {
        "success": True,
        "current_path": USERDATA_DIR,
        "current_source": USERDATA_SOURCE,
        "is_fallback_build_dir": is_fallback,
        "is_legacy_path": is_legacy,
        "pointer_file": str(_userdata_pointer_path()),
        "pointer_target": pointer_target,
        "pointer_exists_on_disk": pointer_exists_on_disk,
        "detection_warning": USERDATA_DETECTION_WARNING,
        "intro_seen": intro_seen,
        "intro_suppressed": intro_suppressed,
        "has_valid_userdata": has_valid_userdata,
        "should_show_intro": should_show_intro,
        "needs_attention": needs_attention,
        "build_dir": DIR,
        "suggested_sibling": str(Path(DIR).parent / "Icarus_userdata"),
        "restart_required": False,  # set true after a path change in this session
    }


# Module-level flag set after a successful set-path call. The popup nags the
# user to restart so the new path takes effect across all consumers of
# USERDATA_DIR (preset_store, settings reads, accounts, auth, etc.).
_userdata_restart_pending = False


@app.get("/api/userdata/info")
async def get_userdata_info():
    payload = _userdata_info_payload()
    payload["restart_required"] = _userdata_restart_pending
    return payload


@app.post("/api/userdata/set-path")
async def set_userdata_path(req: UserdataSetPathRequest):
    global _userdata_restart_pending
    target = (req.path or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        p = Path(target).expanduser().resolve()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Path is not parseable: {exc}")
    # Don't allow pointing at a file.
    if p.exists() and not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Path exists but isn't a directory: {p}")
    # Create the directory if missing; surface clear error if we can't.
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Couldn't create folder at {p}: {exc}")
    # Probe writability so the user finds out NOW, not on first settings save.
    probe = p / ".sweepycl_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Folder isn't writable: {exc}")
    # Optionally migrate the current userdata contents (non-destructive copy
    # for files that don't already exist at the destination).
    migrated_files = 0
    if req.migrate_current and USERDATA_DIR and Path(USERDATA_DIR).resolve() != p:
        try:
            import shutil
            src_root = Path(USERDATA_DIR)
            for src_file in src_root.rglob("*"):
                if not src_file.is_file():
                    continue
                # Skip the in-build defaults that shouldn't follow the user.
                rel = src_file.relative_to(src_root)
                dest = p / rel
                if dest.exists():
                    continue  # never overwrite at the new location
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest)
                migrated_files += 1
        except Exception as exc:
            # Non-fatal — the path is saved, migration partly succeeded.
            print(f"Icarus: userdata migration during set-path failed: {exc}")
    # Persist the pointer.
    saved = _write_userdata_pointer({"userdata_path": str(p)})
    if saved is None:
        raise HTTPException(status_code=500, detail="Failed to write pointer file. Check that ~/.icarus is writable.")
    _userdata_restart_pending = True
    payload = _userdata_info_payload()
    payload["restart_required"] = True
    payload["migrated_files"] = migrated_files
    payload["message"] = "Path saved. Restart Icarus for the new location to take effect."
    return payload


@app.post("/api/userdata/intro-dismissed")
async def dismiss_userdata_intro(req: UserdataIntroDismissRequest = None):
    payload = req or UserdataIntroDismissRequest()
    patch = {}
    if payload.dont_show_again:
        patch["intro_seen"] = True
    if payload.suppress_permanently:
        # "Do not show again" — never auto-open the popup on load again.
        patch["intro_seen"] = True
        patch["intro_suppressed"] = True
    if patch:
        _write_userdata_pointer(patch)
    info = _userdata_info_payload()
    info["restart_required"] = _userdata_restart_pending
    return info


@app.post("/api/userdata/reopen-intro")
async def reopen_userdata_intro():
    """Reset the intro_seen flag so the popup shows again on next dashboard load.
    Useful when a user wants to revisit the setup walkthrough."""
    _write_userdata_pointer({"intro_seen": False, "intro_suppressed": False})
    info = _userdata_info_payload()
    info["restart_required"] = _userdata_restart_pending
    return info


@app.get("/api/tp-restore/status")
async def tp_restore_status():
    """Backward-compatible alias for older callers.

    Pre Icarus now uses the Umabot TP recovery item system. The old
    Toughness/Carats selector is intentionally not reported here.
    """
    return await get_tp_recovery_settings()


class StartCareerRequest(BaseModel):
    card_id: int
    support_card_ids: list[int]
    friend_viewer_id: int
    friend_card_id: int
    parent_id_1: int
    parent_id_2: int
    rental_viewer_id: int = 0
    rental_trained_chara_id: int = 0
    rental_card_id: int = 0
    parent_selection_mode: str = ""
    scenario_id: int = 4
    deck_id: int = 1
    use_tp: int = 30
    difficulty_id: int = 0
    difficulty: int = 0
    is_boost: int = 0
    boost_story_event_id: int = 0
    burn_clocks: bool = False
    carats_enabled: bool = False
    max_clocks_per_career: int = 0
    clocks_g1_debut_only: bool = False
    max_retries_per_race: int = -1
    finalize_single_runs: bool = False
    tp_restore_currency: str = "carats"
    tp_restore_mode: str = ""
    tp_restore_allow_carats_fallback: bool = False


class RunCareerRequest(BaseModel):
    card_id: int = 0
    support_card_ids: list[int] = []
    friend_viewer_id: int = 0
    friend_card_id: int = 0
    parent_id_1: int = 0
    parent_id_2: int = 0
    rental_viewer_id: int = 0
    rental_trained_chara_id: int = 0
    rental_card_id: int = 0
    parent_selection_mode: str = ""
    scenario_id: int = 4
    deck_id: int = 1
    use_tp: int = 30
    difficulty_id: int = 0
    difficulty: int = 0
    is_boost: int = 0
    boost_story_event_id: int = 0
    preset_name: str = ""
    max_steps: int = 2500
    burn_clocks: bool = False
    carats_enabled: bool = False
    max_clocks_per_career: int = 0
    clocks_g1_debut_only: bool = False
    max_retries_per_race: int = -1
    finalize_single_runs: bool = False
    dev_mode: bool = False
    run_count: int = 1  # 1 = one career, N = bounded loop, 0 = loop until stopped.
    tp_restore_currency: str = "carats"
    tp_restore_mode: str = ""
    tp_restore_allow_carats_fallback: bool = False
    race_planner_mode: str = "smart"
    manual_race_ids: list[int] = []


class AiImportLogsRequest(BaseModel):
    source_path: str = ""
    rebuild_dataset: bool = True
    train_after_import: bool = True
    import_presets: bool = True


class SaveRacesRequest(BaseModel):
    races: list[int]
    preset_name: str = ""
    source: str = ""


class EventOverrideRequest(BaseModel):
    story_id: str
    choice: int = -1  # -1 clears runtime override and returns to automatic scoring.


class NativeCaptureRequest(BaseModel):
    enabled: bool = True


class DiscordWebhookRequest(BaseModel):
    webhook_url: str = ""
    enabled: bool = True
    notify_on_finish: bool = True
    notify_on_crash: bool = True
    notify_on_epithet: bool = False


class SavePresetRequest(BaseModel):
    preset: dict


class DeletePresetByNameRequest(BaseModel):
    name: str


class SaveSettingsPresetRequest(BaseModel):
    preset: dict


class SaveSkillConfigRequest(BaseModel):
    config: dict
    preset: str = ""  # v7.6 — target preset (defaults to active)


class SaveSmartSolverConfigRequest(BaseModel):
    config: dict
    preset: str = ""  # v7.6 — target preset (defaults to active)


class CareerActionRequest(BaseModel):
    command_type: int
    command_id: int
    current_turn: int
    current_vital: int
    command_group_id: int = 0
    select_id: int = 0


class FriendListRequest(BaseModel):
    exclude_viewer_ids: list[int] = []
    force_refresh: bool = False


class ApiDelayRequest(BaseModel):
    min: float = 1.6
    max: float = 4.0
    disabled: bool = False


class MasterDataPathRequest(BaseModel):
    master_mdb_path: str


@app.get("/api/settings/turn-delay")
async def get_turn_delay_settings():
    return get_turn_delay()


@app.post("/api/settings/turn-delay")
async def set_turn_delay_settings(req: ApiDelayRequest):
    return set_turn_delay(req.min, req.max, req.disabled)


class SpeedRequest(BaseModel):
    level: str = "safe"


@app.get("/api/settings/speed")
async def get_speed_settings():
    return get_speed()


@app.post("/api/settings/speed")
async def set_speed_settings(req: SpeedRequest):
    return set_speed_level(req.level)


class ApiThemeRequest(BaseModel):
    theme: str = ""


@app.get("/api/settings/theme")
async def get_ui_theme():
    # Server-side theme persistence so the selected theme survives across
    # browsers/origins and server restarts (localStorage alone is per-origin).
    return {"theme": str(_read_settings().get("ui_theme") or "")}


@app.post("/api/settings/theme")
async def set_ui_theme(req: ApiThemeRequest):
    theme = str(req.theme or "").strip()
    data = _read_settings()
    data["ui_theme"] = theme
    _write_settings(data)
    return {"theme": theme}


# Event-effect overlay sourced from gametora.com + master.mdb (tools/
# gametora_event_scraper.py). Fills "effect not in database" gaps for events the
# bot has seen. Keyed by name slug, so seen events are resolved by event NAME
# (falling back to story_id for any future story-id-keyed source).
_EVENT_EFFECTS_SCRAPED = {"data": None, "by_name": None}


def _load_event_effects_scraped():
    if _EVENT_EFFECTS_SCRAPED["data"] is None:
        try:
            p = base_dir / "data" / "event_effects.json"
            if not p.exists():
                p = base_dir / "data" / "event_effects_game8.json"   # legacy fallback
            raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            raw = {}
        data = raw if isinstance(raw, dict) else {}
        _EVENT_EFFECTS_SCRAPED["data"] = data
        idx = {}
        for row in data.values():
            if isinstance(row, dict):
                nm = " ".join(str(row.get("event_name") or "").strip().split()).lower()
                if nm and nm not in idx:
                    idx[nm] = row
        _EVENT_EFFECTS_SCRAPED["by_name"] = idx
    return _EVENT_EFFECTS_SCRAPED["data"]


def _scraped_row_for(sid, event_name):
    """Resolve a scraped event-effects row by story_id, then by event name."""
    data = _load_event_effects_scraped()
    row = data.get(sid)
    if isinstance(row, dict):
        return row
    nm = " ".join(str(event_name or "").strip().split()).lower()
    by_name = _EVENT_EFFECTS_SCRAPED.get("by_name") or {}
    return by_name.get(nm) if nm else {}


def _event_source_name(source_url):
    """BUG #4a: derive a searchable character / support-card name from a gametora
    source_url like .../supports/10017-gold-city or .../characters/100101-special-week
    -> 'Gold City'. Lets Event Choices be searched by the character the card is
    attached to (no rescrape needed; the slug is already in event_effects.json)."""
    try:
        m = re.search(r"/(?:supports|characters)/\d+-([a-z0-9-]+)", str(source_url or ""))
        return m.group(1).replace("-", " ").title() if m else ""
    except Exception:
        return ""


def _running_preset_name():
    """BUG 4b: the preset name of the CURRENTLY-RUNNING career (or None when idle),
    so forced event overrides land on the preset the runner is actually using
    rather than whatever preset is merely 'active' in the UI."""
    try:
        snap = career_runner.snapshot()
        return snap.get("preset") if snap.get("running") else None
    except Exception:
        return None


@app.get("/api/events")
async def get_event_choices(cards: str = ""):
    seen_path, overrides_path = _event_choice_paths()
    seen = _read_json_file(seen_path)
    # Per-preset event choices live on the running preset (when a career is
    # running) else the active preset; merge the legacy global file underneath for
    # display so pre-migration overrides still show. (BUG 4b: show what will apply.)
    overrides = {**(_read_json_file(overrides_path) or {}), **preset_store.read_event_overrides(_running_preset_name())}
    support_filter = {int(x) for x in re.split(r"[,\s]+", str(cards or "")) if x.strip().isdigit()}

    merged = {}
    for sid in seen.keys():
        seen_row = seen.get(sid) if isinstance(seen.get(sid), dict) else {}
        support_card_id = _safe_int(seen_row.get("support_card_id"))
        if support_filter and support_card_id and support_card_id not in support_filter:
            continue
        # gametora+master.mdb is the sole effect/outcome source now (the
        # event_outcomes knowledge base was removed); resolve the seen event by name.
        scraped_row = _scraped_row_for(sid, seen_row.get("event_name"))
        sc = (scraped_row.get("choices") if isinstance(scraped_row, dict) else {}) or {}
        outcomes = {str(k): (v.get("effect") or "") for k, v in sc.items() if isinstance(v, dict) and v.get("effect")}
        # Derive the TRUE choice count: seen num_choices -> captured
        # choice_select_indices -> game8 choice count -> outcomes length.
        true_num_choices = _safe_int(seen_row.get("num_choices"))
        if not true_num_choices:
            csi = seen_row.get("choice_select_indices")
            if isinstance(csi, list) and csi:
                true_num_choices = len(csi)
        if not true_num_choices:
            true_num_choices = len(sc) if isinstance(sc, dict) else 0
        if not true_num_choices:
            true_num_choices = len(outcomes)
        merged[sid] = {
            "story_id": sid,
            "event_id": seen_row.get("event_id", ""),
            "event_name": seen_row.get("event_name") or scraped_row.get("event_name") or "",
            "support_card_id": support_card_id,
            "category": "support_card" if support_card_id else "story",
            "num_choices": int(true_num_choices or 0),
            "choice_select_indices": list(seen_row.get("choice_select_indices") or []),
            "auto_pick": seen_row.get("picked"),
            "auto_source": seen_row.get("source") or ("gametora" if outcomes else ""),
            "count": int(seen_row.get("count") or 0),
            "override": int(overrides[sid]) if sid in overrides else None,
            "outcomes": outcomes if isinstance(outcomes, dict) else {},
            "source_name": _event_source_name((scraped_row or {}).get("source_url")),
        }
    # Also list every catalog event so the panel is populated even before a career
    # has run (events_seen.json may be empty). The event slug is used as the row's
    # story_id so the existing override pipeline (keyed by story_id) keeps working.
    # This runs unconditionally: a deck/cards filter only narrows the seen-event
    # rows above (which carry a real support card id), never this catalog, so the
    # panel is never empty just because a deck is selected.
    catalog = _load_event_effects_scraped()
    for slug, row in catalog.items():
        if slug == "_meta" or slug in seen or slug in merged or not isinstance(row, dict):
            continue
        sc = row.get("choices") if isinstance(row.get("choices"), dict) else {}
        g_outcomes = {str(k): (v.get("effect") or "") for k, v in sc.items() if isinstance(v, dict) and v.get("effect")}
        merged[slug] = {
            "story_id": slug,
            "event_id": "",
            "event_name": row.get("event_name") or "",
            "support_card_id": 0,
            "category": "support_card" if row.get("category") == "support_card" else "story",
            "num_choices": len(sc),
            "choice_select_indices": [int(k) for k in sc.keys() if str(k).lstrip("-").isdigit()],
            "auto_pick": None,
            "auto_source": "gametora",
            "count": 0,
            "override": int(overrides[slug]) if slug in overrides else None,
            "outcomes": g_outcomes,
            "source_name": _event_source_name(row.get("source_url")),
        }
    # Sort by category first (Story before Support Card) so each tab renders a
    # stable, grouped list; catalog support-card rows have support_card_id 0, so the
    # category key — not the card id — drives grouping.
    events = sorted(merged.values(), key=lambda row: (1 if row.get("category") == "support_card" else 0, row.get("support_card_id") or 0, -int(row.get("count") or 0), row.get("event_name") or "~", row.get("story_id") or ""))
    return {"success": True, "events": events}


def _migrate_legacy_event_overrides(name=None):
    """Fold any entries from the legacy global event_overrides.json into the
    target preset's per-preset event_overrides (running preset when given, else
    active), then empty the global file so it no longer wins over the preset in
    the runner. Returns the merged dict."""
    overrides = preset_store.read_event_overrides(name)
    _, overrides_path = _event_choice_paths()
    legacy = _read_json_file(overrides_path) or {}
    if legacy:
        for k, v in legacy.items():
            overrides.setdefault(str(k), v)
        _write_json_file(overrides_path, {})
    return overrides


@app.post("/api/events/override")
async def set_event_choice_override(req: EventOverrideRequest):
    sid = str(req.story_id or "").strip()
    if not sid:
        return {"success": False, "detail": "story_id required"}
    # Event choices are per-preset: store on the RUNNING preset when a career is
    # running (so the forced choice actually applies this career — BUG 4b), else
    # the active preset. Read by the runner via preset.event_overrides.
    target = _running_preset_name()
    overrides = _migrate_legacy_event_overrides(target)
    if int(req.choice) < 0:
        overrides.pop(sid, None)
    else:
        overrides[sid] = int(req.choice)
    saved = preset_store.save_event_overrides(overrides, name=target)
    return {"success": True, "story_id": sid, "override": saved.get(sid)}


# v6.7.25 — bulk reset: wipes every saved override so all events fall back to Auto.
@app.post("/api/events/overrides/clear")
async def clear_all_event_choice_overrides():
    target = _running_preset_name()
    overrides = _migrate_legacy_event_overrides(target)
    cleared = len(overrides)
    preset_store.save_event_overrides({}, name=target)
    return {"success": True, "cleared": cleared}


# v6.7.25 — deck/support card hover info + deck-quality scorelet.
# Resolves each card's effect values at the level implied by its LB, then
# computes a heuristic deck score against the selected trainee's growth profile.
_SUPPORT_TYPE_NAMES = {1: "speed", 2: "stamina", 3: "power", 4: "guts", 5: "wit", 6: "friend", 7: "group"}
_RARITY_LABELS = {1: "R", 2: "SR", 3: "SSR"}  # rarity == star count (id leading digit)
_RARITY_LB0_BASE_LV = {1: 20, 2: 25, 3: 30}  # max level at LB 0 (R=20, SR=25, SSR=30)

# Keys here MUST match the canonical effect names produced by
# _SUPPORT_EFFECT_LABELS in career_bot/master_data.py.
_BONUS_DISPLAY = [
    ("friendship_bonus", "Friendship", "%"),
    ("training_effectiveness", "Training Effect.", "%"),
    ("mood_effect", "Mood Effect", "%"),
    ("race_bonus", "Race Bonus", "%"),
    ("fan_bonus", "Fan Bonus", "%"),
    ("skill_point_bonus", "Skill Pts", "%"),
    ("wit_friendship_recovery", "Wit Recovery", ""),
    ("speed_bonus", "Speed", "%"),
    ("stamina_bonus", "Stamina", "%"),
    ("power_bonus", "Power", "%"),
    ("guts_bonus", "Guts", "%"),
    ("wit_bonus", "Wit", "%"),
    ("initial_speed", "Initial Speed", ""),
    ("initial_stamina", "Initial Stamina", ""),
    ("initial_power", "Initial Power", ""),
    ("initial_guts", "Initial Guts", ""),
    ("initial_wit", "Initial Wit", ""),
    ("initial_friendship_gauge", "Initial Bond", ""),
    ("initial_skill_points", "Initial SP", ""),
    ("hint_levels", "Hint Lv+", ""),
    ("hint_frequency", "Hint Rate", "%"),
    ("specialty_priority", "Specialty Priority", ""),
    ("event_recovery", "Event Recovery", "%"),
    ("event_effectiveness", "Event Effect.", "%"),
    ("failure_protection", "Fail Protect", "%"),
    ("energy_cost_reduction", "Energy Cost-", "%"),
]


def _resolve_card_effects_at_lb(card, lb):
    """Pick the resolved effect row for the level implied by rarity + LB."""
    rarity = int(card.get("rarity") or 1)
    base_lv = _RARITY_LB0_BASE_LV.get(rarity, 30)
    target_lv = base_lv + max(0, int(lb)) * 5
    table = card.get("effect_values_by_level") or {}
    if not table:
        return target_lv, {}
    available = sorted((int(k) for k in table.keys() if str(k).lstrip("-").isdigit()))
    chosen = target_lv
    if available:
        # Largest available level <= target.
        below = [lv for lv in available if lv <= target_lv]
        chosen = below[-1] if below else available[0]
    return chosen, dict(table.get(str(chosen)) or {})


def _load_resolved_supports():
    path = base_dir / "data" / "support_effects_resolved_core.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            blob = json.load(f)
    except Exception:
        return None
    cards = blob.get("support_cards") if isinstance(blob, dict) else None
    if not isinstance(cards, list):
        return None
    return {int(c.get("support_card_id") or 0): c for c in cards}


def _load_trainee_profile(card_id):
    if not card_id:
        return None
    path = base_dir / "data" / "trainee_profiles_core.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            profiles = json.load(f)
    except Exception:
        return None
    target = int(card_id)
    for entry in profiles:
        if int(entry.get("card_id") or 0) == target:
            return entry
        if int(entry.get("chara_id") or 0) == target:
            return entry
    return None


def _compute_deck_score(cards_out, trainee_profile):
    """Return (score_0_to_10, verdict_string, breakdown_dict)."""
    known = [c for c in cards_out if not c.get("unknown")]
    if not known:
        return 0.0, "No card data available.", {}
    n = len(known)
    growth = (trainee_profile or {}).get("growth") or {}
    trainee_name = (trainee_profile or {}).get("name") or "the trainee"
    # Type counts
    type_counts = {}
    for c in known:
        t = c.get("type_label", "?")
        type_counts[t] = type_counts.get(t, 0) + 1
    # LB density (max LB 4 per card)
    total_lb = sum(int(c.get("lb") or 0) for c in known)
    lb_score = min(1.0, total_lb / float(max(1, 4 * n)))
    # Rarity weighted (SSR=3, SR=2, R=1)
    rarity_score = min(1.0, sum({1: 1, 2: 2, 3: 3}.get(int(c.get("rarity") or 3), 1) for c in known) / float(3 * n))
    # Effect strength: sum of friendship/training/race/skill_pt across the deck
    eff_keys = ("friendship_bonus", "training_effectiveness", "race_bonus",
                "skill_point_bonus", "mood_effect")
    eff_sum = 0
    for c in known:
        eff = c.get("effects") or {}
        for k in eff_keys:
            try:
                eff_sum += int(eff.get(k) or 0)
            except Exception:
                pass
    # Rough cap: a stacked SSR LB4 deck pushes ~600+.
    eff_score = min(1.0, eff_sum / 600.0)
    # Type match vs trainee growth
    total_growth = sum(max(0, int(v or 0)) for v in growth.values()) or 1
    type_match = 0.0
    growth_stat_to_type = {"speed": "speed", "stamina": "stamina", "power": "power",
                           "guts": "guts", "wit": "wit", "wiz": "wit"}
    primary_type = max(growth.items(), key=lambda kv: int(kv[1] or 0))[0] if growth else None
    for stat, g in growth.items():
        if not g or int(g or 0) <= 0:
            continue
        t = growth_stat_to_type.get(stat)
        if not t:
            continue
        share = type_counts.get(t, 0) / float(n)
        weight = int(g) / float(total_growth)
        type_match += share * weight
    # Friend card always contributes; bonus for having at least one
    if type_counts.get("friend", 0) >= 1:
        type_match += 0.15
    type_match = min(1.0, type_match)
    # Variety penalty: all-same-type without trainee preference is bad
    distinct = len(type_counts)
    variety_score = min(1.0, distinct / 4.0)  # 4+ distinct types = full credit
    # Weighted combine to 0..10
    raw = (type_match * 4.0
           + eff_score * 2.5
           + lb_score * 2.0
           + rarity_score * 1.0
           + variety_score * 0.5)
    score = round(raw, 1)
    # Verdict
    top_type, top_count = max(type_counts.items(), key=lambda kv: kv[1])
    primary_type_for_label = growth_stat_to_type.get(primary_type or "", primary_type)
    if score >= 7.5:
        verdict = f"Strong fit for {trainee_name}: {top_type}-heavy ({top_count}/{n}), good LB + bonuses."
    elif score >= 5.5:
        verdict = f"Solid for {trainee_name}: leans {top_type}. Room to grow on LB or balance."
    elif score >= 3.5:
        if primary_type_for_label and type_counts.get(primary_type_for_label, 0) < n / 2:
            verdict = f"Workable but mismatched: {trainee_name} grows {primary_type_for_label}, deck leans {top_type}."
        else:
            verdict = f"Workable for {trainee_name}, but LB or rarity could be higher."
    else:
        verdict = f"Weak fit for {trainee_name}: low LB, low effects, or mismatched types."
    breakdown = {
        "type_match": round(type_match, 3),
        "effect_strength": round(eff_score, 3),
        "lb_density": round(lb_score, 3),
        "rarity": round(rarity_score, 3),
        "variety": round(variety_score, 3),
        "total_lb": total_lb,
        "type_counts": type_counts,
        "primary_growth_type": primary_type_for_label,
    }
    return score, verdict, breakdown


@app.get("/api/supports/details")
async def get_support_details(ids: str = "", lbs: str = "", trainee_card_id: int = 0):
    """Per-card resolved effects at the LB-implied level + deck-quality scorelet.

    Query params:
        ids: comma-separated support_card_ids (in deck slot order)
        lbs: comma-separated LB levels (parallel to ids; missing = 0)
        trainee_card_id: optional; used for the type-match score.
    """
    raw_ids = [x for x in re.split(r"[,\s]+", str(ids or "")) if x.strip()]
    id_list = [int(x) for x in raw_ids if x.lstrip("-").isdigit()]
    raw_lbs = [x for x in re.split(r"[,\s]+", str(lbs or "")) if x.strip()]
    lb_list = []
    for i in range(len(id_list)):
        if i < len(raw_lbs) and raw_lbs[i].lstrip("-").isdigit():
            lb_list.append(int(raw_lbs[i]))
        else:
            lb_list.append(0)

    card_by_id = _load_resolved_supports()
    if card_by_id is None:
        return {
            "success": False,
            "detail": "support_effects_resolved_core.json not found. Run master data sync.",
            "cards": [],
        }

    trainee_profile = _load_trainee_profile(trainee_card_id) if trainee_card_id else None

    cards_out = []
    for sid, lb in zip(id_list, lb_list):
        card = card_by_id.get(int(sid))
        if not card:
            cards_out.append({
                "support_card_id": int(sid),
                "name": f"Unknown ({sid})",
                "lb": int(lb),
                "effects": {},
                "unknown": True,
            })
            continue
        chosen_level, raw_effects = _resolve_card_effects_at_lb(card, lb)
        # Keep only non-trivial values for display.
        clean_effects = {}
        for k, v in raw_effects.items():
            try:
                iv = int(v)
            except Exception:
                continue
            if iv in (0, -1):
                continue
            clean_effects[k] = iv
        type_id = int(card.get("support_card_type") or 0)
        cards_out.append({
            "support_card_id": int(sid),
            "name": card.get("name") or f"Card {sid}",
            "rarity": int(card.get("rarity") or 1),
            "rarity_label": _RARITY_LABELS.get(int(card.get("rarity") or 1), "?"),
            "type_id": type_id,
            "type_label": _SUPPORT_TYPE_NAMES.get(type_id, "?"),
            "lb": int(lb),
            "level": int(chosen_level),
            "effects": clean_effects,
            "effects_ordered": [
                {"key": k, "label": label, "value": clean_effects[k], "unit": unit}
                for k, label, unit in _BONUS_DISPLAY
                if k in clean_effects
            ],
        })

    score, verdict, breakdown = _compute_deck_score(cards_out, trainee_profile)
    return {
        "success": True,
        "cards": cards_out,
        "deck_score": score,
        "deck_verdict": verdict,
        "deck_breakdown": breakdown,
        "trainee_name": (trainee_profile or {}).get("name") if trainee_profile else None,
    }


def _skill_optimizer_enabled():
    # #7 — value-per-SP skill-purchase optimizer. OFF by default so the existing
    # priority-order buying is unchanged unless the user opts in.
    return bool(_read_settings().get("skill_optimizer", False))


def _goal_lookahead_enabled():
    # #6 — goal-aware training lookahead (pace-to-target urgency in the
    # goal-aware scorer). OFF by default; default training behavior is unchanged.
    return bool(_read_settings().get("goal_lookahead", False))


@app.get("/api/training/goal-lookahead")
async def get_goal_lookahead():
    return {"success": True, "enabled": _goal_lookahead_enabled()}


@app.post("/api/training/goal-lookahead")
async def set_goal_lookahead(req: NativeCaptureRequest = None):
    payload = req or NativeCaptureRequest()
    settings = _read_settings()
    settings["goal_lookahead"] = bool(payload.enabled)
    _write_settings(settings)
    try:
        career_runner.goal_lookahead = bool(payload.enabled)
    except Exception:
        pass
    return {"success": True, "enabled": bool(payload.enabled)}


@app.get("/api/skills/optimizer")
async def get_skill_optimizer():
    return {"success": True, "enabled": _skill_optimizer_enabled()}


@app.post("/api/skills/optimizer")
async def set_skill_optimizer(req: NativeCaptureRequest = None):
    payload = req or NativeCaptureRequest()
    settings = _read_settings()
    settings["skill_optimizer"] = bool(payload.enabled)
    _write_settings(settings)
    return {"success": True, "enabled": bool(payload.enabled)}


@app.get("/api/settings/discord-webhook")
async def get_discord_webhook():
    cfg = _discord_logging_config(redacted=True)
    return {"success": True, "configured": bool(cfg.get("enabled") and cfg.get("webhook_url")), **cfg}


@app.post("/api/settings/discord-webhook")
async def set_discord_webhook(req: DiscordWebhookRequest):
    cfg = _save_discord_logging_config({
        "enabled": bool(req.enabled and str(req.webhook_url or "").strip()),
        "webhook_url": str(req.webhook_url or "").strip(),
        "send_turn_logs": True,
        "send_career_summary": True,
        "redact_sensitive": True,
        "notify_on_finish": bool(req.notify_on_finish),
        "notify_on_crash": bool(req.notify_on_crash),
        "notify_on_epithet": bool(req.notify_on_epithet),
    })
    return {"success": True, "configured": bool(cfg.get("enabled") and cfg.get("webhook_url")), **cfg}


@app.post("/api/settings/discord-webhook/test")
async def test_discord_webhook():
    cfg = _discord_logging_config()
    url = str(cfg.get("webhook_url") or "").strip()
    if not url:
        return {"success": False, "detail": "No Discord webhook URL configured"}
    try:
        ok = _send_discord_webhook_test(url)
        return {"success": bool(ok)}
    except Exception as exc:
        return {"success": False, "detail": str(exc)}


@app.get("/api/master-data/status")
async def master_data_status():
    return master_data.status(base_dir)


@app.post("/api/master-data/path")
async def set_master_data_path(req: MasterDataPathRequest):
    status = master_data.set_master_mdb_path(base_dir, req.master_mdb_path)
    if status.get("exists"):
        result = master_data.generate(base_dir)
        if result.get("success"):
            status["generated"] = result.get("generated", [])
        else:
            status["generation_error"] = (
                result.get("detail") or "master_data generation failed"
            )
    return status


@app.post("/api/master-data/generate")
async def generate_master_data():
    result = master_data.generate(base_dir)
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("detail") or "master_data generation failed",
        )
    return result


@app.post("/api/presets/save_races")
async def save_races(req: SaveRacesRequest):
    preset_name = (req.preset_name or "").strip()
    if not preset_name:
        preset_name = preset_store.read_settings_presets().get("active") or "Default"
    preset = preset_store.read_one(preset_name)
    if not preset:
        return {"success": False, "detail": f"Preset missing: {preset_name}"}
    preset["extra_race_list"] = req.races
    source = str(getattr(req, "source", "") or "").strip().lower()
    if source in {"manual", "smart"}:
        preset["extra_race_list_source"] = source
    elif req.races:
        preset["extra_race_list_source"] = "manual"
    else:
        preset.pop("extra_race_list_source", None)
    preset_store.write(preset)
    return {"success": True, "preset_name": preset_name, "race_count": len(req.races), "source": preset.get("extra_race_list_source", "")}




@app.post("/api/trackblazer/sync")
def api_trackblazer_sync(force: bool = False):
    try:
        return trackblazer.download_scheduler_data(DIR, force=force)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class TrackblazerPlanRequest(BaseModel):
    aptitudes: dict = Field(default_factory=dict)
    trainee_name: str = ""
    trainee_id: str = ""
    running_style: str = ""
    primary_distances: list = Field(default_factory=list)
    distance_preference_mode: str = "balanced"
    fan_bonus: float = 0
    max_races_in_row: int = 5
    include_op: bool = False
    min_aptitude_floor: int = 6
    solver: str = "auto"
    weights: dict = Field(default_factory=dict)
    target_epithets: list = Field(default_factory=list)
    forced_epithets: list = Field(default_factory=list)
    training_blocks: list = Field(default_factory=list)
    manual_locks: dict = Field(default_factory=dict)
    timeout: int = 30


class TraineeProfileRequest(BaseModel):
    trainee_name: str = ""
    trainee_id: str = ""

class WeightedSkillPreviewRequest(BaseModel):
    trainee_name: str = ""
    trainee_id: str = ""
    preset_name: str = ""
    limit: int = 30



def _trackblazer_profile_aptitudes(req):
    """Build the Trackblazer planning aptitude payload for a selected trainee.

    v6.8 fix: plan from the trainee's BASE (career-start) aptitudes taken from
    the authoritative master-data profile -- NOT from whatever the dashboard
    inferred off the live/last-run trainee.  Aptitudes never start a career at S;
    the live values reflect inheritance/sparks gained at start, so trusting them
    inflated the schedule (e.g. Mile/Medium/Long shown as S when Oguri's base is
    A/A/B).  The running career still re-validates every race against the live
    in-game aptitudes (RacePlanner.check_aptitude), so inheritance is honoured at
    run time -- the *plan* just stops over-promising on ranks the card lacks.
    """
    key_map = {
        "sprint": "Sprint", "mile": "Mile", "medium": "Medium", "middle": "Medium", "long": "Long",
        "turf": "Turf", "dirt": "Dirt",
        "front": "Front", "pace": "Pace", "late": "Late", "end": "End",
    }
    aptitudes = {}
    has_specific_trainee = bool(str(req.trainee_name or "").strip() or str(req.trainee_id or "").strip())

    # 1) Authoritative base aptitudes from the trainee's master-data profile.
    if has_specific_trainee:
        try:
            from career_bot.dynamic_skill_profiles import find_profile
            profile = find_profile(DIR, req.trainee_name or "", req.trainee_id or None)
            if profile and profile.get("name") != "__fallback__" and profile.get("profile_source") != "fallback":
                for group in ("distance_aptitude", "track_aptitude", "style_aptitude"):
                    for key, value in (profile.get(group) or {}).items():
                        if value:
                            aptitudes[key_map.get(str(key).lower(), str(key))] = value
        except Exception:
            pass

    # 2) Fall back to caller-supplied aptitudes only when no base profile
    #    resolved (e.g. an unknown trainee with no master-data entry).
    if not aptitudes and req.aptitudes:
        for key, value in dict(req.aptitudes).items():
            if value:
                aptitudes[key_map.get(str(key).lower(), str(key))] = value

    # 3) Distance / running-style hints only FILL gaps (never override base).
    for distance in req.primary_distances or []:
        aptitudes.setdefault(key_map.get(str(distance).lower(), str(distance)), "A")
    if req.running_style:
        aptitudes.setdefault(key_map.get(str(req.running_style).lower(), str(req.running_style)), "A")

    # 4) Floor guard: if every distance is below the Trackblazer B floor, fall
    #    back to broad planning aptitudes instead of a zero-race route.
    rank_value = {"S": 8, "A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1}
    distance_keys = {"Sprint", "Mile", "Medium", "Long"}
    distance_values = [rank_value.get(str(aptitudes.get(k, "")).upper(), 0) for k in distance_keys if k in aptitudes]
    if distance_values and max(distance_values) < 6:
        for key in distance_keys:
            aptitudes[key] = "B"
        aptitudes.setdefault("Turf", "A")
    return aptitudes



def _profile_to_trackblazer_payload(profile):
    key_map = {
        "sprint": "Sprint", "mile": "Mile", "medium": "Medium", "middle": "Medium", "long": "Long",
        "turf": "Turf", "dirt": "Dirt",
        "front": "Front", "pace": "Pace", "late": "Late", "end": "End",
    }
    source = profile.get("profile_source") or profile.get("source") or ""
    is_fallback = profile.get("name") == "__fallback__" or source == "fallback"

    aptitudes = {}
    if is_fallback:
        # Skill fallback profiles use C/C/C/C to avoid overconfident purchases.
        # Trackblazer planning cannot use those as hard filters because the
        # default floor is B. Use broad, non-destructive planning aptitudes until
        # a real generated/manual profile exists for the trainee.
        aptitudes = {
            "Sprint": "B",
            "Mile": "B",
            "Medium": "B",
            "Long": "B",
            "Turf": "A",
            "Dirt": "G",
        }
    else:
        for key, value in (profile.get("distance_aptitude") or {}).items():
            aptitudes[key_map.get(str(key).lower(), str(key))] = value
        for key, value in (profile.get("track_aptitude") or {}).items():
            aptitudes[key_map.get(str(key).lower(), str(key))] = value
        for key, value in (profile.get("style_aptitude") or {}).items():
            aptitudes[key_map.get(str(key).lower(), str(key))] = value
        if profile.get("recommended_style"):
            mapped = key_map.get(str(profile.get("recommended_style")).lower(), str(profile.get("recommended_style")))
            aptitudes.setdefault(mapped, "A")

    return {
        "name": profile.get("name") or "",
        "profile_source": source,
        "fallback_planning": bool(is_fallback),
        "aptitudes": aptitudes,
        "running_style": profile.get("recommended_style") or profile.get("running_style") or "",
        "primary_distances": profile.get("primary_distances") or ([] if is_fallback else []),
        "secondary_distances": profile.get("secondary_distances") or [],
        "avoid_distances": [] if is_fallback else (profile.get("avoid_distances") or []),
        "source_url": profile.get("source_url") or "",
    }


@app.post("/api/trainee/profile")
def api_trainee_profile(req: TraineeProfileRequest):
    try:
        from career_bot.dynamic_skill_profiles import find_profile
        profile = find_profile(DIR, req.trainee_name or "", req.trainee_id or None)
        payload = _profile_to_trackblazer_payload(profile or {})
        payload["success"] = True
        payload["trainee_name"] = req.trainee_name
        payload["trainee_id"] = req.trainee_id
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))



_SUPPORT_TYPE_TO_STAT = {
    "Speed": "speed",
    "Stamina": "stamina",
    "Power": "power",
    "Guts": "guts",
    "Wit": "wit",
}
_RARITY_WEIGHT = {"SSR": 3, "SR": 2, "R": 1}
_DEFAULT_STAT_PRIORITY = ["speed", "power", "wit", "stamina", "guts"]


def _trainee_stat_priority(card_id):
    """Resolve a trainee's stat priority list from character_profiles, with a
    sensible meta default. Returns (priority_list, profile_name)."""
    base = base_dir / "data" / "character_profiles"
    cid = str(card_id or "")
    chara = cid[:4]
    profile_name = "default"
    try:
        index = json.loads((base / "index.json").read_text(encoding="utf-8"))
        profile_name = (
            index.get("by_card_id", {}).get(cid)
            or index.get("by_chara_id", {}).get(chara)
            or "default"
        )
    except Exception:
        pass
    # v2.1: per-profile stat priority (the old training_scorer_overrides) was
    # removed with the scorer; support recommendations use the meta default.
    priority = list(_DEFAULT_STAT_PRIORITY)
    return priority, profile_name


@app.get("/api/trainee/recommended-supports")
def api_trainee_recommended_supports(card_id: str = "", limit: int = 8):
    """Recommend support cards from the player's OWNED cards for a trainee.

    No explicit per-trainee support recommendations exist in the data, so this
    derives them: rank owned supports by how well their type matches the
    trainee's stat priority, then by rarity. Returns the top matches plus the
    derived stat focus for transparency.
    """
    try:
        priority, profile_name = _trainee_stat_priority(card_id)
        rank = {stat: len(priority) - i for i, stat in enumerate(priority)}
        owned = []
        if active_dashboard_data and active_dashboard_data.get("supports"):
            owned = active_dashboard_data["supports"]
        scored = []
        for card in owned:
            ctype = str(card.get("type") or "")
            stat = _SUPPORT_TYPE_TO_STAT.get(ctype)
            if stat:
                type_score = rank.get(stat, 1)
                reason = f"{ctype} card — matches {stat.title()} focus"
            elif ctype == "Pal":
                type_score = max(1, len(priority) // 2)
                reason = "Pal card — flexible, broadly useful"
            else:
                type_score = 1
                reason = ctype or "Support card"
            rarity = str(card.get("rarity") or "")
            rarity_score = _RARITY_WEIGHT.get(rarity.upper(), 0)
            total = type_score * 10 + rarity_score
            scored.append({**card, "score": total, "reason": reason})
        scored.sort(key=lambda c: (-c["score"], str(c.get("name") or "")))
        top = scored[: max(1, int(limit or 8))]
        return {
            "success": True,
            "card_id": card_id,
            "profile": profile_name,
            "stat_priority": priority,
            "owned_count": len(owned),
            "recommended": top,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# v7.6 — scraped Game8 Trackblazer support-card setups per trainee.
_TRAINEE_SUPPORT_SETUPS = {"data": None}


def _load_trainee_support_setups():
    if _TRAINEE_SUPPORT_SETUPS["data"] is None:
        try:
            p = base_dir / "data" / "trainee_support_setups.json"
            _TRAINEE_SUPPORT_SETUPS["data"] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            _TRAINEE_SUPPORT_SETUPS["data"] = {}
    return _TRAINEE_SUPPORT_SETUPS["data"]


def _find_support_setup_entry(card_id):
    """Match a trainee card_id to a scraped setup entry. Game8 keys by name and
    many trainees have multiple game versions sharing a base name, so the scrape
    exposes card_id (unambiguous) and card_id_candidates (ambiguous versions)."""
    data = _load_trainee_support_setups()
    try:
        cid = int(card_id)
    except Exception:
        return None, None
    for name, entry in data.items():
        if entry.get("card_id") == cid:
            return name, entry
    for name, entry in data.items():
        if cid in (entry.get("card_id_candidates") or []):
            return name, entry
    return None, None


@app.get("/api/trainee/support-setups")
def api_trainee_support_setups(card_id: str = ""):
    """Scraped Game8 Trackblazer recommended support setups for a trainee:
    multiple setups, a budget build, and alternate cards. Each card is marked
    with whether the player owns it (and at what limit break)."""
    try:
        name, entry = _find_support_setup_entry(card_id)
        owned_by_id = {}
        if active_dashboard_data and active_dashboard_data.get("supports"):
            for c in active_dashboard_data["supports"]:
                owned_by_id[str(c.get("id"))] = c

        def mark(cards):
            out = []
            for c in (cards or []):
                cc = dict(c)
                ownc = owned_by_id.get(str(c.get("card_id")))
                cc["owned"] = bool(ownc)
                cc["owned_limit_break"] = ownc.get("limit_break") if ownc else None
                out.append(cc)
            return out

        if not entry:
            return {"success": True, "card_id": card_id, "trainee_name": name,
                    "found": False, "setups": [], "budget": None, "alternates": []}
        setups = [{"label": s.get("label"), "cards": mark(s.get("cards")), "race_bonus": s.get("race_bonus")}
                  for s in (entry.get("setups") or [])]
        budget = None
        if entry.get("budget"):
            budget = {"label": entry["budget"].get("label"), "cards": mark(entry["budget"].get("cards")), "race_bonus": entry["budget"].get("race_bonus")}
        return {
            "success": True,
            "card_id": card_id,
            "trainee_name": name,
            "found": True,
            "setups": setups,
            "budget": budget,
            "alternates": mark(entry.get("alternates")),
            "source_url": entry.get("source_url"),
            "notes": entry.get("notes") or [],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/skills")
def api_skills():
    """Return skill metadata for the weighted skill library."""
    try:
        return {"success": True, "skills": skill_data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/skills/weighted-preview")
def api_weighted_skill_preview(req: WeightedSkillPreviewRequest):
    """Return selected trainee profile + ranked weighted skill preview for the UI."""
    try:
        from career_bot.dynamic_skill_profiles import find_profile, score_skill
        profile = find_profile(DIR, req.trainee_name or "", req.trainee_id or None)

        preset = {}
        if req.preset_name:
            preset = preset_store.read_one(req.preset_name) or {}
        skill_policy = dict(preset.get("skill_policy") or {})
        skill_strategy = preset.get("skill_strategy") or {}

        # Bridge old UI skill_strategy weights into dynamic scorer weights.
        weights = dict(skill_policy.get("weights") or {})
        if isinstance(skill_strategy, dict):
            w = skill_strategy.get("weights") or {}
            if "recommended" in w:
                weights["character_recommended_bonus"] = w.get("recommended")
            if "yellow" in w:
                weights["yellow_skill_bonus"] = w.get("yellow")
            if "green_penalty" in w:
                weights["green_skill_overcap_penalty"] = -abs(int(w.get("green_penalty") or 0))
            if "style" in w:
                weights["style_match_bonus"] = w.get("style")
            if "distance" in w:
                weights["distance_match_bonus"] = w.get("distance")
            if "max_green_per_purchase" in skill_strategy:
                skill_policy["max_green_skills"] = skill_strategy.get("max_green_per_purchase")
        manual_skill_weights = {}
        if isinstance(skill_strategy, dict):
            manual_skill_weights = dict(skill_strategy.get("manual_skill_weights") or {})
        skill_policy["weights"] = weights
        preview_preset = {
            "strategy_mode": preset.get("strategy_mode") or "auto",
            "skill_policy": skill_policy,
        }

        skill_path = Path(DIR) / "data" / "skill_data.json"
        raw = json.loads(skill_path.read_text(encoding="utf-8")) if skill_path.exists() else {}
        official_skill_path = Path(DIR) / "data" / "skill_weighting_core.json"
        try:
            official_skill_rows = json.loads(official_skill_path.read_text(encoding="utf-8")) if official_skill_path.exists() else []
        except Exception:
            official_skill_rows = []
        official_skill_by_id = {
            int(row.get("skill_id") or 0): row
            for row in official_skill_rows if isinstance(row, dict)
        }
        try:
            condition_rows = json.loads((Path(DIR) / "data" / "skill_condition_core.json").read_text(encoding="utf-8"))
        except Exception:
            condition_rows = []
        skill_condition_by_id = {
            int(row.get("skill_id") or 0): row
            for row in condition_rows if isinstance(row, dict)
        }
        try:
            source_payload = json.loads((Path(DIR) / "data" / "skill_sources_core.json").read_text(encoding="utf-8"))
            skill_sources_by_id = {int(k): list(v or []) for k, v in (source_payload.get("skill_to_sources") or {}).items()}
        except Exception:
            skill_sources_by_id = {}
        rows = []
        forced = set((skill_strategy.get("forced_skills") if isinstance(skill_strategy, dict) else []) or preset.get("learn_skill_list", [[]])[0] if preset.get("learn_skill_list") else [])
        blacklist = set((skill_strategy.get("blacklist") if isinstance(skill_strategy, dict) else []) or preset.get("learn_skill_blacklist") or [])

        # P3: read the community tier config ONCE, not once per skill row.
        try:
            community_tiers = json.loads((Path(DIR) / "data" / "community_skill_tiers.json").read_text(encoding="utf-8"))
        except Exception:
            community_tiers = {}

        for raw_id, info in raw.items():
            if not isinstance(info, dict):
                name = str(info)
                info = {}
            else:
                name = str(info.get("name") or raw_id)
            if not name or name in blacklist:
                continue
            community_bonus = 0
            tier = ""
            # Simple tier hint from bundled community tier config (hoisted above).
            for tier_name, names in (community_tiers or {}).items():
                if name in (names or []):
                    tier = tier_name
                    community_bonus = {"SS": 115, "S": 86, "A": 58, "B": 34}.get(str(tier_name).upper(), 20)
                    break

            row = score_skill({
                "name": name,
                "icon_id": info.get("icon_id") or info.get("iconId") or "",
                "type": info.get("type") or "",
            }, profile, preset=preview_preset, community_tier_score=community_bonus)
            official = official_skill_by_id.get(int(raw_id)) if str(raw_id).isdigit() else {}
            condition = skill_condition_by_id.get(int(raw_id)) if str(raw_id).isdigit() else {}
            sources = skill_sources_by_id.get(int(raw_id)) if str(raw_id).isdigit() else []
            if official or condition or sources:
                cost = max(1, int((official or {}).get("cost") or (condition or {}).get("cost") or info.get("need_skill_point") or 160))
                grade = int((official or {}).get("grade_value") or (condition or {}).get("grade_value") or 0)
                official_bonus = min(45, grade / cost * 10) if grade else 0
                ability_types = (official or {}).get("ability_types") or (condition or {}).get("ability_types") or []
                official_bonus += len(ability_types) * 4
                support_source_count = len([src for src in sources if src.get("source_type") in {"support", "support_hint"}])
                trainee_source_count = len([src for src in sources if src.get("source_type") == "trainee"])
                official_bonus += min(12, support_source_count * 1.5)
                official_bonus += min(8, trainee_source_count * 1.0)
                if int((official or {}).get("disable_singlemode") or (condition or {}).get("disable_singlemode") or 0):
                    official_bonus -= 120
                if official_bonus:
                    row["score"] = int(row.get("score") or 0) + int(official_bonus)
                    row.setdefault("reasons", []).append(f"official_master:{round(official_bonus, 1)}")
                if (official or {}).get("conditions") or (condition or {}).get("conditions"):
                    row.setdefault("reasons", []).append("official_conditions")
                if support_source_count:
                    row.setdefault("reasons", []).append(f"support_sources:{support_source_count}")
                if trainee_source_count:
                    row.setdefault("reasons", []).append(f"trainee_sources:{trainee_source_count}")
                row["source_count"] = len(sources)
                row["support_source_count"] = support_source_count
                row["trainee_source_count"] = trainee_source_count
                if condition.get("skill_category_label"):
                    row["skill_category_label"] = condition.get("skill_category_label")
            manual_boost = int(manual_skill_weights.get(name, 0) or 0)
            row["base_score"] = int(row.get("score") or 0)
            row["manual_weight"] = manual_boost
            if manual_boost:
                row["score"] = int(row.get("score") or 0) + manual_boost
                row.setdefault("reasons", []).append(f"manual:{manual_boost:+d}")
            row["skill_id"] = int(raw_id) if str(raw_id).isdigit() else raw_id
            row["cost"] = int(info.get("need_skill_point") or 0) if isinstance(info, dict) else 0
            row["tier"] = tier
            row["forced"] = name in forced
            rows.append(row)

        rows.sort(key=lambda r: (1 if r.get("forced") else 0, int(r.get("score") or 0)), reverse=True)
        limit = max(5, min(int(req.limit or 30), 100))
        return {
            "success": True,
            "profile": profile,
            "preset": {
                "name": preset.get("name", ""),
                "strategy_mode": preset.get("strategy_mode", ""),
                "skill_strategy": skill_strategy,
                "skill_policy": skill_policy,
            },
            "ranked_skills": rows[:limit],
            "total_ranked": len(rows),
            "weighted_system_active": True,
            "logic": {
                "order": "forced skills → character recommendations → community tiers → yellow bonus → style/distance/terrain match → penalties",
                "green_cap": skill_policy.get("max_green_skills", skill_strategy.get("max_green_per_purchase", preset.get("smart_skill_max_green_per_purchase", 1))),
                "weights": weights,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/trackblazer/epithets")
def api_trackblazer_epithets():
    try:
        epithets = trackblazer.epithet_catalog(DIR)
        return {"success": True, "epithets": epithets, "count": len(epithets), "source": "local-structured"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/trackblazer/solver/status")
def api_trackblazer_solver_status():
    try:
        return trackblazer.solver_status(DIR)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/trackblazer/solver/defaults")
def api_trackblazer_solver_defaults():
    try:
        return {"success": True, "defaults": trackblazer.solver_defaults(DIR)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# v6.5 -- character profile endpoints for the dashboard panel
@app.get("/api/character-profile/active")
def api_character_profile_active():
    """Return the currently-active character profile as resolved from the
    runner's last-seen chara_info, with all overrides surfaced for the
    dashboard's Character Profile panel.

    v6.7.1: fixed NameError -- the global is ``career_runner`` (not
    ``runner``) and state is accessed via ``.snapshot()`` (not ``.status``).
    Also adds a fallback to ``active_selection['trainee']`` for the idle
    case where a career hasn't started yet but the user has selected a
    trainee on the dashboard.
    """
    try:
        from career_bot import character_profiles, character_data

        # 1. Live runner state (career running, chara_info loaded)
        try:
            status = career_runner.snapshot() if career_runner else {}
        except Exception:
            status = {}
        chara = (status.get("chara_info") or {}) if isinstance(status, dict) else {}
        card_id = int(chara.get("card_id") or 0)
        chara_id = int(chara.get("chara_id") or 0)
        scenario_id = int((status.get("scenario_id") if isinstance(status, dict) else 0) or 0)
        preset_name = str((status.get("preset_name") if isinstance(status, dict) else "") or "")

        # 2. Fall back to the dashboard's idle selection (the Smart Race
        # Solver Settings 'Character Preset' picker writes here).  The
        # selection shape is {deck, friend, trainee: {id|card_id, name,
        # ...}, veterans, guestParents}.
        selected_name = ""
        if not card_id and not chara_id:
            try:
                sel = active_selection or {}
                trainee = sel.get("trainee") if isinstance(sel, dict) else None
                if isinstance(trainee, dict):
                    cid_candidate = trainee.get("card_id") or trainee.get("id")
                    if cid_candidate:
                        try:
                            card_id = int(cid_candidate)
                            # chara_id is the first 4 digits of card_id
                            # (per the chara_list.json convention)
                            chara_id = int(str(card_id)[:4]) if card_id else 0
                        except (TypeError, ValueError):
                            pass
                    name = trainee.get("name") or trainee.get("display_name") or trainee.get("trained_chara_name")
                    if isinstance(name, str) and name.strip():
                        selected_name = name.strip()
            except Exception:
                pass

        # 3. As a last resort, look up the display name in chara_list.json
        if card_id and not selected_name:
            try:
                chara_list_path = Path(DIR) / "data" / "chara_list.json"
                if chara_list_path.exists():
                    chara_list = json.loads(chara_list_path.read_text(encoding="utf-8"))
                    name_from_list = chara_list.get(str(card_id))
                    if isinstance(name_from_list, str):
                        selected_name = name_from_list
            except Exception:
                pass

        # 4. v6.7.9: when still no card_id available, look at the persisted
        # runner status's ``active_character_profile`` field.  That's the
        # profile the runner USED in the most recent turn / run, with the
        # trainee's display_name and original card_id we can re-resolve
        # from.  Without this fallback the panel falsely showed "default"
        # between runs even when the last career was using a specific
        # profile (e.g. oguri_cap matched via card_id).
        resolved_from_last_run = False
        if not card_id and not chara_id and isinstance(status, dict):
            try:
                last_profile = status.get("active_character_profile") or {}
                if isinstance(last_profile, dict):
                    last_name = last_profile.get("display_name")
                    if isinstance(last_name, str) and last_name.strip():
                        selected_name = last_name.strip()
                        resolved_from_last_run = True
                    # If the persisted profile carried a card_id directly,
                    # use it -- gives us the strongest match path.
                    last_cid = last_profile.get("card_id") or last_profile.get("matched_card_id")
                    if last_cid:
                        try:
                            card_id = int(last_cid)
                            chara_id = int(str(card_id)[:4]) if card_id else 0
                        except (TypeError, ValueError):
                            pass
                    # Also pull scenario_id from the persisted profile if
                    # we didn't get one earlier.
                    last_scenario = last_profile.get("scenario_id")
                    if last_scenario and not scenario_id:
                        try:
                            scenario_id = int(last_scenario)
                        except (TypeError, ValueError):
                            pass
            except Exception:
                pass

        # Build a minimal chara_info-shaped dict so resolve_profile's
        # auto-derivation has something to work with even when the
        # runner hasn't seen the live API payload yet.
        effective_chara = dict(chara) if chara else {}
        if not effective_chara and (card_id or chara_id or selected_name):
            effective_chara = {
                "card_id": card_id,
                "chara_id": chara_id,
                "trained_chara_name": selected_name,
            }

        # Default scenario is 4 (Trackblazer) since that's what every v6.x
        # profile tunes for
        if not scenario_id:
            scenario_id = 4

        profile = character_profiles.resolve_profile(
            card_id=card_id, chara_id=chara_id, scenario_id=scenario_id,
            base_dir=DIR, preset_name=preset_name,
            chara_info=effective_chara if effective_chara else None,
            display_name=selected_name or None,
        )

        # Catalog rows for the picker -- only character-tagged ones for
        # the active trainee plus a count of the full catalog
        char_filtered = []
        all_epithets_count = 0
        try:
            catalog = character_data.load_epithet_catalog(DIR)
            all_epithets_count = len(catalog)
            for title, row in catalog.items():
                if not isinstance(row, dict):
                    continue
                if profile.display_name and profile.display_name in (row.get("characters") or []):
                    char_filtered.append({
                        "title": title,
                        "name": row.get("name") or title,
                        "characters": row.get("characters") or [],
                        "bullet_points": row.get("bullet_points") or [],
                    })
        except Exception:
            pass

        # v6.7.4: live epithet progress from race history.  Reports
        # per-target status (in_progress / completed / not_started / dead)
        # with the races already won and races still needed.
        epithet_progress = []
        try:
            from career_bot import trackblazer as _tb
            # Collect effective targets across preset, profile, forced.
            effective_targets = list(profile.target_epithets or [])
            if profile.auto_pick_epithets and not effective_targets:
                effective_targets = list(profile.auto_picked_epithets or [])
            # Pull race history from the live runner snapshot.  When the
            # career hasn't started yet history is empty, which is fine --
            # everything will show status "not_started".
            history = []
            try:
                snap = career_runner.snapshot() if career_runner else {}
                history = list(snap.get("race_results") or [])
            except Exception:
                history = []
            epithet_progress = _tb.epithet_progress(DIR, effective_targets, history)
            # Mark dead epithets from the solver's last replan.
            try:
                snap2 = career_runner.snapshot() if career_runner else {}
                dead = set((snap2.get("last_smart_replan") or {}).get("dead_epithets") or [])
                for entry in epithet_progress:
                    if entry.get("name") in dead and entry.get("status") != "completed":
                        entry["status"] = "dead"
            except Exception:
                pass
        except Exception:
            epithet_progress = []

        return {
            "success": True,
            "profile": profile.to_dict(),
            "character_filtered_epithets": char_filtered,
            "all_epithets_count": all_epithets_count,
            "epithet_progress": epithet_progress,
            "resolved_from": {
                "card_id": card_id, "chara_id": chara_id,
                "scenario_id": scenario_id, "preset_name": preset_name,
                "selected_name": selected_name,
                "source": (
                    "runner" if chara
                    else "last_run" if resolved_from_last_run
                    else "selection" if (card_id or selected_name)
                    else "default"
                ),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/character-profile/list")
def api_character_profile_list():
    """List all on-disk character profiles for the dashboard."""
    try:
        from career_bot import character_profiles
        return {"success": True, "profiles": character_profiles.list_available_profiles(DIR)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/character-profile/roster")
def api_character_profile_roster():
    """Full trainee roster (name + card_id + base aptitudes) for the Smart Race
    Solver's character picker. Replaces the v3 modal's hardcoded ~16-entry list.
    Aptitude sparks default to 0 (the solve flow adds parent sparks on top)."""
    try:
        import json as _json
        path = base_dir / "data" / "trainee_profiles_core.json"
        rows = _json.loads(path.read_text(encoding="utf-8"))
        DMAP = (("Sprint", "sprint"), ("Mile", "mile"), ("Medium", "medium"), ("Long", "long"))
        TMAP = (("Turf", "turf"), ("Dirt", "dirt"))
        seen = set()
        out = []
        for r in rows:
            name = str(r.get("name") or "").strip()
            cid = r.get("card_id")
            if not name or not cid or name in seen:
                continue
            seen.add(name)
            d = r.get("distance_aptitude") or {}
            t = r.get("track_aptitude") or {}
            apt = {lab: [str(d.get(key) or "G").upper(), 0] for lab, key in DMAP}
            apt.update({lab: [str(t.get(key) or "G").upper(), 0] for lab, key in TMAP})
            out.append({"name": name, "id": int(cid), "apt": apt})
        out.sort(key=lambda x: x["name"])
        return {"success": True, "characters": out}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/character-profile/colors")
def api_character_profile_colors():
    """Per-card UI accent colours (card_id -> {main, sub, border} hex) for the v3
    per-trainee theming. Keyed by card_id (NOT deduped by name) so the active
    career's exact card resolves to its own palette. Read-only metadata; the
    frontend fetches it once and caches it."""
    try:
        import json as _json
        path = base_dir / "data" / "trainee_profiles_core.json"
        rows = _json.loads(path.read_text(encoding="utf-8"))
        colors = {}
        for r in rows:
            cid = r.get("card_id")
            uc = r.get("ui_colors") or {}
            main = str(uc.get("main") or uc.get("border") or "").strip().lstrip("#")
            if not cid or not main:
                continue
            colors[str(int(cid))] = {
                "main": main,
                "sub": str(uc.get("sub") or main).strip().lstrip("#"),
                "border": str(uc.get("border") or main).strip().lstrip("#"),
            }
        return {"success": True, "colors": colors}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/character-profile/auto-pick")
def api_character_profile_auto_pick(req: dict):
    """Toggle auto_pick_epithets for a named profile.

    v6.7.6: when enabled, the profile's signature epithets (auto-derived
    from the character_data catalog) seed the solver's target_epithets
    list if no explicit user targets are set.  Default is OFF (changed
    in v6.7.6) -- the solver picks high-value races organically without
    being biased toward a specific signature.

    Body: ``{"profile_id": "oguri_cap", "auto_pick": true | false}``
    """
    try:
        profile_id = str((req or {}).get("profile_id") or "").strip()
        if not profile_id or "/" in profile_id or ".." in profile_id:
            raise HTTPException(status_code=400, detail="invalid profile_id")
        if "auto_pick" not in (req or {}):
            raise HTTPException(status_code=400, detail="missing auto_pick boolean")
        auto_pick = bool((req or {}).get("auto_pick"))
        from career_bot import character_profiles
        path = Path(DIR) / "data" / character_profiles.PROFILES_DIRNAME / f"{profile_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}")
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        payload["auto_pick_epithets"] = auto_pick
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return {"success": True, "profile_id": profile_id, "auto_pick_epithets": auto_pick}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/character-profile/epithets")
def api_character_profile_epithets(req: dict):
    """Set explicit target/forced epithets for a profile.

    Body: ``{"profile_id": "oguri_cap",
              "target_epithets": ["Ideal Idol", ...],
              "forced_epithets": [...]}``

    Either list may be omitted (no change to that field).  Pass an empty
    list to clear the explicit setting (auto-pick will resume if the
    profile has it enabled).
    """
    try:
        profile_id = str((req or {}).get("profile_id") or "").strip()
        if not profile_id or "/" in profile_id or ".." in profile_id:
            raise HTTPException(status_code=400, detail="invalid profile_id")
        from career_bot import character_profiles
        path = Path(DIR) / "data" / character_profiles.PROFILES_DIRNAME / f"{profile_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}")
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if "target_epithets" in (req or {}):
            payload["target_epithets"] = [str(x) for x in (req["target_epithets"] or [])]
        if "forced_epithets" in (req or {}):
            payload["forced_epithets"] = [str(x) for x in (req["forced_epithets"] or [])]
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return {"success": True, "profile_id": profile_id,
                "target_epithets": payload.get("target_epithets", []),
                "forced_epithets": payload.get("forced_epithets", [])}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/trackblazer/plan")
def api_trackblazer_plan(req: TrackblazerPlanRequest):
    try:
        if not (str(req.trainee_name or "").strip() or str(req.trainee_id or "").strip()):
            raise HTTPException(status_code=400, detail="Select a trainee before generating a Trackblazer plan.")
        aptitudes = _trackblazer_profile_aptitudes(req)
        fan_bonus = max(0.0, min(float(req.fan_bonus or 0), 300.0))
        max_races = max(1, min(int(req.max_races_in_row or 2), 10))
        floor = max(1, min(int(req.min_aptitude_floor or 6), 8))
        result = trackblazer.make_schedule(
            DIR,
            aptitudes=aptitudes,
            fan_bonus=fan_bonus,
            max_races_in_row=max_races,
            include_op=req.include_op,
            floor=floor,
            solver=req.solver,
            weights=req.weights,
            target_epithets=req.target_epithets,
            forced_epithets=req.forced_epithets,
            preferred_distances=req.primary_distances,
            distance_preference_mode=req.distance_preference_mode,
            training_blocks=req.training_blocks,
            manual_locks=req.manual_locks,
            timeout=req.timeout,
        )
        result["aptitudes_used"] = aptitudes
        result["trainee_name"] = req.trainee_name
        result["trainee_id"] = req.trainee_id
        result["plan_key"] = json.dumps({
            "trainee_name": req.trainee_name,
            "trainee_id": req.trainee_id,
            "aptitudes": aptitudes,
            "fan_bonus": fan_bonus,
            "max_races_in_row": max_races,
            "include_op": req.include_op,
            "target_epithets": req.target_epithets,
            "forced_epithets": req.forced_epithets,
            "primary_distances": req.primary_distances,
            "distance_preference_mode": req.distance_preference_mode,
        }, sort_keys=True)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/settings-presets")
async def get_settings_presets():
    payload = preset_store.read_settings_presets()
    return {"success": True, **payload}


@app.post("/api/settings-presets")
async def save_settings_preset(req: SaveSettingsPresetRequest):
    return {"success": True, "preset": preset_store.save_settings_preset(req.preset)}


@app.post("/api/settings-presets/delete")
async def delete_settings_preset(req: DeletePresetByNameRequest):
    return {"success": preset_store.delete_settings_preset(req.name)}


# v7.6 — point the store at the active preset (skill/solver config is now
# per-preset, so switching presets in the UI must update the active pointer).
@app.post("/api/settings-presets/active")
async def set_active_settings_preset(req: DeletePresetByNameRequest):
    return {"success": True, "active": preset_store.set_active(req.name)}


@app.get("/api/skill-config")
async def get_skill_config(preset: str = ""):
    return {"success": True, "config": preset_store.read_skill_config(preset or None)}


@app.post("/api/skill-config")
async def save_skill_config(req: SaveSkillConfigRequest):
    return {"success": True, "config": preset_store.save_skill_config(req.config, (req.preset or None))}


@app.get("/api/smart-solver/config")
async def get_smart_solver_config(preset: str = ""):
    cfg = preset_store.read_solver_config(preset or None)
    # Also surface the persisted race-list source ("manual"/"smart") so the UI can
    # restore the planner mode on load instead of defaulting to "smart" from browser
    # localStorage -- that drift is what silently let the solver take over a manual
    # schedule. read_one(None) resolves to the active preset.
    saved = preset_store.read_one(preset or None) or {}
    source = str(saved.get("extra_race_list_source") or "").strip().lower()
    return {"success": True, "config": cfg, "source": source}


@app.get("/api/trackblazer/races")
def api_trackblazer_races():
    """Race calendar for the v3 manual race picker. Returns the graded + Open races
    (G1/G2/G3/OP) keyed by program_id — the same id the engine matches against in
    extra_race_list. Debut/maiden auto-races (grade 700/800/900) are excluded."""
    try:
        import json as _json
        path = base_dir / "data" / "race_planner_core.json"
        rows = _json.loads(path.read_text(encoding="utf-8"))
        GLABEL = {100: "G1", 200: "G2", 300: "G3", 400: "OP"}
        GPRI = {"G1": 4, "G2": 3, "G3": 2, "OP": 1}
        seen = set()
        out = []
        for r in rows:
            graw = int(r.get("grade_raw") or 0)
            if graw not in GLABEL:
                continue
            pid = r.get("program_id")
            if pid is None:
                continue
            pid = int(pid)
            turn = int(r.get("turn") or 0)
            # Dedup per calendar OCCURRENCE (program_id + turn), not globally by
            # program_id: many G2/G3 races recur in both Classic and Senior years
            # under the SAME program_id, and a global dedup dropped every Senior
            # occurrence (its pid was already 'seen' from the earlier Classic turn),
            # leaving Senior cells like Early Sep/Late Sep/Early Oct/Early Nov/Early
            # Dec empty + unselectable. (A recurring race picked manually still fires
            # whenever the engine is offered that program_id.)
            if (pid, turn) in seen:
                continue
            seen.add((pid, turn))
            out.append({
                "id": pid,
                # BUG #1: per-occurrence id (year_key*100000 + program_id) so the
                # picker can select a recurring race in ONE year only. The engine's
                # wanted_programs turn-scopes occurrence ids (meta[occ].turn) while
                # bare program_ids stay turn-blind, so this is backward compatible.
                "occ": int(r.get("occurrence_id") or 0),
                "turn": turn,
                "date": r.get("date") or "",
                "name": r.get("name") or "",
                "grade": GLABEL[graw],
                "distance": r.get("distance") or "",
                "distance_m": int(r.get("distance_m") or 0),
                "fans": int(r.get("fans") or 0),
            })
        out.sort(key=lambda x: (x["turn"], -GPRI.get(x["grade"], 0)))
        return {"success": True, "races": out}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# --- Race win-probability (read-only analytics, Phase 1) --------------------
# Opponent-aware P(win)/P(top-3) from the game's own master.mdb data. Does NOT
# change how the bot plays; it only reports an estimate so its calibration can
# be validated (tools/race_winnability_report.py) before any Phase-2 decisioning.
_WIN_PROB_MODEL = None
_RACE_PROGRAM_INDEX = None


def _win_prob_model():
    global _WIN_PROB_MODEL
    if _WIN_PROB_MODEL is None:
        from career_bot import win_probability as _wp
        _WIN_PROB_MODEL = _wp.load_model(base_dir)
    return _WIN_PROB_MODEL


def _race_program_index():
    """program_id -> {distance_m, ground, name} (program-constant race facts)."""
    global _RACE_PROGRAM_INDEX
    if _RACE_PROGRAM_INDEX is None:
        idx = {}
        try:
            rows = json.loads((base_dir / "data" / "race_planner_core.json").read_text(encoding="utf-8"))
            for r in rows:
                pid = r.get("program_id")
                if pid is None:
                    continue
                pid = int(pid)
                if pid in idx:
                    continue
                idx[pid] = {
                    "distance_m": int(r.get("distance_m") or 0),
                    "ground": int(r.get("ground") or 1),
                    "name": r.get("name") or "",
                }
        except Exception:
            idx = {}
        _RACE_PROGRAM_INDEX = idx
    return _RACE_PROGRAM_INDEX


class WinProbabilityRequest(BaseModel):
    program_id: int = 0
    turn: int = 0
    trainee_chara_id: int = 0       # base chara id (e.g. 1001); or pass card_id
    card_id: int = 0
    speed: int = 0
    stamina: int = 0
    power: int = 0
    guts: int = 0
    wit: int = 0
    motivation: int = 3
    running_style: int = 0          # 1 front / 2 pace / 3 late / 4 end (for style aptitude)
    # Full aptitude block (letters or ints), shaped like chara_info aptitudes:
    #   {distance:{short,mile,medium,long}, ground:{turf,dirt}, style:{front,pace,late,end}}
    aptitudes: dict = Field(default_factory=dict)
    # Optional explicit per-race grade overrides (used if aptitudes block absent):
    distance_grade: str = ""
    surface_grade: str = ""
    style_grade: str = ""
    distance_m: int = 0             # optional override; else resolved from program_id
    ground: int = 0                 # optional override (1 turf / 2 dirt)
    k: float = 0.0


_STYLE_APT_KEY = {1: "front", 2: "pace", 3: "late", 4: "end"}


def _augment_race_results_with_winprob(rows, card_id):
    """Attach a compact read-only win_probability to each completed-career race
    row (computed from the stored pre-race stat_snapshot + performance_hint, so
    it IS the genuine pre-race estimate). Never raises; skips a row on any error.
    """
    try:
        from career_bot import win_probability as _wp
        model = _win_prob_model()
        chara_id = _wp.chara_id_from_card(card_id)
    except Exception:
        return rows
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        try:
            perf = r.get("performance_hint") or {}
            ground = 2 if str(perf.get("surface_label") or r.get("terrain") or "").lower().startswith("dirt") else 1
            res = model.compute(
                stats=r.get("stat_snapshot") or {}, distance_m=r.get("distance_m"),
                ground=ground, distance_grade=perf.get("distance_aptitude"),
                surface_grade=perf.get("surface_aptitude"),
                style_grade=perf.get("running_style_aptitude"),
                motivation=int(perf.get("motivation") or 3),
                trainee_chara_id=chara_id, turn=int(r.get("turn") or 0),
                program_id=int(r.get("program_id") or 0),
            )
            r["win_probability"] = {
                "p_win": res["p_win"], "p_top3": res["p_top3"],
                "expected_rank": res["expected_rank"], "field_size": res["field_size"],
                "available": res["available"],
            }
        except Exception:
            continue
    return rows


@app.post("/api/race/win-probability")
def api_race_win_probability(req: WinProbabilityRequest):
    """Estimate P(win)/P(top-3) for an upcoming race vs its named-rival field.

    Read-only. `available` is False when no named rivals are known for the race
    (so the caller can hide a misleading 100%). The mob runners that fill the
    rest of the gate at race time are not modelled (see `note`).
    """
    try:
        from career_bot import win_probability as _wp
        model = _win_prob_model()
        prog = _race_program_index().get(int(req.program_id or 0), {})
        distance_m = int(req.distance_m or prog.get("distance_m") or 0)
        ground = int(req.ground or prog.get("ground") or 1)
        chara_id = int(req.trainee_chara_id or 0) or _wp.chara_id_from_card(req.card_id)

        apt = req.aptitudes or {}
        dist_block = apt.get("distance") or {}
        ground_block = apt.get("ground") or apt.get("track") or {}
        style_block = apt.get("style") or {}
        dist_key, _ = _wp.distance_bucket(distance_m)
        # NPC json uses 'medium'; some chara payloads use 'middle' -> accept both.
        distance_grade = (dist_block.get(dist_key) or dist_block.get("middle" if dist_key == "medium" else dist_key)
                          or req.distance_grade or None)
        surf_name = "dirt" if ground == 2 else "turf"
        surface_grade = ground_block.get(surf_name) or req.surface_grade or None
        style_name = _STYLE_APT_KEY.get(int(req.running_style or 0))
        style_grade = (style_block.get(style_name) if style_name else None) or (req.style_grade or None)

        stats = {"speed": req.speed, "stamina": req.stamina, "power": req.power,
                 "guts": req.guts, "wit": req.wit}
        k = float(req.k) if req.k else _wp.DEFAULT_K
        result = model.compute(
            stats=stats, distance_m=distance_m, ground=ground,
            distance_grade=distance_grade, surface_grade=surface_grade,
            style_grade=style_grade, motivation=int(req.motivation or 3),
            trainee_chara_id=chara_id, turn=int(req.turn or 0),
            program_id=int(req.program_id or 0), k=k,
        )
        result.update({"success": True, "program_id": int(req.program_id or 0),
                       "race_name": prog.get("name", ""), "distance_m": distance_m,
                       "ground": ground})
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/smart-solver/config")
async def save_smart_solver_config(req: SaveSmartSolverConfigRequest):
    return {"success": True, "config": preset_store.save_solver_config(req.config, (req.preset or None))}


# Backward-compatible preset endpoints.  They now compose/split the three new
# config files and never recreate data/presets.
@app.get("/api/presets")
async def get_presets():
    return {"success": True, "presets": preset_store.read_all()}


@app.post("/api/presets")
async def save_preset(req: SavePresetRequest):
    return {"success": True, "preset": preset_store.write(req.preset)}


@app.post("/api/presets/delete")
async def delete_preset(req: DeletePresetByNameRequest):
    return {"success": preset_store.delete(req.name)}


def start_career_from_request(req):
    global active_account, active_dashboard_data
    if not active_client:
        return {"success": False, "detail": "Not logged in"}
    if not req.friend_viewer_id or not req.friend_card_id:
        return {"success": False, "detail": "Friend support card is required"}
    selection_error = validate_start_selection(req)
    if selection_error:
        return {"success": False, "detail": selection_error}

    try:
        res = active_client.read_info()
        data = res.get("data", {})
        active_client.refresh_cached_account_state(data)
        update_start_state(data)
        if active_account:
            active_account = get_account_status(data)
            if active_dashboard_data:
                active_dashboard_data["account"] = active_account
    except Exception:
        pass

    if not active_start_state.get("tp_info"):
        return {
            "success": False,
            "detail": "Missing live TP state; login again before starting career",
        }
    if "current_money" not in active_start_state:
        return {
            "success": False,
            "detail": "Missing live item state; login again before starting career",
        }

    tp_info = active_start_state["tp_info"]
    current_tp = int(tp_info.get("current_tp") or 0)

    # Umabot TP recovery replacement. Modes are stored in settings.json:
    #   potion_first: use TP item 32 first, then spend Jewels if still short.
    #   potion_only: use only TP items and refuse to start if still short.
    #   jewels_only: spend Jewels only.
    tp_mode = load_tp_recovery_mode()
    restore_reasoning = [f"TP recovery mode: {tp_recovery_label(tp_mode)}."]

    if req.use_tp and current_tp < req.use_tp and tp_mode in ("potion_first", "potion_only"):
        restore_reasoning.append(f"Current TP {current_tp}/{req.use_tp}; trying TP recovery items before career start.")
        for attempt in range(20):  # Umabot cap: at most 20 items per start.
            if current_tp >= req.use_tp:
                break
            try:
                potions = active_client.tp_potion_count()
            except Exception:
                potions = 0
            if potions <= 0:
                restore_reasoning.append("No TP recovery items remain in the live item cache.")
                break
            try:
                active_client.use_recovery_item(item_num=1)
                tp_info = active_client.tp_info
                active_start_state["tp_info"] = tp_info
                new_tp = int(tp_info.get("current_tp") or 0)
                restore_reasoning.append(f"TP item attempt {attempt + 1}: {current_tp} -> {new_tp} TP; items left {active_client.tp_potion_count()}.")
                if new_tp <= current_tp:
                    restore_reasoning.append("TP item did not increase TP; stopping item recovery attempts.")
                    break
                current_tp = new_tp
            except Exception as e:
                restore_reasoning.append(f"TP item attempt {attempt + 1} failed: {e}")
                if "213" in str(e):
                    try:
                        res = active_client.call("load/index", {"adid": ""})
                        active_client.refresh_cached_account_state(res.get("data", {}))
                        tp_info = active_client.tp_info
                        active_start_state["tp_info"] = tp_info
                        current_tp = int(tp_info.get("current_tp") or 0)
                    except Exception:
                        pass
                else:
                    break
                time.sleep(1)

    if req.use_tp and current_tp < req.use_tp and tp_mode in ("potion_first", "jewels_only"):
        restore_reasoning.append(f"Current TP {current_tp}/{req.use_tp}; trying Jewel TP recovery.")
        for attempt in range(3):
            try:
                needed = ((req.use_tp - current_tp) + 29) // 30
                active_client.recovery_tp(needed)
                tp_info = active_client.tp_info
                active_start_state["tp_info"] = tp_info
                current_tp = int(tp_info.get("current_tp") or 0)
                restore_reasoning.append(f"Jewel recovery attempt {attempt + 1}: TP is now {current_tp}.")
                if current_tp >= req.use_tp:
                    break
            except Exception as e:
                restore_reasoning.append(f"Jewel recovery attempt {attempt + 1} failed: {e}")
                if "213" in str(e):
                    try:
                        res = active_client.call("load/index", {"adid": ""})
                        active_client.refresh_cached_account_state(res.get("data", {}))
                        tp_info = active_client.tp_info
                        active_start_state["tp_info"] = tp_info
                        current_tp = int(tp_info.get("current_tp") or 0)
                    except Exception:
                        pass
                time.sleep(1)

    if req.use_tp and current_tp < req.use_tp:
        active_start_state["tp_restore_reasoning"] = restore_reasoning
        return {"success": False, "detail": f"Not enough TP: {current_tp}/{req.use_tp}. TP recovery mode: {tp_mode}"}

    pre_start = _pre_start_refresh(req)
    if not pre_start.get("success"):
        active_start_state["tp_restore_reasoning"] = restore_reasoning
        return pre_start
    current_money = active_start_state.get("current_money", 0)
    succession_rank_point = selected_succession_rank_point(req)
    tp_info = active_start_state.get("tp_info", tp_info)
    time.sleep(random.uniform(0.5, 1.5))

    active_start_state["tp_restore_reasoning"] = restore_reasoning
    # Safeguard against result_code 2511: the game rejects single_mode_free/start
    # when the deck is illegal. Two triggers: (1) more than 6 cards total, and
    # (2) the borrowed friend duplicated among the owned support_card_ids — the
    # friend has its OWN slot (friend_support_card_info), so the same card_id must
    # not also appear in support_card_ids. A saved preset or the v3 deck picker can
    # produce either. The old guard only count-trimmed and missed the duplicate
    # case. sanitize_support_deck drops blanks/dupes, removes the friend from the
    # owned list, and caps to 5 (friend borrowed) / 6. See tests/test_deck_sanitize.py.
    try:
        from uma_api.deck_sanitize import sanitize_support_deck
        if isinstance(req.support_card_ids, list):
            _before = list(req.support_card_ids)
            req.support_card_ids = sanitize_support_deck(_before, getattr(req, "friend_card_id", 0))
            if req.support_card_ids != _before:
                print(
                    f"[deck-guard] Sanitized support deck {_before} -> {req.support_card_ids} "
                    f"(borrowed friend {getattr(req, 'friend_card_id', 0)}) to avoid result_code 2511."
                )
    except Exception as _deck_guard_err:
        print(f"[deck-guard] sanitize skipped: {_deck_guard_err}")
    try:
        result = active_client.start_career(
            card_id=req.card_id,
            support_card_ids=req.support_card_ids,
            friend_viewer_id=req.friend_viewer_id,
            friend_card_id=req.friend_card_id,
            parent_id_1=req.parent_id_1,
            parent_id_2=req.parent_id_2,
            rental_viewer_id=getattr(req, "rental_viewer_id", 0),
            rental_trained_chara_id=getattr(req, "rental_trained_chara_id", 0),
            scenario_id=req.scenario_id,
            deck_id=req.deck_id,
            use_tp=req.use_tp,
            tp_info=tp_info,
            current_money=current_money,
            succession_rank_point=succession_rank_point,
            difficulty_id=req.difficulty_id,
            difficulty=req.difficulty,
            is_boost=req.is_boost,
            boost_story_event_id=req.boost_story_event_id,
        )
    except Exception as exc:
        err = str(exc)
        if _has_rental_parent(req) and ("501" in err or "500" in err):
            return {
                "success": False,
                "fatal_start": True,
                "detail": (
                    "The game rejected the guest parent start request after refresh. "
                    "The selected rental may have expired, been used up, or become unavailable. "
                    "Refresh Guest Parents and reselect before looping another career. "
                    f"Original error: {err}"
                ),
            }
        # 102 = the server still holds an in-progress career, so a new start is
        # rejected (stale account cache, or a prior run that didn't finish/abandon
        # cleanly). Resume the existing career instead of failing so the runner
        # can finish it and the career-looping feature keeps going. Matches the
        # existing active-career guard in /api/career/run and the runner's own
        # 102 reconciliation. See uma_api/career_recovery.py.
        if is_career_in_progress_error(err):
            recovered = resume_active_career(active_client, on_state=update_start_state)
            if recovered is not None:
                turn = (
                    ((recovered.get("data") or {}).get("chara_info") or {}).get("turn", 0)
                )
                print(
                    f"single_mode_free/start returned 102 (career already in progress); "
                    f"resuming existing career at turn {turn} instead of failing."
                )
                if isinstance(recovered, dict):
                    recovered["_tp_restore_reasoning"] = restore_reasoning
                return {"success": True, "result": recovered, "resumed": True}
        raise
    if isinstance(result, dict):
        result["_tp_restore_reasoning"] = restore_reasoning
    return {"success": True, "result": result}


def apply_career_result(result):
    global active_account, active_dashboard_data
    result_data = result.get("data", {})
    update_start_state(result_data)
    account = get_account_status(result_data, result)
    chara_info = result_data.get("chara_info") or {}
    if chara_info:
        account["career"] = account.get("career") or {}
        card_id = str(chara_info.get("card_id", account["career"].get("card_id", "")))
        account["career"].update(
            {
                "active": True,
                "card_id": card_id,
                "name": chara_map.get(card_id, f"Unknown ({card_id})"),
                "turn": chara_info.get("turn", 0),
                "scenario_id": chara_info.get("scenario_id", 0),
                "fans": chara_info.get("fans", 0),
                "vital": chara_info.get("vital", 0),
                "max_vital": chara_info.get("max_vital", 0),
            }
        )
    active_account = account
    if active_dashboard_data:
        active_dashboard_data["account"] = account
    return account, chara_info


@app.post("/api/login")
async def login(req: LoginRequest):
    global active_client, active_account, active_dashboard_data, active_start_state, active_parent_cards, active_parent_rank_points, pending_game_auth_config, raw_load_index_response, active_selection
    try:
        chara = None
        cfg = dict(pending_game_auth_config)
        pending_game_auth_config = {}

        active_client = None
        active_account = None
        active_dashboard_data = None
        active_start_state = {}
        active_parent_cards = {}
        active_parent_rank_points = {}
        raw_load_index_response = None
        active_selection = _empty_ui_selection()

        has_form_creds = bool(req.username and req.password)
        if req.steam_id and req.steam_session_ticket:
            sid = str(req.steam_id)
            tkt = str(req.steam_session_ticket)
            print("Using provided Steam ticket")
        elif has_form_creds:
            sid, tkt = get_ticket(req.username, req.password, req.code)
        elif "steam_id" in cfg and "steam_session_ticket" in cfg:
            sid = cfg["steam_id"]
            tkt = cfg["steam_session_ticket"]
            print("Using saved Steam ticket from headless bypass")
        else:
            raise Exception("Steam credentials required")

        cfg.update(
            {
                "steam_id": sid,
                "steam_session_ticket": tkt,
                "steam_username": req.username or cfg.get("steam_username", ""),
                "steam_password_seed": req.password
                or cfg.get("steam_password_seed", ""),
            }
        )

        # Inject spoofed hardware info if present (DO NOT override 'udid' or 'device_id' as it breaks auth crypto/binding)
        for key in [
            "device_name",
            "graphics_device_name",
            "platform_os_version",
            "ip_address",
        ]:
            if key in INSTANCE_CONFIG:
                cfg[key] = INSTANCE_CONFIG[key]

        if not has_fresh_auth_config(cfg):
            raise Exception(
                "Fresh in-game auth capture required; switch to the target in-game account, restart capture, then login again"
            )

        # --- UMATRACKER INJECTION: SAVE CONFIGS FOR HEADLESS MODE ---
        try:
            save_cfg = dict(cfg)
            if "steam_username" in save_cfg:
                save_cfg["steam_username"] = _obfuscate_creds(
                    save_cfg["steam_username"]
                )
            if "steam_password_seed" in save_cfg:
                save_cfg["steam_password_seed"] = _obfuscate_creds(
                    save_cfg["steam_password_seed"]
                )

            _save_auth_config_both(save_cfg, PROFILE_NAME)
            with open(os.path.join(RUNTIME_DIR, "steam_token.txt"), "w") as f:
                f.write(tkt)
            # v6.7.6: also persist the steam token to userdata so it
            # survives version upgrades.  RUNTIME_DIR lives inside the
            # build folder and gets blown away on upgrade; the userdata
            # copy is the authoritative one going forward.
            try:
                user_token_path = _user_steam_token_path(PROFILE_NAME)
                user_token_path.write_text(tkt, encoding="utf-8")
            except Exception as user_exc:
                print(f"[-] userdata steam token write failed: {user_exc}")
            print(f"\n[+] UMATRACKER: Saved keys to {RUNTIME_DIR}!", flush=True)
        except Exception as e:
            print(f"[-] Failed to save keys: {e}")
        # ------------------------------------------------------------

        c = attach_turn_delay(UmaClient(cfg, trace_enabled=False))
        c.on_ticket_refreshed = _persist_refreshed_ticket
        res = c.login()
        if not res:
            raise HTTPException(status_code=401, detail="Game login failed")
        active_client = c

        # BUG #5: login wiped active_selection (line ~4789); restore the persisted
        # picker selection from disk so the chosen trainee / parents / guest /
        # deck / friend survive a `python main.py` restart. The Setup UI reads it
        # back via /api/session -> data["selection"]. `global active_selection`
        # is declared at the top of this handler, so this targets the module global.
        _persisted_sel = _load_active_selection()
        if _persisted_sel:
            active_selection = _persisted_sel

        d = res.get("data", {})
        career_data = None
        if d.get("single_mode_chara_light") or d.get("single_mode_chara"):
            try:
                career_res = c.load_career()
                career_data = career_res.get("data")
            except Exception:
                pass

        account = get_account_status(d, career_data)
        active_account = account
        active_start_state = {}
        active_parent_cards = {}
        active_parent_rank_points = {}
        update_start_state(d)

        umas = []
        card_list = d.get("card_list", [])
        for card in card_list:
            cid = str(card.get("card_id", card.get("id", "")))
            # Prefer the versioned card name ("Air Shakur (unsigned)") so each owned
            # version is distinct in the trainee picker; fall back to the chara name.
            umas.append({"id": cid, "name": card_names_map.get(cid) or chara_map.get(cid, f"Unknown ({cid})")})

        supports = []
        support_card_list = d.get("support_card_list", [])
        for s in support_card_list:
            sid = str(s.get("support_card_id", s.get("id", "")))
            # v7.6: preserve limit-break level + exp so deck bonuses and the
            # owned-card picker can compute accurate per-card effect values.
            lb = int(s.get("limit_break_count", s.get("limit_break", 0)) or 0)
            exp = int(s.get("exp", 0) or 0)
            info = support_map.get(sid)
            if info:
                supports.append(
                    {
                        "id": sid,
                        "name": info["name"],
                        "type": display_support_type(info["type"]),
                        "rarity": info["rarity"],
                        "limit_break": lb,
                        "exp": exp,
                    }
                )
            else:
                supports.append(
                    {
                        "id": sid,
                        "name": f"Unknown ({sid})",
                        "type": "Unknown",
                        "rarity": "?",
                        "limit_break": lb,
                        "exp": exp,
                    }
                )

        # v7.6.2: index owned cards by id so in-game deck cards carry the
        # player's REAL limit break (and exp). Without this, deck cards had no
        # limit_break_count, so the Deck Bonuses panel and the deck-hover
        # tooltip both computed every card's effects at LB0 instead of the
        # owned level.
        owned_by_id = {s["id"]: s for s in supports}

        decks = []
        deck_array = d.get("support_card_deck_array", [])
        for deck in deck_array:
            cards = []
            for cid in deck.get("support_card_id_array", []):
                sid = str(cid)
                owned = owned_by_id.get(sid)
                lb = int(owned.get("limit_break", 0)) if owned else 0
                exp = int(owned.get("exp", 0)) if owned else 0
                info = support_map.get(sid)
                if info:
                    cards.append(
                        {
                            "id": sid,
                            "name": info["name"],
                            "rarity": info["rarity"],
                            "type": display_support_type(info["type"]),
                            "limit_break_count": lb,
                            "exp": exp,
                        }
                    )
                else:
                    cards.append(
                        {
                            "id": sid,
                            "name": f"Unknown ({sid})",
                            "rarity": "?",
                            "type": "?",
                            "limit_break_count": lb,
                            "exp": exp,
                        }
                    )

            decks.append(
                {
                    "id": deck.get("deck_id"),
                    "name": deck.get("name", f'Deck {deck.get("deck_id")}'),
                    "cards": cards,
                }
            )

        parents = []
        trained_chara_list = d.get("trained_chara", [])
        for chara in trained_chara_list:

            raw_id = str(chara.get("card_id", ""))

            if "{" in raw_id or "-" in raw_id or not raw_id.isdigit():
                found = False
                for key, val in chara.items():
                    val_str = str(val)
                    if val_str.isdigit() and len(val_str) >= 4:
                        raw_id = val_str
                        found = True
                        break
                if not found:
                    continue

            cid = raw_id

            tree = {
                "self": {
                    "card_id": cid,
                    "name": chara_map.get(cid, f"Unknown ({cid})"),
                    "factors": [],
                    "wins": get_win_summary(chara.get("win_saddle_id_array", [])),
                },
                "p1": {
                    "card_id": 0,
                    "name": "",
                    "factors": [],
                    "wins": get_win_summary([]),
                },
                "p2": {
                    "card_id": 0,
                    "name": "",
                    "factors": [],
                    "wins": get_win_summary([]),
                },
                "gp1": {
                    "card_id": 0,
                    "name": "",
                    "factors": [],
                    "wins": get_win_summary([]),
                },
                "gp2": {
                    "card_id": 0,
                    "name": "",
                    "factors": [],
                    "wins": get_win_summary([]),
                },
                "gp3": {
                    "card_id": 0,
                    "name": "",
                    "factors": [],
                    "wins": get_win_summary([]),
                },
                "gp4": {
                    "card_id": 0,
                    "name": "",
                    "factors": [],
                    "wins": get_win_summary([]),
                },
            }

            tree["self"]["factors"] = get_factors(get_chara_factor_ids(chara), cid)

            for sc in chara.get("succession_chara_array", []):
                pos = sc.get("position_id")
                sc_cid = sc.get("card_id", 0)
                key = ""
                if pos == 10:
                    key = "p1"
                elif pos == 20:
                    key = "p2"
                elif pos == 11:
                    key = "gp1"
                elif pos == 12:
                    key = "gp2"
                elif pos == 21:
                    key = "gp3"
                elif pos == 22:
                    key = "gp4"

                if key:
                    tree[key]["card_id"] = sc_cid
                    tree[key]["name"] = chara_map.get(
                        str(sc_cid), f"Unknown ({sc_cid})"
                    )
                    tree[key]["factors"] = get_factors(
                        sc.get("factor_id_array", []), sc_cid
                    )
                    tree[key]["wins"] = get_win_summary(
                        sc.get("win_saddle_id_array", [])
                    )

            parents.append(
                {
                    "instance_id": chara.get("trained_chara_id"),
                    "card_id": cid,
                    "name": chara_map.get(cid, f"Unknown ({cid})"),
                    "rank": chara.get("rank", 0),
                    "tree": tree,
                }
            )
            lineage_cards = [int(cid)]
            for sc in chara.get("succession_chara_array", []) or []:
                sc_cid = sc.get("card_id", 0)
                if sc_cid:
                    lineage_cards.append(int(sc_cid))
            active_parent_cards[int(chara.get("trained_chara_id"))] = lineage_cards
            active_parent_rank_points[int(chara.get("trained_chara_id"))] = {
                "rank": chara.get("rank", 0),
                "rank_score": chara.get("rank_score", 0),
            }

        # v2.1: STRICT at login. The login home payload has no real guest arrays,
        # so the broad heuristic used to scoop up random umas as "guest parents"
        # (fixed only on Refresh). Strict returns only genuine rental/guest arrays
        # (usually none here) -> the UI shows the empty "Click Refresh" state until
        # a real pre_single_mode fetch resolves the actual guest parents.
        guest_parents = normalize_guest_parents(d, strict=True)
        active_dashboard_data = {
            "success": True,
            "account": account,
            "umas": umas,
            "supports": supports,
            "decks": decks,
            "parents": parents,
            "guestParents": guest_parents,
            "guestParentsLoaded": bool(guest_parents),
        }
        return active_dashboard_data
    except Exception as e:
        msg = str(e)
        if "STEAM_GUARD_REQUIRED" in msg:
            pending_game_auth_config = cfg
            return {"success": False, "needs_2fa": True}
        detail, cooldown_seconds = friendly_steam_login_error(msg)
        return {"success": False, "detail": detail, "cooldown_seconds": cooldown_seconds}


# --- DIRECT CIRCLE LOOKUP ---
@app.get("/api/circle/{circle_id}")
async def get_specific_circle_data(circle_id: int):
    global active_client
    if not active_client:
        return {"success": False, "detail": "Bot is not logged in."}

    try:
        result = active_client.call(
            "circle/detail", {"circle_id": circle_id, "no_join_user": True}
        )
        data = result.get("data", {})

        info = data.get("circle_info", {})
        if not info:
            return {
                "success": False,
                "detail": f"No data returned for Circle ID {circle_id}.",
            }

        # Grab the Club's Monthly Data
        monthly_ranking = data.get("circle_ranking_this_month", {})
        club_monthly_fans = monthly_ranking.get("point", 0)
        club_monthly_rank = monthly_ranking.get("rank", 0)

        # Parse the members
        members_raw = data.get("summary_user_info_array", [])
        formatted_members = []
        all_time_fans_sum = 0

        for m in members_raw:
            user_fans = m.get("fan", 0)
            all_time_fans_sum += user_fans  # Add this user's fans to the club total

            formatted_members.append(
                {
                    "viewer_id": m.get("viewer_id"),
                    "name": m.get("name", "Unknown Trainer"),
                    "fans": user_fans,
                }
            )

        return {
            "success": True,
            "club_name": info.get("name", "Unknown"),
            "club_monthly_fans": club_monthly_fans,
            "club_rank": club_monthly_rank,
            "total_all_time_fans": all_time_fans_sum,
            "member_count": len(formatted_members),
            "members": formatted_members,
        }
    except Exception as e:
        return {"success": False, "detail": str(e)}


# --- PROFILE PROXY LOOKUP ---
@app.get("/api/club_by_member/{trainer_id}")
async def get_club_by_member(trainer_id: int):
    global active_client
    if not active_client:
        return {"success": False, "detail": "API bridge is not logged in."}

    try:
        print(f"[*] Look up Trainer ID: {trainer_id}...", flush=True)

        # We now use the EXACT payload your sniffer discovered for friend search!
        friend_res = active_client.call(
            "friend/search",
            {"friend_viewer_id": trainer_id, "deleted_response_type": 0},
        )
        friend_data = friend_res.get("data", {})

        user_info = friend_data.get("summary_user_info")
        if (
            not user_info
            and "summary_user_info_array" in friend_data
            and len(friend_data["summary_user_info_array"]) > 0
        ):
            user_info = friend_data["summary_user_info_array"][0]

        if not user_info:
            return {
                "success": False,
                "detail": f"Trainer ID {trainer_id} returned no profile data.",
            }

        target_circle_id = user_info.get("circle_id")
        if not target_circle_id:
            return {
                "success": False,
                "detail": f"Trainer {user_info.get('name', trainer_id)} is not currently in a club.",
            }

        print(f"[+] Found Club ID {target_circle_id}! Fetching roster...", flush=True)
        time.sleep(1.0)

        # Again, using the exact payload for the external club fetch
        details = active_client.call(
            "circle/detail", {"circle_id": target_circle_id, "no_join_user": True}
        )
        details_data = details.get("data", {})

        info = details_data.get("circle_info", {})
        members_raw = (
            details_data.get("circle_user_array")
            or details_data.get("circle_member_array")
            or []
        )

        formatted_members = []
        for m in members_raw:
            formatted_members.append(
                {
                    "viewer_id": m.get("viewer_id"),
                    "name": m.get("name", "Unknown Trainer"),
                    "fans": m.get("fans") or m.get("circle_fans") or 0,
                }
            )

        return {
            "success": True,
            "club_name": info.get("name", "Unknown"),
            "club_id": target_circle_id,
            "total_fans": info.get("total_fans") or info.get("fans", 0),
            "member_count": len(formatted_members),
            "members": formatted_members,
        }

    except Exception as e:
        return {"success": False, "detail": str(e)}


@app.get("/api/session")
async def session_status():
    global active_client, active_dashboard_data, active_account, active_selection
    if not active_client or not active_dashboard_data:
        return {"success": False}

    data = dict(active_dashboard_data)
    if active_account:
        data["account"] = active_account
    data["selection"] = active_selection
    data["success"] = True
    return data


def _user_selection_path():
    """v6.7.9: path for the persisted ``active_selection`` so the
    Smart Race Solver Settings picker survives server restarts.  When
    userdata is enabled this lives outside the build folder, so picker
    state also survives version upgrades.
    """
    return Path(USERDATA_DIR) / "active_selection.json"


def _save_active_selection():
    """v6.7.9: persist ``active_selection`` to disk so the dashboard
    Character Profile panel can resolve to the user's picked trainee
    between runs / after restarts.  Best-effort: failures are silent
    so they never break the picker UX."""
    try:
        path = _user_selection_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(active_selection, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_active_selection():
    """Read the persisted ``active_selection`` (if any) at server start.
    Falls back to the empty selection on any error."""
    try:
        path = _user_selection_path()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # Sanity-check the shape: must have the expected keys.
                for k in ("deck", "friend", "trainee", "veterans", "guestParents"):
                    if k not in data:
                        return None
                return data
    except Exception:
        pass
    return None


# v6.7.9: rehydrate the picker selection from disk on startup so the
# Character Profile panel can resolve to the user's last-picked trainee
# even before any career has been started.
_persisted_selection = _load_active_selection()
if _persisted_selection:
    active_selection = _persisted_selection


class UISelectionRequest(BaseModel):
    selection: dict


@app.post("/api/selection")
async def update_selection(req: UISelectionRequest):
    global active_selection
    active_selection = req.selection
    # v6.7.9: persist so the picker survives restarts.
    _save_active_selection()
    return {"success": True}


@app.post("/api/logout")
async def logout():
    global active_client, active_account, active_dashboard_data, active_start_state, active_parent_cards, active_parent_rank_points, raw_load_index_response, pending_game_auth_config, active_selection
    active_client = None
    active_account = None
    active_dashboard_data = None
    active_start_state = {}
    active_parent_cards = {}
    active_parent_rank_points = {}
    raw_load_index_response = None
    pending_game_auth_config = {}
    active_selection = _empty_ui_selection()
    # v6.7.9: also clear the persisted file so a stale selection from
    # the previous user doesn't leak across logouts.
    _save_active_selection()
    return {"success": True}


@app.post("/api/career/start")
async def start_career(req: StartCareerRequest):
    try:
        started = start_career_from_request(req)
        if not started.get("success"):
            return started
        account, chara_info = apply_career_result(started["result"])
        return {"success": True, "account": account, "chara_info": chara_info}
    except Exception as e:
        detail = str(e)
        # A 500/501 at career start is usually a transient server hiccup or an
        # invalid selection; surface something actionable instead of the raw code.
        # (Guest/rental-parent 500s are caught earlier with a more specific message.)
        if "500" in detail or "501" in detail:
            detail = (
                "The game server rejected the career start (HTTP 500/501). This is "
                "usually a temporary server hiccup or an invalid selection (deck, "
                "parent, or scenario). Wait a moment and try again; if it keeps "
                "happening, re-check your Setup selections. Details: " + detail
            )
        return {"success": False, "detail": detail}


backend_loop_thread = None
backend_loop_stop = False


def _effective_run_count(req):
    try:
        raw = int(getattr(req, "run_count", 1) or 0)
    except Exception:
        raw = 1
    # Backward compatibility: the old LOOP toggle sent dev_mode=true with no run_count.
    if getattr(req, "dev_mode", False) and raw == 1:
        return 0
    return max(0, raw)


def _validate_loop_constraints(req, target):
    # Infinite looping IS allowed with a guest/rental parent now: each start
    # revalidates+rewrites the rental id, and the loop auto-stops when the guest is
    # no longer borrowable (fatal_start) or the daily borrow cap is reached
    # (default 5) -- both handled in manage_career_loop.
    return None


def manage_career_loop(req, preset, initial_result):
    global backend_loop_stop, active_account, active_client
    max_steps = max(1, min(int(req.max_steps or 2500), 3000))
    target = _effective_run_count(req)
    consecutive_fails = 0
    runs_done = 0
    current_result = initial_result

    while not backend_loop_stop:
        runs_done += 1
        career_runner.goal_lookahead = _goal_lookahead_enabled()
        career_runner.set_loop_info(runs_done, target)
        career_runner.start(
            active_client,
            preset,
            current_result,
            max_steps,
            burn_clocks=req.burn_clocks,
            carats_enabled=req.carats_enabled,
            max_clocks_per_career=req.max_clocks_per_career,
            clocks_g1_debut_only=getattr(req, "clocks_g1_debut_only", False),
            max_retries_per_race=getattr(req, "max_retries_per_race", -1),
            finalize_single_runs=getattr(req, "finalize_single_runs", False),
            dev_mode=True,
        )

        while career_runner.snapshot().get("running"):
            if backend_loop_stop:
                career_runner.stop()
                return
            time.sleep(1)

        status = career_runner.snapshot()
        # Record the just-completed career into the (session-only) Career History.
        # In loop mode the finished snapshot is transient — the next career starts
        # before the dashboard poll can observe it — so the poll-based recorder on
        # /api/career/runner misses EVERY looped career (history showed nothing even
        # before restart). Record it explicitly here; run_id de-dup makes it safe if
        # the poll also catches it. Still in-memory only (cleared on restart).
        try:
            record_completed_career_from_snapshot(status)
        except Exception:
            pass
        if status.get("last_error"):
            consecutive_fails += 1
            if consecutive_fails >= 3:
                break
        else:
            consecutive_fails = 0

        if target and runs_done >= target:
            print(f"career loop target reached ({runs_done}/{target})", flush=True)
            break

        # Guest/rental parent: each completed run consumes one daily borrow. Stop at
        # the daily cap (default 5, override via mant_config.guest_daily_borrow_cap).
        # The loop also auto-stops earlier if the guest is no longer borrowable
        # (fatal_start below) -- so a finite count is no longer required.
        if _has_rental_parent(req):
            _mc = (preset.get("mant_config") if isinstance(preset, dict) else None) or {}
            guest_cap = int(_mc.get("guest_daily_borrow_cap") or 5)
            if guest_cap > 0 and runs_done >= guest_cap:
                print(f"guest-parent daily borrow cap reached ({runs_done}/{guest_cap}); stopping loop", flush=True)
                break

        for _ in range(6):
            if backend_loop_stop:
                return
            time.sleep(1)

        started_ok = False
        while not started_ok and not backend_loop_stop:
            try:
                # start_career_from_request always calls _pre_start_refresh(), which
                # refreshes and rewrites guest/rental parent ids before every new run.
                started = start_career_from_request(req)
                if not started.get("success"):
                    consecutive_fails += 1
                    if started.get("fatal_start"):
                        print(f"career loop stopped before next start: {started.get('detail')}", flush=True)
                        return
                    if consecutive_fails >= 5:
                        break
                    for _ in range(15):
                        if backend_loop_stop:
                            return
                        time.sleep(1)
                    continue
                current_result = started["result"]
                account, chara_info = apply_career_result(current_result)
                active_account = account
                started_ok = True
                consecutive_fails = 0
            except Exception:
                consecutive_fails += 1
                if consecutive_fails >= 5:
                    break
                for _ in range(15):
                    if backend_loop_stop:
                        return
                    time.sleep(1)

        if not started_ok:
            break


@app.post("/api/career/run")
async def run_career(req: RunCareerRequest):
    global active_account, backend_loop_thread
    if career_runner.snapshot().get("running") or (
        backend_loop_thread and backend_loop_thread.is_alive()
    ):
        return {"success": False, "detail": "Career runner loop already active"}
    run_target = _effective_run_count(req)
    loop_error = _validate_loop_constraints(req, run_target)
    if loop_error:
        return {"success": False, "detail": loop_error}
    preset_name = (req.preset_name or "").strip()
    preset = preset_store.read_one(preset_name) if preset_name else preset_store.read_one(None)
    if not preset:
        if preset_name:
            return {"success": False, "detail": f"Preset missing: {preset_name}"}
        return {"success": False, "detail": "No presets available"}
    preset_name = preset.get("name", "")
    req.preset_name = preset_name
    req.scenario_id = int(preset.get("scenario_id") or 4)
    runtime_preset = dict(preset)
    # #7 — when the value-per-SP skill optimizer is toggled on, run the buyer in
    # "optimize_rank" mode. When off, leave the preset's own strategy untouched
    # (default "best_skills_first"), so nothing changes unless the user opts in.
    if _skill_optimizer_enabled():
        runtime_preset["skill_spending_strategy"] = "optimize_rank"
    race_mode = str(getattr(req, "race_planner_mode", "") or "smart").strip().lower()
    if race_mode not in {"manual", "smart"}:
        race_mode = "smart"
    # v7.2 — Defense in depth. If the request explicitly says "smart" but the
    # preset itself was saved as "manual" with a non-empty extra_race_list,
    # respect the user's persisted choice instead of silently overriding.
    # Without this, a stale UI state (e.g. user reloaded the page before the
    # racePlannerMode localStorage was reapplied) could downgrade them to
    # smart mode and run dirt races they didn't pick.
    saved_source = str((preset or {}).get("extra_race_list_source") or "").strip().lower()
    saved_list = (preset or {}).get("extra_race_list") or []
    if saved_source == "manual" and saved_list and race_mode != "manual":
        race_mode = "manual"
    runtime_preset["extra_race_list_source"] = race_mode
    if race_mode == "manual" and getattr(req, "manual_race_ids", None):
        manual_ids = []
        for value in req.manual_race_ids or []:
            try:
                manual_ids.append(int(value))
            except Exception:
                continue
        runtime_preset["extra_race_list"] = manual_ids
    try:
        account = active_account or {}
        career = account.get("career") or {}
        load_data = {}
        # UNCONDITIONAL live-state probe: always ask the game whether a career is
        # in progress (e.g. one the user started MANUALLY in-game), instead of
        # trusting our possibly-stale cached active flag. Without this, a cold
        # resume right after server start misses the manual career and falls
        # through to a fresh start that ignores the in-game trainee/parents/deck/
        # friend. When no career is in progress this is a harmless read that leaves
        # career.active False, so a genuine fresh start is unaffected.
        if active_client:
            try:
                index_result = active_client.call("load/index")
                load_data = index_result.get("data", {})
                update_start_state(load_data)
                account = get_account_status(load_data)
                active_account = account
                career = account.get("career") or {}
            except Exception as _probe_exc:
                print(f"[career/run] live-state probe failed ({_probe_exc}); using cached account state", flush=True)

        result = None
        chara_info = None
        if career.get("active"):
            try:
                career_result = active_client.load_career()
                career_data = career_result.get("data", {})

                account = get_account_status(load_data, career_result)
                career_status = account.get("career") or {}
                chara_info = career_data.get("chara_info") or {}

                # Self-heal: a genuinely-resumable career must carry a live
                # chara_info + card_id. If load_career came back empty/incomplete
                # (e.g. a stale local active flag, or a non-looped run that
                # self-terminated at the finale), DON'T crash on int(None) -- fall
                # through to a clean start so the user never has to restart the bot.
                # All numeric coercions below are 0-safe for the same reason
                # (matched_deck_id, friend/parent ids can legitimately be None).
                if not chara_info:
                    raise ValueError("stale/incomplete active career: no chara_info")
                # resume_career_fields raises ValueError on a missing card_id and
                # 0-safe coerces the rest (deck_id/friend/parent ids can be None) ->
                # no int(None) crash; the except below self-heals to a fresh start.
                fields = resume_career_fields(career_status)

                active_account = account
                req.card_id = fields["card_id"]
                req.support_card_ids = fields["support_card_ids"]
                req.friend_viewer_id = fields["friend_viewer_id"]
                req.friend_card_id = fields["friend_card_id"]
                req.parent_id_1 = fields["parent_id_1"]
                req.parent_id_2 = fields["parent_id_2"]
                req.deck_id = fields["deck_id"]

                if active_dashboard_data:
                    active_dashboard_data["account"] = account
                result = career_result
            except Exception as resume_exc:
                print(f"[career/run] resume of active career failed ({resume_exc}); "
                      f"clearing stale state and starting fresh", flush=True)
                _clear_finished_career_setup_state(clear_selection=False)
                result = None
        if result is None:
            started = start_career_from_request(req)
            if not started.get("success"):
                return started
            result = started["result"]
            account, chara_info = apply_career_result(result)

        apply_deck_type_counts(runtime_preset, req=req, chara_info=chara_info)

        looping = run_target != 1
        if looping:
            backend_loop_stop = False
            req.dev_mode = True
            backend_loop_thread = threading.Thread(
                target=manage_career_loop, args=(req, runtime_preset, result), daemon=True
            )
            backend_loop_thread.start()
            time.sleep(0.5)
        else:
            career_runner.goal_lookahead = _goal_lookahead_enabled()
            career_runner.set_loop_info(1, 1)
            career_runner.start(
                active_client,
                runtime_preset,
                result,
                max(1, min(int(req.max_steps or 2500), 3000)),
                burn_clocks=req.burn_clocks,
                carats_enabled=req.carats_enabled,
                max_clocks_per_career=req.max_clocks_per_career,
                clocks_g1_debut_only=getattr(req, "clocks_g1_debut_only", False),
                max_retries_per_race=getattr(req, "max_retries_per_race", -1),
                finalize_single_runs=getattr(req, "finalize_single_runs", False),
                dev_mode=False,
            )

        return {
            "success": True,
            "account": account,
            "chara_info": chara_info,
            "runner": career_runner.snapshot(),
        }
    except Exception as e:
        return {"success": False, "detail": str(e)}






class AccountsConfigRequest(BaseModel):
    accounts: list[dict] = []


manager_process = None


def _accounts_path():
    # v6.7.6: stored in userdata when an external userdata folder is
    # configured so the account list survives version upgrades.  Falls
    # back to the in-build location if userdata isn't being used.
    return _user_accounts_path()


def _default_accounts():
    return [
        {"name": PROFILE_NAME or "default", "port": int(PORT), "auto_restart": True, "stale_restart_seconds": 900}
    ]


def _read_accounts_config():
    path = _accounts_path()
    if not path.exists():
        accounts = _default_accounts()
        path.write_text(json.dumps(accounts, indent=2), encoding="utf-8")
        return accounts
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _normalize_account_name(value, fallback):
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or fallback)).strip("_")
    return name or fallback


def _normalize_account_config_name(value, fallback_name):
    raw = str(value or f"{fallback_name}.json").strip()
    raw = raw.replace("\\", "/").split("/")[-1]
    raw = re.sub(r"[^a-zA-Z0-9_.-]+", "_", raw).strip("._")
    if not raw:
        raw = f"{fallback_name}.json"
    if not raw.lower().endswith(".json"):
        raw = f"{raw}.json"
    return raw


def _validate_accounts_config(accounts):
    if not isinstance(accounts, list):
        raise HTTPException(status_code=400, detail="Accounts payload must be a list.")

    clean = []
    seen_ports = {}
    seen_names = {}
    for idx, account in enumerate(accounts):
        if not isinstance(account, dict):
            raise HTTPException(status_code=400, detail=f"Account row {idx + 1} must be an object.")

        name = _normalize_account_name(account.get("name"), f"account{idx + 1}")
        name_key = name.lower()
        if name_key in seen_names:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate account name '{name}' used by row {seen_names[name_key] + 1} and row {idx + 1}. Account names must be unique.",
            )
        seen_names[name_key] = idx

        try:
            port = int(account.get("port"))
        except Exception:
            raise HTTPException(status_code=400, detail=f"Account '{name}' has an invalid port. Use a number from 1024 to 65535.")

        if port < 1024 or port > 65535:
            raise HTTPException(status_code=400, detail=f"Account '{name}' port {port} is outside the allowed range 1024-65535.")

        if port in seen_ports:
            other_name = seen_ports[port]
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate port {port} used by '{other_name}' and '{name}'. Each account must use a unique port.",
            )
        seen_ports[port] = name

        stale_restart_seconds = account.get("stale_restart_seconds", 900)
        try:
            stale_restart_seconds = int(stale_restart_seconds)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Account '{name}' stale restart seconds must be a number.")
        stale_restart_seconds = max(60, min(stale_restart_seconds, 86400))

        config_name = _normalize_account_config_name(account.get("config"), name)

        clean.append({
            "name": name,
            "config": config_name,
            "port": port,
            "auto_restart": bool(account.get("auto_restart", True)),
            "stale_restart_seconds": stale_restart_seconds,
        })

    if not clean:
        clean = _default_accounts()

    return clean


def _write_accounts_config(accounts):
    path = _accounts_path()
    clean = _validate_accounts_config(accounts)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    tmp.replace(path)
    return clean


def _health_for_port(port, timeout=6.0):
    import urllib.request
    import socket
    port = int(port)
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        # v2.0: timeout raised 1.5s -> 6s (matches the manager). /api/health calls
        # snapshot() and can exceed 1.5s mid-career, which falsely flipped a healthy
        # instance to "offline".
        with urllib.request.urlopen(url, timeout=timeout) as res:
            payload = json.loads(res.read().decode("utf-8"))
            payload["reachable"] = True
            return payload
    except Exception as exc:
        # v2.0: fall back to a bare TCP connect. If the port is accepting
        # connections, the instance IS up (just slow/busy answering /api/health) --
        # report reachable instead of offline.
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.5):
                return {"success": True, "reachable": True, "source": "tcp-probe",
                        "detail": "port is listening (health endpoint slow/busy)"}
        except Exception:
            pass
        return {"success": False, "reachable": False, "detail": str(exc)}


@app.get("/api/accounts")
async def api_accounts():
    accounts = _read_accounts_config()
    return {"success": True, "accounts": accounts, "path": str(_accounts_path())}


@app.post("/api/accounts")
async def api_save_accounts(req: AccountsConfigRequest):
    accounts = _write_accounts_config(req.accounts)
    return {"success": True, "accounts": accounts, "path": str(_accounts_path())}


@app.get("/api/accounts/status")
async def api_accounts_status():
    accounts = _read_accounts_config()
    manager_status_path = Path(DIR) / "uma_runtime" / "manager_status.json"
    manager_status = None
    manager_by_port = {}
    manager_by_name = {}
    if manager_status_path.exists():
        try:
            manager_status = json.loads(manager_status_path.read_text(encoding="utf-8"))
            for child in manager_status.get("children", []) or []:
                manager_by_port[int(child.get("port") or 0)] = child
                manager_by_name[str(child.get("name") or "")] = child
        except Exception:
            manager_status = None

    rows = []
    now = time.time()
    self_port = int(PORT)
    _self_snap = career_runner.snapshot() or {}
    self_running = bool(_self_snap.get("running"))
    _self_lt = _self_snap.get("lifetime") or {}
    self_runs = int(_self_lt.get("careers_completed") or 0)
    self_fans = int(_self_lt.get("total_fans_gained_live") or _self_lt.get("total_fans_gained") or 0)
    seen_self = False
    for account in accounts:
        port = int(account.get("port") or 1616)
        name = str(account.get("name") or "")
        # v2.0: the dashboard serving this request is obviously online -- never
        # report the live instance as offline against itself.
        if port == self_port:
            seen_self = True
            rows.append({**account, "runs": self_runs, "fans": self_fans, "health": {
                "success": True, "reachable": True, "source": "self",
                "process_running": True, "runner_running": self_running,
                "detail": "this dashboard instance",
            }})
            continue
        direct_health = _health_for_port(port)
        child = manager_by_port.get(port) or manager_by_name.get(name) or {}
        child_health = child.get("last_health") or {}
        child_running = bool(child.get("running"))

        health = dict(child_health) if child_health else {}
        if direct_health.get("reachable"):
            health.update(direct_health)
            health["source"] = direct_health.get("source") or "direct"
        elif child_running and child_health:
            health.update({
                "reachable": True,
                "source": "manager-cache",
                "detail": "",
            })
        else:
            health = direct_health
            health["source"] = "direct-error"
            # v2.0: help the user spot the most common cause -- a port that no
            # instance is listening on / a roster port that doesn't match the bot.
            health["hint"] = (
                f"Nothing answering on port {port}. This dashboard runs on port {self_port}. "
                f"Check the account's port matches the running bot, or launch it via the Manager."
            )

        health["process_running"] = child_running or bool(health.get("reachable"))
        health["manager_last_health_at"] = child.get("last_health_at", 0)
        health["manager_last_health_age"] = int(max(0, now - float(child.get("last_health_at") or 0))) if child else None
        health["manager_error"] = child.get("last_health_error", "")
        rows.append({**account, "health": health})

    # v2.0: if the live instance isn't in the roster, surface it anyway so it's
    # never invisible / shown offline.
    if not seen_self:
        rows.insert(0, {"name": PROFILE_NAME, "port": self_port, "auto_added": True,
            "runs": self_runs, "fans": self_fans, "health": {
            "success": True, "reachable": True, "source": "self",
            "process_running": True, "runner_running": self_running,
            "detail": "this dashboard instance (auto-added)",
        }})
    return {"success": True, "accounts": rows, "manager_status": manager_status}


@app.post("/api/accounts/manager/start")
async def api_accounts_manager_start():
    global manager_process
    if manager_process and manager_process.poll() is None:
        return {"success": True, "already_running": True, "pid": manager_process.pid}
    log_dir = Path(DIR) / "uma_runtime" / "manager_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(log_dir / "dashboard-manager.log", "a", encoding="utf-8")
    manager_env = os.environ.copy()
    # Ensure the manager (and the per-account children it spawns) resolve the
    # SAME userdata folder the dashboard uses. The account roster lives at
    # ``USERDATA_DIR/accounts.json`` -- usually an external sibling folder --
    # so without this the manager would read a stale/sample accounts.json from
    # the build folder and never launch the accounts configured here.
    manager_env["ICARUS_USERDATA_DIR"] = str(USERDATA_DIR)
    manager_process = subprocess.Popen(
        [sys.executable, "manager.py"],
        cwd=DIR,
        env=manager_env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return {"success": True, "pid": manager_process.pid}


@app.get("/api/stream")
async def api_event_stream():
    """Server-Sent Events feed of live game-API calls (off the event bus the client
    publishes to) — a real-time alternative/supplement to polling. Emits compact,
    SECRET-FREE events {ts, dir, ep, req_id, rc} only; never request payloads. The
    dashboard still polls; this is additive."""
    import queue as _queue
    from fastapi.responses import StreamingResponse
    from career_bot import event_bus

    q = event_bus.subscribe()

    async def gen():
        last_ka = time.time()
        try:
            yield "retry: 3000\n\n"
            yield f"data: {json.dumps({'dir': 'OPEN', 'ep': 'stream', 'ts': time.time()})}\n\n"
            while True:
                drained = 0
                while True:
                    try:
                        evt = q.get_nowait()
                    except _queue.Empty:
                        break
                    yield f"data: {json.dumps(evt)}\n\n"
                    drained += 1
                now = time.time()
                if drained == 0 and now - last_ka >= 15:
                    last_ka = now
                    yield ": keepalive\n\n"  # SSE comment keeps the connection alive
                await asyncio.sleep(0.5)
        finally:
            event_bus.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
async def api_health():
    runner = career_runner.snapshot()
    account = active_account or {}
    career = account.get("career") or {}
    logged_in = active_client is not None
    runner_running = bool(runner.get("running"))
    career_active = bool(career.get("active"))
    last_heartbeat = float(runner.get("last_heartbeat") or runner.get("last_action_at") or 0)
    stale_seconds = int(runner.get("stale_seconds", 0) or 0)
    if runner_running and last_heartbeat:
        stale_seconds = int(max(0, time.time() - last_heartbeat))
    waiting_for_server = bool(runner.get("waiting_for_server"))
    if waiting_for_server:
        state = "waiting-server"
    elif runner_running:
        state = "running"
    elif logged_in and career_active:
        state = "career-open"
    elif logged_in:
        state = "logged-in"
    else:
        state = "booted"
    chara = runner.get("current_chara") or {}
    return {
        "success": True,
        "profile": PROFILE_NAME,
        "port": PORT,
        "state": state,
        "logged_in": logged_in,
        "career_active": career_active,
        "runner_running": runner_running,
        "runner_stale_seconds": stale_seconds,
        "runner_last_error": runner.get("last_error", ""),
        "runner_crashed": (not runner_running) and bool(runner.get("last_error")) and not bool(runner.get("finished")),
        "recoveries": runner.get("recoveries", 0),
        "recent_server_rejects": runner.get("recent_server_rejects", 0),
        "waiting_for_server": waiting_for_server,
        "server_wait_reason": runner.get("server_wait_reason", ""),
        "run_id": runner.get("run_id", ""),
        "turn": runner.get("turn", career.get("turn", 0)),
        "last_action": runner.get("last_action", ""),
        "last_heartbeat": last_heartbeat,
        # Career summary for the multi-account overview.
        "fans": runner.get("fans_current", 0),
        "fans_per_hour": runner.get("fans_per_hour", 0),
        "vital": chara.get("vital"),
        "max_vital": chara.get("max_vital"),
        "motivation": chara.get("motivation"),
        "card_id": chara.get("card_id"),
        "loop_index": runner.get("loop_index", 0),
        "loop_target": runner.get("loop_target", 0),
        "pid": os.getpid(),
        "updated_at": time.time(),
    }


def _latest_snapshot_path():
    runner = career_runner.snapshot()
    candidate = runner.get("last_state_snapshot")
    if candidate and os.path.exists(candidate):
        return Path(candidate)
    root = Path(os.environ.get("UMA_RUNTIME_DIR", RUNTIME_DIR)) / "state_snapshots"
    if not root.exists():
        return None
    files = sorted(root.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0] if files else None


@app.get("/api/career/snapshots/latest")
async def latest_career_snapshot(limit: int = 120):
    path = _latest_snapshot_path()
    if not path:
        return {"success": False, "detail": "No state snapshots found", "rows": []}
    # v2.1: read off the event loop so a large snapshot file can't block the
    # single asyncio worker and stall concurrent /api/career/runner polls (which
    # is what could freeze the live UI).
    def _read_rows():
        out = []
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-max(1, min(int(limit or 120), 1000)):]
        for line in lines:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
        return out
    try:
        rows = await asyncio.to_thread(_read_rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"success": True, "path": str(path), "count": len(rows), "rows": rows}


@app.get("/api/career/snapshots/latest/download")
async def download_latest_career_snapshot():
    path = _latest_snapshot_path()
    if not path:
        raise HTTPException(status_code=404, detail="No state snapshots found")
    return FileResponse(path, filename=path.name, media_type="application/jsonl")




# --- P1a: TTL + off-thread cache for heavy poll endpoints --------------------
# These endpoints read large jsonl aggregates synchronously; polled every 1.5-2s
# they starve the event loop and stall the live panels. We memo the result for a
# short TTL and run the heavy work in a worker thread so the loop stays free.
_POLL_CACHE = {}
_POLL_CACHE_LOCK = threading.Lock()
_POLL_CACHE_INFLIGHT = {}


async def _cached_poll(key, ttl, fn):
    now = time.time()
    with _POLL_CACHE_LOCK:
        ent = _POLL_CACHE.get(key)
        if ent and (now - ent[0]) < ttl:
            return ent[1]
        fut = _POLL_CACHE_INFLIGHT.get(key)
        if fut is None:
            fut = asyncio.ensure_future(asyncio.to_thread(fn))
            _POLL_CACHE_INFLIGHT[key] = fut
            owner = True
        else:
            owner = False
    try:
        result = await fut
    finally:
        if owner:
            with _POLL_CACHE_LOCK:
                _POLL_CACHE[key] = (time.time(), result)
                _POLL_CACHE_INFLIGHT.pop(key, None)
    return result


@app.get("/api/diagnostics/summary")
async def diagnostics_summary():
    return await _cached_poll(
        "diagnostics_summary", 5.0,
        lambda: diagnostics.build_summary(base_dir, career_runner.snapshot()),
    )


@app.get("/api/diagnostics/bundle")
async def diagnostics_bundle():
    path = diagnostics.create_bundle(base_dir, career_runner.snapshot())
    return FileResponse(path, filename=path.name, media_type="application/zip")





@app.get("/api/ai/status")
async def ai_dataset_status():
    """Return local AI-ready dataset counts and advisor aggregate status."""
    return await _cached_poll(
        "ai_status", 10.0, lambda: ai_dataset.dataset_status(base_dir)
    )


@app.post("/api/ai/rebuild-dataset")
async def ai_rebuild_dataset():
    """Rebuild AI JSONL exports from existing career logs.

    This is an offline maintenance action. It does not alter live career logic.
    """
    return ai_dataset.rebuild_from_career_logs(base_dir, build_version=_build_version())


@app.post("/api/ai/import-logs")
async def ai_import_previous_logs(req: AiImportLogsRequest):
    """Import career logs from an older build/runtime folder or zip.

    The import path is resolved by the local Pre Icarus server, so users can paste
    a Windows path such as ``C:/UmamusumeChatGPT/OldBuild`` or a zip file
    path. Gameplay logs, AI-safe aggregates, and settings presets are imported;
    auth files are ignored.
    """
    result = ai_dataset.import_previous_logs(
        base_dir,
        req.source_path,
        rebuild=bool(req.rebuild_dataset),
        build_version=_build_version(),
        import_presets=bool(req.import_presets),
    )
    if result.get("success") and req.train_after_import:
        try:
            result["training"] = ai_trainer.train_once(base_dir, reason="import_previous_logs", rebuild_stats=True)
        except Exception as exc:
            result["training_error"] = f"{type(exc).__name__}: {exc}"
    return result


@app.get("/api/ai/advisor/latest")
async def ai_advisor_latest():
    return await _cached_poll(
        "ai_advisor_latest", 10.0, lambda: ai_advisor.post_run_advice(base_dir)
    )


@app.get("/api/ai/dataset/download")
async def ai_dataset_download(kind: str = "turn_decisions"):
    allowed = ai_dataset.DATASET_FILES
    if kind not in allowed:
        raise HTTPException(status_code=400, detail="Unknown dataset kind")
    path = ai_dataset.runtime_output_root(base_dir) / "ai" / allowed[kind]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset has not been created yet")
    return FileResponse(path, filename=path.name, media_type="application/jsonl")






@app.get("/api/ai/local-llm/config")
async def ai_local_llm_config_get():
    return {"success": True, "config": local_llm.latest_payload(base_dir).get("config", {})}


@app.post("/api/ai/local-llm/config")
async def ai_local_llm_config_post(req: dict):
    cfg = local_llm.save_config(base_dir, req or {})
    latest = local_llm.latest_payload(base_dir)
    return {"success": True, "config": latest.get("config", {}), "saved_config": {k: v for k, v in cfg.items() if k != "api_key"}}


@app.post("/api/ai/local-llm/test")
async def ai_local_llm_test():
    return local_llm.test_connection(base_dir)


@app.post("/api/ai/local-llm/analyze-latest-run")
async def ai_local_llm_analyze_latest_run(req: dict = None):
    force = bool((req or {}).get("force"))
    return local_llm.analyze_latest_run(base_dir, force=force)


@app.post("/api/ai/local-llm/shadow-advice")
async def ai_local_llm_shadow_advice(req: dict = None):
    payload = req or {}
    force = bool(payload.get("force"))
    limit = int(payload.get("limit") or 12)
    return local_llm.shadow_advice(base_dir, force=force, limit=limit)


@app.get("/api/ai/local-llm/latest")
async def ai_local_llm_latest():
    return local_llm.latest_payload(base_dir)


@app.get("/api/ai/auto-training/status")
async def ai_auto_training_status():
    return ai_trainer.trainer_status(base_dir)


@app.get("/api/ai/auto-training/config")
async def ai_auto_training_config_get():
    return {"success": True, "config": ai_trainer.load_auto_config(base_dir)}


@app.post("/api/ai/auto-training/config")
async def ai_auto_training_config_post(req: dict):
    return {"success": True, "config": ai_trainer.save_auto_config(base_dir, req or {})}


@app.post("/api/ai/train-now")
async def ai_train_now():
    return ai_trainer.train_once(base_dir, reason="manual", rebuild_stats=True)


@app.get("/api/ai/post-run/latest")
async def ai_latest_post_run_report():
    path = ai_trainer.ai_root(base_dir) / "post_run_reports" / "latest_post_run_report.json"
    if not path.exists():
        return {"success": False, "detail": "No AI post-run report has been generated yet."}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["success"] = True
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/ai/model/download")
async def ai_model_download(kind: str = "policy_adjustments"):
    allowed = ai_trainer.MODEL_FILES
    if kind not in allowed:
        raise HTTPException(status_code=400, detail="Unknown model kind")
    path = ai_trainer.ai_root(base_dir) / allowed[kind]
    if not path.exists():
        raise HTTPException(status_code=404, detail="AI model artifact has not been created yet")
    media = "application/json" if path.suffix == ".json" else "text/plain"
    return FileResponse(path, filename=path.name, media_type=media)




@app.get("/api/ai/safe-debug-bundle")
async def ai_safe_debug_bundle():
    path = ai_trainer.create_safe_debug_bundle(base_dir)
    return FileResponse(path, filename=path.name, media_type="application/zip")

@app.get("/api/ai/dashboard")
async def ai_dashboard():
    return ai_trainer.latest_dashboard(base_dir)


@app.get("/api/ai/shadow/latest")
async def ai_shadow_latest():
    return ai_trainer.latest_shadow_report(base_dir)


@app.get("/api/ai/backtest/latest")
async def ai_backtest_latest():
    return ai_trainer.latest_backtest_report(base_dir)


@app.get("/api/ai/config-suggestions/latest")
async def ai_config_suggestions_latest():
    return ai_trainer.latest_config_suggestions(base_dir)


@app.get("/api/ai/style-adaptation/latest")
async def ai_style_adaptation_latest():
    return ai_trainer.latest_style_adaptation(base_dir)


@app.get("/api/career/decision-trace/latest")
async def latest_decision_trace(limit: int = 80):
    runner = career_runner.snapshot()
    path = runner.get("last_decision_trace")
    if not path or not os.path.exists(path):
        root = Path(os.environ.get("UMA_RUNTIME_DIR", RUNTIME_DIR)) / "decision_traces"
        if root.exists():
            files = sorted(root.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
            path = str(files[0]) if files else ""
    if not path or not os.path.exists(path):
        return {"success": False, "detail": "No decision traces found", "rows": []}
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-max(1, min(int(limit or 80), 500)): ]
        for line in lines:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"success": True, "path": path, "count": len(rows), "rows": rows}


@app.get("/api/career/decision-trace/latest/download")
async def download_latest_decision_trace():
    runner = career_runner.snapshot()
    path = runner.get("last_decision_trace")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No decision trace found")
    return FileResponse(path, filename=Path(path).name, media_type="application/jsonl")




def _history_safe_int(value, default=0):
    try:
        return int(value or default)
    except Exception:
        return default


CAREER_RANK_LABEL_BY_ID = {
    1: "G", 2: "G+", 3: "F", 4: "F+", 5: "E", 6: "E+",
    7: "D", 8: "D+", 9: "C", 10: "C+", 11: "B", 12: "B+",
    13: "A", 14: "A+", 15: "S", 16: "S+", 17: "SS", 18: "SS+",
}


def _history_rank_from_rating(value):
    rating = _history_safe_int(value, 0)
    if not rating:
        return ""
    for row in career_rank_thresholds or []:
        try:
            min_value = int(row.get("min_value") or 0)
            max_value = int(row.get("max_value") or 0)
            rank_id = int(row.get("id") or 0)
        except Exception:
            continue
        if min_value <= rating <= max_value:
            return CAREER_RANK_LABEL_BY_ID.get(rank_id, str(rank_id))

    # Compatibility fallback for old installs that have not generated the
    # master-data threshold file yet.
    if rating >= 30000:
        return "UF"
    if rating >= 24000:
        return "UE"
    if rating >= 20000:
        return "UG"
    if rating >= 17000:
        return "SS+"
    if rating >= 14500:
        return "S"
    if rating >= 12100:
        return "A+"
    if rating >= 10000:
        return "A"
    if rating >= 8200:
        return "B+"
    if rating >= 6500:
        return "B"
    if rating >= 4900:
        return "C+"
    if rating >= 3500:
        return "C"
    return "D"


APTITUDE_LABEL_BY_VALUE = {
    1: "G",
    2: "F",
    3: "E",
    4: "D",
    5: "C",
    6: "B",
    7: "A",
    8: "S",
}


def _aptitude_label(value):
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        clean = value.strip()
        if not clean:
            return ""
        if not clean.isdigit():
            return clean.upper()
        value = clean
    try:
        numeric = int(value)
    except Exception:
        return str(value or "").upper()
    return APTITUDE_LABEL_BY_VALUE.get(numeric, str(value))


def _history_normalize_aptitudes(aptitudes):
    aptitudes = aptitudes or {}
    def norm(value):
        return _aptitude_label(value)
    return {
        "track": {
            "turf": norm((aptitudes.get("track") or {}).get("turf") or aptitudes.get("Turf")),
            "dirt": norm((aptitudes.get("track") or {}).get("dirt") or aptitudes.get("Dirt")),
        },
        "distance": {
            "sprint": norm((aptitudes.get("distance") or {}).get("sprint") or aptitudes.get("Sprint") or aptitudes.get("short")),
            "mile": norm((aptitudes.get("distance") or {}).get("mile") or aptitudes.get("Mile")),
            "medium": norm((aptitudes.get("distance") or {}).get("medium") or aptitudes.get("Medium") or aptitudes.get("middle")),
            "long": norm((aptitudes.get("distance") or {}).get("long") or aptitudes.get("Long")),
        },
        "style": {
            "front": norm((aptitudes.get("style") or {}).get("front") or aptitudes.get("Front") or aptitudes.get("nige")),
            "pace": norm((aptitudes.get("style") or {}).get("pace") or aptitudes.get("Pace") or aptitudes.get("senko")),
            "late": norm((aptitudes.get("style") or {}).get("late") or aptitudes.get("Late") or aptitudes.get("sashi")),
            "end": norm((aptitudes.get("style") or {}).get("end") or aptitudes.get("End") or aptitudes.get("oikomi")),
        },
    }


def _history_factor_ids(chara):
    ids = []
    for value in chara.get("factor_id_array") or []:
        try:
            ids.append(int(value))
        except Exception:
            pass
    for row in chara.get("factor_info_array") or []:
        try:
            fid = int((row or {}).get("factor_id") or (row or {}).get("id") or 0)
            if fid:
                ids.append(fid)
        except Exception:
            pass
    return list(dict.fromkeys(ids))


def _history_group_skills(chara):
    groups = {}
    labels = {
        101: "Unique",
        5: "Unique",
        1: "Early-Race",
        2: "Mid-Race",
        3: "Late-Race",
        4: "Recovery",
        0: "General",
    }
    for row in chara.get("skill_array") or []:
        if isinstance(row, dict):
            sid = _history_safe_int(row.get("skill_id") or row.get("id") or 0)
        else:
            sid = _history_safe_int(row, 0)
        if not sid:
            continue
        info = skill_data.get(str(sid)) or {}
        name = skill_entry_name(info) or f"Skill {sid}"
        category = _history_safe_int(info.get("skill_category"), 0)
        label = labels.get(category, "Skills")
        groups.setdefault(label, []).append({
            "skill_id": sid,
            "name": name,
            "rarity": info.get("rarity", ""),
            "category": category,
        })
    return groups


def _history_major_wins(chara, action_history=None, race_results=None):
    summary = get_win_summary(chara.get("win_saddle_id_array") or [])
    if summary.get("names"):
        return ", ".join(summary["names"][:6])
    if summary.get("g1") or summary.get("g2") or summary.get("g3"):
        parts = []
        for key, label in [("g1", "G1"), ("g2", "G2"), ("g3", "G3")]:
            if summary.get(key):
                parts.append(f"{summary[key]} {label}")
        return ", ".join(parts)

    # Fallback to the runner's explicit race result ledger. This is more reliable
    # than action_history because rank logs live in the lightweight log buffer.
    wins_by_grade = {"G1": 0, "G2": 0, "G3": 0}
    won_names = []
    for row in race_results or []:
        try:
            if int(row.get("rank") or 99) != 1:
                continue
        except Exception:
            continue
        grade = str(row.get("grade") or "").upper()
        if grade in wins_by_grade:
            wins_by_grade[grade] += 1
        name = str(row.get("name") or "").strip()
        if name and len(won_names) < 4:
            won_names.append(name)
    parts = [f"{count} {grade}" for grade, count in wins_by_grade.items() if count]
    if parts:
        return ", ".join(parts)
    if won_names:
        return ", ".join(won_names)

    # Last fallback: derive a rough win count from any injected action rows.
    wins = 0
    for row in action_history or []:
        if str(row.get("action") or "") in {"race_rank", "race_rank_retry"} and "rank 1" in str(row.get("detail") or ""):
            wins += 1
    return f"{wins} wins" if wins else "Unknown"



def _history_career_grade(races, wins, fans):
    """Return the highest official career grade requirement satisfied.

    The label intentionally keeps the master-data grade id instead of inventing
    a localized class name that is not present in the exported table.
    """
    best = None
    for row in career_progression_core or []:
        try:
            if int(races or 0) < int(row.get("run_num") or 0):
                continue
            if int(wins or 0) < int(row.get("win_num") or 0):
                continue
            if int(fans or 0) < int(row.get("need_fan_count") or 0):
                continue
            if best is None or int(row.get("grade_id") or 0) > int(best.get("grade_id") or 0):
                best = row
        except Exception:
            continue
    if not best:
        return {"grade_id": 0, "label": "Unknown", "need_fan_count": 0, "run_num": 0, "win_num": 0}
    grade_id = int(best.get("grade_id") or 0)
    return {
        "grade_id": grade_id,
        "label": f"Career Grade {grade_id}",
        "need_fan_count": int(best.get("need_fan_count") or 0),
        "run_num": int(best.get("run_num") or 0),
        "win_num": int(best.get("win_num") or 0),
    }


def _career_history_summary_from_runner(snap):
    # Freeze the completed run into a private history snapshot.  Career History
    # must never point at the live runner/status objects or a later run can make
    # older entries show the newest run's Major Wins.
    final_chara = deepcopy(snap.get("final_chara") or {})
    final_stats = deepcopy(snap.get("final_stats") or final_chara.get("stats") or {})
    final_aptitudes = deepcopy(snap.get("final_aptitudes") or final_chara.get("aptitudes") or {})
    action_history = deepcopy(list(snap.get("action_history") or []))
    race_results = deepcopy(list(snap.get("race_results") or final_chara.get("race_results") or []))
    card_id = str(final_chara.get("card_id") or snap.get("card_id") or "")
    # Read-only: attach the pre-race win-probability estimate to each race row so
    # Career History can show "predicted P(win) vs actual finish". Never raises.
    _augment_race_results_with_winprob(race_results, card_id)
    trainee_name = chara_map.get(card_id, f"Card {card_id}" if card_id else "Unknown")
    fans_gained = int(snap.get("fans_gained") or 0)
    fans_current = int(final_chara.get("fans") or snap.get("fans_current") or 0)
    fans_start = int(snap.get("fans_start") or max(0, fans_current - fans_gained) or 0)
    if fans_gained <= 0 and fans_current >= fans_start:
        fans_gained = max(0, fans_current - fans_start)

    rating = final_chara.get("rating") or snap.get("final_rating") or ""
    explicit_rank = final_chara.get("rank") or snap.get("final_rank") or ""
    race_count = _history_safe_int(final_chara.get("race_count"), 0)
    if not race_count:
        race_count = len(race_results)
    if not race_count:
        race_count = sum(1 for row in action_history if str(row.get("action") or "") in {"race", "race_entry"})
    wins = _history_safe_int(final_chara.get("win_count"), 0)
    if not wins:
        wins = sum(1 for row in race_results if _history_safe_int(row.get("rank"), 99) == 1)
    if not wins:
        wins = sum(1 for row in action_history if str(row.get("action") or "") in {"race_rank", "race_rank_retry"} and "rank 1" in str(row.get("detail") or ""))

    career_grade = _history_career_grade(race_count, wins, fans_current or fans_gained)

    sparks = get_factors(_history_factor_ids(final_chara), card_id)
    skills_grouped = _history_group_skills(final_chara)
    scenario_id = int(snap.get("scenario_id") or 0)
    scenario = {
        2: "URA Finale",
        4: "Trackblazer: Start of the Climax",
        10: "Unity Cup",
    }.get(scenario_id, "Trackblazer: Start of the Climax" if scenario_id == 4 else f"Scenario {scenario_id}" if scenario_id else "Unknown")

    explicit_major_wins = (
        snap.get("major_wins")
        or final_chara.get("major_wins")
        or final_chara.get("major_win_summary")
    )
    major_wins = str(explicit_major_wins).strip() if explicit_major_wins else _history_major_wins(final_chara, action_history, race_results)

    return {
        "run_id": snap.get("run_id") or f"run-{len(COMPLETED_CAREER_HISTORY) + 1}",
        "index": len(COMPLETED_CAREER_HISTORY) + 1,
        "trainee": trainee_name,
        "title": final_chara.get("title") or snap.get("title") or "",
        "card_id": card_id,
        "portrait_url": f"/api/images/{card_id}.png" if card_id else "",
        "fans_gained": fans_gained,
        "fans_start": fans_start,
        "fans_final": fans_current,
        "stats": {
            "speed": int(final_stats.get("speed") or 0),
            "stamina": int(final_stats.get("stamina") or 0),
            "power": int(final_stats.get("power") or 0),
            "guts": int(final_stats.get("guts") or 0),
            "wit": int(final_stats.get("wit") or final_stats.get("wiz") or 0),
            "skill_point": int(final_stats.get("skill_point") or final_stats.get("skill_points") or 0),
        },
        "rating": rating,
        "career_rank": explicit_rank or _history_rank_from_rating(rating),
        "aptitudes": _history_normalize_aptitudes(final_aptitudes),
        "sparks": sparks,
        "skills_grouped": skills_grouped,
        "races": race_count,
        "wins": wins,
        "career_grade": career_grade.get("label"),
        "career_grade_id": career_grade.get("grade_id"),
        "career_grade_requirements": career_grade,
        "major_wins": major_wins,
        "major_win_summary": major_wins,
        "race_results": deepcopy(race_results),
        "scenario": scenario,
        "turn": int(snap.get("turn") or 0),
        "steps": int(snap.get("steps") or 0),
        "finished_at": time.time(),
    }


def record_completed_career_from_snapshot(snap):
    if not isinstance(snap, dict):
        return None
    if not snap.get("finished") or snap.get("running") or snap.get("last_error"):
        return None
    run_id = str(snap.get("run_id") or "")
    if not run_id:
        return None
    if run_id in COMPLETED_CAREER_RUN_IDS:
        return None
    entry = _career_history_summary_from_runner(snap)
    COMPLETED_CAREER_RUN_IDS.add(run_id)
    COMPLETED_CAREER_HISTORY.append(entry)
    return entry



def _selected_parent_instance_ids():
    ids = set()
    try:
        for parent in (active_selection or {}).get("veterans") or []:
            iid = _coerce_int((parent or {}).get("instance_id"), 0)
            if iid:
                ids.add(iid)
    except Exception:
        pass
    try:
        career = (active_account or {}).get("career") or {}
        for key in ("parent_id_1", "parent_id_2"):
            iid = _coerce_int(career.get(key), 0)
            if iid:
                ids.add(iid)
    except Exception:
        pass
    return ids


def _evict_parents_from_cache(ids):
    global active_dashboard_data, active_selection
    wanted = {int(i) for i in ids or []}
    if not wanted:
        return
    if isinstance(active_dashboard_data, dict):
        parents = active_dashboard_data.get("parents") or []
        active_dashboard_data["parents"] = [p for p in parents if int(p.get("instance_id") or 0) not in wanted]
    if isinstance(active_selection, dict):
        active_selection["veterans"] = [p for p in (active_selection.get("veterans") or []) if int((p or {}).get("instance_id") or 0) not in wanted]


class RemoveParentsRequest(BaseModel):
    trained_chara_ids: list[int] = []


@app.post("/api/parents/remove")
async def remove_parents(req: RemoveParentsRequest):
    """Safely delete selected trained characters from the account."""
    if not active_client:
        return {"success": False, "detail": "Not logged in"}
    ids = [int(i) for i in (req.trained_chara_ids or []) if int(i or 0) > 0]
    if not ids:
        return {"success": False, "detail": "No trained character IDs provided"}
    selected = _selected_parent_instance_ids()
    blocked = [i for i in ids if i in selected]
    if blocked:
        return {"success": False, "detail": f"Refusing to delete currently selected/active parent IDs: {blocked}"}
    try:
        result = active_client.remove_trained_chara(ids)
        _evict_parents_from_cache(ids)
        return {"success": True, "removed": len(ids), "ids": ids, "result": result}
    except Exception as e:
        return {"success": False, "detail": str(e)}


class RemoveRecentParentsRequest(BaseModel):
    max_age_hours: float = 24.0
    dry_run: bool = True


@app.post("/api/parents/remove-recent")
async def remove_recent_parents(req: RemoveRecentParentsRequest):
    """Preview/delete recently-created parent cards using the dashboard cache.

    This ports the useful Senchou-Saru cleanup idea, but keeps it safer: selected
    parents are excluded, and the frontend previews first with dry_run=true.
    """
    if not active_client:
        return {"success": False, "detail": "Not logged in"}
    if not isinstance(active_dashboard_data, dict):
        return {"success": False, "detail": "Dashboard not loaded; click Sync/Refresh first"}
    max_age = max(0.0, float(req.max_age_hours or 0))
    if max_age <= 0:
        return {"success": False, "detail": "Choose an age window first"}
    cutoff = time.time() - max_age * 3600.0
    selected = _selected_parent_instance_ids()
    candidates = []
    for p in active_dashboard_data.get("parents") or []:
        try:
            iid = int(p.get("instance_id") or 0)
            created = float(p.get("create_date") or 0)
        except Exception:
            continue
        if not iid or iid in selected or created <= 0 or created < cutoff:
            continue
        candidates.append({
            "instance_id": iid,
            "card_id": p.get("card_id"),
            "name": p.get("name") or f"Parent {iid}",
            "rank": p.get("rank"),
            "create_date": int(created),
        })
    ids = [int(p["instance_id"]) for p in candidates]
    if req.dry_run:
        return {"success": True, "dry_run": True, "count": len(ids), "ids": ids, "parents": candidates}
    if not ids:
        return {"success": True, "removed": 0, "ids": [], "detail": "No parents matched the age window"}
    try:
        result = active_client.remove_trained_chara(ids)
        _evict_parents_from_cache(ids)
        return {"success": True, "dry_run": False, "removed": len(ids), "ids": ids, "parents": candidates, "result": result}
    except Exception as e:
        return {"success": False, "detail": str(e), "ids": ids}


@app.post("/api/career/rescue")
async def rescue_career():
    """Probe recovery actions for a stuck single-mode state.

    This is intentionally guarded: it only runs while logged in and while the
    background runner is stopped, so the probes cannot fight active automation.
    """
    if not active_client:
        return {"success": False, "detail": "Not logged in"}
    if career_runner.snapshot().get("running"):
        return {"success": False, "detail": "Stop the career runner first"}

    report = []

    def snap():
        res = active_client.load_career()
        d = res.get("data") or {}
        ch = d.get("chara_info") or {}
        return {
            "turn": ch.get("turn"),
            "playing_state": ch.get("playing_state"),
            "vital": ch.get("vital"),
            "race_program_id": ch.get("race_program_id"),
            "has_race_start_info": bool(d.get("race_start_info")),
            "events": len(d.get("unchecked_event_array") or []),
        }

    try:
        st0 = snap()
    except Exception as e:
        return {"success": False, "detail": f"load failed: {e}", "report": report}
    report.append({"step": "initial", "state": st0})

    start_turn = int(st0.get("turn") or 0)
    vital = int(st0.get("vital") or 0)
    if int(st0.get("playing_state") or 1) == 1:
        return {"success": True, "detail": "career is not stuck", "report": report}

    def probe(label, fn):
        row = {"step": label}
        try:
            fn()
            row["call"] = "ok"
        except Exception as e:
            row["call"] = str(e)[:240]
        try:
            row["state"] = snap()
        except Exception as e:
            row["state"] = {"error": str(e)[:160]}
        report.append(row)
        state = row.get("state") or {}
        playing_state = int(state.get("playing_state") or 0)
        turn_now = int(state.get("turn") or 0)
        return playing_state == 1 or turn_now > start_turn

    t = start_turn
    probes = [
        ("race_out turn", lambda: active_client.race_out(current_turn=t)),
        ("race_out turn+1", lambda: active_client.race_out(current_turn=t + 1)),
        ("race_end turn+1", lambda: active_client.race_end(current_turn=t + 1)),
        ("race_end+out turn", lambda: (active_client.race_end(current_turn=t), active_client.race_out(current_turn=t))),
        ("race_start+end+out turn", lambda: (
            active_client.race_start(is_short=1, current_turn=t),
            active_client.race_end(current_turn=t),
            active_client.race_out(current_turn=t),
        )),
        ("race_start+end+out turn+1", lambda: (
            active_client.race_start(is_short=1, current_turn=t + 1),
            active_client.race_end(current_turn=t + 1),
            active_client.race_out(current_turn=t + 1),
        )),
        ("rest turn+1", lambda: active_client.exec_command(command_type=7, command_id=701, current_turn=t + 1, current_vital=vital)),
    ]
    for label, fn in probes:
        if probe(label, fn):
            return {"success": True, "detail": f"unstuck via: {label}", "report": report}
    return {"success": False, "detail": "still stuck after all probes", "report": report}


@app.get("/api/career/live_history")
async def career_live_history():
    """Live/current run history for the monitor drawer.

    /api/career/history remains the completed-career archive.  This endpoint is
    intentionally separate so the monitor can chart the currently running run.
    """
    snap = career_runner.snapshot()
    history = snap.get("action_history") or []
    return {
        "success": True,
        "stats": [
            {"turn": row.get("turn"), "action": row.get("action"), **(row.get("stats") or {})}
            for row in history
            if isinstance(row, dict)
        ],
        "running": snap.get("running"),
        "finished": snap.get("finished"),
    }


@app.get("/api/career/report")
async def career_report():
    """Live run monitor / post-run summary computed from the run's per-turn
    action history: stat progression, action breakdown, races, energy lows, and
    resilience stats. Reflects the current / most-recent run held in memory."""
    snap = career_runner.snapshot()
    history = [r for r in (snap.get("action_history") or []) if isinstance(r, dict)]
    counts = {"train": 0, "race": 0, "rest": 0, "recreation": 0, "medic": 0, "event": 0, "other": 0}
    train_by_facility = {}
    races = []
    low_energy_turns = []
    curve = []
    for row in history:
        action = str(row.get("action") or "").lower()
        stats = row.get("stats") or {}
        turn = row.get("turn")
        if action in counts:
            counts[action] += 1
        elif action:
            counts["other"] += 1
        if action == "train":
            fac = str(row.get("facility") or "").strip() or "?"
            train_by_facility[fac] = train_by_facility.get(fac, 0) + 1
        elif action == "race":
            races.append(str(row.get("facility") or row.get("detail") or "race"))
        try:
            if stats.get("hp") is not None and int(stats.get("hp")) < 30 and turn is not None:
                low_energy_turns.append(turn)
        except (TypeError, ValueError):
            pass
        if stats:
            curve.append({
                "turn": turn,
                "speed": stats.get("speed"), "stamina": stats.get("stamina"),
                "power": stats.get("power"), "guts": stats.get("guts"), "wit": stats.get("wit"),
                "hp": stats.get("hp"), "motivation": stats.get("motivation"),
            })
    started = float(snap.get("started_at") or 0)
    return {
        "success": True,
        "run_id": snap.get("run_id", ""),
        "running": bool(snap.get("running")),
        "finished": bool(snap.get("finished")),
        "turns": snap.get("turn") or (curve[-1]["turn"] if curve else 0),
        "action_counts": counts,
        "training_by_facility": train_by_facility,
        "races": races,
        "race_count": len(races),
        "low_energy_turns": low_energy_turns,
        "final_stats": (curve[-1] if curve else {}),
        "stat_curve": curve,
        "fans_gained": snap.get("fans_gained", 0),
        "fans_per_hour": snap.get("fans_per_hour", 0),
        "recoveries": snap.get("recoveries", 0),
        "runtime_seconds": int(max(0, time.time() - started)) if started else 0,
        "last_error": snap.get("last_error", ""),
    }


@app.get("/api/career/crash_trace")
async def career_crash_trace():
    trace_path = runtime_output_root(base_dir) / "crash_trace.txt"
    if not trace_path.exists():
        return {"success": True, "trace": ""}
    try:
        text = trace_path.read_text(encoding="utf-8", errors="replace")
        return {"success": True, "trace": text[-8000:]}
    except Exception as e:
        return {"success": False, "detail": str(e)}


@app.get("/api/metrics")
async def bot_metrics():
    snap = career_runner.snapshot()
    return {"success": True, "metrics": snap.get("lifetime", {}), "runner": snap}

@app.get("/api/career/runner")
async def career_runner_status():
    snap = career_runner.snapshot()
    # DEV-ONLY: surface the web skill-buy intercept state for the dev dashboard.
    snap["skill_intercept"] = {"enabled": skill_intercept.is_enabled(), "pending": skill_intercept.get_pending(), "available": _SKILL_INTERCEPT_AVAILABLE}
    record_completed_career_from_snapshot(snap)
    extra = {}
    loop_active = bool(backend_loop_thread and backend_loop_thread.is_alive())
    snap["loop_active"] = loop_active
    if snap.get("finished") and not snap.get("running") and not snap.get("last_error") and not loop_active:
        extra = _clear_finished_career_setup_state(clear_selection=True)
    # Include fresh account resources (TP / carats / gold / clocks) from the live
    # client so the dashboard updates every poll (~1.5s), not only on career
    # start/stop. Preserves the career card from the last full account snapshot.
    account = get_account_status({})
    if active_account and active_account.get("career"):
        account["career"] = active_account["career"]
    return {"success": True, "runner": snap, "account": account, **extra}


@app.get("/api/career/history")
async def career_history():
    """Current-process completed career history.

    This is deliberately not persisted. Restarting python main.py clears it.
    """
    return {
        "success": True,
        "count": len(COMPLETED_CAREER_HISTORY),
        "careers": list(COMPLETED_CAREER_HISTORY),
        "session_only": True,
    }


@app.post("/api/career/runner/stop")
async def stop_career_runner():
    global backend_loop_stop
    backend_loop_stop = True
    skill_intercept.cancel()  # DEV-ONLY: release a waiting skill-buy intercept so stop never hangs
    career_runner.stop()
    snap = career_runner.snapshot()
    extra = {}
    if snap.get("finished") and not snap.get("running"):
        extra = _clear_finished_career_setup_state(clear_selection=True)
    return {"success": True, "runner": snap, **extra}


@app.post("/api/career/runner/pause")
async def pause_career_runner():
    career_runner.pause()
    snap = career_runner.snapshot()
    snap["loop_active"] = bool(backend_loop_thread and backend_loop_thread.is_alive())
    return {"success": True, "runner": snap}


@app.post("/api/career/runner/resume")
async def resume_career_runner():
    career_runner.resume()
    snap = career_runner.snapshot()
    snap["loop_active"] = bool(backend_loop_thread and backend_loop_thread.is_alive())
    return {"success": True, "runner": snap}


class BurnClocksRequest(BaseModel):
    burn_clocks: bool


@app.post("/api/career/runner/burn_clocks")
async def set_burn_clocks(req: BurnClocksRequest):
    career_runner.set_burn_clocks(req.burn_clocks)
    return {"success": True, "runner": career_runner.snapshot()}


# --- DEV-ONLY web skill-buy intercept (private; not for the beta/public build) ---
class SkillInterceptToggle(BaseModel):
    enabled: bool


@app.post("/api/career/runner/skill_intercept")
async def set_skill_intercept(req: SkillInterceptToggle):
    skill_intercept.set_enabled(req.enabled)
    return {"success": True, "enabled": skill_intercept.is_enabled()}


class SkillDecision(BaseModel):
    action: str = "confirm"   # confirm | skip | proceed
    ids: list = []


@app.post("/api/career/runner/skill_decision")
async def submit_skill_decision(req: SkillDecision):
    skill_intercept.submit_decision(req.action, req.ids)
    return {"success": True}


@app.post("/api/career/friends")
async def get_friend_list(req: FriendListRequest):
    global active_client, active_dashboard_data
    if not active_client:
        return {"success": False, "detail": "Not logged in"}

    if (
        not req.exclude_viewer_ids
        and active_dashboard_data is not None
        and "friends" in active_dashboard_data
    ):
        return {
            "success": True,
            "friends": active_dashboard_data["friends"],
            "exclude_viewer_ids": active_dashboard_data.get("friendExcludeIds", []),
            "source": "cache",
            "debug": {
                "cache_hit": True,
                "force_refresh": bool(req.force_refresh),
                "guest_count": len(active_dashboard_data.get("guestParents", [])),
            },
        }

    try:
        result = active_client.pre_single_mode(req.exclude_viewer_ids)
        data = result.get("data", {})
        update_start_state(data)
        friends, exclude_viewer_ids, source = normalize_friend_cards(data)

        if active_dashboard_data is not None:
            active_dashboard_data["friends"] = friends
            active_dashboard_data["friendExcludeIds"] = exclude_viewer_ids
            active_dashboard_data["friendsLoaded"] = True

        return {
            "success": True,
            "friends": friends,
            "exclude_viewer_ids": exclude_viewer_ids,
            "source": source,
        }
    except Exception as e:
        return {"success": False, "detail": str(e)}



@app.get("/api/career/guest_parents/raw")
async def guest_parents_raw_dump():
    """Deep diagnostic for an empty GUEST PARENTS section.

    Calls pre_single_mode and reports EVERY array found at any nesting level of
    the response: its path, length, and the keys of its first element (no values,
    to avoid leaking account data). Also reports what the normalizer extracted and
    writes the full report to data/guest_parents_raw_dump.json for easy sharing.

    Interpreting the result:
      * arrays whose path contains follow/guest/rental/succession/parent are the
        candidates the normalizer targets;
      * if NONE exist, the game simply is not returning borrowable parents for
        this account/state (expected if no followed trainers have trained
        characters available, or while a career is active);
      * if one exists but guest_count is 0, send me its `sample_keys` and I will
        extend the normalizer to that shape.
    """
    global active_client
    if not active_client:
        return {"success": False, "detail": "Not logged in"}
    try:
        result = active_client.pre_single_mode([])
        data = result.get("data", {}) or {}

        arrays = []
        for path, arr in _iter_nested_arrays(data):
            # Only report arrays of objects (skip arrays of scalars / ids).
            first = arr[0] if arr else None
            if isinstance(first, dict):
                arrays.append({
                    "path": path,
                    "len": len(arr),
                    "sample_keys": sorted(first.keys())[:30],
                    "looks_guest_like": _guest_parent_like(first, path),
                })
        # Sort the most promising candidates first.
        arrays.sort(key=lambda a: (a["looks_guest_like"], a["len"]), reverse=True)

        guest_parents = normalize_guest_parents(data)
        guest_sources = discover_guest_parent_sources(data)
        report = {
            "success": True,
            "top_level_keys": sorted(data.keys()),
            "object_array_count": len(arrays),
            "object_arrays": arrays[:80],
            "guest_like_paths": [a["path"] for a in arrays if a["looks_guest_like"]],
            "normalizer_extracted": len(guest_parents),
            "discovered_sources": [
                {"path": s.get("path"), "score": s.get("score"), "count": s.get("count")}
                for s in (guest_sources or [])[:20]
            ],
        }
        try:
            out = Path(DIR) / "data" / "guest_parents_raw_dump.json"
            out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            report["saved_to"] = str(out)
        except Exception:
            pass
        return report
    except Exception as e:
        return {"success": False, "detail": str(e)}


@app.post("/api/career/guest_parents")
async def get_guest_parent_list(req: FriendListRequest):
    global active_client, active_dashboard_data
    if not active_client:
        return {"success": False, "detail": "Not logged in"}

    if (
        not req.force_refresh
        and not req.exclude_viewer_ids
        and active_dashboard_data is not None
        and active_dashboard_data.get("guestParentsLoaded")
    ):
        return {
            "success": True,
            "guestParents": active_dashboard_data.get("guestParents", []),
            "exclude_viewer_ids": active_dashboard_data.get("guestParentExcludeIds", []),
            "source": "cache",
        }

    try:
        # For manual Refresh, send the current exclude list only if available. Passing
        # stale/empty values previously made the UI look like the button did nothing.
        result = active_client.pre_single_mode(req.exclude_viewer_ids or [])
        data = result.get("data", {})
        update_start_state(data)
        guest_parents = normalize_guest_parents(data)
        guest_sources = discover_guest_parent_sources(data)
        friends, exclude_viewer_ids, source = normalize_friend_cards(data)

        # Fallback: some builds nest rental parents under friend/support payloads
        # loaded during login. Try the dashboard cache if the fresh payload had none.
        if not guest_parents and active_dashboard_data:
            # STRICT: only resurface genuine nested guest arrays from the cache,
            # never the broad heuristic (which would re-classify the cached login
            # home payload's random umas / the player's own parents as guests).
            guest_parents = normalize_guest_parents(active_dashboard_data, strict=True)
            guest_sources = discover_guest_parent_sources(active_dashboard_data)

        # Do not fall back to friend support cards. Guest Parents must be real
        # rental/succession trained characters, not support-card summaries.
        if not guest_parents:
            guest_parents = []

        if active_dashboard_data is not None:
            active_dashboard_data["guestParents"] = guest_parents
            active_dashboard_data["guestParentExcludeIds"] = exclude_viewer_ids
            active_dashboard_data["guestParentsLoaded"] = True
            # Keep friend cache in sync if the same call refreshed it.
            active_dashboard_data["friends"] = friends
            active_dashboard_data["friendExcludeIds"] = exclude_viewer_ids
            active_dashboard_data["friendsLoaded"] = True

        return {
            "success": True,
            "guestParents": guest_parents,
            "exclude_viewer_ids": exclude_viewer_ids,
            "source": source,
            "debug": {
                "top_level_keys": sorted(list(data.keys()))[:80],
                "guest_count": len(guest_parents),
                "friend_count": len(friends),
                "guest_sources": [{"path": s.get("path"), "score": s.get("score"), "count": s.get("count")} for s in (guest_sources or [])[:20]],
                "guest_paths_used": sorted(list({g.get("path") or g.get("source") for g in guest_parents if g.get("path") or g.get("source")}))[:20],
                "cache_hit": False,
                "force_refresh": bool(req.force_refresh),
            },
        }
    except Exception as e:
        return {"success": False, "detail": str(e)}


@app.post("/api/career/action")
async def career_action(req: CareerActionRequest):
    global active_client, active_account
    if not active_client:
        return {"success": False, "detail": "Not logged in"}

    try:
        result = active_client.exec_command(
            command_type=req.command_type,
            command_id=req.command_id,
            current_turn=req.current_turn,
            current_vital=req.current_vital,
            command_group_id=req.command_group_id,
            select_id=req.select_id,
        )

        data = result.get("data", {})
        return {
            "success": True,
            "chara_info": data.get("chara_info", {}),
            "command_result": data.get("command_result", {}),
        }
    except Exception as e:
        return {"success": False, "detail": str(e)}


@app.post("/api/career/delete")
async def delete_career(req: DeleteCareerRequest):
    global active_client, active_account, active_dashboard_data, backend_loop_thread
    if not active_client:
        return {"success": False, "detail": "Not logged in"}
    if career_runner.snapshot().get("running") or (
        backend_loop_thread and backend_loop_thread.is_alive()
    ):
        return {
            "success": False,
            "detail": "Cannot delete career while runner is active",
        }

    try:
        account = active_account or {}
        career = account.get("career") or {}
        if not career.get("active"):
            load_result = active_client.call("load/index")
            load_data = load_result.get("data", {})
            update_start_state(load_data)
            account = get_account_status(load_data)
            active_account = account
            career = account.get("career") or {}
        current_turn = req.current_turn or career.get("turn", 0) or 1
        if not career.get("active") and not req.current_turn:
            return {"success": False, "detail": "No active career"}
        active_client.finish_career(current_turn=current_turn, is_force_delete=True)
        account["career"] = None
        active_account = account
        if active_dashboard_data:
            active_dashboard_data["account"] = account
        return {"success": True, "account": account}
    except Exception as e:
        return {"success": False, "detail": str(e)}


@app.get("/api/debug/start_state")
async def get_start_state():
    return active_start_state


@app.get("/api/debug/raw_load")
async def get_raw_load():
    return {"error": "raw load/index response storage disabled"}


def safe_public_path(subdir: str, file_name: str):
    """Resolve a file inside public/<subdir>, refusing path traversal."""
    base = (base_dir / "public" / subdir).resolve()
    try:
        path = (base / file_name).resolve()
    except (OSError, ValueError):
        return None
    if base != path and base not in path.parents:
        return None
    return path if path.is_file() else None


@app.get("/api/images/{image_name}")
async def get_image(image_name: str):
    name_no_ext = image_name.split("?")[0].replace(".png", "")

    # Portraits are content-addressed by id and never change for a given id, so
    # cache them long to avoid re-fetching the whole grid fan-out every load.
    _img_cache = {"Cache-Control": "public, max-age=604800"}
    exact_path = images_dir / f"{name_no_ext}.png"
    if exact_path.exists():
        return FileResponse(exact_path, media_type="image/png", headers=_img_cache)

    for fallback_id in ["100101", "10010", "10000", "10001"]:
        fb_path = images_dir / f"{fallback_id}.png"
        if fb_path.exists():
            return FileResponse(fb_path, media_type="image/png", headers=_img_cache)

    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/api/card-art/{image_name}")
async def get_card_art(image_name: str):
    """Per-trainee 512x512 standing illustration (extracted via
    tools/extract_card_art.py into data/card_art/<chara_id>.png). Keyed by
    card_id in the URL; mapped to chara_id = card_id // 100. Falls back to the
    small portrait icon (/api/images) so callers always get an image."""
    _img_cache = {"Cache-Control": "public, max-age=604800"}
    raw = image_name.split("?")[0].replace(".png", "")
    card_art_dir = base_dir / "data" / "card_art"
    try:
        card_id = int(raw)
        # 1) this card's own outfit (the signature race outfit for base cards,
        #    the alt outfit for alt cards), keyed by card_id.
        own = card_art_dir / f"{card_id}.png"
        if own.exists():
            return FileResponse(own, media_type="image/png", headers=_img_cache)
        # 2) the chara's base/signature card (xxxx01) — same trainee, signature look.
        base_card = card_art_dir / f"{(card_id // 100) * 100 + 1}.png"
        if base_card.exists():
            return FileResponse(base_card, media_type="image/png", headers=_img_cache)
    except (TypeError, ValueError):
        pass
    # 3) fallback: the small portrait icon for this card id
    icon = images_dir / f"{raw}.png"
    if icon.exists():
        return FileResponse(icon, media_type="image/png", headers=_img_cache)
    raise HTTPException(status_code=404, detail="Card art not found")


@app.get("/api/skill-icons/{image_name}")
async def get_skill_icon(image_name: str):
    # Skill icons live in their own namespace because skill icon_ids collide
    # with support-card portrait ids under /api/images (e.g. 20013 is both a
    # card portrait and a skill icon). Serve the real skill icon here; the
    # client falls back to /sweep.png via onerror when one is missing.
    name_no_ext = image_name.split("?")[0].replace(".png", "")
    icon_path = skill_icons_dir / f"{name_no_ext}.png"
    if icon_path.exists():
        # Skill icons are immutable per id — cache long like portraits.
        return FileResponse(
            icon_path, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"}
        )
    raise HTTPException(status_code=404, detail="Skill icon not found")


@app.get("/api/item-icons/{image_name}")
async def get_item_icon(image_name: str):
    # MANT/Trackblazer shop-item icons (game8 source), named by item_id.
    # Served from public/item_icons/. Files may be .png or .jpg; pick the
    # media type by extension. Immutable per id, so cache long.
    path = safe_public_path("item_icons", image_name.split("?")[0])
    if path:
        media = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        return FileResponse(
            path, media_type=media, headers={"Cache-Control": "public, max-age=604800"}
        )
    raise HTTPException(status_code=404, detail="Item icon not found")


@app.get("/api/logs/export")
async def export_logs():
    """Zip all career logs for sharing/feedback. Each log is re-redacted on
    export, so even logs written before redaction shipped are safe to share."""
    import tempfile
    import zipfile
    from datetime import datetime as _dt
    from career_bot import report as _report
    logs_dir = Path(RUNTIME_DIR) / "bot_logs"
    files = sorted(logs_dir.glob("career_log_*.json")) if logs_dir.exists() else []
    stamp = _dt.now().strftime("%Y%m%d_%H%M%S")
    fd, tmp = tempfile.mkstemp(prefix="icarus_logs_", suffix=".zip")
    os.close(fd)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                _report._redact_sensitive(data)
                zf.writestr(f.name, json.dumps(data, ensure_ascii=False, indent=2))
            except Exception:
                continue
    return FileResponse(tmp, filename=f"icarus_career_logs_{stamp}.zip", media_type="application/zip")


@app.get("/api/changelog")
async def get_changelog():
    """Return the latest CHANGELOG.md entry + its version for the what's-new popup."""
    path = base_dir / "CHANGELOG.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="CHANGELOG.md not found")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    version = ""
    title = ""
    body_lines = []
    capturing = False
    for line in lines:
        if line.startswith("## "):
            if capturing:
                break  # reached the next entry; stop
            title = line[3:].strip()
            version = title
            capturing = True
            continue
        if capturing:
            body_lines.append(line)
    latest = "\n".join(body_lines).strip()
    return {
        "success": True,
        "version": version,
        "title": title,
        "markdown": latest,
        "full_markdown": text,
    }


@app.get("/styles.css")
async def styles_css():
    # v3 is the default UI at "/", so root /styles.css serves the v3 stylesheet.
    # The legacy UI lives at /legacy/ and gets its own styles.css from that mount.
    path = base_dir / "public-v3" / "styles.css"
    if path.exists():
        # no-cache (not no-store): the browser caches the file but revalidates
        # via ETag each load, so an unchanged file returns a tiny 304 instead of
        # a full re-download. Editing the file changes its ETag, so never stale.
        return FileResponse(
            path, media_type="text/css", headers={"Cache-Control": "no-cache"}
        )
    raise HTTPException(status_code=404, detail="styles.css not found")


@app.get("/app.js")
async def app_js():
    # v3 default at "/": root /app.js serves the v3 dashboard script (legacy UI's
    # app.js is served from the /legacy/ mount).
    path = base_dir / "public-v3" / "app.js"
    if path.exists():
        return FileResponse(
            path,
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )
    raise HTTPException(status_code=404, detail="app.js not found")


@app.get("/skill_intercept_ui.js")
async def skill_intercept_ui_js():
    # DEV/PRIVATE-only: the old-UI skill-buy intercept toggle script. The old UI
    # serves each public/ file via an explicit route (there is no catch-all), so
    # this file 404'd without one and the toggle never rendered. Served from
    # public/ root like /app.js. Absent from public builds (the file is excluded
    # and its <script> tag stripped by the build), so this 404s harmlessly there.
    path = base_dir / "public" / "skill_intercept_ui.js"
    if path.exists():
        return FileResponse(
            path,
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )
    raise HTTPException(status_code=404, detail="skill_intercept_ui.js not found")


@app.get("/sweep.png")
async def sweep_png():
    path = base_dir / "public" / "sweep.png"
    if path.exists():
        return FileResponse(
            path, media_type="image/png", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    raise HTTPException(status_code=404, detail="sweep.png not found")


@app.get("/broom.png")
async def broom_png():
    path = base_dir / "public" / "broom.png"
    if path.exists():
        return FileResponse(
            path, media_type="image/png", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    raise HTTPException(status_code=404, detail="broom.png not found")


@app.get("/icarus-logo.png")
async def icarus_logo_png():
    path = base_dir / "public" / "icarus-logo.png"
    if path.exists():
        return FileResponse(
            path, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"}
        )
    raise HTTPException(status_code=404, detail="icarus-logo.png not found")


@app.get("/icarus-space-bg.png")
async def icarus_space_bg_png():
    path = base_dir / "public" / "icarus-space-bg.png"
    if path.exists():
        return FileResponse(
            path, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"}
        )
    raise HTTPException(status_code=404, detail="icarus-space-bg.png not found")


@app.get("/icarus-backdrop.jpg")
async def icarus_backdrop_jpg():
    # The Icarus theme backdrop, extracted from styles.css (was a 182KB base64
    # data-URI that bloated the render-blocking stylesheet).  Served as a real,
    # CACHEABLE file so it loads in parallel and isn't re-parsed every load.
    # Bust the cache by bumping the ?v= query in styles.css when the image changes.
    path = base_dir / "public" / "icarus-backdrop.jpg"
    if path.exists():
        return FileResponse(
            path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800"}
        )
    raise HTTPException(status_code=404, detail="icarus-backdrop.jpg not found")


@app.get("/uma-loading.gif")
async def uma_loading_gif():
    path = base_dir / "public" / "uma-loading.gif"
    if path.exists():
        return FileResponse(
            path, media_type="image/gif", headers={"Cache-Control": "public, max-age=604800"}
        )
    raise HTTPException(status_code=404, detail="uma-loading.gif not found")


@app.get("/sweepycl-logo.png")
async def sweepycl_logo_png():
    # Legacy route — serves the Icarus logo so cached references still resolve.
    path = base_dir / "public" / "icarus-logo.png"
    if path.exists():
        return FileResponse(
            path, media_type="image/png", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    raise HTTPException(status_code=404, detail="logo not found")


@app.get("/assets/data/{file_name}")
async def get_asset_data(file_name: str):
    path = safe_public_path("assets/data", file_name)
    if path:
        return FileResponse(path, headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/races/{file_name}")
async def get_race_image(file_name: str):
    path = safe_public_path("races", file_name)
    if path:
        return FileResponse(path, headers={"Cache-Control": "max-age=31536000"})
    raise HTTPException(status_code=404, detail="Race image not found")


@app.get("/css/{file_name}")
async def get_css_file(file_name: str):
    path = safe_public_path("css", file_name)
    if path:
        return FileResponse(path, media_type="text/css", headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=404, detail="CSS file not found")


@app.get("/js/{file_name}")
async def get_js_file(file_name: str):
    path = safe_public_path("js", file_name)
    if path:
        return FileResponse(path, media_type="application/javascript", headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=404, detail="JavaScript file not found")


@app.get("/", response_class=HTMLResponse)
async def root():
    # v3 (public-v3) is now the DEFAULT UI at "/". The legacy UI is at /legacy/.
    index_path = base_dir / "public-v3" / "index.html"
    if not index_path.exists():
        index_path = base_dir / "public" / "index.html"   # fallback to legacy
    if index_path.exists():
        return FileResponse(
            index_path, media_type="text/html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    return "index.html not found"


@app.get("/legacy")
async def legacy_redirect():
    # /legacy -> /legacy/ so the StaticFiles mount resolves relative assets.
    return RedirectResponse(url="/legacy/")


@app.get("/v3")
async def v3_redirect_root():
    # Back-compat: the v3 UI used to live at /v3/. It's now the root, so send
    # any old /v3 bookmark to "/".
    return RedirectResponse(url="/")


@app.get("/v3/{rest:path}")
async def v3_redirect(rest: str):
    return RedirectResponse(url="/" + rest)


# --- Static mounts (registered AFTER every @app route so explicit routes —
# "/", "/api/*", "/app.js", "/styles.css", images, /races, /js, /css, ... —
# always take precedence). ---
#   * Legacy UI preserved at /legacy/ (its assets are relative, so they resolve
#     under the mount automatically).
#   * v3 mounted at "/" as the catch-all so its remaining assets (core.js,
#     setup.html, model-test/, setup.js, ...) are served at the clean root URL.
if (base_dir / "public").exists():
    app.mount(
        "/legacy",
        StaticFiles(directory=base_dir / "public", html=True),
        name="legacy",
    )
# Race banner images (public/races/<name>.png) — used by the v3 race schedule.
# Mounted at /races (before the "/" catch-all) so both UIs resolve them.
if (base_dir / "public" / "races").exists():
    app.mount(
        "/races",
        StaticFiles(directory=base_dir / "public" / "races"),
        name="races",
    )
if (base_dir / "public-v3").exists():
    app.mount(
        "/",
        StaticFiles(directory=base_dir / "public-v3", html=True),
        name="root",
    )


def set_console_topmost():
    if os.name != "nt":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
    except Exception:
        pass


def kill_process_by_name(name):
    if os.name != "nt":
        return
    try:
        subprocess.run(
            ["taskkill", "/IM", name, "/F"], capture_output=True, text=True, timeout=10
        )
    except Exception:
        pass



def _truthy_env(name):
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "y", "on"}


def _port_listener_rows(port):
    """Return netstat rows for LISTENING sockets on the requested local port."""
    rows = []
    try:
        output = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    except Exception:
        return rows

    target_suffix = f":{int(port)}"
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        proto, local_addr, foreign_addr, state, pid = parts[:5]
        if state.upper() != "LISTENING":
            continue
        if not local_addr.endswith(target_suffix):
            continue
        if not pid.isdigit():
            continue
        rows.append({"pid": int(pid), "proto": proto, "local_addr": local_addr})
    return rows


def _process_command(pid):
    try:
        output = subprocess.check_output(
            ["wmic", "process", "where", f"ProcessId={int(pid)}", "get", "CommandLine,Name", "/format:list"],
            text=True,
            errors="ignore",
        )
        result = {}
        for line in output.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip()
        return result
    except Exception:
        return {}


def kill_listeners_on_port(port):
    """Compatibility wrapper.

    Historically this function force-killed anything listening on the dashboard port.
    That is dangerous for multi-account setups, so it now only kills when explicitly
    enabled with UMA_KILL_PORT_LISTENER=1.
    """
    return ensure_port_available(port)


def ensure_port_available(port):
    listeners = _port_listener_rows(port)
    if not listeners:
        return {"success": True, "port": int(port), "listeners": []}

    allow_kill = _truthy_env("UMA_KILL_PORT_LISTENER")
    listener_summaries = []
    for listener in listeners:
        info = _process_command(listener["pid"])
        listener_summaries.append({
            "pid": listener["pid"],
            "local_addr": listener["local_addr"],
            "name": info.get("Name", ""),
            "command": info.get("CommandLine", ""),
        })

    if allow_kill:
        killed = []
        failed = []
        for item in listener_summaries:
            try:
                subprocess.run(["taskkill", "/PID", str(item["pid"]), "/F"], check=True, capture_output=True, text=True)
                killed.append(item)
            except Exception as exc:
                failed.append({"listener": item, "error": str(exc)})
        if failed:
            raise RuntimeError(f"Port {port} is in use and cleanup failed: {failed}")
        print(f"[startup] Cleared {len(killed)} listener(s) from port {port} because UMA_KILL_PORT_LISTENER=1", flush=True)
        return {"success": True, "port": int(port), "listeners": listener_summaries, "killed": killed}

    detail_lines = [
        f"Port {port} is already in use.",
        "Automatic process killing is disabled for safety.",
        "Close the process, choose another account port, or run with UMA_KILL_PORT_LISTENER=1 to force cleanup.",
        "Listeners:",
    ]
    for item in listener_summaries:
        label = item.get("name") or "unknown process"
        command = item.get("command") or ""
        detail_lines.append(f"  PID {item['pid']} | {label} | {item['local_addr']} | {command}")

    raise RuntimeError("\n".join(detail_lines))


def has_fresh_auth_config(cfg):
    app_ver = str(cfg.get("app_ver") or "").strip()
    res_ver = str(cfg.get("res_ver") or "").strip()
    if not app_ver or not res_ver:
        return False
    if int(cfg.get("auth_key_len") or 0) != 48:
        return False
    viewer_id = cfg.get("viewer_id")
    udid = str(cfg.get("udid") or "").strip()
    auth_key = str(cfg.get("auth_key") or "").strip().lower()
    if not viewer_id or not udid or not auth_key:
        return False
    if not re.fullmatch(r"[0-9a-f]+", auth_key):
        return False
    if len(auth_key) < 32 or len(auth_key) % 2:
        return False
    if len(udid) != 36 or udid.count("-") != 4:
        return False
    return True


def check_saved_auth():
    # v6.7.18: prefer the userdata copy of auth_config.json so the
    # headless bypass survives version upgrades.  RUNTIME_DIR lives
    # inside the build folder and is wiped on upgrade; the userdata copy
    # is authoritative.  Fall back to RUNTIME_DIR when userdata has none
    # yet, and migrate it into userdata so the NEXT upgrade is covered.
    runtime_auth_path = os.path.join(RUNTIME_DIR, "auth_config.json")
    try:
        user_auth_path = _user_auth_config_path(PROFILE_NAME)
    except Exception:
        user_auth_path = None

    auth_config_path = None
    if user_auth_path is not None and user_auth_path.exists():
        auth_config_path = str(user_auth_path)
        print(f"[+] Using saved auth from userdata for {PROFILE_NAME}.", flush=True)
    elif os.path.exists(runtime_auth_path):
        auth_config_path = runtime_auth_path
        # Migrate the runtime copy into userdata for future upgrades.
        if user_auth_path is not None:
            try:
                user_auth_path.write_text(
                    Path(runtime_auth_path).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                print(
                    f"[+] Migrated auth_config.json into userdata for {PROFILE_NAME}.",
                    flush=True,
                )
            except Exception as exc:
                print(f"[-] auth_config userdata migration failed: {exc}", flush=True)

    if auth_config_path and os.path.exists(auth_config_path):
        try:
            with open(auth_config_path, "r") as f:
                saved_cfg = json.load(f)

            if "steam_username" in saved_cfg:
                saved_cfg["steam_username"] = _deobfuscate_creds(
                    saved_cfg["steam_username"]
                )
            if "steam_password_seed" in saved_cfg:
                saved_cfg["steam_password_seed"] = _deobfuscate_creds(
                    saved_cfg["steam_password_seed"]
                )

            # First, try with the saved ticket
            if (
                has_fresh_auth_config(saved_cfg)
                and "steam_id" in saved_cfg
                and "steam_session_ticket" in saved_cfg
            ):
                # Apply spoofed hardware info if present (DO NOT override 'udid' or 'device_id' as it breaks auth crypto/binding)
                for key in [
                    "device_name",
                    "graphics_device_name",
                    "platform_os_version",
                    "ip_address",
                ]:
                    if key in INSTANCE_CONFIG:
                        saved_cfg[key] = INSTANCE_CONFIG[key]

                print(
                    f"[+] Found saved auth config for {PROFILE_NAME}. Testing headless bypass...",
                    flush=True,
                )
                c = UmaClient(saved_cfg, trace_enabled=False)
                res = c.login()
                if res and res.get("data"):
                    print("[+] Headless bypass successful!", flush=True)
                    return saved_cfg
                else:
                    print("[-] Headless bypass failed (Invalid session).", flush=True)

            # If that failed, try to get a new ticket if we have credentials
            if saved_cfg.get("steam_username") and saved_cfg.get("steam_password_seed"):
                print("[+] Attempting to refresh Steam session ticket...", flush=True)
                try:
                    sid, tkt = get_ticket(
                        saved_cfg["steam_username"],
                        saved_cfg["steam_password_seed"],
                        "",
                    )
                    saved_cfg["steam_id"] = sid
                    saved_cfg["steam_session_ticket"] = tkt

                    print("[+] Testing with new Steam ticket...", flush=True)
                    c = UmaClient(saved_cfg, trace_enabled=False)
                    res = c.login()
                    if res and res.get("data"):
                        print(
                            "[+] Headless bypass with new ticket successful!",
                            flush=True,
                        )
                        save_cfg = dict(saved_cfg)
                        if "steam_username" in save_cfg:
                            save_cfg["steam_username"] = _obfuscate_creds(
                                save_cfg["steam_username"]
                            )
                        if "steam_password_seed" in save_cfg:
                            save_cfg["steam_password_seed"] = _obfuscate_creds(
                                save_cfg["steam_password_seed"]
                            )

                        _save_auth_config_both(save_cfg, PROFILE_NAME)
                        return saved_cfg
                    else:
                        print("[-] Headless bypass with new ticket failed.", flush=True)
                except Exception as e:
                    if "STEAM_GUARD_REQUIRED" in str(e):
                        print(
                            "[-] Steam ticket refresh failed: Steam Guard code required. Falling back to manual launch.",
                            flush=True,
                        )
                    else:
                        print(f"[-] Steam ticket refresh failed: {e}", flush=True)
        except Exception as e:
            print(f"[-] Headless bypass failed: {e}", flush=True)
    return None


def launch_game():
    if os.name != "nt":
        print("Auth refresh needs Windows Steam launch.")
        return False
    try:
        os.startfile(f"steam://rungameid/{APP_ID}")
        return True
    except Exception as e:
        print(f"Failed to launch Umamusume through Steam: {e}")
        return False


def refresh_auth_before_serving(timeout_sec=None):
    global pending_game_auth_config

    saved_cfg = check_saved_auth()
    if saved_cfg:
        pending_game_auth_config = saved_cfg
        return True

    timeout_sec = timeout_sec or int(
        os.environ.get("SWEEPY_AUTH_CAPTURE_TIMEOUT_SEC", "180")
    )
    started_at = time.time()
    deadline = started_at + timeout_sec

    print("[NEED TO CAPTURE AUTH]", flush=True)
    if not launch_game():
        return False

    print(f"Waiting up to {timeout_sec}s for user to enter game menu", flush=True)

    session = None
    captured_data = {}
    done = {"ok": False}

    def on_message(message, data):
        if message.get("type") == "error":
            print(f"Frida Error: {message.get('description')}", flush=True)
            return
        payload = message.get("payload") or {}
        if payload.get("type") == "creds":
            if payload.get("app_ver") and payload.get("res_ver"):
                captured_data.update(payload)
                done["ok"] = True

    while time.time() < deadline:
        try:
            session = frida.attach(PROCESS_NAME)
            break
        except Exception:
            time.sleep(1)

    if not session:
        print(f"Error: {PROCESS_NAME} not found within timeout.", flush=True)
        return False

    try:
        script = session.create_script(JS_CODE)
        script.on("message", on_message)
        script.load()

        while time.time() < deadline:
            if done["ok"]:
                if has_fresh_auth_config(captured_data):
                    pending_game_auth_config = dict(captured_data)
                    time.sleep(random.uniform(2, 4))
                    kill_process_by_name(PROCESS_NAME)
                    return True
            time.sleep(0.5)
    except Exception as e:
        print(f"Frida injection failed: {e}", flush=True)
    finally:
        if session:
            try:
                session.detach()
            except Exception:
                pass

    print(
        "Auth refresh failed: no fresh credentials captured before timeout.", flush=True
    )
    return False


if __name__ == "__main__":
    import uvicorn

    set_console_topmost()
    ensure_port_available(PORT)
    refresh_status = maybe_start_profile_refresh(DIR, force=False)
    if refresh_status.get("started"):
        print(f"[profile-refresh] background refresh started: {refresh_status.get('reason')}", flush=True)
    else:
        print(f"[profile-refresh] skipped: {refresh_status.get('reason')}", flush=True)
    if not refresh_auth_before_serving():
        raise SystemExit(1)

    # AUTO LOGIN IF WE HAVE SAVED CREDS AND BYPASSED
    if pending_game_auth_config.get("steam_id") and pending_game_auth_config.get(
        "steam_session_ticket"
    ):
        print("[*] Pre-loading backend session to bypass Web UI login...", flush=True)
        backup_cfg = dict(pending_game_auth_config)
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(login(LoginRequest()))
            if res and res.get("success"):
                print(
                    "[+] Backend pre-load successful. You will bypass the Web UI login!",
                    flush=True,
                )
            else:
                print(
                    "[-] Backend pre-load failed. You will need to login on the Web UI.",
                    flush=True,
                )
                pending_game_auth_config = backup_cfg
        except Exception as e:
            print(f"[-] Backend pre-load error: {e}", flush=True)
            pending_game_auth_config = backup_cfg

    print(f"Access the Web UI at: http://127.0.0.1:{PORT}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="error")
