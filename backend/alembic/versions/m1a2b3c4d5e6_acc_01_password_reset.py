"""ACC-01.3: password_reset_tokens + user.refresh_tokens_invalid_before

Revision ID: m1a2b3c4d5e6
Revises: l0a1b2c3d4e5
Create Date: 2026-07-24 14:00:00.000000

ACC-01.3 任务：
- 新建 password_reset_tokens 表（找回密码 Token）
  字段：id / user_id / token_hash(唯一) / expires_at / used_at / created_at / ip_address
- users 表新增 refresh_tokens_invalid_before 字段（DateTime, nullable）
  重置密码成功时设为 now()，refresh 端点校验 token iat >= 此时间，
  实现"旧刷新令牌失效"。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m1a2b3c4d5e6"
down_revision: Union[str, None] = "l0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False,
                  comment="用户 ID"),
        sa.Column("token_hash", sa.String(length=128), nullable=False,
                  comment="Token 的 SHA-256 哈希；不存明文"),
        sa.Column("expires_at", sa.DateTime(), nullable=False,
                  comment="过期时间（默认 30 分钟）"),
        sa.Column("used_at", sa.DateTime(), nullable=True,
                  comment="使用时间；NULL 表示未使用"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True,
                  comment="请求发起 IP（审计用）"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_token_hash"),
    )
    op.create_index(op.f("ix_password_reset_tokens_id"),
                    "password_reset_tokens", ["id"])
    op.create_index(op.f("ix_password_reset_tokens_user_id"),
                    "password_reset_tokens", ["user_id"])
    op.create_index(op.f("ix_password_reset_tokens_token_hash"),
                    "password_reset_tokens", ["token_hash"], unique=True)
    op.create_index("idx_prt_user_created",
                    "password_reset_tokens", ["user_id", "created_at"])

    op.add_column(
        "users",
        sa.Column(
            "refresh_tokens_invalid_before",
            sa.DateTime(),
            nullable=True,
            comment="ACC-01.3: 此时间之前签发的 refresh token 全部失效（重置密码时设置）",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "refresh_tokens_invalid_before")
    op.drop_index("idx_prt_user_created", table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_token_hash"),
                  table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"),
                  table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_id"),
                  table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
