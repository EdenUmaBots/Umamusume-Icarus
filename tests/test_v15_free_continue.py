"""v1.5: Icarus read the wrong free-continue field.

The game state exposes the usable free-continue pool in ``free_continue_num``
(3 on the observed run) but Icarus read ``available_free_continue_num`` (0 on
Trackblazer races without a per-race free continue).  So it fell back to PAID
clocks, which those races reject with error 205, leaving 3 free retries unused.
``_free_continue_count`` must surface whichever field reports availability.
"""
import threading
import sys
import unittest
from unittest.mock import MagicMock

for _m in ("msgpack",):
    sys.modules.setdefault(_m, MagicMock())

from career_bot.runner import CareerRunner


def _runner():
    r = CareerRunner.__new__(CareerRunner)
    r.lock = threading.RLock()
    return r


class FreeContinueCountTests(unittest.TestCase):
    def test_reads_free_continue_num_when_available_field_zero(self):
        r = _runner()
        home = {"available_continue_num": 5, "available_free_continue_num": 0,
                "free_continue_num": 3, "free_continue_time": 123}
        self.assertEqual(r._free_continue_count(home), 3)

    def test_uses_max_of_both_fields(self):
        r = _runner()
        self.assertEqual(r._free_continue_count(
            {"available_free_continue_num": 2, "free_continue_num": 0}), 2)
        self.assertEqual(r._free_continue_count(
            {"available_free_continue_num": 1, "free_continue_num": 4}), 4)

    def test_zero_when_neither_present(self):
        r = _runner()
        self.assertEqual(r._free_continue_count({}), 0)
        self.assertEqual(r._free_continue_count(None), 0)


if __name__ == "__main__":
    unittest.main()
