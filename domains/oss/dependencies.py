# domains/oss/dependencies.py — OSS config domain DI wiring
"""
依赖注入集中管理，Router 通过 Annotated[T, Depends(...)] 消费。
"""
from typing import Annotated

from fastapi import Depends

from core.db import DbDep
from domains.oss.service import OssConfigService


def _get_service(db: DbDep) -> OssConfigService:
    return OssConfigService(db=db)


OssConfigServiceDep = Annotated[OssConfigService, Depends(_get_service)]
