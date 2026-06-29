import json
from copy import deepcopy
from pathlib import Path

from .presets import hydrate_preset, slugify

SETTING_PRESET_KEYS = {
    "name",
    "scenario_id",
    "scenario",
    "training_stat_priority",
    "event_choice_stat_priority",
    "summer_stat_priority",
    "running_style",
    "race_strategy_by_distance",
    "preferred_distances",
    "preferred_surfaces",
    "extra_race_list_source",
    "event_overrides",
    "prioritize_event_energy",
    "event_energy_priority_multiplier",
    "event_stat_priority_bonus_by_rank",
    "mant_config",
    "selection",
}

# event_overrides is managed ONLY by the dedicated save_event_overrides endpoint
# (the Event Choices panel). A whole-preset Settings save round-trips a possibly
# STALE snapshot of event_overrides (captured when the modal loaded, before the
# user forced a choice), so applying it from the incoming preset CLOBBERED the
# forced choices back to {} -- the root cause of "forced event choices ignored".
# Whole-preset writes therefore exclude it; reads (compose/read_settings_presets)
# still include it from the on-disk file.
WHOLE_SAVE_PRESET_KEYS = SETTING_PRESET_KEYS - {"event_overrides"}

SKILL_CONFIG_KEYS = {
    "enable_skill_point_check",
    "learn_skill_threshold",
    "enable_skill_point_check_plan",
    "pre_finals_enabled",
    "career_complete_enabled",
    "purchase_negative_skills",
    "skip_green_skills",
    "skip_red_skills",
    "skip_unique_skills",
    "show_only_selected_skills",
    "skill_spending_strategy",
    "skill_profile",
    "skill_strategy",
    "smart_skill_max_green_per_purchase",
    "smart_skill_yellow_bonus",
    "smart_skill_green_penalty",
    "smart_skill_min_score",
    "learn_skill_list",
    "learn_skill_blacklist",
    "manual_skill_tiers",
    "manual_skill_tiers_dont_spend_extra",
    "skill_stop_after_recommended",
    "skill_manual_auto_fallback",
    # Skill-purchase redesign: Stage 1 condition gate + Stage 3 optimization target.
    "skill_condition_gating",
    "skill_condition_dead_factor",
    "skill_optimization_target",
    "skill_tier_multipliers",
}

SMART_SOLVER_KEYS = {
    "extra_race_list",
    "trackblazer_solver_settings",
    "trackblazer_manual_aptitudes",
    "trackblazer_manual_aptitudes_by_trainee",
    "trackblazer_solver_profiles",
    "trackblazer_weights",
    "trackblazer_target_epithets",
    "trackblazer_forced_epithets",
    "trackblazer_last_plan",
    "training_blocks",
    "manual_locks",
}

LEGACY_SETTINGS_PRESET_NAMES = {
    "fan farming",
    "maru fan farming",
    "oguri",
    "parent farming",
    "xguri",
    "xguri parent",
}


def _is_legacy_settings_preset(preset):
    """Return True for bundled legacy presets that v5.27 should not load.

    User-created presets are kept.  The comparison is intentionally strict on
    normalized names so we do not delete unrelated user presets that merely
    contain similar words.
    """
    return str((preset or {}).get("name") or "").strip().lower() in LEGACY_SETTINGS_PRESET_NAMES



def _read_json(path, default):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(default)
    return deepcopy(default)


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _only_keys(data, keys):
    data = dict(data or {})
    return {k: deepcopy(v) for k, v in data.items() if k in keys}


def _default_settings_preset(name="Default"):
    return {
        "name": name,
        "scenario_id": 4,
        "training_stat_priority": ["speed", "power", "wit", "stamina", "guts"],
        "event_choice_stat_priority": ["speed", "power", "wit", "stamina", "guts"],
        "summer_stat_priority": ["speed", "power", "wit", "stamina", "guts"],
        "running_style": 1,
        "race_strategy_by_distance": {},
        "preferred_distances": [],
        "preferred_surfaces": [],
        "event_overrides": {},
        "mant_config": {},
        "selection": {},
    }


def _default_skill_config():
    return {
        "enable_skill_point_check": True,
        "learn_skill_threshold": 888,
        "enable_skill_point_check_plan": True,
        "pre_finals_enabled": False,
        "career_complete_enabled": False,
        "purchase_negative_skills": False,
        "skip_green_skills": False,
        "skip_red_skills": False,
        "skip_unique_skills": False,
        "show_only_selected_skills": False,
        "skill_spending_strategy": "best_skills_first",
        "skill_profile": "auto",
        "learn_skill_list": [],
        "learn_skill_blacklist": [],
        "smart_skill_max_green_per_purchase": 1,
        "smart_skill_yellow_bonus": 100,
        "smart_skill_green_penalty": 90,
        "smart_skill_min_score": 18,
        # v7.3 — Manual skill tiers, used when enable_skill_point_check_plan
        # is False. Keys are tier numbers as strings ("1" highest priority
        # through "5" lowest). Values are lists of skill NAMES (consistent
        # with how learn_skill_list / forced_skills store identifiers).
        # When the plan-check toggle is off AND any tier has skills, the
        # skill buyer filters candidates to only these skills and orders
        # them by tier ascending. When all tiers are empty, the buyer
        # silently falls back to the smart-scorer behavior so disabling
        # the plan-check toggle never bricks skill purchasing.
        "manual_skill_tiers": {
            "1": [],
            "2": [],
            "3": [],
            "4": [],
            "5": [],
        },
        # v2.1 -- manual tiers buy ONLY the listed skills by default; the
        # auto-fallback toggle (off by default) lets the auto plan spend the
        # rest once every listed skill is owned.
        "manual_skill_tiers_dont_spend_extra": True,
        "skill_manual_auto_fallback": False,
        # v2.1 -- auto strategy stops spending once the character's recommended
        # / best (preferred + community SS/S) skills are all owned, so SP isn't
        # dumped into marginal skills. Pre-finals dump still overrides.
        # 2026-06-26: default OFF. The gate discarded ALL good, on-profile
        # candidates on any turn where none was a top-tier "recommended" skill
        # (not "once recommended owned" as intended), so the bot bought almost
        # nothing and hoarded SP. The smart scorer already filters quality.
        "skill_stop_after_recommended": False,
        # Skill-purchase redesign. Stage 1: schedule-aware condition gate
        # (penalize = dampen eval/SP for skills whose running_style/distance_type
        # conditions can never fire for this trainee; enforce = hard drop; ignore
        # = tag only). Stage 3: optimization target picks which spreadsheet rank
        # column weights the graded tier and whether single-mode-disabled skills
        # are dropped (career) or kept (team_trials / champions). Defaults keep the
        # fans-first single-mode behavior unchanged.
        "skill_condition_gating": "penalize",
        "skill_condition_dead_factor": 0.15,
        "skill_optimization_target": "career",
        "skill_strategy": {
            "forced_skills": [],
            "blacklist": [],
            "manual_skill_weights": {},
            "running_style": "auto",
            "primary_distances": ["auto"],
            "secondary_distances": [],
            "track": "auto",
            "max_green_per_purchase": 1,
            "weights": {
                "recommended": 190,
                "community": 1,
                "yellow": 100,
                "green_penalty": 90,
                "style": 70,
                "distance": 75,
            },
        },
    }


def _default_solver_config():
    return {
        "extra_race_list": [],
        "trackblazer_solver_settings": {},
        "trackblazer_manual_aptitudes": {},
        "trackblazer_manual_aptitudes_by_trainee": {},
        "trackblazer_solver_profiles": [],
        "trackblazer_weights": {},
        "trackblazer_target_epithets": [],
        "trackblazer_forced_epithets": [],
        "trackblazer_last_plan": {},
        "training_blocks": [],
        "manual_locks": {},
    }


def _normalize_skill(cfg):
    """Return a complete, normalized skill-config dict from any partial source.

    Backfills defaults, merges the skill_strategy substructure + weights, and
    ensures all five manual-tier buckets exist as lists.
    """
    base = _default_skill_config()
    out = dict(base)
    out.update(_only_keys(cfg, SKILL_CONFIG_KEYS))
    strat = dict(base["skill_strategy"])
    strat.update(dict(out.get("skill_strategy") or {}))
    strat["weights"] = {**base["skill_strategy"]["weights"], **dict(strat.get("weights") or {})}
    out["skill_strategy"] = strat
    tiers = dict(out.get("manual_skill_tiers") or {})
    for k in ("1", "2", "3", "4", "5"):
        if k not in tiers or not isinstance(tiers.get(k), list):
            tiers[k] = list(tiers.get(k) or [])
    out["manual_skill_tiers"] = tiers
    return out


class ConfigStore:
    """v7.6 per-file preset store.

    Each preset is a single self-contained JSON file under ``data/presets/``
    holding its SETTINGS, SKILL, and SOLVER config together, so a preset's
    "Configure Skills" choices are specific to that preset (they used to live in
    one global ``skill_config.json`` shared by every preset). An
    ``active_preset.json`` pointer names the current preset; skill/solver
    reads/writes target it. The public method surface (read_settings_presets,
    save/delete_settings_preset, read/save_skill_config, read/save_solver_config,
    compose_runtime_preset, read_all/read_one/write/delete) is unchanged, so
    callers in main.py and the runner are unaffected. Legacy split files
    (settings_presets.json + global skill/solver) are auto-migrated on first run.
    """

    def __init__(self, base_dir, userdata_dir=None):
        """v6.7.6: ``userdata_dir`` (optional) holds the active settings,
        skill, and solver JSON files.  When None, defaults to
        ``<base_dir>/data`` (the legacy in-build location).  When set, the
        settings/skill/solver/preset files persist outside the build folder
        so Pre Icarus version upgrades don't blow away saved presets.
        ``base_dir`` is still used as the source for default templates and
        the legacy preset migration path.
        """
        self.base_dir = Path(base_dir)
        if userdata_dir and str(userdata_dir) != str(base_dir):
            self.data_dir = Path(userdata_dir) / "data"
        else:
            self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.presets_dir = self.data_dir / "presets"
        self.active_path = self.data_dir / "active_preset.json"
        # Legacy (pre-v7.6) split files, used only as one-time migration sources.
        self.legacy_settings_path = self.data_dir / "settings_presets.json"
        self.legacy_skill_path = self.data_dir / "skill_config.json"
        self.legacy_solver_path = self.data_dir / "smart_solver_config.json"
        self._migrate_marker = self.data_dir / ".presets_migrated_v76"
        self._maybe_migrate_from_build()
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_to_per_file()
        self._ensure_default()

    # ---- internal helpers ----
    def _maybe_migrate_from_build(self):
        """One-way copy of the legacy split files from the in-build data/ to
        the userdata data/ on first start of a new version, so the per-file
        migration below can pick up the previous version's presets."""
        src_data = self.base_dir / "data"
        if self.data_dir == src_data or not src_data.exists():
            return
        for name in ("settings_presets.json", "skill_config.json", "smart_solver_config.json"):
            src = src_data / name
            dst = self.data_dir / name
            if src.exists() and not dst.exists():
                try:
                    dst.write_bytes(src.read_bytes())
                except Exception:
                    pass

    def _preset_path(self, name):
        return self.presets_dir / f"{slugify(str(name or 'preset'))}.json"

    def _list_preset_files(self):
        return sorted(self.presets_dir.glob("*.json"))

    def _full_default_preset(self, name="Default"):
        full = _default_settings_preset(name)
        full.update(_default_skill_config())
        full.update(_default_solver_config())
        full["name"] = name
        return full

    def _normalize_full(self, full):
        """Ensure a full preset dict has normalized skill substructures."""
        full.update(_normalize_skill(full))
        return full

    def _read_full_preset(self, path):
        raw = _read_json(path, {})
        if not isinstance(raw, dict):
            raw = {}
        # Settings are taken from the hydrated/normalized view; skill + solver
        # keys are read from the RAW dict because hydrate_preset() only knows
        # about settings fields and would drop the skill/solver layers.
        hydrated = hydrate_preset(raw) if raw else {}
        name = raw.get("name") or hydrated.get("name") or Path(path).stem
        full = self._full_default_preset(name)
        full.update(_only_keys(hydrated, SETTING_PRESET_KEYS))
        full.update(_only_keys(raw, SKILL_CONFIG_KEYS))
        full.update(_only_keys(raw, SMART_SOLVER_KEYS))
        if raw.get("skill_strategy"):
            full["skill_strategy"] = raw["skill_strategy"]
        full["name"] = name
        return self._normalize_full(full)

    def _active_name(self, presets=None):
        raw = _read_json(self.active_path, {})
        active = str((raw or {}).get("active") or "").strip()
        if presets is None:
            presets = [self._read_full_preset(p) for p in self._list_preset_files()]
        names = [str(p.get("name", "")) for p in presets]
        if active and any(active.lower() == n.lower() for n in names):
            return active
        return names[0] if names else "Default"

    def set_active(self, name):
        name = str(name or "").strip()
        if not name:
            return self._active_name()
        # resolve to a real preset name (match by name/slug) if possible
        for p in self._list_preset_files():
            full = self._read_full_preset(p)
            if str(full.get("name", "")).lower() == name.lower() or self._preset_path(name) == p:
                name = full.get("name") or name
                break
        _write_json(self.active_path, {"active": name})
        return name

    def _migrate_to_per_file(self):
        """One-time migration from the legacy split layout (settings_presets.json
        + global skill_config.json + smart_solver_config.json) to one
        self-contained file per preset under data/presets/. Idempotent."""
        if self._migrate_marker.exists():
            return {"migrated": False, "reason": "already migrated"}
        existing = self._list_preset_files()
        if existing:
            # Pre-existing per-file presets (e.g. ancient pre-v5.8 format): adopt
            # them, backfilling skill/solver keys so each is self-contained and
            # normalizing the filename to the preset's slug so lookups match.
            for path in existing:
                full = self._read_full_preset(path)
                target = self._preset_path(full.get("name") or path.stem)
                _write_json(target, full)
                if target != path:
                    try:
                        path.unlink()
                    except Exception:
                        pass
        elif self.legacy_settings_path.exists():
            legacy = _read_json(self.legacy_settings_path, {"active": "", "presets": []})
            skill = _read_json(self.legacy_skill_path, {})
            solver = _read_json(self.legacy_solver_path, {})
            for sp in legacy.get("presets", []):
                if _is_legacy_settings_preset(sp):
                    continue
                name = slugify(sp.get("name") or "Default")
                full = self._full_default_preset(name)
                full.update(_only_keys(sp, SETTING_PRESET_KEYS))
                full.update(_only_keys(skill, SKILL_CONFIG_KEYS))
                if skill.get("skill_strategy"):
                    full["skill_strategy"] = skill["skill_strategy"]
                full.update(_only_keys(solver, SMART_SOLVER_KEYS))
                full["name"] = name
                _write_json(self._preset_path(name), self._normalize_full(full))
            active = str(legacy.get("active") or "").strip()
            if active and active.lower() not in LEGACY_SETTINGS_PRESET_NAMES:
                self.set_active(slugify(active))
            # Back up the legacy split files so they aren't re-migrated but stay
            # recoverable.
            for p in (self.legacy_settings_path, self.legacy_skill_path, self.legacy_solver_path):
                try:
                    if p.exists():
                        p.rename(p.with_name(p.name + ".premigrate.bak"))
                except Exception:
                    pass
        try:
            self._migrate_marker.write_text("v7.6", encoding="utf-8")
        except Exception:
            pass
        return {"migrated": True}

    def _ensure_default(self):
        if not self._list_preset_files():
            _write_json(self._preset_path("Default"), self._full_default_preset("Default"))
        if not self.active_path.exists():
            self.set_active(self._active_name())

    # ---- settings presets ----
    def read_settings_presets(self):
        presets = []
        for path in self._list_preset_files():
            full = self._read_full_preset(path)
            if _is_legacy_settings_preset(full):
                continue
            clean = _default_settings_preset(full.get("name") or "Default")
            clean.update(_only_keys(full, SETTING_PRESET_KEYS))
            clean["name"] = full.get("name") or clean["name"]
            presets.append(clean)
        presets.sort(key=lambda p: str(p.get("name", "")).lower())
        if not presets:
            _write_json(self._preset_path("Default"), self._full_default_preset("Default"))
            presets = [_default_settings_preset()]
        return {"active": self._active_name(presets), "presets": presets}

    def save_settings_preset(self, preset):
        name = slugify(str((preset or {}).get("name") or self._active_name() or "Settings Preset").strip() or "Settings Preset")
        path = self._preset_path(name)
        full = self._read_full_preset(path) if path.exists() else self._full_default_preset(name)
        full.update(_only_keys(preset, WHOLE_SAVE_PRESET_KEYS))  # never clobber event_overrides
        full["name"] = name
        _write_json(path, self._normalize_full(full))
        self.set_active(name)
        clean = _default_settings_preset(name)
        clean.update(_only_keys(full, SETTING_PRESET_KEYS))
        clean["name"] = name
        return clean

    def delete_settings_preset(self, name):
        target = str(name or "").lower()
        for path in self._list_preset_files():
            full = self._read_full_preset(path)
            if str(full.get("name", "")).lower() == target or path == self._preset_path(name):
                try:
                    path.unlink()
                except Exception:
                    pass
        self._ensure_default()
        self.set_active(self._active_name())
        return True

    # ---- skill / solver config (operate on the active preset) ----
    def read_skill_config(self, name=None):
        name = name or self._active_name()
        path = self._preset_path(name)
        full = self._read_full_preset(path) if path.exists() else self._full_default_preset(name)
        return _normalize_skill(full)

    def save_skill_config(self, config, name=None):
        name = name or self._active_name()
        path = self._preset_path(name)
        full = self._read_full_preset(path) if path.exists() else self._full_default_preset(name)
        full.update(_only_keys(config, SKILL_CONFIG_KEYS))
        if "skill_strategy" in (config or {}):
            strat = dict(full.get("skill_strategy") or {})
            strat.update(dict(config.get("skill_strategy") or {}))
            strat["weights"] = {**_default_skill_config()["skill_strategy"]["weights"], **dict(strat.get("weights") or {})}
            full["skill_strategy"] = strat
        full["name"] = name
        _write_json(path, self._normalize_full(full))
        return _normalize_skill(full)

    def read_solver_config(self, name=None):
        name = name or self._active_name()
        path = self._preset_path(name)
        full = self._read_full_preset(path) if path.exists() else self._full_default_preset(name)
        cfg = _default_solver_config()
        cfg.update(_only_keys(full, SMART_SOLVER_KEYS))
        return cfg

    def save_solver_config(self, config, name=None):
        name = name or self._active_name()
        path = self._preset_path(name)
        full = self._read_full_preset(path) if path.exists() else self._full_default_preset(name)
        full.update(_only_keys(config, SMART_SOLVER_KEYS))
        full["name"] = name
        _write_json(path, self._normalize_full(full))
        cfg = _default_solver_config()
        cfg.update(_only_keys(full, SMART_SOLVER_KEYS))
        return cfg

    # ---- event-choice overrides (per-preset, key already in SETTING_PRESET_KEYS) ----
    def read_event_overrides(self, name=None):
        name = name or self._active_name()
        path = self._preset_path(name)
        full = self._read_full_preset(path) if path.exists() else self._full_default_preset(name)
        ov = full.get("event_overrides")
        return dict(ov) if isinstance(ov, dict) else {}

    def save_event_overrides(self, overrides, name=None):
        name = name or self._active_name()
        path = self._preset_path(name)
        full = self._read_full_preset(path) if path.exists() else self._full_default_preset(name)
        full["event_overrides"] = dict(overrides or {})
        full["name"] = name
        _write_json(path, self._normalize_full(full))
        return dict(full.get("event_overrides") or {})

    def compose_runtime_preset(self, name=None):
        name = name or self._active_name()
        path = self._preset_path(name)
        full = self._read_full_preset(path) if path.exists() else self._full_default_preset(name)
        settings = _default_settings_preset(full.get("name") or name)
        settings.update(_only_keys(full, SETTING_PRESET_KEYS))
        settings["name"] = full.get("name") or name
        runtime = hydrate_preset(settings)
        runtime.update(_normalize_skill(full))
        solver = _default_solver_config()
        solver.update(_only_keys(full, SMART_SOLVER_KEYS))
        runtime.update(solver)
        runtime["name"] = settings["name"]
        return runtime

    # PresetStore-compatible methods.
    def read_all(self):
        return [self.compose_runtime_preset(p.get("name")) for p in self.read_settings_presets().get("presets", [])]

    def read_one(self, name):
        wanted = str(name or "").strip().lower()
        if not wanted:
            return self.compose_runtime_preset(None)
        for p in self.read_settings_presets().get("presets", []):
            if str(p.get("name", "")).lower() == wanted:
                return self.compose_runtime_preset(p.get("name"))
        return None

    def write(self, preset):
        name = slugify(str((preset or {}).get("name") or self._active_name() or "Settings Preset").strip() or "Settings Preset")
        path = self._preset_path(name)
        full = self._read_full_preset(path) if path.exists() else self._full_default_preset(name)
        full.update(_only_keys(preset, WHOLE_SAVE_PRESET_KEYS))  # never clobber event_overrides
        full.update(_only_keys(preset, SKILL_CONFIG_KEYS))
        if "skill_strategy" in (preset or {}):
            strat = dict(full.get("skill_strategy") or {})
            strat.update(dict(preset.get("skill_strategy") or {}))
            strat["weights"] = {**_default_skill_config()["skill_strategy"]["weights"], **dict(strat.get("weights") or {})}
            full["skill_strategy"] = strat
        full.update(_only_keys(preset, SMART_SOLVER_KEYS))
        full["name"] = name
        _write_json(path, self._normalize_full(full))
        self.set_active(name)
        return self.compose_runtime_preset(name)

    def delete(self, name):
        return self.delete_settings_preset(name)
