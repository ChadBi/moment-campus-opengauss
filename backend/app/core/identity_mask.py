"""身份脱敏（匿名发帖 / 匿名评论 / 匿名地点评价）的统一工具函数。

策略（FND-03.3 / GOV-01.2 身份可见性规则）
------------------------------------------------
当内容（Post / Comment / LocationReview）被标记为 `is_anonymous=True` 时：

  * 作者本人（current_user.id == owner.id）：显示真实身份
    → 便于在「我的发布 / 我的评价 / 我的评论」里认出自家内容。
  * 管理员 / 超级管理员（permissions.is_admin）：显示真实身份
    → 审核治理、内容溯源需要。
  * 其他登录用户 + 游客：author=None 且 user_id=None
    → 严格防止通过 user_id 字段反查用户详情从而穿透匿名。

注意：评论里的 `reply_to_user_id`（被回复者 ID）不敏感，不属于匿名者自身
身份，因此不在本模块处理；调用方需保证只对 *评论者自身* 的 `user_id` /
`author` 应用本工具。
"""
from __future__ import annotations

from typing import Optional, TypeVar

from app.models.user import User
from app.core.permissions import is_admin

T = TypeVar("T")


def should_reveal_identity(
    is_anonymous: bool,
    owner_user_id: Optional[int],
    current_user: Optional[User],
) -> bool:
    """判断当前请求是否有资格看到 owner 的真实身份。

    Args:
        is_anonymous: 内容是否标记为匿名（Post/Comment/LocationReview 的字段）。
        owner_user_id: 内容真实作者的 user.id（ORM 对象上的 user_id 列）。
        current_user: 当前请求用户，可能为 None（游客）。

    Returns:
        True  → 可以显示真实身份（author 对象 + user_id 保留原值）。
        False → 对外脱敏，author=None 且 user_id=None。
    """
    if not is_anonymous:
        return True
    if current_user is None:
        return False
    if owner_user_id is not None and current_user.id == owner_user_id:
        return True
    return is_admin(current_user)


def build_author_brief(user: Optional[User]) -> Optional[dict]:
    """根据 ORM User 关联对象构造响应里的 author 对象（与 UserBrief schema 对齐）。

    UserBrief schema 字段：
        - id: int
        - nickname: str
        - avatar_url: Optional[str]
        - is_verified: bool  （映射到 User.campus_verified 列）
    """
    if user is None:
        return None
    return {
        "id": user.id,
        "nickname": user.nickname,
        "avatar_url": getattr(user, "avatar_url", None),
        "is_verified": bool(getattr(user, "campus_verified", False)),
    }


def apply_author_mask(
    response_obj: T,
    orm_obj: object,
    current_user: Optional[User],
    *,
    is_anonymous_attr: str = "is_anonymous",
    owner_id_attr: str = "user_id",
    user_rel_attr: str = "user",
    set_user_id_none: bool = True,
) -> T:
    """就地修改 Pydantic 响应对象：根据匿名规则填充 author 并脱敏 user_id。

    统一替换原先分散在 posts / comments / locations / search /
    recommendations / topics 六个 API 模块里重复出现的：

        if post.is_anonymous:
            response.author = None
        elif post.user:
            response.author = {"id": ..., "nickname": ...}

    同时补上原先遗漏的「user_id 字段仍原样返回 → 匿名可被穿透」的漏洞，
    并新增「作者本人 / 管理员豁免」以提升产品体感（见本文件头部策略）。

    Args:
        response_obj: 待修改的 Pydantic 响应对象。需要具备：
                      - `author: Optional[UserBrief]` 字段
                      - `user_id: Optional[int]` 字段（当 set_user_id_none=True 时）
        orm_obj: SQLAlchemy ORM 对象（Post / Comment / LocationReview / ...）。
        current_user: 当前请求用户（含游客=None）。
        is_anonymous_attr: ORM 上的匿名布尔列名（默认 "is_anonymous"）。
        owner_id_attr: ORM 上的真实作者 ID 列名（默认 "user_id"）。
        user_rel_attr: ORM 上预加载的 User 关联属性名（默认 "user"，调用方应
                       已通过 joinedload/selectinload 拉取，否则为 None 也安全）。
        set_user_id_none: 脱敏时是否把 response_obj.user_id 置为 None。对
                          reply_to_user_id 这类"别人的 ID"不要传 True，默认
                          只对作者自身的 user_id 生效。

    Returns:
        同一个 response_obj（方便链式使用；修改是 in-place 的，返回只为便利）。
    """
    is_anon = bool(getattr(orm_obj, is_anonymous_attr, False))
    owner_id = getattr(orm_obj, owner_id_attr, None)
    reveal = should_reveal_identity(is_anon, owner_id, current_user)

    if reveal:
        user = getattr(orm_obj, user_rel_attr, None)
        response_obj.author = build_author_brief(user)  # type: ignore[attr-defined]
    else:
        response_obj.author = None  # type: ignore[attr-defined]
        if set_user_id_none and hasattr(response_obj, "user_id"):
            response_obj.user_id = None  # type: ignore[attr-defined]

    return response_obj
