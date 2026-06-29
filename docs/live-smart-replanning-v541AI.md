# Pre Icarus v5.41AI Live Smart Replanning

Pre Icarus v5.41AI makes the Smart Race Solver a live route system instead of a mostly static pre-run schedule.

## What changed

- Before each smart race decision, `RacePlanner` rebuilds the remaining schedule from the current turn.
- The solver receives current stats, fan count, runtime support, clock policy, and the runner's current race-result ledger.
- Profile-specific learned race risk is used when a trainee/preset has enough data, falling back to global race outcome risk otherwise.
- If the rebuilt smart route says `Train`, legacy fan-farming fallback is suppressed so it cannot override the live plan.
- After each race result before turn 72, the runner rebuilds the remaining route so failed races, clock-rescued wins, and epithet branches affect the next decisions.

## Safety rules

- The AI/live policy layer only adjusts legal Smart Race Solver candidate scores.
- Manual locks and training locks are still honored.
- User clock settings remain the source of truth; learned policy cannot use clocks if Burn Clocks is disabled.
- If live replanning fails, the existing plan remains available and the error is recorded in runner metadata/logs.

## Why it matters

The solver can now react to the run as it unfolds. A lost race can mark an epithet branch as dead, a clock-rescued race remains visible as risk, and changing stat/fan/inventory state can affect later race choices without restarting the career.
