# === STABLE - DO NOT MODIFY ===
"""
credits.py — Mode: Check all accounts' credit balances
"""

import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed

from modules.browser_utils import (
    set_browser, get_browser, sleep_log,
    wait_site_loaded, dismiss_all, read_credits_from_page
)
from modules.console_utils import ok, warn, err, info, console
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn
from rich.table import Table
from modules.sheet import credits_log_login, _tab
from modules.config import EMAIL, PASSWORD, TAB_CREDITS, SCHEMA_CREDITS
from modules.video_gen import login, _logout


def _check_single_account(email: str, password: str, headless: bool, dry_run: bool, credit_threshold: int):
    """Check a single account's credits (process-safe)."""
    result = {"email": email, "credits": 0, "status": "Failed"}
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True, no_viewport=True)
        page = context.new_page()
        login(page, custom_email=email, custom_pw=password)

        try:
            page.goto("https://magiclight.ai/user-center", timeout=45000)
            wait_site_loaded(page, None, timeout=30)
            sleep_log(2, "user center settle")
        except Exception as e:
            warn(f"[Credits] Could not load user center for {email}: {e}")

        total, _ = read_credits_from_page(page)
        result["credits"] = total
        result["status"] = "Success"
        ok(f"[Credits] {email}: {total} credits")
        if total < credit_threshold:
            warn(f"[Credits] ⚠️ Low credits warning: {total} < {credit_threshold}")
        if not dry_run:
            credits_log_login(email, total, password, status="Success")

        try: _logout(page)
        except Exception: pass
        context.close()
        browser.close()
        pw.stop()
    except Exception as e:
        err(f"[Credits] Failed for {email}: {e}")
        if not dry_run:
            credits_log_login(email, 0, password, status="Failed")
    return result


def check_all_accounts(headless: bool = False, dry_run: bool = False, credit_threshold: int = 150, concurrency: int = 1):
    """Login to every account in accounts.txt, read credits, log to Sheet."""
    from modules.console_utils import rule
    accounts = []
    if os.path.exists("accounts.txt"):
        with open("accounts.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and ":" in line:
                    u, p = line.split(":", 1)
                    accounts.append((u.strip(), p.strip()))
    if not accounts:
        if EMAIL and PASSWORD:
            accounts = [(EMAIL, PASSWORD)]
        else:
            err("[Credits Check] No credentials in accounts.txt or .env")
            return

    console.print()
    if dry_run:
        rule("Starting Engine 🚀 (DRY-RUN MODE)", style="yellow")
        warn("[Credits Check] Dry-run mode - will NOT log to sheet")
    else:
        rule("Starting Engine 🚀", style="cyan")
    
    # Note: Parallel mode disabled due to Playwright Sync API conflicts with ThreadPoolExecutor
    if concurrency > 1:
        warn(f"[Credits Check] Parallel mode disabled due to Playwright conflicts - running sequentially")
        concurrency = 1
    
    ok(f"[Credits Check] {len(accounts)} account(s) found")
    console.print()

    checked = failed = 0
    results = []  # Track results for summary table

    # Sequential execution (Playwright Sync API conflicts with threading)
    with Progress(
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        expand=False
    ) as progress:
        task = progress.add_task("[Credits] Checking accounts...", total=len(accounts))
        
        for idx, (email, password) in enumerate(accounts, 1):
            console.print()
            rule(f"Account {idx}/{len(accounts)}", style="dim")
            info(f"[Credits] Checking: {email}")
            
            result = _check_single_account(email, password, headless, dry_run, credit_threshold)
            results.append(result)
            if result["status"] == "Success":
                checked += 1
            else:
                failed += 1
            progress.update(task, advance=1)

    console.print()
    rule("Credit Check Complete ✅", style="green")
    ok(f"[Credits Check] Done: {checked} checked, {failed} failed")
    console.print()

    # Display summary table
    if results:
        console.print()
        rule("Summary Table 📊", style="cyan")
        console.print()
        summary_table = Table(title="Credit Check Results")
        summary_table.add_column("Email", style="cyan", width=30)
        summary_table.add_column("Credits", style="green", justify="right")
        summary_table.add_column("Status", style="bold", width=10)
        for r in results:
            status_style = "green" if r["status"] == "Success" else "red"
            summary_table.add_row(r["email"], str(r["credits"]), f"[{status_style}]{r['status']}")
        console.print(summary_table)
        console.print()
