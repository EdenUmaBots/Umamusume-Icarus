# Trackblazer Native Training and Race Decisions

## Purpose

Trackblazer Native Decisions refine training scoring and race selection using native Pre Icarus game state instead of Android OCR or screen-coordinate logic.

## Training scoring

The training scorer supports:

- near-rainbow support-card anticipation from native bond/evaluation data
- true rainbow/friendship precedence over near-rainbow opportunities
- summer stat priority through `summer_stat_priority`
- training facility level weighting for top-priority stats when native payloads expose levels
- rainbow allowance for over-cap stats so capped rainbow turns are not automatically zeroed
- decision trace fields for near-rainbow count and training level

## Race sorting

Trackblazer race candidates are sorted by:

1. rival race
2. preferred distance
3. preferred surface
4. grade
5. fans
6. aptitude
7. fallback score

Supported settings include:

```json
{
  "preferred_distances": ["mile", "medium"],
  "preferred_surfaces": ["turf"]
}
```

or their `mant_config` equivalents.

## Smart solver protection

If `trackblazer_last_plan.decisions[turn].type` is `train`, or if a train-style manual lock/training block applies, fallback race selection is blocked for that turn.

## Dependencies and interactions

Implemented in `career_bot/scenarios/mant.py`, `career_bot/races.py`, `public/app.js`, and `career_bot/presets.py`. Interacts with Smart Race Solver, race planner metadata, preset preferences, and Trackblazer settings windows.

## Verification

Run `tests/test_trackblazer_p2_native.py`. In the UI, set preferred distances/surfaces and verify race traces prefer matching candidates. Apply a smart plan with Train turns and confirm fallback racing does not override them.
