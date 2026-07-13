# domains/slice/models.py — Slide ORM model
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class Slide(Base):
    """病理切片记录。

    status 枚举值：
      - pending : 文件已接收，等待 OSS 上传完成
      - ready   : OSS 上传成功，可正常访问
      - error   : 上传/处理失败
    """

    __tablename__ = "slides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")

    # --- 归属信息 ---
    app_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="应用编码，路由到对应 Bucket 配置")

    # --- 设备关联 + 批量上传 ---
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, comment="关联设备 ID（devices.id）")
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="批次 ID，同批次文件共享（UUID hex）")
    relative_path: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="文件在文件夹中的相对路径（DZI/LD 场景使用）")

    # --- 文件元数据 ---
    slide_code: Mapped[str] = mapped_column(String(255), nullable=False, index=True, comment="切片编码（对应扫描仪 barcode）")
    file_format: Mapped[str] = mapped_column(String(16), nullable=False, comment="文件格式：SVS/TIFF/TIF/DZI/LD（DZI/LD 为文件夹格式）")
    staining_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="染色类型：HE/IHC/PAS/Masson 等")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, comment="文件大小（字节）")

    # --- OSS 路径 ---
    oss_key: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True, comment="OSS 路径：单文件指向文件，LD/DZI 指向目录")
    thumbnail_key: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="缩略图 OSS 路径（可选）")

    # --- 状态与审计 ---
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True, comment="状态：pending/uploading/ready/error")
    uploaded_by: Mapped[int] = mapped_column(Integer, nullable=False, comment="上传人 ID（设备上传时为 device_id）")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<Slide id={self.id} slide_code={self.slide_code} status={self.status}>"
