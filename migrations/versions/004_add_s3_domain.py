"""add s3_domain to oss_configs

Revision ID: add_s3_domain
Revises: remove_s3_fields
Create Date: 2026-06-27

添加 S3 域标识字段，支持多域多 Bucket 配置。
每个 Bucket 可指定使用哪个域的凭证（从环境变量读取）。
"""
from alembic import op
import sqlalchemy as sa

revision = "add_s3_domain"
down_revision = "remove_s3_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'oss_configs', 
        sa.Column('s3_domain', sa.String(length=32), nullable=False, server_default='default', comment='S3 域标识（对应环境变量中的域名称）')
    )


def downgrade() -> None:
    op.drop_column('oss_configs', 's3_domain')
