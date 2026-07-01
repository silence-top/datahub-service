# domains/oss/models.py — OssConfig ORM model
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class OssConfig(Base):
    """S3 存储 Bucket 配置表。

    统一使用 S3 协议，支持：
      - AWS S3
      - MinIO (自建)
      - 阿里云 OSS (S3 兼容模式)
      - 腾讯云 COS (S3 兼容)
    
    AK/SK 从 .env 读取（全局共享），Endpoint/Region/Bucket 存于本表。
    通过 app_code 路由：上传时按 app_code 查找配置，找不到回退 is_default=True 的配置。
    """

    __tablename__ = "oss_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- 路由键 ---
    app_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="应用编码，用于路由存储")

    # --- 连接信息（非敏感）---
    config_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="配置名称")
    endpoint_url: Mapped[str] = mapped_column(
        String(256), nullable=True,
        comment="S3 Endpoint URL（AWS S3 留空，MinIO/阿里云需要）"
    )
    region_name: Mapped[str] = mapped_column(
        String(32), nullable=False, default="us-east-1",
        comment="S3 Region"
    )
    bucket_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Bucket 名称")

    # --- 状态 ---
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否默认配置")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, comment="创建人 user_id")

    # --- 审计 ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<OssConfig id={self.id} app_code={self.app_code} bucket={self.bucket_name}>"
