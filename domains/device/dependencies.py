# domains/device/dependencies.py — Device domain DI wiring
"""
依赖注入集中管理，Router 通过 Annotated[T, Depends(...)] 消费。
"""
from typing import Annotated

from fastapi import Depends, Request

from core.db import DbDep
from domains.device.service import DeviceService
from integrations.core.client import CoreServiceClient


def _get_service(db: DbDep) -> DeviceService:
    return DeviceService(db=db)


def _get_core_client(request: Request) -> CoreServiceClient:
    return request.app.state.core_client


DeviceServiceDep = Annotated[DeviceService, Depends(_get_service)]
CoreClientDep = Annotated[CoreServiceClient, Depends(_get_core_client)]
