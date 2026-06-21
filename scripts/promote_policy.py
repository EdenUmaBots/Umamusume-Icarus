#!/usr/bin/env python3
"""Live-policy promotion review + guarded promote (Idea #3).

Icarus already runs a closed self-improvement loop: every finished career is
appended to the AI dataset, ``ai_trainer.train_once`` rebuilds the models on a
schedule, and each train emits shadow-mode + backtest A/B reports plus a
``live_policy_recommendation``. The one missing piece is a clean, **manual-
approve** surface to read that A/B and flip the promotion switch -- live policy
stays OFF (``enable_live_policy_assistance``) until a human says go.

This tool is that surface:

  * default (no flags)  -- print the A/B review: current state, the
    recommendation (ENABLE / KEEP DISABLED + reasons), shadow precision, and
    backtest capture / false-warning rates.
  * ``--promote``       -- flip ``enable_live_policy_assistance`` ON, but ONLY
    if the recommendation says ENABLE. Refuses otherwise unless ``--force``.
  * ``--demote``        -- flip it back OFF (always allowed).

It changes nothing about the training pipeline itself -- it only gates the
promotion decision the loop deliberately leaves to you.

Usage
-----
    python scripts/promote_policy.py                 # review only
    python scripts/promote_policy.py --promote       # promote if recommended
    python scripts/promote_policy.py --promote --force
    python scripts/promote_policy.py --demote
    python scripts/promote_policy.py --base-dir /path/to/runtime
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from career_bot import ai_trainer  # noqa: E402


# --------------------------------------------------------------------------
# Pure decision + rendering (no I/O -- unit-testable)
# --------------------------------------------------------------------------


def promotion_decision(recommendation: Mapping[str, Any], *, force: bool = False) -> Dict[str, Any]:
    """Decide whether a promotion is allowed.

    Manual-approve policy: only allow when the loop's own
    ``live_policy_recommendation`` says ENABLE -- unless ``--force`` overrides.
    """
    recommend = bool(recommendation.get("recommend_enable"))
    already = bool(recommendation.get("enabled"))
    if already:
        return {"allow": False, "action": "noop",
                "reason": "Live policy assistance is already enabled."}
    if recommend:
        return {"allow": True, "action": "promote",
                "reason": "Recommendation is ENABLE; promoting."}
    if force:
        return {"allow": True, "action": "promote_forced",
                "reason": "Recommendation is KEEP DISABLED, but --force was given."}
    return {"allow": False, "action": "blocked",
            "reason": "Recommendation is KEEP DISABLED. Use --force to override."}


def render_review(status: Mapping[str, Any], shadow: Mapping[str, Any],
                 backtest: Mapping[str, Any]) -> str:
    live = status.get("live_policy") or {}
    rec = live.get("recommendation") or {}
    cfg = status.get("auto_config") or {}
    ds = status.get("dataset_status") or {}

    lines: List[str] = []
    lines.append("=" * 74)
    lines.append("LIVE-POLICY PROMOTION REVIEW")
    lines.append("=" * 74)

    state = "ENABLED" if live.get("enabled") else "DISABLED"
    requested = "yes" if live.get("requested_enabled") else "no"
    lines.append(f"Current live policy: {state}   (flag requested_enabled={requested})")
    lines.append(f"Learned adjustments: races={live.get('race_adjustments', 0)} "
                 f"items={live.get('item_adjustments', 0)} events={live.get('event_adjustments', 0)} "
                 f"@ confidence>= {live.get('confidence_threshold')}")

    # Dataset coverage.
    counts = ds.get("counts") or ds.get("rows") or {}
    if isinstance(counts, Mapping) and counts:
        td = counts.get("turn_decisions")
        cs = counts.get("career_summaries")
        lines.append(f"Dataset: turn_decisions={td}  career_summaries={cs}")

    lines.append("")
    verdict = "ENABLE" if rec.get("recommend_enable") else "KEEP DISABLED"
    lines.append(f">>> RECOMMENDATION: {verdict}")
    if rec.get("message"):
        lines.append(f"    {rec['message']}")
    reasons = rec.get("reasons") or []
    if reasons:
        lines.append("    Blocking reasons:")
        for r in reasons:
            lines.append(f"      - {r}")

    # Shadow A/B.
    lines.append("")
    lines.append("Shadow-mode A/B (what the model WOULD have warned, vs reality):")
    if shadow.get("success"):
        # Real artifact keys: warnings / useful_warnings / false_alarms.
        useful = shadow.get("useful_warnings", shadow.get("true_warnings"))
        false_alarms = shadow.get("false_alarms", shadow.get("false_warnings"))
        lines.append(f"    precision={_pct(shadow.get('precision'))}  "
                     f"evaluated={shadow.get('evaluated_races', shadow.get('evaluated'))}  "
                     f"warnings={shadow.get('warnings')}  "
                     f"useful={useful}  false_alarms={false_alarms}")
    else:
        lines.append(f"    {shadow.get('detail', 'n/a')}")

    # Backtest.
    lines.append("Backtest (historical race capture / false-warning rates):")
    if backtest.get("success"):
        races = backtest.get("historical_race_rows", backtest.get("races", backtest.get("race_count")))
        lines.append(f"    capture_rate={_pct(backtest.get('capture_rate'))}  "
                     f"false_warning_rate={_pct(backtest.get('false_warning_rate'))}  "
                     f"races={races}  risk_warnings={backtest.get('risk_warnings')}")
    else:
        lines.append(f"    {backtest.get('detail', 'n/a')}")

    lines.append("")
    if rec.get("recommend_enable") and not live.get("enabled"):
        lines.append("Action: run with --promote to enable live policy assistance.")
    elif live.get("enabled"):
        lines.append("Action: already enabled. Run with --demote to turn it back off.")
    else:
        lines.append("Action: not recommended yet. Collect more data, or --promote --force to override.")
    return "\n".join(lines)


def _pct(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value * 100:.0f}%"
    return "n/a"


# --------------------------------------------------------------------------
# I/O wrappers
# --------------------------------------------------------------------------


def gather(base_dir: Any) -> Dict[str, Any]:
    return {
        "status": ai_trainer.trainer_status(base_dir),
        "shadow": ai_trainer.latest_shadow_report(base_dir),
        "backtest": ai_trainer.latest_backtest_report(base_dir),
    }


def apply_promotion(base_dir: Any, *, force: bool = False,
                   recommendation: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Promote live policy if allowed. Returns the decision + resulting flag."""
    if recommendation is None:
        status = ai_trainer.trainer_status(base_dir)
        recommendation = (status.get("live_policy") or {}).get("recommendation") or {}
    decision = promotion_decision(recommendation, force=force)
    if decision["allow"]:
        cfg = ai_trainer.save_auto_config(base_dir, {"enable_live_policy_assistance": True})
        decision["enabled_now"] = bool(cfg.get("enable_live_policy_assistance"))
    else:
        decision["enabled_now"] = bool(recommendation.get("enabled"))
    return decision


def apply_demotion(base_dir: Any) -> Dict[str, Any]:
    cfg = ai_trainer.save_auto_config(base_dir, {"enable_live_policy_assistance": False})
    return {"allow": True, "action": "demote",
            "reason": "Live policy assistance disabled.",
            "enabled_now": bool(cfg.get("enable_live_policy_assistance"))}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Review and gate live-policy promotion.")
    parser.add_argument("--base-dir", default=str(REPO_ROOT),
                        help="runtime/project root (defaults to repo root)")
    parser.add_argument("--promote", action="store_true", help="enable live policy if recommended")
    parser.add_argument("--demote", action="store_true", help="disable live policy")
    parser.add_argument("--force", action="store_true", help="promote even if not recommended")
    args = parser.parse_args(argv)

    base_dir = Path(args.base_dir).expanduser().resolve()

    if args.demote:
        result = apply_demotion(base_dir)
        print(f"{result['action']}: {result['reason']} (enabled_now={result['enabled_now']})")
        return 0

    if args.promote:
        result = apply_promotion(base_dir, force=args.force)
        print(f"{result['action']}: {result['reason']}")
        print(f"live policy enabled_now = {result['enabled_now']}")
        if not result["allow"]:
            # Show the review so the user sees why it was blocked.
            data = gather(base_dir)
            print()
            print(render_review(data["status"], data["shadow"], data["backtest"]))
            return 2
        return 0

    # Default: review only.
    data = gather(base_dir)
    print(render_review(data["status"], data["shadow"], data["backtest"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
