# integrations/storage/base.py — 存储层抽象基类（ACL 防腐层）
"""
防腐层设计：
  - 业务域（slice service）仅依赖 StorageClient 抽象接口
  - 具体实现（OssStorageClient / MinIOClient）在运行时注入
  - 未来切换存储后端只需替换实现类，业务代码零改动
"""
from abc import ABC, abstractmethod


class StorageClient(ABC):
    """对象存储抽象接口，所有存储后端必须实现此契约。"""

    @abstractmethod
    async def upload(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """上传对象，返回 oss_key。"""
        ...

    @abstractmethod
    async def delete(self, bucket: str, key: str) -> None:
        """删除对象。"""
        ...

    @abstractmethod
    def get_presigned_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        """生成预签名下载 URL（同步方法，不涉及网络 I/O）。"""
        ...

    @abstractmethod
    async def exists(self, bucket: str, key: str) -> bool:
        """检查对象是否存在。"""
        ...

    async def batch_upload(self, bucket: str, uploads: list[dict]) -> list[str]:
        """并发上传多个对象，返回 oss_key 列表。

        uploads: [{"key": str, "data": bytes, "content_type": str}, ...]
        默认实现：asyncio.gather 并发调用 self.upload()。
        """
        import asyncio

        async def _one(item: dict) -> str:
            return await self.upload(
                bucket=bucket,
                key=item["key"],
                data=item["data"],
                content_type=item.get("content_type", "application/octet-stream"),
            )

        return list(await asyncio.gather(*[_one(u) for u in uploads]))

    @staticmethod
    def build_key(
        app_code: str,
        original_filename: str,
        prefix: str = "slices",
        device_code: str | None = None,
        batch_id: str | None = None,
        relative_path: str | None = None,
    ) -> str:
        """生成 OSS 对象路径。

        有设备+批次:
          {prefix}/{app_code}/{device_code}/{YYYY}/{batch_id}/{relative_path}
        无设备（兼容旧逻辑）:
          {prefix}/{app_code}/{YYYY}/{uuid}{ext}
        """
        import uuid
        from datetime import datetime
        from pathlib import PurePosixPath

        year = datetime.now().strftime("%Y")
        ext = PurePosixPath(original_filename).suffix.lower()

        if device_code and batch_id:
            # 保留目录结构：relative_path 含子目录 + 文件名
            path_segment = relative_path or (uuid.uuid4().hex + ext)
            return f"{prefix}/{app_code}/{device_code}/{year}/{batch_id}/{path_segment}"

        return f"{prefix}/{app_code}/{year}/{uuid.uuid4().hex}{ext}"
