"""add dict tables

Revision ID: add_dict_tables
Revises: add_device_secret
Create Date: 2026-06-30

新增字典管理表（dict_types + dict_values），支持通用字典类型和字典值管理。
"""
from alembic import op
import sqlalchemy as sa

revision = "add_dict_tables"
down_revision = "add_device_secret"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 字典类型表
    op.create_table(
        "dict_types",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("type_code", sa.String(64), unique=True, nullable=False, index=True, comment="字典类型编码，如 device_model"),
        sa.Column("type_name", sa.String(128), nullable=False, comment="字典类型名称，如 设备型号"),
        sa.Column("description", sa.String(256), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 字典值表
    op.create_table(
        "dict_values",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("type_code", sa.String(64), sa.ForeignKey("dict_types.type_code", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("value_key", sa.String(128), nullable=False, comment="存储值，如 leica_apario_cs2"),
        sa.Column("value_label", sa.String(256), nullable=False, comment="显示标签，如 Leica Aperio CS2"),
        sa.Column("sort", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("type_code", "value_key", name="uq_dict_value_type_key"),
    )


def downgrade() -> None:
    op.drop_table("dict_values")
    op.drop_table("dict_types")
