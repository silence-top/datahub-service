# domains/dict/router.py — /dict-types and /dict-values routes
from fastapi import APIRouter, HTTPException, Query, status

from domains.dict.dependencies import DictServiceDep
from domains.dict.exceptions import (
    DictTypeAlreadyExistsError,
    DictTypeNotFoundError,
    DictValueDuplicateError,
    DictValueNotFoundError,
)
from domains.dict.schemas import (
    DictTypeCreate,
    DictTypeListQuery,
    DictTypeUpdate,
    DictValueCreate,
    DictValueUpdate,
)
from nexuskit_sdk import response

router = APIRouter(tags=["dict"])


def _register_exception_handlers():
    """注册自定义异常处理器，转换为标准响应。"""
    pass


# ---------------------------------------------------------------------------
# DictType CRUD
# ---------------------------------------------------------------------------

@router.get("/dict-types")
async def list_dict_types(
    svc: DictServiceDep,
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    all: bool = Query(False, description="是否返回全部（不分页）"),
):
    """查询字典类型列表。"""
    if all:
        items = await svc.list_all_types()
        return response.success(data={"items": [i.model_dump() for i in items]})
    query = DictTypeListQuery(is_active=is_active, page=page, page_size=page_size)
    items, total = await svc.list_types(query)
    return response.success(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [i.model_dump() for i in items],
    })


@router.post("/dict-types", status_code=status.HTTP_201_CREATED)
async def create_dict_type(
    svc: DictServiceDep,
    data: DictTypeCreate,
):
    """新建字典类型。"""
    try:
        obj = await svc.create_type(data)
    except DictTypeAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return response.success(data=obj.model_dump(), message="字典类型创建成功")


@router.put("/dict-types/{type_code}")
async def update_dict_type(
    type_code: str,
    data: DictTypeUpdate,
    svc: DictServiceDep,
):
    """更新字典类型。"""
    try:
        obj = await svc.update_type(type_code, data)
    except DictTypeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return response.success(data=obj.model_dump(), message="更新成功")


@router.delete("/dict-types/{type_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dict_type(type_code: str, svc: DictServiceDep):
    """删除字典类型（级联删除字典值）。"""
    try:
        await svc.delete_type(type_code)
    except DictTypeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# DictValue CRUD
# ---------------------------------------------------------------------------

@router.get("/dict-values/{type_code}")
async def list_dict_values(
    type_code: str,
    svc: DictServiceDep,
    is_active: bool | None = Query(None),
):
    """获取某类型下所有字典值。"""
    try:
        items = await svc.list_values(type_code, is_active)
    except DictTypeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return response.success(data={"items": [i.model_dump() for i in items]})


@router.post("/dict-values/{type_code}", status_code=status.HTTP_201_CREATED)
async def create_dict_value(
    type_code: str,
    data: DictValueCreate,
    svc: DictServiceDep,
):
    """新建字典值。"""
    try:
        obj = await svc.create_value(type_code, data)
    except DictTypeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DictValueDuplicateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return response.success(data=obj.model_dump(), message="字典值创建成功")


@router.put("/dict-values/{value_id}")
async def update_dict_value(
    value_id: int,
    data: DictValueUpdate,
    svc: DictServiceDep,
):
    """更新字典值。"""
    try:
        obj = await svc.update_value(value_id, data)
    except DictValueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DictValueDuplicateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return response.success(data=obj.model_dump(), message="更新成功")


@router.delete("/dict-values/{value_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dict_value(value_id: int, svc: DictServiceDep):
    """删除字典值。"""
    try:
        await svc.delete_value(value_id)
    except DictValueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
