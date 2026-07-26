from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.posts import router as posts_router
from app.api.comments import router as comments_router
from app.api.interactions import router as interactions_router
from app.api.search import router as search_router
from app.api.map import router as map_router
from app.api.categories import router as categories_router
from app.api.notifications import router as notifications_router
from app.api.admin import router as admin_router
from app.api.admin_topics import router as admin_topics_router
from app.api.topics import router as topics_router
from app.api.upload import router as upload_router
from app.api.platform import router as platform_router
from app.api.schools import schools_router, me_router as schools_me_router
from app.api.analytics import router as analytics_router, admin_analytics_router
from app.api.governance import router as governance_router
from app.api.publishers import router as publishers_router
from app.api.admin_publishers import router as admin_publishers_router
from app.api.recommendations import router as recommendations_router
from app.api.subscriptions import router as subscriptions_router

api_router = APIRouter()


@api_router.get("/test")
async def test():
    return {"message": "API is working"}


# 注册路由
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(posts_router)
api_router.include_router(comments_router)
api_router.include_router(interactions_router)
api_router.include_router(search_router)
api_router.include_router(map_router)
api_router.include_router(categories_router)
api_router.include_router(notifications_router)
api_router.include_router(admin_router)
# TOPIC-01.1: 用户端专题（列表/详情，仅展示已发布）
api_router.include_router(topics_router)
# TOPIC-01.2: 专题管理（CRUD/排序/上下线/编排，仅 admin 及以上）
api_router.include_router(admin_topics_router)
api_router.include_router(upload_router)
api_router.include_router(platform_router)
# TEN-03.1: 学校目录、加入、默认学校、切换
api_router.include_router(schools_router)
api_router.include_router(schools_me_router)
# ANA-01.3: 产品事件批量上报
api_router.include_router(analytics_router)
# ANA-02.2: 校级分析指标 + 零结果洞察（admin 及以上）
api_router.include_router(admin_analytics_router)
# GOV-01: 五类协同治理（2 类投票 + 3 类问题报告）
api_router.include_router(governance_router)
# ORG-01: 官方发布主体（用户端 + 管理端）
api_router.include_router(publishers_router)
api_router.include_router(admin_publishers_router)
# SUB-01: 用户级内容订阅（分类/地点/专题）
api_router.include_router(subscriptions_router)
# REC-01: 首页推荐 + 推荐隐私偏好（个性化开关 + 清除画像历史）
api_router.include_router(recommendations_router)
