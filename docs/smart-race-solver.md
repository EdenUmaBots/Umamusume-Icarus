# Smart Race Solver

## Purpose

Smart Race Solver plans Trackblazer/MANT race schedules using solver-backed race-vs-train decisions rather than simple greedy race picking.

## Solver backends

Pre Icarus supports:

1. SciPy MILP exact backend, when SciPy is installed.
2. Beam-search fallback backend, dependency-free.
3. Older greedy behavior only when explicitly requested.

The solver order is:

```text
Smart Race Solver
  -> scipy MILP exact backend
  -> beam-search fallback
  -> old greedy only when explicitly requested
```

## Beam backend

The beam backend is implemented in `career_bot/trackblazer.py` and ports useful Android solver behavior without Android APIs. It supports manual locks, race-vs-train decisions, consecutive race penalties, summer racing penalties, and shared race scoring.

## MILP backend

The optional MILP backend adds binary race decision variables and constraints for:

- at most one race per turn
- manual race locks
- manual Train locks
- max consecutive racing streak
- summer penalty in the objective
- trainee aptitude filtering
- race reward/cost objective

## UI behavior

The planner supports Smart Race Solver mode and Manual Selection mode. Manual race selections are staged until Apply Manual is clicked. Apply Smart writes the solver plan into the preset.

## Dependencies and interactions

`requirements.txt` includes `scipy>=1.11`. If SciPy is missing or the model is infeasible, Pre Icarus falls back to beam search. Trackblazer P2 added train-turn protection so solver-planned Train turns are not stolen by fallback fan racing.

## Verification

Open the race planner, generate a smart plan, apply it, and verify the preset stores `trackblazer_last_plan`. If SciPy is installed, traces may show `smart-race-solver-milp`; otherwise they may show `smart-race-solver-beam`.
