# core/outbox/repository.py — Outbox repository for DB operations
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.outbox.models import OutboxEvent


class OutboxRepository:
    """Outbox 事件的数据库操作。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: int | None,
        payload: dict,
    ) -> OutboxEvent:
        """创建一条待发送的 Outbox 事件。"""
        event = OutboxEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status="pending",
        )
        self._db.add(event)
        return event

    async def fetch_pending(self, limit: int = 100) -> list[OutboxEvent]:
        """获取待发送的事件（按创建时间排序，FIFO）。

        使用 SELECT ... FOR UPDATE SKIP LOCKED 加行锁：
          - FOR UPDATE：锁住行，防止其他事务同时 mark_sent/mark_failed
          - SKIP LOCKED：跳过已被其他事务锁定的行，多实例部署时不会阻塞

        行锁只在包含此查询的事务内有效，事务提交/回滚后自动释放。
        """
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def mark_sent(self, event: OutboxEvent) -> None:
        """标记事件为已发送。"""
        stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.id == event.id)
            .values(status="sent", sent_at=datetime.now())
        )
        await self._db.execute(stmt)

    async def mark_failed(self, event: OutboxEvent, error: str) -> None:
        """标记事件为失败，增加重试计数。"""
        stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.id == event.id)
            .values(
                status="failed",
                retry_count=event.retry_count + 1,
                error_message=error,
            )
        )
        await self._db.execute(stmt)

    async def reset_failed(self, max_retries: int = 3) -> int:
        """重置失败事件为 pending（供重试），返回重置数量。"""
        stmt = (
            update(OutboxEvent)
            .where(
                OutboxEvent.status == "failed",
                OutboxEvent.retry_count < max_retries,
            )
            .values(status="pending", error_message=None)
        )
        result = await self._db.execute(stmt)
        return result.rowcount

    async def move_to_dead_letter(self, max_retries: int = 3) -> int:
        """将超过最大重试次数的事件移入死信队列，返回移动数量。"""
        stmt = (
            update(OutboxEvent)
            .where(
                OutboxEvent.status == "failed",
                OutboxEvent.retry_count >= max_retries,
            )
            .values(status="dead_letter")
        )
        result = await self._db.execute(stmt)
        return result.rowcount

    async def get_dead_letters(self, limit: int = 100) -> list[OutboxEvent]:
        """获取死信队列中的事件（供人工查看/重试）。"""
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == "dead_letter")
            .order_by(OutboxEvent.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def retry_dead_letter(self, event_id: int) -> bool:
        """手动重试死信事件，返回是否成功。"""
        stmt = (
            update(OutboxEvent)
            .where(
                OutboxEvent.id == event_id,
                OutboxEvent.status == "dead_letter",
            )
            .values(status="pending", retry_count=0, error_message=None)
        )
        result = await self._db.execute(stmt)
        return result.rowcount > 0
