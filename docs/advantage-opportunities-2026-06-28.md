<!-- Generated 2026-06-28 via 13-agent advantage-hunt workflow (wf_ea0e0836-c13): 8 angle-investigators -> synth -> 3 adversarial verifiers -> editor. 64 raw ideas, 18 corrections, 26 missed-items folded in. -->

> REFRAME (2026-06-28): the user DROPPED android stat-gap parity as a goal. Ignore the "close ~190k vs android" framing in the baseline line below and the "android-parity lever" wording on the epithet item; read every magnitude as a STANDALONE advantage (win-rate / fans / throughput / safety on its own merit), not as catching up to android. The epithet opportunistic term (1.1) is DEPRIORITIZED: its one measured sim was a LOSS, so it is a risky A/B experiment, not a recommended change.

# Icarus — Advantage Opportunities (Final)

**Baseline:** ~636k fans / 41 races / 85% win per career → reference "android" solver ~826k / 39 races / 95%. Goal: close ~190k fans / ~10 win-points.
**Magnitudes are per-career unless noted.** Effort S/M/L. Every item carries grounding, magnitude+confidence, feasibility, and an explicit "already present?" line.
**This is a read-only audit.** All file:line groundings were re-verified against the live tree at `C:\Icarus\Icarus\Icarusv2.1 (Dev)` (note: the solver-weights file is `career_bot/trackblazer.py`; the engine is `career_bot/scenarios/mant_trackblazer.py`).

---

## TOP 5 HIGHEST-LEVERAGE ADVANTAGES

| # | Advantage | One-line case | Magnitude | Effort |
|---|-----------|---------------|-----------|--------|
| **1** | **Revive `single_mode_npc` extractor** (§1.2) | Opponent / win-prob model is DEAD (`data/single_mode_npc_core.json` is `[]`); add one table name to `DIRECT_TABLES` and an entire opponent-aware tier (§3) lights up. | **+3–5% win, +20–50k fans** (med-high) | **S** (1 line) |
| **2** | **A/B policy-testing harness** (§5.9) | The meta-tool. The epithet term's prior sim showed a *fan loss*, so it must be A/B'd, not blind-flipped — and the same harness retires every other "tune-it" guess with evidence. | unlocks safe tuning of all below; could surface 10–20k of tuning (med) | **M–L** |
| **3** | **Epithet opportunistic MILP term — tune via the harness** (§1.1) | Most-cited stat lever; the *opportunistic* term is gated OFF (correct grounding) while base epithet scoring is ON. Lifting `epithetValue` + the opportunistic term is the android-parity lever — but gated behind #2 because one documented sim went 390k→332k. | +30–90k fans IF tuned right; **net-negative if blind-flipped** (med) | S to flip, but **must A/B** |
| **4** | **Wire `recommended_stat_builds` into the solver** (§1.3) | Per-trainee Game8 targets are loaded but *zero* solver references exist; niche trainees burn budget chasing generic 1200-everything. | +5–15k fans (med) | **S–M** |
| **5** | **Activate the logged item/event/policy models** (§5.1 + §5.2) | Rich models are computed and written to `uma_runtime/ai/` but never read; `enable_live_policy_assistance` defaults False and the *hierarchical* hint is dashboard-only. Pure "turn it on" leverage. | +1–3% (~5–20k) policy + 5–15k item/event (med) | **S** (policy) / **M** (item/event) |

**Honesty split:** #1 and #4 are confirmed grounded data-revival/wiring wins (low risk). #5 is wired-but-disabled (low risk). #3 is high-magnitude but **risky** and must be gated behind #2. #2 is infrastructure, not direct fans.

---

## 1. TOP LEVERS

### 1.1 Epithet / Set-Bonus MILP term — tune the opportunistic term (don't blind-flip)
The catalog's conflict is **RESOLVED and the resolution is correct** — these are TWO distinct mechanisms (verifier-confirmed across all three runs):
- **Base epithet-hit scoring is ON:** `epithetValue=1.0` (trackblazer.py:99), `forcedEpithetValue=500.0` (:106), applied every race at **:685–687** (catalog's "1245–1247" was the *hint-reward* path at :1245–1247; both confirmed live).
- **Opportunistic-completion MILP term is OFF:** gated behind `weights.get("enableOpportunisticEpithets", False)` at **trackblazer.py:1510** (comment at :1501 confirms "DEFAULTS off"). Mechanism fully implemented (`_opportunistic_epithet_milp_vars`, structurally intact).
- **The documented regression is a LOSS, not a gain:** enabling the opportunistic term drove one sim 390k→332k. This is the catalog's own data and the verifiers confirm it — so the lever is *measured tuning of `epithetValue`* (clamp range 0–50 at :310) plus the opportunistic term, **not** a default flip.
- **Grounding:** trackblazer.py:99, 106, 310, 317, 685–687, 1501, 1510; config flags `trackblazer_target_epithets`/`trackblazer_forced_epithets`; memory `icarus-stat-gap-investigation`.
- **Magnitude:** +30–90k fans IF tuned correctly; **net-negative if blind-flipped** (med confidence).
- **Effort:** S to change, but requires §5.9 to test. **Feasibility:** in-hand.
- **Already present?** Mechanism YES (opportunistic term gated off; base scoring on). The *advantage* (correct tuning) is NOT realized. **Do not blind-flip — gate behind §5.9.**

### 1.2 Revive `single_mode_npc` extractor — opponent/win-prob model is DEAD ⭐
**The clearest confirmed bug. Unanimous, and re-verified live this session.**
- `data/single_mode_npc_core.json` literally contains `[]` (2 bytes / 0 rows — confirmed by direct read).
- `synthesize_single_mode_npc_core()` (master_data.py:1203) calls `master_rows(master_data, "single_mode_npc")` at **:1216**, but `"single_mode_npc"` is **absent from `DIRECT_TABLES`** (master_data.py:8+) so it returns `[]`. The table itself exists in `master.mdb` (present in `master_table_catalog_core.json`).
- **Fix:** add `"single_mode_npc"` to `DIRECT_TABLES` (1 line). Join key `single_mode_npc_id` already lives in the populated `rival_races_core.json` (synthesizer at :1186 references it) — consumers are ready.
- **Grounding:** master_data.py:8+, 1186, 1203, 1216, 2203; data/single_mode_npc_core.json (`[]`); data/master_table_catalog_core.json.
- **Magnitude:** +3–5% win-rate, ~20–50k fan swing (avoid unwinnable fields + favorable-matchup selection). Med-high confidence.
- **Effort:** S. **Feasibility:** in-hand.
- **Already present?** NO (dead data). Unblocks ALL of §3. Consumer `tools/race_winnability_report.py` is complete and currently prints "Skipped: …not found" (verified).

### 1.3 Per-trainee recommended stat targets — wire into the solver
- `data/recommended_stat_builds.json` is loaded only by `recommended_stats.py`; **grep confirms ZERO solver references** (no calls from trackblazer.py / mant.py / character_profiles.py). Solver uses generic preset/hardcoded targets, so niche trainees (e.g. want Pow 800, not 1200) waste budget.
- **Fix:** wire `get_recommended_stats()` into the profile resolver → override `trackblazer_stat_targets` on profile match.
- **Grounding:** data/recommended_stat_builds.json; recommended_stats.py (`load_recommended_stats`/`get_recommended_stats`); character_profiles.py.
- **Magnitude:** +5–15k fans (med).
- **Effort:** S–M. **Feasibility:** in-hand (data + loader exist).
- **Already present?** NO (data + loader exist, unreferenced by decision logic). Pairs with the global `stat_targets_by_distance` work (memory `icarus-stattargets-retries-clocks`).

---

## 2. Decision / scoring improvements

### 2.1 Hard win-probability gate on near-impossible races (needs §1.2)
- `race_outcome_risk()` is a *soft* penalty only — a <30% race still nets positive. Add a hard gate: skip <15–20% races unless forced-epithet; cap consecutive-race count when the next 3 are all <25%.
- **Grounding:** race_intelligence.py (outcome harness); trackblazer.py `outcomeRiskWeight` + `_race_cost` penalty path.
- **Magnitude:** +15–35k fans (2–5%); multiplies once §1.2 lands (opponent-aware risk). Med.
- **Effort:** M. **Feasibility:** derivable.
- **Already present?** PARTIAL — soft penalty exists, hard block missing.

### 2.2 Skill-condition–aware selection (evaluate, don't just store)
Two facets, both verifier-confirmed as MAJOR missing:
- **(a) Activation-condition filtering:** `skill_condition_core.json` (~605 skills, ~99% carry `distance_rate/order_rate/running_style` gates) is loaded (skills.py:386) and used for *static* style/distance weighting, but the picker never evaluates the `condition_rate` against the trainee's actual final race schedule — a wrong-condition gold (e.g. `running_style==late` on a front-runner) is a dead buy.
- **(b) Effect-magnitude differentiation:** `float_ability_value` + per-level coef are extracted into `skill_condition_core.json` but scoring treats same-category golds as equal (grade proxy only). Prefer high-magnitude/high-coef skills.
- **Grounding:** skills.py:386, 1040 (`_skill_smart_score`), 1456; master_data.py (skill extractor); data/skill_condition_core.json.
- **Magnitude:** +0.5–1% win + 2–5% skill-grade (med-low).
- **Effort:** M. **Feasibility:** in-hand (data present, evaluator missing).
- **Already present?** PARTIAL — stored + statically weighted, never schedule-evaluated.

### 2.3 Skill-condition lookahead in the TRAINING scorer
- Training scorer is myopic — no peek at upcoming skill unlocks (e.g. a skill unlocking at Power 400 with current 380 makes Power training higher-EV than the raw ratio). Add N-turn skill-unlock lookahead. **No skill-condition reference exists in `mant_trackblazer.py` (verifier-confirmed).**
- **Grounding:** skills.py SkillCondition; career_bot/scenarios/mant_trackblazer.py TrainingScorer.
- **Magnitude:** +5–20k fans (speculative).
- **Effort:** M. **Feasibility:** derivable.
- **Already present?** NO.

### 2.4 Aptitude-match veto in the race-decision gate
- `race_performance_rates_core.json` (distance/ground/style/motivation multipliers) is generated but the train/race/rest gate never asks "is this trainee well-matched for this race?" — aptitude lives in a separate RacePlanner not integrated into the scoring veto.
- **Grounding:** data/race_performance_rates_core.json; mant_trackblazer.py (no aptitude veto); races.py (RacePlanner separate).
- **Magnitude:** +1–2% win (med-low). **Effort:** M. **Feasibility:** in-hand.
- **Already present?** PARTIAL — rate tables ready, veto missing. Overlaps §2.1.

### 2.5 Auto-populate `preferred_distances` from trainee aptitude
- `distancePreferenceBonus=6.0` (trackblazer.py) materially boosts matched races, but `preferred_distances` defaults empty (user-config) so most users never activate it. Seed from aptitude.
- **Grounding:** trackblazer.py (distance-preference bonus path); races.py (no auto-population).
- **Magnitude:** +5–12k fans (0.8–2%, med-low). **Effort:** M. **Feasibility:** derivable.
- **Already present?** PARTIAL — logic complete, auto-seed missing.

### 2.6 Style/positioning scoring from opponent aptitudes (needs §1.2)
- `single_mode_npc` records carry per-NPC running-style aptitudes; `style_adaptation.py` uses only player aptitude + history. Add field-style awareness (run early if field is late-heavy; flag style-mismatch races as low-win even with stat superiority).
- **Grounding:** master_data.py (npc extractor); style_adaptation.py.
- **Magnitude:** +1–2% win (low, high variance). **Effort:** M. **Feasibility:** derivable.
- **Already present?** NO (player-only today; opponent-style input missing).

### 2.7 Stat-cap cascade instead of hard-zero (minor)
- Near-cap priority stats hit the effective-cap gate and are hard-zeroed (mant_trackblazer.py:~504–511) rather than cascading to the next-priority stat → wasted rest in turns 60–73. **Caveat (verifier):** no evidence this differs from android behavior — treat as a hypothesis to A/B, not a confirmed gap.
- **Grounding:** career_bot/scenarios/mant_trackblazer.py:~504–511.
- **Magnitude:** ~5–15k fans (low-med, unconfirmed). **Effort:** M. **Feasibility:** derivable.
- **Already present?** PARTIAL — gate zeros, no reclassification.

### 2.8 Level-boost / bond-weight constant tuning (minor knobs)
- `LEVEL_BOOST_FACTOR` yields ~1.05x for rank-1@L3 (likely conservative); `bond_weight≈0.15` caps rainbow-friendship at 15% of score. Both are A/B candidates, not confirmed gaps.
- **Grounding:** career_bot/scenarios/mant_trackblazer.py (LEVEL_BOOST_FACTOR, REL_WEIGHT_WITH_BARS).
- **Magnitude:** +3–8k (level) / +2–6k (bond), low. **Effort:** S. **Feasibility:** in-hand.
- **Already present?** PRESENT but conservative defaults.

---

## 3. Opponent / win-prob & race modeling — ALL GATED ON §1.2

### 3.1 Empirical win-prob model + ROI measurement (zero new infra)
- `tools/race_winnability_report.py` runs Analysis A (player strength→outcome) + B (player-vs-rival gap→outcome, AUC-scored). **Analysis B is skipped today purely for lack of data** (verified: prints "Skipped … not found"). Gives calibrated signals + tells whether a model helps *before* building one.
- **Grounding:** tools/race_winnability_report.py.
- **Magnitude:** unlocks measurement; feeds 3.2/§2.1. **Effort:** S (run it post-fix). **Already present?** Complete, data-starved.

### 3.2 Wire opponent-gap scoring into race reranking
- `race_intelligence.py` tracks per-program win/loss but has no opponent-gap input; `_smart_race_score` (trackblazer.py) shows **no `field_strength` computation** (verifier-confirmed). Compute `field_strength = mean(npc.speed+npc.pow)`, score entry/style/position by gap.
- **Grounding:** race_intelligence.py; trackblazer.py `_smart_race_score`; master_data.py npc extractor.
- **Magnitude:** +2–3% win (med). **Effort:** M. **Already present?** Harness yes, gap-scoring no.

### 3.3 Opponent-strength–gated retry/clock logic
- Retry only when (stat-cap not reached) AND (field weak). Strong fields are low-ROI *and* the higher detection-risk action to retry.
- **Grounding:** mant_trackblazer.py clock-retry logic; runner.py retry path.
- **Magnitude:** prevents ~5–10% of low-ROI retries → detection-safety + minor fan. **Effort:** M. **Already present?** Retry yes, strength-gate no. Synergizes with §7.3.

---

## 4. Data & asset mining
*(Sniffer + cracked asset decryption are in-hand, so "needs-data" via those is achievable.)*

### 4.1 Inspect `single_mode_chara_effect` — possible per-trainee passives
- **DOWNGRADED per verifier:** the table exists in `master.mdb`, but the claim that it's unextracted *and* carries solver-blind passive signal is **unverified**. Treat as "inspect first," not a confirmed lever.
- **Grounding:** data/master_table_catalog_core.json; master_data.py DIRECT_TABLES.
- **Magnitude:** +0.5–2% IF signal real; 0% if redundant (low). **Effort:** M. **Feasibility:** derivable.
- **Already present?** Unknown — must inspect before proposing as a lever.

### 4.2 Race course geometry (corners/lanes/pacing zones)
- `race_course_set` exposes `turn` (corners), `float_lane_max`, `fence_set`, `inout`, `course_set_status`. Synthesis keeps only distance/ground/track_id, discarding geometry. Enables pacing strategy + lane-block detection + condition adaptation.
- **Grounding:** data/master_table_catalog_core.json; master_data.py course synthesis; data/race_planner_core.json.
- **Magnitude:** +1–3% win / ~10–30k fans on geometry-sensitive races (low-med). **Effort:** M. **Feasibility:** in-hand (table loaded, fields dropped).
- **Already present?** PARTIAL — geometry fields dropped. **Do this before §4.5** (same value, far less effort).

### 4.3 Skill upgrade-chain awareness
- `skill_upgrade_groups_core.json` (219K, base→rarity-3/unique chains) — **grep confirms zero `skill_upgrade` references in skills.py.** Can't favor low-rarity skills with strong upgrade paths.
- **Grounding:** master_data.py upgrade-group extractor; data/skill_upgrade_groups_core.json.
- **Magnitude:** +1–3% win / ~10–30k fans (low-med). **Effort:** S. **Feasibility:** in-hand.
- **Already present?** Extracted, unused.

### 4.4 Succession relation-pair–aware parent selection
- `succession_scoring_core.json` exposes `relation_ranks`/`relation_points`; `successor_relation_member` lists cohorts (Mejiro siblings, etc.). Two parents in the same relation get +10–20% rare-factor pass odds. Parent selection (mant.py / ai_trainer.py) shows no relation weighting (verifier-confirmed).
- **Grounding:** succession_scoring_core.json; succession_core.json relations.
- **Magnitude:** ~1 extra inheritance star → +1–2% stat / faster sparks (cross-career, med). **Effort:** M (a simple "prefer same-relation parents" override is near-zero infra). **Feasibility:** in-hand.
- **Already present?** PARTIAL — data extracted, no pair-weighting. (Relates to §8.2.)

### 4.5 Course 3D-mesh mining (corner radius / elevation)
- UnityFS course meshes could yield physics-grade corner radius + elevation. Decryption cracked (memory `icarus-icon-extraction`, `icarus-deep-capabilities`).
- **Grounding:** decryption capability (memory); no extractor in tools/.
- **Magnitude:** +2–5% win on technical courses but **low** confidence (many careers stamina-limited → pacing moot). **Effort:** L. **Feasibility:** derivable, unvalidated payoff.
- **Already present?** NO. **Recommend §4.2 first.**

---

## 5. AI / ML pipeline
*Theme: infra built, logging rich, the lever between logs and live decisions is barely turned.*

### 5.1 Enable live-policy assistance (gated) + use the hierarchical hint
- Hints ARE wired but `enable_live_policy_assistance` defaults **False** (ai_trainer.py:57; early-return at :1581). Also the live path uses the *flat* hint while the stronger `hierarchical_race_program_hint` (ai_advisor.py) is **dashboard-only** — a near-1-line swap.
- **Grounding:** ai_trainer.py:57, 1581; ai_advisor.py (flat vs hierarchical); trackblazer.py:543 hint call-site.
- **Magnitude:** +1–3% (~5–20k) on 30+ race careers (med). **Effort:** S (flip default + UI toggle + hierarchical swap). Gate on existing min-predictions/coverage/shadow-precision thresholds.
- **Already present?** PARTIAL — wired but disabled; hierarchical built but not called.

### 5.2 Consume the item & event models (computed, never read)
- `item_effectiveness_table`, `event_outcome_table`, `event_value_model` are built by `ai_trainer.py` and written to `uma_runtime/ai/`, but **grep for `load_item_effectiveness`/`load_event_value` in runner.py/trackblazer.py returns zero** (verifier-confirmed). All item/event decisions stay heuristic.
- **Grounding:** ai_trainer.py model builders/writers; runner.py/trackblazer.py (no load).
- **Magnitude:** +5–15k fans (10–20% better item/event ROI, med; ~10 careers to populate). **Effort:** M. **Already present?** FULLY logged, ZERO integration.

### 5.3 Auto-fit calibrator + adaptive confidence threshold
- Isotonic calibrator works but needs a manual "Fit" click; `confidence_threshold=0.65` never adapts to ECE. Auto-fit every N careers; raise threshold when ECE<0.05, lower when >0.12.
- **Grounding:** calibration.py; ai_advisor.py; ai_trainer.py:57.
- **Magnitude:** +1–3% variance reduction (med). **Effort:** S. **Already present?** PARTIAL.

### 5.4 Regret-replay → weight auto-tuning (close the loop)
- `regret_replay.py` computes decision-regret + hindsight stat-gaps but never tunes weights — `suggested_config_tuning` is rule-based and ignores the regret signal. Gradient-style: consistent 2nd-best race picks → raise `raceValue`; missed epithet branches → raise `epithetValue`.
- **Grounding:** regret_replay.py; ai_trainer.py tuning path.
- **Magnitude:** +1–3% per cycle (~5–15k over cycles, med). **Effort:** M. **Already present?** Infra only, no feedback loop.

### 5.5 Skill-ROI learned model
- Every purchase logged (id/cost/turn/stat-delta) but no `(skill, trainee, stat-phase)→gain/cost` model; picker hardcodes `recommended=190` (skills.py). Learn per-trainee skill ROI.
- **Grounding:** ai_dataset.py turn_decision_records; skills.py (hardcoded recommended).
- **Magnitude:** +2–5% stat-efficiency (~8–20k fans, med; ~10 careers). **Effort:** M. **Already present?** Data captured, no model. (Overlaps §8.5.)

### 5.6 Preset×trainee affinity recommender
- `build_preset_trainee_confidence` computed but **dashboard-display only**. Recommend the best preset for a trainee from history; reduce sub-600k outliers.
- **Grounding:** ai_trainer.py:1042+.
- **Magnitude:** +5–15k fans (variance reduction, med). **Effort:** M. **Already present?** PARTIAL — computed, not consumed.

### 5.7 Style-adaptation auto-recommendation
- `style_adaptation_model` computed + shadow-validated but never recommends live style switches (to unlock high-value/forced-epithet races).
- **Grounding:** ai_trainer.py style-model path; style_adaptation.py.
- **Magnitude:** +1–3k avg (15–30k when applicable, ~5–10% of careers; low-med). **Effort:** M. **Already present?** Infra only.

### 5.8 Empirical stat-gain *correction* table (for planning)
- API returns exact per-command gains (captured in `ai_dataset._stats_from_turn_payload`) but they're never aggregated into a per-trainee `(command,mood,fatigue,item)→actual_gain` lookup to correct *theoretical lookahead* estimates. (Not the moot "exact-gain scorer" — live gains are already known; this is predictive for planning.)
- **Grounding:** ai_dataset.py:364–398.
- **Magnitude:** +10–20k fans if training order adapts (med). **Effort:** M. **Already present?** Data present, no model.

### 5.9 A/B policy-testing harness ⭐ (the meta-tool)
- No framework to run N careers under config variants + statistically compare. Build variant storage + headless executor (runner plumbing exists) + Bayesian comparison.
- **Grounding:** regret_replay.py; ai_trainer.py; runner.py (execution plumbing).
- **Magnitude:** operational; could surface 10–20k of tuning. **Effort:** M–L. **Feasibility:** needs-data (design schema). **Already present?** NO. **Build this before §1.1** — it de-risks the epithet blind-flip and validates every "tune-it" hypothesis (§2.7, §2.8, §1.3).

### 5.10 Epithet-ROI oracle (novel)
- Build `(epithet_combo, trainee, stat-priority)→expected stat gain`. Existing `epithet_confidence` tracks *success*, not *ROI*.
- **Grounding:** ai_dataset.py career_summary; ai_trainer.py epithet-confidence path.
- **Magnitude:** +15–30k fans (skip low-value epithet branches, med, needs-data). **Effort:** M. **Already present?** NO. Directly informs §1.1 tuning.

---

## 6. Throughput, efficiency & safety

### 6.1 API circuit breaker for sustained 208 saturation (UmaAuto port-back)
- Exponential backoff exists (`uma_api/client.py` ~0.8·2ⁿ, up to 6 retries) but **NO circuit breaker** — and the 208 attempt counter resets *per call()*. A sustained 208 burst across calls burns the budget and stalls/crashes the career. Add a time-windowed `_api_saturation_state` (≥3 consecutive 208s in 10s → 30–60s longer-sleep). UmaAuto has this (memory `icarus-umaauto-comparison`).
- **Grounding:** uma_api/client.py (backoff path); runner.py.
- **Magnitude:** +15–25% careers/hr in peak load + multi-account fairness + detection-safety (med). **Effort:** M. **Already present?** PARTIAL — retries yes, cross-call breaker no.

### 6.2 URA-Finale finalization for loop runs ⭐ (lowest-effort throughput/safety)
- `finalize_single_runs` exists (runner.py:527 default **False**, stored :551, gates the turn-77 early-exit at :843) but **multi-run loops never pass it** → turn-77 self-terminate forces a game timeout-close (looks like a crash). Pass `True` in the loop/manager start path (main.py loop init ~5407/5624 forward `getattr(req,...,False)`).
- **Grounding:** runner.py:527, 551, 843; main.py loop init; memory `icarus-umaauto-comparison`, `icarus-issue-batch-20260622`.
- **Magnitude:** +1–4% fans (final-race bonus) + cleaner exit (safety). **Effort:** S. **Already present?** PARTIAL — flag exists, loops don't set it. **One-line fix per loop call-site.**

### 6.3 Per-event processing jitter (anti-detection)
- `_drain_events` (runner.py) processes events back-to-back with **no per-event delay** (verifier-confirmed). Add `dna_sleep(5,50)` per event (~40–60 events/career → +0.2–3s total).
- **Grounding:** runner.py `_drain_events`; delay.py.
- **Magnitude:** +15–25% detection-safety vs event-speed analysis; ~0 throughput cost (med, safety). **Effort:** S. **Already present?** NO.

### 6.4 Per-endpoint / per-category pacing (anti-detection)
- Global `MIN_CALL_SPACING=0.14s` for ALL endpoints (uma_api/client.py:30–31). Human signature varies (race-setup slow, skill-shop rapid-fire). Add per-endpoint timing maps + category jitter.
- **Grounding:** uma_api/client.py:30–31; main.py call-spacing.
- **Magnitude:** +20–30% detection-safety; negligible throughput (med, safety). **Effort:** M. **Already present?** NO.

### 6.5 Per-account TP energy scheduling (multi-account)
- Manager (manager.py:256+) starts children sequentially and health-checks them, with **no cross-account TP awareness** — a TP-exhausted account idles while others have TP. Add a shared TP tracker + pause/resume queue reorder.
- **Grounding:** manager.py:256+; runner.py; uma_api/client.py TP path.
- **Magnitude:** +10–15% careers/day on 3–5 accounts (med). **Effort:** M. **Feasibility:** derivable (needs TP-state API integration). **Already present?** NO.

### 6.6 Skill/item multi-turn batching (minor) — LOW PRIORITY
- Single-turn batching exists; multi-turn buffering saves ~2–5 calls/career (~2%) — negligible vs turn delays.
- **Grounding:** uma_api/client.py batching; items.py; runner.py.
- **Effort:** M. **Already present?** PARTIAL. **Low priority.**

### 6.7 Parallel race execution — RULED OUT
- Race sim is server-side (`race_scenario` blob); can't parallelize without RE-ing the engine or a NN predictor. **Not feasible.** Listed to prevent re-proposal.

### 6.8 Saturation-adaptive pacing (novel, verifier-flagged)
- Beyond §6.1's breaker: feed a running 208-frequency window back into `delay.py` to auto-raise `MIN_CALL_SPACING` mid-run when saturation is detected — pure safety, zero retry burn, zero throughput loss when calm.
- **Grounding:** delay.py; uma_api/client.py.
- **Magnitude:** detection-safety, self-limiting (med). **Effort:** S–M. **Already present?** NO.

---

## 7. Economy / resource
*All within user doctrine (summer-only stats, turn-64 dump, no finale coins, over-racing intentional). Magnitudes modest by design.*

### 7.1 Vita reserve order — VERIFIED ALREADY CORRECT (catalog claim was inverted) ✅
- **DELETED as a lever.** `_usable_vita_counts` (items.py:1507–1515) iterates `ENERGY_CONSERVATION_ORDER=("Vita 20","Vita 40","Vita 65")`, decrements the **first available (smallest)** type, and breaks. That reserves the *smallest* and keeps the larger Vitas usable — which is **correct by design**. The catalog's "holds the wrong tier / reverse the sort" framing is inverted. No action.
- **Grounding (verified live):** items.py:1507–1515; trackblazer_rules.py:100.
- **Already present?** YES — correct. Do not "fix."

### 7.2 Promote Energy Drink MAX to tier-2 when owned
- EDM sits at tier-7 in the *shop/buy* ordering (trackblazer_rules.py:63) so it's rarely bought / wrongly dumped — yet the *use*-logic (`_smallest_sufficient_prerace_energy`, items.py) already prefers it pre-race in chain-pos {2,3}. The tension is buy-tier vs use-priority; make tier dynamic (→tier-2) when owned / consec-races expected.
- **Grounding:** trackblazer_rules.py:63; items.py use-logic.
- **Magnitude:** ~20–40 fans (low). **Effort:** S. **Already present?** Use-logic recognizes EDM; buy-tier static. *(Cross-check memory `icarus-late-item-rework`: EDM value already retuned 30→5 — verify no conflict.)*

### 7.3 Carat/clock retry race-value gate
- `retry_extra_races=true` retries ANY eligible G1/G2/G3 with no fan-delta/win-prob gate (runner.py). Add: retry only if `(fans_delta × win_delta) > carat_cost_equiv`.
- **Grounding:** runner.py retry policy; client.py carat path.
- **Magnitude:** ~50–150 fans (redirect 2–5 carats, low-med, needs carat fan-equiv). **Effort:** M. **Already present?** Retry complete, fan-gate absent. Synergizes with §3.3.

### 7.4 Conditional pre-finale coin reserve release
- The finale coin reserve is hard-locked turns 65–73 (items.py) assuming the finale shop stocks hammers. If the T72–73 snapshot shows no new hammers, release early for megaphones/anklets/scrolls. **needs-data** (does the finale restock?).
- **Grounding:** items.py finale-reserve path.
- **Magnitude:** ~15–30 fans IF finale rarely restocks (low). **Effort:** M. **Already present?** Reserve hard-coded, no shop-content check. *(Cross-check memory `icarus-save-items-lategame`: reserve was tuned 150→60 dump — verify the current live value before editing.)*

### 7.5 Consecutive-race pos-1 energy top-up — LIKELY NOT A BUG (deflated)
- **DOWNGRADED per verifier.** The gate is chain-pos {2,3} *by design* (items.py:469–480 comment): pos-1 has minimal punishment, pos-4+ is capped, so only {2,3} justify spending. The catalog's "pos-1 isn't rescued" framing is misleading and the 45–200 fans/batch is likely overstated. Treat as an A/B hypothesis only, not a fix.
- **Grounding:** items.py:469–480.
- **Magnitude:** unclear / possibly zero (low). **Effort:** S. **Already present?** Intentional design. *(Cross-check memory `icarus-late-item-rework`.)*

### 7.6 Anklet pre-conservation cap — RE-BASELINE BEFORE ACTING
- Cap (`trackblazer_anklet_max_stock=2`) is in place; the items.py:129–131 comment flags ~3 historical over-buys as a "P1" issue that **may already be mitigated** by later fixes. Re-verify against a live career log before treating as a lever.
- **Grounding:** items.py:129–136; trackblazer_anklet_max_stock default.
- **Magnitude:** ~5–10 fans (low). **Effort:** S. **Already present?** Cap present; the over-buy may be legacy doc, not a current bug.

---

## 8. Novel / wildcard angles

### 8.1 Pre-career deck/parent auto-optimization from Game8 setups
- `data/trainee_support_setups.json` (per-trainee MLB/budget/speed-wit/stamina decks) is **UI-only** (loaded for `/api/trainee/support-setups`; grep shows zero solver references). The android solver likely pre-selects parents/guests for mid-game synergy. Feed deck-scoring (aptitude-match + synergy-type count) into preset hydration / `career_start_recovery`. Compounds every training decision.
- **Grounding:** main.py `_load_trainee_support_setups` + `api_trainee_support_setups`; career_start_recovery.py; character_profiles.py.
- **Magnitude:** +20–40k fans (3–5 race swing equiv; **speculative**, needs A/B). **Effort:** M. **Already present?** NO (UI data only).

### 8.2 Succession-chain cross-career planning
- `succession_core.json` factors carry between careers, but each career is optimized in isolation (`presets.py` agenda field has no succession target). Plan career N's epithet/factor targets to set up N+1's inheritance baseline (compounding to higher caps).
- **Grounding:** succession_core.json; succession_scoring_core.json; presets.py:105–108.
- **Magnitude:** +20–40k fans on 2nd+ career; nil single-run (med). **Effort:** L (multi-module). **Already present?** NO. (Relates to §4.4.)

### 8.3 Skill-aware event-choice routing
- **GROUNDING CORRECTED:** the catalog's `EventChoicePicker` class does not exist; live event handling is `strategy._choice(event)` (mant Strategy, runner.py ~2371). The lever stands — event scoring is stat/energy/bond-centric and doesn't bias toward skill-enabling paths using `community_skill_tiers.json` + skill conditions — but it must be implemented in the mant Strategy choice path, not a nonexistent picker.
- **Grounding:** runner.py event-choice call-site → mant Strategy `_choice`; community_skill_tiers.json; event_effects.json (2509 events).
- **Magnitude:** +10–20k fans (enable 1 high-value skill earlier; **speculative**). **Effort:** M. **Already present?** NO.

### 8.4 Factor-aware race selection
- `factor_map.json` (~92K, 600+ factors) + factor rewards in `rival_races_core` are unused by race scoring (grep: trackblazer.py `factor` hits only a comment). Prefer races awarding bottleneck-stat factors → coordinate with §8.2.
- **Grounding:** data/factor_map.json; rival_races_core.json; trackblazer.py `_smart_race_score`.
- **Magnitude:** +20–40k fans / 2-career sequence (med, cross-career only). **Effort:** M. **Already present?** NO.

### 8.5 Skill-purchase race-outcome feedback loop
- Skill buyer is purely static `smart_score`; `ai_dataset.py` records `skill_buy_attempts` but activation frequency (which skills actually fired in won races) is never tracked or looped back to deprioritize never-used skills.
- **Grounding:** skills.py buyer; ai_dataset.py logging.
- **Magnitude:** +10–25k fans (1.5–4%, med, needs-data). **Effort:** L. **Already present?** Logging yes, loop no. (Overlaps §5.5.)

### 8.6 Adaptive timing-DNA pacing (safety wildcard)
- `delay.py` generates a per-install `_dna_seed` **once** and reuses it for all runs — no per-session re-seed, no adaptive backoff. UmaAuto's "TimingDNA" is more sophisticated. (Umbrella over §6.3/§6.4/§6.8.)
- **Grounding:** delay.py; memory `icarus-umaauto-comparison`.
- **Magnitude:** account survival (~5–10% fewer losses; **speculative** — detection logic unknown; over/under-pacing both risky). **Effort:** M. **Already present?** Basic per-install jitter only.

---

## Corrections applied vs the synthesized catalog
- **§7.1 (Vita reserve) DELETED as a lever** — verified the smallest-first order is *correct by design* (items.py:1511 breaks on the first/smallest type, reserving it and keeping larger Vitas usable). The catalog's "wrong tier / reverse the sort" was inverted.
- **§7.5 (pos-1 top-up) DEFLATED** — chain-pos {2,3} is intentional; not a bug, magnitude overstated.
- **§7.6 (anklet over-buy) RE-BASELINED** — likely already mitigated; verify against a live log first.
- **§8.3 grounding CORRECTED** — `EventChoicePicker` doesn't exist; the real call-site is the mant Strategy `_choice` path.
- **§4.1 DOWNGRADED** — `single_mode_chara_effect` signal is unverified; "inspect first," not a confirmed lever.
- **§1.1 magnitude framing TIGHTENED** — its only measured sim was a *loss*; recast as gated-tuning, not a flip.
- **§1.1/§5.1/§6.2 line-number drift FIXED** — base epithet applied at trackblazer.py:685–687 (not 1245–1247, which is the hint path); finalize gate at runner.py:843; policy default at ai_trainer.py:57.
- **Verifier false-positive NOTED:** community-tier scoring *is* used — `_community_tier_score` (skills.py:564) is called inside `_skill_smart_score` (:1040). The "SS skills +20% multiplier" idea is therefore a *tuning* of an existing term, not new wiring; folded into §2.2 rather than listed as missing.

## Folded-in "missing" advantages from verifiers
All verifier-flagged gaps are incorporated: stat-cap cascade (§2.7, with android-parity caveat), skill upgrade-chains (§4.3), opponent-gap reranking (§3.2), multi-account TP scheduling (§6.5), succession relation-pairs (§4.4), skill-condition lookahead (§2.3), skill-condition activation eval + effect-magnitude (§2.2a/b), hard win-prob veto (§2.1), aptitude veto (§2.4), opponent-style scoring (§2.6), empirical stat-gain correction (§5.8), epithet-ROI oracle (§5.10), skill-aware events (§8.3), skill activation feedback (§8.5), cross-call 208-burst breaker + saturation-adaptive pacing (§6.1/§6.8), loop finalization 1-line fix (§6.2), per-endpoint human-signature pacing (§6.4), dynamic energy/coin reserve (§7.4 caveat).

---

## Recommended sequencing
1. **§1.2 single_mode_npc 1-line fix** (S) — unanimous, lowest-risk, unblocks all of §3.
2. **§6.2 loop finalization** (S, ~1 line/site) + **§5.1 enable policy + hierarchical swap** (S) — pure "turn it on" wins.
3. **§1.3 recommended-stats wiring** (S–M) + **§5.2 activate item/event models** (M) — high data-leverage.
4. **§5.9 A/B harness** (M–L) — build *before* §1.1.
5. **§1.1 epithet opportunistic term** — A/B via the harness; tune `epithetValue`. Feed by §5.10.
6. **§6.1 circuit breaker** + **§6.3/§6.4/§6.8 anti-detection pacing** (UmaAuto port-backs).
7. Modeling/economy refinements by magnitude×feasibility.

**Two highest-confidence, lowest-effort confirmed wins:** §1.2 (dead-data revival, confirmed bug, file is literally `[]`) and §6.2 (loop finalization, one line per call-site). **Highest-magnitude-but-risky:** §1.1 (epithet) — gate behind §5.9, never blind-flip.