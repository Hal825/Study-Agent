"""
PostgreSQL 笔记仓库 —— 实现 NoteRepository 接口。

直接实现接口（不继承 BaseBusinessRepository）以避免 asyncio.Lock
序列化所有 DB 操作 —— PostgreSQL 自身保证并发安全。
"""

import logging
import time
from typing import Optional

from sqlalchemy import select, func, desc, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.data.interfaces import NoteRepository, StudyNote
from app.data.business.models_orm import StudyNoteModel
from app.data.exceptions import (
    StoreWriteError,
    StoreNotFoundError,
    StoreConnectionError,
    StoreIntegrityError,
)

logger = logging.getLogger("data.business.PgNoteRepository")


def _gen_id() -> str:
    """生成笔记 ID。"""
    return f"note_{int(time.time() * 1000)}_{id(object()) & 0xFFFF:04x}"


class PgNoteRepository(NoteRepository):
    """PostgreSQL 笔记仓库。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ----------------------------------------------------------------
    # NoteRepository 接口实现
    # ----------------------------------------------------------------

    async def save(self, note: StudyNote) -> str:
        """保存笔记，返回 note_id。"""
        if not note.id:
            note.id = _gen_id()
        if not note.created_at:
            note.created_at = time.time()

        model = StudyNoteModel.from_pydantic(note)

        try:
            async with self._session_factory() as session:
                session.add(model)
                await session.commit()
            logger.info(f"笔记已保存: id={model.id}")
            return model.id
        except IntegrityError as e:
            raise StoreIntegrityError(
                f"笔记保存失败 (完整性约束): id={note.id}",
                store_name="PgNoteRepository",
                operation="save",
                detail=str(e),
            ) from e
        except SQLAlchemyError as e:
            raise StoreWriteError(
                f"笔记保存失败: id={note.id}",
                store_name="PgNoteRepository",
                operation="save",
                detail=str(e),
            ) from e

    async def get(self, note_id: str) -> Optional[StudyNote]:
        """按 ID 获取笔记。"""
        try:
            async with self._session_factory() as session:
                model = await session.get(StudyNoteModel, note_id)
                return model.to_pydantic() if model else None
        except SQLAlchemyError as e:
            raise StoreNotFoundError(
                f"笔记获取失败: id={note_id}",
                store_name="PgNoteRepository",
                operation="get",
                detail=str(e),
            ) from e

    async def list_by_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[StudyNote]:
        """列出用户笔记，按时间倒序。"""
        try:
            async with self._session_factory() as session:
                stmt = (
                    select(StudyNoteModel)
                    .where(StudyNoteModel.user_id == user_id)
                    .order_by(desc(StudyNoteModel.created_at))
                    .offset(offset)
                    .limit(limit)
                )
                result = await session.execute(stmt)
                models = result.scalars().all()
                return [m.to_pydantic() for m in models]
        except SQLAlchemyError as e:
            raise StoreNotFoundError(
                f"笔记列表查询失败: user={user_id}",
                store_name="PgNoteRepository",
                operation="list",
                detail=str(e),
            ) from e

    async def delete(self, note_id: str) -> bool:
        """删除笔记，返回是否成功。"""
        try:
            async with self._session_factory() as session:
                stmt = delete(StudyNoteModel).where(
                    StudyNoteModel.id == note_id
                )
                result = await session.execute(stmt)
                await session.commit()
                deleted = result.rowcount > 0
                if deleted:
                    logger.info(f"笔记已删除: id={note_id}")
                return deleted
        except SQLAlchemyError as e:
            raise StoreNotFoundError(
                f"笔记删除失败: id={note_id}",
                store_name="PgNoteRepository",
                operation="delete",
                detail=str(e),
            ) from e

    async def count_by_user(self, user_id: str) -> int:
        """用户笔记总数。"""
        try:
            async with self._session_factory() as session:
                stmt = (
                    select(func.count())
                    .select_from(StudyNoteModel)
                    .where(StudyNoteModel.user_id == user_id)
                )
                result = await session.execute(stmt)
                return result.scalar_one()
        except SQLAlchemyError as e:
            raise StoreConnectionError(
                f"笔记计数失败: user={user_id}",
                store_name="PgNoteRepository",
                operation="count",
                detail=str(e),
            ) from e
