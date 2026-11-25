import random
import time
from urllib.parse import urlsplit
from .challenge.detect import detect, Challenge
from .cooldown import Cooldown
from .errors import ChallengeUnresolved
from .fingerprint.profiles import CHROME, SAFARI, FIREFOX
from .policies import PolicyMap, DomainPolicy
from .proxy.pool import ProxyPool
from .solvers import Solver
from .state import StateStore
from .throttle import Throttle
from .transport.browser import BrowserTransport
from .transport.http import HttpTransport

_PROFILES = {p.name: p for p in (CHROME, SAFARI, FIREFOX)}
DEFAULT = DomainPolicy(
    ladder=("browser",), max_attempts=5, min_delay=1.5, max_delay=5.0
)


class Session:
    def __init__(self, policies=None, solver=None, state=".bkstate",
                 headless=True, rotate_after=2, proxies=None):
        self.policies = policies or PolicyMap(DEFAULT)
        self.solver: Solver | None = solver
        self.state = StateStore(state)
        self.proxies = ProxyPool(proxies)
        self.cooldown = Cooldown()
        self.throttle = Throttle()
        self.rotate_after = rotate_after
        self._headless = headless
        self._hosts: dict[str, dict] = {}   # per-host runtime

    def _rt(self, host):
        if host not in self._hosts:
            stored = self.state.load(host)
            name = stored.get("profile")
            if name not in _PROFILES:
                name = random.choice(list(_PROFILES))
            self._hosts[host] = {
                "profile": _PROFILES[name],
                "name": name,
                "strikes": 0,
                "http": None,
                "browser": None,
                "proxy": self.proxies.pick(),
            }
            self.state.update(host, profile=name)
        return self._hosts[host]

    def _transport(self, rt, host, kind, timeout):
        if kind == "http":
            if not rt["http"]:
                rt["http"] = HttpTransport(rt["profile"], timeout=timeout)
                rt["http"].inject_cookies(self.state.cookies(host))
            return rt["http"]
        if not rt["browser"]:
            rt["browser"] = BrowserTransport(
                rt["profile"],
                self.state.profile_dir(host),
                headless=self._headless,
                timeout=timeout,
            )
        return rt["browser"]

    def _harvest(self, rt, host, tr):
        cookies = tr.cookies()
        self.state.update(host, cookies=self._dump(cookies))
        if tr is rt["browser"] and rt["http"]:
            rt["http"].inject_cookies(cookies)
        elif tr is rt["http"] and rt["browser"]:
            rt["browser"].inject_cookies(cookies, domain=host)

    def fetch(self, url, method="GET", *, headers=None, data=None, json=None):
        host = urlsplit(url).hostname or ""
        pol = self.policies.for_domain(host)
        rt = self._rt(host)
        ladder = list(pol.ladder)
        level = 0
        warmed = bool(self.state.cookies(host))

        for _ in range(pol.max_attempts):
            self.cooldown.wait(host)
            self.throttle.wait(host, pol.min_delay, pol.max_delay)
            kind = ladder[min(level, len(ladder) - 1)]
            tr = self._transport(rt, host, kind, pol.timeout)

            try:
                if not warmed:
                    tr.send(f"https://{host}/", proxy=rt["proxy"])
                    warmed = True
                resp = tr.send(
                    url, method, headers=headers, data=data, json=json, proxy=rt["proxy"]
                )
            except Exception:
                self.proxies.report(rt["proxy"], ok=False)
                if pol.rotate_on_block:
                    rt["proxy"] = self.proxies.pick()
                self.cooldown.blocked(host, 1)
                continue

            ch = detect(resp.status, resp.headers, resp.body, resp.url)
            if ch == Challenge.NONE:
                self.proxies.report(rt["proxy"], ok=True)
                rt["strikes"] = 0
                self._harvest(rt, host, tr)
                return resp

            if ch == Challenge.RATE_LIMIT:
                rt["strikes"] += 1
                self.proxies.report(rt["proxy"], ok=False)
                if pol.rotate_on_block:
                    rt["proxy"] = self.proxies.pick()
                self.cooldown.blocked(host, rt["strikes"])
                continue

            if level + 1 < len(ladder):
                level += 1
                continue

            if self.solver and self.solver.solve(ch, tr, url):
                self._harvest(rt, host, tr)
                continue

            rt["strikes"] += 1
            self.proxies.report(rt["proxy"], ok=False)
            self.cooldown.blocked(host, rt["strikes"])
            if pol.rotate_on_block and rt["strikes"] >= self.rotate_after:
                rt["profile"] = random.choice(list(_PROFILES.values()))
                rt["name"] = rt["profile"].name
                rt["proxy"] = self.proxies.pick()
                self.state.update(host, profile=rt["name"], cookies={})
                rt["strikes"] = 0
                if rt["http"]:
                    rt["http"].close()
                    rt["http"] = None
                if rt["browser"]:
                    rt["browser"].close()
                    rt["browser"] = None
                level = 0

        raise ChallengeUnresolved(f"{host}: unresolved, cooling down")

    @staticmethod
    def _dump(cookies: dict) -> dict:
        exp = time.time() + 3600
        return {k: {"value": v, "exp": exp} for k, v in cookies.items()}

    def close(self):
        for rt in self._hosts.values():
            if rt["http"]:
                rt["http"].close()
                rt["http"] = None
            if rt["browser"]:
                rt["browser"].close()
                rt["browser"] = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
