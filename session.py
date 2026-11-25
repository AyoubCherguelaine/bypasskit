import random
from urllib.parse import urlsplit
from .challenge.detect import detect, Challenge
from .errors import BudgetExceeded, ChallengeUnresolved
from .fingerprint.profiles import CHROME, SAFARI, FIREFOX
from .policies import PolicyMap
from .proxy.pool import ProxyPool
from .solvers import Solver
from .throttle import Throttle
from .transport.browser import BrowserTransport
from .transport.http import HttpTransport

_PROFILES = [CHROME, SAFARI, FIREFOX]

class Session:
    def __init__(self, profile=None, proxies=None, policies=None,
                 solver=None, headless=True):
        self._rotate_identity(profile)
        self.proxies = ProxyPool(proxies)
        self.policies = policies or PolicyMap()
        self.solver: Solver | None = solver
        self.throttle = Throttle()
        self._http = None
        self._browser = None
        self._referer = None
        self._headless = headless

    def _rotate_identity(self, profile=None):
        self.profile = profile or random.choice(_PROFILES)
        if self._http: self._http.close()
        if self._browser: self._browser.close()
        self._http = self._browser = None
        self._proxy = self.proxies.pick() if hasattr(self, "proxies") else None

    def _transport(self, kind):
        if kind == "http":
            if not self._http:
                self._http = HttpTransport(self.profile)
            return self._http
        if not self._browser:
            self._browser = BrowserTransport(self.profile, headless=self._headless)
        return self._browser

    def fetch(self, url, method="GET", *, headers=None, data=None, json=None):
        host = urlsplit(url).hostname or ""
        pol = self.policies.for_domain(host)
        ladder = list(pol.ladder)
        level = 0

        for attempt in range(1, pol.max_attempts + 1):
            kind = ladder[min(level, len(ladder) - 1)]
            self.throttle.wait(host)
            tr = self._transport(kind)
            try:
                resp = tr.send(url, method, headers=headers, data=data, json=json,
                               referer=self._referer, proxy=self._proxy)
            except Exception:
                self.proxies.report(self._proxy, ok=False)
                self._proxy = self.proxies.pick()
                continue

            ch = detect(resp.status, resp.headers, resp.body, resp.url)

            if ch == Challenge.NONE:
                self.proxies.report(self._proxy, ok=True)
                if resp.status < 400:
                    self._referer = resp.url
                    self._harvest(tr)
                return resp

            if ch == Challenge.RATE_LIMIT:
                self.throttle.penalize(host)
                if pol.rotate_on_block:
                    self._proxy = self.proxies.pick()
                continue

            # real challenge: escalate transport first
            if level + 1 < len(ladder):
                level += 1
                continue

            # top of ladder -> solve
            if self.solver and self.solver.solve(ch, tr, url):
                resp = tr.send(url, method, headers=headers, data=data, json=json,
                               referer=self._referer, proxy=self._proxy)
                if detect(resp.status, resp.headers, resp.body, resp.url) == Challenge.NONE:
                    self._harvest(tr)
                    return resp

            if pol.rotate_on_block:
                self._rotate_identity()
                level = 0
                self.throttle.penalize(host)

        raise ChallengeUnresolved(f"{host}: unresolved after {pol.max_attempts} attempts")

    def _harvest(self, tr):
        """Move cookies between transports so a browser solve keeps working on HTTP."""
        if tr is self._browser and self._http:
            self._http.inject_cookies(tr.cookies())
        elif tr is self._http and self._browser:
            self._browser.inject_cookies(tr.cookies())

    def close(self):
        if self._http: self._http.close()
        if self._browser: self._browser.close()

    def __enter__(self): return self
    def __exit__(self, *a): self.close()