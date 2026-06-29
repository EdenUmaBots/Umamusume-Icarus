# TP Restore Safety v5.16

Pre Icarus v5.16 changes TP restore behavior so selecting **Toughness 30** no longer silently falls back to Carats.

## Why this changed

Some server builds reject item-backed calls to `user/recovery_trainer_point` with API/result code `213`. When that happened in v5.15, Pre Icarus refreshed account state and could then fall back to Carats if TP was still below the required value. That made runs continue, but it was not obvious whether Carats were spent.

## New behavior

- **Toughness 30 selected:** Pre Icarus tries Toughness 30 once when the item ID is detected and at least one copy appears to be owned.
- **API 213 on Toughness 30:** Pre Icarus records that the server rejected the item-backed request, refreshes account state, and stops unless explicit fallback is enabled.
- **Carats selected:** Pre Icarus uses the legacy Carats restore path.
- **Carats fallback checkbox:** Carats are only used after a Toughness 30 failure when the dashboard checkbox **Use Carats if Toughness 30 fails** is enabled.

## Interpreting API 213

API 213 means the server rejected the restore request. For Toughness 30 attempts this usually means one of the following:

- the live endpoint does not accept the item-backed payload shape,
- the item count cached by Pre Icarus was stale,
- the item was unavailable even though the static master-data ID was correct.

Pre Icarus still auto-detects the authoritative Toughness 30 item ID from master data, but the live API payload schema is validated by the game server, not by `master.mdb`.
