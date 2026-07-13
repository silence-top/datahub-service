# domains/slice/service.py — Slide business logic
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.outbox import EventPublisher
from domains.device.service import DeviceService
from domains.slice.exceptions import (
    SliceNotFoundError,
    StorageDeleteError,
)
from domains.slice.models import Slide
from domains.slice.repository import SlideRepository
from domains.slice.schemas import (
    RegisterOut,
    RegisterRequest,
    STSCredentials,
    SlideOut,
    SlideListQuery,
    SlideStatusUpdate,
    UploadUrlOut,
)
from integrations.storage.base import StorageClient

# 跨域异常（设备权限相关）
from domains.device.exceptions import DeviceSlicePermissionError


class SlideService:
    def __init__(self, db: AsyncSession, storage: StorageClient) -> None:
        self._repo = SlideRepository(db)
        self._db = db
        self._storage = storage
        self._publisher = EventPublisher(db)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_device_ownership(obj: Slide, device_id: int | None) -> None:
        """校验设备是否为该切片的所属设备。device_id 为空时跳过校验。"""
        print(f"_check_device_ownership: obj={obj.device_id    }, device_id={device_id}")
        if device_id is not None and obj.device_id != device_id:
            raise DeviceSlicePermissionError(obj.id, device_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def list(self, query: SlideListQuery) -> tuple[list[SlideOut], int]:
        items, total = await self._repo.list(query)
        return [SlideOut.model_validate(i) for i in items], total

    async def get(self, slice_id: int) -> SlideOut:
        obj = await self._repo.get_by_id(slice_id)
        if obj is None:
            raise SliceNotFoundError(slice_id)
        return SlideOut.model_validate(obj)

    # ------------------------------------------------------------------
    # Status update
    # ------------------------------------------------------------------

    async def update_status(
        self, slice_id: int, data: SlideStatusUpdate, *, device_id: int | None = None,
    ) -> SlideOut:
        """更新切片状态（扫描仪同步上传进度）。

        当 device_id 不为空时，会校验该设备是否为该切片的所属设备（防止越权）。
        """
        obj = await self._repo.get_by_id(slice_id)
        if obj is None:
            raise SliceNotFoundError(slice_id)
        self._check_device_ownership(obj, device_id)

        old_status = obj.status
        obj.status = data.status
        # error 状态可附加错误信息（暂存在 thumbnail_key 字段或扩展字段）
        # TODO: 如需专门的 error_message 字段，需扩展模型

        # 发布状态变更事件（同一事务）
        await self._publisher.publish(
            event_type="slice.status_changed",
            aggregate_type="slice",
            aggregate_id=slice_id,
            payload={
                "slice_id": slice_id,
                "slide_code": obj.slide_code,
                "old_status": old_status,
                "new_status": data.status,
                "app_code": obj.app_code,
                "error_message": data.error_message,
            },
        )

        await self._db.commit()
        await self._db.refresh(obj)
        return SlideOut.model_validate(obj)

    # ------------------------------------------------------------------
    # Presigned URL
    # ------------------------------------------------------------------

    async def get_presigned_url(self, obj: SlideOut, expires: int = 3600) -> str:
        return await self._storage.get_presigned_url(
            bucket=obj.app_code,
            key=obj.oss_key,
            expires=expires,
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, slice_id: int) -> None:
        # 先获取记录
        obj = await self._repo.get_by_id(slice_id)
        if obj is None:
            raise SliceNotFoundError(slice_id)

        # 删除前先快照字段（对象删除后属性读取可能失效）
        snapshot = {
            "slice_id": slice_id,
            "slide_code": obj.slide_code,
            "oss_key": obj.oss_key,
            "app_code": obj.app_code,
            "thumbnail_key": obj.thumbnail_key,
        }

        # 先删除 OSS 对象，避免数据库记录删了 OSS 还留着
        try:
            await self._storage.delete(bucket=snapshot["app_code"], key=snapshot["oss_key"])
            if snapshot["thumbnail_key"]:
                await self._storage.delete(bucket=snapshot["app_code"], key=snapshot["thumbnail_key"])
        except Exception as exc:
            raise StorageDeleteError(str(exc)) from exc

        await self._repo.delete(obj)

        # 发布删除事件（同一事务，使用快照字段）
        await self._publisher.publish(
            event_type="slice.deleted",
            aggregate_type="slice",
            aggregate_id=slice_id,
            payload=snapshot,
        )

        await self._db.commit()

    # ------------------------------------------------------------------
    # Slice registration
    # ------------------------------------------------------------------

    async def register_slices(
        self,
        *,
        app_code: str,
        user_id: int,
        data: RegisterRequest,
    ) -> RegisterOut:
        """注册切片：创建 DB 记录（status=pending），返回 slice_id。

        此时文件尚未上传，oss_key 为空。
        """
        # 查找设备
        device_svc = DeviceService(self._db)
        device = await device_svc.get_active_device(data.device_code)

        # 创建记录
        obj = await self._repo.create(
            app_code=app_code,
            device_id=device.id,
            slide_code=data.slide_code,
            file_format=data.file_format.upper(),
            staining_type=data.staining_type.upper() if data.staining_type else None,
            file_size=data.file_size,
            status="pending",
            uploaded_by=user_id,
        )

        # 发布注册事件（同一事务）
        await self._publisher.publish(
            event_type="slice.registered",
            aggregate_type="slice",
            aggregate_id=obj.id,
            payload={
                "slice_id": obj.id,
                "slide_code": obj.slide_code,
                "file_format": obj.file_format,
                "staining_type": obj.staining_type,
                "file_size": obj.file_size,
                "device_code": data.device_code,
                "app_code": app_code,
            },
        )

        await self._db.commit()

        return RegisterOut(
            slice_id=obj.id,
            slide_code=obj.slide_code,
            status=obj.status,
        )

    # ------------------------------------------------------------------
    # Upload credentials (STS 临时凭证，单文件/文件夹通用)
    # ------------------------------------------------------------------

    async def get_upload_credentials(
        self, slice_id: int, expires: int = 900, *, device_id: int | None = None,
    ) -> UploadUrlOut:
        """获取上传凭证（STS 临时凭证，单文件和文件夹通用）。

        流程：
          1. 查找 slice_id 对应的记录
          2. 校验设备对该切片的所有权
          3. 计算 dir_key 并写入 DB
          4. 获取 STS 临时凭证（限定只能写入 dir_key）
          5. 返回凭证

        客户端使用凭证 + AWS SDK 直接上传文件到 OSS。
        上传完成后调用 PUT /slices/status 更新状态。
        """
        obj = await self._repo.get_by_id(slice_id)
        if obj is None:
            raise SliceNotFoundError(slice_id)
        self._check_device_ownership(obj, device_id)

        # 获取设备信息（用于生成 dir_key）
        device_svc = DeviceService(self._db)
        device = await device_svc.get_device_by_id(obj.device_id)

        # 生成目录级 dir_key（单文件和文件夹都是目录前缀）
        dir_key = StorageClient.build_key(
            app_code=obj.app_code,
            slide_code=obj.slide_code,
            device_code=device.device_code,
            is_folder=True,  # 统一使用目录级 key
        )

        # 获取 STS 临时凭证
        creds = await self._storage.get_sts_credentials(
            bucket=obj.app_code,
            dir_key=dir_key,
            expires=expires,
        )

        # 获取存储配置
        storage_config = self._storage.get_config(obj.app_code)

        # 更新 oss_key（目录级）和 batch_id
        obj.oss_key = dir_key
        obj.batch_id = obj.batch_id or uuid.uuid4().hex
        await self._db.commit()

        return UploadUrlOut(
            slice_id=obj.id,
            dir_key=dir_key,
            endpoint_url=storage_config["endpoint_url"],
            region_name=storage_config["region_name"],
            bucket_name=storage_config["bucket_name"],
            credentials=STSCredentials(**creds),
            expires_in=expires,
        )

