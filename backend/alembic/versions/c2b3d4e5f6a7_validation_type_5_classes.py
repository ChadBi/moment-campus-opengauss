"""validation type 5 classes

Revision ID: c2b3d4e5f6a7
Revises: b1a2c3d4e5f6
Create Date: 2026-07-02 17:00:00.000000

T-B-02 协同验证类型扩展为 5 类。
- validation_type 字段长度 String(10) → String(20)
  （最长值 conflict_report=14 字符，原 String(10) 不够）
- 添加 comment 说明 5 类
- 无数据迁移（旧值 valid/invalid/uncertain 通过应用层 ALIASES 映射，保留原值即可；
  后续如需统一为新名，可在 T-B-04 中通过 SQL UPDATE 完成）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2b3d4e5f6a7'
down_revision: Union[str, None] = 'b1a2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """扩大 validation_type 字段长度并添加注释（openGauss）"""
    op.alter_column(
        "validation_records",
        "validation_type",
        existing_type=sa.String(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
        comment="协同验证类型：confirmation/refutation/update/expiration_report/conflict_report（5 类，详见 app.core.validation_type）",
    )


def downgrade() -> None:
    """恢复 validation_type 字段长度并移除注释"""
    op.alter_column(
        "validation_records",
        "validation_type",
        existing_type=sa.String(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
        comment=None,
    )
