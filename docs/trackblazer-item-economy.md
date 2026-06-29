# Trackblazer Item Economy

## Purpose

The Trackblazer item economy improves MANT/Trackblazer performance by using native Pre Icarus state to decide what to buy and when to spend training, recovery, condition, and race items.

## Shop priorities

Critical Trackblazer items are purchased before generic stat items:

- Good-Luck Charm
- Master Cleat Hammer
- Artisan Cleat Hammer
- Glow Sticks
- Royal Kale Juice
- Grilled Carrots
- Rich Hand Cream
- Miracle Cure

Stat Scrolls and Manuals remain valuable but sit below the critical kit. Notepads and expensive one-time good-condition items are late/shop-leftover purchases.

## Training item rules

Good-Luck Charm is used only when the selected training has enough failure risk and enough main-stat gain to justify protection. If Charm will be used, energy items are skipped because Charm makes training failure irrelevant and energy is spent after the training.

Energy recovery uses:

- configurable threshold, default 40
- one low-tier Vita reserve by default
- greedy item selection toward a soft 110% cap
- guarded Royal Kale Juice usage
- Royal Kale Juice plus cupcake pairing when mood safety is needed

## Race item rules

Race items use Trackblazer conservation rules:

- Master Hammer for G1 races
- Artisan Hammer for G2/G3 races, or G1 fallback if no Master Hammer exists
- Glow Sticks for high-value G1 races
- conservation starts at turn 65
- Finale reserve logic uses Pre Icarus native turn numbering

## Configuration

Common keys live under `mant_config`:

```json
{
  "energy_recovery_threshold": 40,
  "trackblazer_energy_item_reserve": 1,
  "trackblazer_cupcake_reserve": 1,
  "charm_min_main_gain": 50,
  "trackblazer_master_hammer_finale_reserve": 2,
  "trackblazer_artisan_hammer_min_stock_for_g3": 3,
  "trackblazer_artisan_hammer_min_stock_for_g2": 2,
  "trackblazer_glow_stick_final_reserve": 1,
  "trackblazer_glow_stick_min_fans": 20000
}
```

## Dependencies and interactions

Implemented primarily in `career_bot/items.py`, with shared constants in `career_bot/trackblazer_rules.py`. Interacts with training decision output, race metadata, current turn, inventory, and preset settings.

## Verification

Use unit tests in `tests/test_trackblazer_p0_items.py`. In UI, adjust item conservation settings, run a Trackblazer career, and inspect buy/use traces for Charm, energy, Kale, cupcake, hammers, and Glow Sticks.
