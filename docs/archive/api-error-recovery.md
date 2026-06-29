# API Error Recovery

## Purpose

API Error Recovery keeps the career runner from crashing on recoverable game-server or session-state failures. It is designed for temporary server errors, session desyncs, stale race/event state, and network interruptions.

## Recoverable codes

The runner treats these errors as recoverable:

- network errors and timeouts
- result code 201
- result code 202
- result code 205
- result code 208
- result code 214
- daily reset and maintenance messages
- `StateRecoveryError`

## Result code 214 behavior

Result code 214 can appear after a race or event check and may then repeat on other endpoints such as `read_info/index` or `user/recovery_trainer_point`. In Pre Icarus v5.2, result code 214 is handled as a recoverable session/state desync.

When 214 is seen during a career run, the runner now:

1. logs a recovery event,
2. waits with backoff,
3. reloads the current career state,
4. drains any remaining unchecked events,
5. resumes decision-making from the refreshed state when recovery succeeds.

## Race path protection

Race and race-progress actions now use the same recovery wrapper as command and event actions. Post-race event draining also catches recoverable 214 errors and refreshes career state instead of crashing the runner.

## Dependencies and interactions

This behavior lives in `career_bot/runner.py`. It uses the existing client login/load recovery path and does not change item, training, racing, or skill-selection logic.

## Verification

Run:

```bash
python -m unittest tests/test_sweepymodv52_api214_recovery.py -v
python -m unittest discover -s tests -v
```

A simulated 214 during post-race event handling should return a refreshed career state instead of raising an uncaught exception.
