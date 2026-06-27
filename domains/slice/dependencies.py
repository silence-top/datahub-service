# domains/slice/dependencies.py — Slice domain DI wiring
"""
依赖注入集中管理，Router 通过 Annotated[T, Depends(...)] 消费。
"""
from typing import Annotated

from fastapi import Depends, Request

from core.db import DbDep
from integrations.storage.base import StorageClient
from domains.slice.service import SliceService


def _get_storage(request: Request) -> StorageClient:
    """从 app.state 获取存储客户端（由 main.py lifespan 注入）。"""
    return request.app.state.storage


def _get_service(db: DbDep, storage: StorageClient = Depends(_get_storage)) -> SliceService:
    return SliceService(db=db, storage=storage)


StorageDep = Annotated[StorageClient, Depends(_get_storage)]
ServiceDep = Annotated[SliceService, Depends(_get_service)]
