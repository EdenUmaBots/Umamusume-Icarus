"""Pure Trackblazer policy constants shared by item/race logic.

These rules intentionally contain no OCR concepts.  They are the
algorithmic part of the Trackblazer policy translated for Pre Icarus's
native game-state payloads.
"""

TRACKBLAZER_SHOP_TIERS = {
    # Tier 1: race/training economy spine and emergency protection.
    "good-luck_charm": 1,
    "master_cleat_hammer": 1,
    "artisan_cleat_hammer": 1,
    "glow_sticks": 1,
    "royal_kale_juice": 1,
    "grilled_carrots": 1,
    "rich_hand_cream": 1,
    "miracle_cure": 1,

    # Tier 2: direct stats, with scrolls/manuals above low-value notepads.
    "speed_scroll": 2,
    "stamina_scroll": 2,
    "power_scroll": 2,
    "guts_scroll": 2,
    "wit_scroll": 2,
    "speed_manual": 2,
    "stamina_manual": 2,
    "power_manual": 2,
    "guts_manual": 2,
    "wit_manual": 2,

    # Tier 3: recovery/mood stabilizers.
    "vita_65": 3,
    "vita_40": 3,
    "vita_20": 3,
    "berry_sweet_cupcake": 3,
    "plain_cupcake": 3,

    # Tier 4: training-effect items.
    "empowering_megaphone": 4,
    "motivating_megaphone": 4,
    "coaching_megaphone": 4,
    "reset_whistle": 4,
    "speed_ankle_weights": 4,
    "stamina_ankle_weights": 4,
    "power_ankle_weights": 4,
    "guts_ankle_weights": 4,

    # Tier 5: condition cures other than the Trackblazer-critical ones above.
    "fluffy_pillow": 5,
    "pocket_planner": 5,
    "smart_scale": 5,
    "aroma_diffuser": 5,
    "practice_drills_dvd": 5,

    # Tier 6: permanent facility gains.
    "speed_training_application": 6,
    "stamina_training_application": 6,
    "power_training_application": 6,
    "guts_training_application": 6,
    "wit_training_application": 6,

    # Tier 7: max-energy investments.
    "energy_drink_max": 7,
    "energy_drink_max_ex": 7,

    # Tier 8: expensive one-time statuses and low-impact bond item.
    "pretty_mirror": 8,
    "reporters_binoculars": 8,
    "master_practice_guide": 8,
    "scholars_hat": 8,
    "yummy_cat_food": 8,

    # Notepads are usable if owned, but usually not worth buying before the real kit.
    "speed_notepad": 8,
    "stamina_notepad": 8,
    "power_notepad": 8,
    "guts_notepad": 8,
    "wit_notepad": 8,
}

DEFAULT_ENERGY_RECOVERY_THRESHOLD = 40
DEFAULT_ENERGY_ITEM_RESERVE = 1
DEFAULT_CUPCAKE_RESERVE = 1
ENERGY_OVERSHOOT_CAP_RATIO = 1.10
ENERGY_CRITICAL_KALE_THRESHOLD = 20

# Late-game item policy. When False (the default), after turn 64 the bot dumps
# every remaining item on any slightly-useful training -- summer is over and
# finale races pay zero coins, so an unspent item is pure waste. Set True to keep
# the conservative reserve/priority-gate behavior instead. (Scenario override:
# mant_config.save_items_lategame.)
DEFAULT_SAVE_ITEMS_LATEGAME = False

VITA_GAINS = {
    "Vita 20": 20,
    "Vita 40": 40,
    "Vita 65": 65,
}

ENERGY_CONSERVATION_ORDER = ("Vita 20", "Vita 40", "Vita 65")
CUPCAKE_ORDER = ("Berry Sweet Cupcake", "Plain Cupcake")

DEFAULT_CHARM_FAILURE_THRESHOLD = 20
DEFAULT_CHARM_MIN_MAIN_GAIN = 20
# Above this failure rate, fire the Good-Luck Charm even on a modest-gain
# training (a wasted-turn failure is worse than the saved charm).
DEFAULT_CHARM_FAILURE_RATE_HIGH = 40
DEFAULT_LOW_MOOD_ITEM_GAIN_FLOOR = 15

# P0: conservation must engage much earlier (was 65).  At 65 the bot burned
# hammers freely on every regular G1 right up to the finale window, arriving at
# the T74/76/78 climax with nothing to swing.  25 keeps mid-career G1 spending
# in check while still allowing early debut/G1 usage.
RACE_ITEM_CONSERVATION_START_TURN = 25
TRACKBLAZER_FINALE_RACE_TURNS = (74, 76, 78)
TRACKBLAZER_FINAL_RACE_TURN = 78

# --- Year-end race handling -------------------------------------------------
# A "year-end" race (Hopeful Stakes ~turn 24, Arima Kinen ~turn 72, plus the
# career finale >= 73) is safe to chain into: the year/career ends right after,
# so the consecutive-race energy penalty never carries forward, and any energy
# topped up beforehand can never be spent.
#
# These are TWO distinct concerns with different correct turn-sets:
#  * REST-GUARD exemption: don't rest/skip over a wrap-up race. Mirrors the
#    original (now-removed) legacy engine's race-chain-break exemption. Covers the
#    early-Dec half-turns too {23,47,71} because the chain-break is purely about
#    not resting over the race.
#  * ENERGY-ITEM waste: spending recovery items is pure waste ONLY on the LAST
#    training turn of the year {24,48,72} (and the finale). 23/47/71 are
#    EXCLUDED -- the next turn (24/48/72) is still a real training turn, so
#    energy banked on 23/47/71 can still be used and must NOT be skipped.
YEAR_END_REST_EXEMPT_TURNS = frozenset({23, 24, 47, 48, 71, 72})
YEAR_END_ENERGY_WASTE_TURNS = frozenset({24, 48, 72})


def is_year_end_rest_exempt(turn):
    """True on year-end wrap-up race turns + the finale (>=73): the
    consecutive-race rest guard should NOT fire (parity with mant.py legacy)."""
    t = int(turn or 0)
    return t in YEAR_END_REST_EXEMPT_TURNS or t >= 73


def is_year_end_energy_waste_turn(turn):
    """True on the LAST training turn of each year {24,48,72} + the finale
    (>=73): spending energy/recovery items here is wasted (energy can't be
    used after). Deliberately excludes 23/47/71."""
    t = int(turn or 0)
    return t in YEAR_END_ENERGY_WASTE_TURNS or t >= 73
# P0: hold back ~3 Master hammers for the climax/finale (was 2) so regular G1s
# stop draining the stock.  An analogous Artisan pre-finale reserve protects the
# Artisan stock the same way.
DEFAULT_MASTER_HAMMER_FINALE_RESERVE = 3
DEFAULT_ARTISAN_HAMMER_FINALE_RESERVE = 2
# v2.0: keep exactly this many hammers (Master-preferred) banked for the 3 climax
# races; any hammer beyond this is "surplus" and gets spent on regular G1s
# (weakest first) instead of being stranded unused at career end.
DEFAULT_HAMMER_FINALE_RESERVE = 3
DEFAULT_ARTISAN_HAMMER_MIN_STOCK_FOR_G3 = 3
DEFAULT_ARTISAN_HAMMER_MIN_STOCK_FOR_G2 = 2
DEFAULT_GLOW_STICK_FINAL_RESERVE = 1
DEFAULT_GLOW_STICK_MIN_FANS = 20000
TOP_TIER_G1_GLOW_FAN_FLOOR = 30000

GRADE_RANK = {"G1": 5, "G2": 4, "G3": 3, "OP": 2, "PRE-OP": 1, "800": 0, "900": 0}


def normalize_grade(value):
    text = str(value or "").strip().upper()
    if text in GRADE_RANK:
        return text
    # P0: CLIMAX / finale race rows carry a race_instance_id beginning with "9"
    # (e.g. "920018") and NO official grade text.  Map them to an explicit
    # "CLIMAX" token so downstream item logic can branch cleanly instead of
    # falling through the legacy-digit decode below and being treated as junk.
    if text.startswith("9"):
        return "CLIMAX"
    # Old race_instance_id encoding used a leading digit for grade. Keep this as
    # a fallback for legacy race_map rows that do not carry official grade text.
    if text.startswith("1"):
        return "G1"
    if text.startswith("2"):
        return "G2"
    if text.startswith("3"):
        return "G3"
    return text

# P1 decision-policy defaults.  These stay pure and scenario-local so the
# strategy/item layers can share thresholds without engine-specific logic.
IRREGULAR_TRAINING_MIN_TURN = 25
DEFAULT_IRREGULAR_TRAINING_SCORE_THRESHOLD = 0.62
DEFAULT_IRREGULAR_TRAINING_FAILURE_LIMIT = 24
DEFAULT_IRREGULAR_TRAINING_MIN_MAIN_GAIN = 30
DEFAULT_IRREGULAR_TRAINING_CHARM_FAILURE_LIMIT = 65
DEFAULT_IRREGULAR_TRAINING_CHARM_MIN_MAIN_GAIN = 30

DEFAULT_RACE_CHAIN_TARGET = 3
DEFAULT_CHAIN_CRITICAL_VITAL = 10
DEFAULT_CHAIN_LOW_VITAL = 35
# v1.4: raised 0.22 -> 0.45.  After 2 consecutive races the chain-break guard
# would convert the NEXT planned race into a training turn whenever a merely
# decent training existed (0.22 bar, no energy check), dropping ~10+ planned
# races/career and starving fans.  0.45 keeps planned races unless the training
# is clearly strong; the HP-gated rest branch still protects against racing into
# an energy wall.  Tunable per preset via mant_config.chain_break_training_threshold.
DEFAULT_CHAIN_TRAINING_THRESHOLD = 0.45
DEFAULT_CHAIN_FAILURE_LIMIT = 30
UNSAFE_CHAIN_MIN_GRADE_RANK = 3  # G3+ only when a voluntary streak is already unsafe.

DEFAULT_WHISTLE_SCORE_THRESHOLD = 35
DEFAULT_WHISTLE_MIN_TURN = 13
DEFAULT_WHISTLE_MAX_FAILURE = 49
DEFAULT_WHISTLE_FORCE_SAFE_SCORE = 25


# P2 native decision refinements.
NEAR_RAINBOW_BOND_THRESHOLD = 60
# v1.5: near-rainbow (a partner one bond-tier from rainbow) is worth pushing
# toward, so the incentive was raised from a token 1.14x cap to 1.6x.
NEAR_RAINBOW_BONUS_PER_PARTNER = 0.15
NEAR_RAINBOW_BONUS_CAP = 0.6
SUMMER_PRIORITY_BONUS_BY_RANK = (0.18, 0.10, 0.05)
# v1.5: rank-0 (top-priority stat) leveled-facility reward raised to peak 1.75x
# (was 1.38x) so the bot favors the high-level facilities that the solver grinds.
TRAINING_LEVEL_MULTIPLIER_BY_RANK = {
    0: {2: 1.15, 3: 1.32, 4: 1.52, 5: 1.75},
    1: {2: 1.04, 3: 1.08, 4: 1.14, 5: 1.22},
    2: {2: 1.02, 3: 1.05, 4: 1.08, 5: 1.12},
}
CAP_RAINBOW_ALLOWANCE_FACTOR = 0.22
CAP_SOFT_BUFFER_RATIO = 0.97

RACE_SELECTION_GRADE_WEIGHT = 100000
RACE_SELECTION_RIVAL_WEIGHT = 10000000
RACE_SELECTION_DISTANCE_WEIGHT = 10000
RACE_SELECTION_SURFACE_WEIGHT = 5000
RACE_SELECTION_APTITUDE_WEIGHT = 100

SMART_SOLVER_TRAIN_LOCK_DEFAULT = True


# P3 event-choice scoring parity.  These numbers mirror the reference
# Trackblazer event fallback policy, but remain generic native scoring inputs.
EVENT_CHAIN_UNLOCK_BONUS = 1000
EVENT_CHAIN_END_PENALTY = -300
EVENT_RANDOM_PENALTY = -10
EVENT_RANDOM_PARTIAL_BONUS = 50
EVENT_SKILL_HINT_BONUS = 25
# Extra bonus when a choice hints a skill the user explicitly PLANNED to buy
# (forced_skills / manual_skill_tiers, minus blacklist). Moderate by design:
# stacked on the generic hint (25 -> 55 total) it outranks a small stat/energy
# advantage but not a big swing or a top-priority stat (priority bonus up to 50).
EVENT_PLANNED_SKILL_HINT_BONUS = 30
EVENT_POSITIVE_STATUS_BONUS = 25
EVENT_NEGATIVE_STATUS_PENALTY = -25
EVENT_BOND_GAIN_BONUS = 20
EVENT_BOND_LOSS_PENALTY = -20
EVENT_MOOD_LOSS_PENALTY = -150
EVENT_STAT_PRIORITY_BONUS_BY_RANK = (50, 40, 30, 20, 10)
EVENT_ENERGY_PRIORITIZE_MULTIPLIER = 100
EVENT_LOW_ENERGY_MULTIPLIERS = (
    (30, 4),
    (50, 3),
    (70, 2),
    (90, 1),
)
EVENT_MOOD_BONUS_BY_MOTIVATION = {
    1: 150,
    2: 120,
    3: 90,
    4: 60,
    5: 0,
}
