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
from app.api.upload import router as upload_router

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
api_router.include_router(upload_router)
