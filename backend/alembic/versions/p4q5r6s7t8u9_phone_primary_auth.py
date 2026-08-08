"""手机号主账号、教育邮箱和短信验证码存储。"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p4q5r6s7t8u9"
down_revision: Union[str, None] = "o3p4q5r6s7t8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)
    op.add_column(
        "users",
        sa.Column(
            "phone",
            sa.String(length=11),
            nullable=True,
            comment="国内 11 位手机号；业务唯一身份，新账号必填",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "education_email",
            sa.String(length=255),
            nullable=True,
            comment="教育邮箱；仅用于校园认证，不作为登录凭证",
        ),
    )
    op.execute("UPDATE users SET education_email = LOWER(email) WHERE email IS NOT NULL")
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)
    op.create_index("ix_users_education_email", "users", ["education_email"], unique=True)

    # 邮箱密码身份已不再是有效业务入口；微信身份记录继续保留。
    op.execute("DELETE FROM user_auth_identities WHERE identity_type = 'email_password'")

    op.create_table(
        "sms_verifications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("phone", sa.String(length=11), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("out_id", sa.String(length=100), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("provider", sa.String(length=20), nullable=False, server_default="mock"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sms_verifications_phone", "sms_verifications", ["phone"])
    op.create_index("ix_sms_verifications_out_id", "sms_verifications", ["out_id"], unique=True)
    op.create_index("ix_sms_verifications_sent_at", "sms_verifications", ["sent_at"])
    op.create_index("ix_sms_verifications_expires_at", "sms_verifications", ["expires_at"])
    op.create_index(
        "idx_sms_verification_phone_purpose_sent",
        "sms_verifications",
        ["phone", "purpose", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_sms_verification_phone_purpose_sent", table_name="sms_verifications")
    op.drop_index("ix_sms_verifications_expires_at", table_name="sms_verifications")
    op.drop_index("ix_sms_verifications_sent_at", table_name="sms_verifications")
    op.drop_index("ix_sms_verifications_out_id", table_name="sms_verifications")
    op.drop_index("ix_sms_verifications_phone", table_name="sms_verifications")
    op.drop_table("sms_verifications")
    op.drop_index("ix_users_education_email", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "education_email")
    op.drop_column("users", "phone")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)
