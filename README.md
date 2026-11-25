# bypasskit

A lightweight Python HTTP and browser transport library with policy-driven escalation, browser fingerprint profiles, challenge detection, and persistent per-domain state.

## Features

- **Transport Escalation**: Configurable per-domain transport ladder (`"http"` via `curl_cffi` and `"browser"` via `playwright`), escalating automatically when challenges are detected.
- **Fingerprint Profiles**: Built-in `CHROME`, `SAFARI`, and `FIREFOX` profiles with matching TLS/HTTP impersonation, ordered headers, User-Agent, viewport, locale, and timezone.
- **Challenge Detection**: Detects rate limits (`429`), Cloudflare JS / Turnstile, DataDome, PerimeterX, Akamai, and reCAPTCHA/hCaptcha challenges.
- **Solvers**: Includes `ManualSolver` (waits for manual challenge resolution in a live browser) and `TurnstileSolver` (best-effort auto-click for Cloudflare Turnstile), or subclass `Solver` for custom handling.
- **Per-Domain Policies, Throttling & Cooldown**: Configure attempt budgets, delays, and transport ladders per domain via `PolicyMap` and `DomainPolicy`, backed by randomized throttling (`Throttle`) and exponential per-host backoff (`Cooldown`).
- **Persistent State**: Stores per-domain selected profiles, cookies, and browser profile directories in `.bkstate` via `StateStore`.

## Installation

```bash
pip install -e .
```

If you use the `"browser"` transport, ensure Playwright browsers are installed:

```bash
playwright install
```

## Quick Start

```python
from bypasskit import Session, DomainPolicy, PolicyMap, ManualSolver

pol = PolicyMap()
pol.set(
    "target.com",
    DomainPolicy(
        ladder=("http", "browser"),
        max_attempts=4,
        min_delay=1.0,
        max_delay=3.5,
    ),
)

with Session(policies=pol, solver=ManualSolver(), headless=False) as s:
    r = s.fetch("https://target.com/list?page=1")
    print(r.status, r.transport, len(r.body))
```

## Usage

### Default Session (Browser-Only)

Without a custom `PolicyMap`, `Session` defaults to `ladder=("browser",)`, `max_attempts=5`, and persists cookies and browser state per domain in `.bkstate`:

```python
from bypasskit import Session

s = Session()
r = s.fetch("https://example.com")
print(r.status, r.url, r.elapsed)
```

### HTTP-First with Browser Escalation

Start with fast `curl_cffi` HTTP requests and only spin up Playwright if a challenge is detected:

```python
from bypasskit import Session, DomainPolicy, PolicyMap, TurnstileSolver

pol = PolicyMap(
    default=DomainPolicy(ladder=("http", "browser"), max_attempts=4)
)
pol.set("strict-site.com", DomainPolicy(ladder=("browser",), max_attempts=6))

s = Session(policies=pol, solver=TurnstileSolver(), state=".bkstate")
r = s.fetch("https://strict-site.com/data")
```

### POST Requests & Custom Headers

`fetch()` supports `method`, `headers`, `data`, and `json`:

```python
r = s.fetch(
    "https://target.com/api/search",
    method="POST",
    headers={"X-Requested-With": "XMLHttpRequest"},
    json={"page": 1, "limit": 50},
)
```

### Custom Solver & Error Handling

```python
from bypasskit import Session, ChallengeUnresolved
from bypasskit.solvers import Solver
from bypasskit.challenge.detect import Challenge


class MySolver(Solver):
    def solve(self, challenge: Challenge, transport, url: str) -> bool:
        if challenge == Challenge.RECAPTCHA:
            # integrate external captcha solver here
            return False
        return False


s = Session(solver=MySolver())
try:
    r = s.fetch("https://target.com/protected")
except ChallengeUnresolved as e:
    print("Could not bypass:", e)
```

## API Overview

### `Session`

```python
Session(
    policies=None,      # PolicyMap instance (defaults to browser-only with 5 attempts)
    solver=None,        # Optional Solver instance (e.g., ManualSolver(), TurnstileSolver())
    state=".bkstate",   # Directory for persisted per-host state and browser profiles
    headless=True,      # Run Playwright browser in headless mode
    rotate_after=2,     # Strikes before rotating fingerprint profile and clearing cookies
    proxies=None,       # Optional list of proxy URLs (e.g. ["http://user:pass@host:port"])
)
```

- `session.fetch(url, method="GET", *, headers=None, data=None, json=None) -> Response`
  Returns a `Response(status, headers, body, url, elapsed, transport)` or raises `ChallengeUnresolved` if all attempts fail.
- `session.close()` (or use `with Session(...) as s:`): Closes all open HTTP and browser transports.

### Tests

```bash
python -m unittest discover -s tests -v
```

### `DomainPolicy` & `PolicyMap`

- `DomainPolicy(ladder=("http", "browser"), max_attempts=4, timeout=30.0, rotate_on_block=True, min_delay=0.6, max_delay=2.4)`
- `PolicyMap(default=None)` with `.set(domain, policy)` and `.for_domain(domain)`.

### Solvers

- `ManualSolver(max_wait=180)`: Pauses when using the browser transport so an operator can clear the challenge manually.
- `TurnstileSolver()`: Attempts to click Cloudflare Turnstile frames and wait for clearance.
- `Solver`: Base class with `solve(self, challenge: Challenge, transport, url: str) -> bool`.

### Exceptions

- `BypassError` (base)
  - `TransportError`
  - `BlockedError`
  - `ChallengeUnresolved`
  - `BudgetExceeded`

## Project Structure

```text
bypasskit/
├── __init__.py          # Public exports (Session, DomainPolicy, PolicyMap, solvers, errors, get)
├── session.py           # Session orchestration, warm-up, escalation, and profile rotation
├── policies.py          # DomainPolicy and PolicyMap
├── solvers.py           # Solver, ManualSolver, TurnstileSolver
├── throttle.py          # Randomized per-host request pacing
├── cooldown.py          # Exponential jittered per-host backoff
├── state.py             # StateStore for per-domain profiles, cookies, and browser dirs
├── errors.py            # Exception hierarchy
├── challenge/
│   └── detect.py        # Challenge enum and response detector
├── fingerprint/
│   └── profiles.py      # Browser profiles and ordered header generation
├── proxy/
│   └── pool.py          # Weighted ProxyPool with sticky context support
└── transport/
    ├── base.py          # Response dataclass
    ├── http.py          # HttpTransport (curl_cffi)
    ├── browser.py       # BrowserTransport (playwright)
    └── stealth.py       # Browser init and mouse movement scripts
```
