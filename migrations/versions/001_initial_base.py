"""create initial tables (slice_files, devices, oss_configs)

This is the base migration that creates all tables from scratch.
Replace the previous fragmented migrations.

Revision ID: initial_base
Revises: 
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = "initial_base"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- slice_files table ---
    op.create_table(
        "slice_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("app_code", sa.String(32), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("batch_id", sa.String(64), nullable=True),
        sa.Column("relative_path", sa.String(512), nullable=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("file_format", sa.String(16), nullable=False),
        sa.Column("staining_type", sa.String(32), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("oss_key", sa.String(512), nullable=False),
        sa.Column("thumbnail_key", sa.String(512), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
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
        sa.UniqueConstraint("oss_key"),
    )
    op.create_index("ix_slice_files_app_code", "slice_files", ["app_code"])
    op.create_index("ix_slice_files_device_id", "slice_files", ["device_id"])
    op.create_index("ix_slice_files_batch_id", "slice_files", ["batch_id"])
    op.create_index("ix_slice_files_status", "slice_files", ["status"])

    # --- devices table ---
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("app_code", sa.String(32), nullable=False),
        sa.Column("dept_id", sa.Integer(), nullable=True),
        sa.Column("device_code", sa.String(64), nullable=False),
        sa.Column("device_name", sa.String(128), nullable=False),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("manufacturer", sa.String(64), nullable=True),
        sa.Column("allowed_formats", sa.Text(), nullable=False, server_default='[".svs",".ndpi",".tiff",".tif",".mrxs"]'),
        sa.Column("allowed_staining", sa.Text(), nullable=False, server_default='["HE","IHC","PAS","Masson"]'),
        sa.Column("max_file_size_mb", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
    op.create_index("ix_slice_files_app_case", "slice_files", ["app_code"])
    op.create_index("ix_slice_files_app_patient", "slice_files", ["app_code"])
    op.create_index("ix_devices_app_code", "devices", ["app_code"])
    op.create_index("ix_devices_device_code", "devices", ["device_code"], unique=True)
    op.create_index("ix_devices_dept_id", "devices", ["dept_id"])

    # --- oss_configs table ---
    op.create_table(
        "oss_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("app_code", sa.String(32), nullable=False),
        sa.Column("config_name", sa.String(128), nullable=False),
        sa.Column("bucket_name", sa.String(128), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
    op.drop_index("ix_devices_dept_id", table_name="devices")
    op.drop_index("ix_devices_device_code", table_name="devices")
    op.drop_index("ix_devices_app_code", table_name="devices")
    op.drop_index("ix_slice_files_app_patient", table_name="slice_files")
    op.drop_index("ix_slice_files_app_case", table_name="slice_files")
    op.drop_table("devices")
    op.drop_index("ix_slice_files_status", table_name="slice_files")
    op.drop_index("ix_slice_files_batch_id", table_name="slice_files")
    op.drop_index("ix_slice_files_device_id", table_name="slice_files")
    op.drop_index("ix_slice_files_app_code", table_name="slice_files")
    op.drop_table("slice_files")
