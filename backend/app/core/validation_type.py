"""协同验证类型定义（FND-01 扩展版）

5 类协同验证类型（FND-01.1 契约）：
- confirmation: 证实（用户确认信息真实有效）—— 互斥投票
- refutation: 证伪（用户指出信息有误）—— 互斥投票
- update: 更新建议（提供更新信息）—— 问题报告
- expiration_report: 过期报告（报告信息已过期）—— 问题报告
- conflict_report: 冲突报告（报告与其他信息冲突）—— 问题报告

当前运行逻辑（FND-01 阶段）：
- validation_records 表只处理 confirmation/refutation（2 类互斥投票）
- update/expiration_report/conflict_report 的完整语义由 GOV-01 实现（新增 post_change_reports 表）
- schema 层（app/schemas/enums.py ValidationTypeEnum）已定义完整 5 类供前端契约使用

向后兼容映射：
- valid       → confirmation
- invalid     → refutation
- uncertain   → 原样保留（历史废弃值，不接受新提交）
"""
from typing import Set


class ValidationType:
    """协同验证类型常量

    所有值长度 <= 20，与数据库 validation_type 字段 String(20) 对应。
    """

    # === 2 类互斥投票（validation_records 表当前处理） ===
    CONFIRMATION = "confirmation"            # 证实
    REFUTATION = "refutation"                # 证伪

    # === 3 类问题报告（GOV-01 将新增 post_change_reports 表承载） ===
    UPDATE = "update"                        # 更新建议
    EXPIRATION_REPORT = "expiration_report"  # 过期报告
    CONFLICT_REPORT = "conflict_report"      # 冲突报告

    # 当前 validation_records 表处理的正式类型（2 类互斥投票）
    ALL: tuple = (
        CONFIRMATION,
        REFUTATION,
    )

    # 完整 5 类正式类型（FND-01.1 契约；供 schema 层与 GOV-01 使用）
    ALL_FIVE: tuple = (
        CONFIRMATION,
        REFUTATION,
        UPDATE,
        EXPIRATION_REPORT,
        CONFLICT_REPORT,
    )

    # 3 类问题报告类型（GOV-01 将启用）
    REPORT_TYPES: tuple = (
        UPDATE,
        EXPIRATION_REPORT,
        CONFLICT_REPORT,
    )

    # 别名映射：旧值 → 正式名（向后兼容）
    # - valid     → confirmation（证实信息有效）
    # - invalid   → refutation（证伪信息有误）
    ALIASES: dict = {
        "valid": CONFIRMATION,
        "invalid": REFUTATION,
    }

    # 旧 3 类正向统计字段映射（用于兼容 Post 模型的 valid_count/invalid_count）
    # - confirmation → valid_count
    # - refutation   → invalid_count
    LEGACY_POSITIVE_COUNT_TYPES: Set[str] = {CONFIRMATION}
    LEGACY_NEGATIVE_COUNT_TYPES: Set[str] = {REFUTATION}


def normalize_validation_type(vtype: str) -> str:
    """将验证类型归一化为正式名（别名 → 正式名）

    Args:
        vtype: 原始类型值，可能为别名（如 "valid"）

    Returns:
        归一化后的正式类型名；未知值原样返回
    """
    return ValidationType.ALIASES.get(vtype, vtype)


def is_valid_validation_type(vtype: str) -> bool:
    """判断验证类型是否有效（含别名）

    Args:
        vtype: 待判断的类型值

    Returns:
        True 若 vtype 为 2 类之一或已知别名
    """
    return vtype in ValidationType.ALL or vtype in ValidationType.ALIASES


def get_canonical_types() -> Set[str]:
    """获取全部 2 类正式类型（不含别名）"""
    return set(ValidationType.ALL)
