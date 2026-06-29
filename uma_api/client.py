import base64
import json
import os
import time
import uuid
from curl_cffi import requests
import hashlib
import random
import struct
import msgpack
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import subprocess
import platform
import socket
import shutil
from datetime import datetime
from pathlib import Path
from career_bot.delay import dna_sleep, dna_uniform, dna_gauss
from career_bot import event_bus

class StateRecoveryError(Exception):
    pass

BASE_URL = 'https://api.games.umamusume.com/umamusume/'
DIR = str(Path(__file__).resolve().parent.parent)
LAST_TICKET_GEN_RESULT = None
# Minimum spacing (seconds) between consecutive raw HTTP calls. Doubles as light
# anti-detection pacing. Set by the dashboard Speed dropdown (main.set_speed_level):
# Safe/Fast=0.14, Faster=0.05, Ludicrous=0.0 (no floor).
MIN_CALL_SPACING = 0.14
LAST_SAVED_CONFIG = None


def runtime_output_root():
    override = os.environ.get("UMA_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve()

    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists():
            return candidate / "uma_runtime"
    return here.parent.parent.parent / "uma_runtime"


TRACE_DIR = runtime_output_root() / "trace_logs"

TICKET_GEN_JS = """const SteamUser = require("steam-user");

const args = process.argv.slice(2);
let username = "";
let password = "";
let appid = 3224770;
let code = "";

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--username") username = args[++i];
  else if (args[i] === "--password") password = args[++i];
  else if (args[i] === "--appid") appid = parseInt(args[++i]);
  else if (args[i] === "--code") code = args[++i];
}

if (!username || !password) {
  process.stderr.write(
    "Usage: node ticket_gen.js --username X --password Y [--code Z]\\n"
  );
  process.exit(1);
}

const client = new SteamUser();

const loginOpts = {
  accountName: username,
  password: password,
};

if (code) {
  loginOpts.twoFactorCode = code;
}

client.logOn(loginOpts);

client.on("steamGuard", (domain, callback) => {
  process.stderr.write(
    "NEED_GUARD:" + (domain || "2fa") + "\\n"
  );
  process.exit(2);
});

client.on("error", (err) => {
  process.stderr.write("ERROR:" + err.message + "\\n");
  process.exit(1);
});

client.on("loggedOn", () => {
  process.stderr.write(
    "Logged in as " + client.steamID.getSteamID64() + "\\n"
  );
  client.createAuthSessionTicket(appid, (err, sessionTicket) => {
    if (err) {
      process.stderr.write("Ticket error: " + err.message + "\\n");
      process.exit(1);
    }
    const buf = Buffer.isBuffer(sessionTicket) ? sessionTicket : sessionTicket.sessionTicket || sessionTicket;
    const result = {
      steam_id: client.steamID.getSteamID64(),
      session_ticket: Buffer.from(buf).toString("hex").toUpperCase(),
    };
    process.stdout.write(JSON.stringify(result) + "\\n");
    process.stderr.write(
      "Ticket generated (" + Buffer.from(buf).length + " bytes)\\n"
    );
    setTimeout(() => process.exit(0), 500);
  });
});
"""

SALT = b'co!=Y;(UQCGxJ_n82'
HEAD = bytes.fromhex('6b20e2ab6c311330f761d737ce3f3025750850665eea58b6372f8d2f57501eb344bdb7270a9067f5b63cd61f152cfb986cbfbf7a')
SENSITIVE_ERROR_KEYS = {"auth_key", "steam_session_ticket", "sid", "udid", "device_id"}


def redact_for_console(value, key=""):
    if key in SENSITIVE_ERROR_KEYS:
        return "<redacted>"
    if isinstance(value, dict):
        return {k: redact_for_console(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_for_console(item, key) for item in value[:20]]
    if isinstance(value, str) and len(value) > 160:
        return value[:160] + "...<truncated>"
    return value


# Credential / device-identity fields that must NEVER be persisted to the on-disk
# trace log, even when tracing is explicitly enabled for debugging. The key is
# kept (so the protocol structure stays debuggable) but the value is masked.
# Mirrors SENSITIVE_ERROR_KEYS + report._REDACT_KEYS; viewer_id is intentionally
# NOT redacted (it's a non-secret identifier used throughout debugging).
TRACE_REDACT_KEYS = {
    "auth_key", "steam_session_ticket", "steam_ticket", "sid", "udid",
    "device_id", "device_name", "graphics_device_name", "ip_address",
    "steam_id", "dmm_viewer_id", "dmm_onetime_token", "credential",
    "password", "steam_password_seed", "keychain",
}


def _redact_for_trace(obj):
    """Structure-preserving redaction for trace files: masks the VALUE of any
    credential/identity key (at any depth) while keeping every other field intact
    (no truncation), and never mutates the input."""
    if isinstance(obj, dict):
        return {k: ("<redacted>" if k in TRACE_REDACT_KEYS else _redact_for_trace(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_for_trace(item) for item in obj]
    return obj


def format_api_error(ep, rc, res):
    details = {
        "endpoint": ep,
        "response_code": res.get("response_code"),
        "result_code": rc,
        "data_headers": redact_for_console(res.get("data_headers") or {}),
    }
    data = res.get("data")
    if isinstance(data, dict):
        interesting = {}
        for key in (
            "error_code",
            "error_message",
            "message",
            "result_code",
            "viewer_id",
            "current_turn",
            "chara_info",
            "single_mode_chara_light",
        ):
            if key in data:
                interesting[key] = data[key]
        if interesting:
            details["data"] = redact_for_console(interesting)
    elif data is not None:
        details["data"] = redact_for_console(data)
    return json.dumps(details, ensure_ascii=False, default=str)

def sm5(data):
    h = hashlib.md5()
    h.update(data)
    h.update(SALT)
    return h.digest()

def make_sid(vid, udid):
    return sm5((str(vid) + udid).encode())

def next_sid(sid):
    return sm5(sid.encode())

def gen_key():
    out = b''
    while len(out) < 32:
        out += format(random.randint(0, 65535), 'x').encode()
    return out[:32]

def get_iv(udid):
    return udid.replace('-', '').lower()[:16].encode()

def get_raw_udid(udid):
    return bytes.fromhex(udid.replace('-', '').lower())

def pack(sid, udid_raw, auth, payload, udid):
    key = gen_key()
    p = msgpack.packb(payload, use_bin_type=True)
    body = AES.new(key, AES.MODE_CBC, get_iv(udid)).encrypt(pad(struct.pack('<I', len(p)) + p, 16)) + key
    h = HEAD + sid + udid_raw + os.urandom(32)
    if auth: h += auth
    return base64.b64encode(struct.pack('<I', len(h)) + h + body)

def unpack(text, udid):
    raw = base64.b64decode(text)
    key, cipher = raw[-32:], raw[:-32]
    p = unpad(AES.new(key, AES.MODE_CBC, get_iv(udid)).decrypt(cipher), 16)
    return msgpack.unpackb(p[4:4+struct.unpack('<I', p[:4])[0]], raw=False, strict_map_key=False)

def get_gpu():
    if platform.system() != "Windows":
        raise RuntimeError(f"Unsupported OS: {platform.system()}. Only Windows is supported for PC info consistency.")

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Video") as video_key:
            for i in range(winreg.QueryInfoKey(video_key)[0]):
                adapter_guid = winreg.EnumKey(video_key, i)
                adapter_path = rf"SYSTEM\CurrentControlSet\Control\Video\{adapter_guid}\0000"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, adapter_path) as adapter_key:
                        value, _ = winreg.QueryValueEx(adapter_key, "HardwareInformation.AdapterString")
                        if isinstance(value, bytes):
                            value = value.decode("utf-16-le", errors="ignore")
                        gpu_name = str(value).replace("\x00", "").strip()
                        if gpu_name:
                            return gpu_name
                except OSError:
                    continue
    except Exception as e:
        raise RuntimeError(f"Failed to fetch GPU info: {e}") from e

    raise RuntimeError("Failed to fetch GPU info: display adapter registry value empty")

def get_os():
    return f"Windows 11  ({platform.version()}) 64bit"

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

def _read_smbios_identity():
    """Return (system_product_name, board_manufacturer) from SMBIOS.

    Reads whichever source is available -- they all expose the SAME firmware
    data, so the derived device_name / device_id is identical regardless of which
    one answers:
      1. HARDWARE\DESCRIPTION\System\BIOS         (volatile hive; absent on some Windows builds)
      2. SYSTEM\CurrentControlSet\Control\SystemInformation  (persistent)
      3. WMI (Win32_ComputerSystemProduct / Win32_BaseBoard)
    Returns ("", "") only if every source fails.
    """
    import winreg

    def _qv(key, name):
        try:
            return str(winreg.QueryValueEx(key, name)[0]).strip()
        except OSError:
            return ""

    # 1) Volatile BIOS hive (the original source).
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as k:
            name = _qv(k, "SystemProductName")
            if name:
                return name, _qv(k, "BaseBoardManufacturer")
    except OSError:
        pass

    # 2) Persistent SystemInformation key (same SMBIOS values).
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\SystemInformation") as k:
            name = _qv(k, "SystemProductName")
            if name:
                # BaseBoardManufacturer is often blank here; SystemManufacturer
                # carries the value the BIOS hive exposes as the board maker.
                return name, (_qv(k, "BaseBoardManufacturer") or _qv(k, "SystemManufacturer"))
    except OSError:
        pass

    # 3) WMI fallback (same firmware data, different access path).
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "$p=Get-CimInstance Win32_ComputerSystemProduct;"
             "$b=Get-CimInstance Win32_BaseBoard;"
             "Write-Output $p.Name; Write-Output $b.Manufacturer"],
            stderr=subprocess.DEVNULL, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if lines:
            return lines[0], (lines[1] if len(lines) > 1 else "")
    except Exception:
        pass

    return "", ""


def get_hwid(seed_string="default"):
    guid = str(uuid.uuid4()).lower()

    if platform.system() != "Windows":
        raise RuntimeError(f"Unsupported OS: {platform.system()}. Only Windows is supported for HWID consistency.")

    # v2.1: read system identity from whichever SMBIOS source is available
    # (BIOS hive -> SystemInformation -> WMI). All expose the same firmware data,
    # so device_name -- and therefore device_id -- is identical regardless of
    # which one answers; the bot no longer refuses to start when the volatile
    # HARDWARE\DESCRIPTION\System\BIOS key is missing on newer Windows builds.
    device_name, board_mfg = _read_smbios_identity()
    if board_mfg:
        device_name = f"{device_name} ({board_mfg})"
    if not device_name:
        raise RuntimeError("Failed to fetch system product name from registry or WMI. Refusing to start.")

    machine_guid = ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as crypto_key:
            machine_guid, _ = winreg.QueryValueEx(crypto_key, "MachineGuid")
    except OSError:
        pass

    hardware_string = f"{device_name}_{machine_guid}_{seed_string}"
    device_id = hashlib.sha1(hardware_string.encode()).hexdigest()

    return {
        'device_name': device_name,
        'graphics_device_name': get_gpu(),
        'platform_os_version': get_os(),
        'ip_address': get_ip(),
        'udid': guid,
        'device_id': device_id
    }

def _resolve_exe(name):
    """Find an executable across platforms.

    On Windows, ``node`` ships as ``node.exe`` and ``npm`` as ``npm.cmd``.
    ``subprocess`` without ``shell=True`` will not auto-resolve the ``.cmd``
    extension and raises a cryptic ``[WinError 2] The system cannot find the
    file specified``. Resolving the full path with ``shutil.which`` (which knows
    about PATHEXT) avoids that. Returns the resolved path or ``None``.
    """
    found = shutil.which(name)
    if found:
        return found
    if platform.system() == "Windows":
        for ext in (".cmd", ".exe", ".bat"):
            found = shutil.which(name + ext)
            if found:
                return found
    return None


def check_deps():
    node = _resolve_exe("node")
    if not node:
        raise Exception(
            "Node.js is required for Steam login but was not found. "
            "Install it from https://nodejs.org/ (LTS), reopen your terminal so "
            "PATH refreshes, then restart the bot."
        )
    if not os.path.exists(os.path.join(DIR, 'node_modules')):
        npm = _resolve_exe("npm")
        if not npm:
            raise Exception(
                "npm was not found, so the Steam login dependency (steam-user) "
                "cannot be installed automatically. Open a terminal in the bot "
                "folder and run: npm install"
            )
        try:
            subprocess.run([npm, 'install', '--silent'], check=True, cwd=DIR)
        except FileNotFoundError as exc:
            raise Exception(
                "Failed to launch npm to install the Steam login dependency. "
                "Open a terminal in the bot folder and run: npm install"
            ) from exc
    return node


def get_ticket(u, p, c=''):
    global LAST_TICKET_GEN_RESULT
    node = check_deps()
    cmd = [node, '-e', TICKET_GEN_JS, '--', '--dummy', '--username', u, '--password', p]
    if c: cmd += ['--code', c]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, cwd=DIR)
    except FileNotFoundError as exc:
        raise Exception(
            "Could not launch Node.js to perform Steam login. Confirm Node.js is "
            "installed and on PATH (run 'node --version' in a terminal), then "
            "restart the bot."
        ) from exc
    LAST_TICKET_GEN_RESULT = {
        'stdout': proc.stdout,
        'stderr': proc.stderr,
        'returncode': proc.returncode,
    }
    if proc.returncode == 2:
        raise Exception('STEAM_GUARD_REQUIRED')

    out = proc.stdout.strip()
    if not out or proc.returncode != 0:
        error_msg = proc.stderr.strip() or 'fail'
        raise Exception(error_msg)

    line = out.split('\n')[-1]
    try:
        d = json.loads(line)
        return d['steam_id'], d['session_ticket']
    except:
        raise Exception('bad json')

class UmaClient:

    def __init__(self, cfg, trace_enabled=False):
        profile = get_hwid(cfg.get('steam_password_seed', 'default'))

        self.viewer_id = cfg.get('viewer_id', 0)
        self.udid_str = cfg.get('udid') or profile['udid']
        self.auth_key_hex = cfg.get('auth_key', '')
        self.steam_id = str(cfg.get('steam_id', ''))
        self.steam_ticket = cfg.get('steam_session_ticket', '')
        # Steam credentials (plain at the client layer) let us mint a fresh
        # session ticket mid-run when the server reports the old one as expired
        # (error 394). on_ticket_refreshed is an optional callback(sid, ticket)
        # the host sets to persist a refreshed ticket to disk.
        self.steam_username = cfg.get('steam_username', '')
        self.steam_password_seed = cfg.get('steam_password_seed', '')
        self.on_ticket_refreshed = None

        self.device_id = cfg.get('device_id') or profile['device_id']
        self.device_name = cfg.get('device_name') or profile['device_name']
        self.graphics_device = cfg.get('graphics_device_name') or profile['graphics_device_name']
        self.ip_address = cfg.get('ip_address') or profile['ip_address']
        self.platform_os = cfg.get('platform_os_version') or profile['platform_os_version']
        self.locale = cfg.get('locale', 'JPN')
        
        self.unity_ver = cfg.get('unity_ver', '2022.3.62f2')
        self.app_ver = cfg.get('app_ver', '')
        self.res_ver = cfg.get('res_ver', '')

        if not self.app_ver or not self.res_ver:
             pass

        self.sid = bytes(16)
        self.tp_info = {}
        self.coin_info = {}
        self.item_map = {}
        self.current_scenario_id = None
        # Last full response payloads, cached so the local /api/latent route can
        # surface under-used fields with NO extra game call (API capability map).
        self.last_account_data = {}    # load/index `data`
        self.last_career_data = {}     # single_mode_free/{load,start} `data`
        self.last_data_headers = {}    # data_headers (server_time / maintenance flag)
        self.session = requests.Session()
        self.update_headers()
        self.api_jitter = dna_uniform(-0.02, 0.02)

        self.on_api_log = None
        self.trace_file = None
        if trace_enabled:
            self._init_trace_log()

    def _init_trace_log(self):
        try:
            log_dir = TRACE_DIR / "api_payloads"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            suffix = uuid.uuid4().hex[:6]
            self.trace_file = log_dir / f"{ts}_{suffix}_payloads.jsonl"
        except Exception as e:
            print(f"Error initializing trace log: {e}")
            self.trace_file = None

    def api_log(self, direction, ep, data, req_id=None):
        log_entry = {
            "ts": time.time(),
            "direction": direction,
            "endpoint": ep,
            "data": data
        }
        if req_id:
            log_entry["req_id"] = req_id
            
        if callable(self.on_api_log):
            try:
                self.on_api_log(direction, ep, data, req_id)
            except Exception:
                pass

        # Publish a compact, SECRET-FREE event to the live stream bus (SSE
        # /api/stream). Independent of on_api_log so it survives the runner owning
        # that slot. Never the request payload (which carries the steam ticket).
        try:
            evt = {"ts": log_entry["ts"], "dir": direction, "ep": ep, "req_id": req_id}
            if direction == "RES" and isinstance(data, dict):
                evt["rc"] = (data.get("data_headers") or {}).get("result_code")
            elif direction == "ERR" and isinstance(data, dict):
                evt["err"] = data.get("http_status") or data.get("error") or True
            event_bus.publish(evt)
        except Exception:
            pass

        if self.trace_file:
            try:
                def _json_default(obj):
                    if isinstance(obj, bytes):
                        return obj.hex()
                    return str(obj)

                with open(self.trace_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(_redact_for_trace(log_entry), ensure_ascii=False, default=_json_default) + "\n")
            except Exception as e:
                print(f"Error writing to log: {e}")




    def auth_bytes(self):
        if not self.auth_key_hex or self.auth_key_hex == 'YOUR_AUTH_KEY_HERE':
            return b''
        return bytes.fromhex(self.auth_key_hex)

    def has_captured_auth(self):
        try:
            int(self.viewer_id)
            bytes.fromhex(str(self.auth_key_hex))
        except (TypeError, ValueError):
            return False
        return bool(
            self.viewer_id
            and self.udid_str
            and self.auth_key_hex
            and self.auth_key_hex != 'YOUR_AUTH_KEY_HERE'
            and self.steam_id
            and self.steam_ticket
        )

    @staticmethod
    def _payload_int(mapping, keys, default=0):
        if not isinstance(mapping, dict):
            return default
        for key in keys:
            if key in mapping and mapping.get(key) is not None:
                try:
                    return int(mapping.get(key))
                except Exception:
                    return default
        return default

    @classmethod
    def _payload_item_id(cls, item):
        return cls._payload_int(item or {}, ('item_id', 'itemId', 'id'), 0)

    @classmethod
    def _payload_item_count(cls, item):
        # Account payloads from different endpoints have used several count
        # field names.  Accept all known count-shaped variants so Toughness 30
        # is not marked missing just because `number` was renamed.
        return cls._payload_int(
            item or {},
            ('number', 'item_num', 'itemNum', 'num', 'count', 'quantity', 'owned_num', 'own_num', 'item_count'),
            0,
        )

    def _refresh_item_map(self, item_list):
        if not isinstance(item_list, list):
            return
        for item in item_list:
            iid = self._payload_item_id(item)
            if not iid:
                continue
            self.item_map[int(iid)] = int(self._payload_item_count(item) or 0)

    def refresh_cached_account_state(self, data):
        if not data:
            return
        if data.get('tp_info'):
            self.tp_info = data['tp_info']
        if data.get('coin_info'):
            self.coin_info = data['coin_info']

        item_list = data.get('user_item') or data.get('user_item_array') or data.get('item_list')
        self._refresh_item_map(item_list)

    def _cache_response(self, ep, res):
        """Stash the last full response data so /api/latent can read it without a
        new game call. data_headers (server_time / maintenance) is kept for every
        endpoint; the heavy `data` blocks only for the account/career loads."""
        if not isinstance(res, dict):
            return
        dh = res.get('data_headers')
        if isinstance(dh, dict):
            self.last_data_headers = dh
        data = res.get('data')
        if not isinstance(data, dict):
            return
        if ep == 'load/index':
            self.last_account_data = data
        elif ep in ('single_mode_free/load', 'single_mode_free/start'):
            self.last_career_data = data

    # --- Out-of-career endpoints not previously wrapped (API capability map). The
    # payloads marked INFERRED are derived by analogy to wrapped calls / community
    # knowledge; verify against a live capture before relying on a write succeeding.
    # They are exposed only via the dev-only debug action routes, never auto-called.
    def home_index(self):
        """Load the out-of-career home screen (read)."""
        return self.call('home/index', {})

    def item_use(self, item_id, item_num=1, client_own_num=None):
        """Use a consumable OUTSIDE a career (item/use). INFERRED payload (mirrors
        item/use_recovery_item's {item_id, client_own_num, item_num})."""
        if client_own_num is None:
            client_own_num = int(getattr(self, 'item_map', {}).get(int(item_id), 0) or 0)
        return self.call('item/use', {
            'item_id': int(item_id), 'item_num': int(item_num), 'client_own_num': int(client_own_num),
        })

    def support_card_enhance(self, support_card_id, use_item_info_array=None):
        """Enhance / limit-break a support card (support_card/enhance). INFERRED payload."""
        return self.call('support_card/enhance', {
            'support_card_id': int(support_card_id),
            'use_item_info_array': use_item_info_array or [],
        })

    def chara_talent(self, trained_chara_id, rank_up_target_rank=None, use_item_info_array=None):
        """Raise a trained chara's talent / awakening (chara/talent). INFERRED payload."""
        payload = {'trained_chara_id': int(trained_chara_id)}
        if rank_up_target_rank is not None:
            payload['rank_up_target_rank'] = int(rank_up_target_rank)
        if use_item_info_array is not None:
            payload['use_item_info_array'] = use_item_info_array
        return self.call('chara/talent', payload)

    def chara_nickname(self, trained_chara_id, nickname_id):
        """Set a chara's epithet / title (chara/nickname). INFERRED payload."""
        return self.call('chara/nickname', {
            'trained_chara_id': int(trained_chara_id), 'nickname_id': int(nickname_id),
        })

    def regen_sid(self):
        self.sid = make_sid(self.viewer_id, self.udid_str)

    def common(self):
        return {
            'viewer_id': self.viewer_id, 'device': 4, 'device_id': self.device_id,
            'device_name': self.device_name, 'graphics_device_name': self.graphics_device,
            'ip_address': self.ip_address, 'platform_os_version': self.platform_os,
            'carrier': '', 'keychain': 0, 'locale': self.locale,
            'button_info': '', 'dmm_viewer_id': None, 'dmm_onetime_token': None,
            'steam_id': self.steam_id,
            'steam_session_ticket': self.steam_ticket
        }

    def update_headers(self):
        self.session.headers.update({
            'User-Agent': f'UnityPlayer/{self.unity_ver} (UnityWebRequest/1.0, libcurl/8.10.1-DEV)',
            'Accept': '*/*', 'Accept-Encoding': 'deflate, gzip',
            'Content-Type': 'application/x-msgpack', 'X-Unity-Version': self.unity_ver
        })

    def call(self, ep, args=None, retry_208=6, retry_205=3):
        if not hasattr(self, '_last_raw_call_ts'):
            self._last_raw_call_ts = 0

        floor = MIN_CALL_SPACING
        if floor > 0:
            el = time.time() - self._last_raw_call_ts
            if el < floor:
                dna_sleep(floor - el, floor - el)

        self._last_raw_call_ts = time.time()

        req_id = str(uuid.uuid4())[:8]
        payload = args or {}
        payload.update(self.common())
        
        if ep == 'single_mode_free/race_out':
            import ctypes
            try:
                user32 = ctypes.windll.user32
                user32.SetProcessDPIAware()
                screen_h = user32.GetSystemMetrics(1)
            except Exception:
                screen_h = 864
                
            window_w = int(screen_h * 9 / 16)
            scale_factor = 1080 / window_w
            
            ref_x = max(844, min(1150, int(dna_gauss(991, 62))))
            ref_y = max(55, min(255, int(dna_gauss(144, 33))))
            
            physical_x = int(ref_x / scale_factor)
            physical_y = int(ref_y / scale_factor)
            
            click_x = int(physical_x * scale_factor * 10000)
            click_y = int(physical_y * scale_factor * 10000)
            
            click_ts = int(time.time() - dna_uniform(3.0, 4.5))
            btn = {
                "ViewerId": self.viewer_id,
                "DeviceId": 4,
                "ScenarioId": self.current_scenario_id,
                "ClickPosX": click_x,
                "ClickPosY": click_y,
                "ClickServerTime": click_ts
            }
            payload['button_info'] = json.dumps(btn, separators=(',', ':'))

        body = pack(self.sid, get_raw_udid(self.udid_str), self.auth_bytes(), payload, self.udid_str)
        headers = {
            'SID': self.sid.hex(), 'Device': '4', 'ViewerID': str(self.viewer_id),
            'APP-VER': self.app_ver, 'RES-VER': self.res_ver,
        }
        

        self.api_log("REQ", ep, {
            "payload": payload,
        }, req_id)
        
        net_retries_left = 7
        http_retries_left = 5
        retries_205_left = retry_205
        retries_208_left = retry_208
        retries_394_left = 5
        net_attempt = 0
        http_attempt = 0
        attempt_208 = 0

        while True:
            try:
                resp = self.session.post(BASE_URL + ep, data=body, headers=headers, timeout=30)
            except Exception as e:
                if net_retries_left > 0:
                    net_retries_left -= 1
                    wait_time = min(1.0 + (net_attempt * 2.5), 15.0)
                    net_attempt += 1
                    print(f"Network error on {ep}, retrying in {wait_time:.1f}s... ({net_retries_left} left)")
                    dna_sleep(wait_time, wait_time)
                    continue
                self.api_log("ERR", ep, {"error": str(e)}, req_id)
                raise Exception(f'Network error on {ep}: {e}')

            if resp.status_code != 200:
                body_preview = resp.text[:500] if resp.text else ""
                retryable_http_statuses = {500, 502, 503, 504}
                self.api_log(
                    "ERR",
                    ep,
                    {
                        "http_status": resp.status_code,
                        "body": body_preview,
                        "retryable": resp.status_code in retryable_http_statuses,
                        "http_retries_left": http_retries_left,
                    },
                    req_id,
                )
                if resp.status_code in retryable_http_statuses and http_retries_left > 0:
                    http_retries_left -= 1
                    wait_time = min(1.0 * (2 ** http_attempt), 15.0)
                    http_attempt += 1
                    print(
                        f"HTTP {resp.status_code} on {ep}; temporary gateway/server error. "
                        f"Retrying in {wait_time:.1f}s... ({http_retries_left} left)"
                    )
                    dna_sleep(wait_time, wait_time + 0.5)
                    continue

                print(f"HTTP error on {ep}: status={resp.status_code} body={body_preview}")
                raise Exception(f'HTTP {resp.status_code} on {ep}: {body_preview}')

            res = unpack(resp.text.strip(), self.udid_str)
            dh = res.get('data_headers', {})
            rc = dh.get('result_code', 0)

            self.api_log("RES", ep, res, req_id)
            self._cache_response(ep, res)

            data = res.get('data', {})
            if isinstance(data, dict):
                if data.get('tp_info'):
                    self.tp_info = data['tp_info']
                if data.get('coin_info'):
                    self.coin_info = data['coin_info']
                if data.get('chara_info') and data['chara_info'].get('scenario_id'):
                    self.current_scenario_id = data['chara_info']['scenario_id']
                item_list = data.get('user_item') or data.get('user_item_array') or data.get('item_list')
                self._refresh_item_map(item_list)

            if rc == 709:
                new_vid = dh.get('viewer_id') or res.get('data', {}).get('viewer_id')
                if new_vid and new_vid != self.viewer_id:
                    print(f"VIEWER ID MISMATCH on 709: {self.viewer_id} -> {new_vid}")
                    self.viewer_id = new_vid
                    self.regen_sid()
                raise Exception(f'709 on {ep}')

            if rc != 1:
                if rc == 205 and retries_205_left > 0:
                    retries_205_left -= 1
                    print(f"205 on {ep}, retrying... ({retries_205_left} left)")
                    dna_sleep(0.14, 0.19, 0.166, 0.0083)
                    continue

                if rc == 394 and retries_394_left > 0:
                    retries_394_left -= 1
                    print(f"API error 394 on {ep}, sleeping and retrying... ({retries_394_left} left)")
                    dna_sleep(2.5, 4.0)
                    continue

                if rc == 208 and retries_208_left > 0:
                    if ep in {"single_mode_free/gain_skills", "single_mode_free/multi_item_exchange", "single_mode_free/multi_item_use"}:
                        return res
                    retries_208_left -= 1
                    wait_min = min(0.8 * (2 ** attempt_208), 12.0)
                    wait_max = min(wait_min * 1.6, 18.0)
                    attempt_208 += 1
                    print(f"API error 208 (SERVER BUSY) on {ep}, sleeping ~{wait_min:.1f}s and retrying... (attempts left: {retries_208_left})")
                    dna_sleep(wait_min, wait_max)
                    continue

                err_detail = format_api_error(ep, rc, res)
                err_msg = f'API error {rc} on {ep}: {err_detail}'
                if not (rc == 102 and ep in {"single_mode_free/race_end", "single_mode_free/race_out"}):
                    print(err_msg)
                raise Exception(err_msg)

            if dh.get('sid') and isinstance(dh['sid'], str) and dh['sid'].strip():
                self.sid = next_sid(dh['sid'])

            return res

    def hard_reset(self):
        self.sid = bytes(16)
        self.regen_sid()
        self.session.close()
        self.session = requests.Session()
        self.update_headers()
        try:
            self.call('tool/start_session', {'attestation_type': 0, 'device_token': None})
            res = self.call('load/index', {
                'adid': ''
            })
            data = res.get('data', {})
            self.refresh_cached_account_state(data)
            self.read_info()
            
            try:
                sm_res = self.call('single_mode_free/load', {})
                chara = sm_res.get('data', {}).get('chara_info')
                if not chara:
                    raise StateRecoveryError("No chara_info returned in single_mode_free/load after hard reset.")
            except Exception as e:
                if isinstance(e, StateRecoveryError):
                    raise
                if "API error 201" in str(e) or "API error 102" in str(e):
                    raise StateRecoveryError(f"Cannot recover training state: {e}")
                print(f"single_mode_free/load during hard_reset failed: {e}")

            return res
        except StateRecoveryError:
            raise
        except Exception as e:
            print(f"Hard Reset Failure: {e}")
            raise

    def signup(self):
        self.regen_sid()
        self.call('tool/pre_signup')
        dna_sleep(0.83, 0.83)
        self.regen_sid()
        res = self.call('tool/signup', {
            'error_code': 0, 'error_message': '', 'attestation_type': 0, 
            'optin_user_birth': 199801, 'dma_state': 0, 'country': 'Canada', 'credential': ''
        })
        d = res.get('data', {})
        if d.get('viewer_id'): 
            self.viewer_id = d['viewer_id']
        if d.get('auth_key'): self.auth_key_hex = base64.b64decode(d['auth_key']).hex()
        self.save_config()
        return res

    def refresh_steam_ticket(self, code=''):
        """Mint a fresh Steam session ticket mid-run.

        Steam session tickets are single-use / short-lived; the game server
        reports a stale one as error 394. Re-presenting the same ticket can
        never succeed, so on 394 we mint a new ticket here and re-establish the
        session. Returns True on success, False if no credentials are stored.
        Raises (e.g. STEAM_GUARD_REQUIRED) so the caller can fall back to manual
        auth when a 2FA code is genuinely required.
        """
        if not (self.steam_username and self.steam_password_seed):
            return False
        sid, tkt = get_ticket(self.steam_username, self.steam_password_seed, code)
        self.steam_id = str(sid)
        self.steam_ticket = tkt
        if callable(self.on_ticket_refreshed):
            try:
                self.on_ticket_refreshed(self.steam_id, self.steam_ticket)
            except Exception:
                pass  # persistence is best-effort; never block recovery
        return True

    def login(self, max_retries=3):
        using_existing_auth = self.has_captured_auth()
        if not using_existing_auth:
            self.signup()
            using_existing_auth = self.has_captured_auth()

        old_h = dict(self.session.headers)
        self.session.close()
        self.session = requests.Session()
        self.session.headers.update(old_h)

        ticket_refreshed = False
        for attempt in range(max_retries + 1):
            try:
                self.regen_sid()
                self.call('tool/start_session', {'attestation_type': 0, 'device_token': None})
                res = self.call('load/index', {'adid': ''})
                data = res.get('data', {})
                self.refresh_cached_account_state(data)
                self.read_info()
                return res
            except Exception as e:
                err = str(e)
                if '709' in err and attempt < max_retries:
                    dna_sleep(0.83, 0.83)
                    continue
                if '394' in err and attempt < max_retries:
                    # 394 = invalid/expired Steam session ticket, NOT a transient
                    # server-busy. Mint a fresh ticket once and retry instead of
                    # re-presenting the dead one (which would loop forever).
                    if not ticket_refreshed and self.steam_username and self.steam_password_seed:
                        try:
                            if self.refresh_steam_ticket():
                                ticket_refreshed = True
                                continue
                        except Exception as re_exc:
                            if 'STEAM_GUARD_REQUIRED' in str(re_exc):
                                raise  # needs a 2FA code -> fall back to manual
                    dna_sleep(2.5, 2.5)
                    continue
                if '202' in err and attempt < max_retries:
                    dna_sleep(4.15, 4.15)
                    continue
                raise

    def recovery_tp(self, count=1):
        """Restore TP with Jewels, matching Umabot's currency-only recovery path."""
        total_jewels = self.coin_info.get("fcoin", 0) + self.coin_info.get("coin", 0)
        result = self.call("user/recovery_trainer_point", {
            "count": count,
            "client_own_num": total_jewels,
        })
        data = result.get("data", {})
        tp = data.get("tp_info", {})
        if tp:
            self.tp_info = tp
        coin = data.get("coin_info", {})
        if coin:
            self.coin_info = coin
        return tp


    # TP recovery item.  Umabot uses item 32 through item/use_recovery_item
    # before falling back to Jewels when the selected recovery mode allows it.
    TP_POTION_ITEM_ID = 32

    def tp_potion_count(self, item_id=None):
        item_id = int(item_id or self.TP_POTION_ITEM_ID)
        return int(self.item_map.get(item_id, 0) or 0)

    def use_recovery_item(self, item_num=1, item_id=None):
        """Recover TP by using a TP recovery item via item/use_recovery_item.

        This mirrors Umabot's known-good payload shape:
        {item_id, client_own_num, item_num}.  It deliberately avoids
        user/recovery_trainer_point for item-backed TP recovery.
        """
        item_id = int(item_id or self.TP_POTION_ITEM_ID)
        item_num = max(1, int(item_num or 1))
        own = self.tp_potion_count(item_id)
        result = self.call("item/use_recovery_item", {
            "item_id": item_id,
            "client_own_num": own,
            "item_num": item_num,
        })
        data = result.get("data", {}) if isinstance(result, dict) else {}
        tp = data.get("tp_info", {})
        if tp:
            self.tp_info = tp
        coin = data.get("coin_info", {})
        if coin:
            self.coin_info = coin
        item_list = data.get("user_item") or data.get("user_item_array") or data.get("item_list")
        if isinstance(item_list, list):
            self._refresh_item_map(item_list)
        else:
            self.item_map[item_id] = max(0, own - item_num)
        return tp

    def read_info(self):
        return self.call('read_info/index', {
            'add_home_story_data_array': [],
            'add_short_episode_data_array': [],
            'add_home_poster_data_array': [],
            'add_tutorial_guide_data_array': [],
            'add_released_episode_data_array': [],
        })

    def finish_career(self, current_turn, is_force_delete=False):
        return self.call('single_mode_free/finish', {
            'is_force_delete': is_force_delete,
            'current_turn': current_turn
        })


    def remove_trained_chara(self, trained_chara_id_array: list):
        """Delete one or more trained characters by instance id."""
        return self.call('trained_chara/remove', {
            'trained_chara_id_array': [int(i) for i in trained_chara_id_array],
        })

    def load_career(self):
        return self.call('single_mode_free/load', {})

    def minigame_end(self, current_turn, result_state=1, result_value=0, result_detail_array=None):
        return self.call('single_mode_free/minigame_end', {
            'result': {
                'result_state': result_state,
                'result_value': result_value,
                'result_detail_array': result_detail_array,
            },
            'current_turn': current_turn,
        })
    
    def save_config(self, cfg_path=None):
        global LAST_SAVED_CONFIG
        LAST_SAVED_CONFIG = {
            "viewer_id": self.viewer_id,
            "udid": self.udid_str,
            "auth_key": self.auth_key_hex,
            "steam_id": self.steam_id,
            "steam_session_ticket": self.steam_ticket,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "graphics_device_name": self.graphics_device,
            "ip_address": self.ip_address,
            "platform_os_version": self.platform_os,
        }

    def pre_single_mode(self, exclude_viewer_ids=None):
        payload = {}
        if exclude_viewer_ids:
            payload['exclude_viewer_id_array'] = exclude_viewer_ids
        return self.call('pre_single_mode/index', payload)

    def start_career(self, card_id, support_card_ids, friend_viewer_id, friend_card_id,
                     parent_id_1, parent_id_2, scenario_id, deck_id=1, use_tp=30,
                     tp_info=None, current_money=0, succession_rank_point=0,
                     rental_viewer_id=0, rental_trained_chara_id=0,
                     difficulty_id=0, difficulty=0, is_boost=0,
                     boost_story_event_id=0):
        if not tp_info:
            tp_info = {'current_tp': 100, 'max_tp': 100, 'max_recovery_time': 0}
        start_payload = {
            'start_chara': {
                'card_id': card_id,
                'support_card_ids': support_card_ids,
                'friend_support_card_info': {
                    'viewer_id': friend_viewer_id,
                    'support_card_id': friend_card_id
                },
                'succession_trained_chara_id_1': parent_id_1,
                'succession_trained_chara_id_2': parent_id_2,
                'rental_succession_trained_chara': {
                    'viewer_id': rental_viewer_id,
                    'trained_chara_id': rental_trained_chara_id,
                    'is_circle_member': False,
                    'is_event_rental': False
                },
                'scenario_id': scenario_id,
                'selected_difficulty_info': {
                    'difficulty_id': difficulty_id,
                    'difficulty': difficulty,
                    'is_boost': is_boost
                },
                'select_deck_id': deck_id,
                'boost_story_event_id': boost_story_event_id,
                'is_play_training_challenge': False
            },
            'tp_info': tp_info,
            'current_money': current_money,
            'use_tp': use_tp,
            'current_succession_rank_point': succession_rank_point
        }
        return self.call('single_mode_free/start', start_payload)

    def exec_command(self, command_type, command_id, current_turn, current_vital, command_group_id=0, select_id=0):
        return self.call('single_mode_free/exec_command', {
            'command_type': command_type,
            'command_id': command_id,
            'command_group_id': command_group_id,
            'select_id': select_id,
            'current_turn': current_turn,
            'current_vital': current_vital
        })

    def check_event(self, event_id, current_turn, chara_id=0, choice_number=0):
        payload = {
            'event_id': event_id,
            'chara_id': chara_id or 0,
            'choice_number': choice_number if choice_number is not None else 0,
            'current_turn': current_turn
        }
        return self.call('single_mode_free/check_event', payload)

    def use_items(self, use_item_info_array, current_turn):
        return self.call('single_mode_free/multi_item_use', {
            'use_item_info_array': use_item_info_array,
            'current_turn': current_turn
        })

    def exchange_items(self, exchange_item_info_array, current_turn):
        return self.call('single_mode_free/multi_item_exchange', {
            'exchange_item_info_array': exchange_item_info_array,
            'current_turn': current_turn
        })

    def gain_skills(self, gain_skill_info_array, current_turn):
        gain_skill_info_array = [
            {
                "skill_id": item.get("skill_id"),
                "level": item.get("level", item.get("skill_level", 1)),
            }
            for item in gain_skill_info_array
        ]
        return self.call('single_mode_free/gain_skills', {
            'gain_skill_info_array': gain_skill_info_array,
            'current_turn': current_turn
        })

    def race_entry(self, program_id, current_turn, running_style=None):
        payload = {
            'program_id': program_id,
            'current_turn': current_turn
        }
        if running_style is not None:
            payload['running_style'] = running_style
        return self.call('single_mode_free/race_entry', payload)

    def race_start(self, is_short, current_turn):
        return self.call('single_mode_free/race_start', {
            'is_short': is_short,
            'current_turn': current_turn
        })

    def race_end(self, current_turn):
        return self.call('single_mode_free/race_end', {
            'current_turn': current_turn
        })

    def race_out(self, current_turn):
        return self.call('single_mode_free/race_out', {
            'current_turn': current_turn
        })

    def race_continue(self, current_turn, continue_type):
        return self.call('single_mode_free/continue', {
            'current_turn': current_turn,
            'continue_type': continue_type
        })

    def change_running_style(self, current_turn, running_style, program_id):
        # Sets the running style for an ENTERED race. Verified against a decoded
        # capture of the official client: the call carries program_id + running_style
        # + current_turn, and is only valid AFTER race_entry and BEFORE race_start
        # (the race-prep/strategy screen). Calling it outside that window -> error 102.
        return self.call('single_mode_free/change_running_style', {
            'program_id': program_id,
            'running_style': running_style,
            'current_turn': current_turn
        })

    def reserve_race(self, current_turn, add_race_array=None, cancel_race_array=None):
        return self.call('single_mode_free/reserve_race', {
            'current_turn': current_turn,
            'add_race_array': add_race_array or [],
            'cancel_race_array': cancel_race_array or []
        })
