# Scope: Race Win-Probability Calculator

Date: 2026-06-28 · Status: **PHASE 1 BUILT** (read-only; needs live calibration) · Owner area: `career_bot/`

## Phase 1 — BUILT 2026-06-28 (read-only, zero behaviour change)
- `career_bot/win_probability.py` — pure model: `runner_strength` / `npc_strength`
  (mirror the engine's master.mdb rate convention: speed&power scaled by
  `distance_rate`, whole score by ground/style/motivation, `/scale`), rival-field
  resolution (`build_rival_index`/`resolve_field`, join `(chara_id,turn,program_id)`),
  and `win_probability` = pairwise-logistic P(win) × Poisson-binomial P(top-3).
- `POST /api/race/win-probability` (main.py) — self-contained; resolves
  distance/ground from `program_id`, accepts trainee stats+aptitudes+style+motivation.
- Career-History display: `_augment_race_results_with_winprob` (main.py, read-only,
  per-row try/except, NOT in the runner hot path) attaches a compact estimate to
  each completed-career race row; `public-v3/history.js` renders a `~P(win) NN%`
  chip (marked preliminary/uncalibrated, named-rivals-only caveat in the tooltip;
  hidden when no field is known).
- Backtest: `tools/race_winnability_report.py` Analysis C — model P(win) vs actual,
  Brier + AUC + reliability bins, grid-fits the optimal logistic `k`.
- Tests: 29 across test_win_probability_{,endpoint_,backtest_,history_}20260628.py
  (hand-checked math, real-data rival join, endpoint/history contracts, +4 regressions
  from an adversarial review: auto-style=0 neutralisation [was a 10× deflation BLOCKER],
  negative-k clamp, NaN-stat guard, `_rate` real-zero).
- **NOT engine-wired** (no solver/runner decision reads it). `DEFAULT_K=150` is
  PRELIMINARY — run Analysis C on a real finished-career log to get the fitted `k`,
  then update the default before any Phase-2 decisioning.
- Restart `python main.py` + hard-refresh to see it; not yet in any built zip.

---

## Original scope (below)

Date: 2026-06-28 · Status: SCOPED (not built) · Owner area: `career_bot/`

## Goal
Give Icarus an opponent-aware estimate of **P(win)** / **P(top-3)** for a race
*before committing*, computed from the game's own data rather than heuristics —
so race selection, clock-retry spend, and running-style choice become quantified
bets instead of guesses. Attacks both parity gaps (win-rate, fans/stats).

## Why this is feasible now
The blocking dependency is fixed: `data/single_mode_npc_core.json` now holds
**1,444 NPC stat blocks** (speed/stamina/power/guts/wit, distance/style/ground
aptitude grades, skill_set_id, motivation range) — see
[[icarus-event-force-apply-fix]]/the `single_mode_npc` DIRECT_TABLES fix + regen.
All other inputs already exist on disk.

## Inputs (all already present)
- **Opponent field:** `single_mode_npc_core.json` (stat blocks) joined via
  `rival_races_core.json` (which `single_mode_npc_id` appears at which turn/race).
- **Multiplier tables (master.mdb exports):** `race_performance_rates_core.json` —
  `distance_rate` (aptitude grade → per-distance stat scaling), `ground_rate`
  (turf/dirt), `runningstyle_rate` (front/pace/late/end), `motivation_rate`,
  `popularity_proper_value` (gate/popularity effect).
- **Trainee:** live `chara_info` stats + aptitudes from the current turn payload;
  running style from the preset / `race_strategy_by_distance`.
- **Calibration corpus:** logged finishes from `runner.py` `_record_race_result`
  (race history per career) — the ground truth to fit/validate against.
- **Existing seed:** `tools/race_winnability_report.py` already exists — start there.

## Approach (pragmatic, NOT a full physics sim)
The game's real race is a tick-by-tick simulation; reproducing it exactly is out
of scope and brittle. Instead build a **calibrated field-strength ranking model**:
1. For each runner (trainee + each NPC in the field), compute a scalar
   **strength score** = weighted sum of stats, each scaled by the relevant
   multiplier-table factors for *this* race: distance_rate[aptitude][distance],
   ground_rate[aptitude][surface], runningstyle_rate[style], motivation_rate,
   plus a popularity/gate term. (Skills: phase 2 — add an expected skill
   contribution from `skill_set_id` × `available_skill_set`, weighted by P(fire).)
2. Rank the field by score; derive the trainee's expected finishing position and
   a score-gap to the field.
3. Map (score-gap, field-size) → **P(win)/P(top-3)** via a calibrated function
   (logistic fit) trained on the logged finish history, so the output is a
   probability, not an arbitrary index. **Do not ship uncalibrated.**

## Where it plugs in (phased)
- **Phase 1 — read-only analytics:** a `compute_win_probability(race, chara, preset)`
  helper + a `/api/race/win-probability` endpoint + a v3 display (e.g. a P(win)
  chip on the race picker / decision reasoning). Zero behavior change; lets us
  validate accuracy against real runs first.
- **Phase 2 — decisioning (opt-in, gated):** feed P(win) into (a) the race-value
  term in the solver (`trackblazer.py` scoring) and (b) clock-retry policy
  (`runner.py` — only burn a clock when P(win) on retry clears a threshold) and
  (c) per-race running-style pick. Ship behind a default-off flag until calibrated.

## Risks / guardrails
- **Calibration is the crux** — an uncalibrated score that *looks* like a
  probability is worse than none. Gate Phase 2 on a measured Brier score / hit-rate
  vs logged finishes; keep it default-off until it beats the current heuristic.
- Skill contribution (phase 2) is the largest unknown; ship phase 1 stats-only first.
- NPC field for a race must be resolved correctly via `rival_races_core` +
  `single_mode_npc_id`; verify the join on a live race before trusting output.
- Multiplier-table semantics (exact axis order of `distance_rate` etc.) must be
  confirmed against master.mdb columns before coding the score — don't assume.

## Definition of done (phase 1)
- Helper + endpoint return a P(win)/P(top-3) for any upcoming race.
- A backtest report (extend `tools/race_winnability_report.py`) over logged
  careers showing calibration (predicted vs actual finish) — committed, not just run.
- Tests: unit-test the score math against a hand-checked field; contract-test the
  rival→NPC join.

## NOT in scope
The exact in-game race physics sim; live mid-race prediction; anything requiring
data not already exported from master.mdb.
