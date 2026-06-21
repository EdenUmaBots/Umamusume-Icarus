"""Regression tests for v7.6.1.

``single_mode_free/start`` returns result_code 102 when the server still holds
an in-progress career (stale account cache, or a prior run that didn't
finish/abandon cleanly). Before v7.6.1 this re-raised: the manual start surfaced
a raw 102 to the UI, and the **career loop** would rack up consecutive failures
and quit — silently killing the auto-start-next-career feature.

v7.6.1 adds ``uma_api.career_recovery``: on a 102, refresh state and *resume*
the in-progress career (``single_mode_free/load``), returning it in the same
shape as a start result so the runner finishes it and the loop proceeds.

These tests exercise the recovery module directly (``main.py`` can't be imported
in the sandbox — it spins up FastAPI). They lock in:
  - resume when a career is genuinely in progress,
  - return None (caller re-raises) when there is nothing to resume,
  - non-102 errors are never treated as recoverable,
  - the refresh step is best-effort and never aborts recovery.
"""
import os
import sys
import unittest

# Make the project root importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uma_api.career_recovery import is_career_in_progress_error, resume_active_career


class FakeClient:
    """Minimal stand-in for UmaClient exercising the recovery path."""

    def __init__(self, career_result=None, load_raises=False, index_raises=False):
        self._career_result = career_result
        self._load_raises = load_raises
        self._index_raises = index_raises
        self.calls = []
        self.refreshed_with = None

    def call(self, endpoint, payload=None):
        self.calls.append((endpoint, payload))
        if endpoint == "load/index":
            if self._index_raises:
                raise RuntimeError("load/index boom")
            return {"data": {"viewer_id": 1}}
        raise AssertionError(f"unexpected call {endpoint}")

    def refresh_cached_account_state(self, data):
        self.refreshed_with = data

    def load_career(self):
        if self._load_raises:
            raise Exception("API error 102 on single_mode_free/load")
        return self._career_result


class ErrorClassificationTests(unittest.TestCase):
    def test_102_is_career_in_progress(self):
        self.assertTrue(
            is_career_in_progress_error(
                'API error 102 on single_mode_free/start: {"result_code": 102}'
            )
        )

    def test_other_codes_are_not(self):
        for err in ("API error 208 on single_mode_free/start", "API error 501", "", None):
            self.assertFalse(is_career_in_progress_error(err), err)


class ResumeActiveCareerTests(unittest.TestCase):
    def test_resumes_when_career_in_progress(self):
        career = {"data": {"chara_info": {"turn": 33, "card_id": 100101}}}
        client = FakeClient(career_result=career)
        result = resume_active_career(client)
        self.assertIs(result, career, "must return the loaded in-progress career as the result")

    def test_returns_none_when_no_chara_info(self):
        """No in-progress career -> None so the caller re-raises the real 102."""
        client = FakeClient(career_result={"data": {}})
        self.assertIsNone(resume_active_career(client))

    def test_returns_none_when_load_career_fails(self):
        client = FakeClient(load_raises=True)
        self.assertIsNone(resume_active_career(client))

    def test_refresh_failure_does_not_abort_resume(self):
        """A failing load/index refresh must not stop us from resuming."""
        career = {"data": {"chara_info": {"turn": 5}}}
        client = FakeClient(career_result=career, index_raises=True)
        self.assertIs(resume_active_career(client), career)

    def test_on_state_callback_receives_refreshed_data(self):
        career = {"data": {"chara_info": {"turn": 1}}}
        client = FakeClient(career_result=career)
        seen = {}
        resume_active_career(client, on_state=lambda data: seen.update(data))
        self.assertEqual(seen.get("viewer_id"), 1)
        self.assertEqual(client.refreshed_with, {"viewer_id": 1})

    def test_none_client_is_safe(self):
        self.assertIsNone(resume_active_career(None))


class LoopContractTests(unittest.TestCase):
    """The resumed result must be shaped so the loop's existing consumers
    (apply_career_result / career_runner) work unchanged: a dict with
    ``data.chara_info``. This is what keeps career looping intact."""

    def test_resumed_result_has_start_result_shape(self):
        career = {"data": {"chara_info": {"turn": 12, "card_id": 100101}}}
        client = FakeClient(career_result=career)
        result = resume_active_career(client)
        self.assertIsInstance(result, dict)
        self.assertIn("data", result)
        self.assertIn("chara_info", result["data"])


if __name__ == "__main__":
    unittest.main()
