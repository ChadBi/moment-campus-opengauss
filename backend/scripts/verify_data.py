"""
验证演示数据填充结果
"""
import asyncio
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, func
from app.database import async_session_maker
from app.models import (
    User, School, Post, Category, Tag, PostTag, PostImage,
    Location, Comment, Like, Favorite, ValidationRecord, Report, Notification,
    TopicCollection, TopicCollectionPost, Draft, BrowseHistory, SearchHistory,
    AdminOperationLog
)


async def verify_data():
    """验证数据库中的数据量"""
    async with async_session_maker() as session:
        print("=== 数据库数据验证 ===\n")
        
        # 学校
        result = await session.execute(select(func.count()).select_from(School))
        school_count = result.scalar()
        print(f"学校数量: {school_count}")
        
        # 分类
        result = await session.execute(select(func.count()).select_from(Category))
        category_count = result.scalar()
        print(f"分类数量: {category_count}")

        # 用户
        result = await session.execute(select(func.count()).select_from(User))
        user_count = result.scalar()
        print(f"用户数量: {user_count}")
        
        # 地点
        result = await session.execute(select(func.count()).select_from(Location))
        location_count = result.scalar()
        print(f"地点数量: {location_count}")
        
        # 信息
        result = await session.execute(select(func.count()).select_from(Post))
        post_count = result.scalar()
        print(f"信息数量: {post_count}")
        
        # 评论
        result = await session.execute(select(func.count()).select_from(Comment))
        comment_count = result.scalar()
        print(f"评论数量: {comment_count}")
        
        # 有效性确认记录
        result = await session.execute(select(func.count()).select_from(ValidationRecord))
        validation_count = result.scalar()
        print(f"有效性确认记录数量: {validation_count}")
        
        # 通知
        result = await session.execute(select(func.count()).select_from(Notification))
        notification_count = result.scalar()
        print(f"通知数量: {notification_count}")
        
        # 专题集合
        result = await session.execute(select(func.count()).select_from(TopicCollection))
        topic_count = result.scalar()
        print(f"专题集合数量: {topic_count}")
        
        # 专题关联信息
        result = await session.execute(select(func.count()).select_from(TopicCollectionPost))
        topic_post_count = result.scalar()
        print(f"专题关联信息数量: {topic_post_count}")
        
        # 举报记录
        result = await session.execute(select(func.count()).select_from(Report))
        report_count = result.scalar()
        print(f"举报记录数量: {report_count}")
        
        print("\n=== 验证完成 ===")
        
        # 验证管理员账号
        result = await session.execute(
            select(User).where(User.email == "admin@momentcampus.com")
        )
        admin = result.scalar_one_or_none()
        if admin:
            print(f"\n管理员账号验证:")
            print(f"  邮箱: {admin.email}")
            print(f"  昵称: {admin.nickname}")
            print(f"  角色: {admin.role}")
            print(f"  密码哈希: {admin.password_hash[:20]}...")
        
        # 验证普通用户
        result = await session.execute(
            select(User).where(User.email.like('user%@example.com'))
        )
        users = result.scalars().all()
        print(f"\n普通用户数量: {len(users)}")
        if users:
            print(f"  第一个用户: {users[0].email}")
            print(f"  最后一个用户: {users[-1].email}")


if __name__ == "__main__":
    asyncio.run(verify_data())
