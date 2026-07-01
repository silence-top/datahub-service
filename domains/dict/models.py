# domains/dict/models.py — Dictionary ORM models
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class DictType(Base):
    """字典类型表。

    用于管理各类字典（如设备型号、染色类型、样本类型等）。
    每个 type_code 唯一标识一种字典。
    """

    __tablename__ = "dict_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, comment="字典类型编码，如 device_model"
    )
    type_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="字典类型名称，如 设备型号"
    )
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
        return f"<DictType code={self.type_code} name={self.type_name}>"


class DictValue(Base):
    """字典值表。

    属于某个字典类型的键值对，按 sort 排序。
    """

    __tablename__ = "dict_values"
    __table_args__ = (
        UniqueConstraint("type_code", "value_key", name="uq_dict_value_type_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("dict_types.type_code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="存储值，如 leica_apario_cs2"
    )
    value_label: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="显示标签，如 Leica Aperio CS2"
    )
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
        return f"<DictValue type={self.type_code} key={self.value_key} label={self.value_label}>"
