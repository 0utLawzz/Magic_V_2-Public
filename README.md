# MagicLight Auto v3.0 🪄

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Version](https://img.shields.io/badge/version-v3.0.0-brightgreen)

Kids story video automation pipeline — MagicLight.ai → FFmpeg → Google Drive → YouTube

---

## What It Does

| Mode | Function |
|------|----------|
| **1 — Video Making** | Reads pending rows from Google Sheet → logs into MagicLight.ai → generates video → downloads raw video + thumbnail → writes results back to sheet |
| **2 — Video Process** | Scans `output/` folder → FFmpeg: logo overlay + trim + endscreen → uploads to Drive → marks row Done in sheet |
| **3 — YouTube** | *(coming soon)* Post processed video to YouTube, write back video ID and URL |

Sheet rows link all three modes via `Row_ID`. Status flows: `Pending` → `Processing` → `Generated` → `Done`.

---

## Project Structure

```
Magic_Light_V_2/
├── main.py                  # Central entry + interactive menu
├── modules/
│   ├── config.py            # All settings from .env
│   ├── console_utils.py     # Rich logging helpers
│   ├── sheet.py             # Google Sheets read/write (all columns)
│   ├── drive.py             # Google Drive upload helpers
│   ├── browser_utils.py     # Playwright helpers, popups, sleep
│   ├── video_gen.py         # Mode 1: MagicLight steps 1-4
│   ├── video_process.py     # Mode 2: FFmpeg processing
│   ├── pipeline.py          # Generation pipeline core + account rotation
│   └── credits.py           # Account credit checker
├── assets/
│   ├── logo.png
│   └── endscreen.mp4
├── output/                  # Generated + processed videos
├── docs/
│   ├── SHEET_STRUCTURE.md
│   ├── CHANGELOG.md
│   └── TASKS.md
├── .env                     # Your config (not committed)
├── .env.example
├── accounts.txt             # email:password (not committed)
├── credentials.json         # Google Service Account (not committed)
└── requirements.txt
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/net2t/MagicLight-Auto.git
cd Magic_Light_V_2

# 2. Install
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
playwright install chromium

# 3. Configure
cp .env.example .env           # Fill in SHEET_ID, DRIVE_FOLDER_ID etc.

# 4. Run schema setup (first time only)
python main.py --migrate-schema

# 5. Run interactive menu
python main.py
```

---

## CLI Reference

```
python main.py                          # Interactive menu
python main.py --mode 1 --max 3         # Generate 3 stories
python main.py --mode 1 --loop          # Infinite generation loop
python main.py --mode combined --max 1  # Generate + process inline
python main.py --mode 2                 # Process all local videos
python main.py --mode 2 --upload        # Process + upload to Drive
python main.py --credits                # Check all account credits
python main.py --migrate-schema         # Write sheet headers (run once)
python main.py --health                 # Check system packages/assets
```

---

## Google Sheet Structure

Run `python main.py --migrate-schema` to auto-create headers.
See [docs/SHEET_STRUCTURE.md](docs/SHEET_STRUCTURE.md) for full column reference.

---

## GitHub Actions

Add these repository secrets:
- `ENV_FILE` — contents of your `.env`
- `ACCOUNTS_TXT` — contents of `accounts.txt`
- `GCP_CREDENTIALS` — contents of `credentials.json`

Then trigger the workflow from **Actions → MagicLight Pipeline → Run workflow**.
