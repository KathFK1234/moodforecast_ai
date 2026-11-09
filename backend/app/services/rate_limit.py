"""In-memory limit on how often one visitor can use the site."""

import time
from collections import deque

# Enough for every visitor at a busy moment; beyond it the quietest are forgotten first
MAX_VISITORS = 10000


class RateLimiter:
    """Allows each key `limit` uses per `window_seconds`, counted over the last window."""
    
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._uses: dict[str, deque[float]] = {}
    
    def allow(self, key: str) -> bool:
        """Count a use, unless the key has reached its limit."""
        now = time.monotonic()
        uses = self._uses.pop(key, None) or deque()
        while uses and uses[0] <= now - self.window_seconds:
            uses.popleft()
        allowed = len(uses) < self.limit
        if allowed:
            uses.append(now)
        # Re-inserting keeps the most recently seen visitors last
        self._uses[key] = uses
        while len(self._uses) > MAX_VISITORS:
            del self._uses[next(iter(self._uses))]
        return allowed
    
    def forget_old(self) -> None:
        """Forget every visitor whose last use is a whole window ago: the limit no longer needs them."""
        cutoff = time.monotonic() - self.window_seconds
        for key in [key for key, uses in self._uses.items() if not uses or uses[-1] <= cutoff]:
            del self._uses[key]
    
    def clear(self) -> None:
        """Forget every visitor."""
        self._uses.clear()
