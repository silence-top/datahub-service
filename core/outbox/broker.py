# core/outbox/broker.py — Message broker abstraction
"""
消息代理抽象层：定义事件发布的统一接口。

实现：
  - LogBroker: 开发环境，仅日志输出
  - KafkaBroker: 生产环境（待实现）
  - RabbitMQBroker: 生产环境（待实现）
  - RedisStreamBroker: 轻量生产环境（待实现）
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger("datahub-service.outbox")


@dataclass(frozen=True)
class Message:
    """消息载体。

    event_id 用于下游按 id 做幂等消费（at-least-once 语义下同一事件可能被重复投递）。
    """

    event_id: int
    event_type: str
    payload: dict
    aggregate_type: str | None = None
    aggregate_id: int | None = None


class MessageBroker(ABC):
    """消息代理抽象基类。"""

    @abstractmethod
    async def publish(self, message: Message) -> None:
        """发布一条消息。"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """关闭连接。"""
        ...


class LogBroker(MessageBroker):
    """日志消息代理（开发/测试环境）。

    仅将消息输出到日志，不实际发送到 MQ。
    生产环境请替换为 KafkaBroker / RabbitMQBroker 等实现。
    """

    async def publish(self, message: Message) -> None:
        logger.debug(
            "[Outbox] EventID: %d | Type: %s | Aggregate: %s#%s",
            message.event_id,
            message.event_type,
            message.aggregate_type,
            message.aggregate_id,
        )

    async def close(self) -> None:
        pass
