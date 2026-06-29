# Master Data Alignment for TP Restore and Career History

## Purpose

Pre Icarus v5.11 tightens the Pre Icarus v5.10 TP Restore and Career History changes against the authoritative `master.mdb` schema. The goal is to avoid guessing item IDs, race fan rewards, major-win labels, and career-rank thresholds when those values are available in master data.

## Toughness 30 item detection

`master.mdb` stores generic item names in `text_data` category `23`, where `text_data.index` equals `item_data.id`. Pre Icarus now resolves Toughness 30 through the exact item row:

```sql
SELECT i.id
FROM item_data i
LEFT JOIN text_data n
  ON n.category = 23 AND n."index" = i.id
LEFT JOIN text_data d
  ON d.category = 10 AND d."index" = i.id
WHERE i.item_category = 20
  AND i.effect_type_1 = 2
  AND i.effect_value_1 = 30
  AND n.text = 'Toughness 30'
ORDER BY i.id;
```

The generated `data/tp_restore_items_core.json` records all TP restore items, but only the exact `Toughness 30` row is tagged as `kind: toughness_30` for automatic Toughness 30 restore selection.

## Race fan rewards

Race fan rewards come from:

```text
single_mode_program.fan_set_id
  -> single_mode_fan_count.fan_set_id
  -> single_mode_fan_count.order = 1
  -> single_mode_fan_count.fan_count
```

`race_planner_core.json` and `race_map.json` now include first-place fan reward metadata so Career History race ledgers can show accurate race fan rewards.

## Major wins

Major wins are resolved through `single_mode_wins_saddle` and `text_data` category `111`. Generated metadata is written to:

```text
data/win_saddle_core.json
```

Career History uses this file to display labels such as `Dual Miles` when the final payload includes `win_saddle_id_array`.

## Career rank thresholds

Career rank thresholds are generated from `single_mode_rank` into:

```text
data/career_rank_thresholds_core.json
```

Career History now uses those thresholds before falling back to the older hardcoded display ladder.

## Validation

The regression tests in `tests/test_sweepymodv511_master_data_alignment.py` build a minimal `master.mdb` fixture and verify:

- Toughness 30 resolves to item ID `32`.
- Race fan rewards are joined from `single_mode_fan_count`.
- RacePlanner receives fan reward metadata from `race_planner_core.json`.
- `single_mode_wins_saddle` resolves to major-win names.
- Career rank thresholds are exported from `single_mode_rank`.
