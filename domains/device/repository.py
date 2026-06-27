# domains/device/repository.py — Device data-access layer
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.device.models import Device
from domains.device.schemas import DeviceListQuery


class DeviceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, **kwargs) -> Device:
        obj = Device(**kwargs)
        self._db.add(obj)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def update(self, obj: Device, **kwargs) -> Device:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def delete(self, obj: Device) -> None:
        await self._db.delete(obj)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, device_id: int) -> Device | None:
        result = await self._db.execute(select(Device).where(Device.id == device_id))
        return result.scalar_one_or_none()

    async def get_by_code(self, device_code: str) -> Device | None:
        result = await self._db.execute(select(Device).where(Device.device_code == device_code))
        return result.scalar_one_or_none()

    async def list(self, query: DeviceListQuery) -> tuple[Sequence[Device], int]:
        """返回 (items, total_count)。"""
        stmt = select(Device)
        if query.app_code:
            stmt = stmt.where(Device.app_code == query.app_code)
        if query.is_active is not None:
            stmt = stmt.where(Device.is_active.is_(query.is_active))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self._db.execute(count_stmt)).scalar_one()

        offset = (query.page - 1) * query.page_size
        stmt = stmt.order_by(Device.created_at.desc()).offset(offset).limit(query.page_size)
        items = (await self._db.execute(stmt)).scalars().all()

        return items, total
