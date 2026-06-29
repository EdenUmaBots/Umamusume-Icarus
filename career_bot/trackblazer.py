import json
import os
import re
import shutil
import subprocess
import time
import traceback
from pathlib import Path
from urllib.request import Request, urlopen

from career_bot.race_intelligence import race_outcome_risk, load_outcomes
try:
    from career_bot.ai_trainer import race_policy_adjustment, load_auto_config, load_policy_adjustments
except Exception:
    race_policy_adjustment = None
    load_auto_config = None
    load_policy_adjustments = None

RAW_BASE = "https://raw.githubusercontent.com/daftuyda/umamusume_trackblazer_scheduler/main"
LOCAL_SOLVER_SOURCE = "SweepyCL local Trackblazer SmartRaceSolver port"
STRUCTURED_EPITHETS_FILE = "android_smart_race_epithets.json"
STRUCTURED_RACES_FILE = "android_smart_race_races.json"
DATASETS = {
    "races": f"{RAW_BASE}/races.json",
    "epithets": f"{RAW_BASE}/epithets.json",
    "debut_races": f"{RAW_BASE}/debut_races.json",
}
APT_ORDER = {"G": 1, "F": 2, "E": 3, "D": 4, "C": 5, "B": 6, "A": 7, "S": 8}
DIST_KEYS = {"Sprint": "proper_distance_short", "Mile": "proper_distance_mile", "Medium": "proper_distance_middle", "Long": "proper_distance_long"}
SURF_KEYS = {"Turf": "proper_ground_turf", "Dirt": "proper_ground_dirt"}

GRADE_BASE = {
    "G1": {"stat": 10, "sp": 35, "grade": 5},
    "G2": {"stat": 8, "sp": 25, "grade": 4},
    "G3": {"stat": 8, "sp": 25, "grade": 3},
    "OP": {"stat": 5, "sp": 15, "grade": 2},
    "PRE-OP": {"stat": 5, "sp": 10, "grade": 1},
    "PREOP": {"stat": 5, "sp": 10, "grade": 1},
}
SUMMER_TURNS = {37, 38, 39, 40, 61, 62, 63, 64}
LATE_DEC_TURNS = {23, 47, 71}
TRAIN_LOCKS = {"train", "training", "rest", "none", "no_race", "no-race", "train_lock_sentinel"}

RACE_AGENDAS_FILE = "race_agendas.json"
_RACE_AGENDA_CACHE = {}


def load_race_agendas(base_dir):
    """Return the list of curated race agendas from
    ``data/trackblazer/race_agendas.json`` (``[]`` if the file is missing).

    An agenda is ``{id, title, description, recommended, target_epithets,
    forced_epithets}``.  Selecting one (preset ``trackblazer_race_agenda``)
    feeds its epithets into the smart solver so it schedules the races needed
    to complete them instead of minimising races for fans alone.
    """
    key = str(base_dir or "")
    if key in _RACE_AGENDA_CACHE:
        return _RACE_AGENDA_CACHE[key]
    path = Path(base_dir) / "data" / "trackblazer" / RACE_AGENDAS_FILE
    agendas = []
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            agendas = [a for a in (raw.get("agendas") or []) if isinstance(a, dict) and a.get("id")]
    except Exception:
        agendas = []
    _RACE_AGENDA_CACHE[key] = agendas
    return agendas


def resolve_agenda_epithets(base_dir, agenda_id):
    """Return ``(target_epithets, forced_epithets)`` for an agenda id, or
    ``([], [])`` when the id is empty/unknown."""
    aid = str(agenda_id or "").strip()
    if not aid or aid.lower() in ("none", "off", ""):
        return [], []
    for agenda in load_race_agendas(base_dir):
        if str(agenda.get("id")) == aid:
            return (list(agenda.get("target_epithets") or []),
                    list(agenda.get("forced_epithets") or []))
    return [], []


def _merge_epithet_lists(*lists):
    """Order-preserving de-duplicated union of epithet-name lists."""
    seen = set()
    out = []
    for lst in lists:
        for name in (lst or []):
            key = str(name or "").strip()
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return out

DEFAULT_SOLVER_WEIGHTS = {
    "raceValue": 1.0,
    "epithetValue": 1.0,
    "fanWeight": 0.001,
    "hintRewardWeight": 8.0,
    "consecutiveRacePenalty": 3.0,
    "summerPenalty": 5.0,
    "raceBonusPct": 50.0,
    "raceCostPct": 100.0,
    "forcedEpithetValue": 500.0,
    "trackblazerRewardWeight": 0.2,
    "allowSummerRacing": False,
    "distancePreferenceMode": "balanced",
    "distancePreferenceBonus": 6.0,
    "distancePreferencePenalty": 20.0,
    "lateSeniorRacePressure": 12.0,
    "lateSeniorFanPressure": 0.00025,
    "outcomeRiskWeight": 1.0,
    "longDistanceStaminaFloor": 550,
    "longDistanceRiskPenalty": 45.0,
    "enableOutcomeRisk": True,
    "enableLateSeniorPressure": True,
    "enableDistanceStaminaRisk": True,
    "itemRecoverySupportWeight": 1.0,
    "targetOptionalRaceCount": 36,
    "enableLiveAiPolicy": True,
    "liveAiConfidenceThreshold": 0.65,
    "liveAiAdjustmentWeight": 1.0,
}


def _runtime_output_root(base_dir):
    override = os.environ.get("UMA_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(base_dir).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate / "uma_runtime"
    return base.parent / "uma_runtime"


def _record_solver_fallback(base_dir, exc):
    """Persist MILP fallback details for diagnostics without breaking scheduling."""
    try:
        root = _runtime_output_root(base_dir) / "diagnostics"
        root.mkdir(parents=True, exist_ok=True)
        trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        row = {
            "ts": int(time.time()),
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "traceback": trace,
        }
        path = root / "smart_solver_fallbacks.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        latest = root / "latest_smart_solver_fallback.json"
        latest.write_text(json.dumps(row, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return None


def _scipy_milp_available():
    try:
        from scipy.optimize import milp, LinearConstraint, Bounds  # noqa: F401
        import scipy.sparse  # noqa: F401
        return True
    except Exception:
        return False


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _canon_race_name(value):
    """Canonical key for a race name that is order-independent for the
    ``X (Y)`` / ``Y (X)`` alias pattern.

    v2.0 fix: the candidate pool (data/trackblazer/races.json) names the Derby
    "Japanese Derby (Tokyo Yushun)" while race_map.json and the epithet matchers
    use "Tokyo Yushun (Japanese Derby)". Exact string/slug matching dropped the
    Derby from the pool and from every colt-crown matcher, so forcing the Triple
    Crown became infeasible and the solver substituted the filly/Tenno-Autumn
    sets. Sorting the base + parenthetical halves makes both orderings collapse to
    one key, while genuinely different parentheticals (Tenno Sho (Spring) vs
    (Autumn)) stay distinct."""
    s = " ".join(str(value or "").strip().split())
    if not s:
        return ""
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", s)
    if m:
        parts = sorted(p.strip().lower() for p in (m.group(1), m.group(2)) if p.strip())
        return _slug("|".join(parts))
    return _slug(s)


def _name_eq(a, b):
    return _canon_race_name(a) == _canon_race_name(b)


def _name_in(name, names):
    target = _canon_race_name(name)
    return any(target == _canon_race_name(n) for n in (names or []))


def cache_dir(base_dir):
    path = Path(base_dir) / "data" / "trackblazer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_scheduler_data(base_dir, force=False, timeout=20):
    """Download the static JSON used by race.daftuyda.moe and cache it locally."""
    out = cache_dir(base_dir)
    summary = {"success": True, "files": {}, "source": RAW_BASE}
    for name, url in DATASETS.items():
        target = out / f"{name}.json"
        if target.exists() and not force:
            summary["files"][name] = {"path": str(target), "cached": True, "count": _count_json(target)}
            continue
        req = Request(url, headers={"User-Agent": "Umamusume-Eden-Bot/3.x"})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        # validate JSON before replacing a working cache
        json.loads(data.decode("utf-8"))
        tmp = target.with_suffix(".json.tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
        summary["files"][name] = {"path": str(target), "cached": False, "count": _count_json(target)}
    return summary


def _count_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return len(data) if isinstance(data, list) else len(data.keys()) if isinstance(data, dict) else 0
    except Exception:
        return 0


def load_cached(base_dir):
    root = cache_dir(base_dir)
    result = {}
    for name in DATASETS:
        path = root / f"{name}.json"
        if path.exists():
            result[name] = json.loads(path.read_text(encoding="utf-8"))
    return result


def load_or_download(base_dir):
    data = load_cached(base_dir)
    # Repair partial/stale caches. v5.6 only checked races.json, which left
    # older installs without epithets.json until the user manually synced data.
    missing = [name for name in DATASETS if name not in data]
    if missing:
        download_scheduler_data(base_dir)
        data = load_cached(base_dir)
    return data


def solver_defaults(base_dir=None):
    """Return canonical Smart Race Solver defaults.

    The frontend asks for these defaults so the UI and backend no longer keep
    separate magic numbers. A checked-in JSON file may override the code
    fallback without requiring runtime network access.
    """
    defaults = dict(DEFAULT_SOLVER_WEIGHTS)
    if base_dir:
        try:
            path = Path(base_dir) / "data" / "trackblazer_solver_defaults.json"
            if path.exists():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    defaults.update(loaded)
        except Exception:
            pass
    return defaults


def _to_float(value, default=0.0, minimum=None, maximum=None):
    try:
        out = float(value)
    except Exception:
        out = float(default)
    if minimum is not None:
        out = max(float(minimum), out)
    if maximum is not None:
        out = min(float(maximum), out)
    return out


def _to_int(value, default=0, minimum=None, maximum=None):
    try:
        out = int(value)
    except Exception:
        out = int(default)
    if minimum is not None:
        out = max(int(minimum), out)
    if maximum is not None:
        out = min(int(maximum), out)
    return out


def _solver_weights(weights=None, base_dir=None):
    merged = solver_defaults(base_dir)
    if isinstance(weights, dict):
        merged.update({k: v for k, v in weights.items() if v is not None and v != ""})
    merged["raceValue"] = _to_float(merged.get("raceValue", merged.get("race_value", 1.0)), 1.0, 0.0, 10.0)
    merged["epithetValue"] = _to_float(merged.get("epithetValue", merged.get("epithet_value", 1.0)), 1.0, 0.0, 50.0)
    merged["fanWeight"] = _to_float(merged.get("fanWeight", merged.get("fans", 0.001)), 0.001, 0.0, 0.05)
    merged["hintRewardWeight"] = _to_float(merged.get("hintRewardWeight", merged.get("hint_reward_weight", 8.0)), 8.0, 0.0, 100.0)
    merged["consecutiveRacePenalty"] = _to_float(merged.get("consecutiveRacePenalty", merged.get("consecutive_penalty", 3.0)), 3.0, 0.0, 50.0)
    merged["summerPenalty"] = _to_float(merged.get("summerPenalty", merged.get("summer_penalty", 5.0)), 5.0, 0.0, 100.0)
    merged["raceBonusPct"] = _to_float(merged.get("raceBonusPct", merged.get("race_bonus_pct", 50.0)), 50.0, 0.0, 300.0)
    merged["raceCostPct"] = _to_float(merged.get("raceCostPct", merged.get("race_cost_pct", 100.0)), 100.0, 0.0, 300.0)
    merged["forcedEpithetValue"] = _to_float(merged.get("forcedEpithetValue", merged.get("forced_epithet_value", 500.0)), 500.0, 0.0, 5000.0)
    merged["trackblazerRewardWeight"] = _to_float(merged.get("trackblazerRewardWeight", merged.get("trackblazer_reward_weight", 0.2)), 0.2, 0.0, 5.0)
    merged["allowSummerRacing"] = bool(merged.get("allowSummerRacing", merged.get("allow_summer_racing", False)))
    mode = str(merged.get("distancePreferenceMode", merged.get("distance_preference_mode", "balanced")) or "balanced").lower().strip()
    if mode not in {"strict", "balanced", "loose"}:
        mode = "balanced"
    merged["distancePreferenceMode"] = mode
    merged["distancePreferenceBonus"] = _to_float(merged.get("distancePreferenceBonus", merged.get("distance_preference_bonus", 6.0)), 6.0, 0.0, 200.0)
    merged["distancePreferencePenalty"] = _to_float(merged.get("distancePreferencePenalty", merged.get("distance_preference_penalty", 20.0)), 20.0, 0.0, 500.0)
    merged["lateSeniorRacePressure"] = _to_float(merged.get("lateSeniorRacePressure", merged.get("late_senior_race_pressure", 12.0)), 12.0, 0.0, 250.0)
    merged["lateSeniorFanPressure"] = _to_float(merged.get("lateSeniorFanPressure", merged.get("late_senior_fan_pressure", 0.00025)), 0.00025, 0.0, 0.1)
    merged["outcomeRiskWeight"] = _to_float(merged.get("outcomeRiskWeight", merged.get("outcome_risk_weight", 1.0)), 1.0, 0.0, 5.0)
    merged["longDistanceStaminaFloor"] = _to_int(merged.get("longDistanceStaminaFloor", merged.get("long_distance_stamina_floor", 550)), 550, 0, 2000)
    merged["longDistanceRiskPenalty"] = _to_float(merged.get("longDistanceRiskPenalty", merged.get("long_distance_risk_penalty", 45.0)), 45.0, 0.0, 500.0)
    merged["enableOutcomeRisk"] = bool(merged.get("enableOutcomeRisk", merged.get("enable_outcome_risk", True)))
    merged["enableLateSeniorPressure"] = bool(merged.get("enableLateSeniorPressure", merged.get("enable_late_senior_pressure", True)))
    merged["enableDistanceStaminaRisk"] = bool(merged.get("enableDistanceStaminaRisk", merged.get("enable_distance_stamina_risk", True)))
    merged["itemRecoverySupportWeight"] = _to_float(merged.get("itemRecoverySupportWeight", merged.get("item_recovery_support_weight", 1.0)), 1.0, 0.0, 5.0)
    merged["targetOptionalRaceCount"] = _to_int(merged.get("targetOptionalRaceCount", merged.get("target_optional_race_count", 36)), 36, 0, 60)
    merged["enableLiveAiPolicy"] = bool(merged.get("enableLiveAiPolicy", merged.get("enable_live_ai_policy", True)))
    merged["liveAiConfidenceThreshold"] = _to_float(merged.get("liveAiConfidenceThreshold", merged.get("live_ai_confidence_threshold", 0.65)), 0.65, 0.0, 0.99)
    merged["liveAiAdjustmentWeight"] = _to_float(merged.get("liveAiAdjustmentWeight", merged.get("live_ai_adjustment_weight", 1.0)), 1.0, 0.0, 5.0)
    merged["maxCandidatesPerTurn"] = _to_int(merged.get("maxCandidatesPerTurn", merged.get("max_candidates_per_turn", 8)), 8, 1, 40)
    merged["beamWidth"] = _to_int(merged.get("beamWidth", 32), 32, 4, 256)
    if isinstance(merged.get("currentStats"), dict):
        merged["currentStats"] = dict(merged.get("currentStats") or {})
    if isinstance(merged.get("runtimeSupport"), dict):
        merged["runtimeSupport"] = dict(merged.get("runtimeSupport") or {})
    return merged


def _apt_value(value, default=7):
    if isinstance(value, int):
        return value
    return APT_ORDER.get(str(value or "A").upper(), default)



def _aptitude_match_bonus(race, aptitudes):
    """Small deterministic bonus so different trainee aptitudes can change tie-breaks."""
    aptitudes = aptitudes or {}
    distance = race.get("distance")
    surface = race.get("surface")
    d_val = _apt_value(aptitudes.get(distance) or aptitudes.get(DIST_KEYS.get(distance, "")), default=7)
    s_val = _apt_value(aptitudes.get(surface) or aptitudes.get(SURF_KEYS.get(surface, "")), default=7)
    grade = str(race.get("grade") or "").upper()
    grade_bonus = {"G1": 30, "G2": 18, "G3": 10, "OP": 0}.get(grade, 4)
    return d_val * 12 + s_val * 8 + grade_bonus

def _race_ok(race, aptitudes, floor=6):
    distance = race.get("distance")
    surface = race.get("surface")
    d_val = _apt_value(aptitudes.get(distance) or aptitudes.get(DIST_KEYS.get(distance, "")))
    s_val = _apt_value(aptitudes.get(surface) or aptitudes.get(SURF_KEYS.get(surface, "")))
    return d_val >= floor and s_val >= floor


def _build_program_name_index(base_dir):
    path = Path(base_dir) / "data" / "race_map.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    programs = data.get("program") or {}
    meta_by_pid = {}
    for meta in (data.get("meta") or {}).values():
        try:
            meta_by_pid[int(meta.get("program_id") or 0)] = meta
        except Exception:
            pass
    idx = {}
    for pid_raw, info in programs.items():
        try:
            pid = int(pid_raw)
        except Exception:
            continue
        name = info.get("name") or ""
        meta = meta_by_pid.get(pid) or {}
        row = dict(info)
        row["program_id"] = pid
        row["turn"] = int(meta.get("turn") or 0)
        idx.setdefault(_canon_race_name(name), []).append(row)
    return idx




def _read_data_json(base_dir, filename, default):
    try:
        path = Path(base_dir) / "data" / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _official_program_core(base_dir):
    rows = _read_data_json(base_dir, "race_planner_core.json", [])
    out = {}
    for row in rows if isinstance(rows, list) else []:
        try:
            out[int(row.get("program_id") or 0)] = row
        except Exception:
            continue
    return out


def _trackblazer_reward_core(base_dir):
    rows = _read_data_json(base_dir, "trackblazer_race_rewards_core.json", [])
    out = {}
    for row in rows if isinstance(rows, list) else []:
        try:
            out[int(row.get("program_id") or 0)] = row
        except Exception:
            continue
    return out


def _first_place_value(rows, key):
    best = 0
    for row in rows or []:
        try:
            if int(row.get("order_min") or 0) <= 1 <= int(row.get("order_max") or 0):
                best = max(best, int(row.get(key) or 0))
        except Exception:
            continue
    return best


def _performance_rates(base_dir):
    data = _read_data_json(base_dir, "race_performance_rates_core.json", {})
    return data if isinstance(data, dict) else {}



def _scenario_turns(base_dir, scenario_id=4):
    rows = _read_data_json(base_dir, "scenario_turns_core.json", [])
    out = {}
    for row in rows if isinstance(rows, list) else []:
        try:
            if int(row.get("scenario_id") or 0) == int(scenario_id):
                out[int(row.get("turn") or 0)] = row
        except Exception:
            continue
    return out


def _scenario_summer_turns(base_dir, scenario_id=4):
    rows = _scenario_turns(base_dir, scenario_id)
    summer = {turn for turn, row in rows.items() if row.get("is_summer")}
    return summer or set(SUMMER_TURNS)


def _official_performance_rate(rates, race, aptitudes):
    """Return a lightweight official-rate multiplier for solver scoring.

    master.mdb rate tables use 10000 as neutral scale for most modifiers. The
    values are used as a soft scorer, never as a hard win predictor.
    """
    if not rates:
        return 1.0
    distance = race.get("distance")
    surface = race.get("surface")
    d_val = _apt_value(aptitudes.get(distance) or aptitudes.get(DIST_KEYS.get(distance, "")), default=7)
    s_val = _apt_value(aptitudes.get(surface) or aptitudes.get(SURF_KEYS.get(surface, "")), default=7)
    dist_row = (rates.get("distance_rate") or {}).get(str(d_val), {})
    ground_row = (rates.get("ground_rate") or {}).get(str(s_val), {})
    try:
        dist_speed = float(dist_row.get("proper_rate_speed") or 10000)
        dist_power = float(dist_row.get("proper_rate_power") or 10000)
        ground = float(ground_row.get("proper_rate") or 10000)
        return max(0.0, ((dist_speed + dist_power) / 2.0 + ground) / 20000.0)
    except Exception:
        return 1.0

def _program_rows(base_dir):
    rows = []
    for matches in _build_program_name_index(base_dir).values():
        for row in matches:
            rows.append({
                "program_id": int(row.get("program_id") or 0),
                "turn": int(row.get("turn") or 0),
                "name": row.get("name") or "",
            })
    return rows


def _candidate_rows(base_dir, aptitudes=None, fan_bonus=0, include_op=False, floor=6, trainee_id="", preset_name=""):
    """Build candidate race rows enriched with live learned context.

    trainee_id/preset_name are optional and keep older call sites compatible.
    When provided, local race-outcome intelligence can prefer profile-specific
    risk over broad program-level risk, allowing the Smart Race Solver to adapt
    to the current trainee/preset instead of relying only on static aptitudes.
    """
    aptitudes = aptitudes or {}
    data = load_or_download(base_dir)
    races = data.get("races") or []
    name_index = _build_program_name_index(base_dir)
    official = _official_program_core(base_dir)
    rewards = _trackblazer_reward_core(base_dir)
    rates = _performance_rates(base_dir)
    # P3: load the learned-intelligence files ONCE per solve and reuse across all
    # candidate rows (previously each row re-read outcomes + auto-config + policy
    # from disk, ~744 reads of each per solve).
    outcomes_data = load_outcomes(base_dir)
    _pol_cfg = load_auto_config(base_dir) if (race_policy_adjustment and load_auto_config) else None
    _pol_data = load_policy_adjustments(base_dir) if (race_policy_adjustment and load_policy_adjustments) else None
    rows = []
    for race in races:
        grade = str(race.get("grade") or "").upper()
        if not include_op and grade in {"OP", "PRE-OP", "PREOP"}:
            continue
        if not _race_ok(race, aptitudes, floor=floor):
            continue
        matches = name_index.get(_canon_race_name(race.get("name"))) or []
        for match in matches:
            program_id = int(match["program_id"])
            meta = official.get(program_id) or {}
            reward = rewards.get(program_id) or {}
            fans = int(race.get("fans") or meta.get("fans") or reward.get("fans_first") or 0)
            coin_reward = _first_place_value(reward.get("coin_rewards") or [], "coin_num")
            win_points = _first_place_value(reward.get("win_point_rewards") or [], "point_num")
            performance_rate = _official_performance_rate(rates, race, aptitudes)
            turn_num = int(match.get("turn") or meta.get("turn") or 0)
            outcome_risk = race_outcome_risk(base_dir, program_id, trainee_id=trainee_id, preset_name=preset_name, _data=outcomes_data)
            ai_policy_hint = race_policy_adjustment(base_dir, program_id, _cfg=_pol_cfg, _policy=_pol_data) if race_policy_adjustment else {"adjustment": 0.0, "confidence": 0.0}
            rows.append({
                "program_id": program_id,
                "turn": turn_num,
                "turnNumber": turn_num,
                "name": race.get("name") or match.get("name") or meta.get("name") or "",
                "nameFormatted": race.get("nameFormatted") or meta.get("name_formatted") or "",
                "classYear": race.get("year") or _row_class_year({"turn": turn_num}),
                "raceTrack": race.get("track") or meta.get("venue") or meta.get("race_track") or "",
                "grade": grade or meta.get("grade") or reward.get("grade") or "",
                "distance": race.get("distance") or meta.get("distance"),
                "distance_m": int(meta.get("distance_m") or meta.get("distance") or 0) if str(meta.get("distance_m") or meta.get("distance") or "").isdigit() else 0,
                "surface": race.get("surface") or meta.get("terrain"),
                "fans": fans,
                "est_fans": int(round(fans * (1 + float(fan_bonus or 0) / 100.0))),
                "aptitude_weight": _aptitude_match_bonus(race, aptitudes) + int(round((performance_rate - 1.0) * 100)),
                "performance_rate": round(performance_rate, 4),
                "coin_reward": coin_reward,
                "win_points": win_points,
                "trackblazer_reward_score": coin_reward + win_points,
                "fan_set_id": meta.get("fan_set_id") or reward.get("fan_set_id"),
                "reward_set_id": meta.get("reward_set_id") or reward.get("reward_set_id"),
                "race_group_ids": reward.get("race_group_ids") or [],
                "local_ids": [program_id],
                "outcome_risk": outcome_risk,
                "outcome_risk_penalty": float(outcome_risk.get("penalty") or 0.0),
                "ai_policy_hint": ai_policy_hint,
            })
    return rows



def _grade_key(grade):
    grade = str(grade or "").upper()
    if grade in {"PREOP", "PRE_OP", "PRE-OP"}:
        return "PRE-OP"
    return grade


def _race_baseline(grade, race_bonus_pct, stat_weight, sp_weight):
    grade = _grade_key(grade)
    baseline_grade = grade if grade in {"OP", "PRE-OP"} else "G2"
    base = GRADE_BASE.get(baseline_grade, {"stat": 0, "sp": 0})
    rb = max(0.0, float(race_bonus_pct or 0)) / 100.0
    return stat_weight * int(base.get("stat", 0) * (1 + rb)) + sp_weight * int(base.get("sp", 0) * (1 + rb))



def _row_distance_m(row):
    try:
        return int(row.get("distance_m") or row.get("distance") or 0)
    except Exception:
        text = str(row.get("distance") or row.get("distanceType") or "").strip().lower()
        if text == "long":
            return 3000
        if text in {"medium", "middle"}:
            return 2000
        if text == "mile":
            return 1600
        if text in {"sprint", "short"}:
            return 1200
        return 0


def _runtime_clocks_enabled(weights):
    support = weights.get("runtimeSupport") if isinstance(weights, dict) else {}
    if not isinstance(support, dict):
        return False
    if "burn_clocks_enabled" in support:
        return bool(support.get("burn_clocks_enabled"))
    if "clocks_enabled" in support:
        return bool(support.get("clocks_enabled"))
    if "allow_clocks" in support:
        return bool(support.get("allow_clocks"))
    return False


def _runtime_support_bonus(row, weights):
    support = weights.get("runtimeSupport") if isinstance(weights, dict) else {}
    if not isinstance(support, dict):
        return 0.0
    grade = _grade_key(row.get("grade"))
    turn = int(row.get("turn") or 0)
    bonus = 0.0
    race_items = float(support.get("race_items") or support.get("raceItemCount") or support.get("hammers") or 0)
    energy_items = float(support.get("energy_items") or support.get("energyItemCount") or 0)
    clocks = float(support.get("clocks") or support.get("clocks_left") or 0) if _runtime_clocks_enabled(weights) else 0.0
    if grade == "G1":
        bonus += min(18.0, race_items * 3.0)
    elif grade in {"G2", "G3"}:
        bonus += min(10.0, race_items * 1.5)
    if 65 <= turn <= 72:
        bonus += min(8.0, energy_items * 0.6 + clocks * 0.8)
    return bonus * float(weights.get("itemRecoverySupportWeight", 1.0) or 1.0)


def _long_distance_risk_penalty(row, weights):
    if not bool(weights.get("enableDistanceStaminaRisk", True)):
        return 0.0
    distance_m = _row_distance_m(row)
    if distance_m < 3000:
        return 0.0
    stats = weights.get("currentStats") if isinstance(weights, dict) else {}
    if not isinstance(stats, dict):
        return 0.0
    stamina = _to_float(stats.get("stamina", stats.get("sta", 0)), 0.0, 0.0, 2000.0)
    floor = max(1.0, float(weights.get("longDistanceStaminaFloor", 550) or 550))
    if stamina >= floor:
        return 0.0
    deficit = (floor - stamina) / floor
    return float(weights.get("longDistanceRiskPenalty", 45.0) or 45.0) * deficit


def _smart_race_score(row, weights=None):
    """Shared race scoring adapted from the Trackblazer Smart Race Solver.

    v5.31 adds log-derived intelligence on top of the Trackblazer objective:
    observed race failure penalties, late-Senior fan-pressure, long-distance
    stamina risk, and item/recovery feasibility support.  These are additive and
    can be tuned or disabled from weights without breaking older presets.
    """
    weights = _solver_weights(weights)
    grade = _grade_key(row.get("grade"))
    base = GRADE_BASE.get(grade, {"stat": 0, "sp": 0, "grade": 0})
    race_value = weights["raceValue"]
    stat_weight = _to_float(weights.get("statWeight", weights.get("stats", 1.0)), 1.0, 0.0, 10.0)
    sp_weight = _to_float(weights.get("spWeight", weights.get("skill_points", 1.0)), 1.0, 0.0, 10.0)
    race_bonus_pct = weights["raceBonusPct"]
    race_cost_pct = weights["raceCostPct"]
    fan_weight = weights["fanWeight"]
    rb = max(0.0, race_bonus_pct) / 100.0
    gross = stat_weight * int(base.get("stat", 0) * (1 + rb)) + sp_weight * int(base.get("sp", 0) * (1 + rb))
    cost = (race_cost_pct / 100.0) * _race_baseline(grade, race_bonus_pct, stat_weight, sp_weight)
    value = (gross - cost) * race_value
    fans = max(0.0, float(row.get("est_fans") or row.get("fans") or 0))
    value += fans * fan_weight
    value += float(row.get("aptitude_weight") or 0) * 0.08
    value += float(row.get("trackblazer_reward_score") or 0) * weights["trackblazerRewardWeight"]
    value += float(base.get("grade", 0)) * _to_float(weights.get("gradeWeight", weights.get("grade", 1.5)), 1.5, 0.0, 20.0)
    target_hits = len(row.get("target_epithet_hits") or [])
    forced_hits = len(row.get("forced_epithet_hits") or [])
    if target_hits:
        value += target_hits * weights["epithetValue"]
    if forced_hits:
        value += forced_hits * weights["forcedEpithetValue"]
    if (target_hits or forced_hits) and str(row.get("grade") or "").upper() == "G1":
        value += weights["hintRewardWeight"] * 0.1

    flags = []
    turn = int(row.get("turn") or 0)
    if bool(weights.get("enableLateSeniorPressure", True)) and 65 <= turn <= 72:
        late_bonus = float(weights.get("lateSeniorRacePressure", 12.0) or 12.0) + fans * float(weights.get("lateSeniorFanPressure", 0.00025) or 0.00025)
        value += late_bonus
        flags.append(f"late_senior_pressure:+{late_bonus:.2f}")

    if bool(weights.get("enableOutcomeRisk", True)):
        risk = row.get("outcome_risk") or {}
        penalty = float(row.get("outcome_risk_penalty") or risk.get("penalty") or 0.0) * float(weights.get("outcomeRiskWeight", 1.0) or 1.0)
        if not _runtime_clocks_enabled(weights):
            clock_penalty = float(risk.get("clock_dependency_penalty") or 0.0) * float(weights.get("clockDependencyRiskWeight", 1.0) or 1.0)
            if clock_penalty > 0:
                penalty += clock_penalty
                flags.append(f"clock_dependency_risk:-{clock_penalty:.2f}")
        if penalty > 0:
            value -= penalty
            flags.append(f"observed_risk:-{penalty:.2f}")

    stamina_penalty = _long_distance_risk_penalty(row, weights)
    if stamina_penalty > 0:
        value -= stamina_penalty
        flags.append(f"long_distance_stamina_risk:-{stamina_penalty:.2f}")

    support_bonus = _runtime_support_bonus(row, weights)
    if support_bonus > 0:
        value += support_bonus
        flags.append(f"item_recovery_support:+{support_bonus:.2f}")

    if bool(weights.get("enableLiveAiPolicy", True)):
        hint = row.get("ai_policy_hint") or {}
        conf = float(hint.get("confidence") or 0.0)
        gate = float(weights.get("liveAiConfidenceThreshold", 0.65) or 0.65)
        if conf >= gate:
            adjustment = float(hint.get("adjustment") or 0.0) * float(weights.get("liveAiAdjustmentWeight", 1.0) or 1.0)
            if not _runtime_clocks_enabled(weights):
                adjustment -= float(hint.get("clock_dependency_penalty") or 0.0) * float(weights.get("liveAiAdjustmentWeight", 1.0) or 1.0)
            if adjustment:
                value += adjustment
                flags.append(f"live_ai_policy:{adjustment:+.2f}@{conf:.2f}")

    if flags:
        existing = list(row.get("score_flags") or [])
        row["score_flags"] = existing + flags
    return value


def _selected_epithet_names(base_dir, names):
    return {str(row.get("name") or "").strip() for row in _selected_epithet_rows(base_dir, names) if str(row.get("name") or "").strip()}


def _required_forced_names(base_dir, forced_epithets):
    names = _selected_epithet_names(base_dir, forced_epithets)
    structured = {str(row.get("name") or "").strip() for row in _selected_structured_epithets(base_dir, forced_epithets)}
    return {name for name in (names | structured) if name}


def _selected_epithet_rows(base_dir, names):
    wanted = {str(name or "").strip().lower() for name in (names or []) if str(name or "").strip()}
    if not wanted:
        return []
    data = load_or_download(base_dir)
    rows = []
    for epithet in data.get("epithets") or []:
        if str(epithet.get("name") or "").strip().lower() in wanted:
            rows.append(epithet)
    return rows


def _race_matches_epithet(row, epithet):
    """Best-effort native matcher for unstructured epithet text.

    The race.daftuyda/gametora epithet cache currently gives condition text,
    not executable matcher bytecode.  This matcher intentionally stays simple:
    race names are exact text hits, and broad text hints such as Dirt/G1/Mile
    bias matching races.  The bonus is advisory, not a hard completion proof.
    """
    cond = str(epithet.get("condition_text") or "").lower()
    if not cond:
        return False
    name = str(row.get("name") or "").lower()
    if name and name in cond:
        return True
    grade = str(row.get("grade") or "").upper()
    distance = str(row.get("distance") or "").lower()
    surface = str(row.get("surface") or "").lower()
    if "dirt" in cond and surface == "dirt":
        if "g1" in cond or "g 1" in cond:
            return grade == "G1"
        return True
    if "turf" in cond and surface == "turf":
        return True
    if "sprint" in cond and distance == "sprint":
        return True
    if "mile" in cond and distance == "mile":
        return True
    if ("medium" in cond or "middle" in cond) and distance in {"medium", "middle"}:
        return True
    if "long" in cond and distance == "long":
        return True
    has_specific_surface_or_distance = any(token in cond for token in ["dirt", "turf", "sprint", "mile", "medium", "middle", "long"])
    if not has_specific_surface_or_distance:
        if "g1" in cond and grade == "G1":
            return True
        if "g2" in cond and grade == "G2":
            return True
        if "g3" in cond and grade == "G3":
            return True
    return False


def _annotate_epithet_hits(base_dir, rows, target_epithets=None, forced_epithets=None):
    # Prefer the structured matcher data when present; fall back to the
    # older free-text Trackblazer cache for dev/test fixtures. These fields are
    # advisory annotations for UI/score explainability. Full completion is
    # evaluated against schedule history in the beam backend below.
    target_rows = _selected_structured_epithets(base_dir, target_epithets) or _selected_epithet_rows(base_dir, target_epithets)
    forced_rows = _selected_structured_epithets(base_dir, forced_epithets) or _selected_epithet_rows(base_dir, forced_epithets)
    if not target_rows and not forced_rows:
        return rows
    out = []
    for row in rows:
        item = dict(row)
        target_hits = [e.get("name") for e in target_rows if _race_may_progress_epithet(item, e)]
        forced_hits = [e.get("name") for e in forced_rows if _race_may_progress_epithet(item, e)]
        if target_hits:
            item["target_epithet_hits"] = sorted(set(target_hits))
        if forced_hits:
            item["forced_epithet_hits"] = sorted(set(forced_hits))
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# SmartRaceSolver-inspired structured epithet helpers (v5.30)
# ---------------------------------------------------------------------------
# The structured epithet database ships matchers such as
# winRace, winAnyOf, winCount, epithetAll). Pre Icarus's older Trackblazer
# cache only had free-text condition strings, so forced epithets could be
# treated as weak per-race bonuses instead of real schedule goals. These
# helpers keep the solver local/offline and evaluate epithets against the
# projected schedule history, mirroring the RaceHistory +
# EpithetTracker flow without pulling engine-specific dependencies into the
# desktop bot.

_DISTANCE_ALIASES = {
    "short": "Sprint",
    "sprint": "Sprint",
    "mile": "Mile",
    "medium": "Medium",
    "middle": "Medium",
    "long": "Long",
}
_SURFACE_ALIASES = {"turf": "Turf", "dirt": "Dirt"}
_GRADE_ORDER = {"PRE-OP": 1, "PREOP": 1, "OP": 2, "G3": 3, "G2": 4, "G1": 5}


def _canon_distance(value):
    return _DISTANCE_ALIASES.get(str(value or "").strip().lower(), str(value or "").strip())


def _canon_surface(value):
    return _SURFACE_ALIASES.get(str(value or "").strip().lower(), str(value or "").strip())


def _normalize_distance_preferences(values):
    out = []
    for value in values or []:
        canon = _canon_distance(value)
        if canon in {"Sprint", "Mile", "Medium", "Long"} and canon not in out:
            out.append(canon)
    return out


def _structured_epithet_data(base_dir):
    path = Path(base_dir) / "data" / STRUCTURED_EPITHETS_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = list(data.values()) if isinstance(data, dict) else data
    return [r for r in rows if isinstance(r, dict)]


def _structured_epithets_by_name(base_dir):
    return {str(row.get("name") or "").strip(): row for row in _structured_epithet_data(base_dir) if str(row.get("name") or "").strip()}


def _selected_structured_epithets(base_dir, names=None):
    by_name = _structured_epithets_by_name(base_dir)
    wanted = {str(n or "").strip().lower() for n in (names or []) if str(n or "").strip()}
    if not wanted:
        return []
    return [row for name, row in by_name.items() if name.lower() in wanted]


def _solver_epithet_pool(base_dir, target_epithets=None, forced_epithets=None):
    """Return epithets evaluated by the scheduler.

    All structured epithets are included so the objective can reward incidental
    completions like the solver does. The selected target/forced lists are
    still surfaced separately in UI annotations and hard feasibility checks.
    """
    rows = _structured_epithet_data(base_dir)
    if rows:
        return rows
    names = list(target_epithets or []) + list(forced_epithets or [])
    return _selected_epithet_rows(base_dir, names)


def _row_class_year(row):
    year = str(row.get("classYear") or row.get("class_year") or "").strip()
    if year:
        return year
    turn = int(row.get("turn") or row.get("turnNumber") or 0)
    if 1 <= turn <= 24:
        return "Junior"
    if 25 <= turn <= 48:
        return "Classic"
    if 49 <= turn <= 72:
        return "Senior"
    return ""


def _row_grade_rank(row):
    return _GRADE_ORDER.get(_grade_key(row.get("grade")), 0)


def _matcher_type(matcher):
    return str((matcher or {}).get("type") or "").strip()


def _race_matches_structured_filter(row, flt):
    flt = flt or {}
    terrain = flt.get("terrain")
    if terrain and _canon_surface(row.get("surface") or row.get("terrain")) != _canon_surface(terrain):
        return False
    grade = flt.get("grade")
    if grade and _grade_key(row.get("grade")) != _grade_key(grade):
        return False
    if flt.get("gradeAtLeastOpen") and _row_grade_rank(row) < _GRADE_ORDER["OP"]:
        return False
    if flt.get("gradedOnly") and _grade_key(row.get("grade")) not in {"G1", "G2", "G3"}:
        return False
    distance_types = {_canon_distance(x) for x in (flt.get("distanceTypes") or [])}
    if distance_types and _canon_distance(row.get("distance") or row.get("distanceType")) not in distance_types:
        return False
    tracks = {str(x or "").strip().lower() for x in (flt.get("raceTracks") or []) if str(x or "").strip()}
    track = str(row.get("raceTrack") or row.get("track") or row.get("venue") or "").strip().lower()
    if tracks and track not in tracks:
        return False
    name_contains = flt.get("nameContains")
    if name_contains and str(name_contains).lower() not in str(row.get("name") or "").lower():
        return False
    if flt.get("nameContainsCountry"):
        countries = ["Saudi Arabia", "Argentina", "American", "New Zealand", "Japan "]
        if not any(token.lower() in str(row.get("name") or "").lower() for token in countries):
            return False
    return True


def _race_may_progress_matcher(row, matcher):
    typ = _matcher_type(matcher)
    name = str(row.get("name") or "")
    klass = _row_class_year(row)
    if typ == "winRace":
        return _name_eq(name, matcher.get("name")) and (not matcher.get("atClass") or str(matcher.get("atClass")).lower() == klass.lower())
    if typ == "winRaceTimes":
        return _name_eq(name, matcher.get("name"))
    if typ in {"winAnyOf", "winAtLeast"}:
        return _name_in(name, matcher.get("names") or []) and (not matcher.get("atClass") or str(matcher.get("atClass")).lower() == klass.lower())
    if typ == "winCount":
        return _race_matches_structured_filter(row, matcher.get("filter") or {})
    return False


def _race_may_progress_epithet(row, epithet):
    matchers = epithet.get("matchers") or []
    if matchers:
        return any(_race_may_progress_matcher(row, m) for m in matchers if isinstance(m, dict))
    return _race_matches_epithet(row, epithet)


def _matcher_completed(matcher, history, completed_epithets):
    typ = _matcher_type(matcher)
    if typ == "winRace":
        wanted = matcher.get("name")
        at_class = matcher.get("atClass")
        return any(_name_eq(row.get("name"), wanted) and (not at_class or str(at_class).lower() == _row_class_year(row).lower()) for row in history)
    if typ == "winRaceTimes":
        wanted = matcher.get("name")
        times = max(1, int(matcher.get("times") or 1))
        return sum(1 for row in history if _name_eq(row.get("name"), wanted)) >= times
    if typ == "winAnyOf":
        names = matcher.get("names") or []
        count = max(1, int(matcher.get("count") or 1))
        at_class = matcher.get("atClass")
        return sum(1 for row in history if _name_in(row.get("name"), names) and (not at_class or str(at_class).lower() == _row_class_year(row).lower())) >= count
    if typ == "winAtLeast":
        names = matcher.get("names") or []
        count = max(1, int(matcher.get("count") or 1))
        return len({_canon_race_name(row.get("name")) for row in history if _name_in(row.get("name"), names)}) >= count
    if typ == "winCount":
        count = max(1, int(matcher.get("count") or 1))
        flt = matcher.get("filter") or {}
        return sum(1 for row in history if _race_matches_structured_filter(row, flt)) >= count
    if typ == "epithetAnyOf":
        return any(name in completed_epithets for name in (matcher.get("names") or []))
    if typ == "epithetAll":
        return all(name in completed_epithets for name in (matcher.get("names") or []))
    return False


def _completed_epithets_for_history(epithets, history, seed_completed=None, dead_epithets=None):
    completed = set(seed_completed or set())
    dead = set(dead_epithets or set())
    changed = True
    while changed:
        changed = False
        for epithet in epithets or []:
            name = str(epithet.get("name") or "").strip()
            if not name or name in completed or name in dead:
                continue
            matchers = epithet.get("matchers") or []
            if matchers:
                ok = all(_matcher_completed(m, history, completed) for m in matchers if isinstance(m, dict))
            else:
                ok = any(_race_matches_epithet(row, epithet) for row in history)
            if ok:
                completed.add(name)
                changed = True
    return completed


def epithet_critical_race_names(base_dir, target_epithets, completed_epithets=None):
    """Return the set of race names whose win would progress an unmet
    target epithet.

    Used by the runtime irregular-training hijack to refuse hijacking a
    planned race that is the only path to a still-chasing target.  Only
    looks at unmet epithets (already-completed ones don't gate further
    hijacks).
    """
    if not target_epithets:
        return set()
    completed = set(completed_epithets or set())
    rows = _selected_structured_epithets(base_dir, target_epithets) or _selected_epithet_rows(base_dir, target_epithets)
    out = set()
    for row in rows:
        name = str(row.get("name") or "").strip()
        if name and name in completed:
            continue
        for matcher in row.get("matchers") or []:
            if not isinstance(matcher, dict):
                continue
            typ = _matcher_type(matcher)
            if typ in ("winRace", "winRaceTimes"):
                wanted = matcher.get("name")
                if wanted:
                    out.add(str(wanted).strip())
            elif typ in ("winAnyOf", "winAtLeast"):
                for name_ in matcher.get("names") or []:
                    out.add(str(name_).strip())
        # Legacy unstructured rows
        for legacy_name in row.get("races") or row.get("winRace") or []:
            if isinstance(legacy_name, str):
                out.add(legacy_name.strip())
    out.discard("")
    return out


def epithet_progress(base_dir, target_epithets, race_history):
    """Per-epithet progress report for the dashboard.

    Returns a list of dicts shaped like:
        [{"name": "Ideal Idol", "status": "in_progress",
          "races_won": ["Yasuda Kinen"],
          "races_needed": ["Mile Championship", "Arima Kinen"]}, ...]

    ``status`` is one of "completed", "in_progress", or "no_data" when the
    epithet couldn't be resolved.  Only target_epithets are reported.
    """
    if not target_epithets:
        return []
    history_names = set()
    for row in race_history or []:
        if isinstance(row, dict) and row.get("won") is not False and int(row.get("rank") or 99) == 1:
            n = str(row.get("name") or "").strip()
            if n:
                history_names.add(n)
    rows = _selected_structured_epithets(base_dir, target_epithets)
    out = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        # Collect race-name requirements from structured matchers
        required = set()
        for matcher in row.get("matchers") or []:
            if not isinstance(matcher, dict):
                continue
            typ = _matcher_type(matcher)
            if typ in ("winRace", "winRaceTimes"):
                wanted = matcher.get("name")
                if wanted:
                    required.add(str(wanted).strip())
            elif typ in ("winAnyOf", "winAtLeast"):
                # For winAnyOf, only count toward "needed" the ones still missing
                for n in matcher.get("names") or []:
                    n = str(n).strip()
                    if n and n not in history_names:
                        required.add(n)
        races_won = sorted(history_names & required) if required else []
        races_needed = sorted(required - history_names)
        if required and not races_needed:
            status = "completed"
        elif races_won:
            status = "in_progress"
        elif required:
            status = "not_started"
        else:
            status = "no_data"
        out.append({
            "name": name,
            "status": status,
            "races_won": races_won,
            "races_needed": races_needed,
        })
    return out



def _won_history_rows(rows):
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("won") is False or (row.get("rank") not in (None, "") and int(row.get("rank") or 99) != 1):
            continue
        out.append(row)
    return out


def _lost_history_rows(rows):
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            rank = int(row.get("rank") or 99)
        except Exception:
            rank = 99
        if rank > 1:
            out.append(row)
    return out


def _dead_epithets_from_failed_history(epithets, failed_rows):
    dead = set()
    for epithet in epithets or []:
        name = str(epithet.get("name") or "").strip()
        if not name:
            continue
        if any(_race_may_progress_epithet(row, epithet) for row in failed_rows or []):
            dead.add(name)
    return dead


def _epithet_contributions_for_row(row, epithets):
    names = []
    for epithet in epithets or []:
        name = str(epithet.get("name") or "").strip()
        if name and _race_may_progress_epithet(row, epithet):
            names.append(name)
    return sorted(set(names))


def _build_epithet_ledger(base_dir, schedule, target_epithets=None, forced_epithets=None, race_history=None):
    selected_names = {str(x or "").strip() for x in list(target_epithets or []) + list(forced_epithets or []) if str(x or "").strip()}
    epithets = _solver_epithet_pool(base_dir, target_epithets, forced_epithets)
    if selected_names:
        epithets = [e for e in epithets if str(e.get("name") or "").strip() in selected_names]
    won_history = _won_history_rows(race_history or [])
    failed_history = _lost_history_rows(race_history or [])
    dead = _dead_epithets_from_failed_history(epithets, failed_history)
    completed_before = _completed_epithets_for_history(epithets, won_history, dead_epithets=dead)
    projected_history = won_history + list(schedule or [])
    completed_after = _completed_epithets_for_history(epithets, projected_history, seed_completed=completed_before, dead_epithets=dead)
    ledger = []
    for epithet in epithets:
        name = str(epithet.get("name") or "").strip()
        if not name:
            continue
        contributing = [int(row.get("program_id") or 0) for row in (schedule or []) if _race_may_progress_epithet(row, epithet)]
        if name in dead and name not in completed_before:
            status = "dead"
        elif name in completed_before:
            status = "completed"
        elif name in completed_after:
            status = "projected"
        elif contributing:
            status = "in_progress"
        else:
            status = "untouched"
        ledger.append({
            "name": name,
            "status": status,
            "forced": name in {str(x or "").strip() for x in forced_epithets or []},
            "target": name in {str(x or "").strip() for x in target_epithets or []},
            "contributing_program_ids": contributing,
        })
    by_name = {row["name"]: row for row in ledger}
    return {"ledger": ledger, "completed": sorted(completed_after), "dead": sorted(dead), "by_name": by_name}


def _decorate_schedule_with_epithets(base_dir, schedule, target_epithets=None, forced_epithets=None, race_history=None):
    ledger = _build_epithet_ledger(base_dir, schedule, target_epithets, forced_epithets, race_history)
    epithets = [row for row in _solver_epithet_pool(base_dir, target_epithets, forced_epithets) if str(row.get("name") or "").strip() in ledger["by_name"]]
    decorated = []
    for row in schedule or []:
        item = dict(row)
        contrib = _epithet_contributions_for_row(item, epithets)
        item["epithet_contributions"] = contrib
        item["target_epithet_hits"] = sorted(set(list(item.get("target_epithet_hits") or []) + [n for n in contrib if ledger["by_name"].get(n, {}).get("target")]))
        item["forced_epithet_hits"] = sorted(set(list(item.get("forced_epithet_hits") or []) + [n for n in contrib if ledger["by_name"].get(n, {}).get("forced")]))
        item["race_type"] = "solver_planned"
        decorated.append(item)
    return decorated, ledger

def _epithet_reward_value(epithet, weights):
    if not epithet:
        return 0.0
    amount = epithet.get("amount")
    kind = str(epithet.get("reward_kind") or "").lower()
    bullets = epithet.get("bullet_points") or epithet.get("bullets") or []
    text = " ".join(str(x or "") for x in bullets + [epithet.get("reward_text") or epithet.get("category") or ""])
    if amount is None:
        m = re.search(r"(\d+)\s+random\s+stats?\s*\+(\d+)", text, re.I)
        if m:
            amount = int(m.group(1)) * int(m.group(2))
            kind = kind or "stat"
        else:
            m = re.search(r"\+(\d+)\s+to\s+(\d+)\s+random\s+stats?", text, re.I)
            if m:
                amount = int(m.group(1)) * int(m.group(2))
                kind = kind or "stat"
            else:
                m = re.search(r"hint\s*\+(\d+)", text, re.I)
                if m:
                    amount = int(m.group(1))
                    kind = kind or "hint"
    if kind == "hint" or "hint" in text.lower():
        return float(weights.get("hintRewardWeight", 8.0) or 8.0) * float(amount or 1) * float(weights.get("epithetValue", 1.0) or 1.0)
    if kind == "stat" or amount:
        return float(amount or 0) * float(weights.get("epithetValue", 1.0) or 1.0)
    return 0.0


def _apply_distance_preferences_to_rows(rows, preferred_distances=None, mode="balanced", weights=None):
    prefs = set(_normalize_distance_preferences(preferred_distances))
    if not prefs:
        return rows
    mode = str(mode or "balanced").lower().strip()
    weights = weights or {}
    bonus = float(weights.get("distancePreferenceBonus", 6.0) or 6.0)
    penalty = float(weights.get("distancePreferencePenalty", 20.0) or 20.0)
    out = []
    for row in rows:
        dist = _canon_distance(row.get("distance") or row.get("distanceType"))
        forced = bool(row.get("forced_epithet_hits"))
        item = dict(row)
        if dist in prefs:
            item["distance_preference"] = "preferred"
            item["score"] = float(item.get("score") or 0) + (bonus if mode in {"balanced", "loose"} else 0.0)
            out.append(item)
        elif mode == "strict" and not forced:
            continue
        else:
            item["distance_preference"] = "off-preference"
            if mode == "balanced" and not forced:
                item["score"] = float(item.get("score") or 0) - penalty
            elif mode == "loose":
                item["score"] = float(item.get("score") or 0) - min(2.0, penalty * 0.1)
            out.append(item)
    return out


def _forced_epithet_constraints(base_dir, forced_epithets, candidates):
    """Linear constraints for forced epithets when MILP can express them.

    Dependency epithets are intentionally rejected here so the exact solver can
    fall back to the history-aware beam backend instead of silently relaxing the
    goal.
    """
    constraints = []
    by_name = _structured_epithets_by_name(base_dir)
    forced = [by_name.get(str(name or "").strip()) for name in (forced_epithets or [])]
    for epithet in [e for e in forced if e]:
        for matcher in epithet.get("matchers") or []:
            typ = _matcher_type(matcher)
            if typ in {"epithetAnyOf", "epithetAll"}:
                raise RuntimeError(f"Forced epithet needs beam dependency tracker: {epithet.get('name')}")
            idxs = [idx for idx, row in enumerate(candidates) if _race_may_progress_matcher(row, matcher)]
            if typ == "winRace":
                need = 1
            elif typ == "winRaceTimes":
                need = max(1, int(matcher.get("times") or 1))
            elif typ == "winAnyOf":
                need = max(1, int(matcher.get("count") or 1))
            elif typ == "winAtLeast":
                need = max(1, int(matcher.get("count") or 1))
            elif typ == "winCount":
                need = max(1, int(matcher.get("count") or 1))
            else:
                continue
            if len(idxs) < need:
                raise RuntimeError(f"Forced epithet is infeasible with current filters: {epithet.get('name')}")
            constraints.append((idxs, need, len(idxs)))
    return constraints


def _opportunistic_epithet_milp_vars(epithet_pool, candidates, won_history, dead_names, forced_names, weights):
    """v1.5 (solver parity): build the opportunistic-epithet reward variables
    for the MILP.

    The MILP gives EVERY achievable (non-dead) epithet a reward variable
    in the objective, tied by linear constraints to the races that complete it.
    That reward flips otherwise-zero G2/G3 races positive and is the reason
    The reference solver schedules ~39 races where Icarus's MILP (which had NO epithet term)
    stays train-heavy at ~24.  Icarus already did this in its beam backend, but
    the beam never runs because the MILP succeeds first -- so the parity logic
    was dead.  This wires it into the active MILP path.

    Returns a list of (reward, matcher_constraints) where matcher_constraints is
    a list of (idxs, need): scheduling at least `need` of candidate indices
    `idxs` (with history wins already deducted) is required for the epithet's
    reward.  An epithet with any dependency matcher (epithetAnyOf/All) or any
    matcher unsatisfiable from the remaining races is skipped entirely -- the
    beam fallback handles dependency epithets.  Forced epithets are excluded
    (they are already pinned by _forced_epithet_constraints).
    """
    out = []
    for ep in epithet_pool or []:
        name = str(ep.get("name") or "").strip()
        if not name or name in dead_names or name in forced_names:
            continue
        reward = _epithet_reward_value(ep, weights)
        if reward <= 0:
            continue
        matchers = ep.get("matchers") or []
        if not matchers:
            continue
        matcher_constraints = []
        feasible = True
        for matcher in matchers:
            typ = _matcher_type(matcher)
            if typ in {"epithetAnyOf", "epithetAll"}:
                feasible = False  # dependency matcher -> beam fallback handles it
                break
            if typ == "winRace":
                need = 1
            elif typ in {"winRaceTimes", "winAnyOf", "winAtLeast", "winCount"}:
                need = max(1, int(matcher.get("times") or matcher.get("count") or 1))
            else:
                continue  # unknown matcher type -> contributes no constraint
            hist = sum(1 for r in (won_history or []) if _race_may_progress_matcher(r, matcher))
            need -= hist
            if need <= 0:
                continue  # already satisfied by prior wins
            idxs = [idx for idx, row in enumerate(candidates) if _race_may_progress_matcher(row, matcher)]
            if len(idxs) < need:
                feasible = False  # cannot complete this matcher from remaining races
                break
            matcher_constraints.append((idxs, need))
        if not feasible or not matcher_constraints:
            continue
        out.append((reward, matcher_constraints))
    return out


def _normalize_manual_locks(manual_locks=None):
    out = {}
    for key, value in (manual_locks or {}).items():
        try:
            turn = int(key)
        except Exception:
            continue
        if value is None:
            out[turn] = "train"
        elif isinstance(value, str) and value.lower() in TRAIN_LOCKS:
            out[turn] = "train"
        else:
            try:
                out[turn] = int(value)
            except Exception:
                out[turn] = str(value)
    return out


def _smart_milp_schedule(
    base_dir,
    aptitudes=None,
    fan_bonus=0,
    max_races_in_row=2,
    include_op=False,
    floor=6,
    weights=None,
    training_blocks=None,
    manual_locks=None,
    target_epithets=None,
    forced_epithets=None,
    preferred_distances=None,
    distance_preference_mode="balanced",
    current_turn=14,
    race_history=None,
    trainee_id="",
    preset_name="",
    timeout=30,
    carry_in_streak=0,
):
    """Optional exact MILP backend using scipy.optimize.milp.

    This mirrors the solver's first-choice backend more closely than the
    beam fallback. Variables are binary race decisions. Constraints enforce:
    - at most one race per turn,
    - manual race locks and Train locks,
    - max consecutive racing streak via sliding-window constraints.

    Epithets can still be layered later as extra variables/constraints. For now,
    this exact backend optimizes the same race reward/cost objective used by the
    beam port and then falls back cleanly if SciPy is missing or infeasible.
    """
    try:
        import numpy as np
        from scipy.optimize import milp, LinearConstraint, Bounds
        from scipy.sparse import lil_matrix
    except Exception as exc:
        raise RuntimeError(f"scipy MILP backend unavailable: {exc}")

    rows = _candidate_rows(base_dir, aptitudes=aptitudes, fan_bonus=fan_bonus, include_op=include_op, floor=floor, trainee_id=trainee_id, preset_name=preset_name)
    rows = _annotate_epithet_hits(base_dir, rows, target_epithets=target_epithets, forced_epithets=forced_epithets)
    manual_locks = _normalize_manual_locks(manual_locks)
    training_blocks = set(int(t) for t in (training_blocks or []) if str(t).isdigit())
    weights = _solver_weights(weights, base_dir)
    max_streak = _to_int(max_races_in_row, 2, 1, 10)
    start_turn = max(1, int(weights.get("currentTurn", current_turn) or current_turn))
    allow_summer = bool(weights.get("allowSummerRacing", False))
    summer_turns = _scenario_summer_turns(base_dir)

    candidates = []
    seen = set()
    for row in rows:
        turn = int(row.get("turn") or 0)
        pid = int(row.get("program_id") or 0)
        if not turn or not pid or turn < start_turn or turn > 72:
            continue
        if turn in training_blocks:
            continue
        lock = manual_locks.get(turn)
        if lock == "train":
            continue
        if turn in summer_turns and not allow_summer and not isinstance(lock, int):
            continue
        if isinstance(lock, int) and pid != lock:
            continue
        key = (turn, pid)
        if key in seen:
            continue
        seen.add(key)
        out = dict(row)
        out["score"] = _smart_race_score(out, weights)
        if turn in summer_turns and allow_summer:
            out["score"] -= float(weights.get("summerPenalty", 5.0) or 5.0)
        candidates.append(out)

    candidates = _apply_distance_preferences_to_rows(
        candidates,
        preferred_distances=preferred_distances,
        mode=distance_preference_mode or weights.get("distancePreferenceMode", "balanced"),
        weights=weights,
    )

    required_forced = _required_forced_names(base_dir, forced_epithets)
    if not candidates:
        if required_forced:
            raise RuntimeError("Forced epithet route is infeasible with current filters: " + ", ".join(sorted(required_forced)))
        return {
            "success": True,
            "solver": "smart-race-solver-milp",
            "backend": "scipy-milp",
            "source": LOCAL_SOLVER_SOURCE,
            "generated_at": int(time.time()),
            "race_count": 0,
            "estimated_fans": 0,
            "objective_score": 0,
            "extra_race_list": [],
            "schedule": [],
            "decisions": {turn: {"type": "train"} for turn in range(start_turn, 73)},
            "projected_epithets": [],
            "notes": ["No eligible races after aptitude/manual-lock filtering."],
        }

    n = len(candidates)
    # v1.5: opportunistic epithet reward variables (solver parity) -- every
    # achievable, non-dead epithet gets a y-variable rewarded in the objective
    # and tied to its qualifying races, flipping otherwise-zero G2/G3 races
    # positive so the schedule reaches the target ~39-race count.  Soft (y may be
    # 0), so they can never make the model infeasible.  Disable via
    # weights.enableOpportunisticEpithets=false.
    # v1.5: DEFAULTS OFF.  Direct schedule simulation showed the MILP already
    # schedules the maximum executable races (~37) via the grade term, so adding
    # epithet rewards does NOT increase the race count at any replan -- it only
    # re-prioritises toward epithet completions at a consistent FAN COST
    # (~390k -> ~332k estimated).  The real 37-planned-vs-28-executed gap is
    # runtime (energy rests / hijacks), not the solver.  Kept as an opt-in for
    # users who specifically want to chase achievable epithets.
    epithet_vars = []
    if weights.get("enableOpportunisticEpithets", False):
        try:
            pool = _solver_epithet_pool(base_dir, target_epithets, forced_epithets)
            dead_names = set(_dead_epithets_from_failed_history(pool, _lost_history_rows(race_history or [])))
            forced_names = _required_forced_names(base_dir, forced_epithets)
            won_history = _won_history_rows(race_history or [])
            epithet_vars = _opportunistic_epithet_milp_vars(pool, candidates, won_history, dead_names, forced_names, weights)
        except Exception:
            epithet_vars = []
    m = len(epithet_vars)
    total_vars = n + m
    # scipy.optimize.milp minimizes, so negate scores to maximize.
    c = np.array(
        [-float(row.get("score") or 0) for row in candidates]
        + [-float(reward) for (reward, _cons) in epithet_vars],
        dtype=float,
    )
    integrality = np.ones(total_vars, dtype=int)
    bounds = Bounds(np.zeros(total_vars), np.ones(total_vars))

    rows_by_turn = {}
    for idx, row in enumerate(candidates):
        rows_by_turn.setdefault(int(row["turn"]), []).append(idx)

    constraints = []
    lbs = []
    ubs = []

    # At most one race per turn.
    for turn, idxs in rows_by_turn.items():
        constraints.append(idxs)
        lbs.append(0)
        ubs.append(1)

    # Hard race locks. If a lock exists and the candidate survives filters,
    # force exactly one matching race on that turn.
    for turn, lock in manual_locks.items():
        if turn < start_turn or turn > 72:
            continue
        if lock == "train":
            idxs = rows_by_turn.get(turn, [])
            if idxs:
                constraints.append(idxs)
                lbs.append(0)
                ubs.append(0)
        elif isinstance(lock, int):
            idxs = [i for i in rows_by_turn.get(turn, []) if int(candidates[i]["program_id"]) == lock]
            if idxs:
                constraints.append(idxs)
                lbs.append(1)
                ubs.append(1)

    # Forced epithets are hard constraints. When the structured
    # matcher can be expressed linearly, encode it exactly; dependency-based
    # epithets deliberately raise so the history-aware beam fallback handles
    # them instead of silently relaxing the goal.
    for idxs, lower, upper in _forced_epithet_constraints(base_dir, forced_epithets, candidates):
        constraints.append(idxs)
        lbs.append(lower)
        ubs.append(upper)

    # Max consecutive race streak. For every window of length max_streak+1,
    # allow at most max_streak races. This is a standard linear encoding.
    window = max_streak + 1
    for turn in range(start_turn, 73 - window + 2):
        idxs = []
        for t in range(turn, turn + window):
            idxs.extend(rows_by_turn.get(t, []))
        if idxs:
            constraints.append(idxs)
            lbs.append(0)
            ubs.append(max_streak)

    # v6.7.22: account for races already run immediately before start_turn
    # (carry-in). With a carry-in of k, only (max_streak - k) more consecutive
    # races may run before a break, so cap the first (max_streak - k + 1)
    # candidate turns at (max_streak - k). When k >= max_streak the streak is
    # already maxed, so start_turn itself must be a non-race.
    if carry_in_streak and carry_in_streak > 0:
        allowance = max(0, max_streak - int(carry_in_streak))
        span = allowance + 1
        idxs = []
        for t in range(start_turn, min(73, start_turn + span)):
            idxs.extend(rows_by_turn.get(t, []))
        if idxs:
            constraints.append(idxs)
            lbs.append(0)
            ubs.append(allowance)

    # v1.5: epithet linking rows -- sum(qualifying race vars) - need*y >= 0, so a
    # reward y can be 1 only when at least `need` of its races are scheduled.
    epithet_rows = []
    for j, (reward, cons) in enumerate(epithet_vars):
        for (idxs, need) in cons:
            epithet_rows.append((idxs, n + j, need))

    mat = lil_matrix((len(constraints) + len(epithet_rows), total_vars), dtype=float)
    for r_idx, idxs in enumerate(constraints):
        for c_idx in idxs:
            mat[r_idx, c_idx] = 1.0
    ep_lbs = []
    ep_ubs = []
    base_r = len(constraints)
    for k, (idxs, ycol, need) in enumerate(epithet_rows):
        r_idx = base_r + k
        for c_idx in idxs:
            mat[r_idx, c_idx] = 1.0
        mat[r_idx, ycol] = -float(need)
        ep_lbs.append(0.0)
        ep_ubs.append(np.inf)

    linear = LinearConstraint(
        mat.tocsr(),
        np.array(lbs + ep_lbs, dtype=float),
        np.array(ubs + ep_ubs, dtype=float),
    )
    options = {"time_limit": max(1.0, float(timeout or 30)), "disp": False}
    result = milp(c=c, integrality=integrality, bounds=bounds, constraints=linear, options=options)

    if not result.success or result.x is None:
        raise RuntimeError(f"scipy MILP infeasible or failed: {getattr(result, 'message', 'unknown error')}")

    picked = []
    for idx in range(n):  # first n vars are races; the trailing m are epithet y-vars
        if result.x[idx] >= 0.5:
            out = dict(candidates[idx])
            out["score"] = round(float(out.get("score") or 0), 3)
            picked.append(out)
    picked.sort(key=lambda row: int(row.get("turn") or 0))
    epithets = _solver_epithet_pool(base_dir, target_epithets, forced_epithets)
    history_won = _won_history_rows(race_history or [])
    projected_epithets = sorted(_completed_epithets_for_history(epithets, history_won + picked))
    picked, epithet_ledger = _decorate_schedule_with_epithets(base_dir, picked, target_epithets, forced_epithets, race_history)
    decisions = {turn: {"type": "train"} for turn in range(start_turn, 73)}
    for row in picked:
        decisions[int(row.get("turn") or 0)] = {
            "type": "race",
            "program_id": int(row.get("program_id") or 0),
            "raceKey": row.get("name") or "",
        }

    return {
        "success": True,
        "solver": "smart-race-solver-milp",
        "backend": "scipy-milp",
        "source": LOCAL_SOLVER_SOURCE,
        "generated_at": int(time.time()),
        "race_count": len(picked),
        "estimated_fans": sum(int(r.get("est_fans") or 0) for r in picked),
        "objective_score": round(float(-result.fun), 3) if result.fun is not None else 0,
        "extra_race_list": [int(r["program_id"]) for r in picked],
        "schedule": picked,
        "decisions": decisions,
        "projected_epithets": projected_epithets,
        "epithet_ledger": epithet_ledger.get("ledger", []),
        "dead_epithets": epithet_ledger.get("dead", []),
        "race_type_counts": {"solver_planned": len(picked)},
        "distance_preference_mode": distance_preference_mode or weights.get("distancePreferenceMode", "balanced"),
        "preferred_distances": _normalize_distance_preferences(preferred_distances),
        "notes": [
            "Exact scipy MILP backend selected.",
            "Beam solver remains fallback if scipy is unavailable or the model is infeasible.",
        ],
    }


def _smart_beam_schedule(
    base_dir,
    aptitudes=None,
    fan_bonus=0,
    max_races_in_row=2,
    include_op=False,
    floor=6,
    weights=None,
    training_blocks=None,
    manual_locks=None,
    target_epithets=None,
    forced_epithets=None,
    preferred_distances=None,
    distance_preference_mode="balanced",
    beam_width=32,
    current_turn=14,
    race_history=None,
    trainee_id="",
    preset_name="",
    carry_in_streak=0,
):
    """Dependency-free desktop port of the heuristic backend.

    The implementation tries MILP first and then falls back to beam
    search. Pre Icarus keeps this self-contained and dependency-free by using
    the beam backend directly. It plans the full 72-turn race-vs-train space,
    honors manual locks, applies consecutive and summer penalties, and scores
    candidate races with trainee aptitudes.
    """
    rows = _candidate_rows(base_dir, aptitudes=aptitudes, fan_bonus=fan_bonus, include_op=include_op, floor=floor, trainee_id=trainee_id, preset_name=preset_name)
    rows = _annotate_epithet_hits(base_dir, rows, target_epithets=target_epithets, forced_epithets=forced_epithets)
    manual_locks = _normalize_manual_locks(manual_locks)
    training_blocks = set(int(t) for t in (training_blocks or []) if str(t).isdigit())
    weights = _solver_weights(weights, base_dir)
    max_streak = _to_int(max_races_in_row, 2, 1, 10)
    beam_width = _to_int(beam_width, 32, 4, 256)
    required_forced = _required_forced_names(base_dir, forced_epithets)
    scored_rows = []
    for row in rows:
        turn = int(row.get("turn") or 0)
        if turn:
            item = dict(row)
            item["score"] = _smart_race_score(item, weights)
            scored_rows.append(item)
    scored_rows = _apply_distance_preferences_to_rows(
        scored_rows,
        preferred_distances=preferred_distances,
        mode=distance_preference_mode or weights.get("distancePreferenceMode", "balanced"),
        weights=weights,
    )
    by_turn = {}
    for row in scored_rows:
        by_turn.setdefault(int(row.get("turn") or 0), []).append(row)
    for turn in by_turn:
        by_turn[turn].sort(key=lambda r: (r["score"], r.get("est_fans", 0), r.get("aptitude_weight", 0)), reverse=True)

    epithets = _solver_epithet_pool(base_dir, target_epithets, forced_epithets)
    epithet_by_name = {str(e.get("name") or ""): e for e in epithets}
    start_turn = max(1, int(weights.get("currentTurn", current_turn) or current_turn))
    history_won = _won_history_rows(race_history or [])
    history_lost = _lost_history_rows(race_history or [])
    dead_epithets = _dead_epithets_from_failed_history(epithets, history_lost)
    completed_seed = _completed_epithets_for_history(epithets, history_won, dead_epithets=dead_epithets)
    states = [{
        "score": 0.0,
        "streak": int(max(0, carry_in_streak or 0)),
        "selected": [],
        "won": {int(r.get("program_id") or 0) for r in history_won if int(r.get("program_id") or 0)},
        "completed": set(completed_seed),
        "decisions": {},
    }]
    consecutive_penalty = float(weights.get("consecutiveRacePenalty", 3.0) or 3.0)
    summer_penalty = float(weights.get("summerPenalty", 5.0) or 5.0)
    allow_summer = bool(weights.get("allowSummerRacing", False))
    summer_turns = _scenario_summer_turns(base_dir)
    train_bias = _to_float(weights.get("trainBias", weights.get("train_bias", 0.03)), 0.03, 0.0, 5.0)
    candidate_cap = _to_int(weights.get("maxCandidatesPerTurn", 8), 8, 1, 40)

    for turn in range(start_turn, 73):
        lock = manual_locks.get(turn)
        force_train = turn in training_blocks or lock == "train"
        options = []
        if not force_train:
            turn_rows = by_turn.get(turn, [])
            if turn in summer_turns and not allow_summer and not isinstance(lock, int):
                turn_rows = []
            if isinstance(lock, int):
                options = [r for r in turn_rows if int(r.get("program_id") or 0) == lock]
            else:
                options = turn_rows[:candidate_cap]
        # Manual race locks are hard locks: if the locked race exists, do not
        # let Train/Rest compete with it and do not discard it for streak.
        hard_race_lock = isinstance(lock, int) and bool(options)
        options_with_train = options if hard_race_lock else options + [None]
        next_states = []
        for state in states:
            for race in options_with_train:
                if race and race.get("program_id") in state["won"]:
                    continue
                next_streak = state["streak"] + 1 if race else 0
                if race and next_streak > max_streak and not hard_race_lock:
                    continue
                add_score = 0.0
                selected = state["selected"]
                won = state["won"]
                completed = state.get("completed", set())
                decisions = state["decisions"]
                if race:
                    add_score = float(race.get("score") or 0)
                    if next_streak >= 3 and turn not in LATE_DEC_TURNS:
                        add_score -= consecutive_penalty * (next_streak - 2)
                    if turn in summer_turns and allow_summer:
                        add_score -= summer_penalty
                    selected = selected + [race]
                    won = set(won)
                    won.add(race.get("program_id"))
                    new_completed = _completed_epithets_for_history(epithets, history_won + selected, seed_completed=completed, dead_epithets=dead_epithets)
                    newly_completed = new_completed - set(completed)
                    add_score += sum(_epithet_reward_value(epithet_by_name.get(name), weights) for name in newly_completed)
                    completed = new_completed
                    decisions = dict(decisions)
                    decisions[turn] = {"type": "race", "program_id": race.get("program_id"), "raceKey": race.get("name")}
                else:
                    add_score = train_bias
                    decisions = dict(decisions)
                    decisions[turn] = {"type": "train"}
                next_states.append({
                    "score": state["score"] + add_score,
                    "streak": next_streak,
                    "selected": selected,
                    "won": won,
                    "completed": completed,
                    "decisions": decisions,
                })
        if not next_states:
            next_states = states
        next_states.sort(key=lambda s: s["score"], reverse=True)
        states = next_states[:beam_width]

    if required_forced:
        complete_states = [st for st in states if required_forced.issubset(set(st.get("completed") or set()))]
        if not complete_states:
            missing = sorted(required_forced)
            raise RuntimeError("Forced epithet route is infeasible with current filters: " + ", ".join(missing))
        states = complete_states
    best = max(states, key=lambda s: s["score"]) if states else {"score": 0, "selected": [], "decisions": {}}
    schedule = []
    for row in best["selected"]:
        out = dict(row)
        out["score"] = round(float(out.get("score") or 0), 3)
        schedule.append(out)
    schedule, epithet_ledger = _decorate_schedule_with_epithets(base_dir, schedule, target_epithets, forced_epithets, race_history)
    notes = [
        "Self-contained SweepyCL port of the Trackblazer SmartRaceSolver beam backend.",
        "Manual locks and Train locks are honored.",
        "RaceHistory + EpithetTracker-style completion scoring is active.",
    ]
    target_count = int(weights.get("targetOptionalRaceCount") or 0)
    if target_count and len(schedule) < max(0, target_count - 4):
        notes.append(f"Race density below target ({len(schedule)}/{target_count}); check aptitude, locks, failed-race risk, or distance mode.")
    if epithet_ledger.get("dead"):
        notes.append("Some epithet branches are marked dead by failed historical race results: " + ", ".join(epithet_ledger.get("dead")[:6]))
    return {
        "success": True,
        "solver": "smart-race-solver-beam",
        "backend": "python-beam-port",
        "source": LOCAL_SOLVER_SOURCE,
        "generated_at": int(time.time()),
        "race_count": len(schedule),
        "estimated_fans": sum(int(r.get("est_fans") or 0) for r in schedule),
        "objective_score": round(float(best.get("score") or 0), 3),
        "extra_race_list": [int(r["program_id"]) for r in schedule],
        "schedule": schedule,
        "decisions": best.get("decisions", {}),
        "projected_epithets": sorted(best.get("completed") or set()),
        "epithet_ledger": epithet_ledger.get("ledger", []),
        "dead_epithets": epithet_ledger.get("dead", []),
        "race_type_counts": {"solver_planned": len(schedule)},
        "distance_preference_mode": distance_preference_mode or weights.get("distancePreferenceMode", "balanced"),
        "preferred_distances": _normalize_distance_preferences(preferred_distances),
        "notes": notes,
    }


def _greedy_schedule(base_dir, aptitudes=None, fan_bonus=0, max_races_in_row=2, include_op=False, floor=6, target_epithets=None, forced_epithets=None, weights=None, preferred_distances=None, distance_preference_mode="balanced", trainee_id="", preset_name=""):

    weights = _solver_weights(weights, base_dir)
    rows = _candidate_rows(base_dir, aptitudes=aptitudes, fan_bonus=fan_bonus, include_op=include_op, floor=floor, trainee_id=trainee_id, preset_name=preset_name)
    rows = _annotate_epithet_hits(base_dir, rows, target_epithets=target_epithets, forced_epithets=forced_epithets)
    scored = []
    for row in rows:
        item = dict(row)
        item["score"] = _smart_race_score(item, weights)
        scored.append(item)
    rows = _apply_distance_preferences_to_rows(scored, preferred_distances=preferred_distances, mode=distance_preference_mode, weights=weights)
    by_turn = {}
    for row in rows:
        if row["turn"]:
            by_turn.setdefault(row["turn"], []).append(row)
    selected = []
    streak = 0
    last_turn = None
    allow_summer = bool(weights.get("allowSummerRacing", False))
    summer_turns = _scenario_summer_turns(base_dir)
    for turn in sorted(by_turn):
        if turn in summer_turns and not allow_summer:
            continue
        options = sorted(by_turn[turn], key=lambda r: (r["est_fans"], r.get("aptitude_weight", 0), r["fans"], r["grade"] == "G1"), reverse=True)
        if last_turn is not None and turn == last_turn + 1:
            next_streak = streak + 1
        else:
            next_streak = 1
        if max_races_in_row and next_streak > int(max_races_in_row):
            streak = 0
            last_turn = turn
            continue
        selected.append(options[0])
        streak = next_streak
        last_turn = turn
    return {
        "success": True,
        "solver": "python-greedy",
        "source": LOCAL_SOLVER_SOURCE,
        "generated_at": int(time.time()),
        "race_count": len(selected),
        "estimated_fans": sum(r["est_fans"] for r in selected),
        "extra_race_list": [r["program_id"] for r in selected],
        "schedule": selected,
    }



def epithet_catalog(base_dir):
    """Return the best local epithet catalog for UI pickers.

    The structured file has executable matchers, so it is preferred.
    The old Trackblazer cache is retained as a fallback for older checkouts.
    """
    rows = _structured_epithet_data(base_dir)
    if rows:
        out = []
        for row in rows:
            item = dict(row)
            bullets = item.get("bullet_points") or []
            item.setdefault("condition_text", " ".join(str(x) for x in bullets[:-1]) if bullets else "")
            item.setdefault("reward_text", str(bullets[-1]) if bullets else "")
            item.setdefault("category", item.get("reward_text") or "")
            out.append(item)
        return out
    return (load_or_download(base_dir).get("epithets") or [])

def solver_status(base_dir):
    """Return Smart Race Solver backend status for the diagnostics UI.

    The default Smart solver tries the SciPy MILP backend first and falls back
    to the dependency-free Beam backend. Older Node bridge fields are retained
    for compatibility with existing UI/tests, but the active backend fields are
    the authoritative diagnostics signal.
    """
    data = load_cached(base_dir)
    milp_available = _scipy_milp_available()
    active_backend = "milp" if milp_available else "beam"
    return {
        "success": True,
        "active_backend": active_backend,
        "active_backend_label": "MILP" if active_backend == "milp" else "Beam",
        "milp_available": milp_available,
        "beam_available": True,
        "backend_detail": "SciPy MILP active; Beam fallback ready" if milp_available else "Beam active; SciPy MILP unavailable",
        "cached_data": {name: len(value) if hasattr(value, "__len__") else 0 for name, value in data.items()},
        "source": LOCAL_SOLVER_SOURCE,
    }


def solve_with_node(base_dir, aptitudes=None, fan_bonus=0, max_races_in_row=2, include_op=False, floor=6, weights=None, training_blocks=None, manual_locks=None, target_epithets=None, forced_epithets=None, timeout=30):
    """Run the dependency-free Node bridge. Raises RuntimeError if unavailable or infeasible."""
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js was not found on PATH")
    script = Path(base_dir) / "tools" / "trackblazer_solver.js"
    if not script.exists():
        raise RuntimeError(f"Trackblazer solver bridge missing: {script}")
    data = load_or_download(base_dir)
    payload = {
        "races": data.get("races") or [],
        "epithets": data.get("epithets") or [],
        "programs": _program_rows(base_dir),
        "aptitudes": aptitudes or {},
        "options": {
            "fan_bonus": fan_bonus,
            "max_races_in_row": max_races_in_row,
            "include_op": include_op,
            "min_aptitude_floor": floor,
            "weights": weights or {},
            "training_blocks": training_blocks or [],
            "manual_locks": manual_locks or {},
            "target_epithets": target_epithets or [],
            "forced_epithets": forced_epithets or [],
        },
    }
    proc = subprocess.run(
        [node, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(base_dir),
        timeout=timeout,
    )
    if proc.returncode != 0 and not proc.stdout:
        raise RuntimeError((proc.stderr or "Node solver failed").strip())
    try:
        result = json.loads(proc.stdout)
    except Exception as exc:
        raise RuntimeError(f"Node solver returned non-JSON output: {exc}; stderr={proc.stderr[:500]}")
    if not result.get("success"):
        raise RuntimeError(result.get("detail") or "Node solver returned infeasible schedule")
    result.setdefault("source", RAW_BASE)
    result.setdefault("fallback_used", False)
    return result


def _carry_in_race_streak(race_history, start_turn):
    """Count consecutive race turns ending immediately before ``start_turn``.

    v6.7.22: a forward-only re-solve starts its streak counter at 0, so races
    already run just before the re-solve are not counted and consecutive races
    can pile up past max_races_in_row. This returns how many races run on the
    turns directly preceding ``start_turn`` (no gap), so the solver can seed
    the streak and keep the limit correct across the re-solve boundary.
    """
    race_turns = set()
    for row in race_history or []:
        if not isinstance(row, dict):
            continue
        try:
            t = int(row.get("turn") or row.get("turnNumber") or 0)
        except (TypeError, ValueError):
            continue
        if t:
            race_turns.add(t)
    streak = 0
    t = int(start_turn or 0) - 1
    while t >= 1 and t in race_turns:
        streak += 1
        t -= 1
    return streak


def make_schedule(
    base_dir,
    aptitudes=None,
    fan_bonus=0,
    max_races_in_row=2,
    include_op=False,
    floor=6,
    solver="auto",
    weights=None,
    training_blocks=None,
    manual_locks=None,
    target_epithets=None,
    forced_epithets=None,
    preferred_distances=None,
    distance_preference_mode="balanced",
    timeout=30,
    race_history=None,
    current_turn=14,
    trainee_id="",
    preset_name="",
    carry_in_streak=None,
):
    """Create a bot-ready race list from Trackblazer static data.

    solver='auto'/'smart' tries the SciPy MILP backend first, then falls back
    to the dependency-free Beam backend. solver='beam' forces Beam, solver='node'
    requires the legacy Node bridge, and solver='greedy' skips smart planning.
    """
    solver = (solver or "smart").lower()
    weights = _solver_weights(weights, base_dir)
    fan_bonus = _to_float(fan_bonus, 0.0, 0.0, 300.0)
    max_races_in_row = _to_int(max_races_in_row, 2, 1, 10)
    floor = _to_int(floor, 6, 1, 8)
    # v6.7.22: count the races run on the turns immediately before this
    # re-solve's start, so the streak constraint spans the re-solve boundary.
    # Without it a forward-only re-solve resets the streak to 0 each turn and
    # consecutive races pile up far past max_races_in_row (the 12-in-a-row bug).
    if carry_in_streak is None:
        _start_turn = max(1, int((weights or {}).get("currentTurn", current_turn) or current_turn))
        carry_in_streak = _carry_in_race_streak(race_history, _start_turn)
    carry_in_streak = max(0, int(carry_in_streak or 0))
    if solver in {"smart", "auto", "milp", "smart-race-solver", "smart-milp"}:
        try:
            return _smart_milp_schedule(
                base_dir,
                aptitudes=aptitudes,
                fan_bonus=fan_bonus,
                max_races_in_row=max_races_in_row,
                include_op=include_op,
                floor=floor,
                weights=weights,
                training_blocks=training_blocks,
                manual_locks=manual_locks,
                target_epithets=target_epithets,
                forced_epithets=forced_epithets,
                preferred_distances=preferred_distances,
                distance_preference_mode=distance_preference_mode,
                current_turn=current_turn,
                race_history=race_history,
                trainee_id=trainee_id,
                preset_name=preset_name,
                timeout=timeout,
                carry_in_streak=carry_in_streak,
            )
        except Exception as exc:
            fallback_log = _record_solver_fallback(base_dir, exc)
            fallback = _smart_beam_schedule(
                base_dir,
                aptitudes=aptitudes,
                fan_bonus=fan_bonus,
                max_races_in_row=max_races_in_row,
                include_op=include_op,
                floor=floor,
                weights=weights,
                training_blocks=training_blocks,
                manual_locks=manual_locks,
                target_epithets=target_epithets,
                forced_epithets=forced_epithets,
                preferred_distances=preferred_distances,
                distance_preference_mode=distance_preference_mode,
                beam_width=int((weights or {}).get("beamWidth", 32) or 32),
                current_turn=current_turn,
                race_history=race_history,
                trainee_id=trainee_id,
                preset_name=preset_name,
                carry_in_streak=carry_in_streak,
            )
            trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            fallback["fallback_used"] = True
            fallback["fallback_reason"] = str(exc)
            fallback["fallback_exception_type"] = type(exc).__name__
            fallback["fallback_traceback_tail"] = trace[-4000:]
            if fallback_log:
                fallback["fallback_log"] = fallback_log
            fallback["solver"] = "smart-race-solver-beam-fallback"
            return fallback
    if solver in {"beam", "smart-beam"}:
        return _smart_beam_schedule(
            base_dir,
            aptitudes=aptitudes,
            fan_bonus=fan_bonus,
            max_races_in_row=max_races_in_row,
            include_op=include_op,
            floor=floor,
            weights=weights,
            training_blocks=training_blocks,
            manual_locks=manual_locks,
            target_epithets=target_epithets,
            forced_epithets=forced_epithets,
            preferred_distances=preferred_distances,
            distance_preference_mode=distance_preference_mode,
            beam_width=int((weights or {}).get("beamWidth", 32) or 32),
            current_turn=current_turn,
            race_history=race_history,
            trainee_id=trainee_id,
            preset_name=preset_name,
            carry_in_streak=carry_in_streak,
        )
    if solver in {"node", "node-dp"}:
        return solve_with_node(
            base_dir,
            aptitudes=aptitudes,
            fan_bonus=fan_bonus,
            max_races_in_row=max_races_in_row,
            include_op=include_op,
            floor=floor,
            weights=weights,
            training_blocks=training_blocks,
            manual_locks=manual_locks,
            target_epithets=target_epithets,
            forced_epithets=forced_epithets,
            timeout=timeout,
        )
    return _greedy_schedule(
        base_dir,
        aptitudes=aptitudes,
        fan_bonus=fan_bonus,
        max_races_in_row=max_races_in_row,
        include_op=include_op,
        floor=floor,
        target_epithets=target_epithets,
        forced_epithets=forced_epithets,
        weights=weights,
        preferred_distances=preferred_distances,
        distance_preference_mode=distance_preference_mode,
        trainee_id=trainee_id,
        preset_name=preset_name,
    )
