import time, random

class Cooldown:
    """Exponential, jittered, per-host. No proxy means you must actually wait."""
    def __init__(self, cap=900):
        self.cap = cap
        self._until = {}

    def blocked(self, host, strikes):
        base = min(self.cap, 20 * (2 ** max(0, strikes - 1)))
        self._until[host] = time.monotonic() + base + random.uniform(0, base * 0.35)

    def wait(self, host):
        due = self._until.get(host)
        if due and due > time.monotonic():
            time.sleep(due - time.monotonic())