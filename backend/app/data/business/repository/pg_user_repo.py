"""
PostgreSQL 用户偏好仓库 —— 实现 UserPreferenceRepository 接口。
"""

import logging
from typing import Any

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.data.interfaces import UserPreferenceRepository, UserPreference
from app.data.business.models_orm import UserPreferenceModel
from app.data.exceptions import (
    StoreWriteError,
    StoreNotFoundError,
    StoreConnectionError,
)

logger = logging.getLogger("data.business.PgUserPreferenceRepository")


class PgUserPreferenceRepository(UserPreferenceRepository):
    """PostgreSQL 用户偏好仓库。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ----------------------------------------------------------------
    # UserPreferenceRepository 接口实现
    # ----------------------------------------------------------------

    async def get(self, user_id: str) -> UserPreference:
        """获取用户偏好，不存在时返回默认值（不持久化）。"""
        try:
            async with self._session_factory() as session:
                model = await session.get(UserPreferenceModel, user_id)
                if model:
                    return model.to_pydantic()
                # 返回默认值，不写入数据库
                return UserPreference(user_id=user_id)
        except SQLAlchemyError as e:
            raise StoreNotFoundError(
                f"偏好获取失败: user={user_id}",
                store_name="PgUserPreferenceRepository",
                operation="get",
                detail=str(e),
            ) from e

    async def update(self, user_id: str, prefs: dict[str, Any]) -> None:
        """
        更新偏好（部分更新），使用 session.merge() upsert。

        先获取当前值 → 合并 → 验证 → 写入。
        """
        try:
            current = await self.get(user_id)
            merged = current.model_dump()
            merged.update(prefs)
            validated = UserPreference(**merged)

            model = UserPreferenceModel.from_pydantic(validated)
            async with self._session_factory() as session:
                await session.merge(model)
                await session.commit()
            logger.info(f"偏好已更新: user={user_id}")
        except SQLAlchemyError as e:
            raise StoreWriteError(
                f"偏好更新失败: user={user_id}",
                store_name="PgUserPreferenceRepository",
                operation="update",
                detail=str(e),
            ) from e

    async def reset(self, user_id: str) -> None:
        """重置为默认偏好（删除行，下次 get 返回默认值）。"""
        try:
            async with self._session_factory() as session:
                stmt = delete(UserPreferenceModel).where(
                    UserPreferenceModel.user_id == user_id
                )
                await session.execute(stmt)
                await session.commit()
            logger.info(f"偏好已重置: user={user_id}")
        except SQLAlchemyError as e:
            raise StoreConnectionError(
                f"偏好重置失败: user={user_id}",
                store_name="PgUserPreferenceRepository",
                operation="reset",
                detail=str(e),
            ) from e
