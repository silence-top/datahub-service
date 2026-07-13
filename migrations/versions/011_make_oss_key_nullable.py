"""make oss_key nullable

Revision ID: oss_key_nullable
Revises: staining_type_nullable
Create Date: 2026-07-06

将 slides 表的 oss_key 字段改为可空，支持 register → presign 两阶段流程：
- register 阶段创建记录时 oss_key 为空
- presign 阶段生成 oss_key 并更新
"""
from alembic import op
import sqlalchemy as sa


revision = "oss_key_nullable"
down_revision = "staining_type_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "slides",
        "oss_key",
        existing_type=sa.String(512),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "slides",
        "oss_key",
        existing_type=sa.String(512),
        nullable=False,
    )
