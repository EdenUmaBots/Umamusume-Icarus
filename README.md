# Icarus 3.0

> The most advanced automation and career optimization engine for Umamusume: Pretty Derby.

![Version](https://img.shields.io/badge/version-v3.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.12+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

# About

Icarus is a next-generation automation platform for **Umamusume: Pretty Derby**, designed to maximize career performance through intelligent decision making rather than simple scripted automation.

Unlike traditional bots, Icarus evaluates an entire career as one optimization problem, dynamically balancing:

- Training
- Racing
- Energy
- Shop economy
- Event outcomes
- Skill acquisition
- Set bonuses (Epithets)
- Long-term career planning

The result is significantly higher consistency, improved stat growth, smarter race scheduling, and reduced manual configuration.

---

# Highlights

## Trackblazer Engine

The flagship decision engine.

Instead of evaluating one turn at a time, Trackblazer plans the entire career from start to finish.

Features include:

- Whole-career race optimization
- Dynamic route replanning
- Smart training decisions
- Intelligent energy management
- Risk-aware racing
- Scenario-aware optimization

---

## Smart Race Solver

The race planner now:

- Pursues achievable Set Bonuses (Epithets)
- Optimizes fan gain
- Maximizes stat rewards
- Avoids unnecessary races
- Automatically replans after losses
- Supports exact optimization with heuristic fallback

---

## Intelligent Shop AI

Purchases are no longer static.

Icarus automatically evaluates:

- Current economy
- Priority stats
- Upcoming races
- Finale preparation
- Energy requirements

Items are purchased only when they provide meaningful value.

---

## Event Intelligence

Icarus includes one of the largest event databases available.

Features:

- 3,600+ event outcomes
- Intelligent fallback scoring
- Stat-cap awareness
- Context-aware energy valuation
- Improved event matching

---

## Dashboard

Live dashboard includes:

- Career statistics
- Decision reasoning
- Race schedule
- Item usage
- Shop purchases
- Skill planning
- Real-time diagnostics

---

# Features

- Intelligent career optimization
- Trackblazer Solver
- Smart Race Solver
- Dynamic route replanning
- Adaptive training logic
- Intelligent shop purchasing
- Event database integration
- Skill optimization
- Character profiles
- Recommended stat builds
- Race intelligence
- Career analytics
- Detailed decision explanations
- Modern web dashboard

---

# Installation

Clone the repository:

```bash
git clone https://github.com/EdenUmaBots/Umamusume-Icarus.git
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python main.py
```

---

# Requirements

- Python 3.12+
- Android Emulator / Physical Android Device
- ADB
- Windows 10 / 11

---

# Releases

Current Release:

**Icarus 3.0**

See the Releases page for previous versions and release notes.

---

# Roadmap

Planned improvements include:

- Better AI planning
- Additional scenario support
- Improved race prediction
- Expanded event database
- Enhanced dashboard
- Improved character modeling
- More optimization tools

---

# Disclaimer

This project is intended for educational and research purposes.

Use at your own discretion.

---

# Credits

Special thanks to everyone who contributed feedback, testing, and data collection.

---

# License

MIT License

-------------

## Join our discord: https://discord.gg/wpbd3hTBDc

-------------

# ! Written installation guide, video below.

You will need the latest version of python and C++ Build Tools:

https://www.python.org/downloads/

https://visualstudio.microsoft.com/visual-cpp-build-tools/

For C++ Tools, this is what you need, just check that box. <img width="1221" height="625" alt="image" src="https://github.com/user-attachments/assets/28610cb3-650d-43c9-bf09-4505a62272de" />

# First time instalation:

Step 1: Download bot directly from this repo, unzip file

Step 2: Open the bot folder (usually second one) in cmd like this, please note, this is an example link, yours will be different.

```cmd
cd C:\Users\yourusernamehere\Downloads\Umamusume-API-Bot-main\Umamusume-API-Bot-main
```
Step 3: Paste the following lines in order. 

```cmd
winget install -e --id OpenJS.NodeJS
```
Accept terms, then:

```cmd
npm i
```
Disregard the error you might have here, then:

```cmd
pip install -r requirements.txt 
```
Once the above it done, paste or type:

```cmd
python main.py
```

The bot will launch steam and umamusume then promptly close the game shortly before fully loading in, you will be given a web address, please paste this into your browser, you will be promted to log into your steam account, (it is recommended to use an alt). Web UI will request a steamguard code, once provided, you're in! Everything from here should be self explanitory. 

# Video Guide: https://www.youtube.com/watch?v=SkBItJYJMeE

# Regular use:


```cmd
cd C:\Users\yourusernamehere\Downloads\Umamusume-API-Bot-main\Umamusume-API-Bot-main
```

```cmd
python main.py
```


# Running multiple bots!

Ensure you have multiple seperate folders and keep track. Each bot must have it's own port number, this is located in main.py, line 186, change it to something else, default is 1200, so second bot could be 1201. Each bot needs its own steam account.

Launch first bot until you're in web UI, switch steam accounts, repeat the process. Turn on each bot simoultaneously. First bot acts as an anchor, if this crashes, all bots will crash. We found that we were able to comfortably run 3 accounts at the same time, could try more.

Daily reset will cause the bots to crash, you must set everything up manually then. 

# Future updates.

We will be working towards updating the bot as we see fit and will be porting it over to new scenarios, if you would like to contribute, get in touch with us though discord. Clank responsibly and thank you all. 













