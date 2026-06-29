# Settings Windows and UI Refactor

## Purpose

The settings window system moves training, racing, and scenario configuration out of cramped inline setup controls and into dedicated modal windows backed by real preset settings.

## Setup layout

The Setup section now shows three buttons above Preset Configuration:

- Training Settings
- Racing Settings
- Scenario Overrides

The old Bot Settings heading was removed. Preset Configuration now includes a SAVE button beside NEW and DEL.

## Training Settings

Training Settings controls include:

- blacklist
- General Prioritization
- Event Choice Prioritization
- Summer Training Prioritization
- maximum failure chance
- risky training thresholds
- skill hint priority
- pre-summer rest behavior
- Train Wit During Finale
- training-level weighting
- rainbow and near-rainbow toggles
- preferred distance/stat target settings
- milestone pacing

The three prioritization controls open draggable modals. Dragging stats updates and saves the matching preset array.

## Racing Settings

Racing Settings is the only UI location for race running-style configuration. It includes force racing, farming fans, race warning/energy block behavior, retry controls, mandatory-race handling, and race strategy settings.

## Scenario Overrides

Scenario Overrides exposes Trackblazer-specific settings such as race-chain limits, item conservation thresholds, irregular training gates, shop behavior, preferred race distances/surfaces, and reset-to-defaults behavior.

## Removed duplicates

The old Running Style dropdown was removed from Preset Configuration. The duplicate Running Style control was removed from Skill Configuration because race strategy belongs in Racing Settings.

## Omitted Android-only controls

Training Analysis Validation and YOLO Stat Detection are intentionally not shown because Pre Icarus reads native game payloads rather than Android screenshots.

## Dependencies and interactions

UI code lives in `public/index.html`, `public/app.js`, and `public/styles.css`. Settings persist through `/api/presets` and are consumed by `career_bot/presets.py`, `career_bot/scenarios/mant.py`, `career_bot/races.py`, `career_bot/items.py`, and `career_bot/runner.py`.

## Verification

Open each settings modal, change values, click SAVE, refresh the page, and confirm the values survive. Run `node --check public/app.js` and full Python tests to validate wiring.

## Pre Icarus v5.5 placement correction

The setup workspace grid explicitly places `#bot-settings-section` in the first column immediately above `#preset-section`. This prevents CSS grid auto-placement from pushing the Training Settings, Racing Settings, and Scenario Overrides buttons below Trackblazer or Race Schedule sections when the workspace modal is open.

The corrected order is:

1. Team slots across the full width
2. Settings buttons in the left column
3. Preset Configuration in the left column
4. Trackblazer card in the left column
5. Race Schedule in the left column
6. Library in the right column

