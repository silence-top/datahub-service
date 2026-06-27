# core/lifespan.py — Application startup / shutdown hooks
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.db import AsyncSessionLocal, engine
from core.seed import seed_data
from domains.oss.service import OssConfigService
from integrations.core.client import CoreServiceClient
from integrations.storage.oss import OssStorageClient

logger = logging.getLogger("datahub-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Datahub Service starting up...")

    # --- 1. 初始化默认数据（OSS 配置 + 默认设备）---
    async with AsyncSessionLocal() as db:
        await seed_data(db)

    # --- 2. 从 DB 加载活跃 OSS 配置，初始化 StorageClient ---
    async with AsyncSessionLocal() as db:
        svc = OssConfigService(db)
        configs = await svc.get_all_active()

    if configs:
        app.state.storage = OssStorageClient(configs)
        logger.info("StorageClient 已初始化: %d 条 OSS 配置", len(configs))
    else:
        # 无配置时创建空客户端，后续通过 API 添加配置后 reload
        app.state.storage = OssStorageClient()
        logger.warning("无活跃 OSS 配置，StorageClient 为空。请通过 API 添加 OSS 配置。")

    # --- 3. 初始化 Core-service 跨服务客户端 ---
    app.state.core_client = CoreServiceClient()
    logger.info("CoreServiceClient 已初始化")

    yield

    logger.info("Datahub Service shutting down...")
    await app.state.core_client.close()
    await engine.dispose()
