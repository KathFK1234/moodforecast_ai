"""In-memory TTL cache implementation."""

import time
from typing import Any, Optional
from app.config import settings


class TTLCache:
    """Simple in-memory cache with TTL support."""
    
    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        return self.get_stale(key, self.ttl_seconds)
    
    def get_stale(self, key: str, max_age_seconds: float) -> Optional[Any]:
        """
        Get a cached value up to max_age_seconds old, even if it is past the TTL.
        
        For falling back to the last known value when a fresh one can't be fetched.
        """
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        if time.time() - timestamp > max_age_seconds:
            return None
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set a cached value with current timestamp."""
        self._cache[key] = (value, time.time())
    
    def delete(self, key: str) -> None:
        """Remove a key from cache."""
        self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()


# Global cache instance
cache = TTLCache(settings.cache_ttl_seconds)
