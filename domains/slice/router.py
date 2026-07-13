# domains/slice/router.py — /slices routes
"""
统一 OSS 直传模式（STS 临时凭证）：
  - 客户端请求 STS 凭证 → 直传 OSS → 同步状态
  - 文件数据不经过服务端，服务端只负责发凭证 + 入库
"""
from fastapi import APIRouter, Query, status

from domains.slice.dependencies import DeviceAuthDep, ServiceDep
from domains.slice.schemas import (
    RegisterOut,
    RegisterRequest,
    SlideOut,
    SlideListQuery,
    SlicePresignedUrlOut,
    SlideStatusUpdate,
    UploadUrlOut,
)
from nexuskit_sdk import response

router = APIRouter(prefix="/slices", tags=["slices"])


# ---------------------------------------------------------------------------
# Slice registration
# ---------------------------------------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_slices(
    auth: DeviceAuthDep,
    svc: ServiceDep,
    data: RegisterRequest,
):
    """注册切片：创建 DB 记录（status=pending），返回 slice_id。

    此时文件尚未上传，oss_key 为空。客户端拿到 slice_id 后用于后续的：
      - 获取上传凭证（POST /slices/upload-url?slice_id=xxx）
      - 状态同步（PUT /slices/status）

    认证：通过 X-Device-Code + X-Device-Secret 请求头验证设备身份。
    """
    result = await svc.register_slices(
        app_code=auth.app_code,
        user_id=auth.device_id,
        data=data,
    )
    return response.success(data=result.model_dump(), message="注册完成")


# ---------------------------------------------------------------------------
# Upload credentials (STS 临时凭证，单文件/文件夹通用)
# ---------------------------------------------------------------------------

@router.post("/upload-url")
async def get_upload_credentials(
    svc: ServiceDep,
    auth: DeviceAuthDep,
    slice_id: int = Query(..., description="切片 ID"),
    expires: int = Query(900, ge=60, le=3600, description="凭证有效秒数（60s ~ 1h）"),
):
    """获取上传凭证（STS 临时凭证，单文件和文件夹通用）。

    返回 dir_key + STS 临时凭证，客户端使用凭证 + AWS SDK 直接上传。
    上传完成后调用 PUT /slices/status 更新状态。

    会校验切片是否属于当前设备（防止越权）。
    """
    result = await svc.get_upload_credentials(
        slice_id, expires=expires, device_id=auth.device_id,
    )
    return response.success(data=result.model_dump())


@router.put("/status")
async def update_status(
    svc: ServiceDep,
    auth: DeviceAuthDep,
    data: SlideStatusUpdate,
):
    """更新切片状态（扫描仪同步上传进度）。

    会校验切片是否属于当前设备（防止越权）。
    """
    result = await svc.update_status(data.slice_id, data, device_id=auth.device_id)
    return response.success(data=result.model_dump())


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
    query = SlideListQuery(
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
