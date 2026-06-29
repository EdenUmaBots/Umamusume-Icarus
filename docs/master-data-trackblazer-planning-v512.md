# Master Data Trackblazer Planning v5.12

## Purpose

Pre Icarus v5.12 adds the first official-data planning pass for Trackblazer. It uses `master.mdb` to enrich Smart Race Solver and race-selection logic with static route, rival, race reward, and performance-rate metadata.

## New generated files

- `data/chara_route_core.json` - per-trainee route/race requirement hints from `single_mode_route`, `single_mode_route_race`, and `single_mode_route_condition`.
- `data/rival_races_core.json` - static rival race hints from `single_mode_rival`.
- `data/trackblazer_race_rewards_core.json` - Trackblazer coin, win-point, fan, race-group, and reward-set metadata from the official race reward tables.
- `data/race_performance_rates_core.json` - official distance, surface, running-style, motivation, course-status, and popularity proper-rate tables.

## Runtime integration

`RacePlanner` now loads the new static rival and Trackblazer reward files. Runtime rival data still takes priority, but static master-data rivals are used when the live payload does not expose the race yet. Race sorting now includes official Trackblazer reward value as a tie-breaker after grade/fans.

The Smart Race Solver candidate builder now enriches scheduled races with:

- first-place fan reward from official race metadata,
- first-place Trackblazer coin reward,
- first-place Trackblazer win points,
- race group IDs,
- reward set IDs,
- official performance-rate hints based on aptitude grades.

These values are soft scoring signals. They improve route ranking without turning static data into unsafe hard locks.

## Notes

The route file is a hint layer. It does not force route races by itself because runtime career state and current Smart Race Solver settings still determine actual race availability and user intent.
