"""
Caching layer for reducing Instagram API calls.
Supports in-memory (development) and Redis (production).
"""

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Optional
from functools import wraps

from app.core.config import get_settings
from app.core.logging import logger


class CacheBackend(ABC):
    """Abstract cache backend."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        pass


class InMemoryCache(CacheBackend):
    """
    Simple in-memory cache for development/small deployments.
    Not suitable for multi-process deployments.
    """
    
    def __init__(self, max_size: int = 10000):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key in self._cache:
                value, expires_at = self._cache[key]
                if time.time() < expires_at:
                    return value
                else:
                    del self._cache[key]
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        async with self._lock:
            # Evict oldest entries if at capacity
            if len(self._cache) >= self._max_size:
                # Remove 10% oldest entries
                sorted_keys = sorted(
                    self._cache.keys(),
                    key=lambda k: self._cache[k][1]
                )
                for k in sorted_keys[:self._max_size // 10]:
                    del self._cache[k]
            
            self._cache[key] = (value, time.time() + ttl)
    
    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
    
    async def stats(self) -> dict:
        """Get cache statistics."""
        async with self._lock:
            now = time.time()
            valid = sum(1 for _, (_, exp) in self._cache.items() if exp > now)
            return {
                "total_keys": len(self._cache),
                "valid_keys": valid,
                "expired_keys": len(self._cache) - valid,
                "max_size": self._max_size,
            }


class RedisCache(CacheBackend):
    """
    Redis-based cache for production multi-process deployments.
    Requires: pip install redis
    """
    
    def __init__(self, url: str = "redis://localhost:6379"):
        self._url = url
        self._redis = None
    
    async def _get_client(self):
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self._url, decode_responses=True)
            except ImportError:
                logger.warning("Redis not installed, falling back to in-memory cache")
                raise
        return self._redis
    
    async def get(self, key: str) -> Optional[Any]:
        try:
            client = await self._get_client()
            value = await client.get(f"insta:{key}")
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        try:
            client = await self._get_client()
            await client.setex(f"insta:{key}", ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    async def delete(self, key: str) -> None:
        try:
            client = await self._get_client()
            await client.delete(f"insta:{key}")
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
    
    async def clear(self) -> None:
        try:
            client = await self._get_client()
            keys = await client.keys("insta:*")
            if keys:
                await client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis clear error: {e}")


# Global cache instance
_cache: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        settings = get_settings()
        redis_url = getattr(settings, 'redis_url', None)
        
        if redis_url:
            try:
                _cache = RedisCache(redis_url)
                logger.info(f"Using Redis cache: {redis_url}")
            except Exception:
                _cache = InMemoryCache()
                logger.info("Using in-memory cache (Redis unavailable)")
        else:
            _cache = InMemoryCache()
            logger.info("Using in-memory cache")
    
    return _cache


def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(ttl: int = 300, prefix: str = ""):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds (default 5 minutes)
        prefix: Cache key prefix
    
    Usage:
        @cached(ttl=600, prefix="profile")
        async def get_profile(username: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            key = f"{prefix}:{cache_key(*args, **kwargs)}" if prefix else cache_key(*args, **kwargs)
            
            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {key}")
                return cached_value
            
            # Execute function and cache result
            logger.debug(f"Cache miss: {key}")
            result = await func(*args, **kwargs)
            
            # Only cache successful results
            if result is not None:
                await cache.set(key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# Cache TTL constants (in seconds)
class CacheTTL:
    """Standard cache TTL values."""
    PROFILE = 3600         # 1 hour - profiles change rarely
    POSTS = 3600           # 1 hour - posts don't change
    POST_DETAIL = 7200     # 2 hours - individual post data
    FOLLOWERS = 14400      # 4 hours - follower counts
    SEARCH = 1800          # 30 minutes - search results
    HASHTAG = 900          # 15 minutes - hashtag posts
    STORIES = 300          # 5 minutes - stories expire in 24h
