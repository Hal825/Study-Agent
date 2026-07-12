"""
SQLAlchemy ORM 模型 —— 对应 PostgreSQL 表。

每个模型提供 to_pydantic() / from_pydantic() 转换方法，
对上层使用 Pydantic 模型的代码透明。
"""

from sqlalchemy import String, Text, Float, Boolean, JSON, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    pass


class StudyNoteModel(Base):
    """笔记表 —— study_notes。"""

    __tablename__ = "study_notes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), default="")
    template: Mapped[str] = mapped_column(String(50), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    source_content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float, default=0.0)

    # 联合索引：按用户 + 时间倒序查询
    __table_args__ = (
        Index("idx_notes_user_created", "user_id", "created_at"),
    )

    def to_pydantic(self):
        """转换为 Pydantic StudyNote。"""
        from app.data.interfaces import StudyNote
        return StudyNote(
            id=self.id,
            user_id=self.user_id,
            title=self.title,
            template=self.template,
            content=self.content,
            source_content=self.source_content,
            created_at=self.created_at,
        )

    @classmethod
    def from_pydantic(cls, note):
        """从 Pydantic StudyNote 构建 ORM 实例。"""
        return cls(
            id=note.id,
            user_id=note.user_id,
            title=note.title,
            template=note.template,
            content=note.content,
            source_content=note.source_content,
            created_at=note.created_at,
        )


class UserPreferenceModel(Base):
    """用户偏好表 —— user_preferences。

    注意: SQLAlchemy Base 有保留属性 metadata，
    因此 ORM 字段命名为 metadata_，对应数据库列 "metadata"。
    """

    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    preferred_template: Mapped[str] = mapped_column(
        String(50), default="outline"
    )
    preferred_depth: Mapped[str] = mapped_column(
        String(20), default="detailed"
    )
    language: Mapped[str] = mapped_column(String(10), default="zh")
    enable_auto_save: Mapped[bool] = mapped_column(Boolean, default=True)
    prefs: Mapped[dict] = mapped_column(
        "prefs", JSON, default=dict
    )

    def to_pydantic(self):
        """转换为 Pydantic UserPreference。"""
        from app.data.interfaces import UserPreference
        return UserPreference(
            user_id=self.user_id,
            preferred_template=self.preferred_template,
            preferred_depth=self.preferred_depth,
            language=self.language,
            enable_auto_save=self.enable_auto_save,
            metadata=self.prefs,
        )

    @classmethod
    def from_pydantic(cls, pref):
        """从 Pydantic UserPreference 构建 ORM 实例。"""
        return cls(
            user_id=pref.user_id,
            preferred_template=pref.preferred_template,
            preferred_depth=pref.preferred_depth,
            language=pref.language,
            enable_auto_save=pref.enable_auto_save,
            prefs=pref.metadata,
        )
