import json
from pathlib import Path

from career_bot.events import EventManager
from career_bot.trackblazer_guide import load_guide, is_summer_turn, race_chain_target
from career_bot import trackblazer_rules as tb_rules
from career_bot.scenarios.base import Decision, ScenarioStrategy


STAT_TARGETS = {
    1: 0,
    2: 1,
    3: 2,
    4: 3,
    5: 4,
    30: 5,
}

TRAINING_COMMANDS = {101: 0, 105: 1, 102: 2, 103: 3, 106: 4, 601: 0, 602: 1, 603: 2, 604: 3, 605: 4}
TRAINING_NAMES = ["Speed", "Stamina", "Power", "Guts", "Wit"]
STAT_KEYS = ["speed", "stamina", "power", "guts", "wiz"]
SUMMER_CAMP_TURNS = {36, 37, 38, 39, 40, 60, 61, 62, 63, 64}
SUMMER_CONSERVE_TURNS = {35, 36, 59, 60}
SUMMER_CONSERVE_ENERGY = 60
ENERGY_FAST_MEDIC = 80
ENERGY_MEDIC_GENERAL = 85
DECK_PARTNERS = {1, 2, 3, 4, 5, 6}

# Energy-rescue (ported from UmaAuto's MANT scenario): owned consumables that can
# lift vitality enough to run a strong training instead of wasting the turn on a
# pure rest.  Values are the energy each item restores.
ENERGY_ITEM_VALUES = {2001: 20, 2002: 40, 2003: 65, 2101: 100}  # Vita 20/40/65, Royal Kale Juice
GOOD_LUCK_CHARM_ID = 10001
BAD_EFFECT_NAMES = {
    1: "Night Owl",
    2: "Slacker",
    3: "Skin Outbreak",
    4: "Slow Metabolism",
    5: "Migraine",
    6: "Practice Poor",
}


class MantStrategy(ScenarioStrategy):
    scenario_id = 4

    def __init__(self, race_planner=None):
        self.race_planner = race_planner
        self.event_manager = None
        if self.race_planner and self.race_planner.base_dir:
            self.event_manager = EventManager(self.race_planner.base_dir)
        self.current_preset = {}
        self.last_training_scores = []
        self.last_decision_trace = {}
        self.trackblazer_guide = load_guide(self.race_planner.base_dir) if self.race_planner and self.race_planner.base_dir else {}
        self.training_effects = self._load_training_effects()


    def _load_training_effects(self):
        if not self.race_planner or not self.race_planner.base_dir:
            return {}
        path = Path(self.race_planner.base_dir) / "data" / "training_effects_core.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        rows = payload.get("training_effects") if isinstance(payload, dict) else payload
        out = {}
        for row in rows or []:
            try:
                key = (
                    int(row.get("scenario_id") or self.scenario_id),
                    int(row.get("command_id") or 0),
                    int(row.get("level") or 0),
                    int(row.get("result_state") or 0),
                )
            except Exception:
                continue
            out[key] = row
        return out

    def _official_command_id(self, command):
        command_id = int((command or {}).get("command_id") or 0)
        if command_id in (601, 602, 603, 604, 605):
            idx = TRAINING_COMMANDS.get(command_id)
            return [101, 105, 102, 103, 106][idx] if idx is not None else command_id
        return command_id

    def _official_training_baseline(self, command):
        if not self.training_effects or not command:
            return None
        command_id = self._official_command_id(command)
        level = max(1, self._training_level(command))
        # result_state=2 is the normal success row in master.mdb. Fall back to
        # any result state if that exact row is unavailable.
        key = (int(self.scenario_id), command_id, level, 2)
        row = self.training_effects.get(key)
        if row:
            return row
        for (scenario_id, cid, lvl, _state), value in self.training_effects.items():
            if scenario_id == int(self.scenario_id) and cid == command_id and lvl == level:
                return value
        return None

    def _official_training_effect_items(self, command):
        row = self._official_training_baseline(command)
        if not row:
            return []
        return [
            {"target_type": int(item.get("target_type") or 0), "value": int(item.get("effect_value") or 0), "_source": "master_training_effect"}
            for item in row.get("effects") or []
        ]

    def _official_training_summary(self, command):
        row = self._official_training_baseline(command)
        if not row:
            return None
        return {
            "level": int(row.get("level") or 0),
            "stat_total": int(row.get("stat_total") or 0),
            "skill_points": int(row.get("skill_points") or 0),
            "energy_delta": int(row.get("energy_delta") or 0),
        }

    def _stale_completed_race_state(self, data, chara, race):
        """Detect stale in-race payloads that already have a race result.

        Some reloads report playing_state=3 with race_start_info even after the
        race result is already present and home commands are available. Treating
        that as a live race creates an endless resume loop.
        """
        if not race or not race.get("program_id"):
            return False
        try:
            program_id = int(race.get("program_id") or chara.get("race_program_id") or 0)
            turn = int(chara.get("turn") or 0)
        except Exception:
            return False
        if not program_id or not turn:
            return False
        history = data.get("race_history") or []
        already_recorded = any(
            int((row or {}).get("program_id") or 0) == program_id and int((row or {}).get("turn") or 0) == turn
            for row in history
        )
        commands = ((data.get("home_info") or {}).get("command_info_array") or [])
        has_enabled_home_command = any(int((cmd or {}).get("is_enable") or 0) for cmd in commands)
        return already_recorded and has_enabled_home_command

    def next_decision(self, state, preset):
        self.current_preset = preset or {}
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        self.current_chara = chara
        home = data.get("home_info") or {}
        if "single_mode_finish_common" in data:
            return Decision("finish", {"current_turn": chara["turn"]}, "finished")
        events = data.get("unchecked_event_array") or []
        if events:
            event = events[0] or {}
            choice = self._choice(event)
            payload = {"event_id": event.get("event_id"), "chara_id": event.get("chara_id", 0), "choice_number": choice, "current_turn": chara["turn"]}
            if choice is None:
                payload = {"event_id": event.get("event_id"), "_event": event, "_current_turn": chara["turn"]}
            return Decision("event", payload, "event")
        if chara.get("state") == 3:
            return Decision("finish", {"current_turn": chara["turn"]}, "ready to finish")
        race = data.get("race_start_info")
        playing_state = (chara.get("playing_state") or 0)
        if self._stale_completed_race_state(data, chara, race):
            playing_state = 1
            race = None
        if playing_state == 3:
            return Decision("race_progress", {"current_turn": chara["turn"], "phase": "start", "race_start_info": race, "chara_info": chara}, "resume race start")
        if playing_state == 5:
            return Decision("finish", {"current_turn": chara["turn"]}, "goal failed / career end")     
        if race and race.get("program_id") and playing_state in (2, 4):
            return Decision("race_progress", {"current_turn": chara["turn"], "phase": "start", "race_start_info": race, "chara_info": chara}, "race start")
        # Engine selection. The Trackblazer engine is the DEFAULT: it fully owns
        # the home-screen decision (training/rest/mood/recreation) and race entry.
        # The legacy ("Classic") engine below is selected only when decision_mode
        # is "legacy"/"classic"; "android" is accepted as a legacy alias for
        # Trackblazer, and an unset/absent decision_mode also uses Trackblazer.
        mode = str((((preset or {}).get("mant_config") or {}).get("decision_mode")) or "trackblazer").strip().lower()
        if mode not in ("legacy", "classic"):
            # "trackblazer", "android" (legacy alias), or unset -> Trackblazer engine.
            return self._trackblazer_core().decide(state, preset)
        if self.race_planner:
            forced_program_id = self.race_planner.forced_program(state)
            if forced_program_id:
                cfg = ((preset or {}).get("mant_config") or {})
                if cfg.get("stop_on_mandatory_races", False):
                    return Decision("idle", {}, f"stopped before mandatory race {self.race_planner.label(forced_program_id)}")
                return Decision("race", {"program_id": forced_program_id, "current_turn": chara["turn"], "_strategy": self, "_forced_race": True}, self.race_planner.label(forced_program_id))
            program_id = self.race_planner.choose(state, preset)
            if program_id:
                chain_break = self._guide_race_chain_break(data, chara, preset, program_id)
                if chain_break:
                    return chain_break
                hijack = self._irregular_training_decision(data, chara, preset, program_id)
                if hijack:
                    return hijack
                return Decision("race", {"program_id": program_id, "current_turn": chara["turn"], "_strategy": self}, self.race_planner.label(program_id))
        command = self._best_command(data, chara, preset)
        if command:
            command_type = command.get("command_type", 1)
            command_id = command.get("command_id")
            command_group_id = command.get("command_group_id", 0)
            reason = self._command_reason(command)
            if command_type == 3:
                command_group_id = command_id
                command_id = 0
            return Decision("command", {
                "command_type": command_type,
                "command_id": command_id,
                "command_group_id": command_group_id,
                "select_id": command.get("select_id", 0),
                "current_turn": chara["turn"],
                "current_vital": chara.get("vital", 0),
            }, reason)
        return Decision("idle", {}, "no action")

    def _trackblazer_core(self):
        core = getattr(self, "_trackblazer", None)
        if core is None:
            from career_bot.scenarios.mant_trackblazer import MantTrackblazerCore
            core = self._trackblazer = MantTrackblazerCore(self)
        return core

    def _choice(self, event):
        choices = ((event.get("event_contents_info") or {}).get("choice_array") or [])
        if not choices:
            return 0
        if len(choices) > 1:
            return None
        return 0

    def choice_from_rewards(self, rewards, event):
        choices = ((event.get("event_contents_info") or {}).get("choice_array") or [])
        if not choices:
            return 0
        if not rewards:
            return choices[0].get("select_index", 1)
        best_index = 0
        best_score = None
        for i, reward in enumerate(rewards):
            score = self._reward_score(reward)
            if best_score is None or score > best_score:
                best_score = score
                best_index = i
        if best_index < len(choices):
            return choices[best_index].get("select_index", best_index + 1)
        return choices[0].get("select_index", 1)

    def _reward_score(self, reward):
        score = 0.0
        for item in reward.get("params_inc_dec_info_array") or reward.get("effected_parameter_array") or []:
            target = STAT_TARGETS.get(item.get("target_type"))
            value = float(item.get("value") or 0)
            if target is None:
                if item.get("target_type") == 10:
                    score += value * 0.03
                continue
            score += value * (0.02 if target < 5 else 0.01)
        score += float(reward.get("skill_point") or 0) * 0.01
        score += float(reward.get("vital") or 0) * 0.03
        return score

    def _is_hp_full(self, chara):
        vital = int((chara or {}).get("vital") or 0)
        max_vital = int((chara or {}).get("max_vital") or 100)
        return max_vital > 0 and vital >= max_vital

    def _rainbow_partner_count(self, command, chara):
        """Return high-bond partner count for this training.

        Umamusume's friendship/rainbow training appears in payloads differently
        across clients. The most stable signal available here is a deck partner
        on the training with bond/evaluation >= 80. If the API later exposes a
        direct rainbow flag, this helper also honors common field names.
        """
        if not command:
            return 0
        for key in ("is_rainbow", "is_friendship_training", "friendship_training", "is_special_training"):
            if command.get(key):
                return 1
        bonds = self._bond_map(chara or {})
        count = 0
        for partner_id in command.get("training_partner_array") or []:
            try:
                partner_id = int(partner_id)
            except Exception:
                continue
            if partner_id in DECK_PARTNERS and int(bonds.get(partner_id, 0) or 0) >= 80:
                count += 1
        return count

    def _bondable_count(self, command, chara):
        """Deck partners on this training whose bond is still below 80.

        Used by the junior-year bond-rush: early turns prefer trainings that
        raise the most unbonded deck partners toward the rainbow threshold,
        even over a marginally higher raw score.
        """
        if not command:
            return 0
        bonds = self._bond_map(chara or {})
        count = 0
        for partner_id in command.get("training_partner_array") or []:
            try:
                partner_id = int(partner_id)
            except Exception:
                continue
            if partner_id in DECK_PARTNERS and int(bonds.get(partner_id, 0) or 0) < 80:
                count += 1
        return count

    def _rainbow_bonus(self, command, chara, preset):
        count = self._rainbow_partner_count(command, chara)
        if count <= 0:
            return 0.0
        # v1.5: rainbow/friendship training yields far more stats than a normal
        # facility, so a single rainbow is now worth ~2.0x the base score (was
        # 1.22x, which under-valued them and let plain high-level facilities win
        # the pick).  Android grabs rainbows aggressively; this matches it.  All
        # three values are preset-tunable.
        base = float((preset or {}).get("rainbow_training_bonus") or 1.0)
        stack = float((preset or {}).get("rainbow_training_stack_bonus") or 0.12)
        cap = float((preset or {}).get("rainbow_training_bonus_cap") or 1.25)
        return min(cap, base + max(0, count - 1) * stack)

    def _should_avoid_full_hp_wit(self, command, chara, preset):
        if not command or TRAINING_COMMANDS.get(command.get("command_id")) != 4:
            return False
        if not self._is_hp_full(chara):
            return False
        # v1.5: allow_full_hp_wit_rainbow now defaults TRUE, so a RAINBOW Wit at
        # full HP is permitted (android trains Wit heavily, to 919).  Only a
        # non-rainbow Wit at full HP is still avoided as an energy-recovery waste.
        if not (preset or {}).get("allow_full_hp_wit_rainbow", True):
            return True
        return self._rainbow_partner_count(command, chara) <= 0

    def _training_energy_delta(self, command):
        for item in (command or {}).get("params_inc_dec_info_array") or self._official_training_effect_items(command or {}):
            try:
                if int(item.get("target_type") or 0) == 10:
                    return float(item.get("value") or 0)
            except Exception:
                continue
        return 0.0

    def _target_completion_ratio(self, stat_idx, chara, targets):
        try:
            target = float(targets[stat_idx] if stat_idx < len(targets) else 0)
        except Exception:
            target = 0.0
        if target <= 0:
            return 1.0
        current = float((chara or {}).get(STAT_KEYS[stat_idx]) or 0)
        return current / target

    def _target_pressure_multiplier(self, stat_idx, chara, targets, preset):
        """Android-bot-inspired target pressure for underbuilt stats.

        SweepyCL already scores raw gains and cap pressure. This light
        multiplier gives behind-target stats a fighting chance against Wit
        HP/SP side value without banning Wit outright.
        """
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("enable_target_pressure_scoring", True):
            return 1.0
        completion = self._target_completion_ratio(stat_idx, chara, targets)
        # Android-matched completion buckets (Scoring.kt ratioBreakpoints/Multipliers):
        # a stat far below target gets up to 5x, one near/over target drops to 0.3x.
        if completion < 0.15:
            bucket = 5.0
        elif completion < 0.30:
            bucket = 4.0
        elif completion < 0.45:
            bucket = 3.0
        elif completion < 0.60:
            bucket = 2.0
        elif completion < 0.75:
            bucket = 1.0
        elif completion < 0.90:
            bucket = 0.5
        else:
            bucket = 0.3
        # v1.5: strength stays at 0.35 by default.  Applying the raw android
        # bucket (up to 5x) inflates the BEST training's score ~1.5x, which makes
        # the race-vs-train gates (chain-break 0.45, irregular 0.62, calibrated to
        # the un-inflated scale) drop planned races too eagerly -- cutting race
        # count, the opposite of the goal.  The completion signal is instead
        # sharpened the safe way: by the retuned per-distance targets (Power<Wit),
        # which make a near-target Power bucket low without touching score
        # magnitude.  Raise toward 1.0 only with re-tuned race-vs-train thresholds.
        strength = float(cfg.get("target_pressure_strength") if cfg.get("target_pressure_strength") is not None else 0.35)
        strength = max(0.0, min(1.0, strength))
        return max(0.25, 1.0 + ((bucket - 1.0) * strength))

    def _starved_stat_multiplier(self, idx, chara, targets, preset):
        """v1.5: lift a training whose MAIN stat is below target.

        The 2.0x rainbow bonus makes the bot chase whichever stat the rainbows
        land on, leaving another stat starved (e.g. Wit at 656/1000 while Speed
        gets every rainbow) -- which costs the close, place-2 race losses.  This
        boosts a behind-target training so a neglected stat can win the pick
        against a non-rainbow rival.

        Applied to the WHOLE score, parallel to (and competing with) the rainbow
        bonus -- deliberately NOT via target_pressure_strength, so the general
        score scale and the race-vs-train gates (chain-break/irregular) stay put.
        Deeply-behind -> up to `cap`; at/above `threshold` -> 1.0 (no boost).
        """
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("enable_starved_stat_pull", True):
            return 1.0
        if idx is None or idx < 0 or idx >= 5:
            return 1.0
        completion = self._target_completion_ratio(idx, chara, targets)
        threshold = float(cfg.get("starved_stat_threshold", 0.85))
        if completion >= threshold:
            return 1.0
        strength = float(cfg.get("starved_stat_strength", 2.5))
        cap = float(cfg.get("starved_stat_cap", 0.8))
        boost = min(cap, max(0.0, (threshold - completion) * strength))
        return 1.0 + boost

    def _stat_priority_multiplier(self, stat_idx, preset, turn=0):
        """Per-stat priority weight matching android Scoring.kt priorityMultiplier
        (1.0 + 0.5*(size - rank)): top-priority stat ~3.5x, bottom ~1.5x.

        Icarus previously applied stat priority only through the (conditional)
        training-level and summer multipliers, so on a normal turn the highest
        RAW-gain training won regardless of the user's stat priority.  This adds
        the android baseline weighting on every stat gain.

        Skipped on summer turns -- android swaps to the summer priority list
        there (config.summerTrainingStatPriority), which Icarus already applies
        via _summer_priority_multiplier; applying the regular list too would
        fight it.

        v1.5: DEFAULTS OFF.  Android multiplies stat gains by priority AND
        calibrates its race-vs-train thresholds to that inflated scale.  Icarus's
        thresholds (chain-break 0.45, irregular-training 0.62, summer-conserve
        0.34) are calibrated to the un-inflated score, so applying a 1.5-3.5x
        priority multiplier here makes those gates mis-fire (e.g. substituting
        training for a planned race far too eagerly).  The retuned per-distance
        targets (Power < Wit) already encode the stat priority for the
        completion-bucket scorer, so this extra weighting is redundant by
        default.  Enable only alongside re-tuned race-vs-train thresholds.
        """
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("enable_stat_priority_weighting", False):
            return 1.0
        if turn in SUMMER_CAMP_TURNS or is_summer_turn(turn, self.trackblazer_guide):
            return 1.0
        priorities = self._priority_indices(preset, "training_stat_priority", "stat_priority")
        try:
            rank = priorities.index(stat_idx)
        except ValueError:
            return 1.0
        coeff = float(cfg.get("stat_priority_coefficient", 0.5))
        return 1.0 + coeff * (len(priorities) - rank)

    def _wit_balance_multiplier(self, chara, targets, preset):
        cfg = ((preset or {}).get("mant_config") or {})
        # v1.5: defaults OFF.  Android has no Wit-specific penalty; this damping
        # (x0.72/x0.85 when Wit gets ahead of the weakest stat) was actively
        # capping Wit below the other stats, the opposite of the 919-Wit profile
        # we want.  Re-enable per preset if a build genuinely over-trains Wit.
        if not cfg.get("enable_wit_balance_damping", False):
            return 1.0
        wit_ratio = self._target_completion_ratio(4, chara, targets)
        other_ratios = [self._target_completion_ratio(idx, chara, targets) for idx in range(4)]
        weakest_other = min(other_ratios) if other_ratios else wit_ratio
        gap = wit_ratio - weakest_other
        if gap > 0.12:
            return 0.72
        if gap > 0.06:
            return 0.85
        return 1.0

    def _training_candidate_trace(self, cmd, score, chara, preset):
        idx = TRAINING_COMMANDS.get((cmd or {}).get("command_id"), 0)
        targets = self._training_targets(preset, chara)
        completion = self._target_completion_ratio(idx, chara, targets)
        flags = []
        energy = self._training_energy_delta(cmd)
        if energy > 0:
            flags.append("energy recovery")
        if self._rainbow_partner_count(cmd, chara) > 0:
            flags.append("rainbow training")
        elif self._near_rainbow_partner_count(cmd, chara, preset) > 0:
            flags.append("near-rainbow partner")
        if completion < 0.75:
            flags.append("below target")
        if idx == 4:
            wit_mult = self._wit_balance_multiplier(chara, targets, preset)
            if wit_mult < 1.0:
                flags.append("wit damped because other stats are behind")
        return {
            "command_id": cmd.get("command_id"),
            "name": TRAINING_NAMES[idx],
            "score": round(float(score or 0), 4),
            "failure_rate": int(cmd.get("failure_rate") or 0),
            "rainbow": self._rainbow_partner_count(cmd, chara),
            "near_rainbow": self._near_rainbow_partner_count(cmd, chara, preset),
            "training_level": self._training_level(cmd),
            "official_training": self._official_training_summary(cmd),
            "main_gain": self._command_main_stat_gain(cmd),
            "target_completion": round(completion, 3),
            "target_completion_pct": int(max(0.0, min(2.0, completion)) * 100),
            "energy_delta": energy,
            "reason_flags": flags,
        }

    def _best_command(self, data, chara, preset):
        commands = (data.get("home_info") or {}).get("command_info_array") or []
        enabled = [cmd for cmd in commands if cmd.get("is_enable", 1)]
        rest = self._rest_command(enabled)
        recreation = self._recreation_command(enabled)
        medic = self._medic_command(enabled)
        training = [cmd for cmd in enabled if cmd.get("command_type") == 1 and cmd.get("command_id") in TRAINING_COMMANDS]
        turn = int(chara.get("turn") or 0)
        vital = int(chara.get("vital") or 0)
        motivation = int(chara.get("motivation") or 3)
        cfg = ((preset or {}).get("mant_config") or {})
        bad_status = self._has_curable_bad_status(chara, preset)
        if not training:
            if medic and bad_status and vital <= ENERGY_MEDIC_GENERAL:
                return medic
            return self._record_recovery(rest or recreation, turn)
        scored = [(self._score_command(cmd, data, chara, preset), cmd) for cmd in training]
        if 48 < turn <= 72:
            stat_keys = ["speed", "stamina", "power", "guts", "wiz"]
            highest_idx = max(range(5), key=lambda idx: int(chara.get(stat_keys[idx]) or 0))
            scored = [(score * 0.95 if TRAINING_COMMANDS.get(cmd.get("command_id"), 0) == highest_idx and score > 0 else score, cmd) for score, cmd in scored]
        # Cache the scores from the actual decision path so the decision trace
        # reflects what the bot really evaluated this turn (and so explain_decision
        # does not need to re-score every command a second time).
        self.last_training_scores = [
            self._training_candidate_trace(cmd, score, chara, preset)
            for score, cmd in sorted(scored, key=lambda row: row[0], reverse=True)
        ]
        self._scored_turn = turn
        # Junior-year bond-rush (ported from UmaAuto): during Junior class
        # (turns 1-24) prefer the training that bonds the most still-unbonded
        # deck partners, breaking ties by raw score.  This unlocks friendship/
        # rainbow training sooner, which compounds for the rest of the career.
        if turn <= 24 and cfg.get("junior_bond_rush", True):
            best_score, best = max(scored, key=lambda row: (self._bondable_count(row[1], chara), row[0]))
        else:
            best_score, best = max(scored, key=lambda row: row[0])
        rest_threshold = int(preset.get("rest_threshold") or 48)
        failure = int(best.get("failure_rate") or 0)
        if medic and bad_status and vital <= ENERGY_FAST_MEDIC:
            return medic
        if medic and bad_status and vital <= ENERGY_MEDIC_GENERAL:
            return medic
        force_floor = int(cfg.get("force_train_energy_floor") or 0)
        if force_floor > 0 and (turn in SUMMER_CAMP_TURNS or turn >= 73) and vital <= force_floor:
            if recreation:
                return self._record_recovery(recreation, turn)
            if rest:
                return self._record_recovery(rest, turn)
        if turn in SUMMER_CAMP_TURNS and recreation and (vital <= rest_threshold or failure >= 35 or best_score < 0):
            # v6.7.25 — Summer-camp recreation is a mood-boost play: it's
            # the right call when motivation is below Great so rainbow
            # training maxes out, but it provides almost nothing when
            # motivation is already at Great (5). The screenshot bug
            # (Mant turn 37, motivation already 5) came from this branch
            # firing on energy alone and ignoring mood. Skip the
            # recreation if motivation is already maxed, or if we
            # recreated the previous turn and motivation has already
            # reached Great — let the rest gate handle the energy.
            last_recovery = getattr(self, "_last_recovery_turn", None)
            last_recovery_kind = getattr(self, "_last_recovery_kind", None)
            recently_recreated = (last_recovery == turn - 1 and last_recovery_kind == "recreation")
            summer_skip = (motivation >= 5) or (recently_recreated and motivation >= 4)
            if not summer_skip:
                return self._record_recovery(recreation, turn)
        if self._should_recreate(recreation, preset, turn, motivation, vital, best_score):
            return self._record_recovery(recreation, turn)
        if rest and (vital <= rest_threshold or failure >= 35 or best_score < 0):
            # Energy-rescue (ported from UmaAuto): when the bot would rest only
            # because energy is low or failure is high, but the best training is
            # strong/rainbow and we own a Vita/Kale (energy) or a Good-Luck Charm
            # (zero failure), run the training instead of wasting the turn. The
            # existing item layer tops up energy (or the charm zeroes failure)
            # at line ~807 in the runner, before the command actually execs.
            if self._can_rescue_training(data, chara, preset, best, best_score, vital, failure, rest_threshold):
                best["_energy_rescue"] = True
                return best
            # Wit as low-energy recovery: when the bot would rest only because
            # energy is low (not because training is worthless), a safe Wit option
            # that restores energy gives stats + SP + recovery in one turn instead
            # of a wasted pure rest. Skip during summer camp (handled elsewhere)
            # and when energy is critical (a real rest is better).
            crit_vital = int(preset.get("wit_recovery_min_vital") or 22)
            if (best_score >= 0 and failure < 35 and vital > crit_vital
                    and turn not in SUMMER_CAMP_TURNS):
                wit_cmd = self._enabled_training_idx(enabled, 4)
                if wit_cmd:
                    wit_fail = int(wit_cmd.get("failure_rate") or 0)
                    wit_energy = self._training_energy_delta(wit_cmd)
                    targets = self._training_targets(preset, chara)
                    wit_mult = self._wit_balance_multiplier(chara, targets, preset)
                    if (wit_energy > 0
                            and wit_fail < int(preset.get("wit_recovery_failure_limit") or 30)
                            and wit_mult >= 0.85):
                        return wit_cmd
            if turn >= 73 and cfg.get("train_wit_during_finale", False):
                wit_cmd = self._enabled_training_idx(enabled, 4)
                if wit_cmd:
                    return wit_cmd
            return self._record_recovery(rest, turn)
        conserve = self._summer_conserve_command(enabled, turn, vital, best_score, preset, rest, recreation)
        if conserve:
            return conserve
        return best

    def _rest_command(self, commands):
        for cmd in commands:
            if cmd.get("command_type") == 7 and cmd.get("command_id") == 701:
                return cmd
        return None

    def _recreation_command(self, commands):
        for cmd in commands:
            if cmd.get("command_type") == 3:
                return cmd
        return None

    def _medic_command(self, commands):
        for cmd in commands:
            if cmd.get("command_type") == 8 and cmd.get("command_id") == 801:
                return cmd
        return None

    def _enabled_training(self, commands, command_id):
        for cmd in commands:
            if cmd.get("command_type") == 1 and cmd.get("command_id") == command_id:
                return cmd
        return None

    def _enabled_training_idx(self, commands, idx):
        for cmd in commands:
            if cmd.get("command_type") == 1 and TRAINING_COMMANDS.get(cmd.get("command_id")) == idx:
                return cmd
        return None

    def _summer_conserve_command(self, enabled, turn, vital, best_score, preset, rest, recreation):
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("must_rest_before_summer", True):
            return None
        if turn not in SUMMER_CONSERVE_TURNS:
            return None
        if best_score >= float(preset.get("summer_score_threshold") or 0.34):
            return None
        if vital < SUMMER_CONSERVE_ENERGY:
            if turn in SUMMER_CAMP_TURNS and recreation:
                return recreation
            return rest
        return self._enabled_training_idx(enabled, 4)

    def _has_curable_bad_status(self, chara, preset):
        wanted = self._cure_condition_names(preset)
        if not wanted:
            return False
        for effect_id in chara.get("chara_effect_id_array") or []:
            try:
                effect_id = int(effect_id)
            except (TypeError, ValueError):
                continue
            name = BAD_EFFECT_NAMES.get(effect_id)
            if name and self._condition_key(name) in wanted:
                return True
        return False

    def _cure_condition_names(self, preset):
        result = set()
        names = preset.get("cure_asap_conditions") or []
        if isinstance(names, str):
            names = names.split(",")
        for name in names:
            key = self._condition_key(name)
            if key:
                result.add(key)
        return result

    def _condition_key(self, name):
        text = str(name or "").strip()
        if not text or text.startswith("("):
            return ""
        return "".join(ch.lower() for ch in text if ch.isalnum())

    def _command_reason(self, command):
        command_type = command.get("command_type")
        command_id = command.get("command_id")
        # v6.7.2: human-readable labels without the trailing command_id
        # noise that was cluttering the dashboard's Decision Reasoning panel.
        if command_id in TRAINING_COMMANDS:
            name = TRAINING_NAMES[TRAINING_COMMANDS.get(command_id, 0)]
            try:
                rainbow = self._rainbow_partner_count(command, getattr(self, "current_chara", {}) or {})
            except Exception:
                rainbow = 0
            suffix = f" (rainbow x{rainbow})" if rainbow else ""
            if command.get("_energy_rescue"):
                suffix += " (energy rescue)"
            return f"Train {name}{suffix}"
        if command_type == 7 and command_id == 701:
            return "Rest"
        if command_type == 3:
            return "Recreation"
        if command_type == 8 and command_id == 801:
            return "Medic"
        return f"command {command_type}"

    def _coerce_stat_index(self, value):
        if value is None:
            return None
        text = str(value).strip().lower()
        aliases = {
            "speed": 0, "spd": 0, "101": 0, "601": 0, "0": 0,
            "stamina": 1, "sta": 1, "105": 1, "602": 1, "1": 1,
            "power": 2, "pow": 2, "102": 2, "603": 2, "2": 2,
            "guts": 3, "gut": 3, "103": 3, "604": 3, "3": 3,
            "wit": 4, "wisdom": 4, "wiz": 4, "int": 4, "106": 4, "605": 4, "4": 4,
        }
        return aliases.get(text)

    def _priority_indices(self, preset, key, fallback_key=None):
        cfg = ((preset or {}).get("mant_config") or {})
        raw = cfg.get(key)
        if raw is None:
            raw = (preset or {}).get(key)
        if raw is None and fallback_key:
            raw = cfg.get(fallback_key)
            if raw is None:
                raw = (preset or {}).get(fallback_key)
        if raw is None:
            raw = [0, 1, 2, 3, 4]
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.split(",")]
        out = []
        for value in raw if isinstance(raw, (list, tuple)) else []:
            idx = self._coerce_stat_index(value)
            if idx is not None and idx not in out:
                out.append(idx)
        for idx in range(5):
            if idx not in out:
                out.append(idx)
        return out

    def _training_blacklisted(self, idx, preset):
        cfg = ((preset or {}).get("mant_config") or {})
        raw = cfg.get("training_blacklist") or []
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.split(",")]
        blocked = {self._coerce_stat_index(value) for value in raw}
        return idx in blocked

    def _failure_allowed(self, command, preset, has_charm=False):
        cfg = ((preset or {}).get("mant_config") or {})
        failure = int((command or {}).get("failure_rate") or 0)
        max_failure = int(cfg.get("maximum_failure_chance") or 20)
        if failure <= max_failure:
            return True
        # v1.5 charm-aware admission (android analyzeTrainings(ignoreFailureChance
        # = hasCharm)): when a Good-Luck Charm is held, a high-main-gain training
        # stays ELIGIBLE at any failure chance -- the charm zeroes the failure
        # when this training is the pick (items._charm_target consumes it).  This
        # lets Icarus take the risky high-stat rainbows android routinely grabs.
        if has_charm and cfg.get("enable_charm_aware_training", True):
            main_gain = self._command_main_stat_gain(command)
            _cm = cfg.get("charm_min_main_gain")   # 0-safe: honor an explicit 0
            charm_min = int(_cm) if _cm is not None else tb_rules.DEFAULT_CHARM_MIN_MAIN_GAIN
            charm_fail_limit = int(cfg.get("charm_failure_admit_limit") or 100)
            if main_gain >= charm_min and failure <= charm_fail_limit:
                return True
        if not cfg.get("enable_risky_training", False):
            return False
        main_gain = self._command_main_stat_gain(command)
        min_gain = int(cfg.get("risky_training_min_stat_gain") or 20)
        risky_max = int(cfg.get("risky_training_max_failure_chance") or 30)
        return main_gain >= min_gain and failure <= risky_max

    def _scheduled_distance_target(self, preset):
        """v6.7.15: derive the training-target distance from the races
        the solver actually scheduled (``preset.extra_race_list``),
        rather than from aptitude.

        Returns one of "short"/"mile"/"middle"/"long", or None when no
        schedule is available (manual mode, or before the first solve).

        Rule: pick the LONGEST distance bucket that has meaningful
        representation in the schedule -- at least 20% of scheduled
        races, or at least 3 races.  This means a substantial block of
        longer races pulls the stamina target up, but a single outlier
        long race doesn't drag the whole build toward a distance the
        trainee rarely runs.  A trainee scheduled for 14 Mile + 12
        Medium resolves to "middle" (stamina ~800, enough for 2400m);
        it does NOT resolve to "long" just because Long aptitude is high,
        because no Long races are scheduled.
        """
        rp = getattr(self, "race_planner", None)
        if rp is None:
            return None
        race_ids = (preset or {}).get("extra_race_list") or []
        if not race_ids:
            return None
        from collections import Counter
        buckets: Counter = Counter()
        for rid in race_ids:
            try:
                bucket = rp._distance_bucket(int(rid))
            except Exception:
                bucket = ""
            if bucket:
                # Normalize any "sprint" alias to "short" to match the
                # defaults table keys.
                buckets["short" if bucket == "sprint" else bucket] += 1
        if not buckets:
            return None
        total = sum(buckets.values())
        threshold = max(3, int(total * 0.20))
        order = ["long", "middle", "mile", "short"]  # longest first
        for dist in order:
            if buckets.get(dist, 0) >= threshold:
                return dist
        # Nothing crossed the threshold (very mixed schedule): fall back
        # to the single most-scheduled bucket.
        return buckets.most_common(1)[0][0]

    def _training_targets(self, preset, chara):
        cfg = ((preset or {}).get("mant_config") or {})
        if cfg.get("disable_stat_targets", False):
            return [1200, 1200, 1200, 1200, 1200]
        by_distance = cfg.get("stat_targets_by_distance") or {}
        raw_preferred = cfg.get("preferred_distance")
        # v6.7.13: previously, when by_distance was empty AND
        # preferred_distance was unset/auto, this returned the 9999
        # sentinel immediately -- giving a trainee with no explicit
        # stat targets NO targets at all (trains everything equally,
        # builds Speed-heavy, starves Stamina).  Now we only early-return
        # when expect_attribute carries real (non-sentinel) values;
        # otherwise we fall through to the aptitude-based per-distance
        # defaults below so every trainee gets a sensible stamina target
        # for the distance it will actually race.
        expect = (preset or {}).get("expect_attribute")
        if not by_distance and raw_preferred in (None, "", "auto"):
            if expect and any(int(v or 0) < 9999 for v in expect[:5]):
                return list(expect)[:5]
            # else: fall through to aptitude-based defaults
        preferred = str(raw_preferred or "auto").strip().lower()
        aliases = {"sprint": "short", "medium": "middle", "mid": "middle"}
        preferred = aliases.get(preferred, preferred)
        if preferred == "auto":
            # v6.7.15: the training-target distance should follow the
            # races the solver ACTUALLY SCHEDULES, not the trainee's
            # aptitude.  A trainee can have Long aptitude A (e.g. Oguri
            # Cap after a parent Long spark) yet race only Mile/Medium
            # because that's what the solver picked for fans/epithets.
            # Training to a Long stamina target (~1000) then wastes
            # training turns on stamina the trainee never uses, starving
            # Speed/Power.  So derive the target distance from the
            # scheduled race list first; fall back to the aptitude
            # tie-break only when no schedule is available (manual mode,
            # or early before the first solve).
            scheduled = self._scheduled_distance_target(preset)
            if scheduled:
                preferred = scheduled
            else:
                aptitudes = {
                    "short": int((chara or {}).get("proper_distance_short") or 1),
                    "mile": int((chara or {}).get("proper_distance_mile") or 1),
                    "middle": int((chara or {}).get("proper_distance_middle") or 1),
                    "long": int((chara or {}).get("proper_distance_long") or 1),
                }
                # Tie-break toward the LONGER distance (v6.7.13): a tie
                # picks the higher-stamina target, the safe direction to
                # err when we have no schedule to go on.
                order = ["long", "middle", "mile", "short"]
                best_apt = max(aptitudes.values())
                preferred = next(d for d in order if aptitudes[d] == best_apt)
        defaults = {
            "short": [1200, 450, 1000, 500, 1000],
            "mile": [1200, 600, 1000, 500, 1000],
            "middle": [1200, 800, 1000, 600, 900],
            "long": [1200, 1000, 900, 700, 900],
        }
        row = None
        if isinstance(by_distance, dict):
            row = by_distance.get(preferred) or by_distance.get({"short":"sprint","middle":"medium"}.get(preferred, preferred))
        # v6.7.12 fix: when the preset's stat_targets_by_distance does
        # NOT cover the resolved preferred distance, fall back to the
        # built-in per-distance ``defaults`` BEFORE the expect_attribute
        # sentinel ([9999,...] = "no real target").  Previously the
        # order was row -> expect_attribute -> defaults, so a preset
        # that only specified e.g. "mile" left Medium/Long distances
        # with no stamina target at all (the 9999 sentinel means
        # "train everything equally", which builds Speed-heavy and
        # starves Stamina).  This was the cause of trainees finishing
        # Medium/Long races -- including the Trackblazer finale -- with
        # Mile-tier stamina (~425) and losing.  The defaults give
        # Medium 800 / Long 1000 stamina targets so the bot actually
        # builds for the distance it's racing.
        if row:
            targets = list(row)[:5]
        else:
            default_row = defaults.get(preferred)
            expect = (preset or {}).get("expect_attribute")
            # Use the distance default unless it's missing; only then
            # fall back to expect_attribute, then the 9999 sentinel.
            targets = list(default_row or expect or [9999] * 5)[:5]
        while len(targets) < 5:
            targets.append(9999)
        try:
            turn = int((chara or {}).get("turn") or 0)
        except Exception:
            turn = 0
        # v1.5: milestone target down-scaling now DEFAULTS OFF (full targets all
        # career), matching the actual Android bot.  The v1.4 code scaled targets
        # to 33% (Classic) / 66% (Senior) on the belief it "matched the Android
        # schedule" -- but the Android scorer (Scoring.kt calculateStatEfficiency)
        # measures completion against the FULL per-distance target every turn and
        # lets its ratio-bucket multipliers create the natural pacing.  The v1.4
        # scaling made under-built stats read as ~93% "done" mid-career (e.g.
        # speed 368 vs a scaled 396 target at turn 33), so both the cap curve and
        # _target_pressure_multiplier SUPPRESSED the very stat Android boosts.
        # That back-loaded stats (peak at the finale, underpowered for the
        # Classic/Senior G1s) and lost winnable races.  Pacing now emerges from
        # _target_pressure_multiplier's buckets, exactly like Android.  Users who
        # want the old behaviour can still set classic/senior_year_milestone_pct.
        if turn <= 48:
            raw = cfg.get("classic_year_milestone_pct")
            if raw is None:
                raw = cfg.get("junior_milestone_pct")
            pct = float(raw if raw is not None else 100) / 100.0
            if pct < 1.0:
                targets = [max(1, int(float(v or 0) * pct)) for v in targets]
        elif turn <= 72:
            raw = cfg.get("senior_year_milestone_pct")
            if raw is None:
                raw = cfg.get("classic_milestone_pct")
            pct = float(raw if raw is not None else 100) / 100.0
            if pct < 1.0:
                targets = [max(1, int(float(v or 0) * pct)) for v in targets]
        return targets

    def _near_rainbow_partner_count(self, command, chara, preset):
        if not command or self._rainbow_partner_count(command, chara) > 0:
            return 0
        cfg = ((preset or {}).get("mant_config") or {})
        threshold = int(cfg.get("near_rainbow_bond_threshold") or tb_rules.NEAR_RAINBOW_BOND_THRESHOLD)
        threshold = max(1, min(79, threshold))
        bonds = self._bond_map(chara or {})
        count = 0
        for partner_id in command.get("training_partner_array") or []:
            try:
                partner_id = int(partner_id)
            except Exception:
                continue
            if partner_id in DECK_PARTNERS and threshold <= int(bonds.get(partner_id, 0) or 0) < 80:
                count += 1
        return count

    def _near_rainbow_bonus(self, command, chara, preset):
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("enable_near_rainbow_bonus", True):
            return 0.0
        count = self._near_rainbow_partner_count(command, chara, preset)
        if count <= 0:
            return 0.0
        per = float(cfg.get("near_rainbow_bonus_per_partner") or tb_rules.NEAR_RAINBOW_BONUS_PER_PARTNER)
        cap = float(cfg.get("near_rainbow_bonus_cap") or tb_rules.NEAR_RAINBOW_BONUS_CAP)
        return max(0.0, min(cap, per * count))

    def _training_level(self, command):
        for key in ("training_level", "facility_level", "level", "command_level", "training_lv", "facility_lv"):
            try:
                level = int((command or {}).get(key) or 0)
            except Exception:
                level = 0
            if level:
                return max(1, min(5, level))
        return 0

    def _training_level_multiplier(self, command, idx, preset):
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("enable_training_level_weighting", True):
            return 1.0
        level = self._training_level(command)
        if level < 2:
            return 1.0
        priorities = self._priority_indices(preset, "training_stat_priority", "stat_priority")
        if idx not in priorities[:3]:
            return 1.0
        rank = priorities.index(idx)
        return float(tb_rules.TRAINING_LEVEL_MULTIPLIER_BY_RANK.get(rank, {}).get(level, 1.0))

    def _summer_priority_multiplier(self, idx, turn, preset):
        if turn not in SUMMER_CAMP_TURNS and not is_summer_turn(turn, self.trackblazer_guide):
            return 1.0
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("enable_summer_stat_priority", True):
            return 1.0
        priorities = self._priority_indices(preset, "summer_stat_priority", "training_stat_priority")
        try:
            rank = priorities.index(idx)
        except ValueError:
            return 1.0
        bonuses = cfg.get("summer_priority_bonus_by_rank") or tb_rules.SUMMER_PRIORITY_BONUS_BY_RANK
        try:
            bonus = float(bonuses[rank]) if rank < len(bonuses) else 0.0
        except Exception:
            bonus = 0.0
        return 1.0 + max(0.0, min(0.40, bonus))

    def _cap_adjusted_stat_gain_score(self, stat_gain_score, target, current, cap, command, chara, preset):
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("disable_training_on_maxed_stats", True):
            return stat_gain_score
        if cap <= 0 or target >= 5:
            return stat_gain_score
        ratio = current / cap
        if ratio > 1.0:
            if (self._rainbow_partner_count(command, chara) > 0 and
                    (((preset or {}).get("mant_config") or {}).get("enable_cap_buffer_rainbow_allowance", True))):
                return stat_gain_score * float((((preset or {}).get("mant_config") or {}).get("cap_rainbow_allowance_factor") or tb_rules.CAP_RAINBOW_ALLOWANCE_FACTOR))
            return 0.0
        if ratio > 0.97:
            return stat_gain_score * (0.35 - ((ratio - 0.97) / 0.03) * 0.25)
        if ratio > 0.94:
            return stat_gain_score * (0.55 - ((ratio - 0.94) / 0.03) * 0.20)
        if ratio > 0.90:
            return stat_gain_score * (0.75 - ((ratio - 0.90) / 0.04) * 0.20)
        if ratio > 0.86:
            return stat_gain_score * (0.85 - ((ratio - 0.86) / 0.04) * 0.10)
        if ratio > 0.82:
            return stat_gain_score * (0.91 - ((ratio - 0.82) / 0.04) * 0.06)
        if ratio > 0.78:
            return stat_gain_score * (0.95 - ((ratio - 0.78) / 0.04) * 0.04)
        if ratio > 0.74:
            return stat_gain_score * (0.98 - ((ratio - 0.74) / 0.04) * 0.03)
        if ratio > 0.70:
            return stat_gain_score * (1.00 - ((ratio - 0.70) / 0.04) * 0.02)
        return stat_gain_score

    def _score_command(self, command, data, chara, preset):
        turn = int(chara.get("turn") or 0)
        cfg = ((preset or {}).get("mant_config") or {})
        weights = self._period_row(preset.get("score_value"), turn, [0.11, 0.10, 0.006, 0.09])
        base = preset.get("base_score") or [0, 0, 0, 0, 0]
        targets = self._training_targets(preset, chara)
        idx = TRAINING_COMMANDS.get(command.get("command_id"), 0)
        if self._training_blacklisted(idx, preset):
            if not (cfg.get("enable_prioritize_skill_hints", False) and (command.get("tips_event_partner_array") or [])):
                return -999.0
        has_charm = self._owned_item_count(data, GOOD_LUCK_CHARM_ID) > 0
        if not self._failure_allowed(command, preset, has_charm=has_charm):
            return -999.0
        if self._should_avoid_full_hp_wit(command, chara, preset):
            return -999.0
        score = float(base[idx] if idx < len(base) else 0)
        w_lv1 = float(weights[0] if len(weights) > 0 else 0.11)
        w_lv2 = float(weights[1] if len(weights) > 1 else 0.10)
        w_energy = float(weights[2] if len(weights) > 2 else 0.006)
        w_hint = float(weights[3] if len(weights) > 3 else 0.09)
        stat_mult = preset.get("stat_value_multiplier") or [0.01, 0.01, 0.01, 0.01, 0.01, 0.005]
        bonds = self._bond_map(chara)
        partners = command.get("training_partner_array") or []
        hints = set(command.get("tips_event_partner_array") or [])
        pal_count = 0
        hint_count = 0
        for partner_id in partners:
            bond = bonds.get(partner_id, 0)
            if partner_id in hints:
                hint_count += 1

            if bond >= 80:
                # Rainbow/friendship training: unlike bond-building partners,
                # high-bond deck partners should add direct training value.
                rainbow_value = float(preset.get("rainbow_partner_value") or 0.18)
                if partner_id in DECK_PARTNERS:
                    if partner_id == 6:
                        rainbow_value *= 0.85
                    score += rainbow_value
                continue

            time_decay = max(0.0, (72 - turn) / 72.0)
            efficiency_boost = 1.0 + (bond / 80.0) * 0.5 if bond >= 60 else 1.0
            
            weight = time_decay * efficiency_boost

            if partner_id not in DECK_PARTNERS:
                yield_val = self._npc_score(bond, turn, preset)
                score += yield_val * weight
                continue

            if partner_id == 6:
                pal_count += 1
                yield_val = self._pal_score(bond, preset)
                score += yield_val * weight
                continue

            ratio = min(1.0, bond / 80.0)
            yield_val = w_lv1 + (w_lv2 - w_lv1) * ratio
            score += yield_val * weight
        if hint_count and cfg.get("enable_prioritize_skill_hints", False):
            # Capped diminishing hint bonus (ported from UmaAuto): the first hint
            # is worth full weight; additional hints on the same training add a
            # smaller increment, and the count is capped at 4 so one
            # hint-stacked turn can't dominate the score. Previously this was a
            # steeper, uncapped linear bonus (w_hint * hint_count).
            hint_scale = float(cfg.get("hint_count_scale", 0.5))
            score += w_hint * (1.0 + hint_scale * (min(hint_count, 4) - 1))
        effect_items = command.get("params_inc_dec_info_array") or self._official_training_effect_items(command)
        for item in effect_items:
            value = float(item.get("value") or 0)
            if item.get("target_type") == 10:
                energy_score = value * w_energy
                if int(chara.get("vital") or 0) >= 80 and value < 0:
                    energy_score *= 0.9
                score += energy_score
                continue
            target = STAT_TARGETS.get(item.get("target_type"))
            if target is None:
                continue
            if target == 5:
                # Skill points. Previously ignored entirely, which made Wit/SP
                # training look identical with or without an SP payout. Value SP
                # in proportion to how much we still need: SP is precious early
                # (need it to buy the priority skill list) and worthless once we
                # have a big surplus. Tunable via preset.skill_point_value.
                sp_mult = float(stat_mult[5] if len(stat_mult) > 5 else 0.005)
                sp_mult *= float(preset.get("skill_point_value", 1.0))
                current_sp = float(chara.get("skill_point") or 0)
                sp_soft_cap = float(preset.get("skill_point_soft_cap", 1200))
                need_factor = max(0.15, 1.0 - (current_sp / sp_soft_cap)) if sp_soft_cap > 0 else 1.0
                score += value * sp_mult * need_factor
                continue

            stat_gain_score = value * float(stat_mult[target] if target < len(stat_mult) else 0.01)
            cap = float(targets[target] if target < len(targets) else 9999)
            if cap > 0 and target < 5:
                current = self._current_stat(chara, target)
                stat_gain_score = self._cap_adjusted_stat_gain_score(stat_gain_score, target, current, cap, command, chara, preset)
                stat_gain_score *= self._target_pressure_multiplier(target, chara, targets, preset)
                stat_gain_score *= self._stat_priority_multiplier(target, preset, turn)
            score += stat_gain_score
        if pal_count:
            score *= 1.0 + max(0.0, min(1.0, float(preset.get("pal_card_multiplier") or 0.1)))
        rainbow_bonus = self._rainbow_bonus(command, chara, preset) if cfg.get("enable_rainbow_training_bonus", True) else 0.0
        if rainbow_bonus > 0:
            score *= 1.0 + rainbow_bonus
        else:
            near_bonus = self._near_rainbow_bonus(command, chara, preset)
            if near_bonus > 0:
                score *= 1.0 + near_bonus

        # Lift a behind-target stat so it can compete with the rainbow chase.
        if score > 0:
            score *= self._starved_stat_multiplier(idx, chara, targets, preset)

        score *= self._training_level_multiplier(command, idx, preset)
        score *= self._summer_priority_multiplier(idx, turn, preset)
        if preset.get("compensate_failure", True):
            # A failed training yields nothing, so the expected value of a risky
            # training is roughly score * (1 - p_fail). The old model used
            # (1 - fail/50), which over-punishes (e.g. 30% fail -> x0.40 instead
            # of the true x0.70) and could zero out at 50%. Use a true EV term
            # plus a mild risk-aversion penalty, tunable via failure_risk_aversion.
            fail_rate = float(command.get("failure_rate") or 0) / 100.0
            fail_rate = max(0.0, min(1.0, fail_rate))
            risk_aversion = float(preset.get("failure_risk_aversion", 0.5))
            score *= max(0.0, (1.0 - fail_rate) * (1.0 - fail_rate * risk_aversion))
        if idx == 4:
            vital = int(chara.get("vital") or 0)
            max_vital = int(chara.get("max_vital") or 100)
            gain = self._training_energy_delta(command)
            if vital >= max_vital or (gain > 0 and vital + gain > max_vital):
                score *= 0.35 if turn > 72 else 0.75
            elif vital < 85:
                score *= 1.03
        extra = self._extra_weight(idx, turn, preset)
        if extra == -1:
            return -999.0
        score *= max(0.0, min(2.0, 1.0 + extra))

        if turn < 60:
            deck_mults = preset.get("_deck_multipliers")
            if deck_mults and len(deck_mults) > idx:
                score *= float(deck_mults[idx])

        if is_summer_turn(turn, self.trackblazer_guide):
            score *= 1.0 + float(((self.trackblazer_guide.get("summer_strategy") or {}).get("summer_training_score_bonus") or 0.16))

        if idx == 4:
            score *= self._wit_balance_multiplier(chara, targets, preset)

        return score

    def _command_stat_gain(self, cmd, sp_weight=0):
        if not cmd:
            return 0
        total = 0
        for item in cmd.get("params_inc_dec_info_array") or []:
            tt = item.get("target_type")
            if tt in [1, 2, 3, 4, 5]:
                total += int(item.get("value") or 0)
            elif (tt == 6 or tt == 30) and sp_weight > 0:
                total += int(item.get("value") or 0) * sp_weight
        if total == 0:
            for field in ["speed", "stamina", "power", "guts", "wiz"]:
                total += int(cmd.get(field) or 0)
            if sp_weight > 0:
                total += int(cmd.get("lp") or cmd.get("skill_point") or 0) * sp_weight
        return total

    def _current_stat(self, chara, target):
        keys = ["speed", "stamina", "power", "guts", "wiz", "skill_point"]
        return float(chara.get(keys[target], 0) or 0)

    def _team_command(self, data, command_id):
        team_data = data.get("team_data_set") or {}
        for cmd in team_data.get("command_info_array") or []:
            if cmd.get("command_id") == command_id:
                return cmd
        return None

    def _bond_map(self, chara):
        result = {}
        for row in chara.get("evaluation_info_array") or []:
            result[row.get("target_id", 0)] = row.get("evaluation", 0)
        return result

    def _npc_score(self, bond, turn, preset):
        if bond >= 80:
            return 0.0
        row = self._period_row(preset.get("npc_score_value"), turn, [0.05, 0.05, 0.05])
        v1 = float(row[0] if len(row) > 0 else 0.05)
        v2 = float(row[1] if len(row) > 1 else v1)
        ratio = min(1.0, bond / 80.0)
        return v1 + (v2 - v1) * ratio

    def _pal_score(self, bond, preset):
        if bond >= 80:
            return 0.0
        scores = preset.get("pal_friendship_score") or [0.08, 0.057, 0.018]
        v1 = float(scores[0] if len(scores) > 0 else 0.08)
        v2 = float(scores[1] if len(scores) > 1 else v1)
        ratio = min(1.0, bond / 80.0)
        return v1 + (v2 - v1) * ratio

    def _period_index(self, turn):
        if turn <= 24:
            return 0
        if turn <= 48:
            return 1
        if turn <= 60:
            return 2
        if turn <= 72:
            return 3
        return 4

    def _period_row(self, rows, turn, fallback):
        if not isinstance(rows, list) or not rows:
            return fallback
        idx = min(self._period_index(turn), len(rows) - 1)
        row = rows[idx]
        return row if isinstance(row, list) else fallback

    def _extra_weight(self, idx, turn, preset):
        rows = preset.get("extra_weight") or [[0, 0, 0, 0, 0]] * 4
        if turn <= 24:
            row_idx = 0
        elif turn <= 48:
            row_idx = 1
        elif turn in SUMMER_CAMP_TURNS and len(rows) >= 4:
            row_idx = 3
        else:
            row_idx = 2
        if row_idx >= len(rows) or not isinstance(rows[row_idx], list) or idx >= len(rows[row_idx]):
            return 0.0
        return float(rows[row_idx][idx] or 0)

    def _mood_threshold(self, turn, preset):
        if turn <= 36:
            return int(preset.get("motivation_threshold_year1") or 3)
        if turn <= 60:
            return int(preset.get("motivation_threshold_year2") or 4)
        return int(preset.get("motivation_threshold_year3") or 4)

    # v6.7.25 — tiny helper used by _best_command to remember when rest or
    # recreation actually fired, so the next turn can break a recovery chain.
    def _record_recovery(self, cmd, turn):
        if not cmd:
            return cmd
        ct = cmd.get("command_type")
        if ct == 7:
            self._last_recovery_turn = int(turn)
            self._last_recovery_kind = "rest"
        elif ct == 3:
            self._last_recovery_turn = int(turn)
            self._last_recovery_kind = "recreation"
        return cmd

    def _should_recreate(self, recreation, preset, turn, motivation, vital, best_score):
        if not recreation:
            return False
        if turn in SUMMER_CAMP_TURNS:
            return False
        # v6.7.25 — break the rest → recreation → recreation chain.
        # Two changes:
        #  1) Tighter vital ceiling on the motivation-driven trigger.
        #     The old `vital < 90` would fire recreation any time energy was
        #     even slightly off-cap. After a rest brought vital into the 70s,
        #     the bot would still see a low-mood + weak-rainbow turn and pick
        #     recreation — sometimes for several turns straight while mood
        #     ticked up one tier at a time. A 60-energy ceiling matches the
        #     real intent: "we still need recovery", not "we're not topped up".
        #  2) Don't fire the auto trigger if the previous turn was already
        #     a recovery action (rest or recreation) AND vital is in a
        #     workable range. Pushes the bot to train (or accept a mediocre
        #     score) instead of repeating recovery.
        last_recovery = getattr(self, "_last_recovery_turn", None)
        last_recovery_kind = getattr(self, "_last_recovery_kind", None)
        recovery_just_used = last_recovery == turn - 1
        if motivation < self._mood_threshold(turn, preset) and vital < 60 and best_score <= 0.3:
            if not (recovery_just_used and vital >= 50):
                return True
        # v1.5 mood floor (android parity, CORRECTED).  Android recovers mood
        # whenever it slides to NORMAL or below ("Mood is NORMAL -> recover") on
        # any turn with workable energy -- REGARDLESS of how good the available
        # training is -- because Great mood multiplies every future training AND
        # race.  The first attempt gated this on a best_score ceiling, but a
        # rainbow always cleared it, so mood was NEVER recovered and the trainee
        # ground both summer camps at mood 2 (Bad), tanking stats.  This now
        # fires on any non-camp non-race turn where mood is at/below the floor
        # (default NORMAL=3) and energy is workable, recreating until mood climbs
        # back out of the floor (self-limiting: stops once motivation > floor).
        cfg = ((preset or {}).get("mant_config") or {})
        great = int(cfg.get("great_mood_value") or 5)
        energy_floor = int(cfg.get("mood_recovery_energy_floor") or 50)
        # Pre-summer-camp prep: on the turns right before a Summer block, push
        # mood all the way to GREAT so the camp's boosted rainbow gains aren't
        # capped by sub-Great mood (camp turns themselves train, never recreate,
        # so this is the last chance to fix mood before the biggest stat window).
        if (cfg.get("enable_keep_great_mood", True) and turn in {34, 35, 58, 59}
                and motivation < great and vital >= energy_floor):
            return True
        # General mood floor: recover whenever mood is at/below NORMAL on a
        # workable-energy non-camp turn (android: "Mood is NORMAL -> recover").
        mood_floor = int(cfg.get("mood_recovery_floor") or 3)
        if (cfg.get("enable_keep_great_mood", True)
                and motivation <= mood_floor and vital >= energy_floor):
            return True
        if not preset.get("prioritize_recreation"):
            return False
        thresholds = preset.get("pal_thresholds") or []
        if not thresholds:
            return False
        stage = int(preset.get("_pal_event_stage") or 0)
        if stage >= len(thresholds):
            stage = 0
        row = thresholds[stage]
        if not isinstance(row, list) or len(row) < 2:
            return False
        mood_ok = motivation <= int(row[0])
        energy_ok = vital <= int(row[1])
        score_ok = True
        if len(row) > 2:
            score_ok = best_score <= float(row[2])
        # Same anti-chain guard on the PAL-threshold path: if the prior turn
        # was recreation specifically, require an actual energy deficit before
        # firing again. Rest → recreation is fine; recreation → recreation
        # needs evidence that mood/energy are still bad enough to justify it.
        if recovery_just_used and last_recovery_kind == "recreation" and vital >= 50:
            return False
        return mood_ok and energy_ok and score_ok

    def choose_from_event(self, event, current_turn):
        if self.event_manager:
            return self.event_manager.choose(event, self.current_preset, current_turn, getattr(self, "current_chara", None))
        return 1

    def _decision_payload_from_command(self, command, chara):
        command_type = command.get("command_type", 1)
        command_id = command.get("command_id")
        command_group_id = command.get("command_group_id", 0)
        if command_type == 3:
            command_group_id = command_id
            command_id = 0
        return {
            "command_type": command_type,
            "command_id": command_id,
            "command_group_id": command_group_id,
            "select_id": command.get("select_id", 0),
            "current_turn": chara["turn"],
            "current_vital": chara.get("vital", 0),
        }

    def _recent_race_chain_count(self, data, current_turn):
        """Count immediately preceding race turns from injected/history payloads.

        The runner injects its dashboard action_history into state["data"] before
        strategy evaluation.  Some API payloads also include their own history;
        both shapes are accepted here.  Non-race actions break the streak.
        """
        rows = data.get("action_history") or data.get("turn_history") or []
        if not isinstance(rows, list):
            return 0
        count = 0
        for row in reversed(rows[-10:]):
            if not isinstance(row, dict):
                continue
            try:
                turn = int(row.get("turn") or row.get("current_turn") or 0)
            except Exception:
                continue
            if turn >= int(current_turn or 0):
                continue
            action = str(row.get("action") or row.get("command") or row.get("type") or "").lower()
            if "race" in action:
                count += 1
            elif action:
                break
        return count

    def _program_grade_rank(self, program_id):
        if not self.race_planner or not program_id:
            return 0
        info = {}
        pid = int(program_id or 0)
        info.update((getattr(self.race_planner, "program", {}) or {}).get(pid) or {})
        info.update((getattr(self.race_planner, "official_races", {}) or {}).get(pid) or {})
        grade = tb_rules.normalize_grade(info.get("grade") or info.get("race_instance_id"))
        return int(tb_rules.GRADE_RANK.get(grade, 0) or 0)

    def _best_training_candidate(self, data, chara, preset):
        commands = (data.get("home_info") or {}).get("command_info_array") or []
        enabled = [cmd for cmd in commands if cmd.get("is_enable", 1)]
        training = [cmd for cmd in enabled if cmd.get("command_type") == 1 and cmd.get("command_id") in TRAINING_COMMANDS]
        if not training:
            return None, None, []
        scored = [(self._score_command(cmd, data, chara, preset), cmd) for cmd in training]
        scored.sort(key=lambda row: row[0], reverse=True)
        self.last_training_scores = [
            {
                "command_id": cmd.get("command_id"),
                "name": TRAINING_NAMES[TRAINING_COMMANDS.get(cmd.get("command_id"), 0)],
                "score": round(score, 4),
                "failure_rate": int(cmd.get("failure_rate") or 0),
                "main_gain": self._command_main_stat_gain(cmd),
                "total_gain": self._command_stat_gain(cmd),
                "rainbow": self._rainbow_partner_count(cmd, chara),
                "near_rainbow": self._near_rainbow_partner_count(cmd, chara, preset),
                "training_level": self._training_level(cmd),
            }
            for score, cmd in scored
        ]
        self._scored_turn = int((chara or {}).get("turn") or 0)
        return scored[0][0], scored[0][1], scored

    def _guide_race_chain_break(self, data, chara, preset, program_id):
        cfg = ((preset or {}).get("mant_config") or {})
        # v7.6: never override a hand-picked race schedule.  When the user
        # supplies a manual race list, every race they selected must run --
        # the race-streak safety heuristic (train/rest/recreation substitution)
        # must not hijack it.  This mirrors the manual-mode guard in
        # _irregular_training_decision (see below).  Without this guard the
        # "unsafe grade" branch disproportionately dropped DIRT races, since
        # ~70% of dirt races are OP/PRE-OP grade (rank < 3) versus ~43% of turf.
        if str((preset or {}).get("extra_race_list_source") or "").strip().lower() == "manual":
            return None
        if not cfg.get("enable_game8_race_chain_break", True):
            return None
        if cfg.get("ignore_consecutive_race_warning", False):
            return None
        turn = int(chara.get("turn") or 0)
        # Year-end and Finale race windows are intentionally permissive.
        if turn in {23, 24, 47, 48, 71, 72} or turn >= 73:
            return None
        chain_count = self._recent_race_chain_count(data, turn)
        _rct = cfg.get("race_chain_target")   # 0-safe: honor an explicit 0
        target = int(_rct) if _rct is not None else tb_rules.DEFAULT_RACE_CHAIN_TARGET
        # v6.7.7: reverted to pre-v6.7.3 behavior per user request.  The
        # v6.7.3 fix had introduced an unconditional HP-critical gate
        # that fired at chain_count >= legacy_target (2) regardless of
        # the user's chain target, and a hard cap that forced a break
        # at chain_count >= target with full HP.  Both changes
        # overrode the user's "Ignore Low Energy Racing Block" toggle
        # in subtle ways.  Per user direction, the toggle is now the
        # sole HP authority: ignore_low_energy_racing_block=True races
        # through any HP; =False applies HP gates only at chain_count
        # >= target.  The "Consecutive Races Limit" slider remains a
        # soft preference rather than a hard cap.
        if chain_count < target:
            # Backward-compat: older guide files use a 2-race rhythm. Keep that
            # behavior only for non-critical HP; critical HP waits for 3+ races.
            legacy_target = race_chain_target(self.trackblazer_guide)
            if chain_count < legacy_target:
                return None

        commands = (data.get("home_info") or {}).get("command_info_array") or []
        enabled = [cmd for cmd in commands if cmd.get("is_enable", 1)]
        rest = self._rest_command(enabled)
        recreation = self._recreation_command(enabled)
        vital = int(chara.get("vital") or 0)
        critical_vital = int(cfg.get("chain_break_critical_vital") or tb_rules.DEFAULT_CHAIN_CRITICAL_VITAL)
        low_vital = int(cfg.get("chain_break_low_vital") or tb_rules.DEFAULT_CHAIN_LOW_VITAL)
        grade_rank = self._program_grade_rank(program_id)
        unsafe_grade = grade_rank and grade_rank < int(cfg.get("chain_break_min_grade_rank") or tb_rules.UNSAFE_CHAIN_MIN_GRADE_RANK)

        best_score, best, _ = self._best_training_candidate(data, chara, preset)
        if best is not None:
            training_threshold = float(cfg.get("chain_break_training_threshold") or tb_rules.DEFAULT_CHAIN_TRAINING_THRESHOLD)
            fail_limit = int(cfg.get("chain_break_failure_limit") or tb_rules.DEFAULT_CHAIN_FAILURE_LIMIT)
            if best_score >= training_threshold and int(best.get("failure_rate") or 0) <= fail_limit:
                reason = (
                    f"Trackblazer race-streak safety: train after {chain_count} races "
                    f"score={best_score:.3f}"
                )
                return Decision("command", self._decision_payload_from_command(best, chara), reason)

        if chain_count >= target and vital <= critical_vital and not cfg.get("ignore_low_energy_racing_block", False):
            if recreation:
                return Decision("command", self._decision_payload_from_command(recreation, chara), f"Trackblazer race-streak safety: critical HP after {chain_count} races")
            if rest:
                return Decision("command", self._decision_payload_from_command(rest, chara), f"Trackblazer race-streak safety: critical HP rest after {chain_count} races")

        if chain_count >= target and ((vital <= low_vital and not cfg.get("ignore_low_energy_racing_block", False)) or unsafe_grade):
            if recreation and vital <= max(60, low_vital):
                return Decision("command", self._decision_payload_from_command(recreation, chara), f"Trackblazer race-streak safety: recreation after {chain_count} races")
            if rest and vital <= max(50, low_vital):
                return Decision("command", self._decision_payload_from_command(rest, chara), f"Trackblazer race-streak safety: rest after {chain_count} races")

        return None

    def _owned_item_count(self, data, item_id):
        try:
            item_id = int(item_id or 0)
        except Exception:
            return 0
        total = 0
        free = (data or {}).get("free_data_set") or {}
        for row in free.get("user_item_info_array") or []:
            try:
                if int(row.get("item_id") or 0) == item_id:
                    total += int(row.get("num") or row.get("current_num") or row.get("item_num") or 0)
            except Exception:
                continue
        return total

    def _rescue_energy_value(self, data, vital, rest_threshold, margin):
        """Energy value of the cheapest owned Vita/Kale that, when used, lifts
        vitality clear of ``rest_threshold + margin``; None if none would.

        Ported from UmaAuto.  Prefers the smallest sufficient item so we don't
        burn a Royal Kale Juice when a Vita 20 would do.
        """
        target = rest_threshold + margin
        owned = {}
        free = (data or {}).get("free_data_set") or {}
        for row in free.get("user_item_info_array") or []:
            try:
                iid = int(row.get("item_id") or 0)
            except Exception:
                continue
            if iid in ENERGY_ITEM_VALUES:
                owned[iid] = owned.get(iid, 0) + int(row.get("num") or row.get("current_num") or row.get("item_num") or 0)
        best = None
        for iid, qty in owned.items():
            if qty > 0 and vital + ENERGY_ITEM_VALUES[iid] > target:
                if best is None or ENERGY_ITEM_VALUES[iid] < ENERGY_ITEM_VALUES[best]:
                    best = iid
        return ENERGY_ITEM_VALUES[best] if best is not None else None

    def _can_rescue_training(self, data, chara, preset, best, best_score, vital, failure, rest_threshold):
        """True when a low-energy / high-failure rest should instead run ``best``
        by spending a Vita/Kale (energy rescue) or a Good-Luck Charm.

        Ported from UmaAuto's MANT scenario.  This only decides whether the
        rescue is worth a consumable; the actual top-up is performed by the
        existing item layer (items._energy_targets / _charm_target) once
        ``_best_command`` returns the training and the runner re-decides.
        """
        cfg = ((preset or {}).get("mant_config") or {})
        if not cfg.get("rescue_good_training", True):
            return False
        if best is None or int(best.get("command_type") or 0) != 1:
            return False
        if best_score is None or best_score <= 0:
            return False
        if vital < int(cfg.get("rescue_min_vital") or 25):
            return False
        rainbow = self._rainbow_partner_count(best, chara)
        strong = best_score >= float(cfg.get("rescue_score_threshold") or 0.55)
        if rainbow < 1 and not strong:
            return False
        margin = int(cfg.get("rescue_vital_margin") or 12)
        energy_val = self._rescue_energy_value(data, vital, rest_threshold, margin)
        has_charm = self._owned_item_count(data, GOOD_LUCK_CHARM_ID) > 0
        hard_cap = int(cfg.get("rescue_failure_hard_cap") or 50)
        if failure >= hard_cap:
            return has_charm
        if vital <= rest_threshold:
            return energy_val is not None
        if failure >= 35:
            return has_charm or energy_val is not None
        return False

    def _planned_race_is_epithet_critical(self, program_id, preset, data):
        """Return the set of UNMET target epithet names that this program_id
        would progress, or an empty set if dropping the race is safe.

        Used by ``_irregular_training_decision`` to refuse to hijack races
        that are the only path to an active target.  v6.7.4.
        """
        if not program_id or not self.race_planner:
            return set()
        try:
            from career_bot import trackblazer
        except Exception:
            return set()
        base_dir = getattr(self.race_planner, "base_dir", None)
        if not base_dir:
            return set()
        # Resolve effective target epithets from the preset (or its
        # cached profile pick).  Preset wins above profile auto-pick.
        targets = (preset or {}).get("trackblazer_target_epithets") or []
        if not targets:
            targets = (preset or {}).get("trackblazer_profile_target_epithets") or []
        forced = (preset or {}).get("trackblazer_forced_epithets") or []
        all_targets = list(targets) + [f for f in forced if f not in targets]
        if not all_targets:
            return set()
        # Pull race_history out of the injected runner_context.
        history = []
        if isinstance(data, dict):
            history = data.get("race_history") or []
            if not history:
                ctx = data.get("runner_context") or {}
                history = ctx.get("race_results") or ctx.get("race_history") or []
        if not isinstance(history, list):
            history = []
        # Filter to UNMET epithets
        completed = trackblazer._completed_epithets_for_history(
            trackblazer._selected_structured_epithets(base_dir, all_targets) or [],
            history,
        )
        unmet = [name for name in all_targets if name not in completed]
        if not unmet:
            return set()
        critical_names = trackblazer.epithet_critical_race_names(base_dir, unmet, completed_epithets=completed)
        if not critical_names:
            return set()
        try:
            pid = int(program_id or 0)
        except Exception:
            return set()
        info = {}
        info.update((getattr(self.race_planner, "program", {}) or {}).get(pid) or {})
        info.update((getattr(self.race_planner, "official_races", {}) or {}).get(pid) or {})
        name = str(info.get("name") or "").strip()
        if not name or name not in critical_names:
            return set()
        # Find which specific target epithets this program is critical for
        blocked = set()
        from career_bot.trackblazer import _selected_structured_epithets, _matcher_type
        for row in _selected_structured_epithets(base_dir, unmet):
            ep_name = str(row.get("name") or "").strip()
            for matcher in row.get("matchers") or []:
                if not isinstance(matcher, dict):
                    continue
                typ = _matcher_type(matcher)
                if typ in ("winRace", "winRaceTimes") and str(matcher.get("name") or "").strip() == name:
                    blocked.add(ep_name)
                elif typ in ("winAnyOf", "winAtLeast") and name in {str(n).strip() for n in matcher.get("names") or []}:
                    blocked.add(ep_name)
        return blocked

    def _command_main_stat_gain(self, cmd):
        if not cmd:
            return 0
        main_target_by_command = {101: 1, 601: 1, 105: 2, 602: 2, 102: 3, 603: 3, 103: 4, 604: 4, 106: 5, 605: 5}
        main_target = main_target_by_command.get(int(cmd.get("command_id") or 0))
        if main_target:
            for item in (cmd.get("params_inc_dec_info_array") or self._official_training_effect_items(cmd)):
                try:
                    if int(item.get("target_type") or 0) == main_target:
                        return int(item.get("value") or 0)
                except Exception:
                    continue
        return int(self._command_stat_gain(cmd))

    def _irregular_training_decision(self, data, chara, preset, program_id):
        cfg = ((preset or {}).get("mant_config") or {})
        if str((preset or {}).get("extra_race_list_source") or "").strip().lower() == "manual":
            return None
        if not cfg.get("enable_irregular_training", True):
            return None
        turn = int(chara.get("turn") or 0)
        # v1.5: don't hijack a race the SMART SOLVER explicitly planned for this
        # turn.  Android's rule is "if a race is planned, run it" -- the solver
        # already weighed training value when it built the schedule, and letting
        # the irregular-training heuristic override planned races was eroding
        # ~7 races/career (29 executed vs ~36 planned).  Tunable per preset.
        if self.race_planner is not None and not cfg.get("allow_irregular_over_planned", False):
            try:
                # v1.5: if the solver wanted ANY race this turn, run a race -- not
                # just the exact planned program.  This protects the missing-race
                # substitute (a live-list race the solver intended) from being
                # hijacked back into training, and matches android's solver-first
                # rule ("if a race is planned, run it").
                if self.race_planner.wanted_programs(preset, turn):
                    return None
            except Exception:
                pass
        if turn < int(cfg.get("irregular_training_min_turn") or tb_rules.IRREGULAR_TRAINING_MIN_TURN):
            return None
        if turn in SUMMER_CAMP_TURNS or turn >= 73:
            return None
        if int(chara.get("vital") or 0) <= 0:
            return None

        # v6.7.4: never hijack a race that progresses an UNMET target
        # epithet.  This is the primary fix for the race-drop the user
        # reported -- previously a Wit rainbow training would drop Mile
        # Championship (the only path to Ideal Idol) without any check.
        epithet_critical = self._planned_race_is_epithet_critical(program_id, preset, data)
        if epithet_critical:
            self.last_decision_trace = {
                "type": "irregular_training_check",
                "turn": turn,
                "planned_race": self.race_planner.label(program_id) if self.race_planner else str(program_id),
                "chosen": False,
                "reject_reason": "race_progresses_unmet_target_epithet",
                "blocking_epithets": list(epithet_critical),
            }
            return None

        has_charm = self._owned_item_count(data, 10001) > 0
        score_preset = preset
        if has_charm:
            score_preset = dict(preset or {})
            score_cfg = dict((score_preset.get("mant_config") or {}))
            score_cfg.update({"enable_risky_training": True, "risky_training_min_stat_gain": 0, "risky_training_max_failure_chance": 100})
            score_preset["mant_config"] = score_cfg
        best_score, best, _ = self._best_training_candidate(data, chara, score_preset)
        if best is None:
            return None

        threshold = float(cfg.get("irregular_training_score_threshold") or tb_rules.DEFAULT_IRREGULAR_TRAINING_SCORE_THRESHOLD)
        fail_limit = int(cfg.get("irregular_training_failure_limit") or tb_rules.DEFAULT_IRREGULAR_TRAINING_FAILURE_LIMIT)
        _imm = cfg.get("irregular_training_min_main_gain")   # 0-safe: honor an explicit 0
        min_main_gain = int(_imm) if _imm is not None else tb_rules.DEFAULT_IRREGULAR_TRAINING_MIN_MAIN_GAIN
        charm_min_gain = int(cfg.get("irregular_training_charm_min_main_gain") or tb_rules.DEFAULT_IRREGULAR_TRAINING_CHARM_MIN_MAIN_GAIN)
        charm_fail_limit = int(cfg.get("irregular_training_charm_failure_limit") or tb_rules.DEFAULT_IRREGULAR_TRAINING_CHARM_FAILURE_LIMIT)
        failure = int(best.get("failure_rate") or 0)
        main_gain = self._command_main_stat_gain(best)

        trace = {
            "type": "irregular_training_check",
            "turn": turn,
            "planned_race": self.race_planner.label(program_id) if self.race_planner else str(program_id),
            "score": round(float(best_score or 0), 4),
            "threshold": threshold,
            "failure_rate": failure,
            "main_gain": main_gain,
            "min_main_gain": min_main_gain,
            "charm_available": bool(has_charm),
            "chosen": False,
        }

        if best_score < threshold:
            trace["reject_reason"] = "score_below_threshold"
            self.last_decision_trace = trace
            return None
        if main_gain < min_main_gain:
            trace["reject_reason"] = "main_gain_below_floor"
            self.last_decision_trace = trace
            return None
        if failure > fail_limit:
            if not (has_charm and failure <= charm_fail_limit and main_gain >= charm_min_gain):
                trace["reject_reason"] = "failure_too_high_without_safe_charm"
                self.last_decision_trace = trace
                return None
            trace["uses_charm_window"] = True

        payload = self._decision_payload_from_command(best, chara)
        trace["chosen"] = True
        self.last_decision_trace = trace
        reason = (
            f"irregular training beats planned race {trace['planned_race']} "
            f"score={best_score:.3f} main_gain={main_gain} fail={failure}"
        )
        return Decision("command", payload, reason)

    def explain_decision(self, state, preset, decision):
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        turn = int(chara.get("turn") or 0)
        # Reuse the scores already computed during the real decision this turn to
        # avoid a second full re-scoring pass (and to keep the trace consistent
        # with the action that was actually taken).
        if getattr(self, "_scored_turn", None) == turn and self.last_training_scores:
            scored = list(self.last_training_scores)
        else:
            commands = (data.get("home_info") or {}).get("command_info_array") or []
            training = [cmd for cmd in commands if cmd.get("is_enable", 1) and cmd.get("command_type") == 1 and cmd.get("command_id") in TRAINING_COMMANDS]
            scored = []
            for cmd in training:
                score = self._score_command(cmd, data, chara, preset)
                scored.append(self._training_candidate_trace(cmd, score, chara, preset))
            scored.sort(key=lambda row: row["score"], reverse=True)
        trace = {
            "turn": turn,
            "action": decision.action,
            "reason": decision.reason,
            "energy": int(chara.get("vital") or 0),
            "mood": int(chara.get("motivation") or 0),
            "training_candidates": scored[:5],
        }
        if self.event_manager and getattr(self.event_manager, "last_choice_trace", None):
            trace["last_event_choice"] = self.event_manager.last_choice_trace
        self.last_decision_trace = trace
        return trace
