"""UC-01: 学校切换服务（严格一对一绑定）

切换学校 = 把用户唯一 active membership 指向新学校，并执行副作用：
1. 重置校园身份认证（campus_verified=False 等）
2. 匿名化用户在原学校的帖子/评论/评价（D2：内容保留，作者身份匿名化）

super_admin 豁免一对一限制（join 仍可创建多 membership，见 schools.py）。
"""
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.location_review import LocationReview
from app.models.post import Post
from app.models.school_membership import SchoolMembership
from app.models.user import User


async def switch_school(
    db: AsyncSession,
    user: User,
    new_school_id: int,
) -> SchoolMembership:
    """将用户切换到新学校（一对一）。

    前置条件（由调用方保证）：用户存在唯一 active membership，且
    new_school_id 与当前学校不同。
    返回更新后的 membership（school 关系已加载）。
    """
    # 1. 定位用户唯一 active membership（部分唯一索引保证至多一条）
    membership = (
        await db.execute(
            select(SchoolMembership)
            .options(selectinload(SchoolMembership.school))
            .where(
                SchoolMembership.user_id == user.id,
                SchoolMembership.status == "active",
            )
        )
    ).scalar_one_or_none()

    if membership is None:
        # 理论上不会发生（调用方校验），防御性兜底：不执行切换
        raise ValueError("用户不存在 active 学校成员关系，无法切换")

    old_school_id = membership.school_id
    if old_school_id == new_school_id:
        return membership

    # 2. 匿名化原校内容（D2）
    await _anonymize_old_school_content(db, user.id, old_school_id)

    # 3. 切换 membership + 同步 user.school_id
    membership.school_id = new_school_id
    membership.is_default = True
    membership.updated_at = datetime.now()
    user.school_id = new_school_id
    user.updated_at = datetime.now()

    # 4. 重置校园认证（D5：认证状态在 User 全局字段，切校即失效）
    user.campus_verified = False
    user.campus_verified_at = None

    # 5. 失效未使用的认证 token（防止旧校 token 复用）
    from app.models.campus_verify_token import CampusVerifyToken
    await db.execute(
        update(CampusVerifyToken)
        .where(
            CampusVerifyToken.user_id == user.id,
            CampusVerifyToken.used_at.is_(None),
        )
        .values(used_at=datetime.now())
    )

    await db.commit()
    await db.refresh(membership, attribute_names=["school"])
    return membership


async def _anonymize_old_school_content(
    db: AsyncSession,
    user_id: int,
    old_school_id: int,
) -> None:
    """将用户在原学校发布的帖子/评论/评价匿名化（内容保留，身份隐藏）。"""
    now = datetime.now()

    # 帖子：直接按 school_id 匿名化
    await db.execute(
        update(Post)
        .where(
            Post.user_id == user_id,
            Post.school_id == old_school_id,
            Post.is_deleted == False,  # noqa: E712
        )
        .values(is_anonymous=True, updated_at=now)
    )

    # 评论：无 school_id，通过 post.school_id 子查询
    await db.execute(
        update(Comment)
        .where(
            Comment.user_id == user_id,
            Comment.is_deleted == False,  # noqa: E712
            Comment.post_id.in_(
                select(Post.id).where(
                    Post.school_id == old_school_id,
                    Post.is_deleted == False,  # noqa: E712
                )
            ),
        )
        .values(is_anonymous=True, updated_at=now)
    )

    # 地点评价：location_reviews 自带 school_id
    await db.execute(
        update(LocationReview)
        .where(
            LocationReview.user_id == user_id,
            LocationReview.school_id == old_school_id,
            LocationReview.is_deleted == False,  # noqa: E712
        )
        .values(is_anonymous=True, updated_at=now)
    )
