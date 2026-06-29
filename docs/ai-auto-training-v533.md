# Pre Icarus v5.33 AI Auto-Training and Learned Scoring

This build expands the v5.32 AI dataset foundation into a local, automatic training loop.

## Safety Boundary

The AI layer does not execute game actions. Pre Icarus still builds the legal action list and enforces deterministic safety gates. Learned policy assistance is confidence-gated and only adjusts scores for already-legal candidate actions.

## Phase 2: Local Analytics

Generated under `uma_runtime/<profile>/ai/`:

- `race_outcome_table.json`
- `item_effectiveness_table.json`
- `event_outcome_table.json`
- `post_run_reports/latest_post_run_report.json`
- `post_run_reports/latest_post_run_report.md`

## Phase 3: Learned Scoring

Generated model artifacts:

- `race_risk_model.json`
- `item_value_model.json`
- `event_value_model.json`
- `policy_adjustments.json`

The Trackblazer Smart Race Solver reads `policy_adjustments.json` and applies reversible race score adjustments when confidence meets the configured threshold.

## Phase 4: LLM Advisor Preparation

No external LLM is called in this build. Instead, Pre Icarus prepares prompts and tuning suggestions for later review:

- `llm_advisor/latest_prompt_pack.jsonl`
- `llm_advisor/latest_prompt_pack_manifest.json`
- `suggested_config_tuning.json`

## Phase 5: Live Policy Assistance

Live assistance is optional and reversible. It can penalize races that local history shows as high-risk. It does not make illegal races legal and does not bypass existing solver constraints.

## Automatic Training

Auto-training defaults to enabled and runs:

- after completed career exports, based on `train_after_completed_careers`
- periodically while the bot is idle, based on `interval_minutes`

Configuration lives in:

- `uma_runtime/<profile>/ai/auto_training_config.json`

Diagnostics exposes:

- auto-training status
- Train Now
- latest post-run report
- turn-decision download

## API Endpoints

- `GET /api/ai/auto-training/status`
- `GET /api/ai/auto-training/config`
- `POST /api/ai/auto-training/config`
- `POST /api/ai/train-now`
- `GET /api/ai/post-run/latest`
- `GET /api/ai/model/download?kind=policy_adjustments`
