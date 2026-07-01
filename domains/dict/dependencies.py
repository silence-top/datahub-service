# domains/dict/dependencies.py — Dictionary domain DI wiring
"""
依赖注入集中管理，Router 通过 Annotated[T, Depends(...)] 消费。
"""
from typing import Annotated

from fastapi import Depends

from core.db import DbDep
from domains.dict.service import DictService


def _get_service(db: DbDep) -> DictService:
    return DictService(db=db)


DictServiceDep = Annotated[DictService, Depends(_get_service)]
