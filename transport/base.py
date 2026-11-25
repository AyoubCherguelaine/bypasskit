from dataclasses import dataclass

@dataclass
class Response:
    status: int
    headers: dict
    body: str
    url: str
    elapsed: float
    transport: str