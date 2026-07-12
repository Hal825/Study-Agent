"""
Redis 缓存存储 —— 实现 CacheStore 接口。

直接实现接口（不继承 BaseMemoryStore）避免被 CleanupScheduler 注册，
因为 Redis 原生支持 TTL 自动过期，无需应用层清理。

序列化: pickle（保持 LLMResponse dataclass 的精确类型，无需额外转换逻辑）。
"""

import logging
import pickle
from typing import Any, Optional

import redis.asyncio as aioredis
import redis.exceptions

from app.data.interfaces import CacheStore
from app.data.exceptions import (
    StoreConnectionError,
    StoreTimeoutError,
)

logger = logging.getLogger("data.runtime.RedisCacheStore")


class RedisCacheStore(CacheStore):
    """Redis 缓存存储。"""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        key_prefix: str = "cache:",
    ) -> None:
        self._redis = redis_client
        self._prefix = key_prefix

    def _key(self, raw: str) -> str:
        return f"{self._prefix}{raw}"

    # ----------------------------------------------------------------
    # CacheStore 接口实现
    # ----------------------------------------------------------------

    async def get(self, key: str) -> Optional[Any]:
        """读取缓存，未命中返回 None。"""
        try:
            data = await self._redis.get(self._key(key))
            if data is None:
                return None
            return pickle.loads(data)
        except pickle.UnpicklingError as e:
            logger.warning(f"缓存反序列化失败: key={key}, 将视为未命中")
            await self.delete(key)
            return None
        except redis.exceptions.TimeoutError as e:
            raise StoreTimeoutError(
                f"Redis 读取超时: key={key}",
                store_name="RedisCacheStore",
                operation="get",
                detail=str(e),
                timeout_seconds=5,
            ) from e
        except redis.exceptions.ConnectionError as e:
            raise StoreConnectionError(
                f"Redis 连接失败: key={key}",
                store_name="RedisCacheStore",
                operation="get",
                detail=str(e),
            ) from e

    async def set(self, key: str, value: Any, ttl_seconds: int = 600) -> None:
        """写入缓存，带 TTL。"""
        try:
            data = pickle.dumps(value)
            await self._redis.setex(self._key(key), ttl_seconds, data)
        except redis.exceptions.TimeoutError as e:
            raise StoreTimeoutError(
                f"Redis 写入超时: key={key}",
                store_name="RedisCacheStore",
                operation="set",
                detail=str(e),
                timeout_seconds=5,
            ) from e
        except redis.exceptions.ConnectionError as e:
            raise StoreConnectionError(
                f"Redis 连接失败: key={key}",
                store_name="RedisCacheStore",
                operation="set",
                detail=str(e),
            ) from e

    async def delete(self, key: str) -> None:
        """删除缓存（静默，key 不存在也不报错）。"""
        try:
            await self._redis.delete(self._key(key))
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            # 删除失败不抛异常（对业务无影响）
            logger.debug(f"Redis 删除失败(已忽略): key={key}")

    async def exists(self, key: str) -> bool:
        """检查 key 是否存在。"""
        try:
            count = await self._redis.exists(self._key(key))
            return bool(count)
        except redis.exceptions.ConnectionError as e:
            raise StoreConnectionError(
                f"Redis 连接失败: key={key}",
                store_name="RedisCacheStore",
                operation="exists",
                detail=str(e),
            ) from e
