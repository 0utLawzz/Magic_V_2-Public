"""
sheet.py — Google Sheets: all read/write for all 4 tabs.
Row_ID is the single key that links Stories → Videos → Process → YouTube.
"""

import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials as SACredentials
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from modules.config import (
    SHEET_ID, CREDS_JSON,
    TAB_STORIES, TAB_VIDEOS, TAB_PROCESS, TAB_YOUTUBE,
    TAB_DASHBOARD, TAB_CREDITS,
    SCHEMA_STORIES, SCHEMA_VIDEOS, SCHEMA_PROCESS, SCHEMA_YOUTUBE,
)
from modules.console_utils import ok, warn, info, dbg

# ── Cached handles ─────────────────────────────────────────────────────────────
_gc  = None
_spr = None   # spreadsheet
_tabs: dict[str, gspread.Worksheet] = {}

_TAB_SCHEMAS = {
    TAB_STORIES: SCHEMA_STORIES,
    TAB_VIDEOS:  SCHEMA_VIDEOS,
    TAB_PROCESS: SCHEMA_PROCESS,
    TAB_YOUTUBE: SCHEMA_YOUTUBE,
}

# ── Auth ───────────────────────────────────────────────────────────────────────
def _sa_creds():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    if not os.path.exists(CREDS_JSON):
        raise FileNotFoundError(f"credentials.json not found: {CREDS_JSON}")
    return SACredentials.from_service_account_file(CREDS_JSON, scopes=scopes)

def _oauth_creds():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    token_file = "token.json"
    creds = None
    if os.path.exists(token_file):
        try:
            from google.auth.transport.requests import Request
            creds = Credentials.from_authorized_user_file(token_file, scopes)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
        except Exception:
            creds = None
    if not creds or not creds.valid:
        flow  = InstalledAppFlow.from_client_secrets_file("oauth_credentials.json", scopes)
        creds = flow.run_local_server(port=8080, access_type="offline", prompt="consent")
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return creds

def _get_creds():
    if os.path.exists("oauth_credentials.json"):
        try: return _oauth_creds()
        except Exception: pass
    return _sa_creds()

# ── Spreadsheet + tab handles ──────────────────────────────────────────────────
def _spreadsheet():
    global _gc, _spr
    if _spr: return _spr
    if not SHEET_ID:
        raise ValueError("SHEET_ID not set. Add it to GitHub Secrets / .env")
    _gc  = gspread.authorize(_get_creds())
    _spr = _gc.open_by_key(SHEET_ID)
    return _spr

def _tab(name: str) -> gspread.Worksheet:
    if name in _tabs: return _tabs[name]
    spr = _spreadsheet()
    existing = {ws.title for ws in spr.worksheets()}
    if name not in existing:
        ws = spr.add_worksheet(title=name, rows="1000", cols="30")
        info(f"[sheet] Created tab '{name}'")
    else:
        ws = spr.worksheet(name)
    _tabs[name] = ws
    return ws

# ── Ensure all tabs + headers exist ───────────────────────────────────────────
def ensure_all_tabs():
    """Create all 4 pipeline tabs + Dashboard + Credits with correct headers."""
    for tab_name, schema in _TAB_SCHEMAS.items():
        ws      = _tab(tab_name)
        headers = [""] * max(schema.values())
        for col_name, idx in schema.items():
            headers[idx - 1] = col_name
        end_col = chr(ord("A") + len(headers) - 1)
        ws.update(f"A1:{end_col}1", [headers])
        ok(f"[schema] '{tab_name}' headers written (A–{end_col})")

    _ensure_dashboard()
    _ensure_credits_tab()
    ok("[schema] All tabs ready.")

def _ensure_dashboard():
    ws = _tab(TAB_DASHBOARD)
    ws.update("A1:F1", [["Last_Updated", "Total_Stories", "Generated",
                          "Processed", "On_YouTube", "Credits_Left"]])
    ok(f"[schema] '{TAB_DASHBOARD}' ready")

def _ensure_credits_tab():
    ws = _tab(TAB_CREDITS)
    ws.update("A1:G1", [["Email", "Total_Credits", "Used_Credits",
                          "Remaining", "Last_Checked", "Log_Timestamp", "Detail"]])
    ok(f"[schema] '{TAB_CREDITS}' ready")

# ── Generic read/write ─────────────────────────────────────────────────────────
def read_tab(tab_name: str) -> list[dict]:
    return _tab(tab_name).get_all_records(head=1)

def update_row(tab_name: str, row_num: int, schema: dict, **kw):
    """Write named columns to a specific row in a tab."""
    ws = _tab(tab_name)
    # Read actual headers once
    actual = set(h.strip() for h in ws.row_values(1) if h.strip())
    for col_name, value in kw.items():
        col_idx = schema.get(col_name)
        if col_idx is None:
            dbg(f"[sheet] IGNORED unknown col '{col_name}' in '{tab_name}'")
            continue
        if col_name not in actual:
            dbg(f"[sheet] SKIPPED '{col_name}' — not in '{tab_name}' headers")
            continue
        try:
            ws.update_cell(row_num, col_idx, str(value) if value is not None else "")
        except Exception as e:
            warn(f"[sheet] update_cell({tab_name}!{col_name}@R{row_num}): {e}")

def lock_row(row_num: int, row_id: str):
    """Stamp Row_ID in Stories tab once — marks row as claimed."""
    update_row(TAB_STORIES, row_num, SCHEMA_STORIES, Row_ID=row_id)

# ── Tab 1 helpers ──────────────────────────────────────────────────────────────
def stories_pending() -> list[tuple[int, dict]]:
    records = read_tab(TAB_STORIES)
    return [(i + 2, r) for i, r in enumerate(records)
            if str(r.get("Status", "")).strip().lower() == "pending"]

def stories_generated() -> list[tuple[int, dict]]:
    records = read_tab(TAB_STORIES)
    return [(i + 2, r) for i, r in enumerate(records)
            if str(r.get("Status", "")).strip().lower() == "generated"]

def update_story(row_num: int, **kw):
    update_row(TAB_STORIES, row_num, SCHEMA_STORIES, **kw)

# ── Tab 2 helpers ──────────────────────────────────────────────────────────────
def videos_pending() -> list[tuple[int, dict]]:
    records = read_tab(TAB_VIDEOS)
    return [(i + 2, r) for i, r in enumerate(records)
            if str(r.get("Status", "")).strip().lower() == "pending"]

def update_video(row_num: int, **kw):
    update_row(TAB_VIDEOS, row_num, SCHEMA_VIDEOS, **kw)

def push_to_videos_tab(row_id: str, title: str, drive_raw: str,
                        drive_thumb: str, local_path: str):
    """After generation, push a new row to Tab 2 (processing queue)."""
    ws = _tab(TAB_VIDEOS)
    ws.append_row([
        row_id, "Pending", title, drive_raw,
        local_path, "1080p", "", drive_thumb, "", "", "Auto-queued from Tab 1"
    ])
    ok(f"[sheet] Tab2 row appended for Row_ID={row_id}")

# ── Tab 3 helpers ──────────────────────────────────────────────────────────────
def process_ready() -> list[tuple[int, dict]]:
    records = read_tab(TAB_PROCESS)
    return [(i + 2, r) for i, r in enumerate(records)
            if str(r.get("Status", "")).strip().lower() == "ready"]

def update_process(row_num: int, **kw):
    update_row(TAB_PROCESS, row_num, SCHEMA_PROCESS, **kw)

def push_to_process_tab(row_id: str, title: str, gen_title: str,
                         gen_summary: str, gen_tags: str, drive_processed: str,
                         thumb_path: str):
    """After video processing, push metadata to Tab 3 (YouTube staging)."""
    ws = _tab(TAB_PROCESS)
    ws.append_row([
        row_id, "Pending", title,
        gen_title[:100] if gen_title else title,
        gen_summary[:4000] if gen_summary else "",
        gen_tags,
        "27",       # Kids & Family category
        "public",
        thumb_path,
        drive_processed,
        "",         # Scheduled_Time (leave blank = upload now)
        "Auto-staged from Tab 2"
    ])
    ok(f"[sheet] Tab3 row appended for Row_ID={row_id}")

# ── Tab 4 helpers ──────────────────────────────────────────────────────────────
def update_youtube(row_num: int, **kw):
    update_row(TAB_YOUTUBE, row_num, SCHEMA_YOUTUBE, **kw)

def push_to_youtube_tab(row_id: str, title: str, yt_id: str,
                         yt_url: str, published: str):
    ws = _tab(TAB_YOUTUBE)
    ws.append_row([row_id, "Uploaded", title, yt_id, yt_url, published,
                   "", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""])
    ok(f"[sheet] Tab4 YouTube row for Row_ID={row_id}")

# ── Dashboard refresh ──────────────────────────────────────────────────────────
def refresh_dashboard():
    try:
        s_rows = read_tab(TAB_STORIES)
        v_rows = read_tab(TAB_VIDEOS)
        p_rows = read_tab(TAB_PROCESS)
        y_rows = read_tab(TAB_YOUTUBE)

        def _status(r, val): return str(r.get("Status","")).strip().lower() == val.lower()

        total      = len(s_rows)
        generated  = sum(1 for r in s_rows if _status(r, "Generated"))
        processed  = sum(1 for r in v_rows if _status(r, "Done"))
        on_yt      = sum(1 for r in y_rows if _status(r, "Uploaded"))

        # Credit remaining: latest from Credits tab
        try:
            crows = read_tab(TAB_CREDITS)
            credits_left = sum(int(r.get("Remaining", 0) or 0) for r in crows)
        except Exception:
            credits_left = 0

        ws  = _tab(TAB_DASHBOARD)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.update("A2:F2", [[now, total, generated, processed, on_yt, credits_left]])
        ok(f"[dashboard] Updated: total={total} gen={generated} proc={processed} yt={on_yt}")
    except Exception as e:
        warn(f"[dashboard] Refresh error: {e}")

# ── Credits helpers ────────────────────────────────────────────────────────────
def credits_log_login(email: str, total: int):
    try:
        ws   = _tab(TAB_CREDITS)
        now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = ws.get_all_values()
        found = None
        for i, row in enumerate(rows[1:], start=2):
            if row and row[0].strip().lower() == email.strip().lower():
                found = i; break
        data = [email, str(total), "", "", now]
        if found: ws.update(f"A{found}:E{found}", [data])
        else:     ws.append_row(data)
    except Exception as e:
        warn(f"[credits] Login log: {e}")

def credits_log_completion(email: str, total: int, used: int,
                            row_num: int, action: str, status: str):
    try:
        ws        = _tab(TAB_CREDITS)
        remaining = max(0, total - used)
        now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows      = ws.get_all_values()
        found     = None
        for i, row in enumerate(rows[1:], start=2):
            if row and row[0].strip().lower() == email.strip().lower():
                found = i; break
        detail = f"{action} | Row:{row_num} | {status}"
        if found: ws.update(f"C{found}:G{found}",
                             [[str(used), str(remaining), now, now, detail]])
        else:     ws.append_row([email, str(total), str(used),
                                  str(remaining), now, now, detail])
    except Exception as e:
        warn(f"[credits] Completion log: {e}")
