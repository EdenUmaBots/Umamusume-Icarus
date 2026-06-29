# Code Analysis Follow-Up for Pre Icarus v5.4

## Scope

This follow-up implements the remaining actionable findings recorded in `docs/code-analysis-v5.3.md`. The goal was to close robustness gaps without changing user-facing behavior beyond safer recovery and clearer diagnostics.

## Findings Fixed in Pre Icarus v5.4

### 1. `_drain_events()` could return while events were still unresolved

- **File:** `career_bot/runner.py`
- **Severity:** Robustness / untested path
- **Problem:** `_drain_events()` stopped after its loop limit and returned the current state even if `unchecked_event_array` still contained events. If the same event kept reappearing, the runner could move on to a training or race action while the server still expected an event choice.
- **Fix:** `_drain_events()` now tracks repeated event signatures and refreshes career state if the same event repeats four times. If the drain limit is reached and events remain, it logs `event_drain_limit` and refreshes career state without recursively draining the same stuck queue.
- **Validation:** `tests/test_sweepymodv54_audit_followup.py` covers repeated-event recovery.

### 2. MILP fallback hid implementation defects unless callers inspected the returned payload

- **File:** `career_bot/trackblazer.py`
- **Severity:** Observability / robustness
- **Problem:** `make_schedule()` intentionally falls back from MILP to Beam when MILP fails. That is good for uptime, but the exception type and traceback were not persisted to diagnostics.
- **Fix:** MILP fallback now writes diagnostic rows to `uma_runtime/diagnostics/smart_solver_fallbacks.jsonl` and `latest_smart_solver_fallback.json`. The returned schedule also includes `fallback_exception_type`, `fallback_traceback_tail`, and `fallback_log` when fallback logging succeeds.
- **Validation:** `tests/test_sweepymodv54_audit_followup.py` stubs MILP failure and verifies diagnostic logging.

### 3. Solver status still mixed modern MILP/Beam fields with legacy Node bridge fields

- **File:** `career_bot/trackblazer.py`
- **Severity:** Duplication / compatibility debt
- **Problem:** `solver_status()` still returned `node_found`, `node_path`, `bridge_script`, and `bridge_exists`, which could make the UI or external tooling confuse legacy Node bridge readiness with the active Smart Race Solver backend.
- **Fix:** Removed Node bridge fields from `solver_status()`. The authoritative fields are now `active_backend`, `active_backend_label`, `milp_available`, `beam_available`, and `backend_detail`.
- **Validation:** `tests/test_sweepymodv54_audit_followup.py` confirms the legacy fields are no longer exposed.

### 4. Duplicate mandatory-race failure raise remained in `_race()`

- **File:** `career_bot/runner.py`
- **Severity:** Dead code
- **Problem:** `_race()` contained two identical consecutive `raise RuntimeError(...)` lines for mandatory-race failure.
- **Fix:** Removed the unreachable duplicate raise.

## Finding Rechecked Without Code Change

### Club tracker unreachable code

- **File:** `public/app.js`, `renderClubTracker()`
- **Result:** No unreachable guest-parent refresh statement was present in the packaged `Pre Icarus v5.3` source. No code change was needed.

## Tests Added

- `tests/test_sweepymodv54_audit_followup.py`
  - repeated event-drain recovery
  - MILP fallback diagnostic logging
  - removal of legacy Node bridge fields from solver status
