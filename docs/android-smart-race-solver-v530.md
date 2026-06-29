# Pre Icarus v5.30 Android Smart Race Solver Port

## Overview

Pre Icarus v5.30 replaces the older soft Trackblazer route heuristics with a local, desktop-native port of the Android bot SmartRaceSolver architecture:

- `SmartRaceSolverSettings` style UI snapshot from the existing Pre Icarus Smart Solver panel.
- Local solver state built from selected trainee aptitudes, preferred distances, manual locks, target epithets, and forced epithets.
- Exact SciPy MILP backend first when constraints can be expressed linearly.
- History-aware beam-search fallback when the exact backend is unavailable or the route requires dependency epithets.
- Structured Android epithet matcher support through `data/android_smart_race_epithets.json`.
- Local source label and bundled race/epithet assets so normal planning no longer depends on the external race planner webpage.

## Scoring

The objective follows the Android solver documentation:

```text
score = sum(race_value) - sum(race_cost) + sum(epithet_reward) - penalties
```

Pre Icarus keeps the existing user-facing weights:

- Race Value Weight
- Epithet Value Weight
- Fan Weight
- Hint Reward Weight
- Consecutive Race Penalty
- Summer Block Penalty
- Race Bonus %
- Race Cost %

v5.30 adds distance preference mode:

- `strict`: excludes off-preference races unless they help a forced epithet.
- `balanced`: strongly prefers selected/trainee distances and penalizes off-preference races.
- `loose`: treats distance as a light preference only.

## Epithet Handling

The solver now evaluates projected race history instead of only tagging individual races. This lets forced epithets that require multiple wins, count filters, and dependency epithets behave like real schedule goals.

MILP encodes direct matcher constraints such as `winRace`, `winRaceTimes`, `winAnyOf`, `winAtLeast`, and `winCount`. Dependency epithets such as `epithetAll` intentionally fall back to the beam backend, where the RaceHistory + EpithetTracker flow can project completions correctly.

## UI Fixes

- The skill list preserves scroll/search position after selecting skills, allowing multiple selections without jumping back to the top.
- The top-right navbar now keeps Runs, Theme, and Logout in separate non-overlapping slots.
- The nav currency label now uses `CARROTS` instead of `JEWELS`, including TP recovery mode labels.
