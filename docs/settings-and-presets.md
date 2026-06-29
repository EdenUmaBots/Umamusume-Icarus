# Settings, presets, and the userdata folder

This guide covers how settings and presets work, where they live on
disk, and how to make customizations survive version upgrades.

## The three-tier storage model

Pre Icarus stores configuration across three levels:

1. **In-build defaults** — `data/` inside the `Pre Icarus vX.Y.Z`
   folder. Shipped with each release.
2. **Userdata folder** — `SweepyClaude_userdata/` sibling to the
   build folder. Holds YOUR customizations. Persists across upgrades.
3. **In-memory runtime state** — composed at career start from the
   above two sources.

### Where each file lives

| File | Build default | User customization |
|---|---|---|
| `settings_presets.json` (presets list) | `data/settings_presets.json` | `<userdata>/data/settings_presets.json` |
| `smart_solver_config.json` (solver weights) | `data/smart_solver_config.json` | `<userdata>/data/smart_solver_config.json` |
| `skill_config.json` (skill strategy) | `data/skill_config.json` | `<userdata>/data/skill_config.json` |
| `settings.json` (top-level toggles) | `settings.json` | `<userdata>/settings.json` |
| `accounts.json` (account list) | `accounts.json` | `<userdata>/accounts.json` |
| Steam token | `uma_runtime/<profile>/steam_token.txt` | `<userdata>/auth/<profile>/steam_token.txt` |
| Active selection (picker) | (in-memory only) | `<userdata>/active_selection.json` |

## Recommended folder layout

```
C:\Umamusume API Bot Claude\
    Pre Icarus v6.7.11\          ← the build, replaceable
        main.py, career_bot/, public/, data/, ...
    SweepyClaude_userdata\        ← create once, persists across upgrades
        accounts.json
        settings.json
        active_selection.json
        data\
            settings_presets.json
            smart_solver_config.json
            skill_config.json
            presets\
        auth\
            default\steam_token.txt
```

On the next upgrade, replace just the build folder. Everything in
`SweepyClaude_userdata` is preserved.

## How userdata is discovered

The bot resolves the userdata location in this order:

1. **`SWEEPYCLAUDE_USERDATA_DIR` environment variable** — if set,
   used directly
2. **`<build_dir>/../SweepyClaude_userdata/`** — sibling folder
   convention (recommended)
3. **Fallback to `<build_dir>/`** — legacy behavior, in-build paths
   (no migration triggered)

On first run with userdata configured, in-build defaults are copied
forward (one-way migration). Subsequent upgrades preserve your
customizations.

## Settings presets (Settings tab)

Each preset is a named bundle of:

- `training_stat_priority` — preferred stat order for training picks
- `event_choice_stat_priority` — for in-career events
- `summer_stat_priority` — for summer-camp turns
- `running_style` — preferred race tactic
- `mant_config` — Trackblazer-specific overrides (see below)
- `race_strategy_by_distance` — per-distance tactic overrides
- `preferred_distances` / `preferred_surfaces` — used by the solver

Switch the active preset from the dashboard's left sidebar.

### mant_config — Trackblazer per-preset overrides

These are read by the strategy engine at runtime. Anything you don't
set falls back to the solver-config UI knob or hardcoded default.

| Key | Purpose | Typical value |
|---|---|---|
| `ignore_consecutive_race_warning` | Disable runtime chain-break safety | true for Android-style |
| `ignore_low_energy_racing_block` | Race even at HP=0 | true for Android-style |
| `irregular_training_min_main_gain` | Hijack threshold | 50 (default 30) |
| `charm_min_main_gain` | Charm-window hijack threshold | 50 |
| `race_chain_target` | Soft consecutive-race target | 5 |
| `enable_irregular_training` | Master hijack toggle | true |
| `stat_targets_by_distance` | Per-distance stat caps | `{mile: [1200, 700, 1100, 400, 1000]}` |

## Smart Race Solver Settings (separate panel)

The solver-side knobs live in `smart_solver_config.json` under
`trackblazer_solver_settings` and `trackblazer_weights`. They drive
the race-planning beam search.

**v6.7.11 fix**: previously these UI knobs silently did nothing
because the runner only read from `preset.mant_config`. They now
flow through with the correct precedence:

1. `preset.mant_config.X` (per-preset explicit override)
2. `preset.trackblazer_solver_settings.X` (Smart Race Solver Settings UI)
3. Hardcoded default

The full weight list is in **trackblazer-guide.md**.

## Character profiles

Profiles live under `data/character_profiles/<id>.json` and carry
per-trainee tuning that takes effect when the bot's `chara_info`
card_id matches. The profile resolver falls back to "default" when
no match is found, with auto-derivation from live aptitudes when
chara_info is available.

Profile fields (see **trackblazer-guide.md** for full details):

- `solver_overrides` — per-character solver weight nudges
- `target_epithets` / `forced_epithets` — race-result goals
- `auto_pick_epithets` — opt-in signature-epithet biasing

> **Known limitation**: as of v6.7.11, character profile
> customizations are still in the build folder, NOT in userdata.
> Changes made via the UI persist to the build's JSON files and get
> overwritten by an upgrade. If you've customized a profile, copy
> the relevant JSON to a safe location before upgrading. Userdata
> migration for profiles is a planned future enhancement.

## TP recovery (top-level toggle)

The TP recovery system handles the in-game energy-point cost of
running careers. It's controlled by `settings.json::tp_recovery`:

- `mode: "jewels"` — only spend jewels (gem currency, cheaper)
- `mode: "items"` — spend TP Restore items
- `mode: "both"` — try jewels first, items second
- `mode: "none"` — never auto-recover; bot pauses when TP runs out

## Burn clocks (race retry)

- `burn_clocks: true` — bot uses both free continues AND paid clocks
  to retry races where it didn't finish 1st
- `burn_clocks: false` — bot uses **free continues only** (v6.7.10
  fix). Paid clocks are never spent.

Free continues are always usable; paid require the toggle.

## Logout / multi-account

`POST /api/logout` clears the in-memory client/account state AND
the persisted `active_selection.json`. The next user's picker starts
fresh.

## Resetting to factory defaults

To reset everything:

1. Stop the bot
2. Delete the `SweepyClaude_userdata` folder
3. Restart

On next start, the bot re-migrates in-build defaults into a fresh
userdata folder.
