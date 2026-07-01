# core/seed.py — 首次启动时初始化默认数据
"""Seed 默认 OSS 配置 + 默认设备 + 字典数据。

仅在对应表为空时执行，安全可重入。
"""
import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_app_settings
from domains.device.models import Device
from domains.dict.models import DictType, DictValue
from domains.oss.models import OssConfig

logger = logging.getLogger("datahub-service.seed")


async def _seed_oss_configs(db: AsyncSession) -> None:
    """如果 oss_configs 表为空，提示用户通过 API 添加配置。"""
    count = (await db.execute(select(func.count()).select_from(OssConfig))).scalar_one()
    if count > 0:
        logger.info("oss_configs 已有 %d 条配置，跳过 seed", count)
        return

    # 统一 S3 模式下，不再 seed 默认配置
    # 用户需要通过 API 添加存储配置
    logger.info("oss_configs 表为空，请通过 POST /api/v1/oss-configs 添加存储配置")


async def _seed_devices(db: AsyncSession) -> None:
    """如果 devices 表为空，插入一台默认设备。"""
    count = (await db.execute(select(func.count()).select_from(Device))).scalar_one()
    if count > 0:
        logger.info("devices 已有 %d 台设备，跳过 seed", count)
        return

    device = Device(
        app_code="datahub",
        device_code="default-device",
        device_name="默认扫描仪",
        dept_id = 1,
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
    logger.info("已 seed 默认设备: device_code=default-device, dept_id=1")


async def _seed_dict(db: AsyncSession) -> None:
    """如果 dict_types 表为空，初始化默认字典类型和字典值。"""
    count = (await db.execute(select(func.count()).select_from(DictType))).scalar_one()
    if count > 0:
        logger.info("dict_types 已有 %d 条记录，跳过 seed", count)
        return

    # 字典类型
    dict_types = [
        ("device_model", "设备型号", "扫描仪设备型号列表"),
        ("staining_type", "染色类型", "病理切片染色类型"),
        ("sample_type", "样本类型", "病理样本类型"),
    ]

    for type_code, type_name, description in dict_types:
        dt = DictType(type_code=type_code, type_name=type_name, description=description, is_active=True)
        db.add(dt)
        await db.flush()

    # 字典值：设备型号
    device_models = [
        ("leica_apario_cs2", "Leica Aperio CS2", 1),
        ("leica_apario_gt450", "Leica Aperio GT450", 2),
        ("hamamatsu_nanozoomer_s360", "Hamamatsu NanoZoomer S360", 3),
        ("3dhistech_pannoramic", "3DHISTECH PANNORAMIC", 4),
        ("roche_ventana_dp200", "Roche Ventana DP200", 5),
    ]
    for key, label, sort in device_models:
        dv = DictValue(type_code="device_model", value_key=key, value_label=label, sort=sort, is_active=True)
        db.add(dv)

    # 字典值：染色类型
    staining_types = [
        ("HE", "HE 染色", 1),
        ("IHC", "IHC 免疫组化", 2),
        ("PAS", "PAS 染色", 3),
        ("Masson", "Masson 三色染色", 4),
        ("Silver", "银染", 5),
    ]
    for key, label, sort in staining_types:
        dv = DictValue(type_code="staining_type", value_key=key, value_label=label, sort=sort, is_active=True)
        db.add(dv)

    # 字典值：样本类型
    sample_types = [
        ("组织病理", "组织病理", 1),
        ("细胞病理", "细胞病理", 2),
    ]
    for key, label, sort in sample_types:
        dv = DictValue(type_code="sample_type", value_key=key, value_label=label, sort=sort, is_active=True)
        db.add(dv)

    await db.commit()
    logger.info("已 seed 字典数据: device_model, staining_type, sample_type")


async def seed_data(db: AsyncSession) -> None:
    """首次启动时初始化默认数据。安全可重入。"""
    await _seed_oss_configs(db)
    await _seed_devices(db)
    await _seed_dict(db)
