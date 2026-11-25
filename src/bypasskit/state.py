import hashlib
import json
import os
import time


class StateStore:
    """Per-domain persisted identity + cookies."""

    def __init__(self, root=".bkstate"):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, domain):
        return os.path.join(self.root, hashlib.sha1(domain.encode()).hexdigest() + ".json")

    def load(self, domain) -> dict:
        try:
            with open(self._path(domain)) as f:
                return json.load(f)
        except Exception:
            return {}

    def update(self, domain, **kw):
        d = self.load(domain)
        d.update(kw)
        path = self._path(domain)
        tmp = f"{path}.{os.getpid()}.tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(d, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def profile_dir(self, domain) -> str:
        p = os.path.join(self.root, "profile-" + hashlib.sha1(domain.encode()).hexdigest())
        os.makedirs(p, exist_ok=True)
        return p

    def cookies(self, domain) -> dict[str, str]:
        c = self.load(domain).get("cookies", {})
        now = time.time()
        out = {}
        for k, v in c.items():
            if isinstance(v, dict):
                exp = v.get("exp")
                if (exp is None or exp > now) and "value" in v:
                    out[k] = v["value"]
            elif isinstance(v, str):
                out[k] = v
        return out
