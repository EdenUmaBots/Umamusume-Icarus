# Pre Icarus v5.26 Operator Controls

This update ports selected UmaAuto/UmaBot operator-control patterns while keeping Pre Icarus's Trackblazer and existing dashboard contract intact.

## True pause/resume

`CareerRunner.pause()` now requests a pause that is honored only at safe checkpoints: before state refresh/decision work and immediately before executing the next game action. This avoids interrupting mid-transaction race, event, item, or command calls. `/api/career/runner/pause` and `/api/career/runner/resume` expose the state to the UI.

## Explicit run counts

The dashboard now sends `run_count` with `/api/career/run`:

- `1` runs one career.
- `N` runs exactly `N` careers.
- `0` loops until stopped.

For guest/rental parents, infinite looping is rejected. Finite loops are allowed, but every next career start reuses the existing `_pre_start_refresh()` path so rental/guest parent availability is checked and refreshed before the run begins.

## Event Choices

Runtime event overrides live under `uma_runtime/event_overrides.json`; seen events live under `uma_runtime/events_seen.json`. Runtime overrides are applied before preset event overrides and before weighted scoring, so the user-facing Event Choices UI is authoritative without editing generated data files.

## Discord setup

The Diagnostics card has a simple webhook save/test flow. It writes into `settings.json` under `discord_logging`, which is already read by `career_bot.discord_logger`. Sensitive webhook URLs continue to be redacted by existing Discord telemetry sanitization.
