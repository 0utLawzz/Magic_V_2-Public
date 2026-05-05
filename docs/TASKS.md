# TASKS — MagicLight Auto v2.0

AI context file — read before making ANY changes

Updated: 2026-05-05

## Project Status
Version:    2.0.0
Sheet:      4 tabs (1_Stories / 2_Videos / 3_Process / 4_YouTube)
Row_ID:     Links all 4 tabs — set once in Tab 1, never changed
Pipelines:  2 (GitHub Actions: pipeline1-generation + pipeline2-process-youtube)
Local run:  python main.py (interactive menu)
GitHub:     All config via Secrets + Variables — NO .env on server

## File Map
```
main.py              → menu + CLI
modules/config.py    → ALL settings (env vars) — imported everywhere
modules/sheet.py     → ALL sheet ops (4 tabs + dashboard + credits)
modules/pipeline.py  → trigger chain Tab1→Tab2→Tab3→Tab4
modules/video_gen.py → MagicLight steps 1-4 (DO NOT touch logic)
modules/video_process.py → FFmpeg pipeline
modules/browser_utils.py → Playwright, popup dismissal
modules/drive.py     → Drive upload
modules/credits.py   → credit checker
modules/youtube.py   → YouTube upload (TODO)
```

## Status Flow
```
Tab 1:  Pending → Processing → Generated → Error / No_Video / Low_Credit
Tab 2:  Pending → Processing → Done → Error
Tab 3:  Pending → Ready → Uploading → Uploaded → Error
Tab 4:  Uploaded / Failed
```

## Trigger Chain
```
Tab1 Generated  → push_to_videos_tab()   → Tab2 row (Pending)
Tab2 Done       → push_to_process_tab()  → Tab3 row (Pending)
Tab3 Uploaded   → push_to_youtube_tab()  → Tab4 row (Uploaded)
```

---

## COMPLETED ✅

- [x] 4-tab sheet architecture
- [x] Row_ID linking all tabs
- [x] Trigger chain: Tab1→2→3 (youtube tab4 pending)
- [x] Dual GitHub pipelines
- [x] Pipeline 2 auto-triggers after Pipeline 1 (workflow_run)
- [x] All config via GitHub Secrets + Variables
- [x] Dashboard tab (refresh after every run)
- [x] Credits tab (per-account logging)
- [x] ensure_all_tabs() — creates all 6 tabs in one call
- [x] main.py: 4-mode menu (1/2/3/Full)
- [x] Mode 4: full pipeline in sequence
- [x] README with Secrets/Variables table
- [x] CHANGELOG updated

### Critical Runtime Fixes (2026-05-05)
- [x] Fixed update_row() calls - added required tab_name and schema parameters
- [x] Fixed wait_site_loaded() call to use keyword argument
- [x] Fixed OAuth redirect URI mismatch - using fixed port 8080
- [x] Updated Drive scopes from drive.file to drive for full access
- [x] Resolved Service Account storage quota issues
- [x] All critical import errors resolved
- [x] Health check and setup commands verified working
- [x] Production-ready for v2.0.0 release

### Infrastructure Updates
- [x] Migrated from master to main branch
- [x] OAuth authentication support for Drive uploads
- [x] Service Account and OAuth dual authentication support

### Credits Sheet Restructure (2026-05-06)
- [x] Updated credits sheet structure to: EMAIL, CREDITS, DATE/TIME (DD-MMM-YY hh:mm A), Col4 (empty), Col5 (empty), EMAIL/PASS
- [x] Removed unnecessary columns (Found, RowNum, Status)
- [x] Modified credits.py to append new entries instead of updating existing records
- [x] Removed automatic deletion of rows with credits < 60 - now logs all accounts
- [x] Updated EmailPass column to email:password format in Column F
- [x] Updated all sheet functions to use new SCHEMA_CREDITS structure
- [x] Removed headless prompt for Check Credits - always runs headless
- [x] Fixed double entries by removing duplicate credit logging from video_gen.py
- [x] Marked stable files (video_gen.py, browser_utils.py) with DO NOT MODIFY comment
- [x] Updated output directory to __OutPut (from output) via MAGICLIGHT_OUTPUT env var
- [x] Moved existing output files to __OutPut directory
- [x] Fixed sheet formatting - credit values now passed as numbers not strings
- [x] Enhanced terminal display with dividers and creative messages for menu and credit check
- [x] Implemented progress indicator for credit check (approved improvement)

---

## IMPROVEMENT SUGGESTIONS 💡

**Submitted by:** Cascade (SWE-1.6 AI Assistant)
**Date:** 2026-05-06
**Related Task:** Credits Sheet Restructure & Credit Check Enhancement

### Credit Check Function Improvements

1. **Progress Indicator** `✅ Approved`
   - Add a progress bar or percentage indicator during credit check
   - Current: Shows "Account 1/4" but could be more visual
   - Benefit: Better user experience for large account lists

2. **Summary Table at End**
   - Display a summary table after credit check completes
   - Show: Email | Credits | Status (Success/Failed)
   - Benefit: Quick overview of all accounts checked

3. **Retry Logic for Failed Accounts**
   - Add automatic retry (1-2 attempts) for failed account checks
   - Current: Failed accounts are skipped immediately
   - Benefit: Handles transient network issues better

4. **Dry-Run Mode**
   - Add `--dry-run` flag to check credits without logging to sheet
   - Benefit: Useful for testing account credentials before actual run

5. **Credit Threshold Warning**
   - Add configurable warning threshold (e.g., warn if credits < 100)
   - Current: Only logs the value, no warning
   - Benefit: Proactive alert before running out of credits

6. **Parallel Account Checking**
   - Check multiple accounts in parallel (with configurable concurrency)
   - Current: Sequential checking (one by one)
   - Benefit: Faster for large account lists

**Note:** These are optional improvements. Please review and approve if you'd like any implemented.

---

## IN PROGRESS 🔄

### modules/youtube.py — Mode 3
- [ ] Create modules/youtube.py
- [ ] YouTube Data API v3 OAuth setup
  - Client secrets → yt_client_secrets.json
  - Token → yt_token.json (GitHub Secret: YT_TOKEN)
- [ ] upload_video(row: dict) → {"video_id": str, "url": str}
  - Read: YT_Title, YT_Description, YT_Tags, YT_Privacy, YT_Category
  - Read: Drive_Processed or local file path
  - Set: Scheduled_Time if present
- [ ] Write back: Tab 4 row via push_to_youtube_tab()
- [ ] Update Tab 3 Status = "Uploaded"
- NOTE: Separate OAuth from GCP service account

---

## PENDING / BACKLOG 📋

### Sheet
- [ ] Tab 3: Allow manual edit of YT_Title/Description before upload
- [ ] Tab 1: Add "Retry" status to re-queue failed rows
- [ ] Row_ID: Switch from timestamp to auto-increment (optional)

### Mode 2 Improvements  
- [ ] Read profile from Tab 2 `Profile` column (currently menu-only)
- [ ] Thumbnail extraction from processed video if original missing

### Mode 1 Improvements
- [ ] Style selector (Pixar / Disney / etc.) from sheet column
- [ ] Multi-account parallel generation (multiple contexts)

### General
- [ ] Log file output (save console to logs/YYYY-MM-DD.log)
- [ ] Retry count column in Tab 1
- [ ] Unit tests for sheet.py

---

## RULES FOR AI ASSISTANTS

1. NEVER modify step1/step2/step3/step4 logic in video_gen.py — very fragile
2. All settings must come from modules/config.py — never os.getenv() elsewhere
3. Sheet column indices are in SCHEMA_* dicts in config.py — add cols there first
4. Row_ID is set via lock_row() ONCE — never overwrite
5. Status flow must be respected: Pending → Processing → Done/Error
6. Drive uploads: always check UPLOAD_TO_DRIVE / DRIVE_FOLDER_ID first
7. Console output: always use modules.console_utils (ok/warn/err/info)
8. New modules: add to modules/__init__.py import too
9. GitHub Actions: config = Secrets + Variables ONLY. Never .env file.
10. Test locally before pushing to GitHub Actions
11. After every session: update docs/TASKS.md
