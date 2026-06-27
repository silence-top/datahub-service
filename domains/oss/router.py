# domains/oss/router.py — /oss-configs routes
from fastapi import APIRouter, Query, Request, status

from domains.oss.dependencies import OssConfigServiceDep
from domains.oss.schemas import OssConfigCreate, OssConfigListQuery, OssConfigUpdate
from domains.oss.service import OssConfigService
from nexuskit_sdk import response

router = APIRouter(prefix="/oss-configs", tags=["oss-configs"])


async def _reload_storage(request: Request, svc: OssConfigService) -> None:
    """CRUD 操作后刷新 StorageClient 配置缓存。"""
    storage = getattr(request.app.state, "storage", None)
    if storage is not None and hasattr(storage, "reload"):
        configs = await svc.get_all_active_for_reload()
        storage.reload(configs)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_oss_config(
    request: Request,
    svc: OssConfigServiceDep,
    data: OssConfigCreate,
):
    """新建 OSS 配置。鉴权：读取网关注入的 X-User-Id。"""
    obj = await svc.register(user_id=request.state.user_id, data=data)
    await _reload_storage(request, svc)
    return response.success(data=obj.model_dump(), message="OSS 配置创建成功")


@router.get("")
async def list_oss_configs(
    svc: OssConfigServiceDep,
    app_code: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页查询 OSS 配置列表。"""
    query = OssConfigListQuery(
        app_code=app_code,
        is_active=is_active,
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


@router.get("/{config_id}")
async def get_oss_config(config_id: int, svc: OssConfigServiceDep):
    """获取 OSS 配置详情。"""
    obj = await svc.get(config_id)
    return response.success(data=obj.model_dump())


@router.put("/{config_id}")
async def update_oss_config(
    request: Request,
    config_id: int,
    data: OssConfigUpdate,
    svc: OssConfigServiceDep,
):
    """更新 OSS 配置。"""
    obj = await svc.update(config_id, data)
    await _reload_storage(request, svc)
    return response.success(data=obj.model_dump(), message="更新成功")


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_oss_config(
    request: Request,
    config_id: int,
    svc: OssConfigServiceDep,
):
    """删除 OSS 配置。"""
    await svc.delete(config_id)
    await _reload_storage(request, svc)
