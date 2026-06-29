<!-- Generated 2026-06-28 via the server-grant-feature-hunt workflow (wf_138794d2-023): 4 investigators -> synth -> 2 adversarial verifiers. Corrections from the verifiers are folded in. Builds on docs/api-capability-map-2026-06-28.md. -->

# Server-Grant Catalog — what the game WILL grant (confirmed) vs MAY grant (needs a live test)

Companion to `api-capability-map-2026-06-28.md`. Every item is grounded in code / master-data / real logs and was run past two adversarial verifiers; their corrections are applied.

**Standing safety:** all write/probe paths run via the DEV-ONLY `career_bot/raw_api.py` (`POST /api/debug/call` arbitrary, `POST /api/debug/action` allowlisted) — EXCLUDED from public/beta builds, and the guards REFUSE while a career is running (shared SID) and when logged out. **Run every probe IDLE / between careers.**

---

## A. SERVER WILL GRANT — confirmed, buildable today (no live sniff needed)

### Read-only engine wins (zero new call, pure parsing) — genuinely UNREAD by the solver
| Field | Win | Effort | Grounding |
|---|---|---|---|
| `chara_info.max_speed/max_stamina/max_power/max_guts/max_wiz` | **Cap-aware training** — live per-run stat ceilings; the solver reads only the STATIC master table, so it can over-invest a near-capped stat. Attenuate near-cap stats in scoring. | med | solver reads static only: `master_data.py:890-894,1568-1572`; live field unread; log `chara_info.max_speed=1200` |
| `chara_info.route_race_id_array` | Exact remaining route/finale program_ids → predict climax variant, drive scheduling (via `reserve_race`), detect soft-lock without turn-guessing. | low read / med act | log `[730,40022..40027]` + `route_id=10004`; unread |
| `home_info.race_entry_restriction`, `shortened_race_state`, `chara_info.is_short_race` | Pre-validate race entries + pick the correct short-race mode from the server instead of guessing `is_short`. | low | log `=1/=4/=0`; grep: unread |
| `unchecked_event_array[0]` inner detail (`play_timing`, `event_contents_info{choice_array,support_card_id,show_clear}`) | Value-aware event handling (currently `_drain_events` reads only event_id/chara_id; len() elsewhere). **Caveat:** `reward_type/reward_id` sub-keys did NOT appear in logs — those names need a sniff. | med | `runner.py:2367-2405,1226`; log shape verified |
| `race_reward_info.result_time` + `campaign_id_array` (race_end) | Win-margin benchmarking (`result_time` ms) + active bonus-window detection (join `campaign_id_array` → `campaign_data`, 161 rows, date cols `start_time/end_time`). **Caveat:** `campaign_id_array=[]` this run — non-empty shape needs a race_end during a live campaign. | med | log turn 12; `ai_dataset.py:203` reads top-level only |
| `chara_info.nickname_id_array` | Earned-epithet completion tracking; feeds the epithet/set-bonus stat lever. | low | log `[92]`; `nickname` table 218 rows |
| `chara_info.short_cut_state / route_id / start_time / talent_level` | URA phase-progress UI, career wall-clock duration, trainee-mastery event-proc prediction. | low | log verified; unread |
| `data_headers.server_time / maintenance_mode_flag / viewer_id` | Maintenance gate, clock-skew (anti-detection), active-account verify. **Caveat:** names INFERRED — logs strip data_headers; confirm via `/api/latent` `_meta.found` on one live login. | low + 1 confirm | `client.py:586-594` caches; names unverified |
| `home_info.disable_command_id_array` | (DEMOTED by verifiers) truly unread, but **redundant** — `is_enable` is ALREADY a command filter in the engine (`mant_trackblazer.py:221,459`; `races.py:312-313,835`; `mant.py:157`). Low marginal value. | low | grep |

### In-protocol, no-spend, confirmed callable
| Endpoint | Win | Risk | Grounding |
|---|---|---|---|
| `single_mode_free/reserve_race` | **Already wrapped, NEVER invoked.** Batch pre-reserve/cancel future races (`add_race_array`/`cancel_race_array`). The single best unbuilt in-protocol grant. First probe: both arrays `[]` → expect rc==1. Reversible via cancel. | No spend; reserving commits the schedule (reversible). Must be inside a career at a valid turn (else 102). | wrapper `client.py:1188-1193`; grep: only wrapper + pacing string `main.py:1215` + unrelated test |
| `home/index` | Safe out-of-career home read (home_info + account latent objects). The safe pre-step to all account-claim writes. | None (read). | wrapper `client.py:607-609`; allowlisted `raw_api.py:38` |

### Already done — do NOT rebuild (doc-3A false positives, verifier-confirmed)
- `command_info_array[].params_inc_dec_info_array` (per-command exact stat deltas) — consumed at `mant_trackblazer.py:648`, `mant.py:507,661`, `items.py:2009,2069`.
- `playing_state` — core runner state machine (`runner.py:2040-2047,3761-3818 _blocked_playing_state`).
- `free_continue_time` — already read (`runner.py:1358-1366`) and now surfaced on the navbar.
- `is_enable` — already a command filter (see above).

---

## B. SERVER MAY GRANT — unconfirmed, each needs ONE live test (run IDLE via `/api/debug/*`)

Ranked by value-to-risk. **SAFE/ADDITIVE** = grants resources, spends nothing (but writes account state, not trivially reversible). **SPEND** = consumes currency/items/stamina and is permanent — never auto-run.

### Tier 1 — SAFE/ADDITIVE claims (free resources)
| Probe | Endpoint string | Payload (derive live ids from a `/api/latent` read first) | Confirm |
|---|---|---|---|
| **mission/receive** — claim completed mission rewards | **confirmed** (pacing `main.py:1187`) | `{mission_id: <claimable id>}` → fallbacks `{mission_id_array:[id]}`, claim-all `{receive_type:1}`. Ids from load/index missions list (name inferred). | rc==1 + updated user_item/coin; rc==102 = not complete/bad id |
| **present/receive** — claim present-box gifts | **guess** (not in pacing) | `{present_id:<id>}` → fallback `{present_id_array:[...]}` / `{is_all:true}`. Ids dynamic (load/index). | confirm endpoint string AND key |
| **login_bonus/receive** — daily stamp | guess | `{login_bonus_id:<login_bonus_data.id>}`; likely already auto-claimed (useful negative result). | rc==1 or "already claimed" |

### Tier 2 — LOW risk, cosmetic/social, reversible
| Probe | Endpoint | Payload | Risk |
|---|---|---|---|
| **chara/nickname** — equip earned epithet | confirmed (pacing) | `{trained_chara_id, nickname_id}` (use an id from `nickname_id_array`) | cosmetic, reversible |
| **friend/add** — friend request | confirmed (pacing) | `{friend_viewer_id}` (verbatim from succeeding friend/search `main.py:5210-5213`); probe your alt | visible to a 3rd party |

### Tier 3 — SPENDS + (often) IRREVERSIBLE — never auto-run, probe a throwaway, count:1
| Probe | Endpoint | Payload — **element shapes CORRECTED by verifiers** | Spend |
|---|---|---|---|
| **exchange/item** — redeem event currency | **confirmed** (pacing) | try `{exchange_id, count:1}`; in-career analog actually succeeds with **`{shop_item_id, current_num}`** (NOT `{item_id,exchange_num}` — `items.py:807-810`); also try `{item_exchange_id, exchange_num}`. Pricing from `item_exchange` (566 rows, pay_item_* cols). | event currency |
| **item/use** — consume an item out of career | confirmed (pacing) | `{item_id, client_own_num, item_num}` (VERBATIM from succeeding use_recovery_item `client.py:986-990` — correctly grounded) | 1 item, irreversible |
| **support_card/enhance** — LB/level a card | confirmed (pacing) | `{support_card_id, use_item_info_array:[...]}`; real succeeding element is **`{item_id, use_num, current_num}`** (NOT `{item_id,item_num}` — `items.py:498`). Probe empty array first. | fodder + permanent LB |
| **chara/talent** — rank-up awakening | confirmed (pacing) | `{trained_chara_id, rank_up_target_rank}`; try `{talent_level}`/`{skill_id}` variants; same use_item element correction. Probe without items first. | pieces + permanent |
| **daily_race / legend_race** entry | guess | read `*/index` first; entry `{race_instance_id, group_id, difficulty}` (+`legend_race_boss_npc_id`); lowest difficulty, no loop | daily budget + billing jewels |
| **home/story, story/play\|unlock** | guess | `{story_id, choice_number:0}` (mirrors check_event); add_reward jewels | additive, irreversible state |
| **circle/stamp \| join \| leave** | guess | probe harmless `circle/stamp {circle_id, stamp_id, type}` first | join/leave = membership cooldown |
| **team_stadium / team_building / fan_raid** | guess | read `*/index` first — 1-row master tables ⇒ likely out-of-period/inert | event stamina/slots |
| **champions** entry/submit | guess | **READ `champions/index` ONLY.** Entry = ranked commitment, season-gated, least derivable. | entry slots + jewels, irreversible ranked deck |
| **gacha** pull | n/a | **READ ticket balance only.** Pull payload NOT derivable; `gacha_prize_odds` empty on disk. | NOT BUILDABLE |

### Recommended safe live-test sequence (IDLE account)
1. `home/index` (free read) → 2. `GET /api/latent` to lock account field names via `_meta.found` → 3. `mission/receive` then `present/receive` (free grants). **Defer every SPEND endpoint until names are sniff-confirmed.**

---

## Verifier corrections folded in
1. `is_enable` is ALREADY read (`mant_trackblazer.py:221,459`) → only `disable_command_id_array` is net-new (low value).
2. SPEND payload element shapes were mis-grounded: real in-career elements are `{item_id,use_num,current_num}` (use) and `{shop_item_id,current_num}` (exchange) — probe both, don't claim "verbatim".
3. `campaign_data` date cols are `start_time/end_time` (not start_date/end_date).
4. Endpoint STRINGS confirmed (pacing table): exchange/item, item/use, support_card/enhance, chara/talent, chara/nickname, friend/add, mission/receive, team/evaluation. True guesses: present/receive, login_bonus/receive, daily/legend/team/fan_raid/champions/story/circle writes.
5. `reserve_race` wrapper is `client.py:1188-1193`; `playing_state`/`free_continue_time` confirmed already-read.
