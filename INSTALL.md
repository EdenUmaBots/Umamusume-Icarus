# Pre Icarus Installation Guide

This guide explains how to install and verify Pre Icarus on Windows, Linux, and macOS.

## 1. Prerequisites

### Windows

Install:

- Python 3.10 or newer
- Node.js 18 or newer
- npm, included with Node.js
- Git, optional but useful

Recommended checks:

```powershell
python --version
node --version
npm --version
```

### Linux

Install packages using your distribution's package manager.

Ubuntu/Debian example:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip nodejs npm git
```

Check versions:

```bash
python3 --version
node --version
npm --version
```

### macOS

Install:

- Python 3.10 or newer
- Node.js 18 or newer
- npm
- Git, optional

Homebrew example:

```bash
brew install python node git
```

Check versions:

```bash
python3 --version
node --version
npm --version
```

## 2. Extract Pre Icarus

Extract the build archive, for example:

```text
Pre Icarus v4.1.zip
```

Place it in a folder you can write to, such as:

```text
C:\Pre Icarus
```

Avoid protected folders like `Program Files`.

## 3. Install Python Dependencies

From the project folder:

### Windows

```powershell
pip install -r requirements.txt
```

### Linux/macOS

```bash
python3 -m pip install -r requirements.txt
```

Optional virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Install Web Dependencies

From the project folder:

```bash
npm install
```

or:

```bash
npm i
```

This step is required for the web helper dependencies.

## 5. Configure Master Data

If you have `master.mdb`, place it in the project folder or set the path in Diagnostics.

Then generate master data from the dashboard, or run the relevant master data generator if your build supports command-line generation.

Expected generated files include:

```text
data/race_planner_core.json
data/skill_weighting_core.json
data/trainee_profiles_core.json
data/mant_shop_core.json
data/succession_core.json
```

## 6. Launch Pre Icarus

### Windows

```powershell
python main.py
```

### Linux/macOS

```bash
python3 main.py
```

The console will show the local dashboard address, usually something like:

```text
http://127.0.0.1:1616
```

Open that address in your browser.

## 7. Login and Auth Capture

1. Start Pre Icarus.
2. Open the dashboard.
3. Follow the login/auth capture instructions shown by the app.
4. Launch Umamusume.
5. Reach the game menu.
6. Wait for the dashboard to confirm account data is loaded.

## 8. Verify Successful Installation

Check these items:

- Dashboard opens.
- Account information appears.
- Diagnostics opens.
- Master Data status works.
- Race Planner opens.
- Skill recommendations load.
- TP Restore toggle is visible.
- Start Career button is available.
- Action Log and Decision Reasoning panels are visible.

## 9. Common Troubleshooting

### Web UI opens but buttons fail

Run:

```bash
npm install
```

Then restart:

```bash
python main.py
```

### Python dependency error

Run:

```bash
pip install -r requirements.txt
```

If using Linux/macOS:

```bash
python3 -m pip install -r requirements.txt
```

### Login fails

Try:

1. Restart Pre Icarus.
2. Restart the game.
3. Reach the game menu.
4. Retry auth capture.
5. Check PowerShell or terminal output.

### No race planner data

Generate master data and confirm:

```text
data/race_planner_core.json
```

exists.

### No skill recommendations

Generate master data and confirm:

```text
data/skill_weighting_core.json
```

exists.

### AI Dataset says no rows

Check that completed career logs exist and are imported into the expected dataset folder.

### Dashboard feels stuck

Open the backend terminal and look for errors. Large log folders can take time to scan if the cache is cold.

## 10. Updating Pre Icarus

Before updating:

1. Back up `settings.json`.
2. Back up custom presets.
3. Back up custom profile files.
4. Extract the new build.
5. Copy custom files back carefully.
6. Run `npm install` and `pip install -r requirements.txt` if dependencies changed.
7. Start with `python main.py`.
8. Verify Diagnostics.

## 11. Where to Get Help

Start with:

- `docs/troubleshooting.md`
- `docs/diagnostics.md`
- backend console output
- browser console output

## Pre Icarus v5.42AI Style Adaptation Notes

The AI Learning dashboard now has a **Racing Style Adaptation** card. Leave it on
**Shadow Only** at first so the model can collect race outcomes without changing
live racing style. After several completed careers, click **TRAIN NOW** to build
`style_adaptation_model.json` and the dashboard report.

`Auto Apply` stays safety-locked until enough local evidence exists. The Racing
Settings running style remains the fallback source of truth.

## Optional: Local LLM Advisor

Pre Icarus v5.43 can talk to a local OpenAI-compatible chat server. This is optional and disabled by default. The LLM is used for offline post-run analysis and shadow advice only; Pre Icarus's deterministic runner remains the final authority.

Recommended beginner setup:

1. Install LM Studio.
2. Download a chat/instruct model such as Qwen3 8B Instruct, or use Qwen3 4B on weaker PCs.
3. In LM Studio, load the model and start the local server from the Developer/Server panel.
4. Open Pre Icarus and go to AI Learning → Local LLM Advisor.
5. Set Provider to `LM Studio`.
6. Set Base URL to `http://localhost:1234/v1`.
7. Set Model to the exact model name shown by LM Studio.
8. API Key can usually be `lm-studio` or left blank if your local server accepts it.
9. Click SAVE LLM SETTINGS, then TEST LLM.
10. Start with Offline Analysis. Use Shadow Advisor only after Test LLM succeeds.

Note: after saving once, you may leave API Key blank on future saves to keep the saved key. The dashboard refresh will not overwrite Local LLM fields while you are editing them.

Ollama alternative:

1. Install Ollama.
2. Run `ollama pull qwen3:8b`.
3. Run `ollama run qwen3:8b` once so the model is ready.
4. In Pre Icarus, use Base URL `http://localhost:11434/v1`, Model `qwen3:8b`, and API Key `ollama`.

Local LLM artifacts are written under `uma_runtime/ai/` as `llm_run_summaries.jsonl`, `llm_advice.jsonl`, `latest_llm_run_summary.json`, and `latest_llm_advice.json`.


## Local LLM troubleshooting

If **TEST LLM** succeeds but **ANALYZE LAST RUN** returns `HTTP 400 Bad Request`, update to the Local LLM Analysis Fix build. The analysis request may have exceeded the context window of the loaded local model. The fixed build automatically trims the post-run prompt to a safer size and returns clearer server error details if LM Studio still rejects a request.

If `llm_run_summaries.jsonl` shows JSON stored inside `analysis.raw_text`, update to the Local LLM Parser Cleanup build. The parser now unwraps fenced JSON, nested `analysis` envelopes, double-encoded JSON, and `raw_text`-wrapped JSON into structured fields that the dashboard can display.

For LM Studio, keep the base URL as:

```text
http://localhost:1234/v1
```

Use the exact model ID shown by:

```text
http://localhost:1234/v1/models
```
