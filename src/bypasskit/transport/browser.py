import json as _json
import logging
import random
import time
from urllib.parse import urlencode, urlsplit
from ..errors import TransportError
from .base import Response
from .stealth import INIT_JS

_log = logging.getLogger(__name__)
_warned_chrome_fallback = False

_IN_PAGE_FETCH_JS = """
async ({url, method, headers, body}) => {
  const opts = {method, credentials: 'include'};
  if (headers && Object.keys(headers).length) opts.headers = headers;
  if (body !== null && body !== undefined) opts.body = body;
  const r = await fetch(url, opts);
  const hdrs = {};
  r.headers.forEach((v, k) => { hdrs[k] = v; });
  return {status: r.status, headers: hdrs, body: await r.text(), url: r.url};
}
"""


class BrowserTransport:
    name = "browser"

    def __init__(self, profile, user_data_dir, headless=True, timeout=45.0):
        self.profile = profile
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.timeout = timeout
        self._pw = self._ctx = self._page = None

    def _ensure(self, proxy=None):
        global _warned_chrome_fallback
        if self._page:
            return
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        ctx = None
        try:
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
                ctx = pw.chromium.launch_persistent_context(channel="chrome", **opts)
            except Exception as e:
                if not _warned_chrome_fallback:
                    _log.warning(
                        "Chrome channel unavailable (%s); falling back to bundled Chromium. "
                        "Run `playwright install chrome chromium` for best results.",
                        e,
                    )
                    _warned_chrome_fallback = True
                ctx = pw.chromium.launch_persistent_context(**opts)
            ctx.add_init_script(INIT_JS)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
        except Exception:
            try:
                if ctx:
                    ctx.close()
            finally:
                try:
                    pw.stop()
                except Exception:
                    pass
            raise

        self._pw = pw
        self._ctx = ctx
        self._page = page

    def _same_origin(self, url: str) -> bool:
        if not self._page:
            return False
        cur = urlsplit(self._page.url)
        tgt = urlsplit(url)
        return (
            cur.scheme in ("http", "https")
            and cur.scheme == tgt.scheme
            and cur.netloc == tgt.netloc
        )

    def send(self, url, method="GET", *, headers=None, data=None, json=None,
             referer=None, proxy=None) -> Response:
        self._ensure(proxy)
        t0 = time.monotonic()
        try:
            if method.upper() == "GET" and data is None and json is None:
                if headers:
                    self._page.set_extra_http_headers(headers)
                try:
                    r = self._page.goto(
                        url,
                        wait_until="domcontentloaded",
                        referer=referer,
                        timeout=self.timeout * 1000,
                    )
                finally:
                    if headers:
                        self._page.set_extra_http_headers({})
                try:
                    self._page.mouse.move(
                        random.randint(100, 900),
                        random.randint(100, 700),
                        steps=25,
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

            req_headers = dict(headers) if headers else {}
            if referer:
                req_headers.setdefault("Referer", referer)

            payload = None
            if json is not None:
                payload = _json.dumps(json)
                req_headers.setdefault("Content-Type", "application/json")
            elif data is not None:
                if isinstance(data, dict):
                    payload = urlencode(data)
                    req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
                else:
                    payload = data

            if not self._same_origin(url):
                tgt = urlsplit(url)
                if tgt.scheme in ("http", "https") and tgt.netloc:
                    self._page.goto(
                        f"{tgt.scheme}://{tgt.netloc}/",
                        wait_until="domcontentloaded",
                        timeout=self.timeout * 1000,
                    )

            if self._same_origin(url):
                res = self._page.evaluate(
                    _IN_PAGE_FETCH_JS,
                    {
                        "url": url,
                        "method": method.upper(),
                        "headers": req_headers,
                        "body": payload,
                    },
                )
                return Response(
                    res["status"],
                    res["headers"],
                    res["body"],
                    res["url"],
                    time.monotonic() - t0,
                    self.name,
                )

            req_opts = {"method": method, "timeout": self.timeout * 1000}
            if req_headers:
                req_opts["headers"] = req_headers
            if payload is not None:
                req_opts["data"] = payload
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

    def export_cookies(self) -> dict[str, dict]:
        if not self._ctx:
            return {}
        out = {}
        for c in self._ctx.cookies():
            entry: dict = {"value": c["value"]}
            exp = c.get("expires")
            if exp and exp > 0:
                entry["exp"] = float(exp)
            out[c["name"]] = entry
        return out

    def close(self):
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            self._ctx = self._page = None
            try:
                if self._pw:
                    self._pw.stop()
            finally:
                self._pw = None
