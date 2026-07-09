# Icarus 4.0.0

Icarus 4.0.0 is the biggest release yet, and it starts the moment you download it: the whole app is now a single compiled download with zero install. Grab Icarus.zip, extract it, double-click Icarus.exe, and the dashboard opens itself in your browser. On top of that, this release brings a full visual overhaul, automated dailies, a scheduler, a new scenario, self-updating, and a long list of stability fixes.

## Headline Features

**One Download. Zero Install.**
Icarus now ships as a single compiled app: grab Icarus.zip, extract it, and double-click Icarus.exe. Python, Node.js, and every dependency are bundled inside, so there is nothing to set up, no terminal, and no build tools. The dashboard opens in your browser on its own.

**All-New Control Center**
A complete visual overhaul: a sleek matte-black dashboard with a redesigned layout and a brand-new loading screen, built to make long automated sessions easy to watch at a glance.

**Dailies on Autopilot**
A dedicated Dailies page clears Team Trials (races until your RP is spent), Daily Races (up to the daily cap), and Legend Races (you pick the boss), plus a Daily Shop buyout that spends within your gold balance.

**Set-and-Forget Scheduler**
Pick a day and time and Icarus starts on its own: it runs your dailies, then a chosen number of career runs, then goes idle or shuts down. It reuses your last setup or resumes a career already in progress.

**Unity Cup Scenario**
Icarus now plays the team-based Unity Cup, joining URA Finals and Make a New Track (MANT). Three full scenarios, one bot.

**Veterans Manager**
A new Veterans page lets you review and delete your stored trained characters at a glance. Locked favorites are protected, so you can't remove them by accident.

**Runs Like a Human**
Randomized 5–30 minute breaks every few careers, 2–5 second randomized delays between actions, and Pause/Resume on a live career, all to make activity look less robotic.

**Updates Itself**
Icarus can update itself from the dashboard: when a newer release is available, it downloads the new build, closes, swaps itself in, and relaunches. Your config, presets, and data are preserved.

**Rides Out Game Patches**
Routine game data updates are adopted automatically so the bot keeps going. For larger updates, Icarus stays running so you can simply re-login from the dashboard, instead of the app shutting itself down.

**Live Logs Console**
A searchable log console you can filter by level, module, and time, with one-click export to a shareable zip. Ideal for checking on a run or reporting an issue.

## Improvements

- Live resource HUD across the top bar shows TP, RP, Carrots, Gold, and Clocks at a glance.
- Run-history dashboard summarizes your past careers with grades, fans, and stats.
- Skill management with searchable available, selected (with priority), and banned lists.
- Discord webhook now sends rich run-complete embeds, with a one-click Test Webhook button to confirm your setup before you rely on it.
- Steam Guard sign-in via a bundled login helper works with either the mobile authenticator or email codes.
- One game per device (single-instance) for a clean, predictable public build.

## Fixes & Reliability

- Major stability overhaul: careers, dailies, and the scheduler can now run back-to-back without interfering with each other, making long, unattended sessions far more reliable.
- Stopping a run is now clean and safe: a single Stop no longer leaves the bot needing a full restart.
- Pause and Resume are reliable and won't cancel your run by accident.
- Smarter event handling resolves cases where the bot could get stuck repeating the same turn.
- Improved training decisions for stronger, more consistent career results.
- More reliable Steam login, including a fixed Steam Guard sign-in issue (mobile authenticator or email).
- The scheduler now resumes an active career instead of skipping it when there's no saved run setup.
- After a game update, Icarus stays running so you can simply re-login from the panel instead of the app shutting itself down.

## Notes

- Windows only. The Umamusume (Steam) client must be installed and running when you log in for the first time, and an internet connection is needed on first run (to fetch game data) and for updates.
- On first launch, Windows SmartScreen may show an "unknown publisher" prompt. The app is code-signed as "Icarus Network," just not by a public certificate authority, so click "More info" and then "Run anyway."
- The control panel is served on localhost only; nothing leaves your machine.
- Automating the game is against Cygames' Terms of Service and carries account risk. Use in moderation, at your own risk. The human-like pacing features reduce but do not eliminate detectability.
