"""add devices table and batch upload columns

Revision ID: d5f2e1a03b06
Revises: 
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "d5f2e1a03b06"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- devices table ---
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("app_code", sa.String(32), nullable=False),
        sa.Column("device_code", sa.String(64), nullable=False),
        sa.Column("device_name", sa.String(128), nullable=False),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("manufacturer", sa.String(64), nullable=True),
        sa.Column("allowed_formats", sa.Text(), nullable=False),
        sa.Column("allowed_staining", sa.Text(), nullable=False),
        sa.Column("max_file_size_mb", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("registered_by", sa.Integer(), nullable=False),
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
    op.create_index("ix_devices_app_code", "devices", ["app_code"])
    op.create_index("ix_devices_device_code", "devices", ["device_code"], unique=True)

    # --- slice_files: add device_id, batch_id, relative_path ---
    op.add_column("slice_files", sa.Column("device_id", sa.Integer(), nullable=True))
    op.add_column("slice_files", sa.Column("batch_id", sa.String(64), nullable=True))
    op.add_column("slice_files", sa.Column("relative_path", sa.String(512), nullable=True))
    op.create_index("ix_slice_files_device_id", "slice_files", ["device_id"])
    op.create_index("ix_slice_files_batch_id", "slice_files", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_slice_files_batch_id", table_name="slice_files")
    op.drop_index("ix_slice_files_device_id", table_name="slice_files")
    op.drop_column("slice_files", "relative_path")
    op.drop_column("slice_files", "batch_id")
    op.drop_column("slice_files", "device_id")
    op.drop_index("ix_devices_device_code", table_name="devices")
    op.drop_index("ix_devices_app_code", table_name="devices")
    op.drop_table("devices")
