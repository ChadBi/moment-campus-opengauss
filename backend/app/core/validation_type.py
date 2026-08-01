"""协同验证类型唯一契约。"""
from typing import Set


class ValidationType:
    """协同验证类型常量

    所有值长度 <= 20，与数据库 validation_type 字段 String(20) 对应。
    """

    # === 2 类互斥投票（validation_records 表当前处理） ===
    CONFIRMATION = "confirmation"            # 证实
    REFUTATION = "refutation"                # 证伪

    ALL: tuple = (
        CONFIRMATION,
        REFUTATION,
    )


def normalize_validation_type(vtype: str) -> str:
    """验证并返回正式类型，不再兼容历史别名。"""
    if vtype not in ValidationType.ALL:
        raise ValueError(f"unsupported validation type: {vtype}")
    return vtype


def is_valid_validation_type(vtype: str) -> bool:
    """判断验证类型是否为两个正式值之一。"""
    return vtype in ValidationType.ALL


def get_canonical_types() -> Set[str]:
    """获取全部 2 类正式类型（不含别名）"""
    return set(ValidationType.ALL)
