"""
热点数据缓存 —— 开发环境用内存实现。

线程安全，由 BaseMemoryStore 提供异步锁、日志、异常封装。
支持 TTL 自动过期 + 后台定期清理。
"""

import time
from typing import Any, Optional

from app.data.runtime.base import BaseMemoryStore
from app.data.interfaces import CacheStore


class MemoryCacheStore(BaseMemoryStore, CacheStore):
    """基于内存字典的缓存存储（线程安全 + TTL）。"""

    def __init__(self) -> None:
        super().__init__(name="MemoryCacheStore")
        # key -> (value, expires_at), expires_at=0 表示永不过期
        self._store: dict[str, tuple[Any, float]] = {}

    # ---- CacheStore 接口实现 ----

    async def get(self, key: str) -> Optional[Any]:
        async with self._locked_context("get", key):
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at != 0 and expires_at <= time.time():
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl_seconds: int = 600) -> None:
        async with self._locked_context("set", key):
            expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else 0
            self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        async with self._locked_context("delete", key):
            self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        val = await self.get(key)
        return val is not None

    # ---- 过期清理 ----

    async def _cleanup_expired(self) -> int:
        """主动扫描全部缓存，清理已过期的条目。"""
        now = time.time()
        expired: list[str] = []
        for key, (_, expires_at) in self._store.items():
            if expires_at != 0 and expires_at <= now:
                expired.append(key)

        for key in expired:
            del self._store[key]

        return len(expired)
