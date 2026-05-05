"""
credits.py — Mode: Check all accounts' credit balances
"""

import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

from modules.browser_utils import (
    set_browser, get_browser, sleep_log,
    wait_site_loaded, dismiss_all, read_credits_from_page
)
from modules.console_utils import ok, warn, err, info, console
from modules.sheet import credits_log_login, _tab
from modules.config import EMAIL, PASSWORD, TAB_CREDITS, SCHEMA_CREDITS
from modules.video_gen import login, _logout


def check_all_accounts(headless: bool = False):
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
    rule("Starting Engine 🚀", style="cyan")
    ok(f"[Credits Check] {len(accounts)} account(s) found")
    console.print()

    pw      = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    set_browser(browser)

    checked = failed = 0
    for idx, (email, password) in enumerate(accounts, 1):
        console.print()
        rule(f"Account {idx}/{len(accounts)}", style="dim")
        info(f"[Credits] Checking: {email}")
        try:
            context = browser.new_context(accept_downloads=True, no_viewport=True)
            page    = context.new_page()
            login(page, custom_email=email, custom_pw=password)

            try:
                page.goto("https://magiclight.ai/user-center", timeout=45000)
                wait_site_loaded(page, None, timeout=30)
                sleep_log(2, "user center settle")
            except Exception as e:
                warn(f"[Credits] Could not load user center: {e}")

            total, _ = read_credits_from_page(page)
            ok(f"[Credits] 💰 Credits: {total}")
            credits_log_login(email, total, password)
            checked += 1

            try: _logout(page)
            except Exception: pass
            context.close()
        except Exception as e:
            err(f"[Credits] Failed for {email}: {e}")
            failed += 1
            try: context.close()
            except Exception: pass

    try:
        browser.close()
    except Exception: pass
    try: pw.stop()
    except Exception: pass

    console.print()
    rule("Credit Check Complete ✅", style="green")
    ok(f"[Credits Check] Done: {checked} checked, {failed} failed")
    console.print()
