# Code Analysis Report for Pre Icarus v5.3

## Scope

This review covered the frontend dashboard/settings UI, Trackblazer solver status plumbing, race runner recovery paths, and the existing test suite. The focus was on issues that can cause incorrect behavior, crashes, misleading diagnostics, or hard-to-debug dead paths.

## Findings Fixed in Pre Icarus v5.3

### 1. Diagnostics reported legacy Node bridge status instead of the actual Smart Race Solver backend

- **Files:** `public/app.js`, `career_bot/trackblazer.py`
- **Severity:** Logic error / misleading diagnostics
- **Problem:** The diagnostics UI showed `Node bridge` readiness even though the default Smart Race Solver path now chooses SciPy MILP first, then falls back to Beam. Users could not tell whether MILP or Beam was actually active.
- **Fix:** Added `active_backend`, `active_backend_label`, `milp_available`, and `beam_available` from `/api/trackblazer/solver/status`. The Diagnostics card now shows a MILP/Beam pill.

### 2. API 214 recovery was incomplete on race-entry and race-start paths

- **File:** `career_bot/runner.py`
- **Severity:** Crash / robustness
- **Problem:** Pre Icarus v5.2 recovered from API 214 during post-race event draining, but `race_entry` still only handled 205/208, and initial `race_start` was not wrapped at all. A 214 in either path could still crash the runner.
- **Fix:** Added recoverable-error handling for `race_entry` and initial `race_start`, using the existing backoff and fresh career-state recovery flow.

### 3. Resume race-progress recovery did not use the central recoverable-error policy

- **File:** `career_bot/runner.py`
- **Severity:** Crash / robustness
- **Problem:** `_race_progress()` handled a small hardcoded set of errors on resume `race_out`, but not the central `_is_recoverable_error()` list. Result code 214 could still crash resume/out paths.
- **Fix:** Added recoverable handling to race-progress `race_start`, `race_end`, and `race_out` branches.

### 4. Duplicate unreachable return in race runner

- **File:** `career_bot/runner.py`
- **Severity:** Dead code
- **Problem:** `_race()` ended with two consecutive `return out` statements. The second return was unreachable.
- **Fix:** Removed the duplicate return.

## Remaining Issues Not Fixed Yet

> Follow-up: the actionable items in this section were addressed in `Pre Icarus v5.4`; see `docs/code-analysis-v5.4.md`.


### 1. `_drain_events()` silently returns after 20 unresolved events

- **File:** `career_bot/runner.py`, `_drain_events()`
- **Severity:** Robustness gap / untested path
- **Problem:** If the same event keeps reappearing because the selected choice is invalid, server state is stale, or the response does not clear the queue, `_drain_events()` stops after `limit=20` and returns the still-pending event state. The runner may then attempt training or racing while events remain unresolved.
- **Suggested fix:** Track repeated event IDs and raise/recover when the limit is hit with unresolved events.

```python
if (current.get("data") or {}).get("unchecked_event_array"):
    self._log("event_drain_limit", turn, "pending events remain after drain limit")
    return self._fresh_career_state(client, strategy)
```

### 2. MILP fallback catches every exception and hides implementation defects

- **File:** `career_bot/trackblazer.py`, `make_schedule()`
- **Severity:** Robustness / observability
- **Problem:** The smart solver catches all exceptions from MILP and falls back to Beam. That is good for users, but it also hides real programming errors unless the caller inspects `fallback_reason`.
- **Suggested fix:** Keep fallback behavior, but log the exception type and traceback to diagnostics when `fallback_used` is true.

### 3. Club tracker contains unreachable code after an early return

- **File:** `public/app.js`, `renderClubTracker()`
- **Severity:** Dead code
- **Problem:** The branch handling failed club-tracker data returns and then contains an unreachable guest-parent refresh statement.
- **Suggested fix:** Remove the unreachable lines or move the refresh outside the failure branch if it was intended to run.

### 4. Solver status still keeps legacy Node bridge fields

- **File:** `career_bot/trackblazer.py`, `solver_status()`
- **Severity:** Duplication / compatibility debt
- **Problem:** The response includes both modern MILP/Beam status and old Node bridge status fields. This is retained for compatibility, but future UI code should avoid treating Node bridge readiness as the Smart Race Solver status.
- **Suggested fix:** Keep the fields until older UI/tests no longer reference them, then remove them in a future cleanup build.

## Tests Added

- `tests/test_sweepymodv53_ui_and_recovery.py`
  - Verifies setup buttons are first in the Setup panel above team slots and Preset Configuration.
  - Verifies Diagnostics contains the solver backend indicator.
  - Verifies solver status reports MILP or Beam.
  - Verifies API 214 recovery during `race_entry` and `race_start`.
