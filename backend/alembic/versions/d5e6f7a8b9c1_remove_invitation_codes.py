"""移除邀请码功能：drop school_invitations 表

用户决策（2026-08-01）：注册无需邀请码，初始加入的学校改为注册时自由选择。
删除整个邀请码功能，含 school_invitations 表及其索引。

Revision ID: d5e6f7a8b9c1
Revises: b6c7d8e9f0a1
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c1"
down_revision: Union[str, None] = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """删除邀请码表（索引随表删除）。"""
    op.drop_table("school_invitations")


def downgrade() -> None:
    """重建 school_invitations 表（含 ACC-01.2 新增的 expires_at / used_by 列）。"""
    op.create_table(
        "school_invitations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("school_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("invitation_code", sa.String(64), nullable=False),
        sa.Column("invited_by", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="expires"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("used_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["used_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_invitation_code", "school_invitations", ["invitation_code"], unique=True)
    op.create_index("idx_invitation_email_status", "school_invitations", ["email", "status"])
    op.create_index("idx_invitation_school_status", "school_invitations", ["school_id", "status"])
