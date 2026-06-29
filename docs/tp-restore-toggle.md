# TP Restore Toggle

## Purpose

The TP restore toggle lets the user choose whether Pre Icarus should prefer Toughness items or Carats when restoring TP before starting or continuing automation.

## How it works

The top bar renders two restore options beside the TP display:

- Toughness
- Carats

The selected option is saved in `localStorage` and included in the career-start payload as both:

```json
{
  "tp_restore_currency": "toughness",
  "tp_restore_mode": "toughness"
}
```

The backend accepts `tp_restore_mode` as an alias and uses the selected value when it needs to restore TP.

## Behavior

- Toughness attempts item-based TP recovery first.
- Carats uses Carats for TP recovery.
- If Toughness is selected but unavailable, backend logic can safely fall back to Carats.

## Dependencies and interactions

This feature interacts with the career-start flow and account resource display. It does not change training, racing, skill, or Trackblazer decision logic.

## Verification

Select each toggle option, refresh the page, and verify the selected option persists. Start a career and confirm the outgoing payload includes the expected `tp_restore_currency` and `tp_restore_mode` values.
