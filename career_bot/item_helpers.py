"""Pure item-count helpers extracted from main.py.

These functions take data as arguments and have no dependence on main.py
module globals. They are re-imported into main.py so ``main.<name>`` and
intra-main.py callers continue to resolve unchanged.
"""


def _coerce_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _first_present(mapping, keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping and mapping.get(key) is not None:
            return mapping.get(key)
    return None


def _item_id_from_payload(item):
    return _coerce_int(_first_present(item or {}, ("item_id", "itemId", "id")), 0)


def _item_count_from_payload(item):
    # Live account payloads have drifted across endpoint versions.  The old TP
    # restore code only accepted `number`, which can make owned Toughness 30 look
    # missing when the API reports the same value as `item_num`, `num`, or
    # another count-shaped field.
    return _coerce_int(
        _first_present(
            item or {},
            (
                "number",
                "item_num",
                "itemNum",
                "num",
                "count",
                "quantity",
                "owned_num",
                "own_num",
                "item_count",
            ),
        ),
        0,
    )


def get_item_count(item_list, item_id):
    wanted = _coerce_int(item_id, item_id)
    for item in item_list or []:
        current = _item_id_from_payload(item)
        if current == wanted:
            return _item_count_from_payload(item)
    return 0


def find_item_count(item_list, item_id):
    """Return an item count only when the payload actually includes the item.

    Career responses can include partial user_item arrays. Missing item 32 means
    "unchanged", not zero, so TP item counts fall back to the cached client map.
    """
    wanted = _coerce_int(item_id, item_id)
    for item in item_list or []:
        current = _item_id_from_payload(item)
        if current == wanted:
            return _item_count_from_payload(item)
    return None
