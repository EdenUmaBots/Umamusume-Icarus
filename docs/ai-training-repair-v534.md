# Pre Icarus v5.34 AI Training Repair & Validation

This build repairs the v5.33 AI dataset/trainer pipeline after real runtime logs showed that the live policy layer could become unsafe when race results were not extracted from raw API call logs.

## What changed

- Race results are now extracted from `single_mode_free/race_end` response payloads under `turn.api_calls`.
- Missing race results are no longer treated as losses in the race outcome table.
- Career summaries now include final stat snapshots, final fans, race count, race wins, win rate, rest count, recreation count, and reconstructed race results.
- Item telemetry is flattened from nested `selected`, `attempt`, and payload structures.
- Event analytics can seed from `events_seen.json` when event choices are stored outside career logs.
- The latest LLM prompt pack is overwritten atomically on each training run and its manifest reports the true line count.
- AI data health checks report race-result coverage, parsed item records, parsed event records, final-stat summary coverage, and whether live policy assistance is safe.
- If race rows exist but no race results are extracted, live policy assistance is automatically disabled.
- A safe AI debug bundle endpoint exports AI artifacts without raw auth files or full API logs.

## Why this matters

The v5.33 trainer defaulted missing race ranks to `99`, so a dataset with unparsed race results could falsely learn that every race was a loss. This build prevents that failure mode and requires a healthy race-result extraction rate before live learned policy hints can be used.

## New endpoint

- `GET /api/ai/safe-debug-bundle` creates a share-safe AI diagnostics zip.

## Recommended upgrade step

After installing this build, use Diagnostics → AI Learning Data → **REBUILD AI DATASET**, then **TRAIN NOW**. The AI health panel should report non-zero `race rows with result` before live policy assistance is trusted.
