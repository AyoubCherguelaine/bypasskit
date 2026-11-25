import random, time
from ..errors import TransportError
from .base import Response
from .stealth import INIT_JS, HUMAN_MOUSE_JS

class BrowserTransport:
    name = "browser"

    def __init__(self, profile, headless=True, timeout=45.0):
        self.profile = profile
        self.headless = headless
        self.timeout = timeout
        self._pw = None
        self._ctx = None
        self._page = None

    def _ensure(self, proxy=None):
        if self._page:
            return
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        w, h = self.profile.viewport
        opts = dict(headless=self.headless, viewport={"width": w, "height": h},
                    locale=self.profile.locale, timezone_id=self.profile.timezone,
                    user_agent=self.profile.user_agent)
        if proxy:
            opts["proxy"] = {"server": proxy}
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=f"/tmp/bk-{random.randint(1, 1 << 30)}",
            channel="chrome", args=["--disable-blink-features=AutomationControlled"], **opts)
        self._ctx.add_init_script(INIT_JS)
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

    def send(self, url, method="GET", *, headers=None, data=None, json=None,
             referer=None, proxy=None) -> Response:
        self._ensure(proxy)
        t0 = time.monotonic()
        try:
            if referer:
                self._page.goto(referer, wait_until="domcontentloaded")
            r = self._page.goto(url, wait_until="domcontentloaded",
                                referer=referer, timeout=self.timeout * 1000)
            self._page.evaluate(HUMAN_MOUSE_JS, [random.randint(100, 900), random.randint(100, 700)])
            body = self._page.content()
            hdrs = dict(r.headers) if r else {}
            return Response(r.status if r else 0, hdrs, body, self._page.url,
                            time.monotonic() - t0, self.name)
        except Exception as e:
            raise TransportError(str(e)) from e

    def wait_clear(self, seconds=25.0) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if "just a moment" not in self._page.content().lower():
                return True
            time.sleep(1.0)
        return False

    def click_turnstile(self) -> bool:
        for f in self._page.frames:
            if "challenges.cloudflare.com" in f.url:
                try:
                    f.click("body", timeout=4000)
                    return True
                except Exception:
                    pass
        return False

    def inject_cookies(self, cookies: dict):
        if not cookies:
            return
        self._ensure()
        self._ctx.add_cookies([{"name": k, "value": v,
                                "domain": ".", "path": "/"} for k, v in cookies.items()])

    def cookies(self) -> dict:
        if not self._ctx:
            return {}
        return {c["name"]: c["value"] for c in self._ctx.cookies()}

    def close(self):
        try:
            if self._ctx: self._ctx.close()
            if self._pw: self._pw.stop()
        finally:
            self._pw = self._ctx = self._page = None