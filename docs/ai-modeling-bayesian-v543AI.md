# Pre Icarus v5.43AI — Bayesian AI Advisor

Replaces the v1 advisor's point-estimate win rate and `-8.0` magic-number
penalty with a Beta-Binomial posterior over race-program win rate.  Adds
hierarchical context-aware pooling, calibration tools, and live-policy
safety guards.

## Why this build exists

The v1 advisor's `race_program_hint` scored each race program with:

```python
adjustment = avg_reward
if starts >= 3 and win_rate < 0.5:
    adjustment -= 8.0
```

That had three problems in five lines:

- **Discontinuity at `win_rate = 0.5`.** A program at 5/10 wins scored
  `avg_reward`; a program at 4/10 scored `avg_reward - 8.0`, a free-fall of
  8 score units for a single bad start.
- **No uncertainty.** A program at 7/10 (real signal) and a program at
  70/100 (much stronger signal) both came out as `win_rate = 0.7` with no
  way to express which estimate the advisor was confident in.
- **Uncalibrated sample-size gate.** `starts >= 8` produced a `"high"`
  confidence label.  No one ever checked whether `"high"` corresponded to
  predictions that were actually accurate.

v5.43AI replaces all three with standard Bayesian machinery on the same
JSONL data the existing pipeline already collects.

## What changed, at a glance

| Concern | v1 | v5.43AI |
|---|---|---|
| Win-rate estimate | `wins/starts` | Beta posterior, prior centred on global base rate |
| Score function | `avg_reward - 8.0` at `win_rate < 0.5` | `avg_reward * LCB(0.25)` — smooth, uncertainty-aware |
| Sample-size gate | `starts >= 3 / >= 8` thresholds | Variance-driven, calibrated to land near old buckets |
| Context | program_id only | Hierarchical: `program → +scenario → +preset → +turn_phase` |
| Calibration | None | Reliability diagrams, ECE, Brier, isotonic recalibration |
| Live policy | Free-form `policy_adjustments.json` | `safe_apply` with bounded clamping, sample minimum, KL-based drift detection |

## File map

| File | Status | Purpose |
|---|---|---|
| `career_bot/ai_modeling.py` | NEW | `BetaPosterior`, hierarchical pooling, `score_program` |
| `career_bot/calibration.py` | NEW | Reliability diagrams, ECE/Brier, `IsotonicCalibrator` |
| `career_bot/policy_guards.py` | NEW | `PolicyGuardConfig`, `safe_apply`, drift detection |
| `career_bot/ai_advisor.py` | UPDATED | Wires posteriors into existing functions; adds `hierarchical_race_program_hint` |
| `career_bot/ai_dataset.py` | UPDATED | `rebuild_advisor_stats` now writes `race_programs_context`; new `_turn_phase` helper |
| `tests/test_ai_sprint1.py` | NEW | 40 tests for posteriors, calibration, policy guards, legacy contract |
| `tests/test_ai_sprint2.py` | NEW | 11 tests for hierarchical buckets and `hierarchical_race_program_hint` |
| `CHANGELOG.md` | UPDATED | v5.43AI entry prepended |

No new hard dependencies.  `scipy` is already required.  `scikit-learn`
is optional — `IsotonicCalibrator` falls back to a pure-Python Pool
Adjacent Violators implementation when sklearn isn't installed, and both
produce the same fit for the 1-D monotone problem we have.

## The math, briefly

**Beta-Binomial posterior.**  Each `(program_id, context)` cell maintains
`Beta(α, β)` where:

```
α = α_prior + wins
β = β_prior + losses
```

The prior is `Beta(prior_mean * 4, (1 - prior_mean) * 4)` with
`prior_mean` set to `global_base_rate` — the user's overall program win
rate when at least 10 program-starts have accumulated, else 0.5.  Four
pseudo-observations is gentle enough that a single real observation
already shifts the posterior meaningfully.

**Score function.**  `score_program(posterior, avg_reward)` returns:

```
adjustment = avg_reward * lcb_25
```

where `lcb_25` is the 25th-percentile of the Beta posterior.  A program
with weak data but a high posterior mean still scores low because its
LCB is pulled down by the long left tail of the credible interval.  A
program with strong data scores its actual `avg_reward * win_rate` very
closely.  No discontinuities anywhere.

**Hierarchical pooling.**  `hierarchical_posterior(levels, ...,
parent_discount=0.5)` walks levels least-to-most-specific.  At each
level the parent's posterior is discounted by `parent_discount` and
used as the prior for the child:

```
discounted_prior_α = parent.α * d + base_prior.α * (1 - d)
discounted_prior_β = parent.β * d + base_prior.β * (1 - d)
child.posterior    = Beta(discounted_prior_α + child.wins,
                          discounted_prior_β + child.losses)
```

`parent_discount = 0.5` means the parent carries half its strength into
the child.  Sparse children inherit useful information from rich
parents; rich children are dominated by their own data.

**Drift detection.**  `beta_kl_divergence(recent, long_window)` is the
closed-form KL of two Beta distributions in terms of digamma and
log-gamma.  When KL exceeds `drift_kl_threshold` (default 0.5) the cell
is treated as having shifted distributionally and learned adjustments
are frozen until enough fresh observations accumulate to make the
recent window trustworthy again.

## Integration guide

### Drop-in: no code changes required

The v1 `race_program_hint` and `post_run_advice` signatures are
preserved exactly.  Existing call sites in `runner.py`, `ai_trainer.py`,
and `tests/test_sweepymodv53*` keep working without modification.  The
math under the hood is different and better; the return-shape contract
is unchanged.

### Opt-in: context-aware hints

When the caller has scenario/preset/turn context available (e.g. in
`runner.py`'s race-scheduling code) it can call the richer variant:

```python
from career_bot.ai_advisor import hierarchical_race_program_hint

hint = hierarchical_race_program_hint(
    base_dir,
    program_id=current_race["program_id"],
    scenario_id=runner.scenario_id,
    preset_name=runner.preset_name,
    turn=runner.current_turn,
)

# hint["adjustment"] is the context-aware version
# hint["contributed_levels"] tells you how specific the estimate was
# hint["levels"] lists per-level starts for the dashboard
```

When the v2 `race_programs_context` section is missing (older stats
file), the function automatically falls back to the v1
`race_program_hint` code path and returns `contributed_levels: ["program"]`
on hits, `[]` on cold start.

### Migrating an existing stats archive

Older `advisor_stats.json` files do not contain `race_programs_context`.
The flat `race_programs` section will continue to drive v1 hints
correctly, but you won't see hierarchical pooling benefits until you
rebuild from raw JSONL:

```python
from pathlib import Path
from career_bot.ai_dataset import rebuild_advisor_stats

rebuild_advisor_stats(Path("uma_runtime/ai"))
```

This is also the easiest way to test the new build: rebuild on a
realistic logs archive, then inspect the new `race_programs_context`
section in the resulting `advisor_stats.json`.

## Calibration workflow

Once you've accumulated race predictions with `decision_report.predicted_win_prob`
filled in:

```python
from pathlib import Path
from career_bot.calibration import (
    extract_race_predictions,
    reliability_diagram,
    expected_calibration_error,
    IsotonicCalibrator,
)

preds = extract_race_predictions(Path("uma_runtime/ai/turn_decisions.jsonl"))
print(f"ECE: {expected_calibration_error(preds):.3f}")

for bin in reliability_diagram(preds, n_bins=10):
    print(f"  predicted {bin.predicted_mean:.2f} -> actual {bin.actual_mean:.2f} (n={bin.count})")

# If ECE > 0.05, fit a recalibrator and persist it
if expected_calibration_error(preds) > 0.05:
    cal = IsotonicCalibrator().fit(preds)
    Path("uma_runtime/ai/isotonic_calibrator.json").write_text(
        json.dumps(cal.to_dict())
    )
```

At hint time, load and apply:

```python
cal = IsotonicCalibrator.from_dict(
    json.loads(Path("uma_runtime/ai/isotonic_calibrator.json").read_text())
)
calibrated_p = cal.transform_one(hint["posterior_mean"])
```

Modern well-calibrated classifiers tend to ECE below 0.05.  Values above
0.15 mean the predicted probabilities aren't trustworthy and the
isotonic recalibrator should be on by default.

## Backward compatibility

- `race_program_hint(base_dir, program_id)` — return keys unchanged:
  `program_id, confidence, starts, win_rate, avg_reward, adjustment, reason`.
  Adds `posterior_mean, lcb, ucb, variance, alpha, beta` for new
  consumers.
- `post_run_advice` — same top-level keys.  `tips` now references
  posterior LCB instead of raw win rate; the dashboard surface is
  unaffected.
- `advisor_stats.json` — `actions`, `turn_bands`, `race_programs`
  sections unchanged.  New `race_programs_context` section is additive.
- `tests/test_sweepymodv532_ai_dataset.py` and v533 tests pass without
  modification.

## Test coverage

```
tests/test_ai_sprint1.py   40 tests
tests/test_ai_sprint2.py   11 tests
tests/test_sweepymodv532_ai_dataset.py   4 tests (existing, unchanged)
```

Total: 55 tests pass in ~1 second.  Highlights:

- `test_low_winrate_no_longer_jumps_minus_eight` walks `wins ∈ 0..10`
  and asserts the adjustment is strictly monotone with no step
  exceeding 4.0 — the v1 step at the 0.5 boundary was 8.0.
- `test_sparse_leaf_inherits_from_rich_parent` builds a leaf of 0/1 and
  a parent of 35/50, then asserts the leaf posterior mean lands between
  0.4 and 0.7 (instead of crashing to 0.0).
- `test_isotonic_improves_miscalibrated_predictions` constructs
  systematically overconfident predictions (`emit p, truth is p²`) and
  asserts the calibrator reduces ECE below 0.05 on a held-out set.
- `test_safe_apply_freezes_on_drift` constructs a clear distributional
  shift between recent and long-window posteriors and asserts the
  guard returns `reason="drift_detected"` with the unmodified
  heuristic score.

## Future work

Sprint 3 candidates already enabled by this groundwork:

- **Action-value learning.** The dataset is in the canonical
  `(state, action, reward, next_state)` shape for offline Fitted Q-Iteration.
  LightGBM is the appropriate model class for tabular Q-functions of this
  size.  Output becomes one term in the `runner.py` scoring blend,
  weighted by per-cell posterior variance.
- **Event-choice posteriors.** Same Beta-Binomial treatment applied to
  `event_choices` data in the dataset, indexed per
  `(event_id, choice_index)`.
- **Skill-value learning.** Fit a regressor on `skill_buy_attempts →
  race_win_delta` to replace the hand-curated `skill_weighting_core.json`
  weights with learned ones, keeping the hand-curated values as the
  prior and the model as the correction term.

## v5.43.1 patch — calibration is now live

The "Calibration workflow" section above describes how to fit and apply
the isotonic calibrator manually.  As of v5.43.1, that wiring is built
into the advisor:

- `race_program_hint` and `hierarchical_race_program_hint` load the
  calibrator from `uma_runtime/ai/isotonic_calibrator.json` automatically
  on every call (mtime-cached, so re-fitting takes effect immediately).
- The `adjustment` field uses the calibrated LCB when a calibrator is
  present; the previous v5.43 value is preserved under `raw_adjustment`
  for diagnostics.
- `ai_advisor.fit_calibrator(base_dir)` is the one-call helper for the
  dashboard "Fit calibrator" button.  It returns friendly status
  messages on every failure mode (no dataset yet, not enough
  predictions, fit failure) so the UI never has to handle exceptions.
- `ai_advisor.calibration_summary(base_dir)` is the dashboard payload:
  current ECE, Brier score, plain-English interpretation, reliability
  diagram bins, calibrator metadata when fitted.  `post_run_advice` now
  embeds this under a `calibration` key.

A non-developer's path from cold-start to calibrated decisions:

1. Run the bot normally for a few careers (predictions accumulate in
   `turn_decisions.jsonl`).
2. From the AI dashboard, click "Fit calibrator" once at least 30 race
   predictions are logged.
3. From that point on, every advisor hint applies the calibration
   automatically.  Re-fit whenever the dashboard shows ECE drifting
   upward.
