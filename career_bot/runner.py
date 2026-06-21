import gzip
import base64
import msgpack
import threading
import time
import json
import os
import random
import math
import uuid
from datetime import datetime
from pathlib import Path

from career_bot.scenarios.mant import MantStrategy
from career_bot.races import RacePlanner
from career_bot.skills import SkillBuyer
from career_bot.items import MantItemManager, ITEM_NAMES, SHOP_ITEM_COSTS, DISPLAY_TO_ID, display_to_slug


from career_bot.report import new_report, add_event, add_api_call, add_decision, finish_report, write_report, set_error
from career_bot.delay import dna_sleep, dna_gauss
from career_bot.discord_logger import DiscordCareerLogger
from career_bot.race_intelligence import record_race_outcome
from career_bot.running_style import resolve_running_style_for_race
from career_bot import trackblazer
from career_bot import style_adaptation
from career_bot import event_outcomes as event_kb


STRATEGIES = {
    4: MantStrategy,
}


def runtime_output_root(base_dir):
    override = os.environ.get("UMA_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve()

    base = Path(base_dir).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate / "uma_runtime"
    return base.parent / "uma_runtime"

TRAINING_LABELS = {
    101: "Speed",
    102: "Power",
    103: "Guts",
    105: "Stamina",
    106: "Wit",
    601: "Speed",
    602: "Stamina",
    603: "Power",
    604: "Guts",
    605: "Wit",
}


class CareerRunner:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.report = None
        self.lock = threading.Lock()
        self.thread = None
        self.stop_requested = False
        self.pause_requested = False
        self.burn_clocks = False
        self.carats_enabled = False          # spend carats on retries once clocks run out
        self.max_clocks_per_career = 0       # 0 = unlimited; per-career paid-clock budget
        self.loop_index = 1
        self.loop_target = 1
        self.race_planner = RacePlanner(base_dir)
        self.skill_buyer = SkillBuyer(base_dir)
        self.item_manager = MantItemManager()
        self.discord_logger = None
        self.metrics = self._load_lifetime_metrics()
        self.current_run_recorded = False
        # v7.6.2: native event-outcome capture. SweepyCL already receives
        # chara_info before/after every event choice, so it records outcomes
        # from its own runs into the KB — no Frida/dumper needed. main.py sets
        # this from settings before each start; default on.
        self.native_event_capture = True
        # #6 — goal-aware training lookahead (pace-to-target urgency in the
        # goal-aware scorer). main.py sets this from settings before each start;
        # default OFF so nothing changes unless the user opts in.
        self.goal_lookahead = False
        self.status = {
            "running": False,
            "paused": False,
            "loop_index": 1,
            "loop_target": 1,
            "preset": "",
            "scenario_id": 0,
            "turn": 0,
            "steps": 0,
            "last_action": "",
            "last_error": "",
            "finished": False,
            "skills_bought": 0,
            "items_bought": 0,
            "items_used": 0,
            "clocks_used": 0,
            "log": [],
            "action_history": [],
            "warnings": [],
            "last_seen_at": 0,
            "stale_seconds": 0,
            "same_turn_count": 0,
            "run_id": "",
            "decision_trace": {},
            "last_style_adaptation": {},
        }

    def _metrics_path(self):
        root = runtime_output_root(self.base_dir)
        root.mkdir(parents=True, exist_ok=True)
        return root / "bot_metrics.json"

    def _load_lifetime_metrics(self):
        """Session metrics reset every time python main.py starts.

        Earlier builds loaded bot_metrics.json as a lifetime counter. For the dashboard
        this felt sticky after restarts, so the file is now only a live/session export.
        Closing the PowerShell window and starting python main.py again resets these.
        """
        now = time.time()
        defaults = {
            "first_started_at": now,
            "session_started_at": now,
            "total_runtime_seconds": 0,
            "total_fans_gained": 0,
            "careers_completed": 0,
            "runs_started": 0,
            "last_updated_at": now,
            "session_only": True,
        }
        try:
            # Keep a JSON file for diagnostics, but always overwrite it for this process.
            path = self._metrics_path()
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception:
            pass
        return defaults

    def _save_lifetime_metrics(self):
        try:
            self.metrics["last_updated_at"] = time.time()
            path = self._metrics_path()
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(self.metrics, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception as exc:
            if random.random() < 0.05:
                print(f"metrics save failed: {exc}", flush=True)

    def _lifetime_snapshot(self):
        metrics = dict(self.metrics or {})
        try:
            started = float(metrics.get("first_started_at") or metrics.get("session_started_at") or time.time())
        except Exception:
            started = time.time()
        # Dashboard runtime is process/session uptime, not persistent lifetime and not
        # only career runtime. This resets when python main.py exits.
        total_runtime = max(0, time.time() - started)
        total_fans = int(metrics.get("total_fans_gained") or 0) + int(self.status.get("fans_gained") or 0)
        metrics["total_runtime_seconds_live"] = int(total_runtime)
        metrics["total_runtime_seconds"] = int(total_runtime)
        metrics["total_fans_gained_live"] = int(total_fans)
        metrics["fans_per_hour_live"] = int(total_fans / max(1.0 / 3600.0, total_runtime / 3600.0)) if total_runtime else 0
        return metrics

    def _walk_dicts(self, value, max_depth=7):
        """Yield nested dictionaries from API payloads without assuming a fixed finish schema."""
        seen = set()
        def walk(obj, depth):
            if depth < 0:
                return
            oid = id(obj)
            if oid in seen:
                return
            if isinstance(obj, dict):
                seen.add(oid)
                yield obj
                for child in obj.values():
                    yield from walk(child, depth - 1)
            elif isinstance(obj, list):
                seen.add(oid)
                for child in obj:
                    yield from walk(child, depth - 1)
        yield from walk(value, max_depth)

    def _extract_final_chara_payload(self, finish_state, fallback_chara=None):
        """Build the richest final trainee snapshot available from finish payloads.

        The game has used several finish payload shapes across versions/regions.
        Some responses expose `chara_info`, while others place rating, race count,
        win count, factors, skills, or win saddle ids deeper in result objects.  This
        helper conservatively merges known final-career keys so Career History can
        show rating/races/wins when the server provides them.

        v6.7.6 fix: the finish response's ``single_mode_finish_common`` carries a
        ``trained_chara`` LIST of all the user's saved trainees plus a top-level
        ``trained_chara_id`` field naming WHICH entry in that list represents the
        career that just finished.  Earlier versions of this code picked up factor
        data from whatever entry appeared first, which meant the Career History
        "Sparks" panel showed the same inherited factors from a parent slot every
        career instead of the just-earned random sparks from this run.  Now we
        explicitly resolve the matching entry by id before merging.
        """
        merged = dict(fallback_chara or {})
        payload = finish_state if isinstance(finish_state, dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        direct_names = (
            "chara_info", "single_mode_chara", "single_mode_chara_light",
            "trained_chara", "result_chara", "trained_chara_info",
            "trained_chara_result", "single_mode_chara_result",
        )
        candidates = []
        for name in direct_names:
            value = (data or {}).get(name) if isinstance(data, dict) else None
            if isinstance(value, dict):
                candidates.append(value)

        # v6.7.10: resolve the just-finished trainee deterministically from
        # ``single_mode_finish_common.trained_chara``.  This list contains the
        # user's ENTIRE roster (~121 entries, each with inherited factor arrays
        # and nested ``succession_chara_array`` ancestors).  The finished career
        # is identified by matching the running career's trainee id; if no id
        # matches we fall back to ``trained_chara[0]`` (API convention puts the
        # finished trainee first).  We never use a longest-array heuristic.
        finished_entry = self._resolve_finished_trained_chara(data, fallback_chara)
        if isinstance(finished_entry, dict):
            candidates.insert(0, finished_entry)  # priority over the catch-all

        stat_keys = {"speed", "stamina", "power", "guts", "wiz", "wit"}
        final_keys = {
            "evaluation_point", "evaluation_rank", "rank_score", "rating", "evaluation",
            "chara_rank_score", "trained_chara_evaluation_point", "career_rank",
            "race_count", "race_num", "win_count", "win_num", "fans", "fan_count",
            "factor_id_array", "factor_info_array", "skill_array", "skill_tips_array",
            "win_saddle_id_array", "card_id", "chara_id", "title", "chara_title",
        }
        for row in self._walk_dicts(data):
            keys = set(row.keys())
            if keys & final_keys or len(keys & stat_keys) >= 3:
                candidates.append(row)

        # Prefer specific/nested result objects after the initial fallback so more
        # complete finish payloads can overwrite stale home-screen values.
        for row in candidates:
            for key, value in row.items():
                if value is None or value == "":
                    continue
                if key not in merged or merged.get(key) in (None, "", 0, [], {}):
                    merged[key] = value
                elif key in final_keys or key in stat_keys:
                    # Final response values are usually more authoritative than
                    # the pre-finish home snapshot for these exact keys.
                    merged[key] = value

        # v6.7.10: the trainee's OWN earned sparks live in the finished entry's
        # ``factor_id_array``/``factor_info_array``.  Read them from the
        # deterministically resolved finished entry ONLY (excluding inherited
        # ancestor ``succession_chara_array`` subtrees), not from a
        # longest-array-anywhere heuristic that grabbed roster/ancestor sets.
        inherited_ids = list((fallback_chara or {}).get("factor_id_array") or [])
        # v1.5: pass the full finish ``data`` so the extractor can read the
        # newly-earned spark fields (single_mode_finish_common.gained_factor_info_array
        # / earned_factor_id_array), falling back to the resolved entry's array
        # minus inherited. Reading the roster entry's factor_id_array directly was
        # the inherited (identical-every-career) set.
        gained_ids, gained_info, factor_debug = self._extract_gained_factors(
            data, inherited_ids
        )
        if gained_ids:
            merged["factor_id_array"] = gained_ids
            if gained_info:
                merged["factor_info_array"] = gained_info
        if factor_debug:
            merged["_finish_factor_debug"] = factor_debug
        return merged

    def _resolve_finished_trained_chara(self, data, fallback_chara=None):
        """Return the just-finished trainee's entry from the finish payload's
        ``single_mode_finish_common.trained_chara`` list, or ``None``.

        Selection is deterministic:
          1. Prefer the entry whose ``card_id``/``chara_id`` matches the running
             career's trainee (taken from ``fallback_chara`` -- the live
             ``chara_info`` of the career that just finished).
          2. Otherwise fall back to ``trained_chara[0]`` -- the API convention
             places the finished trainee first.

        Never uses a longest-array heuristic; never inspects roster siblings or
        ancestor ``succession_chara_array`` subtrees.
        """
        try:
            common = data.get("single_mode_finish_common") if isinstance(data, dict) else None
            if not isinstance(common, dict):
                return None
            tc_list = common.get("trained_chara")
            if not isinstance(tc_list, list) or not tc_list:
                return None

            fb = fallback_chara or {}
            wanted = set()
            for key in ("card_id", "chara_id"):
                val = fb.get(key)
                if isinstance(val, (int, float)) and int(val) > 0:
                    wanted.add(int(val))
            # The top-level ``trained_chara_id`` is sometimes 0/unreliable, so we
            # treat it only as an additional hint, never as the sole authority.
            tcid = common.get("trained_chara_id")
            if isinstance(tcid, (int, float)) and int(tcid) > 0:
                wanted.add(int(tcid))

            if wanted:
                for entry in tc_list:
                    if not isinstance(entry, dict):
                        continue
                    for id_key in ("card_id", "chara_id", "trained_chara_id", "id"):
                        ev = entry.get(id_key)
                        if isinstance(ev, (int, float)) and int(ev) in wanted:
                            return entry

            # Fall back to the first entry (finished trainee comes first).
            for entry in tc_list:
                if isinstance(entry, dict):
                    return entry
        except Exception:
            pass
        return None

    def _extract_gained_factors(self, finish_data, inherited_ids):
        """Return the just-finished trainee's NEWLY-EARNED factor (spark) ids.

        v1.5 fix: ``single_mode_finish_common.trained_chara[*].factor_id_array``
        is the trainee's INHERITED parent-spark set -- identical every career for
        a fixed parent pair, which is why Career History showed the same sparks
        every run.  The sparks EARNED this run live in sibling fields of
        ``single_mode_finish_common``:
          * ``gained_factor_info_array`` -- list of ``{factor_id: N, ...}`` dicts
          * ``earned_factor_id_array``   -- plain int id list
        We read those FIRST.  Only if neither is present do we fall back to the
        resolved trainee entry's ``factor_id_array`` MINUS the inherited set, so a
        stale roster slot can never produce the identical-every-career artifact.

        ``finish_data`` may be the full finish ``data`` dict (containing
        ``single_mode_finish_common``) or that common block directly.  Returns
        ``(ids, info_array_or_None, debug_dict)``; ``debug_dict`` is stamped onto
        the summary as ``_finish_factor_debug`` so the populated field can be
        confirmed from a live run.
        """
        inherited = set(int(x) for x in (inherited_ids or []) if isinstance(x, (int, float)))
        seen = {}

        def _ids_from(value):
            if isinstance(value, list):
                if value and all(isinstance(v, (int, float)) for v in value):
                    return [int(v) for v in value]
                # list of {factor_id: N} dicts
                return [int(v.get("factor_id")) for v in value
                        if isinstance(v, dict) and isinstance(v.get("factor_id"), (int, float))]
            return []

        if not isinstance(finish_data, dict):
            return [], None, None
        common = finish_data.get("single_mode_finish_common")
        container = common if isinstance(common, dict) else finish_data

        # 1. PREFERRED: the sparks actually earned this career.
        info = None
        gfi = container.get("gained_factor_info_array")
        earned = _ids_from(gfi) if isinstance(gfi, list) else []
        if earned:
            seen["gained_factor_info_array"] = earned[:8]
            if gfi and isinstance(gfi[0], dict):
                info = gfi
        if not earned:
            efa = container.get("earned_factor_id_array")
            earned = _ids_from(efa)
            if earned:
                seen["earned_factor_id_array"] = earned[:8]
        if earned:
            return earned, info, {"inherited_factor_ids": sorted(inherited), "factor_arrays_seen": seen}

        # 2. FALLBACK: resolved trainee entry's own array, minus inherited sparks.
        entry = None
        if self is not None:
            try:
                resolved = self._resolve_finished_trained_chara(finish_data, None)
                if isinstance(resolved, dict):
                    entry = resolved
            except Exception:
                entry = None
        if entry is None:
            tc = container.get("trained_chara")
            if isinstance(tc, list) and tc and isinstance(tc[0], dict):
                entry = tc[0]
        if isinstance(entry, dict):
            raw_ids = _ids_from(entry.get("factor_id_array"))
            new_ids = [i for i in raw_ids if i not in inherited]
            if new_ids:
                seen["trained_chara.factor_id_array(minus inherited)"] = new_ids[:8]
                info_val = entry.get("factor_info_array")
                if isinstance(info_val, list) and info_val and isinstance(info_val[0], dict):
                    info = [f for f in info_val
                            if not (isinstance(f, dict) and int(f.get("factor_id") or 0) in inherited)] or info_val
                return new_ids, info, {"inherited_factor_ids": sorted(inherited), "factor_arrays_seen": seen}

        debug = {"inherited_factor_ids": sorted(inherited), "factor_arrays_seen": seen} if seen else None
        return [], None, debug

    def _compact_final_chara(self, chara=None):
        """Small in-memory career summary for the dashboard history modal.

        This intentionally stays in runner status only. The backend stores the
        session list in RAM, so closing python main.py clears the history.
        """
        chara = chara or {}
        def pick(*names, default=0):
            for name in names:
                value = chara.get(name)
                if value is not None:
                    return value
            return default

        stats = {
            "speed": int(pick("speed", "speed_value", default=0) or 0),
            "stamina": int(pick("stamina", "stamina_value", default=0) or 0),
            "power": int(pick("power", "pow", "power_value", default=0) or 0),
            "guts": int(pick("guts", "guts_value", default=0) or 0),
            "wit": int(pick("wiz", "wit", "wisdom", "intelligence", default=0) or 0),
            "skill_point": int(pick("skill_point", "skill_points", default=0) or 0),
        }
        aptitudes = {
            "track": {
                "turf": pick("proper_ground_turf", default=""),
                "dirt": pick("proper_ground_dirt", default=""),
            },
            "distance": {
                "sprint": pick("proper_distance_short", default=""),
                "mile": pick("proper_distance_mile", default=""),
                "medium": pick("proper_distance_middle", default=""),
                "long": pick("proper_distance_long", default=""),
            },
            "style": {
                "front": pick("proper_running_style_nige", default=""),
                "pace": pick("proper_running_style_senko", default=""),
                "late": pick("proper_running_style_sashi", default=""),
                "end": pick("proper_running_style_oikomi", default=""),
            },
        }
        return {
            "card_id": pick("card_id", "chara_id", default=0),
            "fans": int(pick("fans", "fan_count", "total_fan_count", default=self.status.get("fans_current", 0)) or 0),
            "rating": pick("evaluation_point", "rank_score", "rating", "evaluation", "chara_rank_score", "trained_chara_evaluation_point", "assessment_point", default=""),
            "rank": pick("evaluation_rank", "rank", "career_rank", "chara_rank", default=""),
            "stats": stats,
            "aptitudes": aptitudes,
            "skill_array": list(chara.get("skill_array") or []),
            "skill_tips_array": list(chara.get("skill_tips_array") or []),
            "factor_id_array": list(chara.get("factor_id_array") or []),
            "factor_info_array": list(chara.get("factor_info_array") or []),
            "win_saddle_id_array": list(chara.get("win_saddle_id_array") or []),
            "title": pick("chara_title", "title", "card_name", default=""),
            "race_count": pick("race_count", "race_num", "race_entry_count", "total_race_count", default=0),
            "win_count": pick("win_count", "win_num", "race_win_count", "total_win_count", default=0),
            # v6.8: diagnostic for the per-run sparks fix -- lists every
            # factor-bearing key found in the finish payload so the exact
            # earned-spark field can be confirmed from one finished career.
            "_finish_factor_debug": chara.get("_finish_factor_debug"),
        }

    def _record_completed_run_metrics(self, chara=None):
        if self.current_run_recorded:
            return
        try:
            fans_now = int((chara or {}).get("fans") or self.status.get("fans_current") or 0)
            fans_start = int(self.status.get("fans_start") or fans_now or 0)
            gained = max(0, fans_now - fans_start)
            runtime_seconds = max(0, time.time() - float(self.status.get("started_at") or time.time()))
            self.metrics["total_fans_gained"] = int(self.metrics.get("total_fans_gained") or 0) + int(gained)
            self.metrics["total_runtime_seconds"] = int(float(self.metrics.get("total_runtime_seconds") or 0) + runtime_seconds)
            self.metrics["careers_completed"] = int(self.metrics.get("careers_completed") or 0) + 1
            self.metrics["last_run_fans_gained"] = int(gained)
            self.metrics["last_run_runtime_seconds"] = int(runtime_seconds)
            self.metrics["last_completed_at"] = time.time()
            self.current_run_recorded = True
            self._save_lifetime_metrics()
        except Exception as exc:
            print(f"metrics complete failed: {exc}", flush=True)

    def _record_stopped_run_runtime(self):
        if self.current_run_recorded:
            return
        try:
            runtime_seconds = max(0, time.time() - float(self.status.get("started_at") or time.time()))
            self.metrics["total_runtime_seconds"] = int(float(self.metrics.get("total_runtime_seconds") or 0) + runtime_seconds)
            self.current_run_recorded = True
            self._save_lifetime_metrics()
        except Exception:
            pass

    def _init_debug_log(self, preset=None, scenario_id=4):
        self.report = new_report(preset, scenario_id)

    def _debug(self, event, state=None, data=None):
        row = {
            "event": event,
        }
        if state:
            d = state.get("data") or {}
            chara = d.get("chara_info") or {}
            free = d.get("free_data_set") or {}
            row["turn"] = int(chara.get("turn") or 0)
            row["skill_point"] = int(chara.get("skill_point") or 0)
            row["mant_coin"] = int(free.get("coin_num") if free.get("coin_num") is not None else free.get("gained_coin_num") or 0)
            row["motivation"] = int(chara.get("motivation") or 0)
            row["stats"] = self._turn_stats(chara)
        if data:
            row.update(data)
        if self.report:
            add_event(self.report, row)

    def start(self, client, preset, initial_result, max_steps=2500, burn_clocks=False, dev_mode=False,
              carats_enabled=False, max_clocks_per_career=0):
        with self.lock:
            if self.status["running"]:
                raise RuntimeError("Career runner already active")
            scenario_id = int(preset.get("scenario_id") or 4)
            strategy_cls = STRATEGIES.get(scenario_id)
            if not strategy_cls:
                raise RuntimeError(f"No runner for scenario {scenario_id}")
            self.stop_requested = False
            self.pause_requested = False
            self.burn_clocks = burn_clocks
            self.carats_enabled = bool(carats_enabled)
            self.max_clocks_per_career = int(max_clocks_per_career or 0)
            self.dev_mode = dev_mode
            self.current_run_recorded = False
            self.metrics["runs_started"] = int(self.metrics.get("runs_started") or 0) + 1
            self._save_lifetime_metrics()
            self.race_planner = RacePlanner(self.base_dir)
            self.skill_buyer = SkillBuyer(self.base_dir)
            self.item_manager = MantItemManager()
            self.status = {
                "running": True,
                "paused": False,
                "loop_index": int(getattr(self, "loop_index", 1) or 1),
                "loop_target": int(getattr(self, "loop_target", 1) or 1),
                "preset": preset.get("name", ""),
                "scenario_id": scenario_id,
                "turn": 0,
                "steps": 0,
                "last_action": "started",
                "last_error": "",
                "finished": False,
                "skills_bought": 0,
                "items_bought": 0,
                "items_used": 0,
                "clocks_used": 0,
                "carat_retries_used": 0,
                "burn_clocks_requested": bool(burn_clocks),
                "clock_retry_policy": {
                    "user_enabled": bool(burn_clocks),
                    "enabled": bool(burn_clocks),
                    "source": "career_start",
                },
                "careers_completed": 0,
                "fans_start": 0,
                "fans_current": 0,
                "fans_gained": 0,
                "fans_per_hour": 0,
                "started_at": time.time(),
                "recoveries": 0,
                "last_seen_at": time.time(),
                "stale_seconds": 0,
                "same_turn_count": 0,
                "last_state_snapshot": "",
                "run_id": time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8],
                "warnings": [],
                "log": [],
                "action_history": [],
                "race_results": [],
                "decision_trace": {},
                "last_style_adaptation": {},
                "lifetime": self._lifetime_snapshot(),
            }
            self.report = new_report(preset, scenario_id)
            try:
                _mc_start = (preset or {}).get("mant_config") or {}
                self.report["runtime_settings"] = {
                    "burn_clocks": bool(burn_clocks),
                    "clock_retry_policy": {
                        "user_enabled": bool(burn_clocks),
                        "enabled": bool(burn_clocks),
                        "source": "career_start",
                    },
                    # Record the active engine + stat-focus so logs are unambiguous
                    # about which mode produced the result (A/B clarity).
                    "decision_mode": str(_mc_start.get("decision_mode") or "trackblazer"),
                    "stat_focus_mode": str(_mc_start.get("stat_focus_mode") or "balanced"),
                    "run_id": self.status.get("run_id"),
                    "loop_index": self.status.get("loop_index"),
                    "loop_target": self.status.get("loop_target"),
                }
            except Exception:
                pass
            tp_reasoning = []
            try:
                tp_reasoning = list((initial_result or {}).get("_tp_restore_reasoning") or [])
                self.status["tp_restore_reasoning"] = tp_reasoning
                if self.report and tp_reasoning:
                    self.report.setdefault("decision_reasoning", []).append({
                        "turn": 0,
                        "action": "tp_restore",
                        "reason": "TP restore resource selection",
                        "reasoning": tp_reasoning,
                    })
            except Exception:
                tp_reasoning = []
            self.discord_logger = DiscordCareerLogger(self.base_dir)
            self.discord_logger.start_career(self.status.get("run_id", ""), preset=preset, status={
                "preset": self.status.get("preset"),
                "scenario_id": self.status.get("scenario_id"),
                "started_at": self.status.get("started_at"),
            })
            if client:
                client.report = self.report
                def _on_api_log(direction, ep, data, req_id=None):
                    if self.report:
                        import time
                        add_api_call(self.report, {
                            "ts": time.time(),
                            "direction": direction,
                            "endpoint": ep,
                            "data": data,
                            "req_id": req_id,
                            "turn": self.status.get("turn", 0)
                        })
                client.on_api_log = _on_api_log
            self._log_locked("started", 0, f"preset {preset.get('name', '')} (burn_clocks={burn_clocks})")
            for reason in tp_reasoning:
                self._log_locked("tp_restore_reason", 0, reason)
            self.thread = threading.Thread(target=self._run, args=(client, preset, initial_result, strategy_cls(self.race_planner), max_steps), daemon=True)
            self.thread.start()

    def stop(self):
        with self.lock:
            self.stop_requested = True
            self.pause_requested = False
            self.status["paused"] = False

    def pause(self):
        """Pause at safe runner checkpoints without ending the active career."""
        with self.lock:
            if self.status.get("running"):
                self.pause_requested = True
                self.status["paused"] = True
                self._log_locked("pause", self.status.get("turn", 0), "pause requested; waiting at the next safe point")

    def resume(self):
        with self.lock:
            self.pause_requested = False
            if self.status.get("paused"):
                self._log_locked("resume", self.status.get("turn", 0), "runner resumed")
            self.status["paused"] = False

    def set_loop_info(self, index=1, target=1):
        with self.lock:
            self.loop_index = max(1, int(index or 1))
            self.loop_target = max(0, int(target or 0))
            self.status["loop_index"] = self.loop_index
            self.status["loop_target"] = self.loop_target

    def _wait_if_paused(self):
        reported = False
        while True:
            with self.lock:
                paused = bool(self.pause_requested)
                stopped = bool(self.stop_requested)
                if paused:
                    self.status["paused"] = True
                    self.status["last_action"] = "paused"
                    self.status["last_seen_at"] = time.time()
                    if not reported:
                        self._log_locked("paused", self.status.get("turn", 0), "runner paused at a safe checkpoint")
                        reported = True
                else:
                    if self.status.get("paused"):
                        self.status["paused"] = False
                    return not stopped
            if stopped:
                return False
            time.sleep(0.25)

    def snapshot(self):
        with self.lock:
            data = dict(self.status)
            last_seen = float(data.get("last_seen_at") or 0)
            data["stale_seconds"] = int(max(0, time.time() - last_seen)) if last_seen else 0
            data["burn_clocks"] = self.burn_clocks
            data["paused"] = bool(self.pause_requested or data.get("paused"))
            data["loop_index"] = int(getattr(self, "loop_index", data.get("loop_index", 1)) or 1)
            data["loop_target"] = int(getattr(self, "loop_target", data.get("loop_target", 1)) or 1)
            data["lifetime"] = self._lifetime_snapshot()
            data["replan_log"] = list(getattr(self.race_planner, "replan_log", []) or [])
            return data

    def set_burn_clocks(self, value):
        with self.lock:
            self.burn_clocks = value
            self._log_locked("update_setting", 0, f"burn_clocks set to {value}")

    def _run(self, client, preset, result, strategy, max_steps):

        state = result or {}
        # v6.7.17: capture the preset's training_stat_priority (the
        # Training Settings panel value) into status so the decision-
        # reasoning display can show the SAME priority the strategy
        # actually used.  The strategy reads preset.training_stat_priority
        # (mant.py _priority_indices), but the reasoning was displaying
        # the character profile's separate training_scorer_overrides.
        # stat_priority -- so a user who reordered priorities in the
        # panel saw the OLD profile order in the reasoning even though
        # the bot was training with their new order.  Storing it here
        # lets the reasoning display match the actual behavior.
        try:
            preset_priority = (
                (preset or {}).get("training_stat_priority")
                or ((preset or {}).get("mant_config") or {}).get("training_stat_priority")
                or []
            )
            with self.lock:
                self.status["preset_training_stat_priority"] = [
                    str(x).lower() for x in (preset_priority or [])
                ]
        except Exception:
            pass
        last_turn = -1
        race_progress_guard = {"turn": None, "count": 0}
        command_guard = {"turn": None, "count": 0}
        try:
            # v7.2 — Per-turn hot-reload of preset and settings. Cached so
            # the file is only re-read when a new turn begins, not on every
            # iteration of the inner loop. Refreshes:
            #   - the preset (extra_race_list, mant_config overrides, etc.)
            #   - the userdata-level settings.json (turn_delay, tp_recovery)
            # so the user can adjust UI controls mid-career and have the
            # changes pick up on the very next turn — no stop/restart needed.
            _hot_reload_state = {"last_turn_reloaded": -1, "store": None, "preset_name": None}
            try:
                from career_bot.config_store import ConfigStore as _ConfigStoreCls
                _userdata_for_run = os.environ.get("SWEEPYCL_USERDATA_DIR") or os.environ.get("SWEEPYCLAUDE_USERDATA_DIR") or getattr(self, "userdata_dir", None) or self.base_dir
                _hot_reload_state["store"] = _ConfigStoreCls(self.base_dir, userdata_dir=_userdata_for_run)
                _hot_reload_state["preset_name"] = (preset or {}).get("name") or ""
            except Exception as _hot_reload_exc:
                self._log("hot_reload_init", 0, f"could not init: {_hot_reload_exc}")

            def _maybe_hot_reload_preset(current_turn, current_preset):
                """Reload the preset from disk if turn changed. Returns the
                preset to use this iteration (either fresh or unchanged)."""
                store = _hot_reload_state.get("store")
                name = _hot_reload_state.get("preset_name")
                if not store or not name:
                    return current_preset
                if current_turn == _hot_reload_state["last_turn_reloaded"]:
                    return current_preset
                try:
                    fresh = store.read_one(name)
                except Exception as exc:
                    self._log("hot_reload_skip", current_turn, f"read_one failed: {exc}")
                    return current_preset
                if not fresh:
                    return current_preset
                # CRITICAL: preserve the runtime-only fields the per-run setup
                # injected on top of the saved preset. extra_race_list_source
                # was set in main.py based on the start-of-run UI state and
                # MUST NOT be overwritten by what's on disk (which may differ
                # if the user is editing). Same for runtime overrides we know
                # the runner cares about.
                preserve_keys = (
                    "extra_race_list_source",
                    "race_planner_mode",
                    "_runtime_overrides",
                    "skill_spending_strategy",
                )
                for k in preserve_keys:
                    if k in current_preset:
                        fresh[k] = current_preset[k]
                # If the user is in manual mode AND has edited their race list,
                # the disk has the new list and we want to use it. If they're
                # in smart mode, the runtime extra_race_list was authored by
                # the smart solver replanning and should be preserved.
                if str(current_preset.get("extra_race_list_source") or "").lower() == "smart":
                    fresh["extra_race_list"] = current_preset.get("extra_race_list", [])
                changed = []
                for k in fresh:
                    if k in preserve_keys: continue
                    if fresh.get(k) != current_preset.get(k):
                        changed.append(k)
                if changed:
                    self._log("hot_reload_preset", current_turn, f"reloaded {len(changed)} field(s): {', '.join(changed[:6])}")
                _hot_reload_state["last_turn_reloaded"] = current_turn
                return fresh

            for i in range(max_steps):
                if self._should_stop():
                    break
                if not self._wait_if_paused():
                    break
                state = self._ensure_chara_info(client, strategy, state)
                data = state.get("data") or {}
                chara = data.get("chara_info") or {}
                turn = int(chara.get("turn") or 0)

                if turn != last_turn:
                    if hasattr(client, "wait_turn_delay"):
                        client.wait_turn_delay()
                    last_turn = turn
                    # v7.2 — Hot-reload the preset at every new turn boundary.
                    preset = _maybe_hot_reload_preset(turn, preset)
                
                self._heartbeat(turn)
                self._mark(turn=turn)
                self._update_analytics(chara)
                self._track_turn_scores(state)
                self._write_state_snapshot(state)
                if self._should_refresh_for_stuck_turn(turn):
                    self._warn(f"same turn seen repeatedly ({turn}); refreshing career state")
                    state = self._fresh_career_state(client, strategy)
                    continue

                if turn == 77 and not getattr(self, "dev_mode", False):
                    print("Turn 77 reached terminating", flush=True)
                    self.stop()
                    break
                
                self.skill_buyer.last_attempt = []
                self.skill_buyer.last_result = {}
                self.item_manager.last_buy_attempt = []
                self.item_manager.last_buy_result = {}
                self.item_manager.last_use_attempt = []
                self.item_manager.last_use_result = {}
                self.skill_buyer.attempt_events = []
                self.item_manager.buy_attempt_events = []
                self.item_manager.use_attempt_events = []

                if data.get("unchecked_event_array"):

                    state = self._drain_events(client, strategy, state)
                    state = self._ensure_chara_info(client, strategy, state, "event drain returned no chara_info")
                    data = state.get("data") or {}
                    chara = data.get("chara_info") or {}
                    self._track_turn_scores(state)
                
                if self._blocked_playing_state(chara):

                    state = self._recover_blocked_state(client, strategy, state)
                    data = state.get("data") or {}
                    chara = data.get("chara_info") or {}
                    if self._blocked_playing_state(chara):

                        self._mark(last_action=f"blocked state {chara.get('playing_state')}")
                        break
                
                self._debug_turn(state, preset)
                self._inject_runner_context(state)
                decision = strategy.next_decision(state, preset)

                
                if self.report:
                    add_decision(self.report, state, decision)
                self._record_decision_trace(strategy, state, preset, decision)
                
                if decision.action == "command":

                    # v6.3/v6.7.5: scorer override moved out of this block.
                    # The "if command" branch here is pre-execution event
                    # handling: it calls ``_handle_items`` then re-derives
                    # ``decision`` via ``strategy.next_decision`` (line 615).
                    # Mutating the first decision had no effect because the
                    # second decision overwrote it.  The override is now
                    # applied at the actual execution point (line ~640).
                    state = self._handle_items(client, state, preset, self._command_from_decision(state, decision), decision)
                    data = state.get("data") or {}
                    if data.get("unchecked_event_array"):

                        state = self._drain_events(client, strategy, state)
                    state = self._ensure_chara_info(client, strategy, state, "command phase returned no chara_info")
                    data = state.get("data") or {}
                    chara = data.get("chara_info") or {}
                    self._mark(turn=chara["turn"])
                    self._update_analytics(chara)
                    self._inject_runner_context(state)
                    decision = strategy.next_decision(state, preset)

                    if self.report:
                        add_decision(self.report, state, decision)
                    self._record_decision_trace(strategy, state, preset, decision)
                
                self._log(decision.action, chara["turn"], decision.reason)
                if decision.action == "idle":
                    self._mark(last_action=decision.reason)
                    break
                if decision.action == "done":
                    self._mark(last_action=decision.reason, finished=True)
                    break
                if not self._wait_if_paused():
                    break
                
                if decision.action == "event":
                    try:
                        state = self._event(client, strategy, decision.payload)
                    except Exception as exc:
                        if self._is_recoverable_error(exc):
                            state = self._recover_with_backoff(client, strategy, exc)
                            continue
                        raise
                elif decision.action == "command":
                    # v6.7.5: apply the scorer override HERE -- to the
                    # decision that actually gets executed.  Previously
                    # the override fired against a pre-event decision
                    # that was immediately thrown away by the re-decide
                    # call above, so the override never affected what ran
                    # but ``last_scorer_override`` was still recorded.
                    # That produced contradictory dashboard rows like
                    # "Trained Wit ... scorer override fired: swapped to
                    # speed" where Wit actually executed.  Applying here
                    # ensures the override either mutates the executed
                    # command_id or stays silent.
                    self._apply_authoritative_scorer_override(state, decision)
                    self._log("command_exec", decision.payload["current_turn"], f"{decision.payload.get('command_type')}:{decision.payload.get('command_id')}:{decision.payload.get('command_group_id')}")
                    self._record_action(decision, chara)
                    try:
                        state = client.exec_command(**decision.payload)
                        data = state.get("data") or {}
                        if data.get("unchecked_event_array"):
                            state = self._drain_events(client, strategy, state)
                    except Exception as exc:
                        if self._is_recoverable_error(exc):
                            state = self._recover_with_backoff(client, strategy, exc)
                            continue
                        if not any(err in str(exc) for err in ("102", "1503")):
                            raise
                        if command_guard["turn"] == turn:
                            command_guard["count"] += 1
                        else:
                            command_guard["turn"], command_guard["count"] = turn, 1
                        if command_guard["count"] > 5:
                            self._log("command_blocked_loop", turn, "exec_command keeps returning 102/1503, stopping")
                            self._mark(last_action="command blocked loop", last_error=f"server rejects all actions at turn {turn} - use Diagnostics rescue")
                            break
                        state = self._recover_blocked_state(client, strategy, state)
                        data = state.get("data") or {}
                        chara = data.get("chara_info") or {}
                        if self._blocked_playing_state(chara):
                            self._mark(last_action=f"blocked state {chara.get('playing_state')}")
                            break
                        continue
                elif decision.action == "race":

                    self._record_action(decision, chara)
                    try:
                        state = self._race(client, state, preset, decision.payload)
                    except Exception as exc:
                        if self._is_recoverable_error(exc):
                            state = self._recover_with_backoff(client, strategy, exc)
                            continue
                        raise
                    # v6.7.12: a non-finale mandatory race loss sets
                    # career_stopped_reason instead of raising.  End the
                    # loop cleanly here so the career report is still
                    # written and no stack trace is shown.  Finale losses
                    # do NOT set this (they fall through to the normal
                    # finish path), so the career completes normally.
                    stopped_reason = None
                    with self.lock:
                        stopped_reason = self.status.get("career_stopped_reason")
                    if stopped_reason:
                        self._mark(last_action=f"career stopped: {stopped_reason}")
                        self._log("career_stopped", turn, stopped_reason)
                        break
                elif decision.action == "race_progress":

                    if race_progress_guard["turn"] == turn:
                        race_progress_guard["count"] += 1
                    else:
                        race_progress_guard["turn"], race_progress_guard["count"] = turn, 1
                    if race_progress_guard["count"] > 8:
                        self._log("race_resume_loop", turn, "giving up after repeated resume attempts")
                        self._mark(last_action="race resume loop", last_error=f"race resume loop at turn {turn}")
                        break
                    if race_progress_guard["count"] > 4:
                        self._log("race_resume_loop", turn, f"attempt {race_progress_guard['count']}, forcing hard recovery")
                        try:
                            if hasattr(client, "hard_reset"):
                                client.hard_reset()
                        except Exception as e:
                            self._log("race_resume_loop", turn, f"hard reset failed: {e}")
                        state = self._fresh_career_state(client, strategy)
                        continue
                    self._record_action(decision, chara)
                    try:
                        state = self._race_progress(client, decision.payload)
                    except Exception as exc:
                        if self._is_recoverable_error(exc):
                            state = self._recover_with_backoff(client, strategy, exc)
                            continue
                        raise
                elif decision.action == "finish":

                    self._record_action(decision, chara)

                    state = self._buy_skills(client, state, preset, True)

                    data = state.get("data") or {}
                    if data.get("race_start_info"):
                        self._log("race_out", decision.payload["current_turn"], "clearing active race")
                        try:
                            state = client.race_out(current_turn=decision.payload["current_turn"])
                        except Exception as e:
                            if any(err in str(e) for err in ("102", "201", "StateRecoveryError")):
                                self._log("race_out_reconciled", decision.payload["current_turn"], f"graceful exit: {e}")
                            else:
                                raise
                    state = self._drain_events(client, strategy, state, limit=50)

                    chara = (state.get("data") or {}).get("chara_info") or {}
                    if int(chara.get("skill_point") or 0) > 200:
                        print(f"SP still high ({chara.get('skill_point')}), retrying final purchase...")
                        state = self._buy_skills(client, state, preset, True)

                    try:
                        state = client.finish_career(current_turn=decision.payload["current_turn"], is_force_delete=False)
                    except Exception as e:
                        if any(err in str(e) for err in ("102", "201", "StateRecoveryError")):
                            self._log("finish_reconciled", decision.payload["current_turn"], f"graceful exit: {e}")
                        else:
                            raise
                    final_chara = self._extract_final_chara_payload(state, chara)
                    final_summary = self._compact_final_chara(final_chara)
                    final_summary["race_results"] = list(self.status.get("race_results") or [])
                    self._record_completed_run_metrics(final_chara)
                    self._mark(
                        last_action="finish",
                        finished=True,
                        final_chara=final_summary,
                        final_stats=final_summary.get("stats", {}),
                        final_aptitudes=final_summary.get("aptitudes", {}),
                        final_rating=final_summary.get("rating", ""),
                        race_results=list(self.status.get("race_results") or []),
                        careers_completed=self.status.get("careers_completed", 0) + 1,
                    )
                    break
                else:

                    self._mark(last_action=decision.action)
                    break
                
                if decision.action not in {"finish"}:
                    state = self._buy_skills(client, state, preset, False)
                
                self._advance(decision.action)
        except Exception as exc:
            import traceback
            trace_str = traceback.format_exc()
            traceback.print_exc()
            print(f"RUNNER CRASH: {exc}")
            
            crash_log_path = runtime_output_root(self.base_dir) / "crash_trace.txt"
            try:
                crash_log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(crash_log_path, "a", encoding="utf-8") as f:
                    f.write(f"--- CRASH AT {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    f.write(trace_str)
                    f.write("\n\n")
            except Exception:
                pass

            self._log("error", self.snapshot().get("turn", 0), str(exc))
            self._mark(last_error=str(exc))
            if self.report:
                set_error(self.report, exc)
        finally:
            if self._should_stop():
                self._record_stopped_run_runtime()
                self._log("stop", self.snapshot().get("turn", 0), "stop requested")
                if self.report:
                    finish_report(self.report, "stopped")
            else:
                if self.report:
                    finish_report(self.report, "finished" if self.status["finished"] else "error")
            if not self.current_run_recorded and not self.status.get("finished"):
                self._record_stopped_run_runtime()
            self._mark(running=False, paused=False)
            with self.lock:
                self.pause_requested = False
            if self.discord_logger:
                try:
                    self.discord_logger.finish_career({
                        "finished": bool(self.status.get("finished")),
                        "last_error": self.status.get("last_error", ""),
                        "turn": self.status.get("turn", 0),
                        "steps": self.status.get("steps", 0),
                        "fans_start": self.status.get("fans_start", 0),
                        "fans_current": self.status.get("fans_current", 0),
                        "fans_gained": self.status.get("fans_gained", 0),
                        "fans_per_hour": self.status.get("fans_per_hour", 0),
                        "skills_bought": self.status.get("skills_bought", 0),
                        "items_bought": self.status.get("items_bought", 0),
                        "items_used": self.status.get("items_used", 0),
                        "clocks_used": self.status.get("clocks_used", 0),
                    })
                except Exception:
                    pass
            if self.report:
                try:
                    self.report["runner_status"] = self.snapshot()
                    self.report.setdefault("runtime_settings", {})["burn_clocks"] = bool(self.burn_clocks)
                    self.report.setdefault("runtime_settings", {})["clock_retry_policy"] = {
                        "user_enabled": bool(self.burn_clocks),
                        "enabled": bool(self.burn_clocks),
                        "source": "report_finalize",
                    }
                except Exception:
                    pass
                try:
                    root_trace_dir = runtime_output_root(self.base_dir) / "bot_logs"
                    out = write_report(self.report, root_trace_dir)
                    print(f"career report written: {out}", flush=True)
                except Exception as e:
                    print(f"failed to write report: {e}", flush=True)


    def _heartbeat(self, turn=None):
        with self.lock:
            previous_turn = int(self.status.get("turn") or 0)
            if turn is not None and int(turn or 0) == previous_turn:
                self.status["same_turn_count"] = int(self.status.get("same_turn_count") or 0) + 1
            else:
                self.status["same_turn_count"] = 0
            self.status["last_seen_at"] = time.time()

    def _stuck_turn_threshold(self):
        raw = os.environ.get("UMA_STUCK_TURN_THRESHOLD", "75")
        try:
            return max(25, int(raw))
        except Exception:
            return 75

    def _should_refresh_for_stuck_turn(self, turn):
        with self.lock:
            count = int(self.status.get("same_turn_count") or 0)
        # A single turn can legitimately involve events, items, races, and skill checks.
        # This only trips when the loop keeps seeing the same turn far beyond normal flow.
        threshold = self._stuck_turn_threshold()
        return bool(turn and count >= threshold and count % max(10, threshold // 3) == 0)

    def _warn(self, message):
        self._log("warning", self.snapshot().get("turn", 0), message)
        with self.lock:
            warnings = self.status.setdefault("warnings", [])
            warnings.append({"time": time.strftime("%H:%M:%S"), "message": str(message)})
            if len(warnings) > 50:
                del warnings[:len(warnings) - 50]

    def _write_state_snapshot(self, state):
        data = (state or {}).get("data") or {}
        chara = data.get("chara_info") or {}
        if not chara:
            return
        try:
            root = runtime_output_root(self.base_dir) / "state_snapshots"
            root.mkdir(parents=True, exist_ok=True)
            run_id = self.status.get("run_id") or "unknown"
            path = root / f"{run_id}.jsonl"
            free = data.get("free_data_set") or {}
            row = {
                "ts": time.time(),
                "turn": int(chara.get("turn") or 0),
                "fans": int(chara.get("fans") or 0),
                "vital": int(chara.get("vital") or 0),
                "max_vital": int(chara.get("max_vital") or 0),
                "motivation": int(chara.get("motivation") or 0),
                "skill_point": int(chara.get("skill_point") or 0),
                "stats": self._turn_stats(chara),
                "coin": int(free.get("coin_num") if free.get("coin_num") is not None else free.get("gained_coin_num") or 0),
                "playing_state": int(chara.get("playing_state") or 0),
                "unchecked_events": len(data.get("unchecked_event_array") or []),
                "race_start": bool(data.get("race_start_info")),
            }
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            with self.lock:
                self.status["last_state_snapshot"] = str(path)
        except Exception as exc:
            # Snapshotting is observability only; never let it break a career.
            if random.random() < 0.02:
                print(f"state snapshot write failed: {exc}", flush=True)


    # Server-side "try again later" codes/phrases. When these persist it's the
    # game server (maintenance / overload / recovery), not a fault in the bot,
    # so the runner rides it out instead of failing the career.
    # 394 is auth/session-invalid (a stale Steam ticket), NOT a server-side
    # maintenance/overload condition -- it is recovered by re-login (which now
    # mints a fresh ticket), so it is intentionally NOT a server-wait token (no
    # 5-minute "waiting for server" backoff / UI banner).
    _SERVER_WAIT_TOKENS = (
        "208", "503", "502", "504",
        "maintenance", "Service Unavailable", "Gateway Timeout", "Bad Gateway",
    )

    def _is_recoverable_error(self, exc):
        text = str(exc)
        return any(token in text for token in (
            "Network error", "timeout", "timed out", "Connection",
            "HTTP 502", "HTTP 503", "HTTP 504", "Gateway Timeout", "Bad Gateway", "Service Unavailable",
            "status=502", "status=503", "status=504",
            "201", "202", "205", "208", "214", "394", "StateRecoveryError",
            "daily reset", "maintenance",
        ))

    def _interruptible_sleep(self, total):
        """Sleep up to ``total`` seconds but wake immediately on a stop request."""
        end = time.time() + max(0.0, float(total))
        while time.time() < end:
            if self._should_stop():
                return
            time.sleep(min(1.0, max(0.0, end - time.time())))

    def _recover_with_backoff(self, client, strategy, exc):
        """Recover from a transient error. For server-side "try again later"
        conditions (maintenance/overload) this keeps waiting with escalating,
        interruptible backoff until the server responds again — riding out a
        maintenance window instead of crashing the career. Returns the fresh
        state, or ``None`` if a stop was requested while waiting (the main loop
        breaks on its own stop check). A genuinely fatal error is re-raised.
        """
        detail = str(exc)
        attempt = 0
        while not self._should_stop():
            attempt += 1
            is_server = any(t in detail for t in self._SERVER_WAIT_TOKENS)
            with self.lock:
                self.status["recoveries"] = int(self.status.get("recoveries") or 0) + 1
                if is_server:
                    self.status["waiting_for_server"] = True
                    self.status["server_wait_reason"] = detail[:160]
            # Server waits ride out longer (cap 5 min); other transient errors
            # use the original shorter cap so normal hiccups recover quickly.
            cap = 300 if is_server else 90
            delay = min(cap, 5 * (2 ** min(6, attempt - 1)))
            note = " (waiting for server / maintenance)" if is_server else ""
            self._log("recover", self.snapshot().get("turn", 0), f"{detail}; retrying after {delay}s{note}")
            self._interruptible_sleep(delay)
            if self._should_stop():
                return None
            try:
                state = self._fresh_career_state(client, strategy)
            except Exception as exc2:
                if self._is_recoverable_error(exc2):
                    detail = str(exc2)
                    continue  # still down — keep waiting
                with self.lock:
                    self.status["waiting_for_server"] = False
                    self.status["server_wait_reason"] = ""
                raise
            with self.lock:
                self.status["same_turn_count"] = 0
                self.status["last_seen_at"] = time.time()
                self.status["waiting_for_server"] = False
                self.status["server_wait_reason"] = ""
            return state
        return None

    def _update_analytics(self, chara):
        chara = chara or {}
        fans = int(chara.get("fans") or 0)
        current_stats = self._turn_stats(chara)
        with self.lock:
            started_at = float(self.status.get("started_at") or time.time())
            if not self.status.get("fans_start") and fans > 0:
                self.status["fans_start"] = fans
            self.status["fans_current"] = fans
            gained = max(0, fans - int(self.status.get("fans_start") or fans or 0))
            self.status["fans_gained"] = gained
            hours = max(1.0 / 3600.0, (time.time() - started_at) / 3600.0)
            self.status["fans_per_hour"] = int(gained / hours)
            # Live career payload for the cockpit UI. This avoids waiting for the
            # separate snapshot endpoint and keeps HP/mood/stats fresh.
            self.status["current_chara"] = {
                "card_id": int(chara.get("card_id") or 0),
                "turn": int(chara.get("turn") or 0),
                "fans": fans,
                "vital": current_stats.get("hp", 0),
                "max_vital": current_stats.get("max_hp", 100),
                "motivation": current_stats.get("motivation", 0),
                "stats": current_stats,
            }

    def _should_stop(self):
        with self.lock:
            return self.stop_requested

    def _advance(self, action):
        with self.lock:
            self.status["steps"] += 1
            self.status["last_action"] = action
            if self.status.get("waiting_for_server"):
                self.status["waiting_for_server"] = False
                self.status["server_wait_reason"] = ""

    def _mark(self, **values):
        with self.lock:
            self.status.update(values)

    def _state_has_chara_turn(self, state):
        data = (state or {}).get("data") or {}
        chara = data.get("chara_info") or {}
        return bool(chara and chara.get("turn") is not None)

    def _ensure_chara_info(self, client, strategy, state, reason="state missing chara_info"):
        """Never let race_out/event-only responses flow into the decision loop.

        Umamusume occasionally returns a valid response without data.chara_info
        after race recovery endpoints.  Refresh before reading chara['turn'] so
        one odd payload cannot crash the runner.
        """
        if self._state_has_chara_turn(state):
            return state
        self._log("recover", self.status.get("turn", 0), f"{reason}, refreshing")
        fresh = self._fresh_career_state(client, strategy)
        if self._state_has_chara_turn(fresh):
            return fresh
        self._mark(last_action="unrecoverable state (no chara_info)")
        raise RuntimeError("StateRecoveryError: state missing chara_info after refresh")

    def _log_locked(self, action, turn, detail):
        items = self.status.setdefault("log", [])
        items.append({
            "id": len(items) + 1,
            "action": action,
            "turn": int(turn or 0),
            "detail": str(detail or ""),
            "time": time.strftime("%H:%M:%S"),
        })
        if len(items) > 120:
            del items[:len(items) - 120]
        try:
            if self.discord_logger and str(action) in {"started", "finish", "error", "warning", "race_rank", "race_reject", "skills", "items_buy", "items_use", "stop"}:
                self.discord_logger.emit_turn({
                    "type": "log",
                    "turn": int(turn or 0),
                    "action": str(action),
                    "detail": str(detail or ""),
                    "time": items[-1].get("time"),
                })
        except Exception:
            pass

    def _log(self, action, turn, detail):
        with self.lock:
            self._log_locked(action, turn, detail)


    def _record_decision_trace(self, strategy, state, preset, decision):
        """Record decision explanations for the dashboard without letting tracing break a run."""
        try:
            trace = None
            if hasattr(strategy, "explain_decision"):
                trace = strategy.explain_decision(state, preset, decision)
            if not trace:
                trace = getattr(strategy, "last_decision_trace", None) or {}
            if not isinstance(trace, dict):
                trace = {"detail": str(trace)}

            data = (state or {}).get("data") or {}
            chara = data.get("chara_info") or {}
            row = dict(trace)
            row.setdefault("ts", time.time())
            row.setdefault("turn", int(chara.get("turn") or 0))
            row.setdefault("action", getattr(decision, "action", ""))
            row.setdefault("reason", str(getattr(decision, "reason", "") or ""))

            root = runtime_output_root(self.base_dir) / "decision_traces"
            root.mkdir(parents=True, exist_ok=True)
            run_id = self.status.get("run_id") or "unknown"
            path = root / f"{run_id}.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

            with self.lock:
                self.status["decision_trace"] = row
                self.status["last_decision_trace"] = str(path)
        except Exception as exc:
            # Decision tracing is observability only. Never let it stop a career.
            if random.random() < 0.05:
                print(f"decision trace write failed: {exc}", flush=True)

    def _decision_reasoning(self, action, facility, detail, stats, decision, payload):
        """Human-readable decision reasoning for the dashboard.

        v6.7.2 rewrite: the "Active profile" line that v6.6 added to every
        row was too noisy and was removed per user feedback.  The profile
        context is now folded INTO the per-action explanations as natural
        WHY language: "Trained Speed -- top-priority stat, current 257
        target 1200, mood favorable, scorer agrees."

        For each action this builds a short list of substantive reasons
        rather than generic boilerplate.  When an irregular-training hijack
        replaced a planned race, decision.reason carries the full hijack
        trace and it's surfaced as the first line.
        """
        raw_reason = str(getattr(decision, "reason", "") or "").strip()
        hp = int((stats or {}).get("hp") or 0)
        max_hp = int((stats or {}).get("max_hp") or 100)
        mood = int((stats or {}).get("motivation") or 0)
        stat_values = {
            "speed": int((stats or {}).get("speed") or 0),
            "stamina": int((stats or {}).get("stamina") or 0),
            "power": int((stats or {}).get("power") or 0),
            "guts": int((stats or {}).get("guts") or 0),
            "wit": int((stats or {}).get("wit") or 0),
        }
        hp_ratio = hp / max(1, max_hp)
        reasons = []

        # Profile context (used for richer reasoning -- NOT surfaced as its
        # own line per user feedback).
        profile_dict = None
        scorer_hint = None
        scorer_override = None
        scorer_override_blocked = None
        epithet_source = None
        preset_priority = []
        try:
            with self.lock:
                profile_dict = self.status.get("active_character_profile")
                scorer_hint = self.status.get("training_scorer_hint")
                scorer_override = self.status.get("last_scorer_override")
                scorer_override_blocked = self.status.get("last_scorer_override_blocked")
                epithet_source = self.status.get("epithet_target_source")
                preset_priority = list(self.status.get("preset_training_stat_priority") or [])
        except Exception:
            pass
        priority = []
        targets = {}
        if profile_dict:
            tso = profile_dict.get("training_scorer_overrides") or {}
            # v6.7.17: show the priority that ACTUALLY drove this
            # decision.  In authoritative mode the scorer overrides the
            # strategy, so the profile's stat_priority is what matters.
            # In hint/disabled mode the strategy decides, and the
            # strategy reads the PRESET's training_stat_priority (the
            # Training Settings panel) -- so that's what we display.
            # Previously the reasoning always showed the profile's
            # priority, which confused users who reordered priorities in
            # the panel: the bot trained with their new order but the
            # reasoning kept showing the profile's old order.
            mode = str(profile_dict.get("training_scorer_mode") or "hint").lower()
            if mode == "authoritative":
                priority = list(tso.get("stat_priority") or [])
            else:
                # Hint / disabled: strategy drives via preset priority.
                priority = list(preset_priority) or list(tso.get("stat_priority") or [])
            targets = tso.get("stat_targets") or {}
        elif preset_priority:
            priority = list(preset_priority)

        # Surface the raw decision reason FIRST so the user always sees the
        # engine's own explanation (especially important for irregular-
        # training hijacks which carry score / main_gain / failure detail).
        if raw_reason and not raw_reason.startswith(("Train ", "Rest", "Recreation", "Medic", "command ")):
            reasons.append(raw_reason)

        if action == "train":
            stat_name = ""
            if facility:
                # facility is "Train Speed" or "Train Speed (rainbow x2)"
                bits = facility.replace("Train ", "").split(" ")
                stat_name = bits[0].lower() if bits else ""
            current = stat_values.get(stat_name, 0)

            # v6.7.9: surface the irregular-training hijack as its own
            # prominent reason line when it replaces a planned race.
            # decision.reason carries the full trace text ("irregular
            # training beats planned race X · G1 · ... score=Y main_gain=Z
            # fail=W").  Previously this was buried in the catch-all
            # action description; users wanted hijack-vs-normal-training
            # distinguishable at a glance in the Decision Reasoning panel.
            if "irregular training beats planned race" in raw_reason.lower():
                # Strip the "v6.3 scorer override: ..." suffix when
                # present so the hijack line stays focused.
                hijack_msg = raw_reason
                if " | v6.3 scorer override" in hijack_msg:
                    hijack_msg = hijack_msg.split(" | v6.3 scorer override")[0].strip()
                reasons.append(
                    "Irregular-training hijack: planned race dropped for training -- "
                    + hijack_msg.replace("irregular training beats planned race ", "")
                )

            why = []
            # Where this stat ranks in the active profile priority
            if stat_name and priority:
                if stat_name in priority:
                    idx = priority.index(stat_name)
                    if idx == 0:
                        why.append(f"top-priority stat ({' > '.join(priority)})")
                    elif idx == 1:
                        why.append(f"2nd-priority stat")
                    else:
                        why.append(f"#{idx + 1} priority")
            # Current value vs target
            target = 0
            if stat_name and targets:
                # Use the medium-distance target as a representative; the
                # full per-distance picture is in the Character Profile tab.
                target = (targets.get("medium") or {}).get(stat_name) or (targets.get("mile") or {}).get(stat_name) or 0
            if current and target:
                pct = int(100 * current / max(1, target))
                why.append(f"at {current}/{target} target ({pct}%)")
            elif current:
                why.append(f"current {current}")
            # HP / mood context
            if hp_ratio < 0.35:
                why.append(f"HP low ({hp}/{max_hp}) but training value still won")
            elif mood >= 4:
                why.append("mood favorable")
            # Scorer agreement / disagreement
            # v6.7.10: when an authoritative override JUST fired this
            # turn, the "scorer agrees" message is tautologically true
            # (the override mutated the action to match the scorer's
            # pick).  Showing both "scorer agrees" AND "override swapped
            # X -> Y" reads as a contradiction to users -- screenshots
            # from one user's run showed multiple turns where the two
            # lines together looked wrong.  Suppress the "agrees" line
            # when the override fired this turn and let the override
            # message carry the full story (with scorer score added so
            # information isn't lost).
            override_fired_this_turn = bool(
                scorer_override
                and int(scorer_override.get("turn") or 0) == int(payload.get("current_turn") or -1)
            )
            if scorer_hint and stat_name and not override_fired_this_turn:
                top = str(scorer_hint.get("best_stat") or "").lower()
                top_score = scorer_hint.get("best_score") or 0
                if top and top == stat_name:
                    why.append(f"v6.1 scorer agrees (score {top_score})")
                elif top:
                    # v6.7.9: when the scorer disagreed AND we're in
                    # authoritative mode AND the override was blocked
                    # by the margin gate, explain that to the user.
                    # Without this they saw "scorer would have picked X"
                    # with no idea why the swap didn't happen.
                    blocked = scorer_override_blocked or {}
                    blocked_turn = int(blocked.get("turn") or 0) if blocked else 0
                    if (blocked and blocked_turn == int(payload.get("current_turn") or -1)
                            and (blocked.get("reason") == "margin_below_threshold")):
                        why.append(
                            f"v6.1 scorer would have picked {top} (score {top_score}); "
                            f"authoritative override blocked -- margin {blocked.get('margin')} "
                            f"below threshold {blocked.get('min_margin')} "
                            f"(tune via training_scorer_overrides.override_margin_pct / _floor)"
                        )
                    else:
                        why.append(f"v6.1 scorer would have picked {top} (score {top_score})")
            # Authoritative override note (rare).  v6.7.5: name the FROM
            # stat instead of the raw command_id and only show this when
            # the override actually swapped *this* training (post-fix the
            # facility/stat_name reflects the post-override command, so
            # ``to_stat`` should equal ``stat_name``).
            # v6.7.10: include the scorer's score in the override line
            # since the redundant "scorer agrees (score N)" line above
            # is now suppressed when the override fired this turn.  The
            # score gives users the same information without the
            # apparent contradiction.
            if scorer_override and int(scorer_override.get("turn") or 0) == int(payload.get("current_turn") or -1):
                from_id = scorer_override.get("from_command_id")
                to_stat = (scorer_override.get("to_stat") or "").lower()
                # Translate from_command_id -> stat name for readability
                from_stat_map = {101: "speed", 102: "power", 103: "guts", 105: "stamina", 106: "wit",
                                 601: "speed", 602: "stamina", 603: "power", 604: "guts", 605: "wit"}
                from_stat = from_stat_map.get(int(from_id or 0), f"cmd {from_id}")
                scorer_score_part = ""
                if scorer_hint and scorer_hint.get("best_score") is not None:
                    scorer_score_part = f", scorer score {scorer_hint.get('best_score')}"
                if to_stat == stat_name:
                    why.append(
                        f"v6.3 authoritative override swapped strategy's pick ({from_stat}) -> {to_stat} "
                        f"(margin {scorer_override.get('margin')}{scorer_score_part})"
                    )
                else:
                    # Override fired but executed action differs -- belt
                    # and suspenders, shouldn't happen post-v6.7.5.
                    why.append(
                        f"override attempted strategy {from_stat} -> {to_stat} (margin {scorer_override.get('margin')}), "
                        f"but final action was {stat_name}"
                    )
            label = stat_name.title() if stat_name else "training"
            reasons.append(f"Trained {label} — " + (", ".join(why) if why else "highest-scoring training this turn"))

        elif action == "race":
            why = []
            # Epithet target progression
            if epithet_source and epithet_source.get("names"):
                names = epithet_source.get("names") or []
                src = epithet_source.get("source") or "auto"
                src_label = {"preset": "user-set", "profile": "profile", "auto": "auto-picked", "none": ""}.get(src, src)
                if names and src_label:
                    why.append(f"chasing {src_label} epithet '{names[0]}'")
            # HP context for races
            if hp_ratio <= 0.15:
                why.append(f"HP critical ({hp}/{max_hp}) but race required by route")
            elif hp_ratio < 0.45:
                why.append(f"HP low ({hp}/{max_hp}), race chosen anyway for fan/route value")
            else:
                why.append(f"HP fine ({hp}/{max_hp})")
            why.append("planned by Smart Race Solver")
            if facility:
                reasons.append(f"Raced {facility} — " + ", ".join(why))
            else:
                reasons.append("Raced — " + ", ".join(why))

        elif action == "rest":
            why = [f"HP {hp}/{max_hp}"]
            if hp_ratio < 0.35:
                why.append("below the productive-training threshold")
            elif hp_ratio < 0.45:
                why.append("below safe-training band")
            else:
                why.append("preemptive recovery before mandatory race")
            if mood >= 4:
                why.append("Recreation was less urgent because mood is already good")
            reasons.append(f"Rested — " + ", ".join(why))

        elif action == "recreation":
            why = [f"mood {mood}"]
            if mood <= 2:
                why.append("at or below the bad-mood floor (stat gains penalized)")
            elif mood == 3:
                why.append("not at favorable; topping up before training")
            if hp_ratio >= 0.6:
                why.append(f"HP fine ({hp}/{max_hp}) so Rest was unnecessary")
            reasons.append(f"Took Recreation — " + ", ".join(why))

        elif action == "medic":
            reasons.append(f"Used Medic — injury or stat-blocking debuff present, HP {hp}/{max_hp}")

        elif action == "finish":
            reasons.append("Career finished — final turn reached or terminal state.")

        else:
            # Fall back to the engine's reason text for action types we
            # haven't customized yet.
            if raw_reason:
                reasons.append(raw_reason)

        # v6.7.10: surface items used this turn with a category-based
        # "why" tag.  The item manager records selections in
        # ``last_use_selected``; we map each item name to a short
        # rationale string ("training failure protection", "mood boost",
        # etc) so the dashboard reasoning panel tells the user what was
        # consumed and why.  Items the bot tried to use but failed
        # (e.g. wrong context) are also surfaced so failures are visible.
        try:
            current_turn = int((payload or {}).get("current_turn") or 0)
            items_line = self._items_used_reason_line(current_turn, action)
            if items_line:
                reasons.append(items_line)
        except Exception:
            pass

        # Deduplicate while preserving order so the raw_reason at the top
        # doesn't repeat the same string the action branch already added.
        seen = set()
        deduped = []
        for r in reasons:
            if r and r not in seen:
                seen.add(r)
                deduped.append(r)
        return deduped

    # v6.7.10: item reasoning is keyed by item_id (matching items.py
    # ITEM_NAMES), NOT display strings -- the old display-name keys did not
    # match the canonical names, so nearly every used item fell through to the
    # bogus "selected by item manager" default.  Each ``last_use_selected``
    # entry carries an ``item_id`` we look up here.
    #
    # Training-effectiveness boost items (Notepad/Manual/Scroll) are
    # stat-specific; the stat is derived from the id's last digit.
    _ITEM_STAT_BY_LAST_DIGIT = {
        1: "Speed", 2: "Stamina", 3: "Power", 4: "Guts", 5: "Wit",
    }

    def _item_reason_for_id(self, item_id):
        """Map an item_id to a human reason string, keyed by the canonical
        items.py id ranges.  Falls back to an id-category description so the
        old ``selected by item manager`` artifact never appears."""
        try:
            iid = int(item_id)
        except Exception:
            return "training item"
        # Training-effectiveness boosts: 1001-1005 (Notepad), 1101-1105
        # (Manual), 1201-1205 (Scroll).
        if 1001 <= iid <= 1205:
            stat = self._ITEM_STAT_BY_LAST_DIGIT.get(iid % 10, "")
            return f"training effectiveness boost ({stat})" if stat else "training effectiveness boost"
        # Energy recovery: Vita 2001-2003, Energy Drink MAX 2201-2202.
        if 2001 <= iid <= 2003 or 2201 <= iid <= 2202:
            return "energy recovery"
        # Max-energy recovery: Royal Kale Juice 2101.
        if iid == 2101:
            return "max-energy recovery"
        # Mood boost: Cupcake 2301-2302.
        if 2301 <= iid <= 2302:
            return "mood boost"
        # Mood + energy snack: Yummy Cat Food 3001, Grilled Carrots 3101.
        if iid in (3001, 3101):
            return "mood + energy (snack)"
        # Training boost (megaphone): 8001-8003 — boosts TRAINING stat gain over
        # several turns. NOT a race item (the cleat hammers below are the race buff).
        if 8001 <= iid <= 8003:
            return "training boost (megaphone)"
        # Race buff (hammer): 11001-11002 — boosts RACE stat gain.
        if 11001 <= iid <= 11002:
            return "race buff (hammer)"
        # Fan boost (glow sticks): 11003.
        if iid == 11003:
            return "fan boost (glow sticks)"
        # Training-failure protection: Good-Luck Charm 10001.
        if iid == 10001:
            return "training-failure protection (charm)"
        # Training reroll: Reset Whistle 7001.
        if iid == 7001:
            return "training reroll (whistle)"
        # Id-category fallback so the artifact string never appears.
        category = iid // 1000
        if category in (1, 5, 9):
            return "training item"
        if category in (8, 11):
            return "race item"
        return "consumable"

    # v6.7.11: solver-setting precedence helpers.  Smart Race Solver
    # Settings panel writes to ``preset.trackblazer_solver_settings``,
    # but the runner historically only read from ``preset.mant_config``.
    # These helpers unify the two sources with proper precedence so the
    # UI knobs actually affect planning.
    def _solver_setting(self, preset, key, default):
        """Read a solver-related setting with precedence:
            1. preset.mant_config[key]    (explicit per-preset override)
            2. preset.trackblazer_solver_settings[key]  (UI panel knob)
            3. ``default``
        Returns the first non-None value found.  Empty strings count as
        unset for string keys so the UI's blank-input case falls through
        to the default.
        """
        try:
            mant = ((preset or {}).get("mant_config") or {})
            mc_val = mant.get(key)
            if mc_val is not None and mc_val != "":
                return mc_val
            tss = ((preset or {}).get("trackblazer_solver_settings") or {})
            tss_val = tss.get(key)
            if tss_val is not None and tss_val != "":
                return tss_val
        except Exception:
            pass
        return default

    # Aptitude letter -> int (matches the trackblazer module's S=8..F=2..G=1 grid).
    _APTITUDE_LETTER_TO_INT = {
        "S": 8, "A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1,
    }

    def _solver_aptitude_floor(self, preset, default_int=6):
        """Resolve ``min_aptitude_floor`` honoring both the integer form
        (used internally) and the letter form (S/A/B/C/D/E/F/G) that the
        UI sometimes saves.  Falls back to ``default_int`` on any parse
        failure so a bad value never crashes the planner."""
        raw = self._solver_setting(preset, "min_aptitude_floor", default_int)
        try:
            if isinstance(raw, str) and raw.strip():
                letter = raw.strip().upper()
                if letter in self._APTITUDE_LETTER_TO_INT:
                    return self._APTITUDE_LETTER_TO_INT[letter]
                # Otherwise let int() try -- the UI also accepts numeric
                # values from older saves.
                return int(letter)
            return int(raw)
        except Exception:
            return int(default_int)

    def _items_used_reason_line(self, current_turn, action=None):
        """Build a single reasoning line describing what items the item
        manager USED this turn and why.  Returns "" if no items were
        used.  v6.7.10."""
        try:
            # On a RACE turn the item manager only holds a train-vs-race PREVIEW
            # selection (e.g. megaphones for a training that didn't happen); it is
            # NOT consumed. The actual race items (cleat hammers / glow sticks) are
            # applied + logged in the pre-race path. Don't surface the unconsumed
            # training preview as "items used" on race turns.
            if str(action or "").strip().lower() == "race":
                return ""
            mgr = getattr(self, "item_manager", None)
            if not mgr:
                return ""
            # ``last_use_selected`` is the list of items the manager
            # actually attempted to use this turn.  Each entry is
            # ``{"name": "...", "item_id": N, "use_num": N}``.  When the
            # API call succeeded, ``last_use_result`` carries
            # ``result == "ok"``; on skip / failure we still want to
            # acknowledge that the manager wanted to use something but
            # couldn't.
            selected = list(getattr(mgr, "last_use_selected", None) or [])
            if not selected:
                return ""
            # Only attribute items to this turn -- the use_attempt_events
            # list carries per-turn entries we can cross-reference.  When
            # the most recent event's turn doesn't match the current
            # turn, the selected list is stale (e.g. from a prior turn);
            # don't double-report.
            events = list(getattr(mgr, "use_attempt_events", None) or [])
            if events:
                last_event_turn = int((events[-1] or {}).get("turn") or 0)
                if last_event_turn != int(current_turn):
                    return ""
            result = (getattr(mgr, "last_use_result", None) or {})
            result_state = ""
            if isinstance(result, dict):
                if result.get("result") == "ok":
                    result_state = ""
                elif result.get("skip"):
                    result_state = f" (skipped: {result.get('skip')})"
                elif "error" in result:
                    result_state = f" (error: {result.get('error')})"
            # Build "Name x N (reason)" entries.
            parts = []
            for entry in selected:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or "").strip()
                if not name:
                    continue
                count = int(entry.get("use_num") or 1)
                why = self._item_reason_for_id(entry.get("item_id"))
                if count > 1:
                    parts.append(f"{name} x{count} ({why})")
                else:
                    parts.append(f"{name} ({why})")
            if not parts:
                return ""
            return f"Items used this turn{result_state}: " + ", ".join(parts)
        except Exception:
            return ""


    def _record_action(self, decision, chara=None):
        payload = decision.payload or {}
        action = decision.action
        turn = int(payload["current_turn"])
        stats = self._turn_stats(chara or {})
        detail = self._format_turn_stats(stats) or str(decision.reason or "")
        facility = ""
        if action == "command":
            command_type = int(payload.get("command_type") or 0)
            command_id = int(payload.get("command_id") or 0)
            command_group_id = int(payload.get("command_group_id") or 0)
            if command_type == 1:
                action = "train"
                facility = TRAINING_LABELS.get(command_id, str(command_id))
            elif command_type == 8:
                action = "medic"
            elif command_type == 7:
                action = "rest"
                facility = str(command_group_id or command_id)
            elif command_type == 3:
                action = "recreation"
                facility = str(command_group_id or command_id)
            else:
                action = f"command {command_type}"
                facility = str(command_id or command_group_id)
        elif action in {"race", "race_progress"}:
            action = "race"
            program_id = int(payload.get("program_id") or 0)
            if program_id and self.race_planner:
                facility = self.race_planner.label(program_id)
            else:
                facility = str(program_id or "")
        elif action == "finish":
            action = "finish"
        reasons = self._decision_reasoning(action, facility, detail, stats, decision, payload)
        row = {
            "turn": turn,
            "action": action,
            "facility": facility,
            "detail": detail,
            "stats": stats,
            "reason": str(getattr(decision, "reason", "") or ""),
            "reasoning": reasons,
            "time": time.strftime("%H:%M:%S"),
        }
        with self.lock:
            history = self.status.setdefault("action_history", [])
            if history and history[-1].get("turn") == row["turn"] and history[-1].get("action") == row["action"] and history[-1].get("facility") == row["facility"]:
                history[-1] = row
            else:
                history.append(row)
            if len(history) > 300:
                del history[:len(history) - 300]

        try:
            if self.discord_logger:
                self.discord_logger.emit_turn({
                    "type": "action",
                    "turn": turn,
                    "action": action,
                    "facility": facility,
                    "detail": detail,
                    "stats": stats,
                    "reason": str(getattr(decision, "reason", "") or ""),
                    "payload": {
                        "command_type": payload.get("command_type"),
                        "command_id": payload.get("command_id"),
                        "command_group_id": payload.get("command_group_id"),
                        "program_id": payload.get("program_id"),
                    },
                })
        except Exception:
            pass

    def _turn_stats(self, chara):
        if not chara:
            return {}
        return {
            "hp": int(chara.get("vital") or 0),
            "max_hp": int(chara.get("max_vital") or 100),
            "motivation": int(chara.get("motivation") or 0),
            "speed": int(chara.get("speed") or 0),
            "stamina": int(chara.get("stamina") or 0),
            "power": int(chara.get("power") or 0),
            "guts": int(chara.get("guts") or 0),
            "wit": int(chara.get("wiz") or 0),
            "skill_point": int(chara.get("skill_point") or 0),
        }

    def _format_turn_stats(self, stats):
        if not stats:
            return ""
        return (
            f"HP {stats['hp']}/{stats['max_hp']} | "
            f"MOOD {stats['motivation']} | "
            f"SPD {stats['speed']} STA {stats['stamina']} PWR {stats['power']} "
            f"GUT {stats['guts']} WIT {stats['wit']} SP {stats['skill_point']}"
        )

    def _blocked_playing_state(self, chara):
        playing_state = int((chara or {}).get("playing_state") or 1)
        return playing_state not in {1, 2, 3, 4, 5}

    def _recover_blocked_state(self, client, strategy, state):
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        if int(chara.get("playing_state") or 0) == 6:
            turn = chara.get("turn", 1)
            if hasattr(client, "minigame_end"):
                state = client.minigame_end(current_turn=turn)
            else:
                state = client.call("single_mode_free/minigame_end", {
                    "result": {
                        "result_state": 1,
                        "result_value": 0,
                        "result_detail_array": None,
                    },
                    "current_turn": turn,
                })
            data = state.get("data") or {}
            if data.get("unchecked_event_array"):
                state = self._drain_events(client, strategy, state)
            return state
        try:
            if hasattr(client, "hard_reset"):
                state = client.hard_reset()
            else:
                state = self._fresh_career_state(client, strategy)
        except Exception as e:
            print(f"Blocked State Recovery Failure: {e}")
            return state
        return state

    def _debug_turn(self, state, preset):
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        free = data.get("free_data_set") or {}
        self.skill_buyer.preview(state, preset)
        self._debug("turn", state, {
            "owned_skills": self._debug_owned_skills(state),
            "inventory": self._debug_inventory(state),
            # Live on-screen race list (program_ids the game is offering this turn).
            # Diagnostic: lets us compare the solver's planned race program_ids
            # (wanted) against what's actually available, to find why marquee G1s
            # (Japan Cup / Arima) fall into the missing-race substitute path.
            "race_condition_array": data.get("race_condition_array") or [],
            "server_skill_tips_raw": chara.get("skill_tips_array") or [],
            "server_owned_skill_raw": chara.get("skill_array") or [],
            "skill_rows_enriched": self._debug_skill_options(state, preset),
            "bot_skill_candidates": list(self.skill_buyer.last_candidates),
            "bot_skill_selected": list(self.skill_buyer.last_selected),
            "bot_skill_attempt": list(self.skill_buyer.last_attempt),
            "bot_skill_result": dict(self.skill_buyer.last_result),
            "server_shop_rows_raw": free.get("pick_up_item_info_array") or [],
            "shop_rows_enriched": self._debug_item_buy_options(state, preset),
            "bot_shop_candidates": list(self.item_manager.last_buy_options),
            "bot_shop_selected": list(self.item_manager.last_buy_selected),
            "bot_shop_attempt": list(self.item_manager.last_buy_attempt),
            "bot_shop_result": dict(self.item_manager.last_buy_result),
            "decision_item_use_rows": list(self.item_manager.last_use_options),
            "bot_item_use_selected": list(self.item_manager.last_use_selected),
            "bot_item_use_attempt": list(self.item_manager.last_use_attempt),
            "bot_item_use_result": dict(self.item_manager.last_use_result),
        })

    def _debug_skill_options(self, state, preset):
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        points = int(chara.get("skill_point") or 0)
        owned = {int(item.get("skill_id") or 0) for item in chara.get("skill_array") or []}
        owned_groups = {self.skill_buyer.skill_to_group_id.get(skill_id, skill_id // 10) for skill_id in owned}
        priority = self.skill_buyer._priority_context(preset)
        blacklist = self.skill_buyer._blacklist(preset)
        selected = {item["skill_id"]: item for item in self.skill_buyer._candidates(chara, preset)}
        result = []
        for tip in chara.get("skill_tips_array") or []:
            resolved = self.skill_buyer.resolve_skill_tip(tip, owned, owned_groups, priority, blacklist, preset)
            skill_id = int((resolved or {}).get("resolved_skill_id") or 0)
            cost = int((resolved or {}).get("cost") or 0)
            selected_flag = skill_id in selected
            skip_reason = (resolved or {}).get("skip_reason")
            if not skip_reason and cost > points:
                skip_reason = "unaffordable"
            elif not skip_reason and not selected_flag:
                skip_reason = "rule_rejected"
            result.append({
                "skill_id": skill_id,
                "group_id": int((resolved or {}).get("group_id") or tip.get("group_id") or 0),
                "tip_rarity": int((resolved or {}).get("tip_rarity") or tip.get("rarity") or 0),
                "hint_level": int((resolved or {}).get("hint_level") or tip.get("level") or 0),
                "candidate_skill_ids": (resolved or {}).get("candidate_skill_ids") or [],
                "name": (resolved or {}).get("resolved_name") or "",
                "cost": cost,
                "affordable": cost <= points,
                "owned_group": (resolved or {}).get("skip_reason") == "owned_group",
                "known": bool((resolved or {}).get("master_exists")),
                "failed_scope": (resolved or {}).get("failed_scope"),
                "selected": selected_flag,
                "resolution_reason": (resolved or {}).get("resolution_reason") or "",
                "skip_reason": skip_reason,
            })
        return result

    def _debug_owned_skills(self, state):
        chara = (state.get("data") or {}).get("chara_info") or {}
        result = []
        for row in chara.get("skill_array") or []:
            skill_id = int(row.get("skill_id") or 0)
            result.append({
                "skill_id": skill_id,
                "group_id": self.skill_buyer.skill_to_group_id.get(skill_id, skill_id // 10),
                "name": self.skill_buyer.skill_names.get(skill_id, ""),
            })
        return result

    def _debug_inventory(self, state):
        free = (state.get("data") or {}).get("free_data_set") or {}
        result = []
        for name, count in sorted(self.item_manager._owned_map(free).items()):
            item_id = DISPLAY_TO_ID.get(name)
            if not item_id:
                continue
            result.append({
                "name": name,
                "item_id": item_id,
                "current_num": int(count),
                "failed_scope": "this_turn" if item_id in self.item_manager.failed_use_this_turn else None,
            })
        return result

    def _debug_item_buy_options(self, state, preset):
        data = state.get("data") or {}
        free = data.get("free_data_set") or {}
        current_turn = int((data.get("chara_info") or {}).get("turn") or 0)
        coin_val = free.get("coin_num")
        if coin_val is None:
            coin_val = free.get("gained_coin_num")
        budget = int(coin_val or 0)
        owned = self.item_manager._owned_map(free)
        result = []
        for row in free.get("pick_up_item_info_array") or []:
            shop_item_id = int(row.get("shop_item_id") or 0)
            item_id = int(row.get("item_id") or 0)
            name = ITEM_NAMES.get(item_id)
            if not name:
                continue
            limit_turn = int(row.get("limit_turn") or 0)
            cost = int(row.get("coin_num") or 0)
            original_cost = int(row.get("original_coin_num") or cost)
            bought = int(row.get("item_buy_num") or 0)
            limit = int(row.get("limit_buy_count") or 1)
            expired = limit_turn > 0 and current_turn > limit_turn
            rejected = shop_item_id in self.item_manager.failed_exchange_this_snapshot
            skip_buy = self.item_manager._skip_buy(name, owned, preset)
            skip_reason = None
            if expired:
                skip_reason = "expired"
            elif bought >= limit:
                skip_reason = "limit_reached"
            elif rejected:
                skip_reason = "rejected"
            elif skip_buy:
                skip_reason = "skip_buy"
            elif cost > budget:
                skip_reason = "unaffordable"
            result.append({
                "shop_item_id": shop_item_id,
                "item_id": item_id,
                "name": name,
                "cost": cost,
                "original_cost": original_cost,
                "mant_coin": budget,
                "affordable": cost <= budget,
                "current_num": bought,
                "limit": limit,
                "absolute_limit_turn": limit_turn,
                "server_turn_delta": (limit_turn - current_turn) if limit_turn > 0 else None,
                "ui_turns_left": None,
                "limit_reached": bought >= limit,
                "expired": expired,
                "rejected": rejected,
                "skip_buy": skip_buy,
                "selected": False,
                "skip_reason": skip_reason,
            })
        cfg = self.item_manager._mant_cfg(preset)
        tiers = cfg.get("item_tiers") or {}
        tier_count = int(cfg.get("tier_count") or 8)
        remaining_budget = budget
        for tier in range(1, tier_count + 1):
            tier_rows = [
                row for row in result
                if row.get("skip_reason") is None
                and not row.get("selected")
                and int(tiers.get(display_to_slug(row.get("name")), 999)) == tier
            ]
            tier_rows.sort(key=lambda row: (int(row.get("absolute_limit_turn") or 99), int(row.get("cost") or 9999)))
            for row in tier_rows:
                cost = int(row.get("cost") or 0)
                remaining = remaining_budget - cost
                if remaining < 0:
                    row["skip_reason"] = "unaffordable"
                    continue
                threshold = 0
                thresholds = cfg.get("tier_thresholds") or {}
                if tier > 1 and current_turn <= 64:
                    threshold = int(thresholds.get(str(tier), thresholds.get(tier, (tier - 1) * 50)) or 0)
                if threshold > 0 and remaining < threshold:
                    row["skip_reason"] = "rule_rejected"
                    continue
                row["selected"] = True
                remaining_budget = remaining
        return result

    def _api_result(self, result):
        result = dict(result or {})
        error = str(result.get("error") or "")
        code = None
        for token in error.replace(":", " ").replace(",", " ").split():
            if token.isdigit():
                value = int(token)
                if value in {201, 202, 205, 208, 214, 394, 709}:
                    code = value
                    break
        if result.get("result") == "ok":
            code = 1
        return {
            "ok": result.get("result") == "ok",
            "result_code": code,
            "error": error or None,
        }

    def _sum_cost(self, rows):
        return sum(int((row or {}).get("cost") or 0) for row in rows or [])

    def _shop_attempt_cost(self, attempt, selected):
        costs = {int(row.get("shop_item_id") or 0): int(row.get("cost") or 0) for row in selected or []}
        return sum(costs.get(int(row.get("shop_item_id") or 0), 0) for row in attempt or [])

    def _fresh_career_state(self, client, strategy=None, drain_events=True):
        import time
        errors = []
        max_retries = 8
        for attempt in range(max_retries):
            relogin = attempt > 0
            try:
                if relogin:
                    if not hasattr(client, "login"):
                        break
                    try:
                        client.login()
                    except Exception as e:
                        if "Network error" in str(e) or "102" in str(e) or "201" in str(e) or "208" in str(e):
                            raise e
                        else:
                            raise
                if hasattr(client, "load_career"):
                    state = client.load_career()
                else:
                    state = client.call("single_mode_free/load", {})
                if drain_events and strategy and (state.get("data") or {}).get("unchecked_event_array"):
                    state = self._drain_events(client, strategy, state)
                self.skill_buyer.reset_scoped_failures()
                self.item_manager.reset_scoped_failures()
                return state
            except Exception as exc:
                err_str = str(exc)
                errors.append(err_str)
                if attempt < max_retries - 1:
                    dna_sleep(10, 10)
        if hasattr(client, "hard_reset"):
            return client.hard_reset()
        raise RuntimeError("career recovery failed: " + " | ".join(errors[-2:]))

    def _event(self, client, strategy, payload):
        data = dict(payload)
        event = data.pop("_event", None)
        current_turn = data.pop("_current_turn", 0)
        if event:
            choice = strategy.choose_from_event(event, current_turn)
            self._log("event_choice", current_turn, f"{data.get('event_id')} -> {choice}")
            return client.check_event(
                event_id=data["event_id"],
                chara_id=event.get("chara_id", 0),
                choice_number=choice,
                current_turn=current_turn
            )
        if "event_id" not in data:
            self._log("recover", current_turn, "event requested without event_id, forcing state refresh")
            return self._fresh_career_state(client, strategy)
        return client.check_event(**data)

    def _drain_events(self, client, strategy, state, limit=20):
        current = state
        seen = {}
        last_turn = self.status.get("turn", 0)
        for index in range(limit):
            data = current.get("data") or {}
            events = data.get("unchecked_event_array") or []
            if not events:
                return current
            event = events[0] or {}
            choice = strategy._choice(event)
            chara_turn = (data.get("chara_info") or {}).get("turn")
            turn = chara_turn if chara_turn is not None else self.status["turn"]
            last_turn = turn
            signature = (event.get("event_id"), event.get("chara_id", 0), turn, choice)
            seen[signature] = seen.get(signature, 0) + 1
            if seen[signature] >= 4:
                self._log(
                    "event_drain_repeat",
                    turn,
                    f"event {event.get('event_id')} repeated {seen[signature]} times; refreshing career state",
                )
                return self._fresh_career_state(client, strategy, drain_events=False)

            payload = {"event_id": event.get("event_id"), "chara_id": event.get("chara_id", 0), "choice_number": choice, "current_turn": turn}
            if choice is None:
                payload = {"event_id": event.get("event_id"), "_event": event, "_current_turn": turn}
            # v7.6.2: snapshot chara_info before the choice so we can record the
            # event's outcome natively from the bot's own API traffic.
            before_chara = (data.get("chara_info") or {}) if self.native_event_capture else None
            try:
                current = self._event(client, strategy, payload)
            except Exception as exc:
                if self._is_recoverable_error(exc):
                    self._log("event_drain_recover", turn, str(exc))
                    return self._recover_with_backoff(client, strategy, exc)
                raise
            if self.native_event_capture and choice is not None:
                self._capture_event_outcome(event, choice, before_chara, current)

        data = current.get("data") or {}
        events = data.get("unchecked_event_array") or []
        if events:
            self._log(
                "event_drain_limit",
                last_turn,
                f"{len(events)} pending event(s) remain after drain limit {limit}; refreshing career state",
            )
            return self._fresh_career_state(client, strategy, drain_events=False)
        return current

    def _capture_event_outcome(self, event, choice_index, before_chara, after_state):
        """v7.6.2: record an event outcome from the bot's own API traffic.

        Native alternative to the external Frida dumper — diffs chara_info
        before/after the choice and writes it to the event-outcome KB, keyed by
        story_id. Must never break a run, so all failures are swallowed.
        """
        try:
            story_id = str((event or {}).get("story_id") or "").strip()
            if not story_id:
                return
            after_chara = ((after_state or {}).get("data") or {}).get("chara_info") or {}
            if not before_chara or not after_chara:
                return
            # Resolve the 1-based select_index of the chosen option (the KB keys
            # outcomes by select_index, not the 0-based choice index).
            choices = ((event.get("event_contents_info") or {}).get("choice_array") or [])
            select_index = None
            if isinstance(choice_index, int) and 0 <= choice_index < len(choices):
                select_index = (choices[choice_index] or {}).get("select_index")
            if select_index is None:
                select_index = (choice_index or 0) + 1
            event_name = (
                ((event.get("event_contents_info") or {}).get("title") if isinstance(event.get("event_contents_info"), dict) else "")
                or event.get("title")
                or event.get("event_title")
                or event.get("name")
                or ""
            )
            event_kb.record_observation(
                self.base_dir,
                story_id=story_id,
                select_index=select_index,
                before=before_chara,
                after=after_chara,
                event_name=event_name,
            )
        except Exception:
            pass

    def _non_retryable_path(self):
        return runtime_output_root(self.base_dir) / "non_retryable_races.json"

    def _load_non_retryable(self):
        """Program ids the game has refused to continue (server 205/2507).

        v1.5: learned across careers and persisted so the bot stops wasting a
        retry attempt -- and logging an error -- on races the game won't let it
        re-run (the junior/classic mandatory G1s, the Twinkle Star finale, etc.).
        """
        cached = getattr(self, "_non_retryable_set", None)
        if cached is not None:
            return cached
        ids = set()
        try:
            path = self._non_retryable_path()
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8")) or {}
                for pid in (data.get("non_retryable_program_ids") or []):
                    try:
                        ids.add(int(pid))
                    except Exception:
                        continue
        except Exception:
            ids = set()
        self._non_retryable_set = ids
        return ids

    def _mark_non_retryable(self, program_id, error_code=""):
        try:
            pid = int(program_id or 0)
        except Exception:
            return
        if pid <= 0:
            return
        ids = self._load_non_retryable()
        if pid in ids:
            return
        ids.add(pid)
        try:
            path = self._non_retryable_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"non_retryable_program_ids": sorted(ids),
                       "note": "Program ids the game rejected race-continue on (205/2507); retries are skipped for these. Delete this file to relearn."}
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _free_continue_count(self, home_info):
        """Usable free race continues.

        v1.5 fix: the game exposes the standing free-continue pool in
        ``free_continue_num`` (with a ``free_continue_time`` refresh stamp), NOT
        ``available_free_continue_num`` -- which is 0 on the Trackblazer races
        that don't grant a per-race free continue.  Reading only the latter made
        Icarus believe it had zero free retries and fall back to PAID clocks,
        which those races reject (error 205) -- so 3 free continues sat unused
        all run.  Use whichever field reports more.
        """
        if not isinstance(home_info, dict):
            return 0
        try:
            a = int(home_info.get("available_free_continue_num", 0) or 0)
        except Exception:
            a = 0
        try:
            b = int(home_info.get("free_continue_num", 0) or 0)
        except Exception:
            b = 0
        return max(a, b)

    def _get_clocks_left(self, root, max_clocks=5):
        data = root.get("data") or {}

        home_info = data.get("home_info")
        if isinstance(home_info, dict) and "available_continue_num" in home_info:
            std = int(home_info.get("available_continue_num", 0))
            free = self._free_continue_count(home_info)
            continue_type = 1 if free > 0 else 2
            return {
                "source": "data.home_info.available_continue_num",
                "clocks_left": std + free,
                "continue_type": continue_type,
            }

        race_start_info = data.get("race_start_info")
        if isinstance(race_start_info, dict) and "continue_num" in race_start_info:
            used = int(race_start_info["continue_num"])
            return {
                "source": "data.race_start_info.continue_num",
                "clocks_used": used,
                "clocks_left": max_clocks - used,
                "continue_type": 2,
            }

        return {"source": "unknown", "clocks_left": 0, "continue_type": 2}

    def _race_program_summary(self, program_id, rank=None, turn=None):
        program_id = int(program_id or 0)
        info = {}
        if self.race_planner:
            try:
                info = self.race_planner._program_info(program_id) or {}
            except Exception:
                info = {}
        def as_int(value, default=0):
            try:
                return int(value or default)
            except Exception:
                return default
        grade = str(info.get("grade") or "").upper()
        official = {}
        reward = {}
        if self.race_planner:
            try:
                official = dict(getattr(self.race_planner, "official_races", {}).get(program_id) or {})
                reward = dict(getattr(self.race_planner, "trackblazer_rewards", {}).get(program_id) or {})
            except Exception:
                official = {}
                reward = {}
        if not grade and self.race_planner:
            try:
                from career_bot import trackblazer_rules as tb_rules
                grade = tb_rules.normalize_grade(info.get("race_instance_id") or info.get("grade"))
            except Exception:
                grade = ""
        return {
            "turn": as_int(turn),
            "program_id": program_id,
            "race_instance_id": as_int(info.get("race_instance_id")),
            "name": str(info.get("name") or (self.race_planner.label(program_id) if self.race_planner and program_id else program_id) or ""),
            "grade": grade,
            "distance_m": as_int(info.get("distance_m") or info.get("distance")),
            "distance_type": str(info.get("distance_type") or ""),
            "terrain": str(info.get("terrain") or info.get("ground_label") or ""),
            "fans": as_int(info.get("fans") or info.get("fan_count") or info.get("base_fans") or info.get("fans_num")),
            "rank": as_int(rank, 99),
            "won": as_int(rank, 99) == 1,
            "master_metadata": {
                "source": "master.mdb_exports" if (official or reward) else "",
                "date": official.get("date"),
                "venue": official.get("venue"),
                "race_track_id": as_int(official.get("race_track_id")),
                "month": as_int(official.get("month")),
                "half": as_int(official.get("half")),
                "permission": as_int(official.get("permission")),
                "fan_set_id": as_int(official.get("fan_set_id") or reward.get("fan_set_id")),
                "need_fan_count": as_int(official.get("need_fan_count")),
                "reward_set_id": as_int(official.get("reward_set_id") or reward.get("reward_set_id")),
                "fans_first": as_int(reward.get("fans_first") or official.get("fans")),
                "trackblazer_coin_first": self.race_planner._first_place_reward(reward.get("coin_rewards") or [], "coin_num") if self.race_planner and reward else 0,
                "trackblazer_win_points_first": self.race_planner._first_place_reward(reward.get("win_point_rewards") or [], "point_num") if self.race_planner and reward else 0,
                "race_group_ids": reward.get("race_group_ids") or [],
            },
        }

    def _classify_race_type(self, preset, payload, program_id, turn):
        """Classify races so logs can separate mandatory/finale/solver/fallback."""
        if payload.get("_forced_race"):
            return "mandatory"
        if int(turn or 0) >= 73:
            return "finale"
        source = str((preset or {}).get("extra_race_list_source") or "").strip().lower()
        try:
            wanted = {int(x) for x in (preset or {}).get("extra_race_list") or []}
        except Exception:
            wanted = set()
        if int(program_id or 0) in wanted:
            return "solver_planned" if source == "smart" else "manual"
        if source == "smart":
            return "fallback"
        return "extra"

    def _official_performance_hint(self, program_id, chara=None, running_style=None):
        """Return compact master.mdb-derived performance-rate context for logs.

        These rates are not treated as a deterministic win predictor.  They give
        the AI dataset real official context for distance/surface/style/mood so
        later models can learn whether a failed race was likely due to aptitude
        or raw stat shortage.
        """
        if not self.race_planner:
            return {}
        chara = chara or {}
        rates = getattr(self.race_planner, "performance_rates", {}) or {}
        info = {}
        try:
            info = self.race_planner._program_info(program_id) or {}
        except Exception:
            info = {}
        def apt(key, default=1):
            try:
                return int(chara.get(key) or default)
            except Exception:
                return int(default)
        distance_m = int(info.get("distance_m") or info.get("distance") or 0)
        if distance_m <= 1400:
            dist_key = "proper_distance_short"
            dist_label = "Sprint"
        elif distance_m <= 1800:
            dist_key = "proper_distance_mile"
            dist_label = "Mile"
        elif distance_m <= 2400:
            dist_key = "proper_distance_middle"
            dist_label = "Medium"
        else:
            dist_key = "proper_distance_long"
            dist_label = "Long"
        ground = int(info.get("ground") or 1)
        surf_key = "proper_ground_dirt" if ground == 2 else "proper_ground_turf"
        surf_label = "Dirt" if ground == 2 else "Turf"
        style_map = {
            1: ("proper_running_style_nige", "Front Runner"),
            2: ("proper_running_style_senko", "Pace Chaser"),
            3: ("proper_running_style_sashi", "Late Surger"),
            4: ("proper_running_style_oikomi", "End Closer"),
        }
        style_key, style_label = style_map.get(int(running_style or 0), ("", ""))
        dist_apt = apt(dist_key)
        surf_apt = apt(surf_key)
        style_apt = apt(style_key) if style_key else 0
        mood = apt("motivation", 3)
        dist_row = (rates.get("distance_rate") or {}).get(str(dist_apt), {}) if isinstance(rates, dict) else {}
        surf_row = (rates.get("ground_rate") or {}).get(str(surf_apt), {}) if isinstance(rates, dict) else {}
        style_row = (rates.get("runningstyle_rate") or {}).get(str(style_apt), {}) if isinstance(rates, dict) and style_apt else {}
        mood_row = (rates.get("motivation_rate") or {}).get(str(mood), {}) if isinstance(rates, dict) else {}
        values = []
        for value in (dist_row.get("proper_rate_speed"), dist_row.get("proper_rate_power"), surf_row.get("proper_rate"), style_row.get("proper_rate"), mood_row.get("motivation_rate")):
            try:
                if value:
                    values.append(float(value))
            except Exception:
                pass
        return {
            "distance_label": dist_label,
            "distance_aptitude": dist_apt,
            "surface_label": surf_label,
            "surface_aptitude": surf_apt,
            "running_style": int(running_style or 0),
            "running_style_label": style_label,
            "running_style_aptitude": style_apt,
            "motivation": mood,
            "distance_speed_rate": dist_row.get("proper_rate_speed"),
            "distance_power_rate": dist_row.get("proper_rate_power"),
            "surface_rate": surf_row.get("proper_rate"),
            "running_style_rate": style_row.get("proper_rate"),
            "motivation_rate": mood_row.get("motivation_rate"),
            "aggregate_rate": round(sum(values) / max(1, len(values)), 2) if values else 0,
            "scale": (rates.get("scale") if isinstance(rates, dict) else 10000) or 10000,
        }

    def _record_race_result(self, program_id, rank, turn, race_type="", stats=None, preset_name="", trainee_id="", clock_retry=None, chara=None, running_style=None, style_decision=None):
        row = self._race_program_summary(program_id, rank=rank, turn=turn)
        row["race_type"] = race_type or row.get("race_type") or "unknown"
        if stats:
            row["stat_snapshot"] = dict(stats)
        if clock_retry:
            row["clock_retry"] = dict(clock_retry)
            row["initial_rank"] = int((clock_retry or {}).get("initial_rank") or rank or 99)
            row["final_rank"] = int(rank or 99)
            row["clocks_used"] = int((clock_retry or {}).get("used") or 0)
            row["won_after_clock"] = bool((clock_retry or {}).get("won_after_retry"))
            row["won_without_clock"] = bool((clock_retry or {}).get("won_before_retry"))
        if style_decision:
            row["style_adaptation"] = {
                "decision_id": (style_decision or {}).get("decision_id"),
                "mode": (style_decision or {}).get("mode"),
                "base_user_style": (style_decision or {}).get("base_user_style"),
                "recommended_style": (style_decision or {}).get("recommended_style"),
                "applied_style": (style_decision or {}).get("applied_style"),
                "style_changed": (style_decision or {}).get("style_changed"),
                "confidence": (style_decision or {}).get("confidence"),
                "expected_reward_delta": (style_decision or {}).get("expected_reward_delta"),
            }
        perf = self._official_performance_hint(program_id, chara=chara or {}, running_style=running_style)
        if perf:
            row["performance_hint"] = perf
        with self.lock:
            results = self.status.setdefault("race_results", [])
            # Replace duplicate result for the same turn/program when a retry improves the rank.
            for idx in range(len(results) - 1, -1, -1):
                old = results[idx]
                if int(old.get("turn") or 0) == int(turn or 0) and int(old.get("program_id") or 0) == int(program_id or 0):
                    results[idx] = row
                    break
            else:
                results.append(row)
            if len(results) > 120:
                del results[:len(results) - 120]
            counts = dict(self.status.get("race_type_counts") or {})
            counts[row["race_type"]] = int(counts.get(row["race_type"], 0)) + 1
            self.status["race_type_counts"] = counts
        try:
            record_race_outcome(self.base_dir, row, stats=stats, preset_name=preset_name, trainee_id=trainee_id)
        except Exception as exc:
            self._log("race_outcome_record_failed", turn, str(exc))
        return row

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

    def _runtime_support_for_solver(self):
        with self.lock:
            inv = dict(self.status.get("inventory") or {})
            clocks = int(self.status.get("clocks_left") or 0)
        def count_any(ids):
            total = 0
            for key in ids:
                total += int(inv.get(str(key), inv.get(key, 0)) or 0)
            return total
        return {
            "energy_items": count_any(["Vita 20", "Vita 40", "Vita 65", 10006, 10007, 10008]),
            "race_items": count_any(["Master Cleat Hammer", "Artisan Cleat Hammer", "Glow Sticks", 10021, 10022, 10023]),
            "clocks": clocks,
            "burn_clocks_enabled": bool(self.burn_clocks),
            "clocks_enabled": bool(self.burn_clocks),
        }

    def _maybe_replan_smart_races_after_result(self, preset, state, program_id, rank, turn, race_type):
        """Re-solve after every live smart-route race result.

        The base route is only a starting point.  After a race is run, the
        remaining schedule is regenerated from current stats, runtime support,
        clock policy, and the accumulated race-result ledger.  This lets failed
        races mark epithet branches dead, clock-rescued wins remain visible as
        risk, and Live Policy Assistance update later choices without stale
        assumptions.
        """
        if str((preset or {}).get("extra_race_list_source") or "").strip().lower() != "smart":
            return None
        cfg = dict((preset or {}).get("mant_config") or {})
        # v1.5: honor the "Live Schedule Re-Planning" UI toggle
        # (trackblazer_solver_settings) via _solver_setting; mant_config still wins.
        if self._solver_setting(preset, "enable_live_smart_replan", True) is False:
            return None
        if int(turn or 0) >= 72:
            return None
        # v6.7.22: Android-style event-driven re-planning (default on). A WON
        # race does not trigger a re-solve -- the existing plan is reused, like
        # the Android bot. Only a loss (handled below) or a vanished planned
        # race (the "missing" re-solve) rebuilds the schedule.
        if int(rank or 99) == 1 and bool(self._solver_setting(preset, "replan_on_events_only", True)):
            return None
        # v6.7.21: "Disable Schedule Re-Plan Upon Race Loss" (Smart Race Solver
        # panel, defaults off). When a race is lost and this is enabled, keep
        # the originally locked-in schedule instead of re-planning the remaining
        # turns. The loss is still recorded by _record_race_result; epithets
        # that depended on the lost race won't be re-routed. Mirrors the Android
        # bot's racing.disableScheduleReplanOnRaceLoss behavior.
        if int(rank or 99) != 1 and bool(self._solver_setting(preset, "disable_schedule_replan_on_race_loss", False)):
            self._log("smart_replan_skipped", turn, f"race lost (rank {rank} on {program_id}); re-plan on loss disabled, keeping original schedule")
            return None
        try:
            data = (state or {}).get("data") or {}
            chara = data.get("chara_info") or {}
            cfg = dict((preset or {}).get("mant_config") or {})
            weights = dict(cfg.get("trackblazer_weights") or (preset or {}).get("trackblazer_weights") or {})
            weights["currentStats"] = self._turn_stats(chara)
            weights["runtimeSupport"] = self._runtime_support_for_solver()
            next_turn = min(72, int(turn or 0) + 1)
            trainee_id = chara.get("card_id") or chara.get("chara_id") or ""
            history = list(self.status.get("race_results") or [])
            # v6.2: resolve the active character profile and layer its solver
            # overrides + epithet goals under the preset's explicit values.
            # v6.3: pass chara_info so the resolver can auto-derive a
            # profile from live aptitudes when no hand-curated one matches.
            from career_bot import character_profiles
            profile = character_profiles.resolve_profile(
                card_id=chara.get("card_id") or 0,
                chara_id=chara.get("chara_id") or 0,
                scenario_id=int(self.status.get("scenario_id") or 4),
                base_dir=self.base_dir,
                preset_name=(preset or {}).get("name", ""),
                chara_info=chara,
            )
            # v6.6: when injecting profile solver overrides, treat a
            # preset value equal to the system default as "not user-set"
            # so the profile override wins.  The old condition only fired
            # for None/""/0, which silently dropped the profile override
            # whenever the preset had been Saved through the dashboard
            # (which writes the system default into trackblazer_weights).
            from career_bot.trackblazer import DEFAULT_SOLVER_WEIGHTS as _SOLVER_DEFAULTS
            for k, v in profile.solver_weight_overrides().items():
                current = weights.get(k)
                preset_default = _SOLVER_DEFAULTS.get(k)
                if k not in weights or current in (None, "", 0):
                    weights[k] = v
                elif preset_default is not None and current == preset_default:
                    # Preset has the system default -> not really user-set,
                    # profile override wins
                    weights[k] = v
                # else: preset has a non-default value the user chose
                # explicitly -> preset wins, profile does NOT override
            # v6.4: profile.effective_target_epithets() returns explicit
            # profile.target_epithets if set, otherwise auto-picked
            # signature epithet(s) when profile.auto_pick_epithets is True,
            # otherwise [].  Preset still wins above the profile.
            profile_targets, target_source = profile.effective_target_epithets()
            preset_targets = (preset or {}).get("trackblazer_target_epithets") or []
            actual_targets = list(preset_targets) if preset_targets else list(profile_targets)
            actual_target_source = "preset" if preset_targets else target_source
            # Race agenda (preset.trackblazer_race_agenda): merge its curated
            # epithet bundle into the solver targets so the schedule commits to a
            # full agenda instead of eroding to minimal fan-only racing after
            # race losses.  Agenda epithets are additive to any explicit targets.
            agenda_id = (preset or {}).get("trackblazer_race_agenda") or ""
            agenda_targets, agenda_forced = trackblazer.resolve_agenda_epithets(self.base_dir, agenda_id)
            if agenda_targets or agenda_forced:
                actual_targets = trackblazer._merge_epithet_lists(actual_targets, agenda_targets)
                actual_target_source = (
                    f"agenda:{agenda_id}" if actual_target_source in ("none", "auto")
                    else f"{actual_target_source}+agenda:{agenda_id}"
                )
            forced_epithets = trackblazer._merge_epithet_lists(
                (preset or {}).get("trackblazer_forced_epithets") or profile.forced_epithets,
                agenda_forced,
            )
            with self.lock:
                self.status["epithet_target_source"] = {
                    "source": actual_target_source,
                    "names": list(actual_targets),
                    "profile_auto_picked": list(profile.auto_picked_epithets),
                }
            plan = trackblazer.make_schedule(
                self.base_dir,
                aptitudes=self._chara_trackblazer_aptitudes(chara),
                # v6.7.11: read solver settings with PROPER precedence:
                #   1. preset.mant_config.X  (explicit per-preset override)
                #   2. preset.trackblazer_solver_settings.X  (UI panel knobs)
                #   3. hardcoded fallback
                # Before v6.7.11, the runner only read from mant_config,
                # which meant every Smart Race Solver Settings panel knob
                # (Max Streak, Fan Bonus, Include OP, Min Aptitude Floor,
                # Distance Preference Mode, Allow Summer Racing) silently
                # did NOTHING -- the UI saved values but the runner used
                # hardcoded defaults.  This kept Max Streak permanently
                # at 2, which capped consecutive races and was the actual
                # bottleneck for the user's "race count won't go above
                # ~30" issue.  Now the UI knobs are honored.
                fan_bonus=float(self._solver_setting(preset, "fan_bonus", 0)),
                max_races_in_row=int(self._solver_setting(preset, "max_races_in_row", 5)),
                include_op=bool(self._solver_setting(preset, "include_op", False)),
                floor=self._solver_aptitude_floor(preset, default_int=6),
                solver=str(cfg.get("solver") or "auto"),
                weights=weights,
                training_blocks=(preset or {}).get("training_blocks") or [],
                manual_locks=(preset or {}).get("manual_locks") or {},
                target_epithets=actual_targets,
                forced_epithets=forced_epithets,
                preferred_distances=cfg.get("preferred_distances") or (preset or {}).get("preferred_distances") or profile.preferred_distances,
                distance_preference_mode=str(self._solver_setting(preset, "distance_preference_mode", "balanced")),
                current_turn=next_turn,
                race_history=history,
                trainee_id=trainee_id,
                preset_name=(preset or {}).get("name", ""),
            )
            remaining = [int(x) for x in plan.get("extra_race_list") or []]
            fallback_used = bool(plan.get("fallback_used"))
            cur_turn = int(next_turn or turn or 0)
            prev_plan = (preset or {}).get("trackblazer_last_plan") or {}
            prev_remaining = [int(x) for x in (prev_plan.get("extra_race_list") or [])]
            prev_was_exact = bool(prev_remaining) and not bool(prev_plan.get("fallback_used"))

            # Detect high-value races the new plan drops vs the held plan.
            if self.race_planner:
                new_hv = self.race_planner._high_value_races(plan)
                prev_hv = self.race_planner._high_value_races(prev_plan)
            else:
                new_hv = prev_hv = {}
            dropped_hv = sorted(
                (
                    {"program_id": pid, "turn": rt, "name": name, "est_fans": fans}
                    for pid, (rt, name, fans) in prev_hv.items()
                    if rt >= cur_turn and pid not in new_hv
                ),
                key=lambda d: d["turn"],
            )

            # v6.7.20 GUARD (mirrors RacePlanner): a beam fallback must not
            # overwrite a good exact plan and silently drop winnable high-fan
            # races. Keep the prior exact plan's upcoming races when the exact
            # backend fails this turn.
            guard_applied = bool(fallback_used and prev_was_exact)
            if guard_applied:
                effective_plan = prev_plan
                effective_remaining = prev_remaining
            else:
                effective_plan = plan
                effective_remaining = remaining
                preset["extra_race_list"] = remaining
                preset["trackblazer_last_plan"] = plan
            reason = "race_result"
            if int(rank or 99) != 1:
                reason = "failed_race_result"
            elif str(race_type or "") != "solver_planned":
                reason = "external_race_result"
            try:
                stamina_now = int((weights.get("currentStats") or {}).get("stamina") or 0)
            except Exception:
                stamina_now = 0
            if self.race_planner:
                self.race_planner._push_replan_log({
                    "turn": cur_turn,
                    "reason": reason,
                    "backend": plan.get("solver"),
                    "fallback_used": fallback_used,
                    "fallback_reason": plan.get("fallback_reason"),
                    "guard_kept_prior_exact_plan": guard_applied,
                    "race_count": len(effective_remaining),
                    "new_solve_race_count": len(remaining),
                    "current_stamina": stamina_now,
                    "dropped_high_value_races": dropped_hv,
                    "program_id": int(program_id or 0),
                    "rank": int(rank or 99),
                    "history_rows": len(history),
                })
            with self.lock:
                self.status["last_smart_replan"] = {
                    "turn": int(turn or 0),
                    "reason": reason,
                    "program_id": int(program_id or 0),
                    "rank": int(rank or 99),
                    "race_type": str(race_type or ""),
                    "new_race_count": len(effective_remaining),
                    "solver": effective_plan.get("solver"),
                    "fallback_used": fallback_used,
                    "guard_kept_prior_exact_plan": guard_applied,
                    "dropped_high_value_races": dropped_hv,
                    "dead_epithets": effective_plan.get("dead_epithets") or [],
                    "projected_epithets": effective_plan.get("projected_epithets") or [],
                    "notes": effective_plan.get("notes") or [],
                    "history_rows": len(history),
                }
            guard_note = " [guard kept prior exact plan]" if guard_applied else ""
            self._log("smart_replan", turn, f"{reason} rank {rank} on {program_id}; {len(effective_remaining)} remaining race(s){guard_note}")
            return effective_plan
        except Exception as exc:
            self._log("smart_replan_failed", turn, str(exc))
            return None

    def _parse_race_rank(self, res):
        import base64
        import gzip
        import struct

        data = res.get("data", {})
        headers = res.get("data_headers", {})
        viewer_id = int(headers.get("viewer_id") or 0)

        race_start_info = data.get("race_start_info", {})
        horses = race_start_info.get("race_horse_data", [])

        player = next((horse for horse in horses if int(horse.get("viewer_id") or 0) == viewer_id), None)
        if not player:
            return 99

        frame_order = player.get("frame_order")
        if not frame_order:
            return 99

        result_index = frame_order - 1

        scenario_b64 = data.get("race_scenario")
        if not scenario_b64:
            return 99

        try:
            blob = gzip.decompress(base64.b64decode(scenario_b64))
        except Exception:
            return 99

        offset = 0

        if len(blob) < offset + 4: return 99
        header_len = struct.unpack_from("<i", blob, offset)[0]
        offset += 4 + header_len

        if len(blob) < offset + 16: return 99
        distance_diff_max, horse_num, horse_frame_size, horse_result_size = struct.unpack_from("<fiii", blob, offset)
        offset += 16

        if len(blob) < offset + 4: return 99
        pad_len = struct.unpack_from("<i", blob, offset)[0]
        offset += 4 + pad_len

        if len(blob) < offset + 8: return 99
        frame_count, frame_size = struct.unpack_from("<ii", blob, offset)
        offset += 8 + frame_count * frame_size

        if len(blob) < offset + 4: return 99
        pad_len = struct.unpack_from("<i", blob, offset)[0]
        offset += 4 + pad_len

        if not (0 <= result_index < horse_num):
            return 99

        if len(blob) < offset + (result_index + 1) * horse_result_size:
            return 99

        finish_order = struct.unpack_from("<i", blob, offset + result_index * horse_result_size)[0]

        return finish_order + 1

    def _running_style_for_race(self, preset, program_id, turn):
        bucket = None
        if self.race_planner and program_id:
            try:
                bucket = self.race_planner._distance_bucket(program_id)
            except Exception:
                bucket = None
        style = resolve_running_style_for_race(preset, bucket, turn, default=None)
        return int(style or 0)

    def _style_adaptation_enabled(self, preset):
        # The style-adaptation system is removed from the live race path by
        # default: the bot uses the preset running_style directly. Re-enable it
        # only if explicitly requested via mant_config.enable_style_adaptation.
        cfg = ((preset or {}).get("mant_config") or {})
        return bool(cfg.get("enable_style_adaptation", False))

    def _race_grade_for_retry(self, program_id):
        if not self.race_planner:
            return ""
        try:
            from career_bot import trackblazer_rules as tb_rules
            info = self.race_planner._program_info(program_id)
            return tb_rules.normalize_grade(info.get("grade") or info.get("race_instance_id"))
        except Exception:
            return ""

    def _is_debut_race(self, program_id, turn=0):
        """True if this is the debut (Make Debut / Maiden) race -- the one the
        user can reserve free continues for. Matched by race name (the program
        id varies by trainee/route), via the race planner's program metadata."""
        try:
            if self.race_planner and program_id:
                info = self.race_planner._program_info(int(program_id)) or {}
                name = str(info.get("name") or self.race_planner.label(program_id) or "").lower()
                if "make debut" in name or "maiden" in name or "debut" in name:
                    return True
        except Exception:
            pass
        return False

    def _race_retry_policy(self, preset, program_id, turn, attempts, *, free_clocks_available=0, is_mandatory=False):
        """Explain whether race continue retries are allowed for this race.

        v6.7.10: free continues are now always usable regardless of the
        Burn Clocks toggle.  They cost nothing -- skipping them when the
        user has burn_clocks=False was wasting a guaranteed second
        attempt at every race.  Paid clocks still require the toggle.

        v6.7.12: ``is_mandatory`` -- when a MANDATORY race is lost the
        whole career ends (or, with complete_career_on_failure=false,
        the bot would otherwise crash).  Spending paid clocks to rescue
        a mandatory race is almost always worth it even when burn_clocks
        is off for optional races.  So mandatory races may use paid
        clocks regardless of the toggle.  Users who genuinely never
        want paid clocks spent can still set
        ``disable_mandatory_race_clocks: true`` in mant_config.

        Returns a policy dict with:
          * ``enabled`` -- True if ANY retry (free or paid) may fire
          * ``free_only`` -- True if only free clocks are usable this
            attempt (paid are disabled by the toggle)
          * ``user_enabled`` -- the Burn Clocks toggle's value
          * ``disabled_reason`` -- empty if enabled, otherwise the
            specific reason ("burn_clocks_disabled_by_user" means paid
            clocks are blocked but free clocks may still fire)
        """
        cfg = ((preset or {}).get("mant_config") or {})
        policy = {
            "user_enabled": bool(self.burn_clocks),
            "enabled": False,
            "free_only": False,
            "is_mandatory": bool(is_mandatory),
            "program_id": int(program_id or 0),
            "turn": int(turn or 0),
            "attempt": int(attempts or 0),
            "max_retries": 0,
            "grade": self._race_grade_for_retry(program_id),
            "allowed_grades": [],
            "disabled_reason": "",
        }
        # v6.7.10: blanket overrides applied first regardless of free vs paid
        if cfg.get("disable_race_retries", False):
            policy["disabled_reason"] = "preset_disable_race_retries"
            return policy
        # v1.5: skip races the game has previously refused to continue (205/2507),
        # learned across careers -- don't waste an attempt + error log on them.
        if (cfg.get("enable_non_retryable_learning", True) and not is_mandatory
                and int(program_id or 0) in self._load_non_retryable()):
            policy["disabled_reason"] = "race_known_non_retryable"
            return policy
        try:
            max_retries = int(cfg.get("max_retries_per_race") if cfg.get("max_retries_per_race") is not None else 5)
        except Exception:
            max_retries = 5
        policy["max_retries"] = max(0, max_retries)
        if int(attempts or 0) >= max(0, max_retries):
            policy["disabled_reason"] = "max_retries_reached"
            return policy
        allowed = cfg.get("retry_race_grades") or ["G1"]   # android-style: G1 only (after debut)
        if isinstance(allowed, str):
            allowed = [part.strip() for part in allowed.split(",") if part.strip()]
        allowed_set = {str(item).upper() for item in allowed}
        policy["allowed_grades"] = sorted(allowed_set)
        # User spec: the Debut/Maiden race is ALWAYS retried on a loss, bypassing
        # the grade filter; every other non-mandatory race must be in the allowed
        # grades (default G1-only). Mandatory races also bypass the filter.
        is_debut = False
        try:
            is_debut = bool(self._is_debut_race(program_id, turn))
        except Exception:
            is_debut = False
        policy["is_debut"] = is_debut
        if not is_debut and allowed_set and policy["grade"] and policy["grade"] not in allowed_set and not is_mandatory:
            policy["disabled_reason"] = "grade_not_allowed"
            return policy
        # v6.7.12: mandatory-race paid-clock rescue.  A mandatory race
        # loss ends the career, so paid clocks are spent to rescue it
        # even when the Burn Clocks toggle is off for optional races --
        # unless the user explicitly opts out.
        if is_mandatory and not cfg.get("disable_mandatory_race_clocks", False):
            policy["enabled"] = True
            policy["mandatory_clock_rescue"] = True
            if not self.burn_clocks:
                policy["disabled_reason"] = "paid_clocks_via_mandatory_rescue"
            return policy
        # v1.5: graded extra-race retries default ON, decoupled from the Burn
        # Clocks toggle -- mirroring android, whose free "Try Again" re-runs any
        # lost G1/G2/G3 extra race by default (the main reason its win rate is
        # ~95% vs Icarus's ~83%).  At this point the race is retry-eligible
        # (grade allowed) and NOT mandatory; allow paid+free clocks up to
        # max_retries_per_race.  Disable via mant_config.retry_extra_races=false
        # (then it falls back to the Burn-Clocks/free-only behaviour below).
        if cfg.get("retry_extra_races", True) and not is_mandatory:
            policy["enabled"] = True
            policy["extra_race_retry"] = True
            if not self.burn_clocks:
                policy["disabled_reason"] = "paid_clocks_via_extra_race_retry"
            return policy
        # v6.7.10: at this point retries are allowed in principle.  Now
        # decide WHICH kinds (free, paid, or both) are usable.
        if not self.burn_clocks:
            # Paid clocks blocked by user.  Free clocks still usable.
            if int(free_clocks_available or 0) > 0:
                policy["enabled"] = True
                policy["free_only"] = True
                # disabled_reason is still set so the AI dataset can see
                # paid clocks were not in scope, but enabled is True.
                policy["disabled_reason"] = "burn_clocks_disabled_by_user_paid_only"
                return policy
            # No free clocks left AND paid clocks blocked.  Truly off.
            policy["disabled_reason"] = "burn_clocks_disabled_by_user"
            return policy
        policy["enabled"] = True
        return policy

    def _race_retry_allowed(self, preset, program_id, turn, attempts, *, free_clocks_available=0, is_mandatory=False):
        return bool(self._race_retry_policy(
            preset, program_id, turn, attempts,
            free_clocks_available=free_clocks_available,
            is_mandatory=is_mandatory,
        ).get("enabled"))

    def _race(self, client, state, preset, payload):
        if int((preset or {}).get("scenario_id") or (preset or {}).get("scenario") or 4) == 4:
            self.item_manager.recover_after_use_error = False
            state, used = self.item_manager.handle_pre_race(client, state, preset, payload, self.status, self.race_planner)
            for event in self.item_manager.use_attempt_events:
                self._debug("items_use_attempt", state, {
                    "selected": event.get("selected") or [],
                    "attempt": event.get("attempt") or [],
                    "payload": event.get("payload") or [],
                    "result": self._api_result(event.get("result") or {}),
                })
            if self.item_manager.recover_after_use_error:
                state = self._fresh_career_state(client, payload.get("_strategy"))
                self._debug_turn(state, preset)
                return state
            if used > 0:
                with self.lock:
                    self.status["items_used"] += used
                    self._log_locked("items_use", payload["current_turn"], f"pre-race {used}")

        program_id = payload.get("program_id")
        current_turn = payload["current_turn"]
        strategy = payload.get("_strategy")
        # v6.7.12: forced races are mandatory -- losing one ends the
        # career.  This flag opts the retry policy into paid-clock
        # rescue even when burn_clocks is off for optional races.
        is_mandatory_race = bool(payload.get("_forced_race"))

        base_running_style = self._running_style_for_race(preset, program_id, current_turn)
        style_decision = {}
        running_style = base_running_style
        if self._style_adaptation_enabled(preset):
            try:
                race_summary_for_style = self._race_program_summary(program_id, rank=None, turn=current_turn)
                race_summary_for_style["performance_hint"] = self._official_performance_hint(
                    program_id,
                    chara=((state or {}).get("data") or {}).get("chara_info") or {},
                    running_style=base_running_style,
                )
                style_context = style_adaptation.build_style_context(
                    self.base_dir,
                    state or {},
                    {**(preset or {}), "burn_clocks": bool(self.burn_clocks)},
                    race_summary_for_style,
                    base_running_style,
                    current_turn,
                )
                style_context["run_id"] = self.status.get("run_id") or style_context.get("run_id") or ""
                style_decision = style_adaptation.decide_style(self.base_dir, style_context)
                style_adaptation.record_decision(self.base_dir, style_decision)
                running_style = int(style_decision.get("applied_style") or base_running_style or 0)
                self._debug("style_adaptation_decision", state, {
                    "decision_id": style_decision.get("decision_id"),
                    "mode": style_decision.get("mode"),
                    "base_user_style": style_decision.get("base_user_style"),
                    "recommended_style": style_decision.get("recommended_style"),
                    "applied_style": style_decision.get("applied_style"),
                    "style_changed": style_decision.get("style_changed"),
                    "confidence": style_decision.get("confidence"),
                    "expected_reward_delta": style_decision.get("expected_reward_delta"),
                    "reason_flags": (style_decision.get("reason_flags") or [])[:8],
                })
                with self.lock:
                    self.status["last_style_adaptation"] = {
                        "turn": int(current_turn or 0),
                        "program_id": int(program_id or 0),
                        "mode": style_decision.get("mode"),
                        "base_user_style": style_decision.get("base_user_style"),
                        "recommended_style": style_decision.get("recommended_style"),
                        "applied_style": style_decision.get("applied_style"),
                        "style_changed": style_decision.get("style_changed"),
                        "confidence": style_decision.get("confidence"),
                        "expected_reward_delta": style_decision.get("expected_reward_delta"),
                    }
            except Exception as exc:
                self._log("style_adaptation_failed", current_turn, str(exc))
                running_style = base_running_style

        # NOTE: race_entry's running_style param is IGNORED by the server. The style
        # is set via single_mode_free/change_running_style, which is only valid AFTER
        # race_entry and BEFORE race_start (see below) -> doing it here would 102.
        try:
            if running_style in (1, 2, 3, 4):
                entry = client.race_entry(program_id=program_id, current_turn=current_turn, running_style=running_style)
            else:
                entry = client.race_entry(program_id=program_id, current_turn=current_turn)
        except Exception as exc:
            # 205/208 on race_entry can still mean the server accepted the race.
            # Reload and reconcile before marking the program as rejected.
            if any(err in str(exc) for err in ("205", "208")):
                fresh = self._fresh_career_state(client, strategy)
                fresh_data = fresh.get("data") or {}
                fresh_chara = fresh_data.get("chara_info") or {}
                in_race = int(fresh_chara.get("playing_state") or 0) in {2, 3, 4, 5} or bool(fresh_data.get("race_start_info"))
                if in_race:
                    self._log("race_entry_reconciled", current_turn, f"{program_id} entered despite error, resuming")
                else:
                    if self.race_planner:
                        self.race_planner.reject(current_turn, program_id)
                    self._log("race_reject", current_turn, program_id)
                return fresh
            if self._is_recoverable_error(exc):
                self._log("race_entry_recover", current_turn, str(exc))
                return self._recover_with_backoff(client, strategy, exc)
            raise
        self._log("race_entry", current_turn, program_id)
        if strategy:
            entry_data = entry.get("data") or {}
            if entry_data.get("unchecked_event_array"):
                entry = self._drain_events(client, strategy, entry)
        
        race_start_info = (entry.get("data") or {}).get("race_start_info") or {}
        # STEP 3 (Trackblazer engine): prediction gate. Only race if our in-game
        # prediction is strong (double-star). For an optional race with a weak
        # prediction, back out (race_out) + reject it so the strategy re-decides
        # this turn (skips the rejected race -> picks another or trains).
        if payload.get("_trackblazer_prediction_gate") and not payload.get("_forced_race") and race_start_info:
            from career_bot.scenarios.mant_trackblazer import trackblazer_is_strong_prediction
            gate_chara = ((state or {}).get("data") or {}).get("chara_info") or {}
            if not trackblazer_is_strong_prediction(race_start_info, gate_chara, preset):
                self._log("trackblazer_prediction_skip", current_turn, f"{program_id} weak prediction -> back out + re-decide")
                try:
                    client.race_out(current_turn=current_turn)
                except Exception as exc:
                    if not any(e in str(exc) for e in ("102", "201", "StateRecoveryError")):
                        raise
                if self.race_planner:
                    self.race_planner.reject(current_turn, program_id)
                return self._fresh_career_state(client, strategy)
        if style_decision.get("decision_id") and race_start_info:
            try:
                style_obs = style_adaptation.record_observation(self.base_dir, style_decision.get("decision_id"), race_start_info, state=state)
                self._debug("style_adaptation_observation", state, {
                    "decision_id": style_decision.get("decision_id"),
                    "opponent_style_counts": style_obs.get("opponent_style_counts") or {},
                    "entry_count": style_obs.get("entry_count") or 0,
                })
            except Exception as exc:
                self._log("style_adaptation_observation_failed", current_turn, str(exc))

        # Set the running style now that the race is entered (valid window:
        # after race_entry, before race_start). Only when it differs from the
        # trainee's current persistent style. program_id identifies the entered race.
        if running_style in (1, 2, 3, 4):
            try:
                _crs_chara = ((state or {}).get("data") or {}).get("chara_info") or {}
                _cur_style = int(_crs_chara.get("race_running_style") or 0)
                if _cur_style != running_style:
                    client.change_running_style(current_turn=current_turn, running_style=running_style, program_id=program_id)
                    self._log("change_running_style", current_turn, f"{_cur_style} -> {running_style}")
            except Exception as exc:
                self._log("change_running_style_failed", current_turn, str(exc))

        is_short = 1
        try:
            res = client.race_start(is_short=is_short, current_turn=current_turn)
            self._log("race_start", current_turn, f"short {is_short}")
        except Exception as exc:
            if self._is_recoverable_error(exc):
                self._log("race_start_recover", current_turn, str(exc))
                return self._recover_with_backoff(client, strategy, exc)
            raise

        rank = self._parse_race_rank(res)
        initial_rank = int(rank or 99)
        self._log("race_rank", current_turn, f"rank {rank}")

        home_info = (state.get("data") or {}).get("home_info") or {}
        std_clocks = int(home_info.get("available_continue_num", 0))
        free_clocks = self._free_continue_count(home_info)
        # v1.5: option to reserve the limited free continues for the debut race
        # only. On any other race the bot would just burn the one free retry (or
        # trip the game's continue-refused error). Paid clocks still follow the
        # normal retry policy (burn_clocks / retry_extra_races).
        if (((preset or {}).get("mant_config") or {}).get("free_retries_debut_only", False)
                and free_clocks > 0 and not self._is_debut_race(program_id, current_turn)):
            free_clocks = 0
        clocks_available_before = std_clocks + free_clocks
        retry_events = []

        # Carats (opt-in) + the per-career clock budget come from the Burn-Clocks
        # UI (the single source of truth), set at career start — NOT the preset.
        # When out of free + standard clocks, spend carats to continue
        # (continue_type 2) IF carats are enabled. Never in free_only mode.
        carat_on = bool(self.carats_enabled)
        carat_cap = 0   # carats unlimited when enabled; PAID CLOCKS are what's
                        # bounded, via max_clocks_per_career below.
        carat_used_career = int(self.status.get("carat_retries_used") or 0)
        carat_used_here = 0
        clock_budget = int(self.max_clocks_per_career or 0)   # 0 = unlimited paid clocks/career
        paid_clocks_used = 0

        retry_attempts = 0
        retry_policy = self._race_retry_policy(
            preset, program_id, current_turn, retry_attempts,
            free_clocks_available=free_clocks,
            is_mandatory=is_mandatory_race,
        )

        def _carats_available():
            if not carat_on or retry_policy.get("free_only"):
                return False
            return carat_cap <= 0 or (carat_used_career + carat_used_here) < carat_cap

        while rank > 1 and retry_policy.get("enabled") and (
                std_clocks > 0 or free_clocks > 0 or _carats_available()):
            # v6.7.10: in free_only mode, abort the loop the moment free
            # clocks run out -- paid clocks must not be spent.
            if retry_policy.get("free_only") and free_clocks <= 0:
                break
            # Per-career PAID-clock budget (max clocks per career): once hit, stop
            # spending standard clocks. Free continues and carats are not counted
            # against it; carats (if enabled) may still continue past the cap.
            if clock_budget > 0 and free_clocks <= 0 and paid_clocks_used >= clock_budget:
                std_clocks = 0
            using_carat = free_clocks <= 0 and std_clocks <= 0
            if using_carat and not _carats_available():
                break
            retry_attempts += 1
            clocks_left = std_clocks + free_clocks
            continue_type = 1 if free_clocks > 0 else 2
            
            self._log("race_clock", current_turn, f"rank {rank}, using clock ({clocks_left} left, type {continue_type})...")
            retry_row = {
                "attempt": retry_attempts,
                "rank_before": int(rank or 99),
                "clocks_left_before": int(clocks_left),
                "standard_clocks_before": int(std_clocks),
                "free_clocks_before": int(free_clocks),
                "continue_type": int(continue_type),
                "policy": dict(retry_policy),
            }
            try:
                cont_res = client.race_continue(current_turn=current_turn, continue_type=continue_type)
                
                cont_data = cont_res.get("data") or {}
                new_home_info = cont_data.get("home_info")
                if isinstance(new_home_info, dict):
                    std_clocks = int(new_home_info.get("available_continue_num", 0))
                    free_clocks = self._free_continue_count(new_home_info)
                else:
                    if free_clocks > 0:
                        free_clocks -= 1
                    elif std_clocks > 0:
                        std_clocks -= 1
                    # else: carat-funded retry -- no clock to decrement

                if strategy:
                    if cont_data.get("unchecked_event_array"):
                        self._drain_events(client, strategy, cont_res)
                
                roll = dna_gauss(0.166 + client.api_jitter, 0.05)
                dna_sleep(0.1, 0.45, 0.166 + client.api_jitter, 0.05)
                res = client.race_start(is_short=is_short, current_turn=current_turn)
                rank = self._parse_race_rank(res)
                retry_row.update({
                    "rank_after": int(rank or 99),
                    "standard_clocks_after": int(std_clocks),
                    "free_clocks_after": int(free_clocks),
                    "success": int(rank or 99) == 1,
                    "carat_retry": bool(using_carat),
                })
                if using_carat:
                    carat_used_here += 1
                    with self.lock:
                        self.status["carat_retries_used"] = carat_used_career + carat_used_here
                    cap_str = "unlimited" if carat_cap <= 0 else str(carat_cap)
                    self._log("race_carat_retry", current_turn,
                              f"spent carats for retry ({carat_used_career + carat_used_here}/{cap_str} this career)")
                retry_events.append(retry_row)
                self._log("race_rank_retry", current_turn, f"rank {rank} after clock")
                with self.lock:
                    self.status["clocks_used"] = int(self.status.get("clocks_used") or 0) + 1
                if continue_type == 2 and not using_carat:
                    paid_clocks_used += 1   # counts against max_clocks_per_career
                retry_policy = self._race_retry_policy(
                    preset, program_id, current_turn, retry_attempts,
                    free_clocks_available=free_clocks,
                    is_mandatory=is_mandatory_race,
                )
            except Exception as e:
                # v6.7.13: a 205 result on continue means the server
                # won't allow a retry for THIS race -- the Trackblazer
                # finale races (Twinkle Star Climax) don't support the
                # standard clock-continue mechanism, so the server
                # rejects the continue with 205.  Recognize that and
                # stop immediately rather than burning the rest of the
                # retry budget (and rather than logging it as a generic
                # failure).  208 (server busy) is transient and the
                # client already retries it internally, so a 208 that
                # bubbles up here is also terminal for this attempt.
                err_str = str(e)
                if "205" in err_str or "2507" in err_str:
                    code = "2507" if "2507" in err_str else "205"
                    # v1.5: remember this race rejects continues so future
                    # careers skip the attempt entirely (the policy early-out).
                    if (preset or {}).get("mant_config", {}).get("enable_non_retryable_learning", True) is not False:
                        self._mark_non_retryable(program_id, code)
                    retry_row.update({"error": err_str, "success": False,
                                      "continue_unavailable": True})
                    retry_events.append(retry_row)
                    self._log(
                        "race_continue_unavailable", current_turn,
                        f"server rejected continue ({code}) -- this race does not "
                        "support retries; recorded as non-retryable, will skip next time",
                    )
                    break
                retry_row.update({"error": err_str, "success": False})
                retry_events.append(retry_row)
                self._log("race_clock_failed", current_turn, err_str)
                break

        final_retry_policy = self._race_retry_policy(
            preset, program_id, current_turn, retry_attempts,
            free_clocks_available=free_clocks,
            is_mandatory=is_mandatory_race,
        )
        if rank <= 1:
            final_retry_policy = dict(final_retry_policy)
            final_retry_policy.setdefault("disabled_reason", "race_won")
        clock_summary = {
            "user_enabled": bool(self.burn_clocks),
            "enabled": bool(self.burn_clocks),
            "policy": final_retry_policy,
            "available_before": int(clocks_available_before),
            "standard_available_before": int(home_info.get("available_continue_num", 0)),
            "free_available_before": self._free_continue_count(home_info),
            "attempts": int(retry_attempts),
            "used": int(len([r for r in retry_events if not r.get("error")])),
            "initial_rank": int(initial_rank or 99),
            "final_rank": int(rank or 99),
            "won_before_retry": int(initial_rank or 99) == 1,
            "won_after_retry": int(initial_rank or 99) > 1 and int(rank or 99) == 1 and bool(retry_events),
            "retry_events": retry_events,
        }
        race_type = self._classify_race_type(preset or {}, payload or {}, program_id, current_turn)
        race_chara = ((state or {}).get("data") or {}).get("chara_info") or {}
        stats_snapshot = self._turn_stats(race_chara)
        trainee_id = race_chara.get("card_id") or race_chara.get("chara_id") or ""
        self._record_race_result(
            program_id,
            rank,
            current_turn,
            race_type=race_type,
            stats=stats_snapshot,
            preset_name=(preset or {}).get("name", ""),
            trainee_id=trainee_id,
            clock_retry=clock_summary,
            chara=race_chara,
            running_style=running_style,
            style_decision=style_decision,
        )
        if style_decision.get("decision_id"):
            try:
                style_outcome = style_adaptation.record_outcome(
                    self.base_dir,
                    style_decision,
                    {"program_id": program_id, "rank": rank, "final_rank": rank},
                    clock_retry=clock_summary,
                    epithet_delta={"source": "solver_live_state", "completed": [], "failed": []},
                )
                self._debug("style_adaptation_outcome", state, {
                    "decision_id": style_decision.get("decision_id"),
                    "reward": style_outcome.get("reward"),
                    "final_rank": style_outcome.get("final_rank"),
                    "clocks_used": style_outcome.get("clocks_used"),
                    "won_after_clock": style_outcome.get("won_after_clock"),
                })
            except Exception as exc:
                self._log("style_adaptation_outcome_failed", current_turn, str(exc))
        try:
            self._debug("race_clock_summary", state, clock_summary)
        except Exception:
            pass
        self._maybe_replan_smart_races_after_result(preset or {}, state, program_id, rank, current_turn, race_type)

        if strategy:
            res_data = res.get("data") or {}
            if res_data.get("unchecked_event_array"):
                res = self._drain_events(client, strategy, res)

        out = res
        try:
            client.race_end(current_turn=current_turn)
            self._log("race_end", current_turn, "")
        except Exception as e:
            if any(err in str(e) for err in ("102", "1503")):
                self._log("race_end_reconciled", current_turn, "server already done (102)")
            elif self._is_recoverable_error(e):
                self._log("race_end_recover", current_turn, str(e))
                return self._recover_with_backoff(client, strategy, e)
            else:
                raise

        try:
            out_res = client.race_out(current_turn=current_turn)
            out = out_res
            if strategy:
                out_data = out.get("data") or {}
                if out_data.get("unchecked_event_array"):
                    out = self._drain_events(client, strategy, out)
        except Exception as e:
            if any(err in str(e) for err in ("102", "1503")):
                self._log("race_out_reconciled", current_turn, "server already done (102)")
            elif self._is_recoverable_error(e):
                self._log("race_out_recover", current_turn, str(e))
                return self._recover_with_backoff(client, strategy, e)
            else:
                raise

        cfg = ((preset or {}).get("mant_config") or {})
        if rank > 1 and payload.get("_forced_race") and not cfg.get("complete_career_on_failure", True):
            # v6.7.12: a mandatory race loss used to raise a fatal
            # RuntimeError that crashed the whole runner and left the
            # career half-finished.  But for the Trackblazer FINALE
            # races (the Twinkle Star Climax at turns 73-78), the
            # career is already over -- there's nothing left to do but
            # accept the result and write the career summary.  Crashing
            # there throws away the entire career's progress.
            #
            # New behavior:
            #   * Finale races (turn >= 73): never crash.  Log the loss,
            #     mark the career as completed-with-loss, and return
            #     normally so the runner finishes gracefully and writes
            #     the career report with whatever fans/stats were earned.
            #   * Non-finale mandatory races (turn < 73) with
            #     complete_career_on_failure=false: still stop the
            #     career, but via a clean "career_failed" status rather
            #     than an exception, so the report is still written and
            #     the loop ends without a stack trace.
            is_finale = int(current_turn or 0) >= 73
            with self.lock:
                self.status["last_mandatory_failure"] = {
                    "turn": int(current_turn or 0),
                    "rank": int(rank or 99),
                    "program_id": int(program_id or 0),
                    "is_finale": is_finale,
                }
            if is_finale:
                self._log(
                    "finale_race_lost", current_turn,
                    f"finale race finished rank {rank}; accepting result and completing career",
                )
                # Fall through to ``return out`` -- the career is over,
                # the runner's normal finish path will write the report.
                return out
            # Non-finale mandatory loss: end the career cleanly without
            # an exception.  Mark status so the runner loop can detect
            # the terminal state.
            self._log(
                "mandatory_race_lost", current_turn,
                f"mandatory race finished rank {rank}; stopping career (complete_career_on_failure=false)",
            )
            with self.lock:
                self.status["career_stopped_reason"] = (
                    f"mandatory_race_failed_turn_{current_turn}_rank_{rank}"
                )
            # Returning the race output lets the caller proceed; the
            # runner checks ``career_stopped_reason`` after the race
            # step and ends the loop gracefully (no stack trace, report
            # still written).
            return out

        return out

    def _race_progress(self, client, payload):
        current_turn = payload["current_turn"]
        phase = payload.get("phase")
        chara = (payload.get("chara_info") or {})
        playing_state = chara.get("playing_state") or 0

        def _safe_state(result):
            # race_out can return an event/race payload without chara_info.
            # Refresh before returning to the main decision loop.
            if isinstance(result, dict) and (result.get("data") or {}).get("chara_info"):
                return result
            return self._fresh_career_state(client, None)
        if playing_state not in {2, 3, 4, 5}:
            self._log("race_skip", current_turn, f"not in race (state={playing_state})")
            return _safe_state(payload)
        
        if phase == "end":
            if playing_state in {1}:
                self._log("race_end_skip", current_turn, "resume already home")
            else:
                try:
                    client.race_end(current_turn=current_turn)
                    self._log("race_end", current_turn, "resume")
                except Exception as e:
                    if any(err in str(e) for err in ("102", "1503")):
                        self._log("race_end_reconciled", current_turn, "resume already done (102)")
                    else:
                        raise
            try:
                return _safe_state(client.race_out(current_turn=current_turn))
            except Exception as e:
                if any(err in str(e) for err in ("102", "1503", "201", "StateRecoveryError")):
                    self._log("race_out_reconciled", current_turn, f"graceful exit: {e}")
                    return _safe_state(payload)
                if self._is_recoverable_error(e):
                    self._log("race_out_recover", current_turn, str(e))
                    return self._recover_with_backoff(client, None, e)
                raise
        if phase == "out":
            self._log("race_out", current_turn, "resume")
            try:
                return _safe_state(client.race_out(current_turn=current_turn))
            except Exception as e:
                if any(err in str(e) for err in ("102", "1503", "201", "StateRecoveryError")):
                    self._log("race_out_reconciled", current_turn, f"graceful exit: {e}")
                    return _safe_state(payload)
                if self._is_recoverable_error(e):
                    self._log("race_out_recover", current_turn, str(e))
                    return self._recover_with_backoff(client, None, e)
                raise
        try:
            client.race_start(is_short=1, current_turn=current_turn)
            self._log("race_start", current_turn, "resume")
        except Exception as e:
            if any(err in str(e) for err in ("102", "1503")):
                self._log("race_start_reconciled", current_turn, f"resume already done: {e}")
                return _safe_state(payload)
            if self._is_recoverable_error(e):
                self._log("race_start_recover", current_turn, str(e))
                return self._recover_with_backoff(client, None, e)
            raise
        if playing_state in {1}:
            self._log("race_end_skip", current_turn, "resume already home")
        else:
            try:
                client.race_end(current_turn=current_turn)
                self._log("race_end", current_turn, "resume")
            except Exception as e:
                if any(err in str(e) for err in ("102", "1503")):
                    self._log("race_end_reconciled", current_turn, "resume already done (102)")
                elif self._is_recoverable_error(e):
                    self._log("race_end_recover", current_turn, str(e))
                    return self._recover_with_backoff(client, None, e)
                else:
                    raise
        try:
            return _safe_state(client.race_out(current_turn=current_turn))
        except Exception as e:
            if any(err in str(e) for err in ("102", "1503", "201", "StateRecoveryError")):
                self._log("race_out_reconciled", current_turn, f"graceful exit: {e}")
                return _safe_state(payload)
            if self._is_recoverable_error(e):
                self._log("race_out_recover", current_turn, str(e))
                return self._recover_with_backoff(client, None, e)
            raise

    def _buy_skills(self, client, state, preset, force):
        self.skill_buyer.recover_after_error = False
        state, bought = self.skill_buyer.buy(client, state, preset, force)
        for event in self.skill_buyer.attempt_events:
            self._debug("skills_attempt", state, {
                "selected": event.get("selected") or [],
                "attempt": event.get("attempt") or [],
                "selected_total_cost": self._sum_cost(event.get("selected") or []),
                "attempt_total_cost": self._sum_cost(event.get("attempt") or []),
                "payload": event.get("payload") or [],
                "result": self._api_result(event.get("result") or {}),
            })
        if self.skill_buyer.recover_after_error:
            try:
                state = self._fresh_career_state(client)
                self._debug_turn(state, preset)
            except Exception as e:
                print(f"Skill phase reload failure: {e}")
                pass
        if bought:
            with self.lock:
                self.status["skills_bought"] += bought
                self.status["last_action"] = f"skills {bought}"
                self._log_locked("skills", (state.get("data") or {}).get("chara_info", {}).get("turn", 0), bought)
        return state


    def _inject_runner_context(self, state):
        """Expose runner-only context to strategies without changing API payloads."""
        try:
            data = state.setdefault("data", {})
            data["action_history"] = list(self.status.get("action_history") or [])
            data["race_history"] = list(self.status.get("race_results") or [])
            data["runner_context"] = {
                "burn_clocks": bool(self.burn_clocks),
                "clock_retry_policy": {
                    "user_enabled": bool(self.burn_clocks),
                    "enabled": bool(self.burn_clocks),
                    "source": "runner_context",
                },
                "clocks_used": int(self.status.get("clocks_used") or 0),
                "clocks_left": int(self.status.get("clocks_left") or 0),
                "race_results": list(self.status.get("race_results") or []),
                "race_history": list(self.status.get("race_results") or []),
                "runtime_support": self._runtime_support_for_solver(),
                "last_smart_replan": dict(self.status.get("last_smart_replan") or {}),
                "replan_log": list(getattr(self.race_planner, "replan_log", []) or []),
            }
        except Exception:
            pass

    def _handle_items(self, client, state, preset, best_command, decision=None):
        if int((preset or {}).get("scenario_id") or (preset or {}).get("scenario") or 4) != 4:
            return state
        self.item_manager.recover_after_exchange_error = False
        self.item_manager.recover_after_use_error = False
        item_status = dict(self.status or {})
        data = (state or {}).get("data") or {}
        item_status["current_chara"] = data.get("chara_info") or {}
        if decision is not None and isinstance(best_command, dict):
            best_command = dict(best_command)
            best_command["_decision_reason"] = str(getattr(decision, "reason", "") or "")
            if (getattr(decision, "payload", {}) or {}).get("_irregular_training"):
                best_command["_irregular_training"] = True
        state, bought, used = self.item_manager.handle(client, state, preset, best_command, item_status, self.race_planner)
        for event in self.item_manager.buy_attempt_events:
            self._debug("items_buy_attempt", state, {
                "selected": event.get("selected") or [],
                "attempt": event.get("attempt") or [],
                "selected_total_cost": self._sum_cost(event.get("selected") or []),
                "attempt_total_cost": self._shop_attempt_cost(event.get("attempt") or [], event.get("selected") or []),
                "payload": event.get("payload") or [],
                "result": self._api_result(event.get("result") or {}),
            })
        for event in self.item_manager.use_attempt_events:
            self._debug("items_use_attempt", state, {
                "selected": event.get("selected") or [],
                "attempt": event.get("attempt") or [],
                "payload": event.get("payload") or [],
                "result": self._api_result(event.get("result") or {}),
            })
        if self.item_manager.recover_after_exchange_error or self.item_manager.recover_after_use_error:
            try:
                state = self._fresh_career_state(client)
                self._debug_turn(state, preset)
            except Exception as e:
                print(f"Item phase reload failure: {e}")
                pass
        if bought or used:
            turn = (state.get("data") or {}).get("chara_info", {}).get("turn", 0)
            with self.lock:
                self.status["items_bought"] += bought
                self.status["items_used"] += used
                if bought:
                    self._log_locked("items_buy", turn, bought)
                if used:
                    self._log_locked("items_use", turn, used)
        return state

    def _merge_state(self, old_state, new_state):
        if not old_state:
            return new_state
        merged = dict(old_state)
        merged["data"] = dict(old_state.get("data") or {})
        for k, v in (new_state.get("data") or {}).items():
            if isinstance(v, dict) and k in merged["data"] and isinstance(merged["data"][k], dict):
                merged_sub = dict(merged["data"][k])
                for sub_k, sub_v in v.items():
                    if sub_v is not None:
                        merged_sub[sub_k] = sub_v
                merged["data"][k] = merged_sub
            else:
                merged["data"][k] = v
        return merged

    def _command_from_decision(self, state, decision):
        payload = decision.payload or {}
        command_type = int(payload["command_type"])
        command_id = int(payload["command_id"])
        command_group_id = int(payload.get("command_group_id", 0))
        for cmd in ((state.get("data") or {}).get("home_info") or {}).get("command_info_array") or []:
            if int(cmd.get("command_type") or 0) != command_type:
                continue
            if command_type == 3 and int(cmd.get("command_id") or 0) == command_group_id:
                return cmd
            if int(cmd.get("command_id") or 0) == command_id:
                return cmd
        return payload

    def _apply_authoritative_scorer_override(self, state, decision):
        """v6.3: when the active character profile is in ``authoritative``
        mode, replace the strategy engine's chosen training command with
        the v6.1 scorer's top pick.

        Hint mode (the default) is unaffected -- only profiles that have
        been explicitly promoted via ``training_scorer_mode: "authoritative"``
        in their JSON file (or per-scenario override) trigger the override.

        v6.7.5: this is now called at the actual execution point so the
        mutation reaches ``_record_action`` and ``exec_command``.  We also
        clear ``last_scorer_override`` for the current turn at the start
        of the call so that turns where the override does NOT fire don't
        inherit a stale entry from an earlier turn.

        The override is conservative:
          - only runs when decision.action == ``"command"`` AND the chosen
            command is a training (command_type == 1)
          - requires the scorer to find a positive-scoring pick
          - requires the new pick to differ from the strategy's pick by a
            non-trivial margin (>= 10% of the runner-up score) to avoid
            chasing noise
          - records the override into status so the dashboard can show
            what was swapped and why
        """
        try:
            payload = decision.payload or {}
            current_turn = int(payload.get("current_turn") or 0)
            # Clear any stale override entry from a previous turn before
            # deciding whether this turn produces a new one.
            with self.lock:
                prev = self.status.get("last_scorer_override") or {}
                if prev and int(prev.get("turn") or 0) != current_turn:
                    self.status["last_scorer_override"] = None
            if int(payload.get("command_type") or 0) != 1:
                return  # not a training command -- nothing to override

            data = state.get("data") or {}
            chara = data.get("chara_info") or {}
            home = data.get("home_info") or {}
            if not home.get("command_info_array"):
                return

            from career_bot import character_profiles, training_scorer

            profile = character_profiles.resolve_profile(
                card_id=chara.get("card_id") or 0,
                chara_id=chara.get("chara_id") or 0,
                scenario_id=int(self.status.get("scenario_id") or 4),
                base_dir=self.base_dir,
                preset_name=str((self.status.get("preset_name") or "")),
                chara_info=chara,
            )
            if profile.training_scorer_mode != "authoritative":
                return

            cfg = profile.training_scorer_config()
            cfg.goal_lookahead = bool(getattr(self, "goal_lookahead", False))
            cfg = training_scorer.adapt_stamina_targets(
                cfg, chara, enabled=bool(getattr(profile, "adapt_targets_to_inheritance", False)),
                turn=int(chara.get("turn") or 0))
            scores = training_scorer.score_trainings(home, chara, config=cfg)
            if not scores or scores[0].score <= 0:
                return  # scorer didn't find anything positive

            scorer_pick = scores[0]
            strategy_id = int(payload.get("command_id") or 0)
            if scorer_pick.command_id == strategy_id:
                return  # already agree

            # Margin gate: require the new pick to beat the strategy's pick
            # by at least 10% of the runner-up score in our own ranking.
            # Without this gate any +1 difference could cause flapping.
            # v6.7.9: the multiplier (default 0.10) and absolute floor
            # (default 1.0) are now configurable via the profile's
            # training_scorer_overrides so users in authoritative mode
            # can tune how aggressively the override fires.
            ts_overrides = (profile.training_scorer_overrides or {})
            margin_pct = float(ts_overrides.get("override_margin_pct", 0.10))
            margin_floor = float(ts_overrides.get("override_margin_floor", 1.0))
            strategy_score = next(
                (s.score for s in scores if s.command_id == strategy_id),
                0.0,
            )
            margin = scorer_pick.score - strategy_score
            min_margin = max(margin_floor, scores[-1].score * margin_pct if len(scores) > 1 else margin_floor)
            if margin < min_margin:
                # v6.7.9: record the BLOCKED override so the dashboard
                # reasoning can explain why the scorer's disagreement
                # didn't translate into a swap.  Without this, users in
                # authoritative mode saw "scorer would have picked X"
                # with no explanation that the margin gate killed the
                # override.
                with self.lock:
                    self.status["last_scorer_override_blocked"] = {
                        "turn": int(chara.get("turn") or 0),
                        "from_command_id": strategy_id,
                        "from_stat": (next((s.stat_name for s in scores if s.command_id == strategy_id), "") or "").lower(),
                        "to_command_id": int(scorer_pick.command_id),
                        "to_stat": scorer_pick.stat_name.lower(),
                        "margin": round(margin, 4),
                        "min_margin": round(min_margin, 4),
                        "reason": "margin_below_threshold",
                    }
                return

            # Override the decision payload's command_id.  command_type
            # stays 1 (still a training command).  command_group_id is
            # left untouched -- the scorer picks within the same train
            # category space.
            original_id = strategy_id
            payload["command_id"] = int(scorer_pick.command_id)
            decision.payload = payload
            new_reason = (
                (decision.reason or "")
                + f" | v6.3 scorer override: {original_id} -> {scorer_pick.command_id} "
                f"({scorer_pick.stat_name}, margin {margin:.2f})"
            )
            decision.reason = new_reason.strip(" |")

            with self.lock:
                self.status["last_scorer_override"] = {
                    "turn": int(chara.get("turn") or 0),
                    "profile_id": profile.profile_id,
                    "from_command_id": original_id,
                    "to_command_id": scorer_pick.command_id,
                    "to_stat": scorer_pick.stat_name,
                    "scorer_top_score": round(scorer_pick.score, 4),
                    "strategy_pick_score": round(strategy_score, 4),
                    "margin": round(margin, 4),
                }
        except Exception:
            # Authoritative override is best-effort.  Any failure must
            # leave the strategy engine's decision unmodified.
            pass

    def _track_turn_scores(self, state):
        data = state.get("data") or {}
        chara = data.get("chara_info") or {}
        turn = int(chara.get("turn") or 0)
        home = data.get("home_info") or {}
        commands = home.get("command_info_array") or []
        max_score = 0
        has_training = False
        for cmd in commands:
            if int(cmd.get("command_type") or 0) == 1:
                has_training = True
                score = self.item_manager._command_stat_gain(cmd)
                if score > max_score:
                    max_score = score
        if has_training:
            with self.lock:
                dh = self.status.setdefault("date_history", [])
                sh = self.status.setdefault("score_history", [])
                if not dh or dh[-1] != turn:
                    dh.append(turn)
                    sh.append(max_score)
                    if len(dh) > 48:
                        dh.pop(0)
                        sh.pop(0)

        # v6.1: publish Android-equivalent training scores as a HINT.
        # v6.2: resolve the active character profile so the scorer uses
        # per-character stat priorities, distance-specific targets, and the
        # right scenario-tuned weights instead of one-size-fits-all defaults.
        # The strategy engine still makes the authoritative decision in
        # profiles whose ``training_scorer_mode`` is ``"hint"`` (the default
        # for fresh profiles); flipping a profile to ``"authoritative"``
        # promotes its scorer to drive the decision -- the wire-in for that
        # path lives in the strategy engine, this hint stays read-only.
        if has_training:
            try:
                from career_bot import training_scorer  # local import to avoid cycles
                from career_bot import character_profiles
                card_id = chara.get("card_id") or 0
                chara_id = chara.get("chara_id") or 0
                scenario_id = int(self.status.get("scenario_id") or 0)
                preset_name = self.status.get("preset_name") or ""
                profile = character_profiles.resolve_profile(
                    card_id=card_id,
                    chara_id=chara_id,
                    scenario_id=scenario_id,
                    base_dir=self.base_dir,
                    preset_name=preset_name,
                    chara_info=chara,
                )
                cfg = profile.training_scorer_config()
                cfg.goal_lookahead = bool(getattr(self, "goal_lookahead", False))
                cfg = training_scorer.adapt_stamina_targets(
                    cfg, chara, enabled=bool(getattr(profile, "adapt_targets_to_inheritance", False)),
                    turn=int(chara.get("turn") or 0))
                scores = training_scorer.score_trainings(home, chara, config=cfg)
                hint = {
                    "turn": turn,
                    "scorer_version": "v6.2",
                    "authoritative": profile.training_scorer_mode == "authoritative",
                    "mode": profile.training_scorer_mode,
                    "profile_id": profile.profile_id,
                    "profile_display_name": profile.display_name,
                    "matched_via": profile.matched_via,
                    "best_command_id": scores[0].command_id if scores else 0,
                    "best_stat": scores[0].stat_name if scores else "",
                    "best_score": round(scores[0].score, 4) if scores else 0.0,
                    "rankings": [s.to_dict() for s in scores],
                }
                with self.lock:
                    self.status["training_scorer_hint"] = hint
                    self.status["active_character_profile"] = profile.to_dict()
                    history = self.status.setdefault("training_scorer_history", [])
                    if not history or history[-1].get("turn") != turn:
                        history.append({
                            "turn": turn,
                            "best_command_id": hint["best_command_id"],
                            "best_stat": hint["best_stat"],
                            "best_score": hint["best_score"],
                            "profile_id": profile.profile_id,
                        })
                        if len(history) > 78:  # one full career
                            history.pop(0)
            except Exception:
                # The hint is best-effort.  A scorer or profile-resolution
                # crash must not break the live decision loop.
                pass

