"""v6.8 bug fixes: per-run sparks extraction (#2) and guest-parent id validation (#3)."""
import unittest

from career_bot.runner import CareerRunner


class GainedFactorsTests(unittest.TestCase):
    """#2: pull the trainee's EARNED sparks, not the inherited parent set."""

    def test_prefers_factor_array_differing_from_inherited(self):
        inherited = [502, 1203]
        data = {"single_mode_finish_common": {
            "trained_chara": [{"factor_id_array": [502, 1203]}],          # inherited (same)
            "gained_factor_info_array": [{"factor_id": 999}, {"factor_id": 888}],  # earned
        }}
        ids, info, debug = CareerRunner._extract_gained_factors(None, data, inherited)
        self.assertEqual(set(ids), {999, 888})
        self.assertIsNotNone(info)
        self.assertIsNotNone(debug)
        self.assertIn("factor_arrays_seen", debug)

    def test_no_earned_array_returns_empty(self):
        # Only the inherited set is present -> nothing to override with.
        data = {"single_mode_finish_common": {"trained_chara": [{"factor_id_array": [502, 1203]}]}}
        ids, info, debug = CareerRunner._extract_gained_factors(None, data, [502, 1203])
        self.assertEqual(ids, [])

    def test_missing_finish_common_is_safe(self):
        ids, info, debug = CareerRunner._extract_gained_factors(None, {}, [1, 2])
        self.assertEqual(ids, [])
        self.assertIsNone(debug)

    def test_plain_int_array_detected(self):
        data = {"single_mode_finish_common": {"earned_factor_id_array": [10, 20, 30]}}
        ids, info, debug = CareerRunner._extract_gained_factors(None, data, [1, 2])
        self.assertEqual(set(ids), {10, 20, 30})


class GuestParentValidationTests(unittest.TestCase):
    """#3: never send a viewer_id / synthetic value as rental_trained_chara_id."""

    @classmethod
    def setUpClass(cls):
        import main
        cls.main = main

    def _req(self, viewer=100, card=5, trained=""):
        from types import SimpleNamespace
        return SimpleNamespace(rental_viewer_id=viewer, rental_card_id=card,
                               rental_trained_chara_id=trained)

    def test_real_trained_id_accepted(self):
        self.assertEqual(self.main._rental_trained_chara_id({"instance_id": 777}, 100), 777)

    def test_viewer_id_rejected(self):
        # instance_id equal to the viewer_id is NOT a borrowable trained-chara id.
        self.assertEqual(self.main._rental_trained_chara_id({"instance_id": 100}, 100), 0)

    def test_synthetic_id_rejected(self):
        self.assertEqual(self.main._rental_trained_chara_id({"instance_id": "follow-100"}, 100), 0)
        self.assertEqual(self.main._rental_trained_chara_id({"instance_id": "src:5:100"}, 100), 0)

    def test_prefers_real_trained_chara_id_field(self):
        guest = {"trained_chara_id": 555, "instance_id": 100}  # instance_id is the viewer
        self.assertEqual(self.main._rental_trained_chara_id(guest, 100), 555)

    def test_match_requires_borrowable_row(self):
        req = self._req()
        # viewer+card match but the row only has a viewer-id fallback -> reject.
        self.assertFalse(self.main._guest_matches_start_request(
            req, {"viewer_id": 100, "card_id": 5, "instance_id": 100}))
        # viewer+card match with a genuine trained id -> accept.
        self.assertTrue(self.main._guest_matches_start_request(
            req, {"viewer_id": 100, "card_id": 5, "instance_id": 777}))

    def test_exact_trained_id_match_still_works(self):
        req = self._req(trained="777")
        self.assertTrue(self.main._guest_matches_start_request(
            req, {"viewer_id": 100, "card_id": 5, "instance_id": 777}))


class TrackblazerAptitudeTests(unittest.TestCase):
    """Planner must use BASE master-data aptitudes, not inflated live values."""

    @classmethod
    def setUpClass(cls):
        import main
        cls.main = main

    def _req(self, **kw):
        from types import SimpleNamespace
        base = dict(trainee_name="Oguri Cap", trainee_id="", aptitudes={},
                    primary_distances=[], running_style="")
        base.update(kw)
        return SimpleNamespace(**base)

    def test_ignores_inflated_live_aptitudes(self):
        # Dashboard sends inflated S-heavy aptitudes (gained at career start via
        # inheritance); the planner must fall back to the card's base ranks.
        inflated = {"Sprint": "D", "Mile": "S", "Medium": "S", "Long": "S",
                    "Turf": "S", "Dirt": "S", "Pace": "S", "Late": "S"}
        apt = self.main._trackblazer_profile_aptitudes(self._req(aptitudes=inflated))
        self.assertEqual(apt.get("Mile"), "A")    # base A, not S
        self.assertEqual(apt.get("Medium"), "A")
        self.assertEqual(apt.get("Long"), "B")    # base B, not S
        self.assertNotIn("S", (apt.get("Mile"), apt.get("Medium"), apt.get("Long")))

    def test_unknown_trainee_falls_back_to_request(self):
        apt = self.main._trackblazer_profile_aptitudes(
            self._req(trainee_name="Nonexistent Trainee ZZZ", aptitudes={"Mile": "A"}))
        self.assertEqual(apt.get("Mile"), "A")


class DeckRarityTests(unittest.TestCase):
    """SSR cards must label/resolve as SSR, not R (rarity tables were inverted)."""

    @classmethod
    def setUpClass(cls):
        import main
        cls.main = main

    def test_rarity_labels_correct(self):
        self.assertEqual(self.main._RARITY_LABELS[1], "R")
        self.assertEqual(self.main._RARITY_LABELS[2], "SR")
        self.assertEqual(self.main._RARITY_LABELS[3], "SSR")

    def test_rarity_base_levels_correct(self):
        self.assertEqual(self.main._RARITY_LB0_BASE_LV[1], 20)   # R
        self.assertEqual(self.main._RARITY_LB0_BASE_LV[3], 30)   # SSR


class PresetSelectionTests(unittest.TestCase):
    """A preset's deck/trainee/parent `selection` must survive serialize (was dropped)."""

    def test_selection_preserved_on_serialize(self):
        from career_bot import presets
        data = {"name": "X", "selection": {"trainee": {"id": 1}, "deck": [10, 20, 30]}}
        out = presets.serialize_preset(data)
        self.assertEqual(out.get("selection"), {"trainee": {"id": 1}, "deck": [10, 20, 30]})


if __name__ == "__main__":
    unittest.main()
