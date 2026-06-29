# Master Data Skill and Support Intelligence (Pre Icarus v5.14)

## Purpose

Pre Icarus v5.14 adds the P2 master-data pass for skill and support intelligence. The goal is to give Configure Skills, weighted skill buying, and future support/deck tools richer official metadata from `master.mdb` without replacing the existing runtime payload logic.

## New generated files

### `data/skill_condition_core.json`

Generated from `skill_data`, `single_mode_skill_need_point`, and `skill_level_value`.

Includes:

- skill ID and name
- rarity, group ID, grade value, cost, category, tags, and icon ID
- preconditions and activation conditions
- ability blocks from `ability_type_*`, `float_ability_value_*`, and target columns
- level-value coefficients for each ability type

### `data/skill_upgrade_groups_core.json`

Generated from `skill_data`.

Groups skill variants by official `group_id`, with sorted white/gold/unique variants and category metadata.

### `data/skill_sources_core.json`

Generated from `available_skill_set`, `skill_set`, `card_data`, and `support_card_data`.

Includes:

- trainee available skill sets
- support-card skill sets
- flattened skill-set rows
- inverted `skill_id -> sources` lookup

### `data/support_hint_sources_core.json`

Generated from `single_mode_hint_gain` and `support_card_data`.

Includes:

- support-card hint rows
- support-card-to-skill lookup
- skill-to-support lookup
- hint level/type metadata

### `data/support_effects_resolved_core.json`

Generated from `support_card_data`, `support_card_effect_table`, `support_card_unique_effect`, `support_card_level`, and `single_mode_hint_gain`.

Includes:

- support-card type, rarity, command, and skill-set metadata
- resolved support effect values at major level breakpoints
- unique effect blocks
- support-card level experience rows
- hint skill counts

## Runtime integration

`career_bot.skills.SkillBuyer` now loads the P2 files when present. Weighted skill scoring receives extra official-source context:

- official skill activation conditions
- support-source counts
- trainee-source counts
- skill category labels

These signals add small scoring bonuses and trace reasons such as:

```text
support_sources:3
trainee_sources:1
official_conditions
```

The existing weighted skill policy remains the primary controller. P2 metadata improves explanation and ranking without hard-forcing skill purchases.

## Validation

Added `tests/test_sweepymodv514_master_p2.py`, covering:

- skill condition export
- skill upgrade group export
- skill source export
- support hint source export
- resolved support effect export
- SkillBuyer use of support/trainee source metadata in scoring reasons
