# Pre Icarus v5.25 Umabot Stability Backports

This build ports low-risk stability and maintainability patterns from Umabot while keeping Pre Icarus's existing UI and feature contracts intact.

## Included improvements

- `uma_api/client.py` now uses an iterative API retry loop for result codes 205/208 instead of recursive calls. The 205 and 208 counters are independent, 208 uses exponential backoff, and HTTP 500 joins 502/503/504 as retryable.
- `career_bot/runner.py` now refreshes career state whenever a valid API response lacks `data.chara_info`, preventing `KeyError: turn` crashes after race recovery responses.
- `career_bot/runner.py` reconciles 205/208 errors from `race_entry` by reloading career state and continuing if the server actually entered a race.
- `career_bot/scenarios/mant.py` detects stale race states where `race_start_info` remains even though the race is already in `race_history` and home commands are enabled.
- `main.py` now uses `safe_public_path()` for public asset routes and exposes `/api/career/rescue`, guarded so it can only run while the runner is stopped.
- `public/js/monitor.js` remains a standalone optional monitor component and now exposes a small `window.SweepyCareerMonitor` handle for manual refresh/open calls.
- Optional theme and UI-polish styles are layered through `public/css/shell.css` instead of growing `public/styles.css`.
- Parent filtering now scans parent and guest-parent grids and continues to hide/reorder cards without removing DOM nodes during filtering or sorting.

## New regression tests

- `tests/test_ui_contract.py`
- `tests/test_sweepymodv525_umabot_stability.py`
- `tests/test_crash_scenario.py`
- `tests/test_stale_race_state.py`
- `tests/test_tp_recovery.py`

Validation command used:

```bash
node --check public/app.js
node --check public/js/monitor.js
python -m py_compile main.py manager.py uma_api/client.py career_bot/runner.py career_bot/scenarios/mant.py
python -m pytest tests -q
```
