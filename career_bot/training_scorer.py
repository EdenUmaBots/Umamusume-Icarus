"""SweepyCL training scorer (v6.1).

Reimplements the Trackblazer training-scoring formula:

    score = (StatEfficiency * w_stat
             + Relationship  * w_rel
             + Misc          * w_misc)
            * RainbowMultiplier
            * FacilityLevelMultiplier

with rainbow detection from ``chara_info.evaluation_info_array``
cross-referenced against each command's ``training_partner_array``, plus an
anticipatory-rainbow bonus, stat-cap awareness, per-distance stat targets,
per-context (training / event / summer) priority lists, and a
failure-rate gate.

The existing strategy engine still makes the authoritative decision.  This
module publishes its scores as a *hint* alongside the strategy's pick so
the dashboard can show both, the user can validate the new scorer over a
few runs, and a future patch can promote the scorer to authoritative once
trust is built.

API surface intentionally small:

  - ``TrainingScorerConfig`` -- dataclass holding all tunables.
  - ``TrainingScore``        -- per-command output with components + diagnostics.
  - ``score_trainings(home_info, chara_info, ...)`` -- returns scores sorted
    best-first.
  - ``pre_summer_action(turn, energy, mood)`` -- standard
    June-Late prep helper (returns ``"rest" | "recover" | "train_wit" | None``).

No new dependencies.  Pure standard library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence


# Game constants -----------------------------------------------------------

# target_type -> stat name; matches the existing items._command_stat_gain
# convention.  6 / 30 are skill-point variants.
STAT_TARGET_TYPES = {1: "speed", 2: "stamina", 3: "power", 4: "guts", 5: "wit"}
SKILL_POINT_TARGETS = {6, 30}

# evaluation_info_array.target_id maps the same way for cards (1..5 = stat
# tab, 6 = friend).  A bond >= ``bond_threshold_rainbow`` makes that card
# eligible to produce a rainbow when it appears in a training_partner_array.
RAINBOW_BOND_THRESHOLD_DEFAULT = 80

# Mood enum (game-canonical):  1=awful 2=bad 3=normal 4=good 5=great.
MOOD_GREAT = 5
MOOD_NORMAL = 3


@dataclass
class TrainingScorerConfig:
    """All tunables for the scorer.  Defaults match the reference solver's
    settings page out-of-the-box so users coming from there don't have to
    re-tune anything obvious."""

    # ----- component weights ----------------------------------------------

    weight_stat_efficiency: float = 0.60
    """Weight on stat-efficiency when at least one support card is present."""

    weight_relationship: float = 0.10
    """Weight on relationship/bond contribution."""

    weight_misc: float = 0.30
    """Weight on mood, skill hints, and misc bonuses."""

    weight_stat_efficiency_no_rel: float = 0.70
    """Stat-efficiency weight when no support cards are present
    (relationship is collapsed into stat efficiency)."""

    weight_misc_no_rel: float = 0.30

    # ----- rainbow multipliers --------------------------------------------

    rainbow_bonus_multiplier: float = 2.0
    """Used when ``rainbow_bonus_enabled`` is on (aggressive rainbow pursuit)."""

    rainbow_normal_multiplier: float = 1.5
    """Default rainbow multiplier (matches the reference default)."""

    no_rainbow_multiplier: float = 1.0

    rainbow_bonus_enabled: bool = False
    """Toggle the 2.0x vs 1.5x rainbow multiplier."""

    anticipatory_cap: float = 1.6
    """Maximum anticipatory-rainbow multiplier (kept below the real-rainbow
    1.5/2.0x band intentionally so anticipation never out-ranks a real
    rainbow)."""

    anticipatory_per_bar: float = 0.20
    """Each near-rainbow bar contributes this * fill_percent."""

    anticipatory_max_bonus: float = 0.60
    """Hard cap on the additive anticipatory bonus."""

    anticipatory_min_fill: float = 0.10
    """Bond bars below this fraction of the rainbow threshold are ignored
    for anticipation (otherwise everything looks ``near-rainbow``)."""

    # ----- facility level weighting (standard formula) ------------------

    enable_level_weighting: bool = True
    """Top-N priority stats get a multiplier based on the training facility
    level (1..5)."""

    level_weighted_top_n: int = 3
    """Only the user's top-N priority stats receive the level boost."""

    level_mult_max_rank1: float = 1.75
    """Level-5 multiplier for the rank-1 priority stat."""

    level_mult_max_rank2: float = 1.25

    level_mult_max_rank3: float = 1.10

    # ----- gates and caps -------------------------------------------------

    max_failure_chance: int = 20
    """Trainings with failure rate above this are filtered out (matches
    Default behavior; risky-training mode override goes through a separate
    config flag downstream)."""

    stat_cap_buffer: int = 100
    """A stat within ``buffer`` units of its scenario cap is treated as
    maxed and scores 0 unless a one-time rainbow allowance applies."""

    stat_cap_absolute: int = 1200
    """Default scenario stat cap.  Overridden per-preset in real configs."""

    # ----- per-distance stat targets --------------------------------------

    stat_targets: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
        "sprint": {"speed": 1200, "stamina": 400, "power": 1100, "guts": 400, "wit": 1000},
        "mile":   {"speed": 1200, "stamina": 600, "power": 1000, "guts": 400, "wit": 1000},
        "medium": {"speed": 1100, "stamina": 800, "power": 1000, "guts": 400, "wit": 1000},
        "long":   {"speed": 1000, "stamina": 1100, "power": 1000, "guts": 400, "wit": 1000},
    })

    # ----- priority lists -------------------------------------------------

    stat_priority: List[str] = field(
        default_factory=lambda: ["speed", "stamina", "power", "guts", "wit"]
    )
    """Ordered priority list used by the training scorer."""

    event_stat_priority: Optional[List[str]] = None
    """Optional separate priority for training-event scoring; falls back
    to ``stat_priority`` when ``None``."""

    summer_stat_priority: Optional[List[str]] = None
    """Optional separate priority for Summer turns (37-40 and 61-64)."""

    # ----- #6 goal-aware lookahead (opt-in) -------------------------------

    goal_lookahead: bool = False
    """When True, stat-gain value is boosted for stats that are BEHIND the pace
    needed to reach their target by the career deadline, and trimmed for stats
    already ahead of pace. Off by default — default scoring is unchanged."""

    career_total_turns: int = 78
    """Total career turns used to compute the goal-lookahead pace target."""

    goal_lookahead_max_boost: float = 0.4
    """Cap on the urgency multiplier swing (±) applied when ``goal_lookahead``."""

    # ----- rainbow detection ----------------------------------------------

    bond_threshold_rainbow: int = RAINBOW_BOND_THRESHOLD_DEFAULT


# --------------------------------------------------------------------------
# Per-command output
# --------------------------------------------------------------------------


@dataclass
class TrainingScore:
    """One training command's scored output.

    Sortable by score descending.  ``skipped_reason`` is set on filtered
    commands so callers can show why a training was excluded.
    """

    command_id: int
    command_type: int
    stat_name: str

    # Final
    score: float

    # Component breakdown
    stat_efficiency: float
    relationship: float
    misc: float
    rainbow_multiplier: float
    level_multiplier: float

    # Raw inputs
    raw_stat_gain: int
    skill_point_gain: int
    failure_rate: int
    training_partners: int
    rainbow_partners: int
    near_rainbow_partners: int
    facility_level: int

    # Filtering
    skipped_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type,
            "stat_name": self.stat_name,
            "score": round(self.score, 4),
            "stat_efficiency": round(self.stat_efficiency, 4),
            "relationship": round(self.relationship, 4),
            "misc": round(self.misc, 4),
            "rainbow_multiplier": round(self.rainbow_multiplier, 4),
            "level_multiplier": round(self.level_multiplier, 4),
            "raw_stat_gain": int(self.raw_stat_gain),
            "skill_point_gain": int(self.skill_point_gain),
            "failure_rate": int(self.failure_rate),
            "training_partners": int(self.training_partners),
            "rainbow_partners": int(self.rainbow_partners),
            "near_rainbow_partners": int(self.near_rainbow_partners),
            "facility_level": int(self.facility_level),
            "skipped_reason": self.skipped_reason,
        }


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _bond_map_from_chara(chara_info: Mapping[str, Any]) -> Dict[int, int]:
    """Map support_card_id -> bond/evaluation value."""
    out: Dict[int, int] = {}
    for row in (chara_info or {}).get("evaluation_info_array") or []:
        if not isinstance(row, Mapping):
            continue
        try:
            cid = int(row.get("support_card_id") or row.get("card_id") or row.get("target_id") or 0)
            val = int(row.get("evaluation") or row.get("value") or 0)
        except (TypeError, ValueError):
            continue
        if cid <= 0:
            continue
        out[cid] = val
    return out


def _current_stats(chara_info: Mapping[str, Any]) -> Dict[str, int]:
    chara = chara_info or {}

    def pull(*names):
        for n in names:
            v = chara.get(n)
            if v not in (None, ""):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    continue
        return 0

    return {
        "speed": pull("speed", "speed_value"),
        "stamina": pull("stamina", "stamina_value"),
        "power": pull("power", "pow", "power_value"),
        "guts": pull("guts", "guts_value"),
        "wit": pull("wiz", "wit", "wisdom", "intelligence"),
    }


# Aptitude rank labels A-G in master.mdb are stored as ints 1..8 where 7 is A
# (a typical "good" aptitude).  We compare numerically so callers passing
# ints or strings both work.
_APTITUDE_RANK_PRIORITY = {
    "S": 8, "A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1,
}


def _aptitude_score(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        return _APTITUDE_RANK_PRIORITY.get(value.upper().strip(), 0)
    return 0


def _infer_distance(chara_info: Mapping[str, Any]) -> str:
    """Pick the trainee's best distance aptitude (sprint/mile/medium/long).

    Used when the caller doesn't override.  Falls back to ``mile`` -- the
    default the game itself uses for first-career horses.
    """
    chara = chara_info or {}
    candidates = {
        "sprint": _aptitude_score(chara.get("proper_distance_short")),
        "mile":   _aptitude_score(chara.get("proper_distance_mile")),
        "medium": _aptitude_score(chara.get("proper_distance_middle")),
        "long":   _aptitude_score(chara.get("proper_distance_long")),
    }
    best = max(candidates.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else "mile"


def _priority_for_context(cfg: TrainingScorerConfig, context: str) -> List[str]:
    if context == "event" and cfg.event_stat_priority:
        return list(cfg.event_stat_priority)
    if context == "summer" and cfg.summer_stat_priority:
        return list(cfg.summer_stat_priority)
    return list(cfg.stat_priority)


def _stat_gain_breakdown(cmd: Mapping[str, Any]) -> tuple[Dict[str, int], int]:
    """Return ({stat_name: gain}, skill_point_gain) for a command."""
    stat_gains: Dict[str, int] = {v: 0 for v in STAT_TARGET_TYPES.values()}
    sp_gain = 0

    array = cmd.get("params_inc_dec_info_array") or []
    if array:
        for entry in array:
            try:
                tt = int(entry.get("target_type") or 0)
                value = int(entry.get("value") or 0)
            except (TypeError, ValueError, AttributeError):
                continue
            name = STAT_TARGET_TYPES.get(tt)
            if name:
                stat_gains[name] += value
            elif tt in SKILL_POINT_TARGETS:
                sp_gain += value
    else:
        # Fall back to the flat field layout some older payloads use.
        for name in stat_gains:
            game_field = "wiz" if name == "wit" else name
            try:
                stat_gains[name] = int(cmd.get(game_field) or cmd.get(name) or 0)
            except (TypeError, ValueError):
                pass
        try:
            sp_gain = int(cmd.get("lp") or cmd.get("skill_point") or 0)
        except (TypeError, ValueError):
            sp_gain = 0
    return stat_gains, sp_gain


def _primary_stat(stat_gains: Mapping[str, int]) -> str:
    """The stat with the largest single-turn gain.  Used to label the
    training (Speed training, Stamina training, etc.)."""
    if not stat_gains:
        return "wit"
    return max(stat_gains.items(), key=lambda kv: kv[1])[0]


def _level_multiplier(
    cfg: TrainingScorerConfig,
    stat_name: str,
    priority: Sequence[str],
    facility_level: int,
) -> float:
    """Standard training-level weighting.

    Only the top-N priority stats get a boost, only when facility level >= 2.
    The Lvl-5 ceilings are configured; intermediate levels fade linearly
    from 1.0 at Lvl 1 to the configured ceiling at Lvl 5.
    """
    if not cfg.enable_level_weighting or facility_level < 2:
        return 1.0

    try:
        rank = priority.index(stat_name)
    except ValueError:
        return 1.0
    if rank >= cfg.level_weighted_top_n:
        return 1.0

    ceiling = {
        0: cfg.level_mult_max_rank1,
        1: cfg.level_mult_max_rank2,
        2: cfg.level_mult_max_rank3,
    }.get(rank, 1.0)

    # Linear fade from 1.0 at level 1 to ceiling at level 5.
    fade = (facility_level - 1) / 4.0
    fade = max(0.0, min(1.0, fade))
    return 1.0 + (ceiling - 1.0) * fade


def _rainbow_multiplier(
    cfg: TrainingScorerConfig,
    rainbow_partners: int,
    near_rainbow_partners: float,
) -> float:
    """Pick the rainbow multiplier.

    Real rainbow (>=1 partner with bond >= threshold AND participating) ->
    the bonus/normal multiplier.

    Otherwise, if any partner is "near rainbow" (above the min-fill
    threshold), apply the anticipatory multiplier capped at
    ``anticipatory_cap`` (which is intentionally < the real-rainbow band so
    anticipation can never out-rank a real rainbow training).
    """
    if rainbow_partners >= 1:
        return (
            cfg.rainbow_bonus_multiplier
            if cfg.rainbow_bonus_enabled
            else cfg.rainbow_normal_multiplier
        )
    if near_rainbow_partners > 0:
        bonus = min(
            cfg.anticipatory_max_bonus,
            cfg.anticipatory_per_bar * near_rainbow_partners,
        )
        return min(cfg.anticipatory_cap, 1.0 + bonus)
    return cfg.no_rainbow_multiplier


def _goal_urgency(
    cfg: TrainingScorerConfig,
    current_stats: Mapping[str, int],
    targets: Mapping[str, int],
    turn: int,
) -> Dict[str, float]:
    """#6 — per-stat pace multiplier for goal-aware lookahead.

    Returns ``{}`` (no effect) unless ``cfg.goal_lookahead`` is on. Otherwise a
    stat that is BEHIND the linear pace needed to reach its target by the career
    deadline is boosted (up to +``goal_lookahead_max_boost``); a stat already
    ahead of pace is trimmed by the same cap. This nudges the goal-aware scorer
    to shore up lagging stats earlier so the target build is met by the finals.
    """
    if not getattr(cfg, "goal_lookahead", False):
        return {}
    total = max(1, int(getattr(cfg, "career_total_turns", 78)))
    turn = int(turn or 0)
    if turn <= 0 or turn >= total:
        return {}
    progress = turn / total
    swing = float(getattr(cfg, "goal_lookahead_max_boost", 0.4))
    out: Dict[str, float] = {}
    for name, target in (targets or {}).items():
        target = int(target or 0)
        if target <= 0:
            continue
        expected = target * progress
        if expected <= 0:
            continue
        current = int((current_stats or {}).get(name) or 0)
        ratio = current / expected  # < 1 behind pace, > 1 ahead of pace
        out[name] = 1.0 + max(-swing, min(swing, 1.0 - ratio))
    return out


def _stat_efficiency(
    stat_gains: Mapping[str, int],
    targets: Mapping[str, int],
    current_stats: Mapping[str, int],
    priority: Sequence[str],
    cfg: TrainingScorerConfig,
    urgency: Optional[Mapping[str, float]] = None,
) -> float:
    """How much the stat gain moves the trainee toward their distance target.

    Two factors combine multiplicatively:

      - **Importance**: per-distance target normalized against the scenario
        max.  A Long-runner whose Stamina target is 1100 gets full importance
        for Stamina; a Sprint-runner whose Stamina target is 400 gets ~36%.
        This is what the "Stat Targets by Distance" setting encodes.

      - **Gap remaining**: ``(target - current) / target`` -- 1.0 when
        starting fresh, 0.0 once you've hit target.  Once at/over target
        the gain is treated as overshoot at a flat discounted rate.

    Priority rank then layers on a smaller secondary factor (the user's
    explicit stat ordering).
    """
    if not stat_gains:
        return 0.0

    cap_normalizer = max(1, int(cfg.stat_cap_absolute))
    total = 0.0

    for name, gain in stat_gains.items():
        if gain <= 0:
            continue
        target = int(targets.get(name) or 0)
        current = int(current_stats.get(name) or 0)

        if target > 0 and current < target:
            remaining = max(1, target - current)
            gap_fraction = remaining / target              # 1.0 fresh, 0.0 at target
            importance = min(1.0, target / cap_normalizer) # higher target = more value
            base = gain * gap_fraction * importance
        else:
            # Overshoot: flat discounted reward so the bot is willing to
            # push past target for a clearly excellent training, but not
            # nearly as eagerly as before reaching it.
            base = gain * 0.25

        if urgency:
            base *= float(urgency.get(name, 1.0))

        # Priority ordering is a secondary modulator -- rank 0 keeps full
        # rate, descending stats fade gradually.
        try:
            rank = priority.index(name)
            priority_factor = max(0.4, 1.0 - rank * 0.12)
        except ValueError:
            priority_factor = 0.4

        total += base * priority_factor

    return total


def _relationship_score(
    cmd: Mapping[str, Any],
    bonds: Mapping[int, int],
    cfg: TrainingScorerConfig,
) -> tuple[float, int, int, float]:
    """Return (relationship_score, partner_count, rainbow_count,
    near_rainbow_count) for one command.

    Partners are read from ``training_partner_array``.  A partner with
    bond >= ``bond_threshold_rainbow`` is a real-rainbow contributor.  A
    partner below that threshold but with a meaningful fraction of the
    threshold counts toward anticipatory rainbow weighting.
    """
    partners = cmd.get("training_partner_array") or []
    partner_count = len(partners)
    if partner_count == 0:
        return 0.0, 0, 0, 0.0

    threshold = max(1, cfg.bond_threshold_rainbow)
    min_fill = cfg.anticipatory_min_fill

    rel = 0.0
    rainbow_count = 0
    near_rainbow_fill = 0.0
    for partner_id in partners:
        try:
            cid = int(partner_id)
        except (TypeError, ValueError):
            continue
        bond = bonds.get(cid, 0)
        rel += bond / threshold  # >=1.0 means fully ready

        if bond >= threshold:
            rainbow_count += 1
        else:
            fill = bond / threshold
            if fill >= min_fill:
                near_rainbow_fill += fill

    return rel, partner_count, rainbow_count, near_rainbow_fill


def _misc_score(
    cmd: Mapping[str, Any],
    sp_gain: int,
    skill_hint_partners: int,
) -> float:
    """Catch-all: skill points, skill hint partners, special items.

    Modest absolute magnitude -- relationship and stat efficiency are the
    main drivers.
    """
    return float(sp_gain) * 1.0 + float(skill_hint_partners) * 8.0


# --------------------------------------------------------------------------
# Top-level entry points
# --------------------------------------------------------------------------


def score_trainings(
    home_info: Mapping[str, Any],
    chara_info: Mapping[str, Any],
    *,
    config: Optional[TrainingScorerConfig] = None,
    distance_label: Optional[str] = None,
    context: str = "training",
) -> List[TrainingScore]:
    """Score every training command in ``home_info.command_info_array``.

    Returns a list sorted best-first.  Filtered commands (failure too high,
    stat capped) appear at the bottom with ``skipped_reason`` set so the
    dashboard can render them as greyed-out rather than hidden.
    """
    cfg = config or TrainingScorerConfig()
    bonds = _bond_map_from_chara(chara_info)
    current_stats = _current_stats(chara_info)
    distance = (distance_label or _infer_distance(chara_info)).lower()
    targets = cfg.stat_targets.get(distance) or cfg.stat_targets.get("mile") or {}
    priority = _priority_for_context(cfg, context)
    urgency = _goal_urgency(cfg, current_stats, targets, int((chara_info or {}).get("turn") or 0))

    scored: List[TrainingScore] = []
    for cmd in (home_info or {}).get("command_info_array") or []:
        if not isinstance(cmd, Mapping):
            continue
        if int(cmd.get("command_type") or 0) != 1:
            continue
        if int(cmd.get("is_enable") or 0) == 0:
            continue
        scored.append(
            _score_one_command(cmd, current_stats, targets, priority, bonds, cfg, urgency)
        )

    # Filtered/skipped commands sort to the bottom by virtue of score=0.
    scored.sort(key=lambda s: (-s.score, s.command_id))
    return scored


def _score_one_command(
    cmd: Mapping[str, Any],
    current_stats: Mapping[str, int],
    targets: Mapping[str, int],
    priority: Sequence[str],
    bonds: Mapping[int, int],
    cfg: TrainingScorerConfig,
    urgency: Optional[Mapping[str, float]] = None,
) -> TrainingScore:
    command_id = int(cmd.get("command_id") or 0)
    command_type = int(cmd.get("command_type") or 0)
    facility_level = int(cmd.get("level") or 1)
    failure_rate = int(cmd.get("failure_rate") or 0)

    stat_gains, sp_gain = _stat_gain_breakdown(cmd)
    primary = _primary_stat(stat_gains)
    raw_total = sum(stat_gains.values())

    # ---- Filters: stop early with score 0 but populate diagnostics. -----

    if failure_rate > cfg.max_failure_chance:
        return TrainingScore(
            command_id=command_id,
            command_type=command_type,
            stat_name=primary,
            score=0.0,
            stat_efficiency=0.0,
            relationship=0.0,
            misc=0.0,
            rainbow_multiplier=cfg.no_rainbow_multiplier,
            level_multiplier=1.0,
            raw_stat_gain=raw_total,
            skill_point_gain=sp_gain,
            failure_rate=failure_rate,
            training_partners=len(cmd.get("training_partner_array") or []),
            rainbow_partners=0,
            near_rainbow_partners=0,
            facility_level=facility_level,
            skipped_reason="failure_too_high",
        )

    # Stat cap: if the primary stat is within buffer of the absolute cap,
    # this training won't move it.  Allows future scenarios to override the
    # cap via cfg.stat_cap_absolute.
    current = int(current_stats.get(primary) or 0)
    if current >= max(0, cfg.stat_cap_absolute - cfg.stat_cap_buffer):
        return TrainingScore(
            command_id=command_id,
            command_type=command_type,
            stat_name=primary,
            score=0.0,
            stat_efficiency=0.0,
            relationship=0.0,
            misc=0.0,
            rainbow_multiplier=cfg.no_rainbow_multiplier,
            level_multiplier=1.0,
            raw_stat_gain=raw_total,
            skill_point_gain=sp_gain,
            failure_rate=failure_rate,
            training_partners=len(cmd.get("training_partner_array") or []),
            rainbow_partners=0,
            near_rainbow_partners=0,
            facility_level=facility_level,
            skipped_reason="stat_capped",
        )

    # ---- Components ----------------------------------------------------

    stat_eff = _stat_efficiency(stat_gains, targets, current_stats, priority, cfg, urgency)
    rel_raw, partner_count, rainbow_count, near_fill = _relationship_score(cmd, bonds, cfg)
    skill_hint_partners = len(cmd.get("tips_event_partner_array") or [])
    misc_raw = _misc_score(cmd, sp_gain, skill_hint_partners)

    if partner_count > 0:
        weighted = (
            stat_eff * cfg.weight_stat_efficiency
            + rel_raw * cfg.weight_relationship * 100.0  # rel_raw is unitless ratio
            + misc_raw * cfg.weight_misc
        )
    else:
        weighted = (
            stat_eff * cfg.weight_stat_efficiency_no_rel
            + misc_raw * cfg.weight_misc_no_rel
        )

    rainbow_mult = _rainbow_multiplier(cfg, rainbow_count, near_fill)
    level_mult = _level_multiplier(cfg, primary, priority, facility_level)
    final = weighted * rainbow_mult * level_mult

    return TrainingScore(
        command_id=command_id,
        command_type=command_type,
        stat_name=primary,
        score=final,
        stat_efficiency=stat_eff,
        relationship=rel_raw,
        misc=misc_raw,
        rainbow_multiplier=rainbow_mult,
        level_multiplier=level_mult,
        raw_stat_gain=raw_total,
        skill_point_gain=sp_gain,
        failure_rate=failure_rate,
        training_partners=partner_count,
        rainbow_partners=rainbow_count,
        near_rainbow_partners=int(round(near_fill)),
        facility_level=facility_level,
        skipped_reason=None,
    )


# --------------------------------------------------------------------------
# Pre-summer prep helper (June Late, Classic/Senior years)
# --------------------------------------------------------------------------


def pre_summer_action(
    turn: int,
    energy: int,
    energy_max: int,
    mood: int,
    *,
    energy_floor_pct: float = 0.70,
) -> Optional[str]:
    """June-Late pre-summer prep decision.

    Returns ``"rest"``, ``"recover"``, ``"train_wit"``, or ``None``.

    The check applies on the last turn before Summer training (turn 24 in
    Junior Year and turn 48 in Classic Year -- Senior summer doesn't get
    this prep because the trainee is about to retire anyway).
    """
    if turn not in (24, 48):
        return None
    energy_pct = (energy / energy_max) if energy_max > 0 else 1.0
    if energy_pct < energy_floor_pct:
        return "rest"
    if mood < MOOD_GREAT:
        return "recover"
    return "train_wit"


def adapt_stamina_targets(
    config: TrainingScorerConfig,
    chara_info: Mapping[str, Any],
    *,
    enabled: bool,
    turn: Optional[int] = None,
    career_total_turns: int = 78,
    min_turn: int = 40,
    lag_ratio: float = 0.8,
    floor: int = 400,
) -> TrainingScorerConfig:
    """Parent/deck-aware stamina relaxation (v6.8, opt-in).

    When ``enabled`` and the trainee's stamina is, by mid-career, projected to
    fall well short of its per-distance target (the signature of no stamina
    inheritance or stamina support feeding it), lower the stamina target for the
    trainee's inferred distance toward the projected-achievable value.  This
    stops the scorer from sinking turns into an unreachable stamina number; those
    turns flow to the next-priority stat (typically speed/wit) instead.

    Heuristic, intentionally conservative: only acts after ``min_turn`` (post the
    first summer camp, so the pace estimate is meaningful) and only when the
    linear end-of-career projection is below ``lag_ratio`` of the target.  The
    relaxed target is floored at ``floor`` and never raised above the original.

    Pure: returns ``config`` unchanged when disabled / too early / on pace.
    """
    if not enabled or not turn or turn < min_turn:
        return config
    distance = _infer_distance(chara_info)
    targets = (config.stat_targets or {}).get(distance)
    if not isinstance(targets, Mapping):
        return config
    target_sta = int(targets.get("stamina") or 0)
    if target_sta <= floor:
        return config
    current_sta = int(chara_info.get("stamina") or chara_info.get("stamina_value") or 0)
    frac = max(0.05, min(1.0, turn / max(1, career_total_turns)))
    projected_end = current_sta / frac
    if projected_end >= target_sta * lag_ratio:
        return config  # on track enough -- leave the target alone
    new_target = max(floor, min(target_sta, int(round(projected_end))))
    if new_target >= target_sta:
        return config
    import copy
    new_cfg = copy.copy(config)
    new_cfg.stat_targets = {d: dict(v) for d, v in (config.stat_targets or {}).items()}
    new_cfg.stat_targets[distance] = dict(targets)
    new_cfg.stat_targets[distance]["stamina"] = new_target
    return new_cfg


__all__ = [
    "TrainingScorerConfig",
    "TrainingScore",
    "score_trainings",
    "pre_summer_action",
    "adapt_stamina_targets",
    "STAT_TARGET_TYPES",
    "SKILL_POINT_TARGETS",
    "RAINBOW_BOND_THRESHOLD_DEFAULT",
]
