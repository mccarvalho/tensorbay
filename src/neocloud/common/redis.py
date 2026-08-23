"""
Redis client configuration and utilities.
"""
import json
from typing import Any, Optional

import redis.asyncio as redis

from .config import get_settings

settings = get_settings()


class RedisClient:
    """Async Redis client wrapper."""
    
    def __init__(self):
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        if not self._pool:
            self._pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                decode_responses=True
            )
            self._client = redis.Redis(connection_pool=self._pool)
    
    async def disconnect(self) -> None:
        """Close Redis connections."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance."""
        if not self._client:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._client
    
    async def set_json(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Store JSON data in Redis."""
        data = json.dumps(value, default=str)
        return await self.client.set(key, data, ex=expire)
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Retrieve JSON data from Redis."""
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def delete(self, key: str) -> int:
        """Delete key from Redis."""
        return await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        return bool(await self.client.exists(key))
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for a key."""
        return await self.client.expire(key, seconds)
    
    async def ttl(self, key: str) -> int:
        """Get time to live for a key."""
        return await self.client.ttl(key)


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency to get Redis client."""
    if not redis_client._client:
        await redis_client.connect()
    return redis_client


# Cache key utilities
class CacheKeys:
    """Centralized cache key management."""
    
    @staticmethod
    def user_session(user_id: str) -> str:
        return f"session:user:{user_id}"
    
    @staticmethod
    def gpu_availability(location: str) -> str:
        return f"availability:gpu:{location}"
    
    @staticmethod
    def customer_profile(customer_id: str) -> str:
        return f"profile:customer:{customer_id}"
    
    @staticmethod
    def reservation_lock(reservation_id: str) -> str:
        return f"lock:reservation:{reservation_id}"