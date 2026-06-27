# domains/device/models.py — Device ORM model
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class Device(Base):
    """扫描仪设备注册表。

    上传前必须校验设备已注册且活跃，未注册设备不允许上传。
    每台设备可配置上传规则（允许格式、染色类型、文件大小上限）。
    """

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- 归属 ---
    app_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dept_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True, comment="部门ID（引用 core-service auth_departments.id）"
    )

    # --- 设备标识 ---
    device_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    device_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- 上传规则配置（JSON 数组字符串）---
    allowed_formats: Mapped[str] = mapped_column(
        Text, nullable=False, default='[".svs",".ndpi",".tiff",".tif",".mrxs"]'
    )
    allowed_staining: Mapped[str] = mapped_column(
        Text, nullable=False, default='["HE","IHC","PAS","Masson"]'
    )
    max_file_size_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=500)

    # --- 状态 ---
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    registered_by: Mapped[int] = mapped_column(Integer, nullable=False)

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
        return f"<Device code={self.device_code} name={self.device_name} active={self.is_active}>"
