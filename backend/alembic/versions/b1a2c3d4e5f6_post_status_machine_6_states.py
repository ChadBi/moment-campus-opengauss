"""post status machine 6 states

Revision ID: b1a2c3d4e5f6
Revises: af3fef102173
Create Date: 2026-07-02 16:00:00.000000

为 posts.status 字段添加 6 态状态机注释（T-B-01）。
- 字段类型保持 String(20) 不变
- default 保持 "pending" 不变
- 仅添加 comment 说明 6 态：draft/pending/published/expired/conflict/archived
- 无数据迁移（现有 published/pending 数据均兼容新状态机）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, None] = 'af3fef102173'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 status 字段注释（仅 PostgreSQL/openGauss 生效，SQLite 忽略 comment）"""
    # SQLite 不支持 column comment，op.alter_column 在 SQLite 上会报错，
    # 因此只在非 SQLite 方言下执行。
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column(
            "posts",
            "status",
            existing_type=sa.String(length=20),
            existing_nullable=False,
            existing_server_default=sa.text("'pending'"),
            comment="状态：draft/pending/published/expired/conflict/archived（6 态状态机，详见 app.core.post_status）",
        )


def downgrade() -> None:
    """移除 status 字段注释"""
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column(
            "posts",
            "status",
            existing_type=sa.String(length=20),
            existing_nullable=False,
            existing_server_default=sa.text("'pending'"),
            comment=None,
        )
