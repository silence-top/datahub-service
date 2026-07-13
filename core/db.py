# core/db.py — Async SQLAlchemy engine + session factory
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import get_db_settings


def _build_engine():
    settings = get_db_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


engine = _build_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """提供 AsyncSession，事务边界由各 Service 自行掌控。

    注意：这里**不**自动 commit / rollback，避免与 Service 内显式 commit 冲突，
    特别是 Outbox 模式下业务数据与 outbox 事件必须在同一个 commit 原子提交。
    """
    async with AsyncSessionLocal() as session:
        yield session


DbDep = Annotated[AsyncSession, Depends(get_db)]
