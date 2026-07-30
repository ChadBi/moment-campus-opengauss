"""迁移脚本：回填现有用户的 email_password 身份记录。

运行方式：
    cd backend
    python -m app.scripts.migrate_identities

或者：
    python -c "from app.scripts.migrate_identities import run_migration; run_migration()"
"""
import asyncio
import logging
import os
import sys

# 确保能导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker, engine
from app.models.user import User
from app.models.user_auth_identity import UserAuthIdentity

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def run_migration():
    """回填所有现有用户的 email_password 身份记录。"""
    logger.info("开始迁移：回填 email_password 身份记录...")

    async with async_session_maker() as db:
        # 1. 查找所有用户
        result = await db.execute(select(User).where(User.is_deleted == False))
        users = result.scalars().all()
        logger.info(f"共 {len(users)} 个用户需要检查")

        created_count = 0
        skipped_count = 0

        for user in users:
            # 检查是否已有 email_password 身份
            identity_check = await db.execute(
                select(UserAuthIdentity).where(
                    UserAuthIdentity.user_id == user.id,
                    UserAuthIdentity.identity_type == "email_password",
                    UserAuthIdentity.identity_key == user.email,
                    UserAuthIdentity.is_deleted == False,
                )
            )
            existing = identity_check.scalar_one_or_none()

            if existing is not None:
                skipped_count += 1
                continue

            # 创建身份记录
            identity = UserAuthIdentity(
                user_id=user.id,
                identity_type="email_password",
                identity_key=user.email,
                password_hash=user.password_hash,
                last_used_at=user.last_login_at,
            )
            db.add(identity)
            created_count += 1

            # 每 100 个用户提交一次
            if created_count % 100 == 0:
                await db.commit()
                logger.info(f"已处理 {created_count} 个用户...")

        await db.commit()
        logger.info(f"迁移完成：新建 {created_count} 条身份记录，跳过 {skipped_count} 条已有记录")

    # 2. 验证
    logger.info("验证迁移结果...")
    async with async_session_maker() as db:
        total_users = (await db.execute(
            text("SELECT COUNT(*) FROM users WHERE is_deleted = false")
        )).scalar()
        total_identities = (await db.execute(
            text("SELECT COUNT(*) FROM user_auth_identities WHERE identity_type = 'email_password' AND is_deleted = false")
        )).scalar()
        users_without = (await db.execute(
            text("SELECT COUNT(*) FROM users u WHERE u.is_deleted = false AND NOT EXISTS ("
                 "SELECT 1 FROM user_auth_identities i WHERE i.user_id = u.id "
                 "AND i.identity_type = 'email_password' AND i.is_deleted = false)")
        )).scalar()

        logger.info(f"用户总数: {total_users}")
        logger.info(f"email_password 身份总数: {total_identities}")
        logger.info(f"缺少身份的用户数: {users_without}")

        if users_without == 0:
            logger.info("✅ 迁移成功：所有用户都有对应的 email_password 身份记录")
        else:
            logger.warning(f"⚠️ 仍有 {users_without} 个用户缺少身份记录")


if __name__ == "__main__":
    asyncio.run(run_migration())
