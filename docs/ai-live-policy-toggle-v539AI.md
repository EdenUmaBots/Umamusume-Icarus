# Pre Icarus v5.39AI Live Policy Assistance Toggle

Pre Icarus v5.39AI adds a dedicated Live Policy Assistance control to the AI Learning dashboard.

## What it does

- Lets users enable or disable live learned-policy score adjustments from the AI Learning modal.
- Shows whether the current model recommends enabling Live Policy Assistance or keeping it disabled.
- Uses data health, race-result coverage, turn-record count, and learned adjustment count to make the recommendation.
- Does not bypass Pre Icarus safety rules. Live policy only adjusts scores among legal Smart Race Solver candidates.

## Recommendation rules

The dashboard recommends keeping Live Policy disabled when:

- AI health checks are unsafe.
- Race-result coverage is below the safe threshold.
- There are not enough turn/race records yet.
- No learned race/item/event adjustments have enough confidence.

It recommends enabling Live Policy only when the local training model has enough reliable evidence.

## API/config

The toggle writes to `enable_live_policy_assistance` in `auto_training_config.json` through `/api/ai/auto-training/config`.
