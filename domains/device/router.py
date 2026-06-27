# domains/device/router.py — /devices routes
from fastapi import APIRouter, Query, Request, status

from domains.device.dependencies import CoreClientDep, DeviceServiceDep
from domains.device.schemas import DeviceCreate, DeviceListQuery, DeviceUpdate
from nexuskit_sdk import response

router = APIRouter(prefix="/devices", tags=["devices"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def register_device(
    request: Request,
    svc: DeviceServiceDep,
    data: DeviceCreate,
):
    """注册新设备。鉴权：读取网关注入的 X-User-Id。"""
    data.app_code = request.state.app_code
    obj = await svc.register(user_id=request.state.user_id, data=data)
    return response.success(data=obj.model_dump(), message="设备注册成功")


@router.get("")
async def list_devices(
    svc: DeviceServiceDep,
    app_code: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页查询设备列表。"""
    query = DeviceListQuery(
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


@router.get("/{device_code}")
async def get_device(device_code: str, svc: DeviceServiceDep):
    """获取设备详情。"""
    obj = await svc.get(device_code)
    return response.success(data=obj.model_dump())


@router.put("/{device_code}")
async def update_device(
    device_code: str,
    data: DeviceUpdate,
    svc: DeviceServiceDep,
):
    """更新设备信息。"""
    obj = await svc.update(device_code, data)
    return response.success(data=obj.model_dump(), message="更新成功")


@router.delete("/{device_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_code: str, svc: DeviceServiceDep):
    """删除设备。"""
    await svc.delete(device_code)


# ---------------------------------------------------------------------------
# Enriched detail (跨服务获取部门/应用信息)
# ---------------------------------------------------------------------------

@router.get("/{device_code}/detail")
async def get_device_detail(
    device_code: str,
    svc: DeviceServiceDep,
    core: CoreClientDep,
):
    """获取设备详情（含部门和应用信息，后端对后端从 core-service 获取）。

    管理员接口，需鉴权。
    """
    detail = await svc.get_detail(device_code, core)
    return response.success(data=detail.model_dump())


# ---------------------------------------------------------------------------
# Scanner endpoint (扫描仪专用，白名单免鉴权)
# ---------------------------------------------------------------------------

@router.get("/scanner/device/{device_code}")
async def scanner_get_device(
    device_code: str,
    svc: DeviceServiceDep,
    core: CoreClientDep,
):
    """扫描仪专用：获取设备信息（含部门/应用详情）。

    无需用户鉴权，通过网关白名单访问。
    """
    detail = await svc.get_detail(device_code, core)
    return response.success(data=detail.model_dump())
