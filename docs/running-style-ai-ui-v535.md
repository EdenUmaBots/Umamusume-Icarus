# Pre Icarus v5.35 Running Style, AI Modal, and Nav Polish

This release focuses on five small but important UX/decision-safety fixes:

- Smart Race Solver now explains Strict, Balanced, and Loose distance preference modes directly in the settings modal.
- Running-style ids are centralized in `career_bot/running_style.py` so Pace Chaser is always game style `2`, Late Surger is always `3`, and both race entry and skill buying use the same resolver.
- Weighted skill buying blocks style-exclusive skills that contradict the selected Racing Settings strategy while still allowing neutral skills.
- AI Learning has its own top-level button and modal, leaving Diagnostics focused on environment/runtime tools.
- The top navigation uses a three-zone grid layout to prevent Theme, Logout, Runs, Delay, and account pills from overlapping.

The AI and skill changes are intentionally conservative: they do not bypass safety gates, and they do not create new live actions. They only make existing selections obey the user's chosen strategy more consistently.
