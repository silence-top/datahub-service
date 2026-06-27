"""add dept_id to devices table

Revision ID: f8b4c2d15e91
Revises: e7a3f5b21c08
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = "f8b4c2d15e91"
down_revision = "e7a3f5b21c08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("dept_id", sa.Integer(), nullable=True))
    op.create_index("ix_devices_dept_id", "devices", ["dept_id"])


def downgrade() -> None:
    op.drop_index("ix_devices_dept_id", table_name="devices")
    op.drop_column("devices", "dept_id")
