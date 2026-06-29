# Master Data Extended Integration

## Purpose

The master-data integration exports official `master.mdb` data into Pre Icarus's `data/` folder so runtime systems can use structured race, skill, trainee, shop, support-card, and succession data instead of relying only on older legacy maps.

## How it works

`career_bot/master_data.py` reads supported tables from `master.mdb` and writes additive JSON exports. If a table is missing, generation skips that table rather than failing the whole export.

Generated files include:

```text
data/race_planner_core.json
data/skill_weighting_core.json
data/trainee_profiles_core.json
data/trainee_skill_profiles.generated.json
data/support_cards_core.json
data/succession_core.json
data/mant_shop_core.json
data/source_table_references.json
```

Legacy exports remain available:

```text
data/skill_data.json
data/chara_list.json
data/support_list.json
data/race_map.json
data/factor_map.json
public/assets/data/uma_race_data.json
```

## Runtime usage

- `career_bot/races.py` loads `race_planner_core.json` and enriches race planner metadata with official grade, distance, terrain, venue, and turn data.
- `career_bot/skills.py` loads `skill_weighting_core.json` and uses official scoring signals for skill recommendations.
- `main.py` exposes official weighting details through `/api/skills/weighted-preview`.
- `career_bot/items.py` loads `mant_shop_core.json` to merge official shop costs/effects into the MANT shop optimizer.
- `career_bot.dynamic_skill_profiles.load_profiles()` consumes `trainee_skill_profiles.generated.json`.
- `succession_core.json` prepares official factor and rental metadata for guest-parent and inheritance workflows.

## Dependencies and interactions

This feature depends on a valid `master.mdb`. The generated files are additive and do not remove older export names, so older preset, race, and skill behavior remains compatible.

## Verification

Generate master data, then confirm the files listed above exist in `data/`. Open Diagnostics or the race/skill planner and verify official metadata appears in planner previews and trace reasons.
