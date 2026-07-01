"""flatten oss configs: drop s3_domains, add endpoint/region to oss_configs

Revision ID: flatten_oss_configs
Revises: add_s3_domains_table
Create Date: 2026-06-30

将 OSS 配置架构扁平化：
1. 删除 s3_domains 表
2. 移除 oss_configs.domain_name 列
3. 新增 oss_configs.endpoint_url 和 region_name 列
"""
from alembic import op
import sqlalchemy as sa

revision = "flatten_oss_configs"
down_revision = "add_s3_domains_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 删除 s3_domains 表
    op.drop_index('ix_s3_domains_domain_name', 's3_domains')
    op.drop_table('s3_domains')

    # 2. 移除 oss_configs.domain_name 列
    op.drop_column('oss_configs', 'domain_name')

    # 3. 新增 endpoint_url 和 region_name
    op.add_column('oss_configs', sa.Column(
        'endpoint_url', sa.String(256), nullable=True,
        comment='S3 Endpoint URL（AWS S3 留空，MinIO/阿里云需要）'
    ))
    op.add_column('oss_configs', sa.Column(
        'region_name', sa.String(32), nullable=False, server_default='us-east-1',
        comment='S3 Region'
    ))


def downgrade() -> None:
    # 1. 移除新增的列
    op.drop_column('oss_configs', 'region_name')
    op.drop_column('oss_configs', 'endpoint_url')

    # 2. 恢复 domain_name 列
    op.add_column('oss_configs', sa.Column(
        'domain_name', sa.String(32), nullable=False, server_default='default',
        comment='S3 域名称'
    ))

    # 3. 恢复 s3_domains 表
    op.create_table(
        's3_domains',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('domain_name', sa.String(32), nullable=False, unique=True),
        sa.Column('endpoint_url', sa.String(256), nullable=True),
        sa.Column('region_name', sa.String(32), nullable=False, server_default='us-east-1'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_s3_domains_domain_name', 's3_domains', ['domain_name'])
