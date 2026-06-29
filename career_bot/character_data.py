"""Pre Icarus character data loaders (v6.3).

Reads two community-maintained JSON catalogs ported from the
the reference automation project (see ``data/character_data/README.md``):

  - ``character_presets.json`` -- 59 trainees with distance & surface
    aptitude grades.  Used as a name-keyed lookup to enrich auto-derived
    profiles with canonical aptitude data when the live chara_info reads
    are partial or absent.

  - ``epithets.json`` -- 217 epithets, 59 of which are tagged as
    character-specific (the trainee's signature title) plus 158 generic
    ones.  Used to populate ``suggested_epithets`` in resolved profiles
    so the dashboard can render a pre-filtered picker like the game's.

Both files are loaded lazily and memoized on first access.  The loaders
are read-only -- this module never writes to disk.

API:
  - ``load_character_presets(base_dir)`` -> ``Dict[name, preset_row]``
  - ``load_epithet_catalog(base_dir)`` -> ``Dict[title, epithet_row]``
  - ``find_character_preset(name, presets)`` -> preset row or ``None``
  - ``epithets_for_character(name, catalog)`` -> list of epithet rows
  - ``signature_epithet(name, catalog)`` -> single character-tagged
    epithet row or ``None``
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


# --------------------------------------------------------------------------
# Caches (per-base_dir; cleared when the source mtime advances)
# --------------------------------------------------------------------------

_PRESETS_CACHE: Dict[str, Dict[str, Any]] = {}
_PRESETS_MTIME: Dict[str, float] = {}
_EPITHETS_CACHE: Dict[str, Dict[str, Any]] = {}
_EPITHETS_MTIME: Dict[str, float] = {}
_CACHE_LOCK = threading.Lock()


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------


def _data_dir(base_dir: Any) -> Path:
    return Path(base_dir) / "data" / "character_data"


def character_presets_path(base_dir: Any) -> Path:
    return _data_dir(base_dir) / "character_presets.json"


def epithets_path(base_dir: Any) -> Path:
    return _data_dir(base_dir) / "epithets.json"


# --------------------------------------------------------------------------
# Loaders (with mtime-keyed memoization)
# --------------------------------------------------------------------------


def _read_json_cached(path: Path, cache: Dict[str, Dict[str, Any]], mtimes: Dict[str, float]) -> Dict[str, Any]:
    key = str(path)
    try:
        mtime = path.stat().st_mtime if path.exists() else -1.0
    except OSError:
        mtime = -1.0

    with _CACHE_LOCK:
        if key in cache and mtimes.get(key) == mtime:
            return cache[key]

    if mtime < 0:
        with _CACHE_LOCK:
            cache[key] = {}
            mtimes[key] = mtime
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            payload = {}
    except (OSError, json.JSONDecodeError):
        payload = {}

    with _CACHE_LOCK:
        cache[key] = payload
        mtimes[key] = mtime
    return payload


def load_character_presets(base_dir: Any) -> Dict[str, Dict[str, Any]]:
    """Return ``{character_name: preset_row}`` for all bundled characters.

    A preset row has the standard shape::

        {"name": "Oguri Cap",
         "distanceAptitudes": {"Sprint": "B", "Mile": "S", "Medium": "A", "Long": "A"},
         "surfaceAptitudes": {"Turf": "A", "Dirt": "B"}}

    Returns an empty dict if the file is missing or unreadable so callers
    can degrade gracefully to live-only aptitude derivation.
    """
    return _read_json_cached(character_presets_path(base_dir), _PRESETS_CACHE, _PRESETS_MTIME)


def load_epithet_catalog(base_dir: Any) -> Dict[str, Dict[str, Any]]:
    """Return ``{epithet_title: epithet_row}`` for all bundled epithets.

    A row has the standard shape::

        {"name": "Showbiz Idol",
         "characters": ["Oguri Cap"],
         "bullet_points": [...],
         "matchers": [{"name": "Arima Kinen", "type": "winRace", ...}, ...]}
    """
    return _read_json_cached(epithets_path(base_dir), _EPITHETS_CACHE, _EPITHETS_MTIME)


# --------------------------------------------------------------------------
# Name matching
# --------------------------------------------------------------------------


def _normalize_name(name: Any) -> str:
    """Casefold + strip + collapse whitespace.  Catches the Oguri Cap /
    'Oguri Cap (Test)' / OGURI_CAP variants without dragging in fuzzywuzzy."""
    if name is None:
        return ""
    text = " ".join(str(name).strip().split()).casefold()
    # Strip trailing parens annotations like "(SSR)" or "(Trackblazer)" that
    # the game sometimes appends.
    if "(" in text:
        text = text.split("(", 1)[0].strip()
    return text


def find_character_preset(
    name: Any,
    presets: Optional[Mapping[str, Mapping[str, Any]]] = None,
    base_dir: Any = None,
) -> Optional[Dict[str, Any]]:
    """Return the matching character preset row by name, or ``None``.

    Accepts either a pre-loaded ``presets`` dict (avoids re-reading from
    disk in tight loops) or a ``base_dir`` to load from.  Exactly one of
    the two should be provided.
    """
    if presets is None:
        presets = load_character_presets(base_dir) if base_dir is not None else {}

    target = _normalize_name(name)
    if not target:
        return None

    # Fast path -- exact case-insensitive key match.
    for key, row in presets.items():
        if _normalize_name(key) == target:
            return dict(row)

    # Fall back to matching the row's "name" field (which may differ from
    # the dict key in some upstream snapshots).
    for row in presets.values():
        if isinstance(row, Mapping) and _normalize_name(row.get("name")) == target:
            return dict(row)

    return None


def epithets_for_character(
    name: Any,
    catalog: Optional[Mapping[str, Mapping[str, Any]]] = None,
    base_dir: Any = None,
) -> List[Dict[str, Any]]:
    """Return epithets where ``characters`` includes the named trainee.

    Generic epithets (no character tag) are NOT included -- this list is
    meant to feed a character-filtered picker.  Generic ones are still
    discoverable via the full catalog.
    """
    if catalog is None:
        catalog = load_epithet_catalog(base_dir) if base_dir is not None else {}

    target = _normalize_name(name)
    if not target:
        return []

    out: List[Dict[str, Any]] = []
    for title, row in catalog.items():
        if not isinstance(row, Mapping):
            continue
        chars = row.get("characters") or []
        if not isinstance(chars, list):
            continue
        for c in chars:
            if _normalize_name(c) == target:
                # Preserve the title so the caller can render it even if
                # the row doesn't carry a ``name`` field.
                out.append({"title": title, **dict(row)})
                break
    return out


def signature_epithet(
    name: Any,
    catalog: Optional[Mapping[str, Mapping[str, Any]]] = None,
    base_dir: Any = None,
) -> Optional[Dict[str, Any]]:
    """Return the single character-tagged epithet for this trainee, or
    ``None`` if the catalog doesn't have one.

    In the character catalog each of the 59 known characters has
    exactly one signature epithet (the title earned by completing their
    character-defining race set).  This helper exists so callers can
    populate a ``suggested_epithets`` list with just the signature title
    without grabbing generic shared epithets like "All-Rounder".
    """
    rows = epithets_for_character(name, catalog=catalog, base_dir=base_dir)
    return rows[0] if rows else None


__all__ = [
    "character_presets_path",
    "epithets_path",
    "load_character_presets",
    "load_epithet_catalog",
    "find_character_preset",
    "epithets_for_character",
    "signature_epithet",
]
