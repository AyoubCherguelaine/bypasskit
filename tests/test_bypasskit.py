import tempfile
import time
import unittest
from unittest.mock import patch

from bypasskit import DomainPolicy, PolicyMap, Session, ChallengeUnresolved
from bypasskit.challenge.detect import Challenge, detect
from bypasskit.fingerprint.profiles import CHROME
from bypasskit.state import StateStore
from bypasskit.transport.base import Response
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
                    "expired": {"value": "old", "exp": now - 10},
                },
            )
            self.assertEqual(store.cookies("example.com"), {"valid": "abc"})


class TestChallengeDetect(unittest.TestCase):
    def test_detect_variants(self):
        self.assertEqual(detect(200, {}, "<html>ok</html>", "https://x.com"), Challenge.NONE)
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


class _FakeTransport:
    def __init__(self, name, responses):
        self.name = name
        self._responses = list(responses)
        self._cookies = {}
        self.closed = False
        self.calls = []

    def send(self, url, method="GET", *, headers=None, data=None, json=None, referer=None, proxy=None):
        self.calls.append((url, method, proxy))
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
                    self.assertEqual(http_tr.cookies().get("cf_clearance"), "xyz")

            self.assertTrue(http_tr.closed)
            self.assertTrue(browser_tr.closed)

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


if __name__ == "__main__":
    unittest.main()
