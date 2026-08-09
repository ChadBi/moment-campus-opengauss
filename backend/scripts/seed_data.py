"""大规模演示数据填充脚本（三校多租户，每校50用户+500帖子）

用于开发和测试环境。

注意：本脚本不再创建表结构，需先通过 Alembic 迁移创建表：
    alembic upgrade head
脚本清空现有数据并重新填充演示数据。

三所演示学校：
- 江南大学（code=jiangnan）—— 主展示租户，无锡蠡湖校区
- 复旦大学（code=fudan）—— 演示校 A，上海邯郸校区
- 浙江大学（code=zju）—— 演示校 B，杭州紫金港校区

数据规模：
- 每校 50 用户（认证率 40%-70% 随机）
- 每校 ~500 帖子（470 published + 30 各状态样本），覆盖 5 分类
- 每个地点 ≥10 条评价
- 点赞/评论/验证真实填充，数量浮动符合幂律分布
- 内容口语化无 Markdown，真实大学生语气
- 可选自动生成 Embedding 向量
"""
import asyncio
import random
import sys
from pathlib import Path
from datetime import datetime, timedelta

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import app.db_compat  # noqa: F401, E402
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_maker, engine
from app.data.demo_coordinates import DEMO_SCHOOL_COORDINATES, location_tuples
from app.models import (
    Base, User, School, Post, Category, PostImage,
    Location, Comment, Like, ValidationRecord, Report, Notification,
    Draft, BrowseHistory, SearchHistory,
    AdminOperationLog, SchoolMembership, SchoolSettings, SchoolSubscription,
    ProductPlan, PlanEntitlement, SchoolDomain, UserAuthIdentity,
)
from app.models.location_review import LocationReview
import bcrypt

random.seed(20260809)

# =============================================================================
# 通用配置：套餐（全平台共享）
# =============================================================================

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

# =============================================================================
# 三校元数据配置
# =============================================================================

SCHOOLS_META = {
    "jiangnan": {
        "name": "江南大学",
        "code": "jiangnan",
        "province": "江苏省",
        "city": "无锡市",
        "address": "江苏省无锡市滨湖区蠡湖大道1800号",
        "center_lat": DEMO_SCHOOL_COORDINATES["jiangnan"]["center_lat"],
        "center_lng": DEMO_SCHOOL_COORDINATES["jiangnan"]["center_lng"],
        "map_zoom": 16,
        "logo_url": None,
        "brand_color": "#1B4332",
        "site_name": "此刻校园 · 江南大学",
        "description": "江南大学蠡湖校区校园信息协作平台",
        "domain": "jiangnan.edu.cn",
        "addl_domains": "stu.jiangnan.edu.cn, example.jiangnan.edu.cn",
        "phone_prefix": "139000000",
        "admin_role": "super_admin",
        "nickname_prefix": "江南",
    },
    "fudan": {
        "name": "复旦大学",
        "code": "fudan",
        "province": "上海市",
        "city": "上海市",
        "address": "上海市杨浦区邯郸路220号",
        "center_lat": DEMO_SCHOOL_COORDINATES["fudan"]["center_lat"],
        "center_lng": DEMO_SCHOOL_COORDINATES["fudan"]["center_lng"],
        "map_zoom": 16,
        "logo_url": None,
        "brand_color": "#00356B",
        "site_name": "此刻校园 · 复旦大学",
        "description": "复旦大学邯郸校区校园信息协作平台",
        "domain": "fudan.edu.cn",
        "addl_domains": "example.fudan.edu.cn",
        "phone_prefix": "139000001",
        "admin_role": "admin",
        "nickname_prefix": "复旦",
    },
    "zju": {
        "name": "浙江大学",
        "code": "zju",
        "province": "浙江省",
        "city": "杭州市",
        "address": "浙江省杭州市西湖区余杭塘路866号",
        "center_lat": DEMO_SCHOOL_COORDINATES["zju"]["center_lat"],
        "center_lng": DEMO_SCHOOL_COORDINATES["zju"]["center_lng"],
        "map_zoom": 16,
        "logo_url": None,
        "brand_color": "#003F7F",
        "site_name": "此刻校园 · 浙江大学",
        "description": "浙江大学紫金港校区校园信息协作平台",
        "domain": "zju.edu.cn",
        "addl_domains": "example.zju.edu.cn",
        "phone_prefix": "139000002",
        "admin_role": "admin",
        "nickname_prefix": "浙大",
    },
}

CATEGORIES_DATA = [
    ("分享吐槽", "share", "💬", "校园生活分享、吐槽、心得", 30, 1),
    ("组队交友", "teamup", "🤝", "组队、交友、活动搭子", 30, 2),
    ("二手交易", "trade", "💰", "二手物品买卖、赠予", 30, 3),
    ("失物招领", "lost_found", "🔍", "丢失与拾到物品信息", 30, 4),
    ("其他", "other", "📝", "其他校园信息", 30, 5),
]

# =============================================================================
# 内容素材库（真实大学生语气，无Markdown）
# =============================================================================

SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗"]
NICKNAME_SUFFIXES = [
    "今天吃什么", "不想起床", "期末抱佛脚", "天天在debug", "干饭第一名",
    "在蠡湖散步", "在图书馆", "刚下课", "想回家", "奶茶续命",
    "猫奴一枚", "摄影爱好者", "跑渣一个", "健身打卡", "熬夜冠军",
    "早八人", "选课难民", "绩点焦虑", "实习摸鱼", "考研上岸",
    "在食堂排队", "快递站常客", "睡不醒选手", "咖啡当水喝", "论文难产中",
    "羽毛球搭子", "夜跑选手", "音乐发烧友", "电影爱好者", "游戏菜鸡",
]
SPECIAL_NICKNAMES = ["蠡湖钓客", "二食堂干饭人", "图书馆常客", "江大摄影师", "流浪猫救助站", "食堂品鉴师", "无锡学长", "跑道冲刺手"]

BIOS = [
    "计院大三狗，天天在debug", "干饭不积极思想有问题", "图书馆三楼是我家",
    "每天夜跑五公里", "摄影社，用镜头记录校园", "校园流浪猫TNR志愿者",
    "靠期末两周创造奇迹", "大四老学长，有问题可以问", "爱吃辣的湖南人",
    "江浙沪包邮区选手", "北方人第一次见这么大的雪", "南方人表示冬天太冷了",
    "羽毛球约起来", "考研倒计时中", "找实习好难啊", "刚考完六级，人没了",
    "明天要pre还没做ppt", "今天也是想退学的一天", "食堂阿姨手抖受害者",
    "快递站排队半小时心态崩了", "宿舍空调什么时候能修好", "早八人早八魂",
    "求推荐附近好吃的外卖", "有没有一起拼单奶茶的", "出闲置，九成新",
    "寻物启事，校园卡丢了", "请问这个课给分怎么样", "选课选了个寂寞",
    "有没有人知道教务处电话", "宿管阿姨人真好", "图书馆占座的人能不能有点素质",
]

COLLEGES = ["计算机学院", "文学院", "理学院", "工学院", "医学院", "商学院", "法学院", "外国语学院", "艺术学院", "食品学院", "纺织学院", "化工学院", "机械学院", "电信学院", "环境学院"]

# ----- 帖子标题 -----
SHARE_TITLES = [
    "{place}的{food}真的绝了", "今天在{place}遇到的离谱事", "家人们谁懂啊，{place}也太{adj}了",
    "{place}新开的店测评", "我宣布{place}是本校最好吃的地方", "避雷！{place}的{food}难吃到吐",
    "有没有人觉得{place}的{thing}很{adj}", "今天在{place}看到一只超可爱的猫",
    "{place}的猫又胖了", "今天在{place}看到的日落绝美", "吐槽一下{place}的排队",
    "{place}的阿姨人也太好了吧", "救命，{place}的空调开了跟没开一样",
    "{place}今天的风差点把我吹走", "为什么{place}总是人满为患", "{place}的隐藏菜单",
    "在{place}学习效率真的很高", "{place}的wifi怎么这么慢", "今天在{place}社死了",
    "{place}的{thing}涨价了？", "你们去{place}一般吃什么", "强推{place}的{food}",
    "有没有人跟我一样喜欢在{place}待着", "{place}今天有活动大家知道吗",
    "{place}的花开了，超好看", "今天在{place}偶遇老师", "{place}的厕所终于修好了",
    "为什么{place}的信号这么差", "{place}附近的外卖推荐", "在{place}丢了伞有人看到吗",
    "今天{place}的人怎么这么少", "{place}的开门时间改了大家注意",
    "吐槽一下{place}的工作人员", "{place}的新装修怎么样", "在{place}背书效率超高",
    "{place}的{food}今天买一送一", "有没有人知道{place}旁边那家店搬去哪了",
    "{place}的饮水机没水了", "{place}的电梯又坏了", "爬楼爬到腿软",
]

TEAMUP_TITLES = [
    "有没有人一起{activity}", "求{activity}搭子", "明天{time}有没有人去{place}",
    "{place}{activity}组队", "期末复习组队，{place}有没有位置", "考研自习室固定搭子",
    "拼单！{thing}还差{num}个人", "社团招新啦，喜欢{thing}的来", "本周{time}在{place}有{activity}",
    "有没有人一起{activity}，我新手", "{activity}缺{num}个人，速来", "找球友，{time}在{place}",
    "一起去看{thing}吗", "讲座搭子，{time}在{place}", "有没有人想一起学{thing}",
    "组队参加{comp}比赛", "找队友打{game}", "{place}约自习，每天{time}",
    "周末{activity}有没有人一起", "饭搭子有没有，每天{time}去{place}",
    "跑步搭子，夜跑{place}一圈", "健身搭子，{time}健身房见", "一起学语言，互相监督",
    "有没有人一起准备{exam}", "论文组队，还差{num}个人", "pre组队，主题是{thing}",
    "志愿者活动招募，{time}在{place}", "社团展演，{time}在{place}欢迎来看",
    "有没有人一起做{project}项目", "找旅伴，{holiday}去{place}玩", "拼车去{place}，{time}出发",
    "一起去看展吗", "剧本杀缺{num}人，{time}在{place}", "桌游局约起来",
    "有没有人会{skill}求带", "求教学{skill}，可以请喝奶茶",
    "街舞社招新，零基础也可以", "合唱团招新，喜欢唱歌的来", "辩论队招新",
]

TRADE_TITLES = [
    "出{thing}，九成新", "{price}出{thing}", "收一个{thing}", "有没有人出{thing}",
    "换{thing}，我有{thing2}", "{thing}免费送，自取", "出电动车，{price}",
    "出教材，{book}几乎全新", "出键盘，{price}可小刀", "出显示器，27寸",
    "出闲置衣服，都是M码", "出自行车，骑了半年", "收个二手充电宝", "收台灯",
    "出床上小桌子", "出收纳盒，几个一起", "出四六级耳机", "出计算器，卡西欧的",
    "出考研资料，学长学姐整理的", "出宿舍神器，{thing}", "出吹风机，功率小不跳闸",
    "出哑铃，一对{weight}kg", "出瑜伽垫，几乎没用过", "出滑板，双翘",
    "出吉他，入门款", "出口红，色号{color}仅试色", "出化妆品，囤多了",
    "出零食，买多了吃不完", "出雨伞，全新的", "出暖宝宝，冬天必备",
    "出小电锅，不跳闸的那种", "出加湿器，宿舍用", "出风扇，夏天救命",
    "出书立，桌面收纳用", "出椅子坐垫，久坐舒服", "出耳机，有线的",
    "出鼠标，无线的", "出电脑包，15.6寸", "出书包，容量大", "出杯子，保温杯",
    "{thing}已出谢谢大家",
]

LOST_FOUND_TITLES = [
    "在{place}丢了{thing}", "丢了校园卡，尾号{num}", "有没有人看到{thing}",
    "寻物启事，{color}色的{thing}", "{place}捡到{thing}，失主联系我",
    "在{place}捡到一串钥匙", "在{place}捡到U盘", "在{place}捡到耳机，{color}的",
    "在{place}捡到一把伞", "在{place}捡到校园卡，名字是{name}",
    "丢了耳机，AirPods Pro", "丢了水杯，{color}色的", "丢了课本，{book}",
    "丢了充电宝，{color}的", "丢了眼镜，黑框的", "丢了钱包，黑色的",
    "丢了身份证，尾号{num}", "丢了钥匙串上面有个{thing}挂件",
    "在{place}捡到饭卡", "在{place}捡到笔袋", "在{place}捡到手套",
    "在{place}捡到围巾，{color}色的", "在{place}捡到帽子", "失物招领：{thing}",
    "求扩散，在{place}丢了很重要的东西", "捡到的{thing}放在{place}服务台了",
]

OTHER_TITLES = [
    "{place}开放时间", "{place}怎么预约", "请问{place}怎么走", "校车时刻表最新版",
    "{place}的电话是多少", "宿舍报修流程", "校园网怎么连", "医保怎么报销",
    "成绩单在哪里打印", "补办校园卡要多久", "图书馆借书规则", "体育馆怎么预约",
    "{place}晚上几点关门", "学校附近哪里可以打印", "学校附近的理发店推荐",
    "学校附近的药店在哪", "校医院上班时间", "取快递要带什么", "{place}可以带外卖吗",
    "宿舍可以用小锅吗", "宿舍几点断电", "热水供应时间", "洗衣机怎么用",
    "空调怎么开，要充钱吗", "校园卡怎么充值", "洗澡怎么扣费", "网费多少钱一个月",
    "奖学金什么时候发", "助学金怎么申请", "选课系统怎么进", "补考时间一般是什么时候",
    "缓考怎么申请", "休学流程", "转专业要求", "双学位怎么修", "交换生项目怎么申请",
    "实习证明怎么开", "报到证怎么办", "三方协议是什么", "答辩一般问什么问题",
    "毕业论文格式要求", "学校心理咨询在哪", "校医院可以看什么病",
]

POST_TITLES = {
    "share": SHARE_TITLES,
    "teamup": TEAMUP_TITLES,
    "trade": TRADE_TITLES,
    "lost_found": LOST_FOUND_TITLES,
    "other": OTHER_TITLES,
}

# ----- 帖子正文 -----
FOODS = ["麻辣香锅", "黄焖鸡", "麻辣烫", "螺蛳粉", "手抓饼", "煎饼果子", "石锅拌饭", "兰州拉面", "沙县小吃", "盖浇饭", "酸菜鱼", "烤肉饭", "脆皮鸡饭", "瓦香鸡", "米线", "面馆", "包子铺", "豆浆油条", "汉堡薯条", "炸鸡", "奶茶", "咖啡"]
ADJECTIVES = ["好吃", "难吃", "坑", "赞", "绝", "离谱", "贵", "便宜", "挤", "空", "吵", "安静", "冷", "热", "香", "臭", "慢", "快", "好", "差"]
THINGS = ["书", "电脑", "手机", "耳机", "充电器", "充电宝", "伞", "钥匙", "水杯", "笔", "本子", "书包", "衣服", "鞋子", "快递", "外卖", "奶茶", "咖啡", "水果", "零食"]
ACTIVITIES = ["打羽毛球", "打乒乓球", "打篮球", "踢足球", "跑步", "健身", "自习", "看电影", "吃火锅", "唱K", "玩剧本杀", "玩桌游", "拍照", "逛超市", "去市区", "爬山", "骑行", "游泳", "跳舞", "画画"]
TIMES = ["早上8点", "中午12点", "下午2点", "晚上7点", "周末", "周五晚上", "周六下午", "下周一", "明天", "后天"]
NUMS = ["1", "2", "3", "一", "两", "三"]
COLORS = ["黑", "白", "红", "蓝", "绿", "黄", "粉", "紫", "灰"]
PRICES = ["50", "100", "150", "200", "300", "500"]
BOOKS = ["高数", "线代", "概率论", "大英", "大物", "C语言", "Java", "数据结构"]
NAMES = ["张三", "李四", "同学", "一个女生", "一个男生"]
COMPS = ["互联网+", "挑战杯", "数学建模", "ACM", "英语竞赛"]
GAMES = ["王者", "LOL", "原神", "星穹铁道", "CS2", "Valorant"]
EXAMS = ["四六级", "考研", "考公", "雅思", "托福", "计算机二级"]
HOLIDAYS = ["国庆", "五一", "清明", "端午", "中秋", "元旦"]
SKILLS = ["PS", "PR", "Python", "摄影", "剪辑", "吉他", "钢琴", "画画", "跳舞", "游泳"]
PROJECTS = ["大创", "科研立项", "课程设计", "毕业设计"]
WEIGHTS = ["5", "10", "15", "20"]

def fill_template(template: str, place: str) -> str:
    result = template
    result = result.replace("{place}", place)
    result = result.replace("{food}", random.choice(FOODS))
    result = result.replace("{adj}", random.choice(ADJECTIVES))
    result = result.replace("{thing}", random.choice(THINGS))
    result = result.replace("{thing2}", random.choice(THINGS))
    result = result.replace("{activity}", random.choice(ACTIVITIES))
    result = result.replace("{time}", random.choice(TIMES))
    result = result.replace("{num}", random.choice(NUMS))
    result = result.replace("{color}", random.choice(COLORS))
    result = result.replace("{price}", random.choice(PRICES))
    result = result.replace("{book}", random.choice(BOOKS))
    result = result.replace("{name}", random.choice(NAMES))
    result = result.replace("{comp}", random.choice(COMPS))
    result = result.replace("{game}", random.choice(GAMES))
    result = result.replace("{exam}", random.choice(EXAMS))
    result = result.replace("{holiday}", random.choice(HOLIDAYS))
    result = result.replace("{skill}", random.choice(SKILLS))
    result = result.replace("{project}", random.choice(PROJECTS))
    result = result.replace("{weight}", random.choice(WEIGHTS))
    return result

SHARE_CONTENTS = [
    "今天去吃了，真的绝\n分量很足，价格也不贵\n推荐大家去试试\n就是人有点多要排队",
    "家人们避雷啊\n难吃到我怀疑人生\n不知道为什么还有那么多人去\n可能是我口味问题吧",
    "哈哈哈哈今天遇到个离谱的事\n在那学习呢，旁边情侣吵架\n吵了半小时，我题都做不进去了",
    "有没有人知道为什么最近\n那个地方人突然变多了\n以前都没什么人的\n现在去都找不到位置",
    "今天的天也太好看了吧\n在那里拍了好多照片\n原相机直出都不用P\n朋友圈发了好多人问在哪拍的",
    "真的会谢\n排队排了四十分钟\n结果告诉我卖完了\n我真的会生气",
    "阿姨人也太好了吧\n我随口说了一句多加点饭\n阿姨给我打了满满一盒\n感动哭了",
    "谁懂啊，这个空调\n开了跟没开一样\n坐在里面还是满头汗\n能不能修修啊",
    "今天风好大\n走在路上伞都差点吹飞了\n大家出门注意安全",
    "我宣布这是本校最好吃的\n不接受反驳\n吃了一学期了还没吃腻\n每周都要去个两三次",
    "新开的店去试了\n味道一般般吧\n价格倒是不便宜\n不会再去第二次了",
    "那只猫又胖了\n每次去都在那睡觉\n喂它肠也不吃\n可能是被喂太饱了",
    "今天社死了\n在那摔了一跤\n周围全是人\n假装镇定爬起来就走\n希望没人认识我",
    "涨价了？之前还没这么贵\n现在随便吃吃都要二十多\n生活费要不够用了",
    "隐藏菜单！一般人我不告诉他\n点单的时候说要那个\n阿姨就知道了\n巨好吃",
    "wifi慢得要死\n刷个朋友圈都刷不出来\n还不如用自己流量\n希望能改进一下",
    "厕所终于修好了\n之前坏了快一周了\n跑上跑下的太不方便了",
    "信号真的差\n在里面扫码都扫半天\n付个款急死人",
    "今天人怎么这么少\n以前这个点都坐满了\n难道大家都出去玩了",
    "花开了真的超好看\n大家有空可以去看看\n拍照很出片\n就是人有点多",
]

TEAMUP_CONTENTS = [
    "有没有人一起啊\n我一个人有点社恐\n最好是女生\n新手也没关系我也菜",
    "求求了来个搭子吧\n每次一个人去好无聊\n最好是固定时间\n我每天都有空",
    "还差两个人\n有没有想一起的\n费用AA\n人多好玩一点",
    "零基础也可以\n我也是新手\n大家一起进步\n有兴趣的评论区dd",
    "本周活动，欢迎大家来\n不用报名直接来就行\n有小礼品送\n来了不亏",
    "时间定在明天下午\n地点在那里\n有问题可以私信我\n看到会回复",
    "有没有人一起拼单\n还差一个人就可以满减\n拼的话人均便宜不少\n要的速来",
    "社团招新啦\n不管有没有基础都可以来\n我们社团氛围超好\n定期有活动",
    "求大佬带带\n我是新手什么都不会\n可以请喝奶茶\n求求了",
    "考研找固定自习搭子\n每天早八晚十\n互相监督不摸鱼\n希望能坚持到最后",
    "饭搭子有没有\n每天中午一起吃饭\n一个人吃饭太没意思了\n口味差不多的来",
    "夜跑搭子\n每天晚上九点左右\n跑个三五公里\n配速六分左右就行",
    "组队参加比赛\n现在还差两个人\n最好会编程或者美工\n有经验的优先",
    "周末一起去玩吧\n我做攻略\nAA制\n有没有一起的",
    "剧本杀缺人\n有没有想玩的\n本已经选好了\n就差人了",
    "一起学英语吧\n每天背单词打卡\n互相监督\n争取这次六级过了",
    "有没有人会PS啊\n能不能教教我\n可以请喝奶茶或者吃饭\n真的很需要",
    "志愿者活动招募\n周末两天\n有志愿时长\n想去的私信我",
    "拼车去机场\n有没有同一航班的\n一起拼车省钱\n时间是下周五早上",
    "约自习\n每天都去图书馆\n不想一个人\n最好是同专业的可以讨论问题",
]

TRADE_CONTENTS = [
    "九成新，买了没用过几次\n因为要毕业了带不走\n便宜出\n想要的私信我看细节图",
    "价格可小刀\n屠龙刀就别来了\n东西没问题\n当面交易或者自提",
    "毕业清闲置\n好多东西带不走\n便宜出\n买多可以送小礼物",
    "功能都正常\n没有损坏\n就是用不上了\n放着也是浪费\n转给有需要的人",
    "收一个这个\n有没有学长学姐出的\n价格好商量\n最好是成色好一点的",
    "免费送，自取\n在宿舍楼下\n要的直接来拿\n先到先得",
    "电动车出\n骑了一年\n电池还很耐用\n续航三十公里左右\n价格可以谈",
    "教材出\n几乎全新没写过字\n几块钱一本\n买多送资料",
    "出键盘\n红轴的\n手感很好\n换了新的所以出掉\n包装还在",
    "出显示器\n27寸1080p\n没有坏点\n色彩正常\n自提优先",
    "衣服都是M码\n只穿过一两次\n洗干净了\n款式都是比较基础的",
    "自行车出\n骑了半年\n没什么问题\n锁和车灯都送",
    "收个充电宝\n容量大点的\n最好是20000毫安的\n价格合理就行",
    "考研资料出\n都是自己整理的\n还有历年真题\n很全\n学弟学妹需要的私",
    "出小电锅\n功率小不会跳闸\n煮泡面火锅都可以\n毕业带不走",
    "已出谢谢大家\n麻烦管理员删帖",
    "东西还在\n想要的直接私信\n看到会回\n评论区不回",
    "可以换物\n我想要那个\n等价交换也行\n看看有没有人换",
    "不单出\n几个一起打包\n打包价更便宜\n单买不划算",
    "刚买的，拆封了没用\n发现买错了\n退不了\n便宜出",
]

LOST_FOUND_CONTENTS = [
    "今天下午在那里丢的\n有捡到的同学麻烦联系我\n真的很重要\n请吃饭感谢",
    "丢了，尾号是xxxx\n有捡到的放在服务台就好\n或者私信我\n非常感谢",
    "是颜色的\n上面有个小挂件\n有看到的麻烦说一声\n找了一上午了",
    "在那里捡到的\n失主看到私信我\n描述一下特征就给你\n我在原地等了一会没人来",
    "捡到一串钥匙\n上面有个挂件\n失主看到联系我\n我会放在宿舍楼下阿姨那里",
    "今天中午在那吃饭\n走的时候忘了拿\n回去找已经不在了\n有没有人看到啊",
    "耳机丢了，是AirPods\n仓上有贴纸\n捡到的同学求求了\n那是我攒了好久钱买的",
    "捡到一个U盘\n银色的32G\n里面有很多学习资料\n失主看到联系我\n我给你送到宿舍",
    "校园卡丢了\n名字是两个字的\n有捡到的麻烦联系我\n补办太麻烦了",
    "雨伞丢了\n是颜色的自动伞\n伞柄那里有点磨损\n有看到的麻烦说一声",
    "身份证丢了\n尾号xxxx\n下星期要考试要用\n有捡到的万分感谢",
    "捡到一本课本\n名字写在扉页了\n失主看到私信我\n我给你放教室讲台上",
    "水杯丢了\n颜色的保温杯\n杯身上有贴纸\n有捡到的麻烦联系我\n用了好久挺有感情的",
    "在那捡到一副手套\n是毛线的\n应该是女生的\n天这么冷丢手套的人肯定着急",
    "围巾丢了\n手织的\n对我很重要\n有捡到的麻烦联系我\n一定重谢",
    "放在那里的书包不见了\n里面没什么贵重东西\n就是有几本课本\n有人拿错了吗",
    "捡到一张校园卡\n已经交给服务台了\n失主去那里拿就行\n不用找我了",
    "钥匙丢了\n上面有个小玩偶\n还有宿舍钥匙\n现在进不去门了\n有捡到的救救孩子",
    "求扩散啊\n在那里丢了很重要的东西\n里面有我的毕业论文\n捡到的我请喝一周奶茶",
    "是我捡到的\n放在服务台了\n你可以去拿\n顺便说一下那个东西真可爱",
]

OTHER_CONTENTS = [
    "有没有人知道几点开门\n想去但是怕跑空\n知道的同学说一声\n谢谢了",
    "怎么预约啊\n看了半天没找到入口\n有没有操作过的同学\n教一下流程",
    "请问怎么走\n我是新生不太认识路\n从这里过去要多久\n有没有近路",
    "最新校车时刻表\n存一下别错过了\n末班车是几点\n别像我上次等了半小时",
    "电话是多少啊\n有急事想打电话问\n官网找了半天没找到\n有知道的吗",
    "宿舍报修是在哪个系统\n我们宿舍空调坏了\n热得睡不着\n有没有人知道流程",
    "校园网怎么连啊\n我连不上\n输入密码也不行\n有没有人知道怎么弄",
    "医保怎么报销啊\n去校医院看了病\n要带什么材料\n去哪里报销",
    "成绩单在哪里打印\n是自助打印机吗\n在几楼\n需要带校园卡吗",
    "补办校园卡要多久\n卡丢了\n补办要多少钱\n里面的钱还在吗",
    "图书馆借书最多借多久\n超期了怎么罚款\n可以续借吗\n最多续几次",
    "体育馆怎么预约场地\n想打羽毛球\n提前几天预约\n一个小时多少钱",
    "晚上几点关门啊\n想去赶作业\n怕去了关门了\n知道的同学说一下",
    "学校附近哪里可以打印\n打印便宜点的\n打印毕业论文\n大概多少钱一张",
    "附近有没有好一点的理发店\n想剪头发不要太贵\n不要那种一直让办卡的",
    "附近的药店在哪\n想买点感冒药\n最近的有多远\n可以刷医保吗",
    "校医院上班时间是几点\n周末开门吗\n晚上有急诊吗\n发烧了想去看看",
    "取快递要带什么\n一定要带身份证吗\n校园卡行不行\n可以代取吗",
    "宿舍可以用小锅吗\n功率多大不会跳闸\n想煮点泡面吃\n有没有推荐的锅",
    "宿舍几点断电啊\n周末断不断电\n夏天不断电吧\n空调可以一直开吗",
    "热水供应时间是几点到几点\n早上几点有热水\n晚上几点停\n错过时间就没热水了吗",
    "洗衣机怎么用\n一次多少钱\n要自己放洗衣液吗\n多久能洗好",
    "空调怎么开啊\n要充钱吗\n怎么充值\n电费多少钱一度",
    "校园卡怎么充值\n只能在食堂充吗\n手机上可以充吗\n充了多久到账",
    "奖学金什么时候发啊\n等了好久了\n是打在校园卡里吗\n还是银行卡里",
]

POST_CONTENTS = {
    "share": SHARE_CONTENTS,
    "teamup": TEAMUP_CONTENTS,
    "trade": TRADE_CONTENTS,
    "lost_found": LOST_FOUND_CONTENTS,
    "other": OTHER_CONTENTS,
}

# ----- 评论 -----
SHORT_COMMENTS = [
    "哈哈哈哈", "真的假的", "我也遇到过", "救命", "dd", "笑死", "确实", "同感",
    "啊这", "离谱", "绝了", "好耶", "哭了", "麻了", "冲", "蹲一个", "mark",
    "同问", "帮顶", "up", "懂", "我也想知道", "真的吗", "好的谢谢", "收到",
]

QUESTION_COMMENTS = [
    "多少钱啊", "在哪个位置", "还有吗", "求私", "怎么联系", "现在还有吗",
    "男生可以吗", "新手可以吗", "什么时候", "在哪里面交", "需要带什么",
    "人够了吗", "还缺人吗", "可以小刀吗", "自提在哪", "能送吗",
]

REPLY_COMMENTS = [
    "楼上说得对", "我昨天刚去过，确实", "已经出了哦", "私信你了",
    "好的好的", "收到谢谢", "同蹲", "我也想去", "加一", "算我一个",
    "联系方式私你了", "看私信", "还有的", "可以的", "没问题",
    "不好意思已经出了", "下次一定", "哈哈哈哈我也觉得", "真的绝",
    "确实坑", "我也被坑过", "避雷了", "谢谢推荐", "明天去试试",
]

REFUTATION_COMMENTS = [
    "不好吃别去", "早就修好了", "假的吧", "已经关门了", "涨价了现在更贵",
    "人没那么多啊", "没你说的那么夸张", "我觉得还行", "看个人口味吧",
    "现在不一样了", "过期了", "活动结束了", "已经招满了", "出掉了",
]

VALIDATION_COMMENTS = [
    "今天去看了是真的", "亲测有效", "确实好吃", "我也买了", "去过了不错",
    "真的坑", "已经过期了", "信息不准", "现在修好了", "活动确实有",
    "人真的很多", "排队排了好久", "味道一般", "阿姨确实给得多",
]

REVIEW_COMMENTS = {
    "食堂": [
        "味道还可以，价格实惠，就是中午人太多了要排队",
        "二楼的麻辣香锅yyds，每周都要吃好几次",
        "阿姨手抖真的名不虚传，每次肉都给得少",
        "早餐种类挺多的，豆浆油条包子都有，就是有点油",
        "性价比还行，一荤一素十块钱左右能吃饱",
        "高峰期人真的太多了，建议错峰去",
        "味道中规中矩吧，吃久了都一样，想念家里的饭",
        "新出的那个菜还不错，可以试试",
        "餐具有时候洗不干净，希望能改进一下",
        "打饭速度挺快的，不用排太久",
    ],
    "图书馆": [
        "环境很安静，插座也多，学习氛围很好",
        "期末的时候人真的太多了，早上七点去都没位置",
        "空调开得很足，夏天去要带件外套",
        "借书还书都很方便，自助机操作很快",
        "三楼自习室氛围最好，大家都在认真学习",
        "占座的人真的很烦，放本书人就不见了",
        "WiFi速度还行，查资料没问题",
        "饮水机在楼梯口，接水很方便",
        "闭馆音乐很好听，每次听到就知道该走了",
        "考研党常驻，大家都很自觉不说话",
    ],
    "公寓": [
        "宿舍条件还行，四人间有独卫，就是没空调夏天热",
        "热水供应时间有点短，晚上回去晚了就没热水了",
        "洗衣机经常坏，而且有人洗鞋真的无语",
        "宿管阿姨人很好，平时有问题找她都能解决",
        "晚上不断电不断网，这点还不错",
        "阳台晒衣服很方便，就是阴天干不了",
        "宿舍限电，大功率电器用不了会跳闸",
        "楼道卫生阿姨每天打扫，挺干净的",
        "快递柜就在楼下，取快递很方便",
        "晚上门禁是十一点，回来晚了要登记",
    ],
    "快递": [
        "饭点取件人真的太多了，排队排半小时",
        "营业时间挺长的，晚上九点才关门",
        "工作人员态度还可以，就是有时候找件慢",
        "快递多的时候爆仓，找件找半天",
        "发错短信的情况偶尔有，不过很快能解决",
        "可以代取，但是要带身份证复印件",
        "大件要去里面找，有点麻烦",
        "双十一期间真的人挤人，建议错峰取",
        "出库很快，扫个码就行",
        "离宿舍很近，取件很方便",
    ],
    "体育场": [
        "场地还行，跑道是塑胶的，跑着挺舒服",
        "晚上人很多，散步的跑步的踢球的都有",
        "篮球场晚上有灯，打到九点多没问题",
        "足球场草皮质量一般，有时候会有坑",
        "羽毛球馆要预约，周末人特别多",
        "游泳馆夏天人很多，跟下饺子一样",
        "健身房器材挺全的，就是有点旧",
        "早上人少，适合晨跑",
        "乒乓球台在室内，不用晒太阳",
        "晚上有灯，跑步视线没问题",
    ],
    "门": [
        "门口共享单车很多，出行很方便",
        "出去就是地铁站，交通便利",
        "保安查证件挺严的，安全有保障",
        "门口小吃摊很多，晚上特别热闹",
        "打车定位这里很方便，司机都知道",
        "门口有公交站，去市区很方便",
        "进出都要刷校园卡，外人进不来",
        "旁边有便利店，买东西很方便",
        "晚上门禁之后回来要登记",
        "门口有共享单车停车点，很方便",
    ],
    "教学楼": [
        "教室挺多的，找空教室自习很方便",
        "多媒体设备有时候会坏，上课前要试一下",
        "空调有的教室冷有的教室热，看运气",
        "电梯上下课高峰期挤不进去，只能爬楼",
        "卫生间很干净，有纸挺好的",
        "走廊里可以背书，很多考研的在那",
        "教室插座不多，带电脑要找位置",
        "桌椅有的有点晃，希望能修修",
        "楼里有自助贩卖机，买水很方便",
        "保洁阿姨打扫得很干净",
    ],
    "超市": [
        "东西挺全的，日常用品都能买到",
        "价格比外面稍微贵一点，但方便",
        "晚上十点关门，去晚了就买不到了",
        "零食种类很多，追剧必备",
        "水果有点贵，而且不太新鲜",
        "可以刷校园卡，也可以手机支付",
        "日用品区在二楼，第一次去有点难找",
        "开学的时候人特别多，结账排队",
        "有打印的地方，打印资料很方便",
        "经常有促销活动，打折的时候很划算",
    ],
    "活动中心": [
        "社团活动基本都在这里，很热闹",
        "报告厅挺大的，办讲座够用",
        "排练室要预约，乐队跳舞的都在那",
        "大厅经常有摆摊活动",
        "会议室可以借，办小组讨论很方便",
        "一楼有咖啡厅，谈事情可以去",
        "周末活动特别多，很有氛围",
        "设备挺全的，音响投影都有",
        "后台有化妆间，演出很方便",
        "暖气开得很足，冬天去很舒服",
    ],
    "科学馆": [
        "讲座经常在这里办，场地很大",
        "报告厅座位很舒服，看演出体验很好",
        "建筑很有年代感，拍照好看",
        "门口的广场经常有活动",
        "音响效果不错，看话剧很过瘾",
        "空调很足，夏天去有点冷",
        "位置有点偏，第一次去不好找",
        "周边停车位不多，建议步行去",
        "经常有免费演出，有空可以去看看",
        "散场的时候人很多，建议提前走",
    ],
    "湖畔": [
        "风景很好，散步很舒服",
        "傍晚看日落绝美，拍照很出片",
        "有黑天鹅，很可爱，不要喂人吃的东西",
        "晚上情侣很多，单身狗慎去",
        "春天柳树发芽的时候特别好看",
        "有长椅可以坐，背书聊天都不错",
        "夏天蚊子有点多，记得带花露水",
        "绕湖一圈大概两公里，跑步刚刚好",
        "冬天风大，有点冷",
        "早上有老人在那打太极，很有生活气息",
    ],
    "打印": [
        "价格便宜，黑白一毛一张",
        "老板人很好，排版问题都会帮忙调",
        "可以微信传文件，很方便",
        "打印毕业论文可以胶装，质量不错",
        "期末的时候人很多，要排队",
        "彩打一块钱一张，质量还可以",
        "营业时间长，晚上九点多才关门",
        "可以打印照片，就是有点贵",
        "老板技术很好，PDF有问题都能解决",
        "量大可以优惠，打印复习资料很划算",
    ],
}

GENERIC_REVIEWS = [
    "还不错，挺方便的",
    "一般般吧，没什么特别的",
    "挺好的，经常去",
    "位置好找，服务态度不错",
    "中规中矩，符合预期",
    "环境还行，就是人多的时候有点挤",
    "性价比可以，推荐",
    "体验不错，下次还来",
    "有点小问题，但是不影响使用",
    "整体满意，希望能继续保持",
]

# =============================================================================
# 工具函数
# =============================================================================

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def generate_nickname(school_code: str, idx: int) -> str:
    if idx < len(SPECIAL_NICKNAMES) and school_code == "jiangnan":
        return SPECIAL_NICKNAMES[idx]
    if random.random() < 0.3:
        return random.choice(SURNAMES) + "同学"
    return random.choice(SURNAMES) + random.choice(NICKNAME_SUFFIXES)


def generate_bio() -> str:
    if random.random() < 0.4:
        return random.choice(COLLEGES) + " | " + random.choice(NICKNAME_SUFFIXES)
    return random.choice(BIOS)


# =============================================================================
# 数据库初始化
# =============================================================================

async def init_db():
    """清空所有现有数据（保留表结构）"""
    tables = [
        "reports",
        "validation_records",
        "likes",
        "comments",
        "post_images",
        "posts",
        "topic_collection_posts",
        "topic_collections",
        "notifications",
        "search_histories",
        "browse_histories",
        "drafts",
        "notification_preferences",
        "user_recommendation_preferences",
        "subscriptions",
        "password_reset_tokens",
        "campus_verify_tokens",
        "sms_verifications",
        "binding_tickets",
        "auth_sessions",
        "user_auth_identities",
        "admin_operation_logs",
        "platform_audit_logs",
        "product_events",
        "ai_invocation_logs",
        "job_run_records",
        "tenant_usage_daily",
        "location_reviews",
        "locations",
        "categories",
        "school_subscriptions",
        "school_memberships",
        "school_domains",
        "school_settings",
        "plan_entitlements",
        "product_plans",
        "users",
        "schools",
    ]
    table_list = ", ".join(tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {table_list} CASCADE;"))
        for table_name in tables:
            try:
                await conn.execute(text(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH 1;"))
            except Exception:
                pass


# =============================================================================
# 基础数据种子
# =============================================================================

async def seed_plans(session: AsyncSession):
    now = datetime.now()
    plans = []
    for p in PLANS_DATA:
        plan = ProductPlan(
            code=p["code"], name=p["name"], description=p["description"],
            status="active", sort_order=p["sort_order"], created_at=now, updated_at=now,
        )
        session.add(plan)
        plans.append(plan)
    await session.flush()

    for plan, p in zip(plans, PLANS_DATA):
        for key, limit_value, is_hard in p["entitlements"]:
            session.add(PlanEntitlement(
                plan_id=plan.id, key=key, limit_value=limit_value, is_hard=is_hard,
                description=f"{p['name']} - {key}", created_at=now, updated_at=now,
            ))
    await session.flush()
    return plans


async def seed_schools(session: AsyncSession):
    now = datetime.now()
    schools = []
    school_by_code = {}
    for meta in SCHOOLS_META.values():
        school = School(
            name=meta["name"], code=meta["code"], province=meta["province"], city=meta["city"],
            address=meta["address"], center_lat=meta["center_lat"], center_lng=meta["center_lng"],
            map_zoom=meta["map_zoom"], logo_url=meta["logo_url"], is_active=True,
            created_at=now, updated_at=now,
        )
        session.add(school)
        schools.append(school)
        school_by_code[meta["code"]] = school
    await session.flush()

    for meta in SCHOOLS_META.values():
        school = school_by_code[meta["code"]]
        domain_list = [meta["domain"].strip()]
        addl = meta.get("addl_domains", "")
        if addl:
            domain_list.extend([d.strip() for d in addl.split(",") if d.strip()])
        for i, d in enumerate(domain_list):
            session.add(SchoolDomain(
                school_id=school.id, domain=d, is_primary=(i == 0),
                created_at=now, updated_at=now,
            ))
    await session.flush()
    return schools, school_by_code


async def seed_school_settings(session: AsyncSession, schools: list, school_by_code: dict):
    now = datetime.now()
    for school in schools:
        meta = SCHOOLS_META[school.code]
        session.add(SchoolSettings(
            school_id=school.id, site_name=meta["site_name"], description=meta["description"],
            require_review=True, allow_anonymous=True, allow_comments=True,
            publish_frequency=10, image_limit=9, default_validity_days=30,
            brand_color=meta["brand_color"], logo_url=meta["logo_url"],
            created_at=now, updated_at=now,
        ))
    await session.flush()


async def seed_subscriptions(session: AsyncSession, schools: list, plans: list, admin_user: User):
    now = datetime.now()
    operations_plan = next((p for p in plans if p.code == "operations"), plans[-1])
    for school in schools:
        session.add(SchoolSubscription(
            school_id=school.id, plan_id=operations_plan.id, status="active",
            started_at=now, expires_at=None, assigned_by=admin_user.id, assigned_at=now,
            note="大规模演示数据：自动分配运营档套餐", created_at=now, updated_at=now,
        ))
    await session.flush()


async def seed_categories(session: AsyncSession, schools: list):
    now = datetime.now()
    categories_by_school = {}
    for school in schools:
        cats = []
        for name, code, icon, desc, days, sort in CATEGORIES_DATA:
            cat = Category(
                school_id=school.id, name=name, code=code, icon=icon, description=desc,
                default_validity_days=days, sort_order=sort, is_active=True,
                created_at=now, updated_at=now,
            )
            session.add(cat)
            cats.append(cat)
        categories_by_school[school.code] = cats
    await session.flush()
    return categories_by_school


async def seed_locations(session: AsyncSession, schools: list, school_by_code: dict):
    now = datetime.now()
    locations_by_school = {}
    for school in schools:
        locs = []
        for name, lat, lng, desc in location_tuples(school.code):
            loc = Location(
                school_id=school.id, name=name, description=desc, latitude=lat, longitude=lng,
                post_count=0, avg_score=0.0, rating_count=0, review_count=0,
                is_verified=True, created_at=now, updated_at=now,
            )
            session.add(loc)
            locs.append(loc)
        locations_by_school[school.code] = locs
    await session.flush()
    return locations_by_school


# =============================================================================
# 用户生成
# =============================================================================

async def seed_users(session: AsyncSession, schools: list, school_by_code: dict):
    now = datetime.now()
    users_by_school = {}
    users_by_phone = {}

    # 预置演示账号配置
    preset_users = {
        "jiangnan": [
            {"seq": 0, "nickname": "江南大学运营组", "role": "admin",
             "bio": "江南大学此刻校园运营组", "campus_verified": False, "password": "pass123"},
            {"seq": 1, "nickname": "校园运营组", "role": "super_admin",
             "bio": "此刻校园平台运营组", "campus_verified": False, "password": "pass123"},
            {"seq": 2, "nickname": "江南小李", "role": "user",
             "bio": "计算机学院大三", "campus_verified": True, "password": "pass123"},
            {"seq": 4, "nickname": "食堂品鉴师", "role": "user",
             "bio": "吃过江南大学所有食堂", "campus_verified": True, "password": "pass123"},
            {"seq": 5, "nickname": "图书馆常客", "role": "user",
             "bio": "图书馆三楼是我家", "campus_verified": True, "password": "pass123"},
            {"seq": 7, "nickname": "二食堂干饭人", "role": "user",
             "bio": "干饭不积极思想有问题", "campus_verified": True, "password": "pass123"},
            {"seq": 8, "nickname": "江大摄影师", "role": "user",
             "bio": "用镜头记录蠡湖四季", "campus_verified": True, "password": "pass123"},
            {"seq": 10, "nickname": "期末突击队", "role": "user",
             "bio": "靠期末两周创造奇迹", "campus_verified": True, "password": "pass123"},
            {"seq": 11, "nickname": "无锡学长", "role": "user",
             "bio": "大四老学长", "campus_verified": True, "password": "pass123"},
            {"phone": "138******00", "nickname": "微信演示用户", "role": "user",
             "bio": "微信授权手机号登录演示", "campus_verified": False, "password": None,
             "auth_mode": "wechat", "wechat_openid": "MOCK_OPENID_STATIC_20260808_LOCAL_DEV"},
        ],
        "fudan": [
            {"seq": 1, "nickname": "复旦运营组", "role": "admin",
             "bio": "复旦此刻校园运营组", "campus_verified": False, "password": "pass123"},
            {"seq": 2, "nickname": "邯郸路书虫", "role": "user",
             "bio": "文科图书馆常客", "campus_verified": True, "password": "pass123"},
            {"seq": 3, "nickname": "光华楼守夜人", "role": "user",
             "bio": "光华楼自习室常驻", "campus_verified": True, "password": "pass123"},
            {"seq": 5, "nickname": "相辉堂常客", "role": "user",
             "bio": "校园话剧爱好者", "campus_verified": True, "password": "pass123"},
        ],
        "zju": [
            {"seq": 1, "nickname": "浙大运营组", "role": "admin",
             "bio": "浙大此刻校园运营组", "campus_verified": False, "password": "pass123"},
            {"seq": 2, "nickname": "紫金港学子", "role": "user",
             "bio": "计算机学院", "campus_verified": True, "password": "pass123"},
            {"seq": 4, "nickname": "西区干饭人", "role": "user",
             "bio": "西区食堂常客", "campus_verified": True, "password": "pass123"},
            {"seq": 5, "nickname": "图书馆守门人", "role": "user",
             "bio": "图书馆是我家", "campus_verified": True, "password": "pass123"},
        ],
    }

    admin_user = None
    for school in schools:
        meta = SCHOOLS_META[school.code]
        users = []
        preset = preset_users.get(school.code, [])
        # 预计算预置用户手机号集合
        preset_phones = set()
        for u in preset:
            if "seq" in u:
                preset_phones.add(f"{meta['phone_prefix']}{u['seq']:02d}")
            else:
                preset_phones.add(u["phone"])
        used_emails = set()

        # 添加预置用户
        for u in preset:
            campus_verified = u.get("campus_verified", False)
            password = u.get("password", "pass123")
            # 动态生成手机号：优先用seq + phone_prefix，微信演示用户直接用phone
            if "seq" in u:
                seq = u["seq"]
                phone = f"{meta['phone_prefix']}{seq:02d}"
            else:
                phone = u["phone"]
                seq = int(phone[-2:])
            # 统一邮箱格式避免冲突
            if campus_verified:
                education_email = f"{school.code}_u{seq}@example.{school.code}.edu.cn"
            else:
                education_email = None
            if education_email:
                used_emails.add(education_email)

            user = User(
                email=None, phone=phone, education_email=education_email,
                nickname=u["nickname"], password_hash=get_password_hash(password) if password else None,
                avatar_url=None, school_id=school.id, registration_school_id=school.id,
                role=u["role"], bio=u["bio"], is_active=True,
                onboarding_completed=True, campus_verified=campus_verified,
                campus_verified_at=now if campus_verified else None,
                created_at=now, updated_at=now,
            )
            session.add(user)
            await session.flush()
            users.append(user)
            users_by_phone[phone] = user
            if u["role"] == "super_admin" and admin_user is None:
                admin_user = user
            if u.get("auth_mode") == "wechat":
                session.add(UserAuthIdentity(
                    user_id=user.id, identity_type="wechat_miniprogram",
                    identity_key=u["wechat_openid"], openid=u["wechat_openid"],
                    unionid=None, last_used_at=now,
                ))

        # 生成剩余用户凑够50人
        target_count = 50
        next_seq = 1
        while len(users) < target_count:
            phone = f"{meta['phone_prefix']}{next_seq:02d}"
            while phone in preset_phones or phone in users_by_phone:
                next_seq += 1
                phone = f"{meta['phone_prefix']}{next_seq:02d}"

            campus_verified = random.random() < 0.55  # 约55%认证率
            education_email = f"{school.code}_u{next_seq}@example.{school.code}.edu.cn" if campus_verified else None
            while education_email and education_email in used_emails:
                next_seq += 1
                phone = f"{meta['phone_prefix']}{next_seq:02d}"
                education_email = f"{school.code}_u{next_seq}@example.{school.code}.edu.cn" if campus_verified else None

            nickname = generate_nickname(school.code, next_seq)
            bio = generate_bio()

            user = User(
                email=None, phone=phone, education_email=education_email,
                nickname=nickname, password_hash=get_password_hash("pass123"),
                avatar_url=None, school_id=school.id, registration_school_id=school.id,
                role="user", bio=bio, is_active=True,
                onboarding_completed=True, campus_verified=campus_verified,
                campus_verified_at=now if campus_verified else None,
                created_at=now - timedelta(days=random.randint(30, 180)),
                updated_at=now,
            )
            session.add(user)
            await session.flush()
            users.append(user)
            users_by_phone[phone] = user
            if education_email:
                used_emails.add(education_email)
            next_seq += 1

        users_by_school[school.code] = users
    await session.flush()

    # 创建 membership
    for school in schools:
        role_map = {"super_admin": "admin", "admin": "admin", "user": "member"}
        for user in users_by_school[school.code]:
            session.add(SchoolMembership(
                user_id=user.id, school_id=school.id,
                role=role_map[user.role], status="active", is_default=True,
                joined_at=now, created_at=now, updated_at=now,
            ))
    await session.flush()
    return users_by_school, users_by_phone, admin_user


# =============================================================================
# 帖子生成
# =============================================================================

async def seed_posts(session: AsyncSession, schools: list, school_by_code: dict,
                     categories_by_school: dict, locations_by_school: dict,
                     users_by_school: dict, users_by_phone: dict):
    now = datetime.now()
    all_posts = []
    post_stats = {code: {"total": 0, "published": 0, "draft": 0, "pending": 0,
                         "expired": 0, "conflict": 0, "archived": 0} for code in SCHOOLS_META}

    for school in schools:
        cats = categories_by_school[school.code]
        cat_by_code = {c.code: c for c in cats}
        locs = locations_by_school[school.code]
        loc_names = [l.name for l in locs]
        users = users_by_school[school.code]
        normal_users = [u for u in users if u.role == "user"]

        posts = []
        post_objects = []

        # 生成470条published帖子
        target_published = 470
        category_weights = {"share": 0.35, "teamup": 0.25, "trade": 0.15, "lost_found": 0.10, "other": 0.15}
        category_pool = []
        for code, w in category_weights.items():
            category_pool.extend([code] * int(w * 1000))

        for i in range(target_published):
            cat_code = random.choice(category_pool)
            cat = cat_by_code[cat_code]
            loc_name = random.choice(loc_names) if random.random() < 0.75 else None
            loc = next((l for l in locs if l.name == loc_name), None) if loc_name else None
            user = random.choice(normal_users)

            title_template = random.choice(POST_TITLES[cat_code])
            title = fill_template(title_template, loc_name if loc_name else random.choice(loc_names))
            if len(title) > 80:
                title = title[:77] + "..."

            content_template = random.choice(POST_CONTENTS[cat_code])
            content = fill_template(content_template, loc_name if loc_name else random.choice(loc_names))
            # 随机加一些口语化后缀
            if random.random() < 0.3:
                suffixes = [
                    "\n\n有没有人同感", "\n\n大家觉得呢", "\n\n求求了有人知道吗",
                    "\n\n就我一个人这样吗", "\n\n真的会谢", "\n\n哈哈哈哈",
                    "\n\n亲测有效", "\n\n避雷避雷", "\n\n推荐推荐",
                ]
                content += random.choice(suffixes)

            # 热度分层：Zipf分布
            rank = i + 1
            if rank <= target_published * 0.05:  # 头部5%
                views = random.randint(800, 3000)
                target_likes = int(views * random.uniform(0.10, 0.16))
                target_comments = random.randint(8, 15)
                target_validations = random.randint(2, 8)
                is_recommend = True
            elif rank <= target_published * 0.35:  # 中部30%
                views = random.randint(150, 600)
                target_likes = int(views * random.uniform(0.06, 0.12))
                target_comments = random.randint(2, 8)
                target_validations = random.randint(0, 3)
                is_recommend = random.random() < 0.1
            else:  # 尾部65%
                views = random.randint(20, 150)
                target_likes = int(views * random.uniform(0.04, 0.10))
                target_comments = random.randint(0, 3)
                target_validations = random.randint(0, 1) if random.random() < 0.3 else 0
                is_recommend = False

            target_likes = min(target_likes, len(normal_users) - 1)
            is_anonymous = random.random() < 0.10

            # 时间分布：过去60天，近期更多
            days_ago = int(random.betavariate(2, 5) * 60)
            hours_ago = random.randint(0, 23)
            created_at = now - timedelta(days=days_ago, hours=hours_ago)
            expire_at = created_at + timedelta(days=cat.default_validity_days)

            lost_type = None
            if cat_code == "lost_found":
                lost_type = "lost" if ("丢" in title or "寻物" in title or "失物" in title) else "found"

            post = Post(
                user_id=user.id, school_id=school.id, category_id=cat.id,
                location_id=loc.id if loc else None, title=title, content=content,
                embedding=None, is_anonymous=is_anonymous, status="published",
                view_count=views, like_count=0, comment_count=0,
                valid_count=0, invalid_count=0,
                credibility_score=None, expire_at=expire_at, lost_type=lost_type,
                contact_info=None, is_recommend=is_recommend,
                created_at=created_at, updated_at=created_at,
                is_deleted=False, deleted_at=None,
            )
            session.add(post)
            await session.flush()
            posts.append(post)
            post_objects.append({
                "post": post, "user": user, "target_likes": target_likes,
                "target_comments": target_comments, "target_validations": target_validations,
                "category_code": cat_code,
            })
            post_stats[school.code]["published"] += 1

        # 状态样本
        status_samples = [
            ("draft", 3), ("pending", 5), ("expired", 8), ("conflict", 4), ("archived", 10),
        ]
        for status, count in status_samples:
            for _ in range(count):
                cat_code = random.choice(list(category_weights.keys()))
                cat = cat_by_code[cat_code]
                loc_name = random.choice(loc_names) if random.random() < 0.7 else None
                loc = next((l for l in locs if l.name == loc_name), None) if loc_name else None
                user = random.choice(normal_users)

                title = f"【{status}】" + fill_template(random.choice(POST_TITLES[cat_code]), loc_name or random.choice(loc_names))
                if len(title) > 80:
                    title = title[:77] + "..."
                content = fill_template(random.choice(POST_CONTENTS[cat_code]), loc_name or random.choice(loc_names))

                days_ago = random.randint(5, 90)
                created_at = now - timedelta(days=days_ago)
                expire_at = created_at + timedelta(days=1) if status == "expired" else created_at + timedelta(days=cat.default_validity_days)

                post = Post(
                    user_id=user.id, school_id=school.id, category_id=cat.id,
                    location_id=loc.id if loc else None, title=title, content=content,
                    embedding=None, is_anonymous=random.random() < 0.1, status=status,
                    view_count=random.randint(0, 200), like_count=random.randint(0, 20),
                    comment_count=0, valid_count=0, invalid_count=0,
                    credibility_score=None, expire_at=expire_at, lost_type=None,
                    contact_info=None, is_recommend=False,
                    created_at=created_at, updated_at=created_at,
                    is_deleted=False, deleted_at=None,
                )
                session.add(post)
                await session.flush()
                posts.append(post)
                post_stats[school.code][status] += 1

        post_stats[school.code]["total"] = len(posts)
        all_posts.extend(post_objects)
        print(f"  {school.name}: {len(posts)} 帖子生成完成")

    await session.flush()
    return all_posts, post_stats


# =============================================================================
# 互动数据生成：点赞、评论、验证
# =============================================================================

async def seed_interactions(session: AsyncSession, all_posts: list, users_by_school: dict):
    """生成点赞、评论、协同验证"""
    now = datetime.now()
    total_likes = 0
    total_comments = 0
    total_validations = 0

    for post_data in all_posts:
        post = post_data["post"]
        author = post_data["user"]
        school_code = next((code for code, meta in SCHOOLS_META.items()
                           if meta["phone_prefix"] in author.phone), "jiangnan")
        school_users = [u for u in users_by_school[school_code] if u.id != author.id and u.role == "user"]
        random.shuffle(school_users)

        # 点赞
        like_count = min(post_data["target_likes"], len(school_users))
        like_users = school_users[:like_count]
        max_seconds = max(300, int((now - post.created_at).total_seconds()))
        for u in like_users:
            like_created = post.created_at + timedelta(
                seconds=random.randint(60, max_seconds)
            )
            session.add(Like(
                post_id=post.id, user_id=u.id, created_at=like_created,
            ))
        post.like_count = like_count
        total_likes += like_count

        # 评论
        comment_count = min(post_data["target_comments"], len(school_users) * 2)
        comment_users = []
        prev_comments = []
        for i in range(comment_count):
            # 选用户：可以重复但不要太频繁
            if random.random() < 0.7 and school_users:
                u = random.choice(school_users)
            elif comment_users:
                u = random.choice(comment_users)
            else:
                u = random.choice(school_users) if school_users else author
            comment_users.append(u)

            # 选评论内容
            r = random.random()
            if r < 0.25:
                content = random.choice(SHORT_COMMENTS)
            elif r < 0.5:
                content = random.choice(QUESTION_COMMENTS)
            elif r < 0.75:
                content = random.choice(REPLY_COMMENTS)
            else:
                content = random.choice(REPLY_COMMENTS)
            # 简单扰动
            if random.random() < 0.2:
                tails = ["啊", "哦", "呢", "吧", "哈哈", "呀", "嘛"]
                content += random.choice(tails)

            comment_created = post.created_at + timedelta(
                seconds=random.randint(120, max_seconds)
            )
            parent_id = None
            reply_to_user_id = None
            if prev_comments and random.random() < 0.25:
                parent = random.choice(prev_comments)
                parent_id = parent.id
                reply_to_user_id = parent.user_id

            comment = Comment(
                post_id=post.id, user_id=u.id, parent_id=parent_id,
                reply_to_user_id=reply_to_user_id, content=content,
                like_count=random.randint(0, 8), status="published",
                created_at=comment_created, updated_at=comment_created,
                is_deleted=False, deleted_at=None, is_anonymous=False,
            )
            session.add(comment)
            await session.flush()
            prev_comments.append(comment)

        post.comment_count = comment_count
        total_comments += comment_count

        # 协同验证
        valid_count = 0
        invalid_count = 0
        val_users_used = set()
        validations = post_data["target_validations"]
        for i in range(validations):
            if not school_users:
                break
            remaining = [u for u in school_users if u.id not in val_users_used]
            if not remaining:
                break
            u = random.choice(remaining)
            val_users_used.add(u.id)

            if random.random() < 0.15 and post_data["category_code"] != "lost_found":
                vtype = "refutation"
                content = random.choice(REFUTATION_COMMENTS)
                invalid_count += 1
            else:
                vtype = "confirmation"
                content = random.choice(VALIDATION_COMMENTS)
                valid_count += 1

            val_created = post.created_at + timedelta(
                seconds=random.randint(300, max_seconds)
            )
            session.add(ValidationRecord(
                post_id=post.id, user_id=u.id, validation_type=vtype,
                comment=content if random.random() < 0.6 else None,
                created_at=val_created, is_deleted=False, deleted_at=None,
            ))
        post.valid_count = valid_count
        post.invalid_count = invalid_count
        total_validations += valid_count + invalid_count

        # 批量flush
        if total_likes % 200 == 0:
            await session.flush()

    await session.flush()
    print(f"  互动数据：{total_likes} 点赞, {total_comments} 评论, {total_validations} 验证")
    return total_likes, total_comments, total_validations


# =============================================================================
# 地点评价生成
# =============================================================================

async def seed_location_reviews(session: AsyncSession, schools: list,
                                locations_by_school: dict, users_by_school: dict):
    now = datetime.now()
    total_reviews = 0

    for school in schools:
        locs = locations_by_school[school.code]
        users = [u for u in users_by_school[school.code] if u.role == "user"]

        for loc in locs:
            # 热门地点15-25条，其他10-15条
            is_popular = any(k in loc.name for k in ["食堂", "图书馆", "快递", "超市"])
            target = random.randint(15, 25) if is_popular else random.randint(10, 15)
            target = min(target, len(users))  # 不超过用户数

            reviewers = random.sample(users, target)
            scores = []

            for u in reviewers:
                # 评分分布：热门地点偏高，偶尔差评
                if any(k in loc.name for k in ["食堂", "快递"]):
                    score = random.choices([3, 4, 5, 2], weights=[3, 4, 2, 1])[0]
                elif any(k in loc.name for k in ["图书馆", "教学楼"]):
                    score = random.choices([4, 5, 3], weights=[4, 4, 2])[0]
                else:
                    score = random.randint(3, 5)
                scores.append(score)

                # 选评价内容
                review_text = None
                if random.random() > 0.3:  # 70%有文字
                    matched = False
                    for keyword, texts in REVIEW_COMMENTS.items():
                        if keyword in loc.name:
                            review_text = random.choice(texts)
                            matched = True
                            break
                    if not matched:
                        review_text = random.choice(GENERIC_REVIEWS)

                review_created = now - timedelta(days=random.randint(1, 120))
                session.add(LocationReview(
                    location_id=loc.id, user_id=u.id, school_id=school.id,
                    score=score, content=review_text, status="published",
                    created_at=review_created, updated_at=review_created,
                    is_deleted=False, deleted_at=None, is_anonymous=False,
                ))
                total_reviews += 1

            # 回写地点统计
            if scores:
                loc.rating_count = len(scores)
                loc.review_count = len(scores)
                loc.avg_score = round(sum(scores) / len(scores), 2)
                loc.post_count = random.randint(5, 50)  # 随机给个帖子数

        await session.flush()
        print(f"  {school.name}: {sum(1 for l in locs for _ in [])} 地点评价完成")

    await session.flush()
    print(f"  地点评价总计: {total_reviews} 条")
    return total_reviews


# =============================================================================
# Embedding生成
# =============================================================================

async def generate_embeddings(session: AsyncSession):
    """尝试为所有published帖子生成embedding，失败则跳过"""
    print("\n[10/10] 尝试生成Embedding向量...")
    try:
        from app.services.embedding_service import generate_post_embedding
    except Exception as e:
        print(f"  ⚠️  无法导入embedding服务: {e}")
        print("  提示：可稍后手动运行 python scripts/generate_embeddings.py --batch-size 50")
        return 0

    try:
        result = await session.execute(
            select(Post).where(Post.status == "published", Post.embedding.is_(None)).limit(50)
        )
        posts = list(result.scalars().all())
        generated = 0
        batch = 0

        while posts:
            batch += 1
            print(f"  处理第 {batch} 批 ({len(posts)} 条)...")
            for post in posts:
                try:
                    vector = await generate_post_embedding(post.title, post.content)
                    if vector:
                        post.embedding = vector
                        generated += 1
                except Exception as e:
                    print(f"  ⚠️  帖子 {post.id} embedding生成失败: {e}")
                    continue
            await session.flush()
            await session.commit()

            result = await session.execute(
                select(Post).where(Post.status == "published", Post.embedding.is_(None)).limit(50)
            )
            posts = list(result.scalars().all())

        print(f"  Embedding生成完成，共生成 {generated} 条向量")
        return generated
    except Exception as e:
        print(f"  ⚠️  Embedding生成失败: {e}")
        print("  提示：请检查AI_API_KEY配置，或稍后手动运行 python scripts/generate_embeddings.py --batch-size 50")
        await session.rollback()
        return 0


# =============================================================================
# 主函数
# =============================================================================

async def main():
    print("=" * 60)
    print("此刻校园 - 大规模演示数据生成脚本")
    print("=" * 60)

    async with async_session_maker() as session:
        print("\n[1/10] 清空现有数据...")
        await init_db()
        print("  数据清空完成")

        print("\n[2/10] 创建套餐...")
        plans = await seed_plans(session)
        print(f"  创建了 {len(plans)} 档套餐")

        print("\n[3/10] 创建学校...")
        schools, school_by_code = await seed_schools(session)
        print(f"  创建了 {len(schools)} 所学校")

        print("\n[4/10] 创建学校设置、分类、地点...")
        await seed_school_settings(session, schools, school_by_code)
        categories_by_school = await seed_categories(session, schools)
        locations_by_school = await seed_locations(session, schools, school_by_code)
        total_locations = sum(len(locs) for locs in locations_by_school.values())
        print(f"  创建了 {total_locations} 个地点")

        print("\n[5/10] 创建用户...")
        users_by_school, users_by_phone, admin_user = await seed_users(session, schools, school_by_code)
        total_users = sum(len(us) for us in users_by_school.values())
        total_verified = sum(1 for us in users_by_school.values() for u in us if u.campus_verified)
        print(f"  创建了 {total_users} 个用户（其中 {total_verified} 已认证）")

        print("\n[6/10] 创建订阅...")
        await seed_subscriptions(session, schools, plans, admin_user)
        print("  三校均已激活运营档套餐")

        print("\n[7/10] 创建帖子...")
        all_posts, post_stats = await seed_posts(
            session, schools, school_by_code, categories_by_school,
            locations_by_school, users_by_school, users_by_phone
        )
        total_posts = sum(s["total"] for s in post_stats.values())
        print(f"  总计 {total_posts} 条帖子")

        print("\n[8/10] 创建互动数据（点赞/评论/验证）...")
        total_likes, total_comments, total_validations = await seed_interactions(
            session, all_posts, users_by_school
        )

        print("\n[9/10] 创建地点评价...")
        total_reviews = await seed_location_reviews(
            session, schools, locations_by_school, users_by_school
        )

        print("\n[9/10] 提交基础数据...")
        await session.commit()
        print("  基础数据提交完成！")

    # Embedding生成（新session）
    async with async_session_maker() as session:
        embedding_count = await generate_embeddings(session)
        if embedding_count > 0:
            await session.commit()

    # 最终统计
    print("\n" + "=" * 60)
    print("数据生成完成！统计信息：")
    print("=" * 60)
    print(f"  学校：{len(schools)} 所")
    print(f"  用户：{total_users} 人（已认证 {total_verified} 人）")
    print(f"  地点：{total_locations} 个")
    print(f"  帖子：{total_posts} 条")
    for code, stats in post_stats.items():
        print(f"    {SCHOOLS_META[code]['name']}: published={stats['published']}, draft={stats['draft']}, "
              f"pending={stats['pending']}, expired={stats['expired']}, "
              f"conflict={stats['conflict']}, archived={stats['archived']}")
    print(f"  点赞记录：{total_likes} 条")
    print(f"  评论：{total_comments} 条")
    print(f"  协同验证：{total_validations} 条")
    print(f"  地点评价：{total_reviews} 条")
    if embedding_count > 0:
        print(f"  Embedding向量：{embedding_count} 条")
    else:
        print(f"  Embedding向量：未生成（可手动运行 generate_embeddings.py）")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
