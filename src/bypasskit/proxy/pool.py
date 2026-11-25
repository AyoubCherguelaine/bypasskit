import random
from contextlib import contextmanager

class ProxyPool:
    def __init__(self, proxies: list[str] | None = None):
        self._score = {p: 1.0 for p in (proxies or [])}

    def __bool__(self):
        return bool(self._score)

    def pick(self) -> str | None:
        if not self._score:
            return None
        items = list(self._score.items())
        total = sum(s for _, s in items)
        r = random.uniform(0, total)
        acc = 0.0
        for p, s in items:
            acc += s
            if r <= acc:
                return p
        return items[-1][0]

    def report(self, proxy: str | None, ok: bool):
        if proxy not in self._score:
            return
        s = self._score[proxy]
        self._score[proxy] = min(2.0, s * 1.3) if ok else max(0.05, s * 0.6)
        if self._score[proxy] <= 0.06:
            del self._score[proxy]

    @contextmanager
    def sticky(self):
        p = self.pick()
        try:
            yield p
        finally:
            pass