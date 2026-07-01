# domains/dict/service.py — Dictionary business logic
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from domains.dict.exceptions import (
    DictTypeAlreadyExistsError,
    DictTypeNotFoundError,
    DictValueDuplicateError,
    DictValueNotFoundError,
)
from domains.dict.models import DictType, DictValue
from domains.dict.repository import DictRepository
from domains.dict.schemas import (
    DictTypeCreate,
    DictTypeListQuery,
    DictTypeOut,
    DictTypeUpdate,
    DictValueCreate,
    DictValueOut,
    DictValueUpdate,
)


class DictService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = DictRepository(db)
        self._db = db

    # ------------------------------------------------------------------
    # DictType CRUD
    # ------------------------------------------------------------------

    async def create_type(self, data: DictTypeCreate) -> DictTypeOut:
        """新建字典类型。"""
        existing = await self._repo.get_type_by_code(data.type_code)
        if existing:
            raise DictTypeAlreadyExistsError(data.type_code)
        obj = await self._repo.create_type(
            type_code=data.type_code,
            type_name=data.type_name,
            description=data.description,
            is_active=True,
        )
        await self._db.commit()
        await self._db.refresh(obj)
        return DictTypeOut.model_validate(obj)

    async def update_type(self, type_code: str, data: DictTypeUpdate) -> DictTypeOut:
        """更新字典类型。"""
        obj = await self._repo.get_type_by_code(type_code)
        if obj is None:
            raise DictTypeNotFoundError(type_code)
        fields = data.model_dump(exclude_unset=True)
        obj = await self._repo.update_type(obj, **fields)
        await self._db.commit()
        await self._db.refresh(obj)
        return DictTypeOut.model_validate(obj)

    async def delete_type(self, type_code: str) -> None:
        """删除字典类型（级联删除字典值）。"""
        obj = await self._repo.get_type_by_code(type_code)
        if obj is None:
            raise DictTypeNotFoundError(type_code)
        await self._repo.delete_type(obj)
        await self._db.commit()

    async def get_type(self, type_code: str) -> DictTypeOut:
        """获取字典类型详情。"""
        obj = await self._repo.get_type_by_code(type_code)
        if obj is None:
            raise DictTypeNotFoundError(type_code)
        return DictTypeOut.model_validate(obj)

    async def list_types(self, query: DictTypeListQuery) -> tuple[list[DictTypeOut], int]:
        """分页查询字典类型列表。"""
        items, total = await self._repo.list_types(query)
        return [DictTypeOut.model_validate(i) for i in items], total

    async def list_all_types(self) -> list[DictTypeOut]:
        """获取所有活跃的字典类型（不分页）。"""
        items = await self._repo.list_all_types()
        return [DictTypeOut.model_validate(i) for i in items]

    # ------------------------------------------------------------------
    # DictValue CRUD
    # ------------------------------------------------------------------

    async def create_value(self, type_code: str, data: DictValueCreate) -> DictValueOut:
        """新建字典值。"""
        type_obj = await self._repo.get_type_by_code(type_code)
        if type_obj is None:
            raise DictTypeNotFoundError(type_code)
        existing = await self._repo.get_value_by_type_and_key(type_code, data.value_key)
        if existing:
            raise DictValueDuplicateError(type_code, data.value_key)
        obj = await self._repo.create_value(
            type_code=type_code,
            value_key=data.value_key,
            value_label=data.value_label,
            sort=data.sort,
            is_active=True,
        )
        await self._db.commit()
        await self._db.refresh(obj)
        return DictValueOut.model_validate(obj)

    async def update_value(self, value_id: int, data: DictValueUpdate) -> DictValueOut:
        """更新字典值。"""
        obj = await self._repo.get_value_by_id(value_id)
        if obj is None:
            raise DictValueNotFoundError(value_id)
        fields = data.model_dump(exclude_unset=True)
        # 如果更新 value_key，检查是否重复
        if "value_key" in fields and fields["value_key"] != obj.value_key:
            existing = await self._repo.get_value_by_type_and_key(obj.type_code, fields["value_key"])
            if existing:
                raise DictValueDuplicateError(obj.type_code, fields["value_key"])
        obj = await self._repo.update_value(obj, **fields)
        await self._db.commit()
        await self._db.refresh(obj)
        return DictValueOut.model_validate(obj)

    async def delete_value(self, value_id: int) -> None:
        """删除字典值。"""
        obj = await self._repo.get_value_by_id(value_id)
        if obj is None:
            raise DictValueNotFoundError(value_id)
        await self._repo.delete_value(obj)
        await self._db.commit()

    async def list_values(self, type_code: str, is_active: bool | None = None) -> list[DictValueOut]:
        """获取某类型下所有字典值。"""
        type_obj = await self._repo.get_type_by_code(type_code)
        if type_obj is None:
            raise DictTypeNotFoundError(type_code)
        items = await self._repo.list_values_by_type(type_code, is_active)
        return [DictValueOut.model_validate(i) for i in items]
