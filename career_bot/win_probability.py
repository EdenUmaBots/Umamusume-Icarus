#!/usr/bin/env python3
"""Opponent-aware race win-probability model (Phase 1, read-only).

Estimates P(win) / P(top-3) for a single-mode race from the game's own
master.mdb-derived data, NOT from heuristics:

  * single_mode_npc_core.json  -- per-opponent stat blocks + aptitude grades
  * rival_races_core.json      -- which named NPCs appear at a given turn/race
  * race_performance_rates_core.json -- the official distance / ground /
    running-style / motivation multiplier tables (scale = 10000 == 1.0x)

The core is pure functions (no I/O) so the math is unit-testable against a
hand-checked field.  `load_model()` is a thin loader that reads the three data
files and returns a cached `WinProbModel` you can query.

READ-ONLY.  Nothing here changes how the bot plays.  Phase 1 only *computes and
reports* a probability so we can validate its calibration against logged
finishes (tools/race_winnability_report.py) before any Phase-2 decisioning is
wired in behind a default-off flag.

Strength model (mirrors the engine's existing rate convention in
career_bot/runner.py:_official_performance_hint and trackblazer.py:
_official_performance_rate -- speed & power scale by the distance table, the
whole score scales by ground / running-style / motivation):

    spd_eff = speed * distance_rate[d].speed/scale
    pwr_eff = power * distance_rate[d].power/scale
    base    = spd_eff + 0.6*pwr_eff + w_sta*stamina + 0.15*guts + 0.15*wit
    strength = base * (ground_rate[s]/scale) * (style_rate[r]/scale)
                    * (motivation_rate[mood]/scale)

w_sta is the distance stamina weight (sprint .30, mile .50, medium .70,
long 1.00), matching tools/race_winnability_report.py:_dist_bucket.

Win probability (independence approximation): for each opponent i,
    q_i = logistic((S_i - S_t) / k)          # P(opponent i finishes ahead)
    P(win)   = product_i (1 - q_i)
    P(top-3) = P(at most 2 opponents ahead)  # Poisson-binomial over {q_i}
    E[rank]  = 1 + sum_i q_i

`k` (DEFAULT_K) is the logistic scale.  It is PRELIMINARY -- the backtest tool
fits the value that minimises Brier score on real logged races and reports it;
do not treat the default as calibrated.
"""

import json
import math
import os

# Aptitude grade letter <-> integer (8 = S best ... 1 = G worst).  master.mdb
# stores integers; single_mode_npc_core.json stores the letters.
LETTER_TO_GRADE = {"S": 8, "A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1}
GRADE_TO_LETTER = {v: k for k, v in LETTER_TO_GRADE.items()}
DEFAULT_GRADE = 7          # "A" -- neutral baseline (rate 10000 == 1.0x)
DEFAULT_SCALE = 10000.0

# Preliminary logistic scale (see module docstring).  Fitted by the backtest.
DEFAULT_K = 150.0

# Distance category -> (npc aptitude key, stamina weight).
#   <=1400 sprint, <=1800 mile, <=2400 medium, else long.
def distance_bucket(distance_m):
    m = int(distance_m or 0)
    if m and m <= 1400:
        return "short", 0.30
    if m and m <= 1800:
        return "mile", 0.50
    if m and m <= 2400:
        return "medium", 0.70
    return "long", 1.00


def grade_value(value, default=DEFAULT_GRADE):
    """Normalise an aptitude grade to an int 1..8.

    Accepts a letter ('S'..'G', any case), an int (0..8), or a numeric string
    ('7'); unknown/empty -> default.  Grade 0 is treated as G (1).
    """
    if value is None or value == "":
        return int(default)
    if isinstance(value, str):
        v = value.strip().upper()
        if v in LETTER_TO_GRADE:
            return LETTER_TO_GRADE[v]
        try:
            iv = int(v)
        except ValueError:
            return int(default)
    else:
        try:
            iv = int(value)
        except (TypeError, ValueError):
            return int(default)
    if iv <= 0:
        return 1               # grade 0 is treated as G in the rate tables
    return min(8, iv)


def _stat(stats, *keys):
    for k in keys:
        v = (stats or {}).get(k)
        if v is not None:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if math.isfinite(fv):      # reject NaN/inf so probabilities stay in [0,1]
                return fv
    return 0.0


def _style_specified(style_grade):
    """True only for a concrete aptitude grade; None/0/''/'0' mean auto/unknown.

    Logged rows store running_style_aptitude=0 for auto running style (the common
    default), which must score as neutral (1.0x), NOT as grade G.
    """
    if style_grade is None:
        return False
    if isinstance(style_grade, str):
        return style_grade.strip() not in ("", "0")
    try:
        return int(style_grade) > 0
    except (TypeError, ValueError):
        return False


def _rate(rates, table, grade, col="proper_rate", default=DEFAULT_SCALE):
    """Look up a multiplier value (already raw, /scale applied by caller)."""
    try:
        row = (rates.get(table) or {}).get(str(int(grade)), {})
        val = row.get(col)
        return float(val) if val is not None else float(default)  # honour a real 0
    except (TypeError, ValueError, AttributeError):
        return float(default)


def _scale(rates):
    try:
        s = float((rates or {}).get("scale") or DEFAULT_SCALE)
        return s or DEFAULT_SCALE
    except (TypeError, ValueError):
        return DEFAULT_SCALE


def runner_strength(stats, *, distance_m, distance_grade, surface_grade,
                    style_grade=None, motivation=3, rates=None):
    """Field-strength scalar for one runner in a specific race.

    stats: dict with speed/stamina/power/guts/wit (wiz/pow tolerated).
    *_grade: aptitude grade as int 0..8 or letter 'S'..'G'.
    style_grade None -> running-style multiplier omitted (1.0x).
    """
    rates = rates or {}
    scale = _scale(rates)
    d = grade_value(distance_grade)
    s = grade_value(surface_grade)
    spd = _stat(stats, "speed")
    sta = _stat(stats, "stamina")
    pwr = _stat(stats, "power", "pow")
    gut = _stat(stats, "guts")
    wit = _stat(stats, "wit", "wiz")
    _, w_sta = distance_bucket(distance_m)

    spd_mult = _rate(rates, "distance_rate", d, "proper_rate_speed") / scale
    pwr_mult = _rate(rates, "distance_rate", d, "proper_rate_power") / scale
    ground_mult = _rate(rates, "ground_rate", s, "proper_rate") / scale
    if not _style_specified(style_grade):
        style_mult = 1.0            # auto/unknown running style -> neutral, not G
    else:
        style_mult = _rate(rates, "runningstyle_rate", grade_value(style_grade), "proper_rate") / scale
    mood = int(motivation or 3)
    mood = min(5, max(1, mood))
    mood_mult = _rate(rates, "motivation_rate", mood, "motivation_rate") / scale

    base = spd * spd_mult + 0.6 * pwr * pwr_mult + w_sta * sta + 0.15 * gut + 0.15 * wit
    return base * ground_mult * style_mult * mood_mult


def npc_strength(npc, *, distance_m, surface, rates=None):
    """Strength for a single_mode_npc stat block in a given race.

    surface: 'turf'/'dirt' or 1 (turf) / 2 (dirt).
    The NPC's running style is unknown, so we use its BEST style aptitude;
    motivation uses the midpoint of its [min,max] range (default 3).
    """
    apt = (npc or {}).get("aptitude") or {}
    dist_key, _ = distance_bucket(distance_m)
    dist_grade = (apt.get("distance") or {}).get(dist_key)
    surf_name = "dirt" if str(surface).lower() in ("dirt", "2") else "turf"
    surf_grade = (apt.get("ground") or {}).get(surf_name)
    styles = (apt.get("style") or {})
    if styles:
        style_grade = max((grade_value(v) for v in styles.values()), default=None)
    else:
        style_grade = None
    mn = int((npc or {}).get("motivation_min") or 0)
    mx = int((npc or {}).get("motivation_max") or 0)
    if mn and mx:
        motivation = round((mn + mx) / 2.0)
    elif mx:
        motivation = mx
    else:
        motivation = 3
    return runner_strength(npc, distance_m=distance_m, distance_grade=dist_grade,
                           surface_grade=surf_grade, style_grade=style_grade,
                           motivation=motivation, rates=rates)


def _logistic(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _poisson_binomial(probs):
    """PMF of the number of successes for independent Bernoulli(p_i)."""
    dp = [1.0]
    for p in probs:
        p = min(1.0, max(0.0, float(p)))
        nxt = [0.0] * (len(dp) + 1)
        for j, val in enumerate(dp):
            nxt[j] += val * (1.0 - p)
            nxt[j + 1] += val * p
        dp = nxt
    return dp


def win_probability(trainee_strength, opponent_strengths, *, k=DEFAULT_K, top_n=3):
    """P(win)/P(top_n)/E[rank] for trainee vs a list of opponent strengths."""
    try:
        k = float(k)
    except (TypeError, ValueError):
        k = DEFAULT_K
    if not (k > 0):                 # negative/zero/NaN k would invert or break the model
        k = DEFAULT_K
    qs = [_logistic((float(s) - float(trainee_strength)) / k) for s in opponent_strengths]
    p_win = 1.0
    for q in qs:
        p_win *= (1.0 - q)
    pmf = _poisson_binomial(qs)             # P(exactly j opponents ahead)
    p_top = sum(pmf[: top_n])               # at most top_n-1 opponents ahead
    expected_rank = 1.0 + sum(qs)
    return {
        "p_win": round(p_win, 4),
        "p_top3": round(min(1.0, p_top), 4),
        "expected_rank": round(expected_rank, 2),
        "field_size": len(qs) + 1,
        "k": k,
    }


def build_rival_index(rival_rows):
    """(chara_id, turn, program_id) -> [single_mode_npc_id, ...] for the field.

    Skips flag-driven rows (turn==0/program==0) and identity-only rows
    (single_mode_npc_id==0).  One opponent per source row; a race's field is the
    collected rows that share the key.
    """
    index = {}
    for r in rival_rows or []:
        try:
            chara = int(r.get("chara_id") or 0)
            turn = int(r.get("turn") or 0)
            prog = int(r.get("race_program_id") or 0)
            npc_id = int(r.get("single_mode_npc_id") or 0)
        except (TypeError, ValueError, AttributeError):
            continue
        if not (chara and turn and prog and npc_id):
            continue
        index.setdefault((chara, turn, prog), []).append(npc_id)
    return index


def resolve_field(rival_index, npc_by_id, *, trainee_chara_id, turn, program_id):
    """Named-rival NPC stat blocks for an upcoming race (may be empty)."""
    key = (int(trainee_chara_id or 0), int(turn or 0), int(program_id or 0))
    out = []
    seen = set()
    for npc_id in rival_index.get(key, []):
        if npc_id in seen:
            continue
        seen.add(npc_id)
        npc = npc_by_id.get(int(npc_id))
        if npc:
            out.append(npc)
    return out


def chara_id_from_card(card_id):
    """100101 -> 1001 (rival_races / single_mode_npc use the base chara id).

    A 6-digit card id is chara_id*100 + outfit variant; a 4-digit value is
    already a chara id and is returned unchanged.
    """
    try:
        cid = int(card_id or 0)
    except (TypeError, ValueError):
        return 0
    return cid // 100 if cid >= 100000 else cid


class WinProbModel:
    """Loaded data + a one-call query.  Built by load_model()."""

    def __init__(self, rates, npc_by_id, rival_index):
        self.rates = rates or {}
        self.npc_by_id = npc_by_id or {}
        self.rival_index = rival_index or {}

    def compute(self, *, stats, distance_m, ground, distance_grade, surface_grade,
                style_grade=None, motivation=3, trainee_chara_id=0, turn=0,
                program_id=0, k=DEFAULT_K):
        """Full P(win) result for the trainee in a race.

        Returns a dict; `available` is False when no named-rival field is known
        for this race (so callers can hide the estimate rather than show a
        misleading 100%).
        """
        field = resolve_field(self.rival_index, self.npc_by_id,
                              trainee_chara_id=trainee_chara_id, turn=turn,
                              program_id=program_id)
        s_t = runner_strength(stats, distance_m=distance_m,
                              distance_grade=distance_grade,
                              surface_grade=surface_grade, style_grade=style_grade,
                              motivation=motivation, rates=self.rates)
        opp = [npc_strength(n, distance_m=distance_m, surface=ground, rates=self.rates)
               for n in field]
        result = win_probability(s_t, opp, k=k)
        result["available"] = bool(field)
        result["trainee_strength"] = round(s_t, 1)
        result["field"] = [
            {"name": n.get("name") or str(n.get("id")), "id": int(n.get("id") or 0),
             "strength": round(strength, 1)}
            for n, strength in zip(field, opp)
        ]
        result["note"] = ("named-rival field only; mob runners that fill the gate "
                          "at race time are not modelled")
        return result


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def load_model(base_dir):
    """Read the three data files under <base_dir>/data and build a WinProbModel."""
    data = os.path.join(str(base_dir), "data")
    rates = _load_json(os.path.join(data, "race_performance_rates_core.json"), {})
    npc_rows = _load_json(os.path.join(data, "single_mode_npc_core.json"), [])
    rival_rows = _load_json(os.path.join(data, "rival_races_core.json"), [])
    npc_by_id = {}
    for n in npc_rows if isinstance(npc_rows, list) else []:
        try:
            npc_by_id[int(n.get("id") or 0)] = n
        except (TypeError, ValueError, AttributeError):
            continue
    return WinProbModel(rates if isinstance(rates, dict) else {}, npc_by_id,
                        build_rival_index(rival_rows if isinstance(rival_rows, list) else []))
