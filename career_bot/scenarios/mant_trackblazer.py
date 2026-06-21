"""Trackblazer decision core for the Trackblazer scenario.

A clean implementation of the reference Trackblazer decision model (a
scoring-shared training scorer plus the Campaign/Trackblazer waterfall), ported
to run on Icarus's exact game-API data.

This is the DEFAULT engine. When active, it FULLY OWNS the per-turn
training/rest/mood/recreation decision — it does NOT use the legacy
``_score_command`` / ``_best_command`` / race-vs-train gates. The legacy
("Classic") engine is left completely intact and is selected via
``mant_config.decision_mode`` in ("legacy", "classic").

Build status (incremental):
  * STEP 1 (this module): training scorer + per-distance targets + milestone
    phasing + the train/rest/mood/recreation/medic + summer/finale/energy
    waterfall. Racing: honors truly-mandatory races and applies the reference
    Trackblazer energy/consecutive-race guards, then defers WHICH-race selection
    to the existing RacePlanner (data-only helper reuse, not legacy decision
    logic).
  * STEP 3: race selection layers the prediction gate on top of the MILP
    solver using the race_entry peek (race_horse_data popularity marks).

All math mirrors the reference training scorer; every constant is inline and
overridable via mant_config so it stays tunable.
"""
from __future__ import annotations

from career_bot.scenarios.base import Decision
from career_bot.trackblazer_guide import is_summer_turn


# --- Trackblazer scoring constants (TrainingScoringConstants, defaults) -------
RATIO_BREAKPOINTS = [15, 30, 45, 60, 75, 90]
RATIO_MULTIPLIERS = [5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 0.3]
PRIORITY_COEFFICIENT = 0.5
# Stat-focus mode (mant_config.stat_focus_mode): "balanced" (default — the
# even-completion curve above) vs "capped" (concentrate priority stats up to the
# cap). Capped FLATTENS the ratio curve (a near-target stat keeps being trained
# instead of being abandoned for whatever is least full), STEEPENS priority
# weighting so the top-priority stats dominate, and trains past the finale buffer
# to the true cap. These two were previously code-only with no override.
RATIO_MULTIPLIERS_CAPPED = [1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9]
PRIORITY_COEFFICIENT_CAPPED = 1.8
LEVEL_BOOST_FACTOR = {1: 0.75, 2: 0.25, 3: 0.10}     # by priority rank (1-based)
MAIN_STAT_THRESHOLD = [30, 30, 30, 30, 15]            # spd/sta/pow/guts/wit
MAIN_STAT_BONUS = 2.0
REL_VALUE_BLUE = 2.5
REL_VALUE_GREEN = 1.0
REL_VALUE_ORANGE = 0.0
REL_DIMINISH = 0.5
REL_EARLY_GAME = 1.3
STAT_WEIGHT_WITH_BARS = 0.6
REL_WEIGHT_WITH_BARS = 0.1
MISC_WEIGHT = 0.3
SKILL_HINT_PER = 10.0
SKILL_HINT_OVERRIDE = 10000.0
RAINBOW_MULT_ENABLED = 2.0
RAINBOW_MULT_DISABLED = 1.5
ANTICIPATORY_MIN_FILL = 50.0
ANTICIPATORY_COEFF = 0.2
ANTICIPATORY_CAP = 0.6
STAT_CAP = 1200
FINALE_STAT_BONUS_PER_RACE = 15

# Per-distance targets [Spd/Sta/Pow/Guts/Wit] — matched to a reference
# run (Oguri_CapP_2026-06-18): 1200/600/1200/600/1200 (Long: Sta 800/
# Guts 500). Override via mant_config.trackblazer_stat_targets (legacy alias:
# android_stat_targets).
DEFAULT_TARGETS = {
    "sprint": [1200, 600, 1200, 600, 1200],
    "mile": [1200, 600, 1200, 600, 1200],
    "medium": [1200, 600, 1200, 600, 1200],
    "long": [1200, 800, 1200, 500, 1200],
}
# Training priority (stat indices). Matched to the reference run:
# Speed, Power, Stamina, Wit, Guts. Read from preset.training_stat_priority when
# present (the user's preset already matches); override via
# trackblazer_stat_priority (legacy alias: android_stat_priority).
DEFAULT_PRIORITY = [0, 2, 1, 4, 3]
STAT_NAME_TO_IDX = {"speed": 0, "stamina": 1, "power": 2, "guts": 3, "wit": 4, "wiz": 4}
GOOD_LUCK_CHARM_ID = 10001

CLASSIC_MILESTONE_PCT = 33
SENIOR_MILESTONE_PCT = 66

# Icarus payload constants (mirror mant.py)
TRAINING_COMMANDS = {101: 0, 105: 1, 102: 2, 103: 3, 106: 4, 601: 0, 602: 1, 603: 2, 604: 3, 605: 4}
STAT_GAIN_TARGET = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}    # params_inc_dec target_type -> stat idx
STAT_KEYS = ["speed", "stamina", "power", "guts", "wiz"]
# Summer camp = the 4 July/August turns each year (Classic 37-40, Senior 61-64).
# Turns 36/60 are LATE JUNE = the Takarazuka Kinen race turn (the solver schedules
# a race there), NOT camp — including them made decide() force-train through it.
SUMMER_CAMP_TURNS = {37, 38, 39, 40, 61, 62, 63, 64}
TRACKBLAZER_PREDICTION_MAX_POPULARITY = 2   # favorite/2nd-favorite ~= "double-star" prediction
# Marquee / set-bonus races that should never be skipped for irregular training
# (the guide's "basically fixed on the schedule" races). Matched on race name.
MARQUEE_RACE_KEYWORDS = (
    "takarazuka", "arima", "japan cup", "tenno sho", "satsuki", "yushun",
    "kikuka", "osaka hai", "oka sho", "oaks", "shuka", "queen elizabeth",
    "nhk mile", "yasuda", "mile championship", "victoria mile",
    "takamatsunomiya", "sprinters", "champions cup",
)
# Energy/HP-restore items (Vita 20/40/65, Royal Kale Juice, Energy Drink MAX/EX).
# Used by the marquee guard to decide whether we can cover a low-energy marquee race.
ENERGY_ITEM_IDS = (2001, 2002, 2003, 2101, 2201, 2202)


def _cfg(preset):
    return ((preset or {}).get("mant_config") or {})


def _acfg(cfg, new_key, old_key, default):
    """Read a config value by its new trackblazer_* key, falling back to the
    legacy android_* key so existing presets keep working."""
    if new_key in cfg:
        return cfg[new_key]
    return cfg.get(old_key, default)


def _is_manual_mode(preset):
    """True when the user is in manual race-selection mode (same signal races.py
    uses). In manual mode the user's picked races are FORCED — exempt from the
    trackblazer prediction gate, irregular-training override, and energy guards."""
    return str((preset or {}).get("extra_race_list_source") or "").strip().lower() == "manual"


def _is_capped_focus(preset):
    """True when stat_focus_mode == "capped" (concentrate priority stats to the
    cap). Default "balanced" keeps the original even-completion behavior."""
    return str(_cfg(preset).get("stat_focus_mode") or "balanced").strip().lower() == "capped"


def _our_horse(race_start_info, chara):
    """Find the player's horse in a race_entry race_horse_data field.

    NPCs have card_id=0/npc_type=0; ours has a real card_id (matches the
    trainee) / npc_type!=0 / viewer_id!=0.
    """  # noqa: race_horse_data is a game-API field name, not user-facing.
    rhd = (race_start_info or {}).get("race_horse_data") or []
    my_card = str((chara or {}).get("card_id") or "")
    if my_card not in ("", "0"):
        for h in rhd:
            if str(h.get("card_id") or "") == my_card:
                return h
    for h in rhd:
        if int(h.get("card_id") or 0) != 0 or int(h.get("npc_type") or 0) != 0 or int(h.get("viewer_id") or 0) != 0:
            return h
    return None


def trackblazer_is_strong_prediction(race_start_info, chara, preset=None):
    """True if our horse's in-game prediction is a strong/double-star contender.

    The Trackblazer engine only enters double-star prediction races; Icarus reads
    the same signal from the race_entry response (``popularity`` rank + the ◎/○/▲
    ``popularity_mark_rank_array``). If the field is missing or our horse can't
    be identified, default True (never block on missing data).
    """
    cfg = _cfg(preset)
    if not _acfg(cfg, "enable_trackblazer_prediction_gate", "enable_android_prediction_gate", True):
        return True
    mine = _our_horse(race_start_info, chara)
    if mine is None:
        return True
    max_pop = int(_acfg(cfg, "trackblazer_prediction_max_popularity",
                        "android_prediction_max_popularity", TRACKBLAZER_PREDICTION_MAX_POPULARITY))
    pop = int(mine.get("popularity") or 99)
    marks = mine.get("popularity_mark_rank_array") or []
    strong_marks = sum(1 for m in marks if int(m or 99) <= 2)
    # Double-star ~= we're a top favorite OR a majority of prediction marks are strong (<=2).
    return pop <= max_pop or (len(marks) > 0 and strong_marks >= max(1, (len(marks) + 1) // 2))


class MantTrackblazerCore:
    """Drop-in Trackblazer decision core. ``ref`` is the owning MantStrategy,
    reused only for neutral data helpers (race_planner accessors, command
    builders, bond map) — never for legacy scoring/gate logic."""

    def __init__(self, ref):
        self.ref = ref

    # ------------------------------------------------------------------ entry
    def decide(self, state, preset):
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        home = data.get("home_info") or {}
        cfg = _cfg(preset)
        manual = _is_manual_mode(preset)   # manual picks are forced -> skip overrides
        commands = [c for c in (home.get("command_info_array") or []) if c.get("is_enable", 1)]
        training = [c for c in commands if c.get("command_type") == 1 and c.get("command_id") in TRAINING_COMMANDS]

        turn = int(chara.get("turn") or 0)
        vital = int(chara.get("vital") or 0)
        motivation = int(chara.get("motivation") or 3)
        summer = (turn in SUMMER_CAMP_TURNS) or is_summer_turn(turn, getattr(self.ref, "trackblazer_guide", {}))
        finale = turn >= 73
        can_safely_train = vital > int(_acfg(cfg, "trackblazer_force_train_energy_floor",
                                             "force_train_energy_floor_android", 20))

        # T0/T1 — the engine trains through summer & finale (banks stats; avoids
        # the consecutive-race energy penalty). Only if a training is available.
        if training and can_safely_train and (summer or finale):
            return self._train(data, chara, preset, training, reason_prefix="summer/finale")

        # Mandatory in-game race always runs (game leaves only the race enabled).
        if self.ref.race_planner:
            forced = self.ref.race_planner.forced_program(state)
            if forced:
                if cfg.get("stop_on_mandatory_races", False):
                    return Decision("idle", {}, f"stopped before mandatory {self.ref.race_planner.label(forced)}")
                return Decision("race", {"program_id": forced, "current_turn": chara["turn"],
                                         "_strategy": self.ref, "_forced_race": True},
                                self.ref.race_planner.label(forced))

        # Runtime consecutive-race streak cap. The solver enforces max_races_in_row
        # in PLANNING, but runtime overrides (marquee guard / missing-race substitute
        # / fallbacks) were pushing streaks to 8-10 races -> almost no training turns
        # -> tanked stats. Enforce it here so OPTIONAL racing never exceeds the user's
        # setting. (Mandatory races above are exempt; manual mode is the user's call.)
        consec = self._consecutive_races(data, turn)
        rest = self.ref._rest_command(commands)
        recreation = self.ref._recreation_command(commands)
        _mc = (preset or {}).get("mant_config") or {}
        _tss = (preset or {}).get("trackblazer_solver_settings") or {}
        max_races_in_row = int(_mc.get("max_races_in_row") or _tss.get("max_races_in_row") or 5)
        streak_ok = manual or consec < max_races_in_row

        # Must-run MARQUEE guard: the fixed set-races (Takarazuka / Arima / Japan
        # Cup / Tenno Sho / Triple Crown / ...) are too valuable to skip. If the
        # game offers one this turn, RACE it — overriding the solver's train- or
        # smaller-race plan. Gated by BOTH the streak cap (never over-race past
        # max_races_in_row) AND energy (vital sufficient OR an energy item owned).
        if not manual and streak_ok and cfg.get("force_marquee_races", True) and self.ref.race_planner:
            mq = self._available_marquee_pid(state, preset)
            if mq:
                try:
                    has_energy_item = any(self.ref._owned_item_count(data, iid) > 0 for iid in ENERGY_ITEM_IDS)
                except Exception:
                    has_energy_item = False
                if vital >= int(cfg.get("marquee_min_vital", 30)) or has_energy_item:
                    # NOT _forced_race: that flag marks a race MANDATORY, so a loss
                    # would stop the career (complete_career_on_failure). A marquee
                    # is optional — run it through the prediction gate so the runner
                    # backs out + re-decides (trains) if our horse isn't a strong
                    # contender, instead of forcing an unwinnable race and aborting.
                    return Decision("race", {"program_id": mq, "current_turn": chara["turn"],
                                             "_strategy": self.ref, "_trackblazer_prediction_gate": True},
                                    self.ref.race_planner.label(mq))

        # Trackblazer energy/consecutive-race guard (shouldAllowConsecutiveRace).
        if not manual and vital <= 10 and consec >= 3 and not cfg.get("ignore_low_energy_racing_block", False):
            return self._as_command(rest or recreation, chara, "trackblazer energy guard: rest (energy<=10, 3+ consecutive races)")

        # STEP 3 (option B): keep Icarus's MILP smart-race solver for scheduling
        # (race_planner.choose -> outcome-risk-aware optimal schedule), then layer
        # the Trackblazer prediction gate at EXECUTION. The runner peeks the chosen
        # race's race_entry marks; if our horse isn't a strong (double-star)
        # contender it backs out + rejects -> choose() re-picks the next planned/
        # available race (or trains). The reference Trackblazer heuristics combine
        # a solver plan with the double-star gate the same way.
        if self.ref.race_planner and training and streak_ok:
            program_id = self.ref.race_planner.choose(state, preset)
            if program_id:
                if not manual and vital <= 1 and consec >= 3 and not cfg.get("ignore_low_energy_racing_block", False):
                    return self._as_command(rest or recreation, chara, "trackblazer hard-block race (energy<=1, 3+ consecutive)")
                # STEP 2: irregular training (Year 2+) — hijack this race turn to
                # train when an exceptional training is available. Skipped in manual
                # mode (user's pick is forced) AND for marquee set-races (Takarazuka,
                # Arima, Japan Cup, etc.) which are "basically fixed on the schedule"
                # per the guide — never train over those.
                try:
                    _rname = str(self.ref.race_planner.label(program_id) or "").lower()
                    marquee = any(k in _rname for k in MARQUEE_RACE_KEYWORDS)
                except Exception:
                    marquee = False
                if not manual and not marquee and _acfg(cfg, "enable_trackblazer_irregular_training",
                                        "enable_android_irregular_training", True) and self._year(turn) > 0:
                    bcmd, _bscore = self._best_training(data, chara, preset, training)
                    if bcmd is not None:
                        bidx = TRAINING_COMMANDS.get(bcmd.get("command_id"), 0)
                        main_gain = self._stat_gains(bcmd)[bidx]
                        thr = int(cfg.get("irregular_training_min_main_gain", 50))
                        if main_gain >= thr:
                            return self._as_command(bcmd, chara, f"trackblazer: irregular training (gain {main_gain} >= {thr}, train over race)")
                # Manual picks are forced -> no prediction gate (the runner only
                # backs out + rejects when _trackblazer_prediction_gate is set).
                race_payload = {"program_id": program_id, "current_turn": chara["turn"], "_strategy": self.ref}
                if not manual:
                    race_payload["_trackblazer_prediction_gate"] = True
                return Decision("race", race_payload, self.ref.race_planner.label(program_id))

        # No training available -> recover.
        if not training:
            medic = self.ref._medic_command(commands)
            if medic and self.ref._has_curable_bad_status(chara, preset) and vital <= 85:
                return self._as_command(medic, chara, "trackblazer: medic (no training, bad status)")
            return self._as_command(rest or recreation, chara, "trackblazer: recover (no training)")

        # Mood recovery (Campaign.shouldRecoverMood: recover when mood < GOOD).
        great = int(cfg.get("great_mood_value", 5))
        good = great - 1                         # GOOD = one below GREAT
        pre_camp = turn in (34, 35, 58, 59)
        want_mood = good if not pre_camp else great
        if recreation and motivation < want_mood and vital >= int(cfg.get("mood_recovery_energy_floor", 50)):
            return self._as_command(recreation, chara, f"trackblazer: recover mood (mot {motivation} < {want_mood})")

        # Energy rest — but first try the energy-item rescue: if a good
        # training exists and an owned Vita/Kale (or charm) can carry it, train
        # instead of resting (the item layer tops up energy on exec).
        _rt = preset.get("rest_threshold")          # 0-safe: honor an explicit 0
        rest_threshold = int(_rt) if _rt is not None else 30
        if vital <= rest_threshold and rest:
            bcmd, bscore = self._best_training(data, chara, preset, training)
            if bcmd is not None:
                failure = int(bcmd.get("failure_rate") or 0)
                try:
                    rescue = self.ref._can_rescue_training(data, chara, preset, bcmd, bscore, vital, failure, rest_threshold)
                except Exception:
                    rescue = False
                if rescue:
                    bidx = TRAINING_COMMANDS.get(bcmd.get("command_id"), 0)
                    return self._as_command(bcmd, chara, f"trackblazer: energy-rescue train {STAT_KEYS[bidx]} (vital {vital}, item top-up)")
            return self._as_command(rest, chara, f"trackblazer: rest (energy {vital} <= {rest_threshold})")

        # Default -> train (the Trackblazer scorer).
        return self._train(data, chara, preset, training, reason_prefix="trackblazer")

    # --------------------------------------------------------------- training
    def _score_trainings(self, data, chara, preset, training):
        """Score every available training (Trackblazer formula) after the
        reference failure admission. Reuses the legacy item-aware
        ``_failure_allowed`` so a Good-Luck Charm relaxes the failure gate exactly
        like the reference heuristics (analyzeTrainings(ignoreFailureChance=
        hasCharm)). Returns (sorted [(score, cmd)], targets, priority)."""
        cfg = _cfg(preset)
        turn = int(chara.get("turn") or 0)
        year = self._year(turn)
        targets = self._phase_targets(chara, preset, year)
        priority = self._priority(preset)
        summer = (turn in SUMMER_CAMP_TURNS) or is_summer_turn(turn, getattr(self.ref, "trackblazer_guide", {}))
        blacklist = set(cfg.get("training_blacklist") or [])
        try:
            has_charm = self.ref._owned_item_count(data, GOOD_LUCK_CHARM_ID) > 0
        except Exception:
            has_charm = False
        scored = []
        for cmd in training:
            idx = TRAINING_COMMANDS.get(cmd.get("command_id"))
            if idx is None or idx in blacklist or STAT_KEYS[idx] in blacklist:
                continue
            try:
                if not self.ref._failure_allowed(cmd, preset, has_charm=has_charm):
                    continue
            except Exception:
                if int(cmd.get("failure_rate") or 0) > int(cfg.get("maximum_failure_chance", 20)):
                    continue
            gains = self._stat_gains(cmd)
            score = self._score_training(cmd, idx, gains, chara, preset, targets, priority, year, summer)
            scored.append((score, cmd))
        scored.sort(key=lambda r: r[0], reverse=True)
        return scored, targets, priority

    def _best_training(self, data, chara, preset, training):
        scored, _, _ = self._score_trainings(data, chara, preset, training)
        if not scored:
            return None, None
        score, cmd = scored[0]
        return cmd, score

    def _train(self, data, chara, preset, training, reason_prefix="trackblazer"):
        scored, targets, priority = self._score_trainings(data, chara, preset, training)
        if not scored:
            commands = [c for c in (data.get("home_info") or {}).get("command_info_array", []) if c.get("is_enable", 1)]
            rest = self.ref._rest_command(commands)
            recreation = self.ref._recreation_command(commands)
            return self._as_command(rest or recreation, chara, "trackblazer: recover (all trainings filtered)")
        self.ref.last_training_scores = [
            {"stat": STAT_KEYS[TRAINING_COMMANDS.get(c.get("command_id"), 0)],
             "score": round(s, 2),
             "gain": self._stat_gains(c)[TRAINING_COMMANDS.get(c.get("command_id"), 0)],
             "failure": int(c.get("failure_rate") or 0)}
            for s, c in scored
        ]
        self.ref.last_decision_trace = {"mode": "trackblazer", "targets": targets, "priority": priority}
        best_score, best = scored[0]
        idx = TRAINING_COMMANDS.get(best.get("command_id"))
        return self._as_command(best, chara, f"{reason_prefix}: train {STAT_KEYS[idx]} (score {best_score:.1f})")

    def _score_training(self, cmd, idx, gains, chara, preset, targets, priority, year, summer):
        """Port of the reference calculateRawTrainingScore."""
        cfg = _cfg(preset)
        cur = int(chara.get(STAT_KEYS[idx]) or 0)
        capped = _is_capped_focus(preset)

        # Junior / pre-debut: bond-rush (Scoring.kt scoreFriendshipTraining).
        if year == 0:
            return self._friendship_score(cmd, chara)

        # Cap / finale-buffer gating. In capped focus mode the ~100-below-cap
        # buffer is removed so priority stats can be trained to the true cap;
        # only the hard STAT_CAP stop remains.
        finale_bonus = self._finale_bonus(int(chara.get("turn") or 0))
        eff_cap = STAT_CAP - 100 - finale_bonus
        rainbow = self.ref._rainbow_partner_count(cmd, chara)
        if cur >= STAT_CAP:
            return 0.0
        potential = cur + (gains[idx] if idx < len(gains) else 0)
        if (not capped) and cfg.get("disable_training_on_maxed_stats", True) and (cur >= eff_cap or potential >= eff_cap):
            if not (rainbow > 0):
                return 0.0

        stat_score = self._stat_efficiency(cmd, gains, chara, targets, priority, summer, capped)
        rel_score = self._relationship_score(cmd, chara, year)
        misc_score = self._misc_score(cmd, cfg)

        total = stat_score * STAT_WEIGHT_WITH_BARS + rel_score * REL_WEIGHT_WITH_BARS + misc_score * MISC_WEIGHT

        # Rainbow multiplier (Year 2+ only).
        if rainbow > 0 and year > 0:
            total *= RAINBOW_MULT_ENABLED if cfg.get("enable_rainbow_training_bonus", True) else RAINBOW_MULT_DISABLED
        elif cfg.get("enable_prioritize_near_max_friendship", True) and year > 0 and rainbow == 0:
            # Anticipatory near-max-friendship.
            contributions = self._near_max_fill(cmd, chara)
            if contributions > 0:
                total *= 1.0 + min(ANTICIPATORY_CAP, ANTICIPATORY_COEFF * contributions)
        return max(0.0, total)

    def _stat_efficiency(self, cmd, gains, chara, targets, priority, summer, capped=False):
        # Capped focus flattens the completion curve (so a near-target priority
        # stat isn't abandoned) and steepens priority weighting.
        ratio_mults = RATIO_MULTIPLIERS_CAPPED if capped else RATIO_MULTIPLIERS
        priority_coeff = PRIORITY_COEFFICIENT_CAPPED if capped else PRIORITY_COEFFICIENT
        main_idx = TRAINING_COMMANDS.get(cmd.get("command_id"))
        level = self.ref._training_level(cmd)
        score = 0.0
        for s in range(5):
            gain = gains[s] if s < len(gains) else 0
            tgt = targets[s] if s < len(targets) else 0
            if gain <= 0 or tgt <= 0:
                continue
            completion = (int(chara.get(STAT_KEYS[s]) or 0) / tgt) * 100.0
            ratio_mult = ratio_mults[-1]
            for i, bp in enumerate(RATIO_BREAKPOINTS):
                if completion < bp:
                    ratio_mult = ratio_mults[i]
                    break
            if s in priority:
                pos = priority.index(s)
                priority_mult = 1.0 + priority_coeff * (len(priority) - pos)
            else:
                priority_mult = 1.0
            level_mult = 1.0
            if s == main_idx and s in priority and level >= 2:
                rank = priority.index(s) + 1
                pf = LEVEL_BOOST_FACTOR.get(rank, 0.0)
                level_mult = 1.0 + pf * ((level - 1) / 4.0)
            main_bonus = 2.0 if (s == main_idx and gain >= MAIN_STAT_THRESHOLD[s]) else 1.0
            score += gain * ratio_mult * priority_mult * level_mult * main_bonus
        return score

    def _relationship_score(self, cmd, chara, year):
        bonds = self.ref._bond_map(chara)
        partners = cmd.get("training_partner_array") or []
        if not partners:
            return 0.0
        score = 0.0
        max_score = 0.0
        early = REL_EARLY_GAME if year == 0 else 1.0
        for pid in partners:
            try:
                bond = int(bonds.get(int(pid), 0) or 0)
            except Exception:
                continue
            base = REL_VALUE_BLUE if bond >= 80 else (REL_VALUE_GREEN if bond >= 60 else REL_VALUE_ORANGE)
            if base > 0:
                fill = bond / 100.0
                score += base * (1.0 - fill * REL_DIMINISH) * early
                max_score += REL_VALUE_BLUE * REL_EARLY_GAME
        return (score / max_score * 100.0) if max_score > 0 else 0.0

    def _misc_score(self, cmd, cfg):
        hints = len(cmd.get("tips_event_partner_array") or [])
        base = 50.0 + SKILL_HINT_PER * hints
        if cfg.get("enable_prioritize_skill_hints", False) and hints > 0:
            return SKILL_HINT_OVERRIDE + base
        return max(0.0, min(100.0, base))

    def _friendship_score(self, cmd, chara):
        bonds = self.ref._bond_map(chara)
        partners = cmd.get("training_partner_array") or []
        if not partners:
            return -1e9
        score = 0.0
        for pid in partners:
            try:
                bond = int(bonds.get(int(pid), 0) or 0)
            except Exception:
                continue
            score += REL_VALUE_BLUE if bond >= 80 else (REL_VALUE_GREEN if bond >= 60 else REL_VALUE_ORANGE)
        return score

    def _near_max_fill(self, cmd, chara):
        bonds = self.ref._bond_map(chara)
        total = 0.0
        for pid in cmd.get("training_partner_array") or []:
            try:
                bond = int(bonds.get(int(pid), 0) or 0)
            except Exception:
                continue
            if bond >= 60 and bond < 80 and (bond / 100.0 * 100.0) > ANTICIPATORY_MIN_FILL:
                total += bond / 100.0
        return total

    # ------------------------------------------------------------ helpers
    def _stat_gains(self, cmd):
        gains = [0, 0, 0, 0, 0]
        for item in cmd.get("params_inc_dec_info_array") or []:
            try:
                tt = int(item.get("target_type") or 0)
                if tt in STAT_GAIN_TARGET:
                    gains[STAT_GAIN_TARGET[tt]] += int(item.get("value") or 0)
            except Exception:
                continue
        return gains

    def _year(self, turn):
        if turn <= 24:
            return 0
        if turn <= 48:
            return 1
        return 2

    def _finale_bonus(self, turn):
        remaining = max(0, 75 - max(turn, 72))
        return remaining * FINALE_STAT_BONUS_PER_RACE

    def _priority(self, preset):
        # explicit index override
        p = _acfg(_cfg(preset), "trackblazer_stat_priority", "android_stat_priority", None)
        if isinstance(p, list) and p and all(isinstance(x, int) for x in p):
            return p
        # else read the preset's stat-name priority (matches the engine setting)
        names = (preset or {}).get("training_stat_priority")
        if isinstance(names, list) and names:
            idxs = [STAT_NAME_TO_IDX[str(n).lower()] for n in names if str(n).lower() in STAT_NAME_TO_IDX]
            if len(idxs) == 5:
                return idxs
        return list(DEFAULT_PRIORITY)

    def _preferred_distance(self, chara, preset):
        cfg = _cfg(preset)
        pref = cfg.get("preferred_distances") or []
        if pref:
            d = str(pref[0]).lower()
            if d in DEFAULT_TARGETS:
                return d
        # else: highest aptitude
        apts = {
            "sprint": int(chara.get("proper_distance_short") or 1),
            "mile": int(chara.get("proper_distance_mile") or 1),
            "medium": int(chara.get("proper_distance_middle") or 1),
            "long": int(chara.get("proper_distance_long") or 1),
        }
        return max(apts, key=lambda k: apts[k])

    def _phase_targets(self, chara, preset, year):
        cfg = _cfg(preset)
        dist = self._preferred_distance(chara, preset)
        # User per-distance targets take PRIORITY over the hard-coded defaults.
        # Priority: explicit trackblazer_stat_targets override (legacy alias:
        # android_stat_targets) > the UI's stat_targets_by_distance (same
        # sprint/mile/medium/long keys, in [Spd,Sta,Pow,Guts,Wit] order) >
        # DEFAULT_TARGETS. (Previously only android_stat_targets was read — a key
        # the UI never writes — so the user's stat targets were silently ignored.)
        override = (_acfg(cfg, "trackblazer_stat_targets", "android_stat_targets", {}) or {}).get(dist)
        if not (isinstance(override, list) and len(override) == 5):
            override = (cfg.get("stat_targets_by_distance") or {}).get(dist)
        base = list(override) if isinstance(override, list) and len(override) == 5 else list(DEFAULT_TARGETS[dist])
        if cfg.get("disable_stat_targets", False):
            return [STAT_CAP] * 5
        if year == 2:
            return base
        pct = (cfg.get("classic_milestone_pct", CLASSIC_MILESTONE_PCT) if year == 0
               else cfg.get("senior_milestone_pct", SENIOR_MILESTONE_PCT)) / 100.0
        return [max(1, int(t * pct)) for t in base]

    def _consecutive_races(self, data, turn):
        try:
            return int(self.ref._recent_race_chain_count(data, turn))
        except Exception:
            return 0

    def _available_marquee_pid(self, state, preset):
        """Highest-fan marquee/set race the game is OFFERING this turn (aptitude-
        passing, not already rejected), else 0. Matches by race name so program_id
        'permission variants' don't matter."""
        rp = self.ref.race_planner
        if not rp:
            return 0
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        rca = data.get("race_condition_array") or []
        turn = int(chara.get("turn") or 0)
        try:
            floor = self.ref._solver_aptitude_floor(preset)
        except Exception:
            floor = 6
        best, best_fans = 0, -1
        for item in rca:
            try:
                pid = int(item.get("program_id") or 0)
            except Exception:
                continue
            if not pid or (turn, pid) in rp.rejected:
                continue
            name = str(rp.label(pid) or "").lower()
            if not any(k in name for k in MARQUEE_RACE_KEYWORDS):
                continue
            try:
                if not rp.check_aptitude(chara, pid, floor):
                    continue
            except Exception:
                pass
            fans = int((rp.program.get(pid) or {}).get("fans") or 0)
            if fans > best_fans:
                best, best_fans = pid, fans
        return best

    def _as_command(self, command, chara, reason):
        if not command:
            return Decision("idle", {}, reason + " (no command available)")
        return Decision("command", self.ref._decision_payload_from_command(command, chara), reason)
