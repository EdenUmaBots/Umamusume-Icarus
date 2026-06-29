# Career History

## Purpose

Career History provides a current-session summary of completed career runs so users can quickly review recent run outcomes without digging through raw logs.

## How it works

The UI adds a CAREER HISTORY entry beside Setup, Accounts, and Diagnostics. The backend records a completed career entry from the runner snapshot when a run finishes successfully.

The backend endpoint is:

```http
GET /api/career/history
```

Each row may show:

- trainee name
- fans gained
- final stats
- career rating, when available
- aptitudes, when available
- finish time

## Persistence

Career History is in-memory only. It clears when `python main.py` is stopped or restarted. No history files are written.

## Dependencies and interactions

Career History depends on runner completion snapshots. It is display-only and does not affect automation decisions.

## Verification

Complete a career successfully, open Career History, and confirm the run appears. Restart Pre Icarus and confirm the list is empty.
