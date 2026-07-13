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

import hashlib
import hmac
import base64
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import quote, urlencode

import aiobotocore.session
import httpx
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
    
            # aiobotocore 的 create_client 返回的是异步上下文管理器
            # 我们需要先创建上下文管理器，然后 __aenter__ 获取 client
            ctx = self._session.create_client(
                's3',
                endpoint_url=config.get("endpoint_url") or None,
                aws_access_key_id=get_s3_settings().S3_ACCESS_KEY_ID,
                aws_secret_access_key=get_s3_settings().S3_SECRET_ACCESS_KEY,
                region_name=config.get("region_name", "us-east-1"),
                config=s3_config,
            )
            client = await ctx.__aenter__()
            self._s3_clients[app_code] = (ctx, client)
            logger.debug("创建 S3 客户端：app=%s, bucket=%s, endpoint=%s",
                         app_code, config["bucket_name"],
                         config.get("endpoint_url") or "AWS S3 (default)")
    
        yield self._s3_clients[app_code][1]

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

    @staticmethod
    def _derive_sts_endpoint(provider: str, endpoint_url: str | None, region_name: str) -> str | None:
        """根据 provider + region_name 推导 STS endpoint。

        - aliyun: https://sts.{region}.aliyuncs.com
        - aws: https://sts.{region}.amazonaws.com
        - minio: 同 S3 endpoint
        """
        if provider == "aliyun":
            return f"https://sts.{region_name}.aliyuncs.com"
        elif provider == "aws":
            return f"https://sts.{region_name}.amazonaws.com"
        else:
            # minio / 其他：STS 和 S3 共用 endpoint
            return endpoint_url

    @staticmethod
    def _build_policy(provider: str, bucket_name: str, dir_key: str) -> dict:
        """根据 provider 构建对应格式的 STS Policy。

        - aliyun: Version=1, acs:oss 格式
        - aws: Version=2012-10-17, arn:aws:s3 格式
        - minio: 同 aws 格式
        """
        if provider == "aliyun":
            return {
                "Version": "1",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["oss:PutObject",
                    "oss:InitiateMultipartUpload",
                    "oss:UploadPart",
                    "oss:CompleteMultipartUpload",
                    "oss:AbortMultipartUpload",
                    "oss:ListParts"],
                    "Resource": [f"acs:oss:*:*:{bucket_name}/{dir_key}/*"],
                }],
            }
        else:
            # aws / minio
            return {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["s3:PutObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/{dir_key}/*"],
                }],
            }

    async def _aliyun_assume_role(
        self, sts_endpoint: str, region_name: str, role_arn: str,
        policy: dict, expires: int,
    ) -> dict:
        """调用阿里云 STS AssumeRole API（签名 v1）。"""
        s3_settings = get_s3_settings()
        ak = s3_settings.S3_ACCESS_KEY_ID
        sk = s3_settings.S3_SECRET_ACCESS_KEY

        # 公共参数
        params = {
            "Action": "AssumeRole",
            "Version": "2015-04-01",
            "Format": "JSON",
            "AccessKeyId": ak,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": uuid.uuid4().hex,
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "RoleArn": role_arn,
            "RoleSessionName": "DatahubUpload",
            "Policy": json.dumps(policy),
            "DurationSeconds": str(expires),
        }

        # 签名 v1：排序 → 拼接 → HMAC-SHA1
        sorted_params = sorted(params.items())
        query_string = urlencode(sorted_params, quote_via=quote)
        string_to_sign = f"GET&{quote('/', safe='')}&{quote(query_string, safe='')}"
        signing_key = (sk + "&").encode("utf-8")
        signature = base64.b64encode(
            hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
        ).decode("utf-8")
        params["Signature"] = signature

        async with httpx.AsyncClient() as client:
            resp = await client.get(sts_endpoint, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

        if "Credentials" not in data:
            raise ValueError(f"阿里云 STS 返回错误: {data}")

        creds = data["Credentials"]
        return {
            "access_key_id": creds["AccessKeyId"],
            "secret_access_key": creds["AccessKeySecret"],
            "session_token": creds["SecurityToken"],
            "expiration": creds["Expiration"],
        }

    async def get_sts_credentials(
        self, bucket: str, dir_key: str, expires: int = 900
    ) -> dict:
        """获取 STS 临时凭证。

        根据 provider 区分运营商：
        - aliyun: 调用阿里云 STS AssumeRole API
        - aws: 调用 AWS STS AssumeRole API
        - minio: 调用 MinIO STS（同 AWS 格式）
        """
        config = self._get_config(bucket)
        bucket_name = config["bucket_name"]
        provider = config.get("provider", "aliyun")
        region_name = config.get("region_name", "us-east-1")
        role_arn = config.get("role_arn")

        # 推导 STS endpoint
        sts_endpoint = self._derive_sts_endpoint(
            provider, config.get("endpoint_url"), region_name
        )

        if not role_arn:
            raise ValueError(
                f"oss_configs[{bucket}] 缺少 role_arn 配置，无法获取 STS 临时凭证"
            )

        # 根据运营商构建 Policy
        policy = self._build_policy(provider, bucket_name, dir_key)

        # 阿里云：直接调用阿里云 STS API
        if provider == "aliyun":
            return await self._aliyun_assume_role(
                sts_endpoint, region_name, role_arn, policy, expires
            )

        # AWS / MinIO：使用 aiobotocore STS client
        s3_settings = get_s3_settings()
        session = aiobotocore.session.get_session()
        async with session.create_client(
            'sts',
            endpoint_url=sts_endpoint,
            aws_access_key_id=s3_settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=s3_settings.S3_SECRET_ACCESS_KEY,
            region_name=region_name,
        ) as sts_client:
            response = await sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="DatahubUpload",
                Policy=json.dumps(policy),
                DurationSeconds=expires,
            )

        creds = response["Credentials"]
        return {
            "access_key_id": creds["AccessKeyId"],
            "secret_access_key": creds["SecretAccessKey"],
            "session_token": creds["SessionToken"],
            "expiration": creds["Expiration"].isoformat(),
        }

    async def close(self) -> None:
        """关闭所有 S3 客户端连接。"""
        for app_code, (ctx, client) in self._s3_clients.items():
            try:
                await ctx.__aexit__(None, None, None)
                logger.debug("关闭 S3 客户端：app=%s", app_code)
            except Exception as e:
                logger.warning("关闭 S3 客户端失败：app=%s, error=%s", app_code, e)
        self._s3_clients.clear()

    def get_config(self, app_code: str) -> dict:
        """获取存储配置（provider, endpoint_url, region_name, bucket_name, role_arn）。"""
        config = self._get_config(app_code)
        return {
            "provider": config.get("provider", "aliyun"),
            "endpoint_url": config.get("endpoint_url") or None,
            "region_name": config.get("region_name", "us-east-1"),
            "bucket_name": config["bucket_name"],
            "role_arn": config.get("role_arn") or None,
        }
