# Unsaved-changes guard for settings modals (#4)

Date: 2026-06-28 · Status: approved, implemented · Area: v3 frontend (`public-v3`)

## Problem

Every v3 settings modal has a separate **DONE/close** path (the top-right `[data-close]`
button, the backdrop, and `Escape`) that closes the modal **without saving**, distinct
from the explicit **SAVE** button. A user who edits settings and then closes via DONE
(or backdrop/Esc) silently loses their changes. #4 asks for a confirm prompt on close
when there are unsaved changes.

## Decisions (user-confirmed)

1. **Triggers:** all three close paths — DONE/X, backdrop click, `Escape`.
2. **Prompt buttons:** **Save Changes** + **Discard Changes** only. Dismissing the prompt
   itself (its backdrop / `Esc`) acts as *keep editing*.
3. **Dirty semantics:** *only saveable changes* count — the prompt fires only if something
   the modal's SAVE button would actually persist has changed. Editing a display-only
   control (e.g. the Smart Solver's Character Preset, which isn't persisted) does not fire it.

## Approach

**Collector-snapshot dirty-check + central close-path guard.** Rejected alternative:
event-based "mark dirty on any interaction" — it false-fires on search boxes and
display-only controls, contradicting decision #3.

Each settings modal already has an exact "what-would-be-saved" function — its
`SAVE_COLLECTORS[url]` entry. Snapshotting `JSON.stringify(collector(o))` after the
modal's init, and comparing on close, is precise and reuses tested code.

## Components

### 1. `core.js` — central guard hook (one-time)
`modal()`'s three close paths call a local `attemptClose()` which delegates to
`o._guardClose(closeModal)` when present, else calls `closeModal()` directly. `escClose`
retargets to the **topmost** overlay and honors its `_guardClose`. Overlays that don't set
`_guardClose` (career / login / priority-editor / recSupports) are unaffected.

### 2. `modals.js` — guard installed uniformly in `wireSave(o)`
When the overlay has a `[data-save]` button:
```
o._guardClose = (close) =>
  (o._cleanSnap != null && snapshot(o) !== o._cleanSnap)
    ? showUnsavedConfirm(o, close)
    : close();
```
`snapshot(o) = JSON.stringify(collectorFor(o)(o) ?? null)` using the *same* collector the
save button uses. If `_cleanSnap` is null (unarmed) it degrades to a silent close (no
false alarms).

### 3. `modals.js` — `armUnsavedGuard(o)`
Sets `o._cleanSnap = snapshot(o)`. Called **after each modal's async init resolves** (via
`Promise.resolve(initFn(o)).then(() => armUnsavedGuard(o))`) so the baseline reflects the
loaded/saved values, not the template defaults. Applied to all 8 settings modals:
training, racing, scenario, solver, skills, customDeck, userdata, discord.

### 4. `modals.js` — `showUnsavedConfirm(o, close)`
A small raw overlay (NOT via `modal()`, to avoid its closeModal-first), layered above the
settings modal, reusing existing `.modal` styling:
- **SAVE CHANGES** (`data-uc-save`) → remove popup, then click the modal's `[data-save]`
  button (existing collect → POST → close path).
- **DISCARD CHANGES** (`data-uc-discard`) → remove popup, then `close()`.
- Backdrop / `Esc` on the popup → remove popup only (= keep editing; handled by the
  existing `escClose` targeting the topmost overlay, which has no guard).

## Data flow (dirty path)
open → init loads saved values → `armUnsavedGuard` snapshots clean → user edits a
persisted control → user closes (X/backdrop/Esc) → `attemptClose` → `_guardClose` →
`snapshot != clean` → `showUnsavedConfirm` → Save (saves+closes) | Discard (closes) |
dismiss (keep editing).

## Edge cases
- Clean close → snapshot == clean → closes silently.
- The SAVE button bypasses the guard (closes via `closeModal()` directly) — no double prompt.
- Modals without `[data-save]` (recSupports) → no guard installed.
- Display-only controls (solver char/aptitudes/epithets; discord notify toggles) have no
  collector entry → never mark dirty (matches decision #3).
- `customDeck` collector returns `null` when empty → `"null"`; adding cards → payload → dirty.
- Save failure → `wireSave` still closes (pre-existing behavior); acceptable.
- Nested priority editor (own overlay, own commit-on-close) unaffected.

## Testing
- Python source-contract test (`tests/test_unsaved_guard_20260628.py`): core.js routes
  closes via `_guardClose`/`attemptClose` and `escClose` honors the guard; `wireSave`
  installs `_guardClose` using the collector snapshot (`_cleanSnap`); `armUnsavedGuard`
  defined + invoked in all 8 settings onMounts; confirm popup has `data-uc-save` +
  `data-uc-discard`. Plus `node --check` on both files.
- The DOM interaction itself is **manually live-verified** (no jsdom in the repo).

## Live-verify checklist
1. Open each settings modal, change one persisted control, click DONE → prompt appears.
2. Save → value persisted (reopen confirms); Discard → value reverts; backdrop/Esc on the
   prompt → returns to the modal.
3. Open a modal, change nothing, close → no prompt.
4. Edit + click SAVE directly → saves, no double prompt.
5. Smart Solver: change only the Character Preset (display-only) + close → no prompt;
   change a Scoring Weight + close → prompt.

## Cache versions
`core.js v=11→12` (accounts, diag, events, help, history, index, setup) and
`modals.js v=14→15` (diag, setup). No CSS change (confirm reuses `.modal*`).
