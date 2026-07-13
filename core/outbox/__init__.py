# core/outbox — Outbox pattern for reliable event publishing
"""
Outbox 模式实现：保证业务数据与事件的最终一致性。

核心组件：
  - OutboxEvent: ORM 模型
  - EventPublisher: 业务层使用，写入 outbox 表
  - OutboxRelay: 后台任务，轮询 outbox 表并发布到 MQ
  - MessageBroker: MQ 抽象层（LogBroker / KafkaBroker / ...）

使用方式：
    # 在 service 中发布事件
    publisher = EventPublisher(db)
    await publisher.publish("slice.registered", "slice", slice_id, {...})
    await db.commit()  # 与业务数据一起提交

    # 在 lifespan 中启动 Relay
    relay = OutboxRelay(broker)
    task = asyncio.create_task(relay.run())
"""

from core.outbox.broker import LogBroker, Message, MessageBroker
from core.outbox.models import OutboxEvent
from core.outbox.publisher import EventPublisher
from core.outbox.relay import OutboxRelay
from core.outbox.repository import OutboxRepository

__all__ = [
    "OutboxEvent",
    "OutboxRepository",
    "EventPublisher",
    "OutboxRelay",
    "MessageBroker",
    "Message",
    "LogBroker",
]
