"""Bayesian primitives for the Pre Icarus AI advisor.

The original advisor used point-estimate win rates with a magic-number penalty
(``adjustment -= 8.0`` when ``starts >= 3 and win_rate < 0.5``).  That gives
a discontinuity at exactly 0.5, no uncertainty quantification, and uncalibrated
sample-size gates.

This module replaces that with a Beta-Binomial posterior over win rate, plus
a small helper for hierarchical pooling across keys of increasing specificity
(global -> program -> program+scenario -> program+scenario+character -> ...).
All functions are pure: they consume data, return values, and never touch disk.

The advisor module ``career_bot.ai_advisor`` wires these into the existing
``race_program_hint`` contract without changing its return-shape.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# scipy is already in requirements.txt (scipy>=1.11). We import lazily inside
# methods that need it so module import stays cheap.


__all__ = [
    "BetaPosterior",
    "hierarchical_posterior",
    "score_program",
    "posterior_from_stats_bucket",
    "global_base_rate",
]


@dataclass(frozen=True)
class BetaPosterior:
    """Beta(alpha, beta) posterior over a Bernoulli rate.

    Conventions used throughout Pre Icarus:
      - ``alpha`` accumulates "successes" (race wins, positive event outcomes)
      - ``beta``  accumulates "failures" (race non-wins, negative outcomes)
      - The prior is supplied at construction via ``from_prior`` and acts as
        pseudo-counts: a ``prior_strength`` of ``4.0`` is equivalent to having
        seen four prior observations distributed according to ``prior_mean``.
    """

    alpha: float
    beta: float

    # ----- construction ---------------------------------------------------

    @classmethod
    def from_prior(
        cls, prior_mean: float = 0.5, prior_strength: float = 4.0
    ) -> "BetaPosterior":
        """Weakly informative prior centred on ``prior_mean``.

        ``prior_strength`` is in units of pseudo-observations.  ``4.0`` is a
        gentle default: at zero real data the posterior mean equals the prior
        mean, and a single real observation already meaningfully shifts the
        posterior.
        """
        prior_mean = max(1e-6, min(1.0 - 1e-6, float(prior_mean)))
        prior_strength = max(1e-6, float(prior_strength))
        return cls(
            alpha=prior_mean * prior_strength,
            beta=(1.0 - prior_mean) * prior_strength,
        )

    @classmethod
    def jeffreys(cls) -> "BetaPosterior":
        """Jeffreys prior — Beta(0.5, 0.5).  Use when no base rate is known."""
        return cls(alpha=0.5, beta=0.5)

    # ----- updates --------------------------------------------------------

    def update(self, wins: int, losses: int) -> "BetaPosterior":
        """Return a new posterior reflecting ``wins`` and ``losses`` observed."""
        if wins < 0 or losses < 0:
            raise ValueError("wins/losses must be non-negative")
        return BetaPosterior(self.alpha + float(wins), self.beta + float(losses))

    def update_one(self, win: bool) -> "BetaPosterior":
        return self.update(1, 0) if win else self.update(0, 1)

    # ----- summary statistics --------------------------------------------

    @property
    def total(self) -> float:
        return self.alpha + self.beta

    def mean(self) -> float:
        return self.alpha / self.total

    def variance(self) -> float:
        t = self.total
        return (self.alpha * self.beta) / ((t * t) * (t + 1.0))

    def mode(self) -> float:
        """MAP estimate.  Defined when alpha,beta > 1; otherwise falls back."""
        if self.alpha > 1.0 and self.beta > 1.0:
            return (self.alpha - 1.0) / (self.total - 2.0)
        return self.mean()

    # ----- quantile-based bounds -----------------------------------------

    def lcb(self, quantile: float = 0.25) -> float:
        """Lower credible bound at ``quantile``.

        ``quantile=0.25`` gives a mildly pessimistic estimate suitable for
        risk-averse program ranking.  Use ``quantile=0.05`` for a stronger
        pessimism (Wilson-style).
        """
        return self._ppf(quantile)

    def ucb(self, quantile: float = 0.75) -> float:
        """Upper credible bound — useful for exploration bonuses."""
        return self._ppf(quantile)

    def credible_interval(self, mass: float = 0.9) -> Tuple[float, float]:
        if not (0.0 < mass < 1.0):
            raise ValueError("mass must be in (0, 1)")
        tail = (1.0 - mass) / 2.0
        return self._ppf(tail), self._ppf(1.0 - tail)

    def _ppf(self, q: float) -> float:
        from scipy.stats import beta as _beta  # lazy import
        q = max(1e-12, min(1.0 - 1e-12, float(q)))
        return float(_beta.ppf(q, self.alpha, self.beta))

    # ----- sampling -------------------------------------------------------

    def sample(self, rng: Any) -> float:
        """Draw a plausible rate.  ``rng`` is a ``numpy.random.Generator`` or
        anything with a ``.beta(a, b)`` method."""
        return float(rng.beta(self.alpha, self.beta))

    # ----- serialization --------------------------------------------------

    def to_dict(self) -> Dict[str, float]:
        return {"alpha": float(self.alpha), "beta": float(self.beta)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BetaPosterior":
        return cls(alpha=float(payload["alpha"]), beta=float(payload["beta"]))


# ---------------------------------------------------------------------------
# Bridges to the existing advisor_stats.json format
# ---------------------------------------------------------------------------


def posterior_from_stats_bucket(
    bucket: Mapping[str, Any],
    prior: Optional[BetaPosterior] = None,
) -> BetaPosterior:
    """Build a posterior from a ``race_programs[pid]`` bucket.

    The bucket is the dict written by ``ai_dataset.rebuild_advisor_stats``
    with keys ``starts``, ``wins``, ``win_rate`` (we trust ``wins``/``starts``
    over ``win_rate`` if both are present).
    """
    if prior is None:
        prior = BetaPosterior.from_prior(0.5, 4.0)
    starts = int(bucket.get("starts") or 0)
    wins = bucket.get("wins")
    if wins is None:
        # Older stats may only have win_rate; reconstruct integer wins.
        win_rate = float(bucket.get("win_rate") or 0.0)
        wins = int(round(starts * win_rate))
    wins = max(0, min(int(wins), starts))
    losses = starts - wins
    return prior.update(wins, losses)


def global_base_rate(
    race_programs: Mapping[str, Mapping[str, Any]],
    min_total_starts: int = 10,
    fallback: float = 0.5,
) -> float:
    """Estimate the population win rate across all programs in the stats.

    Used as the prior mean for individual program posteriors so that a
    cold-start program inherits the user's overall difficulty rather than
    a flat 0.5.
    """
    total_starts = 0
    total_wins = 0
    for bucket in race_programs.values():
        if not isinstance(bucket, Mapping):
            continue
        starts = int(bucket.get("starts") or 0)
        wins = bucket.get("wins")
        if wins is None:
            wins = int(round(starts * float(bucket.get("win_rate") or 0.0)))
        total_starts += starts
        total_wins += max(0, min(int(wins), starts))
    if total_starts < min_total_starts:
        return float(fallback)
    return total_wins / total_starts


# ---------------------------------------------------------------------------
# Hierarchical pooling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HierarchicalLevel:
    """One level in a hierarchical key chain.

    ``name`` is informational (used in diagnostics); ``key`` is the lookup key
    in the per-level stats dictionary; ``stats`` is the bucket dict at that
    level (or ``None`` if no observations exist at that granularity).
    """

    name: str
    key: Any
    stats: Optional[Mapping[str, Any]]


def hierarchical_posterior(
    levels: Sequence[HierarchicalLevel],
    prior_mean: float = 0.5,
    prior_strength: float = 4.0,
    parent_discount: float = 0.5,
) -> Tuple[BetaPosterior, List[str]]:
    """Walk levels least-to-most-specific, using each parent's posterior
    (optionally discounted) as the prior for the child.

    ``parent_discount`` in [0, 1] controls how much the parent's pseudo-counts
    carry into the child.  ``1.0`` is full carry-over (strong shrinkage toward
    parent); ``0.0`` means each level is fitted independently with the base
    prior (no shrinkage).  ``0.5`` is a reasonable default.

    Returns the final posterior plus a list of level names that contributed
    observations (useful for diagnostics).
    """
    if not 0.0 <= parent_discount <= 1.0:
        raise ValueError("parent_discount must be in [0, 1]")

    current = BetaPosterior.from_prior(prior_mean, prior_strength)
    contributed: List[str] = []

    for level in levels:
        if level.stats is None:
            continue
        starts = int(level.stats.get("starts") or 0)
        if starts <= 0:
            continue

        # Convert current posterior into a discounted prior for this level.
        discounted_prior = BetaPosterior(
            alpha=current.alpha * parent_discount + prior_mean * prior_strength * (1 - parent_discount),
            beta=current.beta * parent_discount + (1 - prior_mean) * prior_strength * (1 - parent_discount),
        )

        leaf = posterior_from_stats_bucket(level.stats, prior=discounted_prior)
        current = leaf
        contributed.append(level.name)

    return current, contributed


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_program(
    posterior: BetaPosterior,
    avg_reward: float,
    risk_quantile: float = 0.25,
    exploration_bonus: float = 0.0,
) -> Dict[str, float]:
    """Combine a posterior over win rate with the bucket's average reward
    into a single scoring number suitable for use as an ``adjustment``.

    The replacement for the old ``adjustment -= 8.0`` discontinuity:

      adjustment = avg_reward * lcb + bonus

    where ``lcb`` is the lower credible bound (pessimistic win-rate estimate).
    Programs with low confidence and low samples get a modest score because
    their LCB is pulled down by uncertainty, but the penalty scales smoothly
    instead of snapping at win_rate < 0.5.

    ``exploration_bonus`` adds an upper-credible-bound term — set to a small
    positive value to encourage exploring under-observed programs.
    """
    lcb = posterior.lcb(risk_quantile)
    ucb = posterior.ucb(1.0 - risk_quantile)
    base = float(avg_reward) * lcb
    bonus = exploration_bonus * (ucb - lcb)
    return {
        "adjustment": round(base + bonus, 4),
        "lcb": round(lcb, 4),
        "ucb": round(ucb, 4),
        "mean": round(posterior.mean(), 4),
        "variance": round(posterior.variance(), 6),
        "alpha": round(posterior.alpha, 4),
        "beta": round(posterior.beta, 4),
    }
