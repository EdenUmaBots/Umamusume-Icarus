"""v1.4: chain-break training-substitution bar raised so the bot stops dropping
planned races for merely-decent training after 2 consecutive races."""
import unittest

from career_bot import trackblazer_rules as tr


class ChainBreakThresholdTests(unittest.TestCase):
    def test_threshold_raised(self):
        # Was 0.22 (too eager to convert a planned race to training).
        self.assertEqual(tr.DEFAULT_CHAIN_TRAINING_THRESHOLD, 0.45)

    def test_threshold_above_single_rainbow_floor(self):
        # A single rainbow partner contributes ~0.18; the old 0.22 bar was
        # cleared by almost any decent turn.  0.45 requires clearly-strong
        # training before a planned race is dropped.
        self.assertGreater(tr.DEFAULT_CHAIN_TRAINING_THRESHOLD, 0.22)


if __name__ == "__main__":
    unittest.main()
