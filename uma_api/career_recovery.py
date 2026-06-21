"""Recovery helpers for ``single_mode_free/start`` failures.

A ``result_code`` of **102** on ``single_mode_free/start`` means the server
still holds an *in-progress* career, so a brand-new start is rejected. The game
only allows one active Single Mode career at a time; the most common triggers
are a stale local account cache or a previous run that didn't finish/abandon
cleanly server-side.

Rather than aborting (which would silently kill the career-looping feature —
the loop would just rack up consecutive failures and quit), we **resume** the
existing career: ``single_mode_free/load`` returns it in the same shape as a
start result, so the caller can feed it straight to ``apply_career_result`` /
the career runner. The runner finishes the resumed career and the loop proceeds
to its next start. This mirrors how the runner already reconciles 102 elsewhere
("server already done").

This module is intentionally free of any FastAPI / ``main`` imports so it can be
unit-tested in isolation (``main.py`` can't be imported in the test sandbox).
"""


def is_career_in_progress_error(error_text):
    """True when a start error indicates a career is already in progress.

    ``single_mode_free/start`` surfaces result_code 102 as an exception whose
    text contains ``"102"`` (see ``uma_api/client.py`` error formatting).
    """
    return "102" in str(error_text or "")


def resume_active_career(client, refresh=True, on_state=None):
    """Return a start-shaped result for the in-progress career, or ``None``.

    Steps:
      1. Optionally refresh the authoritative account snapshot (``load/index``)
         so any UI/account caches reflect reality. Best-effort: a failure here
         does not abort recovery.
      2. Load the in-progress career (``single_mode_free/load``).
      3. If it carries ``chara_info`` there is a career to resume — return that
         result. The caller feeds it to ``apply_career_result`` / the runner
         exactly like a start result.

    Returns ``None`` when there is no career to resume (so the caller can
    re-raise the original error rather than masking an unrelated 102).

    ``on_state`` — optional callback invoked with the refreshed ``load/index``
    ``data`` dict so the host can sync its own start-state cache.
    """
    if client is None:
        return None

    if refresh:
        try:
            index_result = client.call("load/index", {"adid": ""})
            index_data = (index_result or {}).get("data", {}) or {}
            refresh_cache = getattr(client, "refresh_cached_account_state", None)
            if callable(refresh_cache):
                try:
                    refresh_cache(index_data)
                except Exception:
                    pass
            if on_state is not None:
                try:
                    on_state(index_data)
                except Exception:
                    pass
        except Exception:
            # The refresh is only to keep caches honest; load_career below is
            # the real source of truth, so a refresh failure is non-fatal.
            pass

    try:
        career_result = client.load_career()
    except Exception:
        # No loadable career (e.g. genuinely no active run) -> let the caller
        # re-raise the original start error.
        return None

    career_data = (career_result or {}).get("data", {}) or {}
    if career_data.get("chara_info"):
        return career_result
    return None
