"""
pipeline.py — Core generation pipeline runner
Reads pending rows from Sheet, rotates accounts, runs video_gen steps,
optionally runs inline processing (combined mode).
"""

import os
import re
import random
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from modules.config import (
    EMAIL, PASSWORD, OUT_BASE, DRIVE_FOLDER_ID, UPLOAD_TO_DRIVE
)
from modules.console_utils import ok, warn, err, info, console, rule
from modules.browser_utils import (
    set_browser, get_browser, sleep_log, screenshot,
    credit_exhausted, read_credits_from_page, is_shutdown
)
from modules.sheet import (
    read_all, update_row, lock_row, credits_log_login, credits_log_completion
)
from modules.video_gen import (
    login, step1, step2, step3, step4, make_safe, retry_from_user_center
)
from modules.video_process import process_video, scan_videos, extract_row_num, make_processed_name
from modules.drive import upload_file

from rich.panel import Panel
from rich.rule import Rule


def load_accounts() -> list[tuple[str, str]]:
    accounts = []
    if os.path.exists("accounts.txt"):
        with open("accounts.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and ":" in line:
                    u, p = line.split(":", 1)
                    accounts.append((u.strip(), p.strip()))
    if not accounts and EMAIL and PASSWORD:
        accounts = [(EMAIL, PASSWORD)]
    return accounts


def run_pipeline(limit: int = 0, headless: bool = False,
                 upload_drive: bool = False, inline_process: bool = False,
                 loop: bool = False):
    """
    Main pipeline entry.
    limit=0 means all pending.
    inline_process=True = combined mode (generate + process).
    """
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless, args=["--start-maximized"])
    set_browser(browser)
    try:
        cycle = 0
        while True:
            cycle += 1
            if loop:
                rule(f"Cycle {cycle}", style="cyan")
            _run_once(limit=limit, upload_drive=upload_drive,
                      inline_process=inline_process)
            if not loop:
                break
            sleep_log(30, "loop cooldown")
    finally:
        try:
            if get_browser(): get_browser().close()
        except Exception:
            pass
        try: pw.stop()
        except Exception: pass


def _run_once(limit: int, upload_drive: bool, inline_process: bool):
    browser = get_browser()
    if not browser:
        err("[pipeline] No browser available")
        return

    # Read sheet
    try:
        records = read_all()
    except Exception as e:
        err(f"Could not read sheet: {e}")
        return

    pending = [(i + 2, r) for i, r in enumerate(records)
               if str(r.get("Status", "")).strip().lower() == "pending"]
    if not pending:
        warn("No pending stories found.")
        return
    if limit > 0:
        pending = pending[:limit]

    accounts = load_accounts()
    if not accounts:
        err("No credentials in accounts.txt or .env")
        return

    random.shuffle(accounts)
    acc_idx     = 0
    curr_email, curr_pw = accounts[acc_idx]
    os.environ["CURRENT_EMAIL"] = curr_email

    context = browser.new_context(accept_downloads=True, no_viewport=True)
    page    = context.new_page()
    try:
        credit_total = login(page, custom_email=curr_email, custom_pw=curr_pw)
    except Exception as e:
        err(f"[FATAL] Login failed for {curr_email}: {e}")
        return

    ok(f"Processing {len(pending)} stor{'y' if len(pending)==1 else 'ies'} | Accounts: {len(accounts)}")

    for row_num, row in pending:
        if is_shutdown():
            break

        # Read credit before
        credit_before = 0
        try:
            page.goto("https://magiclight.ai/user-center", timeout=30000)
            page.wait_for_selector(".home-top-navbar-credit-amount, .credit-amount",
                                    state="visible", timeout=10000)
            credit_before, _ = read_credits_from_page(page)
        except Exception:
            credit_before = max(0, credit_total - 0)

        # Rotate account if credits are low
        if credit_before < 70:
            acc_idx += 1
            if acc_idx >= len(accounts):
                err("All accounts exhausted — stopping.")
                break
            curr_email, curr_pw = accounts[acc_idx]
            os.environ["CURRENT_EMAIL"] = curr_email
            info(f"[Rotate] Switching to {curr_email} (credit={credit_before})")
            try:
                context.close()
                context = browser.new_context(accept_downloads=True, no_viewport=True)
                page    = browser.new_page()
                credit_total  = login(page, custom_email=curr_email, custom_pw=curr_pw)
                credit_before, _ = read_credits_from_page(page)
            except Exception as re_err:
                err(f"Login failed during rotation: {re_err}")
                break

        # Build story text from columns
        vals   = list(row.values())
        col_d  = str(vals[3]).strip() if len(vals) > 3 else ""   # Story
        col_e  = str(vals[4]).strip() if len(vals) > 4 else ""   # Moral
        col_c  = str(vals[2]).strip() if len(vals) > 2 else ""   # Title
        story  = f"{col_c}\n\n{col_d}\n\n{col_e}".strip()
        if not story:
            warn(f"Row {row_num}: empty Story — skipping")
            continue

        title   = str(row.get("Title", f"Row{row_num}")).strip() or f"Row{row_num}"
        safe    = make_safe(row_num, title, "Generated")
        row_id  = f"R{row_num}-{int(time.time())}"

        console.print(Panel(
            f"[bold]Row {row_num}[/bold]  {title}\n"
            f"[dim]Account: {curr_email}   Credit: {credit_before}[/dim]",
            border_style="cyan", expand=False, padding=(0, 1)
        ))

        # Lock row + mark as Processing
        try:
            lock_row(row_num, row_id)
            update_row(row_num,
                Status        = "Processing",
                Email_Used    = curr_email,
                Credit_Before = str(credit_before) if credit_before else "",
                Created_Time  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        except Exception as se:
            warn(f"[sheet] Initial write failed: {se}")

        project_url = ""
        result      = None
        credit_after = 0

        try:
            step1(page, story)
            if credit_exhausted(page):
                err("[Low Credit] Stopping")
                update_row(row_num, Status="Low Credit",
                            Notes="Credits exhausted before Step 2",
                            Completed_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                break
            step2(page)
            step3(page)
            project_url = page.url
            result = step4(page, safe, sheet_row_num=row_num)

            # Read credit after
            try:
                page.goto("https://magiclight.ai/user-center", timeout=40000)
                page.wait_for_selector(".home-top-navbar-credit-amount, .credit-amount",
                                        state="visible", timeout=20000)
                time.sleep(3)
                credit_after, _ = read_credits_from_page(page)
                page.goto("https://magiclight.ai/kids-story/", timeout=30000)
            except Exception:
                credit_after = max(0, credit_before - 60)

            credits_log_completion(curr_email, credit_before, credit_before - credit_after,
                                   row_num, "Generation", "Step4+")

            if credit_exhausted(page):
                update_row(row_num, Status="Low Credit",
                            Credit_After=str(credit_after),
                            Notes="Credits exhausted post-render",
                            Completed_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                break

        except Exception as e:
            screenshot(page, f"error_row{row_num}")
            err(f"Row {row_num} error: {e}")
            if credit_exhausted(page):
                update_row(row_num, Status="Low Credit",
                            Notes="Credits exhausted during generation",
                            Completed_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                break
            try:
                result = retry_from_user_center(page, project_url, safe)
            except Exception as re_err:
                warn(f"[retry] {re_err}")
                result = None
            if not result:
                update_row(row_num, Status="Error",
                            Notes=str(e)[:150],
                            Completed_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                err(f"Row {row_num} → Error")
                sleep_log(5)
                continue

        # Write generated results to sheet
        if result and result.get("video"):
            try:
                update_row(row_num,
                    Status        = "Generated",
                    Gen_Title     = result.get("gen_title", ""),
                    Gen_Summary   = result.get("summary", "")[:200],
                    Gen_Tags      = result.get("tags", ""),
                    Drive_Link    = result.get("drive_link", ""),
                    DriveImg_Link = result.get("drive_thumb", ""),
                    Project_URL   = project_url,
                    Completed_Time= datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    Email_Used    = curr_email,
                    Credit_Before = str(credit_before),
                    Credit_After  = str(credit_after),
                    Notes         = f"Generated OK | Credit: {credit_before}→{credit_after}"
                )
                ok(f"[sheet] Row {row_num} → Generated  Credit: {credit_before}→{credit_after}")
            except Exception as se:
                warn(f"[sheet] Generated write: {se}")
        else:
            try:
                update_row(row_num,
                    Status        = "No_Video",
                    Email_Used    = curr_email,
                    Credit_After  = str(credit_after),
                    Notes         = "Video generation failed",
                    Completed_Time= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            except Exception: pass
            warn(f"Row {row_num} → No_Video")
            continue

        # ── Inline processing (combined mode) ────────────────────────────────
        if inline_process and result and result.get("video"):
            info("[pipeline] Starting inline video processing...")
            vid_path = Path(result["video"])
            if vid_path.exists():
                try:
                    success = process_video(vid_path, dry_run=False)
                    if success:
                        r_num = extract_row_num(vid_path.stem)
                        if "-Generated-" in vid_path.stem:
                            tp = vid_path.stem.split("-Generated-", 1)[1]
                        else:
                            tp = vid_path.stem.split("_", 1)[1] if "_" in vid_path.stem else vid_path.stem
                        if r_num:
                            proc_name = make_processed_name(r_num, tp)
                            proc_path = vid_path.parent / f"{proc_name}{vid_path.suffix}"
                        else:
                            proc_path = vid_path.parent / f"{vid_path.stem}_processed{vid_path.suffix}"

                        if proc_path.exists():
                            ok(f"[pipeline] Processed: {proc_path.name}")
                            processed_link = ""
                            if upload_drive:
                                folder_name    = proc_path.parent.name or proc_path.stem
                                processed_link = upload_file(str(proc_path), folder_name)
                            try:
                                update_row(row_num,
                                    Status         = "Done",
                                    Process_Drive  = processed_link,
                                    Completed_Time = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    Notes          = f"Done | Account: {curr_email}"
                                )
                                ok(f"[sheet] Row {row_num} → Done")
                            except Exception as se:
                                warn(f"[sheet] Done write: {se}")
                        else:
                            warn("Processed file not found after encoding")
                            update_row(row_num, Status="Error",
                                        Notes="Processed file missing after FFmpeg")
                    else:
                        warn("Video processing failed")
                        update_row(row_num, Status="Error",
                                    Notes="FFmpeg encoding failed",
                                    Completed_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                except Exception as pe:
                    warn(f"Processing error: {pe}")
                    update_row(row_num, Status="Error",
                                Notes=f"Processing error: {str(pe)[:150]}",
                                Completed_Time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            else:
                warn("Video file missing for inline processing")
        else:
            ok(f"[sheet] Row {row_num} → Generated (generate-only)")

        if len(pending) > 1:
            sleep_log(5, "cooldown")

    try:
        context.close()
    except Exception:
        pass
    rule(style="cyan")
    ok("Generation sequence complete.")
