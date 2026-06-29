"""Make a support deck legal for ``single_mode_free/start``.

The game caps a Single Mode deck at **6 cards total**. A borrowed friend
occupies its OWN slot (``friend_support_card_info``), so it must NOT also appear
among the owned ``support_card_ids``. Sending the same card twice, or more than
6 cards total, makes the server reject the start with **result_code 2511**.

The old start guard only trimmed the owned list by COUNT, which still let the
borrowed friend (or a duplicate owned card) survive when it sat within the cap.
This sanitizer fixes that: drop blank/invalid ids, remove duplicates (preserving
order), remove the borrowed friend from the owned list, then cap the owned list
to 5 (when a friend is borrowed) or 6 (when none is).

Kept free of FastAPI / ``main`` imports so it can be unit-tested in isolation.
"""


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def sanitize_support_deck(support_card_ids, friend_card_id):
    """Return a legal owned-support deck (list), preserving the original element
    types and order. ``friend_card_id`` is the borrowed friend's support card
    (0 / falsy = none borrowed)."""
    friend = _to_int(friend_card_id)
    has_friend = friend > 0
    cap = 5 if has_friend else 6
    seen = set()
    cleaned = []
    for raw in (support_card_ids or []):
        cid = _to_int(raw)
        if cid <= 0:
            continue                      # blank / invalid slot
        if has_friend and cid == friend:
            continue                      # already the borrowed slot — don't duplicate
        if cid in seen:
            continue                      # duplicate owned card
        seen.add(cid)
        cleaned.append(raw)               # preserve the caller's original element
    return cleaned[:cap]
