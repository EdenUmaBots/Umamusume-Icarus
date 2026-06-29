import json
import os
import sqlite3
import time
from pathlib import Path


DIRECT_TABLES = [
    "skill_data",
    "single_mode_skill_need_point",
    "race",
    "race_course_set",
    "race_instance",
    "single_mode_program",
    "single_mode_scout_chara",
    "card_rarity_data",
    "available_skill_set",
    "support_card_data",
    # Extended official datasets used by the data-driven feature layer.
    "card_data",
    "chara_data",
    "succession_factor",
    "succession_factor_effect",
    "succession_relation",
    "succession_relation_member",
    "succession_rental",
    "succession_initial_factor",
    "succession_relation_rank",
    "single_mode_chara_grade",
    "single_mode_event_choice_reward",
    "single_mode_event_item_detail",
    "single_mode_event_cr_priority",
    "single_mode_event_production",
    "single_mode_event_conclusion",
    "single_mode_free_shop",
    "single_mode_free_shop_item",
    "single_mode_free_shop_effect",
    "item_data",
    "support_card_effect_table",
    "support_card_unique_effect",
    "support_card_level",
    "skill_set",
    "skill_level_value",
    "skill_rarity",
    "single_mode_hint_gain",
    "single_mode_training",
    "single_mode_training_effect",
    "single_mode_free_training_plate",
    "single_mode_scenario",
    "single_mode_turn",
    "single_mode_fan_count",
    "single_mode_wins_saddle",
    "single_mode_rank",
    # Official Trackblazer planning datasets (v5.12 P0).
    "single_mode_chara_program",
    "single_mode_route",
    "single_mode_route_race",
    "single_mode_route_condition",
    "single_mode_rival",
    "single_mode_npc",
    "single_mode_free_coin_race",
    "single_mode_free_win_point",
    "single_mode_reward_set",
    "single_mode_race_group",
    "race_proper_distance_rate",
    "race_proper_ground_rate",
    "race_proper_runningstyle_rate",
    "race_motivation_rate",
    "race_course_set_status",
    "race_popularity_proper_value",
]

TEXT_DATA_CATEGORIES = {
    "cat_4_text": 4,      # trainee/card names
    "cat_28_text": 28,    # race names
    "cat_47_text": 47,    # skill names
    "cat_75_text": 75,    # support card names
    "cat_147_text": 147,  # succession factor names
    "cat_181_text": 181,
    "cat_225_text": 225,  # Trackblazer/MANT shop item names
    "cat_10_text": 10,    # item descriptions
    "cat_23_text": 23,    # item names
    "cat_111_text": 111,  # major win / wins saddle names
    "cat_177_text": 177,  # event item display names
    "cat_178_text": 178,  # event/plow item display names
    "cat_179_text": 179,  # event ending/fan item display names
    "cat_180_text": 180,  # event item name-index display names
    "cat_182_text": 182,  # trainee base names
}


_EVENT_REWARD_TYPE_LABELS = {
    0: "none",
    1: "speed",
    2: "stamina",
    3: "power",
    4: "guts",
    5: "wit",
    6: "motivation",
    7: "bond",
    10: "vital",
    11: "max_vital",
    30: "skill_points",
    101: "motivation",
    103: "bond",
}


def _event_reward_type_label(value):
    try:
        return _EVENT_REWARD_TYPE_LABELS.get(int(value or 0), f"type_{int(value or 0)}")
    except Exception:
        return str(value or "")


def default_master_mdb_path():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data).parent / "LocalLow" / "Cygames" / "Umamusume" / "master" / "master.mdb"
    return Path.home() / "AppData" / "LocalLow" / "Cygames" / "Umamusume" / "master" / "master.mdb"


def settings_path(base_dir):
    return Path(base_dir) / "settings.json"


def read_settings(base_dir):
    path = settings_path(base_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_settings(base_dir, settings):
    path = settings_path(base_dir)
    payload = json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup_dir = path.parent / "uma_runtime" / "config_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"settings-{int(time.time())}.json"
        try:
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def configured_master_mdb_path(base_dir):
    settings = read_settings(base_dir)
    configured = (settings.get("master_data") or {}).get("master_mdb_path")
    return Path(configured).expanduser() if configured else default_master_mdb_path()


def set_master_mdb_path(base_dir, master_mdb_path):
    settings = read_settings(base_dir)
    master_settings = settings.setdefault("master_data", {})
    master_settings["master_mdb_path"] = str(Path(master_mdb_path).expanduser())
    write_settings(base_dir, settings)
    return status(base_dir)


def path_access(path):
    try:
        return path.exists(), None
    except OSError as exc:
        return False, str(exc)


def status(base_dir):
    db_path = configured_master_mdb_path(base_dir)
    exists, access_error = path_access(db_path)
    return {
        "success": True,
        "master_mdb_path": str(db_path),
        "exists": exists,
        "access_error": access_error,
        "requires_user_action": not exists,
    }


def dump_table(cursor, table):
    cursor.execute(f'SELECT * FROM "{table}";')
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def dump_text_data_category(cursor, category):
    cursor.execute(
        'SELECT id, category, "index", text FROM text_data WHERE category = ?;',
        (category,),
    )
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def text_map(rows):
    return {int(row["index"]): row.get("text", "") for row in rows if row.get("index") is not None}


def display_name(name):
    name = str(name or "").strip()
    if name.startswith("[") and "] " in name:
        return name.split("] ", 1)[1].strip()
    return name


def master_rows(master_data, name):
    return master_data.get("tables", {}).get(name) or master_data.get("text", {}).get(name) or []


def synthesize_skill_data(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    skill_names = text_map(master_rows(master_data, "cat_47_text"))
    skill_costs = {
        int(row["id"]): int(row.get("need_skill_point") or 0)
        for row in master_rows(master_data, "single_mode_skill_need_point")
        if row.get("id") is not None
    }
    skills = {}
    for row in master_rows(master_data, "skill_data"):
        skill_id = int(row.get("id") or 0)
        if not skill_id:
            continue
            
        tags = []
        raw_tags = str(row.get("tag_id") or "")
        if raw_tags:
            tags = [int(t) for t in raw_tags.split("/") if t.isdigit()]

        skills[str(skill_id)] = {
            "name": skill_names.get(skill_id, str(skill_id)),
            "rarity": int(row.get("rarity") or 0),
            "group_id": int(row.get("group_id") or 0),
            "grade_value": int(row.get("grade_value") or 0),
            "need_skill_point": skill_costs.get(skill_id, 0),
            "disable_singlemode": int(row.get("disable_singlemode") or 0),
            "tags": tags,
            "icon_id": int(row.get("icon_id") or 0),
            "skill_category": int(row.get("skill_category") or 0),
        }

    write_json(data_dir / "skill_data.json", skills)
    return {"file": "skill_data.json", "skills": len(skills)}


def synthesize_chara_list(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    names = text_map(master_rows(master_data, "cat_4_text"))
    rows_by_card_id = {}
    for row in master_rows(master_data, "card_rarity_data"):
        card_id = int(row.get("card_id") or 0)
        name = display_name(names.get(card_id, ""))
        if card_id and name:
            rows_by_card_id[card_id] = name

    chara = {}
    name_counts = {}
    for card_id, name in sorted(rows_by_card_id.items()):
        name_counts[name] = name_counts.get(name, 0) + 1
        count = name_counts[name]
        if count == 1:
            display = name
        elif count == 2:
            display = f"{name} (Alt)"
        else:
            display = f"{name} (Alt {count - 1})"
        chara[str(card_id)] = display

    if chara:
        write_json(data_dir / "chara_list.json", chara)
    return {"file": "chara_list.json", "rows": len(chara)}


def synthesize_support_list(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    names = text_map(master_rows(master_data, "cat_75_text"))
    rarity_map = {
        1: "R",
        2: "SR",
        3: "SSR",
    }
    command_type_map = {
        101: "Speed",
        102: "Power",
        103: "Guts",
        105: "Stamina",
        106: "Wisdom",
    }
    support_card_type_map = {
        2: "Friends",
        3: "Group",
    }
    supports = {}
    for row in master_rows(master_data, "support_card_data"):
        support_id = int(row.get("id") or 0)
        if not support_id:
            continue
        key = str(support_id)
        support_type = support_card_type_map.get(int(row.get("support_card_type") or 0))
        if not support_type:
            support_type = command_type_map.get(int(row.get("command_id") or 0), "")
        supports[key] = {
            "name": display_name(names.get(support_id, str(support_id))),
            "rarity": rarity_map.get(int(row.get("rarity") or 0), ""),
            "type": support_type,
        }
    if supports:
        write_json(data_dir / "support_list.json", supports)
    return {"file": "support_list.json", "rows": len(supports)}


GRADE_LABELS = {
    100: "G1",
    200: "G2",
    300: "G3",
    400: "OP",
    700: "PRE-OP",
}

TRACK_LABELS = {
    10001: "Sapporo",
    10002: "Hakodate",
    10003: "Niigata",
    10004: "Fukushima",
    10005: "Nakayama",
    10006: "Tokyo",
    10007: "Chukyo",
    10008: "Kyoto",
    10009: "Hanshin",
    10010: "Kokura",
    10101: "Ooi",
}

MONTH_LABELS = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

YEAR_LABELS = {
    0: "Junior Year",
    24: "Classic Year",
    48: "Senior Year",
}


def distance_label(distance):
    distance = int(distance or 0)
    if distance <= 1400:
        return "Sprint"
    if distance <= 1800:
        return "Mile"
    if distance <= 2400:
        return "Medium"
    return "Long"


def year_offsets_for_permission(race_permission):
    return {
        1: [0],
        2: [24],
        3: [24, 48],
        4: [48],
    }.get(int(race_permission or 0), [])


def race_date_label(month, half, year_offset):
    period = "Early" if int(half or 0) == 1 else "Late"
    return f"{YEAR_LABELS[year_offset]} {period} {MONTH_LABELS[int(month or 0)]}"


def race_turn(month, half, year_offset):
    return int(year_offset or 0) + (int(month or 0) - 1) * 2 + int(half or 0)


def race_occurrence_id(program_id, year_offset):
    year_key = {
        0: 1,
        24: 2,
        48: 3,
    }.get(int(year_offset or 0), 9)
    return year_key * 100000 + int(program_id or 0)


def build_race_context(master_data):
    race_names = text_map(master_rows(master_data, "cat_28_text"))
    races = {int(row.get("id") or 0): row for row in master_rows(master_data, "race")}
    course_sets = {int(row.get("id") or 0): row for row in master_rows(master_data, "race_course_set")}
    instances = {int(row.get("id") or 0): row for row in master_rows(master_data, "race_instance")}
    programs = {}

    for row in master_rows(master_data, "single_mode_program"):
        program_id = int(row.get("id") or 0)
        race_instance_id = int(row.get("race_instance_id") or 0)
        if not program_id or not race_instance_id:
            continue
        instance = instances.get(race_instance_id, {})
        race = races.get(int(instance.get("race_id") or 0), {})
        course = course_sets.get(int(race.get("course_set") or 0), {})
        name = race_names.get(race_instance_id, str(race_instance_id))
        programs[program_id] = {
            "program": row,
            "race_instance_id": race_instance_id,
            "race": race,
            "course": course,
            "name": name,
        }
    return programs


def is_ui_selectable_race(info):
    program = info["program"]
    race = info["race"]
    name = info["name"]
    if int(program.get("base_program_id") or 0) != 0:
        return False
    if not year_offsets_for_permission(program.get("race_permission")):
        return False
    if int(race.get("grade") or 0) not in GRADE_LABELS:
        return False
    if "Make Debut" in name or "Maiden Race" in name:
        return False
    return True


def legacy_race_ids_by_occurrence(existing_meta):
    legacy = {}
    for key, value in (existing_meta or {}).items():
        try:
            race_id = int(key)
            program_id = int((value or {}).get("program_id") or 0)
            turn = int((value or {}).get("turn") or 0)
        except (TypeError, ValueError):
            continue
        if not race_id or not program_id or not turn:
            continue
        if race_id == program_id or race_id >= 100000:
            continue
        legacy.setdefault((program_id, turn), []).append(race_id)
    return {key: sorted(set(value)) for key, value in legacy.items()}


def synthesize_public_race_data(base_dir, race_context, existing_meta=None):
    races = []
    legacy_ids = legacy_race_ids_by_occurrence(existing_meta)
    for program_id, info in sorted(race_context.items()):
        if not is_ui_selectable_race(info):
            continue
        program = info["program"]
        race = info["race"]
        course = info["course"]
        month = int(program.get("month") or 0)
        half = int(program.get("half") or 0)
        for year_offset in year_offsets_for_permission(program.get("race_permission")):
            turn = race_turn(month, half, year_offset)
            row = {
                "id": race_occurrence_id(program_id, year_offset),
                "program_id": program_id,
                "turn": turn,
                "name": info["name"],
                "date": race_date_label(month, half, year_offset),
                "type": GRADE_LABELS.get(int(race.get("grade") or 0), ""),
                "terrain": "Dirt" if int(course.get("ground") or 0) == 2 else "Turf",
                "distance": distance_label(course.get("distance")),
                "venue": TRACK_LABELS.get(int(course.get("race_track_id") or 0), ""),
            }
            row_legacy_ids = legacy_ids.get((program_id, turn), [])
            if row_legacy_ids:
                row["legacy_ids"] = row_legacy_ids
            races.append(row)

    def sort_key(item):
        year_offset = next(offset for offset, label in YEAR_LABELS.items() if item["date"].startswith(label))
        month = MONTH_LABELS.index(item["date"].split()[-1])
        half = 1 if " Early " in item["date"] else 2
        return (year_offset + (month - 1) * 2 + half, item["type"], item["name"], item["id"])

    races.sort(key=sort_key)
    path = Path(base_dir) / "public" / "assets" / "data" / "uma_race_data.json"
    write_json(path, {"races": races})
    return {"file": "public/assets/data/uma_race_data.json", "rows": len(races)}


def synthesize_race_map(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    existing = read_json(data_dir / "race_map.json", {})
    existing_public = read_json(Path(base_dir) / "public" / "assets" / "data" / "uma_race_data.json", {})
    race_context = build_race_context(master_data)
    fan_counts = first_place_fans_by_set(master_data)
    programs = {}
    instances = {}
    meta = {}

    for program_id, info in sorted(race_context.items()):
        row = info["program"]
        race_instance_id = info["race_instance_id"]
        course = info["course"]
        month = int(row.get("month") or 0)
        half = int(row.get("half") or 0)
        programs[str(program_id)] = {
            "race_instance_id": race_instance_id,
            "month": month,
            "half": half,
            "name": info["name"],
            "ground": int(course.get("ground") or 0),
            "distance": int(course.get("distance") or 0),
            "fan_set_id": int(row.get("fan_set_id") or 0),
            "fans": int(fan_counts.get(int(row.get("fan_set_id") or 0), 0) or 0),
            "need_fan_count": int(row.get("need_fan_count") or 0),
            "reward_set_id": int(row.get("reward_set_id") or 0),
        }
        instances.setdefault(str(race_instance_id), []).append(program_id)
        for year_offset in year_offsets_for_permission(row.get("race_permission")):
            occurrence_id = race_occurrence_id(program_id, year_offset)
            meta[str(occurrence_id)] = {
                "program_id": program_id,
                "race_instance_id": race_instance_id,
                "turn": race_turn(month, half, year_offset),
                "name": info["name"],
            }

    if programs:
        public_result = synthesize_public_race_data(base_dir, race_context, existing.get("meta") or {})
        current_public = read_json(Path(base_dir) / "public" / "assets" / "data" / "uma_race_data.json", {})
        generated_by_key = {
            (row["name"], row["date"]): row
            for row in current_public.get("races", [])
        }
        for row in existing_public.get("races", []):
            generated = generated_by_key.get((row.get("name"), row.get("date")))
            if not generated:
                continue
            legacy_id = int(row.get("id") or 0)
            program_id = int(generated.get("program_id") or generated.get("id") or 0)
            if not legacy_id or not program_id or legacy_id == program_id:
                continue
            info = race_context.get(program_id)
            if not info:
                continue
            program = info["program"]
            year_offset = next(offset for offset, label in YEAR_LABELS.items() if row["date"].startswith(label))
            turn = race_turn(program.get("month"), program.get("half"), year_offset)
            meta[str(legacy_id)] = {
                "program_id": program_id,
                "race_instance_id": info["race_instance_id"],
                "turn": turn,
                "name": info["name"],
            }

        for key, value in (existing.get("meta") or {}).items():
            if str(key) in meta:
                continue
            program_id = int((value or {}).get("program_id") or 0)
            if program_id in race_context:
                meta[str(key)] = value

        output = {
            "meta": meta,
            "program": programs,
            "instance": {key: sorted(value) for key, value in instances.items()},
        }
        write_json(data_dir / "race_map.json", output)
        return {
            "file": "race_map.json",
            "programs": len(programs),
            "instances": len(instances),
            "meta": len(meta),
            "public_races": public_result["rows"],
        }

    write_json(data_dir / "race_map.json", existing)
    return {"file": "race_map.json", "programs": 0, "instances": 0, "preserved_existing": bool(existing)}


def factor_category(factor_id):
    text = str(factor_id)
    if len(text) == 3:
        return "stat"
    if len(text) == 4:
        return "aptitude"
    if len(text) == 7:
        if text.startswith("1"):
            return "race"
        if text.startswith("2"):
            return "skill"
        if text.startswith("3"):
            return "scenario"
    if len(text) == 8:
        return "unique"
    return "other"


def synthesize_factor_map(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    factors = {}
    for row in master_rows(master_data, "cat_147_text"):
        factor_id = int(row.get("index") or 0)
        if not factor_id:
            continue
        factors[str(factor_id)] = {
            "name": row.get("text", ""),
            "stars": factor_id % 10,
            "category": factor_category(factor_id),
        }

    if factors:
        write_json(data_dir / "factor_map.json", factors)
    return {"file": "factor_map.json", "rows": len(factors)}



def aptitude_rank(value):
    return {
        8: "S",
        7: "A",
        6: "B",
        5: "C",
        4: "D",
        3: "E",
        2: "F",
        1: "G",
        0: "G",
    }.get(int(value or 0), str(value or "G"))


def write_core_pair(data_dir, stem, data):
    """Write JSON and CSV-friendly JSON source data into Sweepy's data folder."""
    path = data_dir / f"{stem}.json"
    write_json(path, data)
    return {"file": f"{stem}.json", "rows": len(data) if hasattr(data, "__len__") else 0}


def first_place_fans_by_set(master_data):
    result = {}
    for row in master_rows(master_data, "single_mode_fan_count"):
        try:
            if int(row.get("order") or 0) != 1:
                continue
            result[int(row.get("fan_set_id") or 0)] = int(row.get("fan_count") or 0)
        except Exception:
            continue
    return result


def synthesize_tp_restore_items_core(base_dir, master_data):
    """Generate master-data-backed TP restore item metadata.

    The UI feature is specifically labelled Toughness 30, so the `kind` field is
    only `toughness_30` for the exact item named Toughness 30. Other 30 TP
    restore items are preserved as generic `tp_restore_30` metadata for future
    diagnostics, but the TP restore selector should only auto-use Toughness 30.
    """
    data_dir = Path(base_dir) / "data"
    item_names = text_map(master_rows(master_data, "cat_23_text"))
    item_desc = text_map(master_rows(master_data, "cat_10_text"))
    rows = []
    for item in master_rows(master_data, "item_data"):
        try:
            item_id = int(item.get("id") or 0)
            category = int(item.get("item_category") or 0)
            effect_type = int(item.get("effect_type_1") or 0)
            effect_value = int(item.get("effect_value_1") or 0)
        except Exception:
            continue
        if not item_id or category != 20 or effect_type != 2 or effect_value <= 0:
            continue
        name = str(item_names.get(item_id, item_id))
        desc = str(item_desc.get(item_id, ""))
        kind = "toughness_30" if name.strip().lower() == "toughness 30" and effect_value == 30 else f"tp_restore_{effect_value}"
        rows.append({
            "item_id": item_id,
            "name": name,
            "description": desc,
            "item_category": category,
            "effect_type": effect_type,
            "tp_restore": effect_value,
            "kind": kind,
        })
    rows.sort(key=lambda row: (0 if row["kind"] == "toughness_30" else 1, row["item_id"]))
    write_json(data_dir / "tp_restore_items_core.json", rows)
    return {"file": "tp_restore_items_core.json", "items": len(rows)}


def synthesize_win_saddle_core(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    names = text_map(master_rows(master_data, "cat_111_text"))
    race_by_instance = {}
    for row in master_rows(master_data, "race_instance"):
        try:
            race_by_instance[int(row.get("id") or 0)] = int(row.get("race_id") or 0)
        except Exception:
            continue
    race_by_id = {
        int(row.get("id") or 0): row
        for row in master_rows(master_data, "race")
        if row.get("id") is not None
    }
    rows = []
    for row in master_rows(master_data, "single_mode_wins_saddle"):
        try:
            sid = int(row.get("id") or 0)
        except Exception:
            continue
        if not sid:
            continue
        race_instance_ids = []
        grades = []
        for idx in range(1, 9):
            try:
                rid = int(row.get(f"race_instance_id_{idx}") or 0)
            except Exception:
                rid = 0
            if not rid:
                continue
            race_instance_ids.append(rid)
            race_id = race_by_instance.get(rid, 0)
            grade_raw = int((race_by_id.get(race_id) or {}).get("grade") or 0)
            if grade_raw:
                grades.append(GRADE_LABELS.get(grade_raw, str(grade_raw)))
        rows.append({
            "id": sid,
            "name": names.get(sid, str(sid)),
            "priority": int(row.get("priority") or 0),
            "group_id": int(row.get("group_id") or 0),
            "condition": int(row.get("condition") or 0),
            "win_saddle_type": int(row.get("win_saddle_type") or 0),
            "race_instance_ids": race_instance_ids,
            "grades": grades,
        })
    rows.sort(key=lambda row: (row["priority"], row["id"]))
    write_json(data_dir / "win_saddle_core.json", rows)
    return {"file": "win_saddle_core.json", "rows": len(rows)}


def synthesize_career_rank_thresholds_core(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in master_rows(master_data, "single_mode_rank"):
        try:
            rows.append({
                "id": int(row.get("id") or 0),
                "min_value": int(row.get("min_value") or 0),
                "max_value": int(row.get("max_value") or 0),
            })
        except Exception:
            continue
    rows.sort(key=lambda row: row["min_value"])
    write_json(data_dir / "career_rank_thresholds_core.json", rows)
    return {"file": "career_rank_thresholds_core.json", "rows": len(rows)}


def synthesize_race_planner_core(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    rows = []
    race_context = build_race_context(master_data)
    fan_counts = first_place_fans_by_set(master_data)
    for program_id, info in sorted(race_context.items()):
        program = info["program"]
        race = info["race"]
        course = info["course"]
        month = int(program.get("month") or 0)
        half = int(program.get("half") or 0)
        grade = GRADE_LABELS.get(int(race.get("grade") or 0), str(race.get("grade") or ""))
        fan_set_id = int(program.get("fan_set_id") or 0)
        fans = int(fan_counts.get(fan_set_id, 0) or 0)
        for year_offset in year_offsets_for_permission(program.get("race_permission")):
            rows.append({
                "program_id": int(program_id),
                "occurrence_id": race_occurrence_id(program_id, year_offset),
                "race_instance_id": int(info.get("race_instance_id") or 0),
                "turn": race_turn(month, half, year_offset),
                "date": race_date_label(month, half, year_offset),
                "name": info["name"],
                "grade": grade,
                "grade_raw": int(race.get("grade") or 0),
                "terrain": "Dirt" if int(course.get("ground") or 0) == 2 else "Turf",
                "ground": int(course.get("ground") or 0),
                "distance": distance_label(course.get("distance")),
                "distance_m": int(course.get("distance") or 0),
                "venue": TRACK_LABELS.get(int(course.get("race_track_id") or 0), str(course.get("race_track_id") or "")),
                "race_track_id": int(course.get("race_track_id") or 0),
                "month": month,
                "half": half,
                "permission": int(program.get("race_permission") or 0),
                "fan_set_id": fan_set_id,
                "fans": fans,
                "need_fan_count": int(program.get("need_fan_count") or 0),
                "reward_set_id": int(program.get("reward_set_id") or 0),
            })
    rows.sort(key=lambda row: (row["turn"], row["grade_raw"], row["program_id"]))
    return write_core_pair(data_dir, "race_planner_core", rows)


def synthesize_skill_weighting_core(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    skill_names = text_map(master_rows(master_data, "cat_47_text"))
    costs = {
        int(row["id"]): int(row.get("need_skill_point") or 0)
        for row in master_rows(master_data, "single_mode_skill_need_point")
        if row.get("id") is not None
    }
    rows = []
    for row in master_rows(master_data, "skill_data"):
        skill_id = int(row.get("id") or 0)
        if not skill_id:
            continue
        raw_tags = str(row.get("tag_id") or "")
        tags = [int(t) for t in raw_tags.split("/") if t.lstrip("-").isdigit()]
        ability_types = []
        for key, value in row.items():
            if key.startswith("ability_type_") and int(value or 0):
                ability_types.append(int(value))
        conditions = [str(row.get("condition_1") or ""), str(row.get("condition_2") or "")]
        rows.append({
            "skill_id": skill_id,
            "name": skill_names.get(skill_id, str(skill_id)),
            "rarity": int(row.get("rarity") or 0),
            "group_id": int(row.get("group_id") or 0),
            "group_rate": int(row.get("group_rate") or 0),
            "grade_value": int(row.get("grade_value") or 0),
            "cost": costs.get(skill_id, 0),
            "skill_category": int(row.get("skill_category") or 0),
            "tags": tags,
            "icon_id": int(row.get("icon_id") or 0),
            "activate_lot": int(row.get("activate_lot") or 0),
            "ability_types": sorted(set(ability_types)),
            "conditions": [c for c in conditions if c],
            "disable_singlemode": int(row.get("disable_singlemode") or 0),
            "is_general_skill": int(row.get("is_general_skill") or 0),
        })
    rows.sort(key=lambda row: (row["group_id"], row["rarity"], row["skill_id"]))
    return write_core_pair(data_dir, "skill_weighting_core", rows)


def synthesize_trainee_profiles_core(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    card_names = text_map(master_rows(master_data, "cat_4_text"))
    card_data = {int(row.get("id") or 0): row for row in master_rows(master_data, "card_data")}
    chara_data = {int(row.get("id") or 0): row for row in master_rows(master_data, "chara_data")}
    rows = []
    for row in master_rows(master_data, "card_rarity_data"):
        card_id = int(row.get("card_id") or 0)
        if not card_id:
            continue
        card = card_data.get(card_id, {})
        chara_id = int(card.get("chara_id") or card_id // 100 or 0)
        chara = chara_data.get(chara_id, {})
        rows.append({
            "card_id": card_id,
            "chara_id": chara_id,
            "name": display_name(card_names.get(card_id, str(card_id))),
            "rarity": int(row.get("rarity") or card.get("default_rarity") or 0),
            "base_stats": {
                "speed": int(row.get("speed") or 0),
                "stamina": int(row.get("stamina") or 0),
                "power": int(row.get("pow") or 0),
                "guts": int(row.get("guts") or 0),
                "wit": int(row.get("wiz") or 0),
            },
            "max_stats": {
                "speed": int(row.get("max_speed") or 0),
                "stamina": int(row.get("max_stamina") or 0),
                "power": int(row.get("max_pow") or 0),
                "guts": int(row.get("max_guts") or 0),
                "wit": int(row.get("max_wiz") or 0),
            },
            "growth": {
                "speed": int(card.get("talent_speed") or 0),
                "stamina": int(card.get("talent_stamina") or 0),
                "power": int(card.get("talent_pow") or 0),
                "guts": int(card.get("talent_guts") or 0),
                "wit": int(card.get("talent_wiz") or 0),
            },
            "distance_aptitude": {
                "sprint": aptitude_rank(row.get("proper_distance_short")),
                "mile": aptitude_rank(row.get("proper_distance_mile")),
                "medium": aptitude_rank(row.get("proper_distance_middle")),
                "long": aptitude_rank(row.get("proper_distance_long")),
            },
            "style_aptitude": {
                "front": aptitude_rank(row.get("proper_running_style_nige")),
                "pace": aptitude_rank(row.get("proper_running_style_senko")),
                "late": aptitude_rank(row.get("proper_running_style_sashi")),
                "end": aptitude_rank(row.get("proper_running_style_oikomi")),
            },
            "track_aptitude": {
                "turf": aptitude_rank(row.get("proper_ground_turf")),
                "dirt": aptitude_rank(row.get("proper_ground_dirt")),
            },
            "ui_colors": {
                "main": chara.get("ui_color_main", ""),
                "sub": chara.get("ui_color_sub", ""),
                "border": chara.get("ui_border_color", ""),
            },
            "available_skill_set_id": int(card.get("available_skill_set_id") or row.get("skill_set") or 0),
            "running_style": int(card.get("running_style") or chara.get("race_running_type") or 0),
        })
    rows.sort(key=lambda row: (row["name"], row["card_id"], row["rarity"]))
    generated_profiles = {}
    for row in rows:
        name = row["name"]
        generated_profiles[name] = {
            "name": name,
            "card_id": row["card_id"],
            "profile_source": "master_mdb",
            "track_aptitude": row["track_aptitude"],
            "distance_aptitude": row["distance_aptitude"],
            "style_aptitude": row["style_aptitude"],
            "recommended_style": {
                1: "front", 2: "pace", 3: "late", 4: "end",
            }.get(int(row.get("running_style") or 0), ""),
            "primary_distances": [
                key for key, value in row["distance_aptitude"].items()
                if value in {"S", "A", "B"}
            ],
            "secondary_distances": [
                key for key, value in row["distance_aptitude"].items()
                if value == "C"
            ],
            "avoid_distances": [
                key for key, value in row["distance_aptitude"].items()
                if value in {"D", "E", "F", "G"}
            ],
            "growth": row["growth"],
            "target_stats": row["max_stats"],
            "preferred_skill_fragments": [],
            "avoid_skill_fragments": [],
            "green_skill_cap": 1,
        }
    if generated_profiles:
        write_json(data_dir / "trainee_skill_profiles.generated.json", generated_profiles)
    result = write_core_pair(data_dir, "trainee_profiles_core", rows)
    result["generated_profiles"] = len(generated_profiles)
    return result


def synthesize_support_cards_core(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    names = text_map(master_rows(master_data, "cat_75_text"))
    effects = {}
    for row in master_rows(master_data, "support_card_effect_table"):
        card_id = int(row.get("id") or 0)
        if not card_id:
            continue
        effects.setdefault(str(card_id), []).append(dict(row))
    unique = {}
    for row in master_rows(master_data, "support_card_unique_effect"):
        card_id = int(row.get("id") or 0)
        if not card_id:
            continue
        unique.setdefault(str(card_id), []).append(dict(row))
    rows = []
    for row in master_rows(master_data, "support_card_data"):
        support_id = int(row.get("id") or 0)
        if not support_id:
            continue
        rows.append({
            "support_card_id": support_id,
            "name": display_name(names.get(support_id, str(support_id))),
            "rarity": int(row.get("rarity") or 0),
            "command_id": int(row.get("command_id") or 0),
            "support_card_type": int(row.get("support_card_type") or 0),
            "effect_rows": effects.get(str(support_id), []),
            "unique_effect_rows": unique.get(str(support_id), []),
        })
    rows.sort(key=lambda row: (row["rarity"], row["support_card_id"]))
    return write_core_pair(data_dir, "support_cards_core", rows)


def synthesize_succession_core(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    names = text_map(master_rows(master_data, "cat_147_text"))
    effects_by_group = {}
    for row in master_rows(master_data, "succession_factor_effect"):
        group_id = int(row.get("factor_group_id") or 0)
        effects_by_group.setdefault(group_id, []).append({
            "effect_id": int(row.get("effect_id") or 0),
            "target_type": int(row.get("target_type") or 0),
            "value_1": int(row.get("value_1") or 0),
            "value_2": int(row.get("value_2") or 0),
        })
    factors = []
    for row in master_rows(master_data, "succession_factor"):
        factor_id = int(row.get("factor_id") or 0)
        group_id = int(row.get("factor_group_id") or 0)
        if not factor_id:
            continue
        factors.append({
            "factor_id": factor_id,
            "factor_group_id": group_id,
            "name": names.get(factor_id, str(factor_id)),
            "rarity": int(row.get("rarity") or 0),
            "grade": int(row.get("grade") or 0),
            "factor_type": int(row.get("factor_type") or 0),
            "category": factor_category(factor_id),
            "effects": effects_by_group.get(group_id, []),
        })
    relations = {}
    points = {
        int(row.get("relation_type") or 0): int(row.get("relation_point") or 0)
        for row in master_rows(master_data, "succession_relation")
    }
    for row in master_rows(master_data, "succession_relation_member"):
        relation_type = int(row.get("relation_type") or 0)
        chara_id = int(row.get("chara_id") or 0)
        if relation_type and chara_id:
            relations.setdefault(str(relation_type), {"point": points.get(relation_type, 0), "members": []})["members"].append(chara_id)
    rentals = [dict(row) for row in master_rows(master_data, "succession_rental")]
    payload = {"factors": factors, "relations": relations, "rentals": rentals}
    write_json(data_dir / "succession_core.json", payload)
    return {"file": "succession_core.json", "factors": len(factors), "relations": len(relations), "rentals": len(rentals)}


def synthesize_mant_shop_core(base_dir, master_data):
    data_dir = Path(base_dir) / "data"
    item_names = text_map(master_rows(master_data, "cat_225_text"))
    effects_by_group = {}
    for row in master_rows(master_data, "single_mode_free_shop_effect"):
        group_id = int(row.get("effect_group_id") or 0)
        effects_by_group.setdefault(group_id, []).append({
            "effect_type": int(row.get("effect_type") or 0),
            "effect_value_1": int(row.get("effect_value_1") or 0),
            "effect_value_2": int(row.get("effect_value_2") or 0),
            "effect_value_3": int(row.get("effect_value_3") or 0),
            "effect_value_4": int(row.get("effect_value_4") or 0),
            "turn": int(row.get("turn") or 0),
        })
    shops = [dict(row) for row in master_rows(master_data, "single_mode_free_shop")]
    rows = []
    for row in master_rows(master_data, "single_mode_free_shop_item"):
        item_id = int(row.get("item_id") or 0)
        group_id = int(row.get("effect_group_id") or 0)
        rows.append({
            "shop_item_master_id": int(row.get("id") or 0),
            "item_id": item_id,
            "name": item_names.get(item_id, str(item_id)),
            "coin_num": int(row.get("coin_num") or 0),
            "limit_num": int(row.get("limit_num") or 0),
            "effect_group_id": group_id,
            "effect_group": int(row.get("effect_group") or 0),
            "effect_priority": int(row.get("effect_priority") or 0),
            "use_flag": int(row.get("use_flag") or 0),
            "effects": effects_by_group.get(group_id, []),
        })
    payload = {"items": rows, "shops": shops}
    write_json(data_dir / "mant_shop_core.json", payload)
    return {"file": "mant_shop_core.json", "items": len(rows), "shops": len(shops)}




def synthesize_chara_route_core(base_dir, master_data):
    """Generate official per-trainee route/race requirement metadata.

    These rows come from the static master database and are used as hints for
    Smart Race Solver and diagnostics. They do not force choices by themselves;
    runtime route payloads still win when available.
    """
    data_dir = Path(base_dir) / "data"
    race_context = build_race_context(master_data)
    programs_by_instance = {}
    for program_id, info in race_context.items():
        try:
            programs_by_instance.setdefault(int(info.get("race_instance_id") or 0), []).append(int(program_id))
        except Exception:
            continue
    routes_by_set = {}
    for row in master_rows(master_data, "single_mode_route_race"):
        try:
            race_set_id = int(row.get("race_set_id") or 0)
        except Exception:
            continue
        routes_by_set.setdefault(race_set_id, []).append(row)
    conditions_by_set = {}
    for row in master_rows(master_data, "single_mode_route_condition"):
        try:
            condition_set_id = int(row.get("condition_set_id") or 0)
        except Exception:
            continue
        conditions_by_set.setdefault(condition_set_id, []).append(dict(row))
    rows = []
    for route in master_rows(master_data, "single_mode_route"):
        try:
            route_id = int(route.get("id") or 0)
            chara_id = int(route.get("chara_id") or 0)
            race_set_id = int(route.get("race_set_id") or 0)
            condition_set_id = int(route.get("condition_set_id") or 0)
        except Exception:
            continue
        if not route_id or not chara_id or not race_set_id:
            continue
        for rr in routes_by_set.get(race_set_id, []):
            try:
                turn = int(rr.get("turn") or 0)
                condition_id = int(rr.get("condition_id") or 0)
            except Exception:
                turn = 0
                condition_id = 0
            candidate_programs = []
            if condition_id:
                if condition_id in race_context:
                    candidate_programs = [condition_id]
                else:
                    candidate_programs = sorted(programs_by_instance.get(condition_id, []))
            race_name = ""
            if candidate_programs:
                race_name = (race_context.get(candidate_programs[0]) or {}).get("name") or ""
            rows.append({
                "route_id": route_id,
                "scenario_id": int(route.get("scenario_id") or 0),
                "chara_id": chara_id,
                "race_set_id": race_set_id,
                "condition_set_id": condition_set_id,
                "priority": int(route.get("priority") or 0),
                "sort_id": int(rr.get("sort_id") or 0),
                "turn": turn,
                "target_type": int(rr.get("target_type") or 0),
                "race_type": int(rr.get("race_type") or 0),
                "condition_type": int(rr.get("condition_type") or 0),
                "condition_id": condition_id,
                "condition_value_1": int(rr.get("condition_value_1") or 0),
                "condition_value_2": int(rr.get("condition_value_2") or 0),
                "determine_race": int(rr.get("determine_race") or 0),
                "determine_race_flag": int(rr.get("determine_race_flag") or 0),
                "candidate_program_ids": candidate_programs,
                "race_name": race_name,
                "route_conditions": conditions_by_set.get(condition_set_id, []),
            })
    rows.sort(key=lambda row: (row["chara_id"], row["scenario_id"], row["priority"], row["turn"], row["sort_id"]))
    return write_core_pair(data_dir, "chara_route_core", rows)


def synthesize_rival_races_core(base_dir, master_data):
    """Generate static rival-race hints from master.mdb."""
    data_dir = Path(base_dir) / "data"
    chara_names = text_map(master_rows(master_data, "cat_4_text"))
    race_context = build_race_context(master_data)
    rows = []
    for row in master_rows(master_data, "single_mode_rival"):
        try:
            program_id = int(row.get("race_program_id") or 0)
            chara_id = int(row.get("chara_id") or 0)
            rival_chara_id = int(row.get("rival_chara_id") or 0)
        except Exception:
            continue
        info = race_context.get(program_id) or {}
        rows.append({
            "id": int(row.get("id") or 0),
            "chara_id": chara_id,
            "turn": int(row.get("turn") or 0),
            "race_program_id": program_id,
            "race_name": info.get("name") or "",
            "rival_flag_id": int(row.get("rival_flag_id") or 0),
            "condition_type": int(row.get("condition_type") or 0),
            "rival_chara_id": rival_chara_id,
            "rival_name": display_name(chara_names.get(rival_chara_id * 100 + 1, chara_names.get(rival_chara_id, str(rival_chara_id)))) if rival_chara_id else "",
            "single_mode_npc_id": int(row.get("single_mode_npc_id") or 0),
            "frame_order": int(row.get("frame_order") or 0),
        })
    rows.sort(key=lambda row: (row["chara_id"], row["turn"], row["race_program_id"], row["frame_order"]))
    return write_core_pair(data_dir, "rival_races_core", rows)


_NPC_APT_LETTERS = {1: "G", 2: "F", 3: "E", 4: "D", 5: "C", 6: "B", 7: "A", 8: "S"}


def _npc_apt_letter(value):
    try:
        return _NPC_APT_LETTERS.get(int(value or 0), "")
    except (TypeError, ValueError):
        return ""


def synthesize_single_mode_npc_core(base_dir, master_data):
    """Export career-mode NPC (rival/competitor) stat blocks from master.mdb.

    rival_races_core references opponents by single_mode_npc_id but only carries
    their identity (who/where/when). This companion table -- single_mode_npc --
    carries their actual stat block and aptitudes, which a race win-probability
    model needs to estimate field strength. Keyed by NPC id; npc_group_id is
    retained so callers can join either way. Aptitude integers (1-8) are also
    surfaced as letter grades (G..S) for readability.
    """
    data_dir = Path(base_dir) / "data"
    chara_names = text_map(master_rows(master_data, "cat_4_text"))
    rows = []
    for row in master_rows(master_data, "single_mode_npc"):
        try:
            npc_id = int(row.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not npc_id:
            continue
        chara_id = int(row.get("chara_id") or 0)
        rows.append({
            "id": npc_id,
            "npc_group_id": int(row.get("npc_group_id") or 0),
            "chara_id": chara_id,
            "name": display_name(chara_names.get(chara_id * 100 + 1, chara_names.get(chara_id, str(chara_id)))) if chara_id else "",
            "mob_id": int(row.get("mob_id") or 0),
            "speed": int(row.get("speed") or 0),
            "stamina": int(row.get("stamina") or 0),
            "power": int(row.get("pow") or 0),
            "guts": int(row.get("guts") or 0),
            "wit": int(row.get("wiz") or 0),
            "aptitude": {
                "distance": {
                    "short": _npc_apt_letter(row.get("proper_distance_short")),
                    "mile": _npc_apt_letter(row.get("proper_distance_mile")),
                    "medium": _npc_apt_letter(row.get("proper_distance_middle")),
                    "long": _npc_apt_letter(row.get("proper_distance_long")),
                },
                "style": {
                    "front": _npc_apt_letter(row.get("proper_running_style_nige")),
                    "pace": _npc_apt_letter(row.get("proper_running_style_senko")),
                    "late": _npc_apt_letter(row.get("proper_running_style_sashi")),
                    "end": _npc_apt_letter(row.get("proper_running_style_oikomi")),
                },
                "ground": {
                    "turf": _npc_apt_letter(row.get("proper_ground_turf")),
                    "dirt": _npc_apt_letter(row.get("proper_ground_dirt")),
                },
            },
            "skill_set_id": int(row.get("skill_set_id") or 0),
            "motivation_min": int(row.get("motivation_min") or 0),
            "motivation_max": int(row.get("motivation_max") or 0),
        })
    rows.sort(key=lambda r: (r["npc_group_id"], r["id"]))
    return write_core_pair(data_dir, "single_mode_npc_core", rows)


def synthesize_trackblazer_race_rewards_core(base_dir, master_data):
    """Generate Trackblazer-specific race reward metadata.

    Coin and win-point tables are Trackblazer/MANT-specific and make race value
    more precise than grade/fan heuristics alone.
    """
    data_dir = Path(base_dir) / "data"
    coin_by_grade = {}
    for row in master_rows(master_data, "single_mode_free_coin_race"):
        try:
            grade = int(row.get("grade") or 0)
        except Exception:
            continue
        coin_by_grade.setdefault(grade, []).append({
            "order_min": int(row.get("order_min") or 0),
            "order_max": int(row.get("order_max") or 0),
            "coin_num": int(row.get("coin_num") or 0),
        })
    win_points_by_group_grade = {}
    for row in master_rows(master_data, "single_mode_free_win_point"):
        try:
            race_group_id = int(row.get("race_group_id") or 0)
            grade = int(row.get("grade") or 0)
        except Exception:
            continue
        win_points_by_group_grade.setdefault(f"{race_group_id}:{grade}", []).append({
            "order_min": int(row.get("order_min") or 0),
            "order_max": int(row.get("order_max") or 0),
            "point_num": int(row.get("point_num") or 0),
        })
    race_groups = {}
    for row in master_rows(master_data, "single_mode_race_group"):
        try:
            program_id = int(row.get("race_program_id") or 0)
            group_id = int(row.get("race_group_id") or 0)
        except Exception:
            continue
        if program_id:
            race_groups.setdefault(program_id, []).append(group_id)
    reward_sets = {}
    for row in master_rows(master_data, "single_mode_reward_set"):
        try:
            reward_set_id = int(row.get("reward_set_id") or 0)
        except Exception:
            continue
        reward_sets.setdefault(reward_set_id, []).append({
            "order_min": int(row.get("order_min") or 0),
            "order_max": int(row.get("order_max") or 0),
            "reward_type": int(row.get("reward_type") or 0),
            "bonus": int(row.get("bonus") or 0),
            "odds": int(row.get("odds") or 0),
            "item_category": int(row.get("item_category") or 0),
            "item_id": int(row.get("item_id") or 0),
            "item_num": int(row.get("item_num") or 0),
        })
    race_context = build_race_context(master_data)
    fan_counts = first_place_fans_by_set(master_data)
    rows = []
    for program_id, info in sorted(race_context.items()):
        program = info["program"]
        race = info["race"]
        grade_raw = int(race.get("grade") or 0)
        groups = sorted(set(race_groups.get(int(program_id), [])))
        win_point_rows = []
        for group_id in [0] + groups:
            win_point_rows.extend(win_points_by_group_grade.get(f"{group_id}:{grade_raw}", []))
        # Deduplicate rows in case generic + group-specific rows overlap.
        seen = set()
        deduped = []
        for item in win_point_rows:
            key = (item["order_min"], item["order_max"], item["point_num"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        fan_set_id = int(program.get("fan_set_id") or 0)
        reward_set_id = int(program.get("reward_set_id") or 0)
        rows.append({
            "program_id": int(program_id),
            "race_instance_id": int(info.get("race_instance_id") or 0),
            "name": info.get("name") or "",
            "grade": GRADE_LABELS.get(grade_raw, str(grade_raw)),
            "grade_raw": grade_raw,
            "race_group_ids": groups,
            "fan_set_id": fan_set_id,
            "fans_first": int(fan_counts.get(fan_set_id, 0) or 0),
            "reward_set_id": reward_set_id,
            "coin_rewards": sorted(coin_by_grade.get(grade_raw, []), key=lambda r: (r["order_min"], r["order_max"])),
            "win_point_rewards": sorted(deduped, key=lambda r: (r["order_min"], r["order_max"])),
            "reward_set": reward_sets.get(reward_set_id, []),
        })
    rows.sort(key=lambda row: row["program_id"])
    return write_core_pair(data_dir, "trackblazer_race_rewards_core", rows)


def synthesize_race_performance_rates_core(base_dir, master_data):
    """Export official race aptitude/mood/popularity rate tables."""
    data_dir = Path(base_dir) / "data"

    def keyed_rows(table, key="id"):
        out = {}
        for row in master_rows(master_data, table):
            try:
                rid = int(row.get(key) or 0)
            except Exception:
                continue
            out[str(rid)] = {k: int(v) if isinstance(v, int) or str(v).lstrip("-").isdigit() else v for k, v in dict(row).items()}
        return out

    payload = {
        "distance_rate": keyed_rows("race_proper_distance_rate"),
        "ground_rate": keyed_rows("race_proper_ground_rate"),
        "runningstyle_rate": keyed_rows("race_proper_runningstyle_rate"),
        "motivation_rate": keyed_rows("race_motivation_rate"),
        "course_set_status": keyed_rows("race_course_set_status", key="course_set_status_id"),
        "popularity_proper_value": [dict(row) for row in master_rows(master_data, "race_popularity_proper_value")],
        "scale": 10000,
    }
    write_json(data_dir / "race_performance_rates_core.json", payload)
    return {
        "file": "race_performance_rates_core.json",
        "distance": len(payload["distance_rate"]),
        "ground": len(payload["ground_rate"]),
        "runningstyle": len(payload["runningstyle_rate"]),
        "motivation": len(payload["motivation_rate"]),
    }


def _target_label(target_type):
    return {
        1: "speed",
        2: "stamina",
        3: "power",
        4: "guts",
        5: "wit",
        10: "energy",
        30: "skill_points",
    }.get(int(target_type or 0), str(target_type or ""))


def synthesize_training_effects_core(base_dir, master_data):
    """Export official base training effects by scenario/command/level.

    The live API remains the primary source for per-turn training gains. This
    master-data export gives Pre Icarus a stable baseline for logging, fallback
    scoring, and anomaly/debug traces when the live command payload is sparse.
    """
    data_dir = Path(base_dir) / "data"
    training_rows = {}
    for row in master_rows(master_data, "single_mode_training"):
        try:
            command_id = int(row.get("command_id") or 0)
            level = int(row.get("command_level") or row.get("sub_id") or 0)
        except Exception:
            continue
        if command_id and level:
            training_rows[(command_id, level)] = dict(row)

    grouped = {}
    for row in master_rows(master_data, "single_mode_training_effect"):
        try:
            scenario_id = int(row.get("scenario_id") or 0)
            command_id = int(row.get("command_id") or 0)
            level = int(row.get("sub_id") or 0)
            result_state = int(row.get("result_state") or 0)
            target_type = int(row.get("target_type") or 0)
            value = int(row.get("effect_value") or 0)
        except Exception:
            continue
        if not scenario_id or not command_id or not level:
            continue
        key = (scenario_id, command_id, level, result_state)
        item = grouped.setdefault(key, {
            "scenario_id": scenario_id,
            "command_id": command_id,
            "level": level,
            "result_state": result_state,
            "command_type": int((training_rows.get((command_id, level)) or {}).get("command_type") or 0),
            "base_command_id": int((training_rows.get((command_id, level)) or {}).get("base_command_id") or command_id),
            "failure_rate_basis_points": int((training_rows.get((command_id, level)) or {}).get("failure_rate") or 0),
            "max_chara_num": int((training_rows.get((command_id, level)) or {}).get("max_chara_num") or 0),
            "effects": [],
            "by_target": {},
            "stat_total": 0,
            "skill_points": 0,
            "energy_delta": 0,
        })
        label = _target_label(target_type)
        item["effects"].append({
            "target_type": target_type,
            "target": label,
            "effect_value": value,
        })
        item["by_target"][label] = item["by_target"].get(label, 0) + value
        if label in {"speed", "stamina", "power", "guts", "wit"}:
            item["stat_total"] += value
        elif label == "skill_points":
            item["skill_points"] += value
        elif label == "energy":
            item["energy_delta"] += value

    rows = sorted(grouped.values(), key=lambda r: (r["scenario_id"], r["command_id"], r["level"], r["result_state"]))
    plate_rows = []
    for row in master_rows(master_data, "single_mode_free_training_plate"):
        try:
            plate_rows.append({
                "id": int(row.get("id") or 0),
                "condition_type": int(row.get("condition_type") or 0),
                "value_min": int(row.get("value_min") or 0),
                "value_max": int(row.get("value_max") or 0),
            })
        except Exception:
            continue
    payload = {"training_effects": rows, "training_plates": plate_rows}
    write_json(data_dir / "training_effects_core.json", payload)
    return {"file": "training_effects_core.json", "rows": len(rows), "plates": len(plate_rows)}


_PERIOD_LABELS = {
    0: "regular",
    1: "pre_debut",
    2: "summer",
    3: "finale",
}

_HALF_LABELS = {1: "early", 2: "late"}


def synthesize_scenario_turns_core(base_dir, master_data):
    """Export official scenario turn calendars from master.mdb."""
    data_dir = Path(base_dir) / "data"
    scenarios = {}
    for row in master_rows(master_data, "single_mode_scenario"):
        try:
            sid = int(row.get("id") or 0)
        except Exception:
            continue
        if sid:
            scenarios[int(row.get("turn_set_id") or 0)] = {
                "scenario_id": sid,
                "sort_id": int(row.get("sort_id") or 0),
                "turn_set_id": int(row.get("turn_set_id") or 0),
                "chara_program_change_flag": int(row.get("chara_program_change_flag") or 0),
            }
    rows = []
    for row in master_rows(master_data, "single_mode_turn"):
        try:
            turn_set_id = int(row.get("turn_set_id") or 0)
            turn = int(row.get("turn") or 0)
        except Exception:
            continue
        scenario = scenarios.get(turn_set_id) or {"scenario_id": 0, "turn_set_id": turn_set_id}
        period = int(row.get("period") or 0)
        year = int(row.get("year") or 0)
        month = int(row.get("month") or 0)
        half = int(row.get("half") or 0)
        rows.append({
            "scenario_id": int(scenario.get("scenario_id") or 0),
            "turn_set_id": turn_set_id,
            "turn": turn,
            "year": year,
            "month": month,
            "half": half,
            "half_label": _HALF_LABELS.get(half, str(half)),
            "period": period,
            "period_label": _PERIOD_LABELS.get(period, str(period)),
            "is_summer": period == 2 or (year in {2, 3} and month in {7, 8}),
            "is_finale": period == 3 or year >= 4,
            "is_pre_debut": period == 1,
            "training_set_id": int(row.get("training_set_id") or 0),
            "outing_set_id": int(row.get("outing_set_id") or 0),
            "race_entry_type": int(row.get("race_entry_type") or 0),
            "unique_command": int(row.get("unique_command") or 0),
            "rest_type": int(row.get("rest_type") or 0),
            "health_room_type": int(row.get("health_room_type") or 0),
        })
    rows.sort(key=lambda r: (r["scenario_id"], r["turn"]))
    write_json(data_dir / "scenario_turns_core.json", rows)
    return {"file": "scenario_turns_core.json", "rows": len(rows)}

# Authoritative support_card_effect_table type -> effect mapping.
# Source: Umamusume Wiki Module:Game/Supports/Data/Effects (getPrettyName),
# cross-verified against gametora.com card pages (Kitasan Black 30028,
# Fine Motion 30010, Aoi Kiryuin 10022) — every resolved value matched.
# The previous map was off-by-one from type 8 onward (it labeled the
# real "training effectiveness" as initial_speed, real "race bonus" as
# fan_bonus, etc.), producing impossible deck totals.
_SUPPORT_EFFECT_LABELS = {
    1: "friendship_bonus",
    2: "mood_effect",
    3: "speed_bonus",
    4: "stamina_bonus",
    5: "power_bonus",
    6: "guts_bonus",
    7: "wit_bonus",
    8: "training_effectiveness",
    9: "initial_speed",
    10: "initial_stamina",
    11: "initial_power",
    12: "initial_guts",
    13: "initial_wit",
    14: "initial_friendship_gauge",
    15: "race_bonus",
    16: "fan_bonus",
    17: "hint_levels",
    18: "hint_frequency",
    19: "specialty_priority",
    20: "max_speed",
    21: "max_stamina",
    22: "max_power",
    23: "max_guts",
    24: "max_wit",
    25: "event_recovery",
    26: "event_effectiveness",
    27: "failure_protection",
    28: "energy_cost_reduction",
    29: "minigame_effectiveness",
    30: "skill_point_bonus",
    31: "wit_friendship_recovery",
    32: "initial_skill_points",
}

_SKILL_CATEGORY_LABELS = {
    0: "green",
    1: "acceleration_start",
    2: "velocity",
    3: "recovery",
    4: "position_corner",
    5: "unique_active",
    101: "scenario",
}

_SUPPORT_COMMAND_LABELS = {
    101: "speed",
    102: "stamina",
    103: "power",
    105: "guts",
    106: "wit",
    0: "friend",
}


def _skill_effect_blocks(row):
    blocks = []
    for condition_index in (1, 2):
        condition = str(row.get(f"condition_{condition_index}") or "")
        precondition = str(row.get(f"precondition_{condition_index}") or "")
        for ability_index in (1, 2, 3):
            ability_type = int(row.get(f"ability_type_{condition_index}_{ability_index}") or 0)
            if not ability_type:
                continue
            blocks.append({
                "condition_slot": condition_index,
                "ability_slot": ability_index,
                "precondition": precondition,
                "condition": condition,
                "ability_type": ability_type,
                "ability_value_usage": int(row.get(f"ability_value_usage_{condition_index}_{ability_index}") or 0),
                "ability_value_level_usage": int(row.get(f"ability_value_level_usage_{condition_index}_{ability_index}") or 0),
                "float_ability_value": int(row.get(f"float_ability_value_{condition_index}_{ability_index}") or 0),
                "target_type": int(row.get(f"target_type_{condition_index}_{ability_index}") or 0),
                "target_value": int(row.get(f"target_value_{condition_index}_{ability_index}") or 0),
            })
    return blocks


def _flatten_skill_set(row):
    skills = []
    for index in range(1, 11):
        skill_id = int(row.get(f"skill_id{index}") or 0)
        if not skill_id:
            continue
        skills.append({
            "slot": index,
            "skill_id": skill_id,
            "skill_level": int(row.get(f"skill_level{index}") or 0),
        })
    return skills


def synthesize_skill_condition_core(base_dir, master_data):
    """Export skill activation conditions and ability blocks from skill_data."""
    data_dir = Path(base_dir) / "data"
    skill_names = text_map(master_rows(master_data, "cat_47_text"))
    costs = {
        int(row["id"]): int(row.get("need_skill_point") or 0)
        for row in master_rows(master_data, "single_mode_skill_need_point")
        if row.get("id") is not None
    }
    level_values_by_ability = {}
    for row in master_rows(master_data, "skill_level_value"):
        ability_type = int(row.get("ability_type") or 0)
        level_values_by_ability.setdefault(str(ability_type), []).append({
            "level": int(row.get("level") or 0),
            "float_ability_value_coef": int(row.get("float_ability_value_coef") or 0),
        })
    for values in level_values_by_ability.values():
        values.sort(key=lambda item: item["level"])

    rows = []
    for row in master_rows(master_data, "skill_data"):
        skill_id = int(row.get("id") or 0)
        if not skill_id:
            continue
        tags = [int(t) for t in str(row.get("tag_id") or "").split("/") if str(t).lstrip("-").isdigit()]
        preconditions = [str(row.get("precondition_1") or ""), str(row.get("precondition_2") or "")]
        conditions = [str(row.get("condition_1") or ""), str(row.get("condition_2") or "")]
        effect_blocks = _skill_effect_blocks(row)
        ability_types = sorted({int(block["ability_type"]) for block in effect_blocks if block.get("ability_type")})
        rows.append({
            "skill_id": skill_id,
            "name": skill_names.get(skill_id, str(skill_id)),
            "rarity": int(row.get("rarity") or 0),
            "group_id": int(row.get("group_id") or 0),
            "group_rate": int(row.get("group_rate") or 0),
            "grade_value": int(row.get("grade_value") or 0),
            "cost": costs.get(skill_id, 0),
            "skill_category": int(row.get("skill_category") or 0),
            "skill_category_label": _SKILL_CATEGORY_LABELS.get(int(row.get("skill_category") or 0), "other"),
            "tags": tags,
            "icon_id": int(row.get("icon_id") or 0),
            "activate_lot": int(row.get("activate_lot") or 0),
            "preconditions": [value for value in preconditions if value],
            "conditions": [value for value in conditions if value],
            "ability_types": ability_types,
            "effect_blocks": effect_blocks,
            "level_values": {
                str(ability_type): level_values_by_ability.get(str(ability_type), [])
                for ability_type in ability_types
            },
            "disable_singlemode": int(row.get("disable_singlemode") or 0),
            "is_general_skill": int(row.get("is_general_skill") or 0),
        })
    rows.sort(key=lambda row: (row["group_id"], row["rarity"], row["skill_id"]))
    return write_core_pair(data_dir, "skill_condition_core", rows)


def synthesize_skill_upgrade_groups_core(base_dir, master_data):
    """Export skill groups/upgrade chains so buyers and UI can reason about variants."""
    data_dir = Path(base_dir) / "data"
    skill_names = text_map(master_rows(master_data, "cat_47_text"))
    costs = {
        int(row["id"]): int(row.get("need_skill_point") or 0)
        for row in master_rows(master_data, "single_mode_skill_need_point")
        if row.get("id") is not None
    }
    grouped = {}
    for row in master_rows(master_data, "skill_data"):
        skill_id = int(row.get("id") or 0)
        if not skill_id:
            continue
        group_id = int(row.get("group_id") or 0) or (skill_id if skill_id < 100000 else skill_id // 10)
        item = {
            "skill_id": skill_id,
            "name": skill_names.get(skill_id, str(skill_id)),
            "rarity": int(row.get("rarity") or 0),
            "grade_value": int(row.get("grade_value") or 0),
            "cost": costs.get(skill_id, 0),
            "skill_category": int(row.get("skill_category") or 0),
            "skill_category_label": _SKILL_CATEGORY_LABELS.get(int(row.get("skill_category") or 0), "other"),
            "icon_id": int(row.get("icon_id") or 0),
        }
        grouped.setdefault(str(group_id), {"group_id": group_id, "skills": []})["skills"].append(item)
    rows = []
    for payload in grouped.values():
        payload["skills"].sort(key=lambda item: (
            int(item.get("rarity") or 99),
            1 if int(item.get("grade_value") or 0) <= 0 else 0,
            int(item.get("grade_value") or 999999),
            int(item.get("skill_id") or 0),
        ))
        payload["base_skill_id"] = payload["skills"][0]["skill_id"] if payload["skills"] else 0
        payload["max_rarity"] = max([int(item.get("rarity") or 0) for item in payload["skills"]] or [0])
        payload["has_gold"] = any(int(item.get("rarity") or 0) == 2 for item in payload["skills"])
        payload["has_unique"] = any(int(item.get("rarity") or 0) >= 3 for item in payload["skills"])
        rows.append(payload)
    rows.sort(key=lambda row: row["group_id"])
    return write_core_pair(data_dir, "skill_upgrade_groups_core", rows)


def synthesize_skill_sources_core(base_dir, master_data):
    """Export where skills come from: trainee available sets, support sets, and generic skill sets."""
    data_dir = Path(base_dir) / "data"
    skill_names = text_map(master_rows(master_data, "cat_47_text"))
    card_names = text_map(master_rows(master_data, "cat_4_text"))
    support_names = text_map(master_rows(master_data, "cat_75_text"))
    available_sets = []
    by_available_set = {}
    skill_to_sources = {}

    def add_source(skill_id, source):
        skill_to_sources.setdefault(str(skill_id), []).append(source)

    for row in master_rows(master_data, "available_skill_set"):
        skill_id = int(row.get("skill_id") or 0)
        set_id = int(row.get("available_skill_set_id") or 0)
        if not skill_id or not set_id:
            continue
        item = {
            "available_skill_set_id": set_id,
            "skill_id": skill_id,
            "skill_name": skill_names.get(skill_id, str(skill_id)),
            "need_rank": int(row.get("need_rank") or 0),
        }
        available_sets.append(item)
        by_available_set.setdefault(str(set_id), []).append(item)
        add_source(skill_id, {"source_type": "available_skill_set", "source_id": set_id, "need_rank": item["need_rank"]})

    skill_sets = []
    skill_sets_by_id = {}
    for row in master_rows(master_data, "skill_set"):
        set_id = int(row.get("id") or 0)
        skills = _flatten_skill_set(row)
        for skill in skills:
            skill["skill_name"] = skill_names.get(int(skill.get("skill_id") or 0), str(skill.get("skill_id") or ""))
            add_source(int(skill["skill_id"]), {"source_type": "skill_set", "source_id": set_id, "skill_level": int(skill.get("skill_level") or 0)})
        payload = {"skill_set_id": set_id, "skills": skills}
        skill_sets.append(payload)
        skill_sets_by_id[str(set_id)] = payload

    trainee_sources = []
    for row in master_rows(master_data, "card_data"):
        card_id = int(row.get("id") or 0)
        set_id = int(row.get("available_skill_set_id") or 0)
        if not card_id or not set_id:
            continue
        skills = by_available_set.get(str(set_id), [])
        source = {
            "card_id": card_id,
            "chara_id": int(row.get("chara_id") or 0),
            "name": display_name(card_names.get(card_id, str(card_id))),
            "available_skill_set_id": set_id,
            "skills": skills,
        }
        trainee_sources.append(source)
        for skill in skills:
            add_source(int(skill["skill_id"]), {"source_type": "trainee", "source_id": card_id, "source_name": source["name"], "need_rank": int(skill.get("need_rank") or 0)})

    support_sources = []
    for row in master_rows(master_data, "support_card_data"):
        support_id = int(row.get("id") or 0)
        set_id = int(row.get("skill_set_id") or 0)
        if not support_id or not set_id:
            continue
        skills = list((skill_sets_by_id.get(str(set_id)) or {}).get("skills") or [])
        source = {
            "support_card_id": support_id,
            "name": display_name(support_names.get(support_id, str(support_id))),
            "rarity": int(row.get("rarity") or 0),
            "command_id": int(row.get("command_id") or 0),
            "command_label": _SUPPORT_COMMAND_LABELS.get(int(row.get("command_id") or 0), str(row.get("command_id") or "")),
            "skill_set_id": set_id,
            "skills": skills,
        }
        support_sources.append(source)
        for skill in skills:
            add_source(int(skill["skill_id"]), {"source_type": "support", "source_id": support_id, "source_name": source["name"], "skill_level": int(skill.get("skill_level") or 0)})

    payload = {
        "available_skill_sets": sorted(available_sets, key=lambda row: (row["available_skill_set_id"], row["skill_id"])),
        "skill_sets": sorted(skill_sets, key=lambda row: row["skill_set_id"]),
        "trainee_sources": sorted(trainee_sources, key=lambda row: (row["name"], row["card_id"])),
        "support_sources": sorted(support_sources, key=lambda row: (row["rarity"], row["name"], row["support_card_id"])),
        "skill_to_sources": {key: value for key, value in sorted(skill_to_sources.items(), key=lambda kv: int(kv[0]))},
    }
    write_json(data_dir / "skill_sources_core.json", payload)
    return {
        "file": "skill_sources_core.json",
        "available_skills": len(payload["available_skill_sets"]),
        "skill_sets": len(payload["skill_sets"]),
        "trainee_sources": len(payload["trainee_sources"]),
        "support_sources": len(payload["support_sources"]),
    }


def synthesize_support_hint_sources_core(base_dir, master_data):
    """Export support-card hint sources from single_mode_hint_gain."""
    data_dir = Path(base_dir) / "data"
    skill_names = text_map(master_rows(master_data, "cat_47_text"))
    support_names = text_map(master_rows(master_data, "cat_75_text"))
    support_by_id = {int(row.get("id") or 0): row for row in master_rows(master_data, "support_card_data")}
    rows = []
    by_support = {}
    by_skill = {}
    for row in master_rows(master_data, "single_mode_hint_gain"):
        support_id = int(row.get("support_card_id") or 0)
        skill_id = int(row.get("hint_value_1") or 0)
        if not support_id or not skill_id:
            continue
        support = support_by_id.get(support_id, {})
        item = {
            "id": int(row.get("id") or 0),
            "hint_id": int(row.get("hint_id") or 0),
            "support_card_id": support_id,
            "support_name": display_name(support_names.get(support_id, str(support_id))),
            "support_rarity": int(support.get("rarity") or 0),
            "support_command_id": int(support.get("command_id") or 0),
            "support_command_label": _SUPPORT_COMMAND_LABELS.get(int(support.get("command_id") or 0), str(support.get("command_id") or "")),
            "hint_group": int(row.get("hint_group") or 0),
            "hint_gain_type": int(row.get("hint_gain_type") or 0),
            "skill_id": skill_id,
            "skill_name": skill_names.get(skill_id, str(skill_id)),
            "hint_level": int(row.get("hint_value_2") or 0),
        }
        rows.append(item)
        by_support.setdefault(str(support_id), []).append(item)
        by_skill.setdefault(str(skill_id), []).append({
            "support_card_id": support_id,
            "support_name": item["support_name"],
            "support_rarity": item["support_rarity"],
            "hint_level": item["hint_level"],
            "hint_gain_type": item["hint_gain_type"],
        })
    rows.sort(key=lambda row: (row["support_card_id"], row["hint_group"], row["skill_id"]))
    payload = {
        "hints": rows,
        "by_support_card": {key: value for key, value in sorted(by_support.items(), key=lambda kv: int(kv[0]))},
        "by_skill": {key: value for key, value in sorted(by_skill.items(), key=lambda kv: int(kv[0]))},
    }
    write_json(data_dir / "support_hint_sources_core.json", payload)
    return {"file": "support_hint_sources_core.json", "hints": len(rows), "support_cards": len(by_support), "skills": len(by_skill)}


def _support_effect_values(effect_rows):
    levels = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    values = {str(level): {} for level in levels}
    raw_rows = []
    for row in effect_rows:
        effect_type = int(row.get("type") or 0)
        label = _SUPPORT_EFFECT_LABELS.get(effect_type, f"effect_{effect_type}")
        latest = int(row.get("init") or 0)
        raw = {"type": effect_type, "label": label, "values": {"0": latest}}
        values["0"][label] = latest
        for level in levels[1:]:
            cell = int(row.get(f"limit_lv{level}") or -1)
            if cell >= 0:
                latest = cell
            values[str(level)][label] = latest
            raw["values"][str(level)] = latest
        raw_rows.append(raw)
    return values, raw_rows


def synthesize_support_effects_resolved_core(base_dir, master_data):
    """Export resolved support card effects at major level/limit break points."""
    data_dir = Path(base_dir) / "data"
    support_names = text_map(master_rows(master_data, "cat_75_text"))
    effects_by_table = {}
    for row in master_rows(master_data, "support_card_effect_table"):
        table_id = int(row.get("id") or 0)
        if table_id:
            effects_by_table.setdefault(table_id, []).append(dict(row))
    unique_by_id = {}
    for row in master_rows(master_data, "support_card_unique_effect"):
        unique_id = int(row.get("id") or 0)
        if not unique_id:
            continue
        blocks = []
        for index in (0, 1):
            effect_type = int(row.get(f"type_{index}") or 0)
            if not effect_type:
                continue
            blocks.append({
                "type": effect_type,
                "label": _SUPPORT_EFFECT_LABELS.get(effect_type, f"effect_{effect_type}"),
                "value": int(row.get(f"value_{index}") or 0),
                "value_1": int(row.get(f"value_{index}_1") or 0),
                "value_2": int(row.get(f"value_{index}_2") or 0),
                "value_3": int(row.get(f"value_{index}_3") or 0),
                "value_4": int(row.get(f"value_{index}_4") or 0),
            })
        unique_by_id.setdefault(unique_id, []).append({"level": int(row.get("lv") or 0), "effects": blocks})
    hints_by_support = {}
    for row in master_rows(master_data, "single_mode_hint_gain"):
        support_id = int(row.get("support_card_id") or 0)
        skill_id = int(row.get("hint_value_1") or 0)
        if support_id and skill_id:
            hints_by_support.setdefault(support_id, []).append(skill_id)

    rows = []
    for row in master_rows(master_data, "support_card_data"):
        support_id = int(row.get("id") or 0)
        if not support_id:
            continue
        effect_table_id = int(row.get("effect_table_id") or support_id or 0)
        unique_effect_id = int(row.get("unique_effect_id") or 0)
        resolved_by_level, effect_rows = _support_effect_values(effects_by_table.get(effect_table_id, []))
        rows.append({
            "support_card_id": support_id,
            "name": display_name(support_names.get(support_id, str(support_id))),
            "rarity": int(row.get("rarity") or 0),
            "command_id": int(row.get("command_id") or 0),
            "command_label": _SUPPORT_COMMAND_LABELS.get(int(row.get("command_id") or 0), str(row.get("command_id") or "")),
            "support_card_type": int(row.get("support_card_type") or 0),
            "skill_set_id": int(row.get("skill_set_id") or 0),
            "outing_max": int(row.get("outing_max") or 0),
            "effect_table_id": effect_table_id,
            "unique_effect_id": unique_effect_id,
            "effect_values_by_level": resolved_by_level,
            "effect_rows": effect_rows,
            "unique_effects": unique_by_id.get(unique_effect_id, []),
            "hint_skill_count": len(set(hints_by_support.get(support_id, []))),
        })
    rows.sort(key=lambda row: (row["rarity"], row["command_id"], row["name"], row["support_card_id"]))
    level_exp = []
    for row in master_rows(master_data, "support_card_level"):
        level_exp.append({
            "rarity": int(row.get("rarity") or 0),
            "level": int(row.get("level") or 0),
            "total_exp": int(row.get("total_exp") or 0),
        })
    payload = {"support_cards": rows, "level_exp": sorted(level_exp, key=lambda row: (row["rarity"], row["level"]))}
    write_json(data_dir / "support_effects_resolved_core.json", payload)
    return {"file": "support_effects_resolved_core.json", "support_cards": len(rows), "level_exp": len(level_exp)}


def _succession_initial_factor_label(row):
    factor_type = int(row.get("factor_type") or 0)
    value_1 = int(row.get("value_1") or 0)
    value_2 = int(row.get("value_2") or 0)
    if factor_type == 1:
        return f"{value_1}★ factor"
    if factor_type == 2:
        if value_2 and value_2 < 999:
            return f"relation rank {value_1}-{value_2}"
        return f"relation rank {value_1}+"
    return f"factor_type_{factor_type}"


def synthesize_succession_scoring_core(base_dir, master_data):
    """Export inheritance scoring helpers from master.mdb.

    This file complements succession_core.json with the small official scoring
    tables needed for parent/spark estimation: initial factor points by star/rank
    and relation-rank thresholds.  Runtime inheritance remains payload-driven;
    these rows provide deterministic labels and estimates for previews/logging.
    """
    data_dir = Path(base_dir) / "data"
    initial_factors = []
    for row in master_rows(master_data, "succession_initial_factor"):
        try:
            item = {
                "id": int(row.get("id") or 0),
                "factor_type": int(row.get("factor_type") or 0),
                "value_1": int(row.get("value_1") or 0),
                "value_2": int(row.get("value_2") or 0),
                "add_point": int(row.get("add_point") or 0),
            }
        except Exception:
            continue
        item["label"] = _succession_initial_factor_label(item)
        initial_factors.append(item)

    relation_ranks = []
    for row in master_rows(master_data, "succession_relation_rank"):
        try:
            relation_ranks.append({
                "relation_rank": int(row.get("relation_rank") or 0),
                "rank_value_min": int(row.get("rank_value_min") or 0),
                "rank_value_max": int(row.get("rank_value_max") or 0),
            })
        except Exception:
            continue

    relation_points = []
    for row in master_rows(master_data, "succession_relation"):
        try:
            relation_points.append({
                "relation_type": int(row.get("relation_type") or 0),
                "relation_point": int(row.get("relation_point") or 0),
            })
        except Exception:
            continue

    payload = {
        "initial_factors": sorted(initial_factors, key=lambda r: r["id"]),
        "relation_ranks": sorted(relation_ranks, key=lambda r: r["relation_rank"]),
        "relation_points": sorted(relation_points, key=lambda r: r["relation_type"]),
    }
    write_json(data_dir / "succession_scoring_core.json", payload)
    return {
        "file": "succession_scoring_core.json",
        "initial_factors": len(payload["initial_factors"]),
        "relation_ranks": len(payload["relation_ranks"]),
        "relation_points": len(payload["relation_points"]),
    }


def synthesize_career_progression_core(base_dir, master_data):
    """Export official career grade requirements from single_mode_chara_grade."""
    data_dir = Path(base_dir) / "data"
    rows = []
    for row in master_rows(master_data, "single_mode_chara_grade"):
        try:
            rows.append({
                "grade_id": int(row.get("id") or 0),
                "win_num": int(row.get("win_num") or 0),
                "run_num": int(row.get("run_num") or 0),
                "need_fan_count": int(row.get("need_fan_count") or 0),
            })
        except Exception:
            continue
    rows.sort(key=lambda r: r["grade_id"])
    payload = {"grades": rows}
    write_json(data_dir / "career_progression_core.json", payload)
    return {"file": "career_progression_core.json", "grades": len(rows)}


def _event_item_name(item, name_maps):
    for key in ("name_index", "item_id", "id"):
        try:
            value = int(item.get(key) or 0)
        except Exception:
            continue
        if not value:
            continue
        for mapping in name_maps:
            name = mapping.get(value)
            if name:
                return display_name(name)
    return ""


def synthesize_event_reward_display_core(base_dir, master_data):
    """Export event reward/display helper tables for event traces and UI labels.

    These tables do not replace runtime event payloads; they provide official
    display metadata where master.mdb
    exposes it so scoring/debug traces can use stable labels instead of opaque IDs.
    """
    data_dir = Path(base_dir) / "data"
    event_names = text_map(master_rows(master_data, "cat_181_text"))
    chara_names = text_map(master_rows(master_data, "cat_182_text"))
    item_name_maps = [
        text_map(master_rows(master_data, "cat_180_text")),
        text_map(master_rows(master_data, "cat_177_text")),
        text_map(master_rows(master_data, "cat_178_text")),
        text_map(master_rows(master_data, "cat_179_text")),
        text_map(master_rows(master_data, "cat_23_text")),
        text_map(master_rows(master_data, "cat_225_text")),
    ]

    choice_rewards = []
    for row in master_rows(master_data, "single_mode_event_choice_reward"):
        try:
            types = [int(row.get(f"effect_value_type_{idx}") or 0) for idx in range(3)]
            choice_rewards.append({
                "id": int(row.get("id") or 0),
                "disp_type": int(row.get("disp_type") or 0),
                "effect_value_types": types,
                "effect_value_labels": [_event_reward_type_label(value) for value in types],
            })
        except Exception:
            continue

    item_details = []
    for row in master_rows(master_data, "single_mode_event_item_detail"):
        item = dict(row)
        try:
            item_details.append({
                "id": int(item.get("id") or 0),
                "event_category_id": int(item.get("event_category_id") or 0),
                "item_id": int(item.get("item_id") or 0),
                "name_index": int(item.get("name_index") or 0),
                "name": _event_item_name(item, item_name_maps),
            })
        except Exception:
            continue

    cr_priority = []
    for row in master_rows(master_data, "single_mode_event_cr_priority"):
        try:
            conditions = [int(row.get(f"effect_value_condition_{idx}") or 0) for idx in range(3)]
            cr_priority.append({
                "id": int(row.get("id") or 0),
                "display_id": int(row.get("display_id") or 0),
                "conditions": conditions,
                "condition_labels": [_event_reward_type_label(value) for value in conditions],
                "priority": int(row.get("priority") or 0),
            })
        except Exception:
            continue

    productions = []
    for row in master_rows(master_data, "single_mode_event_production"):
        try:
            story_id = int(row.get("story_id") or 0)
        except Exception:
            continue
        productions.append({
            "story_id": story_id,
            "story_name": display_name(event_names.get(story_id, str(story_id))),
            "event_category_id": int(row.get("event_category_id") or 0),
            "max_item_id": int(row.get("max_item_id") or 0),
            "item_dir": row.get("item_dir") or "",
            "item_name_pattern": row.get("item_name") or "",
        })

    conclusions_by_id = {}
    for row in master_rows(master_data, "single_mode_event_conclusion"):
        try:
            cid = int(row.get("id") or 0)
            chara_id = int(row.get("chara_id") or 0)
        except Exception:
            continue
        bucket = conclusions_by_id.setdefault(str(cid), {"id": cid, "chara": []})
        bucket["chara"].append({
            "chara_id": chara_id,
            "name": display_name(chara_names.get(chara_id, str(chara_id))),
            "chara_motion_set_id": int(row.get("chara_motion_set_id") or 0),
        })

    payload = {
        "choice_rewards": sorted(choice_rewards, key=lambda r: r["id"]),
        "item_details": sorted(item_details, key=lambda r: r["id"]),
        "cr_priority": sorted(cr_priority, key=lambda r: (r["display_id"], r["priority"], r["id"])),
        "productions": sorted(productions, key=lambda r: r["story_id"]),
        "conclusions": sorted(conclusions_by_id.values(), key=lambda r: r["id"]),
    }
    write_json(data_dir / "event_reward_display_core.json", payload)
    return {
        "file": "event_reward_display_core.json",
        "choice_rewards": len(payload["choice_rewards"]),
        "item_details": len(payload["item_details"]),
        "cr_priority": len(payload["cr_priority"]),
        "productions": len(payload["productions"]),
        "conclusions": len(payload["conclusions"]),
    }

def synthesize_extended_core_jsons(base_dir, master_data):
    generated = [
        synthesize_race_planner_core(base_dir, master_data),
        synthesize_skill_weighting_core(base_dir, master_data),
        synthesize_trainee_profiles_core(base_dir, master_data),
        synthesize_support_cards_core(base_dir, master_data),
        synthesize_succession_core(base_dir, master_data),
        synthesize_mant_shop_core(base_dir, master_data),
        synthesize_tp_restore_items_core(base_dir, master_data),
        synthesize_win_saddle_core(base_dir, master_data),
        synthesize_career_rank_thresholds_core(base_dir, master_data),
        synthesize_chara_route_core(base_dir, master_data),
        synthesize_rival_races_core(base_dir, master_data),
        synthesize_single_mode_npc_core(base_dir, master_data),
        synthesize_trackblazer_race_rewards_core(base_dir, master_data),
        synthesize_race_performance_rates_core(base_dir, master_data),
        synthesize_training_effects_core(base_dir, master_data),
        synthesize_scenario_turns_core(base_dir, master_data),
        synthesize_skill_condition_core(base_dir, master_data),
        synthesize_skill_upgrade_groups_core(base_dir, master_data),
        synthesize_skill_sources_core(base_dir, master_data),
        synthesize_support_hint_sources_core(base_dir, master_data),
        synthesize_support_effects_resolved_core(base_dir, master_data),
        synthesize_succession_scoring_core(base_dir, master_data),
        synthesize_career_progression_core(base_dir, master_data),
        synthesize_event_reward_display_core(base_dir, master_data),
    ]
    return {"generated": generated}


def synthesize_legacy_jsons(base_dir, master_data):
    generated = [
        synthesize_skill_data(base_dir, master_data),
        synthesize_chara_list(base_dir, master_data),
        synthesize_support_list(base_dir, master_data),
        synthesize_race_map(base_dir, master_data),
        synthesize_factor_map(base_dir, master_data),
    ]
    extended = synthesize_extended_core_jsons(base_dir, master_data)

    return {"generated": generated, "extended": extended.get("generated", []), "preserved": []}


def load_master_data(cursor, existing_tables):
    master_data = {"tables": {}, "text": {}}
    extracted = []
    skipped = []

    for table in DIRECT_TABLES:
        if table not in existing_tables:
            skipped.append(table)
            continue
        rows = dump_table(cursor, table)
        master_data["tables"][table] = rows
        extracted.append({"table": table, "rows": len(rows)})

    if "text_data" in existing_tables:
        for filename, category in TEXT_DATA_CATEGORIES.items():
            rows = dump_text_data_category(cursor, category)
            master_data["text"][filename] = rows
            extracted.append({"table": filename, "rows": len(rows)})
    else:
        skipped.extend(TEXT_DATA_CATEGORIES)

    return master_data, extracted, skipped


def generate(base_dir, master_mdb_path=None):
    db_path = Path(master_mdb_path).expanduser() if master_mdb_path else configured_master_mdb_path(base_dir)
    exists, access_error = path_access(db_path)
    if not exists:
        detail = f"master.mdb not found at {db_path}"
        if access_error:
            detail = f"master.mdb could not be accessed at {db_path}: {access_error}"
        return {
            **status(base_dir),
            "success": False,
            "detail": detail,
        }

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = {row[0] for row in cursor.fetchall()}
        master_data, extracted, skipped = load_master_data(cursor, existing_tables)
        catalog = synthesize_master_table_catalog_core_from_cursor(base_dir, cursor, existing_tables)
    finally:
        conn.close()

    legacy = synthesize_legacy_jsons(base_dir, master_data)
    legacy.setdefault("extended", []).append(catalog)
    return {
        **status(base_dir),
        "success": True,
        "extracted": extracted,
        "skipped": skipped,
        "legacy": legacy,
    }


def synthesize_master_table_catalog_core_from_cursor(base_dir, cursor, existing_tables):
    """Write a compact catalog of every table/column visible in master.mdb.

    This is intentionally metadata-only.  It lets AI logs and diagnostics label
    what was official table data without bundling a huge raw database dump or
    pretending hidden simulator formulas are exposed.
    """
    data_dir = Path(base_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for table in sorted(existing_tables):
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            count = int(cursor.fetchone()[0] or 0)
        except Exception:
            count = 0
        columns = []
        try:
            cursor.execute(f'PRAGMA table_info("{table}")')
            for col in cursor.fetchall():
                columns.append({
                    "cid": int(col[0]),
                    "name": str(col[1]),
                    "type": str(col[2] or ""),
                    "notnull": int(col[3] or 0),
                    "default": col[4],
                    "pk": int(col[5] or 0),
                })
        except Exception:
            columns = []
        rows.append({"table": table, "rows": count, "columns": columns})
    payload = {
        "version": 1,
        "generated_at": int(time.time()),
        "source": "official_table_data:master.mdb_catalog",
        "table_count": len(rows),
        "tables": rows,
        "limitations": [
            "This catalog lists official database tables and columns only.",
            "It does not expose exact hidden lane-blocking, acceleration, opponent-AI, or server-side race formulas unless those formulas are represented by visible tables.",
        ],
    }
    write_json(data_dir / "master_table_catalog_core.json", payload)
    return {"file": "master_table_catalog_core.json", "tables": len(rows)}
