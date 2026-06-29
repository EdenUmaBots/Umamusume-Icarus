# Team Sirius + Heirs to the Throne — Group-Card Outing Feature (v2)

**Date:** 2026-06-27 (v2 — reconciled with `STEAL_THE_MOOON.md`)
**Status:** ✅ IMPLEMENTED 2026-06-27 (779 tests green incl. 42 new in `tests/test_sirius_throne_schedule.py`). Needs `python main.py` restart + the card-step-id live-verify (§9). v3 UI only.

**As-built deviations from this spec:**
1. **Items layer:** did NOT add a separate `_rescue_energy_target`. Icarus's existing `items.py _energy_targets` already tops up low-vital camp turns (no rainbow requirement), and the strategy's `_can_rescue_training` camp gate (already wired at `mant_trackblazer.py:384`) makes the bot *choose* to train on weak camp turns — so the camp all-out works end-to-end without duplicating the tuned item logic. Only `SUMMER_TRAINING_TURNS` was added to items.py (for parity + the cross-module test).
2. **Manual-race interaction:** the scheduled veto is NOT gated on manual mode (matches the spec's "fires first"). So on a scheduled-outing turn while in manual-race mode, the outing takes priority over a manually-scheduled race. Rare (schedule turns are bond turns) + recoverable via catch-up; flagged for the user. Free mode is naturally compatible with manual (fires only at the rec/rest gates, after racing).
3. **Knobs** read from `mant_config` via `cfg.get` (Icarus convention), not top-level `preset.get` (the source/spec style) — tests pass `{"mant_config": {...}}`.
**Authoritative spec:** `C:\Users\hiipp\Downloads\STEAL_THE_MOOON.md` (supersedes the source-bot port where they differ)
**Source bot (reference for scheduled mode only):** `Mcqueen-uma-auto-main/career_bot/scenarios/mant.py`
**Target:** `C:\Icarus\Icarus\Icarusv2.1 (Dev)`

---

## 0. What changed in v2 (delta from the v1 plan)

The v1 plan was a straight port of the source bot (a single **boolean** `sirius_throne_schedule`, scheduled mode only). `STEAL_THE_MOOON.md` expands the feature materially:

| # | Change | v1 plan | v2 (this doc) |
|---|--------|---------|---------------|
| 1 | **Setting shape** | boolean `sirius_throne_schedule` | **3-state `sirius_throne_strategy`**: `scheduled` / `free` / `off` / auto |
| 2 | **Free mode (Mode B)** | did not exist | **NEW** — opportunistic outing that replaces mood-rec/non-critical-rest, any available character, no calendar. **Not in the source bot — built fresh.** |
| 3 | **Readers** | `_support_slot` + `_slot_row` helpers | inline `position`-based `_char_outing_state` / `_card_row_state` / `_group_card_slots` (doc's exact impls) |
| 4 | **`support_list.json` 30067** | "add it" | **already present in Icarus** (verified) — doc is wrong for our repo; **no data change** |
| 5 | **UI** | 5 toggles | a 3-state **select** (Auto/Scheduled/Free/Off) + 4 sub-toggles **shown only in scheduled mode** |
| 6 | **Tests** | port 49 scheduled tests | port scheduled tests **+ add free-mode tests** |

Everything else (constants, the 12-turn schedule, goal-driven `_scheduled_recreation`, junior focus, summer all-out, runner stall/error guards, the card-step live-verify gate) is unchanged from v1.

---

## 1. What the cards are

**Team Sirius** (`30081`) + **Heirs to the Throne** (`30067`) are SSR **"Group"** support cards. They add a second recreation command to the turn menu, **`command_id 390`** (`command_type 3`), that opens a **character-selection outing** (distinct from normal mood recreation `301`). Used right, they're the run's primary bond + rainbow lever → SS/UG.

A deck **without** either card is **byte-identical** to current behavior regardless of the setting. Every new branch is gated by `_deck_has_group_cards()`.

---

## 2. The setting: `sirius_throne_strategy` (3-state)

| Value | Behavior |
|-------|----------|
| `"scheduled"` (Mode A) | Fixed-turn calendar: fire specific characters at specific turns + card-itself steps in order; junior bond focus + summer all-out. |
| `"free"` (Mode B) | Opportunistic: whenever the bot would do mood recreation or a non-critical rest, fire `390` with any available character instead. No calendar, no junior/summer changes. |
| `"off"` | No group-outing logic at all; `390` is never used. |
| auto (`None`/`""`) | `scheduled` if a group deck is present, else `off`. |

Resolver (Icarus reads from `mant_config`, per the established knob convention — **not** top-level `preset.get()`):

```python
def _strategy_mode(self, chara, preset):
    cfg = ((preset or {}).get("mant_config") or {})
    mode = cfg.get("sirius_throne_strategy")
    if mode in ("scheduled", "free", "off"):
        return mode
    return "scheduled" if self._deck_has_group_cards(chara) else "off"   # auto
```

**Sub-settings (scheduled mode only), all in `mant_config`, default ON:**
`sirius_throne_card_outing`, `sirius_throne_junior_focus`, `summer_all_out`, `dump_recreation_debug`.

---

## 3. Constants (`mant.py`)

```python
TEAM_SIRIUS_SUPPORT_ID   = 30081
THRONE_SUPPORT_ID        = 30067
SIRIUS_THRONE_GROUP_IDS  = frozenset({30081, 30067})
GROUP_OUTING_COMMAND_ID  = 390          # command_type 3, needs select_id
CARD_SIGNATURE_CHARA     = {30081: 1001, 30067: 1017}   # best guess — live-verify (§9)
JUNIOR_FOCUS_LAST_TURN   = 11
GROUP_CARD_OUTING_MAX    = 2             # Throne 2 steps, Sirius 1
# Broad blackout incl. 36/60 race weeks — distinctly named to avoid clashing with
# mant_trackblazer.py's NARROW SUMMER_CAMP_TURNS = {37-40,61-64}.
RECREATION_BLACKOUT_TURNS = frozenset({36,37,38,39,40,60,61,62,63,64})
RACE_VALUE_CAMP_TURNS    = frozenset({37,38,39,40,61,62,63,64})   # == items.SUMMER_TRAINING_TURNS
SIRIUS_THRONE_RECREATION_SCHEDULE = {
    18:(1002,30081,"Silence Suzuka"), 22:(1016,30081,"Narita Brian"),
    26:(1017,30067,"Symboli Rudolf"), 28:(1030,30081,"Rice Shower"),
    32:(1001,30081,"Special Week"),   35:(1003,30067,"Tokai Teio"),
    43:(1013,30081,"Mejiro McQueen"), 47:(1073,30067,"Tsurumaru Tsuyoshi"),
    51:(None,30067,"Throne card step 1"), 55:(1035,30081,"Winning Ticket"),
    58:(None,30081,"Sirius card step 1"), 59:(None,30067,"Throne card step 2"),
}
```

`items.py`: add module-level `SUMMER_TRAINING_TURNS = {37,38,39,40,61,62,63,64}` (must equal `RACE_VALUE_CAMP_TURNS`; a test asserts it). **⚠ verified: it does not exist in Icarus's items.py yet.**

> NB: where `_scheduled_recreation` checks the summer blackout, use `RECREATION_BLACKOUT_TURNS` (broad). Do not reuse the narrow `SUMMER_CAMP_TURNS` already in `mant_trackblazer.py`.

---

## 4. Engine mapping (verified against Icarus source 2026-06-27)

Icarus deleted the source's legacy `_best_command`. `mant.py` `MantStrategy.next_decision` (line 161) → delegates to `mant_trackblazer.py` `MantTrackblazerCore.decide()` (line 214). So:

| Piece | Lands in |
|-------|----------|
| Constants + read-only helpers + `_scheduled_recreation` + `_free_group_outing` + `_strategy_mode` + `_dump_recreation_debug` | `mant.py` (`MantStrategy`) |
| `_can_rescue_training` camp-all-out upgrade | `mant.py` (already called by core at `mant_trackblazer.py:384`) |
| `_recreation_command` `!= 390` guard | `mant.py` (line 208) |
| **Scheduled veto** call site | `mant_trackblazer.py decide()` — after the mandatory-race block (~line 248), before the marquee/solver racing |
| **Free-mode** call sites | `mant_trackblazer.py decide()` — recreation gate (~355-371) and rest gate (~379-390) |
| **Junior focus** | `mant_trackblazer.py _train()` (~437) |
| Energy-rescue mirror `_rescue_energy_target` | `items.py` |
| Loop-breakers (`_last_outing_turn`, stall/error → strategy block flags) | `runner.py` |
| 3-state setting + 4 sub-toggles | `public-v3/modals.js` (Training Settings modal) |
| Storage round-trip | none — `mant_config` already passes through (`presets.py:98`, `config_store.py:23`) |
| Tests | `tests/test_sirius_throne_schedule.py` (scheduled) + free-mode tests |

**Verified facts (2026-06-27):** both cards already in `support_list.json` (no data change); `mant.py`: `__init__(race_planner=None)` (31), `next_decision` (161), `_recreation_command` (208), `_can_rescue_training` (396); `mant_trackblazer.py`: `decide` (214), recreation/rest computed (256-257), mood-rec gate (355-371), rest gate (379-390), `_can_rescue_training` called (384), `_train` (437); `items.py`: `use_items` (1053), `_energy_targets` (1402), `ENERGY_ITEMS` (160), **no** `_rescue_energy_target`, **no** `SUMMER_TRAINING_TURNS`; `mant_trackblazer.py` `SUMMER_CAMP_TURNS` is the narrow `{37-40,61-64}`.

---

## 5. Read-only helpers (`mant.py`) — use the doc's exact impls

```python
def _deck_has_group_cards(self, chara):
    ids = {int(c.get("support_card_id") or 0) for c in (chara.get("support_card_array") or [])}
    return bool(ids & SIRIUS_THRONE_GROUP_IDS)

def _char_outing_state(self, chara, chara_id):           # (is_outing, story_step)
    for row in chara.get("evaluation_info_array") or []:
        for g in row.get("group_outing_info_array") or []:
            if int(g.get("chara_id") or 0) == chara_id:
                return int(g.get("is_outing") or 0), int(g.get("story_step") or 0)
    return 0, 0

def _card_row_state(self, chara, support_id):            # (is_outing, story_step) of the card-itself row
    slot = next((int(c.get("position") or 0) for c in chara.get("support_card_array") or []
                 if int(c.get("support_card_id") or 0) == support_id), None)
    if slot is None: return 0, 0
    row = next((r for r in chara.get("evaluation_info_array") or []
                if int(r.get("target_id") or 0) == slot), None)
    if not row: return 0, 0
    return int(row.get("is_outing") or 0), int(row.get("story_step") or 0)

def _group_card_slots(self, chara):                      # deck positions (== training partner ids)
    return [int(c.get("position") or 0) for c in chara.get("support_card_array") or []
            if int(c.get("support_card_id") or 0) in SIRIUS_THRONE_GROUP_IDS]

def _get_group_outing_cmd(self, enabled):
    return next((c for c in enabled if c.get("command_type") == 3
                 and int(c.get("command_id") or 0) == GROUP_OUTING_COMMAND_ID), None)

def _build_outing_command(self, outing_cmd, select_id):
    chosen = dict(outing_cmd); chosen["select_id"] = int(select_id); return chosen
```

`__init__` flags: `self._scheduled_outing_blocked = False`, `self._card_outing_blocked = False`, `self._pending_outing_is_card = False`.

The strategy returns the cloned `390` command + `select_id`; Icarus's runner already translates `command_type==3` into the `{command_group_id:390, select_id}` payload (existing swap), so no exec-layer change is needed beyond the runner guards (§8).

---

## 6. Mode A — Scheduled

`_outing_plan()` flattens `SIRIUS_THRONE_RECREATION_SCHEDULE` into turn-sorted steps (char before card; Throne 2 card steps, Sirius 1), each `{turn, kind, support_id, chara_id/step, select_id}` (char `select_id = chara_id`; card `select_id = CARD_SIGNATURE_CHARA[support_id]`).

`_scheduled_recreation(enabled, turn, chara, preset)` — goal-driven: earliest step that is **due** (`step.turn <= turn`), **not done** (`story_step < 1` / card `story_step < step`), **available** (`is_outing == 1`); card steps only after the signature char is done; sets `_pending_outing_is_card`; returns `None` during `RECREATION_BLACKOUT_TURNS`, when `390` is absent, when `_scheduled_outing_blocked`, or nothing due. (Verbatim logic from `STEAL_THE_MOOON.md` §"`_scheduled_recreation`", with `cfg.get(...)` instead of `preset.get(...)` for the `sirius_throne_card_outing` sub-knob.)

**Veto wiring** in `decide()` — insert after the mandatory-race block (after ~line 248), before the marquee/solver racing:

```python
if self._strategy_mode_is(chara, preset, "scheduled"):
    sched = self.ref._scheduled_recreation(commands, turn, chara, preset)
    if sched:
        return self._as_command(sched, chara, "trackblazer: scheduled group outing")
```

(Outings never fire in summer — the `237` force-train branch and the blackout guard keep camp turns training-only. Mandatory in-game races at `241` still win; a slipped scheduled outing is caught up the next available turn.)

**Junior focus** (`_train()`, ~line 452 before `scored[0]`): when `turn <= JUNIOR_FOCUS_LAST_TURN`, group deck, and `cfg.get("sirius_throne_junior_focus", True)`, re-pick by `(group-partner-count, _bondable_count, score)`.

**Summer all-out** (`_can_rescue_training`, mant.py:396): add `camp_all_out = cfg.get("summer_all_out", True) and self._deck_has_group_cards(chara) and turn in RACE_VALUE_CAMP_TURNS`; `strong = best_score >= threshold or camp_all_out`. Mirror in `items.py _rescue_energy_target` with the same gate. Only active in scheduled mode (`_strategy_mode == "scheduled"`).

---

## 7. Mode B — Free (NEW; built fresh per the spec, not in the source)

```python
def _free_outing_select_id(self, chara):
    for row in chara.get("evaluation_info_array") or []:
        for g in row.get("group_outing_info_array") or []:
            if int(g.get("is_outing") or 0) == 1 and int(g.get("story_step") or 0) < 1:
                return int(g.get("chara_id") or 0)
    return 0

def _free_group_outing(self, enabled, turn, chara):
    if getattr(self, "_scheduled_outing_blocked", False): return None
    if not self._deck_has_group_cards(chara): return None
    if turn in RECREATION_BLACKOUT_TURNS: return None
    outing_cmd = self._get_group_outing_cmd(enabled)
    if not outing_cmd: return None
    self._pending_outing_is_card = False
    return self._build_outing_command(outing_cmd, self._free_outing_select_id(chara))
```

**Wiring in `decide()` (free mode only):** define `free_mode = self._strategy_mode_is(chara, preset, "free")` near the top, then substitute at the two gates:

- **Recreation gate** (`mant_trackblazer.py` ~355-371): before `return self._as_command(recreation, ...)`, if `free_mode` and `_free_group_outing()` returns a command → return it.
- **Rest gate** (~379-390): after the energy-rescue check fails, before `return rest`, if `free_mode` and `_free_group_outing()` returns a command → return it.

Free mode applies no junior/summer changes, never fires on `RECREATION_BLACKOUT_TURNS`, never overrides a scheduled slot (modes are mutually exclusive), and falls back to the normal recreation/rest exactly as before when `_free_group_outing` returns `None`. `_pending_outing_is_card` is always `False`.

> Helper: `_strategy_mode_is(self, chara, preset, want)` = `self._strategy_mode(chara, preset) == want` — keeps the call sites terse and the resolver single-sourced.

---

## 8. Runner guards (both modes) — `runner.py`

Unchanged from v1. Import `GROUP_OUTING_COMMAND_ID`; `self._last_outing_turn = None` per career; reset strategy block flags per **new game turn** (turn-keyed, not per inner-loop). Before `exec_command` for `command_type==3 && command_group_id==390`: if `_last_outing_turn == current_turn` → stalled → read `strategy._pending_outing_is_card`, set `_card_outing_blocked` (card) or `_scheduled_outing_blocked` (char), log `outing_stalled`, `continue`; else record `_last_outing_turn`. In the except block (before any re-raise): same → set the matching flag, log `outing_exec_failed`, `continue` — a bad outing must never kill the career.

| Failure | Flag | Characters still fire? |
|---|---|---|
| Card-step wrong `select_id` | `_card_outing_blocked` | ✅ |
| Character outing HTTP error | `_scheduled_outing_blocked` | ❌ (systemic) |

Flags live on the **strategy** object (fresh per career); the runner reads via `getattr(strategy, attr, False)`.

---

## 9. Card-step `select_id` live-verify gate (per earlier user decision)

Character `select_id = chara_id` is **confirmed**. Card-itself `select_id = CARD_SIGNATURE_CHARA[support_id]` (Sirius 1001 / Throne 1017) is a **best guess**. Rollout: implement everything (char outings confirmed; card steps use the guess) with `dump_recreation_debug` on → user runs one live Sirius+Throne career → `recreation_debug_t51/58/59.json` captured → confirm/correct the id → **then** build to beta. Until then the runner's isolation degrades a wrong card-step id to a blocked card step only; **character outings (the bulk of the value) keep working**.

---

## 10. UI — v3 Training Settings modal (`public-v3/modals.js`)

Add inside the `training()` modal, in a new `sec('GROUP CARDS (SIRIUS / THRONE)', ...)`:

- A 3-state **select** via the existing `sel()` helper:
  `sel('Sirius Throne Strategy', [['','Auto'],['scheduled','Scheduled'],['free','Free'],['off','Off']], '', '<help>', 'mant.sirius_throne_strategy')` — `''` = Auto (engine resolves to scheduled on a group deck). Round-trips automatically (`data-k`, type `str`).
- Four sub-toggles via `toggle(..., true, ..., 'mant.<key>')`: `sirius_throne_card_outing`, `sirius_throne_junior_focus`, `summer_all_out`, `dump_recreation_debug`.
- **Conditional visibility:** the 4 sub-toggles show only when the strategy select is `scheduled` (or Auto-resolving-to-scheduled). Add a small `change` listener on the select that toggles a CSS class (`hidden`) on the sub-toggle rows; run it once on modal mount. (Cosmetic — the engine already ignores them outside scheduled mode, so this is polish, not correctness.)

Storage = `mant_config` (no `presets.py` change — already round-trips). Default-ON for the sub-toggles via literal `true` markup + engine `cfg.get(key, True)`. `data-k` strings must exactly equal the engine keys. **v3 only** (per earlier decision).

---

## 11. Tests — `tests/test_sirius_throne_schedule.py`

Port the scheduled suite from `STEAL_THE_MOOON.md` §"Port These Tests" (deck detection, goal-driven firing incl. late-unlock catch-up + card steps + block isolation, schedule invariants, junior focus, all-out summer mirror, `RACE_VALUE_CAMP_TURNS == SUMMER_TRAINING_TURNS`). Adapt: knobs passed via `{"mant_config": {...}}` (Icarus reads `cfg.get`); junior-focus tests target a `MantStrategy.junior_focus_pick` helper the core also calls; items/`_can_rescue` tests set `summer_all_out` in `mant_config`.

**Add free-mode tests** (not in the source): `_free_outing_select_id` picks first unlocked+undone char / returns 0 when all done; `_free_group_outing` returns a `390` command with that `select_id`; returns `None` on `RECREATION_BLACKOUT_TURNS` / no group deck / `_scheduled_outing_blocked` / `390` absent; `_strategy_mode` resolves scheduled/free/off/auto correctly. Plus Icarus integration tests: `decide()` returns the scheduled outing on a due scheduled turn; `decide()` substitutes a free outing at the recreation gate and the rest gate in free mode; neither fires during the blackout or over a mandatory race.

---

## 12. Risks

- **Engine mismatch (highest):** call sites are hand-wired into `decide()`/`_train()`, not copy-pasted. The scheduled veto must sit after mandatory races (so the game's forced race wins) and the free-mode hooks must sit exactly at the recreation/rest gates (not earlier) so they only replace those two decisions.
- **Two summer sets:** use the broad `RECREATION_BLACKOUT_TURNS` for the outing blackout, the narrow `RACE_VALUE_CAMP_TURNS` for all-out — don't shadow `mant_trackblazer.SUMMER_CAMP_TURNS`.
- **`_recreation_command` must skip 390** or the bare recreation path can fire `390` with no `select_id` (esp. in free mode where `recreation` is computed at 257).
- **Card-step id unverified** → §9 gate + isolation fallback.
- **Per-turn flag reset must be turn-keyed**, not per inner-loop iteration.
- **`SUMMER_TRAINING_TURNS` missing** in items.py → add it (silent ImportError otherwise).
- **Conditional UI** is cosmetic; if the show/hide is skipped the feature still works (engine ignores sub-knobs outside scheduled mode).

---

## 13. Out of scope
- Non-group decks stay byte-identical.
- Old UI (`public/`) — v3 only.
- `mant_trackblazer` Trackblazer scorer internals beyond the named insert points.

---

## 14. Decisions captured
- **Plan only** until explicit go-ahead.
- Setting = **3-state `sirius_throne_strategy`** (Auto/Scheduled/Free/Off), in the **v3 Training Settings modal**, stored in `mant_config`.
- **Free mode** is new (built fresh), substituting at the recreation + rest gates only.
- **Live-verify the card-step id** before locking / beta (§9).
- `support_list.json` already has both cards — **no data change**.
