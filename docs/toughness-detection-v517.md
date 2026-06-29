# Pre Icarus v5.17 Toughness 30 Detection Fix

`master.mdb` defines the exact Toughness 30 item as `item_data.id = 32`, with the display name stored in `text_data` category `23`, index `32`.

Older local installs may contain stale configured item IDs from earlier detector attempts. For example, `23` is the `text_data` item-name category, not the Toughness item ID. Pre Icarus v5.17 validates any configured `UMA_TOUGHNESS_ITEM_IDS` or `data/toughness_item_ids.json` values against the authoritative master-data Toughness 30 ID before using them.

If an invalid override is found, Pre Icarus ignores it and writes:

```text
data/toughness_item_ids.invalid.json
```

The account inventory parser also accepts additional live payload count fields such as `item_num`, `num`, `count`, and `owned_num`, so owned Toughness 30 copies are not missed when account endpoints vary their field names.
