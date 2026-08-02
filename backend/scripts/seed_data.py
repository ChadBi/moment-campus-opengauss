"""演示数据填充脚本（三校多租户差异化数据版，TEN-05）

用于开发和测试环境。

注意：本脚本不再创建表结构，需先通过 Alembic 迁移创建表：
    alembic upgrade head
脚本仅清空现有数据并重新填充演示数据。

三所演示学校（TEN-05.1）：
- 江南大学（code=jiangnan）—— 主展示租户，无锡蠡湖校区，30 条真实场景帖 + 状态样本
- 复旦大学（code=fudan）—— 复赛演示校 A，上海邯郸校区
- 浙江大学（code=zju）—— 复赛演示校 B，杭州紫金港校区

每校保证：分类(=5 统一信息分类：share/teamup/trade/lost_found/other) / 地点(≥10) / 用户(≥5 含 admin) / 已发布帖子(≥20) /
状态样本(6 态各 ≥1) / 两类治理样本(confirmation/refutation) /
专题(≥1) / 官方发布主体(≥2) / 品牌设置（差异化主题色） / 套餐（运营档 activated）。

TEN-05.3：user1@/user2@ 加入多校（江南大学 + 复旦/浙大）用于演示切换后角色/内容/统计变化。

坐标约定：数据库与 API 统一使用 GCJ-02；三校点位来源与质量见
``app.data.demo_coordinates``。
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import app.db_compat  # noqa: F401  openGauss 兼容性补丁，必须在 SQLAlchemy 引擎前导入
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_maker, engine
from app.data.demo_coordinates import DEMO_SCHOOL_COORDINATES, location_tuples
from app.models import (
    Base, User, School, Post, Category, PostImage,
    Location, Comment, Like, ValidationRecord, Report, Notification,
    TopicCollection, TopicCollectionPost, Draft, BrowseHistory, SearchHistory,
    AdminOperationLog, SchoolMembership, SchoolSettings, SchoolSubscription,
    ProductPlan, PlanEntitlement,
)
import bcrypt


# =============================================================================
# 通用配置：套餐（全平台共享）
# =============================================================================

# 3 档套餐（COM-01 契约）：试用档 / 标准档 / 运营档
PLANS_DATA = [
    {
        "code": "trial", "name": "试用档", "description": "试用档：20 成员 / 50 帖 / 200MB / AI 20/日",
        "sort_order": 10,
        "entitlements": [
            ("members_max", 20, True), ("posts_max", 50, True),
            ("storage_mb", 200, False), ("ai_calls_daily", 20, True),
        ],
    },
    {
        "code": "standard", "name": "标准档", "description": "标准档：200 成员 / 2000 帖 / 2GB / AI 200/日",
        "sort_order": 20,
        "entitlements": [
            ("members_max", 200, True), ("posts_max", 2000, True),
            ("storage_mb", 2048, False), ("ai_calls_daily", 200, True),
        ],
    },
    {
        "code": "operations", "name": "运营档", "description": "运营档：不限成员/帖数 / 10GB / AI 2000/日",
        "sort_order": 30,
        "entitlements": [
            ("members_max", None, False), ("posts_max", None, False),
            ("storage_mb", 10240, False), ("ai_calls_daily", 2000, True),
        ],
    },
]

# Task 1.2 调整：PostType（信息类型）已删除，统一使用 5 类信息分类
# 5 类分类由 SCHOOLS_REGISTRY 中 *_CATEGORIES 提供


# =============================================================================
# 三校配置：学校元数据 + 分类 + 地点 + 用户 + 帖子 + 专题 + 官方主体
# =============================================================================

# --- 江南大学（主展示，复用既有真实场景数据） -------------------------------
JIANGNAN_META = {
    "name": "江南大学",
    "code": "jiangnan",
    "province": "江苏省",
    "city": "无锡市",
    "address": "江苏省无锡市滨湖区蠡湖大道1800号",
    "center_lat": DEMO_SCHOOL_COORDINATES["jiangnan"]["center_lat"],
    "center_lng": DEMO_SCHOOL_COORDINATES["jiangnan"]["center_lng"],
    "map_zoom": 16,
    "logo_url": None,
    "brand_color": "#1B4332",  # 江南绿
    "site_name": "此刻校园 · 江南大学",
    "description": "江南大学蠡湖校区校园信息协作平台",
}

JIANGNAN_CATEGORIES = [
    ("分享吐槽", "share", "💬", "校园生活分享、吐槽、心得", 30, 1),
    ("组队交友", "teamup", "🤝", "组队、交友、活动搭子", 30, 2),
    ("二手交易", "trade", "💰", "二手物品买卖、赠予", 30, 3),
    ("失物招领", "lost_found", "🔍", "丢失与拾到物品信息", 30, 4),
    ("其他", "other", "📝", "其他校园信息", 30, 5),
]

JIANGNAN_LOCATIONS = location_tuples("jiangnan")

# 江南大学用户清单（1 管理员 + 10 普通用户，昵称/bio 模拟真实学生身份）
JIANGNAN_USERS = [
    {"email": "admin@momentcampus.com", "nickname": "校园运营组", "role": "super_admin",
     "bio": "此刻校园平台运营组，负责内容审核与平台维护"},
    {"email": "user1@example.com", "nickname": "江南小李", "role": "user",
     "bio": "计算机学院大三 | 校园信息搬运工"},
    {"email": "user2@example.com", "nickname": "蠡湖钓客", "role": "user",
     "bio": "喜欢在蠡湖边发呆的钓鱼佬"},
    {"email": "user3@example.com", "nickname": "食堂品鉴师", "role": "user",
     "bio": "吃过江南大学所有食堂 | 美食地图绘制中"},
    {"email": "user4@example.com", "nickname": "图书馆常客", "role": "user",
     "bio": "图书馆三楼是我的第二卧室"},
    {"email": "user5@example.com", "nickname": "跑道冲刺手", "role": "user",
     "bio": "田径队 | 每天夜跑 5 公里"},
    {"email": "user6@example.com", "nickname": "二食堂干饭人", "role": "user",
     "bio": "干饭不积极思想有问题"},
    {"email": "user7@example.com", "nickname": "江大摄影师", "role": "user",
     "bio": "用镜头记录蠡湖的四季 | 摄影社"},
    {"email": "user8@example.com", "nickname": "流浪猫救助站", "role": "user",
     "bio": "校园流浪猫 TNR 志愿者 | 已绝育 12 只"},
    {"email": "user9@example.com", "nickname": "期末突击队", "role": "user",
     "bio": "靠期末两周创造奇迹的大学生"},
    {"email": "user10@example.com", "nickname": "无锡学长", "role": "user",
     "bio": "大四老学长 | 江南生存指南作者"},
]


# --- 复旦大学（复赛演示校 A，上海邯郸校区） -------------------------------
FUDAN_META = {
    "name": "复旦大学",
    "code": "fudan",
    "province": "上海市",
    "city": "上海市",
    "address": "上海市杨浦区邯郸路220号",
    "center_lat": DEMO_SCHOOL_COORDINATES["fudan"]["center_lat"],
    "center_lng": DEMO_SCHOOL_COORDINATES["fudan"]["center_lng"],
    "map_zoom": 16,
    "logo_url": None,
    "brand_color": "#00356B",  # 复旦蓝
    "site_name": "此刻校园 · 复旦大学",
    "description": "复旦大学邯郸校区校园信息协作平台（复赛演示校 A）",
}

FUDAN_CATEGORIES = [
    ("分享吐槽", "share", "💬", "校园生活分享、吐槽、心得", 30, 1),
    ("组队交友", "teamup", "🤝", "组队、交友、活动搭子", 30, 2),
    ("二手交易", "trade", "💰", "二手物品买卖、赠予", 30, 3),
    ("失物招领", "lost_found", "🔍", "丢失与拾到物品信息", 30, 4),
    ("其他", "other", "📝", "其他校园信息", 30, 5),
]

FUDAN_LOCATIONS = location_tuples("fudan")

FUDAN_USERS = [
    {"email": "fudan_admin@momentcampus.com", "nickname": "复旦运营组", "role": "admin",
     "bio": "复旦此刻校园运营组"},
    {"email": "fudan_user1@example.com", "nickname": "邯郸路书虫", "role": "user",
     "bio": "复旦文科院系 | 喜欢泡文科图书馆"},
    {"email": "fudan_user2@example.com", "nickname": "光华楼守夜人", "role": "user",
     "bio": "光华楼自习室常客 | 期末突击选手"},
    {"email": "fudan_user3@example.com", "nickname": "南区干饭人", "role": "user",
     "bio": "南区食堂品鉴员"},
    {"email": "fudan_user4@example.com", "nickname": "相辉堂常客", "role": "user",
     "bio": "校园话剧爱好者 | 学生艺术团"},
    {"email": "fudan_user5@example.com", "nickname": "本部跑者", "role": "user",
     "bio": "本部体育场夜跑爱好者"},
]


# --- 浙江大学（复赛演示校 B，杭州紫金港校区） -------------------------------
ZJU_META = {
    "name": "浙江大学",
    "code": "zju",
    "province": "浙江省",
    "city": "杭州市",
    "address": "浙江省杭州市西湖区余杭塘路866号",
    "center_lat": DEMO_SCHOOL_COORDINATES["zju"]["center_lat"],
    "center_lng": DEMO_SCHOOL_COORDINATES["zju"]["center_lng"],
    "map_zoom": 16,
    "logo_url": None,
    "brand_color": "#003F7F",  # 浙大蓝
    "site_name": "此刻校园 · 浙江大学",
    "description": "浙江大学紫金港校区校园信息协作平台（复赛演示校 B）",
}

ZJU_CATEGORIES = [
    ("分享吐槽", "share", "💬", "校园生活分享、吐槽、心得", 30, 1),
    ("组队交友", "teamup", "🤝", "组队、交友、活动搭子", 30, 2),
    ("二手交易", "trade", "💰", "二手物品买卖、赠予", 30, 3),
    ("失物招领", "lost_found", "🔍", "丢失与拾到物品信息", 30, 4),
    ("其他", "other", "📝", "其他校园信息", 30, 5),
]

ZJU_LOCATIONS = location_tuples("zju")

ZJU_USERS = [
    {"email": "zju_admin@momentcampus.com", "nickname": "浙大运营组", "role": "admin",
     "bio": "浙大此刻校园运营组"},
    {"email": "zju_user1@example.com", "nickname": "紫金港学子", "role": "user",
     "bio": "浙大计算机学院 | 紫金港常住居民"},
    {"email": "zju_user2@example.com", "nickname": "启真湖观察者", "role": "user",
     "bio": "启真湖生态观察 | 校园鸟类记录"},
    {"email": "zju_user3@example.com", "nickname": "西区干饭人", "role": "user",
     "bio": "西区食堂常客 | 性价比美食挖掘"},
    {"email": "zju_user4@example.com", "nickname": "图书馆守门人", "role": "user",
     "bio": "图书馆是我的第二个家"},
    {"email": "zju_user5@example.com", "nickname": "紫金港跑者", "role": "user",
     "bio": "紫金港夜跑团成员"},
]


# =============================================================================
# 江南大学真实场景帖子（30 条，全部 published，复用既有内容）
# 字段：title / content / category_code / location_name / user_email
#       is_anonymous / views / likes / is_recommend / comments / validations
# =============================================================================

JIANGNAN_POSTS = [
    # ==================== 校园美食 (food) ====================
    {
        "title": "二食堂三楼麻辣香锅真的绝了",
        "content": (
            "作为干饭人，今天又来二食堂三楼打卡了。麻辣香锅15块钱一份，荤素自选，加米饭免费。"
            "老板给的料足，麻度可选，我选的中辣刚刚好。\n\n"
            "推荐组合：午餐肉 + 土豆片 + 宽粉 + 豆皮 + 鸡肉串，浇上蒜蓉香油，拌饭绝绝子。"
            "旁边冰柜有冰镇豆奶2块钱一瓶，搭配解辣。\n\n"
            "唯一缺点是中午11:45-12:30排队要15分钟，建议错峰。"
        ),
        "category_code": "share",  # Task 1.2 调整：原 food → share
        "location_name": "第二食堂", "user_email": "user6@example.com",
        "is_anonymous": False, "views": 342, "likes": 28, "is_recommend": True,
        "comments": [
            {"user_email": "user3@example.com", "content": "昨天刚去吃过，确实不错！午餐肉给得超大方", "likes": 5},
            {"user_email": "user9@example.com", "content": "请问辣度选微辣会踩雷吗？不吃辣星人瑟瑟发抖", "likes": 1},
            {"user_email": "user6@example.com", "content": "回复楼上：微辣基本不辣，就是有点麻，可以尝试", "likes": 2},
        ],
        "validations": [
            {"user_email": "user3@example.com", "type": "confirmation", "comment": "今天去验证了，确实好吃"},
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "上个月吃过，依然在线"},
            {"user_email": "user9@example.com", "type": "confirmation", "comment": "亲测有效"},
        ],
    },
    {
        "title": "一食堂早餐油条变好吃了？",
        "content": (
            "今天早上去一食堂吃早餐，发现油条居然变好吃了！以前又硬又油，今天外酥里嫩，"
            "还能闻到面粉香。问了阿姨说是换了供应商。\n\n"
            "推荐搭配：油条1.5元 + 豆浆1元 = 2.5元搞定一顿早餐。"
            "早八党可以提前10分钟来排队，7:30之前基本不用等。\n\n"
            "另外他们家的茶叶蛋也不错，1.5元一个，蛋黄很糯。"
        ),
        "category_code": "share",  # Task 1.2 调整：原 food → share
        "location_name": "第一食堂", "user_email": "user3@example.com",
        "is_anonymous": False, "views": 198, "likes": 15, "is_recommend": False,
        "comments": [
            {"user_email": "user6@example.com", "content": "我也发现了！茶叶蛋确实好吃", "likes": 3},
            {"user_email": "user9@example.com", "content": "豆浆可以单独买吗？", "likes": 0},
        ],
        "validations": [
            {"user_email": "user6@example.com", "type": "confirmation", "comment": "今早验证，确实改善了"},
        ],
    },
    {
        "title": "蠡湖周边10块钱吃饱的5家店",
        "content": (
            "作为资深干饭人，盘点一下蠡湖周边10块以内能吃饱的店：\n\n"
            "1. 北门兰州拉面 - 小碗8块，量大，加辣更香\n"
            "2. 南门沙县小吃 - 拌面5块+蒸饺4块=9块搞定\n"
            "3. 校园超市煎饼果子 - 6块加蛋加肠，早餐之王\n"
            "4. 二食堂包子铺 - 4个肉包5块，下午茶必备\n"
            "5. 教学楼A区便利店 - 三明治6块+牛奶2块\n\n"
            "性价比党可以参考，欢迎补充。"
        ),
        "category_code": "share",  # Task 1.2 调整：原 food → share
        "location_name": "北门", "user_email": "user3@example.com",
        "is_anonymous": False, "views": 521, "likes": 42, "is_recommend": True,
        "comments": [
            {"user_email": "user9@example.com", "content": "沙县拌面真的便宜量大，强推", "likes": 6},
            {"user_email": "user6@example.com", "content": "补充一个：南门黄焖鸡米饭小份12块也还行", "likes": 4},
            {"user_email": "user1@example.com", "content": "兰州拉面老板人超好，会多给汤", "likes": 2},
        ],
        "validations": [
            {"user_email": "user6@example.com", "type": "confirmation", "comment": "5家都吃过，确实便宜"},
            {"user_email": "user9@example.com", "type": "confirmation", "comment": "沙县拌面验证有效"},
        ],
    },
    {
        "title": "第二食堂新出的螺蛳粉测评",
        "content": (
            "听说二食堂新出螺蛳粉，今天特地去试了一下。15块一份，分量中等。\n\n"
            "汤底味道还算正宗，酸笋给得足，腐竹是脆的，但花生放少了。"
            "酸辣度可以自选，我选的标准酸辣，刚好不冲。\n\n"
            "最大问题是味道真的会熏到旁边的人，建议打包回宿舍吃。"
            "综合评分：7/10，性价比可以，社交场景慎选。"
        ),
        "category_code": "share",  # Task 1.2 调整：原 food → share
        "location_name": "第二食堂", "user_email": "user6@example.com",
        "is_anonymous": False, "views": 287, "likes": 19, "is_recommend": False,
        "comments": [
            {"user_email": "user3@example.com", "content": "在食堂吃螺蛳粉会被室友追杀吧哈哈哈", "likes": 8},
            {"user_email": "user9@example.com", "content": "打包回宿舍也会被宿管阿姨追杀", "likes": 5},
        ],
        "validations": [
            {"user_email": "user9@example.com", "type": "refutation", "comment": "今天去没看到螺蛳粉，可能下架了？"},
        ],
    },

    # ==================== 校园动物 (animal) ====================
    {
        "title": "图书馆门口的橘猫又来蹭饭了",
        "content": (
            "今天去图书馆自习，门口又看到那只大橘猫了。看到人就蹭，胖得像个球。"
            "阿姨说它叫\"学士\"，已经养了三年了，体重12斤。\n\n"
            "提醒大家：\n"
            "1. 不要喂人吃的食物（尤其巧克力、洋葱有毒）\n"
            "2. 要喂专门的猫粮，门口小卖部有售5元/包\n"
            "3. 已绝育+定期驱虫，不用太担心卫生\n"
            "4. 摸完记得洗手\n\n"
            "学士的照片评论区见~"
        ),
        "category_code": "share",  # Task 1.2 调整：原 animal → share
        "location_name": "图书馆", "user_email": "user8@example.com",
        "is_anonymous": False, "views": 612, "likes": 56, "is_recommend": True,
        "comments": [
            {"user_email": "user4@example.com", "content": "学士今天在我书包上睡着了哈哈", "likes": 12},
            {"user_email": "user7@example.com", "content": "上周给它拍了组照片，已发朋友圈", "likes": 8},
            {"user_email": "user1@example.com", "content": "请问门口小卖部的猫粮是什么牌子？想自己买", "likes": 1},
        ],
        "validations": [
            {"user_email": "user4@example.com", "type": "confirmation", "comment": "今天去图书馆还看到了"},
            {"user_email": "user7@example.com", "type": "confirmation", "comment": "照片可以作证"},
        ],
    },
    {
        "title": "蠡湖边上的黑天鹅孵化幼崽了",
        "content": (
            "今早跑步经过蠡湖边，发现黑天鹅夫妇带着三只小天鹅在游！"
            "毛茸茸的灰色小球，超级可爱。\n\n"
            "提醒大家：\n"
            "- 远观就好，不要靠近惊扰\n"
            "- 天鹅护崽会有攻击性，保持5米以上距离\n"
            "- 不要投喂面包等人类食物\n"
            "- 拍照请用长焦，不要用闪光灯\n\n"
            "小天鹅大概一个月后会长出成鸟羽毛，喜欢的同学抓紧去看。"
        ),
        "category_code": "share",  # Task 1.2 调整：原 animal → share
        "location_name": "蠡湖畔", "user_email": "user7@example.com",
        "is_anonymous": False, "views": 478, "likes": 38, "is_recommend": True,
        "comments": [
            {"user_email": "user2@example.com", "content": "周末钓鱼时看到了，确实萌", "likes": 4},
            {"user_email": "user5@example.com", "content": "夜跑看到有人想靠近被天鹅追着咬哈哈哈", "likes": 15},
        ],
        "validations": [
            {"user_email": "user2@example.com", "type": "confirmation", "comment": "亲眼所见"},
        ],
    },
    {
        "title": "教学楼A区出现的小奶猫求领养",
        "content": (
            "今天在教学楼A区一楼走廊发现一只小奶猫，大概2个月大，黑白花，"
            "亲人不躲人。我宿舍不能养，希望有爱猫的同学能领养。\n\n"
            "已带去宠物医院检查过：\n"
            "- 健康无疾病\n"
            "- 已做体外驱虫\n"
            "- 公猫，未绝育（建议6月龄后绝育）\n\n"
            "领养要求：\n"
            "- 在校学生，宿舍允许养或校外租房\n"
            "- 签领养协议\n"
            "- 定期回访\n\n"
            "联系方式：评论区留言或私信。"
        ),
        "category_code": "share",  # Task 1.2 调整：原 animal → share
        "location_name": "教学楼A区", "user_email": "user8@example.com",
        "is_anonymous": False, "views": 234, "likes": 21, "is_recommend": False,
        "comments": [
            {"user_email": "user1@example.com", "content": "已私信！想领养", "likes": 2},
            {"user_email": "user7@example.com", "content": "校友群转发了，希望能找到好人家", "likes": 3},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "私信后确认领养了，谢谢"},
        ],
    },

    # ==================== 打印服务 (print) ====================
    {
        "title": "校园超市旁打印店价格便宜一半",
        "content": (
            "发现一个便宜打印的好地方。校园超市旁边那家打印店：\n\n"
            "- 黑白A4：0.2元/张（图书馆0.4元）\n"
            "- 彩色A4：1元/张\n"
            "- 双面打印免费\n"
            "- 胶装：5元/本\n\n"
            "老板说学生价，可以办会员卡充值100送20。论文打印必备。"
            "营业时间：8:00-21:00，周末也开。"
        ),
        "category_code": "other",  # Task 1.2 调整：原 print → other
        "location_name": "校园超市", "user_email": "user9@example.com",
        "is_anonymous": False, "views": 189, "likes": 14, "is_recommend": False,
        "comments": [
            {"user_email": "user4@example.com", "content": "会员卡充值活动持续到什么时候？", "likes": 1},
            {"user_email": "user10@example.com", "content": "胶装质量怎么样？毕业论文要打印", "likes": 0},
        ],
        "validations": [
            {"user_email": "user10@example.com", "type": "confirmation", "comment": "上周去打印了论文，质量不错"},
        ],
    },
    {
        "title": "图书馆自助打印机使用指南",
        "content": (
            "很多新生不会用图书馆自助打印机，写个简单教程：\n\n"
            "1. 二楼服务台刷卡买打印卡（10元起充）\n"
            "2. 在打印电脑上上传文件（支持PDF/Word/图片）\n"
            "3. 选择打印机（黑白/彩色）\n"
            "4. 输入打印卡密码，刷卡扣费取件\n\n"
            "注意事项：\n"
            "- 单次最多打印50页\n"
            "- 彩色需排队，建议错峰使用\n"
            "- 营业时间：8:00-22:00\n"
            "- 打印卡可在北门自助机退卡"
        ),
        "category_code": "other",  # Task 1.2 调整：原 print → other
        "location_name": "图书馆", "user_email": "user10@example.com",
        "is_anonymous": False, "views": 256, "likes": 22, "is_recommend": False,
        "comments": [
            {"user_email": "user1@example.com", "content": "新生感谢学长！已收藏", "likes": 4},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "按教程操作成功"},
            {"user_email": "user9@example.com", "type": "confirmation", "comment": "今天用过，流程准确"},
        ],
    },

    # ==================== 校园活动 (event) ====================
    {
        "title": "文浩科学馆周五晚话剧《雷雨》演出",
        "content": (
            "本周五晚7点，文浩科学馆有江南话剧社演的《雷雨》，免费入场。\n\n"
            "听说排练了半年，舞美和灯光都是同学自己做的，"
            "演员是大三大四的学长学姐，演技在线。\n\n"
            "建议提前30分钟到场，前排位置先到先得。"
            "喜欢话剧的同学不要错过，结束后还有导演见面会。"
        ),
        "category_code": "teamup",  # Task 1.2 调整：原 event → teamup
        "location_name": "文浩科学馆", "user_email": "user1@example.com",
        "is_anonymous": False, "views": 423, "likes": 35, "is_recommend": True,
        "comments": [
            {"user_email": "user3@example.com", "content": "必须去！《雷雨》是经典", "likes": 5},
            {"user_email": "user9@example.com", "content": "周五晚上正好没课，冲", "likes": 2},
        ],
        "validations": [
            {"user_email": "user3@example.com", "type": "confirmation", "comment": "看完了，演技炸裂"},
        ],
    },
    {
        "title": "大学生活动中心街舞社招新中",
        "content": (
            "街舞社开始招新啦！\n\n"
            "时间：本周一到周五中午11:30-13:30\n"
            "地点：大学生活动中心一楼报名点\n\n"
            "零基础也能加入，有专门新人班。会费50元/学期，包含每周2次课程（每次2小时）。\n"
            "舞种：Hip-hop / Jazz / Breaking / Locking 任选。\n\n"
            "学姐说加入街舞社是她大学最不后悔的事，能交到一辈子的朋友。"
        ),
        "category_code": "teamup",  # Task 1.2 调整：原 event → teamup
        "location_name": "大学生活动中心", "user_email": "user1@example.com",
        "is_anonymous": False, "views": 312, "likes": 27, "is_recommend": True,
        "comments": [
            {"user_email": "user9@example.com", "content": "零基础真的能进吗？四肢不协调", "likes": 6},
            {"user_email": "user1@example.com", "content": "回复楼上：完全可以，新人班从零开始教", "likes": 3},
        ],
        "validations": [],
    },
    {
        "title": "计算机学院ACM集训队招新",
        "content": (
            "计算机学院ACM集训队招新啦！面向全校招收对算法感兴趣的同学。\n\n"
            "要求：\n"
            "- 熟悉C++/Java/Python任一语言\n"
            "- 有一定数据结构基础\n"
            "- 每周能投入10小时以上训练\n\n"
            "福利：\n"
            "- 免费参加省赛、国赛\n"
            "- 有机会拿奖金（国赛金牌5000元）\n"
            "- 保研加分（国赛奖项）\n"
            "- 集训队专用自习室\n\n"
            "简历发送到 acm@jiangnan.edu.cn，截止本周日。"
        ),
        "category_code": "teamup",  # Task 1.2 调整：原 event → teamup
        "location_name": "教学楼A区", "user_email": "user10@example.com",
        "is_anonymous": False, "views": 389, "likes": 31, "is_recommend": True,
        "comments": [
            {"user_email": "user1@example.com", "content": "已投简历！希望能进", "likes": 4},
            {"user_email": "user9@example.com", "content": "10小时/周会不会影响绩点？", "likes": 2},
            {"user_email": "user10@example.com", "content": "回复楼上：时间管理好的话不影响，队里绩点都很高", "likes": 5},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "已加入，每周训练很硬核"},
        ],
    },
    {
        "title": "江南大讲堂：人工智能的前沿与未来",
        "content": (
            "本周三下午2点，文浩科学馆报告厅，江南大讲堂邀请到清华姚班教授讲座。\n"
            "主题：《大模型时代的AI前沿》\n\n"
            "内容涵盖：\n"
            "- Transformer架构的最新演进\n"
            "- 大模型训练的工程挑战\n"
            "- AGI的实现路径之争\n"
            "- 学生如何进入AI研究领域\n\n"
            "免费入场，需提前在教务系统预约（限额300人）。"
            "建议带笔记本，可以提问环节互动。"
        ),
        "category_code": "teamup",  # Task 1.2 调整：原 event → teamup
        "location_name": "文浩科学馆", "user_email": "user4@example.com",
        "is_anonymous": False, "views": 567, "likes": 48, "is_recommend": True,
        "comments": [
            {"user_email": "user1@example.com", "content": "已经预约了！冲", "likes": 3},
            {"user_email": "user10@example.com", "content": "学长提醒：提前1小时去抢前排", "likes": 7},
        ],
        "validations": [],
    },

    # ==================== 学习资源 (study) ====================
    {
        "title": "期末复习必备：图书馆开放时间",
        "content": (
            "临近期末，整理一下图书馆开放时间：\n\n"
            "- 周一到周五：7:00-22:30\n"
            "- 周末：8:00-22:00\n"
            "- 考试周延长到23:00\n"
            "- 三楼自习室24小时开放（需提前预约）\n\n"
            "建议早7点前去占位置，9点后基本满座。"
            "考试周期间1楼大厅也会开放临时座位，约200个。"
        ),
        "category_code": "teamup",  # Task 1.2 调整：原 study → teamup
        "location_name": "图书馆", "user_email": "user4@example.com",
        "is_anonymous": False, "views": 678, "likes": 52, "is_recommend": False,
        "comments": [
            {"user_email": "user9@example.com", "content": "考试周必须早6:30去排队", "likes": 8},
            {"user_email": "user1@example.com", "content": "三楼24h自习室预约链接有吗？", "likes": 2},
            {"user_email": "user4@example.com", "content": "回复楼上：图书馆公众号-座位预约", "likes": 3},
        ],
        "validations": [
            {"user_email": "user9@example.com", "type": "confirmation", "comment": "考试周亲测确实延长到23:00"},
        ],
    },
    {
        "title": "三楼自习室占座规则更新",
        "content": (
            "图书馆三楼自习室新规：\n\n"
            "1. 座位预约系统：每日20:00开放次日预约\n"
            "2. 签到：到馆后30分钟内扫码签到，否则释放\n"
            "3. 暂离：可点\"暂离\"30分钟，超时释放\n"
            "4. 信用分：3次违约扣10分，60分以下禁预约1周\n\n"
            "建议大家文明用座，不要用书包占位不签到。"
            "阿姨会定时巡视，违规直接拉黑一周。"
        ),
        "category_code": "teamup",  # Task 1.2 调整：原 study → teamup
        "location_name": "图书馆", "user_email": "user4@example.com",
        "is_anonymous": False, "views": 312, "likes": 18, "is_recommend": False,
        "comments": [
            {"user_email": "user1@example.com", "content": "新规好评！以前书包占位太烦人", "likes": 12},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "新规已生效"},
        ],
    },
    {
        "title": "计算机组成原理复习资料分享",
        "content": (
            "整理了计算机组成原理期末复习资料，包含：\n\n"
            "- 各章节重点笔记（手写版PDF，30页）\n"
            "- 5年真题+答案解析\n"
            "- 常见计算题套路总结\n"
            "- 易错点汇总\n\n"
            "网盘链接：见评论区（提取码8888）。\n\n"
            "希望对学弟学妹有帮助。考完来还愿。"
        ),
        "category_code": "teamup",  # Task 1.2 调整：原 study → teamup
        "location_name": "教学楼A区", "user_email": "user10@example.com",
        "is_anonymous": False, "views": 891, "likes": 87, "is_recommend": True,
        "comments": [
            {"user_email": "user1@example.com", "content": "学长牛逼！已下载", "likes": 5},
            {"user_email": "user9@example.com", "content": "救命数据结构渣渣，谢谢学长", "likes": 3},
            {"user_email": "user4@example.com", "content": "请问有操作系统版本吗？", "likes": 1},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "资料很全，感谢学长"},
            {"user_email": "user9@example.com", "type": "confirmation", "comment": "真题有用"},
        ],
    },

    # ==================== 生活服务 (service) ====================
    {
        "title": "快递服务中心取件高峰时段",
        "content": (
            "快递中心高峰时段提醒：\n\n"
            "- 工作日 11:30-13:30 / 17:30-19:00（饭点人多）\n"
            "- 周末全天人多\n"
            "- 双11/618 等大促后一周会爆仓\n\n"
            "建议错峰取件，最佳时段：\n"
            "- 工作日 9:00-11:00 / 14:00-16:00\n"
            "- 周末早 8:00-9:30\n\n"
            "另外：大件物品需凭学生证+身份证取，不要忘带。"
            "代取需双方身份证复印件+委托书。"
        ),
        "category_code": "other",  # Task 1.2 调整：原 service → other
        "location_name": "快递服务中心", "user_email": "user1@example.com",
        "is_anonymous": False, "views": 423, "likes": 25, "is_recommend": False,
        "comments": [
            {"user_email": "user6@example.com", "content": "上周五饭点排队40分钟，血泪教训", "likes": 8},
            {"user_email": "user9@example.com", "content": "代取委托书模板有吗？", "likes": 1},
        ],
        "validations": [
            {"user_email": "user6@example.com", "type": "confirmation", "comment": "高峰期确实人爆满"},
        ],
    },
    {
        "title": "学士公寓洗衣机维修通知",
        "content": (
            "住在学士公寓的同学注意了。\n\n"
            "3号楼2层洗衣机坏了一台（共4台，现可用3台），已报修，预计本周五修好。"
            "期间请使用其他楼层洗衣机（1层/3层各4台）。\n\n"
            "另外阿姨说最近有人把鞋子扔洗衣机洗，禁止！违规会拉黑校园卡1周。"
            "洗鞋请用专用洗鞋机（一楼有2台）或者手刷。"
        ),
        "category_code": "other",  # Task 1.2 调整：原 service → other
        "location_name": "学士公寓", "user_email": "user1@example.com",
        "is_anonymous": False, "views": 234, "likes": 12, "is_recommend": False,
        "comments": [
            {"user_email": "user6@example.com", "content": "在洗衣机洗鞋的人是什么心态", "likes": 15},
            {"user_email": "user9@example.com", "content": "1楼洗鞋机也经常坏", "likes": 2},
        ],
        "validations": [
            {"user_email": "user6@example.com", "type": "refutation", "comment": "今天看修好了，可以删帖了？"},
        ],
    },
    {
        "title": "校园超市本周打折商品",
        "content": (
            "校园超市本周打折：\n\n"
            "- 雀巢咖啡 7折（原价15元/瓶 → 10.5元）\n"
            "- 方便面买二送一（康师傅/统一）\n"
            "- 牙膏牙刷 8折\n"
            "- 笔记本 5折（A5/B5各型号）\n"
            "- 卫生纸 6折（卷纸/抽纸）\n\n"
            "昨天刚补货，建议早去。日用品囤货党可以行动了。"
            "活动截止周日22:00。"
        ),
        "category_code": "other",  # Task 1.2 调整：原 service → other
        "location_name": "校园超市", "user_email": "user9@example.com",
        "is_anonymous": False, "views": 367, "likes": 31, "is_recommend": False,
        "comments": [
            {"user_email": "user1@example.com", "content": "咖啡7折冲了，囤了5瓶", "likes": 4},
            {"user_email": "user6@example.com", "content": "方便面买二送一等于66折，香", "likes": 3},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "昨天验证，咖啡确实7折"},
        ],
    },

    # ==================== 校园交通 (transport) ====================
    {
        "title": "北门到地铁口的共享单车攻略",
        "content": (
            "北门到地铁2号线江南大学站，走路要15分钟。推荐共享单车：\n\n"
            "停车点：\n"
            "- 北门右侧有美团/哈啰停车点\n"
            "- 地铁口A1出口旁也有停车区\n\n"
            "高峰：\n"
            "- 早高峰7:30-8:30车多但人多\n"
            "- 工作日9点后基本有车\n"
            "- 周末车少，建议提前预约\n\n"
            "价格：\n"
            "- 单程1.5元\n"
            "- 月卡15元无限次（美团/哈啰通用）\n"
            "- 季卡35元更划算"
        ),
        "category_code": "other",  # Task 1.2 调整：原 transport → other
        "location_name": "北门", "user_email": "user5@example.com",
        "is_anonymous": False, "views": 289, "likes": 19, "is_recommend": False,
        "comments": [
            {"user_email": "user1@example.com", "content": "季卡35元？我去办一张", "likes": 2},
            {"user_email": "user9@example.com", "content": "周末经常找不到车，要提前10分钟预约", "likes": 1},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "已办季卡，价格准确"},
        ],
    },
    {
        "title": "校车冬季时刻表更新",
        "content": (
            "校车冬季时刻表（11月-3月）：\n\n"
            "- 北门 ↔ 南门：6:30-22:00 每15分钟\n"
            "- 校内环线：7:00-21:00 每20分钟\n"
            "- 体育馆专线：17:30-21:00 每30分钟（仅工作日）\n\n"
            "费用：校园卡1元/次，现金2元。\n"
            "冬季首发延后30分钟，末班不变。\n\n"
            "实时位置可在\"i江大\"App查看。"
        ),
        "category_code": "other",  # Task 1.2 调整：原 transport → other
        "location_name": "北门", "user_email": "user10@example.com",
        "is_anonymous": False, "views": 312, "likes": 16, "is_recommend": False,
        "comments": [
            {"user_email": "user1@example.com", "content": "i江大App的实时位置经常不准", "likes": 3},
            {"user_email": "user6@example.com", "content": "校内环线周六怎么不到南门？", "likes": 1},
        ],
        "validations": [],
    },

    # ==================== 校园设施 (facility) ====================
    {
        "title": "体育馆游泳馆开放时间",
        "content": (
            "体育馆游泳馆本学期开放时间：\n\n"
            "- 周一到周五 16:00-21:00\n"
            "- 周末 9:00-21:00\n\n"
            "价格：\n"
            "- 单次15元\n"
            "- 月卡120元\n"
            "- 学期卡300元（最划算）\n\n"
            "注意：\n"
            "- 需自带泳衣泳帽\n"
            "- 水深1.2-1.8米\n"
            "- 每月最后一个周三闭馆维护\n"
            "- 学生证必备"
        ),
        "category_code": "other",  # Task 1.2 调整：原 facility → other
        "location_name": "体育馆", "user_email": "user5@example.com",
        "is_anonymous": False, "views": 256, "likes": 14, "is_recommend": False,
        "comments": [
            {"user_email": "user9@example.com", "content": "学期卡300超值，已办", "likes": 3},
            {"user_email": "user1@example.com", "content": "不会游泳可以去学吗？有教练吗？", "likes": 1},
        ],
        "validations": [
            {"user_email": "user9@example.com", "type": "confirmation", "comment": "学期卡已办，价格准确"},
        ],
    },
    {
        "title": "田径场夜跑照明维修通知",
        "content": (
            "田径场照明昨晚坏了一侧（东侧4盏灯），已经报修。"
            "维修师傅说今天下午会修好。\n\n"
            "今晚夜跑的同学注意安全：\n"
            "- 建议白天去（9:00-17:00）\n"
            "- 或者临时去体育馆室内跑道\n"
            "- 必须夜跑的话选西侧跑道，照明正常\n\n"
            "后续如果有照明问题可以打后勤电话6666报修。"
        ),
        "category_code": "other",  # Task 1.2 调整：原 facility → other
        "location_name": "田径场", "user_email": "user5@example.com",
        "is_anonymous": False, "views": 178, "likes": 8, "is_recommend": False,
        "comments": [
            {"user_email": "user1@example.com", "content": "感谢提醒，今晚改去体育馆", "likes": 2},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "refutation", "comment": "今天下午已经修好了，灯都亮着"},
        ],
    },

    # ==================== 活动场地 (venue) ====================
    {
        "title": "大学生活动中心预约流程",
        "content": (
            "很多社团不知道怎么预约活动场地，写个流程：\n\n"
            "1. 校园网登录\"学生活动管理系统\"\n"
            "2. 提交活动方案（含时间、人数、设备需求）\n"
            "3. 社团指导老师审核\n"
            "4. 团委审批（3个工作日内）\n"
            "5. 通过后扫码入场\n\n"
            "建议提前2周申请，热门时段（周末晚上）竞争激烈。"
            "设备需求要写清楚（投影/音响/话筒/灯光），临时加需扣分。"
        ),
        "category_code": "other",  # Task 1.2 调整：原 venue → other
        "location_name": "大学生活动中心", "user_email": "user1@example.com",
        "is_anonymous": False, "views": 234, "likes": 11, "is_recommend": False,
        "comments": [
            {"user_email": "user9@example.com", "content": "请问社团外可以预约吗？班级活动", "likes": 1},
            {"user_email": "user1@example.com", "content": "回复楼上：可以的，走班级活动审批", "likes": 2},
        ],
        "validations": [],
    },
    {
        "title": "文浩科学馆会议室使用规则",
        "content": (
            "文浩科学馆会议室开放预约：\n\n"
            "- 容量：10/20/30/50人 4个会议室\n"
            "- 时段：8:00-22:00\n"
            "- 费用：学生组织免费，个人5元/小时\n"
            "- 设备：投影、白板、空调、音响\n\n"
            "注意事项：\n"
            "- 食物饮料禁止入内\n"
            "- 使用后需打扫\n"
            "- 违规记录会影响后续预约\n"
            "- 临时取消需提前4小时"
        ),
        "category_code": "other",  # Task 1.2 调整：原 venue → other
        "location_name": "文浩科学馆", "user_email": "user10@example.com",
        "is_anonymous": False, "views": 167, "likes": 9, "is_recommend": False,
        "comments": [],
        "validations": [],
    },

    # ==================== 失物招领 (lost_found) ====================
    {
        "title": "一食堂丢失黑色钱包",
        "content": (
            "今天中午（11月15日）在一食堂二楼丢失一个黑色钱包，"
            "内有身份证（王某某）、校园卡、银行卡3张、现金200元左右。\n\n"
            "钱包特征：\n"
            "- 品牌：稻草人\n"
            "- 颜色：黑色\n"
            "- 边角有轻微磨损\n\n"
            "拾到者请联系 187xxxx1234，必有重谢。"
            "也可以交到一食堂服务台，已和阿姨说过帮忙留意。"
        ),
        "category_code": "lost_found", "location_name": "第一食堂", "user_email": "user1@example.com",
        "is_anonymous": False, "views": 312, "likes": 5, "is_recommend": False,
        "comments": [
            {"user_email": "user6@example.com", "content": "中午在二楼吃饭没看到，帮你留意", "likes": 2},
            {"user_email": "user9@example.com", "content": "建议挂失身份证和银行卡！", "likes": 8},
        ],
        "validations": [
            {"user_email": "user6@example.com", "type": "confirmation", "comment": "今天中午确实有人在二楼找东西"},
        ],
    },
    {
        "title": "图书馆三楼捡到U盘",
        "content": (
            "昨晚（11月14日）在图书馆三楼靠窗位置（编号305）捡到一个银色U盘，"
            "金士顿32G，里面有大量学习资料但没有标识。\n\n"
            "已交到图书馆二楼服务台，失主可凭：\n"
            "- U盘外观描述\n"
            "- 文件夹/文件名描述\n\n"
            "认领。提醒大家重要资料记得备份+在U盘里放一个 contact.txt 留联系方式。"
        ),
        "category_code": "lost_found", "location_name": "图书馆", "user_email": "user4@example.com",
        "is_anonymous": False, "views": 145, "likes": 7, "is_recommend": False,
        "comments": [
            {"user_email": "user1@example.com", "content": "感谢同学！U盘放contact.txt这个建议很好", "likes": 3},
        ],
        "validations": [],
    },

    # ==================== 校园兼职 (job) ====================
    {
        "title": "北门外奶茶店招兼职",
        "content": (
            "北门外\"茶颜悦色\"招兼职：\n\n"
            "- 时薪18元\n"
            " 时段：周末全天 / 工作日晚班（17:00-22:00）\n"
            "- 要求：在校大学生，能坚持3个月以上\n"
            "- 福利：员工折扣+免费饮品+节日福利\n\n"
            "带简历直接到店面问，地址北门左转50米。"
            "说是江南同学推荐可以优先面试。"
        ),
        "category_code": "other",  # Task 1.2 调整：原 job → other
        "location_name": "北门", "user_email": "user9@example.com",
        "is_anonymous": False, "views": 423, "likes": 18, "is_recommend": False,
        "comments": [
            {"user_email": "user6@example.com", "content": "18元/时算高的吗？奶茶店普遍15左右", "likes": 4},
            {"user_email": "user9@example.com", "content": "回复楼上：茶颜是连锁，待遇比奶茶店好", "likes": 2},
        ],
        "validations": [],
    },
    {
        "title": "接高数家教",
        "content": (
            "接高数家教：\n\n"
            "- 对象：大一/大二在校生\n"
            "- 内容：高等数学上下册（同济版）\n"
            "- 形式：1对1，1.5小时/次\n"
            "- 价格：80元/次（校内图书馆面授）\n"
            "- 频次：每周1-2次\n\n"
            "本人数学专业大三，绩点3.8，带过3个学生（成绩均有提升）。\n"
            "期末考前2周开始排课，需要的同学私信。"
        ),
        "category_code": "other",  # Task 1.2 调整：原 job → other
        "location_name": "图书馆", "user_email": "user10@example.com",
        "is_anonymous": False, "views": 289, "likes": 12, "is_recommend": False,
        "comments": [
            {"user_email": "user1@example.com", "content": "已私信！下学期高数救命", "likes": 3},
            {"user_email": "user9@example.com", "content": "80元/次算良心价了，外面机构200+", "likes": 5},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "已联系，学长讲得很好"},
        ],
    },

    # ==================== 其他 (other) ====================
    {
        "title": "新生入学须知：宿舍用品清单",
        "content": (
            "给新生整理的宿舍用品清单：\n\n"
            "【床品】\n"
            "- 被子（学校统一发，可自带薄被）\n"
            "- 枕头、床单×2、被套×2\n"
            "- 床垫（90×200cm）\n\n"
            "【日用】\n"
            "- 脸盆×2、毛巾×3、牙刷牙膏、洗发水、洗衣液\n"
            "- 拖鞋、衣架、晾衣夹\n\n"
            "【电子】\n"
            "- 充电宝、台灯、排插、网线\n"
            "- 笔记本电脑+锁\n\n"
            "【学习】\n"
            "- 文具、笔记本、计算器（数学专业必备）\n\n"
            "【不要带】\n"
            "- 大功率电器（违章会没收）\n"
            "- 贵重物品（注意保管）"
        ),
        "category_code": "other", "location_name": "学士公寓", "user_email": "user10@example.com",
        "is_anonymous": False, "views": 1234, "likes": 98, "is_recommend": True,
        "comments": [
            {"user_email": "user1@example.com", "content": "学长救命！正要买装备", "likes": 8},
            {"user_email": "user3@example.com", "content": "补充一个：床帘！必备神器", "likes": 12},
            {"user_email": "user9@example.com", "content": "床垫90×200是对的，已验证", "likes": 4},
        ],
        "validations": [
            {"user_email": "user1@example.com", "type": "confirmation", "comment": "学长清单很全，照着买就行"},
            {"user_email": "user9@example.com", "type": "confirmation", "comment": "床垫尺寸正确"},
        ],
    },
]


# =============================================================================
# 江南大学 6 态状态样本帖子（draft/pending/published/expired/conflict/archived 各 ≥1）
# 与现有 30 条 published 帖子互补，确保 6 态覆盖
# =============================================================================

JIANGNAN_STATUS_SAMPLES = [
    {
        "title": "【草稿】北门外新开咖啡店测评（草稿中，未提交）",
        "content": "正在整理北门外新开咖啡店的测评信息，等周末再去试一次再发布。目前信息：店名、价格、营业时间。",
        "category_code": "share",  # Task 1.2 调整：原 food → share
        "location_name": "北门", "user_email": "user3@example.com",
        "status": "draft", "views": 0, "likes": 0, "is_recommend": False,
    },
    {
        "title": "【待审核】文浩科学馆下周讲座通知（等待管理员审核）",
        "content": "下周三文浩科学馆有学术讲座，提交审核中，审核通过后大家就可以看到了。",
        "category_code": "teamup",  # Task 1.2 调整：原 event → teamup
        "location_name": "文浩科学馆", "user_email": "user4@example.com",
        "status": "pending", "views": 0, "likes": 0, "is_recommend": False,
    },
    {
        "title": "【已过期】上学期期末复习资料（已过期归档）",
        "content": "这是上学期的期末复习资料，已过期，仅供参考。",
        "category_code": "teamup",  # Task 1.2 调整：原 study → teamup
        "location_name": "图书馆", "user_email": "user10@example.com",
        "status": "expired", "views": 156, "likes": 8, "is_recommend": False,
    },
    {
        "title": "【冲突】食堂价格争议帖（信息冲突待处理）",
        "content": "本帖信息与其他帖子存在冲突，已标记为冲突状态，待管理员处理。",
        "category_code": "share",  # Task 1.2 调整：原 food → share
        "location_name": "第一食堂", "user_email": "user6@example.com",
        "status": "conflict", "views": 89, "likes": 3, "is_recommend": False,
    },
    {
        "title": "【已归档】已结束的社团招新通知",
        "content": "该招新活动已结束，帖子归档保存。",
        "category_code": "teamup",  # Task 1.2 调整：原 event → teamup
        "location_name": "大学生活动中心", "user_email": "user1@example.com",
        "status": "archived", "views": 234, "likes": 15, "is_recommend": False,
    },
]


# =============================================================================
# 复旦大学 / 浙江大学 演示帖子数据
# 每校 25 条：20 published + draft/pending/expired/conflict/archived 各 1
# =============================================================================

def _build_demo_post(title, content, category_code, location_name, user_email,
                     views=100, likes=5, is_recommend=False, status="published",
                     comments=None, validations=None):
    """构造演示帖子的统一结构（与江南大学 JIANGNAN_POSTS 字段对齐）

    注意：参数顺序为 ..., views, likes, is_recommend, status, comments, validations。
    - 普通帖：_build_demo_post(..., 234, 18, True, comments=[...], validations=[...])
      → is_recommend=True, status 默认 "published"
    - 状态样本：_build_demo_post(..., 0, 0, status="draft")
      → is_recommend 默认 False, status="draft"
    """
    return {
        "title": title, "content": content,
        "category_code": category_code, "location_name": location_name,
        "user_email": user_email, "is_anonymous": False,
        "views": views, "likes": likes, "is_recommend": is_recommend,
        "status": status,
        "comments": comments or [],
        "validations": validations or [],
    }


FUDAN_POSTS = [
    _build_demo_post(
        "本部食堂二楼麻辣香锅推荐", "本部食堂二楼麻辣香锅，荤素自选，14元/份，加饭免费。",
        "share", "本部食堂", "fudan_user3@example.com", 234, 18, True,
        comments=[{"user_email": "fudan_user1@example.com", "content": "昨天去吃了，确实不错", "likes": 3}],
        validations=[{"user_email": "fudan_user1@example.com", "type": "confirmation", "comment": "亲测好吃"}]
    ),
    _build_demo_post(
        "南区食堂早餐豆浆油条测评", "南区食堂早餐豆浆1元油条1.5元，性价比之王。",
        "share", "南区食堂", "fudan_user3@example.com", 156, 12
    ),
    _build_demo_post(
        "文科图书馆开放时间汇总", "文科图书馆周一到周日 8:00-22:00，期末延长到23:00。",
        "teamup", "文科图书馆", "fudan_user1@example.com", 432, 34, True,
        comments=[{"user_email": "fudan_user2@example.com", "content": "期末占座要早7点去", "likes": 5}]
    ),
    _build_demo_post(
        "光华楼自习室预约指南", "光华楼3-5层自习室需提前1天预约，扫码签到。",
        "teamup", "光华楼", "fudan_user2@example.com", 289, 22,
        comments=[{"user_email": "fudan_user1@example.com", "content": "预约系统经常卡", "likes": 2}]
    ),
    _build_demo_post(
        "相辉堂周五话剧《雷雨》演出", "本周五晚7点相辉堂话剧社演《雷雨》，免费入场。",
        "teamup", "相辉堂", "fudan_user4@example.com", 367, 28, True,
        comments=[{"user_email": "fudan_user3@example.com", "content": "期待！必须去", "likes": 4}],
        validations=[{"user_email": "fudan_user3@example.com", "type": "confirmation", "comment": "看完了，演技在线"}]
    ),
    _build_demo_post(
        "学生活动中心街舞社招新", "本周一到周五中午学生活动中心一楼街舞社招新。",
        "teamup", "学生活动中心", "fudan_user4@example.com", 298, 21
    ),
    _build_demo_post(
        "复旦大讲堂：人工智能伦理", "下周三晚7点光华楼报告厅，清华教授讲AI伦理。",
        "teamup", "光华楼", "fudan_user1@example.com", 412, 35, True
    ),
    _build_demo_post(
        "南区快递点高峰时段提醒", "南区快递点工作日饭点排队30分钟+，建议错峰。",
        "other", "南区学生公寓", "fudan_user3@example.com", 198, 14
    ),
    _build_demo_post(
        "南区学生公寓洗衣机使用规则", "南区公寓每层4台洗衣机，3元/次，禁洗鞋。",
        "other", "南区学生公寓", "fudan_user5@example.com", 167, 9
    ),
    _build_demo_post(
        "邯郸路校门到地铁10号线攻略", "邯郸路校门步行8分钟到地铁10号线国权路站。",
        "other", "邯郸路校门", "fudan_user5@example.com", 312, 18
    ),
    _build_demo_post(
        "本部体育场夜跑照明维修通知", "本部体育场东侧照明维修中，建议西侧跑道。",
        "other", "本部体育场", "fudan_user5@example.com", 145, 7,
        validations=[{"user_email": "fudan_user1@example.com", "type": "refutation", "comment": "今天看修好了"}]
    ),
    _build_demo_post(
        "文科图书馆捡到黑色钱包", "文科图书馆三楼捡到黑色钱包，已交服务台。",
        "lost_found", "文科图书馆", "fudan_user1@example.com", 234, 8
    ),
    _build_demo_post(
        "南区食堂丢失蓝色保温杯", "南区食堂二楼丢失蓝色保温杯，内有刻字。",
        "lost_found", "南区食堂", "fudan_user3@example.com", 156, 5
    ),
    _build_demo_post(
        "邯郸路校门外咖啡店招兼职", "邯郸路校门外星巴克招兼职，时薪20元。",
        "other", "邯郸路校门", "fudan_user2@example.com", 367, 22
    ),
    _build_demo_post(
        "接高数家教", "数学系大三接高数家教，80元/次，图书馆面授。",
        "other", "文科图书馆", "fudan_user1@example.com", 289, 14
    ),
    _build_demo_post(
        "燕园春季樱花观赏指南", "燕园樱花3月底盛开，建议工作日去，周末人爆满。",
        "other", "燕园", "fudan_user4@example.com", 523, 42, True,
        validations=[{"user_email": "fudan_user3@example.com", "type": "confirmation", "comment": "上周去拍过了"}]
    ),
    # 补充 4 条 published 帖子，确保已发布帖 ≥20
    _build_demo_post(
        "南区学生公寓空调使用须知", "南区公寓空调为集中式，遥控器需在宿管处押金借用，电费另算。",
        "other", "南区学生公寓", "fudan_user5@example.com", 178, 11
    ),
    _build_demo_post(
        "本部体育场足球场预约规则", "本部体育场足球场需提前2天预约，每场2小时，免费。",
        "other", "本部体育场", "fudan_user5@example.com", 234, 14,
        comments=[{"user_email": "fudan_user1@example.com", "content": "周末基本约不到", "likes": 3}]
    ),
    _build_demo_post(
        "文科图书馆期末延长开放通知", "期末期间文科图书馆延长至24:00，需刷校园卡入馆。",
        "teamup", "文科图书馆", "fudan_user1@example.com", 412, 31, True,
        comments=[{"user_email": "fudan_user2@example.com", "content": "终于不用挤理科馆了", "likes": 4}]
    ),
    _build_demo_post(
        "邯郸路校门周边早餐车汇总", "邯郸路校门外3个早餐车，5-9点营业，煎饼果子5元最推荐。",
        "share", "邯郸路校门", "fudan_user3@example.com", 289, 19,
        validations=[{"user_email": "fudan_user1@example.com", "type": "confirmation", "comment": "煎饼果子确实好吃"}]
    ),
    # 6 态样本
    _build_demo_post(
        "【草稿】本部食堂新菜测评（草稿中）", "正在整理本部食堂新菜测评，待完善后发布。",
        "share", "本部食堂", "fudan_user3@example.com", 0, 0, status="draft"
    ),
    _build_demo_post(
        "【待审核】光华楼讲座通知", "下周光华楼讲座通知，等待管理员审核。",
        "teamup", "光华楼", "fudan_user1@example.com", 0, 0, status="pending"
    ),
    _build_demo_post(
        "【已过期】上学期期末复习资料", "上学期期末复习资料，已过期归档。",
        "teamup", "文科图书馆", "fudan_user2@example.com", 134, 6, status="expired"
    ),
    _build_demo_post(
        "【冲突】食堂价格争议帖", "本帖价格信息与其他帖子冲突，待处理。",
        "share", "本部食堂", "fudan_user3@example.com", 67, 2, status="conflict"
    ),
    _build_demo_post(
        "【已归档】已结束的招新通知", "该招新活动已结束，归档保存。",
        "teamup", "学生活动中心", "fudan_user4@example.com", 198, 11, status="archived"
    ),
]


ZJU_POSTS = [
    _build_demo_post(
        "西区食堂二楼麻辣香锅推荐", "西区食堂二楼麻辣香锅，13元/份，量足味正。",
        "share", "西区食堂", "zju_user3@example.com", 256, 19, True,
        comments=[{"user_email": "zju_user1@example.com", "content": "经常去，确实不错", "likes": 3}],
        validations=[{"user_email": "zju_user1@example.com", "type": "confirmation", "comment": "亲测好吃"}]
    ),
    _build_demo_post(
        "东区食堂早餐小笼包测评", "东区食堂早餐小笼包6元8个，皮薄馅多。",
        "share", "东区食堂", "zju_user3@example.com", 178, 13
    ),
    _build_demo_post(
        "紫金港图书馆开放时间汇总", "图书馆周一到周日 8:00-22:30，期末延长到23:30。",
        "teamup", "图书馆", "zju_user4@example.com", 478, 38, True,
        comments=[{"user_email": "zju_user1@example.com", "content": "期末必须早6:30去排队", "likes": 6}]
    ),
    _build_demo_post(
        "图书馆三楼自习室预约规则", "图书馆三楼需预约，签到制，违约3次扣信用分。",
        "teamup", "图书馆", "zju_user4@example.com", 312, 24
    ),
    _build_demo_post(
        "学生活动中心话剧社演出", "本周末学生活动中心话剧社演《茶馆》，免费入场。",
        "teamup", "学生活动中心", "zju_user3@example.com", 345, 27, True,
        validations=[{"user_email": "zju_user1@example.com", "type": "confirmation", "comment": "看完了，超棒"}]
    ),
    _build_demo_post(
        "紫金港ACM集训队招新", "面向全校招新，每周10小时训练，简历发 acm@zju.edu.cn。",
        "teamup", "教学楼群", "zju_user1@example.com", 398, 31, True
    ),
    _build_demo_post(
        "浙大讲堂：量子计算前沿", "下周三晚7点图书馆报告厅，院士讲座量子计算。",
        "teamup", "图书馆", "zju_user4@example.com", 456, 36, True
    ),
    _build_demo_post(
        "快递服务中心取件高峰提醒", "快递中心工作日饭点排队30分钟，建议错峰。",
        "other", "快递服务中心", "zju_user3@example.com", 198, 14
    ),
    _build_demo_post(
        "学生公寓洗衣机使用规则", "学生公寓每层4台洗衣机，3元/次，禁洗鞋。",
        "other", "学生公寓", "zju_user5@example.com", 167, 9
    ),
    _build_demo_post(
        "紫金港校门到地铁5号线攻略", "紫金港校门步行10分钟到地铁5号线浙大紫金港站。",
        "other", "紫金港校门", "zju_user5@example.com", 289, 16
    ),
    _build_demo_post(
        "校车冬季时刻表更新", "校车冬季首发延后30分钟，末班不变。",
        "other", "紫金港校门", "zju_user1@example.com", 312, 15
    ),
    _build_demo_post(
        "体育馆游泳馆开放时间", "游泳馆周一到周五16:00-21:00，学期卡300元。",
        "other", "体育馆", "zju_user5@example.com", 234, 12,
        validations=[{"user_email": "zju_user1@example.com", "type": "confirmation", "comment": "学期卡已办"}]
    ),
    _build_demo_post(
        "田径场照明维修通知", "田径场东侧照明维修，建议西侧跑道。",
        "other", "田径场", "zju_user5@example.com", 134, 6,
        validations=[{"user_email": "zju_user1@example.com", "type": "refutation", "comment": "已修好"}]
    ),
    _build_demo_post(
        "图书馆捡到银色U盘", "图书馆三楼捡到银色U盘32G，已交服务台。",
        "lost_found", "图书馆", "zju_user4@example.com", 198, 8
    ),
    _build_demo_post(
        "启真湖黑天鹅孵化幼崽", "启真湖黑天鹅带3只小天鹅，保持5米距离观赏。",
        "share", "启真湖", "zju_user2@example.com", 478, 38, True,
        validations=[{"user_email": "zju_user1@example.com", "type": "confirmation", "comment": "亲眼所见"}]
    ),
    _build_demo_post(
        "校园流浪猫喂食指南", "校园流浪猫请用专门猫粮，禁喂人类食物。",
        "share", "学生公寓", "zju_user2@example.com", 312, 24
    ),
    # 补充 4 条 published 帖子，确保已发布帖 ≥20
    _build_demo_post(
        "启真湖晨跑路线推荐", "启真湖一圈约2.5公里，早晨6-7点人少风景好，适合晨跑。",
        "other", "启真湖", "zju_user5@example.com", 267, 21, True,
        comments=[{"user_email": "zju_user1@example.com", "content": "亲测2.6公里，很准", "likes": 4}]
    ),
    _build_demo_post(
        "学生公寓快递代收点汇总", "学生公寓1号楼下快递柜+菜鸟驿站，顺丰在校门口。",
        "other", "学生公寓", "zju_user3@example.com", 298, 17
    ),
    _build_demo_post(
        "图书馆考研自习室预约攻略", "图书馆5楼考研自习室需预约，每周一放号，违约2次拉黑。",
        "teamup", "图书馆", "zju_user4@example.com", 389, 28, True,
        comments=[{"user_email": "zju_user1@example.com", "content": "周一8点抢号必崩", "likes": 6}],
        validations=[{"user_email": "zju_user1@example.com", "type": "confirmation", "comment": "违约拉黑属实"}]
    ),
    _build_demo_post(
        "紫金港校车早高峰排队提醒", "早8点校车排队30分钟+，建议提前15分钟或骑行。",
        "other", "紫金港校门", "zju_user5@example.com", 234, 13
    ),
    # 6 态样本
    _build_demo_post(
        "【草稿】西区食堂新菜测评（草稿中）", "正在整理西区食堂新菜测评，待完善后发布。",
        "share", "西区食堂", "zju_user3@example.com", 0, 0, status="draft"
    ),
    _build_demo_post(
        "【待审核】图书馆讲座通知", "下周图书馆讲座通知，等待管理员审核。",
        "teamup", "图书馆", "zju_user4@example.com", 0, 0, status="pending"
    ),
    _build_demo_post(
        "【已过期】上学期期末复习资料", "上学期期末复习资料，已过期归档。",
        "teamup", "图书馆", "zju_user4@example.com", 145, 7, status="expired"
    ),
    _build_demo_post(
        "【冲突】食堂价格争议帖", "本帖价格信息与其他帖子冲突，待处理。",
        "share", "西区食堂", "zju_user3@example.com", 78, 3, status="conflict"
    ),
    _build_demo_post(
        "【已归档】已结束的招新通知", "该招新活动已结束，归档保存。",
        "teamup", "学生活动中心", "zju_user3@example.com", 187, 9, status="archived"
    ),
]


# =============================================================================
# 三校专题数据
# =============================================================================

JIANGNAN_TOPICS = [
    ("新生入学指南", "为新生提供校园生活必备信息：宿舍、食堂、学习、交通一站式攻略",
     "user10@example.com"),
    ("江南美食地图", "学姐学长亲测的校园+周边美食清单，干饭人必备",
     "user3@example.com"),
    ("期末复习资源合集", "历年真题、复习笔记、易错点汇总，期末救命资料",
     "user10@example.com"),
    ("蠡湖校园生态", "记录校园流浪猫、蠡湖天鹅等校园生态观察",
     "user8@example.com"),
    ("社团活动精选", "校园社团招新、活动演出信息一网打尽",
     "user1@example.com"),
    ("校园生活贴士", "快递、打印、洗衣、交通等日常生活实用技巧",
     "user9@example.com"),
]

FUDAN_TOPICS = [
    ("复旦新生入学指南", "复旦大学邯郸校区新生必备信息：宿舍、食堂、学习、交通",
     "fudan_admin@momentcampus.com"),
    ("邯郸路美食地图", "本校及周边性价比美食清单",
     "fudan_user3@example.com"),
    ("光华楼自习攻略", "光华楼自习室预约、占座、开放时间完整攻略",
     "fudan_user2@example.com"),
]

ZJU_TOPICS = [
    ("浙大新生入学指南", "浙江大学紫金港校区新生必备信息：宿舍、食堂、学习、交通",
     "zju_admin@momentcampus.com"),
    ("紫金港美食地图", "紫金港东西区食堂及周边性价比美食清单",
     "zju_user3@example.com"),
    ("启真湖生态观察", "记录启真湖鸟类、黑天鹅等校园生态",
     "zju_user2@example.com"),
]


# =============================================================================
# 跨校成员关系（TEN-05.3）：江南大学 user1/user2 加入复旦/浙大，演示切换效果
# =============================================================================

CROSS_SCHOOL_MEMBERSHIPS = [
    # user1@（江南小李，primary=jiangnan）→ 复旦 member
    {"user_email": "user1@example.com", "school_code": "fudan", "role": "member", "is_default": False},
    # user2@（蠡湖钓客，primary=jiangnan）→ 浙大 member
    {"user_email": "user2@example.com", "school_code": "zju", "role": "member", "is_default": False},
]


# =============================================================================
# 三校聚合配置（统一索引，便于 seed 函数遍历）
# =============================================================================

SCHOOLS_REGISTRY = [
    {
        "meta": JIANGNAN_META,
        "categories": JIANGNAN_CATEGORIES,
        "locations": JIANGNAN_LOCATIONS,
        "users": JIANGNAN_USERS,
        "posts": JIANGNAN_POSTS,  # published 帖子
        "status_samples": JIANGNAN_STATUS_SAMPLES,  # 5 个状态样本（draft/pending/expired/conflict/archived）
        "topics": JIANGNAN_TOPICS,
    },
    {
        "meta": FUDAN_META,
        "categories": FUDAN_CATEGORIES,
        "locations": FUDAN_LOCATIONS,
        "users": FUDAN_USERS,
        "posts": FUDAN_POSTS,  # 已包含 6 态样本
        "status_samples": [],  # 帖子列表已包含 6 态样本
        "topics": FUDAN_TOPICS,
    },
    {
        "meta": ZJU_META,
        "categories": ZJU_CATEGORIES,
        "locations": ZJU_LOCATIONS,
        "users": ZJU_USERS,
        "posts": ZJU_POSTS,
        "status_samples": [],
        "topics": ZJU_TOPICS,
    },
]


# =============================================================================
# 工具函数
# =============================================================================

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


async def init_db():
    """清空所有现有数据（保留表结构，openGauss 已通过 Alembic 创建表）

    使用 TRUNCATE ... CASCADE 清空所有业务表数据，再逐表重置自增序列。
    注：openGauss 的 PGXC 架构不支持 RESTART IDENTITY 子句，需手动 ALTER SEQUENCE。

    TEN-05：扩展清空多租户相关表（school_memberships/school_settings/school_subscriptions/
    product_plans/plan_entitlements/platform_audit_logs 等），
    保证重跑种子脚本时外键不冲突。
    注：原 post_change_reports 表已移除（问题报告功能与评论/举报冲突）。
    注：publisher_profiles / publisher_memberships / post_templates 表已随
    migration a6b7c8d9e0f1 drop，不再清空。
    """
    # 按外键依赖逆序列出所有业务表（含多租户与治理扩展表）
    tables = [
        # 治理与报告
        "reports",
        "validation_records",
        # 互动
        "likes",
        "comments",
        "post_images",
        "posts",
        # 专题
        "topic_collection_posts",
        "topic_collections",
        # 通知与历史
        "notifications",
        "search_histories",
        "browse_histories",
        "drafts",
        "notification_preferences",
        "user_recommendation_preferences",
        "subscriptions",
        "password_reset_tokens",
        # 日志与事件
        "admin_operation_logs",
        "platform_audit_logs",
        "product_events",
        "ai_invocation_logs",
        "job_run_records",
        "tenant_usage_daily",
        # 地点
        "locations",
        # 分类（Task 1.2 调整：post_types 表已删除）
        # Task 1.3 调整：tags/post_tags 表已删除
        "categories",
        # 多租户
        "school_subscriptions",
        "school_memberships",
        "school_domains",
        "school_settings",
        # 套餐
        "plan_entitlements",
        "product_plans",
        # 用户与学校（最后清）
        "users",
        "schools",
    ]
    table_list = ", ".join(tables)
    async with engine.begin() as conn:
        # 1. 清空所有表数据（CASCADE 处理外键依赖）
        await conn.execute(
            text(f"TRUNCATE TABLE {table_list} CASCADE;")
        )
        # 2. 重置每张表的自增序列（PGXC 不支持 RESTART IDENTITY，需手动重置）
        for table_name in tables:
            # openGauss 默认序列命名为 <table>_id_seq（部分表可能无 id 列，忽略错误）
            try:
                await conn.execute(
                    text(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH 1;")
                )
            except Exception:
                pass  # 表无自增序列，跳过


# =============================================================================
# 套餐与权益（COM-01）
# =============================================================================

async def seed_plans(session: AsyncSession):
    """创建 3 档套餐 + 权益项（trial/standard/operations）"""
    now = datetime.now()
    plans = []
    for p in PLANS_DATA:
        plan = ProductPlan(
            code=p["code"],
            name=p["name"],
            description=p["description"],
            status="active",
            sort_order=p["sort_order"],
            created_at=now,
            updated_at=now,
        )
        session.add(plan)
        plans.append(plan)
    await session.flush()

    # 创建权益项
    entitlements = []
    for plan, p in zip(plans, PLANS_DATA):
        for key, limit_value, is_hard in p["entitlements"]:
            ent = PlanEntitlement(
                plan_id=plan.id,
                key=key,
                limit_value=limit_value,
                is_hard=is_hard,
                description=f"{p['name']} - {key}",
                created_at=now,
                updated_at=now,
            )
            session.add(ent)
            entitlements.append(ent)
    await session.flush()
    return plans


# =============================================================================
# 学校、分类、地点、用户、成员关系、品牌设置、套餐订阅
# =============================================================================

async def seed_schools(session: AsyncSession):
    """创建三所演示学校"""
    now = datetime.now()
    schools = []
    for cfg in SCHOOLS_REGISTRY:
        meta = cfg["meta"]
        school = School(
            name=meta["name"],
            code=meta["code"],
            province=meta["province"],
            city=meta["city"],
            address=meta["address"],
            center_lat=meta["center_lat"],
            center_lng=meta["center_lng"],
            map_zoom=meta["map_zoom"],
            logo_url=meta["logo_url"],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        schools.append(school)
        session.add(school)
    await session.flush()
    return schools


async def seed_school_settings(session: AsyncSession, schools: list):
    """为每所学校创建差异化的品牌设置（site_name/brand_color/logo_url）"""
    now = datetime.now()
    settings_list = []
    for school, cfg in zip(schools, SCHOOLS_REGISTRY):
        meta = cfg["meta"]
        settings = SchoolSettings(
            school_id=school.id,
            site_name=meta["site_name"],
            description=meta["description"],
            require_review=True,
            allow_anonymous=True,
            allow_comments=True,
            publish_frequency=10,
            image_limit=9,
            default_validity_days=30,
            brand_color=meta["brand_color"],
            logo_url=meta["logo_url"],
            created_at=now,
            updated_at=now,
        )
        session.add(settings)
        settings_list.append(settings)
    await session.flush()
    return settings_list


async def seed_subscriptions(session: AsyncSession, schools: list, plans: list, admin_user: User):
    """为每所学校分配运营档套餐（activated 状态）"""
    now = datetime.now()
    operations_plan = next((p for p in plans if p.code == "operations"), plans[-1])
    subscriptions = []
    for school in schools:
        sub = SchoolSubscription(
            school_id=school.id,
            plan_id=operations_plan.id,
            status="active",
            started_at=now,
            expires_at=None,
            assigned_by=admin_user.id,
            assigned_at=now,
            note=f"TEN-05 三校演示数据：自动分配运营档套餐（activated）",
            created_at=now,
            updated_at=now,
        )
        session.add(sub)
        subscriptions.append(sub)
    await session.flush()
    return subscriptions


async def seed_categories(session: AsyncSession, schools: list):
    """为每所学校创建分类（按 SCHOOLS_REGISTRY 配置）"""
    now = datetime.now()
    categories_by_school = {}  # school_code -> [Category]
    for school, cfg in zip(schools, SCHOOLS_REGISTRY):
        cats = []
        for name, code, icon, desc, days, sort in cfg["categories"]:
            cat = Category(
                school_id=school.id,
                name=name,
                code=code,
                icon=icon,
                description=desc,
                default_validity_days=days,
                sort_order=sort,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(cat)
            cats.append(cat)
        categories_by_school[school.code] = cats
    await session.flush()
    return categories_by_school


async def seed_users(session: AsyncSession, schools: list):
    """为每所学校创建用户（每校 1 admin + N 普通用户）

    用户表的 school_id 字段为该用户的"主校"（默认学校）。
    跨校成员关系由 seed_memberships 单独创建。
    """
    users_by_school = {}  # school_code -> [User]
    users_by_email = {}
    for school, cfg in zip(schools, SCHOOLS_REGISTRY):
        users = []
        for u in cfg["users"]:
            user = User(
                email=u["email"],
                nickname=u["nickname"],
                password_hash=get_password_hash("pass123"),
                school_id=school.id,
                role=u["role"],
                bio=u["bio"],
                is_active=True,
                # ACC-01.4: 演示账号视为已完成首次使用引导，避免每次登录弹教程
                onboarding_completed=True,
            )
            session.add(user)
            users.append(user)
            users_by_email[u["email"]] = user
        users_by_school[school.code] = users
    await session.flush()
    return users_by_school, users_by_email


async def seed_memberships(session: AsyncSession, schools: list, users_by_email: dict):
    """为每位用户创建 SchoolMembership（主校 + 跨校成员关系）

    - 主校：is_default=True，role 与 user.role 一致（admin 或 member）
    - 跨校：根据 CROSS_SCHOOL_MEMBERSHIPS 配置，is_default=False，role=member
    """
    now = datetime.now()
    school_by_code = {s.code: s for s in schools}
    memberships = []

    # 1. 为每位用户创建主校 membership
    for school, cfg in zip(schools, SCHOOLS_REGISTRY):
        for u in cfg["users"]:
            user = users_by_email[u["email"]]
            role_in_school = "admin" if u["role"] == "admin" else "member"
            # super_admin 平台角色映射为 admin（本表不存 super_admin）
            if u["role"] == "super_admin":
                role_in_school = "admin"
            m = SchoolMembership(
                user_id=user.id,
                school_id=school.id,
                role=role_in_school,
                status="active",
                is_default=True,
                joined_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(m)
            memberships.append(m)

    # 2. 跨校成员关系（TEN-05.3）
    for cross in CROSS_SCHOOL_MEMBERSHIPS:
        user = users_by_email.get(cross["user_email"])
        school = school_by_code.get(cross["school_code"])
        if user is None or school is None:
            continue
        m = SchoolMembership(
            user_id=user.id,
            school_id=school.id,
            role=cross["role"],
            status="active",
            is_default=cross["is_default"],
            joined_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(m)
        memberships.append(m)

    await session.flush()
    return memberships


async def seed_locations(session: AsyncSession, schools: list):
    """为每所学校创建地点（基于 SCHOOLS_REGISTRY 配置）"""
    now = datetime.now()
    locations_by_school = {}  # school_code -> [Location]
    for school, cfg in zip(schools, SCHOOLS_REGISTRY):
        locs = []
        for name, lat, lng, desc in cfg["locations"]:
            loc = Location(
                school_id=school.id,
                name=name,
                description=desc,
                latitude=lat,
                longitude=lng,
                post_count=0,
                is_verified=True,
                created_at=now,
                updated_at=now,
            )
            session.add(loc)
            locs.append(loc)
        locations_by_school[school.code] = locs
    await session.flush()
    return locations_by_school


# =============================================================================
# 帖子、评论、协同验证、状态样本
# =============================================================================

# 时间偏移：让帖子分散在过去 30 天内
TIME_OFFSETS_DAYS = [
    30, 29, 28, 27, 26, 25, 24, 23, 22, 21,
    20, 18, 16, 15, 14, 13, 12, 11, 10, 9,
    8, 7, 6, 5, 4, 3, 2, 1, 0, 0,
]


async def seed_posts_for_school(session: AsyncSession, school: School, cfg: dict,
                                 users_by_email: dict, categories: list,
                                 locations: list):
    """为单所学校创建帖子（含评论、协同验证）+ 状态样本

    Task 1.2 调整：移除 post_types 参数（PostType 已删除，统一使用 category）

    返回 (posts, comments, validations)
    """
    user_by_email = {u.email: u for u in [users_by_email[u["email"]] for u in cfg["users"]]}
    category_by_code = {c.code: c for c in categories}
    location_by_name = {l.name: l for l in locations}

    now = datetime.now()
    posts = []
    # post_by_idx[i] = post：保留 all_posts_data 索引到 Post 对象的映射，
    # 用于评论/验证循环按索引查找（主循环可能因 user/category 缺失而跳过某些 post）
    post_by_idx: dict[int, Post] = {}
    all_comments = []
    all_validations = []

    # 合并 published 帖子与状态样本帖子
    all_posts_data = list(cfg["posts"])
    # 为状态样本帖子补充 created_at（避免 TIME_OFFSETS 越界）
    for s in cfg.get("status_samples", []):
        all_posts_data.append(s)

    for i, p in enumerate(all_posts_data):
        user = user_by_email.get(p["user_email"])
        if user is None:
            # 跨校用户（如 user1@ 在江南大学发帖但用户对象来自主校）
            user = users_by_email.get(p["user_email"])
        if user is None:
            continue

        category = category_by_code.get(p["category_code"])
        if category is None:
            continue
        location = location_by_name.get(p["location_name"])

        # 失物招领分类补充 lost_type 字段
        lost_type = None
        if category.code == "lost_found":
            lost_type = "lost" if "丢失" in p["title"] else "found"

        # 计算创建时间
        days_ago = TIME_OFFSETS_DAYS[i % len(TIME_OFFSETS_DAYS)]
        hours_ago = (i * 3) % 24
        created_at = now - timedelta(days=days_ago, hours=hours_ago)

        status = p.get("status", "published")
        # 已过期帖子的 expire_at 设为过去；其他状态按分类默认信息截止天数
        if status == "expired":
            expire_at = created_at + timedelta(days=1)  # 立即过期
        else:
            expire_at = created_at + timedelta(days=category.default_validity_days)

        post = Post(
            user_id=user.id,
            school_id=school.id,
            category_id=category.id,
            location_id=location.id if location else None,
            title=p["title"],
            content=p["content"],
            is_anonymous=p.get("is_anonymous", False),
            status=status,
            view_count=p.get("views", 0),
            like_count=p.get("likes", 0),
            comment_count=len(p.get("comments", [])),
            valid_count=len([v for v in p.get("validations", []) if v["type"] == "confirmation"]),
            invalid_count=len([v for v in p.get("validations", []) if v["type"] == "refutation"]),
            lost_type=lost_type,
            expire_at=expire_at,
            is_recommend=p.get("is_recommend", False),
            created_at=created_at,
            updated_at=created_at,
        )
        posts.append(post)
        post_by_idx[i] = post
        # 单条插入并立即 flush，避免 SQLAlchemy 2.0 insertmanyvalues 在 Python 3.14
        # 下触发 "cannot use 'list' as a set element" 的兼容性问题
        session.add(post)
        try:
            await session.flush()
        except TypeError as te:
            if "unhashable" in str(te):
                import traceback as _tb
                print(f"\n!!! TypeError on post #{i}: {p.get('title', '?')}")
                print(f"!!! school_code={school.code}, category_code={p.get('category_code')}")
                print(f"!!! post attrs: status={status}, lost_type={lost_type}")
                _tb.print_exc()
            raise

    # 创建评论
    for i, p in enumerate(all_posts_data):
        post = post_by_idx.get(i)
        if post is None:
            continue
        for j, c in enumerate(p.get("comments", [])):
            comment_user = users_by_email.get(c["user_email"])
            if comment_user is None:
                continue
            comment_time = post.created_at + timedelta(hours=1 + j * 3)
            if comment_time > now:
                comment_time = now - timedelta(minutes=10 + j * 5)
            comment = Comment(
                post_id=post.id,
                user_id=comment_user.id,
                parent_id=None,
                content=c["content"],
                like_count=c.get("likes", 0),
                status="published",
                created_at=comment_time,
                updated_at=comment_time,
            )
            all_comments.append(comment)

    for comment in all_comments:
        session.add(comment)
    await session.flush()

    # 创建协同验证记录（confirmation/refutation，受 (post_id, user_id) 唯一约束）
    seen_pairs = set()
    for i, p in enumerate(all_posts_data):
        post = post_by_idx.get(i)
        if post is None:
            continue
        for j, v in enumerate(p.get("validations", [])):
            v_user = users_by_email.get(v["user_email"])
            if v_user is None:
                continue
            # 唯一约束：每用户对每帖只能有一条验证记录
            pair = (post.id, v_user.id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            v_time = post.created_at + timedelta(hours=2 + j * 6)
            if v_time > now:
                v_time = now - timedelta(minutes=30 + j * 15)
            record = ValidationRecord(
                post_id=post.id,
                user_id=v_user.id,
                validation_type=v["type"],
                comment=v.get("comment"),
                created_at=v_time,
            )
            all_validations.append(record)
            session.add(record)

    await session.flush()

    return posts, all_comments, all_validations


async def seed_all_posts(session: AsyncSession, schools: list, users_by_email: dict,
                         categories_by_school: dict,
                         locations_by_school: dict):
    """为三所学校创建全部帖子

    Task 1.2 调整：移除 post_types 参数（PostType 已删除）
    """
    all_posts = []
    all_comments = []
    all_validations = []
    posts_by_school = {}  # school_code -> [Post]

    for school, cfg in zip(schools, SCHOOLS_REGISTRY):
        cats = categories_by_school.get(school.code, [])
        locs = locations_by_school.get(school.code, [])
        posts, comments, vals = await seed_posts_for_school(
            session, school, cfg, users_by_email, cats, locs
        )
        all_posts.extend(posts)
        all_comments.extend(comments)
        all_validations.extend(vals)
        posts_by_school[school.code] = posts

    return all_posts, all_comments, all_validations, posts_by_school


# =============================================================================
# 五类治理样本（GOV-01）：
# confirmation / refutation 已由 ValidationRecord 在 seed_posts_for_school 创建
# 原 3 类问题报告（update/expiration_report/conflict_report）已移除（与评论/举报冲突）
# =============================================================================

# seed_governance_reports 函数已移除：原 PostChangeReport 已删除


# =============================================================================
# 专题集合
# =============================================================================

async def seed_topic_collections(session: AsyncSession, schools: list,
                                  users_by_email: dict, posts_by_school: dict):
    """为每所学校创建专题集合（≥1）"""
    topics = []
    topic_posts = []

    for school, cfg in zip(schools, SCHOOLS_REGISTRY):
        school_posts = posts_by_school.get(school.code, [])
        published_posts = [p for p in school_posts if p.status == "published"]

        for i, (title, desc, creator_email) in enumerate(cfg["topics"]):
            creator = users_by_email.get(creator_email)
            if creator is None:
                continue
            topic = TopicCollection(
                title=title,
                description=desc,
                school_id=school.id,
                creator_id=creator.id,
                post_count=0,
                view_count=80 + i * 30,
                status="published",
                sort_order=i + 1,
                published_at=datetime.now(),
            )
            session.add(topic)
            topics.append(topic)

        await session.flush()

        # 为本批 topics 关联帖子（按关键词匹配 published 帖子）
        for i, topic in enumerate(topics[-len(cfg["topics"]):]):
            title, desc, _ = cfg["topics"][i]
            # 简单按关键词匹配
            keywords = [kw for kw in ["美食", "食堂", "新生", "入学", "复习", "期末", "猫", "天鹅", "社团", "招新", "讲座", "话剧", "快递", "打印", "洗衣机", "校车", "游泳", "自习", "光华楼", "启真湖", "燕园"]
                        if kw in title or kw in desc]
            selected = [p for p in published_posts
                        if any(kw in p.title or kw in p.content for kw in keywords)]
            if len(selected) < 3:
                others = [p for p in published_posts if p not in selected]
                selected.extend(others[:3 - len(selected)])
            selected = selected[:5]

            for idx, post in enumerate(selected):
                tp = TopicCollectionPost(
                    topic_collection_id=topic.id,
                    post_id=post.id,
                    sort_order=idx + 1,
                )
                session.add(tp)
                topic_posts.append(tp)
            topic.post_count = len(selected)

    await session.flush()
    return topics


# =============================================================================
# 通知样本（仅江南大学，与既有内容对齐）
# =============================================================================

async def seed_notifications(session: AsyncSession, schools: list, users_by_email: dict,
                              posts_by_school: dict):
    """创建通知数据（基于真实互动场景）"""
    notifications = []
    jiangnan_posts = posts_by_school.get("jiangnan", [])
    if not jiangnan_posts:
        return notifications

    target_post = jiangnan_posts[0]

    notification_templates = [
        ("user6@example.com", "comment", "您的帖子有新评论",
         "江南小李 评论了你的《二食堂三楼麻辣香锅真的绝了》",
         "user1@example.com", False),
        ("user3@example.com", "like", "您的帖子被点赞",
         "二食堂干饭人 等5人 赞了你的《蠡湖周边10块钱吃饱的5家店》",
         "user6@example.com", False),
        ("user8@example.com", "comment", "您的帖子有新评论",
         "图书馆常客 评论了你的《图书馆门口的橘猫又来蹭饭了》",
         "user4@example.com", True),
        ("user10@example.com", "system", "您的帖子被推荐",
         "您的《计算机组成原理复习资料分享》已被推荐到首页",
         "admin@momentcampus.com", False),
        ("user1@example.com", "system", "管理员审核通过",
         "您发布的《文浩科学馆周五晚话剧《雷雨》演出》已通过审核",
         "admin@momentcampus.com", True),
        ("user5@example.com", "like", "您的帖子被点赞",
         "江南小李 赞了你的《体育馆游泳馆开放时间》",
         "user1@example.com", False),
        ("user4@example.com", "system", "帖子即将过期",
         "您的《图书馆开放时间汇总》还有3天过期，如需保留请更新",
         "admin@momentcampus.com", False),
        ("user9@example.com", "comment", "您的帖子有新评论",
         "无锡学长 评论了你的《校园超市本周打折商品》",
         "user10@example.com", True),
    ]

    for user_email, ntype, title, content, actor_email, is_read in notification_templates:
        user = users_by_email.get(user_email)
        actor = users_by_email.get(actor_email)
        if user is None or actor is None:
            continue
        notification = Notification(
            user_id=user.id,
            type=ntype,
            title=title,
            content=content,
            target_type="post",
            target_id=target_post.id,
            actor_id=actor.id,
            is_read=is_read,
        )
        notifications.append(notification)

    session.add_all(notifications)
    await session.flush()
    return notifications


# =============================================================================
# 举报记录样本（仅江南大学）
# =============================================================================

async def seed_reports(session: AsyncSession, schools: list, users_by_email: dict,
                        posts_by_school: dict):
    """创建举报记录数据"""
    jiangnan_posts = posts_by_school.get("jiangnan", [])
    if not jiangnan_posts:
        return []

    admin_user = users_by_email.get("admin@momentcampus.com")

    reports_data = [
        (3, "user2@example.com", "fake", "螺蛳粉现在还有吗？我去没看到，疑似过期信息", "resolved", "已通知作者更新"),
        (4, "user9@example.com", "ad", "评论区有人发外卖广告，请处理", "resolved", "已删除广告评论"),
        (8, "user1@example.com", "inappropriate", "打印机价格可能有误，需核实", "processing", None),
        (10, "user6@example.com", "other", "话剧演出时间是不是改了？", "pending", None),
        (14, "user9@example.com", "fake", "图书馆开放时间跟实际不符", "resolved", "已联系作者更新"),
    ]

    reports = []
    for post_idx, reporter_email, rtype, desc, status, result in reports_data:
        if post_idx >= len(jiangnan_posts):
            continue
        reporter = users_by_email.get(reporter_email)
        if reporter is None:
            continue
        report = Report(
            post_id=jiangnan_posts[post_idx].id,
            comment_id=None,
            reporter_id=reporter.id,
            report_type=rtype,
            description=desc,
            status=status,
            handler_id=admin_user.id if admin_user and status != "pending" else None,
            handle_result=result,
        )
        reports.append(report)

    session.add_all(reports)
    await session.flush()
    return reports


# =============================================================================
# 主函数
# =============================================================================

async def seed_data():
    """主函数：填充所有演示数据（三校多租户差异化数据）"""
    print("=" * 60)
    print("TEN-05 三校多租户差异化数据填充")
    print("=" * 60)

    print("\n[1/11] 清空现有数据（保留表结构）...")
    await init_db()
    print("✓ 已清空所有业务表数据并重置自增 ID")

    async with async_session_maker() as session:
        print("\n[2/11] 创建 3 档套餐与权益项...")
        plans = await seed_plans(session)
        print(f"✓ 创建了 {len(plans)} 档套餐（trial/standard/operations）")

        print("\n[3/11] 创建三所演示学校...")
        schools = await seed_schools(session)
        for s in schools:
            print(f"  - {s.name} (code={s.code}, center={s.center_lat},{s.center_lng})")
        print(f"✓ 创建了 {len(schools)} 所学校")

        print("\n[4/11] 创建三校品牌设置（差异化主题色）...")
        settings_list = await seed_school_settings(session, schools)
        for s in settings_list:
            print(f"  - school_id={s.school_id} site_name='{s.site_name}' brand_color='{s.brand_color}'")
        print(f"✓ 创建了 {len(settings_list)} 条品牌设置")

        print("\n[5/11] 创建三校分类（5 类统一信息分类）...")
        categories_by_school = await seed_categories(session, schools)
        for code, cats in categories_by_school.items():
            print(f"  - {code}: {len(cats)} 个分类")
        total_cats = sum(len(c) for c in categories_by_school.values())
        print(f"✓ 共创建 {total_cats} 个分类")

        print("\n[6/11] 创建三校用户...")
        users_by_school, users_by_email = await seed_users(session, schools)
        for code, users in users_by_school.items():
            admin_count = sum(1 for u in users if u.role == "admin")
            print(f"  - {code}: {len(users)} 个用户（{admin_count} admin + {len(users) - admin_count} user）")
        total_users = sum(len(u) for u in users_by_school.values())
        print(f"✓ 共创建 {total_users} 个用户")

        print("\n[7/11] 创建成员关系（含跨校）...")
        memberships = await seed_memberships(session, schools, users_by_email)
        cross_count = len(CROSS_SCHOOL_MEMBERSHIPS)
        print(f"✓ 创建了 {len(memberships)} 条成员关系（含 {cross_count} 条跨校关系）")
        for cross in CROSS_SCHOOL_MEMBERSHIPS:
            print(f"  - {cross['user_email']} → {cross['school_code']} ({cross['role']})")

        print("\n[8/11] 创建三校地点...")
        locations_by_school = await seed_locations(session, schools)
        for code, locs in locations_by_school.items():
            print(f"  - {code}: {len(locs)} 个地点")
        total_locs = sum(len(l) for l in locations_by_school.values())
        print(f"✓ 共创建 {total_locs} 个地点")

        # [9/11] 创建三校官方发布主体 — 已下线（publisher_profiles / publisher_memberships / post_templates 表已 drop）
        # publishers_by_school = await seed_publishers(...)  # 已移除

        # 取 admin 用户作为订阅分配者
        admin_user = users_by_email.get("admin@momentcampus.com")
        print("\n[10/11] 为三校分配运营档套餐（activated）...")
        subscriptions = await seed_subscriptions(session, schools, plans, admin_user)
        for sub, school in zip(subscriptions, schools):
            print(f"  - {school.code}: plan=operations, status={sub.status}")
        print(f"✓ 创建了 {len(subscriptions)} 条 active 订阅")

        print("\n[11/11] 创建三校帖子（含 6 态样本 + 治理样本 + 专题）...")
        all_posts, all_comments, all_validations, posts_by_school = await seed_all_posts(
            session, schools, users_by_email, categories_by_school,
            locations_by_school
        )
        for code, posts in posts_by_school.items():
            # 统计 6 态分布
            status_counts = {}
            for p in posts:
                status_counts[p.status] = status_counts.get(p.status, 0) + 1
            print(f"  - {code}: {len(posts)} 条帖子，状态分布={status_counts}")
        print(f"✓ 共创建 {len(all_posts)} 条帖子")
        print(f"✓ 共创建 {len(all_comments)} 条评论")
        print(f"✓ 共创建 {len(all_validations)} 条协同验证记录")

        # 原 3 类问题报告样本已移除（PostChangeReport 表已删除）

        print("\n创建三校专题集合...")
        topics = await seed_topic_collections(
            session, schools, users_by_email, posts_by_school
        )
        for school, cfg in zip(schools, SCHOOLS_REGISTRY):
            school_topics = [t for t in topics if t.school_id == school.id]
            print(f"  - {school.code}: {len(school_topics)} 个专题")
        print(f"✓ 共创建 {len(topics)} 个专题集合")

        print("\n创建通知与举报记录（江南大学）...")
        notifications = await seed_notifications(session, schools, users_by_email, posts_by_school)
        reports = await seed_reports(session, schools, users_by_email, posts_by_school)
        print(f"✓ 创建了 {len(notifications)} 条通知")
        print(f"✓ 创建了 {len(reports)} 条举报记录")

        await session.commit()

        # 打印总结
        print("\n" + "=" * 60)
        print("✅ 三校多租户演示数据填充完成！")
        print("=" * 60)
        print("\n【三校账号清单】（密码统一 pass123）")
        for school, cfg in zip(schools, SCHOOLS_REGISTRY):
            print(f"\n  ▶ {school.name} (code={school.code})")
            for u in cfg["users"]:
                print(f"    {u['email']:40s} | {u['nickname']:15s} | {u['role']:10s} | {u['bio']}")

        print("\n【跨校成员关系】")
        for cross in CROSS_SCHOOL_MEMBERSHIPS:
            user = users_by_email.get(cross["user_email"])
            school = next((s for s in schools if s.code == cross["school_code"]), None)
            if user and school:
                primary_school = next((s for s in schools if s.id == user.school_id), None)
                print(f"  - {user.email}（主校={primary_school.code if primary_school else '?'}）"
                      f" → 加入 {school.code} ({cross['role']})")

        print("\n【演示切换说明】")
        print("  登录 user1@example.com 后，可在学校切换器中选择「江南大学」或「复旦大学」，")
        print("  切换后看到的内容/地图/角色/统计会同步变化（TEN-05.3）。")
        print("  登录 user2@example.com 后，可在学校切换器中选择「江南大学」或「浙江大学」。")

        print("\n【三校品牌差异化】")
        for school, cfg in zip(schools, SCHOOLS_REGISTRY):
            meta = cfg["meta"]
            print(f"  - {school.code}: brand_color={meta['brand_color']}, site_name='{meta['site_name']}'")


if __name__ == "__main__":
    asyncio.run(seed_data())
