"""
config.py — Centralized configuration loader
Reads all settings from .env and exposes them as module-level constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

# ── Credentials ────────────────────────────────────────────────────────────────
EMAIL    = os.getenv("EMAIL", "")
PASSWORD = os.getenv("PASSWORD", "")

# ── Google Sheet ───────────────────────────────────────────────────────────────
SHEET_ID        = os.getenv("SHEET_ID", "")
SHEET_NAME      = os.getenv("SHEET_NAME", "Database")
CREDS_JSON      = os.getenv("CREDS_JSON", "credentials.json")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")

# ── Timing ─────────────────────────────────────────────────────────────────────
STEP1_WAIT      = int(os.getenv("STEP1_WAIT",            "60"))
STEP2_WAIT      = int(os.getenv("STEP2_WAIT",            "30"))
STEP3_WAIT      = int(os.getenv("STEP3_WAIT",           "180"))
RENDER_TIMEOUT  = int(os.getenv("STEP4_RENDER_TIMEOUT", "1200"))
POLL_INTERVAL   = 10
RELOAD_INTERVAL = 120

# ── Output Paths ───────────────────────────────────────────────────────────────
OUT_BASE            = "output"
OUT_SHOTS           = os.path.join(OUT_BASE, "screenshots")
MAGICLIGHT_OUTPUT   = Path(os.getenv("MAGICLIGHT_OUTPUT", OUT_BASE))
LOGO_PATH           = Path(os.getenv("LOGO_PATH",   "assets/logo.png"))
ENDSCREEN_VIDEO     = Path(os.getenv("ENDSCREEN_VIDEO", "assets/endscreen.mp4"))

# ── FFmpeg / Branding ──────────────────────────────────────────────────────────
TRIM_SECONDS      = int(os.getenv("TRIM_SECONDS",   "4"))
LOGO_X            = int(os.getenv("LOGO_X",         "7"))
LOGO_Y            = int(os.getenv("LOGO_Y",         "5"))
LOGO_WIDTH        = int(os.getenv("LOGO_WIDTH",     "300"))
LOGO_OPACITY      = float(os.getenv("LOGO_OPACITY", "1.0"))
ENDSCREEN_ENABLED = os.getenv("ENDSCREEN_ENABLED",  "true").lower() == "true"
ENDSCREEN_DURATION = os.getenv("ENDSCREEN_DURATION", "auto")

# ── Feature Flags ──────────────────────────────────────────────────────────────
UPLOAD_TO_DRIVE = os.getenv("UPLOAD_TO_DRIVE", "false").lower() == "true"
DEBUG           = os.getenv("DEBUG", "0") == "1"

# ── Sheet Schema (column index map) ───────────────────────────────────────────
# Row ID links all three sheets.  Columns below are shared across modes.
SHEET_SCHEMA: dict[str, int] = {
    # ── Mode 1: Video Generation ──────────────────────────────────────────────
    "Row_ID":          1,   # A  — unique row lock key (set once, never changed)
    "Status":          2,   # B  — Pending / Processing / Generated / Done / Error
    "Theme":           3,   # C
    "Title":           4,   # D
    "Story":           5,   # E
    "Moral":           6,   # F
    # ── Mode 1 outputs ────────────────────────────────────────────────────────
    "Gen_Title":       7,   # G
    "Gen_Summary":     8,   # H
    "Gen_Tags":        9,   # I
    "Project_URL":    10,   # J
    "Created_Time":   11,   # K
    "Completed_Time": 12,   # L
    # ── Mode 2: Video Processing ──────────────────────────────────────────────
    "Drive_Link":     13,   # M  — raw video Drive link (from generation)
    "DriveImg_Link":  14,   # N  — thumbnail
    "Process_Drive":  15,   # O  — processed video Drive link
    # ── Mode 3: YouTube ───────────────────────────────────────────────────────
    "YT_Status":      16,   # P  — Pending / Uploaded / Failed
    "YT_Video_ID":    17,   # Q
    "YT_URL":         18,   # R
    "YT_Published":   19,   # S
    # ── Credit tracking ───────────────────────────────────────────────────────
    "Credit_Before":  20,   # T
    "Credit_After":   21,   # U
    "Email_Used":     22,   # V
    "Notes":          23,   # W
}

VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv'}
