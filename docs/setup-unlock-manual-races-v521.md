# Setup Unlock and Manual Race Priority v5.21

Pre Icarus v5.21 fixes two lifecycle/race-planning bugs found after completed Trackblazer careers.

## Setup unlock after career finish

The runner can finish a career while the dashboard account cache still says a career is active. That stale cache keeps setup controls locked, including Friend Supports, even though the cockpit says `No active career`.

v5.21 clears the local dashboard career state when a runner snapshot is finished, not running, and has no last error. It also clears the server-side UI selection when the Stop button is pressed after a finished run.

Loop mode keeps the visible setup instead of clearing it between looped careers.

## Manual race priority

Manual Selection now wins over the Smart Race Solver when starting a run.

Before a fresh run starts, if Manual Selection mode has staged races, Pre Icarus automatically saves those races and sends them with the start request as `manual_race_ids` with `race_planner_mode = manual`.

The runtime preset marks the race list as manual, and `RacePlanner.choose()` respects manual due races before Force Racing. Irregular Training also will not hijack a manual race list.

This preserves existing Smart Race Solver behavior in smart mode, while making hand-picked races authoritative in manual mode.
