# domains/slice/dependencies.py — Slice domain DI wiring
"""
依赖注入集中管理，Router 通过 Annotated[T, Depends(...)] 消费。

域间通信严格走 Service 互调，禁止直接 import 其他域的 Repository / models。
"""
import secrets as _secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from core.db import DbDep
from domains.device.exceptions import DeviceAuthFailedError
from domains.device.service import DeviceService
from domains.slice.service import SlideService
from integrations.storage.base import StorageClient


def _get_storage(request: Request) -> StorageClient:
    """从 app.state 获取存储客户端（由 main.py lifespan 注入）。"""
    return request.app.state.storage


def _get_service(db: DbDep, storage: StorageClient = Depends(_get_storage)) -> SlideService:
    return SlideService(db=db, storage=storage)


@dataclass(frozen=True)
class DeviceAuth:
    """设备认证结果。"""
    app_code: str
    device_id: int
    device_code: str


async def _aget_device_auth(request: Request, db: DbDep) -> DeviceAuth:
    """从请求头验证设备身份，通过 DeviceService 互调（避免跨域深路径 import）。"""
    device_code = request.headers.get("X-Device-Code")
    device_secret = request.headers.get("X-Device-Secret")


    if not device_code or not device_secret:
        raise DeviceAuthFailedError("请求头缺少 X-Device-Code 和 X-Device-Secret")

    # 通过 DeviceService 互调（其内部会校验设备注册状态 + 活跃状态）
    device_svc = DeviceService(db)
    obj = await device_svc.get_active_device(device_code)

    if not _secrets.compare_digest(obj.device_secret, device_secret):
        raise DeviceAuthFailedError()

    return DeviceAuth(
        app_code=obj.app_code,
        device_id=obj.id,
        device_code=obj.device_code,
    )


StorageDep = Annotated[StorageClient, Depends(_get_storage)]
ServiceDep = Annotated[SlideService, Depends(_get_service)]
DeviceAuthDep = Annotated[DeviceAuth, Depends(_aget_device_auth)]
