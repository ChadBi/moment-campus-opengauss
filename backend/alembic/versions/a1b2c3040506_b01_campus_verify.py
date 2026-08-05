"""B-01: user 校园认证字段 + campus_verify_tokens 表

Revision ID: a1b2c3040506
Revises: d6e7f8a9b0c1
Create Date: 2026-08-06 00:00:00.000000

导师反馈完善（工作流 B：校园身份认证）：
- users 新增 campus_verified / student_id / campus_email / campus_verified_at
- 新建 campus_verify_tokens 表：学号+校园邮箱验证码（一次性、限时、哈希存储）
  字段：id / user_id / school_id / target_email / token_hash / expires_at
        / used_at / created_at / ip_address
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3040506"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campus_verify_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False,
                  comment="申请认证的用户 ID"),
        sa.Column("school_id", sa.BigInteger(), nullable=False,
                  comment="认证所属学校（多租户隔离）"),
        sa.Column("target_email", sa.String(length=255), nullable=False,
                  comment="用于认证的校园邮箱"),
        sa.Column("token_hash", sa.String(length=128), nullable=False,
                  comment="验证码的 SHA-256 哈希；不存明文"),
        sa.Column("expires_at", sa.DateTime(), nullable=False,
                  comment="过期时间（默认 10 分钟）"),
        sa.Column("used_at", sa.DateTime(), nullable=True,
                  comment="使用时间；NULL 表示未使用"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True,
                  comment="请求发起 IP（审计用）"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campus_verify_tokens_id"),
                    "campus_verify_tokens", ["id"])
    op.create_index(op.f("ix_campus_verify_tokens_user_id"),
                    "campus_verify_tokens", ["user_id"])
    op.create_index(op.f("ix_campus_verify_tokens_school_id"),
                    "campus_verify_tokens", ["school_id"])
    op.create_index("idx_cvt_user_created",
                    "campus_verify_tokens", ["user_id", "created_at"])
    op.create_index("ix_campus_verify_tokens_token_hash",
                    "campus_verify_tokens", ["token_hash"], unique=True)

    op.add_column(
        "users",
        sa.Column("campus_verified", sa.Boolean(), nullable=False,
                  server_default="false", comment="B-01: 是否已完成校园身份认证"),
    )
    op.add_column(
        "users",
        sa.Column("student_id", sa.String(length=50), nullable=True,
                  comment="B-01: 校园学号（认证通过后记录）"),
    )
    op.add_column(
        "users",
        sa.Column("campus_email", sa.String(length=255), nullable=True,
                  comment="B-01: 用于认证的校园邮箱"),
    )
    op.add_column(
        "users",
        sa.Column("campus_verified_at", sa.DateTime(), nullable=True,
                  comment="B-01: 校园身份认证通过时间"),
    )


def downgrade() -> None:
    op.drop_column("users", "campus_verified_at")
    op.drop_column("users", "campus_email")
    op.drop_column("users", "student_id")
    op.drop_column("users", "campus_verified")
    op.drop_index("ix_campus_verify_tokens_token_hash", table_name="campus_verify_tokens")
    op.drop_index("idx_cvt_user_created", table_name="campus_verify_tokens")
    op.drop_index(op.f("ix_campus_verify_tokens_school_id"), table_name="campus_verify_tokens")
    op.drop_index(op.f("ix_campus_verify_tokens_user_id"), table_name="campus_verify_tokens")
    op.drop_index(op.f("ix_campus_verify_tokens_id"), table_name="campus_verify_tokens")
    op.drop_table("campus_verify_tokens")