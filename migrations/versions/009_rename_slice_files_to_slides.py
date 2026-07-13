"""rename slice_files to slides

Revision ID: rename_slides
Revises: add_dict_tables
Create Date: 2026-06-27

重命名表 slice_files → slides，重命名字段 original_name → slide_code。
"""
from alembic import op
import sqlalchemy as sa


revision = "rename_slides"
down_revision = "add_dict_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 重命名字段：original_name → slide_code
    op.alter_column(
        "slice_files",
        "original_name",
        new_column_name="slide_code",
        existing_type=sa.String(255),
        existing_nullable=False,
    )

    # 重命名表：slice_files → slides
    op.rename_table("slice_files", "slides")

    # 重命名索引
    op.execute("ALTER INDEX ix_slice_files_app_code RENAME TO ix_slides_app_code")
    op.execute("ALTER INDEX ix_slice_files_device_id RENAME TO ix_slides_device_id")
    op.create_index("ix_slides_slide_code", "slides", ["slide_code"])


def downgrade() -> None:
    # 删除新索引
    op.drop_index("ix_slides_slide_code", table_name="slides")

    # 恢复索引名
    op.execute("ALTER INDEX ix_slides_device_id RENAME TO ix_slice_files_device_id")
    op.execute("ALTER INDEX ix_slides_app_code RENAME TO ix_slice_files_app_code")

    # 恢复表名
    op.rename_table("slides", "slice_files")

    # 恢复字段名
    op.alter_column(
        "slice_files",
        "slide_code",
        new_column_name="original_name",
        existing_type=sa.String(255),
        existing_nullable=False,
    )
