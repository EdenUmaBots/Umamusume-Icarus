# Settings Preset Split

## Purpose

Pre Icarus v5.9 replaces the old all-in-one preset blob with three separate configuration stores. This prevents Training/Racing/Scenario settings from overwriting Configure Skills or Smart Race Solver settings.

## Storage Files

The new canonical files are:

```text
data/settings_presets.json
data/skill_config.json
data/smart_solver_config.json
```

`data/presets` is no longer part of the packaged build. When an older install still has `data/presets`, `ConfigStore.migrate_legacy_presets()` reads each legacy preset, splits the data into the new files, and deletes the old folder.

## Settings Presets

Settings Presets contain only:

- Training Settings
- Racing Settings
- Scenario Overrides

They intentionally exclude:

- Configure Skills
- Skill Point Threshold
- Planned skill list
- Skill blacklist
- Smart Race Solver settings
- Manual race selections
- Target/Forced epithets
- Solver aptitude overrides

## Runtime Composition

The runner still receives one runtime config. `ConfigStore.compose_runtime_preset()` merges:

1. the active Settings Preset,
2. `skill_config.json`,
3. `smart_solver_config.json`.

This preserves compatibility with the runner and strategy code while keeping the UI/storage model untangled.

## Compatibility Endpoints

The legacy `/api/presets` endpoints are retained as shims. They read and write through the new split store and do not recreate `data/presets`.

## Verification

Run:

```bash
python -m unittest tests.test_sweepymodv59_config_split -v
```

Check that `data/presets` is absent and the three new JSON files exist.
