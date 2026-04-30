# Changelog — MagicLight Auto

## v3.0.0 (2026-04-30)
### Breaking Changes
- Complete project restructure: monolithic `main.py` → modular `modules/` package
- Sheet schema updated: Row_ID (col A), YouTube columns (P-S), Process_Drive (O)
- `main.py` is now only the menu/CLI entry point

### New
- `modules/config.py` — centralized config from .env
- `modules/sheet.py` — all sheet read/write in one place; `lock_row()` for Row_ID stamping
- `modules/drive.py` — Drive upload helpers separated
- `modules/browser_utils.py` — popup dismissal, sleep, DOM helpers
- `modules/video_gen.py` — Mode 1 steps (login, step1-4, download)
- `modules/video_process.py` — Mode 2 FFmpeg pipeline with quality profiles
- `modules/pipeline.py` — core generation runner with account rotation
- `modules/credits.py` — standalone credit checker
- `modules/console_utils.py` — Rich logging helpers shared across modules
- Interactive menu: Modes 1/2/3 + Setup + Credits + Health Check
- Mode 2 now shows video list with size before processing
- Mode 2 supports quality profile selection (720p / 1080p / 1080p HQ)
- `Row_ID` column links Mode1 → Mode2 → Mode3 sheets
- `docs/TASKS.md` — AI-readable task list for ongoing work
- `docs/CHANGELOG.md` — this file

### Removed
- Redundant functions: `debug_buttons`, `dom_click_class`, `cleanup_local_files_if_drive_only`
- `application_detail.html` (unused)
- `SHEET_SCHEMA` LAYER_COLS (overcomplicated)
- Global `args` variable (now passed through cleanly)
- Duplicate credit update paths

### Fixed
- Sheet write now checks actual headers before writing (no silent failures)
- Account rotation works correctly across context lifecycle
- Combined mode guard: inline processing only in combined mode

---

## v2.0.3 (2026-04-11)
- Sheet write guaranteed after video upload
- Upload-to-Drive: video uploaded, Drive_Link written immediately
- Credit tracking: before/after per row
- Account rotation on low credit (<70)
- `--migrate-schema` CLI flag
- `--check-credit` CLI flag

## v2.0.0 (2026-03-xx)
- Combined / generate / process modes
- FFmpeg processing with logo, endscreen, trim
- Google Drive upload with folder-per-story
- Rich progress bars for FFmpeg encoding

## v1.0.0
- Initial single-file automation script
- MagicLight.ai login + story generation
- Basic Google Sheets integration
