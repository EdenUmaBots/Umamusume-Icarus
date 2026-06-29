"""Local AI-advisor scaffolding for Pre Icarus.

This module does not call an external LLM.  It reads AI-ready datasets and local
advisor statistics, then produces deterministic post-run recommendations and
small scoring hints.

History:
  - v1: Point-estimate ``win_rate = wins/starts`` with a ``-8.0`` magic-number
    penalty when ``starts >= 3 and win_rate < 0.5``; string ``confidence``
    buckets at 3/8 starts.
  - v2 (this build): Beta-Binomial posterior over win rate with a weakly
    informative prior centred on the global program base rate.  The
    ``adjustment`` is computed as ``avg_reward * lcb`` so the penalty is
    smooth in win rate and properly accounts for small-sample uncertainty.
    The ``confidence`` string is retained for backward compatibility (call
    sites in ``runner.py`` consume it) but is now derived from the posterior
    variance rather than a hard starts threshold.

The legacy return shape of ``race_program_hint`` is preserved.  New richer
fields (alpha, beta, lcb, ucb, posterior_mean, variance) are *added* to the
returned dict so downstream consumers can opt in incrementally without any
existing code path breaking.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from career_bot.ai_dataset import runtime_output_root, safe_float, safe_int
from career_bot.ai_modeling import (
    BetaPosterior,
    HierarchicalLevel,
    global_base_rate,
    hierarchical_posterior,
    posterior_from_stats_bucket,
    score_program,
)


# ---------------------------------------------------------------------------
# File-IO helpers (unchanged from v1)
# ---------------------------------------------------------------------------


def ai_root(base_dir: Any) -> Path:
    return runtime_output_root(base_dir) / "ai"


def load_advisor_stats(base_dir: Any) -> Dict[str, Any]:
    path = ai_root(base_dir) / "advisor_stats.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def latest_manifest(base_dir: Any) -> Dict[str, Any]:
    path = ai_root(base_dir) / "latest_export_manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def data_health(base_dir: Any) -> Dict[str, Any]:
    path = ai_root(base_dir) / "ai_data_health.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Calibrator persistence + application (v5.43.1)
# ---------------------------------------------------------------------------

# Module-level mtime cache so the calibrator JSON isn't re-parsed on every
# hint call.  Hot-reloads automatically when the file is rewritten.
_CALIBRATOR_CACHE: Dict[str, Any] = {"path": None, "mtime": 0.0, "instance": None}


def calibrator_path(base_dir: Any) -> Path:
    return ai_root(base_dir) / "isotonic_calibrator.json"


def load_calibrator(base_dir: Any):
    """Return the persisted ``IsotonicCalibrator`` for this runtime, or ``None``.

    Missing file -> ``None`` (silent, common case).
    Corrupt file -> ``None`` (logged at debug, never raises).
    """
    from career_bot.calibration import IsotonicCalibrator  # local: avoid import cycle

    path = calibrator_path(base_dir)
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        _CALIBRATOR_CACHE.update(path=str(path), mtime=0.0, instance=None)
        return None
    except Exception:
        return None

    cached_path = _CALIBRATOR_CACHE.get("path")
    cached_mtime = _CALIBRATOR_CACHE.get("mtime") or 0.0
    if cached_path == str(path) and cached_mtime == mtime:
        return _CALIBRATOR_CACHE.get("instance")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        instance = IsotonicCalibrator.from_dict(payload)
    except Exception:
        _CALIBRATOR_CACHE.update(path=str(path), mtime=mtime, instance=None)
        return None

    _CALIBRATOR_CACHE.update(path=str(path), mtime=mtime, instance=instance)
    return instance


def _apply_calibration_to_hint(hint: Dict[str, Any], calibrator) -> Dict[str, Any]:
    """Mutate ``hint`` in place to add calibrated fields and update ``adjustment``.

    The isotonic mapping is applied uniformly to ``posterior_mean``, ``lcb``,
    and ``ucb`` -- it maps "what the model predicts" to "what the empirical
    rate actually is", and is meaningful at every quantile, not just the mean.

    When no calibrator is present this function is a no-op and returns ``hint``
    unchanged.  When applied, the existing ``adjustment`` is overwritten with
    ``avg_reward * calibrated_lcb`` so the live decision path uses the
    corrected estimate.  The raw values stay available under ``raw_*`` keys
    for diagnostics and the dashboard.
    """
    if calibrator is None:
        hint["calibration_active"] = False
        return hint

    try:
        calibrated_mean = float(calibrator.transform_one(hint.get("posterior_mean", 0.0)))
        calibrated_lcb = float(calibrator.transform_one(hint.get("lcb", 0.0)))
        calibrated_ucb = float(calibrator.transform_one(hint.get("ucb", 0.0)))
    except Exception:
        hint["calibration_active"] = False
        return hint

    avg_reward = float(hint.get("avg_reward", 0.0))

    hint["raw_adjustment"] = hint["adjustment"]
    hint["raw_posterior_mean"] = hint["posterior_mean"]
    hint["raw_lcb"] = hint["lcb"]
    hint["raw_ucb"] = hint["ucb"]

    hint["calibrated_mean"] = round(calibrated_mean, 4)
    hint["calibrated_lcb"] = round(calibrated_lcb, 4)
    hint["calibrated_ucb"] = round(calibrated_ucb, 4)
    hint["adjustment"] = round(avg_reward * calibrated_lcb, 4)
    hint["calibration_active"] = True
    return hint


# ---------------------------------------------------------------------------
# Confidence labelling — variance-driven, but consistent with old buckets
# ---------------------------------------------------------------------------


def _confidence_label(starts: int, posterior: BetaPosterior) -> str:
    """Map the posterior variance to a label that means roughly the same
    thing as the old ``high/medium/low/none`` buckets.

    The variance of a Beta(alpha, beta) collapses as the count grows.  These
    thresholds were chosen so that:
      - starts == 0      -> "none"   (prior only)
      - starts in 1..2   -> "low"
      - starts in 3..7   -> "medium" (matches old bucket)
      - starts >= 8      -> "high"   (matches old bucket)
    while *also* responding to extreme prior/posterior mismatches.
    """
    if starts <= 0:
        return "none"
    std = posterior.variance() ** 0.5
    if std >= 0.18:
        return "low"
    if std >= 0.11:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# race_program_hint — backward-compatible signature, new math
# ---------------------------------------------------------------------------


def race_program_hint(base_dir: Any, program_id: Any) -> Dict[str, Any]:
    """Return a scoring hint for a single race program.

    Preserved fields (so existing call sites keep working):
      ``program_id``, ``confidence``, ``starts``, ``win_rate``,
      ``avg_reward``, ``adjustment``, ``reason``

    Added fields (opt-in for new consumers):
      ``lcb``, ``ucb``, ``posterior_mean``, ``variance``, ``alpha``, ``beta``
    """
    stats = load_advisor_stats(base_dir)
    race_programs = stats.get("race_programs") or {}
    key = str(safe_int(program_id))
    bucket = race_programs.get(key) or {}
    starts = safe_int(bucket.get("starts"))

    base_rate = global_base_rate(race_programs, min_total_starts=10, fallback=0.5)
    prior = BetaPosterior.from_prior(prior_mean=base_rate, prior_strength=4.0)

    if starts <= 0:
        # No observations -> hint is just the prior.  Adjustment is zero so
        # the heuristic score passes through untouched.
        return {
            "program_id": safe_int(program_id),
            "confidence": "none",
            "starts": 0,
            "win_rate": 0.0,
            "avg_reward": 0.0,
            "adjustment": 0.0,
            "reason": "No local AI race data yet.",
            "posterior_mean": round(prior.mean(), 4),
            "lcb": round(prior.lcb(0.25), 4),
            "ucb": round(prior.ucb(0.75), 4),
            "variance": round(prior.variance(), 6),
            "alpha": round(prior.alpha, 4),
            "beta": round(prior.beta, 4),
        }

    posterior = posterior_from_stats_bucket(bucket, prior=prior)
    avg_reward = safe_float(bucket.get("avg_reward"), 0.0)
    scoring = score_program(posterior, avg_reward, risk_quantile=0.25)

    win_rate = safe_float(bucket.get("win_rate"))
    if win_rate == 0.0 and starts > 0:
        # Fall back to raw rate if stats lacked the precomputed field.
        wins = bucket.get("wins")
        if wins is not None:
            win_rate = safe_float(wins) / max(1, starts)

    hint = {
        "program_id": safe_int(program_id),
        "confidence": _confidence_label(starts, posterior),
        "starts": starts,
        "win_rate": round(win_rate, 4),
        "avg_reward": round(avg_reward, 4),
        "adjustment": scoring["adjustment"],
        "reason": "Local advisor learned this race from prior Pre Icarus outcomes.",
        "posterior_mean": scoring["mean"],
        "lcb": scoring["lcb"],
        "ucb": scoring["ucb"],
        "variance": scoring["variance"],
        "alpha": scoring["alpha"],
        "beta": scoring["beta"],
    }
    return _apply_calibration_to_hint(hint, load_calibrator(base_dir))


# ---------------------------------------------------------------------------
# hierarchical_race_program_hint — Sprint 2, opt-in context-aware variant
# ---------------------------------------------------------------------------


def _hierarchical_levels(
    stats: Mapping[str, Any],
    program_id: int,
    scenario_id: Optional[int],
    preset_name: Optional[str],
    turn: Optional[int],
):
    """Build the (name, key, stats-bucket) chain for hierarchical_posterior.

    Returns a list of ``HierarchicalLevel`` from least to most specific.
    Levels whose key components are missing are still emitted with
    ``stats=None`` so the diagnostic output remains stable; the walker
    skips them at runtime.
    """
    context = stats.get("race_programs_context") or {}
    pid_key = str(safe_int(program_id))

    by_program = (context.get("by_program") or {}).get(pid_key)
    by_program_scenario = None
    by_program_scenario_preset = None
    by_program_scenario_preset_phase = None

    if scenario_id is not None:
        sid_key = f"{pid_key}:{safe_int(scenario_id)}"
        by_program_scenario = (context.get("by_program_scenario") or {}).get(sid_key)

        if preset_name:
            preset_key = f"{sid_key}:{preset_name}"
            by_program_scenario_preset = (
                context.get("by_program_scenario_preset") or {}
            ).get(preset_key)

            if turn is not None:
                from career_bot.ai_dataset import _turn_phase  # local import
                phase_key = f"{preset_key}:{_turn_phase(safe_int(turn))}"
                by_program_scenario_preset_phase = (
                    context.get("by_program_scenario_preset_phase") or {}
                ).get(phase_key)

    return [
        HierarchicalLevel("program", pid_key, by_program),
        HierarchicalLevel("program_scenario", scenario_id, by_program_scenario),
        HierarchicalLevel("program_scenario_preset", preset_name, by_program_scenario_preset),
        HierarchicalLevel("program_scenario_preset_phase", turn, by_program_scenario_preset_phase),
    ]


def hierarchical_race_program_hint(
    base_dir: Any,
    program_id: Any,
    scenario_id: Any = None,
    preset_name: Optional[str] = None,
    turn: Any = None,
    parent_discount: float = 0.5,
    risk_quantile: float = 0.25,
) -> Dict[str, Any]:
    """Context-aware race-program hint.

    Walks the hierarchy ``program -> program+scenario -> program+scenario+preset
    -> program+scenario+preset+phase`` and pools observations via
    ``hierarchical_posterior``.  Falls back gracefully to ``race_program_hint``
    semantics when the v2 context buckets are missing (older stats file) or
    when the caller omits context components.

    Return shape matches ``race_program_hint`` plus:
      - ``contributed_levels`` -- list of level names that supplied data
      - ``levels`` -- per-level (name, starts) diagnostic for the dashboard
    """
    stats = load_advisor_stats(base_dir)

    # Backward-compat: if no v2 context, fall through to the flat hint.
    if "race_programs_context" not in stats:
        out = race_program_hint(base_dir, program_id)
        out["contributed_levels"] = ["program"] if out.get("starts", 0) > 0 else []
        out["levels"] = []
        return out

    race_programs = stats.get("race_programs") or {}
    base_rate = global_base_rate(race_programs, min_total_starts=10, fallback=0.5)

    levels = _hierarchical_levels(
        stats,
        safe_int(program_id),
        None if scenario_id is None else safe_int(scenario_id),
        preset_name or None,
        None if turn is None else safe_int(turn),
    )

    posterior, contributed = hierarchical_posterior(
        levels,
        prior_mean=base_rate,
        prior_strength=4.0,
        parent_discount=parent_discount,
    )

    # Pick the avg_reward from the most specific contributing level (falls
    # back to the flat race_programs bucket if no context level matched).
    avg_reward = 0.0
    starts_total = 0
    for level in reversed(levels):
        if level.stats:
            avg_reward = safe_float(level.stats.get("avg_reward"), 0.0)
            starts_total = safe_int(level.stats.get("starts"))
            break
    if starts_total == 0:
        flat = race_programs.get(str(safe_int(program_id))) or {}
        avg_reward = safe_float(flat.get("avg_reward"), 0.0)
        starts_total = safe_int(flat.get("starts"))

    scoring = score_program(posterior, avg_reward, risk_quantile=risk_quantile)

    hint = {
        "program_id": safe_int(program_id),
        "confidence": _confidence_label(starts_total, posterior),
        "starts": starts_total,
        "win_rate": round(posterior.mean(), 4),  # posterior mean replaces raw rate
        "avg_reward": round(avg_reward, 4),
        "adjustment": scoring["adjustment"],
        "reason": (
            f"Hierarchical advisor pooled across {len(contributed)} level(s): "
            f"{', '.join(contributed) or 'prior only'}."
        ),
        "posterior_mean": scoring["mean"],
        "lcb": scoring["lcb"],
        "ucb": scoring["ucb"],
        "variance": scoring["variance"],
        "alpha": scoring["alpha"],
        "beta": scoring["beta"],
        "contributed_levels": contributed,
        "levels": [
            {
                "name": level.name,
                "starts": safe_int((level.stats or {}).get("starts")) if level.stats else 0,
            }
            for level in levels
        ],
    }
    return _apply_calibration_to_hint(hint, load_calibrator(base_dir))





def post_run_advice(base_dir: Any) -> Dict[str, Any]:
    """Return a compact, user-readable advisor report from local datasets."""
    stats = load_advisor_stats(base_dir)
    manifest = latest_manifest(base_dir)
    actions = stats.get("actions") or {}
    races = stats.get("race_programs") or {}
    health = data_health(base_dir)

    base_rate = global_base_rate(races, min_total_starts=10, fallback=0.5)
    prior = BetaPosterior.from_prior(prior_mean=base_rate, prior_strength=4.0)

    tips = []
    if health and not health.get("safe_for_live_policy", True):
        tips.append({
            "priority": "high",
            "area": "AI Data Health",
            "message": "AI live policy was disabled because race actions did not have extracted race results. Rebuild the dataset after the parser repair.",
            "examples": health.get("warnings") or [],
        })

    race_bucket = actions.get("race") or {}
    rest_bucket = actions.get("rest") or actions.get("recreate") or {}
    if safe_int(race_bucket.get("count")) and safe_float(race_bucket.get("avg_reward")) < 0:
        tips.append({
            "priority": "high",
            "area": "Smart Race Solver",
            "message": "Recent race decisions have negative average reward. Inspect failed planned races and long-distance risk.",
        })
    if safe_int(rest_bucket.get("count")) >= 5:
        tips.append({
            "priority": "medium",
            "area": "Training / Item Use",
            "message": "Rest/recreation is frequent in the dataset. Item and recovery planning may need more weight.",
        })

    # Risky programs are now identified by posterior LCB rather than raw win rate.
    # This correctly flags low-confidence cells (small samples) without the
    # arbitrary "starts >= 3 and win_rate < 0.6" cutoff from v1.
    risky = []
    for pid, bucket in races.items():
        starts = safe_int(bucket.get("starts"))
        if starts <= 0:
            continue
        posterior = posterior_from_stats_bucket(bucket, prior=prior)
        lcb = posterior.lcb(0.25)
        if lcb < 0.5:
            risky.append({
                "program_id": pid,
                "starts": starts,
                "win_rate": round(safe_float(bucket.get("win_rate"), 0.0), 4),
                "posterior_mean": round(posterior.mean(), 4),
                "lcb": round(lcb, 4),
                "avg_reward": bucket.get("avg_reward"),
            })
    risky.sort(key=lambda row: (row["lcb"], -row["starts"]))
    if risky:
        tips.append({
            "priority": "high",
            "area": "Race Risk",
            "message": f"{len(risky)} race program(s) have a posterior LCB below 0.5. Apply penalties or train prerequisite stats before scheduling them.",
            "examples": risky[:5],
        })

    if not tips:
        tips.append({
            "priority": "info",
            "area": "AI Advisor",
            "message": "Not enough negative patterns found yet. Continue collecting clean career logs.",
        })

    return {
        "success": True,
        "ai_root": str(ai_root(base_dir)),
        "manifest": manifest,
        "records": stats.get("records", {}),
        "tips": tips,
        "stats": stats,
        "data_health": health,
        "global_base_rate": round(base_rate, 4),
        "calibration": calibration_summary(base_dir),
    }


# ---------------------------------------------------------------------------
# Calibration fit + dashboard summary (v5.43.1)
# ---------------------------------------------------------------------------


# Minimum predictions before fitting the calibrator.  Below this the fit is
# essentially noise; we'd be teaching the bot to trust uncertainty as signal.
MIN_PREDICTIONS_FOR_CALIBRATION = 30


def fit_calibrator(
    base_dir: Any,
    min_predictions: int = MIN_PREDICTIONS_FOR_CALIBRATION,
) -> Dict[str, Any]:
    """Fit and persist an isotonic calibrator from logged race predictions.

    Reads ``turn_decisions.jsonl``, pulls every race row that has both a
    predicted win probability and an actual race result, fits the
    calibrator, writes it to ``uma_runtime/ai/isotonic_calibrator.json``,
    and returns a status dict suitable for surfacing in the dashboard.

    Always returns -- never raises -- so the dashboard "Fit calibrator"
    button can show a friendly message when there isn't enough data yet
    instead of producing a stack trace.
    """
    from career_bot.ai_dataset import DATASET_FILES, now_iso
    from career_bot.calibration import (
        IsotonicCalibrator,
        brier_score,
        expected_calibration_error,
        extract_race_predictions,
    )

    root = ai_root(base_dir)
    jsonl_path = root / DATASET_FILES["turn_decisions"]
    if not jsonl_path.exists():
        return {
            "success": False,
            "reason": "no_dataset",
            "message": "No turn_decisions.jsonl found yet. Run at least a few careers first.",
            "predictions": 0,
        }

    predictions = extract_race_predictions(jsonl_path)
    n = len(predictions)
    if n < min_predictions:
        return {
            "success": False,
            "reason": "insufficient_data",
            "message": (
                f"Only {n} usable race predictions in the log; need "
                f"at least {min_predictions} before fitting. Keep running careers."
            ),
            "predictions": n,
            "required": min_predictions,
        }

    ece_before = expected_calibration_error(predictions, n_bins=10)
    brier_before = brier_score(predictions)

    try:
        calibrator = IsotonicCalibrator().fit(predictions)
    except Exception as exc:
        return {
            "success": False,
            "reason": "fit_failed",
            "message": f"Calibrator fit failed: {exc!r}.",
            "predictions": n,
        }

    # Save atomically (tempfile + replace) so an interrupted write can never
    # leave a half-truncated file the loader would silently nullify.
    target = calibrator_path(base_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    payload = {
        "fitted_at": now_iso(),
        "predictions_used": n,
        "ece_before": round(ece_before, 4),
        "brier_before": round(brier_before, 4),
        **calibrator.to_dict(),
    }
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(target)

    # Bust the cache so the new fit takes effect on the next hint call.
    _CALIBRATOR_CACHE.update(path=None, mtime=0.0, instance=None)

    # Sanity check: ECE after recalibration on the same data should be
    # at least as good (in-sample), and usually substantially better.
    recalibrated = [
        (calibrator.transform_one(p), y) for p, y in predictions
    ]
    ece_after = expected_calibration_error(recalibrated, n_bins=10)
    brier_after = brier_score(recalibrated)

    return {
        "success": True,
        "reason": "fitted",
        "message": (
            f"Fitted calibrator on {n} predictions. "
            f"Calibration error went from {ece_before:.3f} to {ece_after:.3f}."
        ),
        "predictions": n,
        "ece_before": round(ece_before, 4),
        "ece_after": round(ece_after, 4),
        "brier_before": round(brier_before, 4),
        "brier_after": round(brier_after, 4),
        "path": str(target),
    }


def calibration_summary(base_dir: Any) -> Dict[str, Any]:
    """Compact calibration status for the AI dashboard.

    Returns ECE/Brier on the most recent logged predictions, whether a
    calibrator is currently loaded, and when it was last fitted.  Designed
    to render as a single dashboard card without further computation.
    """
    from career_bot.ai_dataset import DATASET_FILES
    from career_bot.calibration import (
        brier_score,
        expected_calibration_error,
        extract_race_predictions,
        reliability_diagram,
    )

    root = ai_root(base_dir)
    jsonl_path = root / DATASET_FILES["turn_decisions"]

    predictions = extract_race_predictions(jsonl_path) if jsonl_path.exists() else []
    n = len(predictions)
    diagram = reliability_diagram(predictions, n_bins=10) if predictions else []

    cal_path = calibrator_path(base_dir)
    cal_meta = {}
    if cal_path.exists():
        try:
            cal_meta = json.loads(cal_path.read_text(encoding="utf-8"))
        except Exception:
            cal_meta = {}

    interpretation = _ece_interpretation(
        expected_calibration_error(predictions, n_bins=10) if predictions else None
    )

    return {
        "predictions": n,
        "min_for_fit": MIN_PREDICTIONS_FOR_CALIBRATION,
        "ece": round(expected_calibration_error(predictions, n_bins=10), 4) if predictions else None,
        "brier": round(brier_score(predictions), 4) if predictions else None,
        "interpretation": interpretation,
        "calibrator_present": bool(cal_meta),
        "calibrator_fitted_at": cal_meta.get("fitted_at"),
        "calibrator_predictions_used": cal_meta.get("predictions_used"),
        "calibrator_ece_at_fit": cal_meta.get("ece_before"),
        "reliability_diagram": [
            {
                "bin_lo": round(b.lo, 2),
                "bin_hi": round(b.hi, 2),
                "count": b.count,
                "predicted": round(b.predicted_mean, 4),
                "actual": round(b.actual_mean, 4),
            }
            for b in diagram
        ],
    }


def _ece_interpretation(ece: Optional[float]) -> str:
    """Human-readable interpretation of an ECE score for the dashboard."""
    if ece is None:
        return "Not enough race predictions to score calibration yet."
    if ece < 0.03:
        return "Excellent — predictions match outcomes very closely."
    if ece < 0.07:
        return "Good — predictions are well-calibrated for live use."
    if ece < 0.12:
        return "Mild miscalibration — fitting the calibrator should help."
    return "Significant miscalibration — fit the calibrator to correct it."





def latest_training_run(base_dir: Any) -> Dict[str, Any]:
    path = ai_root(base_dir) / "latest_training_run.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def policy_adjustments(base_dir: Any) -> Dict[str, Any]:
    path = ai_root(base_dir) / "policy_adjustments.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def live_policy_summary(base_dir: Any) -> Dict[str, Any]:
    policy = policy_adjustments(base_dir)
    return {
        "enabled": bool(policy.get("enabled")),
        "race_adjustments": len(policy.get("races") or {}),
        "item_adjustments": len(policy.get("items") or {}),
        "event_adjustments": len(policy.get("events") or {}),
        "confidence_threshold": policy.get("confidence_threshold"),
        "reversible": bool(policy.get("reversible", True)),
    }


def race_policy_hint(base_dir: Any, program_id: Any) -> Dict[str, Any]:
    policy = policy_adjustments(base_dir)
    key = str(safe_int(program_id))
    row = ((policy.get("races") or {}).get(key) or {})
    if not row or not policy.get("enabled", True):
        return {
            "program_id": safe_int(program_id),
            "adjustment": 0.0,
            "confidence": 0.0,
            "reason": "No live learned policy hint for this race.",
        }
    return {"program_id": safe_int(program_id), **row}
