"""演示数据填充脚本（江南大学蠡湖校区真实场景版）

用于开发和测试环境。

注意：本脚本不再创建表结构，需先通过 Alembic 迁移创建表：
    alembic upgrade head
脚本仅清空现有数据并重新填充演示数据。

数据均为模拟真实用户发帖的校园生活场景，覆盖：
- 校园美食 / 校园动物 / 打印服务 / 校园活动 / 学习资源
- 生活服务 / 校园交通 / 校园设施 / 活动场地 / 失物招领
- 校园兼职 / 其他
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
from app.models import (
    Base, User, School, Post, Category, PostType, Tag, PostTag, PostImage,
    Location, Comment, Like, ValidationRecord, Report, Notification,
    TopicCollection, TopicCollectionPost, Draft, BrowseHistory, SearchHistory,
    AdminOperationLog
)
import bcrypt


# =============================================================================
# 真实场景数据：江南大学蠡湖校区
# =============================================================================

# 用户清单（1 管理员 + 10 普通用户，昵称/bio 模拟真实学生身份）
USERS_DATA = [
    {
        "email": "admin@momentcampus.com",
        "nickname": "校园运营组",
        "role": "admin",
        "bio": "此刻校园平台运营组，负责内容审核与平台维护",
    },
    {
        "email": "user1@example.com",
        "nickname": "江南小李",
        "role": "user",
        "bio": "计算机学院大三 | 校园信息搬运工",
    },
    {
        "email": "user2@example.com",
        "nickname": "蠡湖钓客",
        "role": "user",
        "bio": "喜欢在蠡湖边发呆的钓鱼佬",
    },
    {
        "email": "user3@example.com",
        "nickname": "食堂品鉴师",
        "role": "user",
        "bio": "吃过江南大学所有食堂 | 美食地图绘制中",
    },
    {
        "email": "user4@example.com",
        "nickname": "图书馆常客",
        "role": "user",
        "bio": "图书馆三楼是我的第二卧室",
    },
    {
        "email": "user5@example.com",
        "nickname": "跑道冲刺手",
        "role": "user",
        "bio": "田径队 | 每天夜跑 5 公里",
    },
    {
        "email": "user6@example.com",
        "nickname": "二食堂干饭人",
        "role": "user",
        "bio": "干饭不积极思想有问题",
    },
    {
        "email": "user7@example.com",
        "nickname": "江大摄影师",
        "role": "user",
        "bio": "用镜头记录蠡湖的四季 | 摄影社",
    },
    {
        "email": "user8@example.com",
        "nickname": "流浪猫救助站",
        "role": "user",
        "bio": "校园流浪猫 TNR 志愿者 | 已绝育 12 只",
    },
    {
        "email": "user9@example.com",
        "nickname": "期末突击队",
        "role": "user",
        "bio": "靠期末两周创造奇迹的大学生",
    },
    {
        "email": "user10@example.com",
        "nickname": "无锡学长",
        "role": "user",
        "bio": "大四老学长 | 江南生存指南作者",
    },
]

# 帖子清单（30 条真实场景数据）
# 字段：title / content / category_code / location_name / user_email
#       is_anonymous / views / likes / is_top / is_recommend / comments / validations
POSTS_DATA = [
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
        "category_code": "food",
        "location_name": "第二食堂",
        "user_email": "user6@example.com",
        "is_anonymous": False,
        "views": 342, "likes": 28, "is_top": True, "is_recommend": True,
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
        "category_code": "food",
        "location_name": "第一食堂",
        "user_email": "user3@example.com",
        "is_anonymous": False,
        "views": 198, "likes": 15, "is_top": False, "is_recommend": False,
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
        "category_code": "food",
        "location_name": "北门",
        "user_email": "user3@example.com",
        "is_anonymous": False,
        "views": 521, "likes": 42, "is_top": False, "is_recommend": True,
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
        "category_code": "food",
        "location_name": "第二食堂",
        "user_email": "user6@example.com",
        "is_anonymous": False,
        "views": 287, "likes": 19, "is_top": False, "is_recommend": False,
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
        "category_code": "animal",
        "location_name": "图书馆",
        "user_email": "user8@example.com",
        "is_anonymous": False,
        "views": 612, "likes": 56, "is_top": True, "is_recommend": True,
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
        "category_code": "animal",
        "location_name": "蠡湖畔",
        "user_email": "user7@example.com",
        "is_anonymous": False,
        "views": 478, "likes": 38, "is_top": False, "is_recommend": True,
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
        "category_code": "animal",
        "location_name": "教学楼A区",
        "user_email": "user8@example.com",
        "is_anonymous": False,
        "views": 234, "likes": 21, "is_top": False, "is_recommend": False,
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
        "category_code": "print",
        "location_name": "校园超市",
        "user_email": "user9@example.com",
        "is_anonymous": False,
        "views": 189, "likes": 14, "is_top": False, "is_recommend": False,
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
        "category_code": "print",
        "location_name": "图书馆",
        "user_email": "user10@example.com",
        "is_anonymous": False,
        "views": 256, "likes": 22, "is_top": False, "is_recommend": False,
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
        "category_code": "event",
        "location_name": "文浩科学馆",
        "user_email": "user1@example.com",
        "is_anonymous": False,
        "views": 423, "likes": 35, "is_top": True, "is_recommend": True,
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
        "category_code": "event",
        "location_name": "大学生活动中心",
        "user_email": "user1@example.com",
        "is_anonymous": False,
        "views": 312, "likes": 27, "is_top": False, "is_recommend": True,
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
        "category_code": "event",
        "location_name": "教学楼A区",
        "user_email": "user10@example.com",
        "is_anonymous": False,
        "views": 389, "likes": 31, "is_top": False, "is_recommend": True,
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
        "category_code": "event",
        "location_name": "文浩科学馆",
        "user_email": "user4@example.com",
        "is_anonymous": False,
        "views": 567, "likes": 48, "is_top": False, "is_recommend": True,
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
        "category_code": "study",
        "location_name": "图书馆",
        "user_email": "user4@example.com",
        "is_anonymous": False,
        "views": 678, "likes": 52, "is_top": True, "is_recommend": False,
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
        "category_code": "study",
        "location_name": "图书馆",
        "user_email": "user4@example.com",
        "is_anonymous": False,
        "views": 312, "likes": 18, "is_top": False, "is_recommend": False,
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
        "category_code": "study",
        "location_name": "教学楼A区",
        "user_email": "user10@example.com",
        "is_anonymous": False,
        "views": 891, "likes": 87, "is_top": False, "is_recommend": True,
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
        "category_code": "service",
        "location_name": "快递服务中心",
        "user_email": "user1@example.com",
        "is_anonymous": False,
        "views": 423, "likes": 25, "is_top": False, "is_recommend": False,
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
        "category_code": "service",
        "location_name": "学士公寓",
        "user_email": "user1@example.com",
        "is_anonymous": False,
        "views": 234, "likes": 12, "is_top": False, "is_recommend": False,
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
        "category_code": "service",
        "location_name": "校园超市",
        "user_email": "user9@example.com",
        "is_anonymous": False,
        "views": 367, "likes": 31, "is_top": False, "is_recommend": False,
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
        "category_code": "transport",
        "location_name": "北门",
        "user_email": "user5@example.com",
        "is_anonymous": False,
        "views": 289, "likes": 19, "is_top": False, "is_recommend": False,
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
        "category_code": "transport",
        "location_name": "北门",
        "user_email": "user10@example.com",
        "is_anonymous": False,
        "views": 312, "likes": 16, "is_top": False, "is_recommend": False,
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
        "category_code": "facility",
        "location_name": "体育馆",
        "user_email": "user5@example.com",
        "is_anonymous": False,
        "views": 256, "likes": 14, "is_top": False, "is_recommend": False,
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
        "category_code": "facility",
        "location_name": "田径场",
        "user_email": "user5@example.com",
        "is_anonymous": False,
        "views": 178, "likes": 8, "is_top": False, "is_recommend": False,
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
        "category_code": "venue",
        "location_name": "大学生活动中心",
        "user_email": "user1@example.com",
        "is_anonymous": False,
        "views": 234, "likes": 11, "is_top": False, "is_recommend": False,
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
        "category_code": "venue",
        "location_name": "文浩科学馆",
        "user_email": "user10@example.com",
        "is_anonymous": False,
        "views": 167, "likes": 9, "is_top": False, "is_recommend": False,
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
        "category_code": "lost_found",
        "location_name": "第一食堂",
        "user_email": "user1@example.com",
        "is_anonymous": False,
        "views": 312, "likes": 5, "is_top": False, "is_recommend": False,
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
        "category_code": "lost_found",
        "location_name": "图书馆",
        "user_email": "user4@example.com",
        "is_anonymous": False,
        "views": 145, "likes": 7, "is_top": False, "is_recommend": False,
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
        "category_code": "job",
        "location_name": "北门",
        "user_email": "user9@example.com",
        "is_anonymous": False,
        "views": 423, "likes": 18, "is_top": False, "is_recommend": False,
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
        "category_code": "job",
        "location_name": "图书馆",
        "user_email": "user10@example.com",
        "is_anonymous": False,
        "views": 289, "likes": 12, "is_top": False, "is_recommend": False,
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
        "category_code": "other",
        "location_name": "学士公寓",
        "user_email": "user10@example.com",
        "is_anonymous": False,
        "views": 1234, "likes": 98, "is_top": True, "is_recommend": True,
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
# 工具函数
# =============================================================================

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


async def init_db():
    """清空所有现有数据（保留表结构，openGauss 已通过 Alembic 创建表）

    使用 TRUNCATE ... CASCADE 清空所有表数据，再逐表重置自增序列。
    注：openGauss 的 PGXC 架构不支持 RESTART IDENTITY 子句，需手动 ALTER SEQUENCE。
    """
    # 按外键依赖逆序列出所有业务表（favorites 已删除，不再包含）
    tables = [
        "admin_operation_logs",
        "search_histories",
        "browse_histories",
        "drafts",
        "topic_collection_posts",
        "topic_collections",
        "notifications",
        "reports",
        "validation_records",
        "likes",
        "comments",
        "post_images",
        "post_tags",
        "posts",
        "tags",
        "locations",
        "post_types",
        "categories",
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
            # openGauss 默认序列命名为 <table>_id_seq
            await conn.execute(
                text(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH 1;")
            )


async def seed_schools(session: AsyncSession):
    """创建学校数据：江南大学（蠡湖校区）作为唯一模拟核心"""
    schools = [
        School(
            name="江南大学",
            code="jiangnan",
            province="江苏省",
            city="无锡市",
            address="江苏省无锡市滨湖区蠡湖大道1800号",
            center_lat=31.483706,
            center_lng=120.271166,
            map_zoom=16,
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
    """创建用户数据（基于真实身份模拟）"""
    users = []
    for u in USERS_DATA:
        user = User(
            email=u["email"],
            nickname=u["nickname"],
            password_hash=get_password_hash("pass123"),
            school_id=schools[0].id,
            role=u["role"],
            bio=u["bio"],
            is_active=True
        )
        users.append(user)
    session.add_all(users)
    await session.flush()
    return users


async def seed_locations(session: AsyncSession, schools: list):
    """创建地点数据：江南大学蠡湖校区 15 个地点

    坐标基于校区中心 (120.271166, 31.483706) 做合理偏移。
    """
    locations = []

    # 江南大学蠡湖校区地点清单：(名称, 纬度, 经度, 描述)
    jiangnan_locations = [
        ("北门", 31.4863, 120.2712, "蠡湖大道主入口"),
        ("南门", 31.4812, 120.2712, "校园南入口"),
        ("第一食堂", 31.4840, 120.2700, "主食堂"),
        ("第二食堂", 31.4845, 120.2725, "学生食堂"),
        ("图书馆", 31.4835, 120.2715, "主图书馆"),
        ("体育馆", 31.4855, 120.2735, "综合体育馆"),
        ("田径场", 31.4850, 120.2745, "主田径场"),
        ("教学楼A区", 31.4842, 120.2710, "主要教学区"),
        ("学士公寓", 31.4825, 120.2730, "学生宿舍区"),
        ("校园超市", 31.4838, 120.2720, "综合超市"),
        ("文浩科学馆", 31.4830, 120.2705, "讲座演出场地"),
        ("大学生活动中心", 31.4828, 120.2728, "社团活动场地"),
        ("蠡湖畔", 31.4820, 120.2718, "校园水域景观"),
        ("快递服务中心", 31.4833, 120.2738, "校园快递点"),
        ("打印文印店", 31.4847, 120.2708, "文印服务"),
    ]

    for name, lat, lng, desc in jiangnan_locations:
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

    session.add_all(locations)
    await session.flush()
    return locations


async def seed_posts(session: AsyncSession, users: list, schools: list,
                     categories: list, post_types: list, locations: list):
    """创建信息数据（30 条真实校园场景帖子）"""
    # 构建查找索引
    user_by_email = {u.email: u for u in users}
    category_by_code = {c.code: c for c in categories}
    location_by_name = {l.name: l for l in locations}
    # 信息类型：普通信息为默认
    normal_type = next((pt for pt in post_types if pt.code == "normal"), post_types[0])
    event_type = next((pt for pt in post_types if pt.code == "event"), post_types[0])
    lost_found_type = next((pt for pt in post_types if pt.code == "lost_found"), post_types[0])

    # 时间分布策略：让帖子分散在过去 30 天内，最近几条设置在几分钟到几小时前
    # 这样前端能看到"刚刚 / X分钟前 / X小时前 / X天前"各种时间格式
    # 元素为 (days_ago, hours_ago, minutes_ago)，按索引对应 POSTS_DATA 的 30 条
    TIME_OFFSETS = [
        (30, 0, 0),   (29, 3, 0),   (28, 6, 0),   (27, 9, 0),   (26, 12, 0),
        (25, 0, 0),   (24, 2, 0),   (23, 5, 0),   (22, 8, 0),   (21, 14, 0),
        (20, 0, 0),   (18, 4, 0),   (16, 7, 0),   (15, 10, 0),  (14, 16, 0),
        (13, 0, 0),   (12, 3, 0),   (11, 6, 0),   (10, 12, 0),  (9, 18, 0),
        (8, 0, 0),    (7, 4, 0),    (6, 8, 0),    (5, 14, 0),   (4, 20, 0),
        (3, 0, 0),    (2, 6, 0),    (1, 12, 0),   (0, 6, 0),    (0, 0, 45),
    ]
    # 索引说明：
    #   [0-24]  过去 4-30 天 → "X天前"
    #   [25-27] 过去 1-3 天 → "1天前" / "2天前" / "3天前"
    #   [28]    6 小时前 → "6小时前"
    #   [29]    45 分钟前 → "45分钟前"

    posts = []
    all_comments = []
    all_validations = []

    now = datetime.now()

    for i, p in enumerate(POSTS_DATA):
        user = user_by_email[p["user_email"]]
        category = category_by_code[p["category_code"]]
        location = location_by_name.get(p["location_name"])

        # 信息类型映射
        if category.code == "event":
            post_type = event_type
        elif category.code == "lost_found":
            post_type = lost_found_type
        else:
            post_type = normal_type

        # 失物招领分类补充 lost_type 字段（前两条为 lost，后一条为 found）
        lost_type = None
        if category.code == "lost_found":
            lost_type = "lost" if "丢失" in p["title"] else "found"

        # 计算这条帖子的创建时间（分散在过去 30 天内）
        days_ago, hours_ago, mins_ago = TIME_OFFSETS[i] if i < len(TIME_OFFSETS) else (1, 0, 0)
        created_at = now - timedelta(days=days_ago, hours=hours_ago, minutes=mins_ago)

        post = Post(
            user_id=user.id,
            school_id=schools[0].id,
            category_id=category.id,
            post_type_id=post_type.id,
            location_id=location.id if location else None,
            title=p["title"],
            content=p["content"],
            is_anonymous=p.get("is_anonymous", False),
            status="published",
            view_count=p.get("views", 0),
            like_count=p.get("likes", 0),
            comment_count=len(p.get("comments", [])),
            valid_count=len([v for v in p.get("validations", []) if v["type"] == "confirmation"]),
            invalid_count=len([v for v in p.get("validations", []) if v["type"] == "refutation"]),
            lost_type=lost_type,
            expire_at=created_at + timedelta(days=category.default_validity_days),
            is_top=p.get("is_top", False),
            is_recommend=p.get("is_recommend", False),
            created_at=created_at,
            updated_at=created_at,
        )
        posts.append(post)

    session.add_all(posts)
    await session.flush()

    # 创建评论（时间在帖子创建后 1-48 小时内分散）
    for i, p in enumerate(POSTS_DATA):
        post = posts[i]
        for j, c in enumerate(p.get("comments", [])):
            comment_user = user_by_email[c["user_email"]]
            # 每条评论在帖子创建后 1+j*3 小时
            comment_time = post.created_at + timedelta(hours=1 + j * 3)
            # 不超过当前时间
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

    session.add_all(all_comments)
    await session.flush()

    # 创建验证记录（confirmation/refutation，时间在帖子创建后 2-72 小时内）
    for i, p in enumerate(POSTS_DATA):
        post = posts[i]
        for j, v in enumerate(p.get("validations", [])):
            v_user = user_by_email[v["user_email"]]
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

    session.add_all(all_validations)
    await session.flush()

    return posts, all_comments, all_validations


async def seed_notifications(session: AsyncSession, users: list, posts: list):
    """创建通知数据（基于真实互动场景）"""
    notifications = []

    # 模拟真实通知场景：评论/点赞/系统通知
    notification_templates = [
        {"user_email": "user6@example.com", "type": "comment", "title": "您的帖子有新评论",
         "content": "江南小李 评论了你的《二食堂三楼麻辣香锅真的绝了》",
         "actor_email": "user1@example.com", "is_read": False},
        {"user_email": "user3@example.com", "type": "like", "title": "您的帖子被点赞",
         "content": "二食堂干饭人 等5人 赞了你的《蠡湖周边10块钱吃饱的5家店》",
         "actor_email": "user6@example.com", "is_read": False},
        {"user_email": "user8@example.com", "type": "comment", "title": "您的帖子有新评论",
         "content": "图书馆常客 评论了你的《图书馆门口的橘猫又来蹭饭了》",
         "actor_email": "user4@example.com", "is_read": True},
        {"user_email": "user10@example.com", "type": "system", "title": "您的帖子被推荐",
         "content": "您的《计算机组成原理复习资料分享》已被推荐到首页",
         "actor_email": "admin@momentcampus.com", "is_read": False},
        {"user_email": "user1@example.com", "type": "system", "title": "管理员审核通过",
         "content": "您发布的《文浩科学馆周五晚话剧《雷雨》演出》已通过审核",
         "actor_email": "admin@momentcampus.com", "is_read": True},
        {"user_email": "user5@example.com", "type": "like", "title": "您的帖子被点赞",
         "content": "江南小李 赞了你的《体育馆游泳馆开放时间》",
         "actor_email": "user1@example.com", "is_read": False},
        {"user_email": "user4@example.com", "type": "system", "title": "帖子即将过期",
         "content": "您的《图书馆开放时间汇总》还有3天过期，如需保留请更新",
         "actor_email": "admin@momentcampus.com", "is_read": False},
        {"user_email": "user9@example.com", "type": "comment", "title": "您的帖子有新评论",
         "content": "无锡学长 评论了你的《校园超市本周打折商品》",
         "actor_email": "user10@example.com", "is_read": True},
    ]

    user_by_email = {u.email: u for u in users}

    for n in notification_templates:
        target_post = posts[0]  # 简化：target 指向第一条帖子
        notification = Notification(
            user_id=user_by_email[n["user_email"]].id,
            type=n["type"],
            title=n["title"],
            content=n["content"],
            target_type="post",
            target_id=target_post.id,
            actor_id=user_by_email[n["actor_email"]].id,
            is_read=n["is_read"]
        )
        notifications.append(notification)

    session.add_all(notifications)
    await session.flush()
    return notifications


async def seed_topic_collections(session: AsyncSession, schools: list, users: list, posts: list):
    """创建专题集合数据"""
    topics = []

    # 6 个真实主题
    topic_data = [
        ("新生入学指南", "为新生提供校园生活必备信息：宿舍、食堂、学习、交通一站式攻略", schools[0].id, "user10@example.com"),
        ("江南美食地图", "学姐学长亲测的校园+周边美食清单，干饭人必备", schools[0].id, "user3@example.com"),
        ("期末复习资源合集", "历年真题、复习笔记、易错点汇总，期末救命资料", schools[0].id, "user10@example.com"),
        ("蠡湖校园生态", "记录校园流浪猫、蠡湖天鹅等校园生态观察", schools[0].id, "user8@example.com"),
        ("社团活动精选", "校园社团招新、活动演出信息一网打尽", schools[0].id, "user1@example.com"),
        ("校园生活贴士", "快递、打印、洗衣、交通等日常生活实用技巧", schools[0].id, "user9@example.com"),
    ]

    user_by_email = {u.email: u for u in users}

    for i, (title, desc, school_id, creator_email) in enumerate(topic_data):
        topic = TopicCollection(
            title=title,
            description=desc,
            school_id=school_id,
            creator_id=user_by_email[creator_email].id,
            post_count=0,
            view_count=80 + i * 30,
            status="published",
            sort_order=i + 1
        )
        topics.append(topic)

    session.add_all(topics)
    await session.flush()

    # 按主题相关性挑选帖子
    def pick_by_category(post_list, category_codes, n):
        return [p for p in post_list if any(c in p.title or c in p.content for c in category_codes)][:n]

    topic_post_keywords = [
        ["新生", "宿舍", "入学"],  # 新生入学指南
        ["食堂", "美食", "干饭", "螺蛳粉", "油条"],  # 江南美食地图
        ["复习", "图书馆", "自习", "资料", "期末"],  # 期末复习资源合集
        ["猫", "天鹅", "动物"],  # 蠡湖校园生态
        ["话剧", "街舞", "招新", "ACM", "讲座"],  # 社团活动精选
        ["快递", "打印", "洗衣机", "校车", "单车"],  # 校园生活贴士
    ]

    topic_posts = []
    import random
    for topic_idx, topic in enumerate(topics):
        keywords = topic_post_keywords[topic_idx]
        # 找到匹配关键词的帖子，不足则随机补充
        selected = [p for p in posts if any(kw in p.title or kw in p.content for kw in keywords)]
        if len(selected) < 5:
            others = [p for p in posts if p not in selected]
            random.shuffle(others)
            selected.extend(others[:5 - len(selected)])
        else:
            selected = selected[:5]

        for idx, post in enumerate(selected):
            tp = TopicCollectionPost(
                topic_collection_id=topic.id,
                post_id=post.id,
                sort_order=idx + 1
            )
            topic_posts.append(tp)
        topic.post_count = len(selected)

    session.add_all(topic_posts)
    await session.flush()
    return topics


async def seed_reports(session: AsyncSession, posts: list, users: list):
    """创建举报记录数据（基于真实举报场景）"""
    user_by_email = {u.email: u for u in users}
    admin_user = user_by_email["admin@momentcampus.com"]

    reports_data = [
        # 帖子索引, 举报人, 举报类型, 描述, 状态, 处理结果
        (3, "user2@example.com", "fake", "螺蛳粉现在还有吗？我去没看到，疑似过期信息", "resolved", "已通知作者更新"),
        (4, "user9@example.com", "ad", "评论区有人发外卖广告，请处理", "resolved", "已删除广告评论"),
        (8, "user1@example.com", "inappropriate", "打印机价格可能有误，需核实", "processing", None),
        (10, "user6@example.com", "other", "话剧演出时间是不是改了？", "pending", None),
        (14, "user9@example.com", "fake", "图书馆开放时间跟实际不符", "resolved", "已联系作者更新"),
        (24, "user8@example.com", "ad", "疑似家教广告，建议审核", "resolved", "审核通过，正常家教信息"),
    ]

    reports = []
    for post_idx, reporter_email, rtype, desc, status, result in reports_data:
        if post_idx >= len(posts):
            continue
        report = Report(
            post_id=posts[post_idx].id,
            comment_id=None,
            reporter_id=user_by_email[reporter_email].id,
            report_type=rtype,
            description=desc,
            status=status,
            handler_id=admin_user.id if status != "pending" else None,
            handle_result=result
        )
        reports.append(report)

    session.add_all(reports)
    await session.flush()
    return reports


async def seed_data():
    """主函数：填充所有演示数据"""
    print("清空现有数据（保留表结构）...")
    await init_db()
    print("✓ 已清空所有表数据并重置自增 ID")

    async with async_session_maker() as session:
        print("创建学校数据...")
        schools = await seed_schools(session)
        print(f"✓ 创建了 {len(schools)} 所学校（江南大学 - 蠡湖校区）")

        print("创建分类数据...")
        categories = await seed_categories(session)
        print(f"✓ 创建了 {len(categories)} 个分类")

        print("创建信息类型数据...")
        post_types = await seed_post_types(session)
        print(f"✓ 创建了 {len(post_types)} 个信息类型")

        print("创建用户数据...")
        users = await seed_users(session, schools)
        print(f"✓ 创建了 {len(users)} 个用户（1 管理员 + 10 普通用户）")

        print("创建地点数据...")
        locations = await seed_locations(session, schools)
        print(f"✓ 创建了 {len(locations)} 个地点")

        print("创建信息数据（30 条真实场景帖子）...")
        posts, comments, validations = await seed_posts(
            session, users, schools, categories, post_types, locations
        )
        print(f"✓ 创建了 {len(posts)} 条帖子")
        print(f"✓ 创建了 {len(comments)} 条评论")
        print(f"✓ 创建了 {len(validations)} 条协同验证记录")

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
        print("\n账号列表：")
        print("  管理员 - admin@momentcampus.com / pass123")
        print("  普通用户 - user1~user10@example.com / pass123")
        print("\n用户身份：")
        for u in USERS_DATA:
            print(f"  {u['email']:30s} | {u['nickname']:12s} | {u['bio']}")


if __name__ == "__main__":
    asyncio.run(seed_data())
