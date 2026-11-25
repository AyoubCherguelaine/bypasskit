import json, os, hashlib, time

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
        with open(self._path(domain), "w") as f:
            json.dump(d, f)

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
                if v.get("exp", now + 1) > now and "value" in v:
                    out[k] = v["value"]
            elif isinstance(v, str):
                out[k] = v
        return out