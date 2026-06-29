# Pre Icarus v5.28 Preset, History, and Control Polish

This build keeps skill configuration untouched while improving preset/team selection persistence and the run controls.

## Preset team selection

Settings presets may now carry a compact `selection` object with the selected deck, friend support, trainee, own parents, and one guest parent. The frontend restores that selection when switching presets, reusing live dashboard data when possible and keeping guest/rental IDs available for start validation.

## Career History Major Wins

Completed career history rows now deep-copy runner data and store `major_wins`/`major_win_summary` at completion time. This prevents later runs from making older history rows display the newest run's major wins.

## Run controls

The visible Sync button has been removed. Pause/Resume occupies the former third action slot beside Run Career and Stop. Buttons are compacted so the Action Log and Decision Reasoning panes can stretch further.

## Skill systems intentionally unchanged

Configure Skills, skill config storage, and weighted skill purchase behavior are not modified in this build.
