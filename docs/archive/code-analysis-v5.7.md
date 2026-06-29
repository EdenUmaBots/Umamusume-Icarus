# Code Analysis Follow-up for Pre Icarus v5.7

## Purpose

Pre Icarus v5.7 implements the actionable findings from the Pre Icarus v5.6 audit: confirmed bugs, robustness gaps, solver UX improvements, and redundant solver-mode state cleanup.

## Bugs fixed

- Manual Smart Race Solver aptitude overrides are now scoped by selected trainee instead of being stored as one global preset object.
- Explicit low manual aptitudes are no longer overwritten by fallback broad planning aptitudes.
- Summer racing is now blocked when the user disables summer racing instead of merely receiving a penalty.
- Forced epithets are now hard constraints in MILP and Beam solver modes. If no candidate route can satisfy a forced epithet under the native matcher, the solver reports infeasible.
- Trackblazer partial data caches are repaired when any required dataset is missing.
- `/api/trackblazer/plan` now lets intentional `HTTPException(400)` validation errors pass through.
- Numeric solver settings are clamped in both the UI and backend.
- Stale-plan warnings no longer stack duplicate banners.
- Preset hydration no longer uses repeated-list aliasing for nested defaults.

## Improvements implemented

- Solver defaults now live in `data/trackblazer_solver_defaults.json` and are exposed by `/api/trackblazer/solver/defaults`.
- The Smart Race Solver modal displays base aptitude, manual start, estimated parent spark bonus, and solver-final aptitude.
- Epithet picker rendering no longer truncates the available list at 180 entries.
- Schedule previews include hoverable score/explanation hints and a route-diff summary after re-solving.
- The compact Smart Race Solver / Manual Selection buttons are now the only solver-mode control; the modal reports the active mode rather than duplicating it.

## New feature coverage

- Parent spark-aware solver aptitude preview: selected parent aptitude sparks are estimated from available factor data and added to manual/base aptitudes before route solving.
- Forced Epithet Planner behavior: forced epithets are now treated as required native-matcher hits, not just advisory bonuses.
- Route comparison preview: re-solving shows race-count, fan, and score deltas compared with the prior route.

## Validation

```bash
python -m compileall -q career_bot main.py manager.py
node --check public/app.js
python -m unittest discover -s tests -v
```

Expected result in this build:

```text
Ran 58 tests
OK
```
