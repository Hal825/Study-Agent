"""
笔记仓库 —— 开发环境用内存实现。

继承 BaseBusinessRepository，复用异步锁、日志、异常封装。
"""

import time
from typing import Optional

from app.data.interfaces import NoteRepository, StudyNote
from app.data.business.base import BaseBusinessRepository


def _gen_id() -> str:
    return f"note_{int(time.time() * 1000)}_{id(object()) & 0xFFFF:04x}"


class MemoryNoteRepository(BaseBusinessRepository[StudyNote], NoteRepository):
    """基于内存字典的笔记存储（线程安全）。"""

    def __init__(self) -> None:
        super().__init__(name="MemoryNoteRepository")
        self._notes: dict[str, StudyNote] = {}

    # ---- NoteRepository 接口实现 ----

    async def save(self, note: StudyNote) -> str:
        return await super().save(note)

    async def get(self, note_id: str) -> Optional[StudyNote]:
        return await super().get(note_id)

    async def delete(self, note_id: str) -> bool:
        return await super().delete(note_id)

    async def list_by_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[StudyNote]:
        return await super().list_by_user(user_id, limit, offset)

    async def count_by_user(self, user_id: str) -> int:
        return await super().count_by_user(user_id)

    # ---- BaseBusinessRepository 要求覆写的实现 ----

    async def _save_impl(self, model: StudyNote) -> str:
        if not model.id:
            model.id = _gen_id()
        if not model.created_at:
            model.created_at = time.time()
        self._notes[model.id] = model.model_copy(deep=True)
        return model.id

    async def _get_impl(self, entity_id: str) -> Optional[StudyNote]:
        note = self._notes.get(entity_id)
        return note.model_copy(deep=True) if note else None

    async def _delete_impl(self, entity_id: str) -> bool:
        if entity_id in self._notes:
            del self._notes[entity_id]
            return True
        return False

    async def _list_impl(
        self, user_id: str, limit: int, offset: int
    ) -> list[StudyNote]:
        user_notes = [
            n for n in self._notes.values() if n.user_id == user_id
        ]
        user_notes.sort(key=lambda n: n.created_at, reverse=True)
        return user_notes[offset: offset + limit]

    async def _count_impl(self, user_id: str) -> int:
        return sum(1 for n in self._notes.values() if n.user_id == user_id)
