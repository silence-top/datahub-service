# domains/oss/models.py — OssConfig ORM model
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class OssConfig(Base):
    """OSS 存储配置表。

    每条记录代表一个完整的 OSS 连接（AK/SK/Endpoint/Bucket）。
    通过 app_code 路由：上传时按 app_code 查找配置，找不到回退 is_default=True 的配置。
    """

    __tablename__ = "oss_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- 路由键 ---
    app_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="应用编码，用于路由 OSS")

    # --- 配置信息 ---
    config_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="配置名称")
    access_key_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="OSS AccessKey ID")
    access_key_secret: Mapped[str] = mapped_column(String(128), nullable=False, comment="OSS AccessKey Secret")
    endpoint: Mapped[str] = mapped_column(String(256), nullable=False, comment="OSS Endpoint")
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
