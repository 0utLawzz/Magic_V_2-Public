# TASKS — MagicLight Auto v3.0
# AI Context File — Read this before making any changes
# Last updated: 2026-04-30

## Project Status
Version: 3.0.0
Structure: Modular (modules/ package)
Local run: Working
GitHub Actions: Pending test

---

## COMPLETED ✅

### v3.0 Restructure
- [x] Broke monolithic main.py into modules/
- [x] modules/config.py — centralized .env loading
- [x] modules/sheet.py — all sheet ops, Row_ID lock
- [x] modules/drive.py — Drive upload helpers
- [x] modules/browser_utils.py — Playwright, popups, sleep
- [x] modules/video_gen.py — Mode 1: login + steps 1-4
- [x] modules/video_process.py — Mode 2: FFmpeg pipeline
- [x] modules/pipeline.py — core runner + account rotation
- [x] modules/credits.py — credit checker
- [x] main.py — clean 3-mode menu + CLI
- [x] Sheet schema expanded to 23 cols (Row_ID + YouTube cols)
- [x] docs/SHEET_STRUCTURE.md updated
- [x] docs/CHANGELOG.md created
- [x] README.md updated
- [x] .env.example updated
- [x] .gitignore created
- [x] requirements.txt updated

---

## IN PROGRESS 🔄

### Mode 3 — YouTube Upload
- [ ] Create modules/youtube.py
- [ ] OAuth flow for YouTube Data API v3
- [ ] Upload processed video (from Process_Drive or local)
- [ ] Write back YT_Video_ID, YT_URL, YT_Published to sheet
- [ ] Status: Pending → Uploaded / Failed
- [ ] Trigger condition: Status == "Done" AND Process_Drive is set
- NOTE: YouTube API requires OAuth (not service account). Use separate token file.

### Sheet Improvements
- [ ] Add "Generated" status filter for Mode 2 (pick only Generated rows)
- [ ] Add "Done" status filter for Mode 3 (pick only Done rows)
- [ ] Row_ID auto-increment on first write (currently timestamp-based)

---

## PENDING / BACKLOG 📋

### GitHub Actions
- [ ] Test .github/workflows/pipeline.yml with new structure
- [ ] Verify secrets (ENV_FILE, ACCOUNTS_TXT, GCP_CREDENTIALS) work
- [ ] Add workflow for Mode 2 (process only)

### Mode 2 Improvements
- [ ] After processing, auto-update sheet Status to "Done"
- [ ] Allow picking specific row numbers to process (not just all)
- [ ] Add thumbnail extraction from processed video

### Mode 1 Improvements
- [ ] Multiple style options (not hardcoded Pixar/Sophia/Silica)
- [ ] Retry count per row (currently 1 retry only)
- [ ] Parallel processing (multiple browser contexts)

### General
- [ ] Add --profile CLI flag for FFmpeg quality profile
- [ ] Unit tests for sheet.py, config.py
- [ ] Log file output (save console output to logs/)

---

## FILE MAP (for AI reference)

```
main.py
  └── interactive_menu() / CLI
      ├── Mode 1 → modules/pipeline.py → run_pipeline()
      │              └── modules/video_gen.py (login, step1-4)
      ├── Mode 2 → modules/video_process.py → process_all()
      ├── Mode 3 → modules/youtube.py (TODO)
      ├── Setup  → modules/sheet.py → ensure_schema()
      └── Credits→ modules/credits.py → check_all_accounts()

modules/config.py       ← imported by ALL modules (no circular deps)
modules/console_utils.py← imported by ALL modules
modules/sheet.py        ← imported by pipeline, video_gen, video_process, drive
modules/drive.py        ← imported by pipeline, video_gen
modules/browser_utils.py← imported by video_gen, pipeline, credits
```

---

## RULES FOR AI ASSISTANTS

1. NEVER change logic in video_gen.py steps (step1-4) — they were hard to build
2. Always import from modules.config — never hardcode env vars
3. Sheet columns are in SHEET_SCHEMA in config.py — add new cols there first
4. Row_ID is set once via lock_row() — never overwrite it
5. Status flow: Pending → Processing → Generated → Done (never skip)
6. Drive upload is optional — always check UPLOAD_TO_DRIVE / DRIVE_FOLDER_ID before uploading
7. All console output via modules.console_utils (ok/warn/err/info) — no raw print()
8. When adding a new module: add import to modules/__init__.py too
9. Test locally before pushing to GitHub Actions
10. Keep docs/TASKS.md updated after every session
