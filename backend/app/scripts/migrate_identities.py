"""历史身份清理脚本。

旧版本脚本会回填 email_password 身份，已与手机号主账号方案冲突。保留脚本入口
仅用于已有环境清理残留记录；微信小程序身份不会被修改。
"""
import asyncio
import logging

from sqlalchemy import text

from app.database import async_session_maker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def cleanup_legacy_email_identities() -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            text("DELETE FROM user_auth_identities WHERE identity_type = 'email_password'")
        )
        await session.commit()
        return result.rowcount or 0


async def main() -> None:
    count = await cleanup_legacy_email_identities()
    logger.info("已清理 %s 条历史 email_password 身份；微信身份保持不变", count)


if __name__ == "__main__":
    asyncio.run(main())
