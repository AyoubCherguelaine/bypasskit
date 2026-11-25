import random, time

class Throttle:
    def __init__(self, min_delay=0.6, max_delay=2.4):
        self.min_delay, self.max_delay = min_delay, max_delay
        self._next = {}

    def wait(self, host: str, min_delay: float | None = None, max_delay: float | None = None):
        lo = self.min_delay if min_delay is None else min_delay
        hi = self.max_delay if max_delay is None else max_delay
        now = time.monotonic()
        due = self._next.get(host, 0.0)
        if due > now:
            time.sleep(due - now)
        self._next[host] = time.monotonic() + random.uniform(lo, hi)

    def penalize(self, host: str, factor=3.0):
        self._next[host] = time.monotonic() + random.uniform(self.max_delay, self.max_delay * factor)