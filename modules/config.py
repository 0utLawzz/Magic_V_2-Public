"""
config.py — All settings via GitHub Secrets / env vars
NO hardcoded values. NO .env dependency at runtime.
.env is only for LOCAL development.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env ONLY if running locally (not GitHub Actions)
if not os.getenv("GITHUB_ACTIONS"):
    _env = Path(__file__).resolve().parent.parent / ".env"
    if _env.exists():
        load_dotenv(dotenv_path=_env, override=False)

# ── Google Sheets ──────────────────────────────────────────────────────────────
SHEET_ID     = os.getenv("SHEET_ID", "")
CREDS_JSON   = os.getenv("CREDS_JSON", "credentials.json")

# Sheet tab names
TAB_STORIES   = os.getenv("TAB_STORIES",   "1_Stories")
TAB_VIDEOS    = os.getenv("TAB_VIDEOS",    "2_Videos")
TAB_PROCESS   = os.getenv("TAB_PROCESS",   "3_Process")
TAB_YOUTUBE   = os.getenv("TAB_YOUTUBE",   "4_YouTube")
TAB_DASHBOARD = os.getenv("TAB_DASHBOARD", "Dashboard")
TAB_CREDITS   = os.getenv("TAB_CREDITS",   "Credits")

# ── Google Drive ───────────────────────────────────────────────────────────────
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")

# ── MagicLight Credentials (fallback if accounts.txt empty) ───────────────────
EMAIL    = os.getenv("ML_EMAIL",    os.getenv("EMAIL",    ""))
PASSWORD = os.getenv("ML_PASSWORD", os.getenv("PASSWORD", ""))

# ── Timing ─────────────────────────────────────────────────────────────────────
STEP1_WAIT     = int(os.getenv("STEP1_WAIT",             "60"))
STEP2_WAIT     = int(os.getenv("STEP2_WAIT",             "30"))
STEP3_WAIT     = int(os.getenv("STEP3_WAIT",            "180"))
RENDER_TIMEOUT = int(os.getenv("STEP4_RENDER_TIMEOUT", "1200"))
POLL_INTERVAL  = 10
RELOAD_INTERVAL = 120

# ── Output paths ───────────────────────────────────────────────────────────────
OUT_BASE  = os.getenv("MAGICLIGHT_OUTPUT", "__OutPut")
OUT_SHOTS = os.path.join(OUT_BASE, "screenshots")

LOGO_PATH       = Path(os.getenv("LOGO_PATH",       "assets/logo.png"))
ENDSCREEN_VIDEO = Path(os.getenv("ENDSCREEN_VIDEO", "assets/endscreen.mp4"))

# ── FFmpeg ─────────────────────────────────────────────────────────────────────
TRIM_SECONDS      = int(os.getenv("TRIM_SECONDS",   "4"))
LOGO_X            = int(os.getenv("LOGO_X",          "7"))
LOGO_Y            = int(os.getenv("LOGO_Y",          "5"))
LOGO_WIDTH        = int(os.getenv("LOGO_WIDTH",     "300"))
LOGO_OPACITY      = float(os.getenv("LOGO_OPACITY", "1.0"))
ENDSCREEN_ENABLED = os.getenv("ENDSCREEN_ENABLED",  "true").lower() == "true"

# ── Feature flags ──────────────────────────────────────────────────────────────
UPLOAD_TO_DRIVE = os.getenv("UPLOAD_TO_DRIVE", "false").lower() == "true"
DEBUG           = os.getenv("DEBUG", "0") == "1"

VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv'}

# ─────────────────────────────────────────────────────────────────────────────
# SHEET SCHEMAS  (col index = 1-based, matching header row)
# Each tab has its own schema. Row_ID links all 4 tabs.
# ─────────────────────────────────────────────────────────────────────────────

# TAB 1 — Stories (input + generation output)
SCHEMA_STORIES: dict[str, int] = {
    "Row_ID":          1,   # A  — unique key, set once, never changed
    "Status":          2,   # B  — Pending/Processing/Generated/Error/Low_Credit
    "Theme":           3,   # C
    "Title":           4,   # D
    "Story":           5,   # E  ← REQUIRED
    "Moral":           6,   # F
    # Generation outputs
    "Gen_Title":       7,   # G
    "Gen_Summary":     8,   # H
    "Gen_Tags":        9,   # I
    "Project_URL":    10,   # J
    "Drive_Raw":      11,   # K  — raw (unprocessed) video Drive link
    "Drive_Thumb":    12,   # L  — thumbnail Drive link
    # Tracking
    "Email_Used":     13,   # M
    "Credit_Before":  14,   # N
    "Credit_After":   15,   # O
    "Created_Time":   16,   # P
    "Completed_Time": 17,   # Q
    "Notes":          18,   # R
}

# TAB 2 — Videos (processing queue + output)
SCHEMA_VIDEOS: dict[str, int] = {
    "Row_ID":          1,   # A  — links to Stories tab
    "Status":          2,   # B  — Pending/Processing/Done/Error
    "Title":           3,   # C  — copied from Stories
    "Drive_Raw":       4,   # D  — raw video link (from Stories)
    "Local_Path":      5,   # E  — local file path of raw video
    "Profile":         6,   # F  — encode profile: 720p/1080p/1080p_hq
    # Outputs
    "Drive_Processed": 7,   # G  — processed video Drive link
    "Drive_Thumb":     8,   # H  — thumbnail (re-extracted or original)
    "Process_Time":    9,   # I
    "Completed_Time": 10,   # J
    "Notes":          11,   # K
}

# TAB 3 — Process (YouTube-ready metadata staging)
SCHEMA_PROCESS: dict[str, int] = {
    "Row_ID":          1,   # A
    "Status":          2,   # B  — Pending/Ready/Uploaded/Error
    "Title":           3,   # C
    "YT_Title":        4,   # D  — final YouTube title (editable)
    "YT_Description":  5,   # E
    "YT_Tags":         6,   # F
    "YT_Category":     7,   # G
    "YT_Privacy":      8,   # H  — public/unlisted/private
    "Thumbnail_Path":  9,   # I
    "Drive_Processed": 10,  # J  — video to upload
    "Scheduled_Time":  11,  # K  — optional scheduled publish
    "Notes":          12,   # L
}

# TAB 4 — YouTube (upload results)
SCHEMA_YOUTUBE: dict[str, int] = {
    "Row_ID":         1,    # A
    "Status":         2,    # B  — Pending/Uploaded/Failed
    "Title":          3,    # C
    "YT_Video_ID":    4,    # D
    "YT_URL":         5,    # E
    "YT_Published":   6,    # F
    "Views_7d":       7,    # G  — optional: populated by stats job
    "Likes_7d":       8,    # H
    "Uploaded_Time":  9,    # I
    "Notes":         10,    # J
}

# TAB Credits — credit tracking log
SCHEMA_CREDITS: dict[str, int] = {
    "Email":         1,   # A
    "Credits":       2,   # B
    "DateTime":      3,   # C
    "Duplicate":     4,   # D
    "DupRowNumber":  5,   # E
    "EmailPass":     6,   # F (email:password)
    "Status":        7,   # G
}
