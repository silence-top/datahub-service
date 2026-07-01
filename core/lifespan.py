# core/lifespan.py — Application startup / shutdown hooks
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.db import AsyncSessionLocal, engine
from core.seed import seed_data
from domains.oss.service import OssConfigService
from integrations.core.client import CoreServiceClient
from integrations.storage.s3 import S3StorageClient

logger = logging.getLogger("datahub-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Datahub Service starting up...")

    # --- 1. 初始化默认数据（存储配置 + 默认设备）---
    async with AsyncSessionLocal() as db:
        await seed_data(db)

    # --- 2. 从 DB 加载 Bucket 配置，初始化 S3StorageClient ---
    async with AsyncSessionLocal() as db:
        svc = OssConfigService(db)
        configs = await svc.get_all_active()

    app.state.storage = S3StorageClient(configs=configs)
    logger.info("S3StorageClient 已初始化: %d 个 Bucket 映射", len(configs))

    # --- 3. 初始化 Core-service 跨服务客户端 ---
    app.state.core_client = CoreServiceClient()
    logger.info("CoreServiceClient 已初始化")

    yield

    logger.info("Datahub Service shutting down...")
    await app.state.core_client.close()
    await engine.dispose()
