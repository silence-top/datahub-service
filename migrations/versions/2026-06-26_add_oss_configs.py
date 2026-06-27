"""add oss_configs table

Revision ID: e7a3f5b21c08
Revises: d5f2e1a03b06
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = "e7a3f5b21c08"
down_revision = "d5f2e1a03b06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oss_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("app_code", sa.String(32), nullable=False),
        sa.Column("config_name", sa.String(128), nullable=False),
        sa.Column("access_key_id", sa.String(128), nullable=False),
        sa.Column("access_key_secret", sa.String(128), nullable=False),
        sa.Column("endpoint", sa.String(256), nullable=False),
        sa.Column("bucket_name", sa.String(128), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oss_configs_app_code", "oss_configs", ["app_code"])


def downgrade() -> None:
    op.drop_index("ix_oss_configs_app_code", table_name="oss_configs")
    op.drop_table("oss_configs")
