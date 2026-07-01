"""add device_secret column to devices

Revision ID: add_device_secret
Revises: flatten_oss_configs
Create Date: 2026-06-30

为 devices 表新增 device_secret 列，支持扫描仪设备直连认证。
"""
from alembic import op
import sqlalchemy as sa

revision = "add_device_secret"
down_revision = "flatten_oss_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 先加列为 nullable（兼容已有数据），再回填随机密钥，最后改为 NOT NULL
    op.add_column(
        "devices",
        sa.Column("device_secret", sa.String(64), nullable=True, comment="设备唯一密钥，用于扫描仪直连认证"),
    )

    # 为已有设备生成随机密钥（两个 UUID 拼接 = 64 位 hex）
    op.execute(
        "UPDATE devices SET device_secret = replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '')"
    )

    # 改为 NOT NULL
    op.alter_column("devices", "device_secret", nullable=False)


def downgrade() -> None:
    op.drop_column("devices", "device_secret")
