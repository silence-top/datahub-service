# domains/slice/router.py — /slices routes
import json

from fastapi import APIRouter, Form, Query, Request, UploadFile, status

from domains.slice.dependencies import DeviceAuthDep, ServiceDep
from domains.slice.schemas import (
    BatchConfirmRequest,
    BatchUploadResult,
    PresignBatchOut,
    PresignBatchRequest,
    SliceFileOut,
    SliceListQuery,
    SlicePresignedUrlOut,
    SliceUploadMeta,
)
from nexuskit_sdk import response

router = APIRouter(prefix="/slices", tags=["slices"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_slice(
    request: Request,
    svc: ServiceDep,
    file: UploadFile,
    staining_type: str = Form(...),
    description: str | None = Form(None),
    device_code: str | None = Form(None, description="设备编码（可选，传则校验注册状态）"),
):
    """上传病理切片文件（multipart/form-data）。

    鉴权：读取网关注入的 `X-User-Id` 和 `X-App-Code`（由 GatewayAuthMiddleware 验证并注入 request.state）。
    若传了 device_code，会校验设备注册状态和上传规则。
    """
    meta = SliceUploadMeta(
        staining_type=staining_type,
        description=description,
    )
    obj = await svc.upload(
        app_code=request.state.app_code,
        user_id=request.state.user_id,
        file=file,
        meta=meta,
        device_code=device_code,
    )
    return response.success(data=obj.model_dump())


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


# ---------------------------------------------------------------------------
# Presigned direct upload (服务端签名 + 客户端直传 OSS)
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


# ---------------------------------------------------------------------------
# Batch upload
# ---------------------------------------------------------------------------

@router.post("/batch-upload", status_code=status.HTTP_201_CREATED)
async def batch_upload(
    request: Request,
    svc: ServiceDep,
    files: list[UploadFile],
    relative_paths: str = Form(..., description="JSON 数组：每个文件对应的相对路径"),
    device_code: str = Form(..., description="设备编码（必须已注册）"),
    staining_type: str | None = Form(None),
):
    """批量上传：多文件+文件夹，保留目录结构。

    鉴权：读取网关注入的 `X-User-Id` 和 `X-App-Code`。
    """
    paths = json.loads(relative_paths)
    result = await svc.batch_upload(
        app_code=request.state.app_code,
        user_id=request.state.user_id,
        files=files,
        relative_paths=paths,
        device_code=device_code,
    )
    return response.success(data=result.model_dump())
