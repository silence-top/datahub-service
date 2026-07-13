# core/lifespan.py — Application startup / shutdown hooks
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.db import AsyncSessionLocal, engine
from core.outbox import LogBroker, OutboxRelay
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

    # --- 4. 启动 Outbox Relay（事件发布到 MQ）---
    broker = LogBroker()  # 生产环境替换为 KafkaBroker / RabbitMQBroker
    relay = OutboxRelay(broker, poll_interval=5.0)
    relay_task = asyncio.create_task(relay.run())
    app.state.outbox_relay = relay
    logger.info("OutboxRelay 已启动 (LogBroker 模式, poll_interval=5s)")

    yield

    # --- Shutdown ---
    logger.info("Datahub Service shutting down...")
    relay.stop()
    await relay_task
    await broker.close()
    await app.state.core_client.close()
    await engine.dispose()
