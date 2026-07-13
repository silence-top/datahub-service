# core/outbox/relay.py — Outbox relay (polls DB, publishes to broker)
"""
OutboxRelay：后台任务，轮询 outbox_events 表，将 pending 事件发布到 MQ。

启动方式：
    relay = OutboxRelay(broker, poll_interval=1.0)
    task = asyncio.create_task(relay.run())
    # ... shutdown ...
    relay.stop()
    await task
"""
import asyncio
import logging
from datetime import datetime

from core.db import AsyncSessionLocal
from core.outbox.broker import Message, MessageBroker
from core.outbox.repository import OutboxRepository

logger = logging.getLogger("datahub-service.outbox")


class OutboxRelay:
    """Outbox 事件中继器：轮询 DB → 发布到 MQ。"""

    def __init__(
        self,
        broker: MessageBroker,
        *,
        poll_interval: float = 5.0,
        batch_size: int = 100,
        max_retries: int = 3,
        retry_reset_interval: float = 60.0,
    ) -> None:
        self._broker = broker
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._retry_reset_interval = retry_reset_interval
        self._running = False
        self._last_retry_reset = datetime.now()

    def stop(self) -> None:
        """停止 Relay 循环。"""
        self._running = False

    async def run(self) -> None:
        """主循环：轮询 outbox → 发布消息 → 更新状态。"""
        self._running = True
        logger.info("OutboxRelay started (poll_interval=%.1fs, batch_size=%d)", self._poll_interval, self._batch_size)

        while self._running:
            try:
                processed = await self._process_batch()
                if processed > 0:
                    logger.info("OutboxRelay: processed %d events", processed)
                else:
                    await asyncio.sleep(self._poll_interval)
            except Exception:
                logger.exception("OutboxRelay error, retrying in %ss", self._poll_interval * 5)
                await asyncio.sleep(self._poll_interval * 5)

        logger.info("OutboxRelay stopped")

    async def _process_batch(self) -> int:
        """处理一批 pending 事件，返回处理数量。"""
        async with AsyncSessionLocal() as db:
            repo = OutboxRepository(db)

            # 每轮都检查失败事件（内部有时间间隔判断），
            # 避免 pending 队列繁忙时 failed 事件永远得不到重试/进死信。
            await self._maybe_reset_failed(repo)
            try:
                await db.commit()
            except Exception as exc:
                logger.warning("OutboxRelay: reset_failed commit failed: %s", exc)
                try:
                    await db.rollback()
                except Exception:
                    pass

            events = await repo.fetch_pending(limit=self._batch_size)

            if not events:
                return 0

            for event in events:
                message = Message(
                    event_id=event.id,
                    event_type=event.event_type,
                    payload=event.payload,
                    aggregate_type=event.aggregate_type,
                    aggregate_id=event.aggregate_id,
                )

                try:
                    await self._broker.publish(message)
                    await repo.mark_sent(event)
                except Exception as exc:
                    await repo.mark_failed(event, str(exc)[:500])
                    logger.warning("Failed to publish event %s (retry %d/%d): %s",
                                   event.id, event.retry_count + 1, self._max_retries, exc)

            # 批量 commit：成功发送的状态持久化。
            # 若 commit 失败，MQ 已发出但 DB 状态未更新，下一轮会重发，
            # 下游 B 系统需基于 event_id 做幂等消费。
            try:
                await db.commit()
            except Exception as exc:
                logger.error(
                    "OutboxRelay: batch commit failed (%d events, ids=%s). "
                    "Messages already published to MQ; downstream idempotency required. Error: %s",
                    len(events),
                    [e.id for e in events],
                    exc,
                )
                # session 进入 invalid 状态，必须 rollback，否则下次查询报错
                try:
                    await db.rollback()
                except Exception:
                    logger.exception("OutboxRelay: rollback after commit failure also failed")
                # 不 raise，避免触发外层 run() 的长 sleep，下一轮立刻重试

            return len(events)

    async def _maybe_reset_failed(self, repo: OutboxRepository) -> None:
        """定期处理失败事件：重试或移入死信队列。"""
        now = datetime.now()
        if (now - self._last_retry_reset).total_seconds() >= self._retry_reset_interval:
            # 重试未超限的失败事件
            retry_count = await repo.reset_failed(max_retries=self._max_retries)
            if retry_count > 0:
                logger.info("Reset %d failed outbox events for retry", retry_count)

            # 将超过重试限制的事件移入死信队列
            dead_count = await repo.move_to_dead_letter(max_retries=self._max_retries)
            if dead_count > 0:
                logger.error(
                    "Moved %d events to dead_letter queue (exceeded max_retries=%d). "
                    "Manual intervention required!",
                    dead_count, self._max_retries
                )

            self._last_retry_reset = now
