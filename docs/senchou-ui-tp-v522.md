# Pre Icarus v5.22 Senchou-Saru Improvements

Pre Icarus v5.22 ports the useful parts of the uploaded Senchou-Saru Umabot while preserving Pre Icarus's newer Trackblazer systems.

## TP Restore Fix

Toughness 30 now uses the item endpoint proven by the uploaded bot:

```text
item/use_recovery_item
```

Payload shape:

```json
{
  "item_id": 32,
  "client_own_num": 1,
  "item_num": 1
}
```

Carats still use:

```text
user/recovery_trainer_point
```

This separates item restore from carat restore instead of trying to send item metadata to the carat endpoint.

## Parent Spark Filter

A modular `public/js/parent-filter.js` add-on now filters the existing parent grid by:

- parent/spark search
- spark category
- specific factor and minimum star count
- self-only vs full lineage
- rank/total-star/factor-star sort

The module hides/reorders cards visually only. It does not change DOM order, so the existing parent selection index logic remains intact.

## Safe Parent Cleanup

The parent filter includes a preview-first cleanup tool for recently created parents. Selected/active parents are excluded server-side.

Endpoints:

```text
POST /api/parents/remove-recent
POST /api/parents/remove
```

Use dry-run first:

```json
{"max_age_hours": 24, "dry_run": true}
```

## Career Monitor Drawer

A bottom monitor drawer adds:

- live runner log filters
- current-run stat chart
- crash trace viewer

New endpoints:

```text
GET /api/career/live_history
GET /api/career/crash_trace
```

`/api/career/history` remains the completed-career archive and was not repurposed.
