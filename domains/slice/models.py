# domains/slice/models.py — SliceFile ORM model
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class SliceFile(Base):
    """病理切片文件记录。

    status 枚举值：
      - pending : 文件已接收，等待 OSS 上传完成
      - ready   : OSS 上传成功，可正常访问
      - error   : 上传/处理失败
    """

    __tablename__ = "slice_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- 归属信息 ---
    app_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # --- 设备关联 + 批量上传 ---
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    relative_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # --- 文件元数据 ---
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(16), nullable=False)   # SVS/NDPI/TIFF/MRXS
    staining_type: Mapped[str] = mapped_column(String(32), nullable=False)  # HE/IHC/PAS/...
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)         # 字节数

    # --- OSS 路径 ---
    oss_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # --- 状态与审计 ---
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    uploaded_by: Mapped[int] = mapped_column(Integer, nullable=False)       # 来自网关 X-User-Id
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_slice_files_app_case", "app_code"),
        Index("ix_slice_files_app_patient", "app_code"),
    )

    def __repr__(self) -> str:
        return f"<SliceFile id={self.id} app={self.app_code} status={self.status}>"
