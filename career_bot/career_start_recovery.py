"""Pure, import-safe helpers for the /api/career/run resume path.

Kept OUT of main.py so they can be unit-tested without triggering main's heavy
import-time side effects (e.g. master.mdb regeneration). The resume coercion is
the crash-prone part of the "start a new run after a non-looped finish" fix:
a stale/incomplete live career used to throw ``TypeError: int(None)`` and force
a full bot restart.
"""


def resume_career_fields(career_status):
    """Validate + 0-safe coerce a live ``career_status`` for RESUMING an active
    career.

    Raises ``ValueError`` if the career is stale/incomplete (no ``card_id``) so
    the caller can self-heal to a clean fresh start instead of crashing. The
    ``deck_id`` (matched_deck_id) and the friend/parent ids can legitimately be
    ``None`` for a genuine resume, so they are coerced to ``0`` rather than
    crashing on ``int(None)``.
    """
    cs = career_status or {}
    if cs.get("card_id") in (None, ""):
        raise ValueError("stale/incomplete active career: missing card_id")
    return {
        "card_id": int(cs.get("card_id") or 0),
        "support_card_ids": cs.get("support_card_ids"),
        "friend_viewer_id": int(cs.get("friend_viewer_id") or 0),
        "friend_card_id": int(cs.get("friend_card_id") or 0),
        "parent_id_1": int(cs.get("parent_id_1") or 0),
        "parent_id_2": int(cs.get("parent_id_2") or 0),
        "deck_id": int(cs.get("deck_id") or 0),
    }
