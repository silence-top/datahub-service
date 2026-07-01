# domains/oss/repository.py — OssConfig data-access layer
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.oss.models import OssConfig
from domains.oss.schemas import OssConfigListQuery


class OssConfigRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, **kwargs) -> OssConfig:
        obj = OssConfig(**kwargs)
        self._db.add(obj)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def update(self, obj: OssConfig, **kwargs) -> OssConfig:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def delete(self, obj: OssConfig) -> None:
        await self._db.delete(obj)
        await self._db.flush()

    async def clear_default(self, app_code: str) -> None:
        """取消指定 app_code 的默认标记。"""
        result = await self._db.execute(
            select(OssConfig).where(
                OssConfig.app_code == app_code,
                OssConfig.is_default.is_(True),
            )
        )
        for cfg in result.scalars().all():
            cfg.is_default = False
        await self._db.flush()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, config_id: int) -> OssConfig | None:
        result = await self._db.execute(select(OssConfig).where(OssConfig.id == config_id))
        return result.scalar_one_or_none()

    async def get_by_app_code(self, app_code: str) -> OssConfig | None:
        """精确匹配 app_code，找不到回退 is_default=True。"""
        result = await self._db.execute(
            select(OssConfig).where(
                OssConfig.app_code == app_code,
                OssConfig.is_active.is_(True),
            )
        )
        cfg = result.scalar_one_or_none()
        if cfg is not None:
            return cfg

        # 回退默认
        result = await self._db.execute(
            select(OssConfig).where(
                OssConfig.is_default.is_(True),
                OssConfig.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_default(self) -> OssConfig | None:
        result = await self._db.execute(
            select(OssConfig).where(
                OssConfig.is_default.is_(True),
                OssConfig.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_all_active(self) -> Sequence[OssConfig]:
        result = await self._db.execute(
            select(OssConfig).where(OssConfig.is_active.is_(True))
        )
        return result.scalars().all()

    async def list(self, query: OssConfigListQuery) -> tuple[Sequence[OssConfig], int]:
        """返回 (items, total_count)。"""
        stmt = select(OssConfig)
        if query.app_code:
            stmt = stmt.where(OssConfig.app_code == query.app_code)
        if query.is_active is not None:
            stmt = stmt.where(OssConfig.is_active.is_(query.is_active))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self._db.execute(count_stmt)).scalar_one()

        offset = (query.page - 1) * query.page_size
        stmt = stmt.order_by(OssConfig.created_at.desc()).offset(offset).limit(query.page_size)
        items = (await self._db.execute(stmt)).scalars().all()

        return items, total

    async def count_default_by_app_code(self, app_code: str) -> int:
        """统计指定 app_code 下已有几条默认配置。"""
        result = await self._db.execute(
            select(func.count()).select_from(
                select(OssConfig).where(
                    OssConfig.app_code == app_code,
                    OssConfig.is_default.is_(True),
                ).subquery()
            )
        )
        return result.scalar_one()
