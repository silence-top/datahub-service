# integrations/storage/s3.py — 统一 S3 协议存储实现
"""
统一 S3 协议驱动，支持：
  - AWS S3
  - MinIO (自建)
  - 阿里云 OSS (S3 兼容模式)
  - 腾讯云 COS (S3 兼容)
  - 其他 S3 兼容服务

使用 aiobotocore 实现异步 S3 操作。
AK/SK 从 .env 读取（全局共享），Endpoint/Region/Bucket 从数据库 oss_configs 表加载。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiobotocore.session
from aiobotocore.config import AioConfig
from botocore.exceptions import ClientError

from core.config import get_s3_settings
from integrations.storage.base import StorageClient

logger = logging.getLogger("datahub-service.storage")


class S3StorageClient(StorageClient):
    """统一 S3 协议存储实现，支持所有 S3 兼容服务。"""

    def __init__(self, configs: list[dict] | None = None) -> None:
        """初始化 S3 客户端。

        configs: [{
            "app_code": str,              # 应用编码 (路由键)
            "endpoint_url": str | None,   # S3 Endpoint
            "region_name": str,           # 区域
            "bucket_name": str,           # Bucket 名称
            "is_default": bool,           # 是否默认
        }, ...]

        S3 凭证从 .env 读取（全局共享）：
          - S3_ACCESS_KEY_ID
          - S3_SECRET_ACCESS_KEY
        """
        self._session = aiobotocore.session.get_session()

        # 配置缓存：app_code → config dict
        self._config_map: dict[str, dict] = {}
        self._default_app_code: str | None = None

        # S3 客户端缓存：app_code → client
        self._s3_clients: dict[str, aiobotocore.client.AioBaseClient] = {}

        if configs:
            self.reload(configs)

    def reload(self, configs: list[dict]) -> None:
        """重新加载配置缓存（CRUD 变更时调用）。"""
        self._config_map = {}
        self._default_app_code = None
        self._s3_clients.clear()

        for c in configs:
            app_code = c["app_code"]
            self._config_map[app_code] = c
            if c.get("is_default"):
                self._default_app_code = app_code

        logger.info("S3 配置缓存已刷新: %d 个映射, default=%s",
                     len(self._config_map),
                     self._default_app_code or "None")

    def _get_config(self, app_code: str) -> dict:
        """按 app_code 查找配置，找不到回退默认。"""
        config = self._config_map.get(app_code)
        if config:
            return config

        if self._default_app_code:
            return self._config_map[self._default_app_code]

        raise ValueError(
            f"找不到 app_code='{app_code}' 的 OSS 配置且无默认配置，请先在平台添加配置"
        )

    @asynccontextmanager
    async def _get_s3_client(self, app_code: str, config: dict) -> AsyncGenerator[aiobotocore.client.AioBaseClient, None]:
        """按需创建 S3 客户端（连接池复用）。"""
        if app_code not in self._s3_clients:
            s3_config = AioConfig(
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
            )

            client = await self._session.create_client(
                's3',
                endpoint_url=config.get("endpoint_url") or None,
                aws_access_key_id=get_s3_settings().S3_ACCESS_KEY_ID,
                aws_secret_access_key=get_s3_settings().S3_SECRET_ACCESS_KEY,
                region_name=config.get("region_name", "us-east-1"),
                config=s3_config,
            )
            self._s3_clients[app_code] = client
            logger.debug("创建 S3 客户端: app=%s, bucket=%s, endpoint=%s",
                         app_code, config["bucket_name"],
                         config.get("endpoint_url") or "AWS S3 (default)")

        yield self._s3_clients[app_code]

    async def upload(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """上传文件到 S3 存储，返回 key。"""
        config = self._get_config(bucket)
        bucket_name = config["bucket_name"]

        async with self._get_s3_client(bucket, config) as client:
            await client.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
            )

        return key

    async def get_presigned_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        """生成预签名下载 URL，默认有效期 1 小时。"""
        config = self._get_config(bucket)
        bucket_name = config["bucket_name"]

        async with self._get_s3_client(bucket, config) as client:
            url = await client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': key,
                },
                ExpiresIn=expires,
            )

        return url

    async def get_presigned_upload_url(self, bucket: str, key: str, content_type: str = "application/octet-stream", expires: int = 300) -> str:
        """生成预签名上传 URL（PUT），客户端可直传文件到 OSS。"""
        config = self._get_config(bucket)
        bucket_name = config["bucket_name"]

        async with self._get_s3_client(bucket, config) as client:
            url = await client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': key,
                    'ContentType': content_type,
                },
                ExpiresIn=expires,
            )

        return url

    async def delete(self, bucket: str, key: str) -> None:
        """删除 S3 对象。"""
        config = self._get_config(bucket)
        bucket_name = config["bucket_name"]

        async with self._get_s3_client(bucket, config) as client:
            await client.delete_object(
                Bucket=bucket_name,
                Key=key,
            )

    async def exists(self, bucket: str, key: str) -> bool:
        """检查 S3 对象是否存在。"""
        config = self._get_config(bucket)
        bucket_name = config["bucket_name"]

        async with self._get_s3_client(bucket, config) as client:
            try:
                await client.head_object(
                    Bucket=bucket_name,
                    Key=key,
                )
                return True
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    return False
                raise

    async def close(self) -> None:
        """关闭所有 S3 客户端连接。"""
        for app_code, client in self._s3_clients.items():
            try:
                await client.close()
                logger.debug("关闭 S3 客户端: app=%s", app_code)
            except Exception as e:
                logger.warning("关闭 S3 客户端失败: app=%s, error=%s", app_code, e)
        self._s3_clients.clear()
