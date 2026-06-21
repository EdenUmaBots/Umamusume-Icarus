"""v6.8: cures are bought only for an ACTIVE bad condition (not pre-stocked).

Addresses the user report of ending careers with unused Miracle Cures / creams.
Cures sit at base shop-tier 1, so the fix demotes them to no-buy unless their
condition is active (or the opt-in ``preemptive_cure_reserve`` flag is set).
"""
import unittest

from career_bot.items import MantItemManager, DISPLAY_TO_ID


class FakeClient:
    def exchange_items(self, payload, current_turn):
        return {"data": {}}

    def use_items(self, payload, current_turn):
        return {"data": {}}


def shop_row(shop_item_id, name, cost):
    return {
        "shop_item_id": shop_item_id,
        "item_id": DISPLAY_TO_ID[name],
        "coin_num": cost,
        "original_coin_num": cost,
        "item_buy_num": 0,
        "limit_buy_count": 1,
        "limit_turn": 0,
    }


def state(turn=30, shop=None, coins=0, ailment_ids=None, owned=None):
    chara = {"turn": turn, "vital": 80, "max_vital": 100, "motivation": 4, "scenario_id": 4}
    if ailment_ids:
        chara["chara_effect_id_array"] = list(ailment_ids)
    return {
        "data": {
            "chara_info": chara,
            "free_data_set": {
                "coin_num": coins,
                "user_item_info_array": [
                    {"item_id": DISPLAY_TO_ID[n], "num": q} for n, q in (owned or {}).items()],
                "pick_up_item_info_array": shop or [],
                "item_effect_array": [],
            },
        }
    }


class CureGatingTests(unittest.TestCase):
    def _bought(self, mgr):
        return {row["name"] for row in mgr.last_buy_selected}

    def test_no_condition_does_not_buy_cure(self):
        mgr = MantItemManager()
        # Miracle Cure sits at base shop-tier 1, yet with no active condition and
        # the default config it must NOT be purchased (contrast with the
        # preemptive-flag test below, which buys it on the identical setup).
        shop = [shop_row(1, "Miracle Cure", 40)]
        mgr.buy_shop_items(FakeClient(), state(shop=shop, coins=40), {"mant_config": {}})
        self.assertNotIn("Miracle Cure", self._bought(mgr))

    def test_active_condition_buys_specific_cure(self):
        mgr = MantItemManager()
        # Skin Outbreak (effect id 3) -> Rich Hand Cream should be bought.
        shop = [shop_row(1, "Rich Hand Cream", 15)]
        mgr.buy_shop_items(FakeClient(), state(shop=shop, coins=15, ailment_ids=[3]),
                           {"mant_config": {}})
        self.assertIn("Rich Hand Cream", self._bought(mgr))

    def test_active_condition_buys_miracle_cure_as_cure_all(self):
        mgr = MantItemManager()
        # Migraine (id 5) active, only a Miracle Cure available -> bought.
        shop = [shop_row(1, "Miracle Cure", 40)]
        mgr.buy_shop_items(FakeClient(), state(shop=shop, coins=40, ailment_ids=[5]),
                           {"mant_config": {}})
        self.assertIn("Miracle Cure", self._bought(mgr))

    def test_preemptive_flag_restores_old_behaviour(self):
        mgr = MantItemManager()
        shop = [shop_row(1, "Miracle Cure", 40)]
        mgr.buy_shop_items(FakeClient(), state(shop=shop, coins=40),
                           {"mant_config": {"preemptive_cure_reserve": True}})
        self.assertIn("Miracle Cure", self._bought(mgr))

    def test_charm_cap_lowered_to_three(self):
        from career_bot.items import ITEM_INVENTORY_CAPS
        self.assertEqual(ITEM_INVENTORY_CAPS["Good-Luck Charm"], 3)


if __name__ == "__main__":
    unittest.main()
