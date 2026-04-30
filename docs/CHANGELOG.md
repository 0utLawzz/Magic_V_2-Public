# Changelog — MagicLight Auto

## v2.0.0 — 2026-05-01  🎉 Major Release

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
