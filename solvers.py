from .challenge.detect import Challenge

class Solver:
    def solve(self, challenge: Challenge, transport, url: str) -> bool:
        raise NotImplementedError

class ManualSolver(Solver):
    """Blocks until the operator clears the challenge in the live browser."""
    def __init__(self, max_wait=180):
        self.max_wait = max_wait

    def solve(self, challenge, transport, url):
        if transport.name != "browser":
            return False
        print(f"[manual] {challenge.value} on {url} — clear it, waiting {self.max_wait}s")
        return transport.wait_clear(self.max_wait)

class TurnstileSolver(Solver):
    """Best-effort auto-click for managed/interactive Turnstile."""
    def solve(self, challenge, transport, url):
        if transport.name != "browser" or challenge != Challenge.CF_TURNSTILE:
            return False
        return transport.click_turnstile() and transport.wait_clear(30)