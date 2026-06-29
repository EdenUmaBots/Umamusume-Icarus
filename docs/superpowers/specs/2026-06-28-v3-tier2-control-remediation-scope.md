# Scope: v3 tier-2 control remediation

Date: 2026-06-28 · Status: **BUILT 2026-06-29** · From the v3 dead-control audit
(see [[icarus-ui-batch-20260628c]]). Tier-1 already wired; both items below DONE.

## BUILT 2026-06-29
- **Discord notify toggles — all 3 wired as real per-event flags.** Backend:
  `discord_logger.py` DEFAULT_CONFIG + load_config gain `notify_on_finish`(T) /
  `notify_on_crash`(T) / `notify_on_epithet`(F); `finish_career` routes a crashed
  end (last_error) → notify_on_crash and a clean end → notify_on_finish; new
  `notify_epithet(names)` gated on notify_on_epithet, called from
  runner `_epithet_completion_line` when a NEW epithet completes (guarded).
  Endpoint: `DiscordWebhookRequest` + `set_discord_webhook` persist the 3;
  GET `_discord_logging_config` returns them. Frontend: `modals.js` discord()
  toggles carry `data-k` keys, the save collector reads them, onMount restores
  from GET; modals.js?v=18. Tests: tests/test_discord_notify_20260629.py (13).
- **Auto-solve label REMOVED.** setup.js:288 dead decorative `<label>` deleted
  (smart mode already solves at career start; it backed nothing). setup.js?v=28.
- Needs `python main.py` restart + hard-refresh. Folds into next build (~v3.2.2).

---

## Original scope (below)

Date: 2026-06-28 · Status: SCOPED · Tier-1 already wired; these two need decisions.

## 1. Discord "Notify on…" toggles (finish / crash / new epithet) — needs BACKEND

**Current state:** the 3 toggles in the Discord modal are decorative (no `data-k`,
not collected). The backend (`main.py` `set_discord_webhook` + `discord_logger.py`)
stores only `{enabled, webhook_url, send_turn_logs, send_career_summary,
redact_sensitive}` and **hardcodes `send_*=True`** — there are no per-event gates,
and **no epithet-specific Discord send path exists at all**. So they can't be wired
frontend-only; this is a backend feature.

**Work to make them real:**
- **Config + endpoint:** add `notify_on_finish`, `notify_on_crash`,
  `notify_on_epithet` to the discord config + `DiscordWebhookRequest` model +
  `_save_discord_logging_config` (default all `True` to preserve current behavior).
- **Gate the send sites:** career-finish send (`discord_logger.finish_career` /
  `send_career_summary`) → gate on `notify_on_finish`; crash/stuck path
  (`runner.py` error handler ~1140) → gate on `notify_on_crash`; **new**: add an
  epithet-earned send hook (none exists today) gated on `notify_on_epithet`.
- **Frontend:** make the 3 toggles `data-k`-bound and round-trip via the discord
  collector + an `initDiscord` sync (the collector currently only sends
  `{webhook_url, enabled}` — extend it).
- Effort: small for finish/crash (reuse existing gates), **medium for epithet**
  (needs a new send path). 

**Alternative (cheaper, honest):** wire `notify_on_finish` + `notify_on_crash`
only (reuse existing sends) and **drop the "new epithet" toggle** until/unless an
epithet send hook is wanted. Decision needed: build the epithet hook, or drop it.

## 2. Setup "auto-solve before run" label — decorative, recommend REMOVE

**Current state:** `setup.js:~288` renders a `<label>` with a fake green ✓ span and
the text "auto-solve before run" — **no `<input>`, no backing state, read nowhere**
(grep: 1 occurrence). It looks like an always-checked toggle but does nothing.

**Why it's likely redundant:** in smart mode the engine already solves the schedule
at career start (`extra_race_list_source=smart` → live solve in `races.py`), so an
"auto-solve before run" setting wouldn't change behavior.

**Recommendation: REMOVE the label** (1-line delete) — it's misleading decoration.
If an explicit pre-run auto-solve *convenience* is actually wanted, that's a
separate small frontend feature (call the existing SOLVE/APPLY flow on RUN CAREER),
not a backend setting — but default smart-mode behavior already covers it.

## Also still open (tier 2, not in this scope)
Diag/AI page ~15 bare buttons (`TRAIN NOW`, `EXPORT LOGS`, etc.) = unwired
scaffolding; several map to real endpoints (`/api/ai/train-now`, export-logs) so
they could be wired OR hidden behind a "preview" label. Separate decision.
