# TP Restore and Career History Reliability

## Purpose

Pre Icarus v5.10 improves two reliability areas: completed-run Career History metadata and TP restore resource selection before starting a career.

## Career History improvements

The runner now records a race result ledger after each race resolves. Each entry includes the turn, program id, race name, grade, distance, fan reward, final rank, and whether the race was won. Career History uses this ledger when the final server payload does not expose race count, win count, or major-win arrays directly.

The finish handler also searches nested finish payloads for final rating, rank, race count, win count, skills, factors, and win arrays. This makes the redesigned Career History modal more resilient to different response shapes across regions or API versions.

## TP Restore improvements

The TP Restore selector now distinguishes **Toughness 30** from **Carats**. When Toughness 30 is selected, Pre Icarus checks for configured or master.mdb-detected item IDs and verifies at least one copy is owned before attempting an item-backed restore.

If no Toughness 30 item id is configured or detected, or if none are owned, the bot falls back to Carats and records the reason in the career report.

## Configuration

Toughness 30 item IDs may be provided in either of these ways:

```text
UMA_TOUGHNESS_ITEM_IDS=123,456
```

or:

```json
data/toughness_item_ids.json
{
  "item_ids": [123, 456]
}
```

When master.mdb detection succeeds, Pre Icarus writes the detected IDs to:

```text
data/toughness_item_ids.detected.json
```

## Verification

1. Log in and check the account strip. The TP Restore selector should show Toughness 30 and Carats.
2. Open `/api/tp-restore/status` and confirm `toughness.usable` is true before expecting item-backed restore.
3. Start a career with low TP and Toughness 30 selected. The career report should include the TP restore reasoning.
4. Complete a career. Career History should show race count, win count, major wins where available, and rating if the finish payload exposes it.


## Pre Icarus v5.11 note

Pre Icarus v5.11 replaces the broad Toughness 30 text scan with an exact master-data lookup and adds generated metadata files for TP restore items, major-win saddle names, and career rank thresholds. Race fan rewards are now exported into race planner metadata through `single_mode_fan_count`.
