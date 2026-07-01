# domains/slice/dependencies.py — Slice domain DI wiring
"""
依赖注入集中管理，Router 通过 Annotated[T, Depends(...)] 消费。
"""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from core.db import DbDep
from integrations.storage.base import StorageClient
from domains.slice.service import SliceService


def _get_storage(request: Request) -> StorageClient:
    """从 app.state 获取存储客户端（由 main.py lifespan 注入）。"""
    return request.app.state.storage


def _get_service(db: DbDep, storage: StorageClient = Depends(_get_storage)) -> SliceService:
    return SliceService(db=db, storage=storage)


@dataclass(frozen=True)
class DeviceAuth:
    """设备认证结果，从请求头读取 device_code + device_secret 验证。"""
    app_code: str
    device_id: int
    device_code: str


async def _aget_device_auth(request: Request, db: DbDep) -> DeviceAuth:
    """异步版本：从请求头验证设备身份。"""
    import secrets as _secrets

    device_code = request.headers.get("X-Device-Code")
    device_secret = request.headers.get("X-Device-Secret")

    if not device_code or not device_secret:
        raise HTTPException(status_code=401, detail="未授权：请求头缺少 X-Device-Code 和 X-Device-Secret")

    from domains.device.repository import DeviceRepository

    repo = DeviceRepository(db)
    obj = await repo.get_by_code(device_code)

    if obj is None or not _secrets.compare_digest(obj.device_secret, device_secret):
        raise HTTPException(status_code=401, detail="认证失败：设备编码或密钥错误")
    if not obj.is_active:
        raise HTTPException(status_code=403, detail="设备已被禁用")

    return DeviceAuth(
        app_code=obj.app_code,
        device_id=obj.id,
        device_code=obj.device_code,
    )


StorageDep = Annotated[StorageClient, Depends(_get_storage)]
ServiceDep = Annotated[SliceService, Depends(_get_service)]
DeviceAuthDep = Annotated[DeviceAuth, Depends(_aget_device_auth)]
