# Pre Icarus v5.43 Local LLM Advisor

Pre Icarus v5.43 adds an optional Local LLM Advisor that connects to a local OpenAI-compatible chat server. The feature is disabled by default and is designed as an analyst, not a driver.

## What it does

- Tests a local LLM connection.
- Sends compact, safe turn-decision summaries to the model.
- Stores post-run analysis in `uma_runtime/ai/llm_run_summaries.jsonl`.
- Stores shadow turn reviews in `uma_runtime/ai/llm_advice.jsonl`.
- Displays the latest headline, risks, and candidate rules in AI Learning.

## What it does not do

- It does not execute model-generated commands.
- It does not override the deterministic career runner.
- It does not click, read game memory, or use process hooks.
- It does not send account/auth data. The prompt packet is built from AI dataset rows.

## Recommended setup

### LM Studio

Use LM Studio when you want the simplest Windows setup.

- Base URL: `http://localhost:1234/v1`
- Provider: `LM Studio`
- Mode: `Offline Analysis` first, then `Shadow Advisor`
- Model: the exact loaded model ID shown by LM Studio

Suggested model ladder:

- Lower-end PC: Qwen3 4B Instruct or a similar 4B instruct model
- Most gaming PCs: Qwen3 8B Instruct
- Strong PC: Qwen3 14B Instruct

### Ollama

Use Ollama if you prefer command-line setup.

```powershell
ollama pull qwen3:8b
ollama run qwen3:8b
```

Pre Icarus settings:

- Provider: `Ollama`
- Base URL: `http://localhost:11434/v1`
- Model: `qwen3:8b`
- API Key: `ollama`

## Modes

- `Off`: no local LLM usage.
- `Offline Analysis`: manual post-run analysis only.
- `Shadow Advisor`: manual recent-turn review plus post-run analysis.
- `Recommend Only`: stores stronger recommendation text for review, but still does not control the runner.

## Output schema expectation

The adapter tells the model to return strict JSON. Useful keys include:

```json
{
  "summary": "Short assessment of the run.",
  "risk_flags": ["Low energy before optional races"],
  "candidate_rules": [
    {"rule": "Prefer rest when HP is low and training value is weak.", "confidence": 0.72}
  ],
  "recommendation": "Keep Sweepy as baseline and test candidate rules in Shadow Mode."
}
```

Malformed replies are still saved as `raw_text` so they can be inspected without breaking the dashboard.

The parser also unwraps common local-model response shapes, including:

- fenced JSON blocks such as ```json ... ```
- `{ "analysis": { ... } }` envelopes
- `{ "advice": { ... } }` envelopes for shadow reviews
- JSON trapped inside a `raw_text` field
- double-encoded JSON strings
- alternate names such as `patterns`, `suggested_rules`, and `candidate_rules`

When possible, saved summaries now contain clean fields such as `key_patterns`, `risks`, and `repeatable_rules` directly under `analysis`.

## Form behavior

The Local LLM card preserves user edits while the AI Learning dashboard auto-refreshes. Type the model name/API key, check Enable Local LLM, then click **SAVE LLM SETTINGS**. Leaving the API key box blank on later saves keeps the currently saved key.
