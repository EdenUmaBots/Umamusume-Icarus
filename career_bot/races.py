import json
from pathlib import Path

from career_bot import trackblazer_rules as tb_rules


class RacePlanner:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.meta = {}
        self.program = {}
        self.instance = {}
        self.official_races = {}
        self.races_by_turn = {}
        self.static_rivals = {}
        self.trackblazer_rewards = {}
        self.performance_rates = {}
        self.rejected = set()
        self.last_live_replan = {}
        self.last_missing_replan = {}
        self._last_live_replan_key = None
        # v6.7.20: rolling diagnostic record of every re-solve, so a career
        # log captures *why* the schedule changed turn-by-turn (which backend
        # ran, whether the exact MILP fell back to the heuristic beam, the
        # race count, current stamina, and which high-value races were dropped
        # versus the previous plan). Capped to keep logs reasonable.
        self.replan_log = []
        self._replan_log_cap = 250
        self._load()

    # --- v6.7.20 re-solve diagnostics -----------------------------------
    @staticmethod
    def _high_value_races(plan, min_fans=15000):
        """Return {program_id: (turn, name, est_fans)} for the high-fan races
        in a plan's schedule. Used to detect when a re-solve silently drops a
        big race (Japan Cup, Arima, Tenno Sho, etc.)."""
        out = {}
        for row in (plan or {}).get("schedule") or []:
            try:
                fans = int(row.get("est_fans") or row.get("fans") or 0)
            except (TypeError, ValueError):
                fans = 0
            if fans >= min_fans:
                try:
                    pid = int(row.get("program_id") or 0)
                except (TypeError, ValueError):
                    pid = 0
                if pid:
                    out[pid] = (int(row.get("turn") or 0), str(row.get("name") or ""), fans)
        return out

    def _push_replan_log(self, record):
        try:
            self.replan_log.append(record)
            if len(self.replan_log) > self._replan_log_cap:
                # keep the most recent entries
                self.replan_log = self.replan_log[-self._replan_log_cap:]
        except Exception:
            pass

    # --- v6.7.21 "Disable Schedule Re-Plan Upon Race Loss" ---------------
    @staticmethod
    def _history_has_loss(history):
        """True if any recorded race result is a non-1st finish. Rows come from
        the runner's race_results ledger (each carries `won` and/or `rank`)."""
        for row in history or []:
            if not isinstance(row, dict):
                continue
            won = row.get("won")
            if won is False:
                return True
            if won is None and "rank" in row:
                try:
                    if int(row.get("rank") or 1) != 1:
                        return True
                except (TypeError, ValueError):
                    continue
        return False

    def _load(self):
        path = self.base_dir / "data" / "race_map.json"
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.meta = {int(k): v for k, v in (data.get("meta") or {}).items()}
        self.program = {int(k): v for k, v in (data.get("program") or {}).items()}
        self.instance = {int(k): [int(item) for item in v] for k, v in (data.get("instance") or {}).items()}
        self._load_official_race_core()
        self._load_trackblazer_p0_core()

    def _load_official_race_core(self):
        """Load master.mdb-derived race metadata when available.

        The legacy race_map remains the compatibility source. This enrichment is
        only used for labels and safer fallback scoring.
        """
        path = self.base_dir / "data" / "race_planner_core.json"
        if not path.exists():
            return
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        for row in rows if isinstance(rows, list) else []:
            try:
                program_id = int(row.get("program_id") or 0)
                turn = int(row.get("turn") or 0)
            except Exception:
                continue
            if not program_id:
                continue
            self.official_races[program_id] = row
            if turn:
                self.races_by_turn.setdefault(turn, []).append(row)
            self.program.setdefault(program_id, {})
            self.program[program_id].update({
                "name": row.get("name") or self.program[program_id].get("name", ""),
                "race_instance_id": row.get("race_instance_id") or self.program[program_id].get("race_instance_id", 0),
                "ground": row.get("ground") or self.program[program_id].get("ground", 0),
                "distance": row.get("distance_m") or self.program[program_id].get("distance", 0),
                "grade": row.get("grade", ""),
                "turn": turn,
                "fan_set_id": row.get("fan_set_id") or self.program[program_id].get("fan_set_id", 0),
                "fans": row.get("fans") or self.program[program_id].get("fans", 0),
                "need_fan_count": row.get("need_fan_count") or self.program[program_id].get("need_fan_count", 0),
                "reward_set_id": row.get("reward_set_id") or self.program[program_id].get("reward_set_id", 0),
            })

    def _load_json_file(self, name, default):
        path = self.base_dir / "data" / name
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _load_trackblazer_p0_core(self):
        rivals = self._load_json_file("rival_races_core.json", [])
        for row in rivals if isinstance(rivals, list) else []:
            try:
                chara_id = int(row.get("chara_id") or 0)
                turn = int(row.get("turn") or 0)
                pid = int(row.get("race_program_id") or 0)
            except Exception:
                continue
            if chara_id and turn and pid:
                self.static_rivals.setdefault((chara_id, turn), {})[pid] = int(row.get("rival_chara_id") or 0)

        rewards = self._load_json_file("trackblazer_race_rewards_core.json", [])
        for row in rewards if isinstance(rewards, list) else []:
            try:
                pid = int(row.get("program_id") or 0)
            except Exception:
                continue
            if not pid:
                continue
            self.trackblazer_rewards[pid] = row
            self.program.setdefault(pid, {})
            first_coin = self._first_place_reward(row.get("coin_rewards") or [], "coin_num")
            first_points = self._first_place_reward(row.get("win_point_rewards") or [], "point_num")
            self.program[pid].update({
                "trackblazer_coin_reward": first_coin,
                "trackblazer_win_points": first_points,
                "trackblazer_reward_score": first_coin + first_points,
                "race_group_ids": row.get("race_group_ids") or [],
            })

        rates = self._load_json_file("race_performance_rates_core.json", {})
        if isinstance(rates, dict):
            self.performance_rates = rates

    def _first_place_reward(self, rows, key):
        best = 0
        for row in rows or []:
            try:
                if int(row.get("order_min") or 0) <= 1 <= int(row.get("order_max") or 0):
                    best = max(best, int(row.get(key) or 0))
            except Exception:
                continue
        return best

    def _static_rival_race_map(self, state):
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        card_id = int(chara.get("card_id") or chara.get("chara_id") or 0)
        chara_id = int(chara.get("chara_id") or (card_id // 100 if card_id else 0) or 0)
        turn = int(chara.get("turn") or 0)
        return dict(self.static_rivals.get((chara_id, turn), {}))

    def _fallback_race_score(self, chara, program_id):
        info = self.official_races.get(int(program_id or 0)) or self.program.get(int(program_id or 0)) or {}
        score = 0
        grade = str(info.get("grade") or "").upper()
        score += {"G1": 60, "G2": 38, "G3": 26, "OP": 10, "PRE-OP": 4}.get(grade, 0)
        distance = int(info.get("distance_m") or info.get("distance") or 0)
        if distance:
            if distance <= 1400:
                apt = int(chara.get("proper_distance_short") or 1)
            elif distance <= 1800:
                apt = int(chara.get("proper_distance_mile") or 1)
            elif distance <= 2400:
                apt = int(chara.get("proper_distance_middle") or 1)
            else:
                apt = int(chara.get("proper_distance_long") or 1)
            score += max(0, apt - 5) * 12
        ground = int(info.get("ground") or 0)
        if ground == 2:
            score += max(0, int(chara.get("proper_ground_dirt") or 1) - 5) * 10
        else:
            score += max(0, int(chara.get("proper_ground_turf") or 1) - 5) * 10
        return score

    def get_rival_race_map(self, state):
        rivals = (
            state.get("data", {})
            .get("free_data_set", {})
            .get("rival_race_info_array", [])
        )
        out = self._static_rival_race_map(state)
        out.update({
            int(r["program_id"]): int(r["chara_id"])
            for r in rivals
            if "program_id" in r and "chara_id" in r
        })
        return out

    def wanted_programs(self, preset, turn=None):
        result = []
        seen = set()
        current_turn = int(turn or 0)
        for value in preset.get("extra_race_list") or []:
            try:
                race_id = int(value)
            except (TypeError, ValueError):
                continue
            
            pids = []
            if race_id in self.meta:
                info = self.meta[race_id]
                occurrence_turn = int(info.get("turn") or 0)
                if current_turn and occurrence_turn and occurrence_turn != current_turn:
                    continue
                pid = info.get("program_id")
                if pid:
                    pids.append(pid)
            elif race_id in self.program:
                pids.append(race_id)
            else:
                for program_id in self.instance.get(race_id, []):
                    pids.append(program_id)
            
            for pid in pids:
                if pid not in seen:
                    seen.add(pid)
                    result.append(pid)
        return result

    def available_programs(self, state):
        data = state.get("data") or {}
        rca = data.get("race_condition_array") or []
        available = set()
        for item in rca:
            pid = int(item.get("program_id") or 0)
            if pid:
                available.add(pid)
        return available

    def _program_instance_id(self, pid):
        """race_instance_id for a program_id — the STABLE race identity. The game
        offers a race under one program_id 'permission variant' (e.g. Japan Cup
        pid 79) while the solver's plan may hold another variant (pid 1088); both
        share a race_instance_id. Matching on that fixes the marquee-G1 misses."""
        try:
            pid = int(pid or 0)
        except Exception:
            return 0
        row = self.program.get(pid) or self.official_races.get(pid) or {}
        try:
            return int(row.get("race_instance_id") or 0)
        except Exception:
            return 0

    def _resolve_wanted_live(self, wanted, available, turn):
        """Map each wanted (planned) program_id to a RUNNABLE live program_id,
        matching by race_instance_id so program_id variants still match, and
        returning the live id the game actually offers (so race_entry works).
        Preserves wanted order, drops rejected, de-dups."""
        avail = set(available)
        avail_by_instance = {}
        for pid in avail:
            iid = self._program_instance_id(pid)
            if iid:
                avail_by_instance.setdefault(iid, pid)
        out = []
        seen = set()
        for wpid in wanted:
            live = wpid if wpid in avail else None
            if live is None:
                iid = self._program_instance_id(wpid)
                if iid:
                    live = avail_by_instance.get(iid)
            if live and (turn, live) not in self.rejected and live not in seen:
                seen.add(live)
                out.append(live)
        return out

    def forced_program(self, state):
        data = state.get("data") or {}
        home = data.get("home_info") or {}
        commands = home.get("command_info_array") or []
        race_enabled = any(cmd.get("command_type") == 4 and cmd.get("command_id") == 401 and cmd.get("is_enable", 0) for cmd in commands)
        other_enabled = any(cmd.get("command_type") != 4 and cmd.get("is_enable", 0) for cmd in commands)
        if not race_enabled or other_enabled:
            return 0
        for item in data.get("race_condition_array") or []:
            pid = int(item.get("program_id") or 0)
            if pid:
                return pid
        race = data.get("race_start_info") or {}
        return int(race.get("program_id") or 0)

    def check_aptitude(self, chara, program_id, floor=6):
        info = self.program.get(int(program_id or 0)) or {}
        ground = int(info.get("ground") or 1)
        distance = int(info.get("distance") or 1200)
        
        if ground == 2:
            g_apt = int(chara.get("proper_ground_dirt") or 1)
        else:
            g_apt = int(chara.get("proper_ground_turf") or 1)
            
        if distance <= 1400:
            d_apt = int(chara.get("proper_distance_short") or 1)
        elif distance <= 1800:
            d_apt = int(chara.get("proper_distance_mile") or 1)
        elif distance <= 2400:
            d_apt = int(chara.get("proper_distance_middle") or 1)
        else:
            d_apt = int(chara.get("proper_distance_long") or 1)
            
        return g_apt >= floor and d_apt >= floor

    def _program_info(self, program_id):
        pid = int(program_id or 0)
        info = {}
        info.update(self.program.get(pid) or {})
        info.update(self.official_races.get(pid) or {})
        return info

    def _grade_rank(self, program_id):
        info = self._program_info(program_id)
        grade = tb_rules.normalize_grade(info.get("grade") or info.get("race_instance_id"))
        return int(tb_rules.GRADE_RANK.get(grade, 0) or 0)

    def _fan_reward(self, program_id):
        info = self._program_info(program_id)
        for key in ("fans", "fan_count", "base_fans", "fans_num"):
            try:
                value = int(info.get(key) or 0)
            except Exception:
                value = 0
            if value:
                return value
        return 0

    def _trackblazer_reward_score(self, program_id):
        info = self._program_info(program_id)
        try:
            return int(info.get("trackblazer_reward_score") or 0)
        except Exception:
            return 0

    def _distance_bucket(self, program_id):
        info = self._program_info(program_id)
        try:
            distance = int(info.get("distance_m") or info.get("distance") or 0)
        except Exception:
            distance = 0
        if distance <= 0:
            text = str(info.get("distance_type") or info.get("distance") or "").lower()
            if any(key in text for key in ("short", "sprint")):
                return "short"
            if "mile" in text:
                return "mile"
            if any(key in text for key in ("medium", "middle")):
                return "middle"
            if "long" in text:
                return "long"
            return ""
        if distance <= 1400:
            return "short"
        if distance <= 1800:
            return "mile"
        if distance <= 2400:
            return "middle"
        return "long"

    def _surface_key(self, program_id):
        info = self._program_info(program_id)
        text = str(info.get("terrain") or info.get("surface") or "").lower()
        if "dirt" in text:
            return "dirt"
        if "turf" in text:
            return "turf"
        try:
            ground = int(info.get("ground") or 0)
        except Exception:
            ground = 0
        return "dirt" if ground == 2 else "turf"

    # v7.2 — Filter a candidate program-id list down to races whose surface
    # matches the user's mant_config.preferred_surfaces. Returns the filtered
    # list, or an empty list if nothing matches. Callers fall back to the
    # unfiltered pool ONLY when this returns empty (so the bot can still race
    # something if a preferred surface isn't available this turn — but no
    # longer auto-picks dirt when the user only wanted turf).
    def _filter_by_surface_preference(self, program_ids, preset):
        cfg = ((preset or {}).get("mant_config") or {})
        preferred = cfg.get("preferred_surfaces") or []
        # Normalize to a set of lowercase strings.
        wanted = set()
        for s in preferred:
            if not s: continue
            s_low = str(s).strip().lower()
            if s_low in ("turf", "dirt"):
                wanted.add(s_low)
        if not wanted:
            return list(program_ids)  # no preference set; return as-is
        return [pid for pid in program_ids if self._surface_key(pid) in wanted]

    def _aptitude_score(self, chara, program_id):
        dist = self._distance_bucket(program_id)
        surface = self._surface_key(program_id)
        dist_key = {
            "short": "proper_distance_short",
            "mile": "proper_distance_mile",
            "middle": "proper_distance_middle",
            "long": "proper_distance_long",
        }.get(dist, "proper_distance_mile")
        surf_key = "proper_ground_dirt" if surface == "dirt" else "proper_ground_turf"
        try:
            d = int((chara or {}).get(dist_key) or 1)
        except Exception:
            d = 1
        try:
            s = int((chara or {}).get(surf_key) or 1)
        except Exception:
            s = 1
        return max(0, d - 1) + max(0, s - 1)

    def _pref_rank(self, value, preferred):
        if not preferred:
            return 0
        if isinstance(preferred, str):
            preferred = [part.strip() for part in preferred.split(",")]
        norm = [str(item or "").strip().lower() for item in preferred]
        value = str(value or "").strip().lower()
        if value in norm:
            return len(norm) - norm.index(value)
        aliases = {"medium": "middle", "mid": "middle", "sprint": "short"}
        value = aliases.get(value, value)
        norm = [aliases.get(item, item) for item in norm]
        return len(norm) - norm.index(value) if value in norm else 0

    def _truthy_cfg(self, preset, key, default=False):
        cfg = ((preset or {}).get("mant_config") or {})
        return bool(cfg.get(key, default))

    def _smart_solver_train_locked(self, preset, turn):
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("enable_smart_solver_train_lock", tb_rules.SMART_SOLVER_TRAIN_LOCK_DEFAULT):
            return False
        if int(turn or 0) in {int(t) for t in (preset or {}).get("training_blocks", []) if str(t).lstrip('-').isdigit()}:
            return True
        locks = (preset or {}).get("manual_locks") or {}
        lock = locks.get(str(int(turn or 0)), locks.get(int(turn or 0))) if isinstance(locks, dict) else None
        if isinstance(lock, str) and lock.lower() in {"train", "training", "rest", "none", "no_race", "no-race", "train_lock_sentinel"}:
            return True
        plan = (preset or {}).get("trackblazer_last_plan") or (preset or {}).get("trackblazer_plan") or {}
        decisions = plan.get("decisions") or {}
        decision = decisions.get(str(int(turn or 0)), decisions.get(int(turn or 0))) if isinstance(decisions, dict) else None
        return isinstance(decision, dict) and str(decision.get("type") or "").lower() == "train"

    def _sort_races_for_trackblazer(self, pids, state, preset):
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        cfg = ((preset or {}).get("mant_config") or {})
        preferred_distances = cfg.get("preferred_distances", (preset or {}).get("preferred_distances", []))
        preferred_surfaces = cfg.get("preferred_surfaces", (preset or {}).get("preferred_surfaces", []))
        rival_map = self.get_rival_race_map(state)
        def key(pid):
            rival = 1 if int(pid) in rival_map else 0
            dist_rank = self._pref_rank(self._distance_bucket(pid), preferred_distances)
            surf_rank = self._pref_rank(self._surface_key(pid), preferred_surfaces)
            grade = self._grade_rank(pid)
            fans = self._fan_reward(pid)
            reward = self._trackblazer_reward_score(pid)
            aptitude = self._aptitude_score(chara, pid)
            fallback = self._fallback_race_score(chara, pid)
            return (
                rival,
                dist_rank,
                surf_rank,
                grade,
                fans,
                reward,
                aptitude,
                fallback,
                -int(pid),
            )
        return sorted(pids, key=key, reverse=True)

    def _chara_trackblazer_aptitudes(self, chara):
        def rank(value):
            try:
                iv = int(value or 0)
            except Exception:
                iv = 0
            return {8: "S", 7: "A", 6: "B", 5: "C", 4: "D", 3: "E", 2: "F", 1: "G"}.get(iv, "A")
        return {
            "Sprint": rank((chara or {}).get("proper_distance_short")),
            "Mile": rank((chara or {}).get("proper_distance_mile")),
            "Medium": rank((chara or {}).get("proper_distance_middle")),
            "Long": rank((chara or {}).get("proper_distance_long")),
            "Turf": rank((chara or {}).get("proper_ground_turf")),
            "Dirt": rank((chara or {}).get("proper_ground_dirt")),
        }

    def _race_history_for_live_solver(self, state):
        data = (state or {}).get("data") or {}
        history = data.get("race_history")
        if isinstance(history, list) and history:
            return history
        context = data.get("runner_context") or {}
        history = context.get("race_results") or context.get("race_history")
        return history if isinstance(history, list) else []

    def _runtime_support_for_live_solver(self, state):
        context = ((state or {}).get("data") or {}).get("runner_context") or {}
        support = dict(context.get("runtime_support") or {}) if isinstance(context.get("runtime_support"), dict) else {}
        support.setdefault("clocks", int(context.get("clocks_left") or 0))
        support.setdefault("clocks_left", int(context.get("clocks_left") or 0))
        support.setdefault("burn_clocks_enabled", bool((context.get("clock_retry_policy") or {}).get("enabled", context.get("burn_clocks", False))))
        support.setdefault("clocks_enabled", bool(support.get("burn_clocks_enabled")))
        return support

    def _live_replan_key(self, state, turn):
        data = (state or {}).get("data") or {}
        chara = data.get("chara_info") or {}
        history = self._race_history_for_live_solver(state)
        last = history[-1] if history else {}
        context = data.get("runner_context") or {}
        stats_key = (
            int(chara.get("speed") or 0), int(chara.get("stamina") or 0),
            int(chara.get("power") or 0), int(chara.get("guts") or 0), int(chara.get("wiz") or 0),
            int(chara.get("fans") or 0),
        )
        last_key = (int(last.get("turn") or 0), int(last.get("program_id") or 0), int(last.get("rank") or last.get("final_rank") or 0), int(last.get("clocks_used") or 0))
        return (int(turn or 0), len(history), last_key, stats_key, int(context.get("clocks_used") or 0), bool((context.get("clock_retry_policy") or {}).get("enabled", False)))

    # v6.7.16: solver-setting precedence helpers, mirroring the runner's
    # v6.7.11 fix.  The Smart Race Solver Settings UI panel writes to
    # ``preset.trackblazer_solver_settings``, but this re-solve path was
    # reading only ``preset.mant_config`` (empty for UI-set values),
    # silently defaulting Max Streak back to 2 after every race.  That
    # undid the v6.7.11 initial-plan fix at runtime and was the real
    # cause of the persistent low race count: initial plan = streak 5
    # (37 races), then the first re-solve dropped it to streak 2 (~28).
    _APTITUDE_LETTER_TO_INT = {
        "S": 8, "A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1,
    }

    def _solver_setting(self, preset, key, default):
        """First non-None of preset.mant_config[key] /
        preset.trackblazer_solver_settings[key] / default.  Empty string
        counts as unset; numeric zero and boolean False are valid.

        v7.2 — When the user has selected manual race mode
        (``extra_race_list_source == "manual"``), the ``trackblazer_solver_settings``
        lookup is SKIPPED. Those settings (max_races_in_row, fan_bonus,
        optimization_mode, etc.) are scheduler knobs for the Smart Race Solver
        and should not affect bot behavior when the user has hand-picked
        their schedule. The mant_config lookup still runs because those are
        scenario-wide overrides the user explicitly set in Scenario Overrides.
        """
        try:
            mant = ((preset or {}).get("mant_config") or {})
            mc_val = mant.get(key)
            if mc_val is not None and mc_val != "":
                return mc_val
            source_mode = str((preset or {}).get("extra_race_list_source") or "").strip().lower()
            if source_mode == "manual":
                return default
            tss = ((preset or {}).get("trackblazer_solver_settings") or {})
            tss_val = tss.get(key)
            if tss_val is not None and tss_val != "":
                return tss_val
        except Exception:
            pass
        return default

    def _solver_aptitude_floor(self, preset, default_int=6):
        """Resolve min_aptitude_floor honoring both int and letter
        (S/A/B/C/D/E/F/G) forms.  Falls back to default on parse error."""
        raw = self._solver_setting(preset, "min_aptitude_floor", default_int)
        try:
            if isinstance(raw, str) and raw.strip():
                letter = raw.strip().upper()
                if letter in self._APTITUDE_LETTER_TO_INT:
                    return self._APTITUDE_LETTER_TO_INT[letter]
                return int(letter)
            return int(raw)
        except Exception:
            return int(default_int)

    def _replan_smart_schedule(self, state, preset, turn, reason="live", force=False):
        """Re-solve the smart race route from live career state.

        This is the turn-by-turn bridge between static Smart Solver plans and
        current reality.  It feeds the solver current stats, runtime recovery
        support, previous race outcomes, clock policy, and live failed-epithet
        branches so the remaining schedule can change as the run unfolds.
        """
        if str((preset or {}).get("extra_race_list_source") or "").strip().lower() != "smart":
            return None
        cfg = dict((preset or {}).get("mant_config") or {})
        # v1.5: resolve via _solver_setting so the "Live Schedule Re-Planning"
        # UI toggle (stored in trackblazer_solver_settings) is honored, while a
        # mant_config override still wins for backward compatibility.
        if not force and self._solver_setting(preset, "enable_live_smart_replan", True) is False:
            return None
        # v6.7.22: event-driven re-planning (default on). The
        # routine every-turn "live" re-solve is skipped -- the plan is solved
        # once and reused, and only real events (a loss, or a planned race that
        # vanished, handled via reason="missing"/force) trigger a re-solve. This
        # matches the reference behavior and removes the per-turn churn that piled up
        # race streaks and dropped winnable high-fan races. Falls through to
        # solve when no plan exists yet, so the first solve still locks one in.
        if reason == "live" and not force and bool(self._solver_setting(preset, "replan_on_events_only", True)):
            existing = (preset or {}).get("trackblazer_last_plan")
            if existing:
                return existing
        # v6.7.21: "Disable Schedule Re-Plan Upon Race Loss". When enabled and
        # the run has already recorded a loss, keep the existing locked-in plan
        # instead of re-solving the remaining turns. The "missing" re-solve
        # (reason="missing"/force) is exempt: a planned race genuinely became
        # unavailable that turn, so the route must still adapt around it.
        if reason == "live" and not force and bool(self._solver_setting(preset, "disable_schedule_replan_on_race_loss", False)):
            if self._history_has_loss(self._race_history_for_live_solver(state)):
                return (preset or {}).get("trackblazer_last_plan")
        key = self._live_replan_key(state, turn)
        if not force and reason == "live" and key == self._last_live_replan_key:
            return (preset or {}).get("trackblazer_last_plan")
        try:
            from career_bot import trackblazer
            data = (state or {}).get("data") or {}
            chara = data.get("chara_info") or {}
            weights = dict(cfg.get("trackblazer_weights") or (preset or {}).get("trackblazer_weights") or {})
            # Outcome-Risk toggle (Racing Settings): let mant_config override the
            # solver's learned-loss penalty so the user can turn it on/off / tune it.
            _mc = (preset or {}).get("mant_config") or {}
            if _mc.get("enable_outcome_risk") is not None:
                weights["enableOutcomeRisk"] = bool(_mc.get("enable_outcome_risk"))
            if _mc.get("outcome_risk_weight") is not None:
                weights["outcomeRiskWeight"] = _mc.get("outcome_risk_weight")
            weights["currentStats"] = {
                "speed": int(chara.get("speed") or 0),
                "stamina": int(chara.get("stamina") or 0),
                "power": int(chara.get("power") or 0),
                "guts": int(chara.get("guts") or 0),
                "wit": int(chara.get("wiz") or 0),
                "fans": int(chara.get("fans") or 0),
            }
            weights["runtimeSupport"] = self._runtime_support_for_live_solver(state)
            weights["currentTurn"] = max(1, int(turn or 0))
            race_history = self._race_history_for_live_solver(state)
            trainee_id = chara.get("card_id") or chara.get("chara_id") or ""
            # v6.2: resolve the active character profile and layer its solver
            # overrides + epithet goals under the preset's explicit values.
            # Preset wins if set; profile fills in.
            from career_bot import character_profiles
            profile = character_profiles.resolve_profile(
                card_id=chara.get("card_id") or 0,
                chara_id=chara.get("chara_id") or 0,
                scenario_id=4,
                base_dir=self.base_dir,
                preset_name=(preset or {}).get("name", ""),
                chara_info=chara,
            )
            profile_weights = profile.solver_weight_overrides()
            # v6.6: profile overrides win when preset value equals the
            # system default (see runner.py for the rationale).
            from career_bot.trackblazer import DEFAULT_SOLVER_WEIGHTS as _SOLVER_DEFAULTS
            for k, v in profile_weights.items():
                current = weights.get(k)
                preset_default = _SOLVER_DEFAULTS.get(k)
                if k not in weights or current in (None, "", 0):
                    weights[k] = v
                elif preset_default is not None and current == preset_default:
                    weights[k] = v
                # else: preset has a non-default value -> preset wins
            # v6.4: profile.effective_target_epithets() returns explicit
            # profile.target_epithets if set, otherwise auto-picked
            # signature epithet(s) when profile.auto_pick_epithets is True,
            # otherwise [].  Preset still wins above the profile.
            profile_targets, target_source = profile.effective_target_epithets()
            plan = trackblazer.make_schedule(
                self.base_dir,
                aptitudes=self._chara_trackblazer_aptitudes(chara),
                fan_bonus=float(cfg.get("fan_bonus") or 0),
                max_races_in_row=int(self._solver_setting(preset, "max_races_in_row", 5)),
                include_op=bool(self._solver_setting(preset, "include_op", False)),
                floor=self._solver_aptitude_floor(preset, 6),
                solver=str(cfg.get("solver") or "auto"),
                weights=weights,
                training_blocks=(preset or {}).get("training_blocks") or [],
                manual_locks=(preset or {}).get("manual_locks") or {},
                target_epithets=trackblazer._merge_epithet_lists(
                    (preset or {}).get("trackblazer_target_epithets") or profile_targets,
                    trackblazer.resolve_agenda_epithets(self.base_dir, (preset or {}).get("trackblazer_race_agenda") or "")[0],
                ),
                forced_epithets=trackblazer._merge_epithet_lists(
                    (preset or {}).get("trackblazer_forced_epithets") or profile.forced_epithets,
                    trackblazer.resolve_agenda_epithets(self.base_dir, (preset or {}).get("trackblazer_race_agenda") or "")[1],
                ),
                preferred_distances=cfg.get("preferred_distances") or (preset or {}).get("preferred_distances") or profile.preferred_distances,
                distance_preference_mode=str(cfg.get("distance_preference_mode") or (preset or {}).get("distance_preference_mode") or "balanced"),
                current_turn=max(1, int(turn or 0)),
                race_history=race_history,
                trainee_id=trainee_id,
                preset_name=(preset or {}).get("name", ""),
            )
            remaining = [int(x) for x in plan.get("extra_race_list") or []]
            fallback_used = bool(plan.get("fallback_used"))
            cur_turn = max(1, int(turn or 0))
            prev_plan = (preset or {}).get("trackblazer_last_plan") or {}
            prev_remaining = [int(x) for x in (prev_plan.get("extra_race_list") or [])]
            prev_was_exact = bool(prev_remaining) and not bool(prev_plan.get("fallback_used"))

            # Detect high-value races the *new* plan drops relative to the plan
            # we already hold, considering only races still in the future.
            new_hv = self._high_value_races(plan)
            prev_hv = self._high_value_races(prev_plan)
            dropped_hv = sorted(
                (
                    {"program_id": pid, "turn": rt, "name": name, "est_fans": fans}
                    for pid, (rt, name, fans) in prev_hv.items()
                    if rt >= cur_turn and pid not in new_hv
                ),
                key=lambda d: d["turn"],
            )

            # v6.7.20 GUARD: never let a degraded heuristic (beam) re-solve
            # overwrite a good exact (MILP) plan. The beam can silently drop
            # winnable high-fan races (Japan Cup, Arima, ...) that the exact
            # solver would always keep. When the exact backend fails *this*
            # turn but the plan we already hold was exact, keep the exact
            # plan's upcoming races rather than churning to the beam result.
            # Skipped for reason="missing": there a planned race genuinely
            # vanished this turn, so we must accept a fresh plan even if it is
            # the beam, otherwise we would re-suggest an unavailable race.
            guard_applied = bool(fallback_used and prev_was_exact and reason != "missing")
            if guard_applied:
                effective_plan = prev_plan
                effective_remaining = prev_remaining
            else:
                effective_plan = plan
                effective_remaining = remaining
                preset["extra_race_list"] = remaining
                preset["trackblazer_last_plan"] = plan

            try:
                stamina_now = int((weights.get("currentStats") or {}).get("stamina") or 0)
            except Exception:
                stamina_now = 0

            self._push_replan_log({
                "turn": cur_turn,
                "reason": str(reason or "live"),
                "backend": plan.get("solver"),
                "fallback_used": fallback_used,
                "fallback_reason": plan.get("fallback_reason"),
                "guard_kept_prior_exact_plan": guard_applied,
                "race_count": len(effective_remaining),
                "new_solve_race_count": len(remaining),
                "current_stamina": stamina_now,
                "dropped_high_value_races": dropped_hv,
                "history_rows": len(race_history),
            })

            summary = {
                "turn": cur_turn,
                "reason": str(reason or "live"),
                "race_count": len(effective_remaining),
                "solver": effective_plan.get("solver"),
                "fallback_used": fallback_used,
                "guard_kept_prior_exact_plan": guard_applied,
                "dropped_high_value_races": dropped_hv,
                "dead_epithets": effective_plan.get("dead_epithets") or [],
                "projected_epithets": effective_plan.get("projected_epithets") or [],
                "notes": effective_plan.get("notes") or [],
                "history_rows": len(race_history),
            }
            self.last_live_replan = summary
            if reason == "missing":
                self.last_missing_replan = summary
            self._last_live_replan_key = key
            return effective_plan
        except Exception as exc:
            summary = {"turn": int(turn or 0), "reason": str(reason or "live"), "error": str(exc)}
            self.last_live_replan = summary
            if reason == "missing":
                self.last_missing_replan = summary
            return None

    def _try_replan_missing_smart_race(self, state, preset, turn):
        """Re-solve when a planned smart race is no longer available this turn."""
        return self._replan_smart_schedule(state, preset, turn, reason="missing", force=True)

    def choose(self, state, preset):
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        turn = int(chara.get("turn") or 0)
        is_mant = int(chara.get("scenario_id") or 0) == 4

        if is_mant and str((preset or {}).get("extra_race_list_source") or "").strip().lower() == "smart":
            self._replan_smart_schedule(state, preset or {}, turn, reason="live", force=False)

        if is_mant and self._smart_solver_train_locked(preset or {}, turn):
            return 0

        home = data.get("home_info") or {}
        commands = home.get("command_info_array") or []
        race_enabled = any(cmd.get("command_type") == 4 and cmd.get("command_id") == 401 and cmd.get("is_enable", 0) for cmd in commands)
        if not race_enabled:
            return 0

        available = self.available_programs(state)
        if not available:
            return 0

        cfg = ((preset or {}).get("mant_config") or {})
        # Live race-entry aptitude floor — configurable via min_aptitude_floor
        # (smart race solver settings), matching the solver's aptitudeThreshold.
        # Requires BOTH distance and surface aptitude >= floor (standard behavior).
        apt_floor = self._solver_aptitude_floor(preset)
        all_valid = [pid for pid in available if (turn, pid) not in self.rejected and self.check_aptitude(chara, pid, apt_floor)]

        wanted = self.wanted_programs(preset or {}, turn)
        # Match planned races to the live list by race_instance_id (not raw
        # program_id) so marquee G1s whose program_id 'variant' differs from the
        # offered one (Japan Cup, Arima, ...) are recognized and run. Returns the
        # LIVE program_id the game offers.
        valid_wanted = self._resolve_wanted_live(wanted, available, turn)
        source_mode = str((preset or {}).get("extra_race_list_source") or "").strip().lower()
        if is_mant and source_mode == "smart" and wanted and not valid_wanted and turn <= 72:
            # v1.5: the solver planned a race for this turn but the exact program
            # is not in the live race list (calendar drift).  Rather than re-solve
            # the whole remaining schedule -- the "missing"-race re-solve erodes
            # the plan ~1 race per event and was the main reason executed races
            # stalled ~10 below the plan (24 missing events in one run) -- run the
            # best AVAILABLE aptitude-passing race for this turn from the live
            # list.  This is what the reference solver does (it reads the on-screen
            # race list), and it keeps the race slot the solver intended.
            if cfg.get("enable_missing_race_substitute", True) and all_valid:
                filtered = self._filter_by_surface_preference(all_valid, preset or {})
                pool = filtered if filtered else all_valid
                return self._sort_races_for_trackblazer(pool, state, preset or {})[0]
            # No available race to substitute with -> TRAIN this turn. The reference solver
            # does NOT re-solve the schedule when its planned race isn't on the
            # live list; it falls back to the on-screen list (handled above) or
            # trains. Falls through to the smart-mode "nothing wanted -> train".
        is_manual_race_list = source_mode == "manual"
        if valid_wanted and is_manual_race_list:
            # RIVAL OVERWRITE (Trackblazer): a turn-slot may list a MAIN race plus
            # one or more rival-overwrite races (extra_race_list = [main, overwrite,
            # ...] for that turn, order preserved by _resolve_wanted_live). If the
            # main is NOT the rival the game is presenting this turn but an overwrite
            # IS, run the rival race instead of the main. Single-race turns and turns
            # with no offered rival are unaffected (still the main pick). This is the
            # only place manual mode deviates from strict "run valid_wanted[0]".
            if is_mant and len(valid_wanted) > 1:
                rival_map = self.get_rival_race_map(state)
                if valid_wanted[0] not in rival_map:
                    for overwrite_pid in valid_wanted[1:]:
                        if overwrite_pid in rival_map:
                            return overwrite_pid
            return valid_wanted[0]

        # v7.2 — Manual mode is STRICT. If the user picked a manual race list:
        #   - on turns where one of their races is valid → run it (above)
        #   - on turns where their list has nothing for this turn → DO NOT race
        #
        # Previously the code fell through to force_racing / fan_farming /
        # trackblazer-sort, which would pick from `all_valid` (every aptitude-
        # passing race including dirt), ignoring preferred_surfaces. That's
        # how dirt races slipped in on turns not covered by the user's list.
        # Now manual mode short-circuits all smart fallbacks. Surface and
        # distance preferences are honored implicitly because the user picked
        # the exact races they want.
        if is_manual_race_list:
            # Opt-in (off by default): if the user picked a race for THIS turn but
            # the game is not offering it (calendar drift), run the best available
            # aptitude-passing race from the live list instead of silently
            # training -- mirrors the smart-mode missing-race substitute.  Manual
            # stays strictly exact otherwise: a turn the user's list does not
            # cover (wanted empty) still trains.
            if (cfg.get("manual_missing_race_substitute", False)
                    and wanted and not valid_wanted and turn <= 72 and all_valid):
                filtered = self._filter_by_surface_preference(all_valid, preset or {})
                pool = filtered if filtered else all_valid
                return self._sort_races_for_trackblazer(pool, state, preset or {})[0]
            return 0

        # Smart Race Solver owns extra-race decisions.  If the dynamically
        # rebuilt live plan says Train/Rest on this turn, suppress legacy
        # fan-farming/look-ahead fallbacks so stale heuristics cannot fight the
        # current RaceHistory/EpithetTracker route.
        if is_mant and source_mode == "smart" and not valid_wanted:
            return 0

        if is_mant and cfg.get("force_racing", False) and all_valid:
            return self._sort_races_for_trackblazer(self._filter_by_surface_preference(all_valid, preset or {}), state, preset or {})[0] if self._filter_by_surface_preference(all_valid, preset or {}) else self._sort_races_for_trackblazer(all_valid, state, preset or {})[0]

        if not valid_wanted:
            fans = int(chara.get("fans") or 0)
            if fans < 350 and turn > 11:
                scored = []
                for pid in available:
                    if (turn, pid) not in self.rejected and self.check_aptitude(chara, pid):
                        scored.append(pid)
                if scored:
                    # v7.2 — Also honor preferred_surfaces in the low-fans
                    # fallback. Falls back to unfiltered list only if the
                    # filter empties (i.e. no preferred-surface races at all
                    # this turn).
                    filtered = self._filter_by_surface_preference(scored, preset or {})
                    if filtered:
                        scored = filtered
                    if is_mant:
                        return self._sort_races_for_trackblazer(scored, state, preset or {})[0]
                    scored = [(self._fallback_race_score(chara, pid), pid) for pid in scored]
                    scored.sort(reverse=True)
                    return scored[0][1]
            if is_mant and cfg.get("enable_farming_fans", False):
                interval = max(1, int(cfg.get("days_to_run_extra_races") or 5))
                if turn > 11 and turn % interval == 0 and all_valid:
                    filtered = self._filter_by_surface_preference(all_valid, preset or {})
                    pool = filtered if filtered else all_valid
                    return self._sort_races_for_trackblazer(pool, state, preset or {})[0]
            return 0

        if not is_mant:
            return valid_wanted[0]

        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("enable_trackblazer_race_sorting", True):
            rival_map = self.get_rival_race_map(state)
            main_race_id = valid_wanted[0]
            if main_race_id in rival_map:
                return main_race_id
            for overwrite_pid in valid_wanted[1:]:
                if overwrite_pid in rival_map:
                    return overwrite_pid
            return main_race_id

        return self._sort_races_for_trackblazer(valid_wanted, state, preset or {})[0]

    def reject(self, turn, program_id):
        self.rejected.add((int(turn or 0), int(program_id or 0)))

    def label(self, program_id):
        info = self.program.get(int(program_id or 0)) or {}
        official = self.official_races.get(int(program_id or 0)) or {}
        name = official.get("name") or info.get("name") or ""
        # v6.7.2: clean dashboard label, no leading program_id / race_instance_id
        if not name:
            return f"Race #{program_id}"
        bits = [name]
        grade = str(official.get("grade") or "").upper()
        if grade:
            bits.append(grade)
        distance = official.get("distance_m") or ""
        if distance:
            bits.append(f"{distance}m")
        terrain = str(official.get("terrain") or "").strip()
        if terrain:
            bits.append(terrain)
        return " · ".join(bits)
