"""
MagicLight Auto v3.0
=====================
Central entry point with clean 3-mode menu.

Modes
-----
  1  Video Making   — MagicLight.ai generation (sheet → generate → download)
  2  Video Process  — FFmpeg post-processing   (pick video → process → Drive/local)
  3  YouTube        — (coming soon)

Extra
-----
  S  Setup / Sheet schema migration
  C  Check credits for all accounts

Usage
-----
  python main.py                        # Interactive menu
  python main.py --mode 1 --max 3       # Generate 3 stories
  python main.py --mode 2               # Process all local videos
  python main.py --mode 2 --upload      # Process + upload to Drive
  python main.py --mode combined --max 1  # Generate + process inline
  python main.py --credits              # Credit check
  python main.py --migrate-schema       # Write sheet headers
  python main.py --loop --mode 1        # Infinite loop mode
"""

__version__ = "3.0.0"

import os
import sys
import argparse
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

from modules.console_utils import console, ok, warn, err, info, rule, header_panel
from modules.config import OUT_BASE, DRIVE_FOLDER_ID
from modules.sheet import read_all, ensure_schema


# ── Menu state persistence ────────────────────────────────────────────────────
import json

_STATE_FILE = ".menu_state.json"

def _load_state() -> dict:
    try:
        if os.path.exists(_STATE_FILE):
            with open(_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"last_amount": 1, "last_drive": True, "last_loop": False}


def _save_state(state: dict):
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


# ── Sheet summary table ───────────────────────────────────────────────────────
def _show_sheet_summary():
    try:
        records = read_all()
    except Exception as e:
        warn(f"Could not read sheet: {e}")
        return

    def _status(r): return str(r.get("Status", "")).strip().lower()

    pending   = [(i + 2, r) for i, r in enumerate(records) if _status(r) == "pending"]
    done      = sum(1 for r in records if _status(r) == "done")
    generated = sum(1 for r in records if _status(r) == "generated")
    errors    = sum(1 for r in records if _status(r) in ("error", "no_video"))
    total     = len(records)

    # Stats bar
    sg = Table.grid(padding=(0, 3))
    sg.add_column(); sg.add_column(); sg.add_column(); sg.add_column(); sg.add_column()
    sg.add_row(
        f"[bold]Total[/bold]  [cyan]{total}[/cyan]",
        f"[bold]Pending[/bold]  [yellow]{len(pending)}[/yellow]",
        f"[bold]Generated[/bold]  [blue]{generated}[/blue]",
        f"[bold]Done[/bold]  [green]{done}[/green]",
        f"[bold]Errors[/bold]  [red]{errors}[/red]",
    )
    console.print(sg)
    console.print()

    if not pending:
        console.print("  [dim]No pending stories.[/dim]")
        return

    t = Table(show_header=True, header_style="bold cyan",
              border_style="dim", show_lines=False,
              title=f"[bold]Pending Stories ({len(pending)})[/bold]",
              title_style="cyan", min_width=70)
    t.add_column("#",     style="dim",    width=4,  justify="right")
    t.add_column("Row",   style="cyan",   width=5,  justify="center")
    t.add_column("Theme", style="yellow", width=16)
    t.add_column("Title", style="white",  width=42)

    for idx, (row_num, row) in enumerate(pending[:15], 1):
        title = str(row.get("Title", "")).strip()[:40] or "(no title)"
        theme = str(row.get("Theme", "")).strip()[:14] or "—"
        t.add_row(str(idx), f"R{row_num}", theme, title)

    if len(pending) > 15:
        t.add_row("...", "", "", f"[dim]and {len(pending)-15} more[/dim]")

    console.print(t)


# ── Input helpers ─────────────────────────────────────────────────────────────
def _ask_int(prompt: str, default: int) -> int:
    ans = console.input(f"  [bold cyan]{prompt}[/bold cyan] [dim](default {default})[/dim] : ").strip()
    return int(ans) if ans.isdigit() else default


def _ask_bool(prompt: str, default: bool) -> bool:
    dstr = "Y" if default else "N"
    ans  = console.input(f"  [bold cyan]{prompt}[/bold cyan] [dim](Y/N, default {dstr})[/dim] : ").strip().upper()
    return (ans == "Y") if ans in ("Y", "N") else default


# ── Mode 1: Video Making ──────────────────────────────────────────────────────
def _run_mode1(args=None, headless: bool = False):
    from modules.pipeline import run_pipeline

    state = _load_state()
    console.print()
    console.rule("[bold cyan]Mode 1 — Video Making[/bold cyan]", style="cyan")
    console.print()
    _show_sheet_summary()
    console.print()

    if args and getattr(args, "max", 0):
        amount = args.max
    else:
        amount = _ask_int("How many stories? (0 = all pending)", state.get("last_amount", 1))

    if args and getattr(args, "upload", False):
        upload = True
    else:
        upload = _ask_bool("Upload to Google Drive?", state.get("last_drive", True))

    loop = False
    if not (args and getattr(args, "loop", False)):
        loop = _ask_bool("Run on loop?", state.get("last_loop", False))
    else:
        loop = True

    combined = args and getattr(args, "combined", False)
    if not combined:
        combined = _ask_bool("Also process (logo+trim) after generation?", False)

    _save_state({"last_amount": amount, "last_drive": upload, "last_loop": loop})

    if loop and not DRIVE_FOLDER_ID:
        err("DRIVE_FOLDER_ID required for loop mode. Set it in .env")
        return

    console.print()
    run_pipeline(
        limit=amount,
        headless=headless,
        upload_drive=upload,
        inline_process=combined,
        loop=loop
    )


# ── Mode 2: Video Process ─────────────────────────────────────────────────────
def _run_mode2(args=None):
    from modules.video_process import scan_videos, process_all, PROFILES
    from pathlib import Path

    console.print()
    console.rule("[bold cyan]Mode 2 — Video Process[/bold cyan]", style="cyan")
    console.print()

    base   = Path(OUT_BASE)
    videos = scan_videos(base)

    if not videos:
        warn(f"No unprocessed videos found in '{OUT_BASE}/'")
        return

    # Show list
    t = Table(show_header=True, header_style="bold cyan", border_style="dim",
              title=f"[bold]Unprocessed Videos ({len(videos)})[/bold]")
    t.add_column("#", width=4, justify="right", style="dim")
    t.add_column("File", style="white")
    t.add_column("MB", width=8, justify="right", style="cyan")
    for i, v in enumerate(videos, 1):
        mb = v.stat().st_size / 1_048_576
        t.add_row(str(i), f"{v.parent.name}/{v.name}", f"{mb:.1f}")
    console.print(t)
    console.print()

    # Options
    if args and getattr(args, "max", 0):
        limit = args.max
    else:
        limit = _ask_int("How many to process? (0 = all)", 0)
    if limit > 0:
        videos = videos[:limit]

    if args and getattr(args, "upload", False):
        upload = True
    else:
        upload = _ask_bool("Upload processed video to Google Drive?", True)

    # Profile
    profile_keys = list(PROFILES.keys())
    console.print()
    for i, k in enumerate(profile_keys, 1):
        console.print(f"  [cyan]{i}[/cyan]  {PROFILES[k]['label']}")
    prof_input = console.input("  [bold cyan]Encode profile[/bold cyan] [dim](1/2/3, default 2)[/dim] : ").strip()
    profile = profile_keys[int(prof_input) - 1] if prof_input.isdigit() and 1 <= int(prof_input) <= 3 else "1080p"

    dry = _ask_bool("Dry run only? (preview, no encode)", False)

    console.print()
    process_all(videos=videos, dry_run=dry, upload=upload, profile=profile)


# ── Mode 3: YouTube ───────────────────────────────────────────────────────────
def _run_mode3():
    console.print()
    console.rule("[bold cyan]Mode 3 — YouTube[/bold cyan]", style="cyan")
    console.print()
    warn("YouTube mode is coming soon. Not yet implemented.")
    console.print()


# ── Setup / Schema ────────────────────────────────────────────────────────────
def _run_setup():
    console.print()
    console.rule("[bold cyan]Setup — Sheet Schema Migration[/bold cyan]", style="cyan")
    console.print()
    ensure_schema()
    console.print()
    console.print("[dim]Now open your Google Sheet and verify columns A–W are correct.[/dim]")
    console.print("[dim]Set any row Status = 'Pending' to queue it for generation.[/dim]")


# ── Credits check ─────────────────────────────────────────────────────────────
def _run_credits(headless: bool = False):
    from modules.credits import check_all_accounts
    check_all_accounts(headless=headless)


# ── Health check ─────────────────────────────────────────────────────────────
def _run_health():
    import subprocess
    console.print()
    console.rule("[bold cyan]System Health Check[/bold cyan]", style="cyan")
    issues = 0
    py = sys.version_info
    if py.major >= 3 and py.minor >= 8:
        ok(f"Python {py.major}.{py.minor}.{py.micro}")
    else:
        err(f"Python too old: {py.major}.{py.minor}"); issues += 1

    pkgs = {"playwright": "playwright", "gspread": "gspread",
            "google-auth-oauthlib": "google_auth_oauthlib",
            "google-api-python-client": "googleapiclient",
            "python-dotenv": "dotenv"}
    for pkg, imp in pkgs.items():
        try:
            __import__(imp); ok(f"Package: {pkg}")
        except ImportError:
            err(f"Missing: {pkg}"); issues += 1

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        ok("FFmpeg installed")
    except Exception:
        err("FFmpeg NOT found in PATH"); issues += 1

    from modules.config import LOGO_PATH, ENDSCREEN_VIDEO, SHEET_ID, DRIVE_FOLDER_ID
    ok(f"Logo: {LOGO_PATH}") if LOGO_PATH.exists() else warn(f"Logo missing: {LOGO_PATH}")
    ok(f"Endscreen: {ENDSCREEN_VIDEO}") if ENDSCREEN_VIDEO.exists() else warn(f"Endscreen missing: {ENDSCREEN_VIDEO}")
    ok("SHEET_ID set") if SHEET_ID else warn("SHEET_ID not set")
    ok("DRIVE_FOLDER_ID set") if DRIVE_FOLDER_ID else warn("DRIVE_FOLDER_ID not set")

    console.print()
    ok("All core checks passed!") if issues == 0 else err(f"{issues} issue(s) found")


# ── Interactive menu ──────────────────────────────────────────────────────────
def interactive_menu():
    header_panel(
        f"MagicLight Auto  v{__version__}",
        "Kids Story Video Pipeline"
    )
    _show_sheet_summary()
    console.print()

    mt = Table(show_header=False, box=None, padding=(0, 2))
    mt.add_column("key",   style="bold cyan",  width=4)
    mt.add_column("label", style="bold white", width=28)
    mt.add_column("desc",  style="dim",        width=40)
    mt.add_row("1", "Video Making",   "MagicLight.ai → generate → download")
    mt.add_row("2", "Video Process",  "Pick video → FFmpeg → Drive/local")
    mt.add_row("3", "YouTube",        "Post processed video to YouTube")
    mt.add_row("─", "──────────────", "─────────────────────────────────────")
    mt.add_row("S", "Setup Sheet",    "Write column headers (run once)")
    mt.add_row("C", "Check Credits",  "Login + log credits for all accounts")
    mt.add_row("H", "Health Check",   "Verify packages, FFmpeg, assets")
    console.print(mt)
    console.print()

    choice = console.input("  [bold cyan]Select [1/2/3/S/C/H] : [/bold cyan]").strip().upper()

    if choice == "1":
        _run_mode1()
    elif choice == "2":
        _run_mode2()
    elif choice == "3":
        _run_mode3()
    elif choice == "S":
        _run_setup()
    elif choice == "C":
        hl = _ask_bool("Run headless?", True)
        _run_credits(headless=hl)
    elif choice == "H":
        _run_health()
    else:
        warn("Unknown choice — exiting.")


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description=f"MagicLight Auto v{__version__}")
    p.add_argument("--mode",     choices=["1", "2", "3", "combined"], help="Run mode directly")
    p.add_argument("--max",      type=int, default=0, help="Max rows/videos to process (0=all)")
    p.add_argument("--upload",   action="store_true", help="Upload to Google Drive")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument("--loop",     action="store_true", help="Infinite loop mode")
    p.add_argument("--combined", action="store_true", help="Generate + process inline")
    p.add_argument("--dry-run",  action="store_true", help="FFmpeg dry run (no encode)")
    p.add_argument("--credits",  action="store_true", help="Check all account credits")
    p.add_argument("--migrate-schema", action="store_true", help="Write sheet headers")
    p.add_argument("--health",   action="store_true", help="Run health check")
    return p.parse_args()


if __name__ == "__main__":
    try:
        args = parse_args()

        # Ensure output directories exist
        os.makedirs(os.path.join(OUT_BASE, "screenshots"), exist_ok=True)

        if args.migrate_schema:
            _run_setup()
        elif args.health:
            _run_health()
        elif args.credits:
            _run_credits(headless=args.headless)
        elif args.mode == "1":
            _run_mode1(args=args, headless=args.headless)
        elif args.mode == "combined":
            args.combined = True
            _run_mode1(args=args, headless=args.headless)
        elif args.mode == "2":
            _run_mode2(args=args)
        elif args.mode == "3":
            _run_mode3()
        else:
            interactive_menu()

    except KeyboardInterrupt:
        console.print("\n[bold yellow][STOP] Exiting...[/bold yellow]")
        from modules.browser_utils import close_browser
        close_browser()
        import os as _os
        _os._exit(0)
    except Exception as e:
        console.print(f"\n[bold red][FATAL] {e}[/bold red]")
        import traceback
        traceback.print_exc()
        import os as _os
        _os._exit(1)
