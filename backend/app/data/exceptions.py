"""
Data Layer 统一异常体系。

所有存储层异常均继承自 StorageError，
上层通过捕获 StorageError 即可统一处理所有存储故障。
"""

from typing import Optional


class StorageError(Exception):
    """
    存储层根异常。

    Attributes:
        store_name: 发生异常的存储实例名称
        operation:  失败的操作（get / set / delete / save ...）
        detail:     额外上下文信息
    """

    def __init__(
        self,
        message: str,
        *,
        store_name: str = "",
        operation: str = "",
        detail: str = "",
    ) -> None:
        super().__init__(message)
        self.store_name = store_name
        self.operation = operation
        self.detail = detail


class StoreNotFoundError(StorageError):
    """
    目标数据不存在。

    用于 get/delete 操作找不到指定数据的情况。
    这不是系统故障，而是正常的业务状态。
    """

    def __init__(
        self,
        message: str = "数据不存在",
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)


class StoreWriteError(StorageError):
    """
    写入操作失败。

    用于 put/set/save 操作异常的情况，
    通常意味着底层存储不可用或数据校验失败。
    """

    def __init__(
        self,
        message: str = "写入失败",
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)


class StoreConnectionError(StorageError):
    """
    存储连接失败。

    用于 Redis/PostgreSQL 等外部存储不可达的情况。
    内存实现不会抛出此异常，为生产环境预留。
    """

    def __init__(
        self,
        message: str = "存储连接失败",
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)


class StoreTimeoutError(StorageError):
    """
    存储操作超时。

    用于外部存储响应过慢的情况。
    """

    def __init__(
        self,
        message: str = "存储操作超时",
        *,
        timeout_seconds: float = 0,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds


class StoreIntegrityError(StorageError):
    """
    数据完整性约束违反。

    用于 UnitOfWork 提交时发现数据不一致的情况。
    """

    def __init__(
        self,
        message: str = "数据完整性约束违反",
        *,
        conflicting_stores: Optional[list[str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.conflicting_stores = conflicting_stores or []
