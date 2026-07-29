"""共享枚举定义（FND-01.1）

集中定义跨 schema 复用的关键枚举，确保前后端契约一致：
- ReportType：举报类型（5 类）
- PostStatusEnum：帖子状态（6 态）
- ValidationTypeEnum：协同验证类型（5 类）

所有枚举继承 (str, Enum)，Pydantic v2 原生支持，OpenAPI 自动生成 enum 值。
"""
from enum import Enum


class ReportType(str, Enum):
    """举报类型（6 类）"""
    SPAM = "spam"                  # 垃圾信息
    ABUSE = "abuse"                # 滥用
    HARASSMENT = "harassment"      # 骚扰
    FALSE_INFO = "false_info"      # 虚假信息
    EXPIRED_INFO = "expired_info"  # 信息过期
    OTHER = "other"                # 其他


class PostStatusEnum(str, Enum):
    """帖子状态（6 态状态机）

    依据 app/core/post_status.py PostStatus：
    draft / pending / published / expired / conflict / archived
    """
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    EXPIRED = "expired"
    CONFLICT = "conflict"
    ARCHIVED = "archived"


class ValidationTypeEnum(str, Enum):
    """协同验证类型（5 类）

    - confirmation / refutation：互斥投票（validation_records 表，2 类）
    - update / expiration_report / conflict_report：问题报告（GOV-01 将新增 post_change_reports 表）

    FND-01 阶段在 schema 层定义完整 5 类枚举供 GOV-01 使用；
    当前 validation_record 表逻辑仍只处理 confirmation/refutation（2 类）。
    """
    CONFIRMATION = "confirmation"            # 证实
    REFUTATION = "refutation"                # 证伪
    UPDATE = "update"                        # 更新建议
    EXPIRATION_REPORT = "expiration_report"  # 过期报告
    CONFLICT_REPORT = "conflict_report"      # 冲突报告
