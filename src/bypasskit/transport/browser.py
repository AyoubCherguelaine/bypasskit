import random
import time
from ..errors import TransportError
from .base import Response
from .stealth import INIT_JS, HUMAN_MOUSE_JS


class BrowserTransport:
    name = "browser"

    def __init__(self, profile, user_data_dir, headless=True, timeout=45.0):
        self.profile = profile
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.timeout = timeout
        self._pw = self._ctx = self._page = None

    def _ensure(self, proxy=None):
        if self._page:
            return
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        w, h = self.profile.viewport
        opts = dict(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            viewport={"width": w, "height": h},
            locale=self.profile.locale,
            timezone_id=self.profile.timezone,
            user_agent=self.profile.user_agent,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        if proxy:
            opts["proxy"] = {"server": proxy}
        try:
            self._ctx = self._pw.chromium.launch_persistent_context(channel="chrome", **opts)
        except Exception:
            self._ctx = self._pw.chromium.launch_persistent_context(**opts)
        self._ctx.add_init_script(INIT_JS)
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

    def send(self, url, method="GET", *, headers=None, data=None, json=None,
             referer=None, proxy=None) -> Response:
        self._ensure(proxy)
        t0 = time.monotonic()
        try:
            if method.upper() == "GET" and data is None and json is None:
                r = self._page.goto(
                    url,
                    wait_until="domcontentloaded",
                    referer=referer,
                    timeout=self.timeout * 1000,
                )
                try:
                    self._page.evaluate(
                        HUMAN_MOUSE_JS,
                        [random.randint(100, 900), random.randint(100, 700)],
                    )
                except Exception:
                    pass
                body = self._page.content()
                hdrs = dict(r.headers) if r else {}
                return Response(
                    r.status if r else 0,
                    hdrs,
                    body,
                    self._page.url,
                    time.monotonic() - t0,
                    self.name,
                )
            req_opts = {"method": method, "timeout": self.timeout * 1000}
            if headers:
                req_opts["headers"] = headers
            if json is not None:
                req_opts["data"] = json
            elif data is not None:
                req_opts["data"] = data
            r = self._ctx.request.fetch(url, **req_opts)
            return Response(
                r.status,
                dict(r.headers),
                r.text(),
                r.url,
                time.monotonic() - t0,
                self.name,
            )
        except Exception as e:
            raise TransportError(str(e)) from e

    def wait_clear(self, seconds=25.0) -> bool:
        if not self._page:
            return False
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                if "just a moment" not in self._page.content().lower():
                    return True
            except Exception:
                pass
            time.sleep(1.0)
        return False

    def click_turnstile(self) -> bool:
        if not self._page:
            return False
        for f in self._page.frames:
            if "challenges.cloudflare.com" in f.url:
                try:
                    f.click("body", timeout=4000)
                    return True
                except Exception:
                    pass
        return False

    def inject_cookies(self, cookies: dict, domain: str | None = None):
        if not cookies or not domain:
            return
        self._ensure()
        url = f"https://{domain}/"
        items = []
        for k, v in cookies.items():
            val = v["value"] if isinstance(v, dict) else v
            items.append({"name": k, "value": val, "url": url})
        self._ctx.add_cookies(items)

    def cookies(self) -> dict:
        if not self._ctx:
            return {}
        return {c["name"]: c["value"] for c in self._ctx.cookies()}

    def close(self):
        try:
            if self._ctx:
                self._ctx.close()
            if self._pw:
                self._pw.stop()
        finally:
            self._pw = self._ctx = self._page = None


    def send(self, url, method="GET", *, headers=None, data=None, json=None,
             referer=None, proxy=None) -> Response:
        self._ensure(proxy)
        t0 = time.monotonic()
        try:
            if method.upper() == "GET" and data is None and json is None:
                r = self._page.goto(
                    url,
                    wait_until="domcontentloaded",
                    referer=referer,
                    timeout=self.timeout * 1000,
                )
                try:
                    self._page.evaluate(
                        HUMAN_MOUSE_JS,
                        [random.randint(100, 900), random.randint(100, 700)],
                    )
                except Exception:
                    pass
                body = self._page.content()
                hdrs = dict(r.headers) if r else {}
                return Response(
                    r.status if r else 0,
                    hdrs,
                    body,
                    self._page.url,
                    time.monotonic() - t0,
                    self.name,
                )
            req_opts = {"method": method, "timeout": self.timeout * 1000}
            if headers:
                req_opts["headers"] = headers
            if json is not None:
                req_opts["data"] = json
            elif data is not None:
                req_opts["data"] = data
            r = self._ctx.request.fetch(url, **req_opts)
            return Response(
                r.status,
                dict(r.headers),
                r.text(),
                r.url,
                time.monotonic() - t0,
                self.name,
            )
        except Exception as e:
            raise TransportError(str(e)) from e

    def wait_clear(self, seconds=25.0) -> bool:
        if not self._page:
            return False
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                if "just a moment" not in self._page.content().lower():
                    return True
            except Exception:
                pass
            time.sleep(1.0)
        return False

    def click_turnstile(self) -> bool:
        if not self._page:
            return False
        for f in self._page.frames:
            if "challenges.cloudflare.com" in f.url:
                try:
                    f.click("body", timeout=4000)
                    return True
                except Exception:
                    pass
        return False

    def inject_cookies(self, cookies: dict, domain: str | None = None):
        if not cookies or not domain:
            return
        self._ensure()
        url = f"https://{domain}/"
        items = []
        for k, v in cookies.items():
            val = v["value"] if isinstance(v, dict) else v
            items.append({"name": k, "value": val, "url": url})
        self._ctx.add_cookies(items)

    def cookies(self) -> dict:
        if not self._ctx:
            return {}
        return {c["name"]: c["value"] for c in self._ctx.cookies()}

    def close(self):
        try:
            if self._ctx:
                self._ctx.close()
            if self._pw:
                self._pw.stop()
        finally:
            self._pw = self._ctx = self._page = None