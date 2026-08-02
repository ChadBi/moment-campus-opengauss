"""大数据量演示数据生成脚本（每校 500 帖 + 50 用户）

用途：为三所演示学校程序化生成接近真实校园社区规模的数据，替代 seed_data.py 的手写小数据集。

规模（每校）：
- 50 个活跃用户（1 admin + 49 user，含现有演示账号）
- 500 条有效帖子（status=published，过去 30 天幂律分布）
- 真实互动：浏览数按热度分层（热门/中等/冷门），点赞率 6%~15%，点赞:评论 ≈ 6:1
- likes 表真实填充，帖子 like_count 与实际 Like 记录一致
- 所有帖子 ≥1 条主题相关评论，热门帖更多
- 少量协同验证记录（confirmation/refutation）

运行前需先执行：alembic upgrade head
运行方式（Windows PowerShell）：
    $env:APP_ENV="opengauss"
    python scripts/generate_bulk_data.py
脚本自身会清空现有全部业务数据并重新填充。

生成完成后（可选）回填向量：
    python scripts/generate_embeddings.py --batch-size 50
"""
import asyncio
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import app.db_compat  # noqa: F401  openGauss 兼容性补丁，必须在 SQLAlchemy 引擎前导入
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models import (
    User, Post, Comment, Like, ValidationRecord, SchoolMembership,
)
from scripts.seed_data import (
    init_db, seed_plans, seed_schools, seed_school_settings, seed_subscriptions,
    seed_categories, seed_locations, SCHOOLS_REGISTRY, get_password_hash,
    CROSS_SCHOOL_MEMBERSHIPS,
)

# =============================================================================
# 常量配置
# =============================================================================
USERS_PER_SCHOOL = 50      # 每校用户数（含 1 admin）
POSTS_PER_SCHOOL = 500     # 每校有效（published）帖子数
PASSWORD = "pass123"

# 浏览数按热度分层（幂律离散化）：top 5% 热门 / 60% 中等 / 35% 冷门
VIEW_RANGES = {
    "hot": (1500, 3000),   # 热门帖：高浏览高互动
    "mid": (80, 400),      # 中等帖
    "cold": (30, 100),     # 冷门帖：低互动但仍有评论
}
TIER_SHARES = {"hot": 0.05, "mid": 0.60, "cold": 0.35}
# 点赞率（浏览数的 6%~15%）与 点赞:评论 比例（评论=点赞×12%~20%）
LIKE_RATE = (0.06, 0.15)
COMMENT_RATE = (0.12, 0.20)
MAX_LIKERS = 48            # 同校用户池（49 人）扣除发帖人后的点赞上限
MAX_COMMENTS = 40          # 热门帖评论数上限

# 帖子创建时间：过去 30 天内，近期更多（幂律）
RECENT_DAYS = 30

# =============================================================================
# 用户属性模板
# =============================================================================
NICK_PREFIX = [
    "江大", "蠡湖", "江南", "二食堂", "图书馆", "跑道", "北门", "南门", "宿舍",
    "期末", "自习", "干饭", "骑行", "摄影", "志愿者", "计算机", "机械", "设计",
    "外院", "理学院", "经管", "医学", "法学", "文法", "音乐", "美术", "建筑", "化工",
]
NICK_SUFFIX = [
    "小新", "学姐", "学长", "同学", "干饭人", "夜猫子", "跑者", "书虫", "摄影控",
    "手工达人", "游戏宅", "健身党", "志愿星", "学霸", "咸鱼", "猫奴", "钓鱼佬",
    "骑行侠", "社团人", "摸鱼人", "卷王", "躺平者", "早八人", "晚自习常客",
]
COLLEGES = [
    "计算机学院", "机械工程学院", "设计学院", "外国语学院", "理学院", "商学院",
    "医学院", "法学院", "人文学院", "化工学院", "电气学院", "土木学院", "纺织学院",
    "食品学院", "物联网学院", "环境学院", "数媒学院", "公共管理学院",
]
GRADES = ["大一", "大二", "大三", "大四", "研一", "研二", "研三"]
INTERESTS = [
    "校园美食探店", "图书馆自习", "夜跑爱好者", "摄影记录校园", "流浪动物救助",
    "羽毛球", "篮球", "桌游", "剧本杀", "电竞", "动漫", "音乐现场", "话剧社",
    "骑行环湖", "志愿服务", "辩论队", "编程竞赛", "考研备战", "实习求职", "探店打卡",
]


def _gen_nickname() -> str:
    return random.choice(NICK_PREFIX) + random.choice(NICK_SUFFIX)


def _gen_bio() -> str:
    return f"{random.choice(COLLEGES)}{random.choice(GRADES)} | {random.choice(INTERESTS)}"


# =============================================================================
# 帖子内容模板（按 5 分类；{place} 占位符用学校地点名填充）
# =============================================================================
TITLE_TEMPLATES = {
    "share": [
        "{place}这家店的{food}绝了，便宜又好吃",
        "{place}排队要多久？实测分享",
        "关于{place}的一个冷知识，涨知识了",
        "{place}新装修后体验如何？",
        "在{place}发现一家宝藏小店",
        "{place}早餐推荐，性价比超高",
        "吐槽一下{place}的排队问题",
        "{place}的隐藏角落，拍照绝美",
        "{place}阿姨人超好，每次都给很多",
        "{place}的{season}限定来了！",
        "今天在{place}遇到暖心一幕",
        "{place}适合自习吗？亲测感受",
        "大家觉得{place}怎么样？",
        "{place}最近人好多，建议错峰",
        "在{place}捡到宝贝了哈哈",
    ],
    "teamup": [
        "周末{place}约起来，缺人",
        "{place}羽毛球局，组队中",
        "找人一起{place}自习，互相监督",
        "{place}电影之夜，有约的吗",
        "想组队参加{place}的活动",
        "{place}晨跑搭子，长期有效",
        "王者开黑车队缺人，{place}附近",
        "{place}摄影约拍，有兴趣的来",
        "考研搭子招募，{place}固定自习",
        "{place}桌游局，新手友好",
        "周末去{place}春游，欢迎加入",
        "{place}篮球半场，还差两个人",
        "想学{place}相关的，求带",
        "{place}志愿服务队招新啦",
        "一起打卡{place}，坚持一个月",
    ],
    "trade": [
        "{place}出{goods}，九成新",
        "毕业季清仓：{goods}低价出",
        "出{goods}，{place}自提",
        "{goods}转让，用了不到一年",
        "{place}附近收{goods}，有出的吗",
        "{goods}急出，价格好商量",
        "出一批{goods}，{place}交易",
        "{goods}几乎全新，只试过一次",
        "搬家出{goods}，{place}面交",
        "{goods}换{goods}也行，{place}",
        "出{goods}，附赠周边小物",
        "{goods}便宜出了，{place}自取",
        "大四清仓：{goods}白菜价",
        "{goods}九成新带票，{place}",
        "{goods}闲置转让，可小刀",
    ],
    "lost_found": [
        "在{place}丢失{goods}，急寻！",
        "{place}捡到{goods}，失主速来",
        "求助：{place}丢的{goods}有人看到吗",
        "{place}拾获{goods}一个，已交服务台",
        "在{place}丢失{goods}，内有重要物品",
        "{place}捡到钥匙一串，认领",
        "昨天{place}丢的{goods}，求转发",
        "{place}拾获{goods}，请失主联系",
        "丢失{goods}，最后一次出现在{place}",
        "{place}捡到学生卡，已放门卫",
        "急！{place}丢的{goods}里面有证件",
        "{place}拾得{goods}，失主看到请回复",
    ],
    "other": [
        "{place}今天有活动，路过可以看看",
        "{place}开放时间调整通知",
        "{place}的{wifi}信号实测报告",
        "关于{place}的使用小贴士",
        "{place}最近在施工，注意绕行",
        "{place}值班表已更新",
        "{place}附近新开了家{shop}",
        "调查：大家觉得{place}该不该改造",
        "{place}注意事项汇总，建议收藏",
        "{place}预约流程详解",
        "收到{place}的通知，分享给大家",
        "{place}存在安全隐患，提醒注意",
    ],
}

BODY_TEMPLATES = {
    "share": [
        "今天去{place}体验了一下，整体感觉不错。价格{price}元左右，分量足，味道也稳定。推荐大家有空去试试，人多的话建议错峰。",
        "在{place}待了一下午，把心得整理了一下：环境干净、服务热情、性价比高。如果大家也有体验，欢迎在评论区补充。",
        "之前一直听说{place}不错，今天终于去打卡了。{detail}，总体值得。想去的朋友可以参考一下。",
        "分享一个{place}的小攻略：最佳时段、人均消费、注意事项都整理好了，需要的自取。",
        "{place}最近人流量明显变多，估计是口碑传开了。排队时间大概{mins}分钟，可以错开饭点。",
    ],
    "teamup": [
        "计划本周{weekday}去{place}，目前{count}人，还差{need}人。时间可以商量，男女不限，新手友好，欢迎有兴趣的同学私信报名。",
        "长期找{place}搭子，时间比较灵活，主要是想找人一起坚持。有兴趣的评论区留言或私信。",
        "准备在{place}组织一次小活动，预计{time}开始，报名人数有限，先到先得。",
        "招募{place}活动伙伴，有经验者优先，但零基础也欢迎，可以一起学。",
        "想找几个志同道合的同学一起去{place}，平时可以互相交流，周末约起来。",
    ],
    "trade": [
        "{goods}，用了{months}个月，日常使用无磕碰，功能一切正常。{price}元出，{place}自提，可小刀，诚心要的私信。",
        "出{goods}，成色如图（九成新），入手渠道正规，有发票。{place}当面交易，爽快的送个小礼物。",
        "{goods}闲置转让，因为毕业季搬家带不走。{price}元，{place}自取，价格可以再聊。",
        "转{goods}一个，几乎全新，只用过几次。{place}交易，支持试，满意再付。",
        "{goods}九成新，配件齐全，{place}面交，诚心出，不墨迹。",
    ],
    "lost_found": [
        "今天{time}在{place}丢失{goods}，特征：{detail}。里面有一些重要物品，找到的朋友请联系我，必有重谢！",
        "在{place}捡到{goods}，目前放在{where}，请失主凭描述前来认领，也麻烦大家帮忙转发让失主看到。",
        "求助：昨天在{place}附近丢失{goods}，监控显示被一位同学捡到，如能归还非常感谢。",
        "{place}拾获{goods}一件，已交至服务台，请失主携带相关证明认领。",
        "在{place}丢的{goods}还没找到，请各位同学帮忙留意一下，有线索请私信。",
    ],
    "other": [
        "刚刚收到的通知，关于{place}的最新安排，发出来给大家同步一下，有需要的留意。",
        "整理了一份{place}的实用指南，包含开放时间、预约方式、常见问题，有需要的可以收藏。",
        "{place}最近有些变化，路过的时候注意一下，具体说明见正文。",
        "关于{place}，有几点想提醒大家：{detail}，安全第一，相互转告。",
        "给大家分享一个{place}的小技巧，实测有效，能省不少时间。",
    ],
}

COMMENT_TEMPLATES = {
    "share": [
        "这个我也发现了！确实不错",
        "亲测好用，支持一下",
        "请问具体在{place}哪个位置？",
        "收藏了，周末去看看",
        "价格这么良心吗？心动",
        "已去过，表示赞同",
        "能不能出个详细攻略？",
        "感谢分享，很实用",
        "哈哈哈哈同感，排队真的久",
        "下次带朋友去试试",
        "老板确实人好，赞一个",
        "这个信息太及时了",
        "有什么推荐必点的吗？",
        "环境怎么样？适合拍照吗？",
        "刚去看了一下，确实如你所说",
    ],
    "teamup": [
        "还缺人吗？想报名",
        "几点开始？方便吗？",
        "已私信！带我一个",
        "时间冲突了，下次一定",
        "需要准备什么吗？第一次参加",
        "有点心动，具体怎么安排？",
        "举手报名，正好闲着",
        "这个活动有意思，算我一个",
        "地点具体在哪？怎么集合？",
        "有群吗？拉我一下",
        "零基础真的可以吗？有点怕拖后腿",
        "已转发给室友，她也有兴趣",
        "本周有空，坐标{place}附近",
        "期待！之前就想参加了",
        "需要AA吗？大概费用多少？",
    ],
    "trade": [
        "还在吗？多少钱出的？",
        "成色怎么样？有实拍图吗？",
        "{place}哪里交易方便？",
        "可以小刀吗？诚心要",
        "还在的话私信你了",
        "有没有发票？保修期到什么时候？",
        "价格再低点考虑一下",
        "怎么联系？麻烦发个联系方式",
        "东西还新吗？想收",
        "能走平台交易吗？",
        "我就在{place}附近，方便看货",
        "这个型号不错，可惜刚买了",
        "已出吗？没出的话我想要",
        "配件全吗？",
        "帮顶一下，好东西",
    ],
    "lost_found": [
        "已转发朋友圈，希望早日找到！",
        "在哪丢的？我帮忙留意",
        "找到了吗？关注后续",
        "帮你顶一下，别沉",
        "我昨天好像看到了类似的",
        "已转宿舍群，大家留意",
        "希望失主早点看到",
        "要不要去失物招领处看看？",
        "帮转！重要物品一定要找回",
        "上次我也丢过，理解你的心情",
        "有消息第一时间通知你",
        "祝早日找回！",
        "已关注，有线索联系你",
        "描述再详细点更好找",
        "顶起来，让更多人看到",
    ],
    "other": [
        "感谢分享，很有用",
        "已收藏，正好需要",
        "这个提醒很及时，谢谢",
        "原来是这样，学到了",
        "支持，希望更多人看到",
        "这个安排合理，赞",
        "能不能再详细说明一下？",
        "信息很有价值，帮顶",
        "收到，感谢同步",
        "问一下，具体时间是？",
        "这个技巧实用，已试过",
        "关注了，后续有更新求通知",
        "大家转发一下，让更多人知道",
        "写得很清楚，辛苦整理",
        "收藏了，随时查看",
    ],
}

VALIDATION_TEMPLATES = {
    "confirmation": [
        "亲测属实，信息准确",
        "已核实，确实如此",
        "我去确认过，没有问题",
        "情况属实，可以放心",
        "刚验证过，和描述一致",
    ],
    "refutation": [
        "信息不准确，实际情况有出入",
        "今天去看已经和描述不同了",
        "这个说法不太对，供参考",
        "价格和时间可能有变动",
    ],
}

# 模板占位词池（用于填充 {food}/{goods}/{price} 等）
FOODS = ["麻辣香锅", "黄焖鸡", "螺蛳粉", "牛肉面", "煎饼果子", "烤冷面", "奶茶", "炸鸡", "关东煮", "炒饭"]
GOODS = ["自行车", "显示器", "蓝牙耳机", "教科书", "吉他", "台灯", "键盘", "行李箱", "平板", "滑板"]
SHOPS = ["奶茶店", "咖啡店", "打印店", "水果店", "超市", "理发店", "洗衣店", "文具店"]
SEASONS = ["季节限定", "新学期", "暑期", "冬季", "毕业季"]
DETAILS = ["味道正宗", "分量很足", "价格实惠", "环境不错", "服务热情", "出餐很快"]
PLACES_EXTRA = ["食堂", "图书馆", "教学楼", "操场", "宿舍楼", "学生活动中心", "北门", "南门", "东门", "商业街"]


def _pick(placeholder_pool: list[str]) -> str:
    return random.choice(placeholder_pool)


# =============================================================================
# 互动数据（幂律分层）
# =============================================================================
def _assign_tiers(n: int) -> list[str]:
    """按 5%/60%/35% 分层分配热度（幂律离散化），随机打乱。"""
    hot = max(1, int(n * TIER_SHARES["hot"]))
    mid = int(n * TIER_SHARES["mid"])
    cold = n - hot - mid
    tiers = ["hot"] * hot + ["mid"] * mid + ["cold"] * cold
    random.shuffle(tiers)
    return tiers


def _gen_view_count(tier: str) -> int:
    lo, hi = VIEW_RANGES[tier]
    return random.randint(lo, hi)


def _fill_template(template: str, place_names: list[str]) -> str:
    """填充模板占位符。"""
    place = random.choice(place_names) if place_names else random.choice(PLACES_EXTRA)
    return (
        template
        .replace("{place}", place)
        .replace("{food}", _pick(FOODS))
        .replace("{goods}", _pick(GOODS))
        .replace("{shop}", _pick(SHOPS))
        .replace("{season}", _pick(SEASONS))
        .replace("{detail}", _pick(DETAILS))
        .replace("{price}", str(random.randint(5, 80)))
        .replace("{mins}", str(random.randint(5, 60)))
        .replace("{count}", str(random.randint(2, 5)))
        .replace("{need}", str(random.randint(1, 3)))
        .replace("{weekday}", random.choice(["周六", "周日", "周三晚", "周五晚"]))
        .replace("{time}", random.choice(["19:00", "14:00", "10:00", "20:30"]))
        .replace("{months}", str(random.randint(3, 24)))
        .replace("{where}", random.choice(["服务台", "门卫室", "宿管阿姨处", "失物招领处"]))
    )


def _gen_created_at() -> datetime:
    """过去 RECENT_DAYS 天内，近期更多（幂律）。"""
    days = int(RECENT_DAYS * (random.random() ** 1.6))
    hours = random.randint(0, 23)
    minutes = random.randint(0, 59)
    return datetime.now() - timedelta(days=days, hours=hours, minutes=minutes)


def _gen_post_time(after: datetime) -> datetime:
    """帖子之后的互动时间（不超过 now）。"""
    now = datetime.now()
    span = (now - after).total_seconds()
    if span <= 60:
        return now - timedelta(seconds=random.randint(5, 55))
    offset = random.randint(1, max(1, int(span)))
    t = after + timedelta(seconds=offset)
    return min(t, now - timedelta(seconds=random.randint(5, 55)))


# =============================================================================
# 用户与成员关系
# =============================================================================
async def seed_bulk_users(session: AsyncSession, schools: list):
    """创建用户：保留现有演示账号（含 admin），程序化补齐至 USERS_PER_SCHOOL/校。

    返回 (users_by_email, users_by_school)
    """
    users_by_email = {}
    users_by_school = {}
    for school, cfg in zip(schools, SCHOOLS_REGISTRY):
        users = []
        # 1. 现有演示用户（含 admin / super_admin）
        for u in cfg["users"]:
            user = User(
                email=u["email"],
                nickname=u["nickname"],
                password_hash=get_password_hash(PASSWORD),
                school_id=school.id,
                role=u["role"],
                bio=u["bio"],
                is_active=True,
                onboarding_completed=True,
            )
            session.add(user)
            users.append(user)
            users_by_email[u["email"]] = user
        # 2. 程序化补齐普通用户至 USERS_PER_SCHOOL
        existing_regular = sum(1 for u in cfg["users"] if u["role"] == "user")
        need = (USERS_PER_SCHOOL - 1) - existing_regular
        for i in range(1, need + 1):
            email = f"{school.code}_s{i}@example.com"
            user = User(
                email=email,
                nickname=_gen_nickname(),
                password_hash=get_password_hash(PASSWORD),
                school_id=school.id,
                role="user",
                bio=_gen_bio(),
                is_active=True,
                onboarding_completed=True,
            )
            session.add(user)
            users.append(user)
            users_by_email[email] = user
        users_by_school[school.code] = users
    await session.flush()
    return users_by_email, users_by_school


async def seed_bulk_memberships(session: AsyncSession, schools: list,
                                users_by_email: dict, users_by_school: dict):
    """为每用户创建主校 active membership；保留跨校成员关系。"""
    now = datetime.now()
    school_by_code = {s.code: s for s in schools}

    # 1. 主校 membership（is_default=True）
    for school, cfg in zip(schools, SCHOOLS_REGISTRY):
        for u in cfg["users"]:
            user = users_by_email[u["email"]]
            role_in_school = "admin" if u["role"] in ("admin", "super_admin") else "member"
            session.add(SchoolMembership(
                user_id=user.id, school_id=school.id,
                role=role_in_school, status="active", is_default=True,
                joined_at=now, created_at=now, updated_at=now,
            ))
        # 程序化用户的主校 membership
        for user in users_by_school[school.code]:
            # 跳过已在演示列表中（上面已建）
            if any(u["email"] == user.email for u in cfg["users"]):
                continue
            session.add(SchoolMembership(
                user_id=user.id, school_id=school.id,
                role="member", status="active", is_default=True,
                joined_at=now, created_at=now, updated_at=now,
            ))

    # 2. 跨校成员关系（TEN-05.3 演示切换）
    for cross in CROSS_SCHOOL_MEMBERSHIPS:
        user = users_by_email.get(cross["user_email"])
        school = school_by_code.get(cross["school_code"])
        if user is None or school is None:
            continue
        session.add(SchoolMembership(
            user_id=user.id, school_id=school.id,
            role=cross["role"], status="active", is_default=cross["is_default"],
            joined_at=now, created_at=now, updated_at=now,
        ))
    await session.flush()


# =============================================================================
# 帖子生成
# =============================================================================
async def seed_bulk_posts_for_school(
    session: AsyncSession, school, categories: list, locations: list,
    user_ids: list[int],
) -> list[Post]:
    """为单校生成 POSTS_PER_SCHOOL 条 published 帖子 + 6 态样本。

    Post 含 Vector(512) 字段，沿用 seed_data 单条 flush 模式规避
    Python 3.14 insertmanyvalues unhashable 兼容性问题。
    """
    category_by_code = {c.code: c for c in categories}
    place_names = [loc.name for loc in locations] or PLACES_EXTRA
    now = datetime.now()
    posts: list[Post] = []

    # 每分类帖数大致均分（share/teamup/trade/lost_found/other）
    codes = list(category_by_code.keys())
    if not codes:
        return posts

    tiers = _assign_tiers(POSTS_PER_SCHOOL)
    for i in range(POSTS_PER_SCHOOL):
        code = codes[i % len(codes)]
        category = category_by_code[code]
        tier = tiers[i]
        # 标题/正文模板
        title_tpl = random.choice(TITLE_TEMPLATES[code])
        body_tpl = random.choice(BODY_TEMPLATES[code])
        title = _fill_template(title_tpl, place_names)
        content = _fill_template(body_tpl, place_names)
        # 失物招领 lost_type
        lost_type = None
        if code == "lost_found":
            lost_type = "lost" if ("丢失" in title or "丢" in title or "求助" in title) else "found"
        created_at = _gen_created_at()
        post = Post(
            user_id=random.choice(user_ids),
            school_id=school.id,
            category_id=category.id,
            location_id=random.choice([loc.id for loc in locations]) if locations and random.random() < 0.8 else None,
            title=title[:200],
            content=content,
            status="published",
            view_count=_gen_view_count(tier),
            like_count=0,           # 互动阶段回填
            comment_count=0,
            valid_count=0,
            invalid_count=0,
            lost_type=lost_type,
            expire_at=created_at + timedelta(days=category.default_validity_days),
            is_recommend=(tier == "hot"),  # top 5% 热门置推荐
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(post)
        await session.flush()   # 单条 flush（Vector 兼容）
        posts.append(post)
        post.tier = tier         # 供互动阶段使用

    # 6 态样本（每态 1-2 条，保证状态机覆盖）
    status_samples = [
        ("draft", "【草稿】{place}探店笔记（整理中，暂未发布）", "正在整理{place}的探店信息，等下次再体验一次后发布。"),
        ("pending", "【待审核】{place}下周活动预告（等待审核）", "下{weekday}{place}有一场活动，信息已提交，审核通过后大家即可看到。"),
        ("expired", "【已过期】{place}上学期优惠活动（已过期）", "这是上学期的优惠活动信息，已过期，仅供参考。"),
        ("conflict", "【冲突】关于{place}的信息（与其他帖子冲突）", "本帖信息与其他帖子存在冲突，已标记待处理。"),
        ("archived", "【已归档】已结束的{place}通知", "该通知对应事项已结束，帖子归档保存。"),
    ]
    for status, title_tpl, body_tpl in status_samples:
        created_at = now - timedelta(days=random.randint(1, 10))
        expire_at = (
            created_at + timedelta(days=1)   # expired 样本：立即过期
            if status == "expired"
            else now + timedelta(days=30)
        )
        post = Post(
            user_id=random.choice(user_ids),
            school_id=school.id,
            category_id=category_by_code["other"].id,
            location_id=random.choice([loc.id for loc in locations]) if locations else None,
            title=_fill_template(title_tpl, place_names)[:200],
            content=_fill_template(body_tpl, place_names),
            status=status,
            view_count=0,
            like_count=0, comment_count=0, valid_count=0, invalid_count=0,
            expire_at=expire_at,
            is_recommend=False,
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(post)
        await session.flush()
        posts.append(post)
        post.tier = "cold"

    return posts


# =============================================================================
# 互动数据：点赞 / 评论 / 协同验证（真实填充明细 + 更新计数）
# =============================================================================
async def seed_interactions_for_school(
    session: AsyncSession, school, posts: list[Post], user_ids: list[int],
    comment_templates: dict,
) -> tuple[int, int, int]:
    """为单校帖子生成点赞/评论/验证，并回填帖子计数。

    返回 (likes_count, comments_count, validations_count)
    """
    now = datetime.now()
    likes_total = 0
    comments_total = 0
    validations_total = 0

    for post in posts:
        if post.status != "published":
            continue  # 非 published 样本不做互动

        author_id = post.user_id
        pool = [uid for uid in user_ids if uid != author_id]
        if not pool:
            continue
        pool_len = len(pool)

        # 浏览 → 点赞 → 评论（真实比例）
        view = post.view_count
        like_target = min(MAX_LIKERS, pool_len, max(1, round(view * random.uniform(*LIKE_RATE))))
        comment_target = min(MAX_COMMENTS, max(1, round(like_target * random.uniform(*COMMENT_RATE))))

        # 1. 点赞明细（无放回，保证 (post_id, user_id) 唯一）
        likers = random.sample(pool, like_target)
        for uid in likers:
            session.add(Like(
                post_id=post.id, user_id=uid,
                created_at=_gen_post_time(post.created_at),
            ))
        post.like_count = len(likers)
        likes_total += len(likers)

        # 2. 评论明细（主题相关模板）
        template_pool = comment_templates[post.category_id]
        comments_created = 0
        for k in range(comment_target):
            user = random.choice(pool)
            template = random.choice(template_pool)
            content = _fill_template(template, [])
            session.add(Comment(
                post_id=post.id, user_id=user,
                parent_id=None,
                content=content,
                like_count=random.randint(0, 5),
                status="published",
                created_at=_gen_post_time(post.created_at),
                updated_at=_gen_post_time(post.created_at),
            ))
            comments_created += 1
        post.comment_count = comments_created
        comments_total += comments_created

        # 3. 协同验证（热门帖为主）
        if post.tier == "hot" and random.random() < 0.7:
            n_validation = random.randint(1, 3)
            v_users = random.sample(pool, min(n_validation, pool_len))
            confirm = 0
            refute = 0
            for uid in v_users:
                v_type = random.choices(
                    ["confirmation", "refutation"],
                    weights=[0.85, 0.15],
                )[0]
                v_comment = random.choice(VALIDATION_TEMPLATES[v_type])
                session.add(ValidationRecord(
                    post_id=post.id, user_id=uid,
                    validation_type=v_type,
                    comment=_fill_template(v_comment, []),
                    created_at=_gen_post_time(post.created_at),
                ))
                if v_type == "confirmation":
                    confirm += 1
                else:
                    refute += 1
            post.valid_count = confirm
            post.invalid_count = refute
            validations_total += confirm + refute

    # 分批 flush（互动表无 Vector 字段，可批量）
    await session.flush()
    return likes_total, comments_total, validations_total


# =============================================================================
# 主流程
# =============================================================================
async def main():
    print("=" * 60)
    print("大数据量演示数据生成：每校 500 帖 + 50 用户")
    print("=" * 60)

    print("\n[1/9] 清空现有数据（保留表结构）...")
    await init_db()
    print("✓ 已清空所有业务表数据并重置自增 ID")

    async with async_session_maker() as session:
        print("\n[2/9] 创建 3 档套餐与权益项...")
        plans = await seed_plans(session)
        print(f"✓ 创建了 {len(plans)} 档套餐")

        print("\n[3/9] 创建三所演示学校...")
        schools = await seed_schools(session)
        for s in schools:
            print(f"  - {s.name} (code={s.code})")
        print(f"✓ 创建了 {len(schools)} 所学校")

        print("\n[4/9] 品牌设置 / 分类 / 地点...")
        await seed_school_settings(session, schools)
        categories_by_school = await seed_categories(session, schools)
        locations_by_school = await seed_locations(session, schools)
        for code in categories_by_school:
            print(f"  - {code}: {len(categories_by_school[code])} 分类, {len(locations_by_school[code])} 地点")
        print("✓ 品牌设置/分类/地点已创建")

        print(f"\n[5/9] 创建用户（每校 {USERS_PER_SCHOOL} 个，含现有演示账号）...")
        users_by_email, users_by_school = await seed_bulk_users(session, schools)
        for code, users in users_by_school.items():
            print(f"  - {code}: {len(users)} 个用户")
        print(f"✓ 共创建 {sum(len(v) for v in users_by_school.values())} 个用户")

        print("\n[6/9] 创建成员关系（主校 + 跨校）...")
        await seed_bulk_memberships(session, schools, users_by_email, users_by_school)
        print(f"✓ 成员关系已创建（含 {len(CROSS_SCHOOL_MEMBERSHIPS)} 条跨校关系）")

        # 套餐订阅（需 admin 用户）
        admin_user = users_by_email.get("admin@momentcampus.com")
        print("\n[7/9] 为三校分配运营档套餐...")
        subs = await seed_subscriptions(session, schools, plans, admin_user)
        print(f"✓ 创建了 {len(subs)} 条 active 订阅")

        # 评论模板按分类 id 组织
        comment_templates_by_cat = {}
        for code, cats in categories_by_school.items():
            for c in cats:
                comment_templates_by_cat[c.id] = COMMENT_TEMPLATES[c.code]

        print(f"\n[8/9] 生成帖子 + 互动（每校 {POSTS_PER_SCHOOL} 条 published + 状态样本）...")
        grand_posts = 0
        grand_likes = 0
        grand_comments = 0
        grand_validations = 0
        for school, cfg in zip(schools, SCHOOLS_REGISTRY):
            cats = categories_by_school.get(school.code, [])
            locs = locations_by_school.get(school.code, [])
            users = users_by_school[school.code]
            user_ids = [u.id for u in users]
            posts = await seed_bulk_posts_for_school(
                session, school, cats, locs, user_ids,
            )
            likes_n, comments_n, validations_n = await seed_interactions_for_school(
                session, school, posts, user_ids, comment_templates_by_cat,
            )
            status_counts = {}
            for p in posts:
                status_counts[p.status] = status_counts.get(p.status, 0) + 1
            published = status_counts.get("published", 0)
            print(f"  - {school.code}: 帖子={len(posts)} (published={published}) "
                  f"点赞记录={likes_n} 评论={comments_n} 验证={validations_n}")
            print(f"    状态分布={status_counts}")
            grand_posts += len(posts)
            grand_likes += likes_n
            grand_comments += comments_n
            grand_validations += validations_n
            await session.commit()   # 每校提交一次，避免长事务
            print(f"    ✓ {school.code} 已提交")

        print(f"\n[9/9] 全部完成。总计：帖子={grand_posts} 点赞={grand_likes} 评论={grand_comments} 验证={grand_validations}")

        print("\n" + "=" * 60)
        print("✅ 大数据量演示数据填充完成！")
        print("=" * 60)
        print("\n【账号清单】（密码统一 pass123）")
        for school, cfg in zip(schools, SCHOOLS_REGISTRY):
            print(f"\n  ▶ {school.name} (code={school.code})")
            for u in cfg["users"]:
                print(f"    {u['email']:40s} | {u['nickname']:15s} | {u['role']:10s}")
            print(f"    另含 {USERS_PER_SCHOOL - len(cfg['users'])} 个程序化用户（{school.code}_s1@{'example.com'} 起）")

        print("\n【Embedding 回填建议】")
        print("  运行：python scripts/generate_embeddings.py --batch-size 50")


if __name__ == "__main__":
    asyncio.run(main())
