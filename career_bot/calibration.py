"""Calibration tools for Pre Icarus's AI advisor.

A predictor that says "70% chance of winning" should actually win ~70% of the
time across many predictions in that bin.  The original advisor returned
``confidence`` strings (``"high" | "medium" | "low"``) gated on
``starts >= 8 / >= 3``, with no validation that those numbers correspond to
anything real.

This module provides three things:

  1. Reliability diagrams: bin predictions by predicted probability, compute
     the empirical win rate per bin.  This is what you plot to *see* whether
     the model is calibrated.

  2. Expected Calibration Error (ECE): a single scalar summary of how far
     the reliability curve deviates from the y=x identity line.

  3. Isotonic recalibration: a non-parametric monotone mapping from raw
     predicted probabilities to calibrated ones, fit on held-out data.
     Falls back to a pure-Python implementation when scikit-learn is not
     installed so this module remains usable without adding a hard
     dependency.

All inputs are ``(predicted_probability, actual_outcome)`` pairs, which the
existing ``turn_decisions.jsonl`` pipeline already produces for race actions
(``predicted`` comes from the advisor hint, ``actual`` from
``outcome.race_result.rank == 1``).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple

Prediction = Tuple[float, bool]


__all__ = [
    "reliability_diagram",
    "expected_calibration_error",
    "brier_score",
    "IsotonicCalibrator",
    "extract_race_predictions",
]


# ---------------------------------------------------------------------------
# Reliability diagram + scalar calibration metrics
# ---------------------------------------------------------------------------


@dataclass
class ReliabilityBin:
    lo: float
    hi: float
    count: int
    predicted_mean: float
    actual_mean: float

    def gap(self) -> float:
        return abs(self.predicted_mean - self.actual_mean)


def reliability_diagram(
    predictions: Sequence[Prediction],
    n_bins: int = 10,
) -> List[ReliabilityBin]:
    """Return one ``ReliabilityBin`` per non-empty equal-width bin in [0, 1].

    Empty bins are omitted — they aren't plotted, and including them with
    zero count distorts ECE.
    """
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")
    if not predictions:
        return []

    edges = [i / n_bins for i in range(n_bins + 1)]
    edges[-1] = 1.0 + 1e-12  # so a prediction of exactly 1.0 lands in the last bin

    buckets: List[List[Prediction]] = [[] for _ in range(n_bins)]
    for p, y in predictions:
        p = max(0.0, min(1.0, float(p)))
        idx = min(n_bins - 1, int(p * n_bins))
        buckets[idx].append((p, bool(y)))

    out: List[ReliabilityBin] = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        preds = [p for p, _ in bucket]
        outs = [1.0 if y else 0.0 for _, y in bucket]
        out.append(
            ReliabilityBin(
                lo=edges[i],
                hi=edges[i + 1],
                count=len(bucket),
                predicted_mean=sum(preds) / len(preds),
                actual_mean=sum(outs) / len(outs),
            )
        )
    return out


def expected_calibration_error(
    predictions: Sequence[Prediction],
    n_bins: int = 10,
) -> float:
    """Weighted average gap between predicted and actual win rates.

    Returns a value in [0, 1].  ``0`` is perfectly calibrated.  Modern
    well-tuned classifiers tend to land below 0.05; values above 0.15 mean
    the predicted probabilities are not trustworthy and need recalibration.
    """
    diagram = reliability_diagram(predictions, n_bins=n_bins)
    if not diagram:
        return 0.0
    total = sum(b.count for b in diagram)
    if total == 0:
        return 0.0
    return sum((b.count / total) * b.gap() for b in diagram)


def brier_score(predictions: Sequence[Prediction]) -> float:
    """Mean squared error between predicted probability and actual outcome.

    Brier rewards both calibration and resolution; ECE only checks
    calibration.  Use both side by side for a fuller picture.
    """
    if not predictions:
        return 0.0
    n = len(predictions)
    total = 0.0
    for p, y in predictions:
        p = max(0.0, min(1.0, float(p)))
        actual = 1.0 if y else 0.0
        total += (p - actual) ** 2
    return total / n


# ---------------------------------------------------------------------------
# Isotonic recalibration
# ---------------------------------------------------------------------------


class IsotonicCalibrator:
    """Monotone non-decreasing map from raw predicted probability to
    calibrated probability.

    Uses scikit-learn's IsotonicRegression when available; otherwise falls
    back to the Pool Adjacent Violators algorithm in pure Python.  Both
    produce the same fit for the (1-D, monotonic) problem we have here.
    """

    def __init__(self) -> None:
        self._fitted = False
        self._sk_model: Any = None
        # Fallback breakpoints: parallel arrays of x (raw predictions) and
        # y (calibrated outputs), monotone non-decreasing in y.
        self._x: List[float] = []
        self._y: List[float] = []

    # ----- fitting --------------------------------------------------------

    def fit(self, predictions: Sequence[Prediction]) -> "IsotonicCalibrator":
        if not predictions:
            raise ValueError("cannot fit calibrator on empty predictions")
        xs = [max(0.0, min(1.0, float(p))) for p, _ in predictions]
        ys = [1.0 if y else 0.0 for _, y in predictions]

        try:
            from sklearn.isotonic import IsotonicRegression  # type: ignore

            self._sk_model = IsotonicRegression(
                y_min=0.0, y_max=1.0, out_of_bounds="clip"
            ).fit(xs, ys)
        except ImportError:
            self._x, self._y = _pav_fit(xs, ys)

        self._fitted = True
        return self

    # ----- prediction -----------------------------------------------------

    def transform_one(self, p: float) -> float:
        if not self._fitted:
            raise RuntimeError("call fit() before transform_one()")
        p = max(0.0, min(1.0, float(p)))
        if self._sk_model is not None:
            return float(self._sk_model.predict([p])[0])
        return _pav_predict(self._x, self._y, p)

    def transform(self, ps: Iterable[float]) -> List[float]:
        return [self.transform_one(p) for p in ps]

    # ----- serialization --------------------------------------------------

    def to_dict(self) -> dict:
        if not self._fitted:
            raise RuntimeError("calibrator not fitted")
        if self._sk_model is not None:
            return {
                "backend": "sklearn",
                "x": [float(x) for x in self._sk_model.X_thresholds_],
                "y": [float(y) for y in self._sk_model.y_thresholds_],
            }
        return {"backend": "pav", "x": list(self._x), "y": list(self._y)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "IsotonicCalibrator":
        c = cls()
        c._x = [float(v) for v in payload.get("x") or []]
        c._y = [float(v) for v in payload.get("y") or []]
        if not c._x:
            raise ValueError("calibrator payload missing breakpoints")
        c._fitted = True
        # Always use the fallback predictor when deserializing — keeps
        # behavior identical across hosts even if one has sklearn and one
        # doesn't.
        c._sk_model = None
        return c


# ---------------------------------------------------------------------------
# Pure-Python Pool Adjacent Violators (sklearn-free fallback)
# ---------------------------------------------------------------------------


def _pav_fit(xs: List[float], ys: List[float]) -> Tuple[List[float], List[float]]:
    """Pool Adjacent Violators on equal-weight observations.

    Returns sorted breakpoints (x, y) defining a step function that is the
    L2-optimal monotone non-decreasing fit to (xs, ys).
    """
    n = len(xs)
    if n == 0:
        return [], []

    order = sorted(range(n), key=lambda i: xs[i])
    sx = [xs[i] for i in order]
    sy = [ys[i] for i in order]

    # Each block: [sum_y, count, lo_index, hi_index]
    blocks: List[List[float]] = [[sy[i], 1.0, float(i), float(i)] for i in range(n)]

    # Merge adjacent blocks while a left block's mean exceeds a right block's mean.
    i = 0
    while i < len(blocks) - 1:
        left = blocks[i]
        right = blocks[i + 1]
        left_mean = left[0] / left[1]
        right_mean = right[0] / right[1]
        if left_mean > right_mean:
            blocks[i] = [left[0] + right[0], left[1] + right[1], left[2], right[3]]
            del blocks[i + 1]
            if i > 0:
                i -= 1
        else:
            i += 1

    # Materialize breakpoints: each block becomes a constant segment at its mean
    # over [sx[lo], sx[hi]].  We return a small set of (x, y) tuples sufficient
    # for piecewise-linear interpolation on lookup.
    out_x: List[float] = []
    out_y: List[float] = []
    for block in blocks:
        sum_y, count, lo, hi = block
        mean_y = sum_y / count
        out_x.append(sx[int(lo)])
        out_y.append(mean_y)
        if hi != lo:
            out_x.append(sx[int(hi)])
            out_y.append(mean_y)
    return out_x, out_y


def _pav_predict(xs: List[float], ys: List[float], p: float) -> float:
    """Piecewise-linear interpolation against the PAV breakpoints."""
    if not xs:
        return p
    if p <= xs[0]:
        return ys[0]
    if p >= xs[-1]:
        return ys[-1]
    # Binary search for the interval.
    lo, hi = 0, len(xs) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if xs[mid] <= p:
            lo = mid
        else:
            hi = mid
    x0, x1 = xs[lo], xs[hi]
    y0, y1 = ys[lo], ys[hi]
    if x1 == x0:
        return y0
    t = (p - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


# ---------------------------------------------------------------------------
# Helpers to extract predictions from the existing JSONL pipeline
# ---------------------------------------------------------------------------


def extract_race_predictions(
    turn_decisions_path: Path,
    advisor_field: str = "predicted_win_prob",
) -> List[Prediction]:
    """Read ``turn_decisions.jsonl`` and pull ``(predicted, actual)`` pairs
    for every row whose action was a race.

    ``predicted`` comes from ``decision_report[advisor_field]`` if present,
    otherwise from ``decision_report.race_context.win_rate``, otherwise the
    row is skipped (no prediction recorded => nothing to calibrate).

    ``actual`` is ``True`` iff ``outcome.race_result.rank == 1``.
    """
    out: List[Prediction] = []
    path = Path(turn_decisions_path)
    if not path.exists():
        return out

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            action = (row.get("action") or {}).get("type") or ""
            if action != "race":
                continue

            outcome = row.get("outcome") or {}
            result = outcome.get("race_result") or {}
            rank = result.get("rank")
            if rank is None:
                rank = result.get("result_rank")
            if rank is None:
                continue
            actual = int(rank) == 1

            decision = row.get("decision_report") or {}
            predicted = decision.get(advisor_field)
            if predicted is None:
                race_context = decision.get("race_context") or {}
                predicted = race_context.get("win_rate")
            if predicted is None:
                continue
            try:
                p = float(predicted)
            except Exception:
                continue
            out.append((p, actual))

    return out
