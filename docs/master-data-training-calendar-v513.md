# Master Data Training and Calendar Integration v5.13

## Purpose

Pre Icarus v5.13 adds the P1 master-data pass for Trackblazer decision quality. It exports official training baselines and scenario turn-calendar metadata from `master.mdb` so Pre Icarus can make safer fallback decisions and produce clearer traces.

## Generated Files

### `data/training_effects_core.json`

Generated from:

- `single_mode_training`
- `single_mode_training_effect`
- `single_mode_free_training_plate`

Each training row is grouped by scenario, command, level, and result state. Rows include:

- command id
- training level
- result state
- target effects
- stat total
- skill point gain
- energy delta
- failure-rate basis points from the official training table

Pre Icarus uses this as a fallback and trace source. Live API command payloads remain the preferred per-turn source when available.

### `data/scenario_turns_core.json`

Generated from:

- `single_mode_scenario`
- `single_mode_turn`

Rows include:

- scenario id
- turn set id
- turn number
- year/month/half
- period label
- summer/finale/pre-debut flags
- training/race command metadata

## Runtime Use

`career_bot.scenarios.mant.MantStrategy` loads `training_effects_core.json` and uses it when a training command has no live `params_inc_dec_info_array`. This prevents sparse payloads from scoring every training as if it had no stat/SP/energy value.

`career_bot.trackblazer` loads `scenario_turns_core.json` and uses the official Trackblazer summer turns for Smart Race Solver summer filtering. If the export is missing, the previous hardcoded summer-turn fallback is used.

## Verification

Run:

```bash
python -m unittest tests/test_sweepymodv513_master_p1.py -v
```

Then run the full validation suite:

```bash
python -m compileall -q career_bot main.py manager.py
node --check public/app.js
python -m unittest discover -s tests -q
```
