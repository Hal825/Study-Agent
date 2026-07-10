"""
用户偏好仓库 —— 开发环境用内存实现。

继承 BaseBusinessRepository 复用锁和日志，
但因接口不是标准实体 CRUD，方法直接使用 _locked_context。
"""

from typing import Any

from app.data.interfaces import UserPreferenceRepository, UserPreference
from app.data.business.base import BaseBusinessRepository


class MemoryUserPreferenceRepository(
    BaseBusinessRepository[UserPreference],
    UserPreferenceRepository,
):
    """基于内存字典的用户偏好存储（线程安全）。"""

    def __init__(self) -> None:
        super().__init__(name="MemoryUserPreferenceRepository")
        self._prefs: dict[str, UserPreference] = {}

    # ---- UserPreferenceRepository 接口实现 ----

    async def get(self, user_id: str) -> UserPreference:
        async with self._locked_context("get", user_id):
            if user_id not in self._prefs:
                self._prefs[user_id] = UserPreference(user_id=user_id)
            return self._prefs[user_id].model_copy(deep=True)

    async def update(self, user_id: str, prefs: dict[str, Any]) -> None:
        async with self._locked_context("update", user_id):
            current = self._prefs.get(user_id)
            if current is None:
                current = UserPreference(user_id=user_id)
            updated_data = current.model_dump()
            updated_data.update(prefs)
            self._prefs[user_id] = UserPreference(**updated_data)
            self._logger.info(f"偏好已更新: user={user_id}")

    async def reset(self, user_id: str) -> None:
        async with self._locked_context("reset", user_id):
            self._prefs[user_id] = UserPreference(user_id=user_id)
            self._logger.info(f"偏好已重置: user={user_id}")

    # ---- BaseBusinessRepository 要求覆写的实现（留空，此仓库不使用标准实体 CRUD） ----

    async def _save_impl(self, model: UserPreference) -> str:
        self._prefs[model.user_id] = model.model_copy(deep=True)
        return model.user_id

    async def _get_impl(self, entity_id: str) -> UserPreference | None:
        return self._prefs.get(entity_id)

    async def _delete_impl(self, entity_id: str) -> bool:
        return bool(self._prefs.pop(entity_id, None))

    async def _list_impl(self, user_id: str, limit: int, offset: int) -> list[UserPreference]:
        return [p for uid, p in self._prefs.items() if uid == user_id]

    async def _count_impl(self, user_id: str) -> int:
        return len(self._prefs)
