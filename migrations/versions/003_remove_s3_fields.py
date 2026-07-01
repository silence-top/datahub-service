"""remove s3 fields from oss_configs

Revision ID: remove_s3_fields
Revises: add_s3_fields
Create Date: 2026-06-27

移除 S3 凭证字段（endpoint_url、access_key_id、secret_access_key、region_name），
这些字段改从环境变量读取，数据库只存储 Bucket 映射关系。
"""
from alembic import op
import sqlalchemy as sa

revision = "remove_s3_fields"
down_revision = "add_s3_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('oss_configs', 'region_name')
    op.drop_column('oss_configs', 'secret_access_key')
    op.drop_column('oss_configs', 'access_key_id')
    op.drop_column('oss_configs', 'endpoint_url')


def downgrade() -> None:
    op.add_column('oss_configs', sa.Column('endpoint_url', sa.String(length=256), nullable=True, comment='S3 Endpoint URL'))
    op.add_column('oss_configs', sa.Column('access_key_id', sa.String(length=128), nullable=True, comment='S3 Access Key ID'))
    op.add_column('oss_configs', sa.Column('secret_access_key', sa.String(length=128), nullable=True, comment='S3 Secret Access Key'))
    op.add_column('oss_configs', sa.Column('region_name', sa.String(length=32), nullable=True, server_default='us-east-1', comment='S3 Region'))
