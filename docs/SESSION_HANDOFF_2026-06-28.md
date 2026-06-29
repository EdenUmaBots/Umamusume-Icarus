# Session Handoff — 2026-06-28

In-depth handoff for the next session. Covers everything done this session, the
current build state, pending work with diagnoses, and the queued release steps.
Dev folder is `C:\Icarus\Icarus\IcarusDev`. Project = Icarus, an Umamusume
career-automation bot (Python FastAPI backend + vanilla-JS v3 frontend in
`public-v3/`). Engine = `career_bot/scenarios/mant_trackblazer.py`.

---

## 0. TL;DR — start here next session

1. **Two UI tasks are still PENDING:** **#1** (smart-solver Character Preset defaults to "Admire Vega") and **#4** (cross-cutting "unsaved changes — Save/Discard?" popup). Diagnoses below + in memory `icarus-ui-batch-20260628c`.
2. **The public `Icarusv3.2.zip` is now STALE** — it was built BEFORE the manual-career-resume fix and the post-build UI batch (#5/#3/#2). After #1+#4, **rebuild it** and update CHANGELOG + Help.
3. Several changes need a **live check on a real career** (flagged in §5).
4. Everything is on disk in the dev folder (no build contains the newest changes yet). Full test suite was last green at **924** (before the latest UI/main.py edits — re-run before the final build).

---

## 1. What shipped this session (all in the dev folder)

### A. Skill-purchase redesign (Stage 1+2+3) — DONE, tested
Memory: `icarus-skill-purchase-redesign`.
- **Stage 1 (prior):** schedule-aware activation-condition gate in `career_bot/skills.py` (`evaluate_skill_conditions`, `_skill_condition_can_fire`) — down-weights skills whose `running_style`/`distance_type` conditions can never fire for the trainee.
- **Stage 2/3 (this session):** sheet-driven graded tier. ETL `tools/spreadsheet_skill_tier_scraper.py` → `data/skill_tiers_normalized.json` (289 skills, TT + CM rank columns). `skills.py`: `_load_sheet_tiers`, `_sheet_tier_score`, `DEFAULT_SHEET_TIER_BONUS`, `_normalize_skill_target`, `_disable_singlemode_adjustment`; sheet tier supersedes the coarse legacy `_community_tier_score`. New config `skill_optimization_target` (career|team_trials|champions, default career) + `skill_tier_multipliers` (added to `config_store.py` SKILL_CONFIG_KEYS + defaults; also registered the Stage-1 gate keys). `disable_singlemode` now mode-dependent: hard-drop in career, kept in TT/CM (removed the baked-in −120 in `_load_official_skill_weights`, applied at score time).
- UI: "Skill Optimization Target" dropdown in `public-v3/modals.js` skills modal.
- Tests: `tests/test_v21_skill_tier_sheet.py` (+ preset round-trip in `test_v76_presets.py`).

### B. Clock-retry 2507 fix — DONE, tested, LIVE-CONFIRMED
Memory: `icarus-clock-retry-2507-fix`.
- **Root cause:** race retry = `single_mode_free/continue`. `2507` ⟺ free-continue pool (`home_info.available_free_continue_num`, AFCN) == 0 (transient, daily refresh). The bot treated any 2507 as a PERMANENT "non-retryable" and cached the program_id in a SHARED, never-cleared file → over many loops it banned ~every race. Also `_free_continue_count` returned `max(AFCN, constant_cap)` so it always thought it had 3 free continues → always sent `continue_type=1` and NEVER spent a standard clock (`continue_type=2`).
- **Fixes (`career_bot/runner.py`):** `_continue_error_code(err)` → 2507 transient (not learned), only genuine 205 learned; `_free_continue_count` returns live AFCN only; `_race_retry_policy` mandatory rescue survives `max_retries==0` (`mandatory_rescue_live`); cleared BOTH poisoned `non_retryable_races.json` (IcarusDev/uma_runtime/default + C:/Icarus/Icarus/uma_runtime/default), backups `*.poisoned-20260628.bak.json`.
- **LIVE-CONFIRMED:** user log `career_log_20260628_151104.json` → clocks_used=4, a `continue_type=2` retry won Asahi Hai 13→1 at free_before=0. So spending a standard clock at AFCN=0 IS server-accepted.
- Tests: `tests/test_clock_retry_fix_20260628.py`; rewrote `tests/test_v15_free_continue.py` (counter now reads live AFCN).

### C. Three read-only "use data the game already sends" wins — DONE, tested
Memory: `icarus-api-capability-map` (follow-up paragraph).
- **F3 cap-aware training** (`mant_trackblazer.py`): `_live_stat_cap(chara, idx)` reads `chara_info.max_speed/stamina/power/guts/wiz`; used in `_score_training` for the hard stop + `eff_cap` instead of static `STAT_CAP=1200`. No-op while caps are 1200.
- **F2 server-driven short race** (`runner.py`): `_race_short_mode(state)` reads `home_info.shortened_race_state` to choose `is_short` (default 1=skip, only 0 when skip explicitly locked) — replaced hardcoded `is_short=1`; logs the race-availability flags.
- **F1 route awareness** (`runner.py`): `_route_info(chara)` reads `chara_info.route_id` + `route_race_id_array`; `_update_route_info` stashes it in status (snapshot); soft-lock log now includes route context. (Turn-77 termination left untouched — load-bearing.)
- Tests: `tests/test_server_grant_reads_20260628.py` (helpers; also smoke-tested logic in node).

### D. FREE CLK navbar readout — DONE, tested
`runner.py` `_update_clocks_left` stores `free_clocks`/`standard_clocks`/`free_continue_time` in status → snapshot. `public-v3/app.js` runner view-model `clocks{}` + `freeClockPill()` shows live free count + estimated daily-refresh countdown when empty. Tests: `tests/test_clock_navbar_readout_20260628.py`.

### E. Action-log badges + console cleanup + SSE — DONE
- Action Log ACT column now uses the same `rcard-badge bg-*` colored badges as Decision Reasoning (`app.js` `renderLog`); added `.bg-purple` (`styles.css`, recreation tone).
- Removed a leftover `[start] single_mode_free/start payload: …` diagnostic print from `main.py`.
- SSE live stream (`/api/stream` + `career_bot/event_bus.py` + Diag LIVE API feed) is now SHIPPED in builds (kept by the new build pipeline — see §3). It was a Tier-2 "API capability" feature; the user asked to include it.

### F. Server-grant research (workflow) — RESEARCH DOC
Doc: `docs/server-grant-probes-2026-06-28.md` (verifier-checked WILL-grant + MAY-grant tables with ready-to-run `/api/debug/*` probes). Key NEW read-only wins beyond the three built: live stat ceilings (built as F3), `route_race_id_array` (F1), race-availability flags (F2), `nickname_id_array`, `unchecked_event` inner detail. Best in-protocol no-spend win still unbuilt: **`reserve_race`** (already wrapped at `client.py:1188-1193`, never invoked). MAY-grant (need a live sniff, run IDLE via dev-only `raw_api.py`): mission/receive, present/receive, etc. — every SPEND probe loudly flagged.

### G. Unconditional manual-career resume — DONE (NOT yet in any build)
This session's feature request: if a career was started manually in-game, resume it using the in-game trainee/parents/deck/friend (override Setup).
- The recovery + override ALREADY existed in `main.py` `/api/career/run` (5586-5616, via `resume_career_fields` + `get_account_status`) but was GATED on a possibly-stale cached active flag.
- **Fix:** made the live-state probe UNCONDITIONAL — `/api/career/run` now always calls `load/index`, detects an in-progress career, and applies the composition override regardless of the cached flag (falls back to cached only if the probe call fails; harmless read when no career is in progress).
- Verified: `main.py` parses; resume/recovery/crash suites pass (32). **NEEDS LIVE TEST:** start server → RUN CAREER on a manually-started career → confirm it resumes with the in-game composition.

### H. Post-v3.2 UI batch (memory `icarus-ui-batch-20260628c`)
- **#5 DONE** — portrait 3D/PNG button now reads **"Seiun"** in 3D mode (`app.js` `b.textContent = png ? 'PNG' : 'Seiun'`; `index.html` button text).
- **#3 DONE** — Configure Skills modal (`modals.js`): removed the redundant `sk-tier-add` search row + its dead wirings; added a "right-click to add to tier" hint in Planned Skills + the tiers card; clicking a skill into the Plan now auto-opens the tier picker (`openCtx`) — on add only, plan tab only.
- **#2 DONE (Option 2)** — `setup.js` `applyActiveCareerParents()`: on session load, if `data.account.career.active`, resolve `career.parent_id_1/parent_id_2` against `L.parents` by `instance_id`, set `sel.veterans`, and `saveSelection()` (overwrites saved picks). Placeholder `{instance_id,name:'Career parent <id>'}` if unresolved. Called after `applyServerSelection` (~setup.js:1287).
- **#1 PENDING** and **#4 PENDING** — see §2.

### I. Parents "Display Settings" rebuild (earlier this session) — DONE
The Parents picker filter/sort was rebuilt into an in-game-style modal (Sort tab + Filter tab: Attribute/Aptitude/Unique spark sections, each All/2★+/3★-only + Include Origin Legacies; Sort by Rating/Sparks/Skills/Track/Distance/Style/Date/Name/Favorites). In `setup.js` (`openDisplaySettings`, `pfPasses`, `pfMetric`, `sparkHit`, `sumStars`, etc.). Spark names come from `data/factor_map.json` (categories stat/aptitude/unique/skill/race/scenario). Dropped Affinity Bonus + Memo sorts (no data). The Icarus-only age cleanup tool moved into the Filter tab. (This IS in the public `Icarusv3.2.zip`.)

---

## 2. PENDING WORK (do these next)

### #1 — Smart-solver "Character Preset" defaults to "Admire Vega" regardless of trainee
Files: `public-v3/modals.js`. **Diagnosed, NOT fixed.**
- `SV = { charId: 100021, ... }` (modals.js:1010) — static default "Air Shakur".
- `charById = id => SOLVER_CHAR_MAP[id] || SOLVER_CHARS[0]` (modals.js:359).
- On modal open, `loadSolverRoster()` (modals.js:368) replaces `SOLVER_CHARS` from `GET /api/character-profile/roster` (`main.py:4277`, `r.characters = [{name,id,apt}]`). The static list's ids are noted "wrong", so `100021` likely isn't a roster id → `charById(100021)` falls back to `SOLVER_CHARS[0]` = first roster entry = **"Admire Vega"**.
- The trainee-sync (modals.js:480-490) reads `GET /api/character-profile/active` (`main.py:4071`, returns `card_id` + `chara_id`) and only sets `SV.charId` when `SOLVER_CHAR_MAP[cid]` exists → if `/active`'s id isn't a `/roster` id, sync never fires.
- **NEXT (confirm FIRST, do not guess the id field):** read what `/roster` uses as `id` (its source) and compare to `/active`'s `card_id` vs `chara_id` — are they the same id space? Then fix: (a) default `SV.charId` from the active trainee, not hardcoded `100021`; (b) make the sync match on whichever field equals roster ids (try `card_id` then `chara_id`); (c) if still unmatched, synthesize a roster entry for the trainee instead of silently falling back to `SOLVER_CHARS[0]`.
- NOTE: this exact area has produced false-positive "fixes" before (see memory `icarus-verify-before-implement`, `icarus-v3-bugbatch-20260627`). Verify against live data.

### #4 — Unsaved-changes guard on settings modals (cross-cutting, largest)
On clicking DONE/close of ANY settings modal after a change, show a popup "Changes were made, don't forget to save!" with **Save Changes** + **Discard Changes** buttons.
- Modal infra: `public-v3/modals.js` (`.modal-overlay`, `wireSave` ~117, `SAVE_COLLECTORS`, the close/`modal-x` handlers).
- Approach: track a per-modal dirty flag (set on any input/toggle/select/chip change), intercept the close/DONE path, and if dirty show a confirm popup wired to the modal's existing save collector (Save) vs just close (Discard). Design once, apply uniformly to every settings modal's close path.

---

## 3. BUILD STATE (important)

Build scripts in `C:\Icarus\Icarus\claude_scripts\`. Dev folder = `C:\Icarus\Icarus\IcarusDev`. Outputs to `C:\Icarus\Icarus\`.

- **`_build_v32_beta_sse.ps1 -Name <Name>`** — the CURRENT pipeline. KEEPS the SSE live stream (`/api/stream` + `event_bus.py` + Diag LIVE API), EXCLUDES intercept + `raw_api.py` + `latent_data.py`. Uses `_strip_intercept_release.py` + the NEW `_strip_latent_only.py` (strips only the `/api/latent` route + diag latent panel, keeps SSE). Flat zip root; audits exclusions. Use this for both beta and public, varying `-Name`.
- `_build_v31_zip.ps1` — older pipeline that ALSO strips SSE (use only if a future release should drop SSE).
- Memory `icarus-v3-release-build` documents all of this.

**Zips built this session (in `C:\Icarus\Icarus\`):**
- `Icarusv3.2Beta.zip` — beta (SSE in, intercept/raw_api/latent out).
- `Icarusv3.2.zip` — public release. **STALE:** built BEFORE (G) unconditional resume and (H) the #5/#3/#2 UI batch. Contains: clock fix, skill redesign, F1/F2/F3, FREE CLK, action badges, SSE, parents Display Settings (I), print removal. Does NOT contain: the resume fix, #5, #3, #2 (or pending #1/#4).

**Standing build rules (MUST hold):** never ship the skill-buy intercept (`skill_intercept.py`/`skill_intercept_ui.js`), the raw-call debug route (`raw_api.py`), or `latent_data.py` in beta/public. Exclude settings.json/steam_token.txt/auth_config.json/accounts.json/uma_runtime/__pycache__/.pyc/.git. Flat zip root (no `IcarusVx/IcarusVx`).

---

## 4. QUEUED FINAL STEPS (after #1 + #4)

1. Run the full test suite (`cd IcarusDev && PYTHONIOENCODING=utf-8 python -m pytest tests/ -q`); confirm green (~924+).
2. Rebuild the public release: `powershell.exe -ExecutionPolicy Bypass -File C:\Icarus\Icarus\claude_scripts\_build_v32_beta_sse.ps1 -Name "Icarusv3.2"` (overwrites the stale zip with everything).
3. **CHANGELOG.md** (`IcarusDev/CHANGELOG.md`): top entry is already `## v3.2 (2026-06-28)` (drives `_build_version` + `/api/changelog` What's-New popup). Add the post-build items that aren't yet listed: the unconditional manual-career resume, #5 Seiun button, #3 skills-modal changes, #2 resumed-career parents, plus #1/#4 once done.
4. **Help** (`public-v3/help.html`): there's a "What's new in v3.2" section (nav `data-sec="whatsnew"`). Add the same post-build items.
5. Bump cache versions for any changed frontend files (see §6).

---

## 5. LIVE-VERIFY CAVEATS (test on a real career)

- **#2 / resume parents id-space:** assumes `career.parent_id_1/2` (succession trained-chara ids) == `L.parents[].instance_id`. If not, the PARENT slots show "Career parent <id>" placeholders. Same id-mapping risk class as #1.
- **G / unconditional resume:** verify start-server → RUN → resumes the manual career with its real composition.
- **#1:** the id-space question is the crux — confirm before fixing.
- **Clock fix:** already live-confirmed (clocks_used=4) — good.

---

## 6. CACHE VERSIONS (current, in `public-v3/*.html`)

- `app.js?v=24` (index.html) — bumped for FREE CLK readout + #5 Seiun + action badges.
- `modals.js?v=13` (setup.html, diag.html) — bumped for skill target dropdown + #3.
- `setup.js?v=27` (setup.html) — bumped for parents Display Settings + #2.
- `styles.css?v=8` (all pages) — bumped for `.bg-purple`.
- Bump again for any further frontend edits in #1/#4, and confirm before the final build.

---

## 7. KEY REFERENCES

- Memory index: `MEMORY.md`. Most relevant: `icarus-ui-batch-20260628c` (this batch), `icarus-clock-retry-2507-fix`, `icarus-skill-purchase-redesign`, `icarus-api-capability-map`, `icarus-v3-release-build`, `icarus-verify-before-implement`, `icarus-stale-server-masks-fixes`.
- Docs: `docs/server-grant-probes-2026-06-28.md`, `docs/api-capability-map-2026-06-28.md`, `docs/skill-purchase-redesign-2026-06-28.md`.
- Standing rules: tell before behavioral changes; TDD new features/fixes; restart `python main.py` for on-disk changes to take effect (stale-server rule); credentials never plaintext; verify "already built/verified" claims against live code/logs before editing.

---

## 8. HANDY COMMANDS
- Full tests: `cd C:/Icarus/Icarus/IcarusDev && PYTHONIOENCODING=utf-8 python -m pytest tests/ -q`
- JS check: `node --check public-v3/<file>.js`
- Public build: `powershell.exe -ExecutionPolicy Bypass -File C:\Icarus\Icarus\claude_scripts\_build_v32_beta_sse.ps1 -Name "Icarusv3.2"`
- Bash is available here for python/node/grep; build scripts are PowerShell (invoke via `powershell.exe -File`).
