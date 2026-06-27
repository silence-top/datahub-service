# integrations/storage/oss.py — 阿里云 OSS 存储实现
"""
阿里云 OSS 驱动，实现 StorageClient 抽象接口。
支持多 OSS 实例：配置由数据库管理，启动时通过 lifespan 加载到内存缓存。
"""
from __future__ import annotations

import asyncio
import io
import logging

import oss2

from integrations.storage.base import StorageClient

logger = logging.getLogger("datahub-service.storage")


class OssStorageClient(StorageClient):
    """阿里云 OSS 具体实现，配置从 DB 动态加载。"""

    def __init__(self, configs: list[dict] | None = None) -> None:
        """初始化时接收配置列表。

        configs: [{"app_code": str, "access_key_id": str, "access_key_secret": str,
                   "endpoint": str, "bucket_name": str, "is_default": bool}, ...]
        """
        self._configs: dict[str, dict] = {}
        self._default: dict | None = None
        if configs:
            self.reload(configs)

    def reload(self, configs: list[dict]) -> None:
        """重新加载 OSS 配置缓存（配置变更时调用）。"""
        self._configs = {}
        self._default = None
        for c in configs:
            self._configs[c["app_code"]] = c
            if c.get("is_default"):
                self._default = c
        logger.info("OSS 配置缓存已刷新: %d 条配置, default=%s",
                     len(self._configs),
                     self._default["app_code"] if self._default else "None")

    def _get_config(self, app_code: str) -> dict:
        """按 app_code 查找配置，找不到回退默认。"""
        cfg = self._configs.get(app_code) or self._default
        if not cfg:
            raise ValueError(
                f"找不到 app_code='{app_code}' 的 OSS 配置且无默认配置，请先在平台添加 OSS 配置"
            )
        return cfg

    def _get_bucket(self, app_code: str) -> oss2.Bucket:
        """按 app_code 返回对应 Bucket 客户端。"""
        cfg = self._get_config(app_code)
        auth = oss2.Auth(cfg["access_key_id"], cfg["access_key_secret"])
        return oss2.Bucket(auth, cfg["endpoint"], cfg["bucket_name"])

    async def upload(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """上传文件到 OSS，返回 oss_key。在线程池中执行阻塞 IO。"""
        oss_bucket = self._get_bucket(bucket)

        def _put():
            headers = {"Content-Type": content_type}
            oss_bucket.put_object(key, io.BytesIO(data), headers=headers)

        await asyncio.get_event_loop().run_in_executor(None, _put)
        return key

    def get_presigned_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        """生成预签名下载 URL，默认有效期 1 小时。"""
        oss_bucket = self._get_bucket(bucket)
        return oss_bucket.sign_url("GET", key, expires)

    async def delete(self, bucket: str, key: str) -> None:
        """删除 OSS 对象。"""
        oss_bucket = self._get_bucket(bucket)

        def _del():
            oss_bucket.delete_object(key)

        await asyncio.get_event_loop().run_in_executor(None, _del)

    async def exists(self, bucket: str, key: str) -> bool:
        """检查 OSS 对象是否存在。"""
        oss_bucket = self._get_bucket(bucket)
        try:
            await asyncio.get_event_loop().run_in_executor(None, lambda: oss_bucket.head_object(key))
            return True
        except oss2.exceptions.NoSuchKey:
            return False
