"""
Business 存储基类 —— 提供异步锁、统一日志、异常封装、通用 CRUD。

所有 Business 层的仓库实现继承此类，
子类只需覆写 _save_impl / _get_impl / _delete_impl / _list_impl。
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Generic, TypeVar, Optional

from pydantic import BaseModel

from app.data.exceptions import (
    StorageError,
    StoreNotFoundError,
    StoreWriteError,
)

# 泛型：ModelT 是 Pydantic 数据模型类型
ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseBusinessRepository(Generic[ModelT]):
    """
    Business 仓库基类。

    提供：
    - asyncio.Lock 保证并发安全
    - 统一操作日志
    - 异常封装为 StorageError 子类
    - 通用 CRUD 模板方法
    """

    def __init__(self, name: str = "") -> None:
        self._lock = asyncio.Lock()
        self._store_name = name or type(self).__name__
        self._logger = logging.getLogger(f"data.business.{self._store_name}")

    # ---- 子类必须覆写 ----

    async def _save_impl(self, model: ModelT) -> str:
        """保存实体，返回 ID。"""
        raise NotImplementedError

    async def _get_impl(self, entity_id: str) -> Optional[ModelT]:
        """按 ID 获取实体，不存在返回 None。"""
        raise NotImplementedError

    async def _delete_impl(self, entity_id: str) -> bool:
        """按 ID 删除实体，返回是否成功。"""
        raise NotImplementedError

    async def _list_impl(
        self, user_id: str, limit: int, offset: int
    ) -> list[ModelT]:
        """分页列出用户实体。"""
        raise NotImplementedError

    async def _count_impl(self, user_id: str) -> int:
        """统计用户实体数量。"""
        raise NotImplementedError

    # ---- 对外暴露的线程安全方法 ----

    async def save(self, model: ModelT) -> str:
        """线程安全保存。"""
        async with self._locked_context("save", ""):
            try:
                entity_id = await self._save_impl(model)
                self._logger.info(f"保存成功: id={entity_id}")
                return entity_id
            except StorageError:
                raise
            except Exception as e:
                raise StoreWriteError(
                    f"[{self._store_name}] 保存失败",
                    store_name=self._store_name,
                    operation="save",
                    detail=str(e),
                ) from e

    async def get(self, entity_id: str) -> Optional[ModelT]:
        """线程安全获取。"""
        async with self._locked_context("get", entity_id):
            try:
                return await self._get_impl(entity_id)
            except StorageError:
                raise
            except Exception as e:
                raise StoreNotFoundError(
                    f"[{self._store_name}] 获取失败: id={entity_id}",
                    store_name=self._store_name,
                    operation="get",
                    detail=str(e),
                ) from e

    async def delete(self, entity_id: str) -> bool:
        """线程安全删除。"""
        async with self._locked_context("delete", entity_id):
            try:
                result = await self._delete_impl(entity_id)
                if result:
                    self._logger.info(f"删除成功: id={entity_id}")
                return result
            except StorageError:
                raise
            except Exception as e:
                raise StoreNotFoundError(
                    f"[{self._store_name}] 删除失败: id={entity_id}",
                    store_name=self._store_name,
                    operation="delete",
                    detail=str(e),
                ) from e

    async def list_by_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[ModelT]:
        """线程安全分页查询。"""
        async with self._locked_context("list", f"user={user_id}"):
            try:
                return await self._list_impl(user_id, limit, offset)
            except Exception as e:
                raise StoreNotFoundError(
                    f"[{self._store_name}] 查询失败: user={user_id}",
                    store_name=self._store_name,
                    operation="list",
                    detail=str(e),
                ) from e

    async def count_by_user(self, user_id: str) -> int:
        """线程安全统计。"""
        async with self._locked_context("count", f"user={user_id}"):
            try:
                return await self._count_impl(user_id)
            except Exception as e:
                raise StorageError(
                    f"[{self._store_name}] 统计失败: user={user_id}",
                    store_name=self._store_name,
                    operation="count",
                    detail=str(e),
                ) from e

    @property
    def store_name(self) -> str:
        return self._store_name

    # ---- 内部工具 ----

    @asynccontextmanager
    async def _locked_context(
        self, operation: str, target: str
    ) -> AsyncIterator[None]:
        """锁上下文管理器。"""
        start = time.perf_counter()
        async with self._lock:
            try:
                yield
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                if elapsed > 100:
                    self._logger.warning(
                        f"[{operation}] target={target} 耗时 {elapsed:.0f}ms (慢操作)"
                    )
