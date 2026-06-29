# Changelog

## v3.2.3 (2026-06-29)

Adds a **Display** (appearance) panel — scale the whole interface's text size and pick your own fonts — plus a single centralized type-scale config under the hood.

**Added / Changed**
- New **DISPLAY** button in the top navbar (with a ⚙ gear, like Tempt Fate / Retries) opens an Appearance panel where you can:
  - Set the interface **font size** — Small / Normal / Large / X-Large — which scales every font at once (handy if the dense UI is hard to read).
  - Choose separate **Body**, **Heading**, and **Numeric** fonts from a curated list of Google Fonts (including the high-legibility Atkinson Hyperlegible, serif options, and several monospaces).
  - Switch the **accent theme** (the 6 colours that were previously only reachable by clicking the ICARUS logo).
  Choices apply instantly and are remembered per device. (Selected fonts download from Google Fonts and need an internet connection; offline, a matching system font is used instead.)
- Under the hood, every hardcoded font size across the v3 UI was moved into one centralized type-scale config (CSS variables in `styles.css`), so all sizes can be tuned from a single place. Nothing changes size at the "Normal" setting.
- On the dashboard, the LOGOUT button moved down into the transport bar (next to RUN / PAUSE / STOP), and the new DISPLAY button takes its former spot in the top-right of the navbar.
- This build also includes the late-game megaphone (Reset Whistle) dump fix and the 3rd/final-climax Master Cleat Hammer display fix described in v3.2.2.

## v3.2.2 (2026-06-29)

Patch release on top of v3.2.1: forced event choices finally persist, smarter energy/recovery-item use, much more aggressive late-game item dumping, functional Discord notifications, and a read-only race win-probability estimate.

**Fixed**
- Forced event choices were still being silently reset. Saving any settings modal (Training / Racing / Scenario / etc.) re-wrote the whole preset with an empty event-choice list, wiping the choices you forced from the Event Choices panel — so the runner always fell back to Auto and pressed the default option. Event-choice overrides are now stored independently and can only be changed from the Event Choices panel, so they survive every other save and actually apply in-career.
- Energy / recovery items (Vita, Energy Drink, Royal Kale Juice) were being used on REST turns — a waste, since resting already restores energy. They now fire only when the turn's action is TRAINING and energy is the limiting factor (the late-game dump still empties them).
- Pre-race energy was being "preemptively" topped up at any energy below ~40 before a race. A race only needs more than 0 energy to avoid punishment, so an energy item is now used before a race ONLY when energy is exactly 0 — same turn, before the race — regardless of the race's position in a consecutive-race chain.

**Added / Changed**
- Second summer camp (turns 61–64): the bot now TRAINS at neutral mood instead of spending a precious camp turn on Recreation; and once past turn 61 with no Royal Kale Juice left, it releases the held-back cupcake to fix mood on a training turn rather than recreating.
- Late-game item dumping (after turn 64, when "Save Items Late Game" is OFF) is now far more aggressive: Empowering Megaphones, Ankle Weights, Good-Luck Charms, and the small +5 Energy Drink MAX are spent on essentially every training turn instead of stranding unused at career end. (Ankle weights still only apply to their own stat's training; the "Save Items Late Game" toggle keeps the old conservative behavior.) Also fixed a Reset Whistle turn in the dump window wrongly suppressing the megaphone/anklet that turn (it stranded lower-tier megaphones).
- Career History now correctly shows the Master Cleat Hammer on the 3rd (final) climax race. The hammer was always used on all three climaxes; the panel just hid it on the last one because that race shares its turn with career finish — a display fix, no behavior change.
- Discord notifications: the "Notify on career finish / crash / new epithet" toggles are now real per-event switches (previously decorative). A crashed/stuck career routes to the crash toggle, a clean finish to the finish toggle, and a newly earned set-bonus epithet pings the epithet toggle (off by default).
- Career History now shows a read-only pre-race win-probability estimate per race (~P(win)), computed from the game's own opponent stat data. It is preliminary/uncalibrated and does not affect how the bot plays.
- Removed a misleading "auto-solve before run" checkbox in Setup that did nothing (smart mode already solves the schedule at career start).

## v3.2.1 (2026-06-28)

Patch release on top of v3.2: forced event choices now actually apply, the Smart Race Solver follows your selected trainee, settings modals warn before discarding unsaved edits, and manually-started careers resume correctly.

**Fixed**
- Forced event choices were not being applied. Two separate bugs: (1) a choice forced from the Event Choices panel for an event you had not encountered yet was saved under the event's catalog name-key, which the runner never matched against the live in-game event, so the forced choice was ignored; (2) the forced choice was stored as a 0-based position but read as a 1-based game index, so forcing the 2nd (or later) option selected the option before it. Both are fixed — forced choices now resolve by event name and pick exactly the option you chose.
- The Smart Race Solver's "Character Preset" always showed "Admire Vega" regardless of the trainee selected in Setup. It now follows the active trainee (resolving outfit variants and versioned names) and falls back sensibly when no trainee is selected.
- Closing a settings modal (Training / Racing / Scenario / Smart Solver / Skills / Custom Deck / Userdata / Discord) after editing it no longer silently discards your changes — a prompt now offers Save Changes or Discard Changes. This applies whether you close via DONE, the dark backdrop, or Esc; dismissing the prompt keeps you in the modal.

**Added / Changed**
- A career started manually in-game now resumes with its real in-game trainee, parents, deck, and friend support: the live game state overrides the Setup selection whenever an in-progress career is detected.
- Resuming an in-progress career now fills the Setup PARENT slots with the career's actual inherited parents.
- Configure Skills modal: removed the redundant in-tier search row; you can now right-click any skill to assign it to a tier, and adding a skill to the Plan auto-opens the tier picker.
- The dashboard portrait toggle's 3D button is now labeled "Seiun" (the 3D model is Seiun Sky).

## v3.2 (2026-06-28)

Public release on top of v3.0, focused on race-retry (clock) fixes, a skill-purchase overhaul, and several "read what the game already tells us" improvements.

**Fixed**
- Fixed the bot never burning clocks to retry lost races. A transient "free-continue pool empty" response (server code 2507) was being treated as a permanent "this race cannot be retried" and cached forever in a shared list. Over many career loops that list grew to ban almost every race (every G1, the Junior Make Debut, and the whole finale) from ever retrying, so the bot stopped attempting retries entirely. 2507 is now correctly treated as transient and never cached; only a genuine refusal (code 205) is learned.
- Fixed the free-continue counter, which read a constant daily cap instead of the live remaining balance. This made the bot always attempt a (doomed) free retry and never spend an actual standard clock. It now reads the live balance and correctly falls back to spending a standard clock when the free pool is empty. (Confirmed live: clock retries now win lost races, e.g. a 13th-place finish retried up to 1st.)
- Cleared the existing poisoned non-retryable race cache (backed up first) so previously-banned races are retryable again.
- Fixed a setting interaction where "max retries per race = 0" silently disabled even the career-saving mandatory-race rescue.

**Added / Changed**
- Rebuilt the Parents search/filter/sort into an in-game-style "Display Settings" popup with Sort and Filter tabs: filter by Attribute / Aptitude / Unique sparks (each with an All / 2-star+ / 3-star-only level and an "Include Sparks from Origin Legacies" toggle), and sort by Rating, Sparks, Skills, Track, Distance, Style, Date Acquired, Name, or Favorites.
- Cap-aware training: the engine now reads each stat's live ceiling from the game (instead of assuming a fixed 1200) so it stops investing in a stat that has hit its real cap. No change when the live cap is 1200.
- Races now choose skip (short) vs full mode from the game's own skip-race state instead of always forcing skip, and log the server's race-availability flags. Defaults to skip (the previous behavior) unless the game signals skip is locked.
- The bot now reads the career's route/finale race list from the game (route id + scheduled route races), surfaces it in the runner status, and includes it in soft-lock diagnostics instead of inferring late-career state from the turn number.
- A free-continue ("FREE CLK") readout in the navbar showing the live free-retry count plus an estimated daily-refresh countdown when empty.
- The Action Log now shows the same colored action badges (RACE / REST / TRAIN / REC) used in the Decision Reasoning panel, instead of plain colored text.
- Added a real-time live API event stream (Server-Sent Events) on the Diag page's "LIVE API" panel, pushing each game-API call the instant it happens instead of polling. Events are compact and contain no secrets.
- Removed a leftover diagnostic line that printed the career-start deck payload to the console.
- Skill purchase: added a schedule-aware activation-condition gate that down-weights skills whose running-style/distance conditions can never trigger for the current trainee (so skill points are not wasted on dead skills).
- Skill purchase: replaced the coarse community tier list with a graded tier built from the full community skill spreadsheet (289 skills), and added a "Skill Optimization Target" dropdown (Career / Team Trials / Champions) that weights skills by the chosen mode's ranking. Career remains the default and preserves fans-first behavior.
- Skill purchase: skills the game disables during a career run are now hard-dropped in Career mode (wasted SP) but kept and valued under Team Trials / Champions, where they work on the finished trainee.

## v3.0 (2026-06-28)

Cumulative public release covering every change since the v2.1 beta (all beta
builds 1-13 and the post-beta work).

**Features Added**
- Introduced the v3 "Command Console" UI: a complete dark-cockpit redesign (vanilla HTML/CSS/JS, no build step) now served as the default at "/" with the legacy UI moved to "/legacy"
- Added high-resolution character card art extracted from local game assets (512x512), shown in the Setup trainee picker, Career History, and dashboard, via a new /api/card-art endpoint
- Added a 3D/PNG portrait toggle in the dashboard to switch between the 3D model viewer and flat card art
- Added per-trainee theme colors that apply each trainee's signature palette during live careers (logo-cycle theme remains the idle fallback)
- Added a manual race schedule picker with per-turn clickable race selection, a modal listing all available races, and a SMART/MANUAL toggle that round-trips through presets
- Added a Retries configuration popover with a "use clocks on only G1/Debut races" toggle and a max-retries-per-race input, stored per career request
- Added a global stat-target option that overrides per-distance targets across all distances
- Added the Trackblazer engine as the default decision engine, with whole-career race scheduling, live re-planning after losses, and energy/consecutive-race/marquee-race guards
- Added set-bonus (epithet) chasing so the Smart Race Solver schedules races to complete Triple Crowns and distance/regional/surface sets for their large random-stat rewards (configurable, default off)
- Added a Live Schedule Re-Planning toggle that re-routes after a race loss (default on)
- Added Trackblazer RIVAL OVERWRITE races with a multi-select per-turn race picker
- Added per-race running-style overrides with curated rows for marquee races
- Added a Stat Focus control: "Balanced" spreads stats evenly, "Capped" concentrates priority stats toward their ceilings
- Added a Speed dropdown (Safe / Fast / Faster / Ludicrous) whose levels genuinely scale API pacing, replacing the old on/off toggle
- Added a goal-aware training lookahead toggle that boosts stats behind pace and trims those already ahead (default off)
- Added a skill-point optimizer toggle that spends SP for maximum total skill value per point (default off)
- Added manual skill tiers (T1-T5, color-coded, searchable, drag-reorderable) that drive purchases independently of the Skill Point Check plan, with a "don't spend extra skill points" option
- Added a "skill stop after recommended" toggle and a manual auto-fallback toggle to the Configure Skills modal
- Added a Shop Purchase Logic settings section with Coin Reserve Override, BBQ Buy Threshold, Fast Learner Shop Boost, and Preemptive Cure Reserve
- Added item-conservation knobs including a Late Whistle Lackluster Threshold, configurable cupcake/finale-hammer reserves, and a save-items-lategame toggle
- Added a rainbow attenuation toggle and floor slider that scales down near-cap rainbow training value (default on)
- Added an Outcome Risk settings section with a toggle and weight slider to tune the learned race-loss penalty
- Added per-turn skill, fan, and item logging that powers the live monitor event stream and item chips
- Added item icons and epithet-completion announcements in Decision Reasoning
- Added a custom deck builder (owned cards only) with search, filters, and per-preset persistence
- Added a Deck Bonuses panel that sums each effect across the selected deck at real limit-break levels with type chips and a deck-quality score
- Added Game8 Trackblazer recommended-support builds per trainee with OWNED / NOT OWNED badges
- Added a Recommended Supports ranking in Library by stat-priority match and rarity
- Added favorite parents and guests as pinned toggles with star badges
- Added an MLB label for fully limit-broken support cards, plus per-card outfit names and icons
- Added per-preset self-contained config (settings, skills, solver, team selection), per-preset event-choice answers, and a LOAD button to revert a preset to its on-disk state
- Added mid-career settings hot-reload so changes take effect on the next turn
- Added a What's New popup, a /api/changelog endpoint, and an in-depth rewritten Help page
- Added career-log redaction of device/network/Steam/credential fields plus a one-click EXPORT LOGS button
- Added a multi-account TCP-connect health check and an Accounts overview showing live per-account status
- Added theme persistence across browsers and restarts, cached assets and parallel dashboard startup for faster loads, and an animated loading screen
- Added friendlier Steam login/2FA error messages, a failed-login cool-down, and resilient escalating backoff that auto-resumes through maintenance and 5xx/394/208 errors

**Major Changes / Reworked Logic**
- Reworked the event-choice database to source from gametora plus the game's master.mdb (2,500+ events with English skill names), with stat-cap awareness, turn-aware energy valuation, tightened fuzzy matching, and skill-aware choice picking
- Rebranded the product to Icarus with a navy-and-gold default theme, new logo across login/2FA/Help/What's New, and auto-recognition of legacy userdata folders
- Renamed the engine to Trackblazer (config keys aliased for backward compatibility) and exposed a Decision Engine selector
- Wired the v3 dashboard to live APIs across all per-page scripts and fixed guest-parent selection to send the correct run payload
- Reworked Decision Reasoning into synthesized per-turn labels with stat deltas and placements, colored event keywords, clean card titles, and bulleted breakdowns
- Reworked the live Monitor dock into a granular event stream (hp_check / action / fan_gain) with real deltas and placements
- Reworked late-game item usage (turn 60+): megaphone/anklet/whistle/Vita/EDM turn-window rules, cupcake-for-mood and kale summer-lock, finale hammer reservation, and aggressive post-turn-64 dumping
- Reworked skill purchasing with career-persistent owned-skill tracking, owned-by-name exclusion, stop-after-recommended cutoff, confirmed-purchase reconciliation, and per-row error isolation
- Reworked marquee G1 matching (Japan Cup, Arima Kinen, Takarazuka Kinen, Tenno Sho) to match by race instance id, closing a large fans gap and running correct races instead of substitutes
- Enforced the consecutive-race cap at runtime so careers honor the max-races-in-a-row setting
- Added a marquee-race guard with energy gating that forces marquee races when offered
- Retuned bond training so off-priority cards build bond and the orange-to-rainbow progression no longer stalls
- Made manual race selection strict, short-circuiting smart fallbacks and filtering all fallback paths by preferred surfaces
- Reworked live schedule re-planning to solve once at career start and re-plan only on a loss or unavailable races, with streak seeding across solve boundaries
- Corrected the summer-camp turn set so the bot no longer trains through late-June marquee races
- Restricted clocks/retries to Debut, G1, and finale Climax losses
- Hardened startup: safe-loaded import-time JSON, refactored master-data generation, added a manager max-restart breaker, and made the server import side-effect-free
- Slimmed career logs from ~44MB to ~2-3MB

**Fixes**
- Fixed normal careers buying zero skills by flipping the stop-after-recommended default off and no longer discarding all candidates when none matched recommended names
- Fixed a skill re-buy bug where the partial rotating skill view caused owned skills to be repurchased across a career
- Fixed a skill-buy silent failure where a 208 envelope masked a stale 205, by refreshing server state before buying and verifying grants with retry
- Fixed auto-skill buying to hard-filter off-distance exclusive skills and to read both the Configure Skills and legacy blacklists by id and name
- Fixed set-bonus race selection so a colt Triple Crown schedules Satsuki/Derby/Kikuka instead of the filly set
- Fixed manual schedules being ignored on summer/finale turns and manual dirt races being dropped by a guide-race heuristic
- Fixed RIVAL OVERWRITE races not running when the main race was unavailable on a rival turn
- Fixed Career History sparks so each finished career shows its actually-earned sparks instead of inherited parent sparks
- Fixed in-race running style so it is sent at the correct step with correct data
- Fixed the item-use log 1-turn lag and surfaced hammer use in Decision Reasoning
- Fixed energy items being wasted at year-end races and pre-race energy being burned past turn 71
- Fixed the Energy Drink MAX value and stopped purchasing items that do nothing (Yummy Cat Food, Energy Drink MAX EX, Reporter's Binoculars, Master Practice Guide)
- Fixed shop coin hoarding with flush-buy behavior and a finale coin reserve
- Fixed the glow-stick fan multiplier so it scales correctly before the user threshold
- Fixed live UI freezes via fetch timeouts and off-thread snapshot reads
- Fixed the dashboard poll killing its own timer and spamming idle POSTs, and stopped the account strip from wiping the TP-recovery dropdown mid-selection
- Fixed manual-mode persistence so race picks round-trip through presets
- Fixed guest parents being misclassified as random umas at login
- Fixed new runs failing after a non-looped finish with a career self-heal and a FINISH RUN toggle
- Fixed friend-support duplication on deck start and added deck auto-trim to the legal size
- Fixed Steam API 394 forcing re-setup by auto-refreshing the session ticket mid-run, plus career-loop recovery from API 102 and Guest Parent API 500
- Fixed parent rank labels to use the game's real rank ids, the missing Career History trainee icon, and inverted Deck Bonus rarity tables
- Fixed the Smart Race Solver to use a data-driven roster (~289 trainees with aptitudes), plan from true base aptitudes, and refresh aptitude/threshold buttons instantly
- Fixed stat-target year milestones (33% by end of Classic, 66% by end of Senior) with auto-migration of existing presets
- Fixed an empty Decision Reasoning panel and stuck monitor caused by a variable-shadowing regression
- Fixed multi-account instances showing as offline and the Manager resolving the wrong userdata folder across ports
- Fixed the Accounts and Diag pages showing fabricated or blank data, now showing real health and an untrained-state banner
- Fixed Career History not recording in loop mode and showing identical outfits across careers
- Fixed manual race selection in v3 being dead due to a mismatched click handler, and race banner images failing to serve
- Fixed senior-year race cells (Early Sep through Early Dec) being unselectable, and Training Settings priorities not saving
- Fixed Career History overlapping the live monitor, a duplicate "Wit" stat in the stats chart, and a parent-search hover tooltip regression
- Fixed the dashboard latching to mock data on first failure so it now self-heals to live without a refresh
- Fixed Tempt Fate/Burn/Loop controls not responding and not restoring their state across page switches
- Fixed the 3D viewer to be offline-safe and corrected its T-pose, cheek-texture blending, hair cel-shading, and spin animation
- Fixed washed-out live-mode reasoning cards and per-race style overrides not being cleared on save

**Removals**
- Removed the Event Outcome Knowledge Base entirely (store, import pipeline, native capture, dashboard card, endpoints, and dataset files)
- Removed the legacy training scorer; Trackblazer is the single scorer
- Removed the old game8 event scraper in favor of the gametora + master.mdb pipeline
- Removed the endpoint-pacing engine and old Bot Speed dropdown, replaced by the genuine Speed levels
- Removed the preview-mode mock simulator so the UI never shows fabricated data, falling back to an offline banner and empty states

**UI Changes**
- Made v3 the default at "/" with the legacy UI at "/legacy" and back-compat redirects from "/v3"
- Reworked the navbar to a balanced 2+2 layout around a wider SETUP button, with lifetime metrics shown as a bordered strip on every page
- Merged Diagnostics and AI/Misc into one tabbed Diag / AI page and moved the userdata and EXPORT LOGS controls into the userdata modal
- Made the Library tabbed (Trainees / Parents / Guest Parents / Decks / Friend Supports / Owned Cards) with Deck Bonuses pinned in the Decks tab and the Guest Parents section collapsible
- Redesigned the Event Choices panel with search, accurate AUTO/FORCED badges, Story/Support filter tabs, an "only my deck's events" checkbox, full pre-run catalog population, and per-choice effect details
- Made selection order consistent (Trainee, Parent 1, Parent 2, Deck, Friend) across Setup and Library
- Replaced the Tempt Fate inputs with a modal containing the Speed levels and custom delays, and moved Retries to a floating popover
- Added the race-schedule UI with real banner images, a SCHEDULED ribbon, an OP-races toggle, selectable senior-year cells, a per-cell modal picker, and a RIVAL +N badge
- Showed RATING RANK and real per-card outfit icons in Career History with compact thumbnails and a full per-race breakdown
- Enlarged Library card text and added LB/MLB badges, switched icons to contain (no cropping), and added a deep-space backdrop default with reduced stylesheet size
- Restored the Live Run Monitor inside Career History with a LIVE badge and no overlap, and showed a What's New popup once per version

## Icarus v2.1 (dev)

Builds on v2.0 with two rounds of gameplay and dashboard fixes (the changes were
trialed as the Beta 1 and Beta 2 tester builds). Headline: a reworked skill
purchase system, a smarter shop, and a live dashboard that no longer needs manual
refreshing.

**Skill purchase system**

- **Manual skill tiers now drive purchases.** Whenever any tier has skills, the
  bot buys them by tier (T1 first) — no longer gated behind the "Skill Point Check
  Plan" toggle, which previously made the tier list do nothing under the default.
  New **"Don't spend extra skill points"** option (on by default) stops buying once
  your listed skills are purchased, leaving the rest of your SP unspent.
- **Auto plan no longer buys off-profile skills.** Distance-exclusive skills that
  don't fit the trainee's distance(s) are hard-filtered (e.g. no more Long-only
  skills on a Miler); off-style filtering is unchanged. Skills you list manually
  are still bought even if off-profile — your pick wins.
- **Skill blacklist fixed.** Now reads the Configure Skills blacklist as well as
  the legacy list, and matches by skill ID as well as by name.

**Racing**

- **Set-bonus race selection fixed** — forcing a colt crown (Triple Crown, etc.)
  now schedules the correct races (Satsuki / Tokyo Yushun / Kikuka) instead of
  substituting the filly set. (Root cause: a race-name alias mismatch.)
- **Manual race schedule honored on summer/finale turns** — manual mode consults
  your schedule before force-training, falling back to train/rest/recreation only
  when the scheduled race isn't available.
- **Clocks/retries restricted to Debut + G1 + finale Climax** on a loss (including
  mandatory races of those grades); G2/G3 losses no longer burn clocks.

**Items & Shop**

- **Megaphones** fire only in summer, on strong rainbow turns, or to burn
  end-of-career excess — and are bought big-only (no small; medium only if short
  on big for summer).
- **Whistles** held for summer + end of career instead of random mid-career.
- **Hammers** reserve exactly 3 for the climax and spend the surplus on regular
  G1s (no more stranded hammers); their use now **shows** in Decision Reasoning.
- **No recreation pre-debut** (early bond building comes first).
- **New "Shop Purchase Logic" settings section** — Coin Reserve Override, BBQ Buy
  Threshold, Fast Learner Shop Boost, and Preemptive Cure Reserve.

**Dashboard**

- **Live UI no longer freezes** — career status, lifetime metrics, action log,
  decision reasoning, career history and the live monitor keep auto-updating; hung
  fetches now time out and the snapshot read no longer blocks the server.
- **Set bonuses announced** in Decision Reasoning when earned, with the reward
  (e.g. "🏆 Set bonus earned: Stunning (2 random stats +10)").
- **Item-use log 1-turn lag fixed** — per-turn item usage reflects the current
  turn.
- **Training Scorer removed** — the Trackblazer engine is the single scorer; the
  redundant scorer score and its UI control are gone.
- **Diagnostics + AI/Misc merged** into one **Diag / AI** page (tabbed).
- **Library is now tabbed** — Trainees / Parents / Guest Parents / Decks /
  Friend Supports / Owned Cards — with Deck Bonuses pinned atop the Decks tab.
  (Also fixes Guest Parents never rendering.)
- **Multi-account control** no longer shows a running instance as offline.
- Career logs **redact** device / network / Steam / credential fields; new
  one-click **EXPORT LOGS** button; cleaner item labels; "Retry" → "Retries".

**Reference**

- **HARDCODES.md** in the install folder lists the remaining hard-coded gates /
  thresholds and the config key (if any) that overrides each.

## Icarus v2.0

The biggest leap since launch. The Trackblazer Engine grows up: it now chases
set-bonuses (Triple Crowns and more), races smarter without over-racing, spends
the shop like a pro, picks event answers from a 3,600+ event database — and the
dashboard finally *shows* you what it's doing, item icons and all.

**The Trackblazer Engine is now the default**

Icarus now runs on the **Trackblazer Engine** by default — a solver-driven
decision core built for the Trackblazer/MANT scenario. Rather than scoring a
single turn in isolation, it treats the whole career as one optimization problem
and plans accordingly:

- **Whole-career race scheduling.** An exact route optimizer (with a fast
  heuristic fallback) weighs the entire race calendar at once and locks in the
  schedule that maximizes stats, fans, set-bonus completion, and aptitude fit —
  while respecting your max-races-in-a-row limit and the summer / finale windows.
- **Plans, then adapts.** The route is solved once at career start and then
  re-planned live when a race is lost or a planned race drops off the calendar, so
  it stays valid as the run actually plays out (you control this with the new
  *Live Schedule Re-Planning* toggle).
- **Built around the racing economy.** Its train-vs-race-vs-rest decisions account
  for the scenario's currency → items → stats loop, energy and mood,
  consecutive-race risk, and the marquee G1s and finale climax races — not generic
  training rules.
- **Smarter, safer racing.** Energy and consecutive-race guards, a marquee-race
  prediction gate, and summer / finale handling are built into the engine so it
  pushes for value without over-racing or throwing winnable races.
- **Classic is still here.** The previous turn-by-turn engine remains selectable as
  **Classic** under *Decision Engine* if you prefer the old behavior.
- Across the dashboard, settings, and help, it's now consistently the
  **Trackblazer Engine**.

**Race & Set-Bonus Engine**

- **Chases set-bonuses (epithets).** New *Chase Achievable Set-Bonuses* option: the
  Smart Race Solver now schedules races to *complete* sets — Triple Crowns,
  distance / regional / surface sets, and more — for their large random-stat
  rewards, which were previously left on the table. This is the headline stat
  lever and is enabled on the Oguri preset.
- **Live Schedule Re-Planning toggle.** The live re-planning control is now a
  proper switch in Smart Race Solver settings: on (default) re-routes the
  remaining schedule after a race loss; off locks in the plan solved at career
  start. It surfaces the existing setting rather than adding a duplicate.
- **No more over-racing.** A runtime consecutive-race cap now honors your
  *max races in a row* setting. Careers that were running 46–48 races with 8–10 in
  a row now run ~42 with streaks capped — recovering total stats and win rate.
- **More marquee G1s run.** Fixed race matching for marquee races (Japan Cup,
  Arima Kinen, Takarazuka Kinen, Tenno Sho, and friends) that the game offers
  under several internal IDs — they were being skipped, and now run.
- **Outcome Risk has its own section** in Racing settings, with a toggle, so you
  decide whether the solver weighs race-loss risk.

**Stat Focus**

- New **Stat Focus** control: **Balanced** spreads stats evenly, while **Capped**
  concentrates your priority stats to push their ceilings. Pick per preset.

**Speed**

- The old Tempt-Fate on/off toggle is replaced by a **Speed dropdown** —
  *Safe / Fast / Faster / Ludicrous*. The levels now genuinely differ: each scales
  the bot's API pacing (Safe keeps human-like timing; Ludicrous removes it).
  Previously Fast, Faster, and Ludicrous all ran at the same real speed.

**Shop & Items**

- **Smarter shop spending.** Race hammers are conserved and saved for the three
  finale climax races (where they pay off most); training megaphones and anklets
  are bought for your priority stats; energy drinks, cures, and snacks are bought
  by need; and a finale coin reserve keeps funds on hand for the climax.
- **Item icons in Decision Reasoning.** Every shop item the bot buys or uses now
  shows its in-game icon beside its name in the Decision Reasoning panel.

**Event Choices**

- **Massively expanded coverage.** When there's no observed data for an event, the
  auto-selector now falls back to a 3,600+ event effect database and scores the
  real choice effects — instead of a blind "pick the second option" guess.
- **Stat-cap aware.** Event choices no longer over-value points dumped into a stat
  that's already maxed.
- **Turn-aware energy.** Energy rewards are valued more during summer camp and the
  finale stretch, where energy matters most.
- **More accurate matching.** Tightened event lookup so it no longer mis-scores an
  unrelated event that merely shared a few trailing ID digits.

**Decision Reasoning**

- Clearer, more accurate per-turn explanations — including correct item labels
  (training megaphones are shown as *training boosts*, race hammers as *race
  buffs*) so the panel matches what actually happened.
- The live on-screen race list is now captured in the logged state for diagnostics.

**Fixes & Quality of Life**

- **Career History sparks are correct per career.** Each finished career now shows
  the sparks it *actually earned*, instead of repeating the same inherited parent
  sparks on every entry.
- **Running style is set correctly** (e.g. Oguri Cap runs *Pace*, not *Late*) —
  fixed the in-race running-style change to send the right data at the right step.
- **Skill-config UI fixes** and a fixed dashboard console / network error.

## Icarus v1.5

The biggest update yet — a dramatically stronger race engine, presets that
finally save *everything*, in-game agenda support, and a stack of fixes.

**Race & Training Engine**

- **More races run per career.** When the solver's planned race isn't on the
  live calendar, Icarus now runs the best available race from the live on-screen
  list instead of quietly dropping it — so the bot completes far more of its
  planned schedule, which lifts total fans right alongside it.
- **Smarter training.** Rainbow (friendship) training is valued far more
  aggressively now, and a new *starved-stat* boost stops the bot from neglecting
  whichever stat the rainbows skipped — so builds stay balanced and win more of
  the close races.
- **Mood is kept high through both summer camps**, where it multiplies every stat
  gain, turning more of those razor-thin races into wins.

**New Features**

- **In-game Agendas.** Reserve a race in-game (Steam, mobile, or emulator) and
  Icarus will run it for you, overriding the solver — manual race selection
  straight from the game. Toggle on with *Use in-game agenda*.
- **Debut-only free retries.** Optionally reserve your free race retries for the
  debut race so they aren't spent (or wasted) elsewhere.

**Presets**

- **Presets now save EVERYTHING.** Switching or loading a preset restores the
  Smart Race Solver / manual schedule, skills, scenario overrides, and your
  trainee + parents + deck + friend — not just Training and Racing settings.
- **Event choices are now per-preset**, so each preset remembers its own answers.

**Shop**

- **No more wasted coins.** Yummy Cat Food, Energy Drink MAX EX, Reporter's
  Binoculars, and Master Practice Guide are no longer purchased — they were
  auto-used on races where they do nothing — leaving more coins for items that
  matter.

**Fixes & Quality of Life**

- **Steam "API 394" no longer forces a re-setup.** Icarus now refreshes the
  expired Steam session ticket automatically mid-run and saves it, instead of
  looping on the dead ticket and dropping you back to manual login.
- **Parent sorting fixed** — owned parents no longer vanish when you hover over
  them while sorted by anything other than name.
- **Your theme is remembered** across browsers and server restarts.
- **Faster page loads** — scripts, styles, and character portraits are now
  cached, and the dashboard's startup data loads in parallel.
- The *What's New* popup now shows on every load.

## Icarus v1.3

**Bug fixes**

- **Deck Bonuses now show the correct rarity and values.** SSR support cards were
  being labeled "R" and shown with the weaker R-tier effect values (two internal
  rarity tables were inverted). SSRs now display as SSR with full SSR effects,
  and the deck-quality score weights rarity correctly.
- **Settings presets now save your deck / trainee / parent selection.** The
  selected team was written to the preset file but silently dropped on re-load,
  so it never restored. Fixed — your selection round-trips correctly now.
- **New LOAD button for settings presets** — reloads the active preset's saved
  values from disk, discarding any unsaved changes.
- **Stat-target year milestones now match the intended schedule.** They
  were shifted a year early — aiming for 33% of final stats by end of *Junior*
  and 66% by end of *Classic*, with no Senior milestone — which front-loaded
  training onto weak early-game facilities. They now pace correctly: 33% by end
  of **Classic** year and 66% by end of **Senior** (then full targets for the
  finals), so training builds toward the strong Summer-Camp window. Existing
  presets migrate automatically — your saved 33/66 values move to the correct
  years with nothing to re-enter.
- **Smart Race Solver aptitude & threshold buttons now update instantly.** They
  previously didn't show the new selection until you closed and reopened the
  page (checkboxes/sliders worked, buttons didn't). Fixed.
- **Smart Race Solver settings now refresh the trainee's aptitudes** when opened
  (and when you change trainee while it's open), so the aptitude grid reflects
  the current trainee instead of a stale cache.

**Performance**

- **Faster dashboard loading.** The theme's backdrop image was embedded as a
  ~180KB blob inside the stylesheet, bloating it to 420KB and blocking first
  paint; it's now a separate cached image, cutting the stylesheet to ~245KB.
  Also reduced an always-on navbar blur and stopped the live action log from
  rebuilding its whole table every 1.5s when nothing changed.

## Icarus v1.2

**Race scheduler aptitude fix**

- **Smart Race Solver now plans from the trainee's true base aptitudes.** It was
  building the schedule from inflated live/last-run aptitudes (e.g. showing
  Mile/Medium/Long as **S** when the card's base is A/A/B) — aptitudes never
  start a career at S, so the planner was over-promising on ranks the trainee
  didn't have. It now anchors on the card's base aptitudes from master data,
  while the running career still validates each race against your live in-game
  aptitudes (so inheritance is still honoured at run time).

## Icarus v1.1

**Minor fixes & improvements**

- **Live Run Monitor overlap** — fixed the Live Run Monitor overlapping the
  Career History list while a run is live.
- **Duplicate "Wit" stat** — fixed the phantom second "Wit" entry in the
  dashboard's monitor stats chart; it now shows a single, correct Wit line.
- **Guest Parent API 500** — borrowing an invalid or expired guest parent no
  longer throws API error 500. The start now fails cleanly with a clear message
  to refresh and reselect, or start without a guest parent.
- **Smarter shop spending** — the bot no longer stockpiles cure items, mood
  cupcakes, or Good-Luck Charms you never use. Cures are bought only when a bad
  condition is actually active.
- **Stat target & priority editor** — you can now edit a character profile's
  per-distance stat targets and stat priority directly in the Character Profile
  panel (previously JSON-only).
- **Parent-aware stamina tuning (optional)** — a new per-profile toggle that
  relaxes the stamina target when a trainee lacks stamina inheritance, so
  training turns aren't wasted chasing an unreachable number.
- **Oguri Cap tuning** — training priority retuned to Speed → Power → Stamina →
  Wit → Guts.

## Icarus v1.0

### Error-handling fixes (from user reports)
- **No more "API error 2511" from an oversized deck.** Career start now trims the
  support deck to a legal size automatically (max 6 cards including the borrowed
  friend), so a saved preset with too many cards can't fail the whole run.
- **Clearer career-start failures.** A server 500/501 at start (including an
  expired/used-up guest parent) now shows an actionable explanation instead of a
  raw error code.
- **Friendlier Steam login/2FA errors.** Steam throttling now reads "Steam
  temporarily blocked sign-ins after too many attempts — wait ~15-30 minutes…"
  instead of `ERROR:RATELIMITEXCEEDED`, and bad-password / bad-code cases get
  plain-language guidance.
- **Login cool-down.** After a failed login or 2FA attempt the button briefly
  locks (20s normally, 60s after a Steam rate-limit) so rapid retries don't
  deepen Steam's own lockout.

### Reliability & insight
- **Rides out server hiccups & maintenance.** When the game server returns a
  "try again later" condition (394/208/maintenance/5xx), the bot now waits with
  escalating, stoppable backoff and **auto-resumes** when the server recovers,
  instead of giving up on the career. The state shows as **WAITING** in the
  Accounts overview.
- **Accounts overview.** The Accounts panel now shows each account's live
  status at a glance — turn, fans, fans/hr, energy, mood, run progress, and the
  new WAITING state.

### Optional decision tuning (off by default)
- **Goal-aware training lookahead** *(Training Settings → toggle)* — boosts
  stats that are behind the pace needed to hit their target by the finals and
  trims those already ahead. Off by default; turn it on to try it.
- **Skill-point optimizer** *(Skills → toggle)* — spends SP to maximize total
  skill value per point instead of strict priority order. Off by default;
  turn it off any time if you prefer the standard buying.

### Interface
- **Selection order is now consistent.** The Setup row (left→right) and the
  Library sections (top→bottom) both follow **Trainee → Parent 1 → Parent 2 →
  Deck → Friend Support**.
- **Deep-space backdrop (now the default).** The default **Icarus** theme now
  uses a real deep-space photo backdrop with calmer, toned-down gold accents
  and glassy, semi-transparent dashboard panels so the backdrop shows through.
  The previous star-and-nebula CSS look is still available as **Icarus Alt** in
  the theme selector.
- **Live Run Monitor is back in Career History** — the run summary sits at the
  top of the Career History window (with a LIVE badge while a run is active) and
  no longer overlaps the history list.
- **Consistent branding everywhere** — the Icarus logo now appears on the Steam
  login & 2FA screens, the What's New popup, and the Help page; remaining pink
  neon text in Help has been retoned to the Icarus gold/navy palette.
- **Configure Skills** gives the **Optimize SP Spend** option its own section
  with a full description of what it does and how it works.
- **Character Profile** now mirrors the stat priority from Training Settings
  when the profile has no override of its own.
- **Career History** portraits are now compact thumbnails (no more oversized
  art).
- **New loading screen** — an animated character portrait framed in a gold ring
  with a soft glow, replacing the old broom/witch art.

### Rebrand — Pre Icarus is now Icarus
- New name and identity across the whole dashboard: the **Icarus** logo in the
  navbar and the What's New popup, "Icarus" page/window title, and Icarus naming
  throughout the in-app help and messages.
- **New navy + gold "Icarus" theme**, now the default look across the entire UI.
  The **THEME** dropdown lets you switch between **Icarus**, **Neon Cockpit**,
  **Midnight** (blue), and **Clean Dark** — your choice is remembered.
- **Your data is safe.** Userdata now prefers an `Icarus_userdata` folder /
  `ICARUS_USERDATA_DIR` env var / `~/.icarus` pointer, but existing
  `SweepyCL_userdata` (and older `SweepyClaude_userdata`) locations, env vars,
  and pointers are still recognized automatically — your login, presets, and
  accounts carry over with nothing to migrate by hand.

### Removed
- **Club Fan Tracker removed**, along with everything tied to the external
  `uma.moe` service (the dashboard card, its API key field, the
  `/api/club-tracker` endpoint, and all related code). Nothing in Icarus calls
  `uma.moe` anymore.

### Fixed
- **Multi-account now works across ports.** The Manager read its account list
  from the build folder while the dashboard saved it to your (external)
  userdata folder, so launching the Manager never started the accounts you
  configured. The Manager now resolves the same userdata folder as the
  dashboard and launches each account on its own port with its own isolated
  login. Added a description and step-by-step how-to in the **Accounts** panel.

## Pre Icarus v7.6.3

Fixes and polish across the dashboard — most importantly, support-card effect
values are now correct.

### Deck bonuses now show correct values

- The support-card effect **type mapping was off by one** from "training
  effectiveness" onward, so cards showed impossible numbers (e.g. **Race Bonus
  +105%** across a deck).
- Mapping corrected against the Umamusume Wiki effect enum and cross-checked
  against gametora for several cards. Race bonus, fan bonus, training
  effectiveness, mood effect, hints, and the event/energy effects now read
  correctly (e.g. Kitasan Black race bonus is **5%**, not 35%).
- The fix applies to both the **Deck Bonuses** panel and the deck-hover tooltip.

### Logo fixed

- The new **Pre Icarus** navbar logo now loads (it was missing its server route).

### Recommended Supports — cleaner Game8-style layout

- Each setup now has a centered title bar over a tidy 6-card row, with a build
  subtitle, mirroring the Game8 trainee pages.
- Each setup shows its **race-bonus caption** (e.g. "65% Race Bonus (MLB)"),
  scraped from Game8 — the scraper was extended to capture it.
- **Alternate cards** are grouped by stat (Speed / Stamina / Power / Guts / Wit).

### Deck hover popup is now horizontal

- The deck tooltip lays cards out in a wide grid so all six are visible — no more
  vertical cut-off.

### AI panel renamed to "AI / Misc" and explained

- **AI Learning** is now **AI / Misc**.
- Added short plain-language explanations under **Shadow Mode**, **Backtest**,
  **Learned Risk / Value**, and **Epithet / Preset Confidence**.
- The **Event Outcome Knowledge Base** now explains what it is, how it fills up
  (auto-captured from your runs), how it's used, and what a "known outcome" means.
- Import example paths now reference Pre Icarus folders.

### Event Choices — outcome-data confidence

- Each event now shows a chip indicating how well-backed its data is:
  **OBSERVED N×** (recorded from your own runs), **DB EFFECTS** (community
  effects database), **KB** (imported), or **NO DATA**.

### Other

- The **Dumper Watcher** feature was removed — native auto-capture already keeps
  the event knowledge base updated from your runs. Its leftover staging code was
  also deleted.
- Added a **regression test** that locks the support-effect type mapping and
  asserts realistic effect caps, so a future master-data re-sync can't silently
  reintroduce the deck-bonus shift.
- The **What's New** popup is cleaner and easier to read (accented headings,
  styled bullets).

## Pre Icarus v7.6.2

A batch of dashboard fixes and a big event-data change: Pre Icarus now **captures
event outcomes natively from its own runs**, plus a
deck limit-break fix, a Recommended Supports modal, a new lifetime metric, the
new logo, and several UI fixes.

### Event outcomes auto-captured from the bot's own runs

Pre Icarus is an API bot — it already receives each event's stat changes before
and after every choice it makes. It now **records those outcomes into the Event
Outcome Knowledge Base automatically as you run careers**, so event-choice
scoring (and the AI Dataset / LLM context) improves on its own. Observed outcomes are keyed by
story id and take precedence over imported/static data for events you've actually
played. A new **Auto-capture** toggle (on by default) sits in the Event Outcome
Knowledge Base card; the manual import and Dumper Watcher remain for seeding
events you haven't run yet. New `record_observation`/`compute_chara_delta` in
`career_bot/event_outcomes.py`; regression-tested
(`tests/test_v762_native_event_capture.py`).

### Deck limit break fixed (Deck Bonuses + deck hover)

The **Deck Bonuses** panel and the deck-hover tooltip were computing every card
at limit break 0 because in-game deck cards weren't carrying your owned cards'
limit-break level. They now use each card's **real limit break**, so the bonus
totals and per-card effects reflect your actual cards.

### Recommended Supports moved into a modal

**Recommended Supports** is no longer a separate Library section — it's now a
**RECOMMENDED SUPPORTS** button inside the **Deck Bonuses** panel that opens a
clean modal with the Trackblazer builds for the selected trainee.

### Career fan gain in Lifetime Metrics

The Lifetime Metrics card now shows **Career Fan Gain** — the fans earned in the
current career — alongside the lifetime totals.

### Career loop on by default

**LOOP** mode now defaults to **on** (run until you stop it) for new users. Set
**RUNS** to 1 for a single career. A saved preference still wins.

### UI fixes

- **Event Choices "Set all to Auto"** now correctly shows every event as **Auto**
  (it was wrongly showing "Choice 1" because `null` compared equal to choice 0).
- The **What's New** popup is now dismissable **only via its close button**
  (no accidental backdrop-click or Escape).
- The **What's New** topics were removed from the in-app Help (the popup already
  covers release notes); fixed two stale Help references (USERDATA button,
  energy-control locations).
- New **Pre Icarus logo** in the top-left of the navbar.

## Pre Icarus v7.6.1

A reliability fix for **career looping**: the bot now recovers from a "career
already in progress" error (API 102) on career start instead of giving up.

### Career start now recovers from API error 102 (career already in progress)

`single_mode_free/start` returns **result code 102** when the server still holds
an in-progress career — so a brand-new start is rejected. This happens when the
local account state is stale, or when a previous run didn't finish/abandon
cleanly (crash, force-close, network drop mid-career).

Before this fix, a 102 on start re-raised: a manual start showed a raw 102, and
the **career loop** (the feature that auto-starts the next career when one
finishes) treated it as a failure — it would retry into the same 102 a few times
and then **stop the loop entirely.**

Now a 102 on start triggers automatic recovery: Pre Icarus refreshes account
state, then **resumes the in-progress career** (`single_mode_free/load`) and
hands it to the runner exactly like a fresh start. The runner finishes that
career and the loop proceeds to the next one — no manual intervention, the loop
stays alive. This mirrors the existing active-career guard on manual start and
the runner's own 102 reconciliation. If there is genuinely no career to resume,
the original error is still surfaced (so unrelated 102s aren't masked). New
`uma_api/career_recovery.py`; regression-tested
(`tests/test_v761_loop_start_102_recovery.py`).

## Pre Icarus v7.6

A large batch: a top-priority race-selection fix, a custom deck builder, a deck
bonuses panel, Game8-scraped recommended supports, event-effect backfill, skill
tier right-click/drag, a smarter userdata popup, and a presets overhaul where
each preset (including its skill config) is its own file.

### Race-skipping fix (dirt & manual schedule) — top priority

When a **manual race schedule** is set, the bot now always runs every race you
picked. The "race-streak safety" heuristic (`_guide_race_chain_break`) ran on
every chosen race with no manual-mode exemption — unlike its sibling
`_irregular_training_decision`, which already bailed out in manual mode. Its
"unsafe grade" branch fires on OP/PRE-OP races, and ~70% of **dirt** races are
OP/PRE-OP (vs ~43% of turf), so it dropped hand-picked dirt races
disproportionately. A manual-mode short-circuit now exempts user-picked
schedules entirely. Regression-tested (`tests/test_v76_fixes.py`).

### Custom deck builder (owned cards only)

`LIBRARY → DECKS → BUILD CUSTOM` opens a picker of the support cards you own
(search + type filter, five slots — a career deck is 5 of your own cards plus 1
borrowed friend — with limit-break badges). The chosen deck feeds the
next career run via the existing `support_card_ids` start payload and persists
across reloads/presets. The game API has no deck-save endpoint, so this does not
change in-game saved deck slots — it replaces needing to edit decks in-game for
the bot's runs. The owned-cards list now preserves each card's limit break + exp.

### Deck Bonuses panel

A new **DECK BONUSES** section at the top of the Library sums each effect across
the selected deck at every card's real limit-break level (reusing the deck-detail
endpoint), with type chips and a deck-quality score.

### Recommended Supports — Game8 Trackblazer builds

Rebuilt to show scraped **Game8 Trackblazer** setups for the selected trainee —
multiple builds, a budget build, and alternates — each card marked OWNED (+LB) or
NOT OWNED. New `tools/game8_support_setups_scraper.py` →
`data/trainee_support_setups.json` (70/75 trainees; 100% card-name resolution).
New `GET /api/trainee/support-setups`. Trainees with no Game8 Trackblazer build
fall back to the owned-card heuristic.

### Event effects backfilled + "Set all to auto"

Events showing "effect not in database" are now filled at serve time from a
scraped gametora effects database (`tools/event_effects_scraper.py` →
`data/event_effects_scraped.json`, 3,639 events), joined purely on `story_id`
(curated/dumper data still wins). The bulk button is now **SET ALL TO AUTO** and
reports the actual number of forced choices cleared.

### Skill tiers: right-click & drag

In Configure Skills, right-click any shown skill to drop it into a Manual Skill
Tier, and drag tier chips between tiers (reusing the existing drag pattern).

### Per-preset settings + skill config

Presets are now **one self-contained file per preset** under
`SweepyCL_userdata/data/presets/`, each holding its settings, skill, and solver
config together — so **Configure Skills choices are now specific to each preset**
(they used to live in one global `skill_config.json` shared by every preset). The
legacy split layout auto-migrates on first run (old files backed up as
`.premigrate.bak`). The store's public API is unchanged; skill/solver endpoints
now take an optional `preset` and switching presets repoints the active store.
Covered by `tests/test_v76_presets.py`.

### Smarter userdata popup

The setup popup no longer appears once a valid userdata folder is configured, and
gained a **"Do not show again"** checkbox (permanent suppress + reopen reset). It
remains reachable from the USERDATA button.

### Removed

- The "Omitted OCR-only Detection" section in Training Settings.

## Pre Icarus v7.4

Three dashboard improvements: a cleaner **Event Choices** window with search and
a fixed auto/forced indicator, **Recommended Supports** for the selected trainee
in the Library, and a **What's New** popup that surfaces this changelog after an
update. Plus an AI tuning fix: **Shadow Mode race warnings are now far more
precise**.

### Shadow Mode — race warnings now gate on win rate (higher precision)

Shadow Mode scores the learned race-risk model by checking how often a *warned*
race actually finished below 1st. A warning that fires on a race the bot then
wins is a **false alarm**, and precision is `useful / (useful + false alarms)`.
Precision was sitting around **16%** — the model was flagging races you reliably
win.

The cause: a race emitted a warning whenever its learned penalty was above zero,
and the penalty formula includes an average-finishing-position term. A race the
bot wins 90% of the time still averages slightly worse than 1st, so it accrued a
small penalty and warned anyway — then "lost" the precision check by winning.

Two changes make warnings selective:

- **`warn_win_rate_ceiling`** (new auto-config knob, default `0.50`): a race only
  produces a negative ("warning") adjustment when its historical win rate is at
  or below the ceiling. Races the bot usually wins no longer warn. Lower it
  (e.g. `0.35`) to warn only on races that lose most of the time and push
  precision higher; clock-dependency data is still recorded either way.
- **`min_samples_for_model`** raised `2 → 4`: a race needs more recorded runs
  before it can warn at all, filtering noisy one-off losses.

Both knobs live in the AI auto-config and are documented in the in-app AI
Learning help. Re-run training after a few careers to see the new precision.

### Event Choices — cleaner UI, search, and an accurate status badge

The EVENT CHOICES window was restyled into clearer cards and gained a search box
(filter by event name, story id, or support card id). Each event now shows a
status badge that is derived from the saved override state:

| Badge | Meaning |
|---|---|
| **AUTO** | The bot decides — single-choice events are auto-confirmed; multi-choice events are scored against your event stat priority. |
| **FORCED** | You locked a specific choice; the bot will always pick it. |

This fixes the previous behavior where a row could still read "Bot auto-picks
Choice X" even when a manual override was set (the old line keyed off the last
run's pick and ignored the saved override). The badge and status text now update
live as you change a dropdown, and search filters a cached list so typing never
re-hits the network.

### Recommended Supports for the selected trainee

The LIBRARY panel has a new **RECOMMENDED SUPPORTS** section. Selecting a trainee
ranks the support cards you already own for that trainee. Because the data has no
explicit per-trainee card recommendations, the ranking is derived: each owned
card is scored by how well its type matches the trainee's stat priority (resolved
from the character profile, falling back to a Speed/Power/Wit meta default), then
by rarity (SSR > SR > R). The section header shows the stat focus used, and each
card's tooltip explains why it was picked. Served by a new
`GET /api/trainee/recommended-supports` endpoint.

### What's New popup

After the dashboard loads — and specifically after the userdata setup popup is
closed or skipped — a **What's New** popup shows the latest changelog entry. It
appears once per version (gated by a `sweepy_changelog_seen_version` localStorage
key) and is served by a new `GET /api/changelog` endpoint that parses this file.

### Files changed

- `main.py` — new `/api/trainee/recommended-supports` and `/api/changelog`
  routes; `_trainee_stat_priority` helper.
- `public/index.html` — event-choices search box + status/legend bar;
  RECOMMENDED SUPPORTS library section; changelog modal markup.
- `public/app.js` — event-choices render rewrite (badge + cached search),
  `loadRecommendedSupports`, changelog popup module, userdata-closed signal,
  help section entry.
- `public/styles.css` — styling for the event-choice badges/search/rows,
  recommended-support cards, and the changelog modal.

## Pre Icarus v7.3

Adds **Manual Skill Tiers** to the Configure Skills modal — a tier-based
skill selector that drives skill purchases when **Enable Skill Point
Check Plan (Beta)** is turned off.

### How it works

In the Configure Skills modal, a new "Manual Skill Tiers" section sits
between "Strategy & Planned Skills" and "Configuration Summary". It has
five tier rows (T1 S through T5 D) with color-coded borders to indicate
priority, a search box at the bottom for adding skills, and a tier-target
dropdown that picks which tier a search result goes into when clicked.

Behavior depends on the **Enable Skill Point Check Plan (Beta)** toggle:

| Plan Check | Manual Tiers | Behavior |
|---|---|---|
| ON | any | Existing smart-scorer behavior, manual tiers ignored. Section shows `INACTIVE — Plan Check is ON`. |
| OFF | empty | Falls back to the smart scorer (no regression). Section shows `PLAN CHECK OFF — fallback to smart scorer (no tiers set)`. |
| **OFF** | **populated** | **Tier list drives purchases.** Section shows `ACTIVE — driving skill purchases`. |

A mode badge inside the section header surfaces which of the three states
is active in real time so the user always knows what the bot will do.

### Tier ordering rules

Tier 1 is highest priority. Within a tier, ties are broken by the
existing smart_score (descending) and cost (ascending). A skill can
appear in only one tier — adding it to a new tier removes it from any
previous one, so the UI can't get into an inconsistent state.

The candidate pool itself is unchanged — every skill the game currently
offers is still considered. The tier system only filters that pool down
to "skills the user wants" and reorders them. Filters like Skip Green /
Skip Red / Skip Unique still apply on top.

### Why not just replace the smart scorer entirely

Some users want manual control over a few specific skills but are happy
with the smart scorer for everything else. Two design choices accommodate
this:

1. **Plan Check is still the master gate.** Leaving it on keeps the
   smart scorer as the source of truth. The tier list is opt-in.
2. **Empty tiers fall back to smart.** Turning the toggle off without
   building a tier list doesn't brick skill purchasing — it just keeps
   the smart scorer running until the user has added enough skills to
   take over.

### Files changed

- `career_bot/config_store.py` — `manual_skill_tiers` added to
  `_default_skill_config()` and `SKILL_CONFIG_KEYS`. `read_skill_config`
  backfills missing tier keys (`"1"` through `"5"`) for older configs.
- `career_bot/skills.py` — new `_manual_tier_lookup()` helper plus a gated
  branch in `_candidates()` that filters and re-sorts candidates by tier
  when `enable_skill_point_check_plan == False` and any tier has skills.
- `public/app.js` — new `renderManualTierSection()` /
  `renderManualTierSearchResults()` / `bindManualTierControls()` plus
  hooks into the existing Configure Skills render cycle. Summary panel
  now includes a `MANUAL TIERS` row with active-state highlighting.
- `public/index.html` — no change (the new section is rendered into the
  existing `#skill-config-body` container).
- `public/styles.css` — tier-row styling, color-coded left borders, chip
  styling, section badge.

### What didn't change

- The smart scorer and all its tuning knobs (`smart_skill_yellow_bonus`,
  `smart_skill_green_penalty`, `smart_skill_min_score`, the weights dict)
  are untouched. Plan Check ON behavior is byte-identical to v7.2.
- `learn_skill_list` / `forced_skills` continue to work as priority hints
  for the smart scorer. They're a separate feature from manual tiers —
  the existing "Planned Skills" tab still controls them.
- Old `skill_config.json` files without `manual_skill_tiers` load
  cleanly. No migration required.

### Note on the v7.2 manual race fix carryover

All v7.2 fixes (strict manual race mode, smart-solver gating, hot-reload,
responsive top nav, parent search hover) are preserved unchanged.

## Pre Icarus v7.2

Large release. Audit-driven fixes for manual race selection, surface
preference enforcement, smart-solver scope, top-nav responsive layout,
and the parent-search hover regression. Bot Speed removed per user
request. New: mid-career settings hot-reload.

### Manual race selection — strict mode (fixes dirt races on fallback)

**Audit finding from 3 career logs:** 102 of 117 race picks matched the
user's manual list. The 15 deviations broke down as:

- 3 picks on turn 12 (`_forced_race=True`) — the scenario-scripted Make-Up Debut
- 5 picks on turns 74/76 (`_forced_race=True`) — URA / Mant Finals (also scripted)
- 7 picks on turns 37 / 71 (forced=False) — **the actual bug**

The non-forced deviations were `force_racing: true` (from `mant_config`)
firing on turns where the user's list had nothing scheduled. The old
code would then call `_sort_races_for_trackblazer(all_valid, ...)` which
picks from every aptitude-passing race — including dirt, despite the
user only selecting turf races in `preferred_surfaces`.

**Fix in `career_bot/races.py`:**

1. When `extra_race_list_source == "manual"`, the runner now **short-circuits
   all smart fallbacks** (`force_racing`, `enable_farming_fans`, low-fans
   auto-race). If the user's list has no race for this turn, the bot
   trains instead of picking a random aptitude-passing race.
2. New `_filter_by_surface_preference()` helper. Applied to every
   non-manual fallback path (low-fans rescue, fan farming) so dirt races
   no longer slip through when the user set `preferred_surfaces: ["turf"]`.
3. Defense in depth in `main.py`: if a request explicitly says
   `race_planner_mode: smart` but the saved preset has
   `extra_race_list_source: manual` with a non-empty list, the runtime
   stays in manual mode. Prevents a stale UI state from silently
   downgrading.

### Smart Race Solver settings now gated to smart mode

User report: "the consecutive races limit in scenario overrides doesn't
do anything; the max streak setting in smart race solver does. Make it
so smart solver settings only apply when smart is on."

`career_bot/races.py:_solver_setting()` reads from `mant_config[key]`
first, then `trackblazer_solver_settings[key]`. The latter is now
**skipped entirely when `extra_race_list_source == "manual"`**. So
`max_races_in_row`, `fan_bonus`, `optimization_mode`, etc. only
influence the bot when the Smart Race Solver is actually driving.

`mant_config` overrides (which include `race_chain_target`,
`preferred_distances`, etc.) still apply in manual mode because those
are scenario-wide settings the user explicitly set in Scenario Overrides.

### Bot Speed removed

Per user feedback ("the speed settings on the top nav bar don't change
anything"), the v6.7.27 Bot Speed dropdown is removed:

- `career_bot/delay.py` — `DELAY_SCALE`, `set_delay_scale`, and
  `get_delay_scale` deleted. `simulate_delay` and `simulate_turn_delay`
  reverted to their pre-v6.7.27 bodies.
- `main.py` — `BOT_SPEED_PRESETS`, `load_bot_speed_scale`,
  `set_bot_speed_scale`, `bot_speed_label`, and the `/api/settings/bot-speed`
  GET/POST endpoints deleted.
- `public/index.html` / `app.js` / `styles.css` — SPEED dropdown, JS
  handlers, and CSS removed.

If your `settings.json` still has a `bot_speed_scale` key from v6.7.27,
it's harmless dead data and can be left as-is.

### Mid-career settings hot-reload (new feature)

User request: "Make it so if the user changes settings in the middle of
a career run it saves it and uses those changed settings for the next
runs after, that way the user doesn't have to stop the entire bot and
then restart it for the changes to take effect."

`career_bot/runner.py:_run()` now re-reads the preset from disk at the
top of every new turn (turn-change boundary, not every inner-loop
iteration — so I/O cost is ~78 reads per career, negligible). Changes
the user makes in the UI mid-career take effect on the very next turn.

Runtime-only fields (`extra_race_list_source`, `race_planner_mode`,
`_runtime_overrides`) are preserved across hot-reload so the start-of-run
mode choice isn't accidentally overridden by what's on disk. When in
smart mode, the runtime `extra_race_list` (authored by the smart-solver
replanner) is also preserved so a hot-reload doesn't clobber an
in-progress dynamic schedule.

Hot-reload events are logged to the runner's `_log` stream as
`hot_reload_preset` entries with the list of changed fields, so you can
audit when settings actually took effect.

### Top nav bar — responsive layout

Buttons were `min-width: 220px` × 7 = 1540px minimum even before gaps.
Common 1366×768 / 1440×900 monitors couldn't fit them, causing overlap
and squish. Now:

- `flex-wrap: wrap` on `.v516-top-actions` so buttons wrap to a second
  row instead of squishing.
- `min-width: clamp(120px, 16vw, 220px)` on buttons so they scale fluidly.
- `font-size` and `letter-spacing` also clamped so labels stay
  legible at smaller sizes.
- Two new breakpoints at 1500px and 1200px that tighten gaps and
  shrink button heights for laptop screens.

### Parent search hover bug (regression from v6.7.25)

The v6.7.25 width-cap CSS was scoped to descendants of
`.guest-parent-card`. But the JS `show()` handler appends the tooltip
to `<body>` to escape grid clipping — moving it out of the descendant
selector. The cap stopped applying, tooltips reverted to the default
~620px width, and they once again covered the surrounding parent
cards (making them appear to "disappear" when one was hovered).

Fix:

- New body-level CSS rule `body > .sparks-tooltip[data-guest-index]`
  that reapplies the cap after the tooltip moves to body. The
  `data-guest-index` attribute persists across the DOM move, so the
  selector matches.
- Patched the direct (non-delegated) hover bind to set
  `data-guest-index` when the card is a guest parent — the delegate
  already did this, the direct path didn't, so the attribute was
  inconsistently present.

### What didn't change

- v7.1.x userdata-folder popup and resolver, Dumper Watcher (v6.7.26),
  screenshot-driven solver fixes, project rename to Pre Icarus —
  all preserved.
- Existing presets and settings remain compatible. No migration needed.

## Pre Icarus v7.1.2

Bug fix: the userdata popup was firing on `DOMContentLoaded`, which runs
before authentication. That meant it appeared on top of the Steam auth
form, blocking the user from logging in.

### Fix

The popup now waits for a new `sweepycl:dashboard-ready` event dispatched
at the end of `renderDashboard()` in app.js. This event fires for both
manual login and cached-session auto-login, so the popup auto-opens
after either path. It also fires after the brand-intro animation
completes, so the popup doesn't cover a transition mid-flight.

A 1.5s safety fallback handles a rare race condition where the listener
attaches after the event has already fired (e.g. very fast cached
auto-login): it checks whether the dashboard view is visible and runs
the same handler. The handler itself is idempotent (`_autoOpenFired`
flag) so there's no risk of double-opening.

The diagnostics card injection and the binding of buttons still happen
on DOMContentLoaded, so when the user reaches the dashboard everything
is already wired and the auto-open is instant.

### What didn't change

- All v7.1.1 fixes carry over: no click-outside-to-close, no
  Escape-to-close, prominent red × button, Diagnostics fallback card.
- API endpoints, pointer file location, resolution order, migration
  behavior — all identical.
- The popup still auto-opens whenever it should (first load after auth,
  detection warnings, or via the USERDATA top-bar button / Diagnostics
  card).

## Pre Icarus v7.1.1

Bug fixes for the userdata popup from v7.1:

### Fixes

- **The popup no longer closes on click-outside or Escape.** In v7.1 the
  modal had a click-outside-to-close handler and an Escape-to-close
  handler, but in practice that meant: pasting a path via the OS context
  menu (right-click → Paste) would dismiss the context menu with a click
  that registered on the modal backdrop, instantly closing the popup
  with the path you hadn't yet pasted. Same thing for stray clicks just
  outside the input padding. Both handlers are removed entirely. The
  only ways to close the popup now are:
  - The red **×** close button (now styled prominently in the header)
  - The **I'LL HANDLE IT LATER** dismiss button (marks intro seen)
  - Successfully applying a path (the popup stays open so you can read
    the "restart required" confirmation)

- **Userdata setup is now reachable from Diagnostics as a fallback.**
  A new "Userdata Folder" card lives inside the Diagnostics modal,
  showing the current resolved path, source, pointer-file target, and
  any detection warnings inline — plus an `OPEN USERDATA SETUP` button
  that reopens the popup. This is in addition to the existing USERDATA
  button in the top action row. If you dismissed the startup popup
  before finishing, or the popup ever gets into a weird state, the
  Diagnostics card is always there.

### What didn't change

- The resolution order, pointer-file location (`~/.sweepycl/userdata_pointer.json`),
  API endpoints, and migration behavior are all identical to v7.1.
- The popup still auto-opens on first load and whenever a detection
  warning fires.
- All v6.7.x and v7.0/7.1 carryovers (Bot Speed, Dumper Watcher, the
  rename, etc) are unchanged.

## Pre Icarus v7.1

Adds a first-load **Userdata folder** popup that walks users through
setting up a stable, version-independent location for settings, presets,
and Steam auth. Solves the upgrade scenario where you download a new
build into a fresh folder (without overwriting the previous version) and
the new install can't see the old userdata.

### What the popup does

- On first dashboard load after Steam auth, the popup explains what the
  userdata folder is for and shows where settings currently live.
- Lets the user enter a custom path (text field; the folder will be
  created if missing and probed for writability before the path is
  saved).
- A `USE SUGGESTED` button fills in the recommended convention
  (`<build's parent>/SweepyCL_userdata`).
- Optional **migrate** checkbox — copy currently-loaded
  settings/presets/auth into the new folder when applying. Non-destructive:
  files already at the destination are never overwritten.
- An `I'LL HANDLE IT LATER` dismiss button records the choice so the
  intro doesn't pop up again on every load.
- Reopen any time via the new **USERDATA** button in the top action row.

### How upgrades find the old userdata

New resolver step: a pointer file at `~/.sweepycl/userdata_pointer.json`
(or `%USERPROFILE%/.sweepycl/userdata_pointer.json` on Windows). Lives
outside the build folder so a fresh install of any future Pre Icarus
version automatically picks up where the user told a previous version
their data lives. The resolution order is now:

1. `$SWEEPYCL_USERDATA_DIR` env var
2. `$SWEEPYCLAUDE_USERDATA_DIR` (legacy env var)
3. **NEW** Pointer file at `~/.sweepycl/userdata_pointer.json`
4. `../SweepyCL_userdata` sibling folder
5. `../SweepyClaude_userdata` (legacy sibling folder)
6. In-build `DIR` (fallback — the popup warns about this case)

### Detection warnings the popup surfaces

- **Pointer file references a folder that doesn't exist anymore** —
  "Your saved userdata path (…) doesn't exist or isn't a folder.
  Settings will fall back to a default location until you fix this."
  Fires when the user moves/deletes the userdata folder, or when they
  point an old install at a path that doesn't exist on a new machine.
- **No userdata configured at all** — "Settings will be saved inside
  the build folder, which means they'll be lost when you upgrade to a
  new version unless you overwrite the install."
- **Using a legacy Pre Icarus path** — informational only; still
  works, but the popup offers to migrate to a Pre Icarus path cleanly.
- **Path change pending a restart** — after applying a new path in this
  session, the popup notes that some consumers of the path are cached
  and a restart is needed for the new location to take full effect.

### Why a restart is required after changing the path

`USERDATA_DIR` is read once at module import and cached by several
consumers (preset_store, settings reads, accounts.json, auth, the
active-selection file, etc). Hot-swapping it mid-session would risk
inconsistent reads/writes. The popup writes the pointer file
immediately and explicitly tells the user to restart Pre Icarus — much
safer than trying to invalidate every cache live.

### What didn't change

- Existing v7.0 installs continue to work exactly as before. The popup
  only opens when there's something to set up or warn about.
- Env var overrides (`$SWEEPYCL_USERDATA_DIR`,
  `$SWEEPYCLAUDE_USERDATA_DIR`) still beat the pointer file, so power
  users with scripted setups are unaffected.
- Legacy `SweepyClaude_userdata` sibling folders are still resolved
  with no changes.
- All v6.7.x carryovers (Bot Speed scaling, Dumper Watcher, etc) are
  preserved.

### Files changed

- `main.py` — new pointer-file helpers, expanded `_resolve_userdata_dir`
  with source tracking and warning generation, six new endpoints under
  `/api/userdata/*`, and Pydantic models for the two POST bodies.
- `public/index.html` — userdata modal markup; new USERDATA button in
  the top action row.
- `public/app.js` — self-contained IIFE (matches the v6.7.19 help
  modal's pattern) that auto-opens on load when needed, handles apply
  / dismiss / suggest / reopen, and never blocks the rest of the
  dashboard from booting.
- `public/styles.css` — modal styling.

## Pre Icarus v7.0

**Project renamed: Pre Icarus → Pre Icarus.** Major version bump to mark
the rename cleanly. No new features — this is purely a rebrand release.
The functional behavior of v6.7.27 is preserved exactly, including the
Bot Speed dropdown, Dumper Watcher, screenshot-driven solver fix, and
everything else from the v6.7.x series.

Future releases follow `Pre Icarus v7.x` for new features and `Pre Icarus v7.x.y`
for patches. Historical changelog entries below keep their original
`Pre Icarus v6.7.x` and `Pre Icarus vX.x` names because those releases
shipped under those names — rewriting the history would just be
confusing.

### What changed

- **User-facing UI**: help modal title, footer, in-app documentation, and
  Discord webhook identity all now say "Pre Icarus" instead of
  "Pre Icarus" / "Pre Icarus".
- **Active code**: docstrings, comments, version label constants (e.g.
  AI dataset version stamps for newly-written rows), and the build_version
  string written into freshly-rebuilt AI datasets all use "Pre Icarus".
- **INSTALL.md**: rebranded throughout.

### What did NOT change (and why)

- **`SweepyClaude_userdata` folder discovery still works.** The userdata
  resolver now prefers `SweepyCL_userdata` and `$SWEEPYCL_USERDATA_DIR`,
  but falls back to the legacy `SweepyClaude_userdata` folder and
  `$SWEEPYCLAUDE_USERDATA_DIR` env var if the new ones aren't present.
  Existing v6.7.x installs upgrade without any data migration required.
  Brand-new installs use the new names.
- **The "paste an old Pre Icarus folder" import dialog** still says
  "Pre Icarus" because that text describes folder names that exist on
  users' disks from the original Pre Icarus era. Renaming the prompt
  would just be misleading — those folders are still called what they're
  called.
- **Test file names** like `test_sweepymodv544_event_outcomes.py` and
  archive docs under `docs/` keep their original names. They document
  features introduced under the Pre Icarus name; renaming them serves no
  purpose.
- **Historical version stamps** already written into past data files
  (`Pre Icarus v5.40AI` build_version, `Pre Icarus Event Outcome KB v1`
  label that's been replaced with `Pre Icarus` for new exports but
  recognized as legacy when reading old files) are not retroactively
  rewritten in existing user data.

### Upgrade path

Drop this build over your v6.7.27 install. Your `SweepyClaude_userdata`
folder will continue to be picked up automatically. If you want to rename
it to `SweepyCL_userdata` to match the new convention you may, but it's
optional — both names work.

## Pre Icarus v6.7.27

Adds a **Bot Speed** preset selector that actually makes the bot fast. The
existing **Tempt Fate** button only zeroes the between-turn pause; it does
**not** touch the per-endpoint anti-detection sleeps in
`career_bot/delay.py:_BASE_DELAYS`. Those were the real bottleneck —
`exec_command` averages ~5 s/call and `gain_skills` averages ~48 s/call, so
even with Tempt Fate on, a career sits around 25-30 min.

### What changed

- `career_bot/delay.py` — new `DELAY_SCALE` global (default 1.0) plus
  `set_delay_scale()` / `get_delay_scale()`. Applied inside
  `simulate_delay()` (both the known-endpoint and unknown-endpoint paths,
  including the distraction bonus) and `simulate_turn_delay()`. Scaling
  the lognormal target mean and the min/max clamps in proportion preserves
  the human-looking distribution shape; it just compresses it.
- `main.py` — settings persistence under `bot_speed_scale`, applied on
  startup and on every config write so the value survives restarts. New
  endpoints: `GET /api/settings/bot-speed` and `POST /api/settings/bot-speed`.
  Four presets: `realistic` 1.0×, `brisk` 0.5×, `fast` 0.25×, `speedrun` 0.05×.
- `public/index.html` / `app.js` / `styles.css` — a SPEED dropdown sits in
  the top control bar next to Tempt Fate. Independent of Tempt Fate: stack
  them for max effect.

### Measured impact (simulated against actual per-career call frequencies)

| Preset | scale | exec_command avg | gain_skills avg | est. career |
|---|---|---|---|---|
| Realistic | 1.0× | 6.16 s | 44.5 s | ~27 min |
| Brisk | 0.5× | 2.92 s | 21.4 s | ~14 min |
| **Fast** | **0.25×** | **1.47 s** | **11.2 s** | **~7 min** ← target |
| Speedrun | 0.05× | 0.29 s | 2.2 s | ~1.5 min |

These are anti-detection sleeps only; actual network round-trips add to all
of them, so real-world careers will run slightly slower than the simulated
floor.

### What is NOT scaled (and why)

`dna_sleep()` calls in `uma_api/client.py` (the 0.83 s / 2.5 s / 4.15 s
backoffs after HTTP 709 / 394 / 202 errors) and `runner.py`'s 10-second
recovery wait are **not scaled**. These are tuned to the game server's own
recovery timing — compressing them risks immediately re-tripping the same
error. They also don't fire on a clean career, so they're not the
bottleneck anyway.

### Risk tradeoff (read before picking Speedrun)

The lognormvariate distributions in `_BASE_DELAYS` were designed to mimic
human reaction-time variance. Scaling them down doesn't change the *shape*
but it does compress the timing window into something a server-side
behavioral classifier might flag as bot-like. Higher scales = safer.
Defaults to 1.0 (realistic); the user has to explicitly choose faster.

### How to use it

1. Top control bar, next to TEMPT FATE: new `SPEED` dropdown.
2. Pick a preset. Saves immediately, applies to the next API call.
3. Stack with Tempt Fate (which zeroes the between-turn pause) for max
   speed. Fast + Tempt Fate is the recommended setting for the ~6 min
   target.

## Pre Icarus v6.7.26

Adds **Dumper Watcher** — a background poller that auto-imports event
outcome data from the community dumper tool's `outcomes.json` into an
**isolated staging file** the bot never reads. Lets observations
accumulate from real play without ever changing how the bot scores
events. You review the diff in the AI Learning panel and click PROMOTE
when you're ready to feed the new data into live decisions.

### Why isolation matters

The bot's `EventManager` (in `career_bot/events.py`) reads exactly one
file when deciding event choices: `data/event_outcomes.json`. The AI
Dataset reads exactly one jsonl: `event_outcome_rows.jsonl`. The
watcher writes to neither of those — it writes to
`data/event_outcomes_staging.json` and
`uma_runtime/ai/event_outcome_staging_rows.jsonl`. Until you click
**PROMOTE** in the dashboard, staged data has zero effect on bot
behavior. Verified with a smoke test against the dumper's
`outcomes.json`: live file byte-identical before and after import.

### How to use it

1. Run the community dumper as you normally would.
2. In Pre Icarus, open **AI LEARNING** → **Dumper Watcher**.
3. Paste the path to the dumper's `outcomes.json`, set a poll interval
   (default 30 s), check **Enable**, click **SAVE**. The watcher will
   re-import in the background whenever the file's mtime changes.
4. The status block shows the watcher's state: enabled / thread alive,
   last poll time, last import time and event count, and any error.
5. The diff block shows how staging compares against live:
   - **new vs live** — events the dumper has captured that aren't yet
     in the live KB.
   - **updated** — events whose actual outcome data differs from live
     (provenance-only differences are filtered out so you don't see
     phantom updates).
6. When the diff looks healthy, click **PROMOTE NEW EVENTS** (safe; only
   adds events that don't yet exist in live) or **PROMOTE ALL** (also
   overwrites existing entries where the staging values have changed).
   Both buttons confirm before writing.
7. **CLEAR STAGING** wipes the staging file and resets the watcher
   mtime so the next poll re-imports from scratch. The live KB is
   never touched by this.

### What changed

- `career_bot/event_outcomes.py` — new `import_outcomes_to_staging()`
  that mirrors `import_outcomes()`'s merge semantics but writes to
  `STAGING_FILE` and `STAGING_DATASET_FILE` only.
- `main.py` — background watcher thread (off by default), settings
  persistence under `dumper_watcher` key, and six endpoints:
  `GET /api/dumper-watcher/status`, `POST /api/dumper-watcher/config`,
  `POST /api/dumper-watcher/run-now`, `GET /api/dumper-watcher/diff`,
  `POST /api/dumper-watcher/promote`, `POST /api/dumper-watcher/clear-staging`.
  The watcher starts on app boot but self-gates on the `enabled` flag,
  so it's a no-op until you turn it on.
- `public/index.html` / `app.js` / `styles.css` — new Dumper Watcher
  card inside the existing AI Learning modal, sitting next to the
  Event Outcome KB card. Both promote actions show a confirm dialog
  before writing to live.

### Caveat carried over from the dumper itself

The dumper's README notes its "take most extreme observed delta"
approach means early observations under-report variable events
(e.g. an event that gives −20 energy will be recorded as −5 if it
fired while you had 5 energy). The watcher imports whatever the
dumper writes; the staging file inherits this noise. Stage data for
a while before promoting, and spot-check `event_outcomes_staging.json`
for entries with implausibly tiny deltas or uniformly large gains
before clicking PROMOTE.

## Pre Icarus v6.7.25

UI bug-fix and feature pass. Six items: the Event Choices panel finally lets
you actually pick a choice, the panel gets a one-click bulk Reset to Auto,
the parent grid stops "swallowing" parents when you hover after a Refresh,
hovering a deck now shows a per-card breakdown with real bonuses and a
deck-quality score against the selected trainee, the rest → recreation
chain that ate three turns in a row is guarded, and clicking an already-
focused turn in the Action Log unlocks it so the Decision Reasoning panel
resumes tail-following.

### Event Choices — clicking a Choice actually sticks now

The dropdowns in **Event Choices** were unresponsive to user picks. The
change handler was disabling the `<select>` and then awaiting a full re-
render of the entire list, which destroyed the very element the user was
still interacting with — dropping the click on the floor. The handler now
updates the row's local state (`has-override` class flip) and POSTs the
override without tearing down the DOM. Optimistic update on success, roll
back the class on failure, no more interrupted clicks.

### Event Choices — Reset All to Auto

A new **RESET ALL TO AUTO** button sits next to **REFRESH EVENTS** at the
top of the Event Choices modal. One click wipes every saved override so
every event falls back to Auto (the bot's own scoring) without having to
walk down the list and reset each one by hand. Backed by a new endpoint
`POST /api/events/overrides/clear` that empties `event_overrides.json`.

### Guest Parents — hover no longer hides the parents

After Refresh (which "searches" guest/rental/follow/friend/succession
sources), hovering any parent card made the surrounding parents appear to
disappear. Root cause: the sparks tooltip is a fixed-position panel that
defaults to ~620px wide and up to full viewport height. The positioning
helper clamped its top to `8px` when the card was near the top of the
viewport, but that meant the tooltip landed *on top of* the hovered card
plus the next three to four cards in the row. Two fixes:

- `positionSparkTooltip()` now flips below the card when the above
  placement would clip, instead of clamping the tooltip on top of the
  card it's describing.
- Inside `#guest-parent-grid` the tooltip is capped to ~420px wide and
  ~440px tall so it can no longer span four 145px columns. The owned-
  parent tooltip on the larger Parents grid is unchanged.

### Deck hover info + deck-quality score

Hovering a deck container (own or any saved deck slot) now opens a
breakdown panel:

- Per card: name, type chip (speed / stamina / power / guts / wit /
  friend), rarity badge, LB level, resolved character level, and the
  top bonuses at that level. Numbers come from
  `support_effects_resolved_core.json` so they match what the card
  actually grants (Friendship, Training Effectiveness, Motivation, Race
  Bonus, Skill Points, stat bonuses, etc.).
- A deck-quality score on a 0–10 scale and a one-line verdict ("Strong
  fit for X — speed-heavy, good LB", "Workable but mismatched: trainee
  grows stamina, deck leans speed", and so on). Scoring weights
  type-match against the trainee's `growth` profile from
  `trainee_profiles_core.json`, with secondary contributions from total
  bonus strength, LB density, rarity, and type variety.
- A footer with the breakdown: total LB, type-match %, bonus strength %,
  LB density %.

Backed by a new endpoint `GET /api/supports/details?ids=…&lbs=…&trainee_card_id=…`.
If `support_effects_resolved_core.json` is missing (no master data sync
yet), the panel says so politely instead of erroring out.

### Solver — break the rest → recreation chain

The screenshot showed a Mant career (Oguri Cap, scenario 4) picking rest
at turn 35 (HP 0/108, MOOD 4), then recreation at turn 36 (HP 30/108,
MOOD 4 → 5), then **recreation again at turn 37 with motivation already
at Great (5)** — a wasted turn. The career log confirmed both turn 36
and turn 37 sent `command_type=3` (recreation). The actual culprit is
the **summer-camp recreation branch** in `_best_command`:

```python
if turn in SUMMER_CAMP_TURNS and recreation and (vital <= rest_threshold or failure >= 35 or best_score < 0):
    return recreation
```

It fires on energy / failure / score alone and never looks at mood, so
once vital is low during summer camp the bot will recreate every turn
until vital recovers — even after motivation has already hit Great,
where the action gives essentially nothing. Fixes:

- The summer-camp branch now skips recreation when motivation is at
  Great (5), or when motivation already reached Great after a previous-
  turn recreation. Turn 37 in the screenshot now falls through to the
  rest gate (vital 30 ≤ rest_threshold 48) and returns rest, which is
  what should have happened.
- `_should_recreate()` separately tightens the motivation-driven trigger
  (vital ceiling from `< 90` to `< 60`) and adds a previous-recovery-turn
  guard against recreation-after-recreation on the PAL-thresholds path.
  These cover the non-summer-camp loop variants where the trigger is
  mood + weak rainbows rather than the summer-camp special.
- `_best_command` records the turn number and kind whenever it returns
  rest or recreation via a small `_record_recovery` helper, so the next
  turn can see "we just recovered" and act on it.

If you re-run with v6.7.25 and still see a recovery chain, the most
likely remaining path is the trackblazer race-streak safety at
`mant.py:1255` (only fires after many consecutive races) — send the log
and I'll guard that path too.

### Action Log — second click unlocks the focus

Clicking a turn in the **Action Log** (or a card in **Decision Reasoning**)
focuses that turn — Decision Reasoning scrolls to it and stops following
the live run. Clicking the same row a second time now unlocks the
selection: `state.reasonSelectionLocked` is cleared, the highlight is
removed, and the panel re-pins to the bottom so it resumes tail-following
as new turns arrive. No need to scroll back to the bottom by hand.

## Pre Icarus v6.7.24

Groundwork for race win-probability analysis. This release adds data and an
offline analysis tool ONLY — it changes nothing about how the bot plays. The
goal is to find out, on real career logs, whether "field strength vs your
stats" actually separates wins from losses before any of it touches the solver.

### New competitor-stat export (Phase 0)

The master-data export now includes `single_mode_npc_core.json`, built from the
`single_mode_npc` table in master.mdb. `rival_races_core.json` already told the
bot which rival appears in which race, but only their identity — this new file
adds their actual stat block (speed/stamina/power/guts/wit) and aptitudes
(distance/style/ground, as letter grades), keyed by NPC id. It is generated the
next time you run a master-data sync. Nothing reads it during a run yet.

### New offline analyzer (Phase 1)

`tools/race_winnability_report.py` reads a finished-career log and reports
whether simple strength signals predict your results. It runs two checks:

- Analysis A (log only): does your stat strength at each race separate wins
  from losses, overall and per grade? Reported as an AUC (0.50 = no signal,
  0.70+ = useful).
- Analysis B (needs the new export): for races where a named rival appeared,
  does the gap between your stats and the rival's actual stats predict the
  result?

Run it with `python tools/race_winnability_report.py <career_log.json>`. On an
example log, Analysis A returned an AUC around 0.70 — meaningful, but partly
driven by stats naturally rising over a career, with the high-stat losses
explained by 0-energy racing and long-distance stamina rather than raw
strength. That is exactly the kind of finding this tool exists to surface.

### Next

If the analysis holds up on more logs, Phase 2 would wire a win-probability
estimate into the solver as an optional, gated race-preference nudge (prefer
winnable races, skip unwinnable ones), defaulting off and validated before
becoming a default — same posture as the LPA and event-driven toggles.

## Pre Icarus v6.7.23

UI and documentation pass: a full per-race history in Career History, a much
clearer Event Choices panel, an overhauled Help section (now covering the
Local LLM advisor), and the decision-reasoning panel follows the live run
again.

### Career History — per-race breakdown

VIEW DETAILS on any completed career now includes a **Race History** section
listing every race that career ran, styled like the in-game Career Info
screen: grade badge (G1/G2/G3/EX/Debut), race name, venue, surface and
distance, the in-game date, your finishing place, and fans earned. It also
adds information the game does not surface in one place — the **stats and
energy you had at the moment of each race**, the race type (mandatory vs
solver-planned), and whether a clock was used. A summary line flags how many
races were run at 0 energy, making over-racing easy to spot at a glance.

### Event Choices — shows what each choice does

The panel previously listed events with bare "Choice 1/2/…" dropdowns. It now
shows **the effect of each choice** (e.g. "speed +6, stamina +6", "skill hints
1"), pulled from the outcome database and colour-coded for gains vs losses,
both inline under each event and inside the dropdown itself. The auto line is
clearer about what the bot would pick and why, and "Auto" vs a forced choice
is explained. Events with no recorded data are labelled plainly. (Backend:
`/api/events` now returns per-choice `outcomes`.)

### Help section overhaul

Every area got more practical detail, and a new **Event choices** topic was
added. The big addition is the **AI Learning** rewrite, which now documents:

- Outcome risk, Shadow Mode, and Live Policy Assistance (and the shadow-
  precision gate that keeps learned hints off until they are reliable).
- The **Local LLM advisor** end to end — how to set it up with LM Studio or
  Ollama (provider, base URL, model), what each mode does (Off / Offline
  Analysis / Shadow Advisor / Recommend Only), the fact that it is
  advisory-only and cannot control the runner, how it could ever influence
  decisions (only via the precision-gated policy path, never directly), and a
  clear recommendation to use Offline Analysis for post-run insight.

The Smart Race Solver topic now explains event-driven re-planning (v6.7.22)
and the energy/streak interaction, and the History topic documents the new
per-race detail.

### Decision Reasoning — tail-follow restored

The Decision Reasoning panel follows the live run again: while scrolled to the
bottom it stays pinned as new turns arrive; scrolling up pauses it; scrolling
back to the bottom resumes following. Focusing a specific turn still works.

## Pre Icarus v6.7.22

The big one: aligns the re-planning model with the reference bot and fixes the
"raced 12 in a row with Max Streak 5" bug. Two changes that share one root
cause — the old every-turn, forward-only re-solve.

### Background (from a real v6.7.20 career log)

A career raced 12 times in a row (turns 48–59) with Max Streak set to 5, and
the last eight of those were at **0 energy**, which lost the big races
(including a 15,000-fan Tenno Sho Spring at 9th). Root cause: the solver was
re-solved after every race, forward-only, and each re-solve reset its streak
counter to 0 — so races already run just before the re-solve weren't counted
and consecutive races piled up far past the limit. A well-tuned bot doesn't do
this: it solves once and only re-plans on real events.

### What's new

**1. Re-Plan Only on Race Events (event-driven) — new toggle, defaults ON.**
The schedule is now solved once and reused. Winning a race keeps the plan;
only a **loss** (unless you've also disabled loss re-planning) or a **planned
race that became unavailable** triggers a re-solve. This removes the per-turn
churn that piled up race streaks and, in earlier versions, dropped winnable
high-fan races. Turn it OFF to restore the old every-turn behavior.

**2. Carry-in streak seeding (always on).** Whenever the solver does run, it
now counts the races on the turns immediately before it and keeps the
consecutive-race limit correct across the re-solve boundary — both in the
exact MILP backend (a boundary constraint) and the beam backend (a seeded
streak). So Max Streak is now respected even across a re-solve, not just
within one solve's window. Verified end-to-end against the live solver.

**3. Re-solve diagnostics now actually appear in the career log.** v6.7.20's
`replan_log` was written to the wrong place and never surfaced; it's now part
of the saved log, so each re-solve's backend, fallback, race count, current
stamina, and any dropped high-value races are visible.

### Recommended companion setting

Independently of these fixes: "Ignore Low Energy Racing Block" + energy
threshold 0 makes the bot race at 0 energy, which loses races. The reference bot
wins more *because* it manages energy. Turning that block off and setting a
real energy threshold (~30) is strongly recommended for win rate.

### Notes

Defaulting event-only re-planning to ON changes behavior for everyone on
upgrade — this is intentional, since the every-turn re-solve was the source of
the streak blowout, the high-value-race drops (v6.7.17), and run-to-run plan
churn. The v6.7.20 beam-fallback guard and v6.7.21 loss toggle both still
apply and compose with this.

## Pre Icarus v6.7.21

Adds a **Disable Schedule Re-Plan Upon Race Loss** option to the Smart Race
Solver page, mirroring the feature the reference bot shipped in
its 5.7.x line.

### What's new

A new "Re-Planning" card on the Smart Race Solver page with a single toggle,
**Disable Schedule Re-Plan Upon Race Loss** (defaults to **off**). By default,
losing a race re-plans the remaining turns — the lost race may be re-routed
to a later turn and epithet branches re-evaluated. When the toggle is on, the
original schedule is kept after a loss instead.

The loss itself is still recorded either way; only the *re-planning* is
suppressed. Epithets that depended on the lost race won't be re-routed when
the toggle is on (matching the benchmark's wording exactly).

### How it works

Two re-solve paths honor the setting when it is on:

  * The **race-result re-solve** that runs after each race is skipped on any
    non-1st finish (a 1st-place finish still re-solves normally).
  * The routine **every-turn re-solve** reuses the plan already held once the
    run has recorded any loss, so the schedule stays locked in for the
    remaining turns.

The **missing-race re-solve** (a planned race that genuinely became
unavailable that turn) is never gated — the route must still adapt around a
race it can no longer run. With the toggle off, all behavior is exactly as
before.

### Notes

The setting reads with the same precedence as the other solver knobs
(`mant_config` override, then the Smart Race Solver panel value) and is
saved into `trackblazer_solver_settings`, so it travels with the preset and
shows up in the settings banner. This pairs naturally with v6.7.20's
beam-fallback guard: together they keep a good plan stable rather than
churning it after a loss.

## Pre Icarus v6.7.20

Diagnoses and guards against the run-to-run race-count / fan swings (some
careers hit 40 races and 700K+ fans, others stall at 32 races and ~360K).

### Background

Tracing real career logs showed the entire fan gap comes from the big
repeated G1s — Japan Cup and Arima Kinen (30,000 fans each), plus Tenno
Sho. Good runs race and win all of them; weak runs skip almost all. It is
not HP and not stamina (the weak run often had *more* stamina at the
skipped turns), and the initial solver plan is stable at 42 races. The
difference is the runtime re-solve: in some runs it leaves a high-value
turn unscheduled and the training scorer fills the gap.

The solver tries an exact MILP first and falls back to a heuristic beam
search on any MILP failure (including a solve-time-limit timeout). The
exact solver always keeps the highest-scored races; the beam can drop
them. Running the exact solver many times per career on a slower machine
can intermittently time out into the beam — which fits the observed
inconsistency.

### What's new

  * **Re-solve diagnostics.** Every turn-by-turn re-solve now records which
    backend ran, whether it fell back from the exact solver to the beam
    (and why), the resulting race count, current stamina, and any
    high-value races (15,000+ fans) it dropped relative to the plan
    already held. These accumulate in a new `replan_log` saved in the
    career log, so the cause of any future skipped race is visible at a
    glance instead of inferred.

  * **Beam-fallback guard.** A degraded beam re-solve is no longer allowed
    to overwrite a good exact plan. When the exact backend fails on a given
    turn but the plan already held was exact, the prior exact plan's
    upcoming races are kept rather than churning to the beam result. This
    directly prevents the beam from silently dropping a winnable Japan Cup
    or Arima. The guard is skipped only when a planned race genuinely
    vanished that turn (so a fresh plan is required) and when there is no
    prior exact plan to fall back on (the first solve still uses the beam
    if that is all that is available).

### Notes

If a future career still skips a big race, the `replan_log` will now show
exactly why (which backend, what was dropped, at what stamina), turning
the remaining diagnosis into a single look rather than guesswork. The
immediate workaround of locking the key G1s via Manual selection still
applies and guarantees they run regardless of the re-solve.

## Pre Icarus v6.7.19

Adds an in-app Help & Documentation page so the bot is approachable to
new users without external notes.

### What's new

A HELP button now sits in the top action row, between SETUP
and ACCOUNTS, styled to match the existing buttons (it carries a blend
of the pink and cyan accents that flank it). Clicking it opens a
full documentation modal built in the same neon panel language as the
SETUP and ACCOUNTS modals.

The modal is a proper docs page, not a wall of text:

  * **Sidebar navigation** grouped into Getting Started, Core Features,
    Intelligence, and Strategy, with the current section highlighted as
    you scroll (scroll-spy).
  * **Search box** that filters sections live as you type, with an
    empty-state message when nothing matches.
  * **Readable content column** with section eyebrows, callouts (tips,
    warnings, key points), comparison tables, and numbered how-to
    steps.

### Topics covered

Overview and how a career run flows; a five-step quick start; Setup and
the support deck; Accounts and login (including userdata persistence);
the Smart Race Solver (data source, how it chooses, Max Streak and the
other settings, the race-vs-stat tradeoff, **Smart vs. Manual
selection**); Training (priority, blacklist, targets, event/summer
priorities, failure tolerance); Character profiles and scorer modes;
**Run controls & toggles** (Start/Stop/Pause, turn delay and Tempt Fate,
Burn Clocks, Loop, Rescue, Discord notifications, Scenario Overrides and
Event Choices); AI Learning (outcome risk, LPA, shadow precision, when
to reset); Items and skills; Career history and the Decision Reasoning
panel; Diagnostics; Strategy and tips (parent sparks, the race-vs-stat
tradeoff, realistic race targets); and a Troubleshooting / FAQ.

### Implementation notes

  * The Help module is self-contained and renders its content on first
    open; it does its own element lookups and uses the same idempotent
    bound-guard event wiring as the other modals.
  * Close via the DONE button, clicking the backdrop, or the Escape key.
  * Fully responsive: on narrow screens the sidebar stacks above the
    content. Reduced-motion preferences are respected.
  * A standalone preview of the modal (assembled from the exact shipped
    CSS, JS, and markup) is available for review outside the app.

### Files touched

  * ``public/index.html``: HELP button between SETUP and ACCOUNTS; the
    Help modal shell; cache-busters bumped (``app.js?v=545``,
    ``styles.css?v=537``).
  * ``public/styles.css``: the full Help modal stylesheet (launch
    button, overlay/panel/topbar, sidebar nav, content, callouts,
    tables, keyword chips, step lists, responsive + reduced-motion).
  * ``public/app.js``: the self-contained Help documentation module
    (content, render, search, scroll-spy, open/close wiring).
  * ``tests/test_v6719_fixes.py`` (new, 17 tests): button placement
    between setup and accounts, modal markup and render targets, JS
    module wiring and section coverage, CSS classes, active-state,
    responsive/reduced-motion, and a guard against dev-time typos.

Curated regression set: 339/339 tests pass (17 new + 322 baseline).

``main.py`` build_version bumped to ``Pre Icarus v6.7.19``.

## Pre Icarus v6.7.18

Fixes Steam headless-bypass auth not surviving version upgrades -- you
had to re-authenticate (manual Steam launch) after every update, even
though SweepyClaude_userdata was supposed to persist it.

### The bug (two halves)

v6.7.6 added external-userdata persistence so settings survive upgrades.
For Steam auth it persisted ``steam_token.txt`` to userdata -- but that
is NOT the file the auth check actually reads:

  1. ``check_saved_auth()`` reads ``auth_config.json`` (which holds
     steam_id, session ticket, and obfuscated credentials), and it read
     it ONLY from ``RUNTIME_DIR`` -- the build folder, which is wiped on
     every version upgrade.
  2. ``auth_config.json`` was never written to userdata. Only
     ``steam_token.txt`` was, and nothing reads that on startup.

So after upgrading to a new build folder: the folder is empty ->
``check_saved_auth()`` finds no ``auth_config.json`` -> headless bypass
fails -> falls back to a manual Steam launch. The userdata copy couldn't
help because the file the check needs was never saved there.

### The fix

  * The full ``auth_config.json`` is now written to BOTH the runtime
    build folder and userdata (new ``_save_auth_config_both`` helper),
    at every point auth is saved -- initial login and ticket refresh.
  * ``check_saved_auth()`` now reads userdata FIRST
    (``SweepyClaude_userdata/auth/<profile>/auth_config.json``), falls
    back to ``RUNTIME_DIR``, and when it falls back it MIGRATES the
    runtime copy into userdata so the next upgrade is covered.

After this fix, your Steam auth persists across upgrades: authenticate
once and the headless bypass keeps working on every future version.

### For your current situation

Because the file was never in userdata before, the very first launch on
v6.7.18 will still need a normal authentication (there's nothing in
userdata to migrate yet). After that one time, it's saved to userdata
and every subsequent upgrade will reuse it. If your current build folder
still has a working ``auth_config.json``, launching v6.7.18 will migrate
it into userdata automatically -- so you may not need to re-auth at all.

### Note on credential safety

This change only moves the SAME already-obfuscated ``auth_config.json``
that was already being written to the build folder. It does not change
what is stored or how it's protected; it just also stores it in the
userdata location so it isn't lost on upgrade. Pre Icarus continues to
never store credentials in plain text.

### Files touched

  * ``main.py``:
    - new ``_user_auth_config_path`` and ``_save_auth_config_both``
      helpers
    - initial-login save now writes auth_config to both locations
    - ``check_saved_auth`` reads userdata-first, falls back to runtime,
      and migrates runtime -> userdata
    - ticket-refresh re-save writes to both locations
  * ``tests/test_v6718_fixes.py`` (new, 6 tests): save-to-both,
    upgrade-reads-from-userdata (the reported bug), userdata-preferred,
    runtime-fallback-with-migration, none-anywhere, per-profile
    isolation. (Mirrors main.py path logic since main.py can't be
    imported in the test sandbox.)

Curated regression set: 322/322 tests pass (6 new + 316 baseline).

``main.py`` build_version bumped to ``Pre Icarus v6.7.18``.

## Pre Icarus v6.7.17

Fixes a confusing display mismatch: the Decision Reasoning panel showed
a different stat priority order than the Training Settings panel.

### The discrepancy

A user reordered their training priorities in the Training Settings
panel (moving Stamina above Wit), but the Decision Reasoning log kept
showing the old order ("speed > power > wit > stamina > guts"). It
looked like the change hadn't taken effect.

### What was actually happening

There are TWO separate stat-priority lists, read by two different
pieces of code:

  * ``preset.training_stat_priority`` -- set by the Training Settings
    panel. The actual training STRATEGY reads this (``mant.py``
    ``_priority_indices``) to make decisions.
  * ``profile.training_scorer_overrides.stat_priority`` -- the
    character profile's separate scorer priority. The Decision
    Reasoning DISPLAY was reading this.

So the bot WAS training with the user's new panel order (Stamina #3) --
that part worked correctly. But the reasoning text displayed the
character profile's order (Wit #3), which the user hadn't changed. The
behavior was right; only the displayed explanation was wrong.

**Answer to "which one is active": the Training Settings panel.** That
is what the bot uses for training decisions in hint and disabled scorer
modes (which is the default). The profile's separate priority only
drives decisions in authoritative scorer mode.

### The fix

The Decision Reasoning panel now displays the priority that ACTUALLY
drove each decision:

  * **hint / disabled mode** (strategy decides) -> shows
    ``preset.training_stat_priority`` (the Training Settings panel)
  * **authoritative mode** (scorer overrides the strategy) -> shows the
    profile's ``stat_priority``

The preset priority is captured into run status at career start so the
reasoning can reach it. Older logs without it fall back to the profile
priority so the line still renders.

After this fix, the priority shown in Decision Reasoning will match
what you set in Training Settings (in the default hint mode), so there's
no more apparent contradiction.

### Note on the "target" numbers

The reasoning also shows a target value (e.g. "253/1150 target"). That
number comes from the character profile's ``stat_targets`` and may
differ from the per-distance default the strategy actually trains
toward (v6.7.15 derives the training-target distance from the scheduled
races). That display is not changed in this release; if it causes
confusion, it can be aligned in a follow-up. The priority-order
mismatch -- the one flagged -- is fixed here.

### Files touched

  * ``career_bot/runner.py``:
    - ``_run`` captures ``preset.training_stat_priority`` into status at
      career start
    - ``_decision_reasoning`` selects the priority to display based on
      scorer mode (preset priority in hint/disabled, profile priority
      in authoritative)
  * ``tests/test_v6717_fixes.py`` (new, 5 tests):
    - hint mode shows preset priority, authoritative shows profile
      priority, disabled shows preset, fallback to profile when preset
      priority absent, preset priority used with no profile

Curated regression set: 316/316 tests pass (5 new + 311 baseline).

``main.py`` build_version bumped to ``Pre Icarus v6.7.17``.

## Pre Icarus v6.7.16

**This is the real root cause of the persistent low race count.** Every
fix since v6.7.11 was correct but incomplete -- they patched the
initial race plan while a second code path silently undid the most
important setting after the first race of every career.

### The bug that was hiding behind all the others

v6.7.11 found that the Smart Race Solver Settings UI panel writes to
``preset.trackblazer_solver_settings`` while the runner read from
``preset.mant_config`` -- so Max Streak was stuck at 2. v6.7.11 fixed
that in ``runner.py`` (the INITIAL plan), which is why the manual
"Solve Smart" preview correctly showed ~37-42 races.

But there are TWO solver call sites, and v6.7.11 only fixed one:

  * ``runner.py`` -- builds the INITIAL race plan at career start.
    Fixed in v6.7.11. Reads Max Streak 5 -> plans 37 races.
  * ``races.py`` -- ``_replan_smart_schedule``, the RUNTIME RE-SOLVE
    that fires after EVERY race to update the remaining schedule.
    **Never fixed.** Still read ``cfg.get("max_races_in_row") or 2``
    from the (empty) mant_config -> defaulted Max Streak back to 2.

So every career played out like this:

  1. Career starts: initial plan built at Max Streak 5 -> 37 races
  2. Bot runs the first race
  3. Re-solve fires -> reads Max Streak 2 (the bug) -> remaining plan
     shrinks to ~2-streak behavior
  4. Every subsequent race re-solves and keeps the streak capped at 2
  5. Career finishes at ~28 races regardless of the UI setting

This is exactly why the user reported "it hasn't changed much" across
v6.7.11-v6.7.15 -- the initial plan looked right (and the manual
preview showed 42), but the moment racing started, the re-solve quietly
reverted Max Streak to 2. Diagnosed by running the solver directly:
Max Streak 5 yields 37 races, Max Streak 2 yields 32, and the user's
careers landed at ~28 -- consistent with the re-solve running at
streak 2 the whole time.

The same line also mis-read ``include_op`` (-> False) and
``min_aptitude_floor`` (-> 6/B instead of the user's C/5), so the
re-solve was also slightly stricter on race eligibility than intended.

### The fix

``RacePlanner`` gains the same ``_solver_setting`` and
``_solver_aptitude_floor`` precedence helpers the runner got in
v6.7.11 (mant_config -> trackblazer_solver_settings -> default), and
the re-solve's three settings now use them:

```python
max_races_in_row=int(self._solver_setting(preset, "max_races_in_row", 2)),
include_op=bool(self._solver_setting(preset, "include_op", False)),
floor=self._solver_aptitude_floor(preset, 6),
```

Now the initial plan and the re-solve resolve solver settings
IDENTICALLY, so the plan no longer shrinks after the first race. With
Max Streak 5, the bot should now actually run ~37 races instead of
collapsing to ~28.

### Reaching the benchmark of 41 races

With the re-solve fixed, the solver math (verified directly against the
race calendar for this trainee's aptitudes) is:

  * Max Streak 5 -> 37 races
  * Max Streak 8 -> 41 races (matches the reference bot)
  * Max Streak 5 + Include OP races -> 40 races
  * Max Streak 10 + Include OP -> 44 races

**Recommendation: set Max Streak to 8** in Smart Race Solver Settings
to match the 41-race benchmark. (The benchmark effectively
races in longer streaks than the old default-2 cap allowed.) Now that
the re-solve honors the setting, this will actually take effect for the
whole career instead of only the first race.

### On the fan gap (354k vs 800k)

The fan difference is partly the race count (28 vs 41) and partly race
GRADE. This trainee has 34 Mile/Medium G1 races available (Japan Cup
alone is 30,000 fans, recurring in Classic and Senior years), but the
careers were running only ~5 G1s. With more races scheduled (streak 8)
and the re-solve no longer pruning the plan, more of the high-fan G1s
will be picked up. The solver already prioritizes by fan/epithet value;
it simply wasn't getting to schedule enough races. Fan total should
rise substantially once race count climbs toward 41.

### Files touched

  * ``career_bot/races.py``:
    - New ``_solver_setting`` and ``_solver_aptitude_floor`` helpers on
      ``RacePlanner`` (+ ``_APTITUDE_LETTER_TO_INT``)
    - ``_replan_smart_schedule`` re-solve now uses them for
      max_races_in_row, include_op, and min_aptitude_floor
  * ``tests/test_v6716_fixes.py`` (new, 10 tests):
    - 8 re-solve setting tests (UI honored, default only when unset,
      mant override wins, include_op, aptitude-floor letter, garbage
      fallback, zero/false valid, None-preset safe)
    - 2 parity tests confirming the re-solve and the runner now resolve
      settings identically

Curated regression set: 311/311 tests pass (10 new + 301 baseline).

``main.py`` build_version bumped to ``Pre Icarus v6.7.16``.

## Pre Icarus v6.7.15

Corrects an over-correction in v6.7.14. The training-target distance is
now derived from the races the solver ACTUALLY SCHEDULES, not from the
trainee's aptitude. This was a good catch: v6.7.14's aptitude tie-break
was building stamina for a distance the trainee never raced.

### The problem with v6.7.14's aptitude tie-break

v6.7.14 resolved a tied-aptitude trainee's training target by picking
the longest distance it had aptitude for. But aptitude is NOT the same
as what the solver schedules. Concretely, for the user's Oguri Cap:

  * Aptitudes (post-parent-spark): Mile A, Medium A, **Long A** (tied)
  * What the solver actually scheduled: **14 Mile + 12 Medium, ZERO
    Long** (longest race 2400m = top of Medium)

v6.7.14's tie-break picked **Long** (stamina target ~1000) because Long
aptitude was A. But the trainee never ran a Long race. Building toward
1000 stamina wastes training turns on stamina it doesn't need, starving
Speed/Power -- the opposite of helpful.

### The fix: follow the schedule, not the aptitude

New ``_scheduled_distance_target(preset)`` reads the solver's scheduled
race list (``preset.extra_race_list``), buckets each race by distance
via the race planner's ``_distance_bucket``, and picks the **longest
distance bucket with meaningful representation** -- at least 20% of
scheduled races, or at least 3 races.

  * 14 Mile + 12 Medium -> **Medium** (stamina ~800, enough for the
    2400m races), NOT Long
  * 8 Medium + 6 Long -> **Long** (the Long block is substantial)
  * 20 Mile + 1 Long -> **Mile** (one outlier Long doesn't drag the
    build)

The Medium target (800) is the right answer for the user's trainee:
high enough to win the 2400m races it was losing (it finished at 441),
but not so high it wastes turns on stamina for Long races that don't
exist.

### Resolution priority for the training-target distance

  1. Explicit ``preferred_distance`` in mant_config (user override)
  2. **Scheduled race list** (v6.7.15) -- the authoritative signal
  3. Aptitude tie-break (v6.7.14) -- fallback when no schedule exists
     (manual mode, or before the first solve)

Explicit ``stat_targets_by_distance`` entries still win over the
defaults for whichever distance is resolved.

### Why aptitude is only a fallback now

Aptitude tells you what a trainee CAN race well, not what it WILL race.
The solver picks races for fan value, epithet progress, and race
density -- which often means a Mile/Medium schedule even for a trainee
with high Long aptitude. The schedule is the ground truth for "what
stats does this trainee actually need", so it takes precedence. The
aptitude tie-break is retained only for the brief window before the
first solve, or for manual race-selection mode where no solver schedule
exists.

### Files touched

  * ``career_bot/scenarios/mant.py``:
    - New ``_scheduled_distance_target`` helper
    - ``_training_targets`` "auto" branch now tries the schedule first,
      falling back to the aptitude tie-break only when no schedule is
      available
  * ``tests/test_v6715_fixes.py`` (new, 10 tests):
    - 7 ``_scheduled_distance_target`` tests (Mile/Medium -> middle, no
      schedule -> None, no planner -> None, substantial long block ->
      long, single outlier doesn't drag, 3-race floor, sprint alias)
    - 3 end-to-end ``_training_targets`` tests (schedule overrides
      aptitude, no-schedule falls back to aptitude, explicit target
      still wins)

Curated regression set: 301/301 tests pass (10 new + 291 baseline).

``main.py`` build_version bumped to ``Pre Icarus v6.7.15``.

## Pre Icarus v6.7.14

Three stat-build and finale-handling fixes found by analyzing a
completed v6.7.12 career. The career finished cleanly (the v6.7.12
crash fix held), but the trainee finished with only 441 Stamina and
lost the longest races (Japanese Oaks 2400m rank 2, finale rank 9).
Root cause: a distance tie-break quirk was giving all-rounder trainees
a Mile-tier stamina target even though they race Medium/Long.

### 1. Distance aptitude tie-break now favors the LONGER distance

**The bug.** When a trainee's distance aptitudes tie -- e.g. Oguri Cap
with Mile = Middle = Long all at aptitude 7 -- the code picked the
"preferred" distance with Python's ``max()``, which returns the FIRST
key on a tie. The aptitude dict was ordered short -> mile -> middle ->
long, so a tie resolved to **mile**, giving a Mile-tier stamina target
(~600). But the Trackblazer senior calendar is full of Medium
(1800-2400m) and the trainee also runs 2400m races, which need
800-1000 stamina. The trainee was trained to the wrong target and
under-built stamina for the races it actually ran.

**The fix.** Ties now resolve to the LONGER distance (order long ->
middle -> mile -> short). A tied Mile/Middle/Long trainee now gets the
Long stamina target (~1000) instead of Mile (~600). Erring toward the
longer distance is the safe direction: extra stamina never loses a
shorter race, but missing stamina loses a longer one. Trainees with a
clear single best distance are unaffected -- the tie-break only
changes behavior on actual ties. Users who set ``preferred_distance``
explicitly override the tie-break entirely.

### 2. No-targets fallback uses aptitude defaults instead of the 9999 sentinel

**The bug.** When a trainee had NO explicit ``stat_targets_by_distance``
AND ``preferred_distance`` was unset/auto, the code returned the
``[9999, 9999, ...]`` sentinel immediately -- which means "no stamina
target, train everything equally" and builds Speed-heavy, starving
Stamina. This was an even earlier exit than the v6.7.12 fix addressed.

**The fix.** The early-return now only fires when ``expect_attribute``
carries real (non-9999) values. Otherwise the code falls through to
the aptitude-based per-distance defaults, so every trainee gets a
sensible stamina target for the distance it will race. The
``disable_stat_targets`` escape hatch is unaffected.

### 3. Finale race continue (205) recognized and handled cleanly

**The issue.** Your PowerShell log showed a burst of 205 and 208
errors on ``single_mode_free/continue`` at the end of the run. The
v6.7.12 mandatory-clock-rescue correctly TRIED to use a clock to
rescue the rank-9 finale loss, but the Trackblazer finale races
(Twinkle Star Climax) don't support the standard clock-continue
mechanism -- the server rejects the continue with 205. The bot
retried the doomed call a few times before giving up.

**The fix.** A 205 result on the continue call is now recognized as
"this race does not support clock retries" and stops the retry loop
immediately, logging ``race_continue_unavailable`` instead of burning
the retry budget on calls the server will always reject. The career
still finishes gracefully (the v6.7.12 graceful-finale handling
already ensured no crash); this just makes the bot stop wasting
attempts and keeps the log clean. (208 SERVER BUSY remains transient
and is retried by the client internally.)

### What this means for your careers

The stamina fixes are automatic -- no setting change needed. An
all-rounder like your Oguri Cap will now train toward a Long-distance
stamina target (~1000) instead of the Mile target (~600), so it
should reach the longer races (Japanese Oaks 2400m, the finale) with
enough stamina to actually compete. Combined with v6.7.11's Max
Streak fix and v6.7.12's mandatory clock rescue, this should improve
both race wins and completed-race count.

### Files touched

  * ``career_bot/scenarios/mant.py``:
    - ``_training_targets`` aptitude tie-break reordered to favor
      longer distances
    - No-targets early-return now only fires for real
      ``expect_attribute`` values, else falls through to defaults
  * ``career_bot/runner.py``:
    - Race-continue retry loop recognizes 205 and stops cleanly with
      a ``race_continue_unavailable`` log entry
  * ``tests/test_v6713_stamina.py`` (new, 9 tests):
    - 5 distance tie-break tests (tied -> long, tied mile/middle ->
      middle, clear mile stays mile, clear long -> long, explicit
      preferred overrides)
    - 3 no-targets fallback tests (aptitude defaults used, real
      expect_attribute honored, disable_stat_targets unaffected)
    - 1 205-detection predicate test

Curated regression set: 291/291 tests pass (9 new + 282 baseline).

``main.py`` build_version bumped to ``Pre Icarus v6.7.14``.

## Pre Icarus v6.7.13

Fixes the Character Profile panel showing "default" between runs. This
is the same class of issue as v6.7.9 tried to address, but v6.7.9's fix
was incomplete -- it surfaced the trainee's name but couldn't actually
resolve a profile from a name.

### The "shows default" bug (round 2)

When you opened the Character Profile panel between runs, it showed
"Default / Matched via default / auto-derived from aptitudes" even
though your last career used the Oguri Cap profile (matched via
card_id, hand-curated).

**Why v6.7.9 didn't fully fix it.** v6.7.9 added a fallback that read
the trainee's ``display_name`` from the persisted
``active_character_profile`` status dict. But that dict carries
``display_name`` WITHOUT a ``card_id``, and ``resolve_profile`` had
no name-based match path -- it only matched by card_id, chara_id, or
preset_name. So a name-only resolution fell straight through to
"default". v6.7.9 set the name but the resolver ignored it.

**The complete fix (v6.7.13):**

  1. **``resolve_profile`` gains a ``display_name`` parameter** and a
     name-based match path. Resolution order is now:
       1. card_id
       2. chara_id
       3. preset_name
       4. **display_name** (NEW)
       5. auto-derive from aptitudes
       6. default
  2. **The profile index builds a ``by_name`` map** from each profile
     JSON's ``display_name`` field, so name lookups are O(1) and cover
     every shipped + user profile.
  3. **``CharacterProfile`` gains ``matched_card_id``** -- the card_id
     the profile resolved from. This is now persisted into the
     ``active_character_profile`` status dict, so future resolutions
     have a real card_id to use (the strongest match path) rather than
     relying on name matching. Older logs without it still work via
     the name path from fix #1.

**Result.** The panel now correctly shows your last-used profile
between runs: "Oguri Cap / Matched via name (or card_id) / hint mode /
your stat priorities". When a fresh career starts and live chara_info
loads, it flips back to card_id matching automatically.

### Why this kept happening

The dashboard panel resolves profile independently from the running
bot. During a career the bot has live ``chara_info`` with the card_id,
so it always matched correctly -- your Oguri tuning was ALWAYS applied
at runtime (confirmed across every career log). The panel only
mis-displayed between runs because it had a weaker resolution path.
This was always a display-only bug; runtime behavior was never
affected. But it was confusing, so it's now fixed properly.

### Files touched

  * ``career_bot/character_profiles.py``:
    - ``resolve_profile`` gains ``display_name`` param + name-match path
    - ``_load_index`` builds a ``by_name`` map from profile display_names
    - ``CharacterProfile`` dataclass gains ``matched_card_id`` field
    - ``to_dict`` includes ``matched_card_id``
    - Hand-curated resolution sets ``matched_card_id`` from the
      resolved card_id
  * ``main.py``:
    - ``api_character_profile_active`` passes ``display_name=selected_name``
      into ``resolve_profile`` so the name path can fire
  * ``tests/test_v6713_fixes.py`` (new, 11 tests):
    - 5 name-resolution tests (resolve by name, case-insensitive,
      unknown name falls to default, card_id wins over name, preset
      wins over name)
    - 3 matched_card_id tests (set on card_id resolution, in to_dict,
      zero on name resolution)
    - 3 index by_name tests (map exists, maps Oguri, other keys intact)

Curated regression set: 282/282 tests pass (11 new + 271 baseline).

``main.py`` build_version bumped to ``Pre Icarus v6.7.13``.

## Pre Icarus v6.7.12

The v6.7.11 solver fix worked -- the bot now plans 42 races (up from 36).
This release fixes the crash you hit and the underlying stat-build problem
that was capping completed-race count and causing finale losses.

### 1. Crash fix: mandatory race loss no longer kills the runner

**The crash.** Your PowerShell log showed:

  > RuntimeError: Mandatory race failed at turn 78, rank 6

Turn 78 is the final race of the Trackblazer finale (Twinkle Star
Climax). The trainee finished 6th, and because
``complete_career_on_failure: false``, the bot raised a fatal
exception that crashed the runner and abandoned the entire career --
throwing away all the fans and stats earned across 78 turns.

**The fix.** Mandatory race failures are now handled gracefully:

  * **Finale races (turn >= 73)**: the career is already over, so the
    bot logs the loss, records it in status, and completes the career
    normally. The report is written with whatever was earned. No crash.
  * **Non-finale mandatory races (turn < 73)** with
    ``complete_career_on_failure: false``: the career stops cleanly via
    a ``career_stopped_reason`` status flag instead of an exception.
    The runner loop detects it, ends gracefully, and writes the report.
    No stack trace.

### 2. Mandatory races can spend paid clocks to avoid the loss

**The deeper issue.** At turn 78 you had **5 paid clocks available**
but ``burn_clocks: false``, so the retry loop never fired -- the bot
took the rank-6 loss without trying to rescue it. A finale loss is
catastrophic (ends the career), so spending a clock there is almost
always worth it.

**The fix.** ``_race_retry_policy`` gains an ``is_mandatory`` flag.
Mandatory races (forced races) may now use paid clocks even when the
Burn Clocks toggle is off for optional races. Mandatory races also
bypass the grade filter (a forced race must be retried regardless of
its grade). Opt out with ``disable_mandatory_race_clocks: true`` in
mant_config if you genuinely never want paid clocks spent.

This means: with your current ``burn_clocks: false`` setting, the bot
will still try to rescue a mandatory race loss using available clocks,
but won't burn clocks on optional races. Best of both worlds.

### 3. Stamina-target fix: the actual cause of finale losses AND low race count

**The root cause.** Your trainee finished with **Stamina 425** -- but
its race schedule was heavily Medium distance: Japanese Oaks (2400m),
Kobe Shimbun Hai (2400m), Kyoto Shimbun Hai (2200m), American JCC
(2200m), plus a dozen 2000m races. Medium distance (1800-2400m) needs
600-800 stamina; Long needs 900-1100. The trainee was racing at
Mile-tier stamina (425) for its entire Medium/Long schedule.

Why? Your preset's ``stat_targets_by_distance`` only specifies
``mile`` targets. The strategy code resolved the trainee's best
distance as **Middle**, looked for a Middle target, found none, and
fell through to the ``expect_attribute`` sentinel ([9999, 9999, ...])
-- which means "train everything equally" and builds Speed-heavy,
starving Stamina.

There WAS a sensible built-in defaults table (Middle: 800 stamina,
Long: 1000 stamina) but it was listed AFTER the 9999 sentinel in the
fallback chain, so it never got used.

**The fix.** ``_training_targets`` now falls back to the built-in
per-distance defaults BEFORE the 9999 sentinel:

  * Preset specifies the trainee's distance -> use the explicit target
  * Preset doesn't cover it -> use the built-in default for that
    distance (Sprint 450 / Mile 600 / Middle 800 / Long 1000 stamina)
  * Only if both are missing -> 9999 sentinel

**Impact**: Medium/Long trainees will now build appropriate stamina.
This directly addresses both symptoms:

  * **Finale losses**: the trainee will reach the finale with enough
    stamina to actually compete in Medium/Long finale races
  * **Race count**: a trainee that can win its races (rather than
    scraping by or losing) lets the solver schedule and complete more
    races -- under-staminaed trainees were losing races that then
    couldn't be retried

### Recommended action

The stamina fix is automatic -- no setting change needed. But for the
best results, you can also add Medium/Long targets to your Oguri preset
explicitly. The shipped Oguri **profile** already has them; if you want
your saved **preset** to carry them too, set in mant_config:

```json
"stat_targets_by_distance": {
    "mile":   [1200, 700, 1100, 400, 1000],
    "medium": [1150, 850, 1050, 400, 1000],
    "long":   [1050, 1100, 1000, 400, 1000]
}
```

(Stamina is the 2nd value. Medium 850, Long 1100 for a stayer build.)

With the stamina fix + Max Streak 5 (v6.7.11) + mandatory clock rescue,
expect: more races completed, finale wins instead of crashes, race
count closer to the high-30s/40.

### Files touched

  * ``career_bot/runner.py``:
    - ``_race_retry_policy`` gains ``is_mandatory`` kwarg; mandatory
      races get paid-clock rescue + grade-filter bypass
    - ``_race_retry_allowed`` threads the kwarg
    - ``_race`` captures ``is_mandatory_race`` from the payload and
      threads it through all retry-policy calls
    - Mandatory-race-failure handling: finale completes gracefully,
      non-finale sets ``career_stopped_reason`` instead of raising
    - Main run loop checks ``career_stopped_reason`` after a race step
      and ends cleanly
  * ``career_bot/scenarios/mant.py``:
    - ``_training_targets`` fallback order fixed: built-in per-distance
      defaults now beat the 9999 sentinel
  * ``tests/test_v6712_fixes.py`` (new, 10 tests):
    - 5 mandatory-clock-rescue tests (rescue with burn off, optional
      still blocked, opt-out, grade bypass, max-retries respected)
    - 5 stat-target fallback tests (Middle uses default, Long uses
      default, explicit wins, senior not scaled, junior scaled)

Curated regression set: 271/271 tests pass (10 new + 261 baseline).

``main.py`` build_version bumped to ``Pre Icarus v6.7.12``.

## Pre Icarus v6.7.11

**This release fixes the actual root cause of the persistent low-race-count
issue.** Every Smart Race Solver Settings UI knob has been silently doing
NOTHING since the panel was added. After upgrading, raise Max Streak in
that panel to 5 and you should see race count climb noticeably.

### The race-count bug

The user reported across multiple releases that race count was stuck
around 27-31, far below the benchmark's 41. Previous releases
chased symptoms (chain-break behavior, hijack thresholds, irregular
training rules, profile resolution, raceCostPct tuning) without
finding the actual cause.

The actual cause: **Smart Race Solver Settings UI knobs write to
``preset.trackblazer_solver_settings`` but the runner only read from
``preset.mant_config``.** Two different sub-dicts that never overlap.
Every UI knob in the panel was a no-op:

  * **Max Streak** -- UI value 2 / runner default 2 -- by coincidence
    the user's UI value matched the default, but this was THE
    constraint capping race streaks at 2. Raising the slider had zero
    effect because the runner ignored it.
  * **Fan Bonus** -- UI value 0 / runner default 0 -- coincidental
    match, but raising it does nothing
  * **Include OP Races** -- UI False / runner default False
  * **Min Aptitude Floor** -- UI "C" (letter) / runner default 6
    (integer), and the runner would have crashed if it had ever
    tried to read the letter form
  * **Distance Preference Mode** -- UI "balanced" / runner default
    "balanced"

Verified by inspecting the user's actual smart_solver_config.json and
settings_presets.json side-by-side: every UI knob was in the
trackblazer_solver_settings dict, NONE were in mant_config.

### The fix

Two new helpers on ``CareerRunner``:

  * ``_solver_setting(preset, key, default)`` -- returns the first
    non-None value from:
      1. ``preset.mant_config[key]`` (explicit per-preset override)
      2. ``preset.trackblazer_solver_settings[key]`` (UI panel knob)
      3. the supplied default
    Empty strings count as unset; numeric zero and boolean False
    are valid (don't collapse to default).
  * ``_solver_aptitude_floor(preset, default_int)`` -- handles both
    the letter form (S/A/B/C/D/E/F/G -> 8/7/6/5/4/3/2/1) and the
    int form. Invalid values fall back to default instead of
    crashing.

Five sites in ``runner.py`` updated to call these helpers:
``fan_bonus``, ``max_races_in_row``, ``include_op``,
``min_aptitude_floor`` (via the aptitude helper), and
``distance_preference_mode``.

**Backward compatibility**: presets that explicitly set a value in
mant_config still win (precedence stage 1). The fix only changes
behavior for presets without an explicit override -- which is the
default case for every shipped preset and almost every user-saved
preset.

### What this means for you in practice

After upgrading, your Smart Race Solver Settings panel now actually
controls runtime planning. To climb past your current race count:

  1. Open **Smart Race Solver Settings** in the dashboard.
  2. Set **Max Streak** to **5** (matches the benchmark).
  3. Optionally drop **Race Cost %** to **75** for more races per
     career value.
  4. Save the preset, start a new career.

Expected impact: race count should jump from 27-31 to the
high-30s/low-40s range, much closer to the benchmark. The actual ceiling
depends on the trainee's aptitudes and the rest of the solver
weights -- but the bottleneck (Max Streak silently capped at 2)
is gone.

### Documentation overhaul

Per user request, ``docs/`` has been reorganized:

  * **New top-level guides** consolidating overlapping single-feature
    notes:
    - ``docs/trackblazer-guide.md`` -- everything race-related: how
      the smart race solver decides, the four knobs that drive race
      count, the chain-break safety layer, irregular training
      hijacks, items, profiles. The "Quick start" section at the
      top is the single-screen answer to "how do I get more races".
    - ``docs/ai-learning.md`` -- LPA vs Training Scorer Mode, the
      shadow precision gate, when to enable LPA, the dataset, style
      adaptation.
    - ``docs/settings-and-presets.md`` -- the three-tier storage
      model, the userdata folder convention, the v6.7.11 fix
      explained, where every config file lives.
  * **README.md** rewritten as a navigable index pointing to the
    consolidated guides with quick-links for the three most-asked
    questions.
  * **archive/** subfolder created. Pure-internal dev notes moved:
    - ``code-analysis-v5.3.md``, ``v5.4.md``, ``v5.7.md``
    - ``v524-reverted-ui-selective-keep.md``
    - ``settings-windows-and-ui-refactor.md``
    - ``api-error-recovery.md``
  * Single-feature notes that are still valid kept in place;
    README sections call them out for users who want depth.

Net: 56 root-level docs -> 53 (3 new guides + 6 moved to archive +
3 historical docs that didn't fit categories were left in place but
linked from README under "Other topics").

### Files touched

  * ``career_bot/runner.py``:
    - New ``_solver_setting`` helper
    - New ``_solver_aptitude_floor`` helper
    - ``_APTITUDE_LETTER_TO_INT`` constant
    - Five sites in ``make_schedule`` call updated to use the helpers
  * ``tests/test_v6711_fixes.py`` (new, 16 tests):
    - 7 precedence tests for ``_solver_setting`` (mant wins over UI,
      UI used when mant missing, default when both missing, safe on
      None preset, empty string treated as unset, zero is valid,
      False is valid)
    - 7 aptitude-floor tests (S/C/G letter, integer pass-through,
      integer-string pass-through, invalid fallback, missing fallback)
    - 2 user-scenario reproduction tests: user's actual state with
      Max Streak=2 resolves correctly; raising to 5 takes effect
  * ``docs/`` -- consolidation pass:
    - ``README.md`` rewritten
    - ``trackblazer-guide.md`` new
    - ``ai-learning.md`` new
    - ``settings-and-presets.md`` new
    - ``archive/`` subfolder with 6 moved files

Curated regression set: 261/261 tests pass (16 new + 245 baseline).

``main.py`` build_version bumped to ``Pre Icarus v6.7.11``.

## Pre Icarus v6.7.10

Four user-requested changes addressing dashboard UX clarity and a
real retry-policy bug.  Oguri profile recommendation: stays in
``hint`` mode (the shipped default) -- previous override to
``authoritative`` was causing the scorer to consistently swap your
higher-priority stats (Speed/Power) to lower-priority ones
(Wit/Guts), since the v6.1 scorer's value function isn't priority-
driven.

### 1. Free continue retries are now ALWAYS usable, even with Burn Clocks OFF

**The bug.**  The pre-v6.7.10 retry policy gated the ENTIRE retry
loop behind ``burn_clocks=True``.  With the toggle off, free continues
that the game gave the user (e.g. the first free retry per race) were
silently wasted -- the loop never even started.  Result: lost wins
that would have been free.

**The fix.**  ``_race_retry_policy`` now takes ``free_clocks_available``
and returns a 3-state result:

  * **paid + free** -- ``burn_clocks=True`` (both kinds usable)
  * **free-only** -- ``burn_clocks=False`` AND ``free_clocks_available>0``;
    ``policy["free_only"] == True``, ``disabled_reason`` is
    ``"burn_clocks_disabled_by_user_paid_only"`` (preserved for AI
    dataset labeling so learned policy can distinguish the regimes)
  * **disabled** -- everything else (max retries hit, grade not
    allowed, preset disable, or no clocks of any kind)

The retry loop in ``_race`` was updated to pass the current free-clock
count into the policy each iteration and to break out the moment
free clocks run out in ``free_only`` mode -- paid clocks must never
be spent when the toggle is off.

For users who set ``burn_clocks=True``, behavior is identical to
pre-v6.7.10 (paid clocks fire after free clocks are exhausted, same
as before).  Users with ``burn_clocks=False`` now get the free retry
they were missing.

### 2. "v6.1 scorer agrees" suppressed when an authoritative override just fired

**The bug.**  A user reported screenshots showing reasoning text like:

  > "Trained Wit -- #3 priority, ..., v6.1 scorer agrees (score 17.66),
  > v6.3 authoritative override swapped strategy's pick (power) -> wit
  > (margin 10.19)"

The two clauses read as a contradiction.  In fact they were both
true -- "scorer agrees" referred to the POST-override action matching
the scorer's pick, which is tautological since the override mutated
the action to be the scorer's pick.  But the user read it as "scorer
and strategy agreed, no swap needed... so why does it say a swap
happened?"

**The fix.**  ``_decision_reasoning`` now detects when an authoritative
override fired this turn and suppresses the redundant "scorer agrees"
line.  The scorer's score is appended to the override line so no
information is lost:

  > "Trained Wit -- #3 priority, ...,
  > v6.3 authoritative override swapped strategy's pick (power) -> wit
  > (margin 10.19, scorer score 17.66)"

In hint mode (where no override fires) and on natural-agreement
turns, the "scorer agrees" line is unchanged.

### 3. Items used this turn are surfaced in Decision Reasoning

Per user request, the dashboard's reasoning panel now includes a
dedicated "Items used this turn" line whenever the item manager
attempted to use one or more items.  Each item is followed by a
category-based "why" tag:

  > "Items used this turn: Charm (training failure protection),
  > Energy Drink (HP recovery), Cupcake (mood boost)"

Failed / skipped attempts are also surfaced so visibility is
complete:

  > "Items used this turn (skipped: no_targets): ..."

Stale item state from a prior turn is NOT attributed to the current
turn (the manager's ``use_attempt_events`` timestamp is checked).

Category mapping covers all currently-shipped consumables: Good Luck
Charm, Energy Drink / Drink Max, Vita Juice / Royal Vita Juice /
Royal Kale Juice, Cupcake / Sweet Cupcake, Megaphone / Reflective
Megaphone, Reset Whistle, Master Hammer / Artisan Hammer / Glow
Stick, Healthy Manju / Pure Manju / Aroma Bath, Wristlet Anklet.
Reasons are keyed by canonical item_id (items.py ITEM_NAMES), not
display strings; unknown items fall back to an id-category descriptor
("training item"/"race item"/"consumable") so the old "selected by
item manager" artifact never appears and adding new consumables won't
crash the path.

### 4. Oguri profile recommendation: stay in `hint` mode

Following analysis of the user's screenshots, the v6.1 scorer's
value function (rainbow bonus, training level, support density,
failure rate) wasn't matching the user's priority-driven goal
(Speed > Power > Wit > Stamina > Guts).  In authoritative mode the
scorer was consistently swapping Speed/Power picks to Wit/Guts.

The shipped Oguri profile remains ``"training_scorer_mode": "hint"``.
Users who had set authoritative via the dashboard UI in a previous
version will be reset back to hint on upgrade (the build's shipped
profile JSON overwrites local changes on extraction; userdata-level
character profile persistence is a planned future enhancement).

Users who genuinely want authoritative behavior with a calmer
override frequency can use the v6.7.9 margin gate config:

```json
"training_scorer_overrides": {
    ...,
    "override_margin_floor": 15.0,
    "override_margin_pct": 0.5
}
```

### Files touched

  - ``career_bot/runner.py``:
    - ``_race_retry_policy`` signature gains ``free_clocks_available``
      kwarg.  Returns ``free_only`` flag.
    - ``_race_retry_allowed`` updated to thread the kwarg.
    - Retry loop in ``_race`` calls the policy with current free-clock
      count and breaks early when ``free_only`` + no free clocks.
    - ``_decision_reasoning`` suppresses "scorer agrees" when the
      override fired this turn; adds scorer score to the override line.
    - New ``_items_used_reason_line`` helper called from the end of
      ``_decision_reasoning``.
    - New ``_ITEM_REASON_BY_NAME`` category mapping.
  - ``tests/test_v6710_fixes.py`` (new, 14 tests):
    - 6 retry-policy tests (free-only, free+paid, max retries, grade
      filter, preset disable, no clocks at all)
    - 3 scorer-agrees suppression tests (suppression on override,
      preservation on agreement, stale-override no-suppression)
    - 5 items-used reasoning tests (single item, multiple items,
      no items, stale prior-turn selection, unknown item fallback)

Curated regression set: 245/245 tests pass (14 new + 231 baseline).

`main.py` build_version bumped to `Pre Icarus v6.7.10`.

## Pre Icarus v6.7.9

Four targeted fixes addressing user-reported issues with the dashboard
and runtime behavior.  No solver-weight changes; race-count tuning is
still a manual exercise (set `raceCostPct` lower in Smart Race Solver
Settings).

### 1. Authoritative scorer override -- margin gate now configurable

**The problem.**  In authoritative mode the v6.1 training scorer's
top pick should swap the strategy engine's choice when they disagree.
But the override included a hardcoded margin gate -- the scorer's
pick had to beat the strategy's by at least `max(1.0, runner_up * 0.10)`
or the override silently suppressed itself.  Users in authoritative
mode saw `"v6.1 scorer would have picked X"` in the reasoning panel
with no swap happening AND no explanation why -- which looked like
the mode wasn't honored.

**Fix.**  The two gate parameters are now read from the profile's
`training_scorer_overrides`:

  * **`override_margin_pct`** -- the multiplier (default `0.10`).
    Lower it to be more aggressive; raise it for less.
  * **`override_margin_floor`** -- the absolute minimum (default `1.0`).
    Set to `0.0` to disable the floor entirely (override fires on any
    non-trivial disagreement).

To make the v6.1 scorer fully authoritative on every disagreement,
set both to `0.0` in the profile JSON or via a per-character override.

### 2. Blocked-override recording + reasoning text

When the margin gate blocks the swap, the override now writes
`last_scorer_override_blocked` to runner status with `from_stat`,
`to_stat`, the actual margin, and the threshold.  The decision-reasoning
panel reads this and emits:

  > v6.1 scorer would have picked guts (score 0.31); authoritative
  > override blocked -- margin 0.01 below threshold 1.0 (tune via
  > training_scorer_overrides.override_margin_pct / _floor)

instead of the bare `"would have picked X"` line.

Hint-mode profiles see the original `"would have picked X"` text since
the override doesn't apply to them.

### 3. Irregular-training hijack now prominent in Decision Reasoning

When the strategy hijacks a planned race for irregular training, the
hijack reason was buried inside the catch-all action description.
Users wanted hijack-vs-normal-training distinguishable at a glance.

`_decision_reasoning` now emits a dedicated leading line for hijacks:

  > Irregular-training hijack: planned race dropped for training --
  > Osaka Hai · G1 · 2000m · Turf score=1.733 main_gain=35 fail=0

The `| v6.3 scorer override` suffix is stripped from this line so it
stays focused on the hijack itself (the override message still
appears below it via the normal scorer-override reasoning).

### 4. Character Profile panel: better resolution between runs

**The problem.**  The `/api/character-profile/active` endpoint resolved
profile in three stages:

  1. Live runner's `chara_info` (only available during turn execution)
  2. `active_selection.trainee` (an in-memory global, lost on restart)
  3. Fallback to "default"

Between runs / before any career started / after a server restart,
stages 1 and 2 were both empty, so the panel showed `"default"`
even when the user's last career was tuned to a specific profile
(e.g. `oguri_cap`).  This caused at least one user to believe their
profile customizations weren't being applied at runtime, when they
in fact were.

**Fix.**  Two changes:

  * **New fallback stage:** before defaulting, read
    `runner_status.active_character_profile` (the persisted record of
    the profile used in the most recent turn / run).  When that's
    populated, use its `display_name` + `card_id` + `scenario_id` to
    re-resolve the profile.
  * **`resolved_from.source` adds a new value `"last_run"`** so the
    dashboard can render a "showing last run's profile" badge.  When
    a fresh career starts and live `chara_info` becomes available,
    the source flips back to `"runner"` automatically.

### 5. `active_selection` persistence to userdata

The Smart Race Solver Settings picker (deck / friend / trainee /
veterans / guestParents) lived only in an in-memory global on the
server.  Restarting the server forgot the picks.

**Fix.**  Every `POST /api/selection` now persists to
`<userdata>/active_selection.json`.  On server startup, the picker
rehydrates from that file.  `POST /api/logout` clears both the
in-memory state and the persisted file so a stale selection from
one user doesn't leak to the next.

Combined with the v6.7.6 userdata folder convention, this means a
trainee picked once survives both server restarts AND version upgrades.

### Files touched

  - `career_bot/runner.py`:
    - `_apply_authoritative_scorer_override` reads `override_margin_pct`
      and `override_margin_floor` from `profile.training_scorer_overrides`
      with defaults of 0.10 / 1.0 (preserves pre-v6.7.9 behavior when
      unset).
    - When the gate blocks the swap, writes a structured record to
      `status["last_scorer_override_blocked"]`.
    - `_decision_reasoning` reads that record + builds the
      blocked-override explanation message.
    - `_decision_reasoning` also surfaces the irregular-training
      hijack as a prominent leading line.
  - `main.py`:
    - `api_character_profile_active` adds the `runner_status.active_character_profile`
      fallback stage between active_selection and the default.
    - New helpers `_user_selection_path`, `_save_active_selection`,
      `_load_active_selection`.
    - Module-level rehydration of `active_selection` from disk on
      startup.
    - `POST /api/selection` and `POST /api/logout` write through to
      disk.
  - `tests/test_v679_fixes.py` (new, 8 tests):
    - Margin gate blocks the swap and records the blocked entry.
    - Lowering `override_margin_floor` to 0 lets the override fire.
    - `active_selection` save/load roundtrip preserves the data.
    - Loading from a fresh userdata folder returns None safely.
    - `_decision_reasoning` builds the prominent hijack line.
    - `_decision_reasoning` explains blocked overrides distinctly
      from hint-mode disagreement.
    - `_decision_reasoning` falls back to the plain `"would have
      picked"` text when no blocked record exists for this turn.
  - `tests/test_scorer_override_placement.py`:
    - `fake_profile` fixture gains `training_scorer_overrides={}` so
      the v6.7.9 attribute access doesn't AttributeError in the
      isolated unit test.

Curated regression set: 231/231 tests pass (8 new + 223 baseline).

`main.py` build_version bumped to `Pre Icarus v6.7.9`.

### Recommended user action for race-count tuning (no code change)

The bot's RUNTIME behavior is now fully tuned to your profile.  The
remaining bottleneck for race count vs the 41-race benchmark is
the solver's `raceCostPct` weight (default 100.0).  To match the benchmark:

  - Open Smart Race Solver Settings
  - Lower `raceCostPct` to ~75 (or even 60 to be aggressive)
  - Save the preset, restart a career

`raceCostPct` is the cost per race the solver charges against each
race's fan/epithet value.  Lower values let the solver plan more
races whose fan value would otherwise not justify the cost.  Other
levers in the same panel: `targetOptionalRaceCount` (default 36),
`lateSeniorRacePressure` (default 12.0).

## Pre Icarus v6.7.8

### Live Policy Assistance recommendation now gates on shadow-mode precision

**The problem.** The "Recommended: ENABLE" green-light banner in the AI
Learning panel checked five data-sufficiency criteria (turn records,
race-result coverage, race rows, learned-adjustment count above
confidence gate, health-safe flag) but never checked whether the
model's predictions were actually correct.  A user observed exactly
the failure mode this enabled: 3108 turn records, 100% race-result
coverage, 80 learned adjustments above the 0.65 confidence gate, yet
shadow-mode precision of just 19% (127 useful warnings against 547
false alarms over 797 evaluated hints).  The dashboard recommended
enabling.  Had the user enabled, ~547 winnable races would have been
suppressed for every ~126 risky races correctly avoided -- a net
loss to race count, the exact opposite of LPA's purpose.

**Root cause.** "Confidence" (the gate at 0.65) measures how certain
the model is, not how correct it is.  A model can be confidently
wrong.  The recommendation logic needed a separate accuracy check.

**Fix.** ``live_policy_recommendation`` in ``career_bot/ai_trainer.py``
now accepts an optional ``shadow=`` keyword argument and applies a
precision gate when shadow has evaluated enough race hints to be
statistically meaningful.  When the gate fires, the recommendation
flips to "KEEP DISABLED" with the precision percentage spelled out:

  Recommended: KEEP DISABLED. Shadow-mode precision is 19% over 797
  evaluated hints; minimum is 60%. Enabling would suppress more good
  races than bad ones.

When data is healthy and precision passes, the ENABLE message
includes the precision number so it's visible at a glance:

  Recommended: ENABLE. Model data looks healthy: 3108 turn records,
  1057/1057 race results, and 80 learned adjustments above the 0.65
  confidence gate. Shadow precision 72%.

**Defaults and configurability.**

  - ``min_shadow_precision`` -- default 0.60 (60%).  Below this the
    model's "this race is risky" warnings are net-negative for race
    count.  Configurable per-deployment via the auto-config JSON.
  - ``min_shadow_evaluations`` -- default 100.  Below this the
    precision number is too noisy to trust as a signal, so the gate
    is silent.  Configurable.
  - The third gate, "low confidence with < 1000 turn records",
    remains unchanged from v6.7.7.

**Backward compatibility.**  ``shadow=`` is an optional kwarg.  Older
callers that don't pass it still work; the precision gate is
silently skipped when no shadow data is available.

**Files touched.**

  - ``career_bot/ai_trainer.py``:
    - ``live_policy_recommendation`` signature gains
      ``shadow: Optional[Mapping[str, Any]] = None``.
    - New precision gate at the bottom of the reasons-building block.
    - ENABLE message now includes shadow precision when known.
    - Return payload includes ``shadow_precision``,
      ``shadow_evaluated_races``, ``min_shadow_precision``,
      ``min_shadow_evaluations`` for dashboard rendering.
    - All three call sites updated to pass ``shadow=``:
      - Live-dashboard caller passes the in-scope ``shadow`` variable.
      - Training-summary caller passes the same.
      - AI-status caller reads ``shadow_mode`` from the latest
        training record.
  - ``tests/test_v678_fixes.py`` (new, 8 tests):
    - User's actual 19%-precision scenario routes to KEEP DISABLED
    - 75% precision routes to ENABLE
    - Below-threshold evaluation counts skip the gate (no false-noise)
    - Missing shadow data preserves old behavior (no gate applied)
    - ``min_shadow_precision`` is configurable
    - ``min_shadow_evaluations`` is configurable
    - Returned payload exposes the precision fields for the UI
    - Backward-compat: callers without ``shadow=`` still work

Curated regression set: 223/223 tests pass (8 new + 215 baseline).

`main.py` build_version bumped to `Pre Icarus v6.7.8`.

### What this changes for you in practice

Your dashboard will now show:

  Recommended: KEEP DISABLED. Shadow-mode precision is 19% over 797
  evaluated hints; minimum is 60%.

Instead of the misleading ENABLE banner.  No other behavior changes;
LPA itself is unaffected since you have it off.  When you eventually
collect enough diverse career data to push precision above 60%, the
dashboard will correctly flip to ENABLE on its own.

## Pre Icarus v6.7.7

Single targeted revert per user request, plus documentation.

### Reverted: v6.7.3 race-chain HP safety layer

The v6.7.3 release added two changes to ``_guide_race_chain_break``:

  1. HP-critical and HP-low gates fired at ``chain_count >= legacy_target``
     (2 races) independent of the user's "Consecutive Races Limit" slider
  2. A hard cap that forced a break at ``chain_count >= target`` even
     with full HP

Per user direction, both are reverted in v6.7.7.  The user already has
the "Ignore Low Energy Racing Block" toggle in Racing Settings and wants
that toggle to be the sole HP authority -- not a separate code-level
gate that overlays it.  The "Consecutive Races Limit" slider is back to
being a soft preference rather than a hard cap.

**New contract** (pre-v6.7.3 behavior restored):

  * **Below chain_count == target**: function returns None regardless of
    HP.  Whether the bot races at low HP is governed entirely by the
    "Ignore Low Energy Racing Block" toggle and the upstream irregular-
    training / scorer paths.
  * **At chain_count >= target with low HP**: HP-low / HP-critical
    gates fire only when "Ignore Low Energy Racing Block" is OFF, same
    as the pre-v6.7.3 implementation.
  * **At chain_count >= target with full HP**: function returns None.
    The chain target is a SOFT preference; the race may proceed if
    other checks allow it.
  * **Escape hatches preserved**: ``ignore_consecutive_race_warning``
    and ``enable_game8_race_chain_break=False`` still bypass the
    function entirely.

The v6.7.4 epithet protection layer (irregular-training hijack guard)
is in a different code path (`_irregular_training_decision`) and is
NOT affected by this revert.  Critical races still bypass the hijack.

**To match benchmark throughput**: set "Ignore Low Energy Racing
Block" ON, "Ignore Consecutive Race Warning" ON, Energy Threshold 0.
Accept HP=0 races as the cost of more races per career.

**To enforce a hard cap on consecutive races**: set "Consecutive Races
Limit" to your desired number AND ensure "Ignore Consecutive Race
Warning" is OFF.  The chain-break function will still fire at the
limit when HP is low; toggle the HP behavior separately.

### Files touched

  - **`career_bot/scenarios/mant.py`** -- ``_guide_race_chain_break``
    restored to the pre-v6.7.3 structure.  Same legacy guard at the
    top (`chain_count < legacy_target` returns None), same training
    bypass when a clean training is available, same HP gates gated
    behind ``chain_count >= target`` plus the ``ignore_low_energy_racing_block``
    check.  No hard cap, no unconditional HP critical.
  - **`tests/test_race_chain_safety.py`** -- 4 tests rewritten to
    assert the v6.7.7 contract:
      * `test_user_reported_6_race_streak_at_hp0` -> `test_chain_count_below_target_does_not_fire_with_hp_low`
      * `test_hp_critical_fires_at_legacy_target` -> `test_hp_critical_fires_only_at_user_target`
      * `test_hp_critical_below_legacy_target_does_not_fire` -> `test_no_hp_gate_below_user_target`
      * `test_hard_cap_forces_break_at_target_even_with_full_hp` -> `test_chain_target_is_soft_when_hp_is_fine`
    Tests for escape hatches and Finale carve-out unchanged and still pass.

Curated regression set: 215/215 tests pass.

`main.py` build_version bumped to `Pre Icarus v6.7.7`.



Three user-reported issues fixed plus one documented behavior clarification.

### 1. Career History "Sparks" panel was showing identical factors across runs

Verified against five of the user's career logs: each run had a unique
`trained_chara_id` and a different `factor_info_array` (different earned
sparks per run, as expected -- sparks are RNG per career).  The display
bug was upstream in `_extract_final_chara_payload`: the finish response's
`single_mode_finish_common.trained_chara` is the user's entire saved
collection (208 entries in the user's case), with the just-finished
trainee identified by the response's top-level `trained_chara_id`.  The
old code picked up the first array slot regardless, which is always a
parent or older saved trainee with constant factors -- producing the
identical-sparks-every-run symptom.

**Fix**: `_extract_final_chara_payload` now resolves the matching entry
by id before merging.  Verified against the user's 5 logs:

  - Run 1: factor IDs [201, 3202, 1000802, ...]
  - Run 2: factor IDs [202, 3403, 2003301, ...]
  - Run 3: factor IDs [102, 2201, 1002702, ...]
  - Run 4: factor IDs [101, 1202, 1002103, ...]
  - Run 5: factor IDs [202, 3302, 1000801, ...]

Different per run as expected.

### 2. Auto-pick epithet goals -- default flipped to OFF, toggle added to UI

Per user request: the v6.5-v6.7.5 default of automatically biasing the
smart race solver toward each character's signature epithet (e.g.
Oguri Cap -> "Ideal Idol" -> Mile Championship / Yasuda Kinen / Arima
Kinen) is now OFF.  The solver picks its highest fan-value race plan
without any signature bias, which often produces more total races.

  - **`career_bot/character_profiles.py`** -- dataclass default and
    resolver default both flipped from True to False.  The auto-derived
    profile path also now constructs with `auto_pick_epithets=False`.
  - **`career_bot/character_profiles.py`** -- catalog signature LOOKUP
    is unchanged (the candidate list is still populated for opt-in
    use); only the INJECTION into solver target_epithets requires the
    flag to be on.
  - **`main.py`** -- new endpoint `POST /api/character-profile/auto-pick`
    persists `auto_pick_epithets: true | false` to the profile JSON.
  - **`public/index.html` / `public/app.js`** -- new "Auto-pick
    Signature Epithets" section in the Character Profile tab, with a
    checkbox + Save button next to the Training Scorer Mode dropdown.
    Per-profile state is loaded from the API.  Explanation copy makes
    the trade-off clear:

      OFF (default): solver picks the best fan/epithet route without
      bias toward any specific signature.

      ON: catalog signatures seed solver target_epithets and are
      protected from the irregular-training hijack (v6.7.4 epithet
      protection still gates on the same field).

### 3. External user-data folder so presets / settings / steam auth persist across upgrades

Per user request: presets and steam auth tokens used to live inside the
Pre Icarus vX.Y.Z folder, which meant version upgrades wiped them.
v6.7.6 adds a sibling-folder convention so a single `SweepyClaude_userdata`
folder next to the build folder owns the persistent state.

**Resolution order** (first match wins):

  1. `$SWEEPYCLAUDE_USERDATA_DIR` env var -- explicit override
  2. `<DIR>/../SweepyClaude_userdata/` -- sibling folder (recommended)
  3. Fallback: in-build `<DIR>/` paths (the pre-v6.7.6 behavior)

**Files routed through userdata when configured**:

  - `data/settings_presets.json` (the "Settings Presets" listed in the
    dashboard's left sidebar)
  - `data/skill_config.json`
  - `data/smart_solver_config.json`
  - `data/presets/*.json` (legacy preset files)
  - `accounts.json`
  - `settings.json`
  - `auth/<profile>/steam_token.txt`

**Migration**: on the first start where userdata exists but is empty,
in-build defaults are copied forward.  Subsequent upgrades do NOT
overwrite existing userdata files (the user's customizations win).

**Recommended directory layout for new users**:

```
C:\Umamusume API Bot Claude\
    Pre Icarus v6.7.6\          (the build folder, replaceable)
        main.py, career_bot/, public/, data/, ...
    SweepyClaude_userdata\       (created by user, persists across upgrades)
        accounts.json
        settings.json
        data/
            settings_presets.json
            presets/*.json
        auth/
            default/steam_token.txt
```

On the next upgrade to (e.g.) v6.7.7, replace just the build folder.
All user-customized state in `SweepyClaude_userdata` is preserved.

  - **`main.py`** -- new `_resolve_userdata_dir()`, `_user_settings_path()`,
    `_user_accounts_path()`, `_user_presets_dir()`, `_user_steam_token_path()`
    helpers.  `SETTINGS_PATH` rerouted.  `_accounts_path()` rerouted.
    Steam token write site also persists a copy to userdata.
  - **`career_bot/config_store.py`** -- `ConfigStore.__init__` accepts
    `userdata_dir=` so settings/skill/solver paths follow the userdata
    convention.  `_maybe_migrate_from_build()` copies in-build defaults
    on first run.
  - **`career_bot/presets.py`** -- `PresetStore.__init__` accepts
    `preset_dir=` for the rare callers that hit it directly.

### 4. Documentation: Live Policy Assistance vs Training Scorer Mode

Different scopes, both safe to leave enabled simultaneously.

| System | Where | Affects | Default |
|---|---|---|---|
| Live Policy Assistance | AI Learning tab | **Race** selection (planning) | OFF (recommended until shadow precision > 75%) |
| Training Scorer Mode | Character Profile tab | **Training** selection (runtime) | hint |

  - **Live Policy Assistance** uses learned data from past careers'
    race outcomes.  It applies small score adjustments to race
    candidates in the Smart Race Solver based on which races have
    historically failed for similar trainees.  Only affects race
    SCORING -- never overrides safety gates or race availability.

  - **Training Scorer Mode** controls how the v6.1 training scorer
    interacts with the strategy engine's per-turn training decisions.
    `hint` = scorer publishes its opinion to the dashboard, strategy
    decides what runs (safe default).  `authoritative` = scorer overrides
    strategy on training picks when margin warrants (now works correctly
    per v6.7.5).  `disabled` = scorer skipped entirely.

The two never conflict.  LPA is about *which races to plan*; Training
Scorer Mode is about *which training to pick this turn*.

### 5. Race-count update (no code change)

The v6.7.5 log shipped by the user shows 28 races, 1 hijack (T69 JBC
Ladies' Classic), 0 chain breaks, 0 HP=0 races.  The chain-break and
epithet-protection layers are working as designed.  v6.7.6's auto-pick-
default-off MAY organically add 1-2 races by letting the solver pick
freely (less bias toward Ideal Idol-specific G1s lets other high-fan
G2/G3 races into the plan).  The structural ~30-race ceiling vs the benchmark's
41 is the safety-vs-throughput trade-off discussed in the v6.7.5
"settings analysis" turn -- the user can match the benchmark's count
by toggling Ignore Consecutive Race Warning + Ignore Low Energy Racing
Block on, accepting HP=0 races as a cost.

### Tests

`tests/test_v676_fixes.py` (new, 7 tests):

  - Sparks fix: `factor_info_array` differs between runs when
    `trained_chara_id` differs; parent slot factors are NOT picked up
  - Userdata: ConfigStore routes settings to userdata when configured
  - Userdata: in-build defaults migrate forward on first run
  - Userdata: `userdata_dir=None` uses in-build path (no regression)
  - Userdata: user changes survive a simulated v6.7.7 upgrade
  - Auto-pick: dataclass default is False
  - Auto-pick: profile JSON can opt in via explicit flag

Existing `tests/test_character_profiles.py` updated for the v6.7.6
default flip:

  - `test_auto_pick_default_is_true` -> `test_auto_pick_default_is_false_v676`
  - `test_auto_picks_signature_when_target_empty` -> `_when_target_empty_and_opted_in` (uses temp dir with explicit opt-in)
  - `test_each_profile_gets_signature` updated to check candidate list when opted in
  - `test_oguri_auto_picks_ideal_idol`, `test_special_week_auto_picks_signature`, `test_to_dict_includes_auto_pick_fields` updated to the opt-in pattern
  - `test_auto_derived_path_also_gets_auto_picks` now verifies the candidate list IS populated but the effective target list is empty until opt-in

Curated regression set: 215 tests pass (7 new + 208 baseline).

`main.py` build_version bumped to `Pre Icarus v6.7.6`.

## Pre Icarus v6.7.5

### Authoritative scorer override was being thrown away (dashboard contradiction fix)

User reported a Decision Reasoning row that said "T29 Wit ... Trained Wit ... scorer override fired: strategy picked 106, swapped to speed (margin 7.3435)".  Wit and Speed can't both be true.  Audit confirmed the override was structurally broken and had been since v6.3.

### What was actually happening

The strategy decision flow in `career_bot/runner.py` runs in two phases for command actions:

  1. Pre-event phase (line 595-619): strategy picks a command, items are processed, events drained, then **the strategy is re-invoked** at line 615 and a NEW decision object is produced.
  2. Execution phase (line 639-643): the new decision is recorded and executed.

`_apply_authoritative_scorer_override` was called at line 602 on the **first** decision (pre-event).  It mutated that decision's `payload["command_id"]` and recorded `status["last_scorer_override"]`.  Then line 615 created a brand-new decision object that overwrote the mutated one -- the override's effect on the executed command was discarded.

So the runtime outcome was: Wit ran (strategy's re-decision), but `last_scorer_override` was set to "Wit -> Speed".  The dashboard's Decision Reasoning then read both and produced the contradictory row.

### Fix in v6.7.5

  1. **`career_bot/runner.py`** -- removed the misplaced override call at line 602.  Added a new call at line 639 (the actual execution branch, immediately before `_record_action` and `client.exec_command`).  Now the override either mutates the executed command_id or stays silent.

  2. **`_apply_authoritative_scorer_override`** -- on entry, clears `last_scorer_override` if it's tagged with a previous turn.  This prevents stale entries from leaking into later turns' dashboard text on turns where the override doesn't fire.

  3. **`_decision_reasoning`** -- override message reworded.  Now uses stat names instead of raw command_ids ("strategy's pick (wit) -> speed" instead of "strategy picked 106, swapped to speed").  Includes a defensive fallback that explicitly says "override attempted X but final action was Y" if a mismatch is ever detected (shouldn't happen post-fix, but the message is now self-consistent if a future regression appears).

### What the user will see after v6.7.5

For Oguri's profile (default `training_scorer_mode: "hint"`) the override never fires -- only the "v6.1 scorer would have picked speed (score X.XX)" message will appear when scorer and strategy disagree.  No "override fired" sentence at all.

If a profile is in `authoritative` mode AND the override actually swaps the command, the row header AND the override sentence will both name the same stat ("T29 Speed ... v6.3 authoritative override swapped strategy's pick (wit) -> speed (margin 7.34)").  The Wit/Speed contradiction is no longer possible.

### Tests

`tests/test_scorer_override_placement.py` (new, 4 tests):

  - Stale override from T15 is cleared when T29 runs (no cross-turn leakage)
  - Current-turn override entry is preserved during evaluation
  - Authoritative-mode override mutates the final decision payload (Wit -> Speed)
  - Hint-mode override is a no-op (no mutation, no status write)

Curated regression set: 208 tests pass (4 new + 11 epithet + 8 race-chain + 185 baseline).

`main.py` build_version bumped to `Pre Icarus v6.7.5`.

## Pre Icarus v6.7.4

### Audit findings from the user's uma_runtime + epithet protection fix

User asked: (1) can the bot tell when epithets are achieved, (2) why does it still say "chasing Ideal Idol" at T71, (3) why isn't race count climbing even with `irregular_training_min_main_gain` raised to 50?

I extracted the user's uma_runtime and audited the latest career log (`career_log_20260615_182219.json`).  Findings:

#### What I found in the actual run

  - Trainee: Oguri Cap, scenario 4 (Trackblazer Start of the Climax)
  - Run completed successfully -- 78 turns, 29 races, 322,063 fans
  - Action counts: train 37, race 29, recreation 6, rest 4, medic 2, finish 1
  - Confirmed T19-T24 was a 6-race streak with HP=0 from T21-T24 (the bug v6.7.3 fixes for future runs)
  - Long training stretches at T28-T31 (4 turns) and T43-T49 (7 turns) where the solver had planned races but training hijacked them.  T46 was a Wit rainbow-x3 training (main gain ~60-80), which would pass the 30 default AND the user's raised 50 threshold.
  - Yasuda Kinen WAS won (T59) but Mile Championship and Arima Kinen were never raced -- they were almost certainly hijacked by rainbow training turns.
  - Trackblazer solver's projected_epithets list did NOT include Ideal Idol -- the solver had given up on it during planning -- but the dashboard kept showing "chasing Ideal Idol" because that's the profile's auto-pick.  No mechanism connected the live state to the message.

#### Root cause of race-drop on target epithets

`_irregular_training_decision` in `career_bot/scenarios/mant.py:1229` had **zero awareness** of which races progress active target epithets.  Once a rainbow training scored high enough and gave 30+ main gain, it could hijack ANY planned race -- including the single Mile Championship that was Oguri's only path to Ideal Idol.  Raising `irregular_training_min_main_gain` to 50 helps with solo and rainbow-x1 trainings but doesn't stop rainbow-x2 / rainbow-x3 turns which routinely give 60-90 main gain on a strong support deck.

#### Fixes in v6.7.4

  1. **`career_bot/trackblazer.py`** -- two new public helpers:
     - `epithet_critical_race_names(base_dir, target_epithets, completed_epithets)` returns the set of race names whose win would progress an unmet target epithet
     - `epithet_progress(base_dir, target_epithets, race_history)` returns a per-target progress report: `[{name, status, races_won, races_needed}]` where status is one of `completed`, `in_progress`, `not_started`, `no_data`, or `dead` (overridden when the solver marks it as such)

  2. **`career_bot/scenarios/mant.py`** -- the hijack code now gates on epithet-criticality FIRST.  A new `_planned_race_is_epithet_critical(program_id, preset, data)` method computes which unmet target epithets would be blocked by dropping the race.  If the set is non-empty, the hijack returns None with `reject_reason: "race_progresses_unmet_target_epithet"` and `blocking_epithets: [...]` in the trace -- so the dashboard can show exactly why the race was preserved.

  3. **`main.py /api/character-profile/active`** -- response now carries an `epithet_progress` array with the live per-target report.  Solver-flagged dead epithets are tagged in-place so the dashboard can render them differently.

#### Direct answers to the user's questions

  Q: "Can the bot tell if any epithets have been achieved?"
  A: Yes, and it has been since v6.1 -- `_completed_epithets_for_history` walks the race result history after every race and the solver re-plans with that knowledge.  What was missing was surfacing this on the dashboard and using it to defend critical races at runtime.  v6.7.4 adds both.

  Q: "Could it make the smart race solver re-evaluate based on that?"
  A: It already does -- `_maybe_replan_smart_races_after_result` runs the solver again after every race result, with race_history feeding into the epithet-completion check.  What v6.7.4 adds is preventing the irregular-training hijack from dropping races that the solver still needs to complete unmet targets.  The replan can only redistribute remaining races; it can't undo a race that was hijacked at runtime.

  Q: "Even on turn 71 it says it's still chasing Ideal Idol."
  A: That message reflected the configured TARGET, not the live PROGRESS.  At T71 Oguri had only won 1 of the 3 needed races (Yasuda Kinen; Mile Championship and Arima Kinen had been hijacked at T44 and likely T67 area).  The endpoint now returns per-target status with the actual won/needed counts; the dashboard can render this as "Ideal Idol -- 1/3 won (need Mile Championship, Arima Kinen)" instead of just "chasing Ideal Idol".

  Q: "Is something overriding settings in Scenario Overrides?"
  A: No, the UI's `irregular_training_min_main_gain` slider does correctly persist to `mant_config` and is read by `_irregular_training_decision` at runtime.  But on a strong support deck, rainbow-x2/x3 trainings routinely produce 60-90 main gain, so even a 50 threshold leaves many trainings that still pass the gate.  To fully stop the hijack on rainbow x3 you'd need to set it to ~80.  Better: v6.7.4 makes epithet-critical races immune to hijacks regardless of training value, so the threshold matters less.

### Test coverage

`tests/test_epithet_protection.py` (new, 11 tests): epithet_progress status transitions (empty / partial / full history, rank-1-only counting), epithet_critical_race_names returns expected race names for Ideal Idol against the live catalog (Mile Championship / Yasuda Kinen / Arima Kinen), `_planned_race_is_epithet_critical` returns the blocking set on unmet targets and empty set on completed targets or non-critical races.

Curated regression set (204 tests, including 11 epithet + 8 race-chain + 185 baseline): all pass.

`main.py` build_version bumped to `Pre Icarus v6.7.4`.

## Pre Icarus v6.7.3

### Race-chain HP safety fix (user-reported 6-race streak at HP=0)

User reported: "Consecutive Races Limit = 5" set in Scenario Overrides, but the action log showed 6 races in a row (T19-T24), with the last 4 at HP=0/104.  Both safety toggles ("Ignore Consecutive Race Warning" and "Ignore Low Energy Racing Block") were OFF, so neither escape hatch should have applied.

**Root cause** -- `career_bot/scenarios/mant.py::_guide_race_chain_break` had two structural bugs in its safety hierarchy:

1. **HP-critical and HP-low gates were conditioned on `chain_count >= target`.**  This meant raising the dashboard's "Consecutive Races Limit" simultaneously disabled HP safety for races 1..target-1 of any streak.  With target=5, the bot could race at HP=0 for four turns in a row before any HP check could fire.  Even at the target boundary, the HP gate competed with the training-bypass and could lose.

2. **`target` was a soft tie-breaker, not a hard cap.**  When `chain_count >= target` was reached with full HP and no viable training, the function fell through to `return None` and let the race execute.  The "Consecutive Races Limit" UI control therefore behaved as "preferred limit when other gates agree" rather than as a real maximum.

**Fix** -- the function is restructured into four explicit steps:

  Step 1 (chain_count >= legacy_target = 2):
    HP-critical fires -- recreation or rest, independent of target.
    This is the user-protective floor that the v6.7.2-and-earlier code
    only enforced after the user had already raced ``target`` times.

  Step 2 (any chain_count >= legacy_target):
    training bypass if a clean training is available (preserves the
    existing rainbow-windfall optimization).

  Step 3 (chain_count >= target OR unsafe grade context):
    HP-low / unsafe-grade gate -- recreation/rest for HP <= low_vital
    (default 35) when racing G2/G3 mid-streak.

  Step 4 (chain_count >= target):
    hard cap.  Recreation or rest is selected unconditionally when no
    earlier gate fired.  The user's setting is now a real maximum.

Below ``legacy_target`` (2 prior races) the function still returns None on the first turn after a rest, preserving the original race-rhythm behavior.  The Year-end/Finale carve-out at turns 23-24, 47-48, 71-72, and >= 73 is preserved unchanged.

### Settings answers to the user's question

  Q: "Is something overriding my Consecutive Races Limit setting?"
  A: Yes.  Before v6.7.3 the limit was a tie-breaker, not a cap.  The HP-critical gate was also gated behind the same threshold, so raising the limit disabled HP safety for the early part of every streak.  After v6.7.3, the limit is a hard cap and HP safety is independent.

  Q: "Is the decision to override my settings the right choice?"
  A: No.  Continuing to race at HP=0 risks the trainee's career and contradicts the user's intent.  The override was a bug in the safety hierarchy, not a deliberate design choice, and is fixed in v6.7.3.

### Test coverage

`tests/test_race_chain_safety.py` (new, 8 tests): locks in the contract with the exact T19-T24 scenario, the HP-critical floor at legacy_target, the hard cap at target with full HP, escape hatches (ignore_low_energy_racing_block, ignore_consecutive_race_warning, enable_game8_race_chain_break=False), and the Finale carve-out.

Curated regression set (193 tests, including the 8 new ones): all pass.

`main.py` build_version bumped to `Pre Icarus v6.7.3`.

## Pre Icarus v6.7.2

### Decision Reasoning cleanup + diagnosis of the actual race-drop mechanism

Two user-facing problems fixed, plus a key diagnosis on why race counts aren't climbing.

#### 1. Decision Reasoning panel cleanup

The panel was showing raw command IDs everywhere (`training Wit 106`, `rest 701`, `recreation 301`, race labels with leading `program_id race_instance_id`) and the v6.6 "Active profile" line that appeared on every entry was noise.  Cleaned up:

- **`career_bot/scenarios/mant.py::_command_reason`** -- the decision reason strings dropped the trailing command_id.  Now emits clean labels: `"Train Speed"`, `"Train Wit (rainbow x2)"`, `"Rest"`, `"Recreation"`, `"Medic"`.
- **`career_bot/races.py::label`** -- the race label dropped the leading `program_id` and `race_instance_id`.  Now emits dot-separated bits: `"Junior Make Debut · G3 · 1600m · turf"` instead of `"1070 904186 Junior Make Debut G3 1600m turf"`.
- **`career_bot/runner.py::_decision_reasoning`** rewritten.  The v6.6 "Active profile: Oguri Cap (matched via card_id, hand_curated, scorer mode: hint)" line is GONE.  Profile context is now folded into the per-action explanations as natural language:

  Old (v6.6): `"Active profile: Oguri Cap (matched via card_id, hand_curated, scorer mode: hint). Profile stat priority: speed > power > wit > stamina > guts."`

  New (v6.7.2): `"Trained Speed -- top-priority stat (speed > power > wit > stamina > guts), at 257/1200 target (21%), mood favorable, v6.1 scorer agrees (score 22.5)"`

  Each action type (train / race / rest / recreation / medic / finish) has its own focused WHY phrasing.  Race rows surface the active epithet target source ("chasing auto-picked epithet 'Ideal Idol'").  Training rows show the stat's priority rank, current value vs the profile's per-distance target, mood/HP context, and scorer agreement.  Irregular-training hijacks surface as the engine's own raw reason ("irregular training beats planned race Sapporo Kinen score=12.345 main_gain=42 fail=8").

#### 2. Why race count stalled at 24-27 -- the actual mechanism

After auditing the runtime decision path, the structural cause of the race-count gap is `_irregular_training_decision` at `career_bot/scenarios/mant.py:1185`.  When a planned race is scheduled for the current turn, this code evaluates the best available training and **hijacks the planned race** when:

  - training score >= `irregular_training_score_threshold` (default 0.62)
  - main stat gain >= `irregular_training_min_main_gain` (default 30, the value you have in Scenario Overrides)
  - failure rate <= `irregular_training_failure_limit` (default 24, or 65 with a Charm available)

With Oguri's strong support deck most trainings exceed the 30 main-gain floor (rainbow trainings often give 60-80+).  This is correct behavior for stat-efficiency runs, but it's the structural ceiling on race count.  Solver picks 36 races, runtime hijacks 10-12 of them for high-value training, you see 24-26 races executed.

**User action recommended.** The cleanest fix from your existing UI without touching the code:

  Option A (gentler) -- raise the threshold so only truly exceptional training hijacks:

    Scenario Overrides Settings -> "Minimum Main Stat Gain for Irregular Training": 30 -> 80

  Option B (firmest) -- disable hijacking entirely for this preset:

    Scenario Overrides Settings -> uncheck "Enable Irregular Training"

  Option A keeps the rainbow-windfall benefit (>=80 main gain is rare, only the most valuable training will still hijack) while letting nearly all solver-planned races execute.  Option B will run every solver-planned race, potentially leaving small-stat-gain training windows on the table.  Either way you'll see race count climb toward the 36 the solver picks.

#### 3. Backtest tool: command_id mapping bug fixed

The backtest script's `COMMAND_TO_STAT` had wrong mappings -- assumed 102=Stamina/103=Power/104=Guts/105=Wit but the real mapping per `runner.py::TRAINING_LABELS` is 102=Power/103=Guts/105=Stamina/106=Wit.  Also missing was the 601-605 summer-camp variant range.  Both fixed.  Re-running the backtest against the existing logs now shows accurate per-stat distribution.

#### 4. Tests + housekeeping

- 185 tests pass.  test_backtest's command_id test updated to reflect the corrected mapping.
- `main.py` build_version bumped to `Pre Icarus v6.7.2`.

## Pre Icarus v6.7.1

### Hotfix: `/api/character-profile/active` was raising `NameError` ("name 'runner' is not defined")

The endpoint I introduced in v6.5 referenced a non-existent global `runner`.  The actual global in `main.py` is `career_runner` (a `CareerRunner` instance), and its state is read via `.snapshot()` (which acquires the lock and returns a thread-safe dict copy), not `.status` directly.  This is why the CHARACTER PROFILE tab showed "Could not load profile: name 'runner' is not defined" for every user from v6.5 through v6.7 -- the bug existed in every release that shipped the endpoint.

- **`main.py /api/character-profile/active`** -- fixed the name (`runner` -> `career_runner`), the access pattern (`runner.status` -> `career_runner.snapshot()`), and added a fallback path for the idle case.  When the runner hasn't loaded `chara_info` yet (career not running, just sitting on the dashboard with a trainee selected in the Smart Race Solver Settings picker), the endpoint now reads from the global `active_selection["trainee"]` to pull the selected `card_id` / name, looks the name up in `data/chara_list.json`, and synthesizes a minimal `chara_info` dict for `resolve_profile` to use.  This means the panel renders correctly in three states: (1) live career mid-run, (2) idle with a dashboard selection, (3) cold start with nothing selected (default profile).
- `resolved_from` payload gains a `source` field with values `"runner"` / `"selection"` / `"default"` so the dashboard can show why this particular profile was resolved.
- No other changes.  All 185 tests still pass.

`main.py` build_version bumped to `Pre Icarus v6.7.1`.

#### Verified states after the fix

Smoke test against the actual profile resolver returns:

  - Live career with chara_info loaded -> resolves to `oguri_cap (hand_curated)`, epithetValue override 3.0
  - Idle career with dashboard "Oguri Cap" selected -> same: `oguri_cap (hand_curated)`, epithetValue 3.0
  - Nothing selected -> `default (default)`, no overrides

So the CHARACTER PROFILE tab will now load and render correctly whether or not a career is actively running.

## Pre Icarus v6.7

### Character Profile relocated to a tab on the Decision Reasoning pane

v6.5 added a CHARACTER PROFILE section as a sidebar-style collapsible between Smart Race Solver and Race Schedule.  That section was never visible on the main dashboard because the dashboard layout doesn't use the sidebar-section pattern -- those headers live under the SETUP tab, which is a separate workspace.  v6.7 puts the panel where you actually see it during a run.

- **`public/index.html`** -- Decision Reasoning header now contains two tab buttons (`DECISION REASONING` / `CHARACTER PROFILE`) instead of the single label.  A second pane is added inside `.v547-reason-pane` and hidden by default; the existing decision-reasoning content is the active pane on first paint.  The orphan `#character-profile-section` block from v6.5 is removed.
- **`public/app.js`** -- the `setupCharacterProfilePanel` IIFE retargets the new `#v66-character-profile-pane` element, wires the tab buttons to toggle pane visibility, hides the WAITING / turn-N pill while the profile tab is active so it doesn't look like the profile is waiting on a turn, and only fetches `/api/character-profile/active` when the profile tab is opened (no auto-load on dashboard paint).  Re-polls every 30s while the profile tab is the active view.
- **`public/styles.css`** -- new `.v66-tab-btn`, `.v66-tab-active`, `.v66-tab-pane`, `.v66-reason-tabs` classes for the pill-style tab buttons in the existing reason-pane header.  The existing `.cp-*` classes (panel content) get tighter padding/font sizes inside `.v547-reason-pane` since this pane is narrower than the sidebar context the v6.5 design targeted.
- No backend changes -- the v6.5 endpoints (`/api/character-profile/active`, `/list`, `/mode`, `/epithets`) all still serve the same data.
- 185 tests still pass (the change is UI-only).

`main.py` build_version bumped to `Pre Icarus v6.7`.

#### What you'll see now

Open the main dashboard.  The DECISION REASONING panel is the same one you've always had on the right side, but the header now has two clickable pill buttons.  Click **CHARACTER PROFILE** to swap the pane content: profile pills (display name, derivation, matched-via, scenario), training-scorer-mode dropdown with Save button, stat priority row, per-distance stat targets table, scenario-tuned solver overrides, the auto-picked / effective epithet targets, and the character-filtered catalog picker.  Click **DECISION REASONING** to swap back.  No collapse, no scrolling around to find it.

## Pre Icarus v6.6

### Critical: silent profile-override drop fixed (+ Oguri profile retuned, decision reasoning enriched)

This is a **bug-fix release** addressing why race counts stalled around 27 despite v6.2-v6.5's profile system shipping with Oguri-specific tuning.  Two structural bugs and one no-op lever were silently neutralizing the entire profile-override layer.  All character profiles benefit, but Oguri's profile in particular has been retuned to use levers that actually move the solver's race-count math.

#### Bug #1 (CRITICAL): profile solver overrides were silently dropped when the preset had defaults populated

The v6.2 injection logic at the two Trackblazer solver call sites had this condition::

    if k not in weights or weights.get(k) in (None, "", 0):
        weights[k] = v

The intent was "fill in blanks from the profile while letting user overrides win," but the implementation only treated `None`, `""`, and `0` as blank.  When a user clicked **Save** in the Smart Race Solver Settings dashboard panel, the preset's `mant_config.trackblazer_weights` was populated with all system defaults (e.g. `epithetValue: 1.0`, `raceCostPct: 100.0`).  At that point every profile override was blocked because the condition `1.0 in (None, "", 0)` evaluates False.

The v6.6 fix recognizes "preset value equals system default" as "user didn't actually choose this" and lets the profile win in that case::

    elif preset_default is not None and current == preset_default:
        weights[k] = v

User overrides that *differ* from the system default still win.  Patched at both call sites (`career_bot/runner.py` line 1867, `career_bot/races.py` line 493).

Impact: a smoke-test verifies Oguri's profile overrides (epithetValue 3.0, raceCostPct 75.0, longDistanceStaminaFloor 450) now flow through to the live solver instead of being neutralized by default-valued presets.

#### Bug #2: targetOptionalRaceCount is a no-op for race count

The solver only references `targetOptionalRaceCount` to emit a diagnostic warning note *after* the schedule is already chosen.  It does NOT influence per-race scoring or the beam-search optimization.  Setting it to 40 in Oguri's profile was structurally ineffective.

Removed from `data/character_profiles/oguri_cap.json` and replaced with levers that actually move the solver's race-count math:

- `epithetValue: 3.0` (was 2.0) — each target_epithet_hit on Oguri's "Ideal Idol" required races (Mile Championship, Yasuda Kinen, Arima Kinen) now adds +3.0 to the per-race score
- `raceCostPct: 75.0` (was default 100.0) — lowers the per-race cost threshold so more middling G2/G3 races become net-positive in the cost-benefit math
- `lateSeniorRacePressure: 20.0` (was default 12.0) — pushes more racing in late senior turns 65-72
- `distancePreferenceBonus: 12.0` (was 8.0) — further rewards her Mile/Medium aptitude races

#### Bug #3: decision reasoning didn't surface v6.2-v6.5 context

`_decision_reasoning` was generating reasonable text for the dashboard's Action Log but didn't mention the active character profile, the v6.1 scorer hint vs strategy pick, the v6.3 authoritative-override events, or the v6.4 epithet target source.  So users couldn't verify from the dashboard whether the profile system was actually in effect.

Enriched with these new context lines per training/race decision:

- "Active profile: Oguri Cap (matched via card_id, hand_curated, scorer mode: hint)."
- "Profile stat priority: speed > power > wit > stamina > guts."
- "v6.1 scorer agrees: top pick was speed (score 22.5)." (or disagrees with both names + scores)
- "v6.3 authoritative override fired: 105 -> 101 (speed, margin 4.2)." (when authoritative mode is on and the override actually triggered)
- "Epithet targets (auto-picked signature): Ideal Idol." (or preset/profile/none source)

#### Tests + regression

5 new tests in `tests/test_character_profiles.py::SolverWeightInjectionTests` reproducing the silent-drop bug, verifying the v6.6 fix, confirming user explicit non-default overrides still win, and asserting the v6.6 Oguri profile has the right levers and not the no-op one.  Updated `test_oguri_cap_trackblazer_overrides_apply` to match the new tuning.  **185 tests pass across the full suite.**

#### Why this matters in practice

If you ever opened the Smart Race Solver Settings dashboard panel and clicked Save (even without changing anything), the preset's `mant_config.trackblazer_weights` got populated with system defaults.  From that point onward, *every* solver-side profile override across v6.2-v6.5 was silently dropped.  The bot was running with `epithetValue: 1.0` (default) instead of 2.0, `raceCostPct: 100` instead of any profile tuning, and the auto-picked "Ideal Idol" epithet was being awarded the default reward weight when its target races were hit.  That's the structural reason race count plateaued around 27.

With v6.6 the profile overrides actually take effect.  Combined with the more aggressive Oguri tuning, expected impact on a Trackblazer Oguri run:

- Race count: should climb meaningfully from the 26-27 baseline (each "Ideal Idol" matcher race now adds +9 to its score vs +3 previously, and more middling races become net-positive at raceCostPct 75)
- Late senior racing density: up due to lateSeniorRacePressure 20 vs 12
- Fan count: likely up proportionally with race count

Run a fresh Oguri career after installing and compare against the 358K/27-race / 339K/26-race baseline from your screenshot.  If race count climbs into the mid-30s or higher, the bug fix is doing the work.  If it doesn't, the next investigation target is the solver's beam-search algorithm parameters vs the reference implementation.

`main.py` build_version bumped to `Pre Icarus v6.6`.

## Pre Icarus v6.5

### Dashboard Character Profile panel, promotion-mode toggle, three new hand-curated profiles, backtest tool

Closes out all four next-session candidates from v6.4 in one release.  The dashboard now renders the v6.1+ profile data the bot has been publishing since v6.1, the training_scorer_mode flag can be flipped per-profile without editing JSON, the catalog of hand-curated profiles grows from 2 to 5, and a CLI backtest tool lets you sanity-check the strategy engine's training distribution against the active profile's stat priority before promoting any profile to authoritative.

- **`public/index.html` + `public/app.js` + `public/styles.css`** -- new `CHARACTER PROFILE` collapsible section in the dashboard sidebar (between Smart Race Solver and Race Schedule).  Renders the active resolved profile with which file matched, how it matched (card_id/chara_id/preset/auto/default), and what overrides apply: stat priority, per-distance stat targets, scenario-tuned solver overrides, current epithet target source (preset/profile/auto/none), the catalog of character-filtered epithets as a checkbox picker, and a Save button that POSTs to `/api/character-profile/epithets` to write the user's selections back to the profile JSON.  Auto-refreshes every 30s plus on-demand via the Refresh button.
- **Promotion-mode toggle**: dropdown in the panel for ``hint`` / ``authoritative`` / ``disabled``.  POSTs to `/api/character-profile/mode` which rewrites the profile JSON on disk.  Inline help text explains each mode.
- **Three new hand-curated profiles**:
  - `data/character_profiles/sakura_bakushin_o.json` -- pure Sprinter (Sprint=A, Mile=B). Speed-Power priority, long-distance stamina floor dropped to 300 (she shouldn't race long), `distancePreferenceMode: strict` to push the solver away from off-aptitude distances. card_id 104101 / chara_id 1041.
  - `data/character_profiles/daiwa_scarlet.json` -- Mile/Medium specialist (Mile=A, Medium=A, Long=B). Speed/Power/Wit priority similar to Oguri, stamina floor 425. card_id 100901 / chara_id 1009.
  - `data/character_profiles/tokai_teio.json` -- Medium specialist with Long backup (Medium=A, Long=B, Mile=E). Stamina-leaning Medium-Long priority, targetOptionalRaceCount 38. card_ids 100301/100302 / chara_id 1003.
- **`main.py`** new endpoints:
  - `GET /api/character-profile/active` -- resolves the active profile from the runner's chara_info, returns full profile dict plus character-filtered epithet catalog for the picker.
  - `GET /api/character-profile/list` -- enumerates all on-disk profiles.
  - `POST /api/character-profile/mode` -- writes a new `training_scorer_mode` to a profile JSON (body: `{profile_id, mode}`).
  - `POST /api/character-profile/epithets` -- writes explicit `target_epithets` / `forced_epithets` to a profile JSON (body: `{profile_id, target_epithets, forced_epithets}`).
- **`scripts/backtest_training_scorer.py`** -- new CLI tool.  Reads career_log_*.json files (single file or directory), extracts the training command executed at each turn (from api_calls `exec_command` REQs with `payload.command_type == 1`), tallies per-stat, resolves the active character profile, and compares the actual distribution against the v6.1 scorer's stat priority.  Outputs per-run alignment scores and an aggregate report grouped by profile.  `--csv` flag emits a spreadsheet-ready file.  `--trainee` / `--scenario` flags filter.  Practical use: run against your bot_logs directory before flipping any profile to authoritative.
- **Tests**: 19 new tests covering the three new profiles (Sakura Bakushin O, Daiwa Scarlet, Tokai Teio), the cross-profile signature epithet auto-pick regression, and the backtest script's extraction/distribution/alignment logic.  181 tests pass across the full suite.
- `main.py` build_version bumped to `Pre Icarus v6.5`.

#### What the new panel looks like

Open the dashboard and the CHARACTER PROFILE section appears between Smart Race Solver and Race Schedule.  When a run is active and the bot has loaded chara_info, the panel auto-populates with the resolved profile.  Between runs it shows whatever the last known card_id/chara_id resolved to, falling back to the default profile when neither is set.

The epithet picker checkboxes are character-filtered -- pick Oguri Cap and the picker shows only her tagged epithets ("Ideal Idol" plus any generics she shares).  Clicking Save writes the selections to her profile JSON and the next solver pass picks them up via the existing precedence chain (preset > profile JSON > auto-pick > none).  Clicking Clear empties target_epithets and lets auto-pick resume.

#### Running the backtest

    python scripts/backtest_training_scorer.py uma_runtime/default/bot_logs/

For the two career_logs available in my smoke test, both showed Speed and Wit consistently over-trained vs the default Speed/Stamina/Power/Guts/Wit priority -- which is the diagnostic signal that those runs were on the default profile but the trainee benefited from different priorities.  Once the runs use a hand-curated or auto-derived profile, the alignment should climb.

## Pre Icarus v6.4

### Auto-pick signature epithets with full user-override precedence

Where v6.3 surfaced suggested epithets to the dashboard but never fed them to the solver, v6.4 closes that gap: every active character profile now auto-promotes the trainee's signature epithet into ``target_epithets`` when neither the preset nor the profile JSON sets them explicitly.  This means a fresh Oguri Cap run will automatically chase "Ideal Idol" (her character title) as a soft solver goal -- which raises the schedule's race count and gives the bot a concrete objective to weigh G2/G3 picks against -- without forcing the schedule into anything infeasible.

User override still wins at every layer.  The precedence chain is::

    preset.trackblazer_target_epithets   (dashboard / user explicit)
    -> profile.target_epithets           (profile JSON explicit)
    -> profile.auto_picked_epithets      (signature epithet from catalog)
    -> []                                (no goals)

- **`career_bot/character_profiles.CharacterProfile`** gains two fields: ``auto_pick_epithets: bool`` (default ``True``, can be set ``False`` in the profile JSON or under a ``scenarios.<id>`` block to opt out) and ``auto_picked_epithets: List[str]`` (the catalog-derived signature epithet name(s), populated by the resolver from the trainee's display name).
- **`CharacterProfile.effective_target_epithets()`** -- new method that returns ``(epithet_names, source)`` for callers, with ``source`` being ``"profile"`` (explicit JSON), ``"auto"`` (signature epithet), or ``"none"`` (no goals).  Used by the runner / races call sites to feed the solver.
- **`career_bot/runner.py` Trackblazer solver call site** now consults ``effective_target_epithets()`` and publishes ``status.epithet_target_source`` with the chosen source label so the dashboard can render which path provided the active goals.
- **`career_bot/races.py` live-replan call site** uses the same effective-targets path.
- Both the hand-curated and v6.3 auto-derived profile resolution paths now populate ``auto_picked_epithets`` from the bundled smart-race epithet catalog (or the v6.3 ported ``data/character_data/epithets.json``).  Each of the 59 character-tagged signature epithets in the catalog -- Oguri's "Ideal Idol", Mejiro McQueen's "Best Actress", Special Week's "Showbiz Idol", etc. -- becomes a sensible per-character default.
- 10 new tests in `tests/test_character_profiles.py::AutoPickEpithetsTests` covering the explicit-wins precedence chain, per-scenario opt-out, default-True behavior, missing-catalog fallback, and shipped-catalog regressions for Oguri Cap, Special Week, and Mejiro McQueen (auto-derived).  162 tests pass across the full suite.
- `main.py` build_version bumped to `Pre Icarus v6.4`.

#### Background: where the data lives

Worth noting since it came up in design discussion: Pre Icarus has been pulling its Trackblazer epithet, race, and debut-race data from the `daftuyda/umamusume_trackblazer_scheduler` GitHub repo since well before v6.0 -- the same source repo behind the [race.daftuyda.moe](https://race.daftuyda.moe/) web scheduler.  The reference bot does *not* pull from there; they ship their own copy.  v6.3 added a parallel copy at `data/character_data/epithets.json` for the auto-derivation name lookup, but the solver-side canonical catalog at the bundled smart-race epithet catalog (217 entries, 59 character-tagged) has been there all along and is what v6.4's auto-pick uses.

#### Disabling auto-pick

To turn auto-pick off for a specific character profile, add to the JSON::

    "auto_pick_epithets": false

To disable per-scenario only::

    "scenarios": {
      "4": {"auto_pick_epithets": false}
    }

The signature epithet will still show up in ``suggested_epithets`` for the dashboard picker, but it won't be promoted into the solver's target list.

## Pre Icarus v6.3

### Auto-derived profiles for every trainee, character + epithet catalogs, authoritative-mode wire-in, Special Week profile

Where v6.2 introduced the profile system but only shipped a hand-curated profile for Oguri Cap, v6.3 makes the system useful for every trainee.  Two ported community datasets plus a live-aptitude auto-derivation layer mean any character now gets a sensible profile -- hand-curating remains the way to express stronger opinions, but it's no longer the only way to get character-aware tuning.

- **`data/character_data/`** -- new directory holding two community-maintained JSON catalogs ported from an upstream community project: `character_presets.json` (59 trainees with distance and surface aptitudes) and `epithets.json` (217 epithets, 59 character-tagged signature titles plus 158 generic ones).  `README.md` carries the attribution.
- **`career_bot/character_data.py`** -- new loader module with mtime-keyed memoization.  Exposes `load_character_presets`, `load_epithet_catalog`, `find_character_preset`, `epithets_for_character`, and `signature_epithet`.  Name matching is case-insensitive, whitespace-tolerant, and strips parenthetical suffixes like "(SSR)" or "(Alt)".
- **Auto-derivation in `career_bot/character_profiles.py`** -- `resolve_profile` now accepts an optional `chara_info` argument.  When no hand-curated profile matches, it synthesizes a profile from the live aptitudes: stat priority chosen by best-distance bucket (Mile/Sprint -> Speed-Power-Wit, Medium -> Speed-Stamina-Power, Long -> Stamina-Speed-Power), per-distance stat targets scaled by aptitude grade (S/A get full strength, lower grades scale down), preferred_distances includes everything at B-grade or better, and long-distance stamina floor scales with the Long aptitude (550 at S/A, 400 at D-grade or weaker).  When the trainee's name matches a catalog entry, the signature epithet is surfaced into `suggested_epithets` for the dashboard picker.
- **`data/character_profiles/special_week.json`** -- second hand-curated profile.  Long stayer (Long=A, Medium=A): Stamina-Speed-Power priority, per-distance targets push Stamina to 1200 on Long and trim Sprint stats, Trackblazer-tuned `targetOptionalRaceCount=40`, `epithetValue=2.0`, `longDistanceStaminaFloor` held at default 550 (build the stamina).  Matched via `card_id` 100101/100102 and `chara_id` 1001.
- **Authoritative-mode wire-in.**  `_apply_authoritative_scorer_override` runs immediately before training-command execution.  When the active profile has `training_scorer_mode == "authoritative"` AND the strategy engine's chosen command is a training, the v6.1 scorer is consulted and its top pick replaces the strategy's pick if it beats the strategy's score by a configurable margin.  Override events are logged to `status.last_scorer_override` for dashboard rendering.  `hint` mode profiles are unaffected (still publish to the hint payload, strategy engine still decides).
- **Resolved profile gains `derivation` and `suggested_epithets` fields.**  `derivation` is `"hand_curated"`, `"auto_derived"`, or `"default"` -- the dashboard can show users which path resolved their active profile.  `suggested_epithets` is a list of epithet rows tagged with the active character; it's read-only and never auto-promotes into `target_epithets`.
- 28 new tests across `tests/test_character_data.py` (catalog loaders, name matching, missing-file fallback) and the expanded `tests/test_character_profiles.py` (auto-derivation for stayer / miler / sprinter, stamina-floor scaling, per-distance target scaling, letter-grade aptitude handling, hand-curated profiles still winning over auto, missing-aptitude default fallback, suggested-epithet lookup, Special Week regression).  152 tests pass across the full suite.
- `main.py` build_version bumped to `Pre Icarus v6.3`.

#### What changes the next time you run a non-Oguri character

Every trainee now gets character-tuned defaults the first time they're run -- no JSON authoring required.  Mejiro McQueen (Long=S Medium=A) will automatically pick up Stamina-first priority, push per-distance stat targets toward Long, hold the stamina floor at 550, and surface "Best Actress" in `suggested_epithets`.  Special Week works identically but uses the hand-curated profile (which has Trackblazer-specific `targetOptionalRaceCount=40` and `epithetValue=2.0` overrides that the auto-derived path doesn't apply by default).

To promote a profile to authoritative mode, flip its `training_scorer_mode` from `"hint"` to `"authoritative"` in the JSON file (or under a `scenarios.<id>` block to promote only for a specific scenario).  The override only triggers on training commands and only when the scorer's pick beats the strategy's by a clear margin -- noise-level disagreements still defer to the strategy engine.

## Pre Icarus v6.2

### Per-character preset profiles + Trackblazer-tuned Oguri Cap profile

Where v6.1 built the native training scorer, v6.2 plugs it (and the existing Trackblazer race solver) into a per-character configuration layer.  Each character now gets a JSON profile that bundles tuned stat priorities, per-distance stat targets, race-solver weight overrides, epithet goals, and a training-scorer mode flag.  Active profile resolution happens at run start from the trainee's ``card_id`` / ``chara_id``, with the preset name as a third lookup key and a ``default`` profile as the always-on fallback.

- **`career_bot/character_profiles.py`** -- new module.  ``resolve_profile(card_id, chara_id, scenario_id, base_dir, preset_name)`` returns a ``CharacterProfile`` dataclass with ``training_scorer_config()``, ``solver_weight_overrides()``, ``epithet_goals()``, and a per-profile ``training_scorer_mode`` flag (``"hint"`` / ``"authoritative"`` / ``"disabled"``).
- **`data/character_profiles/`** -- new directory with shipped JSON profiles: `default.json` (empty overrides, matches v6.1 behavior), `oguri_cap.json` (Speed/Power/Wit priority, rainbow bonus on, Mile/Medium per-distance targets), and `index.json` mapping `card_id 100601` and `chara_id 1006` to the Oguri profile.
- **Per-scenario overrides** nest under `scenarios.<id>` and stomp the base profile values for that scenario only -- the shipped Oguri profile uses this to ship Trackblazer-specific tuning (`longDistanceStaminaFloor: 450` down from 550, `targetOptionalRaceCount: 40` up from 36, `epithetValue: 2.0` up from 1.0) without affecting other scenarios.
- **`career_bot/runner.py`** v6.1 training-scorer hint now resolves the active profile and passes its ``TrainingScorerConfig`` into ``score_trainings``.  Hint payload gains ``profile_id``, ``profile_display_name``, ``matched_via``, and ``mode`` fields so the dashboard can show which profile is active and how it matched.
- **`career_bot/runner.py`** and **`career_bot/races.py`** Trackblazer solver call sites both layer `profile.solver_weight_overrides()` under the preset weights and fall back to the profile's `target_epithets` / `forced_epithets` / `preferred_distances` when the preset doesn't supply them.  Preset values still win when set -- the profile is the default, the preset is the user override.
- 27 new tests in `tests/test_character_profiles.py` covering every lookup path (card_id, chara_id, preset, default fallback, missing-file graceful fallback), per-scenario override semantics (dict shallow-merge, list replacement), `TrainingScorerConfig` round-trip with unknown-key tolerance, mode normalization, and end-to-end resolution against the shipped Oguri Cap profile.
- `main.py` build_version bumped to `Pre Icarus v6.2`.

#### Promoting the training scorer to authoritative

Each profile's `training_scorer_mode` defaults to `"hint"` (v6.1 behavior: scorer publishes to the dashboard but the strategy engine still decides).  Flipping a profile's mode to `"authoritative"` will let the v6.1 scorer drive that profile's training decisions while leaving other profiles unchanged -- the wire-in for that path lives in the strategy engine and lands as a follow-up patch when you're ready to evaluate the scorer's picks against the live decision over a few real runs.

## Pre Icarus v6.1

### Training scorer (native), measurement fix, style adaptation enabled

This release closes most of the gameplay gap identified in the performance audit.  Three things ship together: a real training scorer module, a measurement fix that lets the AI advisor see end-of-career fan/rating numbers it was previously blind to, and a config flip that takes style adaptation out of perpetual shadow mode.

- **`career_bot/training_scorer.py`** -- new module implementing the native formula `(StatEfficiency * 0.60 + Relationship * 0.10 + Misc * 0.30) * RainbowMultiplier * FacilityLevelMultiplier`.  Rainbow detection cross-references each command's `training_partner_array` against `chara_info.evaluation_info_array` (bond >= 80 = real rainbow; below threshold but >= 10% fill = anticipatory rainbow, capped at 1.6x so anticipation never out-ranks a real rainbow).  Facility-level weighting boosts top-3 priority stats by 1.10x-1.75x based on the `level` field already exposed in `command_info_array`.  Stat-cap awareness sets score to 0 within the buffer of the absolute cap.  Failure-rate gate filters above the configured threshold (default 20%).
- Per-distance stat targets (Sprint/Mile/Medium/Long) and per-context priorities (training / event / summer) are first-class config in `TrainingScorerConfig`.
- `pre_summer_action(turn, energy, mood)` helper for the June-Late prep decision (rest / recover / train_wit) on turns 24 and 48.
- Scorer wired into `runner._track_turn_scores` as a **hint**: published to `status.training_scorer_hint` and `status.training_scorer_history` so the dashboard can show what the new scorer thinks alongside the strategy engine's pick.  The strategy engine remains authoritative for the live decision in v6.1; promotion to authoritative is planned for v6.2 once the scorer has been validated against a few real runs.
- 29 new tests in `tests/test_training_scorer.py` covering every component (stat efficiency, relationship, misc, rainbow detection both real and anticipatory, level multiplier, per-context priorities, per-distance targets), filter gates (failure_too_high, stat_capped), edge cases (no partners, malformed entries, the older flat-field payload layout), the pre-summer helper, and a regression test using the exact API shape we observed in real run data.
- `main.py` build_version constants bumped to `Pre Icarus v6.1`.

## Pre Icarus v6.0.1

### Career-summary measurement fix + style adaptation out of shadow mode

Two narrow fixes that don't change runtime behavior but fix the diagnostic plumbing the AI advisor depends on.

- **Career summary measurement fix.**  `career_bot/ai_dataset.py::career_summary_record` was looking for `fans` inside `final_chara.stats` (the nested stats sub-dict containing speed/stamina/etc.), but `runner._compact_final_chara` writes `fans`, `rating`, `rank`, `card_id`, and `title` at the top level of `final_chara`.  Every completed run in `career_summaries.jsonl` therefore recorded `final_fans: 0` even though the dashboard had the right number all along (it reads from the per-turn `bot_logs/career_log_*.json` files directly).  Now the summary cascade pulls `fans` / `rating` / `rank` / `card_id` / `chara_title` from `report.final_chara` -> `status_snapshot.final_chara` -> `status_snapshot`, first non-empty value wins.  Adds `final_fans`, `final_rating`, `final_rank`, `card_id`, and `chara_title` to the JSONL schema.  Impact: the Bayesian advisor and any future Q-learning over career outcomes finally gets reward signal for whole-career fan/rating performance instead of always seeing zero.
- **Style adaptation out of shadow mode.**  `career_bot/style_adaptation.py` DEFAULT_CONFIG `style_adaptation_mode` flipped from `"shadow"` to `"recommend"`.  Shadow mode logged style recommendations but never applied them; with 0.99 confidence on the vast majority of decisions across many runs of validation, it's safe to let the recommendation actually drive race style when the existing confidence and aptitude gates allow.

## Pre Icarus v6.0

### Merge release — modeling improvements + upstream v5.44 features in one build

This release combines the v5.43AI/v5.43.1AI Bayesian advisor modeling track with the upstream developer's v5.43 Local LLM Advisor and v5.44 Event Outcome Knowledge Base.  The merge is additive across the board.

- Brought forward from v5.43AI: Beta-Binomial posteriors over race-program win rate, hierarchical context-aware pooling, `policy_guards.safe_apply` with KL-divergence drift detection, and the calibration module (`calibration.py`) with reliability diagrams, ECE/Brier, and an isotonic recalibrator.
- Brought forward from v5.43.1AI: live calibrator wire-in.  `race_program_hint` and `hierarchical_race_program_hint` apply the persisted isotonic calibrator automatically; `fit_calibrator(base_dir)` returns a dashboard-friendly payload; `calibration_summary` surfaces ECE + reliability diagram + plain-English interpretation under `post_run_advice`.
- Brought forward from upstream v5.43: Local LLM Advisor (`career_bot/local_llm.py`).  Optional integration with OpenAI-compatible local servers (LM Studio, Ollama, custom).  Strict-JSON prompting, redacted config storage, post-run analysis and shadow advice as append-only JSONL artifacts; LLM outputs are never executed as bot commands.
- Brought forward from upstream v5.44: Event Outcome Knowledge Base (`career_bot/event_outcomes.py`, bundled `data/dumper_outcomes_import.json` merged into `data/event_outcomes.json`).  Event-name matching, normalized stat deltas / energy / vital / motivation / skill points / skill hints / conditions / confidence metadata, AI Dataset event outcome rows in `event_outcome_rows.jsonl`, `/api/events/outcome-kb` endpoints, AI Learning dashboard card.
- `career_bot/ai_dataset.py` registers the upstream's `event_outcome_rows.jsonl` path in `DATASET_FILES` while keeping the v5.43AI hierarchical bucket logic in `rebuild_advisor_stats`.
- `career_bot/ai_advisor.py` is the v5.43.1AI version (Bayesian math + calibration wire-in) preserved unchanged through the merge; upstream did not modify the functions involved.
- `main.py` build_version constants set to `Pre Icarus v6.0`.
- Test coverage carried forward: 68 modeling tests (Sprint 1 / Sprint 2 / Sprint 1.4.3.1) plus upstream's regression tests for event outcome import / scoring / LLM context.

## Pre Icarus v5.44

### Event Outcome Knowledge Base + Dumper Outcome Importer

- Added `career_bot/event_outcomes.py` for safe static event outcome imports and normalization.
- Bundled `data/dumper_outcomes_import.json` and merged normalized imported outcomes into `data/event_outcomes.json`.
- Added event-name matching so known static outcomes can score events even when a story ID is not available.
- Added support for imported outcome details such as stat deltas, energy/vital changes, motivation, skill points, skill hints, max vital, gained/lost conditions, and confidence/source metadata.
- Added AI Dataset event outcome rows in `uma_runtime/ai/event_outcome_rows.jsonl`.
- Added `/api/events/outcome-kb` and `/api/events/outcome-kb/import`.
- Added an AI Learning **Event Outcome Knowledge Base** card with coverage stats and bundled import/refresh controls.
- Local LLM post-run analysis and shadow review prompts now receive compact known-event-outcome context.
- Added documentation in `docs/event-outcome-kb-v544.md` and regression tests for import, scoring, and LLM context.

## Pre Icarus v5.43.1AI

- Wired the v5.43 calibration module into the live race advisor. When an isotonic calibrator is fitted, both `race_program_hint` and `hierarchical_race_program_hint` now apply it to the posterior mean and LCB before producing `adjustment`, so the live decision path uses the corrected estimate instead of just exposing the calibrator as a tool.
- Added `ai_advisor.fit_calibrator(base_dir)` -- reads `turn_decisions.jsonl`, extracts race predictions, fits an isotonic calibrator, and persists it atomically to `uma_runtime/ai/isotonic_calibrator.json`. Returns a `{success, reason, message, ece_before, ece_after, brier_before, brier_after, predictions}` payload designed for direct rendering on a dashboard button.
- Added `ai_advisor.calibration_summary(base_dir)` -- compact dashboard payload with current ECE, Brier score, plain-English interpretation, reliability diagram bins, and calibrator metadata (when fitted: `fitted_at`, `predictions_used`, `ece_before`).
- `post_run_advice` now embeds the calibration summary under a `calibration` key so the existing AI dashboard surfaces it without an additional endpoint.
- Calibrator JSON is loaded with mtime-cached, hot-reload-aware semantics: re-fitting from the dashboard takes effect on the next hint call without restarting the bot.
- Hints now expose `calibration_active` (bool), `calibrated_mean`, `calibrated_lcb`, `calibrated_ucb`, and `raw_adjustment` / `raw_posterior_mean` / `raw_lcb` / `raw_ucb` for the previous values, so the dashboard can show both the corrected estimate and what the model thought before correction.
- All v5.43 fields are unchanged. Existing callers that read only the legacy fields see no behavior change other than `adjustment` being the calibrated value when a calibrator is present.
- `fit_calibrator` returns friendly status messages instead of raising for the common failure modes: no `turn_decisions.jsonl` yet, fewer than `MIN_PREDICTIONS_FOR_CALIBRATION` (30) predictions logged, isotonic fit failure on degenerate input.
- Atomic file write (tempfile + rename) on persistence so an interrupted save can never leave a half-written calibrator that the loader would silently nullify on next startup.
- Added 13 unit tests in `tests/test_ai_sprint143_1.py` covering: cold-start no-op behavior, hierarchical wire-in, the four `fit_calibrator` outcome paths, ECE-improvement verification on synthetic miscalibrated data, mtime-cache invalidation on re-fit, and the three lifecycle stages of `calibration_summary`.
- Build version bumped in `main.py` to `Pre Icarus v5.43.1AI`.

## Pre Icarus v5.43AI

- Replaced the AI advisor's point-estimate `win_rate` and `-8.0` magic-number penalty with a Beta-Binomial posterior over race-program win rate, prior centred on the user's global program base rate. Adjustments are now `avg_reward * lower_credible_bound`, smooth across the full `win_rate` range with no discontinuity at 0.5.
- Added `career_bot/ai_modeling.py` with `BetaPosterior` (prior construction, Bayesian update, mean/variance/mode, lower/upper credible bounds, credible interval, Thompson sampling, round-trip serialization), `posterior_from_stats_bucket`, `global_base_rate`, `hierarchical_posterior` with parent-discounted shrinkage, and `score_program`.
- Added `career_bot/calibration.py` with `reliability_diagram`, `expected_calibration_error`, `brier_score`, and `IsotonicCalibrator`. Calibrator uses scikit-learn when available and falls back to a pure-Python Pool Adjacent Violators implementation when not, so calibration runs are reproducible across hosts.
- Added `career_bot/policy_guards.py` with `PolicyGuardConfig`, `safe_apply` returning a `GuardDecision` with reasons `insufficient_samples` / `drift_detected` / `clamped` / `applied`, closed-form `beta_kl_divergence`, and `compute_posterior_drift` for detecting meta shifts via posterior KL on rolling windows.
- Extended `ai_dataset.rebuild_advisor_stats` with a new `race_programs_context` section containing four levels of hierarchical aggregation (`by_program` / `by_program_scenario` / `by_program_scenario_preset` / `by_program_scenario_preset_phase`). The legacy `race_programs` flat section is preserved unchanged for backward compatibility.
- Added `career_bot/ai_dataset._turn_phase` exposing the early/classic/senior/finale boundaries used by both the existing `turn_bands` aggregation and the new hierarchical buckets.
- Added `ai_advisor.hierarchical_race_program_hint(base_dir, program_id, scenario_id, preset_name, turn)` which walks the hierarchical buckets least-to-most-specific via parent-discounted shrinkage. Sparse leaves inherit from their richer parent levels instead of producing wild estimates. Returns the same fields as `race_program_hint` plus `contributed_levels` and a per-level `levels` diagnostic for the dashboard.
- Falls back automatically to v1 semantics when `race_programs_context` is missing from `advisor_stats.json`, so existing stats archives keep working until the next dataset rebuild.
- `race_program_hint` legacy return fields (`program_id`, `confidence`, `starts`, `win_rate`, `avg_reward`, `adjustment`, `reason`) preserved exactly so existing call sites in `runner.py`, `ai_trainer.py`, and the v532/v533 test contracts continue to pass unchanged. Adds `posterior_mean`, `lcb`, `ucb`, `variance`, `alpha`, `beta` for new consumers.
- `post_run_advice` risky-program detection now uses posterior LCB instead of raw win rate, replacing the `starts >= 3 and win_rate < 0.6` cutoff with continuous uncertainty-aware ranking.
- `_confidence_label` derives the `confidence` string from posterior variance and is calibrated so the new buckets land in the same general regions as the v1 `starts >= 3 / >= 8` thresholds, keeping `tests/test_sweepymodv533_ai_auto_training` assertions intact.
- Added 51 unit tests across `tests/test_ai_sprint1.py` and `tests/test_ai_sprint2.py` covering Beta posterior math, hierarchical pooling behavior, calibration metrics, isotonic recalibration (with and without scikit-learn), policy guard branches, drift detection, hierarchical bucket builder semantics, and full backward-compat contract tests for `race_program_hint` and `hierarchical_race_program_hint`.
- Added documentation in `docs/ai-modeling-bayesian-v543AI.md`.

## Pre Icarus v5.43

### Pre Icarus v5.43 Local LLM Parser Cleanup

- Improved Local LLM response parsing so JSON wrapped inside `analysis`, `advice`, `result`, `response`, or `raw_text` envelopes is unwrapped into clean structured fields.
- Added support for fenced JSON, double-encoded JSON strings, trailing-comma cleanup, and common alias normalization such as `patterns` → `key_patterns` and `suggested_rules` → `repeatable_rules`.
- Updated the AI Learning Local LLM output card to show key patterns, risks, and repeatable rules instead of only `Analysis saved.` when structured data is available.
- Added regression tests for enveloped/raw-text model replies.

### Pre Icarus v5.43 Local LLM Analysis Fix

- Fixed Local LLM post-run analysis requests that could trigger LM Studio `HTTP 400 Bad Request` errors when completed career logs produced prompts larger than the loaded model context.
- Added prompt budgeting for Analyze Last Run so recent turns are automatically trimmed/slimmed before sending to the local model.
- Improved Local LLM HTTP error details so future failures include the server response body instead of only `HTTPError: 400`.
- Added regression coverage for large-run prompt budgeting.


- Added optional Local LLM Advisor support for OpenAI-compatible local servers such as LM Studio, Ollama, or custom endpoints.
- Added `career_bot/local_llm.py` with redacted config storage, connection tests, strict-JSON prompt handling, post-run analysis, and shadow turn review.
- Added AI endpoints for Local LLM config, testing, latest state, latest-run analysis, and shadow advice.
- Added AI Learning Local LLM card with provider/mode/base URL/model/API key fields plus Save, Test, Analyze Last Run, and Shadow Review buttons.
- Local LLM outputs are stored in `uma_runtime/ai/llm_run_summaries.jsonl` and `uma_runtime/ai/llm_advice.jsonl` and never execute direct runner commands.
- AI dashboard now surfaces Local LLM status, last analysis headline, risk flags, and candidate rules.
- Added documentation in `docs/local-llm-advisor-v543.md` and regression tests for config normalization, connection testing, and analysis artifacts.
- Fixed the Local LLM Advisor form so dashboard refreshes no longer overwrite unsaved edits, checkbox changes, model text, or API key typing.
- Fixed Local LLM config saving so leaving the API key field blank preserves the previously saved key instead of erasing it.

## Pre Icarus v5.42AI

- Added conservative Racing Style Adaptation telemetry and model scaffolding for Pre Icarus AI.
- Added append-only `style_adaptation_experiences.jsonl` rows for every race style decision, observation, and outcome.
- Logs now include selected Racing Settings style, shadow recommendation, applied style, current stats, style/distance/surface aptitudes, owned skill summaries, clock usage, clean vs clock-rescued wins, and opponent style counts when exposed after race entry.
- Added `career_bot/style_adaptation.py` with Shadow Only, Recommend Only, and safety-gated Auto Apply modes.
- Added generated artifacts: `style_adaptation_model.json`, `style_adaptation_report.json`, `style_adaptation_shadow_report.json`, and `style_adaptation_backtest.json`.
- Added AI Learning dashboard controls for Racing Style Adaptation mode and a report card for samples, switch outcomes, bad switch rate, and Auto Apply lock status.
- Added official master.mdb table catalog export in `data/master_table_catalog_core.json` so the AI can label official table data without pretending hidden formulas are exposed.
- Added source labels for `official_table_data`, `api_observed_data`, `empirical_estimate`, and `unknown_hidden_formula` in style-adaptation artifacts.
- Added documentation in `docs/style-adaptation-v542AI.md`.

## Pre Icarus v5.41AI

- Added live turn-by-turn Smart Race Solver re-planning so smart schedules are rebuilt from current stats, runner context, previous race results, clock policy, and current race history before each race decision.
- Smart solver routes now pass current trainee/preset identity into race-risk lookup so learned penalties can use per-preset/per-trainee history before falling back to global race outcomes.
- Solver-generated Train turns now suppress legacy fan-farming and fallback race heuristics, preventing old logic from racing when the live smart route says to train/rest.
- Re-planning after race results now runs for all smart-route race outcomes before turn 72, not only failed solver-planned races, so missed/failed epithets and clock-rescued outcomes immediately affect the remaining schedule.
- Runner context now exposes live race history, runtime support, clock policy, and latest re-plan metadata to decision systems and logs.
- Added regression coverage for live smart re-planning, profile-specific learned race risk, and smart Train-turn fallback suppression.

## Pre Icarus v5.40AI

- Added clock-aware race retry telemetry to career logs, race outcome aggregates, and AI turn-decision exports.
- Logs now distinguish clean wins from wins rescued by clocks, including initial rank, final rank, clocks used, retry attempts, and whether Burn Clocks was enabled by the user.
- Smart Race Solver learned scoring now applies extra clock-dependency risk when Burn Clocks is disabled, while preserving user choice as the source of truth.
- Expanded race logs with compact master.mdb-derived metadata: venue/date, fan and reward set IDs, Trackblazer first-place coin/win-point rewards, race groups, and official performance-rate hints.
- Regenerated bundled master-data JSON exports from the provided master.mdb so the new logging fields use current official metadata.
- Added AI health/dashboard fields for clock retry rows and clock-policy-enabled race rows.
- Added documentation in `docs/clock-aware-ai-logs-v540AI.md` and regression tests for clock-aware AI logging/model behavior.

## Pre Icarus v5.39AI

- Added a Live Policy Assistance toggle inside the AI Learning dashboard.
- Added visible recommendation text showing whether the current AI model recommends enabling Live Policy Assistance or keeping it disabled.
- Recommendation logic now checks AI health, race-result coverage, turn records, race sample counts, learned adjustment counts, and confidence thresholds.
- Dashboard now distinguishes Live Policy states as OFF, REQUESTED, or ACTIVE.
- Live Policy remains safety-gated and only adjusts legal Smart Race Solver candidate scores.
- Added documentation in `docs/ai-live-policy-toggle-v539AI.md`.

## Pre Icarus v5.38AI

- Extended AI Learning import to also import settings presets from previous builds.
- Importer now accepts `data/settings_presets.json` and legacy `data/presets/*.json` files.
- Preset import deduplicates safely and never overwrites existing presets with different content.
- Updated AI Learning modal copy from Import Previous Logs to Import Previous Logs & Presets.
- Added documentation in `docs/ai-log-preset-import-v538AI.md`.
- Packaged release with root files directly in the zip to avoid nested duplicate folders when extracting.

## Pre Icarus v5.37AI
- Added AI Learning import controls so previous build folders, `uma_runtime` folders, `bot_logs` folders, or zip files can be imported into the current AI dataset.
- Added `/api/ai/import-logs` with duplicate-safe career log importing, race outcome merging, event history merging, automatic dataset rebuild, and optional training.
- Added `import_manifest.json` so repeated imports do not duplicate old career logs.
- Added UI guidance for the easier long-term approach: keep/copy `uma_runtime/default` between builds or import it from the AI Learning modal.

## Pre Icarus v5.36AI
- Fixed the dedicated AI Learning modal so its dashboard content is visible instead of being hidden by the old Diagnostics CSS rule.
- Added an AI Training Dashboard artifact and UI cards for model confidence, learned records, race-result coverage, Shadow Mode, backtesting, learned risk/value summaries, config suggestions, epithet confidence, and per-preset/per-trainee confidence.
- Added Shadow Mode reports that compare learned race-risk hints against historical outcomes without changing live gameplay decisions.
- Added offline backtesting reports that estimate how often learned race-risk penalties would have warned on historically failed races.
- Added stronger local analytics artifacts for epithet completion confidence and preset/trainee model confidence.
- Added AI dashboard, shadow report, backtest report, and config-suggestion API endpoints.
- Updated safe AI debug bundles to include the new dashboard, shadow, backtest, epithet, and confidence artifacts.

## Pre Icarus v5.35AI
- Added Smart Race Solver help text explaining Strict, Balanced, and Loose distance preference modes.
- Centralized running-style conversion so Pace Chaser maps to game style 2 and Late Surger maps to game style 3 consistently.
- Updated weighted skill purchasing to block style-exclusive skills that contradict the selected Racing Settings strategy.
- Moved AI Learning controls from Diagnostics into a dedicated top-level AI Learning modal.
- Reworked the top navigation layout to prevent Runs, Theme, Logout, Delay, and account/status pills from overlapping.

## Pre Icarus v5.34AI

- Repaired AI race-result extraction from `single_mode_free/race_end` API response logs.
- Fixed AI race outcome training so missing results are not counted as losses.
- Added AI data health checks and auto-disables live policy assistance when race-result coverage is unsafe.
- Added nested item telemetry parsing and `events_seen.json` support for item/event analytics.
- Expanded career summaries with final stats, final fans, race counts, win rate, rest/recreation counts, and reconstructed race results.
- Fixed LLM prompt-pack manifest counts by atomically overwriting the latest prompt pack per training run.
- Added a safe AI debug bundle endpoint and Diagnostics health display.


## Pre Icarus v5.33AI

- Added automatic local AI training that runs after completed career exports and on a timer while the runner is idle.
- Added Phase 2 local analytics tables: race outcomes, item effectiveness, event outcomes, and automatic post-run reports.
- Added Phase 3 learned scoring artifacts: race-risk model, item-value model, event-value model, and confidence-gated policy adjustments.
- Added Phase 4 LLM advisor preparation: prompt packs, synthetic review prompts, and suggested config tuning. No external LLM calls are made by default.
- Added Phase 5 optional live policy assistance for the Smart Race Solver. Learned adjustments only modify legal race candidate scores and are fully reversible/confidence-gated.
- Added AI auto-training Diagnostics controls: auto-training toggle, Train Now, post-run report, advisor report, and dataset download.
- Added API endpoints for AI auto-training status/config, manual training, latest post-run report, and model artifact downloads.
- Added unit tests for auto-training, analytics table generation, learned policy hints, and post-career training scheduling.

## Pre Icarus v5.30

- Replaced the Smart Race Solver route core with a local purpose-built architecture: exact MILP first, history-aware beam fallback, local structured epithet matchers, and RaceHistory/EpithetTracker-style projected completions.
- Added distance preference modes for Smart Race Solver: Strict, Balanced, and Loose. Strict mode blocks off-preference races unless needed for forced epithets.
- Bundled structured race/epithet assets for local planning and removed normal solver reliance on the external race-planner webpage.
- Improved Smart Solver preview details with preferred distances, distance mode, and projected epithets.
- Fixed skill list selection stability so multi-select actions no longer jump back to the top after each choice.
- Cleaned up the top-right navbar so Runs, Theme, and Logout no longer overlap.
- Renamed nav currency labels and TP recovery labels from Jewels to Carrots.


## Pre Icarus v5.29

- Fixed Action Log historical-click behavior so Decision Reasoning stays focused on the clicked turn instead of snapping back to the latest turn during polling refreshes.
- Hid the live footer turn ticker while the runner is active to prevent `Turn / action / step` text from appearing behind Run/Stop/Pause controls; pause/error messages still display.
- Added benchmark-inspired training target pressure so underbuilt stats receive stronger score weight before Wit HP/SP side value dominates.
- Added Wit balance damping when Wit is already ahead of weaker target stats and tightened Wit-as-rest replacement to avoid repeated unnecessary Wit turns.
- Expanded training candidate traces with main gain, target completion, energy delta, and reason flags for clearer Decision Reasoning.
- Added regression tests for reasoning selection lock, footer overlap cleanup, and Wit/target-pressure scoring helpers.

## Pre Icarus v5.28

- Fixed Career History Major Wins by freezing per-run history snapshots instead of allowing entries to depend on live runner data.
- Settings presets now save and restore the selected deck, friend support, trainee, own parents, and guest parent.
- Replaced the visible Sync button with the existing Pause/Resume control in the Run controls row.
- Compacted Run Career, Stop, and Pause controls so the Action Log and Decision Reasoning area can use more vertical space.
- Renamed top-bar labels to `TP POTIONS` and `JEWELS` while keeping backend field names stable.
- Kept Configure Skills, skill configuration, and weighted skill purchase behavior unchanged.

## Pre Icarus v5.27

- Replaced the bundled legacy settings presets with one neutral `Default` preset.
- Added runtime sanitization so existing installs stop loading `Fan Farming`, `Maru Fan Farming`, `Oguri`, `Parent Farming`, `xguri`, and `xguri parent`.
- Removed the hard-coded `xguri parent` preset fallback from race saving and career-run startup.
- Made the frontend prefer the backend active preset when local storage does not point to a valid preset.
- Fixed the Crash Trace route by importing `runtime_output_root` into `main.py`.
- Renamed Smart Race Solver `Optimization Mode` to `Optimization Weight Preset` and clarified that it is a UI weight macro.

## Pre Icarus v5.26

- Added true Pause/Resume runner controls that pause only at safe automation checkpoints.
- Added explicit run counts: 1 for single career, N for bounded loops, and 0 for until-stopped loops.
- Guarded infinite loops when a guest/rental parent is selected; finite loops continue to refresh and validate guest/rental parent availability before every new career.
- Added Event Choices UI and runtime event override storage under `uma_runtime/`.
- Added simple Discord webhook save/test setup using the existing Discord telemetry logger configuration.
- Added regression coverage for pause/resume, loop info snapshots, runtime event overrides, and seen-event logging.

## Pre Icarus v5.25

- Ported Umabot's iterative 205/208 API retry loop with independent counters, exponential 208 backoff, and HTTP 500 retry support.
- Added runner safeguards for API responses missing `data.chara_info` and reconciled race-entry 205/208 responses before rejecting races.
- Added stale-race-state detection, `/api/career/rescue`, traversal-safe public asset paths, modular shell CSS, hardened monitor module, and UI contract tests.
- Expanded regression coverage with Umabot-style crash, stale race, TP recovery, race-entry reconciliation, and UI contract tests.

## Pre Icarus v5.24 TP Recovery Replacement

- Replaced the active Toughness/Carats TP Restore flow with Umabot-style TP recovery modes: `potion_first`, `potion_only`, and `jewels_only`.
- Added `/api/settings/tp-recovery` GET/POST endpoints backed by `settings.json`.
- Updated career start to use TP item 32 through `item/use_recovery_item` before optional Jewel recovery, matching Umabot behavior.
- Updated the account strip to show live TP item count and the persisted TP recovery mode selector.
- Preserved unrelated v5.24 selective improvements, including the theme selector, decision reasoning feed, and career-history aptitude fix.


## Pre Icarus v5.24

- Reverted the dashboard UI to the Pre Icarus v5.22 layout.
- Kept the persisted Neon Cockpit / Clean Dark theme selector.
- Kept the turn-by-turn Decision Reasoning feed backed by `/api/career/decision-trace/latest?limit=160`.
- Fixed Career History aptitude labels to use the actual 1=G through 8=S aptitude scale.

## Pre Icarus v5.22

- Ported useful Umabot improvements without replacing Pre Icarus's Trackblazer solver stack.
- Fixed Toughness 30 TP restore to use `item/use_recovery_item`, while Carats continue using `user/recovery_trainer_point`.
- Added modular parent spark filtering and safe preview-first recent-parent cleanup.
- Added a bottom Career Monitor drawer with live log filters, crash trace display, and current-run stat charting.
- Added `/api/career/live_history`, `/api/career/crash_trace`, `/api/parents/remove`, and `/api/parents/remove-recent`.

## Pre Icarus v5.21

- Fixed finished-career setup locks where the cockpit showed no active career but Friend Supports still said `ACTIVE CAREER, ENDPOINT BLOCKED`.
- Clears stale dashboard/backend career state and setup selection after a finished runner stop, while preserving loop-mode reuse between automatic careers.
- Auto-applies staged Manual Selection races before a fresh run starts.
- Sends `race_planner_mode` and `manual_race_ids` to the backend so manual race lists are tagged separately from Smart Race Solver plans.
- Makes manual due races take priority over Force Racing and prevents Irregular Training from hijacking a manual race list.
- Added regression coverage for setup unlock and manual race priority.
- Added documentation in `docs/setup-unlock-manual-races-v521.md`.

## Pre Icarus v5.20

- Retries temporary HTTP 502/503/504 gateway/server responses inside the API client instead of crashing immediately.
- Marks HTTP 502/503/504 and Gateway Timeout errors as recoverable in the career runner, so `single_mode_free/check_event` timeouts can reload state and continue.
- Added regression coverage for HTTP 504 retry success, retry-budget exhaustion, and runner recoverability.
- Added documentation in `docs/http-gateway-recovery-v520.md`.

## Pre Icarus v5.19

- Fixed guest-parent loop starts after a completed career by refreshing the selected rental parent against a fresh pre-start guest list before every new start.
- Stops the loop cleanly when a selected guest parent is no longer available instead of retrying `single_mode_free/start` and producing repeated API 501 errors.
- Converts guest-parent API 500/501 start rejections into a clear dashboard/loop message telling the user to refresh Guest Parents and reselect.
- Caches Toughness 30 API 213 rejections for 30 minutes in the current process, so looped runs no longer repeatedly hit the rejected item-backed TP restore call before falling back to Carats.
- Added regression coverage for looped guest-parent starts, fatal start handling, and cached Toughness 30 restore rejection handling.

## Pre Icarus v5.18

- Fixed guest parent cards not appearing in the top Parent 2 setup slot.
- Fixed own + guest parent career start payloads to use `rental_succession_trained_chara` instead of sending the guest as `succession_trained_chara_id_2`.
- Added frontend validation that blocks career start when a guest parent is missing the viewer/trained character IDs required by the start endpoint.
- Added backend validation for the supported parent combinations: 2 owned parents, or 1 owned parent + 1 guest parent.
- Added regression coverage for guest-parent slot display, start payload fields, and backend rental fields.

## Pre Icarus v5.17

- Fixed Toughness 30 detection being overridden by stale configured item IDs from older builds.
- Validates configured Toughness IDs against authoritative master-data IDs before use.
- Added robust inventory count parsing for TP restore items across `number`, `item_num`, `num`, `count`, and related account payload fields.
- Writes `data/toughness_item_ids.invalid.json` when an invalid local override is ignored.


All notable changes to this project are documented in this file.

This project now uses the exact build naming format `Pre Icarus vx.x`, where `x.x` is a major/minor version number. Entries are sorted newest first. Older source notes that did not record a release date are marked as `Date not recorded` instead of inventing one.


## [Pre Icarus v5.16] - 2026-06-11

### Fixed
- TP restore safety: selecting Toughness 30 no longer silently falls back to Carats after an API 213/item-backed restore rejection.
- Toughness 30 restore now reports API 213 as a server-side item restore rejection and stops unless explicit Carats fallback is enabled.
- Closed the master-data sqlite connection explicitly so test runs no longer emit the unclosed-connection ResourceWarning.

### Added
- Dashboard checkbox: **Use Carats if Toughness 30 fails**. It is disabled by default and sent as `tp_restore_allow_carats_fallback`.
- Documentation: `docs/tp-restore-safety-v516.md`.

## [Pre Icarus v5.15] - 2026-06-11

### Added

- Added `succession_scoring_core.json`, generated from `succession_initial_factor`, `succession_relation_rank`, and `succession_relation`.
- Added `career_progression_core.json`, generated from `single_mode_chara_grade`.
- Added `event_reward_display_core.json`, generated from official event reward/display tables and event text categories.
- Added official inheritance-point hints to Career History spark chips when available.
- Added Career Grade derivation in Career History using official win/run/fan requirements.
- Added event reward display labels to event-choice scoring traces when native event payloads expose display IDs.
- Added regression coverage for P3 master-data exports and the API 214 race-entry noisy-log fix.
- Added `docs/master-data-succession-career-events-v515.md`.

### Changed

- API 214 race-entry test recovery now logs through structured runner logs instead of printing a noisy simulated error line during tests.
- Career History detail metadata now includes official Career Grade when progression data is available.
- Master-data generation now extracts the P3 parent/spark, career progression, and event display tables.


## [Pre Icarus v5.14] - 2026-06-11

### Added

- Added `skill_condition_core.json`, generated from `skill_data`, `single_mode_skill_need_point`, and `skill_level_value`.
- Added `skill_upgrade_groups_core.json`, generated from official skill `group_id` chains.
- Added `skill_sources_core.json`, generated from `available_skill_set`, `skill_set`, `card_data`, and `support_card_data`.
- Added `support_hint_sources_core.json`, generated from `single_mode_hint_gain` and support-card metadata.
- Added `support_effects_resolved_core.json`, generated from support-card effect, unique-effect, level, and hint tables.
- Added regression coverage for the v5.14 master-data P2 skill/support exports.
- Added `docs/master-data-skill-support-v514.md`.

### Changed

- Weighted skill scoring now enriches official skill scores with master-data skill conditions, support-source counts, and trainee-source counts when those exports are available.
- Skill preview/scoring traces can now explain official support and trainee skill sources through reasons such as `support_sources:N` and `trainee_sources:N`.
- Master-data generation now extracts the official skill/source/support tables used by the P2 skill and support intelligence pass.

## [Pre Icarus v5.13] - 2026-06-11

### Added

- Added `training_effects_core.json`, generated from `single_mode_training`, `single_mode_training_effect`, and `single_mode_free_training_plate`.
- Added `scenario_turns_core.json`, generated from `single_mode_scenario` and `single_mode_turn`.
- Added official training-effect fallback traces to Trackblazer training scoring.
- Added scenario-calendar-backed summer-turn detection for Smart Race Solver backends.
- Added regression coverage for v5.13 master-data P1 exports and training fallback behavior.
- Added `docs/master-data-training-calendar-v513.md`.

### Changed

- Trackblazer training scoring can now use official master-data base training effects when the live command payload does not include stat/energy/SP deltas.
- Training decision traces now include an `official_training` summary with level, stat total, skill points, and energy delta when master-data baselines are available.
- Smart Race Solver summer filtering now reads official scenario calendar metadata when available, falling back to the previous hardcoded summer turns only if the export is missing.


## [Pre Icarus v5.12] - 2026-06-11

### Added

- Added `chara_route_core.json`, `rival_races_core.json`, `trackblazer_race_rewards_core.json`, and `race_performance_rates_core.json` master-data exports.
- Added static rival-race enrichment from `single_mode_rival` so RacePlanner can prioritize rival races even when runtime rival payloads are incomplete.
- Added Trackblazer race reward enrichment from `single_mode_free_coin_race`, `single_mode_free_win_point`, `single_mode_reward_set`, and `single_mode_race_group`.
- Added official race performance rate export from distance, ground, running-style, motivation, course-status, and popularity rate tables.
- Added regression tests for the v5.12 master-data planning exports and solver integration.
- Added `docs/master-data-trackblazer-planning-v512.md`.

### Changed

- Smart Race Solver candidate rows now include official fan reward fallback, Trackblazer coin reward, win points, race group IDs, reward set ID, and an official performance-rate hint.
- RacePlanner Trackblazer race sorting now considers official Trackblazer reward value after grade and fan reward.
- Master-data generation now extracts the official route, rival, reward, and performance-rate tables used by the P0 Trackblazer planning pass.

## [Pre Icarus v5.11] - 2026-06-11

### Added

- Added `tp_restore_items_core.json`, `win_saddle_core.json`, and `career_rank_thresholds_core.json` master-data exports.
- Added first-place fan reward metadata from `single_mode_program` and `single_mode_fan_count` into race planner metadata.
- Added regression tests that validate TP restore, fan rewards, major-win metadata, and rank thresholds against a master.mdb-shaped fixture.
- Added `docs/master-data-alignment-v511.md`.

### Changed

- Toughness 30 detection now uses a direct `item_data` + `text_data` query that returns `item_data.id` instead of scanning broad text tables.
- Career History rank display now uses `single_mode_rank` thresholds when generated master-data thresholds are available.
- Major-win display now resolves `win_saddle_id_array` through generated `win_saddle_core.json` labels before falling back to race-result counts.
- RacePlanner now preserves generated race fan reward, fan set, required fan, and reward-set metadata.

### Fixed

- Fixed Toughness 30 auto-detection potentially returning text category IDs such as `23` instead of the true item ID `32`.
- Fixed race result ledger fan rewards often showing `0` because generated race metadata did not include `single_mode_fan_count` values.
- Fixed direct major-win summary lookup treating win-saddle IDs as flat race-map IDs.
- Fixed rating-to-rank display using stale hardcoded thresholds when master.mdb rank thresholds are available.

## [Pre Icarus v5.10] - 2026-06-11

### Added

- Added a runner-level race result ledger for Career History, recording program id, race name, grade, distance, fan reward, final rank, and win status after race retries resolve.
- Added `/api/tp-restore/status` so the dashboard can report whether Toughness 30 is configured, owned, and usable before career start.
- Added regression coverage for rich Career History race counts/rating extraction and Toughness 30 TP restore payload support.

### Changed

- Career History now falls back to the race result ledger for race count, wins, major wins, and race details when the final server payload does not expose those fields directly.
- Career completion now searches nested finish payloads for rating, rank, race count, win count, skills, factors, and final trainee arrays instead of only reading top-level `chara_info`.
- The TP Restore UI now labels the item option as Toughness 30 to distinguish it from Carats.
- Toughness 30 TP restore now checks both configured/detected item IDs and currently owned item count before falling back to Carats.

### Fixed

- Fixed Career History showing `0 races / 0 wins` when the runner action history stored race actions as `race` rather than `race_entry`.
- Fixed major wins showing `Unknown` for runs that have race result data but no `win_saddle_id_array` in the final payload.
- Fixed TP restore fallback messaging so it clearly explains when Toughness 30 cannot be used because item IDs are missing or no copies are owned.

## [Pre Icarus v5.9] - 2026-06-11

### Added

- Added the split configuration store in `career_bot/config_store.py`, separating Settings Presets, Configure Skills, and Smart Race Solver configuration.
- Added `data/settings_presets.json`, `data/skill_config.json`, and `data/smart_solver_config.json` as the new canonical storage files.
- Added `/api/settings-presets`, `/api/skill-config`, and `/api/smart-solver/config` endpoints.
- Added a redesigned Configure Skills launcher and weighted skill configuration screen.
- Added Skill Point Threshold to Configure Skills with purchase-gate behavior: the bot waits to buy skills until enough skill points are accumulated.
- Added Skill Config tests for split storage, threshold behavior, disabled auto-purchase, and UI replacement.
- Added documentation for Settings Preset splitting and weighted skill configuration.

### Changed

- Replaced the old Preset Configuration section with Settings Presets, which only save Training Settings, Racing Settings, and Scenario Overrides.
- Moved Configure Skills below Training/Racing/Scenario settings buttons and above Settings Presets.
- Split runtime configuration composition so the runner still receives one combined config built from settings, skill, and solver stores.
- Smart Race Solver settings and manual race plans are now stored separately from Settings Presets.
- Configure Skills now stores the weighted skill purchase system independently of Settings Presets.
- Running Style and Track Distance in Configure Skills are read-only summaries sourced from Racing/Training behavior rather than duplicate controls.

### Fixed

- Fixed manual race selections being tied to the old preset blob by persisting them through Smart Solver config.
- Fixed skill threshold wording and behavior so it no longer implies stopping the bot.
- Fixed stale old preset files being carried forward by migrating and deleting `data/presets`.

### Removed

- Removed the old `data/presets` folder from the packaged build.
- Removed old skill tier/blacklist editor DOM from the Skill Configuration modal.
- Removed Min Skill Pt from the old preset area; it now belongs to Configure Skills.

## [Pre Icarus v5.8] - 2026-06-11

### Added

- Redesigned Career History as a desktop-first, two-level modal with rich summary cards and clickable detail views.
- Added searchable/sortable Career History controls for newest, rating, fans, wins, and trainee name.
- Added career detail panels for trainee portrait, rank, rating, fans, scenario, races/wins, final stats, aptitudes, sparks, and skills.
- Added CSS-rendered stat/aptitude grade badges and spark star chips.
- Added `docs/career-history-redesign.md`.

### Changed

- `/api/career/history` now enriches completed career entries with normalized aptitude labels, spark data, grouped skills, race/win totals, major-win summaries, and portrait URLs when available.
- Career completion snapshots now preserve final skill, factor, and win arrays when the game payload provides them.
- Replaced the old Career History table with desktop cards; no mobile variant is included.

## [Pre Icarus v5.7] - 2026-06-11

### Added

- Added per-trainee manual Smart Race Solver aptitude overrides so one trainee's solver edits no longer leak into another trainee.
- Added estimated parent-spark aptitude bonuses to the Smart Race Solver aptitude preview and route payload calculation.
- Added canonical solver defaults in `data/trackblazer_solver_defaults.json` plus `/api/trackblazer/solver/defaults` so frontend/backend default values share one source.
- Added hard forced-epithet constraints for MILP and Beam schedules: every selected forced epithet must have at least one native-matched scheduled race, or the solver reports infeasible.
- Added route-diff preview text comparing a newly solved route against the previous route.
- Added additional regression tests for summer blocking, forced epithets, partial cache repair, per-trainee aptitudes, solver defaults, and list-alias safety.
- Added `docs/code-analysis-v5.7.md`.

### Changed

- Smart Race Solver settings now use the compact Smart Race Solver / Manual Selection buttons as the single source of truth for planner mode.
- "Allow racing during Summer" now actually blocks summer-camp races when disabled instead of merely applying a score penalty.
- Solver numeric settings are clamped in the UI and backend to prevent negative or extreme values from warping schedules.
- Epithet pickers no longer silently slice the available list to 180 entries.
- Trackblazer cache loading repairs any missing dataset, not just missing `races.json`.
- `/api/trackblazer/plan` now preserves intentional 400 validation errors instead of converting them to 500 errors.
- Pydantic request models now use `Field(default_factory=...)` for mutable collections.

### Fixed

- Fixed explicit low manual aptitudes being overwritten by broad fallback `B` planning aptitudes.
- Fixed repeated stale-plan warning banners stacking in the Trackblazer card.
- Fixed preset hydration list aliasing in `extra_weight` and `spirit_explosion`.
- Fixed stale `solver_status()` documentation.

### Removed

- Removed the redundant Smart Race Solver enable/disable toggle from the Smart Race Solver Settings modal.

## [Pre Icarus v5.6] - 2026-06-11

### Added

- Added a **SMART RACE SOLVER SETTINGS** button to the Trackblazer card.
- Added a dedicated Smart Race Solver Settings modal for solver mode, trainee preset selection, manual solver aptitudes, aptitude threshold, OP/Pre-OP inclusion, summer racing, target/forced epithets, optimization mode, scoring weights, and schedule preview.
- Added `/api/trackblazer/epithets` for loading epithet data into the solver settings modal.
- Added backend support for `target_epithets` and `forced_epithets` in Trackblazer plan requests.
- Added tests for preserving solver settings and applying target epithet bias to matching races.
- Added `docs/smart-race-solver-settings.md`.

### Changed

- Moved Include OP / Pre-OP, Fan Bonus %, and Max Streak out of the compact Trackblazer card and into the Smart Race Solver Settings modal.
- Smart Race Solver plan payloads now use persisted preset-level solver settings instead of transient dashboard inputs.
- Target and forced epithets now apply an advisory scoring bonus to candidate races matching their condition text.



## [Pre Icarus v5.5] - 2026-06-11

### Fixed

- Moved Training Settings, Racing Settings, and Scenario Overrides inside the setup workspace so they appear immediately above Preset Configuration instead of auto-placing below Race Schedule.
- Added responsive setup-workspace grid rules so the buttons preserve their existing appearance and behavior on desktop and stack cleanly on smaller screens.


## [Pre Icarus v5.4] - 2026-06-11

### Added

- Added MILP fallback diagnostic logging to `uma_runtime/diagnostics/smart_solver_fallbacks.jsonl` and `latest_smart_solver_fallback.json`.
- Added `fallback_exception_type`, `fallback_traceback_tail`, and `fallback_log` fields to Beam fallback schedules after MILP failures.
- Added `docs/code-analysis-v5.4.md` documenting the remaining v5.3 audit follow-up work.
- Added regression tests for repeated event-drain recovery, MILP fallback diagnostics, and solver status cleanup.

### Changed

- `solver_status()` now reports only the authoritative MILP/Beam smart solver backend fields instead of also returning legacy Node bridge fields.

### Fixed

- Fixed `_drain_events()` so repeated or stuck event queues refresh career state instead of returning with unresolved `unchecked_event_array` entries.
- Fixed event-drain recovery to avoid recursively draining the same stuck event queue after a forced state refresh.
- Removed a duplicate unreachable mandatory-race failure raise in `_race()`.

## [Pre Icarus v5.3] - 2026-06-11

### Added

- Added a Diagnostics solver backend indicator showing whether the default Smart Race Solver backend is MILP or Beam.
- Added backend solver status fields for `active_backend`, `active_backend_label`, `milp_available`, and `beam_available`.
- Added tests for the solver backend status UI and additional race 214 recovery paths.

### Changed

- Moved Training Settings, Racing Settings, and Scenario Overrides to the first Setup content row above team slots and Preset Configuration.
- Updated the Trackblazer solver status display to report the actual MILP/Beam smart backend instead of the legacy Node bridge status.

### Fixed

- Recovered from API 214 errors during `race_entry`, initial `race_start`, race-progress `race_start`, race-progress `race_end`, and race-progress `race_out` instead of allowing those paths to crash.
- Removed a duplicate unreachable `return out` in the race runner.


## [Pre Icarus v5.2] - 2026-06-11

### Fixed

- Treated API result code 214 as a recoverable session/state desync instead of an immediate runner crash.
- Wrapped race and race-progress execution paths in the same recovery flow used by event and command actions.
- Recovered from result code 214 during post-race event draining by refreshing career state instead of stopping the run.
- Added result-code parsing for 214 in runner debug summaries.

### Added

- Added regression tests for API 214 recovery during race-out event handling.
- Added documentation for recoverable API error handling.

## [Pre Icarus v5.1] - 2026-06-10

### Added

- Added this consolidated `CHANGELOG.md` as the single release-history file for future updates.
- Added a `docs/` folder with feature documentation for the implemented systems that were previously scattered across release-note fragments.
- Added documentation for master-data export integration, TP restore selection, career history, smart training, guest-parent UI behavior, Smart Race Solver backends, skill-profile compatibility, Trackblazer item economy, Trackblazer decision safety, Trackblazer native scoring/race selection, Trackblazer event scoring, and setup/settings UI windows.

### Changed

- Consolidated the previous root-level release fragments into one consistent changelog structure.
- Moved feature explanations into dedicated Markdown documents under `docs/`.

### Removed

- Removed legacy root-level changelog/release-note fragments after their contents were consolidated.

## [Pre Icarus v5.0] - Date not recorded

### Added

- Added the setup settings window system with three buttons: Training Settings, Racing Settings, and Scenario Overrides.
- Added modal windows for training, racing, and Trackblazer scenario configuration.
- Added draggable priority editor modals for General Prioritization, Event Choice Prioritization, and Summer Training Prioritization.
- Added a manual SAVE button beside NEW and DEL in Preset Configuration.
- Added backend preservation for `mant_config` so settings persist across preset save/load.
- Added Trackblazer item-economy rules ported natively from the reference automation policy: shop priority retune, Charm-aware energy behavior, greedy energy recovery, Royal Kale Juice/cupcake pairing, and race-item conservation.
- Added Trackblazer P1 decision safety: irregular training gates, action-history race-chain awareness, low-energy race safety, and Reset Whistle rescue restrictions.
- Added Trackblazer P2 native decision scoring: near-rainbow anticipation, training-level weighting, summer priorities, race sorting by rival/distance/surface/grade/fans, and smart-solver train-turn protection.
- Added Trackblazer P3 event-choice scoring: stat/skill-point/energy/mood/bond/status reward parsing, event stat priority, energy-priority mode, and richer event traces.

### Changed

- Moved Training Settings, Racing Settings, and Scenario Overrides above Preset Configuration.
- Removed the redundant Bot Settings heading.
- Made Racing Settings the sole UI location for race running-style configuration.
- Replaced inline priority chips with modal drag-and-drop priority editors.
- Updated preset serialization to preserve Trackblazer plans, locks, priority settings, event settings, racing preferences, and scenario override fields.
- Updated full test discovery so the Smart Race Solver test accepts either the MILP backend or beam fallback label depending on installed dependencies.

### Removed

- Removed the old Running Style dropdown from Preset Configuration.
- Removed the duplicate Running Style control from Skill Configuration.
- Omitted OCR-only Training Analysis Validation and YOLO Stat Detection controls because Pre Icarus uses native game payloads, not OCR/screen detection.

### Fixed

- Fixed settings persistence for `mant_config` values.
- Fixed environment-sensitive Smart Race Solver test behavior when SciPy selects the MILP backend.

## [Pre Icarus v4.9] - Date not recorded

### Fixed

- Fixed crashes when generated trainee skill profiles supplied scalar `card_id` values instead of iterable `card_ids` values.
- Updated skill profile matching to safely accept list, tuple, set, string, scalar, or missing card ID values.
- Added unit coverage for scalar card ID profile matching.

## [Pre Icarus v4.8] - Date not recorded

### Added

- Added an optional SciPy MILP backend for the Smart Race Solver.
- Added MILP constraints for binary race decisions, one race per turn, manual race locks, manual train locks, max consecutive racing streaks, summer penalties, aptitude filtering, and race reward/cost objectives.

### Changed

- Smart Race Solver now tries the MILP backend first when SciPy is available, then falls back to beam search if SciPy is missing or the model is infeasible.
- `requirements.txt` includes `scipy>=1.11`.

### Notes

- Epithet variables and full matcher constraints were noted as future work in the original source note.

## [Pre Icarus v4.7] - Date not recorded

### Added

- Added a dependency-free Smart Race Solver beam backend for Trackblazer/MANT race planning.
- Added Smart Race Solver and Manual Selection UI modes.
- Added Apply Smart and Apply Manual actions.
- Added staged manual selections so manual race choices are not applied until confirmation.

### Changed

- Ported the useful reference solver behavior into `career_bot/trackblazer.py` without external automation APIs or screen automation dependencies.

## [Pre Icarus v4.6] - Date not recorded

### Fixed

- Fixed guest-parent hover popups by binding guest cards to the same `.sparks-tooltip` system as owned parents.
- Added delegated hover/focus handling on `#guest-parent-grid` so popups survive refresh and re-render.
- Added fallback popup content when guest entries have basic character data but no factor data.
- Removed pure friend support card rows from guest-parent results.

## [Pre Icarus v4.5] - Date not recorded

### Added

- Added guest-parent hover popups using the existing owned-parent spark tooltip system.
- Added keyboard-focus support for guest-parent popups.

### Changed

- Reused existing viewport-safe tooltip positioning and popup styling instead of creating a separate popup system.

## [Pre Icarus v4.4] - Date not recorded

### Added

- Added smarter training behavior that values rainbow/friendship training when high-bond deck partners are present.
- Added visible `rainbow xN` text in command reasons.
- Added preset tuning knobs for rainbow training behavior: `rainbow_training_bonus`, `rainbow_training_stack_bonus`, `rainbow_partner_value`, and `allow_full_hp_wit_rainbow`.

### Changed

- Wit training is no longer selected at full HP by default because it can waste its HP recovery value.
- Tightened Resume Career / Stop / Sync footer spacing.

### Fixed

- Fixed Career History button binding with a more robust DOM lookup.
- Improved guest-parent normalization by collapsing duplicate API paths, filtering likely owned/veteran trained characters, and ignoring unrelated directory/scenario arrays.

## [Pre Icarus v4.3] - Date not recorded

### Added

- Added the Career History UI beside Setup, Accounts, and Diagnostics.
- Added a current-session Career History modal.
- Added backend endpoint `GET /api/career/history`.
- Added completed-career recording from runner snapshots after successful runs.

### Changed

- Removed the lower duplicate SETUP button above Run/Stop/Sync.

### Notes

- Career History is stored in process memory only and clears when `python main.py` is closed or restarted.

## [Pre Icarus v4.2] - Date not recorded

### Added

- Added a top-bar TP restore selector beside the TP resource UI.
- Added Toughness and Carats restore buttons.
- Added `tp_restore_currency` and `tp_restore_mode` to the career-start payload.
- Added backend support for `tp_restore_mode` as an alias.

### Changed

- The selected TP restore option is saved in localStorage.
- Backend TP restore messages now say Carats instead of Carrots.

### Notes

- If Toughness is selected but unavailable, the backend can safely fall back to Carats.

## [Unversioned project notes] - Date not recorded

### Added

- Added extended master-data integration for `master.mdb` exports.
- Added official-data exports for race planner data, skill weighting, trainee profiles, generated trainee skill profiles, support cards, succession data, MANT shop data, and source table references.
- Added runtime integration points for the race planner, weighted skill system, MANT shop optimizer, trainee profiles, and inheritance/guest-parent data.

### Changed

- Master-data exports are additive and remain backward compatible with legacy generated files.
- Missing master-data tables are skipped instead of failing generation.

### Pre Icarus v5.43 Local LLM enable-state hotfix
- Fixed Local LLM Enable checkbox appearing to undo itself after saving.
- The Local LLM card now hydrates only from `/api/ai/local-llm/latest` instead of stale AI dashboard snapshots generated during previous training runs.
