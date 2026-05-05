# Changelog — MagicLight Auto

## v2.0.0 — 2026-05-05  🎉 Major Release

### Architecture: 4-Tab Sheet Pipeline

- **BREAKING**: Single `Database` sheet tab replaced with 4 linked tabs:
  - `1_Stories` — input + generation output
  - `2_Videos` — FFmpeg processing queue
  - `3_Process` — YouTube metadata staging
  - `4_YouTube` — upload results
  - `Dashboard` — live summary counts
  - `Credits` — per-account credit log
- `Row_ID` column links all 4 tabs (set once in Tab 1, never changed)
- Status trigger chain: Tab1 Generated → auto-push Tab2 → Tab2 Done → auto-push Tab3

### Dual GitHub Pipelines

- **pipeline1-generation.yml** — Story generation only (Tab 1)
- **pipeline2-process-youtube.yml** — FFmpeg + YouTube (Tab 2 + 3→4)
- Pipeline 2 auto-triggers after Pipeline 1 via `workflow_run`
- No `.env` file on GitHub — all config via **Secrets + Variables**

### Config: Secrets & Variables (no .env on server)

- All GitHub Actions config moved to repo Secrets + Variables
- Separated concerns: credentials in Secrets, tuning in Variables
- `.env` only used locally (dev mode)
- See README for full Secrets/Variables table

### Sheet Improvements

- `push_to_videos_tab()` — auto-queue Tab 2 after generation
- `push_to_process_tab()` — auto-queue Tab 3 after processing
- `refresh_dashboard()` — live counts after every pipeline run
- `ensure_all_tabs()` — creates all 6 tabs in one `--setup` call

### Menu

- Mode 4 added: Full Pipeline (1 → 2 → 3 in sequence)
- Sheet summary shows all 4 tab statuses in menu header
- Profile selection for FFmpeg (720p / 1080p / 1080p HQ)

### Code Cleanup

- Removed: `gdown`, unused `LAYER_COLS`, `Credit_Acct/Total/Used/Remaining` columns
- `pipeline.py` now handles full trigger chain
- All sheet ops centralized in `sheet.py` (no direct gspread calls elsewhere)

### Critical Runtime Fixes (2026-05-05)

- **Fixed update_row() calls** - Added required `tab_name` and `schema` parameters in drive.py and video_process.py
- **Fixed OAuth redirect URI mismatch** - Using fixed port 8080 for consistent authentication
- **Updated Drive scopes** - Changed from `drive.file` to `drive` for full access
- **Resolved Service Account storage quota** - OAuth authentication support for Drive uploads
- **Fixed wait_site_loaded() call** - Using keyword argument for timeout parameter
- **All import errors resolved** - Production-ready with health check verification
- **Branch migration** - Migrated from master to main branch

---

## v2.0.1 — 2026-05-06

### Credits Sheet Restructure

- **BREAKING**: Credits sheet structure changed to append-only log
  - New columns: EMAIL, CREDITS, DATE/TIME (DD-MMM-YY hh:mm A), Duplicate, DupRowNumber, EMAIL/PASS, Status
  - Previous columns: Email, Total_Credits, Used_Credits, Remaining, Last_Checked, Log_Timestamp, Detail
- **Append-only behavior** - Credit checks now add new rows instead of updating existing records
- **Email/Password format** - Column F stores email:password format (e.g., user@example.com:password123)
- **Duplicate tracking** - Added Duplicate and DupRowNumber columns for duplicate entry detection
- **Status tracking** - Added Status column (Success/Failed) for each credit check
- **Added SCHEMA_CREDITS** to config.py for consistent column mapping
- **Updated credits.py** - Modified `check_all_accounts()` to log all accounts regardless of credit amount
- **Updated sheet.py** - Modified `credits_log_login()` and `credits_log_completion()` to append only, updated `_ensure_credits_tab()` to use new schema
- **Updated dashboard** - Changed credits calculation to sum Credits column instead of Remaining
- **Check Credits headless** - Removed prompt, now always runs in headless mode
- **Fixed double entries** - Removed duplicate credit logging from video_gen.py
- **Progress indicator** - Added Rich progress bar for credit check function
- **Output folder** - Added __OutPut/ to .gitignore

### Output Directory Change

- **Output directory renamed** - Changed from `output/` to `__OutPut/`
- **Environment variable** - Added `MAGICLIGHT_OUTPUT` env var (default: `__OutPut`)
- **File migration** - Existing output files moved to new directory
- **Old directory removed** - `output/` directory deleted after migration

---

## v1.5.0 — 2026-04-11  (previously labeled v2.0.3)

- Sheet write guaranteed after video upload
- Credit tracking per row (before/after)
- Account rotation on credit < 70
- `--migrate-schema` CLI flag
- `--check-credit` CLI flag
- Loop mode stabilized

## v1.0.0 — 2026-03-xx

- Initial single-file automation script
- MagicLight.ai login + 4-step generation
- Basic Google Sheets integration (single tab)
- FFmpeg processing with logo + endscreen
- Google Drive upload
