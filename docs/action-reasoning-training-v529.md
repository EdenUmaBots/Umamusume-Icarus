# Pre Icarus v5.29 Action Reasoning and Training Balance

## Action Log click lock

The cockpit now remembers the historical Action Log row selected by the user. Regular runner and decision-trace polling keeps that selected turn visible instead of forcing Decision Reasoning back to the newest turn. If the selected turn rolls out of the retained action buffer, the UI returns to live/latest behavior.

## Footer overlap cleanup

The live `Turn / action / step` footer ticker was redundant with Action Log, Decision Reasoning, the Career card, and the Monitor drawer. While the runner is active, the footer status is now blank unless the runner is paused or an error/status message needs attention. This prevents the status text from appearing behind the Run/Stop/Pause row.

## Training balance

Training scoring keeps Pre Icarus's existing MANT logic but adds a small target-pressure layer inspired by the Android automation bot's ratio-based scoring. Stats far below their target get a stronger multiplier, stats close to target taper down, and Wit receives dampening when it is already ahead of weaker target stats.

Wit is still allowed when it is valuable, especially for safe recovery or strong friendship training. The change only reduces repeated Wit picks when Speed, Power, Stamina, or Guts are clearly behind the selected build targets.

## Decision trace details

Training candidates now include extra diagnostic fields:

- `main_gain`
- `target_completion` / `target_completion_pct`
- `energy_delta`
- `reason_flags` such as `energy recovery`, `below target`, and `wit damped because other stats are behind`

These fields are surfaced in Decision Reasoning so users can see why a training candidate won or why Wit was damped.
