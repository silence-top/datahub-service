# domains/slice/service.py — SliceFile business logic
from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import Sequence

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from domains.device.exceptions import (
    FileFormatNotAllowedError,
    FileSizeExceededError,
)
from domains.device.models import Device
from domains.device.service import DeviceService
from domains.slice.exceptions import (
    SliceNotFoundError,
    StorageDeleteError,
    StorageUploadError,
    UnsupportedFileFormatError,
)
from domains.slice.models import SliceFile
from domains.slice.repository import SliceRepository
from domains.slice.schemas import (
    BatchFileFailure,
    BatchConfirmRequest,
    BatchUploadResult,
    PresignBatchOut,
    PresignBatchRequest,
    PresignItemOut,
    SliceFileOut,
    SliceListQuery,
    SliceUploadMeta,
)
from integrations.storage.base import StorageClient

# 允许上传的文件扩展名白名单
_ALLOWED_EXTENSIONS = {".svs", ".ndpi", ".tiff", ".tif", ".mrxs", ".vms", ".vmu", ".scn", ".czi"}


class SliceService:
    def __init__(self, db: AsyncSession, storage: StorageClient) -> None:
        self._repo = SliceRepository(db)
        self._db = db
        self._storage = storage

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    async def upload(
        self,
        *,
        app_code: str,
        user_id: int,
        file: UploadFile,
        meta: SliceUploadMeta,
        device_code: str | None = None,
    ) -> SliceFileOut:
        """接收上传文件 → OSS → 写入 DB，返回 SliceFileOut schema。

        若传了 device_code，校验设备注册状态 + 上传规则。
        """
        original_name = file.filename or "unknown"
        ext = os.path.splitext(original_name)[1].lower()

        # ── 设备校验（可选）────────────────────
        device_id: int | None = None
        if device_code:
            device_svc = DeviceService(self._db)
            device = await device_svc.get_active_device(device_code)
            device_id = device.id

            # 规则校验
            allowed_formats: list[str] = json.loads(device.allowed_formats)
            allowed_formats_lower = [f.lower() for f in allowed_formats]
            if ext not in allowed_formats_lower:
                raise FileFormatNotAllowedError(ext, allowed_formats, original_name)

            data = await file.read()
            file_size = len(data)
            max_size_bytes = device.max_file_size_mb * 1024 * 1024
            if file_size > max_size_bytes:
                raise FileSizeExceededError(
                    file_size / (1024 * 1024), device.max_file_size_mb, original_name
                )
        else:
            # 无设备时走原有白名单
            if ext not in _ALLOWED_EXTENSIONS:
                raise UnsupportedFileFormatError(ext, list(_ALLOWED_EXTENSIONS))
            data = await file.read()
            file_size = len(data)

        file_format = ext.lstrip(".")

        # 构建 OSS key
        oss_key = StorageClient.build_key(app_code, original_name)

        # 上传到 OSS（捕获具体异常，转为域异常）
        try:
            await self._storage.upload(
                bucket=app_code,
                key=oss_key,
                data=data,
                content_type=file.content_type or "application/octet-stream",
            )
        except Exception as exc:
            raise StorageUploadError(str(exc)) from exc

        # 写入数据库
        async with self._db.begin():
            obj = await self._repo.create(
                app_code=app_code,
                device_id=device_id,
                original_name=original_name,
                file_format=file_format.upper(),
                staining_type=meta.staining_type,
                file_size=file_size,
                oss_key=oss_key,
                status="ready",
                uploaded_by=user_id,
            )
        return SliceFileOut.model_validate(obj)

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
    # Presigned direct upload (服务端签名 + 客户端直传 OSS)
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

        allowed_formats: list[str] = json.loads(device.allowed_formats)
        allowed_formats_lower = [f.lower() for f in allowed_formats]
        max_size_bytes = device.max_file_size_mb * 1024 * 1024

        batch_id = uuid.uuid4().hex
        presigns: list[PresignItemOut] = []
        skipped: list[str] = []

        # ② 逐个校验 + 生成 key + 签名
        for item in data.files:
            ext = os.path.splitext(item.filename)[1].lower()

            # 格式校验
            if ext not in allowed_formats_lower:
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
    # Batch upload (legacy proxy upload, kept for backward compatibility)
    # ------------------------------------------------------------------

    async def batch_upload(
        self,
        *,
        app_code: str,
        user_id: int,
        files: list[UploadFile],
        relative_paths: list[str],
        device_code: str,
    ) -> BatchUploadResult:
        """批量上传：多文件+文件夹，保留目录结构。

        流程：
          1. 校验设备注册状态 + 规则
          2. 逐个校验文件格式 + 大小
          3. 生成 batch_id
          4. 并发上传到 OSS
          5. 批量写入 DB
          6. 返回结果摘要
        """
        # ① 校验设备
        device_svc = DeviceService(self._db)
        device = await device_svc.get_active_device(device_code)

        # 加载设备规则
        allowed_formats: list[str] = json.loads(device.allowed_formats)
        allowed_formats_lower = [f.lower() for f in allowed_formats]
        max_size_bytes = device.max_file_size_mb * 1024 * 1024

        batch_id = uuid.uuid4().hex
        failures: list[BatchFileFailure] = []
        upload_tasks: list[dict] = []

        # ② 逐个校验
        for i, file in enumerate(files):
            original_name = file.filename or "unknown"
            ext = os.path.splitext(original_name)[1].lower()
            rel_path = relative_paths[i] if i < len(relative_paths) else original_name

            # 格式校验
            if ext not in allowed_formats_lower:
                failures.append(BatchFileFailure(
                    filename=rel_path,
                    error=f"格式 '{ext}' 不在设备允许列表 {sorted(allowed_formats)} 中",
                ))
                continue

            # 读取文件内容
            data = await file.read()
            file_size = len(data)

            # 大小校验
            if file_size > max_size_bytes:
                size_mb = file_size / (1024 * 1024)
                failures.append(BatchFileFailure(
                    filename=rel_path,
                    error=f"大小 {size_mb:.1f} MB 超过设备上限 {device.max_file_size_mb} MB",
                ))
                continue

            oss_key = StorageClient.build_key(
                app_code=app_code,
                original_filename=original_name,
                device_code=device_code,
                batch_id=batch_id,
                relative_path=rel_path,
            )

            upload_tasks.append({
                "original_name": original_name,
                "ext": ext,
                "data": data,
                "file_size": file_size,
                "oss_key": oss_key,
                "relative_path": rel_path,
                "content_type": file.content_type or "application/octet-stream",
            })

        # ③ 并发上传到 OSS
        async def _upload_one(task: dict) -> dict | None:
            try:
                await self._storage.upload(
                    bucket=app_code,
                    key=task["oss_key"],
                    data=task["data"],
                    content_type=task["content_type"],
                )
                return task
            except Exception as exc:
                failures.append(BatchFileFailure(
                    filename=task["relative_path"],
                    error=f"OSS 上传失败：{exc}",
                ))
                return None

        results = await asyncio.gather(*[_upload_one(t) for t in upload_tasks])
        successful = [r for r in results if r is not None]

        # ④ 批量写入 DB
        if successful:
            db_items = []
            for t in successful:
                db_items.append({
                    "app_code": app_code,
                    "device_id": device.id,
                    "batch_id": batch_id,
                    "relative_path": t["relative_path"],
                    "original_name": t["original_name"],
                    "file_format": t["ext"].lstrip(".").upper(),
                    "file_size": t["file_size"],
                    "oss_key": t["oss_key"],
                    "status": "ready",
                    "uploaded_by": user_id,
                })
            async with self._db.begin():
                await self._repo.batch_create(db_items)

        return BatchUploadResult(
            batch_id=batch_id,
            device_code=device_code,
            success_count=len(successful),
            failure_count=len(failures),
            failures=failures,
        )
