<!-- 2026-06-28 9-agent workflow wf_0e496164-d29: 5 angles -> synth -> 2 adversarial verifiers. Sheet = C:\Icarus\Icarus\_sheet_csv (community Uma Musume Skills Spreadsheet). -->

# Icarus — Skill Purchase System: Sheet Comparison + Redesign

## Executive Take

**Partly — yes for fixing real SP leaks, no for a step-change in fans.** The scraped community sheet supplies exactly the five signals the bot structurally cannot express today (Score/SP efficiency, per-style tiers, per-distance tiers, a Team-Trials-vs-PvP split, and a condition shorthand) across ~98.5% of named skills vs the current ~6.3%. Adopting it — plus a schedule-aware condition gate the bot can build from data it *already loads* — will measurably cut wrong-context "dead buys" and over-pays. **The one caveat that governs everything:** the sheet ranks skills for Team Trials / PvP / Champions Meeting (finished umas racing other players), not single-mode career fan-farming vs fixed NPCs — so only the career-transferable slices (Team Trials rank, Score/SP, style/distance/condition fit) may be used; PvP rank, the `Why?` column, and debuff emphasis are advisory or noise. It still won't model fans-per-SP or cross-turn SP budgeting, so expect *fewer wasted buys*, not a new ceiling.

---

## 1. How the bot's skill purchase works today (pipeline, every lever, weaknesses)

### Pipeline (`career_bot/skills.py`, class `SkillBuyer`)

`buy()` (skills.py:687) is a guarded multi-stage flow:

1. **Threshold / hoard gate** (skills.py:699-727). Master toggle `enable_skill_point_check` (default True, :699); SP floor `learn_skill_threshold` (default 888, :706) — at/below it, no buy. Two multi-turn overrides: hoard guard (`points > 1500` forces a buy, :705) and `pre_finals_skill_dump` (default True) which at `pre_finals_skill_turn` (default 73) sets `force=True` to dump SP (:712-714).
2. **Candidate resolution** (`_candidates()`, skills.py:1190-1346). Reads `chara.skill_tips_array`; each tip resolved via `resolve_skill_tip()` (:1373-1509).
3. **Tier/rarity resolution** (`_resolve_buyable_tier()`, skills.py:287-301). Walks upgrade groups (white→green→gold by `group_id`) and returns the single next-buyable ID — a gold tip resolves to gold only if green is owned (:295-300). **Deterministic by rarity+ownership, not efficiency-ranked** (note: tie-breaking *between* unowned tiers in the same group was not separately verified beyond the rarity/ownership walk).
4. **Smart scoring** (`_skill_smart_score()`, skills.py:1040-1171), per candidate (:1456).
5. **Selection** (skills.py:742-757). Filters by config (skip green/red/unique), sorts, caps greens via `smart_skill_max_green_per_purchase` (default 1, :743), affordability check `spent + cost > points` (:751).
6. **Batch purchase** (`_buy_batch()`, skills.py:1511-1710) with retry on game error codes 205/208 (:1646-1700); on 205, refresh-then-buy.
7. **Career-persistent owned set** (`_acquired_skill_ids`, skills.py:195-201). `_candidates` unions the partial rotating `chara.skill_array` view into a whole-career set (`self._acquired_skill_ids |= current_owned`, :1196), plus name-based dedup backstop (:1274-1276). This is the verified fix for the Fast-Paced/200542 "bought 15×" re-buy bug.

### Scoring model: a dominant primary key + a heuristic tiebreaker

`_skill_smart_score` is two layers (skills.py:1144-1171):

- **PRIMARY key** (:1164-1166): `eval_per_sp * primary_scale + heuristic`, where `eval_per_sp = (grade_value / need_skill_point) * aptitude_multiplier` and `primary_scale` defaults to **1000**. `grade_value`/`need_skill_point` come from `skill_data.json`; `aptitude_multiplier` = S/A 1.1, B/C 0.9, D/E/F 0.8, G 0.7 (:981-986) over the trainee's best aptitude on the skill's tags (:1012-1038).
- **HEURISTIC tiebreaker** (:1045-1142): character-recommended +190 (:1052); community tier SS/S/A/B +115/86/52/25 (`TIER_SCORE`, :149); yellow +100 (:1062); green −90 (:1068); red −45 (:1071); style match +70 (:1083); **style mismatch −10000 hard gate** (:1085-1088, effectively a filter since it dominates the 1000× primary term); primary distance +75 / secondary +24 / avoid −45 (:1098-1104); wrong track −140 (:1108); race-context 0–45 (:1111); official-master 0–50 incl. `disable_singlemode` −120 (:368-371, :1136).

The comment at :1145-1159 confirms the design: "Primary ordering now mirrors reference bot," heuristic demoted to tiebreaker. **Consequence:** eval/SP dominates; everything else only breaks ties — character recommendations (+190) are buried under a small eval/SP delta.

### Every lever (12+ knobs)

From `_skill_config` (skills.py:661-674) and the buy loop: `enable_skill_point_check`, `learn_skill_threshold` (888), `purchase_negative_skills` (False), `skip_green_skills`/`skip_red_skills`/`skip_unique_skills` (False), `skill_spending_strategy` (`best_skills_first` vs `optimize_rank`, :1247-1259), `skill_stop_after_recommended` (False; drops candidates once recommended+SS/S owned, :1327-1336), `skill_manual_auto_fallback` (False, :1313), `skip_double_circle_unless_high_hint` (:1481), `smart_skill_max_green_per_purchase` (1), `pre_finals_skill_turn`/`pre_finals_skill_dump`, `manual_skill_tiers` + `learn_skill_only_user_provided` (:1338-1344), plus weight overrides under `skill_strategy.weights` {recommended, community, yellow, green_penalty, style, distance}.

### Concrete weaknesses

- **No SP-efficiency ranking *within* a tier.** A 50-SP SS and a 200-SP SS both get a flat +115 (:149); `eval_per_sp` exists (:1164) but is a *global* primary key, not a per-tier discriminator. The community tier file carries **no cost data at all**.
- **No schedule-aware activation-condition gating.** Conditions are loaded (`skill_condition_core.json` → `official_skill_conditions`, :324-333; 1.3 MB) and counted for a flat bonus (:363) and surfaced only in log reasons (:1138), but **never parsed/evaluated against the trainee's schedule**. `_race_context()` counts distance/terrain only (:570-615); `_race_context_score()` only adds a distance-overlap bonus (:617-640). Conditions contain real gates like `distance_rate>=50&distance_rate<=60&order_rate>50` and `order_rate>50` — none of which the picker reads. So an `order_rate>50` late-surger gold on a front-runner is scored and bought as dead weight. **This is the prior advantage-hunt finding, confirmed verbatim.**
- **Coarse, sparse tier list.** `community_skill_tiers.json` = 38 names (SS:14, S:14, A:10) → **6.3% of the 605-skill DB** (35–38 unique names map cleanly, 100% accuracy after normalization). ~94% of skills get zero tier signal. No per-style/per-distance differentiation — an "Early Lead" essential for front-runners scores identically on a late-surger.
- **`disable_singlemode` is a soft −120, not a hard gate** (:368-369), so a PvP-only skill with a big tier/eval bonus can still survive. (Aside from this −120 penalty, the loaded `official_skill_weights` cost/grade/condition fields show no other downstream scoring use found.)
- **No cross-turn SP budgeting.** Affordability is a single-turn greedy check (:751); the only multi-turn logic is the crude hoard/dump pair. No reserve, pacing, or synergy budgeting.
- **Name-matching robust on exact normalized matches but fragile across mark variants.** `norm()`/`strip_mark()` (:154-164) collapse `◎`/`◯`, which dedups reliably but **conflates distinct rarity variants into one flat tier**, erasing the cost/efficiency signal that distinguishes them (:399-401, :564-568).

---

## 2. Current community tiers vs the scraped sheet — capability comparison

| Capability | Current (`community_skill_tiers.json` + `TIER_SCORE`) | Scraped sheet (`_sheet_csv/`) |
|---|---|---|
| Granularity | 3 flat tiers SS/S/A (+B fallback), fixed +115/86/52/25 (skills.py:149) | 6 graded symbols ⍟/◎/◯/▲/△/✕ with defined meaning (00_README.csv:12-43) |
| Coverage | 38 skills → **6.3%** of the 605-skill DB | 269 unique skills; **265/269 (98.5%) name-match** the DB after normalization |
| Cost-efficiency | **None** — tier is cost-blind | `Score/SP` numeric column (e.g. Lone Wolf 7.143 / 70 SP at 12_Greens.csv; Corners ◯ 3.846 / 130 SP at 01_Speed.csv col 4) |
| Base cost | Not in tier file (only `skill_data.json` `need_skill_point`) | `Base Cost` column incl. compound `120+120` (01_Speed.csv col 5) |
| Per-style tiers | **None** (one global score for all trainees) | 14_Front / 15_Pace / 16_Late / 17_End, each with side-by-side Team-Trials + PvP tier columns |
| Per-distance tiers | **None** | 18_Sprint / 19_Mile / 20_Medium / 21_Long |
| Career vs PvP split | **None** (single undifferentiated list, source unknown) | Dual columns `Rank (Team Trials)` (col 2) **vs** `Rank (CM9)` (col 3) per skill |
| Activation conditions | Stored separately (`skill_condition_core.json`), unused in matching | `Distance/Run Style` shorthand + natural-language `Condition(s)` |
| Rationale | None | `Why?` column (descriptive, PvP-flavored) |
| Maintenance | Hand-curated ~47-line JSON, no scraper | Sheet header dated 2025-12-12 (00_README.csv:3); needs an ETL tool (none in `tools/`) |
| Data quality | n/a | Clean UTF-8; trailing rows are blank padding; `23_alldata.csv` triples blocks for side-by-side display |

**Net:** the sheet adds five things the current system structurally cannot express — Score/SP efficiency, dual Trials/PvP ranks, per-style tiers, per-distance tiers, and a condition shorthand — across ~16× the coverage (6.3% → 98.5%).

> **Caveats on the comparison (folded from verifier "missing"):**
> - **Column stability across tabs.** Header layout was spot-checked on `01_Speed` and `14_Front` (and `12_Greens` for Score/SP); the analysis *assumes* the same `Skill Name | Rank (Team Trials) | Rank (CM9) | Score/SP | Base Cost | …` layout holds for the other main type tabs (02_Accel, 03_Other, 10_Stamina, 11_Debuff). The scraper must validate headers per tab, not hard-code column indices.
> - **`23_alldata.csv` structure unconfirmed.** Described as ~4492 populated rows / 29 cols / three side-by-side skill blocks, but that file was not directly examined. The scraper should read it defensively (detect block boundaries) or prefer the per-type tabs as the source of truth.
> - **"Monthly update" cadence is inferred, not proven.** Only one date (2025-12-12) is visible in the header; there's no git/changelog history to confirm a monthly cadence. Treat the sheet as "periodically updated, re-scrape on demand," not "auto-stale monthly."

---

## 3. Career-vs-PvP transferability verdict (per signal)

The sheet ranks for **Team Trials and PvP/Champions Meeting (CM9)** — finished umas racing other players — **not** single-mode career fan-farming vs fixed NPCs. Honest per-signal verdict:

- **Score/SP efficiency — TRANSFERS STRONGLY.** Cost-to-value is mode-agnostic; "cheap and consistent must-haves" (01_Speed.csv `Why?`) is exactly right for career, where SP is scarce. The single most valuable column to adopt.
- **Per-style tiers (14–17) — TRANSFERS.** Whether a skill fits a front-runner is a property of the skill's activation, identical in both modes. Directly fixes the bot's style blindness.
- **Per-distance tiers (18–21) — TRANSFERS.** Same logic; career schedules have fixed distance mixes the bot already counts in `_race_context()`.
- **Activation conditions / `Distance/Run Style` shorthand — TRANSFERS as a filter.** A skill needing `order_rate>50` is useless on a front-runner in *any* mode. The shorthand is more immediately actionable than mapping the prose `Condition(s)` to the bot's structured gates.
- **Rank (Team Trials) — TRANSFERS BEST of the two rank columns.** TT is NPC-vs-schedule, like career; default to this column.
- **Rank (CM9 / PvP) — LARGELY NOISE for career.** Harsh PvP-specific downgrades (e.g. Mile Maven ◎ TT → ✕ CM at 13_Tierlist.csv; Productive Plan ◯→✕) reflect PvP constraints. Do not default to it; expose only as an optional knob.
- **`Why?` rationale — ADVISORY / NOISE.** Mixed: some generic ("cheap and consistent"), but clear PvP framing exists — Lone Wolf's "prevent someone else's proc" (14_Front.csv, verified) and PDM/CM phrasing. Useful for human explanation, **not** career scoring. (Honest note: it was *not* exhaustively audited as uniformly "PvP-meta"; treat it as "use for display, never for scoring.")
- **Debuff/red rankings (11_Debuff) — DO NOT TRANSFER.** Career opponents are fixed NPCs; PvP debuff chains barely matter. The bot already penalizes red −45 (:1071); keep it.
- **Start-bonus / team-event skills (Focus, Concentration) — WEAK.** High in Trials/PvP for start-bonus scoring that single-mode lacks.

**Verdict:** the sheet is the *right source* — but only the **Team Trials column + Score/SP + per-style/per-distance tiers + condition shorthand**. Treat CM9 rank, `Why?`, and debuff emphasis as advisory/ignored. Its structure is precisely what the bot is missing, *provided you select the career-relevant slices rather than ingesting it wholesale.*

---

## 4. Proposed redesign (staged: quick wins first, sheet ingestion later)

The single highest-value change depends on **no sheet at all** — so it leads. Each stage is independently shippable and gated for rollback.

### Stage 1 — Schedule-aware condition gate (NO sheet dependency) — *quick win, highest ROI*

Build the `_skill_condition_score()` helper the prior finding calls for, using data already loaded.

- **What:** parse the `order_rate` / `distance_rate` / `running_style` gates in `skill_condition_core.json` (already in memory via `official_skill_conditions`, :324-333) and evaluate them against the trainee profile + `_race_context()` distance/terrain mix (:570-615).
- **Where:** new helper called from `_skill_smart_score` at the existing race-context site (around :1111, where `_race_context_score` already fires). Minimal surface area.
- **Behavior:** **penalize, don't reject by default** (≈ −50 when a gate is unsatisfiable for this trainee/schedule) so rarely-but-meaningfully-firing skills (e.g. "≥3 nearby" Uma-Stan types) still get a chance. Gate behind `skill_condition_gating: penalize|enforce|ignore`.
- **Effort:** **Low** — one new helper + a parser for the `a>=x&b<=y&...` mini-grammar already present in the conditions data; one call site. No JSON schema, no scraper.
- **Risk:** **Low–Medium** — the only risk is mis-parsing condition strings or over-penalizing conditional-but-good skills; mitigated by `penalize` default + an `ignore` escape hatch. Must A/B against current behavior.
- **Why first:** it directly kills the confirmed dead-buy class (wrong-style/wrong-order golds) and needs nothing external.

> *Honest gap (folded from verifier):* we have **no historical quantification** of how many bought skills actually never activated due to schedule mismatch (logs report `skills_bought` but not per-skill activation). Stage 1 should ship with diagnostic logging that records, per buy, whether its conditions are satisfiable — so the SP-leak size can finally be measured rather than asserted.

### Stage 2 — SP-efficiency as a first-class term (NO sheet dependency) — *quick win*

- **What:** promote efficiency from an implicit global key to an explicit, weighted heuristic term using `grade_value / need_skill_point` (both already in `skill_data.json`), so cheap-consistent skills win ties they currently lose to high-tier expensive ones. New knob `skill_efficiency_weight` (modest default).
- **Where:** `_skill_smart_score` (:1144-1171). The spine `eval_per_sp * primary_scale` stays; this just adds a tie-tunable companion term.
- **Effort:** **Low.** **Risk:** **Low–Medium** (re-weighting can shift buy mix; A/B required).
- **Also fold in here:** promote `disable_singlemode` from a soft −120 (:368-369) to a **hard candidate-drop**, since a PvP-only skill should never survive on a high eval/SP. Trivial change, removes a known leak.

### Stage 3 — Sheet ingestion (ETL → graded, context-selected tiers)

New maintainer tool `tools/spreadsheet_skill_tier_scraper.py` (none exists in `tools/` today). Reads `23_alldata.csv` (defensively) and tabs 14–21, emits `data/skill_tiers_normalized.json`:

```
{ <skill_base_name>: {
    team_trials_rank, pvp_rank,            # ⍟/◎/◯/▲/△/✕
    score_per_sp, base_cost,
    style_tiers:    {front, pace, late, end},
    distance_tiers: {sprint, mile, medium, long},
    condition_shorthand, why } }
```

ETL rules grounded in observed data quirks:
- **Validate headers per tab** before reading columns (don't trust fixed indices; see §2 caveat).
- **Strip marks, collapse variants** with existing `strip_mark()`/`norm()` (:154-164), but **preserve a `{common, rare}` sub-rank** so the rarity/cost signal the bot currently loses is retained.
- **Resolve bracket placeholders** (`[Run Style]`, `[Distance]`) from the `Distance/Run Style` context column, not the name — these are the ~4 unmatched rows (98.5% match; the misses are placeholders that shouldn't map to a single ID).
- **Handle fill-down** ("blank = value above") and drop trailing blank padding.
- **Validate names** against `skill_data.json` (case-insensitive + light ~2-edit fuzzy); **log every unmatched** name.

Then wire into scoring:
- **Replace the flat `_community_tier_score`** with a style/distance-*selected* graded tier: pick the trainee's style tier (`profile.running_style` → 14–17) and primary-distance tier (18–21), fall back to global TT rank, then to legacy `community_skill_tiers.json` + `TIER_SCORE`. Map symbols to configurable bonuses (e.g. ⍟ +140, ◎ +110, ◯ +60, ▲ +20, △ +5, ✕ −60). Now "Early Lead" ranks high *only* on front-runners.
- **Effort:** **Moderate** — the CSV is clean; the hard parts are mark/bracket parsing + fill-down, all enumerated above. **Risk:** **Medium** — name-mapping drift over game/sheet updates (mitigate with the validator + unmatched-logging), and PvP-overfit if a user flips `rank_source` to `pvp`.

### Stage 4 — Config surfacing

Expose the new `skill_scoring_v2` block in preset / `mant_config` / UI:
- `skill_tier_rank_source`: `team_trials` (default) | `pvp`
- `skill_tier_multipliers`: per-symbol bonus map (defaults above)
- `skill_efficiency_weight`: float (modest default)
- `skill_condition_gating`: `penalize` (default) | `enforce` | `ignore`
- `skill_tier_source`: `style_distance` (default) | `global`

**Effort:** Low. **Risk:** Low (UI/config only).

### Backward compatibility

If `skill_tiers_normalized.json` is missing **or** `skill_scoring_v2` is off, fall back to `community_skill_tiers.json` + hardcoded `TIER_SCORE` (:149) — byte-identical behavior. Integration is narrow: `_skill_smart_score` (called at :1456) and the `_candidates` sort (:1258). No changes to the buy loop, `_buy_batch`, or `_acquired_skill_ids`.

---

## 5. Honest verdict

**Is it actually better? Yes, qualitatively — but bounded.**

- **Biggest wins, high confidence:** (a) the **condition gate** (Stage 1) eliminates the well-documented dead-buy class (wrong-style/wrong-order golds bought because conditions are loaded but never matched to the schedule), and (b) **Score/SP + per-style/per-distance tiers** stop equal-tier-but-wrong-context over-purchases. Both are real, currently-unaddressed SP leaks. Coverage jumps from **6.3% → 98.5%** of named skills.
- **It's the right source *only if sliced correctly*.** The sheet is built for Team Trials / PvP, not career. The value depends entirely on using the **Team Trials column + Score/SP + style/distance/condition** signals and treating CM9 rank, `Why?`, and debuff emphasis as advisory. Ingesting wholesale would import PvP-meta overfit.
- **What it does NOT do:** it still doesn't model **fans-per-SP** or **cross-turn SP budgeting** — the deepest gaps. There is no career race-simulation here; "does the condition match the schedule?" is a strong *proxy* for fan impact, not a measurement. Skill-buy stays heuristic.

**Risks:** (1) name-mapping drift as sheet/game update — needs the validator + unmatched-logging; (2) variant-mark/bracket parsing is the trickiest ETL step (fill-down + `◯`/`◎` collapse with sub-rank preservation); (3) maintenance — the sheet updates periodically, so without the scraper it stales; (4) tuning symbol→bonus and efficiency weights risks regressions if not A/B'd; (5) PvP-overfit if a user flips `rank_source` to `pvp` without understanding the trade.

**Effort:** moderate and well-bounded. Stages 1–2 are sheet-free, low-line-count edits to `_skill_smart_score` + one helper, fully gated. Stage 3's scraper is a single clean tool whose only hard parts are enumerated above.

**Recommendation:** Ship **Stage 1 (condition gate) and Stage 2 (efficiency term + hard `disable_singlemode` filter) first and independently** — they need no sheet, carry the highest ROI, and directly fix the confirmed "conditions loaded but never matched" leak. Add diagnostic logging in Stage 1 so the SP-leak size is finally *measured*. Then adopt the sheet in Stage 3, behind `skill_scoring_v2` with the legacy path as fallback, using **only its career-transferable slices**.

**The honest downside:** even fully built, this buys you *fewer wasted SP purchases* (fewer wrong-condition golds, better cheap-consistent prioritization), **not a step-change in fans** — because the levers that actually bound fan output (fan-per-SP value modeling and cross-turn SP budgeting) remain unmodeled, and the sheet's career-vs-PvP mismatch means a careless rank-source flip can quietly make picks worse. The condition gate (Stage 1) is worth shipping regardless of whether the sheet is ever ingested.

---

## Addendum (2026-06-28): Team Trials / CM optimization modes (approved direction)

The skill-spending dropdown gains an OPTIMIZATION-TARGET axis, distinct from the existing how-to-spend axis:

- Targets: **Career / Balanced (default)**, **Team Trials**, **Champions Meeting**. Default stays fans/career (uses the Team-Trials column as the best race-winning proxy). TT/CM are explicit overrides for umas built to race competitively.
- The target only chooses WHICH competitive tier column drives the tier bonus (Stage 3 data). Stage 1 (condition gate) and Stage 2 (SP-efficiency) run in ALL targets - they prevent dead/overpriced buys regardless of target.
- **`disable_singlemode` becomes mode-dependent:** in Career mode a single-mode-disabled skill is dead SP -> hard-drop; in TT/CM mode that same skill works on the finished uma -> ALLOW it and value it by its TT/CM rank. (A blanket hard-drop, as Stage 2 first proposed, is only correct for Career mode.)
- Condition-relevance source differs by target: Career = the actual career race schedule; TT/CM = the trainee's intended style/distance via the sheet's per-style/distance tiers.
- Requires Stage 3 (sheet ingestion) for the TT/CM data. Keep fans the default; UI must note CM mode "optimizes the finished uma for CM (may cost some career fans)."
- Keep the two axes from conflating: target (Career/TT/CM) vs how (best_skills_first / optimize_rank).
