# MagicLight Auto v2.0 🤖🚀

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Version](https://img.shields.io/badge/version-v2.0.0-brightgreen)

Kids story video automation pipeline — MagicLight.ai → FFmpeg → Google Drive → YouTube

---

## How It Works

```
Google Sheet (4 Tabs)
─────────────────────────────────────────────────────────────────
Tab 1: Stories   →  Tab 2: Videos   →  Tab 3: Process  →  Tab 4: YouTube
  (input+gen)         (FFmpeg)          (YT metadata)       (results)
      │                   │                  │                   │
 [Row_ID links all tabs — trigger chain: complete one → auto-queue next]
```

| Tab | Name | Purpose |
|-----|------|---------|
| **1_Stories** | Story Input | Input stories + generation output (raw video, Drive link) |
| **2_Videos** | Video Queue | FFmpeg processing queue + processed video Drive link |
| **3_Process** | YT Staging | YouTube metadata (title, description, tags, privacy) |
| **4_YouTube** | YT Results | Video ID, URL, publish time, stats |
| Dashboard | Summary | Live counts: generated / processed / on YouTube / credits |
| **Credits** | Accounts | Per-account credit tracking (append-only log with duplicate detection) |

---

## Quick Start (Local)

### 1. Clone

```
git clone https://github.com/0utLawzz/Magic_V_2-Public.git
cd Magic_Light_V_2
```

### 2. Setup venv

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Fill in .env (local only)

```
cp .env.example .env
# Add SHEET_ID, DRIVE_FOLDER_ID etc.
```

### 4. Initialize Sheet tabs (run once)

```
python main.py --setup
```

### 5. Run

```
python main.py
```

### Credit Check with Parallel Processing

```
# Sequential (default)
python main.py --credits

# Parallel (recommended for GitHub Actions)
python main.py --credits --concurrency 2

# Parallel with dry-run
python main.py --credits --concurrency 3 --dry-run
```

---

## GitHub Actions Setup

No `.env` needed on GitHub. Use **Secrets + Variables** only.

### Repository Secrets (Settings → Secrets → Actions)

| Secret | Value |
|--------|-------|
| `SHEET_ID` | Your Google Sheet ID |
| `DRIVE_FOLDER_ID` | Google Drive folder ID |
| `GCP_CREDENTIALS` | Full contents of `credentials.json` |
| `ACCOUNTS_TXT` | Full contents of `accounts.txt` (email:password per line) |
| `ML_EMAIL` | Fallback MagicLight email |
| `ML_PASSWORD` | Fallback MagicLight password |
| `YOUTUBE_TOKEN` | YouTube OAuth token JSON (for Mode 3) |
| `YT_CLIENT_SECRETS` | YouTube client secrets JSON |

### Repository Variables (Settings → Variables → Actions)

| Variable | Default | Description |
|----------|---------|-------------|
| `STEP1_WAIT` | 60 | Seconds to wait after story input |
| `STEP2_WAIT` | 30 | Seconds for character generation |
| `STEP3_WAIT` | 180 | Seconds for storyboard |
| `RENDER_TIMEOUT` | 1200 | Max render wait (seconds) |
| `TRIM_SECONDS` | 4 | Trim from end of video |
| `LOGO_X` | 7 | Logo X position |
| `LOGO_Y` | 5 | Logo Y position |
| `LOGO_WIDTH` | 300 | Logo width (px) |
| `LOGO_OPACITY` | 1.0 | Logo opacity (0.0–1.0) |
| `ENDSCREEN_ENABLED` | true | Enable endscreen append |
| `UPLOAD_TO_DRIVE` | false | Auto-upload to Drive |

### Two Pipelines

**Pipeline 1** (`pipeline1-generation.yml`)

- Trigger: Manual or scheduled (every 4h)
- Reads Tab 1 pending stories → generates → downloads → queues Tab 2
- Inputs: quantity, upload_drive, loop

**Pipeline 2** (`pipeline2-process-youtube.yml`)

- Trigger: Manual OR auto after Pipeline 1 completes
- Modes: `process` / `youtube` / `both`
- Reads Tab 2 → FFmpeg → queues Tab 3
- Reads Tab 3 → YouTube → writes Tab 4

---

## CLI Reference

```bash
python main.py                    # Interactive menu
python main.py --mode 1 --max 3   # Generate 3 stories
python main.py --mode 2 --upload  # Process all pending + upload
python main.py --mode 3           # Upload pending to YouTube
python main.py --mode full --max 1  # Full pipeline (1→2→3)
python main.py --setup            # Create sheet tabs
python main.py --credits          # Check all account credits
python main.py --health           # System health check
```

---

## Project Structure

```
Magic_Light_V_2/
├── main.py                  ← Entry point + menu
├── modules/
│   ├── config.py            ← All settings (env vars / secrets)
│   ├── console_utils.py     ← Rich logging helpers
│   ├── sheet.py             ← All 4-tab sheet operations
│   ├── drive.py             ← Google Drive upload
│   ├── browser_utils.py     ← Playwright helpers
│   ├── video_gen.py         ← Mode 1: MagicLight steps
│   ├── video_process.py     ← Mode 2: FFmpeg
│   ├── pipeline.py          ← Trigger chain: Tab1→2→3→4
│   ├── credits.py           ← Credit checker
│   └── youtube.py           ← Mode 3: YouTube (coming soon)
├── assets/
│   ├── logo.png
│   └── endscreen.mp4
├── docs/
│   ├── SHEET_STRUCTURE.md
│   ├── CHANGELOG.md
│   └── TASKS.md
├── .github/workflows/
│   ├── pipeline1-generation.yml
│   └── pipeline2-process-youtube.yml
├── .env.example             ← Local dev only
├── .gitignore
└── requirements.txt
```

---

## Sheet Flow (Row_ID trigger chain)

```
1_Stories:  Status=Pending
    ↓ [Pipeline 1 runs]
1_Stories:  Status=Generated, Drive_Raw=..., Row_ID=R5-1234567
    ↓ [auto-pushed to Tab 2]
2_Videos:   Status=Pending, Row_ID=R5-1234567
    ↓ [Pipeline 2: process mode runs]
2_Videos:   Status=Done, Drive_Processed=...
    ↓ [auto-pushed to Tab 3]
3_Process:  Status=Ready, YT_Title=..., YT_Tags=...
    ↓ [Pipeline 2: youtube mode runs]
4_YouTube:  Status=Uploaded, YT_Video_ID=..., YT_URL=...
```
