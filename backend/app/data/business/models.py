"""
Business 数据模型。

当前为 Pydantic 模型（Phase 1），后续可迁移为 SQLAlchemy ORM 模型。
"""

from app.data.interfaces import StudyNote, UserPreference

# Phase 1 直接使用 interfaces 中的 Pydantic 模型。
# 后续引入 SQLAlchemy 时，在此文件中定义 ORM 模型并同时实现
# to_pydantic() / from_pydantic() 转换方法，对上层透明。

__all__ = ["StudyNote", "UserPreference"]
