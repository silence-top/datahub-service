# 012_add_outbox_events.py — Outbox 模式事件表
"""创建 outbox_events 表，用于 Outbox 模式的事件发布"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "outbox_events"
down_revision = "add_sts_endpoint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 检查表是否已存在
    tables = {row[0] for row in conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public'"
    )).fetchall()}

    if "outbox_events" not in tables:
        op.create_table(
            "outbox_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("event_type", sa.String(128), nullable=False, comment="事件类型，如 slice.registered"),
            sa.Column("aggregate_type", sa.String(64), nullable=False, comment="聚合根类型，如 slice"),
            sa.Column("aggregate_id", sa.Integer(), nullable=True, comment="聚合根 ID"),
            sa.Column("payload", JSONB(), nullable=False, comment="事件载荷（JSON）"),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending", comment="投递状态：pending/sent/failed"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0", comment="已重试次数"),
            sa.Column("error_message", sa.Text(), nullable=True, comment="最近一次错误信息"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True, comment="成功发送时间"),
            sa.PrimaryKeyConstraint("id"),
        )

        # 索引
        op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
        op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
        op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
        op.create_index("ix_outbox_status_created", "outbox_events", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_status_created", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_table("outbox_events")
