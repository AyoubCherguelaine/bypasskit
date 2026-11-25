import random, time

class Throttle:
    def __init__(self, min_delay=0.6, max_delay=2.4):
        self.min_delay, self.max_delay = min_delay, max_delay
        self._next = {}

    def wait(self, host: str):
        now = time.monotonic()
        due = self._next.get(host, 0.0)
        if due > now:
            time.sleep(due - now)
        self._next[host] = time.monotonic() + random.uniform(self.min_delay, self.max_delay)

    def penalize(self, host: str, factor=3.0):
        self._next[host] = time.monotonic() + random.uniform(self.max_delay, self.max_delay * factor)