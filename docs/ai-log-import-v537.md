# Pre Icarus v5.37 AI Previous Log Import

Pre Icarus v5.37 adds an **Import Previous Logs** control to the AI Learning modal.

Accepted sources:

- an older Pre Icarus build folder, such as `C:\UmamusumeChatGPT\Pre Icarus v5.33`
- an older `uma_runtime` folder
- an older `bot_logs` folder
- a zip containing any of the above

The importer only reads gameplay learning data:

- `career_log_*.json`
- `race_outcomes.json`
- `events_seen.json`

Auth files, Steam tokens, account config, and unrelated runtime files are ignored.

After import, Pre Icarus rebuilds the AI dataset and can immediately train the local advisor. Repeated imports are hash-deduplicated through `uma_runtime/default/ai/import_manifest.json`.

## Easier long-term option

For future upgrades, the simplest migration is to copy the whole old `uma_runtime/default` folder into the new build before launching, or paste the old build folder path into the Import Previous Logs field after launching.
