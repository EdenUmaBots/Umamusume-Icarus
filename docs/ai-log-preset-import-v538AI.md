# Pre Icarus v5.38AI AI Log + Preset Import

Pre Icarus v5.38AI extends the AI Learning importer so old builds can bring over both learning history and user presets.

## What gets imported

The AI importer accepts an old Pre Icarus folder, an old `uma_runtime` folder, an old `bot_logs` folder, or a zip file. It imports:

- `career_log_*.json`
- `race_outcomes.json`
- `events_seen.json`
- `data/settings_presets.json`
- legacy `data/presets/*.json` preset files

Auth/session files, Steam tokens, and raw account credentials are ignored.

## Preset merge behavior

- Existing presets are never overwritten.
- If an imported preset has the same name and the same content, it is counted as a duplicate.
- If an imported preset has the same name but different content, it is imported with an `Imported` suffix.
- Legacy bundled presets such as Fan Farming, Maru Fan Farming, Oguri, Parent Farming, xguri, and xguri parent are still filtered out.
- If the current build is still using the neutral `Default` preset, the imported active preset can become active automatically.

## Recommended long-term workflow

The easiest method is still to keep one shared runtime folder between builds. When that is not convenient, use AI Learning -> Import Previous Logs & Presets and paste the old build path.
