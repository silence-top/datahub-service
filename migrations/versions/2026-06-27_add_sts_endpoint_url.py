# 2026-06-27_add_role_arn_and_provider.py — 添加 role_arn 和 provider 配置
"""添加 role_arn、provider 字段，删除 sts_endpoint_url 字段"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_sts_endpoint"
down_revision = "oss_key_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 检查已有列
    existing = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='oss_configs'"
    )).fetchall()}

    # 删除不再需要的 sts_endpoint_url
    if "sts_endpoint_url" in existing:
        op.drop_column("oss_configs", "sts_endpoint_url")

    # 添加 provider 字段
    if "provider" not in existing:
        op.add_column(
            "oss_configs",
            sa.Column(
                "provider",
                sa.String(length=16),
                nullable=False,
                server_default="aliyun",
                comment="OSS 运营商：aliyun / aws / minio",
            ),
        )

    # 添加 role_arn 字段
    if "role_arn" not in existing:
        op.add_column(
            "oss_configs",
            sa.Column(
                "role_arn",
                sa.String(length=256),
                nullable=True,
                comment="RAM Role ARN（阿里云 STS AssumeRole 用，如 acs:ram::123:role/xxx）",
            ),
        )


def downgrade() -> None:
    op.drop_column("oss_configs", "role_arn")
    op.drop_column("oss_configs", "provider")
    op.add_column(
        "oss_configs",
        sa.Column(
            "sts_endpoint_url",
            sa.String(length=256),
            nullable=True,
            comment="STS Endpoint URL（获取临时凭证用）",
        ),
    )
