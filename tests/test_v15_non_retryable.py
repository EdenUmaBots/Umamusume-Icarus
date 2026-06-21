"""v1.5: learned non-retryable-race map.

When the game rejects a race continue (205 or 2507), the program id is recorded
and persisted so future careers skip the retry attempt entirely instead of
re-issuing a doomed continue and logging an error.
"""
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock

for _m in ("msgpack",):
    sys.modules.setdefault(_m, MagicMock())

from career_bot.runner import CareerRunner


class NonRetryableMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._prev_env = os.environ.get("UMA_RUNTIME_DIR")
        os.environ["UMA_RUNTIME_DIR"] = self.tmp
        self.r = CareerRunner.__new__(CareerRunner)
        self.r.lock = threading.RLock()
        self.r.base_dir = self.tmp
        self.r.burn_clocks = False
        self.r._race_grade_for_retry = lambda program_id: "G1"

    def tearDown(self):
        if self._prev_env is None:
            os.environ.pop("UMA_RUNTIME_DIR", None)
        else:
            os.environ["UMA_RUNTIME_DIR"] = self._prev_env

    def test_mark_and_load_roundtrip(self):
        self.r._mark_non_retryable(625, "205")
        self.r._mark_non_retryable(629, "2507")
        # fresh instance reads the persisted file
        r2 = CareerRunner.__new__(CareerRunner)
        r2.lock = threading.RLock()
        r2.base_dir = self.tmp
        self.assertEqual(r2._load_non_retryable(), {625, 629})

    def test_policy_skips_known_non_retryable_race(self):
        self.r._mark_non_retryable(625, "205")
        policy = self.r._race_retry_policy(
            {"mant_config": {}}, program_id=625, turn=24, attempts=0,
            free_clocks_available=3, is_mandatory=False,
        )
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["disabled_reason"], "race_known_non_retryable")

    def test_unknown_race_still_retries(self):
        policy = self.r._race_retry_policy(
            {"mant_config": {}}, program_id=999, turn=24, attempts=0,
            free_clocks_available=3, is_mandatory=False,
        )
        self.assertTrue(policy["enabled"])

    def test_learning_can_be_disabled(self):
        self.r._mark_non_retryable(625, "205")
        policy = self.r._race_retry_policy(
            {"mant_config": {"enable_non_retryable_learning": False}},
            program_id=625, turn=24, attempts=0, free_clocks_available=3, is_mandatory=False,
        )
        self.assertTrue(policy["enabled"])


if __name__ == "__main__":
    unittest.main()
