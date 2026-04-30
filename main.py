"""
MagicLight Auto v2.0
=====================
4-Tab Pipeline: Stories → Videos → Process → YouTube

Menu
----
  1  Video Making   — Tab 1: MagicLight.ai generation
  2  Video Process  — Tab 2: FFmpeg post-processing
  3  YouTube        — Tab 3→4: Upload to YouTube
  4  Full Pipeline  — Tabs 1→2→3 in sequence

Setup
-----
  S  Setup Sheet    — Create all 4 tabs with correct headers
  C  Check Credits  — Login all accounts, log credit balances
  H  Health Check   — Verify packages, FFmpeg, assets, secrets

CLI
---
  python main.py --mode 1 --max 3
  python main.py --mode 2 --upload
  python main.py --mode full --max 1 --loop
  python main.py --setup
  python main.py --credits
  python main.py --health
"""

__version__ = "2.0.0"

import os, sys, argparse, warnings, json
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from rich.panel import Panel
from rich.table import Table

from modules.console_utils import console, ok, warn, err, info, rule, header_panel
from modules.config import OUT_BASE, DRIVE_FOLDER_ID

# ── Menu state ─────────────────────────────────────────────────────────────────
_STATE = ".menu_state.json"

def _load() -> dict:
    try:
        if Path(_STATE).exists():
            return json.loads(Path(_STATE).read_text())
    except Exception: pass
    return {"qty": 1, "upload": True, "loop": False, "profile": "1080p"}

def _save(d: dict):
    try: Path(_STATE).write_text(json.dumps(d))
    except Exception: pass

# ── Sheet summary ──────────────────────────────────────────────────────────────
def _sheet_summary():
    try:
        from modules.sheet import read_tab, refresh_dashboard
        from modules.config import TAB_STORIES, TAB_VIDEOS, TAB_PROCESS, TAB_YOUTUBE

        s = read_tab(TAB_STORIES)
        v = read_tab(TAB_VIDEOS)
        p = read_tab(TAB_PROCESS)
        y = read_tab(TAB_YOUTUBE)

        def cnt(rows, val):
            return sum(1 for r in rows if str(r.get("Status","")).strip().lower() == val.lower())

        g = Table.grid(padding=(0, 4))
        g.add_column(); g.add_column(); g.add_column(); g.add_column(); g.add_column()
        g.add_row(
            f"[bold]Stories[/bold] [yellow]{cnt(s,'Pending')}[/yellow] pending  [green]{cnt(s,'Generated')}[/green] done",
            f"[bold]Videos[/bold] [yellow]{cnt(v,'Pending')}[/yellow] pending  [green]{cnt(v,'Done')}[/green] done",
            f"[bold]Process[/bold] [yellow]{cnt(p,'Pending')+cnt(p,'Ready')}[/yellow] ready",
            f"[bold]YouTube[/bold] [green]{cnt(y,'Uploaded')}[/green] uploaded",
            f"[dim]Total: {len(s)} stories[/dim]",
        )
        console.print(g)
        console.print()

        # Pending stories preview
        pending = [(i+2, r) for i, r in enumerate(s)
                   if str(r.get("Status","")).strip().lower() == "pending"]
        if pending:
            t = Table(show_header=True, header_style="bold cyan",
                      border_style="dim", show_lines=False, expand=False,
                      title=f"[bold]Pending Stories ({len(pending)})[/bold]")
            t.add_column("#",     width=4,  justify="right", style="dim")
            t.add_column("Row",   width=5,  justify="center", style="cyan")
            t.add_column("Theme", width=14, style="yellow")
            t.add_column("Title", width=45)
            for idx, (rn, r) in enumerate(pending[:12], 1):
                t.add_row(str(idx), f"R{rn}",
                          str(r.get("Theme",""))[:12] or "—",
                          str(r.get("Title",""))[:43] or "(no title)")
            if len(pending) > 12:
                t.add_row("..","","",f"[dim]+{len(pending)-12} more[/dim]")
            console.print(t)
    except Exception as e:
        warn(f"Sheet summary: {e}")

# ── Input helpers ──────────────────────────────────────────────────────────────
def _int(prompt, default):
    a = console.input(f"  [bold cyan]{prompt}[/bold cyan] [dim](default {default})[/dim]: ").strip()
    return int(a) if a.isdigit() else default

def _bool(prompt, default):
    d = "Y" if default else "N"
    a = console.input(f"  [bold cyan]{prompt}[/bold cyan] [dim](Y/N, default {d})[/dim]: ").strip().upper()
    return (a == "Y") if a in ("Y","N") else default

# ── Mode runners ───────────────────────────────────────────────────────────────
def mode1(args=None, headless=False):
    from modules.pipeline import run_generation
    s = _load()
    console.print(); rule("Mode 1 — Video Making", style="cyan"); console.print()
    _sheet_summary(); console.print()

    qty    = getattr(args, "max",    0) or _int("How many stories? (0=all)", s["qty"])
    upload = getattr(args, "upload", None)
    if upload is None: upload = _bool("Upload raw video to Drive?", s["upload"])
    loop   = getattr(args, "loop",   False) or _bool("Run on loop?", s["loop"])
    _save({**s, "qty": qty, "upload": upload, "loop": loop})
    console.print()
    run_generation(limit=qty, headless=headless, upload_drive=upload,
                   auto_trigger_process=True, loop=loop)

def mode2(args=None):
    from modules.pipeline import run_processing
    from modules.video_process import PROFILES
    s = _load()
    console.print(); rule("Mode 2 — Video Process", style="cyan"); console.print()

    qty    = getattr(args, "max", 0) or _int("How many? (0=all pending in Tab2)", 0)
    upload = getattr(args, "upload", None)
    if upload is None: upload = _bool("Upload processed video to Drive?", s["upload"])

    console.print()
    for i, (k, v) in enumerate(PROFILES.items(), 1):
        console.print(f"  [cyan]{i}[/cyan]  {v['label']}")
    pi = console.input("  [bold cyan]Profile[/bold cyan] [dim](1/2/3, default 2)[/dim]: ").strip()
    profile = list(PROFILES.keys())[int(pi)-1] if pi.isdigit() and 1<=int(pi)<=3 else "1080p"

    _save({**s, "upload": upload, "profile": profile})
    console.print()
    run_processing(limit=qty, upload=upload, profile=profile, auto_trigger_youtube=True)

def mode3(args=None):
    from modules.pipeline import run_youtube_upload
    console.print(); rule("Mode 3 — YouTube Upload", style="cyan"); console.print()
    qty = getattr(args, "max", 0) or _int("How many? (0=all ready)", 0)
    console.print()
    run_youtube_upload(limit=qty)

def mode_full(args=None, headless=False):
    """Run all 3 pipelines in sequence."""
    console.print()
    rule("Full Pipeline: Tab1 → Tab2 → Tab3", style="cyan")
    console.print()
    s   = _load()
    qty = getattr(args, "max", 0) or _int("Max stories per pipeline? (0=all)", 1)
    _save({**s, "qty": qty})
    console.print()
    info("[Full] Step 1/3 — Generation..."); mode1(args, headless=headless)
    info("[Full] Step 2/3 — Processing..."); mode2(args)
    info("[Full] Step 3/3 — YouTube...");    mode3(args)
    ok("[Full] All 3 pipelines done.")

def run_setup():
    console.print(); rule("Setup — Sheet Tabs", style="cyan"); console.print()
    from modules.sheet import ensure_all_tabs
    ensure_all_tabs()
    console.print()
    console.print("[dim]Open your Google Sheet — you should see 6 tabs:[/dim]")
    console.print("[dim]  1_Stories / 2_Videos / 3_Process / 4_YouTube / Dashboard / Credits[/dim]")
    console.print("[dim]Set any row in 1_Stories Status='Pending' to queue it.[/dim]")

def run_credits(headless=False):
    from modules.credits import check_all_accounts
    check_all_accounts(headless=headless)

def run_health():
    import subprocess
    console.print(); rule("Health Check", style="cyan")
    issues = 0
    py = sys.version_info
    ok(f"Python {py.major}.{py.minor}.{py.micro}") if py >= (3,8) else (err("Python too old") or issues+1)

    for pkg, imp in [("playwright","playwright"), ("gspread","gspread"),
                     ("google-auth-oauthlib","google_auth_oauthlib"),
                     ("google-api-python-client","googleapiclient"),
                     ("python-dotenv","dotenv"), ("rich","rich")]:
        try: __import__(imp); ok(f"Package: {pkg}")
        except ImportError: err(f"Missing: {pkg}"); issues += 1

    try: subprocess.run(["ffmpeg","-version"], capture_output=True, check=True); ok("FFmpeg installed")
    except: err("FFmpeg NOT found"); issues += 1

    from modules.config import LOGO_PATH, ENDSCREEN_VIDEO, SHEET_ID, DRIVE_FOLDER_ID
    ok(f"Logo: {LOGO_PATH}") if LOGO_PATH.exists() else warn(f"Logo missing: {LOGO_PATH}")
    ok("SHEET_ID set") if SHEET_ID else err("SHEET_ID missing — set GitHub Secret")
    ok("DRIVE_FOLDER_ID set") if DRIVE_FOLDER_ID else warn("DRIVE_FOLDER_ID not set")

    console.print()
    ok("All OK!") if issues == 0 else err(f"{issues} issue(s) — fix before running")

# ── Interactive menu ───────────────────────────────────────────────────────────
def menu():
    header_panel(f"MagicLight Auto  v{__version__}", "4-Tab Kids Story Pipeline")

    # Try to show sheet summary (may fail before setup)
    try: _sheet_summary()
    except Exception: pass

    console.print()
    mt = Table(show_header=False, box=None, padding=(0,2))
    mt.add_column("k", style="bold cyan", width=4)
    mt.add_column("l", style="bold white", width=22)
    mt.add_column("d", style="dim")
    mt.add_row("1",  "Video Making",    "Tab 1 — Generate from MagicLight.ai")
    mt.add_row("2",  "Video Process",   "Tab 2 — FFmpeg: logo + trim + endscreen")
    mt.add_row("3",  "YouTube Upload",  "Tab 3→4 — Post processed video to YouTube")
    mt.add_row("4",  "Full Pipeline",   "Run all 3 modes in sequence")
    mt.add_row("─",  "──────────────",  "─────────────────────────────────────────")
    mt.add_row("S",  "Setup Sheet",     "Create all tabs + headers (run once)")
    mt.add_row("C",  "Check Credits",   "Login all accounts → log balances")
    mt.add_row("H",  "Health Check",    "Verify packages, FFmpeg, secrets, assets")
    console.print(mt); console.print()

    ch = console.input("  [bold cyan]Select [1/2/3/4/S/C/H]: [/bold cyan]").strip().upper()
    if   ch == "1": mode1()
    elif ch == "2": mode2()
    elif ch == "3": mode3()
    elif ch == "4": mode_full()
    elif ch == "S": run_setup()
    elif ch == "C":
        hl = _bool("Run headless?", True)
        run_credits(headless=hl)
    elif ch == "H": run_health()
    else: warn("Unknown choice.")

# ── CLI ────────────────────────────────────────────────────────────────────────
def _args():
    p = argparse.ArgumentParser(description=f"MagicLight Auto v{__version__}")
    p.add_argument("--mode",     choices=["1","2","3","full"])
    p.add_argument("--max",      type=int, default=0)
    p.add_argument("--upload",   action="store_true")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--loop",     action="store_true")
    p.add_argument("--setup",    action="store_true")
    p.add_argument("--credits",  action="store_true")
    p.add_argument("--health",   action="store_true")
    return p.parse_args()

if __name__ == "__main__":
    os.makedirs(os.path.join(OUT_BASE, "screenshots"), exist_ok=True)
    try:
        a = _args()
        if   a.setup:          run_setup()
        elif a.health:         run_health()
        elif a.credits:        run_credits(headless=a.headless)
        elif a.mode == "1":    mode1(a, headless=a.headless)
        elif a.mode == "2":    mode2(a)
        elif a.mode == "3":    mode3(a)
        elif a.mode == "full": mode_full(a, headless=a.headless)
        else:                  menu()
    except KeyboardInterrupt:
        console.print("\n[bold yellow][STOP] Exiting...[/bold yellow]")
        from modules.browser_utils import close_browser
        close_browser(); os._exit(0)
    except Exception as e:
        console.print(f"\n[bold red][FATAL] {e}[/bold red]")
        import traceback; traceback.print_exc(); os._exit(1)
