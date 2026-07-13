"""make staining_type nullable

Revision ID: staining_type_nullable
Revises: rename_slides
Create Date: 2026-07-06

将 slides 表的 staining_type 字段改为可空（染色类型在上传时可能未知）。
"""
from alembic import op
import sqlalchemy as sa


revision = "staining_type_nullable"
down_revision = "rename_slides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "slides",
        "staining_type",
        existing_type=sa.String(32),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "slides",
        "staining_type",
        existing_type=sa.String(32),
        nullable=False,
    )
