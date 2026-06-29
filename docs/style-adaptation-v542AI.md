# Pre Icarus v5.42AI Racing Style Adaptation

Pre Icarus AI now records and trains a conservative racing-style adaptation model.
The model is designed to learn whether changing from the Racing Settings style
before a race would have helped, without claiming access to hidden game formulas.

## What is logged

Every race can emit append-only rows to:

```text
uma_runtime/default/ai/style_adaptation_experiences.jsonl
```

Rows include:

- selected Racing Settings style
- shadow/recommended/applied style
- current stats, motivation, fans, HP, and skill points
- style, distance, and surface aptitudes
- owned skill IDs and official skill-condition summaries when available
- race metadata from official master-data exports
- clock policy and clock retry outcome
- opponent style counts when the API exposes them after race entry
- clean win vs clock-rescued win
- final rank and computed style reward

Opponent style counts usually become available after `race_entry`, which is too
late to change the style for that exact race. The model still logs them for
future learning and similar-race estimates.

## Data labels

Artifacts intentionally label evidence sources:

- `official_table_data`: generated from `master.mdb` exports
- `api_observed_data`: direct API/log observations
- `empirical_estimate`: learned from historical outcomes
- `unknown_hidden_formula`: a limitation marker for mechanics not exposed by data

## Modes

The AI Learning dashboard includes **Racing Style Adaptation**:

- `Disabled`: no style recommendations are used.
- `Shadow Only`: logs and predicts only; live style stays unchanged.
- `Recommend Only`: shows recommendations but keeps the user-selected style.
- `Auto Apply`: only applies a style switch after strict safety thresholds pass.

Default is **Shadow Only**.

## Safety thresholds

Auto Apply remains locked until the local model has enough evidence, including:

- at least 100 completed style experiences
- at least 20 style-change outcomes
- bad switch rate no higher than 20%
- candidate confidence and switch margin above config thresholds

The user’s Racing Settings style remains the fallback source of truth.

## Generated artifacts

Training writes:

- `style_adaptation_model.json`
- `style_adaptation_report.json`
- `style_adaptation_shadow_report.json`
- `style_adaptation_backtest.json`

The safe AI debug bundle includes these files.
