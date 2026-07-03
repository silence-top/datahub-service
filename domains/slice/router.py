# domains/slice/router.py — /slices routes
"""
统一 OSS 直传模式：
  - 客户端请求预签名 URL → 直传 OSS → 通知服务端写 DB
  - 文件数据不经过服务端，服务端只负责签名 + 入库
"""
import json

from fastapi import APIRouter, Query, status

from domains.slice.dependencies import DeviceAuthDep, ServiceDep
from domains.slice.schemas import (
    BatchConfirmRequest,
    BatchUploadResult,
    FolderUploadRequest,
    FolderUploadResult,
    PresignBatchOut,
    PresignBatchRequest,
    SliceFileOut,
    SliceListQuery,
    SlicePresignedUrlOut,
)
from nexuskit_sdk import response

router = APIRouter(prefix="/slices", tags=["slices"])


# ---------------------------------------------------------------------------
# Presigned direct upload — 批量单文件（SVS/TIFF 等）
# 流程：客户端签名 → 直传 OSS → 确认写 DB
# ---------------------------------------------------------------------------

@router.post("/presign-upload-urls")
async def presign_upload_urls(
    auth: DeviceAuthDep,
    svc: ServiceDep,
    data: PresignBatchRequest,
):
    """生成批量预签名上传 URL（客户端直传 OSS，文件不经后端）。

    认证：通过 X-Device-Code + X-Device-Secret 请求头验证设备身份。
    校验设备注册状态 + 文件格式/大小规则。
    """
    result = await svc.presign_batch_upload(
        app_code=auth.app_code,
        data=data,
    )
    return response.success(data=result.model_dump())


@router.post("/batch-confirm", status_code=status.HTTP_201_CREATED)
async def batch_confirm(
    auth: DeviceAuthDep,
    svc: ServiceDep,
    data: BatchConfirmRequest,
):
    """确认批量直传完成（文件已直传到 OSS，本接口仅写入 DB）。

    认证：通过 X-Device-Code + X-Device-Secret 请求头验证设备身份。
    """
    result = await svc.confirm_batch_upload(
        app_code=auth.app_code,
        user_id=auth.device_id,
        data=data,
    )
    return response.success(data=result.model_dump(), message="批量确认完成")


# ---------------------------------------------------------------------------
# Presigned direct upload — 文件夹格式（DZI/LD）
# 流程：上传软件遍历文件夹 → 签名 → 直传 OSS → 确认写 DB
# ---------------------------------------------------------------------------

@router.post("/folder-presign-urls")
async def folder_presign_urls(
    auth: DeviceAuthDep,
    svc: ServiceDep,
    data: FolderUploadRequest,
):
    """为文件夹格式（DZI/LD）生成预签名上传 URL。

    上传软件负责遍历文件夹，服务端只记录格式标识。
    客户端直传 OSS，文件不经后端。

    认证：通过 X-Device-Code + X-Device-Secret 请求头验证设备身份。
    """
    result = await svc.presign_folder_upload(
        app_code=auth.app_code,
        device_code=auth.device_code,
        data=data,
    )
    return response.success(data=result.model_dump())


@router.post("/folder-confirm", status_code=status.HTTP_201_CREATED)
async def folder_confirm(
    auth: DeviceAuthDep,
    svc: ServiceDep,
    data: FolderUploadRequest,
    batch_id: str = Query(..., description="批次 ID"),
    oss_keys: str = Query(..., description="JSON 数组：每个文件对应的 OSS key"),
):
    """确认文件夹格式上传完成（文件已直传到 OSS）。

    将文件夹内所有文件记录写入 DB，file_format 统一为 DZI/LD。
    """
    keys = json.loads(oss_keys)
    result = await svc.confirm_folder_upload(
        app_code=auth.app_code,
        user_id=auth.device_id,
        data=data,
        batch_id=batch_id,
        oss_keys=keys,
    )
    return response.success(data=result.model_dump(), message="文件夹上传完成")


# ---------------------------------------------------------------------------
# Query / Download / Delete
# ---------------------------------------------------------------------------

@router.get("")
async def list_slices(
    svc: ServiceDep,
    app_code: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页查询切片列表，支持 app_code / status 过滤。"""
    query = SliceListQuery(
        app_code=app_code,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    items, total = await svc.list(query)
    return response.success(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [i.model_dump() for i in items],
    })


@router.get("/{slice_id}")
async def get_slice(slice_id: int, svc: ServiceDep):
    """获取切片元数据详情。"""
    obj = await svc.get(slice_id)
    return response.success(data=obj.model_dump())


@router.get("/{slice_id}/url")
async def get_presigned_url(
    slice_id: int,
    svc: ServiceDep,
    expires: int = Query(3600, ge=60, le=86400, description="URL 有效秒数（60s ~ 24h）"),
):
    """获取 OSS 预签名下载 URL。"""
    obj = await svc.get(slice_id)
    url = await svc.get_presigned_url(obj, expires=expires)
    result = SlicePresignedUrlOut(slice_id=slice_id, url=url, expires_in=expires)
    return response.success(data=result.model_dump())


@router.delete("/{slice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slice(slice_id: int, svc: ServiceDep):
    """删除切片记录及 OSS 对象。"""
    await svc.delete(slice_id)
