"""
sheet.py — Google Sheets read/write helpers
All sheet interaction is centralized here.
Row_ID column is used to cross-link Mode1 → Mode2 → Mode3.
"""

import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from modules.config import SHEET_ID, SHEET_NAME, CREDS_JSON, SHEET_SCHEMA
from modules.console_utils import ok, warn, info, dbg

_gc  = None
_ws  = None
_hdr = []
_cws = None   # Credits worksheet


# ── Auth ──────────────────────────────────────────────────────────────────────
def _get_service_account_credentials():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]
    if not os.path.exists(CREDS_JSON):
        raise FileNotFoundError(f"credentials.json not found: {CREDS_JSON}")
    return ServiceAccountCredentials.from_service_account_file(CREDS_JSON, scopes=scopes)


def _get_oauth_credentials():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]
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
        flow = InstalledAppFlow.from_client_secrets_file("oauth_credentials.json", scopes)
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return creds


def _get_credentials():
    if os.path.exists("oauth_credentials.json"):
        try:
            return _get_oauth_credentials()
        except Exception:
            pass
    return _get_service_account_credentials()


# ── Sheet handle ──────────────────────────────────────────────────────────────
def get_sheet():
    global _gc, _ws, _hdr
    if _ws is not None:
        return _ws
    if not SHEET_ID:
        raise ValueError("SHEET_ID not set in .env")
    creds = _get_credentials()
    _gc = gspread.authorize(creds)
    sh  = _gc.open_by_key(SHEET_ID)
    _ws = sh.worksheet(SHEET_NAME)
    _hdr = _ws.row_values(1)
    return _ws


def ensure_credits_sheet():
    global _cws, _gc
    if _cws is not None:
        return _cws
    get_sheet()
    sh = _gc.open_by_key(SHEET_ID)
    try:
        _cws = sh.worksheet("Credits")
    except Exception:
        info("[credits] Creating Credits sheet...")
        _cws = sh.add_worksheet(title="Credits", rows="500", cols="10")
        _cws.update("A1:G1", [["Email", "Total_Credits", "Used_Credits",
                                "Remaining", "Last_Checked",
                                "Log_Timestamp", "Log_Detail"]])
        ok("[credits] Credits sheet created")
    return _cws


# ── Helpers ───────────────────────────────────────────────────────────────────
def _actual_cols() -> set:
    try:
        get_sheet()
        return set(h.strip() for h in _hdr if h.strip())
    except Exception:
        return set(SHEET_SCHEMA.keys())


def _col(name: str) -> int | None:
    return SHEET_SCHEMA.get(name)


# ── Public API ────────────────────────────────────────────────────────────────
def read_all() -> list[dict]:
    return get_sheet().get_all_records(head=1)


def update_row(row_num: int, **kw):
    """Write one or more named columns to a specific sheet row."""
    ws = get_sheet()
    actual = _actual_cols()
    for col_name, value in kw.items():
        col_idx = _col(col_name)
        if col_idx is None:
            dbg(f"[sheet] IGNORED unknown col '{col_name}'")
            continue
        if col_name not in actual:
            dbg(f"[sheet] SKIPPED '{col_name}' — not in sheet headers")
            continue
        try:
            ws.update_cell(row_num, col_idx, str(value) if value is not None else "")
            dbg(f"[sheet] R{row_num} '{col_name}'({col_idx}) = '{str(value)[:40]}'")
        except Exception as e:
            warn(f"[sheet] update_cell({col_name}→{col_idx}): {e}")


def lock_row(row_num: int, row_id: str):
    """Stamp Row_ID once — marks the row as claimed by this pipeline run."""
    update_row(row_num, Row_ID=row_id)


def ensure_schema():
    """Write correct column headers to row 1 (run once during setup)."""
    ws = get_sheet()
    headers = [""] * max(SHEET_SCHEMA.values())
    for name, idx in SHEET_SCHEMA.items():
        headers[idx - 1] = name
    end_col = chr(ord("A") + len(headers) - 1)
    ws.update(f"A1:{end_col}1", [headers])
    ok(f"[schema] Headers written (A–{end_col})")


# ── Credit helpers ────────────────────────────────────────────────────────────
def credits_log_login(email: str, total: int):
    try:
        ws  = ensure_credits_sheet()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = ws.get_all_values()
        found = None
        for i, row in enumerate(rows[1:], start=2):
            if row and row[0].strip().lower() == email.strip().lower():
                found = i; break
        data = [email, str(total), "", "", now]
        if found:
            ws.update(f"A{found}:E{found}", [data])
        else:
            ws.append_row(data)
    except Exception as e:
        warn(f"[credits] Login log error: {e}")


def credits_log_completion(email: str, total: int, used: int,
                            row_num: int, action: str, status: str):
    try:
        ws        = ensure_credits_sheet()
        remaining = max(0, total - used)
        now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = ws.get_all_values()
        found = None
        for i, row in enumerate(rows[1:], start=2):
            if row and row[0].strip().lower() == email.strip().lower():
                found = i; break
        detail = f"{action} | Row:{row_num} | Status:{status}"
        if found:
            ws.update(f"C{found}:G{found}",
                      [[str(used), str(remaining), now, now, detail]])
        else:
            ws.append_row([email, str(total), str(used), str(remaining),
                           now, now, detail])
    except Exception as e:
        warn(f"[credits] Completion log error: {e}")
