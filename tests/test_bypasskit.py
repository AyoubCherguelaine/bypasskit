import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from bypasskit import (
    BlockedError,
    ChallengeUnresolved,
    DomainPolicy,
    PolicyMap,
    Session,
)
from bypasskit.challenge.detect import Challenge, detect
from bypasskit.cooldown import Cooldown
from bypasskit.fingerprint.profiles import CHROME
from bypasskit.proxy.pool import ProxyPool
from bypasskit.state import StateStore
from bypasskit.transport.base import Response
from bypasskit.transport.browser import BrowserTransport
from bypasskit.transport.http import HttpTransport


class TestStateStore(unittest.TestCase):
    def test_cookies_filter_expired_and_return_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(tmp)
            now = time.time()
            store.update(
                "example.com",
                cookies={
                    "valid": {"value": "abc", "exp": now + 60},
                    "session": {"value": "sess"},
                    "expired": {"value": "old", "exp": now - 10},
                },
            )
            self.assertEqual(
                store.cookies("example.com"),
                {"valid": "abc", "session": "sess"},
            )
            leftovers = [f for f in os.listdir(tmp) if f.endswith(".tmp")]
            self.assertEqual(leftovers, [])


class TestChallengeDetect(unittest.TestCase):
    def test_detect_variants(self):
        self.assertEqual(detect(200, {}, "<html>ok</html>", "https://x.com"), Challenge.NONE)
        self.assertEqual(detect(200, {}, "Hold on, just a moment please", "https://x.com"), Challenge.NONE)
        self.assertEqual(detect(200, {}, "window.__cf_chl_opt={}", "https://x.com"), Challenge.CF_JS)
        self.assertEqual(detect(429, {}, "slow down", "https://x.com"), Challenge.RATE_LIMIT)
        self.assertEqual(
            detect(403, {"cf-mitigated": "challenge"}, "just a moment", "https://x.com"),
            Challenge.CF_JS,
        )
        self.assertEqual(
            detect(403, {"cf-mitigated": "challenge"}, "challenges.cloudflare.com", "https://x.com"),
            Challenge.CF_TURNSTILE,
        )
        self.assertEqual(detect(403, {}, "captcha-delivery.com", "https://x.com"), Challenge.DATADOME)
        self.assertEqual(detect(403, {}, "px-captcha", "https://x.com"), Challenge.PERIMETERX)
        self.assertEqual(detect(403, {}, "Reference #18.abc", "https://x.com"), Challenge.AKAMAI)
        self.assertEqual(detect(200, {}, '<div class="g-recaptcha">', "https://x.com"), Challenge.RECAPTCHA)
        self.assertEqual(detect(403, {}, "forbidden", "https://x.com"), Challenge.UNKNOWN)


class TestResponse(unittest.TestCase):
    def test_repr_omits_body(self):
        r = Response(200, {}, "secret-body-text", "https://x.com", 0.1, "http")
        rep = repr(r)
        self.assertIn("status=200", rep)
        self.assertIn("body_len=16", rep)
        self.assertNotIn("secret-body-text", rep)


class TestCooldown(unittest.TestCase):
    def test_failed_uses_short_backoff(self):
        cd = Cooldown()
        t0 = time.monotonic()
        cd.failed("example.com")
        delta = cd._until["example.com"] - t0
        self.assertGreaterEqual(delta, 0.9)
        self.assertLessEqual(delta, 4.1)


class TestProxyPool(unittest.TestCase):
    def test_empty_pool_returns_none_and_exhausted_raises_blocked(self):
        empty = ProxyPool()
        self.assertIsNone(empty.pick())

        pool = ProxyPool(["http://p1:8080"])
        for _ in range(10):
            pool.report("http://p1:8080", ok=False)
        with self.assertRaises(BlockedError):
            pool.pick()


class TestHttpTransport(unittest.TestCase):
    def test_inject_cookies_accepts_str_and_dict(self):
        tr = HttpTransport(CHROME)
        try:
            tr.inject_cookies({"a": "1", "b": {"value": "2", "exp": time.time() + 60}})
            cookies = tr.cookies()
            self.assertEqual(cookies.get("a"), "1")
            self.assertEqual(cookies.get("b"), "2")
        finally:
            tr.close()


class TestBrowserTransport(unittest.TestCase):
    def test_json_post_uses_dumps_and_content_type(self):
        tr = BrowserTransport(CHROME, "/tmp/unused")
        fake_res = MagicMock(status=200, headers={"content-type": "application/json"}, url="https://api.x.com/v1")
        fake_res.text.return_value = '{"ok":true}'
        tr._page = MagicMock(url="about:blank")
        tr._ctx = MagicMock()
        tr._ctx.request.fetch.return_value = fake_res

        resp = tr.send("https://api.x.com/v1", method="POST", json={"page": 1})
        self.assertEqual(resp.status, 200)
        _, kwargs = tr._ctx.request.fetch.call_args
        self.assertEqual(kwargs["data"], json.dumps({"page": 1}))
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")

    def test_same_origin_form_post_uses_in_page_fetch(self):
        tr = BrowserTransport(CHROME, "/tmp/unused")
        tr._page = MagicMock(url="https://api.x.com/home")
        tr._page.evaluate.return_value = {
            "status": 200,
            "headers": {"content-type": "application/json"},
            "body": '{"ok":true}',
            "url": "https://api.x.com/v1",
        }
        tr._ctx = MagicMock()

        resp = tr.send("https://api.x.com/v1", method="POST", data={"a": "1", "b": "2"})
        self.assertEqual(resp.status, 200)
        tr._ctx.request.fetch.assert_not_called()
        _, arg = tr._page.evaluate.call_args[0]
        self.assertEqual(arg["body"], "a=1&b=2")
        self.assertEqual(arg["headers"]["Content-Type"], "application/x-www-form-urlencoded")

    def test_close_stops_pw_even_if_ctx_close_raises(self):
        tr = BrowserTransport(CHROME, "/tmp/unused")
        ctx = MagicMock()
        ctx.close.side_effect = RuntimeError("ctx close failed")
        pw = MagicMock()
        tr._ctx = ctx
        tr._pw = pw
        tr._page = MagicMock()

        with self.assertRaises(RuntimeError):
            tr.close()
        pw.stop.assert_called_once()
        self.assertIsNone(tr._ctx)
        self.assertIsNone(tr._pw)
        self.assertIsNone(tr._page)


class _FakeTransport:
    def __init__(self, name, responses):
        self.name = name
        self._responses = list(responses)
        self._cookies = {}
        self.closed = False
        self.calls = []

    def send(self, url, method="GET", *, headers=None, data=None, json=None, referer=None, proxy=None):
        self.calls.append((url, method, referer, proxy))
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def inject_cookies(self, cookies, domain=None):
        self._cookies.update(cookies)

    def cookies(self):
        return dict(self._cookies)

    def close(self):
        self.closed = True


class TestSession(unittest.TestCase):
    def test_escalation_from_http_to_browser_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            pol = PolicyMap()
            pol.set("example.com", DomainPolicy(ladder=("http", "browser"), max_attempts=3, min_delay=0.0, max_delay=0.0))

            http_tr = _FakeTransport(
                "http",
                [
                    Response(200, {}, "home", "https://example.com/", 0.1, "http"),  # warm-up
                    Response(403, {"cf-mitigated": "challenge"}, "just a moment", "https://example.com/p", 0.1, "http"),
                ],
            )
            browser_tr = _FakeTransport(
                "browser",
                [
                    Response(200, {}, "ok page", "https://example.com/p", 0.2, "browser"),
                ],
            )
            browser_tr._cookies = {"cf_clearance": "xyz"}

            with patch("bypasskit.session.HttpTransport", return_value=http_tr), \
                 patch("bypasskit.session.BrowserTransport", return_value=browser_tr):
                with Session(policies=pol, state=tmp, proxies=["http://p1:8080"]) as s:
                    resp = s.fetch("https://example.com/p")
                    self.assertEqual(resp.status, 200)
                    self.assertEqual(resp.transport, "browser")
                    self.assertEqual(resp.challenge, Challenge.NONE)
                    self.assertEqual(http_tr.cookies().get("cf_clearance"), "xyz")
                    # Warm-up set referer for the subsequent request
                    self.assertEqual(http_tr.calls[1][2], "https://example.com/")

            self.assertTrue(http_tr.closed)
            self.assertTrue(browser_tr.closed)

    def test_200_recaptcha_returns_response_with_challenge_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            pol = PolicyMap()
            pol.set("example.com", DomainPolicy(ladder=("http",), max_attempts=2, min_delay=0.0, max_delay=0.0))

            http_tr = _FakeTransport(
                "http",
                [
                    Response(200, {}, "home", "https://example.com/", 0.1, "http"),
                    Response(200, {}, '<form><div class="g-recaptcha"></div></form>', "https://example.com/login", 0.1, "http"),
                ],
            )

            with patch("bypasskit.session.HttpTransport", return_value=http_tr):
                with Session(policies=pol, state=tmp) as s:
                    resp = s.fetch("https://example.com/login")
                    self.assertEqual(resp.status, 200)
                    self.assertEqual(resp.challenge, Challenge.RECAPTCHA)

    def test_warmup_exception_is_caught_and_raises_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            pol = PolicyMap()
            pol.set("example.com", DomainPolicy(ladder=("http",), max_attempts=2, min_delay=0.0, max_delay=0.0))

            http_tr = _FakeTransport("http", [RuntimeError("boom"), RuntimeError("boom")])

            with patch("bypasskit.session.HttpTransport", return_value=http_tr), \
                 patch("bypasskit.cooldown.time.sleep"):
                with Session(policies=pol, state=tmp) as s:
                    with self.assertRaises(ChallengeUnresolved):
                        s.fetch("https://example.com/p")
            self.assertEqual(len(http_tr.calls), 2)


if __name__ == "__main__":
    unittest.main()
