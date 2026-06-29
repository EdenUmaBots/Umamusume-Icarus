# Pre Icarus v5.32 AI Advisor Dataset Foundation

This build starts the AI/LLM integration safely by adding an offline learning layer. The live runner remains deterministic; the new components export structured data that can be used by local analytics, reward models, or future LLM tooling.

## Added runtime outputs

All files are written under `uma_runtime/ai/`.

- `turn_decisions.jsonl` - one state/action/outcome record per decision turn.
- `career_summaries.jsonl` - one summary per completed or stopped career.
- `failed_runs.jsonl` - summaries of careers that did not finish cleanly.
- `synthetic_scenarios.jsonl` - validated template prompts for offline edge-case labeling.
- `advisor_stats.json` - local aggregate statistics over exported decisions and race programs.
- `latest_export_manifest.json` - latest export manifest.

## New API endpoints

- `GET /api/ai/status`
- `POST /api/ai/rebuild-dataset`
- `GET /api/ai/advisor/latest`
- `GET /api/ai/dataset/download?kind=turn_decisions`

## Design notes

The AI layer is deliberately advisory only. It does not execute game actions and it does not bypass Pre Icarus's existing safety gates. Future live scoring can read these datasets and advisor tables, but all actions should continue to pass through the deterministic runner, Smart Race Solver, item logic, and event logic.

## UI

The Diagnostics card now contains an **AI Learning Data** section with dataset counts, a rebuild button, an advisor report button, and a turn-decision dataset download button.
