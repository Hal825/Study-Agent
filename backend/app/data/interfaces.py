"""
Data Layer 抽象接口。

上层模块只依赖这些接口，不依赖具体存储实现（Memory / Redis / PostgreSQL）。
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================
# Runtime 接口 —— 会话级临时存储
# ============================================================

class CheckpointEntry(BaseModel):
    """LangGraph checkpoint 条目。"""
    thread_id: str
    checkpoint_ns: str = ""
    checkpoint_id: str
    parent_checkpoint_id: Optional[str] = None
    channel_values: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CheckpointStore(ABC):
    """LangGraph checkpoint 持久化抽象。"""

    @abstractmethod
    async def put(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        parent_checkpoint_id: Optional[str],
        channel_values: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        """写入一个 checkpoint。"""
        ...

    @abstractmethod
    async def get(
        self, thread_id: str, checkpoint_ns: str = ""
    ) -> Optional[CheckpointEntry]:
        """获取最新 checkpoint。"""
        ...

    @abstractmethod
    async def get_by_id(
        self, thread_id: str, checkpoint_id: str
    ) -> Optional[CheckpointEntry]:
        """按 ID 获取指定 checkpoint。"""
        ...

    @abstractmethod
    async def list_checkpoints(
        self, thread_id: str, checkpoint_ns: str = ""
    ) -> list[CheckpointEntry]:
        """列出某 thread 的所有 checkpoint。"""
        ...

    @abstractmethod
    async def delete_thread(self, thread_id: str) -> None:
        """删除某 thread 的全部 checkpoint。"""
        ...


class SessionStore(ABC):
    """会话临时状态存储（当前步骤、中间结果、SSE channel 等）。"""

    @abstractmethod
    async def get(self, session_id: str, key: str) -> Optional[Any]:
        """读取一个 key。"""
        ...

    @abstractmethod
    async def set(
        self, session_id: str, key: str, value: Any, ttl_seconds: int = 3600
    ) -> None:
        """写入一个 key，可选 TTL。"""
        ...

    @abstractmethod
    async def delete(self, session_id: str, key: str) -> None:
        """删除一个 key。"""
        ...

    @abstractmethod
    async def clear_session(self, session_id: str) -> None:
        """清空某个会话的全部临时状态。"""
        ...


class CacheStore(ABC):
    """热点数据缓存抽象（LLM 响应去重、Token 计数等）。"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """读取缓存。"""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int = 600) -> None:
        """写入缓存。"""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除缓存。"""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查 key 是否存在。"""
        ...


# ============================================================
# Business 接口 —— 跨会话持久化
# ============================================================

class StudyNote(BaseModel):
    """学习笔记数据模型。"""
    id: str = ""
    user_id: str = "anonymous"
    title: str = ""
    template: str = ""
    content: str = ""
    source_content: str = ""           # 原始输入内容
    created_at: float = 0.0            # Unix timestamp


class UserPreference(BaseModel):
    """用户偏好设置。"""
    user_id: str
    preferred_template: str = "outline"
    preferred_depth: str = "detailed"  # brief | standard | detailed
    language: str = "zh"
    enable_auto_save: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class NoteRepository(ABC):
    """笔记持久化仓库。"""

    @abstractmethod
    async def save(self, note: StudyNote) -> str:
        """保存笔记，返回 note_id。"""
        ...

    @abstractmethod
    async def get(self, note_id: str) -> Optional[StudyNote]:
        """按 ID 获取笔记。"""
        ...

    @abstractmethod
    async def list_by_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[StudyNote]:
        """列出用户的所有笔记，按时间倒序。"""
        ...

    @abstractmethod
    async def delete(self, note_id: str) -> bool:
        """删除笔记，返回是否成功。"""
        ...

    @abstractmethod
    async def count_by_user(self, user_id: str) -> int:
        """用户笔记总数。"""
        ...


class UserPreferenceRepository(ABC):
    """用户偏好存取。"""

    @abstractmethod
    async def get(self, user_id: str) -> UserPreference:
        """获取偏好，不存在时返回默认值。"""
        ...

    @abstractmethod
    async def update(self, user_id: str, prefs: dict[str, Any]) -> None:
        """更新偏好（部分更新）。"""
        ...

    @abstractmethod
    async def reset(self, user_id: str) -> None:
        """重置为默认偏好。"""
        ...
