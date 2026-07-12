"""
Business 数据模型 —— Pydantic + SQLAlchemy ORM。

Pydantic 模型用于接口层，ORM 模型用于 PostgreSQL 持久化。
通过 to_pydantic() / from_pydantic() 双向转换，对上层透明。
"""

from app.data.interfaces import StudyNote, UserPreference
from app.data.business.models_orm import StudyNoteModel, UserPreferenceModel

__all__ = [
    "StudyNote",
    "UserPreference",
    "StudyNoteModel",
    "UserPreferenceModel",
]
