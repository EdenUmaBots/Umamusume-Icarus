# Pre Icarus documentation

Start here if you're new. The docs are organized into a few focused
user guides plus a deeper archive of historical implementation notes.

## User guides (read these first)

| Guide | Read it when… |
|---|---|
| **[trackblazer-guide.md](trackblazer-guide.md)** | You want to understand how the bot picks races, why race count is what it is, and which knobs to tune for more races |
| **[ai-learning.md](ai-learning.md)** | You're trying to enable Live Policy Assistance or wondering what "shadow precision" means |
| **[settings-and-presets.md](settings-and-presets.md)** | You're setting up the bot, customizing presets, or worried about losing settings on upgrade |
| **[smart-training.md](smart-training.md)** | You want to understand how training picks get made each turn |

## Quick links — the 3 most-asked questions

### "Why is my race count low?"

Go to **Smart Race Solver Settings** and raise **Max Streak** to 5
(default is 2 — that's the cap). Also drop **Race Cost %** to 75.
Both knobs were silently no-ops before v6.7.11; they work now. See
[trackblazer-guide.md](trackblazer-guide.md) for the full list.

### "What's the difference between Live Policy Assistance and Training Scorer Mode?"

Different systems. LPA biases RACES at planning time. Training
Scorer Mode biases TRAININGS each turn. Both are safe to leave at
defaults until you've collected 50+ careers. See
[ai-learning.md](ai-learning.md).

### "Where do my presets live and will an upgrade wipe them?"

Presets live in `<userdata>/data/settings_presets.json` (outside the
build folder). Upgrades don't touch them. See
[settings-and-presets.md](settings-and-presets.md) for the full
folder layout.

## Other topics (single-feature notes)

- Career history: `career-history.md`, `career-history-redesign.md`
- Skills: `weighted-skill-configuration.md`,
  `skill-profile-card-id-compatibility.md`
- Preset UI history: `preset-history-ui-v528.md`,
  `preset-system-v527.md`, `settings-preset-split.md`
- TP recovery: `tp-restore-toggle.md`, `tp-restore-safety-v516.md`,
  `tp-restore-and-career-history-v510.md`
- Game data: `master-data-training-calendar-v513.md`
- UI / stability fragments: `senchou-ui-tp-v522.md`,
  `umabot-stability-v525.md`, `operator-controls-v526.md`
- Feature notes: `guest-parent-loop-tp-v519.md`,
  `setup-unlock-manual-races-v521.md`, `toughness-detection-v517.md`
- Deeper Trackblazer mechanics:
  `trackblazer-decision-safety.md`, `trackblazer-event-scoring.md`,
  `trackblazer-item-economy.md`, `trackblazer-native-decisions.md`
- Smart race solver details: `android-smart-race-solver-v530.md`,
  `smart-race-solver-settings.md`, `smart-race-solver.md`
- AI subsystem details (see ai-learning.md for the user summary):
  `style-adaptation-v542AI.md`, `clock-aware-ai-logs-v540AI.md`,
  `ai-modeling-bayesian-v543AI.md`,
  `running-style-ai-ui-v535.md`
- AI feature history: `action-reasoning-training-v529.md`,
  `ai-advisor-dataset-v532.md`, `ai-auto-training-v533.md`,
  `ai-dashboard-shadow-v536.md`, `ai-live-policy-toggle-v539AI.md`,
  `ai-log-import-v537.md`, `ai-log-preset-import-v538AI.md`,
  `ai-training-repair-v534.md`

## Archive

`archive/` contains historical implementation notes and dev-only
analyses. They reference old code paths and are not maintained.

## Changelog

The release-by-release record is in `../CHANGELOG.md` at the repo
root. Each entry includes the user-facing rationale and file impact.
