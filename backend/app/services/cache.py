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
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
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
