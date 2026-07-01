# domains/oss/service.py — OssConfig business logic
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from domains.oss.exceptions import OssConfigNotFoundError
from domains.oss.models import OssConfig
from domains.oss.repository import OssConfigRepository
from domains.oss.schemas import (
    OssConfigCreate,
    OssConfigListQuery,
    OssConfigOut,
    OssConfigUpdate,
)


def _to_out(obj: OssConfig) -> OssConfigOut:
    """ORM → OssConfigOut。"""
    return OssConfigOut(
        id=obj.id,
        app_code=obj.app_code,
        config_name=obj.config_name,
        endpoint_url=obj.endpoint_url,
        region_name=obj.region_name,
        bucket_name=obj.bucket_name,
        is_default=obj.is_default,
        is_active=obj.is_active,
        created_by=obj.created_by,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


class OssConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = OssConfigRepository(db)
        self._db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def register(self, *, user_id: int, data: OssConfigCreate) -> OssConfigOut:
        """新建 OSS 配置。"""
        # 若标记为默认，先取消同 app_code 的旧默认
        if data.is_default:
            existing_count = await self._repo.count_default_by_app_code(data.app_code)
            if existing_count > 0:
                await self._repo.clear_default(data.app_code)

        obj = await self._repo.create(
            app_code=data.app_code,
            config_name=data.config_name,
            endpoint_url=data.endpoint_url,
            region_name=data.region_name,
            bucket_name=data.bucket_name,
            is_default=data.is_default,
            is_active=True,
            created_by=user_id,
        )
        await self._db.commit()
        await self._db.refresh(obj)
        return _to_out(obj)

    async def get(self, config_id: int) -> OssConfigOut:
        """按 ID 获取单个 OSS 配置。"""
        obj = await self._repo.get(config_id)
        if not obj:
            raise OssConfigNotFoundError(config_id)
        return _to_out(obj)

    async def update(self, config_id: int, data: OssConfigUpdate) -> OssConfigOut:
        """更新 OSS 配置。"""
        obj = await self._repo.get(config_id)
        if not obj:
            raise OssConfigNotFoundError(config_id)

        fields = data.model_dump(exclude_unset=True)

        # 如果要更新 is_default，先清除旧默认
        if "is_default" in fields and fields["is_default"] is True:
            await self._repo.clear_default(obj.app_code)

        obj = await self._repo.update(obj, **fields)
        await self._db.commit()
        await self._db.refresh(obj)
        return _to_out(obj)

    async def delete(self, config_id: int) -> None:
        """删除 OSS 配置。"""
        obj = await self._repo.get(config_id)
        if not obj:
            raise OssConfigNotFoundError(config_id)
        await self._repo.delete(obj)
        await self._db.commit()

    async def list(self, query: OssConfigListQuery) -> tuple[Sequence[OssConfigOut], int]:
        """列出 OSS 配置。"""
        items, total = await self._repo.list(query)
        return [_to_out(item) for item in items], total

    # ------------------------------------------------------------------
    # Internal helpers (供 S3StorageClient / lifespan 调用)
    # ------------------------------------------------------------------

    async def get_active_config(self, app_code: str) -> OssConfig | None:
        """按 app_code 查找活跃配置，找不到回退默认。"""
        return await self._repo.get_by_app_code(app_code)

    async def get_all_active(self) -> list[dict]:
        """获取所有活跃配置（供 S3StorageClient 初始化缓存）。"""
        configs: Sequence[OssConfig] = await self._repo.get_all_active()
        return [
            {
                "app_code": c.app_code,
                "endpoint_url": c.endpoint_url,
                "region_name": c.region_name,
                "bucket_name": c.bucket_name,
                "is_default": c.is_default,
            }
            for c in configs
        ]

    async def get_all_active_for_reload(self) -> list[dict]:
        """get_all_active 的别名，语义化调用。"""
        return await self.get_all_active()