# Master Data Succession, Career Progression, and Event Display v5.15

## Purpose

Pre Icarus v5.15 adds the P3 master-data pass for parent/spark scoring helpers, Career History polish, and official event reward/display labels.

## Generated files

### `data/succession_scoring_core.json`

Generated from:

- `succession_initial_factor`
- `succession_relation_rank`
- `succession_relation`

This file contains official initial inheritance point helpers and relation-rank thresholds. Career History spark chips use this data to show official initial-point hints when the factor star level is known.

### `data/career_progression_core.json`

Generated from:

- `single_mode_chara_grade`

This file stores official career grade requirements by race count, win count, and fan count. Career History uses it to derive the highest satisfied Career Grade from completed run data.

### `data/event_reward_display_core.json`

Generated from:

- `single_mode_event_choice_reward`
- `single_mode_event_item_detail`
- `single_mode_event_cr_priority`
- `single_mode_event_production`
- `single_mode_event_conclusion`
- `text_data` categories 177, 178, 179, 180, 181, and 182

This file provides display labels for event reward/debug traces. It does not replace runtime event payloads; it adds official labels when display IDs are present.

## Runtime integration

- `main.py` loads `succession_scoring_core.json` and adds `initial_points` to spark rows in Career History.
- `main.py` loads `career_progression_core.json` and emits `career_grade`, `career_grade_id`, and `career_grade_requirements` in Career History rows.
- `career_bot/events.py` loads `event_reward_display_core.json` and adds official labels to event-choice trace reasons.
- `career_bot/runner.py` no longer prints the simulated API 214 race-entry error during tests; recovery remains logged structurally.

## Notes

The Career Grade label intentionally uses `Career Grade <id>` because `single_mode_chara_grade` exposes numeric requirements but not a localized display name in the exported table. This avoids inventing labels that are not present in master data.
