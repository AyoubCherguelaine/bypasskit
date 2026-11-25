from dataclasses import dataclass
from ..challenge.detect import Challenge


@dataclass
class Response:
    status: int
    headers: dict
    body: str
    url: str
    elapsed: float
    transport: str
    challenge: Challenge = Challenge.NONE

    def __repr__(self) -> str:
        return (
            f"Response(status={self.status}, url={self.url!r}, "
            f"transport={self.transport!r}, challenge={self.challenge.value!r}, "
            f"body_len={len(self.body)})"
        )
