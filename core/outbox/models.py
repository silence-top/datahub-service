# core/outbox/models.py — Outbox Event ORM model
"""
Outbox 模式：业务数据与事件在同一个 DB 事务中写入，保证最终一致性。

Relay 进程轮询此表，将 pending 事件发布到 MQ。
"""
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class OutboxEvent(Base):
    """Outbox 事件表。

    业务操作在同一个事务中写入此表，Relay 异步消费并发布到 MQ。

    status 状态机：
      pending → sent (成功)
      pending → failed (失败，retry_count++)
      failed → pending (重试，retry_count < max_retries)
      failed → dead_letter (超过最大重试次数，需人工干预)
    """

    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- 事件标识 ---
    event_type: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="事件类型，如 slice.registered / slice.status_changed"
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="聚合根类型，如 slice / device"
    )
    aggregate_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        comment="聚合根 ID"
    )

    # --- 事件内容 ---
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        comment="事件载荷（JSON）"
    )

    # --- 投递状态 ---
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True,
        comment="投递状态：pending / sent / failed / dead_letter"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="已重试次数"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="最近一次错误信息"
    )

    # --- 时间戳 ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="事件创建时间"
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="成功发送时间"
    )

    __table_args__ = (
        # Relay 查询优化：按 status + created_at 顺序消费
        Index("ix_outbox_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<OutboxEvent id={self.id} type={self.event_type} status={self.status}>"
