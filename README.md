# Umamusume Icarus

Full-auto training, dailies, and scheduling for Umamusume Pretty Derby on Steam — all from one local dashboard.

## Download & run

No installation, no terminal, no build tools.

1. Download the latest **Icarus.zip** from the [Releases](https://github.com/EdenUmaBots/Umamusume-Icarus/releases) page.
2. Extract the zip anywhere you like.
3. Double-click **Icarus.exe**.

Python, Node.js, and every dependency are bundled inside the app. The control center opens in your browser automatically.

## Features

### Career automation
- **Three scenarios, one bot:** URA Finals, Make a New Track (MANT), and the team-based Unity Cup.
- **Smart training decisions** for stronger, more consistent career results.
- **Skill management** with searchable available, selected (with priority), and banned lists.
- **Run-history dashboard** summarizing your past careers with grades, fans, and stats.
- **Rides out game patches:** routine game data updates are adopted automatically so the bot keeps going. For larger updates, Icarus stays running so you can simply re-login from the dashboard, instead of the app closing on you.

### Dailies
A dedicated Dailies page clears your routine content on autopilot:
- **Team Trials** — races until your RP is spent.
- **Daily Races** — up to the daily cap.
- **Legend Races** — you pick the boss.
- **Daily Shop buyout** — spends within your gold balance.

### Scheduler
Set a day and time and Icarus kicks off on its own: it runs your dailies, then a number of career runs you choose, then goes idle or shuts down. It reuses your last setup or resumes a career already in progress.

> The scheduler triggers automation inside Icarus while the app is running. Fully unattended, hands-off sessions require your Steam credentials to be saved so the bot can log in on its own.

### Runs like a human
Designed to make activity look less robotic:
- Randomized **5–30 minute breaks** every few careers.
- Randomized **2–5 second delays** between actions.
- **Pause and Resume** on a live career without cancelling the run.

### Management & quality of life
- **All-new control center:** a sleek matte-black dashboard with a redesigned layout and a fresh loading screen, built to make long sessions easy to watch at a glance.
- **Live resource HUD** across the top bar shows TP, RP, Carrots, Gold, and Clocks.
- **Veterans manager:** review and delete stored trained characters at a glance. Locked favorites are protected, so you can't remove them by accident.
- **Live logs console:** searchable, filterable by level/module/time, with one-click export to a shareable zip — ideal for checking on a run or reporting an issue.
- **Discord webhook** sends rich run-complete embeds, with a one-click **Test Webhook** button to confirm your setup.
- **Steam Guard sign-in** via a bundled login helper works with either the mobile authenticator or email codes.
- **Self-updating** (see below).

## Requirements

- **Windows.**
- The **Umamusume (Steam)** client installed and running when you log in for the first time.
- **Internet** on first run (to fetch game data) and for updates.
- Nothing else — everything the app needs is bundled inside.

One game per device (single instance).

## Using it

1. Download **Icarus.zip** from Releases, extract it, and run **Icarus.exe**.
2. The control center opens in your browser.
3. Make sure the Umamusume Steam client is installed and running, then sign in to Steam through Icarus (mobile authenticator or email code).
4. Configure your run: pick a scenario, character, skills, and options.
5. Start a career or dailies, or set the scheduler for a hands-off session.
6. Watch progress from the dashboard, resource HUD, and logs console. Optionally hook up a Discord webhook for run-complete notifications.

## Updating

Icarus can update itself from the dashboard. When a newer release is published, it offers to download the new build, close, swap itself in, and relaunch — preserving your config, presets, and data.

## Notes

- **First-launch SmartScreen prompt:** Windows may show an "unknown publisher" warning on first run. The app is code-signed as *Icarus Network*, but not through a public certificate authority, so Windows doesn't recognize it yet. Click **More info**, then **Run anyway**.
- **Everything stays local:** the control panel is served on **localhost only**. Nothing leaves your machine.
- **Disclaimer:** automating the game is against Cygames' Terms of Service and carries account risk. Use in moderation, at your own risk. The human-like pacing features reduce, but do not eliminate, detectability.
