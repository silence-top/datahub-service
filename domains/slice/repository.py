# domains/slice/repository.py — Slide data-access layer
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.slice.models import Slide
from domains.slice.schemas import SlideListQuery


class SlideRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, **kwargs) -> Slide:
        obj = Slide(**kwargs)
        self._db.add(obj)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def update_status(
        self,
        slice_id: int,
        status: str,
        thumbnail_key: str | None = None,
    ) -> Slide | None:
        obj = await self.get_by_id(slice_id)
        if obj is None:
            return None
        obj.status = status
        if thumbnail_key is not None:
            obj.thumbnail_key = thumbnail_key
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def delete(self, obj: Slide) -> None:
        await self._db.delete(obj)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, slice_id: int) -> Slide | None:
        result = await self._db.execute(
            select(Slide).where(Slide.id == slice_id)
        )
        return result.scalar_one_or_none()

    async def get_by_oss_key(self, oss_key: str) -> Slide | None:
        result = await self._db.execute(
            select(Slide).where(Slide.oss_key == oss_key)
        )
        return result.scalar_one_or_none()

    async def list(self, query: SlideListQuery) -> tuple[Sequence[Slide], int]:
        """返回 (items, total_count)。"""
        stmt = select(Slide)
        if query.app_code:
            stmt = stmt.where(Slide.app_code == query.app_code)
        if query.status:
            stmt = stmt.where(Slide.status == query.status)

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self._db.execute(count_stmt)).scalar_one()

        # Paginated items
        offset = (query.page - 1) * query.page_size
        stmt = stmt.order_by(Slide.created_at.desc()).offset(offset).limit(query.page_size)
        items = (await self._db.execute(stmt)).scalars().all()

        return items, total
