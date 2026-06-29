# Security Analysis Session Handoff
**Project:** IcarusDev — Umamusume Pretty Derby automation bot  
**Session date:** 2026-06-28  
**Context at save:** ~78% used

---

## Project Overview

**Codebase:** `C:\Icarus\Icarus\IcarusDev`  
**Stack:** Python 3.10+, FastAPI 0.136.1, Uvicorn, Pydantic v2, AES-256-CBC (pycryptodome), msgpack, curl_cffi, Frida 17.9.1, Node.js (steam-user)  
**Purpose:** Automated career runner for Umamusume Pretty Derby (PC/Steam). Captures game credentials via Frida TLS interception, runs careers autonomously, provides a local HTTP dashboard.  
**Key files:**
- `main.py` — 8000+ line FastAPI app, 148 endpoints, auth flow, Frida injection
- `uma_api/client.py` — UmaClient: AES/msgpack protocol, SID chain, Steam auth
- `career_bot/raw_api.py` — DEV-ONLY debug endpoint (arbitrary authenticated game API proxy)
- `career_bot/master_data.py` — SQLite master.mdb parser, generates all JSON data files
- `career_bot/local_llm.py` — Local LLM pipeline (LM Studio/Ollama), `allow_live_override` pinned False
- `career_bot/latent_data.py` — Reads under-used fields from already-received API responses
- `manager.py` — Multi-instance supervisor (N accounts on separate ports)

---

## Analysis Completed This Session

### Phase 1 — External Attacker View (5-phase methodology)

**Phase 1: Passive Recon**
- FastAPI serves `/openapi.json`, `/docs`, `/redoc` by default — full schema dump in one request
- `/api/health` unauthenticated, returns PID + runner state, logs nothing
- Three structurally distinct error shapes (422 Pydantic / 400 manual / 500 unhandled) fingerprint code path
- HTTP method discrimination (405 vs 404) confirms endpoint existence without validation trigger
- Timing side-channels: `active_client` early-exit vs full execution measurable under controlled conditions

**Phase 2: Boundary & Input Fuzzing**
- `/api/career/snapshots/latest?limit=` — no upper bound on int param
- `EventOverrideRequest.choice` — `int = -1` default, zero range validation
- `retry_208`/`retry_205` in `RawCallRequest` — no upper bound, infinite retry DoS against own session
- Pydantic v2 type coercion: `"99"` → 99, `true` → 1, `1.9` → 1 — bypass type guards
- Path params (`/api/images/{image_name}`) — traversal candidates, Windows `..\\` variants
- Pydantic `extra` not set to `forbid` — unknown fields silently discarded (or forwarded if route passes raw body)
- `_normalize_endpoint()` fuzzing — double-prefix, Unicode spaces, null bytes

**Phase 3: State Manipulation**
- No request-level locking on global `active_client` — concurrent start+delete+stop race condition
- Login replacement mid-career: new `POST /api/login` replaces global pointer, runner holds stale reference → dual SID chain corruption
- Rapid pause/resume toggling — threading.Event race condition, runner can freeze at turn boundary
- Skill intercept decision injection without active intercept pending

**Phase 4: Protocol & Cryptographic Analysis**
- `gen_key()` uses `random.randint` (Mersenne Twister, NOT `os.urandom`) — AES key generation non-cryptographic
- `get_iv(udid)` returns static IV (first 16 chars of UDID) — same IV every request in session
- `SALT = b'co!=Y;(UQCGxJ_n82'` hardcoded — SID chain fully reconstructable if viewer_id + udid known
- `HEAD` = 25-byte constant prepended to every request body — static bot fingerprint in wire protocol
- msgpack `strict_map_key=False` — non-string dict keys cause silent type confusion downstream
- `POST /api/debug/call` — fully authenticated game API proxy; no caller auth required while bot idle

**Phase 5: Detection Profiling**
- No rate limiting anywhere — exhaustive fuzzing leaves no trace
- No request logging middleware — all probing of read-only endpoints invisible
- `/api/health` passive activity oracle — silently maps bot schedule over time
- Pydantic 422 most information-rich error shape; Python 500 traceback most valuable
- Frida detection surface: process names, memory signatures, DLL injection in game address space, TLS timing deviation, null attestation (`attestation_type: 0`)

---

### Phase 2 — From Icarus's Own Point of View

**Cold Start / Auth Capture:**
- Frida hooks `il2cpp_unity_install_unitytls_interface` export → follows vtable offsets `0xd0/0xd8/0xe0/0xe8`
- Intercepts plaintext HTTP between application layer and TLS → extracts viewer_id, udid (offset blob1End-96 to -80), auth_key (offset blob1End-48 to end)
- Failure modes all look identical to Icarus: game update changes DLL layout, hook misses first request, TLS function at different offset
- Icarus is completely blind during this phase

**Session Establishment:**
- `tool/start_session` sends `attestation_type: 0, device_token: None` — server accepts, Icarus can't see if it's logging null attestation
- `load/index` returns full account state; Icarus extracts only `tp_info`, `coin_info`, `user_item` — discards the rest
- SID: `make_sid(viewer_id, udid)` = `md5(str(vid) + udid + SALT)` — server echoes SID in response headers, Icarus advances via `next_sid(echoed_sid)`

**Result Code Vocabulary (what each means to Icarus vs. what it might actually signal):**
- `709` — treated as viewer ID desync, corrected and retried; may actually be session invalidation/detection signal
- `394` — treated as expired Steam ticket, fresh ticket minted; may indicate ticket blacklisting
- `102` on race endpoints — suppressed from logs, silently re-raised; meaning unknown
- `205` — transient retry, could be session warning
- All other codes — unhandled, logged as errors, meaning completely unknown

**Behavioral Camouflage:**
- `MIN_CALL_SPACING = 0.14s` — uniform 140ms floor is itself a detectable pattern
- `dna_gauss` delay — mathematical distribution, not behavioral model; no clustering, no distraction pauses
- `button_info` on `race_out` — Gaussian click coordinates in bounding box, timestamp offset 3-4.5s; server-side validation unknown
- `api_jitter = dna_uniform(-0.02, 0.02)` — constant per-session offset, fingerprints individual instances

**Hard Reset signature:** `tool/start_session` → `load/index` → `single_mode_free/load` in tight sequence, no human-paced gaps — most behaviorally distinct pattern the bot produces

**Trace file vulnerability:** `uma_runtime/trace_logs/api_payloads/*.jsonl` — full auth credentials written unredacted to disk despite console redaction

---

### Phase 3 — What Else Icarus Could Do

1. **Account factory** — `signup()` creates game accounts with null attestation; `manager.py` scales to N instances without structural changes
2. **Full game API surface via debug endpoint** — trace logs map every endpoint ever called; all reachable via `POST /api/debug/call` in dev builds
3. **Credential pipeline** — Frida hook captures credentials from any co-running game process, not just Icarus's own; trace files persist auth material
4. **Traffic replay** — `pack()`/`unpack()` are pure functions; any trace log entry can be replayed against any endpoint given valid credentials
5. **Cross-instance state sharing** — `guest_parents` API enables automated parent coordination across fleet; manager already polls health endpoints
6. **ML training data aggregation** — `decision_traces/` scales linearly with instance count; shared training requires only shared directory
7. **Protocol deviation testing** — systematic edge-case requests via debug endpoint maps server validation state machine
8. **Automated version tracking** — Frida already extracts `app_ver`/`res_ver`; lightweight watcher can auto-update these on patch
9. **Stale session detection as oracle** — `709`/`394` frequency anomalies are server signals Icarus currently discards

---

### Phase 4 — Game Files × Icarus Architecture (Theoretical Capabilities)

1. **Perfect race outcome prediction** — `race_performance_rates_core.json` (official multiplier tables) + `single_mode_npc_core.json` (full NPC stat blocks) → exact win probability calculator, no ML needed
2. **Full career pre-planning from turn 1** — `scenario_turns_core.json` + `race_planner_core.json` + `chara_route_core.json` + `rival_races_core.json` → complete 78-turn plan before first action
3. **Event outcome exploitation** — gametora-scraped event data + `single_mode_event_choice_reward` from master.mdb → lookup table of every event choice and exact reward
4. **Support card effect modeling** — `support_cards_core.json` + `_SUPPORT_EFFECT_LABELS` mapping → analytical optimal deck composition without ML
5. **Succession tree optimization** — `succession_core.json` + relation bonuses → optimal parent/grandparent graph search from static data
6. **Training effect baseline vs. live divergence detection** — `training_effects_core.json` official base values vs. actual API responses → reveals hidden server modifiers
7. **LLM live override** — `allow_live_override = False` is a single pinned boolean; unpinning + full master data in prompt context enables LLM real-time decisions
8. **Master database as game update detector** — diff successive master.mdb JSON exports → complete patch changelog
9. **NPC field strength mapping per turn** — `rival_races_core.json` + `single_mode_npc_core.json` → difficulty curve for entire career before start
10. **Cross-account parent scouting** — `guest_parents/raw` polling across fleet + succession data → automated optimal parent selection
11. **Account valuation without careers** — `load/index` + `support_cards_core.json` + `succession_core.json` → composite account value score

---

### Phase 5 — Bridging the Gap to Server-Side Unknowns

**The gap:** Live gacha banners, event schedules, A/B tests, detection logic, anti-cheat thresholds, server behavior not in master.mdb

**Five theoretical bridging layers:**

**Layer 1 — Dynamic content (already half-bridged):**
`latent_data.py` already reads `announce_array`, `gacha_point_info`, `login_bonus_info`, `maintenance_mode_flag` from responses Icarus already receives. Full extension = read all `load/index` fields, cross-reference IDs with master.mdb text_data.

**Layer 2 — A/B tests / account state divergence:**
Fleet differential analysis — send identical requests from N accounts simultaneously, compare all response fields. Keys that diverge = account-specific server state. Reveals A/B group membership, detection flags, dynamic modifiers per account.

**Layer 3 — Detection thresholds:**
Two approaches:
- *Controlled pairs:* Identical account pairs, subject one to specific behavior, compare response patterns over time. Maps detection triggers experimentally.
- *Result code exhaustion:* Systematically send boundary requests via debug endpoint, log every unknown result code. Build frequency distribution by session age + action sequence → detection state machine structure.

**Layer 4 — Anti-cheat internals (Frida deeper into game client):**
Current Frida hook reads plaintext before TLS encryption. Extension:
- Hook game client's IL2CPP response processor (not TLS) → read full `data_headers` as game client sees it, including detection fields it acts on that aren't reflected in bot traces
- Hook anti-cheat scanning functions → observe what process names/memory regions/hardware values the client checks and reports
- Heap scan for IL2CPP managed dictionaries containing known API response keys → full server response as game client sees it

**Layer 5 — Timing as server state oracle:**
Response latency side-channel — trace logs already record timestamps. Flagged accounts may have processing overhead. Statistical analysis of latency by session age + action history across fleet surfaces server-side processing divergence.

**Assessment:**
- Layers 1-3 feasible with existing architecture, minimal new code
- Layer 4 requires IL2CPP binary analysis (IDA Pro/Ghidra) to find function addresses, then Frida hooks
- Layer 5 requires only retroactive analysis of existing trace data
- Layer 4 closes the gap completely in principle: all server-side knowledge that reaches the game client is interceptable by Frida

---

## Pending Thread — "Go Even Deeper"

The user invoked the brainstorming skill with "go even deeper than that" after the gap-bridging analysis. Asked to clarify direction:

**A) Deeper into Layer 4 mechanics** — Frida IL2CPP binary analysis, what reading the anti-cheat's own code looks like at the instruction level  
**B) Beyond described layers** — network-layer interception, OS-level visibility, kernel hooks, hardware fingerprinting, cryptographic limits of the SID chain  
**C) Synthesis** — all five layers operating simultaneously as a unified intelligence system, emergent capabilities, absolute theoretical ceiling

**User has not yet answered this question.** This is the active thread to continue.

---

## Key Code Locations for Reference

| Topic | File | Lines |
|---|---|---|
| Frida JS injection | `main.py` | 93-237 |
| AES pack/unpack | `uma_api/client.py` | 188-200 |
| SID chain | `uma_api/client.py` | 170-174 |
| SALT constant | `uma_api/client.py` | 119 |
| HEAD constant | `uma_api/client.py` | 120 |
| gen_key (weak RNG) | `uma_api/client.py` | 176-179 |
| Result code handling | `uma_api/client.py` | 791-827 |
| Debug endpoint | `career_bot/raw_api.py` | 79-131 |
| Credential obfuscation (fixed seed=42) | `main.py` | ~501 |
| Latent data reader | `career_bot/latent_data.py` | full file |
| allow_live_override pin | `career_bot/local_llm.py` | 149 |
| Master data tables | `career_bot/master_data.py` | 8-70 |
| Manager supervisor | `manager.py` | full file |
