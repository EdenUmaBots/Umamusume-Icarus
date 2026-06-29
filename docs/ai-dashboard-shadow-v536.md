# Pre Icarus v5.36 AI Dashboard & Shadow Evaluation

Pre Icarus v5.36 promotes the AI learning layer from hidden artifacts into a visible AI Learning dashboard. The dashboard remains local-first and deterministic: it reports what the learned models think, but live gameplay still flows through Pre Icarus's normal safety gates.

## Added artifacts

- `ai_dashboard.json`: compact UI-ready dashboard summary.
- `shadow_policy_report.json`: compares learned race-risk hints against historical outcomes without changing live decisions.
- `backtest_report.json`: offline replay-style metrics for learned risk warnings.
- `epithet_confidence.json`: best-effort epithet completion/confidence ledger.
- `preset_trainee_confidence.json`: per preset/trainee confidence and outcome summaries.

## Added endpoints

- `GET /api/ai/dashboard`
- `GET /api/ai/shadow/latest`
- `GET /api/ai/backtest/latest`
- `GET /api/ai/config-suggestions/latest`

## Safety

The dashboard is observational. Live policy assistance still only adjusts scores for legal candidates and remains confidence-gated. The AI cannot create an unavailable race, bypass mandatory game state, or execute an action directly.
