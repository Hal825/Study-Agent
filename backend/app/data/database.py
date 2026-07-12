"""
数据库引擎模块 —— async SQLAlchemy 单例管理。

用法:
    from app.data.database import init_database, get_session_factory, close_database

    await init_database("postgresql+asyncpg://user:pass@localhost:5432/db")
    factory = get_session_factory()
    async with factory() as session:
        ...
    await close_database()
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger("data.database")

_engine = None  # type: ignore
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def init_database(database_url: str, echo: bool = False) -> None:
    """
    初始化数据库引擎和 Session 工厂。

    Args:
        database_url: postgresql+asyncpg://user:pass@host:port/db
        echo: 是否打印 SQL（调试用）
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        database_url,
        echo=echo,
        pool_size=10,
        max_overflow=20,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("数据库引擎已初始化, pool_size=10")


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    获取 Session 工厂。

    Raises:
        RuntimeError: 未调用 init_database
    """
    if _session_factory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_database()")
    return _session_factory


async def close_database() -> None:
    """关闭数据库引擎，释放连接池。"""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("数据库引擎已关闭")


async def create_tables() -> None:
    """
    自动建表（仅开发/首次部署使用，生产应使用 Alembic 迁移）。

    导入所有 ORM 模型后调用 Base.metadata.create_all。
    """
    if _engine is None:
        raise RuntimeError("数据库未初始化，请先调用 init_database()")

    from app.data.business.models_orm import Base  # noqa: E402
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表已创建/确认")
