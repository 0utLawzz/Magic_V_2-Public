"""
video_gen.py — Mode 1: MagicLight.ai video generation pipeline
Login → Step1 (story) → Step2 (cast) → Step3 (storyboard) → Step4 (render+download)
"""

import os
import re
import time
import requests
from datetime import datetime
from pathlib import Path

from modules.config import (
    EMAIL, PASSWORD, STEP1_WAIT, STEP2_WAIT, STEP3_WAIT,
    RENDER_TIMEOUT, POLL_INTERVAL, RELOAD_INTERVAL,
    OUT_BASE, MAGICLIGHT_OUTPUT, DRIVE_FOLDER_ID, UPLOAD_TO_DRIVE
)
from modules.console_utils import ok, warn, err, info, dbg, console
from modules.browser_utils import (
    sleep_log, wait_dismissing, dismiss_all, dismiss_popups,
    dismiss_animation_modal, wait_site_loaded, dom_click_text,
    screenshot, credit_exhausted, read_credits_from_page, is_shutdown
)
from modules.drive import upload_story
from modules.sheet import update_row, credits_log_login, credits_log_completion


# ── Filename helpers ──────────────────────────────────────────────────────────
def make_safe(row_num: int, title: str, file_type: str = "") -> str:
    if file_type:
        safe_title = re.sub(r"[^\w\-]", "_", str(title)[:40])
        return f"row{row_num}-{file_type}-{safe_title}".strip("_")
    return re.sub(r"[^\w\-]", "_", f"row{row_num}_{str(title)[:40]}").strip("_")


def story_dir(safe_name: str) -> str:
    d = os.path.join(OUT_BASE, safe_name)
    os.makedirs(d, exist_ok=True)
    return d


# ── Login ─────────────────────────────────────────────────────────────────────
def _logout(page):
    try:
        page.goto("https://magiclight.ai/", timeout=30000)
        wait_site_loaded(page, None, timeout=20)
        time.sleep(2)
        page.evaluate("""\
() => {
    const logoutTexts = ['Log out','Logout','Sign out','Sign Out','Log Out'];
    for (const el of Array.from(document.querySelectorAll('a,button,div,span'))) {
        const t = (el.innerText || '').trim();
        if (logoutTexts.includes(t) && el.getBoundingClientRect().width > 0) {
            el.click(); return t;
        }
    }
    return null;
}""")
        time.sleep(1)
    except Exception:
        pass
    try: page.context.clear_cookies()
    except Exception: pass


def login(page, custom_email: str = None, custom_pw: str = None):
    from modules.sheet import credits_log_login
    info("[Login] Starting fresh login...")
    try: page.context.clear_cookies()
    except Exception: pass
    _logout(page)
    page.goto("https://magiclight.ai/login/?to=%252Fkids-story%252F", timeout=60000)
    try: page.wait_for_load_state("networkidle", timeout=15000)
    except Exception: pass
    sleep_log(3, "page settle")

    clicked_email_tab = False
    for sel in ['.entry-email', 'text=Log in with Email',
                'button:has-text("Log in with Email")', '[class*="entry-email"]']:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=3000):
                loc.click(timeout=5000)
                clicked_email_tab = True
                sleep_log(3, "inputs settle")
                break
        except Exception:
            pass
    if not clicked_email_tab:
        page.evaluate("""() => {
            const el = document.querySelector('.entry-email') ||
                       [...document.querySelectorAll('button')].find(b => b.innerText.includes('Email'));
            if (el) el.click();
        }""")
        sleep_log(2)

    email_filled = False
    for sel in ['input[type="text"]', 'input[type="email"]', 'input[name="email"]',
                'input.arco-input', 'input[placeholder*="mail" i]']:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=15000)
            loc.scroll_into_view_if_needed()
            loc.click()
            page.wait_for_timeout(500)
            loc.fill(custom_email or EMAIL)
            email_filled = True
            break
        except Exception:
            continue
    if not email_filled:
        screenshot(page, "login_fail_no_email")
        raise Exception("Login failed — email input not found")

    page.wait_for_timeout(500)
    pass_filled = False
    for sel in ['input[type="password"]', 'input[name="password"]',
                'input[placeholder*="password" i]']:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=8000)
            loc.fill(custom_pw or PASSWORD)
            pass_filled = True
            break
        except Exception:
            continue
    if not pass_filled:
        raise Exception("Login failed — password input not found")

    clicked = False
    for _ in range(3):
        for sel in [".signin-continue", "text=Continue", "div.signin-continue",
                    "button:has-text('Continue')", "button.arco-btn-primary"]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    clicked = True
                    break
            except Exception:
                pass
        if clicked:
            break
        page.wait_for_timeout(2000)
    if not clicked:
        raise Exception("Login failed — Continue button not found")

    try:
        page.wait_for_url("**/kids-story/**", timeout=30000)
    except Exception:
        page.wait_for_timeout(5000)
    ok(f"[Login] Logged in → {page.url}")
    page.wait_for_timeout(3000)
    dismiss_popups(page, timeout=10, sweeps=4)

    # Read and log credits
    try:
        page.goto("https://magiclight.ai/user-center", timeout=45000)
        page.wait_for_selector(".home-top-navbar-credit-amount, .credit-amount",
                                state="visible", timeout=15000)
        sleep_log(2, "user center settle")
    except Exception as e:
        warn(f"[credits] Could not load user center: {e}")
    total, _ = read_credits_from_page(page)
    if total > 0:
        credits_log_login(custom_email or EMAIL, total)
    try:
        page.goto("https://magiclight.ai/kids-story/", timeout=45000)
        wait_site_loaded(page, None, timeout=30)
    except Exception:
        pass
    return total


# ── Step helpers ──────────────────────────────────────────────────────────────
def _select_dropdown(page, label_text: str, option_text: str):
    js_open = """\
(label) => {
    for (const el of Array.from(document.querySelectorAll('label,div,span,p'))) {
        const own = Array.from(el.childNodes)
            .filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
        if (own !== label && (el.innerText || '').trim() !== label) continue;
        let c = el.parentElement;
        for (let i = 0; i < 6; i++) {
            if (!c) break;
            const t = c.querySelector('.arco-select-view,.arco-select-view-input,' +
                '[class*="select-view"],[class*="arco-select"]');
            if (t && t.getBoundingClientRect().width > 0) { t.click(); return label; }
            c = c.parentElement;
        }
    }
    return null;
}"""
    js_pick = """\
(opt) => {
    const items = Array.from(document.querySelectorAll(
        '.arco-select-option,[class*="select-option"],[class*="option-item"]'
    )).filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    for (const el of items)
        if ((el.innerText || '').trim() === opt) { el.click(); return opt; }
    return null;
}"""
    try:
        r = page.evaluate(js_open, label_text)
        if r:
            time.sleep(0.8)
            r2 = page.evaluate(js_pick, option_text)
            if r2:
                ok(f"{label_text} → {option_text}")
            else:
                page.keyboard.press("Escape")
                warn(f"'{option_text}' not in {label_text} dropdown")
        else:
            warn(f"{label_text} dropdown not found")
    except Exception as e:
        warn(f"Dropdown error: {e}")


def step1(page, story_text: str):
    info("[Step 1] Story input...")
    page.goto("https://magiclight.ai/kids-story/", timeout=60000)
    wait_site_loaded(page, None, timeout=60)
    dismiss_popups(page, timeout=10)
    ta = page.get_by_role("textbox", name="Please enter an original")
    wait_site_loaded(page, ta, timeout=60)
    dismiss_popups(page, timeout=6)
    ta.wait_for(state="visible", timeout=20000)
    ta.click()
    ta.fill(story_text)
    ok("Story text filled")
    sleep_log(1)
    try:
        page.locator("div").filter(has_text=re.compile(r"^Pixar\s*$")).first.click()
        ok("Style: Pixar")
    except Exception:
        warn("Pixar not found — default")
    try:
        page.locator("div").filter(has_text=re.compile(r"^16:9$")).first.click()
        ok("Aspect: 16:9")
    except Exception:
        warn("16:9 not found — default")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    sleep_log(1)
    _select_dropdown(page, "Voiceover", "Sophia")
    _select_dropdown(page, "Background Music", "Silica")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    sleep_log(1)
    clicked = False
    for sel in ["button.arco-btn-primary:has-text('Next')", "button:has-text('Next')",
                ".vlog-bottom", "div[class*='footer-btn']:has-text('Next')"]:
        try:
            el = page.locator(sel)
            if el.count() > 0 and el.first.is_visible():
                el.first.click()
                clicked = True
                break
        except Exception:
            pass
    if not clicked:
        clicked = dom_click_text(page, ["Next", "Next Step", "Continue"], timeout=20)
    if not clicked:
        raise Exception("Step 1 Next button not found")
    ok("Step 1 → Next")
    wait_dismissing(page, STEP1_WAIT, "AI generating script")


def step2(page):
    info(f"[Step 2] Cast generation ({STEP2_WAIT}s)...")
    dismiss_popups(page, timeout=5)
    wait_dismissing(page, STEP2_WAIT, "characters generating")
    dismiss_popups(page, timeout=5)
    clicked = False
    for sel in ["div[class*='step2-footer-btn-left']",
                "button:has-text('Next Step')",
                "div[class*='footer']:has-text('Next Step')"]:
        try:
            el = page.locator(sel)
            if el.count() > 0 and el.first.is_visible():
                el.first.click()
                clicked = True
                break
        except Exception:
            pass
    if not clicked:
        clicked = dom_click_text(page, ["Next Step", "Next", "Animate All"], timeout=30)
    sleep_log(4)
    dismiss_animation_modal(page)
    sleep_log(3)
    ok("[Step 2] Done")


def step3(page):
    info(f"[Step 3] Storyboard (up to {STEP3_WAIT}s)...")
    dismiss_popups(page, timeout=5)
    js_img = """\
() => document.querySelectorAll(
    '[class*="role-card"] img,[class*="scene"] img,' +
    '[class*="storyboard"] img,[class*="story-board"] img'
).length"""
    deadline = time.time() + STEP3_WAIT
    while time.time() < deadline:
        if is_shutdown(): break
        if page.evaluate(js_img) >= 2: break
        dismiss_all(page)
        time.sleep(5)
    sleep_log(3)
    _set_subtitle_style(page)
    clicked = False
    for sel in ["[class*='header'] button:has-text('Next')",
                "[class*='header-shiny-action__btn']:has-text('Next')",
                "div[class*='step2-footer-btn-left']"]:
        try:
            el = page.locator(sel)
            if el.count() > 0 and el.first.is_visible():
                el.first.click()
                clicked = True
                break
        except Exception:
            pass
    if not clicked:
        dom_click_text(page, ["Next", "Next Step"], timeout=15)

    sleep_log(3, "checking for Animate All popup")
    js_animate = """() => {
        for (let b of Array.from(document.querySelectorAll('button, div[class*="btn"]'))) {
            const t = (b.innerText || '').trim();
            if (t === 'Animate All') {
                const r = b.getBoundingClientRect();
                if (r.width > 0) { b.click(); return true; }
            }
        }
        return false;
    }"""
    if page.evaluate(js_animate):
        info("[Step 3] Clicked 'Animate All' — waiting for scenes...")
        start = time.time()
        last_pct = ""
        while time.time() - start < RENDER_TIMEOUT:
            if is_shutdown(): break
            prog_js = """() => {
                const prog = Array.from(document.querySelectorAll(
                    '[class*="progress"],[class*="Progress"],[class*="render-progress"],[class*="generating"]'
                )).find(el => el.getBoundingClientRect().width > 0 && (el.innerText||'').match(/[0-9]+\\s*%/));
                if (prog) {
                    const m = (prog.innerText||'').match(/(\\d+)\\s*%/);
                    return m ? m[1] : null;
                }
                const chk = document.body.innerText || '';
                if (chk.includes('have been generated') || !chk.includes('generating')) return 'DONE';
                return null;
            }"""
            res = page.evaluate(prog_js)
            if res and res != "DONE" and res != last_pct:
                console.print(f"  [cyan]>[/cyan] Scenes Animating... [bold]{res}%[/bold]")
                last_pct = res
            elif res == "DONE" or (not res and last_pct == "100"):
                break
            time.sleep(POLL_INTERVAL)
            try: page.evaluate("""\
() => {
    const BAD = ["Got it","Got It","Close","Done","OK","Later","No thanks"];
    document.querySelectorAll('button,span,div,a').forEach(el => {
        const t = (el.innerText||el.textContent||'').trim();
        if (BAD.includes(t)) { const r = el.getBoundingClientRect(); if(r.width>0) el.click(); }
    });
}""")
            except Exception: pass
        sleep_log(3, "scenes animated")
        for _ in range(3):
            if dom_click_text(page, ["Next"], timeout=5): break
            time.sleep(2)
    else:
        dismiss_animation_modal(page)
    sleep_log(3)
    ok("[Step 3] Done")


def _set_subtitle_style(page):
    for txt in ["Subtitle Settings", "Subtitle", "Caption"]:
        try:
            t = page.locator(f"text='{txt}'")
            if t.count() > 0 and t.first.is_visible():
                t.first.click()
                sleep_log(2)
                break
        except Exception:
            pass
    result = page.evaluate("""\
() => {
    let items = Array.from(document.querySelectorAll('.coverFontList-item'));
    if (!items.length) items = Array.from(document.querySelectorAll(
        '[class*="coverFont"] [class*="item"],[class*="subtitle-item"]'
    ));
    const vis = items.filter(el => { const r=el.getBoundingClientRect(); return r.width>5&&r.height>5; });
    if (vis.length >= 10) { vis[9].click(); return 'subtitle style #10 set'; }
    return 'only ' + vis.length + ' items';
}""")
    info(f"[step3] {result}")


def step4(page, safe_name: str, sheet_row_num: int = None) -> dict:
    info("[Step 4] Navigating to Generate...")
    js_header_next = """\
() => {
    for (const el of Array.from(document.querySelectorAll(
        '[class*="header-shiny-action__btn"],[class*="header-left-btn"]'
    ))) {
        const t = (el.innerText||'').trim();
        const r = el.getBoundingClientRect();
        if (t === 'Next' && r.width > 0) { el.click(); return 'header-shiny: Next'; }
    }
    for (const el of Array.from(document.querySelectorAll('button.arco-btn-primary'))) {
        const t = (el.innerText||'').trim();
        const r = el.getBoundingClientRect();
        if (t === 'Next' && r.width > 0) { el.click(); return 'arco-primary: Next'; }
    }
    return null;
}"""
    js_has_gen = """\
() => {
    const texts = ["Generate","Create Video","Export","Create now","Render"];
    for (let i = (document.querySelectorAll(
        'button,div[class*="btn"],span[class*="btn"],div[class*="footer-btn"],' +
        'div[class*="header-shiny-action__btn"]'
    )).length - 1; i >= 0; i--) {
        const el = Array.from(document.querySelectorAll(
            'button,div[class*="btn"],span[class*="btn"],div[class*="footer-btn"],' +
            'div[class*="header-shiny-action__btn"]'
        ))[i];
        let dt = '';
        el.childNodes.forEach(n => { if (n.nodeType === Node.TEXT_NODE) dt += n.textContent; });
        const t = dt.trim() || (el.innerText||'').trim();
        if (texts.includes(t)) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) return t + '|||' + el.className.substring(0,60);
        }
    }
    return null;
}"""
    for attempt in range(100):
        dismiss_animation_modal(page)
        sleep_log(2)
        raw = page.evaluate(js_has_gen)
        if raw:
            ok(f"Generate button found after {attempt} attempts")
            break
        blocking = page.evaluate("""\
() => {
    const masks = Array.from(document.querySelectorAll('.arco-modal-mask,[class*="modal-mask"]'))
        .filter(el => { const r=el.getBoundingClientRect(); return r.width>200&&r.height>200; });
    return masks.length ? 'mask' : null;
}""")
        if blocking:
            warn("Modal blocking — re-dismissing")
            dismiss_animation_modal(page)
            sleep_log(3)
            continue
        r = page.evaluate(js_header_next)
        info(f"[step4] attempt {attempt+1}: {r or 'no header Next'}")
        sleep_log(4)
    else:
        raise Exception("Could not reach Generate button")

    if not dom_click_text(page, ["Generate", "Create Video", "Export", "Create now"], timeout=20):
        raise Exception("Generate click failed")
    sleep_log(3)
    dom_click_text(page, ["OK", "Ok", "Confirm"], timeout=5)
    sleep_log(3)
    dismiss_all(page)

    info(f"[Step 4] Waiting for render (max {RENDER_TIMEOUT//60} min)...")
    start = time.time()
    last_reload = start
    render_done = False
    last_pct = ""
    js_state = r"""
() => {
    const prog = Array.from(document.querySelectorAll(
        '[class*="progress"],[class*="Progress"],[class*="render-progress"],[class*="generating"]'
    )).filter(el => { const r=el.getBoundingClientRect(); return r.width>0&&r.height>0&&(el.innerText||'').match(/[0-9]+\s*%/); });
    if (prog.length > 0) {
        const m = (prog[0].innerText||'').match(/(\d+)\s*%/);
        return 'progress:' + (m ? m[1] : '?') + '%';
    }
    const body = (document.body && document.body.innerText) || '';
    const kws = ['video has been generated','generation complete','successfully generated','video is ready','has been generated'];
    for (const k of kws) if (body.toLowerCase().includes(k.toLowerCase())) return 'text:' + k;
    const btns = Array.from(document.querySelectorAll('button,a,div[class*="btn"]'));
    for (const el of btns) {
        const t = (el.innerText||'').trim(); const r = el.getBoundingClientRect();
        if (r.width > 0 && (t==='Download video'||t==='Download Video'||t==='Download')) return 'btn:' + t;
    }
    return null;
}"""
    while time.time() - start < RENDER_TIMEOUT:
        if is_shutdown(): break
        elapsed = int(time.time() - start)
        if time.time() - last_reload >= RELOAD_INTERVAL:
            try:
                page.reload(timeout=30000, wait_until="domcontentloaded")
                wait_site_loaded(page, None, timeout=30)
                dismiss_all(page)
            except Exception as e:
                warn(f"Reload error: {e}")
            last_reload = time.time()
        dismiss_all(page)
        try:
            if page.is_closed(): break
            sig = page.evaluate(js_state)
        except Exception as e:
            warn(f"Page eval error: {e}")
            try:
                page.goto(page.url, timeout=30000)
                wait_site_loaded(page, None, timeout=30)
                dismiss_all(page)
                sig = page.evaluate(js_state)
            except Exception:
                err("Cannot recover — aborting render wait")
                break
        if sig is None:
            if elapsed % 30 == 0:
                info(f"[step4] {elapsed//60}m{elapsed%60}s elapsed")
        elif sig.startswith("progress:"):
            pct = sig.split(":", 1)[1]
            if pct != last_pct:
                console.print(f"  [cyan]>[/cyan] Rendering... [bold]{pct}[/bold]")
                last_pct = pct
        else:
            ok(f"Render done ({elapsed}s) → {sig}")
            render_done = True
            break
        time.sleep(POLL_INTERVAL)

    if not render_done:
        warn("Render timeout — attempting download anyway")
    sleep_log(3, "UI settle")

    popup_visible = page.evaluate("""\
() => {
    const body = (document.body && document.body.innerText) || '';
    return body.includes('has been generated') && body.includes('Submit');
}""")
    if popup_visible or render_done:
        _handle_generated_popup(page)
        sleep_log(3, "post-submit settle")
        _wait_for_preview_page(page, timeout=45)
    sleep_log(2)
    return _download(page, safe_name, sheet_row_num=sheet_row_num)


def _wait_for_preview_page(page, timeout: int = 60) -> bool:
    info("[post-render] Waiting for preview page...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_shutdown(): return False
        found = page.evaluate("""\
() => {
    const items = document.querySelectorAll('.previewer-new-body-right-item');
    const dlBtn = Array.from(document.querySelectorAll('button,a')).find(el => {
        const t = (el.innerText||'').trim(); const r = el.getBoundingClientRect();
        return r.width > 0 && (t==='Download video'||t==='Download Video');
    });
    return items.length > 0 || !!dlBtn;
}""")
        if found:
            ok("Preview page loaded")
            return True
        time.sleep(2)
    warn("Preview page timeout")
    return False


def _handle_generated_popup(page) -> bool:
    info("[post-render] Checking for generated popup...")
    submitted = False
    deadline = time.time() + 15
    while time.time() < deadline:
        for sel in ["button:has-text('Submit')", "button.arco-btn:has-text('Submit')",
                    ".arco-modal button:has-text('Submit')"]:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    ok("Submit clicked")
                    submitted = True
                    break
            except Exception:
                pass
        if submitted: break
        time.sleep(2)
    if submitted:
        sleep_log(4, "post-submit settle")
        _wait_for_preview_page(page, timeout=30)
    dl_deadline = time.time() + 30
    while time.time() < dl_deadline:
        for sel in ["button:has-text('Download video')", "a:has-text('Download video')",
                    "button:has-text('Download Video')", "a:has-text('Download Video')"]:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    ok("Download video clicked")
                    return True
            except Exception:
                pass
        time.sleep(2)
    warn("[post-render] Download video button not found")
    return False


def _download(page, safe_name: str, sheet_row_num: int = None) -> dict:
    out = {"video": "", "thumb": "", "gen_title": "", "summary": "", "tags": "",
           "drive_link": "", "drive_thumb": ""}
    sdir = story_dir(safe_name)
    meta = page.evaluate("""\
() => {
    const result = { title: '', summary: '', hashtags: '' };
    document.querySelectorAll('.previewer-new-body-right-item').forEach(item => {
        const label = (item.querySelector('.previewer-new-body-right-item-header-title')||{}).innerText||'';
        const ta    = item.querySelector('textarea.arco-textarea');
        const val   = ta ? (ta.value || ta.innerText || '').trim() : '';
        const key   = label.trim().toLowerCase();
        if (key === 'title')    result.title    = val;
        if (key === 'summary')  result.summary  = val;
        if (key === 'hashtags') result.hashtags = val;
    });
    return result;
}""") or {}
    out["gen_title"] = meta.get("title", "")
    out["summary"]   = meta.get("summary", "")
    out["tags"]      = meta.get("hashtags", "")

    cookies = {c["name"]: c["value"] for c in page.context.cookies()}
    headers = {"User-Agent": "Mozilla/5.0", "Referer": page.url}
    thumb_dest = os.path.join(sdir, f"{safe_name}_thumb.jpg")

    # Scroll to reveal thumbnail
    try:
        page.mouse.move(1000, 400)
        page.mouse.wheel(0, 3000)
        time.sleep(1)
        page.keyboard.press("PageDown")
        page.keyboard.press("PageDown")
        time.sleep(1)
        page.evaluate("""() => {
            document.querySelectorAll('*').forEach(el => {
                try {
                    const ov = window.getComputedStyle(el).overflowY;
                    if(ov==='auto'||ov==='scroll'||ov==='overlay') {
                        if(el.scrollHeight>el.clientHeight) el.scrollTop=el.scrollHeight;
                    }
                } catch(e){}
            });
            window.scrollTo(0, document.body.scrollHeight);
        }""")
        time.sleep(3)
    except Exception as e:
        warn(f"[thumb] Scroll warning: {e}")

    thumb_url = page.evaluate("""\
() => new Promise(async (resolve) => {
    function findImages(wrapper) {
        for (let img of Array.from(wrapper.querySelectorAll('img[src]'))) {
            let s = img.src.toLowerCase();
            if ((s.startsWith('http')||s.startsWith('blob:')||s.startsWith('data:'))
                && img.naturalWidth > 100
                && !s.includes('avatar') && !s.includes('icon') && !s.includes('logo'))
                return img.src;
        }
        return null;
    }
    let src = null;
    const dlBtn = document.querySelector('.show-cover-download');
    if (dlBtn) {
        let w = dlBtn;
        for (let i=0; i<4; i++) { if(!w) break; src=findImages(w); if(src) break; w=w.parentElement; }
    }
    if (!src) {
        for (const el of Array.from(document.querySelectorAll('div, span'))) {
            if ((el.innerText||'').trim().toLowerCase() === 'magic thumbnail') {
                let w = el;
                for (let i=0; i<4; i++) { if(!w) break; src=findImages(w); if(src) break; w=w.parentElement; }
                if(src) break;
            }
        }
    }
    if (!src) return resolve(null);
    if (src.startsWith('data:')) return resolve(src);
    try {
        const response = await window.fetch(src);
        const blob = await response.blob();
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.onerror = () => resolve(src);
        reader.readAsDataURL(blob);
    } catch(e) { resolve(src); }
})""")
    if thumb_url:
        try:
            content_bytes = None
            if thumb_url.startswith("data:"):
                import base64
                header, encoded = thumb_url.split(",", 1)
                content_bytes = base64.b64decode(encoded)
            elif thumb_url.startswith("http"):
                r = requests.get(thumb_url, timeout=30)
                if r.status_code == 200:
                    content_bytes = r.content
            if content_bytes and len(content_bytes) > 5000:
                with open(thumb_dest, "wb") as f: f.write(content_bytes)
                out["thumb"] = thumb_dest
                ok(f"Thumbnail → {thumb_dest} ({len(content_bytes)//1024} KB)")
        except Exception as e:
            warn(f"Thumbnail error: {e}")

    # Video download
    video_dest = os.path.join(sdir, f"{safe_name}.mp4")
    try:
        cancel_btn = page.locator('button', has_text="Cancel")
        if cancel_btn.count() > 0 and cancel_btn.first.is_visible(timeout=1000):
            cancel_btn.first.click(timeout=1000)
            sleep_log(1)
    except Exception:
        pass

    for sel in ["button:has-text('Download video')", "a:has-text('Download video')",
                "button:has-text('Download Video')", "a:has-text('Download Video')",
                "a[download]", "a[href*='.mp4']"]:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                with page.expect_download(timeout=180000) as dl_info:
                    loc.first.click()
                dl = dl_info.value
                dl.save_as(video_dest)
                if os.path.exists(video_dest) and os.path.getsize(video_dest) > 10000:
                    out["video"] = video_dest
                    ok(f"Video → {video_dest} ({os.path.getsize(video_dest)//1024} KB)")
                    break
        except Exception as e:
            warn(f"  {sel}: {e}")

    if not out["video"]:
        vid_url = page.evaluate("""\
() => {
    const v = document.querySelector('video');
    if (v && v.src && v.src.includes('.mp4')) return v.src;
    const s = document.querySelector('video source');
    if (s && s.src && s.src.includes('.mp4')) return s.src;
    const a = document.querySelector('a[href*=".mp4"]');
    if (a) return a.href;
    return null;
}""")
        if vid_url:
            try:
                r = requests.get(vid_url, stream=True, timeout=180,
                                  cookies=cookies, headers=headers)
                r.raise_for_status()
                total = 0
                with open(video_dest, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if chunk: f.write(chunk); total += len(chunk)
                if total > 10000:
                    out["video"] = video_dest
                    ok(f"Video (URL) → {video_dest} ({total//1024} KB)")
            except Exception as e:
                warn(f"Video URL download error: {e}")

    if not out["video"]:
        err("[dl] VIDEO DOWNLOAD FAILED")

    # Drive upload
    if out.get("video") and DRIVE_FOLDER_ID:
        try:
            drive_results = upload_story(
                safe_name, out["video"], out.get("thumb", ""),
                sheet_row_num=sheet_row_num
            )
            out["drive_link"]  = drive_results["video_link"]
            out["drive_thumb"] = drive_results["thumb_link"]
        except Exception as e:
            warn(f"Drive upload error: {e}")
    return out


def retry_from_user_center(page, project_url: str, safe_name: str):
    info("[retry] Opening User Center...")
    sleep_log(5, "pre-retry")
    try:
        page.goto("https://magiclight.ai/user-center/", timeout=60000)
        wait_site_loaded(page, None, timeout=45)
        sleep_log(4)
        dismiss_all(page)
    except Exception as e:
        warn(f"User Center failed: {e}")
        return None
    clicked = page.evaluate("""\
(targetUrl) => {
    if (targetUrl) {
        const parts = targetUrl.replace(/[/]+$/, '').split('/');
        const projId = parts[parts.length - 1];
        if (projId && projId.length > 5) {
            const match = Array.from(document.querySelectorAll('a[href]'))
                .find(a => a.href && a.href.includes(projId));
            if (match && match.getBoundingClientRect().width > 0) {
                match.click(); return 'matched ID: ' + projId;
            }
        }
    }
    const editLinks = Array.from(document.querySelectorAll('a[href*="/project/edit/"],a[href*="/edit/"]'))
        .filter(a => a.getBoundingClientRect().width > 0);
    if (editLinks.length) { editLinks[0].click(); return 'edit-link'; }
    return null;
}""", project_url or "")
    if not clicked:
        if project_url and "/project/" in project_url:
            try:
                page.goto(project_url, timeout=60000)
                wait_site_loaded(page, None, timeout=30)
                sleep_log(3)
                dismiss_all(page)
                _handle_generated_popup(page)
                sleep_log(2)
                return _download(page, safe_name)
            except Exception as e:
                warn(f"Direct goto failed: {e}")
        warn("[retry] Could not find project")
        return None
    ok(f"[retry] Project opened ({clicked})")
    sleep_log(5)
    wait_site_loaded(page, None, 30)
    dismiss_all(page)
    _handle_generated_popup(page)
    sleep_log(2)
    try:
        return _download(page, safe_name)
    except Exception as e:
        warn(f"[retry] Download failed: {e}")
        return None
