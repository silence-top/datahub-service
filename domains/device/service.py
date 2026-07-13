# domains/device/service.py — Device business logic
import asyncio
import json
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from domains.device.exceptions import DeviceNotFoundError
from domains.device.models import Device
from domains.device.repository import DeviceRepository
from domains.device.schemas import (
    DeviceAuthOut,
    DeviceCreate,
    DeviceDetailOut,
    DeviceListQuery,
    DeviceOut,
    DeviceUpdate,
)
from integrations.core.client import CoreServiceClient


class DeviceService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = DeviceRepository(db)
        self._db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def register(self, user_id: int, data: DeviceCreate) -> DeviceOut:
        """注册新设备，自动生成唯一密钥。"""
        device_secret = secrets.token_hex(32)
        obj = await self._repo.create(
            app_code=data.app_code,
            dept_id=data.dept_id,
            device_code=data.device_code,
            device_secret=device_secret,
            device_name=data.device_name,
            model=data.model,
            manufacturer=data.manufacturer,
            allowed_formats=json.dumps(data.allowed_formats),
            allowed_staining=json.dumps(data.allowed_staining),
            max_file_size_mb=data.max_file_size_mb,
            is_active=True,
            registered_by=user_id,
        )
        await self._db.commit()
        await self._db.refresh(obj)
        return DeviceOut.model_validate(obj)

    async def update(self, device_code: str, data: DeviceUpdate) -> DeviceOut:
        """更新设备信息。"""
        obj = await self._repo.get_by_code(device_code)
        if obj is None:
            raise DeviceNotFoundError(device_code)

        fields = data.model_dump(exclude_unset=True)
        # dept_id 直接传递（整型，无需转换）
        # JSON 字段序列化为字符串
        if "allowed_formats" in fields and fields["allowed_formats"] is not None:
            fields["allowed_formats"] = json.dumps(fields["allowed_formats"])
        if "allowed_staining" in fields and fields["allowed_staining"] is not None:
            fields["allowed_staining"] = json.dumps(fields["allowed_staining"])

        obj = await self._repo.update(obj, **fields)
        await self._db.commit()
        await self._db.refresh(obj)
        return DeviceOut.model_validate(obj)

    async def get(self, device_code: str) -> DeviceOut:
        """获取设备详情。"""
        obj = await self._repo.get_by_code(device_code)
        if obj is None:
            raise DeviceNotFoundError(device_code)
        return DeviceOut.model_validate(obj)

    async def list(self, query: DeviceListQuery) -> tuple[list[DeviceOut], int]:
        """分页列表。"""
        items, total = await self._repo.list(query)
        return [DeviceOut.model_validate(i) for i in items], total

    async def delete(self, device_code: str) -> None:
        """删除设备。"""
        obj = await self._repo.get_by_code(device_code)
        if obj is None:
            raise DeviceNotFoundError(device_code)
        await self._repo.delete(obj)
        await self._db.commit()

    async def authenticate(self, device_code: str, device_secret: str) -> DeviceAuthOut:
        """验证设备编码+密钥，返回设备信息（不含密钥）。"""
        from domains.device.exceptions import DeviceAuthFailedError

        obj = await self._repo.get_by_code(device_code)
        if obj is None:
            raise DeviceAuthFailedError()
        if not obj.is_active:
            raise DeviceAuthFailedError("设备已被禁用")
        if not secrets.compare_digest(obj.device_secret, device_secret):
            raise DeviceAuthFailedError()
        return DeviceAuthOut.model_validate(obj)

    async def regenerate_secret(self, device_code: str) -> str:
        """重新生成设备密钥，返回新密钥。"""
        obj = await self._repo.get_by_code(device_code)
        if obj is None:
            raise DeviceNotFoundError(device_code)
        new_secret = secrets.token_hex(32)
        obj = await self._repo.update(obj, device_secret=new_secret)
        await self._db.commit()
        return new_secret

    # ------------------------------------------------------------------
    # Validation helpers (供 slice 域调用)
    # ------------------------------------------------------------------

    async def get_active_device(self, device_code: str) -> Device:
        """获取活跃设备，不存在或已停用抛异常。"""
        from domains.device.exceptions import DeviceInactiveError, DeviceNotRegisteredError

        obj = await self._repo.get_by_code(device_code)
        if obj is None:
            raise DeviceNotRegisteredError(device_code)
        if not obj.is_active:
            raise DeviceInactiveError(device_code)
        return obj

    async def get_device_by_id(self, device_id: int) -> Device:
        """根据 ID 获取活跃设备，不存在或已停用抛异常。"""
        from domains.device.exceptions import DeviceInactiveError, DeviceNotRegisteredError

        obj = await self._repo.get_by_id(device_id)
        if obj is None:
            raise DeviceNotRegisteredError(str(device_id))
        if not obj.is_active:
            raise DeviceInactiveError(str(device_id))
        return obj

    # ------------------------------------------------------------------
    # Enriched detail (跨服务获取部门/应用信息)
    # ------------------------------------------------------------------

    async def get_detail(
        self, device_code: str, core_client: CoreServiceClient
    ) -> DeviceDetailOut:
        """获取设备详情，后端对后端调用 core-service 获取部门和应用信息。

        如果 core-service 不可用，返回设备本地信息，关联字段为 None（优雅降级）。
        """
        obj = await self._repo.get_by_code(device_code)
        if obj is None:
            raise DeviceNotFoundError(device_code)

        # 本地字段
        detail = DeviceDetailOut.model_validate(obj)

        # 并发获取应用和部门信息（任一失败不阻塞另一个）
        async def _noop() -> None:
            return None

        app_info, dept_info = await asyncio.gather(
            core_client.get_app(obj.app_code),
            core_client.get_department(obj.dept_id) if obj.dept_id else _noop(),
            return_exceptions=True,
        )

        # 填充应用信息
        if isinstance(app_info, dict):
            detail.app_name = app_info.get("app_name")
            detail.app_perm_mode = app_info.get("perm_mode")
            detail.app_description = app_info.get("description")

        # 填充部门信息
        if isinstance(dept_info, dict):
            detail.dept_name = dept_info.get("dept_name")
            detail.dept_leader = dept_info.get("leader")
            detail.dept_phone = dept_info.get("phone")
            detail.dept_email = dept_info.get("email")
            detail.dept_is_active = dept_info.get("is_active")

        return detail
