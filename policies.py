from dataclasses import dataclass, field

@dataclass
class DomainPolicy:
    ladder: tuple[str, ...] = ("http", "browser")
    max_attempts: int = 4
    timeout: float = 30.0
    rotate_on_block: bool = True
    min_delay: float = 0.6
    max_delay: float = 2.4

class PolicyMap:
    def __init__(self, default: DomainPolicy | None = None):
        self.default = default or DomainPolicy()
        self._by_domain: dict[str, DomainPolicy] = {}

    def set(self, domain: str, policy: DomainPolicy):
        self._by_domain[domain] = policy

    def for_domain(self, domain: str) -> DomainPolicy:
        return self._by_domain.get(domain, self.default)