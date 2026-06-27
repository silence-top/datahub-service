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


def _mask_secret(secret: str) -> str:
    """脱敏 AccessKey Secret：只显示后 4 位。"""
    if len(secret) <= 4:
        return "****"
    return f"****{secret[-4:]}"


def _to_out(obj: OssConfig) -> OssConfigOut:
    """ORM → OssConfigOut（脱敏 secret）。"""
    data = {
        "id": obj.id,
        "app_code": obj.app_code,
        "config_name": obj.config_name,
        "access_key_id": obj.access_key_id,
        "access_key_secret": _mask_secret(obj.access_key_secret),
        "endpoint": obj.endpoint,
        "bucket_name": obj.bucket_name,
        "is_default": obj.is_default,
        "is_active": obj.is_active,
        "created_by": obj.created_by,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
    }
    return OssConfigOut(**data)


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
            access_key_id=data.access_key_id,
            access_key_secret=data.access_key_secret,
            endpoint=data.endpoint,
            bucket_name=data.bucket_name,
            is_default=data.is_default,
            is_active=True,
            created_by=user_id,
        )
        await self._db.commit()
        await self._db.refresh(obj)
        return _to_out(obj)

    async def update(self, config_id: int, data: OssConfigUpdate) -> OssConfigOut:
        """更新 OSS 配置。"""
        obj = await self._repo.get_by_id(config_id)
        if obj is None:
            raise OssConfigNotFoundError(config_id)

        fields = data.model_dump(exclude_unset=True)

        # 若设为默认，先取消同 app_code 的旧默认
        if fields.get("is_default") is True:
            await self._repo.clear_default(obj.app_code)

        obj = await self._repo.update(obj, **fields)
        await self._db.commit()
        await self._db.refresh(obj)
        return _to_out(obj)

    async def get(self, config_id: int) -> OssConfigOut:
        """获取配置详情。"""
        obj = await self._repo.get_by_id(config_id)
        if obj is None:
            raise OssConfigNotFoundError(config_id)
        return _to_out(obj)

    async def list(self, query: OssConfigListQuery) -> tuple[list[OssConfigOut], int]:
        """分页列表。"""
        items, total = await self._repo.list(query)
        return [_to_out(i) for i in items], total

    async def delete(self, config_id: int) -> None:
        """删除配置。"""
        obj = await self._repo.get_by_id(config_id)
        if obj is None:
            raise OssConfigNotFoundError(config_id)
        await self._repo.delete(obj)
        await self._db.commit()

    # ------------------------------------------------------------------
    # Internal helpers (供 OssStorageClient / lifespan 调用)
    # ------------------------------------------------------------------

    async def get_active_config(self, app_code: str) -> OssConfig | None:
        """按 app_code 查找活跃配置，找不到回退默认。"""
        return await self._repo.get_by_app_code(app_code)

    async def get_all_active(self) -> list[dict]:
        """获取所有活跃配置（供 OssStorageClient 初始化缓存）。"""
        configs: Sequence[OssConfig] = await self._repo.get_all_active()
        return [
            {
                "app_code": c.app_code,
                "access_key_id": c.access_key_id,
                "access_key_secret": c.access_key_secret,
                "endpoint": c.endpoint,
                "bucket_name": c.bucket_name,
                "is_default": c.is_default,
            }
            for c in configs
        ]

    async def get_all_active_for_reload(self) -> list[dict]:
        """get_all_active 的别名，语义化调用。"""
        return await self.get_all_active()
