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
    async def get_presigned_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        """生成预签名下载 URL（异步方法）。"""
        ...

    @abstractmethod
    async def get_sts_credentials(
        self, bucket: str, dir_key: str, expires: int = 900
    ) -> dict:
        """获取 STS 临时凭证，限定只能写入指定目录前缀。

        返回格式：
        {
            "access_key_id": str,
            "secret_access_key": str,
            "session_token": str,
            "expiration": str (ISO 8601),
        }
        """
        ...

    @abstractmethod
    async def exists(self, bucket: str, key: str) -> bool:
        """检查对象是否存在。"""
        ...

    @abstractmethod
    def get_config(self, app_code: str) -> dict:
        """获取存储配置（provider, endpoint_url, region_name, bucket_name, role_arn）。

        返回：{"provider": str, "endpoint_url": str|None, "region_name": str, "bucket_name": str, "role_arn": str|None}
        """
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
        slide_code: str,
        prefix: str = "slices",
        device_code: str | None = None,
        original_filename: str | None = None,
        relative_path: str | None = None,
        is_folder: bool = False,
    ) -> str:
        """生成 OSS 对象路径。

        以样本为单位，目录段使用 slide_code（不带文件后缀）。

        单文件（SVS/TIFF）：
          {prefix}/{device_code}/{YYYY-MM-DD}/{slide_code}_{uuid}/{filename}
          示例：slices/scanner-001/2026-07-06/340C_a1b2c3d4/340C.svs

        文件夹（DZI/LD）：
          {prefix}/{device_code}/{YYYY-MM-DD}/{slide_code}_{uuid}
          示例：slices/scanner-001/2026-07-06/340C_a1b2c3d4
        """
        import uuid
        from datetime import datetime
        from pathlib import PurePosixPath

        today = datetime.now().strftime("%Y-%m-%d")
        uid = uuid.uuid4().hex[:8]
        dev = device_code or "unknown"

        # 目录段：slide_code 不带文件后缀
        sc = PurePosixPath(slide_code).stem

        if is_folder:
            # DZI/LD：oss_key 指向目录
            return f"{prefix}/{dev}/{today}/{sc}_{uid}"
        else:
            # 单文件：oss_key 指向文件
            filename = original_filename or slide_code
            return f"{prefix}/{dev}/{today}/{sc}_{uid}/{filename}"
