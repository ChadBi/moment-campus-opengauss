"""ACC-01.2: school_invitations 增加 expires_at / used_by 字段

Revision ID: n2b3c4d5e6f7
Revises: m1a2b3c4d5e6
Create Date: 2026-07-24 15:00:00.000000

ACC-01.2 任务：
- school_invitations 表新增 expires_at（DateTime, nullable）：邀请码过期时间，NULL 不限时
- school_invitations 表新增 used_by（BigInteger, nullable, FK users.id）：实际使用该邀请码的用户 ID
- 既有 accepted_at / status='accepted' 语义保留：accepted_at 即"使用时间"，status='accepted' 即"已使用"

向后兼容：两列均 nullable，旧数据不受影响；schools.py 既有 join_school 流程不变。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n2b3c4d5e6f7"
down_revision: Union[str, None] = "m1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "school_invitations",
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=True,
            comment="ACC-01.2: 邀请码过期时间，NULL 表示不限时",
        ),
    )
    op.add_column(
        "school_invitations",
        sa.Column(
            "used_by",
            sa.BigInteger(),
            nullable=True,
            comment="ACC-01.2: 实际使用该邀请码的用户 ID",
        ),
    )
    op.create_foreign_key(
        "fk_school_invitations_used_by",
        "school_invitations",
        "users",
        ["used_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_school_invitations_used_by",
        "school_invitations",
        type_="foreignkey",
    )
    op.drop_column("school_invitations", "used_by")
    op.drop_column("school_invitations", "expires_at")
