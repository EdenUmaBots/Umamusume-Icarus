"""Counterfactual "regret" replay over a completed career log.

Given a finished ``career_log_*.json`` (or any mapping with the same ``turns``
shape), this scores *how much each training turn cost the run* in two
independent, honest ways:

1. **Decision regret** -- when the log stored the scorer's per-candidate
   ``training_candidates`` (each with a ``score``), the regret of a turn is
   ``best_available_score - chosen_score``.  A turn where the bot picked the
   top-ranked option has zero regret; a turn where it left a much better option
   on the table has high regret.  This is *only* available for runs whose logs
   carried candidate scores -- older logs don't, and we say so rather than
   inventing numbers.

2. **Hindsight stat-gap regret** -- with the benefit of the final target build,
   flag training turns that poured gains into a stat already at/over its target
   while another stat was still far short.  Needs only the per-turn stat
   snapshot plus a target build, so it works on any log.

Pure standard library, no I/O, deterministic given inputs -- so it can be
re-run over historical logs freely and reused inside the Last Run Report or the
benchmark harness.  The career log does *not* persist the full
``home_info.command_info_array`` per turn, so this module works from what the
log actually records rather than re-deriving per-turn training scores.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

# command_id -> stat (matches the training labels in career_bot/runner.py).
COMMAND_TO_STAT: Dict[int, str] = {
    101: "speed",
    102: "power",
    103: "guts",
    105: "stamina",
    106: "wit",
    601: "speed",
    602: "stamina",
    603: "power",
    604: "guts",
    605: "wit",
}

STAT_ORDER = ["speed", "stamina", "power", "guts", "wit"]

# Default balanced target -- mirrors recommended_stats.DEFAULT_RECOMMENDED_STATS
# but kept local so this module stays pure/standalone.  Callers that know the
# trainee should pass their own ``target_stats``.
DEFAULT_TARGET_STATS = {
    "speed": 1200,
    "stamina": 600,
    "power": 1200,
    "guts": 600,
    "wit": 1200,
}


@dataclass
class TurnRegret:
    """Decision-regret detail for a single training turn."""
    turn: int
    chosen_id: int
    chosen_name: str
    chosen_score: float
    best_id: int
    best_name: str
    best_score: float
    regret: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "chosen_id": self.chosen_id,
            "chosen_name": self.chosen_name,
            "chosen_score": round(self.chosen_score, 3),
            "best_id": self.best_id,
            "best_name": self.best_name,
            "best_score": round(self.best_score, 3),
            "regret": round(self.regret, 3),
        }


@dataclass
class HindsightFlag:
    """A training turn that, in hindsight, fed an already-capped stat."""
    turn: int
    stat: str
    current: int
    target: int
    overshoot: int
    neglected_stat: str
    neglected_gap: int
    wasted: int  # min(overshoot, neglected_gap) -- the recoverable misallocation
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "stat": self.stat,
            "current": self.current,
            "target": self.target,
            "overshoot": self.overshoot,
            "neglected_stat": self.neglected_stat,
            "neglected_gap": self.neglected_gap,
            "wasted": self.wasted,
            "note": self.note,
        }


@dataclass
class RegretReport:
    has_candidate_data: bool = False
    evaluated_turns: int = 0
    decision_regret_total: float = 0.0
    decision_regret_mean: float = 0.0
    top_decision_regret: List[TurnRegret] = field(default_factory=list)
    hindsight_flags: List[HindsightFlag] = field(default_factory=list)
    hindsight_wasted_total: int = 0
    target_stats: Dict[str, int] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_candidate_data": self.has_candidate_data,
            "evaluated_turns": self.evaluated_turns,
            "decision_regret_total": round(self.decision_regret_total, 3),
            "decision_regret_mean": round(self.decision_regret_mean, 3),
            "top_decision_regret": [t.to_dict() for t in self.top_decision_regret],
            "hindsight_flags": [h.to_dict() for h in self.hindsight_flags],
            "hindsight_wasted_total": self.hindsight_wasted_total,
            "target_stats": dict(self.target_stats),
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------
# Log-shape helpers (tolerant of the several places fields can live)
# --------------------------------------------------------------------------


def _turns(career_log: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    turns = career_log.get("turns")
    return [t for t in turns if isinstance(t, Mapping)] if isinstance(turns, list) else []


def _decision_report(turn: Mapping[str, Any]) -> Mapping[str, Any]:
    dr = turn.get("decision_report")
    return dr if isinstance(dr, Mapping) else {}


def _training_candidates(turn: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    """Find scored training candidates wherever the logger stashed them.

    Newer career logs put them in ``decision_report.training_candidates``; the
    AI-flattened ``turn_decisions`` rows use ``candidate_context``.  We accept
    either and only keep dict rows that carry a numeric ``score``.
    """
    locations = [
        _decision_report(turn).get("training_candidates"),
        (turn.get("candidate_context") or {}).get("training_candidates")
        if isinstance(turn.get("candidate_context"), Mapping) else None,
        (_decision_report(turn).get("candidate_context") or {}).get("training_candidates")
        if isinstance(_decision_report(turn).get("candidate_context"), Mapping) else None,
    ]
    for cands in locations:
        if isinstance(cands, list):
            rows = [c for c in cands if isinstance(c, Mapping) and _has_score(c)]
            if rows:
                return rows
    return []


def _has_score(candidate: Mapping[str, Any]) -> bool:
    return isinstance(candidate.get("score"), (int, float))


def _chosen_command_id(turn: Mapping[str, Any]) -> Optional[int]:
    """The training command_id the bot actually executed this turn, if any."""
    payload = _decision_report(turn).get("payload")
    if isinstance(payload, Mapping):
        ctype = payload.get("command_type")
        cid = payload.get("command_id")
        if ctype in (1, "1") and isinstance(cid, (int, float)):
            return int(cid)
    # Flattened ``action`` form (turn_decisions rows).
    action = turn.get("action")
    if isinstance(action, Mapping) and action.get("command_type") in (1, "1"):
        cid = action.get("command_id")
        if isinstance(cid, (int, float)):
            return int(cid)
    return None


def _turn_state(turn: Mapping[str, Any]) -> Dict[str, int]:
    """Stat snapshot at decision time -- prefer decision_report.state, fall
    back to the turn's own ``stats``/``state`` block."""
    for src in (_decision_report(turn).get("state"), turn.get("stats"), turn.get("state")):
        if isinstance(src, Mapping) and src:
            return _normalize_stats(src)
    return {}


def _normalize_stats(stats: Mapping[str, Any]) -> Dict[str, int]:
    def _int(*keys: str) -> int:
        for k in keys:
            v = stats.get(k)
            if isinstance(v, (int, float)):
                return int(v)
        return 0
    return {
        "speed": _int("speed"),
        "stamina": _int("stamina"),
        "power": _int("power"),
        "guts": _int("guts"),
        "wit": _int("wit", "wiz", "wisdom"),
    }


def normalize_target_stats(target: Optional[Mapping[str, Any]]) -> Dict[str, int]:
    """Accept Title-case (``Speed``) or lower-case (``speed``) target builds."""
    if not isinstance(target, Mapping) or not target:
        return dict(DEFAULT_TARGET_STATS)
    out: Dict[str, int] = {}
    for stat in STAT_ORDER:
        val = target.get(stat)
        if val is None:
            val = target.get(stat.title())
        try:
            out[stat] = int(val) if val is not None else DEFAULT_TARGET_STATS[stat]
        except (TypeError, ValueError):
            out[stat] = DEFAULT_TARGET_STATS[stat]
    return out


# --------------------------------------------------------------------------
# The two regret passes
# --------------------------------------------------------------------------


def _match_chosen_in_trace(row: Mapping[str, Any], cands: List[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """Identify the candidate the bot actually trained from a decision-trace row.

    Trace rows don't store an explicit chosen command_id -- they store
    ``action`` ("command") and ``reason`` ("Train Power"). We match the reason
    text against the candidate names.
    """
    if str(row.get("action") or "").strip().lower() != "command":
        return None
    reason = str(row.get("reason") or "").lower()
    if "train" not in reason:
        return None
    # Prefer the longest candidate name that appears in the reason, so "Wit"
    # never shadows a longer match.
    best = None
    for c in cands:
        nm = str(c.get("name") or "").strip().lower()
        if nm and nm in reason:
            if best is None or len(nm) > len(str(best.get("name") or "")):
                best = c
    return best


def _decision_regret_from_traces(trace_rows: List[Mapping[str, Any]]) -> List[TurnRegret]:
    out: List[TurnRegret] = []
    for row in trace_rows:
        if not isinstance(row, Mapping):
            continue
        cands = [c for c in (row.get("training_candidates") or [])
                 if isinstance(c, Mapping) and _has_score(c)]
        if not cands:
            continue
        chosen = _match_chosen_in_trace(row, cands)
        if chosen is None:
            continue
        best = max(cands, key=lambda c: float(c.get("score") or 0.0))
        chosen_score = float(chosen.get("score") or 0.0)
        best_score = float(best.get("score") or 0.0)
        chosen_id = int(chosen.get("command_id") or 0)
        out.append(TurnRegret(
            turn=int(row.get("turn") or 0),
            chosen_id=chosen_id,
            chosen_name=str(chosen.get("name") or COMMAND_TO_STAT.get(chosen_id, "?")),
            chosen_score=chosen_score,
            best_id=int(best.get("command_id") or 0),
            best_name=str(best.get("name") or "?"),
            best_score=best_score,
            regret=max(0.0, best_score - chosen_score),
        ))
    return out


def _decision_regret(turns: List[Mapping[str, Any]]) -> List[TurnRegret]:
    out: List[TurnRegret] = []
    for turn in turns:
        cands = _training_candidates(turn)
        if not cands:
            continue
        chosen_id = _chosen_command_id(turn)
        if chosen_id is None:
            continue
        chosen = next((c for c in cands if int(c.get("command_id") or 0) == chosen_id), None)
        if chosen is None:
            continue
        best = max(cands, key=lambda c: float(c.get("score") or 0.0))
        chosen_score = float(chosen.get("score") or 0.0)
        best_score = float(best.get("score") or 0.0)
        regret = max(0.0, best_score - chosen_score)
        out.append(TurnRegret(
            turn=int(turn.get("turn") or 0),
            chosen_id=chosen_id,
            chosen_name=str(chosen.get("name") or COMMAND_TO_STAT.get(chosen_id, "?")),
            chosen_score=chosen_score,
            best_id=int(best.get("command_id") or 0),
            best_name=str(best.get("name") or COMMAND_TO_STAT.get(int(best.get("command_id") or 0), "?")),
            best_score=best_score,
            regret=regret,
        ))
    return out


def _hindsight_flags(turns: List[Mapping[str, Any]], target: Dict[str, int]) -> List[HindsightFlag]:
    out: List[HindsightFlag] = []
    for turn in turns:
        cid = _chosen_command_id(turn)
        if cid is None or cid not in COMMAND_TO_STAT:
            continue
        stat = COMMAND_TO_STAT[cid]
        state = _turn_state(turn)
        if not state:
            continue
        current = state.get(stat, 0)
        tgt = target.get(stat, 0)
        overshoot = current - tgt
        if overshoot <= 0:
            continue  # trained a stat still under target -- fine
        # Find the most-neglected other stat (largest remaining gap).
        gaps = {s: target.get(s, 0) - state.get(s, 0) for s in STAT_ORDER if s != stat}
        neglected_stat, neglected_gap = max(gaps.items(), key=lambda kv: kv[1])
        if neglected_gap <= 0:
            continue  # everything else is also at/over target -- nothing wasted
        wasted = min(overshoot, neglected_gap)
        out.append(HindsightFlag(
            turn=int(turn.get("turn") or 0),
            stat=stat,
            current=current,
            target=tgt,
            overshoot=overshoot,
            neglected_stat=neglected_stat,
            neglected_gap=neglected_gap,
            wasted=wasted,
            note=(f"trained {stat} ({current}, +{overshoot} over target) while "
                  f"{neglected_stat} was {neglected_gap} short"),
        ))
    return out


def analyze_regret(
    career_log: Optional[Mapping[str, Any]] = None,
    *,
    trace_rows: Optional[List[Mapping[str, Any]]] = None,
    target_stats: Optional[Mapping[str, Any]] = None,
    top_n: int = 5,
) -> RegretReport:
    """Compute decision + hindsight regret for a completed career.

    Decision regret prefers ``trace_rows`` (decision_traces, which carry the
    per-candidate scorer scores) when given; otherwise it falls back to
    candidate scores embedded in the career log's turns (rare). Hindsight
    stat-gap analysis uses the career log's per-turn stat trajectory.
    """
    report = RegretReport()
    report.target_stats = normalize_target_stats(target_stats)
    turns = _turns(career_log or {})

    if trace_rows:
        decision = _decision_regret_from_traces(trace_rows)
    else:
        decision = _decision_regret(turns)
    report.has_candidate_data = bool(decision)
    if decision:
        report.evaluated_turns = len(decision)
        report.decision_regret_total = sum(t.regret for t in decision)
        report.decision_regret_mean = report.decision_regret_total / len(decision)
        report.top_decision_regret = sorted(
            decision, key=lambda t: t.regret, reverse=True
        )[:max(0, top_n)]
    else:
        report.notes.append(
            "No per-turn training_candidate scores available (pass decision_traces "
            "rows for decision-regret). Hindsight stat-gap analysis below uses only "
            "the target build and the recorded stat trajectory."
        )

    if not turns and not trace_rows:
        report.notes.append("No turns or traces found.")
        return report

    hindsight = _hindsight_flags(turns, report.target_stats)
    report.hindsight_flags = sorted(hindsight, key=lambda h: h.wasted, reverse=True)[:max(0, top_n)]
    report.hindsight_wasted_total = sum(h.wasted for h in hindsight)
    return report


# --------------------------------------------------------------------------
# Human-facing rendering -- reusable in the Last Run Report
# --------------------------------------------------------------------------


def regret_summary_lines(report: RegretReport) -> List[str]:
    """Render a compact "where the run was won/lost" section."""
    lines: List[str] = []
    if report.has_candidate_data:
        lines.append(
            f"Decision regret: total {report.decision_regret_total:.1f} over "
            f"{report.evaluated_turns} training turns "
            f"(mean {report.decision_regret_mean:.2f}/turn)."
        )
        if report.top_decision_regret:
            lines.append("Highest-regret turns (a much better option was available):")
            for t in report.top_decision_regret:
                if t.regret <= 0:
                    continue
                lines.append(
                    f"  T{t.turn}: chose {t.chosen_name} ({t.chosen_score:.1f}) "
                    f"-- {t.best_name} scored {t.best_score:.1f} (+{t.regret:.1f})"
                )
    else:
        for note in report.notes:
            lines.append(note)

    if report.hindsight_flags:
        lines.append(
            f"Hindsight: ~{report.hindsight_wasted_total} stat points fed into "
            f"already-capped stats while others lagged. Worst turns:"
        )
        for h in report.hindsight_flags:
            lines.append(f"  T{h.turn}: {h.note} (~{h.wasted} pts recoverable)")
    elif report.hindsight_wasted_total == 0 and report.target_stats:
        lines.append("Hindsight: no significant misallocation against the target build.")
    return lines


def render_report(report: RegretReport) -> str:
    header = "=" * 70 + "\nREGRET REPLAY -- where the run was won / lost\n" + "=" * 70
    body = "\n".join(regret_summary_lines(report)) or "(no findings)"
    return header + "\n" + body


# --------------------------------------------------------------------------
# Convenience I/O (the one impure helper -- everything above is pure)
# --------------------------------------------------------------------------


def load_decision_traces(path: Any) -> List[Dict[str, Any]]:
    """Read a ``decision_traces/<run_id>.jsonl`` file into a list of rows.

    Tolerant of blank/corrupt lines. The trace filename equals the career
    log's ``run_id`` (runtime_settings.run_id / runner_status.run_id).
    """
    from pathlib import Path
    rows: List[Dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        return rows
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = __import__("json").loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows
