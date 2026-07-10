"""
会话临时状态存储 —— 开发环境用内存实现。

线程安全，由 BaseMemoryStore 提供异步锁、日志、异常封装。
支持 TTL 自动过期 + 后台定期清理。
"""

import time
from typing import Any, Optional

from app.data.runtime.base import BaseMemoryStore
from app.data.interfaces import SessionStore


class MemorySessionStore(BaseMemoryStore, SessionStore):
    """基于内存字典的会话状态存储（线程安全 + TTL）。"""

    def __init__(self) -> None:
        super().__init__(name="MemorySessionStore")
        # session_id -> { key -> (value, expires_at) }
        # expires_at 为 0 表示永不过期
        self._store: dict[str, dict[str, tuple[Any, float]]] = {}

    # ---- SessionStore 接口实现 ----

    async def get(self, session_id: str, key: str) -> Optional[Any]:
        async with self._locked_context("get", f"{session_id}/{key}"):
            entry = self._store.get(session_id, {}).get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at != 0 and expires_at <= time.time():
                # 惰性清理
                del self._store[session_id][key]
                if not self._store[session_id]:
                    del self._store[session_id]
                return None
            return value

    async def set(
        self, session_id: str, key: str, value: Any, ttl_seconds: int = 3600
    ) -> None:
        async with self._locked_context("set", f"{session_id}/{key}"):
            if session_id not in self._store:
                self._store[session_id] = {}
            expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else 0
            self._store[session_id][key] = (value, expires_at)

    async def delete(self, session_id: str, key: str) -> None:
        async with self._locked_context("delete", f"{session_id}/{key}"):
            self._store.get(session_id, {}).pop(key, None)
            if session_id in self._store and not self._store[session_id]:
                del self._store[session_id]

    async def clear_session(self, session_id: str) -> None:
        async with self._locked_context("clear_session", session_id):
            self._store.pop(session_id, None)

    # ---- 过期清理（主动扫描，解决惰性清理的内存泄漏） ----

    async def _cleanup_expired(self) -> int:
        """
        主动扫描所有 session，清理已过期的 key。
        与惰性清理不同，此方法会遍历全部数据。
        """
        now = time.time()
        cleaned = 0
        empty_sessions: list[str] = []

        for session_id, keys in self._store.items():
            expired_keys: list[str] = []
            for key, (_, expires_at) in keys.items():
                if expires_at != 0 and expires_at <= now:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._store[session_id][key]
                cleaned += 1

            if not self._store[session_id]:
                empty_sessions.append(session_id)

        for sid in empty_sessions:
            del self._store[sid]

        return cleaned
