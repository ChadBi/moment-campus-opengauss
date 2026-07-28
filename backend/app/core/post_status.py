"""Post 状态机定义与流转规则（T-B-01）

6 态状态机：
- draft: 草稿
- pending: 待审核（等价于 docs/21 中的 pending_review，沿用现有代码命名以保持兼容）
- published: 已发布
- expired: 已过期
- conflict: 冲突中（同一地点出现相互矛盾的信息）
- archived: 已归档（终态）

流转规则依据：
- docs/21_后续开发任务清单.md T-B-01
- docs/25_数据库概念模型设计.md 状态机图
- docs/27_数据库物理模型设计.md 触发器 TR01

设计原则：
1. 兼容现有 seed_data.py 的 status="published" 与新创建默认 "pending"
2. 提供 can_transition() 供 Service 层（T-B-03/T-B-04）调用
3. 提供别名映射，使 doc 中的 "pending_review" 与代码中的 "pending" 等价
"""
from typing import Set


class PostStatus:
    """Post 状态常量

    所有状态值为字符串，与数据库 status 字段（String(20)）直接对应。
    """

    DRAFT = "draft"
    PENDING = "pending"            # 待审核（doc 21 记为 pending_review）
    PUBLISHED = "published"
    EXPIRED = "expired"
    CONFLICT = "conflict"
    ARCHIVED = "archived"

    # 全部正式状态
    ALL: tuple = (DRAFT, PENDING, PUBLISHED, EXPIRED, CONFLICT, ARCHIVED)

    # 别名映射：doc 中的命名 → 代码中的命名
    # 用于读取历史数据或外部输入时的归一化
    ALIASES: dict = {
        "pending_review": PENDING,
    }


# 合法流转规则：current -> {allowed target statuses}
#
# 依据 docs/21 T-B-01 验收标准与 docs/25 状态机图：
#   draft      → pending / archived              （用户提交审核或放弃）
#   pending    → published / draft / archived    （管理员审核通过/驳回/放弃）
#   published  → pending / expired / conflict / archived
#              （FND-03.2: 实质修改回审 pending / 自动过期 / 冲突检测 / 管理员归档）
#   expired    → published / archived            （用户续期/管理员归档）
#   conflict   → published / archived            （管理员裁定后恢复/归档）
#   archived   → （终态，不可流转）
#
# FND-03.2 说明：
#   - published → pending 仅用于「已发布帖子被作者实质修改后自动回审」场景，
#     由 update_post API 在检测到实质字段变更时通过状态机服务触发，禁止其他路径直接写入。
#   - 删除走 is_deleted=True + 任意非终态 → archived（由状态机校验），
#     不引入第 7 种 deleted 状态。
_TRANSITIONS: dict = {
    PostStatus.DRAFT:     {PostStatus.PENDING, PostStatus.ARCHIVED},
    PostStatus.PENDING:   {PostStatus.PUBLISHED, PostStatus.DRAFT, PostStatus.ARCHIVED},
    PostStatus.PUBLISHED: {PostStatus.PENDING, PostStatus.EXPIRED, PostStatus.CONFLICT, PostStatus.ARCHIVED},
    PostStatus.EXPIRED:   {PostStatus.PUBLISHED, PostStatus.ARCHIVED},
    PostStatus.CONFLICT:  {PostStatus.PUBLISHED, PostStatus.ARCHIVED},
    PostStatus.ARCHIVED:  set(),  # 终态
}


# FND-03.2: 实质修改字段集合——已发布帖子修改这些字段时必须回 pending 重新审核
# 不含：expire_at（信息截止时间修正不回审）、
#       contact_info（联系方式更新不回审）、is_anonymous（可由作者随时切换）、
#       image_urls（附属数据，不改变信息主体语义）
# Task 1.2 调整：post_type_id 已随 PostType 模型删除移除
# Task 1.3 调整：tags 已随 Tag 模型删除移除
# Task 1.4 调整：activity_start_at / activity_end_at 已随活动时间字段移除
SUBSTANTIAL_FIELDS: frozenset = frozenset({
    "title", "content", "category_id",
    "location_id", "location_name", "location_lat", "location_lng",
    "lost_type",
})


def is_substantial_change(changed_fields: set) -> bool:
    """判断字段变更集合是否包含实质修改（需要回审）

    Args:
        changed_fields: 已发生变更的字段名集合

    Returns:
        True 若包含任一实质字段
    """
    return bool(changed_fields & SUBSTANTIAL_FIELDS)


def normalize_status(status: str) -> str:
    """将状态值归一化为正式名（别名 → 正式名）

    Args:
        status: 原始状态值，可能为别名（如 "pending_review"）

    Returns:
        归一化后的正式状态名（如 "pending"）；未知值原样返回
    """
    return PostStatus.ALIASES.get(status, status)


def is_valid_status(status: str) -> bool:
    """判断状态值是否有效（含别名）

    Args:
        status: 待判断的状态值

    Returns:
        True 若 status 为 6 态之一或已知别名
    """
    return status in PostStatus.ALL or status in PostStatus.ALIASES


def can_transition(current: str, target: str) -> bool:
    """判断状态流转是否合法

    Args:
        current: 当前状态（接受别名）
        target: 目标状态（接受别名）

    Returns:
        True 若 current → target 流转合法；若 current 为未知状态返回 False

    Examples:
        >>> can_transition("draft", "pending")
        True
        >>> can_transition("archived", "draft")
        False
        >>> can_transition("pending_review", "published")  # 别名
        True
    """
    current = normalize_status(current)
    target = normalize_status(target)
    return target in _TRANSITIONS.get(current, set())


def get_allowed_transitions(current: str) -> Set[str]:
    """获取当前状态可流转的目标状态集合

    Args:
        current: 当前状态（接受别名）

    Returns:
        可流转目标状态的集合；未知状态返回空集
    """
    current = normalize_status(current)
    return _TRANSITIONS.get(current, set()).copy()
