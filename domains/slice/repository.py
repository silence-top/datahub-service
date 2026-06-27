# domains/slice/repository.py — SliceFile data-access layer
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.slice.models import SliceFile
from domains.slice.schemas import SliceListQuery


class SliceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, **kwargs) -> SliceFile:
        obj = SliceFile(**kwargs)
        self._db.add(obj)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def update_status(
        self,
        slice_id: int,
        status: str,
        thumbnail_key: str | None = None,
    ) -> SliceFile | None:
        obj = await self.get_by_id(slice_id)
        if obj is None:
            return None
        obj.status = status
        if thumbnail_key is not None:
            obj.thumbnail_key = thumbnail_key
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def delete(self, obj: SliceFile) -> None:
        await self._db.delete(obj)
        await self._db.flush()

    async def batch_create(self, items: list[dict]) -> list[SliceFile]:
        """批量插入切片记录。"""
        objs = [SliceFile(**data) for data in items]
        self._db.add_all(objs)
        await self._db.flush()
        for obj in objs:
            await self._db.refresh(obj)
        return objs

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, slice_id: int) -> SliceFile | None:
        result = await self._db.execute(
            select(SliceFile).where(SliceFile.id == slice_id)
        )
        return result.scalar_one_or_none()

    async def get_by_oss_key(self, oss_key: str) -> SliceFile | None:
        result = await self._db.execute(
            select(SliceFile).where(SliceFile.oss_key == oss_key)
        )
        return result.scalar_one_or_none()

    async def list(self, query: SliceListQuery) -> tuple[Sequence[SliceFile], int]:
        """返回 (items, total_count)。"""
        stmt = select(SliceFile)
        if query.app_code:
            stmt = stmt.where(SliceFile.app_code == query.app_code)
        if query.status:
            stmt = stmt.where(SliceFile.status == query.status)

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self._db.execute(count_stmt)).scalar_one()

        # Paginated items
        offset = (query.page - 1) * query.page_size
        stmt = stmt.order_by(SliceFile.created_at.desc()).offset(offset).limit(query.page_size)
        items = (await self._db.execute(stmt)).scalars().all()

        return items, total
