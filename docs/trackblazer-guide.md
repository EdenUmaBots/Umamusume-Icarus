# Trackblazer guide — racing, training, and the smart race solver

This is the user guide for everything Trackblazer-related: how the bot
picks races, how training-vs-racing decisions get made, and the knobs
you have to influence both.

If you're new here, read the **Quick start** section first — it covers
the 3-4 settings that actually matter for race count.

## Quick start: getting more races per career

The single most-asked question is "why is my race count low?" Here are
the four knobs that drive it, in order of impact. All four live in
**Smart Race Solver Settings** in the dashboard.

| Setting | What it does | If race count is low, try |
|---|---|---|
| **Max Streak** | Caps how many races in a row the solver will plan. Default: 2 | Raise to **5** (matches Android benchmark). Range 1–10. |
| **Race Cost %** | Cost the solver subtracts from each race's projected value. Default: 100 | Drop to **75** (moderate) or **60** (aggressive) |
| **Race Bonus %** | Uplift applied to each race's projected reward. Default: 50 | Raise to **60–70** for marginal pushes |
| **Consecutive Race Penalty** | Penalty after 3+ race streaks. Default: 3 | Lower to **1** if you want long streaks |

In **Racing Settings** (separate panel):

| Setting | What it does |
|---|---|
| **Ignore Consecutive Race Warning** | When ON, runtime won't break streaks for chain safety. The Smart Race Solver's Max Streak is still the upstream cap. |
| **Ignore Low Energy Racing Block** | When ON, bot races even at HP=0. Sole HP authority since v6.7.7. |
| **Consecutive Races Limit** | Soft preference, NOT a hard cap. The actual cap is **Max Streak** above. |

> **Common mismatch**: users see "Consecutive Races Limit 5" in Racing
> Settings and assume that's the cap, but the solver-side **Max Streak**
> in Smart Race Solver Settings is the real constraint. Both need to
> be raised together for streaks > 2.

## How the smart race solver decides

The solver runs at career start and after every race. It does a beam
search over future race candidates, scoring each by:

- **Race value** — base reward from the race (stat gain, skill points)
- **Fan value** — projected fans, weighted by `fanWeight`
- **Epithet value** — bonus for races that progress active target epithets
- **Hint reward** — bonus for races that grant skill hints

Then it subtracts:

- **Race cost** — `raceCostPct`% of the candidate's projected value
- **Consecutive race penalty** — applied after `Max Streak` is approached
- **Summer block penalty** — applied to summer-camp turn races
- **Outcome risk** — learned penalty for races that have historically
  failed for similar trainees (only if Live Policy Assistance is on)

The solver picks the highest-net-value subset that fits the career's
turn calendar and aptitude constraints.

### Key advanced weights

These live in **Smart Race Solver Settings → Scoring Weights** but
default values usually work; tune only if you have a specific goal.

| Weight | Default | Purpose |
|---|---|---|
| `epithetValue` | 1.0 | Bonus per active-target-epithet race |
| `forcedEpithetValue` | 500 | Massive bonus for forced epithets |
| `lateSeniorRacePressure` | 12.0 | Encourages racing in late senior year |
| `longDistanceStaminaFloor` | 550 | Penalizes long races below this stat |
| `distancePreferenceBonus` | 6.0 | Bonus for races at preferred distance |
| `targetOptionalRaceCount` | 36 | Diagnostic target (not a hard cap) |
| `hintRewardWeight` | 8.0 | Multiplier on skill-hint epithets |

## Race chain safety (runtime)

Separate from the solver, the runtime has a safety layer that can
break a planned race for rest/recreation if HP is dangerously low.
**As of v6.7.7**, the "Ignore Low Energy Racing Block" toggle in
Racing Settings is the sole authority:

- **Toggle ON**: bot races even at HP=0 (Android-style throughput)
- **Toggle OFF** + `chain_count >= target` + low HP: bot stops for
  recovery
- **Toggle OFF** + `chain_count < target`: race proceeds regardless
  of HP (the chain target is a SOFT preference)

To match Android's race count, leave the toggle ON and let the
solver's Max Streak do the capping.

## Irregular training hijacks

On a turn where a planned race is available AND a high-value training
becomes available (rainbow x2/x3, low failure, big stat gain), the
bot can "hijack" the race for the training. Tunables:

| Setting | Default | What it does |
|---|---|---|
| `irregular_training_min_main_gain` | 30 | Hijack only fires if the training's main-stat gain is ≥ this |
| `irregular_training_score_threshold` | 0.62 | Hijack score floor |
| `irregular_training_failure_limit` | 20 | Max failure % for the hijack |
| `enable_irregular_training` | true | Master toggle |

**v6.7.4 epithet protection**: hijacks NEVER drop a race that
progresses an unmet target epithet, regardless of the above
thresholds.

To make hijacks rare, raise `irregular_training_min_main_gain` to 50+.
To disable entirely, set `enable_irregular_training: false`.

## Items and the item manager

The bot uses items during career turns based on a priority queue:

1. **Ailment cures** — Healthy Manju / Pure Manju / Aroma Bath for
   status effects that block training
2. **Charm** — used when training failure ≥ `risky_training_max_failure_chance`
3. **Energy items** — Energy Drink / Vita Juice / Royal Kale Juice
   for HP recovery (skipped if Charm is queued and
   `save_energy_under_charm: true`)
4. **Mood items** — Cupcake / Sweet Cupcake for mood < 4
5. **Megaphones** — applied before big races (G1/G2 by default)
6. **Wristlet Anklet** — race entry guarantee

**Item usage is now surfaced in Decision Reasoning** (v6.7.10) so you
can see exactly what was consumed and why per turn.

## Profiles and stat priorities

Character profiles (under `data/character_profiles/`) carry per-trainee
training and solver overrides. The active profile is matched by
`card_id`, with auto-derivation for unknown trainees.

Each profile has:

- `solver_overrides` — per-character weight overrides applied UNDER the
  preset's explicit weights
- `target_epithets` — explicit epithet goals for this trainee
- `auto_pick_epithets` — when ON, the trainee's signature epithets
  seed `target_epithets`. Default OFF since v6.7.6 (the solver picks
  high-value races organically).
