# core/outbox/publisher.py — Event publisher for service layer
"""
EventPublisher：业务代码通过此类将事件写入 Outbox 表。

使用方式：
    publisher = EventPublisher(db)
    publisher.publish("slice.registered", "slice", slice_id, {"slide_code": "xxx", ...})
    await db.commit()  # 与业务数据在同一个事务中提交
"""
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.outbox.repository import OutboxRepository

logger = logging.getLogger("datahub-service.outbox")


def _safe_serialize(payload: dict) -> dict:
    """确保 payload 可写入 JSONB。

    将 datetime / Decimal / UUID 等非 JSON 原生类型兜底转为字符串，
    避免 asyncpg 报 "Object of type X is not JSON serializable"。
    """
    try:
        return json.loads(json.dumps(payload, default=str, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        logger.warning("Payload serialization fallback: %s", exc)
        # 最终兆底：强制转 repr
        return json.loads(json.dumps(payload, default=repr, ensure_ascii=False))


class EventPublisher:
    """事件发布器：将事件写入 Outbox 表（与业务数据同一事务）。"""

    def __init__(self, db: AsyncSession) -> None:
        self._repo = OutboxRepository(db)

    async def publish(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: int | None,
        payload: dict,
    ) -> None:
        """发布事件到 Outbox（pending 状态，等待 Relay 消费）。

        注意：此方法不自动 commit，由调用方在同一事务中统一 commit。
        payload 中的 datetime/Decimal/UUID 会被安全序列化，无需担心 JSONB 报错。
        """
        await self._repo.create(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=_safe_serialize(payload),
        )
