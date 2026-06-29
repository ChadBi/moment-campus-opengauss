"""
演示数据填充脚本
用于开发和测试环境
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_maker, engine
from app.models import (
    Base, User, School, Post, Category, PostType, Tag, PostTag, PostImage,
    Location, Comment, Like, Favorite, ValidationRecord, Report, Notification,
    TopicCollection, TopicCollectionPost, Draft, BrowseHistory, SearchHistory,
    AdminOperationLog
)
import bcrypt


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


async def init_db():
    """初始化数据库，创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_schools(session: AsyncSession):
    """创建学校数据"""
    schools = [
        School(
            name="华东师范大学",
            code="ecnu",
            province="上海",
            city="上海",
            address="上海市普陀区中山北路3663号",
            center_lat=31.2297,
            center_lng=121.4075,
            map_zoom=15,
            is_active=True
        ),
        School(
            name="复旦大学",
            code="fudan",
            province="上海",
            city="上海",
            address="上海市杨浦区邯郸路220号",
            center_lat=31.2982,
            center_lng=121.5035,
            map_zoom=15,
            is_active=True
        )
    ]
    session.add_all(schools)
    await session.flush()
    return schools


async def seed_categories(session: AsyncSession):
    """创建分类数据"""
    categories = [
        Category(name="校园美食", code="food", icon="🍜", description="校园食堂、餐厅、小吃", default_validity_days=30, sort_order=1, is_active=True),
        Category(name="校园动物", code="animal", icon="🐱", description="校园流浪猫狗、野生动物", default_validity_days=90, sort_order=2, is_active=True),
        Category(name="打印服务", code="print", icon="🖨️", description="打印店、复印服务", default_validity_days=60, sort_order=3, is_active=True),
        Category(name="校园活动", code="event", icon="🎉", description="社团活动、讲座、演出", default_validity_days=7, sort_order=4, is_active=True),
        Category(name="学习资源", code="study", icon="📚", description="自习室、图书馆、学习小组", default_validity_days=30, sort_order=5, is_active=True),
        Category(name="生活服务", code="service", icon="🛠️", description="快递、维修、洗衣", default_validity_days=60, sort_order=6, is_active=True),
        Category(name="校园交通", code="transport", icon="🚌", description="校车、公交、共享单车", default_validity_days=30, sort_order=7, is_active=True),
        Category(name="校园设施", code="facility", icon="🏢", description="体育馆、游泳池、健身房", default_validity_days=90, sort_order=8, is_active=True),
        Category(name="活动场地", code="venue", icon="🏟️", description="会议室、活动室、操场", default_validity_days=30, sort_order=9, is_active=True),
        Category(name="失物招领", code="lost_found", icon="🔍", description="失物招领信息", default_validity_days=30, sort_order=10, is_active=True),
        Category(name="校园兼职", code="job", icon="💼", description="兼职、实习信息", default_validity_days=30, sort_order=11, is_active=True),
        Category(name="其他", code="other", icon="📌", description="其他校园信息", default_validity_days=30, sort_order=12, is_active=True),
    ]
    session.add_all(categories)
    await session.flush()
    return categories


async def seed_post_types(session: AsyncSession):
    """创建信息类型数据"""
    post_types = [
        PostType(name="普通信息", code="normal", description="一般校园信息", sort_order=1, is_active=True),
        PostType(name="活动", code="event", description="校园活动信息", sort_order=2, is_active=True),
        PostType(name="失物招领", code="lost_found", description="失物招领信息", sort_order=3, is_active=True),
    ]
    session.add_all(post_types)
    await session.flush()
    return post_types


async def seed_users(session: AsyncSession, schools: list):
    """创建用户数据"""
    users = []
    
    # 创建管理员
    admin = User(
        email="admin@momentcampus.com",
        nickname="管理员",
        password_hash=get_password_hash("pass123"),  # 使用短密码避免 bcrypt 72 字节限制
        school_id=schools[0].id,
        role="admin",
        bio="系统管理员",
        is_active=True
    )
    users.append(admin)
    
    # 创建普通用户
    for i in range(1, 11):
        user = User(
            email=f"user{i}@example.com",
            nickname=f"用户{i}",
            password_hash=get_password_hash("pass123"),  # 使用短密码避免 bcrypt 72 字节限制
            school_id=schools[i % 2].id,
            role="user",
            bio=f"这是用户{i}的个人简介",
            is_active=True
        )
        users.append(user)
    
    session.add_all(users)
    await session.flush()
    return users


async def seed_locations(session: AsyncSession, schools: list):
    """创建地点数据"""
    locations = []
    
    # 华东师范大学地点
    ecnu_locations = [
        ("丽娃河畔", 31.2297, 121.4075, "校园著名景点"),
        ("第一食堂", 31.2300, 121.4080, "主食堂"),
        ("图书馆", 31.2295, 121.4070, "主图书馆"),
        ("体育馆", 31.2290, 121.4065, "综合体育馆"),
        ("教学楼A", 31.2305, 121.4085, "主要教学楼"),
        ("学生宿舍区", 31.2310, 121.4090, "学生生活区"),
        ("校园超市", 31.2298, 121.4078, "便利店"),
        ("打印店", 31.2302, 121.4082, "文印服务"),
    ]
    
    for name, lat, lng, desc in ecnu_locations:
        loc = Location(
            school_id=schools[0].id,
            name=name,
            description=desc,
            latitude=lat,
            longitude=lng,
            post_count=0,
            is_verified=True
        )
        locations.append(loc)
    
    # 复旦大学地点
    fudan_locations = [
        ("光华楼", 31.2982, 121.5035, "标志性建筑"),
        ("食堂一楼", 31.2985, 121.5040, "主食堂"),
        ("图书馆", 31.2980, 121.5030, "主图书馆"),
        ("体育馆", 31.2975, 121.5025, "综合体育馆"),
        ("教学楼B", 31.2990, 121.5045, "主要教学楼"),
        ("学生宿舍区", 31.2995, 121.5050, "学生生活区"),
        ("校园超市", 31.2983, 121.5038, "便利店"),
    ]
    
    for name, lat, lng, desc in fudan_locations:
        loc = Location(
            school_id=schools[1].id,
            name=name,
            description=desc,
            latitude=lat,
            longitude=lng,
            post_count=0,
            is_verified=True
        )
        locations.append(loc)
    
    session.add_all(locations)
    await session.flush()
    return locations


async def seed_posts(session: AsyncSession, users: list, schools: list, categories: list, post_types: list, locations: list):
    """创建信息数据"""
    posts = []
    
    # 创建30条信息
    for i in range(30):
        user = users[i % len(users)]
        school = schools[i % 2]
        category = categories[i % len(categories)]
        post_type = post_types[i % len(post_types)]
        location = locations[i % len(locations)]
        
        post = Post(
            user_id=user.id,
            school_id=school.id,
            category_id=category.id,
            post_type_id=post_type.id,
            location_id=location.id,
            title=f"测试信息标题 {i+1}",
            content=f"这是第{i+1}条测试信息的详细内容。包含校园生活相关的信息分享。",
            is_anonymous=i % 5 == 0,  # 20%匿名
            status="published",
            view_count=random.randint(10, 500),
            like_count=random.randint(0, 50),
            comment_count=0,
            favorite_count=random.randint(0, 20),
            valid_count=random.randint(0, 10),
            invalid_count=0,
            expire_at=datetime.now() + timedelta(days=category.default_validity_days),
            is_top=i < 3,  # 前3条置顶
            is_recommend=i % 4 == 0,  # 25%推荐
        )
        posts.append(post)
    
    session.add_all(posts)
    await session.flush()
    return posts


async def seed_comments(session: AsyncSession, posts: list, users: list):
    """创建评论数据"""
    comments = []
    
    # 为每条信息创建1-3条评论
    for post in posts:
        num_comments = random.randint(1, 3)
        for j in range(num_comments):
            user = users[random.randint(0, len(users)-1)]
            comment = Comment(
                post_id=post.id,
                user_id=user.id,
                parent_id=None,
                content=f"这是第{j+1}条评论，内容很有意义。",
                like_count=random.randint(0, 10),
                status="published"
            )
            comments.append(comment)
    
    session.add_all(comments)
    await session.flush()
    
    # 更新信息的评论数
    for post in posts:
        post.comment_count = len([c for c in comments if c.post_id == post.id])
    
    return comments


async def seed_validation_records(session: AsyncSession, posts: list, users: list):
    """创建有效性确认记录"""
    records = []
    
    # 为部分信息创建有效性确认
    for post in posts[:20]:  # 前20条信息
        num_records = random.randint(1, 3)
        for _ in range(num_records):
            user = users[random.randint(0, len(users)-1)]
            record = ValidationRecord(
                post_id=post.id,
                user_id=user.id,
                validation_type="valid" if random.random() > 0.2 else "invalid",
                comment="信息仍然有效" if random.random() > 0.3 else "信息已过时"
            )
            records.append(record)
    
    session.add_all(records)
    await session.flush()
    
    # 更新信息的有效性计数
    for post in posts:
        post_records = [r for r in records if r.post_id == post.id]
        post.valid_count = len([r for r in post_records if r.validation_type == "valid"])
        post.invalid_count = len([r for r in post_records if r.validation_type == "invalid"])
    
    return records


async def seed_notifications(session: AsyncSession, users: list, posts: list):
    """创建通知数据"""
    notifications = []
    
    # 为每个用户创建1-2条通知
    for user in users[:10]:
        num_notifications = random.randint(1, 2)
        for _ in range(num_notifications):
            notification = Notification(
                user_id=user.id,
                type=random.choice(["comment", "like", "system"]),
                title="您有新的通知",
                content="这是一条测试通知内容",
                target_type="post",
                target_id=posts[random.randint(0, len(posts)-1)].id,
                actor_id=users[random.randint(0, len(users)-1)].id,
                is_read=random.choice([True, False])
            )
            notifications.append(notification)
    
    session.add_all(notifications)
    await session.flush()
    return notifications


async def seed_topic_collections(session: AsyncSession, schools: list, users: list, posts: list):
    """创建专题集合数据"""
    topics = []
    
    # 创建6个专题
    topic_data = [
        ("新生入学指南", "为新生提供校园生活必备信息", schools[0].id),
        ("毕业季攻略", "毕业季相关活动和信息汇总", schools[0].id),
        ("校园美食地图", "校园周边美食推荐", schools[1].id),
        ("学习资源汇总", "图书馆、自习室学习资源", schools[1].id),
        ("社团活动精选", "精彩社团活动合集", schools[0].id),
        ("校园生活贴士", "校园生活实用技巧", schools[1].id),
    ]
    
    for i, (title, desc, school_id) in enumerate(topic_data):
        topic = TopicCollection(
            title=title,
            description=desc,
            school_id=school_id,
            creator_id=users[i % len(users)].id,
            post_count=0,
            view_count=random.randint(50, 200),
            status="published",
            sort_order=i+1
        )
        topics.append(topic)
    
    session.add_all(topics)
    await session.flush()
    
    # 为每个专题关联5条信息
    topic_posts = []
    for topic in topics:
        selected_posts = random.sample(posts, min(5, len(posts)))
        for idx, post in enumerate(selected_posts):
            tp = TopicCollectionPost(
                topic_collection_id=topic.id,
                post_id=post.id,
                sort_order=idx+1
            )
            topic_posts.append(tp)
        topic.post_count = len(selected_posts)
    
    session.add_all(topic_posts)
    await session.flush()
    return topics


async def seed_reports(session: AsyncSession, posts: list, users: list):
    """创建举报记录数据"""
    reports = []
    
    # 创建10条举报记录
    for i in range(10):
        report = Report(
            post_id=posts[i % len(posts)].id,
            comment_id=None,
            reporter_id=users[i % len(users)].id,
            report_type=random.choice(["fake", "ad", "inappropriate", "other"]),
            description=f"举报说明 {i+1}",
            status=random.choice(["pending", "processing", "resolved"]),
            handler_id=users[0].id if i % 2 == 0 else None,  # 管理员处理
            handle_result="已处理" if i % 2 == 0 else None
        )
        reports.append(report)
    
    session.add_all(reports)
    await session.flush()
    return reports


async def seed_data():
    """主函数：填充所有演示数据"""
    print("开始初始化数据库...")
    await init_db()
    
    async with async_session_maker() as session:
        print("创建学校数据...")
        schools = await seed_schools(session)
        print(f"✓ 创建了 {len(schools)} 所学校")
        
        print("创建分类数据...")
        categories = await seed_categories(session)
        print(f"✓ 创建了 {len(categories)} 个分类")
        
        print("创建信息类型数据...")
        post_types = await seed_post_types(session)
        print(f"✓ 创建了 {len(post_types)} 个信息类型")
        
        print("创建用户数据...")
        users = await seed_users(session, schools)
        print(f"✓ 创建了 {len(users)} 个用户（包含1个管理员）")
        
        print("创建地点数据...")
        locations = await seed_locations(session, schools)
        print(f"✓ 创建了 {len(locations)} 个地点")
        
        print("创建信息数据...")
        posts = await seed_posts(session, users, schools, categories, post_types, locations)
        print(f"✓ 创建了 {len(posts)} 条信息")
        
        print("创建评论数据...")
        comments = await seed_comments(session, posts, users)
        print(f"✓ 创建了 {len(comments)} 条评论")
        
        print("创建有效性确认记录...")
        validation_records = await seed_validation_records(session, posts, users)
        print(f"✓ 创建了 {len(validation_records)} 条有效性确认记录")
        
        print("创建通知数据...")
        notifications = await seed_notifications(session, users, posts)
        print(f"✓ 创建了 {len(notifications)} 条通知")
        
        print("创建专题集合数据...")
        topics = await seed_topic_collections(session, schools, users, posts)
        print(f"✓ 创建了 {len(topics)} 个专题集合")
        
        print("创建举报记录数据...")
        reports = await seed_reports(session, posts, users)
        print(f"✓ 创建了 {len(reports)} 条举报记录")
        
        await session.commit()
        print("\n✅ 所有演示数据填充完成！")
        print("\n管理员账号：")
        print("  邮箱: admin@momentcampus.com")
        print("  密码: pass123")
        print("\n普通用户账号：")
        print("  邮箱: user1@example.com ~ user10@example.com")
        print("  密码: pass123")


if __name__ == "__main__":
    asyncio.run(seed_data())
