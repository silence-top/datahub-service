# domains/slice/service.py — SliceFile business logic
from __future__ import annotations

import json
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.device.service import DeviceService
from domains.slice.exceptions import (
    SliceNotFoundError,
    StorageDeleteError,
    UnsupportedFileFormatError,
)
from domains.slice.models import SliceFile
from domains.slice.repository import SliceRepository
from domains.slice.schemas import (
    BatchFileFailure,
    BatchConfirmRequest,
    BatchUploadResult,
    FolderUploadRequest,
    FolderUploadResult,
    PresignBatchOut,
    PresignBatchRequest,
    PresignItemOut,
    SliceFileOut,
    SliceListQuery,
)
from integrations.storage.base import StorageClient

# 文件夹格式（上传软件负责遍历，服务端只记录格式标识）
_FOLDER_FORMATS = {"DZI", "LD"}


class SliceService:
    def __init__(self, db: AsyncSession, storage: StorageClient) -> None:
        self._repo = SliceRepository(db)
        self._db = db
        self._storage = storage

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def list(self, query: SliceListQuery) -> tuple[list[SliceFileOut], int]:
        items, total = await self._repo.list(query)
        return [SliceFileOut.model_validate(i) for i in items], total

    async def get(self, slice_id: int) -> SliceFileOut:
        obj = await self._repo.get_by_id(slice_id)
        if obj is None:
            raise SliceNotFoundError(slice_id)
        return SliceFileOut.model_validate(obj)

    # ------------------------------------------------------------------
    # Presigned URL
    # ------------------------------------------------------------------

    async def get_presigned_url(self, obj: SliceFileOut, expires: int = 3600) -> str:
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

        # 先删除 OSS 对象，避免数据库记录删了 OSS 还留着
        try:
            await self._storage.delete(bucket=obj.app_code, key=obj.oss_key)
            if obj.thumbnail_key:
                await self._storage.delete(bucket=obj.app_code, key=obj.thumbnail_key)
        except Exception as exc:
            raise StorageDeleteError(str(exc)) from exc

        async with self._db.begin():
            await self._repo.delete(obj)

    # ------------------------------------------------------------------
    # Presigned direct upload — 批量单文件（SVS/TIFF 等）
    # 流程：客户端请求签名 → 直传 OSS → 确认写 DB
    # ------------------------------------------------------------------

    async def presign_batch_upload(
        self,
        *,
        app_code: str,
        data: PresignBatchRequest,
    ) -> PresignBatchOut:
        """生成批量预签名 URL（文件不经后端，客户端直传 OSS）。

        流程：
          1. 校验设备注册状态 + 文件格式/大小
          2. 生成 batch_id
          3. 为每个文件生成 oss_key
          4. 调用 S3 生成 presigned PUT URL
          5. 返回签名 URL 列表
        """
        # ① 校验设备
        device_svc = DeviceService(self._db)
        device = await device_svc.get_active_device(data.device_code)

        allowed_formats: list[str] = [f.lower().lstrip(".") for f in json.loads(device.allowed_formats)]
        max_size_bytes = device.max_file_size_mb * 1024 * 1024

        batch_id = uuid.uuid4().hex
        presigns: list[PresignItemOut] = []
        skipped: list[str] = []

        # ② 逐个校验 + 生成 key + 签名
        for item in data.files:
            ext = os.path.splitext(item.filename)[1].lower().lstrip(".")

            # 格式校验
            if ext not in allowed_formats:
                skipped.append(item.filename)
                continue

            # 大小校验
            if item.file_size > max_size_bytes:
                skipped.append(item.filename)
                continue

            oss_key = StorageClient.build_key(
                app_code=app_code,
                original_filename=item.filename,
                device_code=data.device_code,
                batch_id=batch_id,
                relative_path=item.relative_path,
            )

            url = await self._storage.get_presigned_upload_url(
                bucket=app_code,
                key=oss_key,
                content_type="application/octet-stream",
                expires=300,
            )

            presigns.append(PresignItemOut(
                filename=item.filename,
                upload_url=url,
                oss_key=oss_key,
            ))

        return PresignBatchOut(
            batch_id=batch_id,
            presigns=presigns,
            expires_in=300,
        )

    async def confirm_batch_upload(
        self,
        *,
        app_code: str,
        user_id: int,
        data: BatchConfirmRequest,
    ) -> BatchUploadResult:
        """确认批量直传完成，将文件记录写入 DB。

        前置条件：文件已由客户端直传到 OSS，本方法仅写数据库。
        """
        # 查找设备
        device_svc = DeviceService(self._db)
        device = await device_svc.get_active_device(data.device_code)

        # 批量写入 DB
        db_items = []
        for item in data.files:
            db_items.append({
                "app_code": app_code,
                "device_id": device.id,
                "batch_id": data.batch_id,
                "relative_path": None,
                "original_name": item.filename,
                "file_format": item.file_format.upper(),
                "file_size": item.file_size,
                "oss_key": item.oss_key,
                "status": "ready",
                "uploaded_by": user_id,
            })

        if db_items:
            async with self._db.begin():
                await self._repo.batch_create(db_items)

        return BatchUploadResult(
            batch_id=data.batch_id,
            device_code=data.device_code,
            success_count=len(db_items),
            failure_count=0,
        )

    # ------------------------------------------------------------------
    # Presigned direct upload — 文件夹格式（DZI/LD）
    # 流程：上传软件遍历文件夹 → 签名 → 直传 OSS → 确认写 DB
    # ------------------------------------------------------------------

    async def presign_folder_upload(
        self,
        *,
        app_code: str,
        device_code: str,
        data: FolderUploadRequest,
    ) -> PresignBatchOut:
        """为文件夹格式生成预签名上传 URL（DZI/LD 格式）。

        上传软件负责遍历文件夹，服务端只记录格式标识。
        """
        # ① 校验格式
        file_format = data.format.upper()
        if file_format not in _FOLDER_FORMATS:
            raise UnsupportedFileFormatError(file_format, list(_FOLDER_FORMATS))

        batch_id = uuid.uuid4().hex
        presigns: list[PresignItemOut] = []

        # ② 为每个文件生成 presigned URL
        for item in data.files:
            oss_key = StorageClient.build_key(
                app_code=app_code,
                original_filename=data.folder_name,
                device_code=device_code,
                batch_id=batch_id,
                relative_path=item.relative_path,
            )

            url = await self._storage.get_presigned_upload_url(
                bucket=app_code,
                key=oss_key,
                content_type="application/octet-stream",
                expires=300,
            )

            presigns.append(PresignItemOut(
                filename=item.filename,
                upload_url=url,
                oss_key=oss_key,
            ))

        return PresignBatchOut(
            batch_id=batch_id,
            presigns=presigns,
            expires_in=300,
        )

    async def confirm_folder_upload(
        self,
        *,
        app_code: str,
        user_id: int,
        data: FolderUploadRequest,
        batch_id: str,
        oss_keys: list[str],
    ) -> FolderUploadResult:
        """确认文件夹格式上传完成（文件已直传到 OSS）。

        将文件夹内所有文件记录写入 DB，file_format 统一为 DZI/LD。
        """
        # 校验格式
        file_format = data.format.upper()
        if file_format not in _FOLDER_FORMATS:
            raise UnsupportedFileFormatError(file_format, list(_FOLDER_FORMATS))

        # 批量写入 DB
        db_items = []
        for i, item in enumerate(data.files):
            db_items.append({
                "app_code": app_code,
                "device_id": user_id,
                "batch_id": batch_id,
                "relative_path": item.relative_path,
                "original_name": item.filename,
                "file_format": file_format,
                "staining_type": data.staining_type or "UNKNOWN",
                "file_size": item.file_size,
                "oss_key": oss_keys[i],
                "status": "ready",
                "uploaded_by": user_id,
            })

        if db_items:
            async with self._db.begin():
                await self._repo.batch_create(db_items)

        return FolderUploadResult(
            batch_id=batch_id,
            folder_name=data.folder_name,
            file_format=file_format,
            success_count=len(db_items),
            failure_count=0,
        )
