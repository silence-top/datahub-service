# core/seed.py — 首次启动时初始化默认数据
"""Seed 默认 OSS 配置 + 默认设备。

仅在对应表为空时执行，安全可重入。
"""
import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import (
    OSS_ACCESS_KEY_ID,
    OSS_ACCESS_KEY_SECRET,
    OSS_BUCKET_MAP,
    OSS_ENDPOINT,
)
from domains.device.models import Device
from domains.oss.models import OssConfig

logger = logging.getLogger("datahub-service.seed")


async def _seed_oss_configs(db: AsyncSession) -> None:
    """如果 oss_configs 表为空，从 .env 的 OSS_* 变量初始化一条默认配置。"""
    count = (await db.execute(select(func.count()).select_from(OssConfig))).scalar_one()
    if count > 0:
        logger.info("oss_configs 已有 %d 条配置，跳过 seed", count)
        return

    if not OSS_ACCESS_KEY_ID or not OSS_ACCESS_KEY_SECRET or not OSS_ENDPOINT:
        logger.warning("OSS_* 环境变量为空，跳过 OSS 配置 seed。请通过 API 手动添加 OSS 配置。")
        return

    # 从 OSS_BUCKET_MAP 解析 default bucket
    try:
        bucket_map = json.loads(OSS_BUCKET_MAP)
    except (json.JSONDecodeError, TypeError):
        bucket_map = {}

    default_bucket = bucket_map.get("default", "bucket-default")

    cfg = OssConfig(
        app_code="default",
        config_name="默认OSS",
        access_key_id=OSS_ACCESS_KEY_ID,
        access_key_secret=OSS_ACCESS_KEY_SECRET,
        endpoint=OSS_ENDPOINT,
        bucket_name=default_bucket,
        is_default=True,
        is_active=True,
        created_by=1,  # admin
    )
    db.add(cfg)
    await db.commit()
    logger.info("已 seed 默认 OSS 配置: endpoint=%s, bucket=%s", OSS_ENDPOINT, default_bucket)


async def _seed_devices(db: AsyncSession) -> None:
    """如果 devices 表为空，插入一台默认设备。"""
    count = (await db.execute(select(func.count()).select_from(Device))).scalar_one()
    if count > 0:
        logger.info("devices 已有 %d 台设备，跳过 seed", count)
        return

    device = Device(
        app_code="diagnosis",
        device_code="default-scanner",
        device_name="默认扫描仪",
        model="Generic",
        manufacturer=None,
        allowed_formats='[".svs",".ndpi",".tiff",".tif",".mrxs"]',
        allowed_staining='["HE","IHC","PAS","Masson"]',
        max_file_size_mb=500,
        is_active=True,
        registered_by=1,  # admin
    )
    db.add(device)
    await db.commit()
    logger.info("已 seed 默认设备: device_code=default-scanner")


async def seed_data(db: AsyncSession) -> None:
    """首次启动时初始化默认数据。安全可重入。"""
    await _seed_oss_configs(db)
    await _seed_devices(db)
