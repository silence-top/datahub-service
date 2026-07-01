# domains/dict/repository.py — Dictionary data-access layer
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.dict.models import DictType, DictValue
from domains.dict.schemas import DictTypeListQuery


class DictRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # DictType
    # ------------------------------------------------------------------

    async def create_type(self, **kwargs) -> DictType:
        obj = DictType(**kwargs)
        self._db.add(obj)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def update_type(self, obj: DictType, **kwargs) -> DictType:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def delete_type(self, obj: DictType) -> None:
        await self._db.delete(obj)
        await self._db.flush()

    async def get_type_by_code(self, type_code: str) -> DictType | None:
        result = await self._db.execute(
            select(DictType).where(DictType.type_code == type_code)
        )
        return result.scalar_one_or_none()

    async def list_types(self, query: DictTypeListQuery) -> tuple[Sequence[DictType], int]:
        """返回 (items, total_count)。"""
        stmt = select(DictType)
        if query.is_active is not None:
            stmt = stmt.where(DictType.is_active.is_(query.is_active))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self._db.execute(count_stmt)).scalar_one()

        offset = (query.page - 1) * query.page_size
        stmt = stmt.order_by(DictType.created_at.desc()).offset(offset).limit(query.page_size)
        items = (await self._db.execute(stmt)).scalars().all()

        return items, total

    async def list_all_types(self) -> Sequence[DictType]:
        """返回所有活跃的字典类型（不分页）。"""
        result = await self._db.execute(
            select(DictType).where(DictType.is_active.is_(True)).order_by(DictType.type_name)
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # DictValue
    # ------------------------------------------------------------------

    async def create_value(self, **kwargs) -> DictValue:
        obj = DictValue(**kwargs)
        self._db.add(obj)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def update_value(self, obj: DictValue, **kwargs) -> DictValue:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def delete_value(self, obj: DictValue) -> None:
        await self._db.delete(obj)
        await self._db.flush()

    async def get_value_by_id(self, value_id: int) -> DictValue | None:
        result = await self._db.execute(
            select(DictValue).where(DictValue.id == value_id)
        )
        return result.scalar_one_or_none()

    async def get_value_by_type_and_key(self, type_code: str, value_key: str) -> DictValue | None:
        result = await self._db.execute(
            select(DictValue).where(
                DictValue.type_code == type_code,
                DictValue.value_key == value_key,
            )
        )
        return result.scalar_one_or_none()

    async def list_values_by_type(self, type_code: str, is_active: bool | None = None) -> Sequence[DictValue]:
        """获取某类型下所有字典值，按 sort 排序。"""
        stmt = select(DictValue).where(DictValue.type_code == type_code)
        if is_active is not None:
            stmt = stmt.where(DictValue.is_active.is_(is_active))
        stmt = stmt.order_by(DictValue.sort, DictValue.value_label)
        result = await self._db.execute(stmt)
        return result.scalars().all()
