#!/usr/bin/env python3
"""Cross-bot career benchmark harness (Idea #1).

Ingests any finished career run -- Icarus's own ``career_log_*.json`` or a
foreign bot's log (e.g. steve1316's uma-android-automation) -- into one
normalised schema, scores it on a fixed set of dimensions, and prints a
leaderboard. The first row of the leaderboard is meant to be the android-vs-
Icarus comparison; every future run drops into the same table.

Dimensions (all higher = better unless noted):

  * stat_achievement  -- % of the target build actually reached (avg over stats)
  * fans_total / fans_per_hour (per-hour needs a runtime; None if unknown)
  * race_win_rate     -- wins / races entered
  * fans_per_turn     -- output efficiency
  * energy_efficiency -- 1 - (rest+recreation+medic turns / total turns)
  * decision_regret   -- mean per-turn regret from regret_replay (lower = better;
                         only when the log carried candidate scores)

A 0..100 ``composite`` blends the normalisable dimensions so runs rank against
each other. The weights are explicit and easy to retune.

Usage
-----
    # One Icarus log vs one android log:
    python scripts/benchmark.py icarus=path/to/career_log.json \
        android=path/to/android_run.json

    # Auto-detect format, whole directory of Icarus logs:
    python scripts/benchmark.py path/to/bot_logs/

    # Tag sources + CSV export:
    python scripts/benchmark.py icarus=a.json android=b.json --csv out.csv

A ``source=path`` token tags the run's source; a bare ``path`` is auto-detected
(``icarus`` when the log has the Icarus ``turns``/``decision_report`` shape,
otherwise ``foreign``).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from career_bot import regret_replay  # noqa: E402
from career_bot.recommended_stats import get_recommended_stats  # noqa: E402

STAT_ORDER = ["speed", "stamina", "power", "guts", "wit"]

# command_id -> stat (training), matching runner.TRAINING_LABELS.
COMMAND_TO_STAT = {
    101: "speed", 102: "power", 103: "guts", 105: "stamina", 106: "wit",
    601: "speed", 602: "stamina", 603: "power", 604: "guts", 605: "wit",
}
# command_type -> coarse action class (runner convention).
REST_LIKE_TYPES = {3, 7, 8}  # 3=recreation, 7=rest, 8=medic

# Composite weights (sum need not be 1; normalised at the end).
COMPOSITE_WEIGHTS = {
    "stat_achievement": 0.40,
    "race_win_rate": 0.25,
    "energy_efficiency": 0.20,
    "fans_per_turn": 0.15,
}
# fans_per_turn is normalised against this reference for the composite.
FANS_PER_TURN_REFERENCE = 1500.0


# --------------------------------------------------------------------------
# Normalised run schema
# --------------------------------------------------------------------------


@dataclass
class NormalizedRun:
    source: str
    label: str
    trainee_name: str = ""
    card_id: int = 0
    scenario_id: int = 0
    final_turn: int = 0
    final_stats: Dict[str, int] = field(default_factory=dict)
    target_stats: Dict[str, int] = field(default_factory=dict)
    final_fans: int = 0
    final_rating: int = 0
    final_rank: str = ""
    runtime_seconds: Optional[float] = None
    races: List[Dict[str, Any]] = field(default_factory=list)
    turns: List[Dict[str, Any]] = field(default_factory=list)  # {turn, action, stat}
    trace_rows: List[Dict[str, Any]] = field(default_factory=list)  # decision_traces
    raw_log: Mapping[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Icarus adapter
# --------------------------------------------------------------------------


def _runner_status(log: Mapping[str, Any]) -> Mapping[str, Any]:
    rs = log.get("runner_status")
    return rs if isinstance(rs, Mapping) else {}


def _icarus_race_results(log: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    rs = _runner_status(log)
    for src in (rs.get("race_results"), log.get("race_results")):
        if isinstance(src, list) and src:
            return [r for r in src if isinstance(r, Mapping)]
    return []


def _icarus_final_stats(log: Mapping[str, Any]) -> Tuple[Dict[str, int], int, int, str]:
    """(stats, fans, rating, rank) from the richest available source."""
    rs = _runner_status(log)
    final_chara = rs.get("final_chara") if isinstance(rs.get("final_chara"), Mapping) else {}
    stats_src = None
    for cand in (rs.get("final_stats"), final_chara.get("stats")):
        if isinstance(cand, Mapping) and cand:
            stats_src = cand
            break
    if stats_src is None:
        # Fall back to the last turn with a stats block.
        for turn in reversed(log.get("turns") or []):
            if isinstance(turn, Mapping) and isinstance(turn.get("stats"), Mapping) and turn["stats"]:
                stats_src = turn["stats"]
                break
    stats = _norm_stats(stats_src or {})
    fans = _first_int(rs.get("final_fans"), final_chara.get("fans"), default=0)
    rating = _first_int(rs.get("final_rating"), final_chara.get("rating"), default=0)
    rank = str(rs.get("final_rank") or final_chara.get("rank") or "")
    return stats, fans, rating, rank


def _icarus_trainee(log: Mapping[str, Any], base_dir: Path) -> Tuple[str, int]:
    rs = _runner_status(log)
    final_chara = rs.get("final_chara") if isinstance(rs.get("final_chara"), Mapping) else {}
    card_id = _first_int(final_chara.get("card_id"), default=0)
    # 1) Walk api_calls for an explicit chara name (works on logs that store it).
    for turn in log.get("turns") or []:
        if not isinstance(turn, Mapping):
            continue
        for call in turn.get("api_calls") or []:
            if not isinstance(call, Mapping) or call.get("direction") != "RES":
                continue
            d = call.get("data") or {}
            payload = d.get("response") if isinstance(d, Mapping) else None
            payload = payload if isinstance(payload, Mapping) else (d if isinstance(d, Mapping) else {})
            ch = payload.get("chara_info") if isinstance(payload, Mapping) else None
            if isinstance(ch, Mapping):
                card_id = card_id or _first_int(ch.get("card_id"), default=0)
                for key in ("trained_chara_name", "chara_name", "name"):
                    name = ch.get(key)
                    if isinstance(name, str) and name.strip():
                        return name.strip(), card_id
    # 2) final_chara title, when present.
    title = str(final_chara.get("title") or "").strip()
    if title:
        return title, card_id
    # 3) Resolve display name from card_id via the character-profile index.
    if card_id:
        name = _name_from_card_id(card_id, _first_int(log.get("scenario_id"), default=0), base_dir)
        if name:
            return name, card_id
    return "", card_id


def _name_from_card_id(card_id: int, scenario_id: int, base_dir: Path) -> str:
    """Best-effort card_id -> display name using the resolved character profile."""
    try:
        from career_bot import character_profiles
        profile = character_profiles.resolve_profile(
            card_id=card_id, scenario_id=scenario_id, base_dir=base_dir)
        if profile and profile.matched_via in ("card_id", "chara_id", "name", "preset"):
            name = str(getattr(profile, "display_name", "") or "").strip()
            if name and name.lower() != "default":
                return name
    except Exception:
        pass
    return ""


def _load_trace_rows(log: Mapping[str, Any], log_path: Optional[Path]) -> List[Dict[str, Any]]:
    """Locate and load the decision_traces file for this run (filename == run_id)."""
    if log_path is None:
        return []
    run_id = ((log.get("runtime_settings") or {}).get("run_id")
              or _runner_status(log).get("run_id"))
    if not run_id:
        return []
    trace_path = Path(log_path).resolve().parent.parent / "decision_traces" / f"{run_id}.jsonl"
    return regret_replay.load_decision_traces(trace_path)


def _icarus_turns(log: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for turn in log.get("turns") or []:
        if not isinstance(turn, Mapping):
            continue
        dr = turn.get("decision_report") if isinstance(turn.get("decision_report"), Mapping) else {}
        payload = dr.get("payload") if isinstance(dr.get("payload"), Mapping) else {}
        ctype = _first_int(payload.get("command_type"), default=0)
        cid = _first_int(payload.get("command_id"), default=0)
        action = str(dr.get("action") or turn.get("selected_action") or "")
        if cid in COMMAND_TO_STAT and ctype not in REST_LIKE_TYPES:
            kind, stat = "train", COMMAND_TO_STAT[cid]
        elif ctype in REST_LIKE_TYPES:
            kind, stat = "rest", ""
        elif action == "race" or payload.get("program_id"):
            kind, stat = "race", ""
        else:
            kind, stat = (action or "other"), ""
        out.append({"turn": _first_int(turn.get("turn"), default=0), "action": kind, "stat": stat})
    return out


def ingest_icarus(log: Mapping[str, Any], label: str, base_dir: Path,
                 log_path: Optional[Path] = None) -> NormalizedRun:
    stats, fans, rating, rank = _icarus_final_stats(log)
    name, card_id = _icarus_trainee(log, base_dir)
    races = []
    for r in _icarus_race_results(log):
        rk = _first_int(r.get("rank"), r.get("final_rank"), default=99)
        races.append({
            "turn": _first_int(r.get("turn"), default=0),
            "name": str(r.get("name") or ""),
            "grade": str(r.get("grade") or ""),
            "rank": rk,
            "won": bool(r.get("won")) or rk == 1,
            "fans": _first_int(r.get("fans"), r.get("fans_gained"), default=0),
        })
    return NormalizedRun(
        source="icarus",
        label=label,
        trainee_name=name,
        card_id=card_id,
        scenario_id=_first_int(log.get("scenario_id"), default=0),
        final_turn=_first_int(log.get("final_turn"), _runner_status(log).get("turn"), default=len(log.get("turns") or [])),
        final_stats=stats,
        target_stats=_resolve_target(base_dir, name),
        final_fans=fans,
        final_rating=rating,
        final_rank=rank,
        runtime_seconds=_icarus_runtime(log),
        races=races,
        turns=_icarus_turns(log),
        trace_rows=_load_trace_rows(log, log_path),
        raw_log=log,
    )


def _icarus_runtime(log: Mapping[str, Any]) -> Optional[float]:
    start = log.get("started_at")
    end = log.get("ended_at")
    if isinstance(start, str) and isinstance(end, str):
        try:
            from datetime import datetime
            fmt = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
            return max(0.0, (fmt(end) - fmt(start)).total_seconds())
        except Exception:
            return None
    return None


# --------------------------------------------------------------------------
# Foreign adapter -- documented minimal schema
# --------------------------------------------------------------------------

FOREIGN_SCHEMA_DOC = """
Foreign (non-Icarus) logs are normalised from this minimal JSON shape. Map a
bot's own export into it once and every future run benchmarks for free:

{
  "trainee_name": "Oguri Cap",
  "scenario_id": 0,
  "final_turn": 78,
  "final_stats": {"speed":1200,"stamina":700,"power":1000,"guts":500,"wit":900},
  "final_fans": 120000,
  "final_rating": 17000,
  "final_rank": "SS",
  "runtime_seconds": 5400,                      # optional, enables fans/hour
  "races": [ {"turn":12,"name":"...","grade":"G1","rank":1,"fans":8000}, ... ],
  "turns": [ {"turn":1,"action":"train","stat":"speed"}, ... ]  # optional
}

Only final_stats + races are needed for most dimensions; turns enables the
energy-efficiency dimension; runtime_seconds enables fans/hour. Unknown fields
are ignored; missing ones degrade gracefully.
""".strip()


def ingest_foreign(payload: Mapping[str, Any], label: str, base_dir: Path,
                  source: str = "foreign") -> NormalizedRun:
    name = str(payload.get("trainee_name") or payload.get("trainee") or "")
    races = []
    for r in payload.get("races") or []:
        if not isinstance(r, Mapping):
            continue
        rk = _first_int(r.get("rank"), r.get("placement"), default=99)
        races.append({
            "turn": _first_int(r.get("turn"), default=0),
            "name": str(r.get("name") or ""),
            "grade": str(r.get("grade") or ""),
            "rank": rk,
            "won": bool(r.get("won")) or rk == 1,
            "fans": _first_int(r.get("fans"), default=0),
        })
    turns = []
    for t in payload.get("turns") or []:
        if isinstance(t, Mapping):
            turns.append({
                "turn": _first_int(t.get("turn"), default=0),
                "action": str(t.get("action") or "other"),
                "stat": str(t.get("stat") or ""),
            })
    return NormalizedRun(
        source=source,
        label=label,
        trainee_name=name,
        card_id=_first_int(payload.get("card_id"), default=0),
        scenario_id=_first_int(payload.get("scenario_id"), default=0),
        final_turn=_first_int(payload.get("final_turn"), default=len(turns)),
        final_stats=_norm_stats(payload.get("final_stats") or {}),
        target_stats=_resolve_target(base_dir, name),
        final_fans=_first_int(payload.get("final_fans"), default=0),
        final_rating=_first_int(payload.get("final_rating"), default=0),
        final_rank=str(payload.get("final_rank") or ""),
        runtime_seconds=_opt_float(payload.get("runtime_seconds")),
        races=races,
        turns=turns,
        raw_log=payload,
    )


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _norm_stats(stats: Mapping[str, Any]) -> Dict[str, int]:
    def _int(*keys: str) -> int:
        for k in keys:
            v = stats.get(k)
            if v is None:
                v = stats.get(k.title())
            if isinstance(v, (int, float)):
                return int(v)
        return 0
    return {
        "speed": _int("speed"),
        "stamina": _int("stamina"),
        "power": _int("power", "pow"),
        "guts": _int("guts"),
        "wit": _int("wit", "wiz", "wisdom"),
    }


def _first_int(*values: Any, default: int = 0) -> int:
    for v in values:
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str) and v.strip().lstrip("-").isdigit():
            return int(v)
    return default


def _opt_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _resolve_target(base_dir: Path, trainee_name: str) -> Dict[str, int]:
    raw = get_recommended_stats(base_dir, trainee_name or "")
    return regret_replay.normalize_target_stats(raw)


def is_icarus_log(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    if not isinstance(payload.get("turns"), list):
        return False
    for turn in payload["turns"]:
        if isinstance(turn, Mapping) and ("decision_report" in turn or "api_calls" in turn):
            return True
    # An Icarus log with the report skeleton but sparse turns still has these.
    return any(k in payload for k in ("runner_status", "decision_reasoning", "preset_name"))


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def score_run(run: NormalizedRun) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}

    # Stat achievement: avg over stats of min(final/target, 1).
    target = run.target_stats or regret_replay.DEFAULT_TARGET_STATS
    ratios = []
    for s in STAT_ORDER:
        tgt = target.get(s, 0)
        if tgt > 0:
            ratios.append(min(1.0, run.final_stats.get(s, 0) / tgt))
    metrics["stat_achievement"] = round(100.0 * sum(ratios) / len(ratios), 1) if ratios else 0.0
    metrics["total_stats"] = sum(run.final_stats.get(s, 0) for s in STAT_ORDER)

    # Races.
    n_races = len(run.races)
    n_wins = sum(1 for r in run.races if r.get("won"))
    metrics["race_count"] = n_races
    metrics["race_wins"] = n_wins
    metrics["race_win_rate"] = round(100.0 * n_wins / n_races, 1) if n_races else None

    # Fans throughput.
    metrics["fans_total"] = run.final_fans
    metrics["fans_per_turn"] = round(run.final_fans / run.final_turn, 1) if run.final_turn else None
    if run.runtime_seconds and run.runtime_seconds > 0:
        metrics["fans_per_hour"] = round(run.final_fans / (run.runtime_seconds / 3600.0), 1)
        metrics["runtime_hours"] = round(run.runtime_seconds / 3600.0, 2)
    else:
        metrics["fans_per_hour"] = None
        metrics["runtime_hours"] = None

    # Energy efficiency: fraction of turns spent NOT resting/recovering.
    if run.turns:
        rest = sum(1 for t in run.turns if t.get("action") == "rest")
        metrics["rest_turns"] = rest
        metrics["energy_efficiency"] = round(100.0 * (1.0 - rest / len(run.turns)), 1)
    else:
        metrics["rest_turns"] = None
        metrics["energy_efficiency"] = None

    # Decision regret -- prefer decision_traces (carry candidate scores), fall
    # back to candidate scores embedded in the log.
    regret = regret_replay.analyze_regret(
        run.raw_log, trace_rows=run.trace_rows or None, target_stats=run.target_stats)
    if regret.has_candidate_data:
        metrics["decision_regret_mean"] = round(regret.decision_regret_mean, 2)
    else:
        metrics["decision_regret_mean"] = None
    metrics["hindsight_wasted"] = regret.hindsight_wasted_total

    metrics["composite"] = _composite(metrics)
    return metrics


def _composite(metrics: Mapping[str, Any]) -> float:
    """Blend normalisable dimensions into a 0..100 score over present terms."""
    parts: List[Tuple[float, float]] = []  # (weight, value 0..100)
    sa = metrics.get("stat_achievement")
    if sa is not None:
        parts.append((COMPOSITE_WEIGHTS["stat_achievement"], sa))
    wr = metrics.get("race_win_rate")
    if wr is not None:
        parts.append((COMPOSITE_WEIGHTS["race_win_rate"], wr))
    ee = metrics.get("energy_efficiency")
    if ee is not None:
        parts.append((COMPOSITE_WEIGHTS["energy_efficiency"], ee))
    fpt = metrics.get("fans_per_turn")
    if fpt is not None:
        parts.append((COMPOSITE_WEIGHTS["fans_per_turn"],
                      min(100.0, 100.0 * fpt / FANS_PER_TURN_REFERENCE)))
    if not parts:
        return 0.0
    total_w = sum(w for w, _ in parts)
    return round(sum(w * v for w, v in parts) / total_w, 1)


# --------------------------------------------------------------------------
# Loading / leaderboard
# --------------------------------------------------------------------------


def load_run(path: Path, source: str, base_dir: Path) -> Optional[NormalizedRun]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  skipped {path.name}: {exc}", file=sys.stderr)
        return None
    label = path.stem
    if source == "auto":
        source = "icarus" if is_icarus_log(payload) else "foreign"
    if source == "icarus":
        return ingest_icarus(payload, label, base_dir, log_path=path)
    return ingest_foreign(payload, label, base_dir, source=source)


def _fmt(v: Any, suffix: str = "") -> str:
    if v is None:
        return "  n/a"
    if isinstance(v, float):
        return f"{v:.1f}{suffix}"
    return f"{v}{suffix}"


def print_leaderboard(rows: List[Tuple[NormalizedRun, Dict[str, Any]]]) -> None:
    rows = sorted(rows, key=lambda rm: rm[1].get("composite", 0.0), reverse=True)
    print("=" * 92)
    print("CAREER BENCHMARK LEADERBOARD")
    print("=" * 92)
    header = (f"{'#':>2} {'source':<9} {'label':<22} {'comp':>5} {'stat%':>6} "
              f"{'win%':>6} {'fans/h':>9} {'f/turn':>7} {'enrg%':>6} {'regret':>7}")
    print(header)
    print("-" * 92)
    for i, (run, m) in enumerate(rows, 1):
        print(f"{i:>2} {run.source:<9} {run.label[:22]:<22} "
              f"{_fmt(m.get('composite')):>5} {_fmt(m.get('stat_achievement')):>6} "
              f"{_fmt(m.get('race_win_rate')):>6} {_fmt(m.get('fans_per_hour')):>9} "
              f"{_fmt(m.get('fans_per_turn')):>7} {_fmt(m.get('energy_efficiency')):>6} "
              f"{_fmt(m.get('decision_regret_mean')):>7}")
    print("-" * 92)
    # Per-run detail.
    for run, m in rows:
        print(f"\n  {run.source}:{run.label}  trainee={run.trainee_name or '?'} "
              f"turns={run.final_turn} scenario={run.scenario_id}")
        print(f"    final stats: " + " ".join(
            f"{s.title()}={run.final_stats.get(s, 0)}/{run.target_stats.get(s, 0)}" for s in STAT_ORDER))
        print(f"    races: {m.get('race_count')} (wins {m.get('race_wins')}), "
              f"fans {m.get('fans_total')}, rating {run.final_rating}, rank {run.final_rank or '?'}")
        if m.get("decision_regret_mean") is None:
            print("    decision regret: n/a (log has no per-turn candidate scores)")
        if m.get("hindsight_wasted"):
            print(f"    hindsight: ~{m.get('hindsight_wasted')} stat pts into capped stats")


CSV_FIELDS = [
    "source", "label", "trainee_name", "scenario_id", "final_turn", "composite",
    "stat_achievement", "total_stats", "race_count", "race_wins", "race_win_rate",
    "fans_total", "fans_per_turn", "fans_per_hour", "energy_efficiency",
    "decision_regret_mean", "hindsight_wasted", "final_rating", "final_rank",
]


def emit_csv(rows: List[Tuple[NormalizedRun, Dict[str, Any]]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for run, m in rows:
            row = {k: m.get(k) for k in CSV_FIELDS}
            row.update({
                "source": run.source, "label": run.label,
                "trainee_name": run.trainee_name, "scenario_id": run.scenario_id,
                "final_turn": run.final_turn, "final_rating": run.final_rating,
                "final_rank": run.final_rank,
            })
            writer.writerow(row)
    print(f"\nCSV written to {path}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _expand_target(token: str) -> List[Tuple[str, Path]]:
    """Parse a CLI token into (source, path) pairs. ``source=path`` tags the
    source; a directory expands to its career_log_*.json files."""
    source = "auto"
    raw = token
    if "=" in token and not Path(token).exists():
        source, raw = token.split("=", 1)
    p = Path(raw).expanduser()
    if p.is_dir():
        return [(source, f) for f in sorted(p.glob("career_log_*.json"))]
    return [(source, p)]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark career runs (Icarus or foreign) on a common scale.",
        epilog=FOREIGN_SCHEMA_DOC, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="+",
                        help="log files or dirs; prefix with 'source=' to tag (e.g. android=run.json)")
    parser.add_argument("--csv", help="write the leaderboard to this CSV path", default=None)
    parser.add_argument("--base-dir", default=str(REPO_ROOT),
                        help="project root used to resolve target stat builds")
    args = parser.parse_args(argv)

    base_dir = Path(args.base_dir).expanduser().resolve()
    pairs: List[Tuple[str, Path]] = []
    for token in args.targets:
        pairs.extend(_expand_target(token))
    if not pairs:
        print("No logs found.", file=sys.stderr)
        return 1

    rows: List[Tuple[NormalizedRun, Dict[str, Any]]] = []
    for source, path in pairs:
        run = load_run(path, source, base_dir)
        if run is None:
            continue
        rows.append((run, score_run(run)))
    if not rows:
        print("No runs could be ingested.", file=sys.stderr)
        return 1

    print_leaderboard(rows)
    if args.csv:
        emit_csv(sorted(rows, key=lambda rm: rm[1].get("composite", 0.0), reverse=True),
                 Path(args.csv).expanduser().resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
