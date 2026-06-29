<!-- Generated 2026-06-28 via 12-agent capability-map workflow (wf_532ee035-ed3): 7 mappers -> synth -> 3 adversarial verifiers -> editor. 335 raw findings, 14 corrections, 10 missed-items folded in. -->

# Icarus — Full API Capability Map

This is the definitive inventory of everything the bot can do with the Umamusume game API — current, latent, and untapped — plus the bot's own local server API. It merges the synthesized catalog with the verifier corrections: wrong groundings fixed, dishonest feasibility tiers re-tiered, and every flagged "missing" item folded in.

Every actionable item carries a feasibility tier:
- **T1-free** — already in hand (code/data present, callable or parsed today)
- **T2-known-payload** — payload referenced/sniffed/derivable right now
- **T3-derivable** — inferable from data + observed API patterns
- **T4-needs-live-sniff** — write/entry payload not derivable from repo or data; needs the user's packet sniffer
- **T5-ruled-out** — not possible / not worth it

> **Grounding-notation correction (verifier):** Section 5's `catalog:NNNN-NNNN` line citations were an **invented notation** — `data/master_table_catalog_core.json` is a single JSON file of table arrays with no stable line numbers. All such pseudo-citations below are replaced with **table-name groundings**. The tables themselves are real (verified present). The catalog's **row counts are also stale/wrong** — corrected inline where stated by the verifier.

---

## HOW TO CALL AN ARBITRARY ENDPOINT (the literal answer to "new ways to communicate")

There is **no endpoint whitelist**. `UmaClient.call()` (`uma_api/client.py:588-756`) is a fully generic invoker: it `common()`-merges the universal payload, msgpack-packs, AES-CBC encrypts, envelopes, base64s, POSTs to `BASE_URL + ep`, then decrypts/unpacks the response and rotates the SID. Any path segment + any msgpack-encodable dict is reachable today with zero new transport code.

Recipe (using the already-authenticated active client the runner holds):
```python
# active_client is the live UmaClient (auth_key/SID/UDID already loaded)
res = active_client.call("mission/receive", {"mission_id": 12345},
                         retry_208=6, retry_205=3)
# res is the decrypted msgpack dict; res["data_headers"]["result_code"] is the rc
```
- `ep` is the raw path after `umamusume/` (e.g. `"single_mode_free/reserve_race"`, `"home/index"`, `"mission/receive"`).
- Defaults `retry_208=6, retry_205=3` already handle server-busy/retry codes; `394`→ticket refresh, `709`→SID regen are automatic.
- This is exactly how the two sniffer-discovered endpoints are already invoked (`circle/detail`, `friend/search` at `main.py:5096-5193`).
- **What's missing is only a route** that exposes this generic invoker — see Section 6's "Raw game-endpoint debug route" (T2).

---

## 1. Protocol & Transport Mechanics — and New Communication Channels

A single generic HTTP POST invoker; whole game surface reachable today.

### Request / response cryptography
- **Request envelope (`pack`)** — AES-CBC encrypt `[4-byte LE msgpack length + msgpack payload + PKCS#7 pad-16]` with a per-request random key; build header `[HEAD const + SID (16B) + raw UDID + os.urandom(32) nonce + optional auth]`; envelope `[4-byte LE header length + header + ciphertext + 32-byte key]`; base64. `uma_api/client.py:187-193`. **T1-free**
  - **Correction (verifier):** **HEAD is 52 bytes, not 48** — `bytes.fromhex(...)` at `client.py:119` is 104 hex chars = 52 bytes (verified). **The length prefixes are little-endian (`struct.pack('<I', ...)`)**, not big-endian as the catalog stated (`client.py:190,193,199`).
- **Response envelope (`unpack`)** — trailing 32 bytes = AES key; decrypt remainder; IV = `get_iv(udid)` = UDID with dashes stripped, lowercased, first 16 chars (`client.py:181-182,195-199`). Skip 4-byte LE length; msgpack. Captured traffic is decryptable because UDID is settable in config. **T1-free**
- **No request signing (no HMAC)** — encrypt-then-no-sign; a leaked AES key allows undetected plaintext forgery. `pack :187-193`. **T1-free**
- **AES-256-CBC per-request key + 32-byte random nonce** — confidentiality + replay nonce. `client.py:187-199`. **T1-free**

### Session & auth
- **SID chaining (`next_sid`)** — `make_sid(vid,udid) = sm5((str(vid)+udid).encode())`, rotated each success via `next_sid(sid) = sm5(sid.encode())`. `client.py:163-173, 754`. **T1-free**
  - **Correction (verifier):** the formula is **`sm5(x) = MD5(x + SALT).digest()`** — a full **16-byte** MD5 digest where **SALT (`b'co!=Y;(UQCGxJ_n82'`, `client.py:118`) is mixed into the hash input**, NOT `MD5(SID)[:16] + SALT` concatenated onto the output. Still deterministic → predictable from an initial SID.
- **`auth_key` injection** — `bytes.fromhex(cfg['auth_key'])` appended to envelope header only when present; `has_captured_auth()` validates viewer_id + udid + auth_key + steam_id + steam_ticket; captured from `tool/signup`. `client.py:192, 500-518, 804`. **T1-free**
- **Steam ticket lifecycle (394)** — `refresh_steam_ticket()` mints a fresh ticket via Node.js `SteamUser.createAuthSessionTicket(appid=3224770)`; `on_ticket_refreshed()` persists it; 2FA supported. `client.py:378-410, 808-828`; retry `main.py:856-869`. **T1-free**
- **Viewer-id recovery (709)** — server returns a new viewer_id → `regen_sid()` + raise → caller retries. `client.py:715-721`, `main.py:853-854`. **T1-free**
- **Attestation disabled** — `tool/start_session {attestation_type:0, device_token:None}`; no Play Integrity / SafetyNet enforcement observed. `client.py:794-800, 765/845`. **T1-free**

### Universal payload injection — `common()`, merged into EVERY request (`client.py:570-602`)
Fields: `viewer_id, device=4, device_id (SHA1 hwid), device_name (SMBIOS), graphics_device_name, ip_address (8.8.8.8 DNS lookup), platform_os_version, carrier='', keychain=0, locale='JPN', button_info='', dmm_viewer_id=None, dmm_onetime_token=None, steam_id, steam_session_ticket`.
- **Device spoofing** — `device_id = SHA1(device_name + machine_guid + seed)`; spoof via configurable `seed_string` or a pre-computed `device_id`. `get_hwid :295-330`, `_read_smbios_identity :237-292`. **T1-free**
- **Locale switching** — defaults `JPN`, configurable via `cfg['locale']`; may unlock region-gated content. `client.py:435, 575`. **T1-free (latent-unused)**
- **Unused settable spoof slots** — `dmm_viewer_id, dmm_onetime_token, carrier, keychain, adid` (`load/index {adid:''}` :766). **T1-free**
- **IP honesty** — real public IP via `getaddrinfo(8.8.8.8)`; not spoofable without network-layer tools → VPN/geofence detectable. `:230-235`. **T1-free**

### Anti-detection / pacing (timing attack surface)
- **`button_info` screen-coordinate spoof (race_out only)** — JSON `{ViewerId, DeviceId=4, ScenarioId, ClickPosX/Y (Gaussian + DPI), ClickServerTime (3.0-4.5s before now)}` fakes a human forfeit click. `client.py:604-634`. **T1-free**
- **Per-endpoint lognormal delay (7 tiers)** — pre_signup 11-21ms → gain_skills/chara/item ~30s; fatigue sinusoid (period 2160-2520s, ±15%), `GLOBAL_SESSION_JITTER` ±8%, `api_delay_scale` (Speed level). `main.py:1126-1246, 715`. **T1-free**
- **`MIN_CALL_SPACING` floor** — 0.14→0.0s by Speed (Safe/Fast 0.14, Faster 0.05, Ludicrous 0.0). `client.py:30, 592-596`; `set_speed_level main.py:961-979`. **T1-free**
- **TLS impersonation** — `curl_cffi.requests.Session()` defeats JA3/JARM fingerprinting. `client.py:6, 449`. **T1-free**
- **Unity UA spoof** — `UnityPlayer/{ver} (UnityWebRequest/1.0, libcurl/8.10.1-DEV)` + per-call headers `SID, Device=4, ViewerID, APP-VER, RES-VER`. `:581-586, 637-640`. **T1-free**

### Resilience & result codes (`client.py:723-751`) — also a state-recon oracle
`1`=ok · `205`=retry (3×, 0.14-0.19s) · `208`=server-busy (6×, exp backoff; gain_skills/multi_item_* return anyway) · `394`=expired ticket (5×, refresh) · `709`=viewer mismatch (regen SID + raise) · `102`=invalid state (silent on race_end/race_out, else raise) · `201/202`=career-state mismatch (fatal in hard_reset). HTTP 5xx → exp backoff (cap 15s); network errors → linear backoff. `:659-696`. Codes double as a **state oracle** (e.g. `102` ⇒ career in progress). **T1-free**

### New communication channels (tracing / replay / local hooks)
- **TRACE_DIR JSONL trace** — `{ts, direction(REQ/RES/ERR), endpoint, data, req_id}` → `api_payloads/*.jsonl`; enables **offline replay** and mock feeding. `client.py:46, 458-495, 643/667/673/702`. **T1-free**
- **`on_api_log` callback** — live per-event hook for every game API call; could back a real-time local stream (not yet exposed). **T1-free**
- **Generic `call()` invoker** — `call(ep, args, retry_208=6, retry_205=3)`; arbitrary endpoint + payload, no whitelist; any sniffed/derived endpoint instantly callable. `client.py:588-756`. **T1-free**
- **Replay/forgery** — with valid SID + auth_key + UDID, captured payloads replay; SID sequence is deterministic. **T1-free**

### Hard limits (ruled out)
- **No batching / multiplexing** — one HTTP POST per call. `:588-756`. **T5**
- **No alternate protocols** (WebSocket/gRPC/UDP) for the game API — the Steam CM WebSocket is auth-only. **T5**
- **No dynamic master-data endpoint** — master data is static, bundled (`data/master_table_catalog_core.json`). **T5 (for transport)**

---

## 2. Current Game-API Endpoint Surface

**27 endpoints called today** (verifier correction: 25 wrapped client methods + 2 sniffer-verified raw `.call()` sites = 27, not 26). All **T1-free**.

| Endpoint | Request (key fields) | Response used |
|---|---|---|
| `tool/pre_signup` | (empty) | — `client.py:794` |
| `tool/signup` | error_code, error_message, attestation_type, optin_user_birth, dma_state, country, credential | viewer_id, auth_key(b64) `:797-806` |
| `tool/start_session` | attestation_type:0, device_token:None | SID rotation `:765,845` |
| `load/index` | adid:'' | chara_info, user_item[], tp_info, coin_info, single_mode_free_info `:766,846; main.py:4591` |
| `read_info/index` | add_home_story/short_episode/home_poster/tutorial_guide/released_episode arrays | (arrays returned, unread) `:929-936` |
| `pre_single_mode/index` | exclude_viewer_id_array (opt) | single_mode_data[], rental_single_mode_data[] `:979-983` |
| `single_mode_free/load` | (empty) | chara_info(turn,vital,rank,scenario_id), command_info_array[], unchecked_event_array[], user_item[] `:774,952` |
| `single_mode_free/start` | start_chara{card_id, support_card_ids, friend_support_card_info, succession_trained_chara_id_1/2, rental_succession_trained_chara, scenario_id, selected_difficulty_info{difficulty_id,difficulty,is_boost}, select_deck_id, boost_story_event_id, is_play_training_challenge}, tp_info, current_money, use_tp, current_succession_rank_point | chara_info, command_info_array, single_mode_free_info `:985-1024` |
| `single_mode_free/exec_command` | command_type(1 train/8 infirmary/7 rest/3 outing), command_id, command_group_id(390 group outing), select_id(0 default; card IDs for Sirius/Throne), current_turn, current_vital | chara_info, command_info_array, unchecked_event_array[], user_item[] `:1026-1034` |
| `single_mode_free/check_event` | event_id, chara_id(0 generic), choice_number(0 view, N select), current_turn | event_info(choice_detail_array[], event_description), chara_info `:1036-1043` |
| `single_mode_free/multi_item_use` | use_item_info_array[{item_id,item_num}], current_turn | user_item[], chara_info `:1045-1049` |
| `single_mode_free/multi_item_exchange` | exchange_item_info_array[{item_id,exchange_num}], current_turn | user_item[], chara_info `:1051-1055` |
| `single_mode_free/gain_skills` | gain_skill_info_array[{skill_id,level}], current_turn | chara_info(skill_list[]), user_item[] `:1057-1068` |
| `single_mode_free/race_entry` | program_id, current_turn, running_style(1-4, ignored by server) | race_start_info, chara_info `:1070-1077` |
| `single_mode_free/change_running_style` | program_id, running_style(1-4), current_turn (post-entry, pre-start or 102) | race_start_info, chara_info `:1101-1110` |
| `single_mode_free/race_start` | is_short(0/1), current_turn | race_result_info(rank,star_count), chara_info `:1079-1083` |
| `single_mode_free/race_end` | current_turn | chara_info(skill_list,vital), user_item[] `:1085-1088` |
| `single_mode_free/race_out` | current_turn (+ button_info spoof) | chara_info; graceful on 102 `:1090-1093` |
| `single_mode_free/continue` | current_turn, continue_type(1 free/2 paid) | home_info(available_continue_num), chara_info `:1095-1099` |
| `single_mode_free/reserve_race` | current_turn, add_race_array[{program_id}], cancel_race_array[{program_id}] | **wrapped but NEVER called (latent)** `:1112-1117` — **T2** |
| `single_mode_free/minigame_end` | result{result_state,result_value,result_detail_array}, current_turn | chara_info, command_info_array `:954-962` |
| `single_mode_free/finish` | is_force_delete(bool), current_turn | add_trained_chara_info{trained_chara_id}, user_item[] `:938-942` |
| `user/recovery_trainer_point` | count(1), client_own_num | tp_info, coin_info `:875-889` |
| `item/use_recovery_item` | item_id(32=TP potion), client_own_num, item_num | tp_info, coin_info, user_item[] `:900-927` |
| `trained_chara/remove` | trained_chara_id_array[] | (unparsed) `:945-949` |
| `circle/detail` *(sniffer-verified, raw .call)* | circle_id, no_join_user:true | circle_info{name,total_fans}, circle_ranking_this_month{rank,point}, summary_user_info_array/circle_member_array[{viewer_id,name,fan}] `main.py:5096-5193` |
| `friend/search` *(sniffer-verified, raw .call)* | friend_viewer_id, deleted_response_type:0 | summary_user_info(_array)[{viewer_id,name,circle_id,fan}] `main.py:5161-5164` |

**One free in-protocol win:** `reserve_race` is fully wrapped but never invoked → batch race scheduling is **T2-known-payload**.

---

## 3. Latent Response Data — split into TRULY UNREAD vs ALREADY-READ

The synthesized catalog claimed ~40 fields were "received but ignored." **The verifiers disproved a large fraction** — many are actively parsed (in `career_bot/items.py`, `career_bot/scenarios/mant.py`, `career_bot/races.py`, `career_bot/ai_dataset.py`, `career_bot/character_profiles.py`). This section is re-partitioned. **All fields arrive in responses today and need NO new request; the "TRULY UNREAD" group is the genuine free-win surface.**

> Wrapper baseline: `client.py` extracts only `tp_info, coin_info, user_item, scenario_id`, SID. The runner consumes narrow `chara_info` slices, `home_info.available_continue_num`, `command_info_array`, `unchecked_event_array` **length**, and `race_condition_array`.

### 3A. TRULY UNREAD — genuine free wins (pure parsing, T1-free)
Verified absent from any read in `career_bot/` + `uma_api/` + `main.py`:
- **`training_level_info_array`** — exact per-NPC stat gains per command. **Not read anywhere** (only the *static* master table is parsed at `master_data.py:2308-2330`); the live array is unused → precise trainer selection without sniffing.
- **`route_race_id_array`** — completed URA route races; exact progress, climax-variant prediction, soft-lock detect. **Not read.**
- **`unchecked_event_array` detail** — `{event_id, event_type, reward_type, reward_id}`. The runner reads **length only** (`runner.py:858, 896, 964, 1226`); inner fields never parsed → high-value-event prioritization.
- **`route_race_id_array`, `route_id`, `start_time`** — route variant + career duration (runner reads `scenario_id` only). **Not read.**
- **`campaign_id_array`** (in race_reward_info) — active campaigns; auto-prioritize bonus windows. **Not read** (only `race_reward_info` top-level at `ai_dataset.py:203`).
- **`result_time`** — race duration (ms); closeness benchmarking. **Not read.**
- **`nickname_id_array`** — epithets earned live; completion tracking. **Not read.**
- **`twinkle_race_npc_info_array / _result_array / twinkle_race_ranking`** — Twinkle Race scoring/leaderboard (distinct from `win_points`, which IS read). **Not read.**
- **`guest_outing_info_array`** — group-outing partner/outcome state. **Not read.**
- **`command_info_array` detail** — `{is_enable, reserve_command_id}`; runner reads `command_id` only → auto-skip disabled trainers. **Detail not read.**
- **`race_entry_restriction`** — race-availability bitmask by phase. **Not read.**
- **`shortened_race_state` / `is_short_race`** — skip/auto-play availability; sprint-career flag. **Not read.**
- **`disable_command_id_array`** — server-side disabled commands (exact UI gating). **Not read.**
- **`free_continue_time`** — epoch of next free clock; optimal sleep-to-clock. **Not read.**
- **`shop_id / sale_value`** — shop pricing context; buy-on-sale. **Not read.**
- **`unchecked_event_achievement_id`** — hidden achievement/quest flag. **Not read.**
- **`playing_state`** — career state machine (0 train…3 soft-lock…4 finished); soft-lock auto-detect. **Not read.**
- **`short_cut_state`** — URA phase-completion bitfield. **Not read.**
- **`talent_level`** — trainee mastery; event-proc prediction. **Not read.**
- **`chara_info` stat ceilings (partial)** — `max_speed/stamina/power/guts/wiz` are **NOT read** (cap-aware training, inheritance diagnostics). *(Verifier correction: `max_vital` IS read at `runner.py:1220, 2012`, so only the non-vital ceilings are latent.)*
- **`data_headers` beyond SID** — `viewer_id, server_time, maintenance_mode_flag`; maintenance/clock-skew/multi-account detection (`client.py:699-754` reads only result_code + sid). **Not read.**

### 3B. ACCOUNT-LEVEL latent (load/index, read_info/index) — T1-free
`client.py:556-579` extracts only tp_info/coin_info/user_item. Unread objects: **`present_box`, `mission_progress`, `login_bonus_progress`, `gacha_ticket_array`, `circle_info`, `fan_information`, `story_progress_info`, `daily_quest_progress`, `weekly_quest_progress`, `announce_array`** (in-game announcement/banner schedule; `announce_data` table = 84 rows, verifier-confirmed correct). Use: pre-career diagnostics — validate tickets, warn on login-bonus/gift expiry, log baseline coin/TP, detect circle-rank changes, maintenance window.

### 3C. ALREADY-READ — catalog was wrong; **NOT a free win** (verifier corrections)
These were claimed latent but are actively parsed — listed for honesty so no one re-implements them:
- **`evaluation_info_array`** (per-NPC bond) — READ at `items.py:605, 1689` and `scenarios/mant.py:278, 290, 377, 423, 522`.
- **`support_card_array` detail** (`support_card_id, limit_break_count, owner_viewer_id`) — READ at `scenarios/mant.py:257-298` and `main.py:1839-1845` (not "position+id only").
- **`race_history`** (`turn, program_id, result_rank, weather, ground, style`) — READ at `ai_dataset.py:207`, `races.py`, `report.py`, `runner.py`, `trackblazer.py`.
- **`chara_effect_id_array`** (buffs/debuffs) — READ at `items.py`, `scenarios/mant.py`, `style_adaptation.py`.
- **`item_effect_array`** (active effects + turns) — READ at `items.py`.
- **`pick_up_item_info_array`** (event loot) — READ at `items.py:574`, `runner.py`.
- **`rival_race_info_array`** — READ at `races.py:218`.
- **`win_points` / `prev_win_points`** — READ at `races.py:164`, `runner.py`, `trackblazer.py:539+`, `style_adaptation.py`.
- **`user_item_info_array`** (fine-grained inventory) — READ at `items.py`, `scenarios/mant.py` (catalog's `client.py:712` claim notwithstanding, it's consumed downstream).
- **`rarity` + `proper_*` aptitudes** (live distance/ground/style grades) — READ at `character_profiles.py:421-442, 505-520` (`_aptitudes_from_chara_info`), plus `master_data.py`, `races.py`, `runner.py`, `trackblazer.py`, `style_adaptation.py`.
- **`max_vital`** — READ at `runner.py:1220, 2012`.
- **`race_reward_bonus / _bonus_win / _plus_bonus`** — **do not exist as field names in code**; only `race_reward_info` (top-level) is parsed at `ai_dataset.py:203`. The granular breakdown sub-fields, if the server sends them, would be **truly unread** (move to 3A if a live sniff confirms the names), but the catalog's specific field names are unverified.

---

## 4. Known Endpoints Referenced but Not Wrapped

In the pacing table (`main.py:1158-1237`) or sniffer-discovered, no full wrapper. Each is callable today via `call()` (see top recipe).

| Endpoint | Likely request | Feasibility | Grounding |
|---|---|---|---|
| `circle/detail` | {circle_id, no_join_user} | **T1-free** (sniffer-verified, actively used) | `main.py:5096-5193` |
| `friend/search` | {friend_viewer_id, deleted_response_type} | **T1-free** (sniffer-verified, actively used) | `main.py:5161-5164` |
| `home/index` | {} or minimal | **T2-known-payload** (test data shapes the response: home_info{available_continue_num,...}, free_data_set) | `main.py:1183`; `test_dashboard_shop_logs_20260622.py:79-87` |
| `support_card/enhance` | {support_card_id, use_item_array[{item_id,item_num}]} | **T2-known-payload** (analog to item-use/exchange endpoints) | `main.py:1216` |
| `chara/talent` | {trained_chara_id, skill_id\|talent_level} | **T2-known-payload** (skill/talent awaken; mirrors gain_skills shape) | `main.py:1229` |
| `item/use` | {item_id, client_own_num, item_num} | **T2-known-payload** (mirrors `use_recovery_item :900-927`) | `main.py:1230` |
| `chara/nickname` | {trained_chara_id, nickname_id} | **T3-derivable** (cosmetic epithet set) | `main.py:1228` |
| `friend/add` | {friend_viewer_id} | **T3-derivable** (analog to friend/search) | `main.py:1217` |
| `exchange/item` | {exchange_id, count} | **T3-derivable** (out-of-career shop; cf. `multi_item_exchange :1051`) | `main.py:1215` |
| `mission/receive` | {mission_id} or list-then-claim | **T4-needs-live-sniff** *(re-tiered)* | `main.py:1171` |
| `team/evaluation` | {team_id, deck[]} (team-specific) | **T4-needs-live-sniff** | `main.py:1231` |
| `single_mode_free/pre` | {} or scenario filters | **T4-needs-live-sniff** (distinct from pre_single_mode/index) | `main.py:1202` |
| `single_mode/load` (non-free) | minimal/empty | **T3-derivable** (tests reference; likely mirrors single_mode_free/load) | tests |

> **Re-tier (verifier):** `mission/receive` is in the pacing table but **never called**, with **no test mock, no sniff, no derivable pattern** — moved **T3 → T4**. It still belongs in Section 5 / Top-10 as a high-value target *once sniffed* (it is the present-box/mission claim path).

---

## 5. Untapped Game Subsystems

Mapped from the master-data catalog (`data/master_table_catalog_core.json`). READ-only metadata is generally **T1-free**; WRITE/entry payloads range T2-T5. **All `catalog:NNNN` line citations removed (invented notation); groundings are table names. Row counts corrected per verifier where the catalog was wrong.**

### Mostly READ-available now (T1-free reads)
- **Campaign / bonus multipliers** — tables `campaign_data` *(161 rows, not 110)*, `campaign_present_bonus_detail` *(68, not 86)*, `campaign_single_race_add_data` *(18, not 46)* / `_reward`; auto-applied in race_end responses, no claim needed. **T1-free**
- **Main Story races** — entered via `single_mode_free/race_entry` with a story program_id; bonuses auto. Tables `main_story_data, main_story_race_bonus, main_story_race_chara_data`. **T1-free**
- **Succession / inheritance** — fully wrapped in `start_career` (owned + rental). Tables `succession_factor, _effect, _initial_factor, _relation, _rental`. **T1-free**
- **Honor / epithet tracking** — derived from race history; table `honor_data`; `runner.py:4177`. **T1-free**
- **Item exchange (career shop)** — wrapped (`multi_item_exchange`). Tables `item_exchange, single_mode_free_shop, _item, _effect`. **T1-free**
- **Jukebox** — READ-only flavor metadata; `jukebox_music_data`. **T1-free**
- **Audience / crowd** — cosmetic render metadata; `audience_data`. **T1-free**
- **Announcements** — in load/index; `announce_data` *(84 rows — verifier-confirmed correct)*. **T1-free**
- **Cosmetics (READ)** — `dress_data, profile_card_bg, name_card_bg`. **T1-free reads**

### Login / mail / missions
- **Login bonus** — tables `login_bonus_data, _detail`; likely auto-claimed on load/index, else a simple ID claim. **T2-known-payload (read) / T4 (write if not auto)**
- **Present box / gift inbox** — presents likely surface in load/index; claim via a `present/receive {present_id}` or bulk write. **T1-free (read latent — see 3B) / T4-needs-live-sniff (write)**; table `gift_message`.
- **Missions** — `mission/receive` endpoint is real; table `mission_data`. List visible in load/index (`mission_progress`, 3B); claim payload **unsniffed**. **T1 read / T4 write.**

### Card / character progression
- **Support card enhance / LB** — tables `support_card_limit` *(3 rows, not 104)*, `support_card_level` *(135, not 338)*; payload derivable from item-use shape. **T2-known-payload**
- **Card talent / hint unlock** — tables `card_talent_upgrade, _hint_upgrade, support_card_unique_effect`. **T2-known-payload**
- **Chara talent / nickname** — `chara/talent` (T2), `chara/nickname` (T3). `main.py:1228-1229`
- **Dress / profile / name-card equip (WRITE)** — `{trained_chara_id, dress_id|bg_id}`. **T2-known-payload** (cosmetic)
- **Trainer profile edit** — `profile/edit {name, comment}`. **T2-known-payload**

### Racing subsystems beyond career
- **Story Events (time-limited)** — tables `story_event_data` *(16 rows, not 108)*, `_mission, _bingo_reward, _point_reward, _story_data, _win_bonus, _top_chara`; mission/bingo/point claims likely ID-based; event races mirror single_mode_program. Event KB at `data/event_effects.json` (2509 events). **T2-known-payload**
- **Team Stadium** — tables `team_stadium` *(1 row, not 53)*, `_rank, _class, _class_reward, _evaluation_rate`; `team/evaluation` referenced; entry mirrors race_entry but team fields unknown. **T4-needs-live-sniff**
- **Team Building (co-op)** — tables `team_building_data, _race, _race_npc, _rank, _basic_reward, _rank_reward_group`. **T3-derivable**
- **Legend Race** — tables `legend_race, _npc, _boss_npc, _billing`; likely under race/entry with a legend flag. **T3-derivable**
- **Challenge / training-exam races** — tables `training_challenge_master, _exam, _score, _total_score`; follows legend pattern. **T3-derivable**
- **Fan Raid (co-op)** — tables `fan_raid_data, _all_reward, _individual_reward, _top_data, _top_chara`. **T3-derivable**
- **Daily Race** — tables `daily_race` *(8 rows, not 248)*, `_npc, _billing`; entry WRITE not derivable. **T4-needs-live-sniff**
- **Champions Meeting (PvP)** — 20+ `champions_*` tables (`schedule, round_detail, entry_reward, evaluation_rate, reward_rate, race_condition`); entry/submit WRITE not derivable. **T4-needs-live-sniff**

### Minigames / social / story
- **Crane game** — tables `crane_game_define_param, _arm_swing, _catch_result, _prize_pattern, _hidden_odds`; play WRITE (arm-swing mechanics) server-side. **T4-needs-live-sniff**
- **Live / concert** — tables `live_data, live_extra_data, live_permission_data`; start/finish + score WRITE unknown. **T4-needs-live-sniff**
- **Home story / dorm events** — tables `home_event_schedule, home_story_trigger, home_poster_data`; likely `home/story {story_id, choice}` (cf. check_event); `read_info` adds home_story arrays (`client.py:931`). **T2-known-payload**
- **Circle / club WRITE** — read via `circle/detail` (T1); join/leave/stamp likely `circle/join {circle_id}`; tables `circle_rank_data, circle_stamp_data`. **T3-derivable**
- **Friend WRITE** — `friend/add {viewer_id}`, `friend/accept`. **T3-derivable**
- **Limited / seasonal exchange** — tables `limited_exchange, _reward, _reward_odds`; mirrors item_exchange. **T3-derivable**
- **Story / main-scenario unlock (WRITE)** — `story/play|finish|unlock {episode_id}`. **T4-needs-live-sniff**

### Gacha (scouting)
- **Gacha** — tables `gacha_available` *(11694 rows, not 70)*, `gacha_data` *(122, not 214)*, `gacha_prize_odds` *(0 rows — empty on disk, not 338)*, `gacha_exchange, gacha_free_campaign, gacha_piece, gacha_stock_campaign`; READ (banners) derivable, but **pull WRITE payload not derivable from data** (confirmed by prior research), and **odds table is empty on disk** so odds-modeling is not even a local-data win. **T4-needs-live-sniff (write) / T5 (odds modeling — no data).**

---

## 6. The Bot's Own Local Server API (FastAPI, `main.py`)

**Comm model:** REST + JSON, Pydantic models. **No WebSocket/SSE/long-poll** — the v3 frontend polls `/api/career/runner` every 1.5-2s on a cached loop to avoid stalling the event loop. Static mounts: `/legacy` (old UI), `/` (v3 catch-all), `/races` (banners). The `on_api_log` hook streams game events to TRACE_DIR but **no live stream is exposed**, and **no "raw call any game endpoint" debug route exists**. All routes **T1-free**.

> **Route-count correction (verifier):** the codebase has **147 `@app` decorators** in `main.py` (not ~89). Subsystem partitions corrected below: **23 `/api/career/*` routes** and **23 AI routes** (15 GET + 8 POST). Career sub-routes are namespaced **`/api/career/runner/...`** (not bare `/runner/...`).

### Auth / session / selection
`/api/login` POST, `/api/logout` POST, `/api/session` GET, `/api/selection` POST (persists picker to disk). `main.py:2573, 5305, 5227, 5292`

### Career control — 23 routes (corrected names + folded-in missing routes)
- Control: `/api/career/start` POST, `/api/career/run` POST (single `run_count=1` | loop `N` | infinite `0`), `/api/career/runner` GET (live poll), `/api/career/runner/stop` POST, `/api/career/runner/pause` POST, `/api/career/runner/resume` POST, `/api/career/runner/burn_clocks` POST, `/api/career/runner/skill_intercept` POST *(dev-only)*, `/api/career/runner/skill_decision` POST *(dev-only)*, `/api/career/action` POST (manual exec_command), `/api/career/delete` POST (force-delete), `/api/career/rescue` POST (probe race_out/end/start to unstick).
- **Trace / history / reporting (verifier-flagged MISSING — now folded in):** `/api/career/snapshots/latest` GET (`5959`) + `/download` (`5984`), `/api/career/decision-trace/latest` GET (`6219`) + `/download` (`6244`), `/api/career/live_history` GET (`6772`), `/api/career/report` GET (`6793`), `/api/career/crash_trace` GET (`6852`), `/api/career/history` GET (`6889`).
- **Setup/pickers under /api/career (folded in):** `/api/career/friends` POST (`6964`), `/api/career/guest_parents` POST (`7073`) + `/api/career/guest_parents/raw` GET (`7009`).

### Setup / parents
`/api/parents/remove` POST, `/api/parents/remove-recent` POST (dry-run preview). `main.py:6623-6690`

### Presets / settings
`/api/presets` GET/POST + `/delete` + `/save_races`; `/api/settings-presets` GET/POST/delete/active; `/api/skill-config` GET/POST; `/api/smart-solver/config` GET/POST; `/api/settings/theme|turn-delay|speed|tp-recovery` GET/POST; `/api/events` GET + `/override` + `/overrides/clear`. `main.py:4407-4518, 2586-2969, 3011-3128`

### Userdata
`/api/userdata/info` GET, `/set-path` POST (writes `~/.icarus/userdata_pointer.json`), `/intro-dismissed` POST, `/reopen-intro` POST. `main.py:2689-2778`

### Character / trainee / skills / training
`/api/character-profile/active|list|roster|colors` GET, `/auto-pick` POST, `/epithets` POST; `/api/trackblazer/epithets|solver/status|solver/defaults|races` GET, `/plan` POST; `/api/trainee/profile` POST, `/profile-refresh(+/status)`, `/recommended-supports` GET, `/support-setups` GET; `/api/skills` GET, `/optimizer` GET/POST, `/weighted-preview` POST; `/api/training/goal-lookahead` GET/POST; `/api/supports/details` GET. `main.py:4025-4498, 3306-3996, 3399-3428`

### Master data / club / metrics / health
`/api/master-data/status` GET, `/path` POST, `/generate` POST; `/api/circle/{circle_id}` GET, `/api/club_by_member/{trainer_id}` GET (friend/search → circle/detail); `/api/metrics` GET; `/api/health` GET (live beacon). `main.py:3462-3489, 5096-5224, 6864-6867, 5890-5944`

### AI / diagnostics — 23 routes (15 GET + 8 POST; verifier correction)
- GET: `/api/ai/status, /advisor/latest, /dataset/download, /post-run/latest, /model/download, /safe-debug-bundle, /dashboard, /shadow/latest, /backtest/latest, /config-suggestions/latest, /style-adaptation/latest, /local-llm/latest, /auto-training/status, /diagnostics/summary, /diagnostics/bundle`.
- POST (verifier-flagged MISSING — now folded in): `/api/ai/rebuild-dataset, /import-logs, /train-now, /local-llm/config, /local-llm/test, /local-llm/analyze-latest-run, /local-llm/shadow-advice, /auto-training/config`. `main.py:6026-6216`

### Multi-account manager
`/api/accounts` GET/POST, `/accounts/status` GET (all-instance health), `/accounts/manager/start` POST (launches manager.py supervisor; shares `ICARUS_USERDATA_DIR`). `main.py:5771-5887`

### Notifications / misc
`/api/settings/discord-webhook` GET/POST + `/test`; `/api/changelog` GET; `/api/logs/export` GET (redacted zip). `main.py:3431-3460, 7330-7359, 7306-7327`

### Asset serving
`/api/images/{name}`, `/api/card-art/{name}`, `/api/skill-icons/{name}`, `/api/item-icons/{name}`; `/styles.css`, `/app.js`, `/skill_intercept_ui.js` *(dev-only)*; `/`, `/legacy`, `/v3`(+`/{rest}`), `/assets/data/{file}`, `/races/{file}`, `/css/{file}`, `/js/{file}`, branding PNGs, root catch-all StaticFiles. `main.py:7228-7572`

### Unused / latent / dev-only local routes
- **`/api/debug/raw_load`** — stub, storage disabled (deprecated). `main.py:7211-7213`
- **`/api/debug/start_state`** — diagnostic-only pre_single_mode cache dump. `main.py:7206-7208`
- **`/api/career/runner/skill_intercept`, `/skill_decision`, `/skill_intercept_ui.js`** — dev-only, inert/absent in public builds (STANDING RULE: never ship intercept).

### New local-comm ideas (feasible)
- **Live event stream (SSE/WebSocket)** off the existing `on_api_log` hook → real-time UI instead of 1.5-2s polling. **T2** (hook exists; needs an endpoint)
- **Raw game-endpoint debug route** — expose `active_client.call(ep, args)` behind a dev guard to exploit the generic invoker for sniffer-discovered endpoints without code changes (this is the literal "new way to communicate"). **T2** (transport already generic; intentionally absent today)
- **Latent-data passthrough** — surface the Section 3A/3B truly-unread fields (bonds-detail are already used; the genuinely new ones: training_level_info_array, present_box, missions, login_bonus, stat ceilings, playing_state, free_continue_time) via new read-only `/api/*` routes. **T1-free** (pure parsing)

---

## 7. External / Unverified Endpoints (web research — NOT confirmed against live API)

All tagged **EXTERNAL/UNVERIFIED**; corroboration only.
- **Architecture corroboration** — community confirms msgpack + AES; **CarrotJuicer** (GitHub CNA-Bld) decompiles Umamusume msgpack packets ("first ~114 bytes differ per request, remainder standard msgpack" — consistent with the in-repo 4+52(HEAD)+16(SID)+16(UDID)+32(nonce) envelope prefix). **T1-free** (tooling).
- **SimpleSandman/UmaMusumeAPI** (archived Oct 2025) — REST wrapper over **master.mdb static data** (raw tables, condensed views, succession-recommendation procs). NOT the live game server. **T1-free** (static data).
- **Umapyoi.net public API** — public static Uma game data (characters/items/skills). **T1-free** (static data).
- **Umaplay** (GitHub Magody/Umaplay) — screen-driven auto-trainer; no published endpoint list. External reference only.
- **umamusume-sweepy** (GitHub SweepTosher) — headless bot, the upstream of this repo. External reference only.

> Prior research already **ruled out** deriving WRITE payloads for daily-race/gacha/club-join/champions from data alone, and confirmed the API already sends exact training stat-gains (so an "exact stat-gain scorer" is moot). These stay **T4-needs-live-sniff** / **T5** unless the user's packet sniffer captures them — a valid path given the user owns one.

---

## Feasibility Tally (corrected)

- **T1-free (in hand):** 27 live endpoints (25 wrapped + circle/detail + friend/search) + ~20 *truly-unread* response fields (3A) + ~10 latent account-level objects (3B) + ~10 READ-only subsystems + **147 local server routes** + tracing/replay/generic-invoker/device+locale spoofing + latent-data local passthrough idea. *(Note: ~10 fields the catalog called "latent" are actually already read — moved to 3C.)*
- **T2-known-payload:** reserve_race; home/index, support_card/enhance, chara/talent, item/use; login-bonus read, support-card LB/level, card-talent/hint, story-event mission/bingo/point claims, home/story, dress/profile/name-card equip, profile edit; local SSE stream + raw-call debug route.
- **T3-derivable:** chara/nickname, friend/add, friend/accept, exchange/item, single_mode/load; team-building, legend-race, challenge-race, fan-raid, limited-exchange, circle join/leave/stamp.
- **T4-needs-live-sniff:** **mission/receive (re-tiered from T3)**, present-box write, daily-race entry, champions entry/submit, crane play, live start/finish, story unlock, team-stadium/team-evaluation write, single_mode_free/pre.
- **T5-ruled-out:** gacha pull WRITE (data-underivable) + gacha-odds modeling (`gacha_prize_odds` empty on disk), request batching, alternate protocols (WS/gRPC), dynamic master-data endpoint, "exact stat-gain scorer" (API already provides gains).

---

## TOP 10 HIGH-VALUE, LOW-RISK NEXT STEPS (ranked)

1. **Parse the truly-unread latent fields you already receive (3A) — zero new API calls.** `training_level_info_array` (exact per-NPC stat gains, never read), `unchecked_event_array` *detail* (event_id/reward_type — runner reads length only, `runner.py:858/1226`), `playing_state` (soft-lock auto-detect), `free_continue_time` (sleep-to-clock), non-vital stat ceilings (cap-aware training). **T1-free**, highest ROI, no detection risk.
2. **Auto-claim missions + present-box reads now, claim later.** Surface `mission_progress`, `present_box`, `login_bonus_progress`, `gacha_ticket_array` from load/index (3B) — all **T1-free reads** today. The *claim* write (`mission/receive`) is **T4 (re-tiered)**: capture it once with the user's sniffer, then call via the generic invoker. Read first (free), write after one sniff.
3. **Call the already-wrapped `reserve_race` — batch race scheduling.** Fully wrapped at `client.py:1112-1117`, never invoked; payload known. **T2**, in-protocol, indistinguishable from normal play.
4. **Add a dev-guarded "call any game endpoint" debug route.** Expose `active_client.call(ep, args)` behind the same dev guard as skill_intercept. Turns every sniffer-discovered endpoint into a same-day capability with no transport code. **T2** — the single highest-leverage "new way to communicate."
5. **SSE/WebSocket live stream off `on_api_log`.** The per-event hook already fires for every game call; one new endpoint replaces the 1.5-2s `/api/career/runner` poll with a real-time feed. **T2**, local-only, no game-side risk.
6. **`support_card/enhance` (LB/level support cards).** Pacing-table-referenced (`main.py:1216`); payload mirrors the item-use shape. Between-careers automation win. **T2**.
7. **`chara/talent` (skill/talent awaken).** `main.py:1229`; mirrors `gain_skills`. Out-of-career progression. **T2**.
8. **`item/use` (generic out-of-career item consumption).** `main.py:1230`; direct mirror of `use_recovery_item` (`client.py:900-927`). **T2**.
9. **Read-only subsystem status dashboard (campaign/announcements/circle/fan).** `campaign_data`, `announce_data` (84 rows, in load/index), `circle/detail` (already used) — surface bonus-window + maintenance + announcement state read-only. **T1-free**, pure passthrough.
10. **`home/index` + `data_headers` maintenance/clock-skew probe.** `home/index` response shape is known from test data (`test_dashboard_shop_logs_20260622.py:79-87`) — **T2**; pair with reading `data_headers.server_time / maintenance_mode_flag` (currently ignored, `client.py:699-754`) — **T1-free** — to gate runs around maintenance and detect clock skew.