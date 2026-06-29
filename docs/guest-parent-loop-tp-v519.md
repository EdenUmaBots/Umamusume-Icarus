# Guest Parent Loop and TP Restore Guard v5.19

Pre Icarus v5.19 fixes two loop-start failure paths discovered after v5.18.

## Guest parent refresh before looped starts

When a career finishes and dev-loop mode starts the next career, Pre Icarus now refreshes `pre_single_mode/index` and verifies the selected guest/rental parent is still present in the fresh guest-parent list. If the same viewer/card is still available, the request is rewritten with the fresh `trained_chara_id` before calling `single_mode_free/start`.

If the rental is no longer available, the loop stops cleanly and asks the user to refresh Guest Parents and reselect instead of repeatedly sending stale rental payloads that can return API 501.

## API 500/501 start rejection handling

If the game still rejects a guest-parent start after refresh, Pre Icarus treats that as a fatal loop-start error and stops the loop. This prevents repeated rejected `single_mode_free/start` calls.

## Toughness 30 API 213 guard

When the server rejects the item-backed Toughness 30 restore payload with API 213, Pre Icarus caches that rejection for 30 minutes in the current process. During that window:

- if Carats fallback is enabled, the loop skips the rejected Toughness attempt and uses Carats directly;
- if Carats fallback is disabled, the start is blocked with a clear message.

This keeps the console from repeatedly showing the same rejected Toughness 30 restore call during career loops.
