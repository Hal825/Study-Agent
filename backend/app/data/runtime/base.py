"""
Runtime 存储基类 —— 提供异步锁、统一日志、异常封装。

所有 Runtime 层的内存实现继承此类，
子类只需关注「数据怎么存」，锁/日志/异常由基类统一处理。
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from app.data.exceptions import (
    StorageError,
    StoreNotFoundError,
    StoreWriteError,
)


class BaseMemoryStore:
    """
    Runtime 内存存储基类。

    提供：
    - asyncio.Lock 保证单实例内的并发安全
    - 统一操作日志（INFO 级别记录写，DEBUG 级别记录读）
    - 异常封装：将原生异常转为 StorageError 子类
    - 耗时统计
    """

    def __init__(self, name: str = "") -> None:
        self._lock = asyncio.Lock()
        self._store_name = name or type(self).__name__
        self._logger = logging.getLogger(f"data.runtime.{self._store_name}")

    # ---- 子类钩子 ----

    async def _get_impl(self, key: str) -> Any:
        """子类覆写：读取单个 key 的实现。"""
        raise NotImplementedError

    async def _set_impl(self, key: str, value: Any) -> None:
        """子类覆写：写入单个 key 的实现。"""
        raise NotImplementedError

    async def _delete_impl(self, key: str) -> bool:
        """子类覆写：删除单个 key，返回是否成功。"""
        raise NotImplementedError

    async def _clear_impl(self) -> None:
        """子类覆写：清空全部数据。"""
        raise NotImplementedError

    async def _cleanup_expired(self) -> int:
        """子类覆写：清理过期数据，返回清理条数。默认不清理。"""
        return 0

    # ---- 对外暴露的线程安全方法 ----

    async def get(self, key: str, *, default: Any = None) -> Any:
        """
        线程安全读取，key 不存在时返回 default。
        不抛异常，除非底层存储故障。
        """
        async with self._locked_context("get", key):
            try:
                result = await self._get_impl(key)
                return result if result is not None else default
            except StorageError:
                raise
            except Exception as e:
                raise StoreNotFoundError(
                    f"[{self._store_name}] 读取失败: key={key}",
                    store_name=self._store_name,
                    operation="get",
                    detail=str(e),
                ) from e

    async def set(self, key: str, value: Any) -> None:
        """线程安全写入。"""
        async with self._locked_context("set", key):
            try:
                await self._set_impl(key, value)
            except StorageError:
                raise
            except Exception as e:
                raise StoreWriteError(
                    f"[{self._store_name}] 写入失败: key={key}",
                    store_name=self._store_name,
                    operation="set",
                    detail=str(e),
                ) from e

    async def delete(self, key: str) -> bool:
        """线程安全删除。"""
        async with self._locked_context("delete", key):
            try:
                return await self._delete_impl(key)
            except StorageError:
                raise
            except Exception as e:
                raise StoreNotFoundError(
                    f"[{self._store_name}] 删除失败: key={key}",
                    store_name=self._store_name,
                    operation="delete",
                    detail=str(e),
                ) from e

    async def clear(self) -> None:
        """线程安全清空。"""
        async with self._locked_context("clear", ""):
            try:
                await self._clear_impl()
            except Exception as e:
                raise StoreWriteError(
                    f"[{self._store_name}] 清空失败",
                    store_name=self._store_name,
                    operation="clear",
                    detail=str(e),
                ) from e

    async def cleanup(self) -> int:
        """线程安全执行过期清理。"""
        async with self._locked_context("cleanup", ""):
            count = await self._cleanup_expired()
            if count > 0:
                self._logger.info(f"清理了 {count} 条过期数据")
            return count

    @property
    def store_name(self) -> str:
        return self._store_name

    # ---- 内部工具 ----

    @asynccontextmanager
    async def _locked_context(self, operation: str, key: str) -> AsyncIterator[None]:
        """
        锁上下文管理器：获取锁 → 记录日志 → 执行 → 记录耗时。

        用法：
            async with self._locked_context("get", key):
                return self._data.get(key)
        """
        start = time.perf_counter()
        async with self._lock:
            try:
                yield
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                if elapsed > 100:  # 超过 100ms 记录警告
                    self._logger.warning(
                        f"[{operation}] key={key} 耗时 {elapsed:.0f}ms (慢操作)"
                    )
                elif elapsed > 10:
                    self._logger.debug(
                        f"[{operation}] key={key} 耗时 {elapsed:.0f}ms"
                    )
