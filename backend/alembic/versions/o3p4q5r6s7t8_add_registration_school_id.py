"""B-06: 保存注册学校，支持切校后原校认证保留且其他学校只读。"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o3p4q5r6s7t8"
down_revision: Union[str, None] = "m1n2o3p4q5r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "registration_school_id",
            sa.BigInteger(),
            nullable=True,
            comment="注册时选择的学校；仅该校允许校园身份认证和普通用户写操作",
        ),
    )
    op.create_index(
        "idx_user_registration_school",
        "users",
        ["registration_school_id"],
    )
    op.create_foreign_key(
        "fk_users_registration_school_id_schools",
        "users",
        "schools",
        ["registration_school_id"],
        ["id"],
    )
    op.execute(
        "UPDATE users SET registration_school_id = school_id "
        "WHERE registration_school_id IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_users_registration_school_id_schools",
        "users",
        type_="foreignkey",
    )
    op.drop_index("idx_user_registration_school", table_name="users")
    op.drop_column("users", "registration_school_id")
