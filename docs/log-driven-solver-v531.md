# Pre Icarus v5.31 Log-Driven Smart Race Solver Improvements

This build turns recent Android-vs-Sweepy career-log findings into solver and observability changes.

## Solver intelligence

The Smart Race Solver now adjusts schedule scoring using local runtime evidence:

- **Observed outcome risk** from `uma_runtime/race_outcomes.json` penalizes races that repeatedly fail for the current install.
- **Late Senior pressure** adds value to good races in turns 65-72 so fan-farming routes do not drift into unnecessary training/rest after Senior summer.
- **Long-distance stamina risk** applies a configurable penalty to 3000m+ races when the current stamina snapshot is below the configured safety floor.
- **Item/recovery support** can add feasibility value when race items, energy items, or clocks make dense race routing safer.

All of these sit on top of the Android-style objective from v5.30 and can be tuned through solver weights.

## Epithet ledger

Solver output now includes `epithet_ledger`, `dead_epithets`, and per-race `epithet_contributions` so the UI/logs can explain which races progress selected target or forced epithets.

## Re-solving

During active careers, Pre Icarus now re-solves remaining smart-planned races after a solver-planned race is lost. The race planner also attempts a re-solve if a smart-planned race is no longer available on its scheduled turn.

## Logs

Career logs now include:

- `decision_report` per turn with selected action, reason, state snapshot, and race context.
- `race_results[].race_type` so analysis can separate solver-planned races from mandatory/finale/manual/fallback races.
- Atomic JSON log writes plus validation so interrupted writes do not replace the latest valid log with truncated JSON.

