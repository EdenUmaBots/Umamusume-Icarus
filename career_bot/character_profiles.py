"""Pre Icarus character profiles (v6.2 / v6.3).

Each character profile is a JSON file under ``data/character_profiles/`` that
ships a tuned override bundle for:

  - the Trackblazer race solver (weight overrides, target/forced epithets,
    distance preferences)

Profiles are resolved at run start from the trainee's ``card_id`` (or
``chara_id``).  When no character match is found, the v6.3 auto-derivation
layer builds a synthetic profile from the live ``chara_info`` aptitudes so
every trainee -- not just the hand-curated ones -- gets a sensible default.
The chain is::

    hand-curated profile -> auto-derived profile -> default.json -> empty

Per-scenario overrides nested under a scenario_id stomp the base profile
values for that scenario only.

This module is pure-Python with no new dependencies and is **read-only**
relative to disk -- it reads JSON, never writes.  All write/edit affordances
live in the dashboard layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple


PROFILES_DIRNAME = "character_profiles"
INDEX_FILENAME = "index.json"
DEFAULT_PROFILE_ID = "default"
AUTO_DERIVED_PROFILE_ID = "auto"

# Aptitude grade -> numeric strength.  Matches the convention the existing
# trackblazer.py uses (APT_ORDER) so the two layers agree on what "A" means.
_APT_RANK = {
    "S": 8, "A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1,
}


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass
class CharacterProfile:
    """Resolved, merged profile for one run.

    Created by ``resolve_profile`` after walking the index, loading the
    matched file, applying per-scenario overrides, and folding in any
    preset-level tweaks.  Consumers should never construct this directly --
    use the resolver.
    """

    profile_id: str
    display_name: str
    matched_via: str           # "card_id" | "chara_id" | "preset" | "name" | "auto" | "default"
    scenario_id: int

    # v6.7.13: the card_id this profile was resolved from (when known).
    # Persisted into the active_character_profile status dict so the
    # dashboard can re-resolve the exact profile between runs without
    # relying on name matching.
    matched_card_id: int = 0

    # Race solver overrides (subset of trackblazer DEFAULT_SOLVER_WEIGHTS)
    solver_overrides: Dict[str, Any] = field(default_factory=dict)

    # Solver goal language
    target_epithets: List[str] = field(default_factory=list)
    forced_epithets: List[str] = field(default_factory=list)

    # v6.3: dashboard-only data, NOT consumed by the solver directly.
    # Filled by auto-derivation from the bundled epithet catalog when the
    # active trainee matches a known character.  The picker UI shows these
    # at the top of the epithet selector so the user can promote them into
    # ``target_epithets`` / ``forced_epithets`` with one click.
    suggested_epithets: List[Dict[str, Any]] = field(default_factory=list)

    # Preferred distances passed into the solver (subset of
    # {"sprint","mile","medium","long"})
    preferred_distances: List[str] = field(default_factory=list)

    # v6.3: how this profile was sourced.  ``"hand_curated"`` for files
    # under data/character_profiles/, ``"auto_derived"`` for live-aptitude
    # fallbacks, ``"default"`` for the empty fallback.
    derivation: str = "hand_curated"

    # v6.4: auto-pick the character's signature epithet as a soft target
    # when neither the preset nor the profile JSON sets target_epithets
    # explicitly.  v6.7.6: default flipped from True to False per user
    # request -- the smart race solver already picks high-value races and
    # will complete some epithets organically.  Setting an auto-pick
    # target biases the solver away from its natural fan-maximizing path
    # and can drop other valuable races.  Opt-in via the Character
    # Profile panel's "Auto-pick signature epithets" checkbox.
    auto_pick_epithets: bool = False

    # v6.4: epithets the auto-pick layer would inject when target_epithets
    # is empty.  Populated by ``resolve_profile`` from the bundled catalog
    # via the trainee's display_name -> signature_epithet lookup.  This is
    # informational on the resolved profile; the actual injection into the
    # solver call happens via ``effective_target_epithets()``.
    auto_picked_epithets: List[str] = field(default_factory=list)

    # Raw payload for debug/dashboard rendering
    raw: Dict[str, Any] = field(default_factory=dict)

    # ----- convenience accessors -----


    def solver_weight_overrides(self) -> Dict[str, Any]:
        """Return a flat dict ready to feed into ``trackblazer.solve_with_node(weights=...)``."""
        return dict(self.solver_overrides or {})

    def epithet_goals(self) -> Tuple[List[str], List[str]]:
        return list(self.target_epithets), list(self.forced_epithets)

    def effective_target_epithets(self) -> Tuple[List[str], str]:
        """v6.4: return ``(epithet_names, source)`` for the active run.

        ``source`` is one of ``"profile"`` (explicit profile JSON value),
        ``"auto"`` (auto-picked signature epithet), or ``"none"`` (no
        epithets active).  Callers in runner.py / races.py use this to
        feed the solver while preserving the precedence chain
        preset > profile JSON > auto-pick.
        """
        if self.target_epithets:
            return list(self.target_epithets), "profile"
        if self.auto_pick_epithets and self.auto_picked_epithets:
            return list(self.auto_picked_epithets), "auto"
        return [], "none"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "matched_via": self.matched_via,
            "matched_card_id": self.matched_card_id,
            "derivation": self.derivation,
            "scenario_id": self.scenario_id,
            "solver_overrides": dict(self.solver_overrides),
            "target_epithets": list(self.target_epithets),
            "forced_epithets": list(self.forced_epithets),
            "suggested_epithets": [dict(e) for e in self.suggested_epithets],
            "preferred_distances": list(self.preferred_distances),
            "auto_pick_epithets": bool(self.auto_pick_epithets),
            "auto_picked_epithets": list(self.auto_picked_epithets),
        }


# --------------------------------------------------------------------------
# Index loading
# --------------------------------------------------------------------------


def _profiles_dir(base_dir: Any) -> Path:
    return Path(base_dir) / "data" / PROFILES_DIRNAME


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _load_index(base_dir: Any) -> Dict[str, Any]:
    """Return ``{"by_card_id": {...}, "by_chara_id": {...}, "by_preset": {...}, "by_name": {...}}``.

    Missing index file is non-fatal: the resolver falls back to the default
    profile.

    v6.7.13: ``by_name`` maps lowercased display names -> profile_id.
    Built by scanning the profile JSON files for their ``display_name``
    field, since the index file itself is keyed by id/preset.  This
    lets the dashboard resolve a profile from just a trainee's display
    name (e.g. when the persisted ``active_character_profile`` carries
    a name but not a card_id).
    """
    index = _read_json(_profiles_dir(base_dir) / INDEX_FILENAME) or {}
    by_name: Dict[str, str] = {}
    try:
        prof_dir = _profiles_dir(base_dir)
        if prof_dir.exists():
            for jf in prof_dir.glob("*.json"):
                if jf.stem in (INDEX_FILENAME.replace(".json", ""), "index"):
                    continue
                payload = _read_json(jf)
                if isinstance(payload, dict):
                    dn = str(payload.get("display_name") or "").strip().lower()
                    if dn:
                        by_name.setdefault(dn, jf.stem)
    except Exception:
        pass
    return {
        "by_card_id": {str(k): str(v) for k, v in (index.get("by_card_id") or {}).items()},
        "by_chara_id": {str(k): str(v) for k, v in (index.get("by_chara_id") or {}).items()},
        "by_preset": {str(k).lower(): str(v) for k, v in (index.get("by_preset") or {}).items()},
        "by_name": by_name,
    }


def _load_profile_payload(base_dir: Any, profile_id: str) -> Optional[Dict[str, Any]]:
    path = _profiles_dir(base_dir) / f"{profile_id}.json"
    return _read_json(path)


# --------------------------------------------------------------------------
# Merging
# --------------------------------------------------------------------------


def _coalesce_field(base: Mapping[str, Any], scenario_block: Mapping[str, Any], field_name: str) -> Any:
    """Per-scenario override wins, falling back to the base value."""
    if field_name in scenario_block:
        return scenario_block[field_name]
    return base.get(field_name)


def _merge_scenario(payload: Mapping[str, Any], scenario_id: int) -> Dict[str, Any]:
    """Apply the per-scenario overrides for ``scenario_id`` onto the base profile.

    The on-disk schema looks like::

        {
          "display_name": "Oguri Cap",
          "solver_overrides": {...},
          "target_epithets": [...],
          ...
          "scenarios": {
            "4": {
              "solver_overrides": {...}
            }
          }
        }

    Per-scenario blocks shallow-merge into the base for the dict-valued
    fields and replace whole-list fields.
    """
    merged: Dict[str, Any] = {}
    scenario_block = ((payload.get("scenarios") or {}).get(str(scenario_id))) or {}

    for k in ("display_name",):
        merged[k] = _coalesce_field(payload, scenario_block, k)

    # v6.4: auto_pick_epithets is a bool with a True default; the
    # _coalesce_field helper isn't quite right for bools because a base
    # value of False would be overridden by the default.  Handle it
    # explicitly so a profile can disable auto-pick globally or per
    # scenario.
    if "auto_pick_epithets" in scenario_block:
        merged["auto_pick_epithets"] = bool(scenario_block.get("auto_pick_epithets"))
    elif "auto_pick_epithets" in payload:
        merged["auto_pick_epithets"] = bool(payload.get("auto_pick_epithets"))
    else:
        # v6.7.6: default flipped to False (was True).  Profiles can opt
        # in via "auto_pick_epithets": true in their JSON or via the
        # Character Profile tab's checkbox.
        merged["auto_pick_epithets"] = False

    # Dict fields: shallow-merge scenario overrides onto base
    for k in ("solver_overrides",):
        base = dict(payload.get(k) or {})
        base.update(dict(scenario_block.get(k) or {}))
        merged[k] = base

    # List fields: scenario replaces base entirely if set
    for k in ("target_epithets", "forced_epithets", "preferred_distances"):
        if k in scenario_block:
            merged[k] = list(scenario_block.get(k) or [])
        else:
            merged[k] = list(payload.get(k) or [])

    return merged


# --------------------------------------------------------------------------
# Top-level resolver
# --------------------------------------------------------------------------


def resolve_profile(
    card_id: Any = 0,
    chara_id: Any = 0,
    scenario_id: int = 0,
    base_dir: Any = ".",
    preset_name: Optional[str] = None,
    chara_info: Optional[Mapping[str, Any]] = None,
    display_name: Optional[str] = None,
) -> CharacterProfile:
    """Resolve and build the active ``CharacterProfile`` for this run.

    Resolution order:
      1. ``index.by_card_id[card_id]``  -> hand-curated profile
      2. ``index.by_chara_id[chara_id]`` -> hand-curated profile
      3. ``index.by_preset[preset_name.lower()]`` -> hand-curated profile
      4. v6.7.13: ``index.by_name[display_name.lower()]`` -> hand-curated
         profile (lets the dashboard resolve from a trainee display name
         when no card_id is available, e.g. between runs)
      5. v6.3: auto-derive from ``chara_info`` aptitudes (if provided)
      6. ``default.json``

    Per-scenario overrides nested under ``scenarios.<id>`` are applied on
    top of the base profile (for the hand-curated path).  Auto-derived
    profiles are shaped per scenario from the get-go and don't go through
    the merge step.

    Returns a default profile (with empty overrides) when no match is found
    and no chara_info is available, so callers never have to handle a
    missing-profile case.
    """
    index = _load_index(base_dir)
    profile_id: Optional[str] = None
    matched_via = "default"

    try:
        cid = int(card_id or 0)
    except (TypeError, ValueError):
        cid = 0
    try:
        chid = int(chara_id or 0)
    except (TypeError, ValueError):
        chid = 0

    if cid and str(cid) in index["by_card_id"]:
        profile_id = index["by_card_id"][str(cid)]
        matched_via = "card_id"
    elif chid and str(chid) in index["by_chara_id"]:
        profile_id = index["by_chara_id"][str(chid)]
        matched_via = "chara_id"
    elif preset_name and preset_name.lower() in index["by_preset"]:
        profile_id = index["by_preset"][preset_name.lower()]
        matched_via = "preset"
    elif display_name and str(display_name).strip().lower() in index.get("by_name", {}):
        # v6.7.13: name-based resolution.  The dashboard's persisted
        # active_character_profile carries display_name but not card_id,
        # so without this path the panel fell back to "default" between
        # runs even when the last career used a specific profile.
        profile_id = index["by_name"][str(display_name).strip().lower()]
        matched_via = "name"

    payload = _load_profile_payload(base_dir, profile_id) if profile_id else None

    # v6.3 — when no hand-curated profile matches, try auto-derivation from
    # live aptitudes before falling all the way back to default.
    if payload is None and chara_info is not None:
        auto = _derive_from_chara_info(chara_info, scenario_id, base_dir)
        if auto is not None:
            return auto

    if payload is None:
        payload = _load_profile_payload(base_dir, DEFAULT_PROFILE_ID) or {}
        profile_id = DEFAULT_PROFILE_ID
        matched_via = "default"

    merged = _merge_scenario(payload, scenario_id)

    # Suggested epithets: when a hand-curated profile matches AND we have a
    # display_name we can look up in the catalog, surface the signature
    # epithet so the dashboard picker can render it.  This is read-only --
    # it never auto-promotes into target_epithets.
    display_name = merged.get("display_name") or profile_id or "Default"
    suggested = _suggested_epithets_for_name(display_name, base_dir)
    auto_pick_enabled = bool(merged.get("auto_pick_epithets", False))
    auto_picked = _auto_pick_epithet_names(display_name, base_dir) if auto_pick_enabled else []

    return CharacterProfile(
        profile_id=str(profile_id or DEFAULT_PROFILE_ID),
        display_name=str(display_name),
        matched_via=matched_via,
        matched_card_id=cid,
        scenario_id=int(scenario_id or 0),
        solver_overrides=dict(merged.get("solver_overrides") or {}),
        target_epithets=list(merged.get("target_epithets") or []),
        forced_epithets=list(merged.get("forced_epithets") or []),
        suggested_epithets=suggested,
        preferred_distances=list(merged.get("preferred_distances") or []),
        derivation="default" if matched_via == "default" else "hand_curated",
        auto_pick_epithets=auto_pick_enabled,
        auto_picked_epithets=auto_picked,
        raw=dict(payload),
    )


# --------------------------------------------------------------------------
# v6.3 auto-derivation: synthesize a profile from live chara aptitudes
# --------------------------------------------------------------------------


def _apt_to_rank(value: Any) -> int:
    """Aptitude as either a 1-8 int or an S-G letter -> numeric strength."""
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if isinstance(value, str):
        return _APT_RANK.get(value.upper().strip(), 0)
    return 0


def _trainee_name(chara_info: Mapping[str, Any]) -> str:
    """Best-effort extraction of the trainee's display name from the API."""
    for key in ("trained_chara_name", "chara_name", "name", "chara_title", "title", "card_name"):
        v = chara_info.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _aptitudes_from_chara_info(chara_info: Mapping[str, Any]) -> Dict[str, int]:
    """Pull the four distance aptitudes as 1-8 ranks."""
    return {
        "sprint": _apt_to_rank(chara_info.get("proper_distance_short")),
        "mile":   _apt_to_rank(chara_info.get("proper_distance_mile")),
        "medium": _apt_to_rank(chara_info.get("proper_distance_middle")),
        "long":   _apt_to_rank(chara_info.get("proper_distance_long")),
    }


# Stat priorities by best-distance bucket.  Sourced from the community
# consensus that the reference per-character presets implicitly encode:
# Mile runners lean Speed-Power-Wit, Stayers lean Stamina-Speed-Power.
_PRIORITY_BY_DISTANCE = {
    "sprint": ["speed", "power", "wit", "stamina", "guts"],
    "mile":   ["speed", "power", "wit", "stamina", "guts"],
    "medium": ["speed", "stamina", "power", "wit", "guts"],
    "long":   ["stamina", "speed", "power", "guts", "wit"],
}


def _derive_stat_targets(aptitudes: Mapping[str, int]) -> Dict[str, Dict[str, int]]:
    """Shape per-distance stat targets by aptitude strength.

    Where the trainee has S/A aptitude, full-strength targets apply.  Lower
    grades pull the targets down (a C-aptitude Long target doesn't push to
    1100 Stamina because the trainee can't compete at that distance anyway).
    Targets de-weight weak distances by their magnitude.
    """
    out: Dict[str, Dict[str, int]] = {}
    # Default per-distance targets.
    defaults = {
        "sprint": {"speed": 1200, "stamina": 400, "power": 1100, "guts": 400, "wit": 1000},
        "mile":   {"speed": 1200, "stamina": 600, "power": 1000, "guts": 400, "wit": 1000},
        "medium": {"speed": 1100, "stamina": 800, "power": 1000, "guts": 400, "wit": 1000},
        "long":   {"speed": 1000, "stamina": 1100, "power": 1000, "guts": 400, "wit": 1000},
    }
    for dist, base in defaults.items():
        apt = aptitudes.get(dist, 0)
        # 1.0 at S/A (rank 7+), 0.85 at B, 0.70 at C, 0.55 at D, 0.40 below.
        if apt >= 7: scale = 1.00
        elif apt == 6: scale = 0.85
        elif apt == 5: scale = 0.70
        elif apt == 4: scale = 0.55
        else: scale = 0.40
        out[dist] = {stat: max(300, int(round(value * scale))) for stat, value in base.items()}
    return out


def _suggested_epithets_for_name(name: str, base_dir: Any) -> List[Dict[str, Any]]:
    """Look up the signature epithet (if any) for a trainee name."""
    if not name:
        return []
    try:
        from career_bot import character_data
        sig = character_data.signature_epithet(name, base_dir=base_dir)
        return [sig] if sig else []
    except Exception:
        return []


def _auto_pick_epithet_names(name: str, base_dir: Any) -> List[str]:
    """v6.4: return a short list of epithet *names* (not full rows) to
    auto-promote into ``target_epithets`` when neither the preset nor the
    profile JSON sets them explicitly.

    Currently returns just the trainee's signature epithet (the single
    character-tagged title from the catalog).  Future enhancement: also
    include aptitude-matched generic epithets like "Mile Specialist".
    """
    suggested = _suggested_epithets_for_name(name, base_dir)
    out: List[str] = []
    for row in suggested:
        epi_name = row.get("name") or row.get("title")
        if isinstance(epi_name, str) and epi_name.strip():
            out.append(epi_name.strip())
    return out


def _derive_from_chara_info(
    chara_info: Mapping[str, Any],
    scenario_id: int,
    base_dir: Any,
) -> Optional[CharacterProfile]:
    """Build a synthetic profile from the live ``chara_info`` aptitudes.

    Returns ``None`` if chara_info doesn't carry enough aptitude data to
    derive anything meaningful (caller should fall through to default).
    """
    aptitudes = _aptitudes_from_chara_info(chara_info)
    if not any(aptitudes.values()):
        return None

    # Best distance bucket -> priority order.  Ties favor the more general
    # bucket (mile > medium > long > sprint) to avoid extreme builds when
    # the trainee is balanced.
    bucket_priority_order = ["mile", "medium", "long", "sprint"]
    best_dist = max(bucket_priority_order, key=lambda d: (aptitudes.get(d, 0), -bucket_priority_order.index(d)))

    priority = list(_PRIORITY_BY_DISTANCE.get(best_dist, _PRIORITY_BY_DISTANCE["mile"]))
    stat_targets = _derive_stat_targets(aptitudes)

    # Long-distance stamina floor scales with long-aptitude: a strong stayer
    # gets the default 550 (force the bot to build stamina), a weak stayer
    # gets a much lower floor (don't penalize long-race candidates that the
    # trainee won't be able to compete in well anyway).
    long_apt = aptitudes.get("long", 0)
    if long_apt >= 7:
        stamina_floor = 550
    elif long_apt == 6:
        stamina_floor = 500
    elif long_apt == 5:
        stamina_floor = 450
    else:
        stamina_floor = 400

    # Preferred distances: all distances with aptitude >= B (rank 6).
    preferred = [d for d in bucket_priority_order if aptitudes.get(d, 0) >= 6]

    # Suggested epithet from the character catalog, if the name matches.
    name = _trainee_name(chara_info) or "Auto-derived"
    suggested = _suggested_epithets_for_name(name, base_dir)
    auto_picked = _auto_pick_epithet_names(name, base_dir)

    solver_overrides: Dict[str, Any] = {}
    # Trackblazer (scenario_id == 4) is the only scenario we currently tune
    # the solver weights for.  Other scenarios run with the global defaults.
    if int(scenario_id or 0) == 4:
        solver_overrides["longDistanceStaminaFloor"] = stamina_floor
        # Default targetOptionalRaceCount stays at 36 for auto-derived
        # profiles -- the hand-curated path can push higher when there are
        # explicit epithet goals to chase.

    return CharacterProfile(
        profile_id=AUTO_DERIVED_PROFILE_ID,
        display_name=name,
        matched_via="auto",
        scenario_id=int(scenario_id or 0),
        solver_overrides=solver_overrides,
        target_epithets=[],
        forced_epithets=[],
        suggested_epithets=suggested,
        preferred_distances=preferred,
        derivation="auto_derived",
        # v6.7.6: auto_pick default flipped to False for auto-derived
        # profiles too, matching the hand-curated default.  User can opt
        # in via the Character Profile tab if they want signature
        # epithets biased into the solver.
        auto_pick_epithets=False,
        auto_picked_epithets=auto_picked,
        raw={
            "auto_derived_from": {
                "name": name,
                "aptitudes": aptitudes,
                "best_distance": best_dist,
            },
        },
    )


def list_available_profiles(base_dir: Any = ".") -> List[Dict[str, Any]]:
    """Enumerate the on-disk profile files for the settings UI."""
    profiles_dir = _profiles_dir(base_dir)
    out: List[Dict[str, Any]] = []
    if not profiles_dir.exists():
        return out
    for path in sorted(profiles_dir.iterdir()):
        if path.name == INDEX_FILENAME or path.suffix != ".json":
            continue
        payload = _read_json(path) or {}
        out.append({
            "profile_id": path.stem,
            "display_name": payload.get("display_name") or path.stem,
            "scenarios_with_overrides": sorted((payload.get("scenarios") or {}).keys()),
            "has_epithet_goals": bool(payload.get("target_epithets") or payload.get("forced_epithets")),
        })
    return out


__all__ = [
    "CharacterProfile",
    "resolve_profile",
    "list_available_profiles",
    "DEFAULT_PROFILE_ID",
    "PROFILES_DIRNAME",
    "INDEX_FILENAME",
]
