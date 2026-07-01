"""add s3_domains table and rename s3_domain to domain_name

Revision ID: add_s3_domains_table
Revises: add_s3_domain
Create Date: 2026-06-27

创建 s3_domains 表存储域配置（Endpoint/Region），所有域共享统一主账号 AK/SK。
将 oss_configs.s3_domain 重命名为 domain_name。
"""
from alembic import op
import sqlalchemy as sa

revision = "add_s3_domains_table"
down_revision = "add_s3_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 s3_domains 表
    op.create_table(
        's3_domains',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('domain_name', sa.String(32), nullable=False, unique=True, comment='域名称'),
        sa.Column('endpoint_url', sa.String(256), nullable=True, comment='S3 Endpoint URL'),
        sa.Column('region_name', sa.String(32), nullable=False, server_default='us-east-1', comment='S3 Region'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true', comment='是否启用'),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default='false', comment='是否默认域'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), comment='更新时间'),
    )
    
    # 2. 创建索引
    op.create_index('ix_s3_domains_domain_name', 's3_domains', ['domain_name'])
    
    # 3. 重命名 oss_configs.s3_domain → domain_name
    op.alter_column('oss_configs', 's3_domain', new_column_name='domain_name')


def downgrade() -> None:
    # 1. 重命名回 s3_domain
    op.alter_column('oss_configs', 'domain_name', new_column_name='s3_domain')
    
    # 2. 删除索引
    op.drop_index('ix_s3_domains_domain_name', 's3_domains')
    
    # 3. 删除表
    op.drop_table('s3_domains')
