from __future__ import annotations
import time
from typing import List, Tuple

class ApiKeyPool:
    def __init__(self, keys: List[str], cooldown_seconds: float = 60.0):
        if not keys:
            raise ValueError("ApiKeyPool requires at least one API key")
        self.state = [{"key": k, "cooldown_until": 0.0} for k in keys]
        self.idx = 0
        self.cooldown_seconds = cooldown_seconds

    def acquire(self) -> Tuple[str, int]:
        now = time.time()
        n = len(self.state)
        for hop in range(n):
            j = (self.idx + hop) % n
            if now >= self.state[j]["cooldown_until"]:
                self.idx = (j + 1) % n
                return self.state[j]["key"], j
        j = min(range(n), key=lambda i: self.state[i]["cooldown_until"])
        self.idx = (j + 1) % n
        return self.state[j]["key"], j

    def penalize(self, index: int, seconds: float | None = None):
        until = time.time() + (seconds if seconds is not None else self.cooldown_seconds)
        self.state[index]["cooldown_until"] = max(self.state[index]["cooldown_until"], until)
