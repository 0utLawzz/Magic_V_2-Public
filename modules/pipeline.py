"""
pipeline.py — Core pipeline runners for all 4 modes.
Tab 1 → Tab 2 → Tab 3 → Tab 4 via Row_ID trigger chain.
"""

import os
import re
import time
import random
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from modules.config import (
    EMAIL, PASSWORD, OUT_BASE, DRIVE_FOLDER_ID,
    TAB_STORIES, TAB_VIDEOS, TAB_PROCESS, TAB_YOUTUBE,
    SCHEMA_STORIES, SCHEMA_VIDEOS,
)
from modules.console_utils import ok, warn, err, info, rule, console
from modules.browser_utils import (
    set_browser, get_browser, sleep_log, screenshot,
    credit_exhausted, read_credits_from_page, is_shutdown
)
from modules.sheet import (
    stories_pending, stories_generated,
    videos_pending, process_ready,
    update_story, update_video, update_process,
    push_to_videos_tab, push_to_process_tab,
    lock_row, credits_log_login, credits_log_completion,
    refresh_dashboard,
)
from modules.video_gen import (
    login, step1, step2, step3, step4,
    make_safe, retry_from_user_center,
)
from modules.video_process import process_video, extract_row_num, make_processed_name
from modules.drive import upload_file, upload_story
from rich.panel import Panel


# ── Account loader ─────────────────────────────────────────────────────────────
def load_accounts() -> list[tuple[str, str]]:
    accs = []
    if os.path.exists("accounts.txt"):
        with open("accounts.txt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and ":" in line:
                    u, p = line.split(":", 1)
                    accs.append((u.strip(), p.strip()))
    if not accs and EMAIL and PASSWORD:
        accs = [(EMAIL, PASSWORD)]
    return accs


# ── Pipeline 1 — Story → Generate (Tab 1) ─────────────────────────────────────
def run_generation(limit: int = 0, headless: bool = False,
                   upload_drive: bool = False,
                   auto_trigger_process: bool = True,
                   loop: bool = False):
    """
    Reads pending rows from Tab 1 (Stories).
    On completion, pushes a row to Tab 2 (Videos) to trigger processing.
    """
    pw      = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless, args=["--start-maximized"])
    set_browser(browser)

    try:
        while True:
            _gen_cycle(limit=limit, upload_drive=upload_drive,
                       auto_trigger_process=auto_trigger_process)
            refresh_dashboard()
            if not loop:
                break
            sleep_log(30, "loop cooldown")
    finally:
        try: get_browser().close()
        except Exception: pass
        try: pw.stop()
        except Exception: pass


def _gen_cycle(limit: int, upload_drive: bool, auto_trigger_process: bool):
    pending = stories_pending()
    if not pending:
        warn("[Tab1] No pending stories.")
        return
    if limit > 0:
        pending = pending[:limit]

    accounts = load_accounts()
    if not accounts:
        err("No credentials found."); return

    random.shuffle(accounts)
    acc_idx          = 0
    curr_email, curr_pw = accounts[acc_idx]

    browser = get_browser()
    context = browser.new_context(accept_downloads=True, no_viewport=True)
    page    = context.new_page()

    try:
        credit_total = login(page, custom_email=curr_email, custom_pw=curr_pw)
    except Exception as e:
        err(f"[FATAL] Login failed: {e}"); context.close(); return

    ok(f"[Tab1] {len(pending)} stor{'y' if len(pending)==1 else 'ies'} | Accounts: {len(accounts)}")

    for row_num, row in pending:
        if is_shutdown(): break

        # Credit check
        credit_before = 0
        try:
            page.goto("https://magiclight.ai/user-center", timeout=30000)
            page.wait_for_selector(".home-top-navbar-credit-amount, .credit-amount",
                                    state="visible", timeout=10000)
            credit_before, _ = read_credits_from_page(page)
        except Exception:
            credit_before = credit_total

        # Rotate account if low
        if credit_before < 70:
            acc_idx += 1
            if acc_idx >= len(accounts):
                err("[Tab1] All accounts exhausted."); break
            curr_email, curr_pw = accounts[acc_idx]
            info(f"[Rotate] → {curr_email} (credit was {credit_before})")
            try:
                context.close()
                context = browser.new_context(accept_downloads=True, no_viewport=True)
                page    = context.new_page()
                credit_total  = login(page, custom_email=curr_email, custom_pw=curr_pw)
                credit_before, _ = read_credits_from_page(page)
            except Exception as re:
                err(f"Rotation login failed: {re}"); break

        # Build story text
        title  = str(row.get("Title", f"Row{row_num}")).strip() or f"Row{row_num}"
        story  = "\n\n".join(filter(None, [
            str(row.get("Theme",  "")).strip(),
            str(row.get("Title",  "")).strip(),
            str(row.get("Story",  "")).strip(),
            str(row.get("Moral",  "")).strip(),
        ]))
        if not story:
            warn(f"[Tab1] Row {row_num}: empty Story — skip"); continue

        safe   = make_safe(row_num, title, "Generated")
        row_id = f"R{row_num}-{int(time.time())}"

        console.print(Panel(
            f"[bold]Row {row_num}[/bold]  {title}\n[dim]{curr_email}   Credit: {credit_before}[/dim]",
            border_style="cyan", expand=False, padding=(0, 1)
        ))

        try:
            lock_row(row_num, row_id)
            update_story(row_num,
                Status        = "Processing",
                Email_Used    = curr_email,
                Credit_Before = str(credit_before),
                Created_Time  = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception as se:
            warn(f"[sheet] Initial write: {se}")

        project_url = ""
        result      = None
        credit_after = 0

        try:
            step1(page, story)
            if credit_exhausted(page):
                err("[Low Credit]")
                update_story(row_num, Status="Low_Credit",
                    Notes="Credits exhausted pre-step2",
                    Completed_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                break
            step2(page)
            step3(page)
            project_url = page.url
            result = step4(page, safe, sheet_row_num=row_num)

            try:
                page.goto("https://magiclight.ai/user-center", timeout=40000)
                page.wait_for_selector(".home-top-navbar-credit-amount",
                                        state="visible", timeout=15000)
                time.sleep(3)
                credit_after, _ = read_credits_from_page(page)
                page.goto("https://magiclight.ai/kids-story/", timeout=30000)
            except Exception:
                credit_after = max(0, credit_before - 60)

            credits_log_completion(curr_email, credit_before,
                                   credit_before - credit_after,
                                   row_num, "Generation", "Step4+")
        except Exception as e:
            screenshot(page, f"error_row{row_num}")
            err(f"Row {row_num} error: {e}")
            try: result = retry_from_user_center(page, project_url, safe)
            except Exception: result = None
            if not result:
                update_story(row_num, Status="Error",
                    Notes=str(e)[:150],
                    Completed_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                sleep_log(5); continue

        # Write back to Tab 1
        if result and result.get("video"):
            update_story(row_num,
                Status        = "Generated",
                Gen_Title     = result.get("gen_title", ""),
                Gen_Summary   = result.get("summary", "")[:200],
                Gen_Tags      = result.get("tags", ""),
                Drive_Raw     = result.get("drive_link", ""),
                Drive_Thumb   = result.get("drive_thumb", ""),
                Project_URL   = project_url,
                Completed_Time= datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                Email_Used    = curr_email,
                Credit_Before = str(credit_before),
                Credit_After  = str(credit_after),
                Notes         = f"OK | Credit: {credit_before}→{credit_after}",
            )
            ok(f"[Tab1] Row {row_num} → Generated")

            # ── TRIGGER: push to Tab 2 ──────────────────────────────────────
            if auto_trigger_process:
                try:
                    push_to_videos_tab(
                        row_id    = row_id,
                        title     = title,
                        drive_raw = result.get("drive_link", ""),
                        drive_thumb = result.get("drive_thumb", ""),
                        local_path  = result.get("video", ""),
                    )
                    info(f"[TRIGGER] Row_ID {row_id} queued in Tab 2")
                except Exception as te:
                    warn(f"[TRIGGER] Tab2 push failed: {te}")
        else:
            update_story(row_num, Status="No_Video",
                Notes="Video download failed",
                Completed_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            warn(f"[Tab1] Row {row_num} → No_Video")

        if len(pending) > 1:
            sleep_log(5, "cooldown")

    try: context.close()
    except Exception: pass
    rule(style="cyan")
    ok("[Tab1] Generation complete.")


# ── Pipeline 2 — Process (Tab 2) ──────────────────────────────────────────────
def run_processing(limit: int = 0, upload: bool = False,
                   profile: str = "1080p",
                   auto_trigger_youtube: bool = True):
    """
    Reads pending rows from Tab 2 (Videos).
    On completion, pushes a row to Tab 3 (Process/YouTube staging).
    """
    pending = videos_pending()
    if not pending:
        warn("[Tab2] No pending videos to process."); return
    if limit > 0:
        pending = pending[:limit]

    ok(f"[Tab2] Processing {len(pending)} video(s)...")

    for row_num, row in pending:
        if is_shutdown(): break

        row_id     = str(row.get("Row_ID", "")).strip()
        title      = str(row.get("Title",  "Row?")).strip()
        local_path = str(row.get("Local_Path", "")).strip()

        if not local_path or not Path(local_path).exists():
            warn(f"[Tab2] R{row_num}: local file missing ({local_path}) — skip")
            update_video(row_num, Status="Error", Notes="Local file not found")
            continue

        vid_path = Path(local_path)
        update_video(row_num, Status="Processing",
                     Process_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        try:
            success = process_video(vid_path, dry_run=False, profile=profile)
        except Exception as e:
            err(f"[Tab2] R{row_num} error: {e}")
            update_video(row_num, Status="Error", Notes=str(e)[:150])
            continue

        if not success:
            update_video(row_num, Status="Error", Notes="FFmpeg failed")
            continue

        # Find the processed file
        r_num = extract_row_num(vid_path.stem)
        if "-Generated-" in vid_path.stem:
            tp = vid_path.stem.split("-Generated-", 1)[1]
        else:
            tp = vid_path.stem.split("_", 1)[1] if "_" in vid_path.stem else vid_path.stem
        proc_name = make_processed_name(r_num, tp) if r_num else f"{vid_path.stem}_processed"
        proc_path = vid_path.parent / f"{proc_name}{vid_path.suffix}"

        processed_link = ""
        if upload and proc_path.exists():
            processed_link = upload_file(str(proc_path), proc_path.parent.name)

        update_video(row_num,
            Status         = "Done",
            Drive_Processed= processed_link,
            Completed_Time = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            Notes          = "Processed OK",
        )
        ok(f"[Tab2] Row {row_num} → Done")

        # ── TRIGGER: push to Tab 3 ──────────────────────────────────────────
        if auto_trigger_youtube and row_id:
            try:
                # Lookup metadata from Tab 1
                from modules.sheet import read_tab
                from modules.config import TAB_STORIES
                s_rows = read_tab(TAB_STORIES)
                meta   = next((r for r in s_rows
                               if str(r.get("Row_ID","")).strip() == row_id), {})
                push_to_process_tab(
                    row_id         = row_id,
                    title          = title,
                    gen_title      = meta.get("Gen_Title", title),
                    gen_summary    = meta.get("Gen_Summary", ""),
                    gen_tags       = meta.get("Gen_Tags", ""),
                    drive_processed= processed_link,
                    thumb_path     = str(proc_path.parent / f"{vid_path.stem.replace('Generated','Generated')}_thumb.jpg"),
                )
                info(f"[TRIGGER] Row_ID {row_id} queued in Tab 3")
            except Exception as te:
                warn(f"[TRIGGER] Tab3 push failed: {te}")

    refresh_dashboard()
    rule(style="cyan")
    ok("[Tab2] Processing complete.")


# ── Pipeline 3 — YouTube Upload (Tab 3 → Tab 4) ───────────────────────────────
def run_youtube_upload(limit: int = 0):
    """Reads ready rows from Tab 3 and uploads to YouTube. Writes to Tab 4."""
    try:
        from modules.youtube import upload_video as yt_upload
    except ImportError:
        warn("[Tab3] modules/youtube.py not found. YouTube mode coming soon.")
        return

    pending = process_ready()
    if not pending:
        warn("[Tab3] No videos ready for YouTube."); return
    if limit > 0:
        pending = pending[:limit]

    for row_num, row in pending:
        if is_shutdown(): break
        row_id = str(row.get("Row_ID", "")).strip()
        update_process(row_num, Status="Uploading")
        try:
            result = yt_upload(row)
            if result.get("video_id"):
                update_process(row_num, Status="Uploaded",
                    Notes=f"YT: {result['video_id']}")
                push_to_youtube_tab(
                    row_id    = row_id,
                    title     = str(row.get("Title", "")),
                    yt_id     = result["video_id"],
                    yt_url    = result.get("url", ""),
                    published = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
                ok(f"[Tab3] Row {row_num} → YouTube: {result['url']}")
            else:
                update_process(row_num, Status="Error",
                    Notes=result.get("error", "Unknown error"))
        except Exception as e:
            update_process(row_num, Status="Error", Notes=str(e)[:150])
            err(f"[Tab3] Row {row_num}: {e}")

    refresh_dashboard()
    ok("[Tab3] YouTube upload run complete.")
