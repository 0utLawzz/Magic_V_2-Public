"""
browser_utils.py — Playwright browser/page helpers
Popup dismissal, sleep helpers, DOM click utilities, screenshots
"""

import os
import re
import time
import signal

from modules.console_utils import ok, warn, info, dbg, console

# ── Global state ──────────────────────────────────────────────────────────────
_shutdown = False
_browser  = None


def get_browser():
    return _browser


def set_browser(b):
    global _browser
    _browser = b


def is_shutdown():
    return _shutdown


def close_browser():
    global _browser
    if _browser:
        try:
            for ctx in _browser.contexts:
                try:
                    for p in ctx.pages:
                        p.close()
                except Exception:
                    pass
                ctx.close()
            _browser.close()
            _browser = None
            ok("[browser] Browser closed")
        except Exception as e:
            warn(f"[browser] Close error: {e}")


def _sig(sig, frame):
    global _shutdown
    warn("[STOP] Ctrl+C — cleaning up...")
    _shutdown = True
    close_browser()
    import os as _os
    _os._exit(1)


signal.signal(signal.SIGINT, _sig)


# ── Sleep helpers ─────────────────────────────────────────────────────────────
def sleep_log(seconds: int, reason: str = ""):
    secs = int(seconds)
    if secs <= 0:
        return
    label = f" ({reason})" if reason else ""
    info(f"[wait] {secs}s{label}...")
    for _ in range(secs):
        if _shutdown:
            return
        time.sleep(1)


def wait_dismissing(page, seconds: int, reason: str = ""):
    label = f" ({reason})" if reason else ""
    info(f"[wait] {seconds}s{label} (popup-watch)...")
    start    = time.time()
    last_pct = ""
    while time.time() - start < seconds:
        if _shutdown:
            return
        pct = min(100, int((time.time() - start) / seconds * 100))
        if str(pct) != last_pct and pct % 5 == 0:
            console.print(f"  [cyan]>[/cyan] Waiting{label}... [bold]{pct}%[/bold]")
            last_pct = str(pct)
        dismiss_all(page)
        time.sleep(1)


# ── Popup JS ──────────────────────────────────────────────────────────────────
_CLOSE_SELECTORS = [
    'button.notice-popup-modal__close',
    'button[aria-label="close"]',
    'button[aria-label="Close"]',
    '.sora2-modal-close',
    'button:has-text("Got it")',
    'button:has-text("Got It")',
    'button:has-text("Later")',
    'button:has-text("Not now")',
    'button:has-text("No thanks")',
    '.notice-bar__close',
    '.arco-modal-close-btn',
    '.arco-icon-close',
    'button.arco-btn-secondary:has-text("Cancel")',
    'button:has-text("Skip")',
    'button.close-btn',
    'span[class*="close"]',
]

_PROMO_CLOSE_JS = """\
() => {
    const promoClose = Array.from(document.querySelectorAll(
        '[class*="privilege-modal"] [class*="close"],' +
        '[class*="new-year"] [class*="close"],' +
        '[class*="promo"] [class*="close"],' +
        '[class*="upgrade"] [class*="close"],' +
        '.arco-modal-close-btn'
    )).filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    if (promoClose.length) { promoClose[0].click(); return 'promo-closed'; }
    const svgBtns = Array.from(document.querySelectorAll(
        '.arco-modal .arco-modal-close-btn, .arco-modal-close-btn'
    )).filter(el => el.getBoundingClientRect().width > 0);
    if (svgBtns.length) { svgBtns[0].click(); return 'modal-x-closed'; }
    return null;
}"""

_POPUP_JS = """\
() => {
    const BAD = ["Got it","Got It","Close","Done","OK","Later","No thanks",
                 "Maybe later","Not now","Dismiss","Close samples","No","Cancel","Skip"];
    let n = 0;
    document.querySelectorAll('button,span,div,a').forEach(el => {
        const t = (el.innerText || el.textContent || '').trim();
        if (BAD.includes(t)) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) { el.click(); n++; }
        }
    });
    document.querySelectorAll(
        '.arco-modal-mask,.driver-overlay,.diy-tour__mask,[class*="tour-mask"],[class*="modal-mask"]'
    ).forEach(el => { try { el.style.display='none'; } catch(e){} });
    return n;
}"""

_REAL_DIALOG_JS = """\
() => {
    const masks = Array.from(document.querySelectorAll(
        '.arco-modal-mask,[class*="modal-mask"]'
    )).filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 100 && r.height > 100;
    });
    if (!masks.length) return null;
    const chk = Array.from(document.querySelectorAll(
        'input[type="checkbox"],.arco-checkbox-icon,label[class*="checkbox"]'
    )).find(el => {
        const par = el.closest('label') || el.parentElement;
        const txt = ((par && par.innerText) || el.innerText || '').toLowerCase();
        return txt.includes('remind') || txt.includes('again') || txt.includes('ask');
    });
    if (chk) { try { chk.click(); } catch(e) {} }
    const xBtn = document.querySelector(
        '.arco-modal-close-btn,[aria-label="Close"],[aria-label="close"],' +
        '.arco-icon-close,[class*="modal-close"],[class*="close-icon"]'
    );
    if (xBtn && xBtn.getBoundingClientRect().width > 0) {
        xBtn.click(); return 'dialog: closed X';
    }
    const wrapper = document.querySelector('.arco-modal-wrapper');
    if (wrapper) {
        wrapper.remove();
        masks.forEach(m => m.remove());
        return 'dialog: removed wrapper';
    }
    return 'dialog: mask found but no X';
}"""


def dismiss_all(page):
    try: page.evaluate(_PROMO_CLOSE_JS)
    except Exception: pass
    try: page.evaluate(_POPUP_JS)
    except Exception: pass
    for sel in _CLOSE_SELECTORS:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=1000)
        except Exception:
            pass


def dismiss_popups(page, timeout: int = 10, sweeps: int = 3):
    for _ in range(sweeps):
        if _shutdown:
            return
        dismiss_all(page)
        try:
            page.wait_for_timeout(800)
        except Exception:
            time.sleep(0.8)


def dismiss_animation_modal(page):
    try: page.evaluate(_PROMO_CLOSE_JS)
    except Exception: pass
    try:
        r = page.evaluate(_REAL_DIALOG_JS)
        if r:
            info(f"[modal] {r}")
            time.sleep(2)
            return
    except Exception: pass
    for sel in ["label:has-text(\"Don't remind again\")",
                "label:has-text(\"Don't ask again\")"]:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=1500)
                time.sleep(0.5)
        except Exception:
            pass
    for sel in ['.arco-modal-close-btn', 'button[aria-label="Close"]', '.arco-icon-close']:
        try:
            loc = page.locator(sel).first
            if loc.is_visible():
                loc.click(timeout=2000)
                time.sleep(2)
                return
        except Exception:
            pass
    try: page.keyboard.press("Escape"); time.sleep(0.5)
    except Exception: pass


# ── DOM helpers ───────────────────────────────────────────────────────────────
def wait_site_loaded(page, key_locator=None, timeout: int = 60) -> bool:
    try: page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
    except Exception: pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _shutdown:
            return False
        try:
            if page.evaluate("document.readyState") in ("interactive", "complete"):
                break
        except Exception:
            pass
        time.sleep(0.3)
    if key_locator is not None:
        try:
            key_locator.wait_for(
                state="visible",
                timeout=max(1000, int((deadline - time.time()) * 1000))
            )
        except Exception:
            return False
    return True


def dom_click_text(page, texts: list[str], timeout: int = 60) -> bool:
    js = """\
(texts) => {
    const all = Array.from(document.querySelectorAll(
        'button,div[class*="btn"],span[class*="btn"],a,' +
        'div[class*="vlog-btn"],div[class*="footer-btn"],' +
        'div[class*="shiny-action"],div[class*="header-left-btn"]'
    ));
    for (let i = all.length - 1; i >= 0; i--) {
        const el = all[i]; let dt = '';
        el.childNodes.forEach(n => { if (n.nodeType === Node.TEXT_NODE) dt += n.textContent; });
        const t = dt.trim() || (el.innerText || '').trim();
        if (texts.includes(t)) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) { el.click(); return t; }
        }
    }
    return null;
}"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _shutdown:
            return False
        r = page.evaluate(js, texts)
        if r:
            info(f"  clicked '{r}'")
            return True
        time.sleep(2)
    return False


def screenshot(page, name: str) -> str:
    from modules.config import OUT_SHOTS
    path = os.path.join(OUT_SHOTS, f"{name}_{int(time.time())}.png")
    try: page.screenshot(path=path, full_page=True)
    except Exception: pass
    return path


def credit_exhausted(page) -> bool:
    try:
        body = page.evaluate("() => (document.body && document.body.innerText) || ''")
        for kw in ["insufficient credits", "not enough credits", "out of credits",
                   "credits exhausted", "quota exceeded"]:
            if kw in body.lower():
                return True
    except Exception:
        pass
    return False


def read_credits_from_page(page) -> tuple[int, int]:
    try:
        credit_text = None
        for sel in [".home-top-navbar-credit-amount", ".credit-amount",
                    "[class*='credit']"]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    t = el.inner_text().strip()
                    if t and any(c.isdigit() for c in t):
                        credit_text = t
                        break
            except Exception:
                continue
        if credit_text:
            m = re.search(r"(\d+)", credit_text.replace(",", ""))
            if m:
                return int(m.group(1)), 0
    except Exception as e:
        warn(f"[credits] Read error: {e}")
    return 0, 0
